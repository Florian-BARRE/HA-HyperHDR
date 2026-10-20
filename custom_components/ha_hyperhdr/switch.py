"""Switches: HyperHDR components, HDR tone mapping, and on/off settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COMPONENT_HDR
from .entity import HyperHDRInstanceEntity, HyperHDRServerEntity, hyperhdr_command
from .hub import HyperHDRConfigEntry, HyperHDRHub
from .settings import SWITCHES, SwitchSetting

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ComponentDescription(SwitchEntityDescription):
    component: str


COMPONENTS: tuple[ComponentDescription, ...] = (
    ComponentDescription(
        key="led_output", translation_key="led_output", icon="mdi:led-strip-variant", component="LEDDEVICE"
    ),
    ComponentDescription(
        key="video_capture", translation_key="video_capture", icon="mdi:video-input-hdmi", component="VIDEOGRABBER"
    ),
    ComponentDescription(
        key="system_capture",
        translation_key="system_capture",
        icon="mdi:monitor-screenshot",
        component="SYSTEMGRABBER",
        entity_registry_enabled_default=False,
    ),
    ComponentDescription(key="smoothing", translation_key="smoothing", icon="mdi:blur", component="SMOOTHING"),
    ComponentDescription(
        key="black_border", translation_key="black_border", icon="mdi:border-outside", component="BLACKBORDER"
    ),
    ComponentDescription(
        key="forwarder",
        translation_key="forwarder",
        icon="mdi:share",
        component="FORWARDER",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    ComponentDescription(key="hdr", translation_key="hdr", icon="mdi:hdr", component=COMPONENT_HDR),
)


def _description(setting: SwitchSetting) -> SwitchEntityDescription:
    return SwitchEntityDescription(
        key=setting.key,
        translation_key=setting.key,
        entity_category=setting.category,
        entity_registry_enabled_default=setting.enabled,
        icon=setting.icon,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    entities: list[SwitchEntity] = []
    for connection in hub.instances.values():
        present = connection.state.components
        entities.extend(
            ComponentSwitch(hub, connection, description)
            for description in COMPONENTS
            if description.component in present
        )
        if hub.admin:
            entities.extend(
                SettingSwitch(hub, connection, _description(setting), setting)
                for setting in SWITCHES
                if setting.scope == "instance"
            )
    if hub.admin:
        entities.extend(
            ServerSettingSwitch(hub, _description(setting), setting)
            for setting in SWITCHES
            if setting.scope == "server"
        )
    async_add_entities(entities)


class ComponentSwitch(HyperHDRInstanceEntity, SwitchEntity):
    entity_description: ComponentDescription

    @property
    def is_on(self) -> bool:
        if self.entity_description.component == COMPONENT_HDR:
            return self.state_data.hdr
        return self.state_data.components.get(self.entity_description.component, False)

    async def _set(self, state: bool) -> None:
        if self.entity_description.component == COMPONENT_HDR:
            await self.client.set_hdr(state)
        else:
            await self.client.set_component(self.entity_description.component, state)

    @hyperhdr_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    @hyperhdr_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class SettingSwitch(HyperHDRInstanceEntity, SwitchEntity):
    def __init__(self, hub: HyperHDRHub, connection, description, setting: SwitchSetting) -> None:
        super().__init__(hub, connection, description)
        self.setting = setting

    @property
    def is_on(self) -> bool | None:
        value = self.setting.read(self.hub, self.state_data)
        return None if value is None else bool(value)

    @hyperhdr_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.setting.write(self.client, True)

    @hyperhdr_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.setting.write(self.client, False)


class ServerSettingSwitch(HyperHDRServerEntity, SwitchEntity):
    def __init__(self, hub: HyperHDRHub, description, setting: SwitchSetting) -> None:
        super().__init__(hub, description)
        self.setting = setting

    @property
    def is_on(self) -> bool | None:
        value = self.setting.read(self.hub, None)
        return None if value is None else bool(value)

    @hyperhdr_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.setting.write(self.client, True)

    @hyperhdr_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.setting.write(self.client, False)
