"""Diagnostics: what the integration knows, without the token."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .hub import HyperHDRConfigEntry

TO_REDACT = {CONF_TOKEN, CONF_PASSWORD, "password", "username", "keyPassPhrase", "id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: HyperHDRConfigEntry) -> dict[str, Any]:
    hub = entry.runtime_data
    server = asdict(hub.server)
    server["performance"]["fps"] = {f"{kind}:{index}": fps for (kind, index), fps in hub.server.performance.fps.items()}
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "admin": hub.admin,
        "server": async_redact_data(server, TO_REDACT),
        "instances": {
            index: {
                "connected": connection.client.connected,
                "state": async_redact_data(
                    {**asdict(connection.state), "led_colors": len(connection.state.led_colors)}, TO_REDACT
                ),
            }
            for index, connection in hub.instances.items()
        },
    }
