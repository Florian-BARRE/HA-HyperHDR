"""Device names from a prefix of the user's own convention, and entity ids after them.

With a prefix such as `salon-ambilight-hyperhdr`, the server is
`salon-ambilight-hyperhdr-hub` and each strip `salon-ambilight-hyperhdr-<name>`,
the strip's HyperHDR name with its spaces as underscores (`salon canapé WLED`
→ `salon_canapé_WLED`): hyphens part the levels, underscores join the words.

Home Assistant makes an entity id once, from the names of the moment. When
the prefix changes, the integration renames its devices (dropping names
typed by hand on them) and recreates the entity ids from the device name and
the entity name only: the prefix already holds the room, so the area that
Home Assistant's default "Entity ID format" puts first would come twice
(`sensor.salon_salon_ambilight_hyperhdr_hub_…`).

Entity ids come from the English names, whatever Home Assistant's language,
as Home Assistant makes them: a Home Assistant in French keeps
`sensor.…_cpu_temperature`, not `sensor.…_temperature_du_cpu`. The registry's
own names cannot be trusted for that: `original_name` is in Home Assistant's
language, and so is `object_id_base` for entities registered before it
existed (Home Assistant copied `original_name` into it).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from .const import CONF_NAME_PREFIX, DOMAIN

_LOGGER = logging.getLogger(__name__)

#: In the entry's data: the prefix the names and entity ids were last made from.
APPLIED_PREFIX = "applied_name_prefix"
#: In the entry's data: how the entity ids were made. 2: from the English names
#: (0.1.0b5 used the names in Home Assistant's language).
APPLIED_NAMING = "applied_naming"
NAMING_VERSION = 2


def name_prefix(entry: ConfigEntry) -> str:
    return str(entry.options.get(CONF_NAME_PREFIX) or "").strip()


def hub_name(prefix: str, default: str) -> str:
    return f"{prefix}-hub" if prefix else default


def strip_name(prefix: str, name: str) -> str:
    if not prefix:
        return name
    return f"{prefix}-{'_'.join(name.split())}"


def _needs_naming(entry: ConfigEntry, prefix: str) -> bool:
    if prefix != entry.data.get(APPLIED_PREFIX, ""):
        return True
    # Ids made by an older way are made again, once.
    return bool(prefix) and entry.data.get(APPLIED_NAMING, 1) < NAMING_VERSION


async def async_apply_names(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Once the entities are registered: renames after a new prefix. True when done."""
    prefix = name_prefix(entry)
    if not _needs_naming(entry, prefix):
        return False
    english = await async_get_translations(hass, "en", "entity", [DOMAIN])
    _apply_names(hass, entry, prefix, english)
    return True


@callback
def _apply_names(hass: HomeAssistant, entry: ConfigEntry, prefix: str, english: dict[str, str]) -> None:
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    # Names typed by hand on the devices would hide the new ones.
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        if device.name_by_user:
            devices.async_update_device(device.id, name_by_user=None)
    reserved: set[str] = set()
    renamed = 0
    for item in er.async_entries_for_config_entry(entities, entry.entry_id):
        device = devices.async_get(item.device_id) if item.device_id else None
        device_name = (device.name_by_user or device.name) if device else None
        entity_name = item.name or _english_name(english, item) or item.original_name
        object_id = " ".join(part for part in (device_name, entity_name) if part)
        if not object_id:
            continue
        new_id = _available_entity_id(entities, item.domain, object_id, item.entity_id, reserved)
        reserved.add(new_id)
        if new_id != item.entity_id:
            entities.async_update_entity(item.entity_id, new_entity_id=new_id)
            renamed += 1
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, APPLIED_PREFIX: prefix, APPLIED_NAMING: NAMING_VERSION},
        title=prefix or entry.title,
    )
    _LOGGER.info("HyperHDR names from %r: %s entity ids recreated", prefix, renamed)


def _english_name(english: dict[str, str], item: er.RegistryEntry) -> str | None:
    """The entity's name in English, from its translation key (none: the device's name alone)."""
    if not item.translation_key:
        return None
    return english.get(f"component.{DOMAIN}.entity.{item.domain}.{item.translation_key}.name")


def _available_entity_id(
    entities: er.EntityRegistry, domain: str, object_id: str, current: str, reserved: set[str]
) -> str:
    # `async_get_available_entity_id` replaces `async_generate_entity_id` (2026.10).
    get = getattr(entities, "async_get_available_entity_id", None) or entities.async_generate_entity_id
    return get(domain, object_id, current_entity_id=current, reserved_entity_ids=reserved)
