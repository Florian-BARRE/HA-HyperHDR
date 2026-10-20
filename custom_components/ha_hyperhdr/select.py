"""Selects: the source on the LEDs, and settings with choices."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HyperHDRInstanceEntity, hyperhdr_command
from .hub import HyperHDRConfigEntry, HyperHDRHub
from .settings import SELECTS, SelectSetting, schema_options
from .state import Priority

PARALLEL_UPDATES = 0

SOURCE = SelectEntityDescription(key="source", translation_key="source")
AUTO = "auto"


def source_label(item: Priority) -> str:
    """`Effect: Rainbow (1)`-like label of a source, unique by its priority."""
    origin = item.origin.split("@")[0] if item.origin else ""
    name = item.component.replace("_", " ").title()
    if origin and origin.lower() not in {"system", name.lower()}:
        name = f"{name}: {origin}"
    return f"{name} ({item.priority})"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    entities: list[SelectEntity] = []
    for connection in hub.instances.values():
        entities.append(SourceSelect(hub, connection, SOURCE))
        entities.extend(
            SettingSelect(hub, connection, setting) for setting in SELECTS if hub.admin or not setting.needs_admin
        )
    async_add_entities(entities)


class SourceSelect(HyperHDRInstanceEntity, SelectEntity):
    """`auto`, or a source forced on the LEDs."""

    @property
    def options(self) -> list[str]:
        return [AUTO, *(source_label(item) for item in self.state_data.priorities if item.active)]

    @property
    def current_option(self) -> str | None:
        if self.state_data.autoselect:
            return AUTO
        visible = self.state_data.visible
        return source_label(visible) if visible else AUTO

    @hyperhdr_command
    async def async_select_option(self, option: str) -> None:
        if option == AUTO:
            await self.client.source_select(None)
            return
        for item in self.state_data.priorities:
            if source_label(item) == option:
                await self.client.source_select(item.priority)
                return
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="unknown_source", translation_placeholders={"source": option}
        )


class SettingSelect(HyperHDRInstanceEntity, SelectEntity):
    def __init__(self, hub: HyperHDRHub, connection, setting: SelectSetting) -> None:
        description = SelectEntityDescription(
            key=setting.key,
            translation_key=setting.key,
            entity_category=setting.category,
            entity_registry_enabled_default=setting.enabled,
            icon=setting.icon,
        )
        super().__init__(hub, connection, description)
        self.setting = setting
        values = list(setting.options) if setting.writer == "processing" else schema_options(setting, hub)
        # Options are lowercase (translation keys); HyperHDR's values may not be.
        self._values = {value.lower(): value for value in values}
        self._attr_options = list(self._values)

    @property
    def current_option(self) -> str | None:
        value = self.setting.read(self.hub, self.state_data)
        option = str(value).lower() if value is not None else None
        return option if option in self._values else None

    @hyperhdr_command
    async def async_select_option(self, option: str) -> None:
        await self.setting.write(self.client, self._values.get(option, option))
