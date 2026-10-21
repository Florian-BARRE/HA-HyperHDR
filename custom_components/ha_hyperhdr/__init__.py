"""HyperHDR for Home Assistant.

One WebSocket per running instance, HyperHDR pushes every change: lights,
components, color adjustments, settings, host health and the captured
picture, without polling.
"""

from __future__ import annotations

from homeassistant.const import CONF_TOKEN, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import CONF_LEGACY_TOKEN, DOMAIN
from .entity import server_device
from .hub import HyperHDRConfigEntry, HyperHDRHub
from .naming import async_apply_names
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HyperHDRConfigEntry) -> bool:
    hub = HyperHDRHub(hass, entry)
    await hub.async_setup()
    entry.runtime_data = hub
    # The server device first: the instance devices hang under it.
    device = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, **server_device(hub))
    hub.server_device_id = device.id

    async def _stop(_: Event) -> None:
        await hub.async_shutdown()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The entities are registered: new names, then their entity ids.
    async_apply_names(hass, entry)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: HyperHDRConfigEntry) -> bool:
    """1 → 2: the token is dropped (HyperHDR makes a new one each time it starts).

    The password it came from was not kept: the entry tries HyperHDR's default
    one, and asks for the password once if the server has another one.
    """
    if entry.version > 2:
        return False
    if entry.version == 1:
        data = {key: value for key, value in entry.data.items() if key != CONF_TOKEN}
        if entry.data.get(CONF_TOKEN):
            data[CONF_LEGACY_TOKEN] = True
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HyperHDRConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
