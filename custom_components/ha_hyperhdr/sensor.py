"""Sensors: host health, grabber, frame rates, the source on the LEDs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HyperHDRError
from .entity import HyperHDRInstanceEntity, HyperHDRServerEntity
from .hub import HyperHDRConfigEntry
from .state import PERF_INSTANCE, PERF_LED, PERF_VIDEO_GRABBER, InstanceState, ServerState

PARALLEL_UPDATES = 0
#: Only the average color is read on demand (HyperHDR does not push it).
SCAN_INTERVAL = timedelta(seconds=15)

FPS = "fps"


@dataclass(frozen=True, kw_only=True)
class ServerSensorDescription(SensorEntityDescription):
    value: Callable[[ServerState], Any]
    attributes: Callable[[ServerState], dict[str, Any]] | None = None
    performance: bool = False


@dataclass(frozen=True, kw_only=True)
class InstanceSensorDescription(SensorEntityDescription):
    value: Callable[[InstanceState, ServerState], Any]
    attributes: Callable[[InstanceState, ServerState], dict[str, Any]] | None = None
    performance: bool = False
    #: Read from the instance's settings, which need the admin password.
    admin: bool = False


def _device(state: InstanceState) -> dict[str, Any]:
    device = state.settings.get("device")
    return device if isinstance(device, dict) else {}


def _device_address(state: InstanceState) -> str | None:
    """Where the LEDs are sent: the network host (WLED, UDP…) or the serial port."""
    device = _device(state)
    for key in ("host", "output"):
        value = device.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _grabber_fps(server: ServerState) -> float | None:
    rates = [fps for (kind, _), fps in server.performance.fps.items() if kind == PERF_VIDEO_GRABBER]
    return max(rates) if rates else None


def _current(server: ServerState) -> dict[str, Any]:
    current = server.grabber.get("current")
    return current if isinstance(current, dict) else {}


SERVER_SENSORS: tuple[ServerSensorDescription, ...] = (
    ServerSensorDescription(
        key="cpu",
        translation_key="cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        performance=True,
        value=lambda server: server.performance.cpu,
    ),
    ServerSensorDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        performance=True,
        value=lambda server: server.performance.temperature,
    ),
    ServerSensorDescription(
        key="memory",
        translation_key="memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        performance=True,
        value=lambda server: server.performance.memory_percent,
        attributes=lambda server: {
            "used_mb": server.performance.memory_used_mb,
            "total_mb": server.performance.memory_total_mb,
        },
    ),
    ServerSensorDescription(
        key="capture_fps",
        translation_key="capture_fps",
        native_unit_of_measurement=FPS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        performance=True,
        value=_grabber_fps,
    ),
    ServerSensorDescription(
        key="grabber",
        translation_key="grabber",
        value=lambda server: _current(server).get("device") or None,
        attributes=lambda server: {
            "video_mode": _current(server).get("videoMode") or None,
            "active": server.grabber.get("active"),
        },
    ),
    ServerSensorDescription(
        key="video_mode",
        translation_key="video_mode",
        value=lambda server: _current(server).get("videoMode") or None,
    ),
    ServerSensorDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda server: server.version or None,
        attributes=lambda server: {
            "architecture": server.system.get("architecture"),
            "cpu": server.system.get("cpuModelName"),
            "hostname": server.hostname,
        },
    ),
)


def _instance_fps(kind: int) -> Callable[[InstanceState, ServerState], float | None]:
    return lambda state, server: server.performance.fps.get((kind, state.index))


def _visible(state: InstanceState, server: ServerState) -> str | None:
    visible = state.visible
    return visible.component.lower() if visible else "none"


INSTANCE_SENSORS: tuple[InstanceSensorDescription, ...] = (
    InstanceSensorDescription(
        key="visible_source",
        translation_key="visible_source",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "none",
            "videograbber",
            "systemgrabber",
            "color",
            "effect",
            "image",
            "flatbufserver",
            "protoserver",
            "rawudpserver",
            "cec",
            "unknown",
        ],
        value=lambda state, server: v if (v := _visible(state, server)) in INSTANCE_SENSORS_OPTIONS else "unknown",
        attributes=lambda state, server: {
            "priority": state.visible.priority if state.visible else None,
            "origin": state.visible.origin if state.visible else None,
            "sources": [
                {"priority": item.priority, "component": item.component, "origin": item.origin, "active": item.active}
                for item in state.priorities
            ],
        },
    ),
    InstanceSensorDescription(
        key="output_fps",
        translation_key="output_fps",
        native_unit_of_measurement=FPS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        performance=True,
        value=_instance_fps(PERF_INSTANCE),
    ),
    InstanceSensorDescription(
        key="led_fps",
        translation_key="led_fps",
        native_unit_of_measurement=FPS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        performance=True,
        entity_registry_enabled_default=False,
        value=_instance_fps(PERF_LED),
    ),
    InstanceSensorDescription(
        key="led_device",
        translation_key="led_device",
        admin=True,
        value=lambda state, server: str(_device(state).get("type") or "").strip() or None,
        attributes=lambda state, server: {
            "address": _device_address(state),
            "refresh_time_ms": _device(state).get("refreshTime"),
        },
    ),
    InstanceSensorDescription(
        key="led_count",
        translation_key="led_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda state, server: state.led_count or None,
    ),
)
INSTANCE_SENSORS_OPTIONS = set(INSTANCE_SENSORS[0].options or [])

AVERAGE_COLOR = SensorEntityDescription(
    key="average_color", translation_key="average_color", entity_registry_enabled_default=False
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    entities: list[SensorEntity] = [
        ServerSensor(hub, description)
        for description in SERVER_SENSORS
        if hub.performance or not description.performance
    ]
    for connection in hub.instances.values():
        entities.extend(
            InstanceSensor(hub, connection, description)
            for description in INSTANCE_SENSORS
            if (hub.performance or not description.performance) and (hub.admin or not description.admin)
        )
        entities.append(AverageColorSensor(hub, connection, AVERAGE_COLOR))
    async_add_entities(entities)


class ServerSensor(HyperHDRServerEntity, SensorEntity):
    entity_description: ServerSensorDescription

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.server)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes = self.entity_description.attributes
        return attributes(self.server) if attributes else None


class InstanceSensor(HyperHDRInstanceEntity, SensorEntity):
    entity_description: InstanceSensorDescription

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.state_data, self.hub.server)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes = self.entity_description.attributes
        return attributes(self.state_data, self.hub.server) if attributes else None


class AverageColorSensor(HyperHDRInstanceEntity, SensorEntity):
    """Average color of the LEDs, read every 15 s while enabled (not pushed)."""

    _attr_should_poll = True
    _value: str | None = None
    _rgb: list[int] | None = None

    @property
    def native_value(self) -> str | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"rgb_color": self._rgb}

    async def async_update(self) -> None:
        try:
            color = await self.client.average_color()
        except HyperHDRError:
            return
        rgb = [int(color.get(channel, 0)) for channel in ("red", "green", "blue")]
        self._rgb = rgb
        self._value = "#{:02x}{:02x}{:02x}".format(*rgb)
