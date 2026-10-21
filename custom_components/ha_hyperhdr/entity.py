"""Base entities: one device for the server, one per instance."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Concatenate

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import HyperHDRCommandError, HyperHDRError
from .const import DOMAIN, MANUFACTURER
from .hub import HyperHDRHub, InstanceConnection
from .naming import hub_name, name_prefix, strip_name
from .state import InstanceState, ServerState


def server_device(hub: HyperHDRHub) -> DeviceInfo:
    server = hub.server
    scheme = "https" if hub.use_ssl else "http"
    return DeviceInfo(
        identifiers={(DOMAIN, hub.server_id)},
        name=hub_name(name_prefix(hub.entry), f"HyperHDR {server.hostname}".strip() if server.hostname else "HyperHDR"),
        manufacturer=MANUFACTURER,
        model=str(server.system.get("cpuModelName") or server.system.get("architecture") or "HyperHDR"),
        sw_version=server.version or None,
        configuration_url=f"{scheme}://{hub.host}:{hub.port}",
    )


def instance_device(hub: HyperHDRHub, connection: InstanceConnection) -> DeviceInfo:
    name = strip_name(name_prefix(hub.entry), connection.state.name or f"Instance {connection.index}")
    return DeviceInfo(
        identifiers={(DOMAIN, f"{hub.server_id}_{connection.index}")},
        name=name,
        manufacturer=MANUFACTURER,
        model="LED instance",
        sw_version=hub.server.version or None,
        via_device_id=hub.server_device_id,
    )


def hyperhdr_command[**P, R](
    func: Callable[Concatenate[Any, P], Awaitable[R]],
) -> Callable[Concatenate[Any, P], Awaitable[R]]:
    """Turns HyperHDR errors into errors Home Assistant shows to the user."""

    @wraps(func)
    async def wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(self, *args, **kwargs)
        except HyperHDRCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"command": err.command, "error": err.error},
            ) from err
        except HyperHDRError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_connected",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper


class HyperHDRInstanceEntity(CoordinatorEntity[Any]):
    """An entity of one instance, updated by its pushed state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hub: HyperHDRHub,
        connection: InstanceConnection,
        description: EntityDescription,
    ) -> None:
        super().__init__(connection.coordinator)
        self.hub = hub
        self.connection = connection
        self.entity_description = description
        self._attr_unique_id = f"{hub.server_id}_{connection.index}_{description.key}"
        self._attr_device_info = instance_device(hub, connection)

    @property
    def state_data(self) -> InstanceState:
        return self.connection.state

    @property
    def client(self):
        return self.connection.client


class HyperHDRServerEntity(CoordinatorEntity[Any]):
    """An entity of the server device (host, grabber)."""

    _attr_has_entity_name = True

    def __init__(self, hub: HyperHDRHub, description: EntityDescription) -> None:
        super().__init__(hub.server_coordinator)
        self.hub = hub
        self.entity_description = description
        self._attr_unique_id = f"{hub.server_id}_{description.key}"
        self._attr_device_info = server_device(hub)

    @property
    def server(self) -> ServerState:
        return self.hub.server

    @property
    def client(self):
        assert self.hub.primary is not None
        return self.hub.primary.client
