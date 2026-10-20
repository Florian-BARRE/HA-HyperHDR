"""Buttons: give the LEDs back to the capture."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HyperHDRInstanceEntity, hyperhdr_command
from .hub import HyperHDRConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ClearDescription(ButtonEntityDescription):
    everything: bool


BUTTONS = (
    ClearDescription(key="clear", translation_key="clear", everything=False),
    ClearDescription(
        key="clear_all", translation_key="clear_all", everything=True, entity_registry_enabled_default=False
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    async_add_entities(
        ClearButton(hub, connection, description) for connection in hub.instances.values() for description in BUTTONS
    )


class ClearButton(HyperHDRInstanceEntity, ButtonEntity):
    entity_description: ClearDescription

    @hyperhdr_command
    async def async_press(self) -> None:
        if self.entity_description.everything:
            await self.client.clear_all()
        else:
            await self.client.clear(self.hub.priority)
