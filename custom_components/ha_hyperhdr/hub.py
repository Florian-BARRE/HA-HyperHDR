"""Connections to a HyperHDR server, one per running instance.

Each connection keeps its instance's state from HyperHDR's pushed updates and
hands it to a push-only coordinator: entities update when HyperHDR says
something changed, never on a timer. The connection of the first instance
also carries the server-wide state (host health, grabber, instances).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PERFORMANCE_SUBSCRIPTION,
    SETTINGS_SUBSCRIPTION,
    STATE_SUBSCRIPTIONS,
    HyperHDRAuthError,
    HyperHDRClient,
    HyperHDRError,
)
from .const import (
    CONF_LED_INTERVAL,
    CONF_PERFORMANCE,
    CONF_PRIORITY,
    CONF_STREAM_FPS,
    CONF_USE_SSL,
    DEFAULT_LED_INTERVAL,
    DEFAULT_PRIORITY,
    DEFAULT_STREAM_FPS,
    DOMAIN,
    RECONNECT_DELAYS,
)
from .state import InstanceState, ServerState

_LOGGER = logging.getLogger(__name__)

type HyperHDRConfigEntry = ConfigEntry[HyperHDRHub]


class _Stream:
    """A stream started on demand and stopped when its last viewer leaves."""

    def __init__(self, start: Callable[[], Any], stop: Callable[[], Any]) -> None:
        self._start = start
        self._stop = stop
        self._users = 0
        self._lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        return self._users > 0

    async def acquire(self) -> None:
        async with self._lock:
            self._users += 1
            if self._users == 1:
                try:
                    await self._start()
                except HyperHDRError:
                    self._users -= 1
                    raise

    async def release(self) -> None:
        async with self._lock:
            if self._users == 0:
                return
            self._users -= 1
            if self._users == 0:
                with contextlib.suppress(HyperHDRError):
                    await self._stop()

    async def restart(self) -> None:
        """After a reconnection: the server forgot the stream."""
        if self._users:
            with contextlib.suppress(HyperHDRError):
                await self._start()


class InstanceConnection:
    """One instance: its client, its state, its coordinator, its reconnections."""

    def __init__(self, hub: HyperHDRHub, index: int, name: str) -> None:
        self.hub = hub
        self.index = index
        self.state = InstanceState(index=index, name=name)
        self.client = HyperHDRClient(
            hub.host,
            hub.port,
            session=hub.session,
            token=hub.token,
            instance=index,
            ssl=hub.use_ssl,
        )
        self.coordinator: DataUpdateCoordinator[InstanceState] = DataUpdateCoordinator(
            hub.hass,
            _LOGGER,
            config_entry=hub.entry,
            name=f"{DOMAIN} {hub.host} instance {index}",
        )
        self._reconnect: asyncio.Task[None] | None = None
        self._closing = False
        self._led_listeners: list[Callable[[list[int]], None]] = []
        self.led_stream = _Stream(
            lambda: self.client.led_stream(True, hub.led_interval),
            lambda: self.client.led_stream(False),
        )
        self.client.add_listener(self._on_message)
        self.client.add_disconnect_listener(self._on_disconnect)

    @property
    def primary(self) -> bool:
        return self is self.hub.primary

    async def start(self) -> None:
        """First connection; raises so that the setup can retry or reauth."""
        await self.client.connect()
        await self._load()

    async def stop(self) -> None:
        self._closing = True
        if self._reconnect:
            self._reconnect.cancel()
        await self.client.close()

    async def _load(self) -> None:
        """Full state after a (re)connection, then the pushed updates."""
        client = self.client
        subscriptions = list(STATE_SUBSCRIPTIONS)
        if client.admin:
            subscriptions.append(SETTINGS_SUBSCRIPTION)
        info = await client.server_info(subscriptions)
        self.state.load(info)
        if self.primary:
            self.hub.server.load(info)
        if client.admin:
            settings = await client.get_config()
            self.state.settings = settings
            if self.primary:
                self.hub.server.settings = dict(settings)
        if self.primary and self.hub.performance:
            await client.subscribe([PERFORMANCE_SUBSCRIPTION])
        await self.led_stream.restart()
        if self.primary:
            await self.hub.image_stream.restart()
        self.coordinator.async_set_updated_data(self.state)
        if self.primary:
            self.hub.server_coordinator.async_set_updated_data(self.hub.server)

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("command") == "ledcolors-ledstream-update":
            if self.state.apply(message):
                for listener in list(self._led_listeners):
                    listener(self.state.led_colors)
            return
        changed = self.state.apply(message)
        if self.primary and self.hub.server.apply(message):
            self.hub.server_coordinator.async_set_updated_data(self.hub.server)
            if message.get("command") == "instance-update":
                self.hub.instances_changed()
        if changed:
            self.coordinator.async_set_updated_data(self.state)

    def add_led_listener(self, listener: Callable[[list[int]], None]) -> Callable[[], None]:
        self._led_listeners.append(listener)
        return lambda: self._led_listeners.remove(listener)

    @callback
    def _on_disconnect(self) -> None:
        if self._closing:
            return
        _LOGGER.info("Connection to HyperHDR %s (instance %s) lost", self.hub.host, self.index)
        self.coordinator.async_set_update_error(UpdateFailed("Connection lost"))
        if self.primary:
            self.hub.server_coordinator.async_set_update_error(UpdateFailed("Connection lost"))
        if self._reconnect is None or self._reconnect.done():
            self._reconnect = self.hub.entry.async_create_background_task(
                self.hub.hass, self._reconnect_loop(), f"{DOMAIN} reconnect {self.index}"
            )

    async def _reconnect_loop(self) -> None:
        attempt = 0
        while not self._closing:
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            await asyncio.sleep(delay)
            try:
                await self.client.connect()
                await self._load()
            except HyperHDRAuthError:
                _LOGGER.warning("HyperHDR %s refused the stored credentials", self.hub.host)
                self.hub.entry.async_start_reauth(self.hub.hass)
                return
            except HyperHDRError as err:
                attempt += 1
                _LOGGER.debug("Reconnecting to %s failed: %s", self.hub.host, err)
                await self.client.close()
                continue
            _LOGGER.info("Reconnected to HyperHDR %s (instance %s)", self.hub.host, self.index)
            return


class HyperHDRHub:
    """Everything the integration keeps for one HyperHDR server."""

    def __init__(self, hass: HomeAssistant, entry: HyperHDRConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.host: str = entry.data[CONF_HOST]
        self.port: int = entry.data[CONF_PORT]
        self.token: str | None = entry.data.get(CONF_TOKEN)
        self.use_ssl: bool = entry.data.get(CONF_USE_SSL, False)
        self.session = async_get_clientsession(hass, verify_ssl=False)
        self.server = ServerState()
        self.server_coordinator: DataUpdateCoordinator[ServerState] = DataUpdateCoordinator(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {self.host} server"
        )
        self.instances: dict[int, InstanceConnection] = {}
        self.primary: InstanceConnection | None = None
        self.schema: dict[str, Any] = {}
        self.image_stream = _Stream(self._start_images, self._stop_images)
        self.server_device_id: str | None = None

    # ------------------------------------------------------------------ options

    @property
    def priority(self) -> int:
        return int(self.entry.options.get(CONF_PRIORITY, DEFAULT_PRIORITY))

    @property
    def performance(self) -> bool:
        return bool(self.entry.options.get(CONF_PERFORMANCE, True))

    @property
    def stream_fps(self) -> int:
        return int(self.entry.options.get(CONF_STREAM_FPS, DEFAULT_STREAM_FPS))

    @property
    def led_interval(self) -> int:
        return int(self.entry.options.get(CONF_LED_INTERVAL, DEFAULT_LED_INTERVAL))

    @property
    def admin(self) -> bool:
        return bool(self.primary and self.primary.client.admin)

    @property
    def server_id(self) -> str:
        return self.entry.unique_id or self.server.id or self.host

    # -------------------------------------------------------------------- setup

    async def async_setup(self) -> None:
        primary = InstanceConnection(self, 0, "")
        self.primary = primary
        try:
            await primary.client.connect()
            self.server.load_sysinfo(await primary.client.sys_info())
            await primary._load()
            if primary.client.admin:
                self.schema = await primary.client.get_schema()
        except HyperHDRAuthError as err:
            await primary.stop()
            raise ConfigEntryAuthFailed(str(err)) from err
        except HyperHDRError as err:
            await primary.stop()
            raise ConfigEntryNotReady(str(err)) from err
        self.instances[0] = primary
        for index, (name, running) in sorted(self.server.instances.items()):
            if index == 0:
                primary.state.name = name
                continue
            if not running:
                continue
            connection = InstanceConnection(self, index, name)
            try:
                await connection.start()
            except HyperHDRError as err:
                _LOGGER.warning("Instance %s of %s is not reachable: %s", index, self.host, err)
                await connection.stop()
                continue
            self.instances[index] = connection
        self._running = self._running_instances()

    async def async_shutdown(self) -> None:
        for connection in self.instances.values():
            await connection.stop()
        self.instances.clear()

    def _running_instances(self) -> set[int]:
        return {index for index, (_, running) in self.server.instances.items() if running}

    @callback
    def instances_changed(self) -> None:
        """An instance was created, started or stopped: reload to follow it."""
        if self._running_instances() != getattr(self, "_running", set()):
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)

    # ------------------------------------------------------------------ images

    async def _start_images(self) -> None:
        if self.primary:
            await self.primary.client.image_stream(True)

    async def _stop_images(self) -> None:
        if self.primary:
            await self.primary.client.image_stream(False)

    def add_image_listener(self, listener: Callable[[bytes], None]) -> Callable[[], None]:
        assert self.primary is not None
        return self.primary.client.add_image_listener(listener)

    # ------------------------------------------------------------------ helpers

    def connection(self, index: int) -> InstanceConnection:
        try:
            return self.instances[index]
        except KeyError as err:
            raise HyperHDRError(f"Instance {index} is not connected") from err

    def schema_property(self, section: str, key: str) -> dict[str, Any]:
        """The JSON schema of one setting, as the server describes it."""
        props = self.schema.get("properties", {})
        node = props.get(section, {})
        if key:
            for part in key.split("."):
                node = node.get("properties", {}).get(part, node.get("items", {}).get("properties", {}).get(part, {}))
        return node if isinstance(node, dict) else {}
