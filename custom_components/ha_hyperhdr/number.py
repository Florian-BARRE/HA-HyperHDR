"""Numbers: color adjustments, smoothing and grabber settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HyperHDRInstanceEntity, HyperHDRServerEntity, hyperhdr_command
from .hub import HyperHDRConfigEntry, HyperHDRHub
from .settings import NUMBERS, NumberSetting, schema_bounds
from .state import InstanceState

PARALLEL_UPDATES = 0


def _description(setting: NumberSetting, hub: HyperHDRHub) -> NumberEntityDescription:
    low, high = schema_bounds(setting, hub)
    return NumberEntityDescription(
        key=setting.key,
        translation_key=setting.key,
        entity_category=setting.category,
        entity_registry_enabled_default=setting.enabled,
        icon=setting.icon,
        native_min_value=round(low * setting.scale, 6),
        native_max_value=round(high * setting.scale, 6),
        native_step=round(setting.step * setting.scale, 6),
        native_unit_of_measurement=setting.unit,
        mode=NumberMode(setting.mode),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    usable = [setting for setting in NUMBERS if hub.admin or not setting.needs_admin]
    entities: list[NumberEntity] = []
    for connection in hub.instances.values():
        entities.extend(
            SettingNumber(hub, connection, _description(setting, hub), setting)
            for setting in usable
            if setting.scope == "instance"
        )
    entities.extend(
        ServerSettingNumber(hub, _description(setting, hub), setting) for setting in usable if setting.scope == "server"
    )
    async_add_entities(entities)


class _NumberMixin(NumberEntity):
    setting: NumberSetting
    hub: HyperHDRHub

    def _state(self) -> InstanceState | None:
        return None

    @property
    def native_value(self) -> float | None:
        value = self.setting.read(self.hub, self._state())
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        return round(float(value) * self.setting.scale, 4)

    @hyperhdr_command
    async def async_set_native_value(self, value: float) -> None:
        stored = value / self.setting.scale
        integer = self.setting.step >= 1 and self.setting.scale == 1
        stored = round(stored) if integer else round(stored, 4)
        await self.setting.write(self.client, stored)  # type: ignore[attr-defined]


class SettingNumber(_NumberMixin, HyperHDRInstanceEntity):
    def __init__(self, hub: HyperHDRHub, connection, description, setting: NumberSetting) -> None:
        HyperHDRInstanceEntity.__init__(self, hub, connection, description)
        self.setting = setting

    def _state(self) -> InstanceState | None:
        return self.state_data


class ServerSettingNumber(_NumberMixin, HyperHDRServerEntity):
    def __init__(self, hub: HyperHDRHub, description, setting: NumberSetting) -> None:
        HyperHDRServerEntity.__init__(self, hub, description)
        self.setting = setting
