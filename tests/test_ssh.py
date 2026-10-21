"""SSH power off, against an SSH server run by the test (asyncssh)."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

import asyncssh
import pytest

from custom_components.ha_hyperhdr.ssh import (
    SSHAuthError,
    SSHConnectionError,
    SSHHostKeyError,
    SSHSudoError,
    check,
    power,
)

pytestmark = pytest.mark.usefixtures("socket_enabled")

USER = "pi"
PASSWORD = "raspberry-pass"


@dataclass
class FakeMachine:
    """What the fake machine was asked, and how its sudo behaves."""

    sudo_needs_password: bool = True
    user_may_sudo: bool = True
    commands: list[str] = field(default_factory=list)
    sudo_inputs: list[str] = field(default_factory=list)


@pytest.fixture
async def machine():
    state = FakeMachine()
    key = asyncssh.generate_private_key("ssh-ed25519")

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username: str) -> bool:
            return True

        def password_auth_supported(self) -> bool:
            return True

        def validate_password(self, username: str, password: str) -> bool:
            return username == USER and password == PASSWORD

    async def handle(process: asyncssh.SSHServerProcess) -> None:
        command = process.command or ""
        state.commands.append(command)
        prefix = "sudo -S -p '' "
        if not command.startswith(prefix):
            process.exit(127)
            return
        if state.sudo_needs_password:
            line = await process.stdin.readline()
            state.sudo_inputs.append(line)
            if line.strip() != PASSWORD:
                process.stderr.write("Sorry, try again.\n")
                process.exit(1)
                return
        if not state.user_may_sudo:
            process.stderr.write(f"{USER} is not in the sudoers file.\n")
            process.exit(1)
            return
        target = command[len(prefix) :]
        if target in ("systemctl poweroff", "systemctl reboot"):
            # The machine goes down: the connection drops without an exit status.
            process.channel.get_connection().abort()
            return
        process.exit(0)

    server = await asyncssh.create_server(Server, "127.0.0.1", 0, server_host_keys=[key], process_factory=handle)
    port = server.sockets[0].getsockname()[1]
    state.port = port  # type: ignore[attr-defined]
    state.public_key = key.export_public_key("openssh").decode().strip()  # type: ignore[attr-defined]
    yield state
    server.close()
    await server.wait_closed()


async def test_check_learns_the_host_key(machine) -> None:
    key = await check("127.0.0.1", machine.port, USER, PASSWORD)
    assert key == machine.public_key
    # A harmless command, with the password handed to sudo.
    assert machine.commands == ["sudo -S -p '' true"]
    assert machine.sudo_inputs == [PASSWORD + "\n"]


async def test_power_off(machine) -> None:
    await power("poweroff", "127.0.0.1", machine.port, USER, PASSWORD, machine.public_key)
    assert machine.commands == ["sudo -S -p '' systemctl poweroff"]


async def test_reboot(machine) -> None:
    await power("reboot", "127.0.0.1", machine.port, USER, PASSWORD, machine.public_key)
    assert machine.commands == ["sudo -S -p '' systemctl reboot"]


async def test_sudo_without_password(machine) -> None:
    """Raspberry Pi OS's first user may sudo without a password: same command."""
    machine.sudo_needs_password = False
    await power("poweroff", "127.0.0.1", machine.port, USER, PASSWORD, machine.public_key)
    assert machine.commands == ["sudo -S -p '' systemctl poweroff"]


async def test_wrong_password(machine) -> None:
    with pytest.raises(SSHAuthError):
        await check("127.0.0.1", machine.port, USER, "wrong")


async def test_user_without_sudo(machine) -> None:
    machine.user_may_sudo = False
    with pytest.raises(SSHSudoError, match="sudoers"):
        await check("127.0.0.1", machine.port, USER, PASSWORD)
    with pytest.raises(SSHSudoError):
        await power("poweroff", "127.0.0.1", machine.port, USER, PASSWORD, machine.public_key)


async def test_other_host_key_is_refused(machine) -> None:
    other = asyncssh.generate_private_key("ssh-ed25519").export_public_key("openssh").decode()
    with pytest.raises(SSHHostKeyError):
        await power("poweroff", "127.0.0.1", machine.port, USER, PASSWORD, other)
    assert machine.commands == []


async def test_machine_off() -> None:
    # Nothing listens there: the machine is off.
    with pytest.raises(SSHConnectionError):
        await asyncio.wait_for(check("127.0.0.1", 1, USER, PASSWORD), 15)


# ---------------------------------------------------------------- real OpenSSH

LIVE_SSH = os.environ.get("SSH_TEST_HOST")
live_ssh = pytest.mark.skipif(LIVE_SSH is None, reason="SSH_TEST_HOST is not set (scripts/ssh-test-host.sh)")
LIVE_PORT = int(os.environ.get("SSH_TEST_PORT", "2222"))
LIVE_USER = os.environ.get("SSH_TEST_USER", "hhpi")
LIVE_PASSWORD = os.environ.get("SSH_TEST_PASSWORD", "hh-pass-1234")
LIVE_LOG = os.environ.get("SSH_TEST_LOG", "/tmp/hh-systemctl.log")


def _reset_log() -> None:
    open(LIVE_LOG, "w").close()


def _asked() -> list[str]:
    with open(LIVE_LOG, encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


@live_ssh
async def test_real_openssh_and_sudo_with_password() -> None:
    """A real sshd and a real sudo that asks for the user's password."""
    _reset_log()
    key = await check(LIVE_SSH, LIVE_PORT, LIVE_USER, LIVE_PASSWORD)
    assert key.startswith("ssh-")
    await power("poweroff", LIVE_SSH, LIVE_PORT, LIVE_USER, LIVE_PASSWORD, key)
    assert _asked() == ["poweroff"]
    await power("reboot", LIVE_SSH, LIVE_PORT, LIVE_USER, LIVE_PASSWORD, key)
    assert _asked() == ["poweroff", "reboot"]


@live_ssh
async def test_real_openssh_wrong_password() -> None:
    with pytest.raises(SSHAuthError):
        await check(LIVE_SSH, LIVE_PORT, LIVE_USER, "wrong-password")
