"""Asynchronous client for HyperHDR's JSON API over its WebSocket.

One connection carries everything: requests (matched to their reply by
`tan`), the updates HyperHDR pushes after a `serverinfo` subscription, and
the binary JPEG frames of the image stream. Nothing is polled.

This module has no Home Assistant dependency, so it can be tested against a
real HyperHDR server.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8090
DEFAULT_TIMEOUT = 10.0

#: Subscriptions that keep an instance's state up to date.
STATE_SUBSCRIPTIONS = [
    "components-update",
    "priorities-update",
    "adjustment-update",
    "videomodehdr-update",
    "imageToLedMapping-update",
    "grabberstate-update",
    "instance-update",
]
#: Needs admin rights: every settings change, pushed.
SETTINGS_SUBSCRIPTION = "settings-update"
PERFORMANCE_SUBSCRIPTION = "performance-update"

MessageListener = Callable[[dict[str, Any]], None]
ImageListener = Callable[[bytes], None]


class HyperHDRError(Exception):
    """Base error."""


class HyperHDRConnectionError(HyperHDRError):
    """The server cannot be reached, or the connection dropped."""


class HyperHDRAuthError(HyperHDRError):
    """The password is refused."""


class HyperHDRBlockedError(HyperHDRConnectionError):
    """Too many refused logins: HyperHDR refuses every login for 10 minutes."""


class HyperHDRCommandError(HyperHDRError):
    """HyperHDR answered a command with an error."""

    def __init__(self, command: str, error: str) -> None:
        super().__init__(f"{command}: {error}")
        self.command = command
        self.error = error


class HyperHDRClient:
    """A WebSocket connection to one HyperHDR server, bound to one instance."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        session: aiohttp.ClientSession,
        password: str | None = None,
        instance: int = 0,
        ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.instance = instance
        #: The admin password, sent at every connection: the token HyperHDR
        #: gives for it changes each time HyperHDR starts, so it is not kept.
        self.password = password
        self._session = session
        self._ssl = ssl
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reader: asyncio.Task[None] | None = None
        self._tans = itertools.count(1)
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        #: Commands whose replies are streams: their `tan` keeps coming back.
        self._stream_tans: set[int] = set()
        self._listeners: list[MessageListener] = []
        self._image_listeners: list[ImageListener] = []
        self._disconnect_listeners: list[Callable[[], None]] = []
        self.admin = False

    @property
    def url(self) -> str:
        return f"{'wss' if self._ssl else 'ws'}://{self.host}:{self.port}/"

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    # ------------------------------------------------------------------ setup

    async def connect(self) -> None:
        """Opens the connection, logs in with the password if any, selects the instance."""
        try:
            self._ws = await self._session.ws_connect(
                self.url, heartbeat=30, max_msg_size=0, timeout=aiohttp.ClientWSTimeout(ws_close=5)
            )
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise HyperHDRConnectionError(f"Cannot connect to {self.url}: {err}") from err
        self._reader = asyncio.create_task(self._read(), name=f"hyperhdr-{self.host}-{self.instance}")
        try:
            self.admin = False
            if self.password:
                await self.login(self.password)
            if self.instance:
                await self.request("instance", subcommand="switchTo", instance=self.instance)
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        reader, self._reader = self._reader, None
        ws, self._ws = self._ws, None
        if ws is not None and not ws.closed:
            with contextlib.suppress(Exception):
                await ws.close()
        if ws is not None:
            await asyncio.sleep(0)
            _stop_heartbeat(ws)
        if reader is not None and reader is not asyncio.current_task():
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await reader
        self._fail_pending(HyperHDRConnectionError("Connection closed"))

    async def login(self, password: str) -> None:
        """Logs in with the admin password, for this connection only.

        HyperHDR answers with a user token, but makes a new one each time it
        starts: the password is what is kept, and sent again on reconnection.
        """
        try:
            await self.request("authorize", subcommand="login", password=password)
        except HyperHDRCommandError as err:
            if "too many" in err.error.lower():
                raise HyperHDRBlockedError(err.error) from err
            raise HyperHDRAuthError(err.error) from err
        self.admin = True

    # --------------------------------------------------------------- listeners

    def add_listener(self, listener: MessageListener) -> Callable[[], None]:
        """Pushed updates (`components-update`, …). Returns a remover."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def add_image_listener(self, listener: ImageListener) -> Callable[[], None]:
        self._image_listeners.append(listener)
        return lambda: self._image_listeners.remove(listener)

    def add_disconnect_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._disconnect_listeners.append(listener)
        return lambda: self._disconnect_listeners.remove(listener)

    # ---------------------------------------------------------------- requests

    async def request(
        self,
        command: str,
        *,
        subcommand: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        stream: bool = False,
        **params: Any,
    ) -> dict[str, Any]:
        """Sends a command and waits for its reply. Raises on an error reply."""
        ws = self._ws
        if ws is None or ws.closed:
            raise HyperHDRConnectionError("Not connected")
        tan = next(self._tans)
        message: dict[str, Any] = {"command": command, "tan": tan, **params}
        if subcommand is not None:
            message["subcommand"] = subcommand
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[tan] = future
        if stream:
            self._stream_tans.add(tan)
        try:
            await ws.send_str(json.dumps(message, separators=(",", ":")))
            reply = await asyncio.wait_for(future, timeout)
        except TimeoutError as err:
            raise HyperHDRConnectionError(f"No reply to {command}") from err
        except (aiohttp.ClientError, ConnectionResetError, RuntimeError) as err:
            raise HyperHDRConnectionError(str(err)) from err
        finally:
            self._pending.pop(tan, None)
        if not reply.get("success", False):
            raise HyperHDRCommandError(command, str(reply.get("error", "unknown error")))
        return reply

    async def server_info(self, subscribe: list[str] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"subscribe": subscribe} if subscribe else {}
        reply = await self.request("serverinfo", **params)
        return reply.get("info") or {}

    async def subscribe(self, subscriptions: list[str]) -> None:
        """Subscriptions that bring no state (performance) are sent on their own."""
        await self.request("serverinfo", subscribe=subscriptions)

    async def performance_counters(self) -> None:
        """Asks for the host's CPU, memory, temperature and undervoltage.

        HyperHDR measures them only when asked (its web interface asks every
        second); they come back as `performance-update` messages.
        """
        await self.request("performance-counters", subcommand="resources")

    async def sys_info(self) -> dict[str, Any]:
        return (await self.request("sysinfo")).get("info") or {}

    async def get_config(self) -> dict[str, Any]:
        return (await self.request("config", subcommand="getconfig", timeout=20)).get("info") or {}

    async def get_schema(self) -> dict[str, Any]:
        return (await self.request("config", subcommand="getschema", timeout=20)).get("info") or {}

    async def set_config(self, config: dict[str, Any]) -> None:
        """Writes settings; a section may be partial (HyperHDR merges it)."""
        await self.request("config", subcommand="setconfig", config=config, timeout=20)

    async def set_component(self, component: str, state: bool) -> None:
        await self.request("componentstate", componentstate={"component": component, "state": state})

    async def set_adjustment(self, **values: Any) -> None:
        await self.request("adjustment", adjustment=values)

    async def set_hdr(self, enabled: bool) -> None:
        await self.request("videomodehdr", HDR=1 if enabled else 0)

    async def set_color(
        self, rgb: tuple[int, int, int], priority: int, duration: int | None = None, origin: str = "Home Assistant"
    ) -> None:
        params: dict[str, Any] = {"color": list(rgb), "priority": priority, "origin": origin}
        if duration:
            params["duration"] = duration
        await self.request("color", **params)

    async def set_effect(
        self, name: str, priority: int, duration: int | None = None, origin: str = "Home Assistant"
    ) -> None:
        params: dict[str, Any] = {"effect": {"name": name}, "priority": priority, "origin": origin}
        if duration:
            params["duration"] = duration
        await self.request("effect", **params)

    async def clear(self, priority: int) -> None:
        await self.request("clear", priority=priority)

    async def clear_all(self) -> None:
        await self.request("clearall")

    async def source_select(self, priority: int | None) -> None:
        if priority is None:
            await self.request("sourceselect", auto=True)
        else:
            await self.request("sourceselect", priority=priority)

    async def set_video_mode(self, mode: str) -> None:
        await self.request("videomode", videoMode=mode)

    async def set_mapping(self, mapping: str) -> None:
        await self.request("processing", mappingType=mapping)

    async def average_color(self) -> dict[str, int]:
        reply = await self.request("current-state", subcommand="average-color", instance=self.instance)
        return reply.get("info") or {}

    async def image_stream(self, start: bool) -> None:
        await self.request("ledcolors", subcommand="imagestream-start" if start else "imagestream-stop")

    async def led_stream(self, start: bool, interval: int = 200) -> None:
        if start:
            await self.request("ledcolors", subcommand="ledstream-start", interval=max(50, interval), stream=True)
        else:
            await self.request("ledcolors", subcommand="ledstream-stop")

    async def backup(self) -> dict[str, Any]:
        return (await self.request("save-db", timeout=30)).get("info") or {}

    # ------------------------------------------------------------------ reader

    async def _read(self) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            async for message in ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    self._handle_text(message.data)
                elif message.type == aiohttp.WSMsgType.BINARY:
                    for listener in list(self._image_listeners):
                        listener(message.data)
                elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except (aiohttp.ClientError, ConnectionResetError) as err:
            _LOGGER.debug("Connection to %s lost: %s", self.url, err)
        finally:
            _stop_heartbeat(ws)
            self._fail_pending(HyperHDRConnectionError("Connection lost"))
            if self._ws is ws:
                self._ws = None
                for listener in list(self._disconnect_listeners):
                    listener()

    def _handle_text(self, data: str) -> None:
        try:
            message = json.loads(data)
        except ValueError:
            _LOGGER.debug("Unreadable message from %s: %.200s", self.url, data)
            return
        if not isinstance(message, dict):
            return
        tan = message.get("tan")
        command = str(message.get("command", ""))
        # Stream updates repeat the tan of the request that started them.
        is_update = "data" in message or command.endswith("-update")
        if isinstance(tan, int) and not is_update:
            future = self._pending.get(tan)
            if future is not None and not future.done():
                future.set_result(message)
            if tan not in self._stream_tans:
                return
        if is_update or "result" in message:
            for listener in list(self._listeners):
                try:
                    listener(message)
                except Exception:
                    _LOGGER.exception("Error handling %s", command)

    def _fail_pending(self, error: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()


def _stop_heartbeat(ws: aiohttp.ClientWebSocketResponse) -> None:
    """aiohttp can re-arm its heartbeat after a close while data was still
    arriving; a closed connection must leave no timer behind."""
    if hasattr(ws, "_heartbeat"):
        ws._heartbeat = None  # nothing re-arms it any more
    cancel = getattr(ws, "_cancel_heartbeat", None)
    if callable(cancel):
        cancel()
