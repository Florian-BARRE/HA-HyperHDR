"""Turning HyperHDR's machine off (or restarting it) cleanly, over SSH.

HyperHDR's API has no system command, so the integration logs in over SSH
with the machine's own user (the one set in Raspberry Pi Imager) and runs
`sudo systemctl poweroff`. Nothing is installed on the machine: SSH is enough.
The password is also handed to sudo, which works whether or not sudo asks for
it. The host key is learnt when SSH is set up, and checked afterwards.

No Home Assistant dependency here, so it can be tested against a real server.
"""

from __future__ import annotations

import logging
import shlex
from typing import Literal

import asyncssh

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22
CONNECT_TIMEOUT = 10
COMMAND_TIMEOUT = 20

PowerAction = Literal["poweroff", "reboot"]

#: Ran with sudo; `-S` reads the password on stdin, `-p ''` keeps the prompt quiet.
SUDO = "sudo -S -p '' "
COMMANDS: dict[PowerAction, str] = {
    "poweroff": "systemctl poweroff",
    "reboot": "systemctl reboot",
}
#: Checks the login and sudo without changing anything.
CHECK = "true"


class SSHError(Exception):
    """Base error."""


class SSHConnectionError(SSHError):
    """The machine cannot be reached over SSH."""


class SSHAuthError(SSHError):
    """The user or the password is refused."""


class SSHHostKeyError(SSHError):
    """The machine's key is not the one learnt: reinstalled, or another machine."""


class SSHSudoError(SSHError):
    """Logged in, but sudo refused (the user may not use sudo)."""


def _known_hosts(host_key: str | None) -> tuple[list[asyncssh.SSHKey], list, list] | None:
    if not host_key:
        return None
    return ([asyncssh.import_public_key(host_key)], [], [])


async def _connect(
    host: str, port: int, username: str, password: str, host_key: str | None
) -> asyncssh.SSHClientConnection:
    try:
        return await asyncssh.connect(
            host,
            port=port,
            username=username,
            password=password,
            known_hosts=_known_hosts(host_key),
            # Only this password: no key from Home Assistant's machine, no agent.
            client_keys=None,
            agent_path=None,
            preferred_auth=["password", "keyboard-interactive"],
            connect_timeout=CONNECT_TIMEOUT,
        )
    except asyncssh.PermissionDenied as err:
        raise SSHAuthError(str(err)) from err
    except asyncssh.HostKeyNotVerifiable as err:
        raise SSHHostKeyError(str(err)) from err
    except (OSError, TimeoutError, asyncssh.Error) as err:
        raise SSHConnectionError(str(err)) from err


async def _sudo(conn: asyncssh.SSHClientConnection, command: str, password: str) -> None:
    try:
        result = await conn.run(SUDO + command, input=password + "\n", timeout=COMMAND_TIMEOUT, check=False)
    except asyncssh.ProcessError as err:
        raise SSHSudoError(str(err)) from err
    if result.exit_status not in (0, None):
        error = str(result.stderr or result.stdout or "").strip()
        raise SSHSudoError(error or f"exit status {result.exit_status}")


async def check(host: str, port: int, username: str, password: str, host_key: str | None = None) -> str:
    """Logs in and runs a harmless sudo; returns the machine's host key to keep."""
    conn = await _connect(host, port, username, password, host_key)
    try:
        await _sudo(conn, CHECK, password)
        key = conn.get_server_host_key()
        if key is None:
            raise SSHConnectionError("No host key")
        return key.export_public_key("openssh").decode().strip()
    finally:
        conn.close()
        await conn.wait_closed()


async def power(action: PowerAction, host: str, port: int, username: str, password: str, host_key: str | None) -> None:
    """Asks the machine to power off or reboot.

    The machine closing the connection while doing it is the expected end,
    not an error.
    """
    conn = await _connect(host, port, username, password, host_key)
    try:
        await _sudo(conn, COMMANDS[action], password)
    except SSHSudoError:
        raise
    except (OSError, asyncssh.Error) as err:
        # Dropped by the machine going down.
        _LOGGER.debug("SSH connection to %s closed during %s: %s", host, action, err)
    finally:
        conn.close()
    _LOGGER.info("Asked %s to %s (%s)", host, action, shlex.quote(COMMANDS[action]))
