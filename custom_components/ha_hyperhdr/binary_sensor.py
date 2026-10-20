"""Binary sensors: the connection to HyperHDR, and undervoltage of its host."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HyperHDRServerEntity
from .hub import HyperHDRConfigEntry

PARALLEL_UPDATES = 0

CONNECTED = BinarySensorEntityDescription(
    key="connected",
    translation_key="connected",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)
UNDERVOLTAGE = BinarySensorEntityDescription(
    key="undervoltage",
    translation_key="undervoltage",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    entities: list[BinarySensorEntity] = [ConnectedSensor(hub, CONNECTED)]
    if hub.performance:
        entities.append(UndervoltageSensor(hub, UNDERVOLTAGE))
    async_add_entities(entities)


class ConnectedSensor(HyperHDRServerEntity, BinarySensorEntity):
    """Stays available: it is what tells the connection dropped."""

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.hub.primary and self.hub.primary.client.connected and self.coordinator.last_update_success)


class UndervoltageSensor(HyperHDRServerEntity, BinarySensorEntity):
    """Raspberry Pi undervoltage, as HyperHDR reads it; unknown elsewhere."""

    @property
    def is_on(self) -> bool | None:
        return self.server.performance.undervoltage
