"""Services on a HyperHDR server: its configuration and its backup."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import HyperHDRCommandError, HyperHDRError
from .const import CONF_INSTANCE, DOMAIN
from .hub import HyperHDRHub

ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_CONFIG = "config"

_BASE = {
    vol.Required(ATTR_CONFIG_ENTRY): cv.string,
    vol.Optional(CONF_INSTANCE, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
}


def _hub(hass: HomeAssistant, call: ServiceCall) -> HyperHDRHub:
    entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")
    hub: HyperHDRHub = entry.runtime_data
    if not hub.admin:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="admin_required")
    return hub


async def _run(coro: Any) -> Any:
    try:
        return await coro
    except HyperHDRCommandError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"command": err.command, "error": err.error},
        ) from err
    except HyperHDRError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="not_connected", translation_placeholders={"error": str(err)}
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def get_config(call: ServiceCall) -> ServiceResponse:
        hub = _hub(hass, call)
        client = await _run(_client(hub, call))
        return {"config": await _run(client.get_config())}

    async def set_config(call: ServiceCall) -> None:
        hub = _hub(hass, call)
        client = await _run(_client(hub, call))
        await _run(client.set_config(call.data[ATTR_CONFIG]))

    async def backup(call: ServiceCall) -> ServiceResponse:
        hub = _hub(hass, call)
        assert hub.primary is not None
        return {"backup": await _run(hub.primary.client.backup())}

    hass.services.async_register(
        DOMAIN, "get_config", get_config, schema=vol.Schema(_BASE), supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN,
        "set_config",
        set_config,
        schema=vol.Schema({**_BASE, vol.Required(ATTR_CONFIG): dict}),
    )
    hass.services.async_register(
        DOMAIN,
        "backup",
        backup,
        schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )


async def _client(hub: HyperHDRHub, call: ServiceCall):
    return hub.connection(call.data.get(CONF_INSTANCE, 0)).client
