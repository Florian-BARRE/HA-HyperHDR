"""Config flow, with the server check mocked."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_hyperhdr.config_flow import AuthRequired, CannotConnect, InvalidAuth, TooOld
from custom_components.ha_hyperhdr.const import CONF_PRIORITY, DOMAIN

RESULT = {"id": "533f43e3", "version": "22.0.0", "hostname": "pi", "token": "t" * 128}
VALIDATE = "custom_components.ha_hyperhdr.config_flow.validate"
SETUP = "custom_components.ha_hyperhdr.async_setup_entry"


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch(VALIDATE, return_value=RESULT) as validate, patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.20", CONF_PORT: 8090, CONF_PASSWORD: "secret"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HyperHDR pi"
    assert result["data"] == {CONF_HOST: "192.168.1.20", CONF_PORT: 8090, CONF_TOKEN: "t" * 128}
    validate.assert_called_once_with(hass, "192.168.1.20", 8090, "secret")


async def test_user_flow_errors(hass: HomeAssistant) -> None:
    for error, field, key in (
        (CannotConnect, "base", "cannot_connect"),
        (InvalidAuth, CONF_PASSWORD, "invalid_auth"),
        (AuthRequired, CONF_PASSWORD, "auth_required"),
        (TooOld("20.0.0"), "base", "too_old"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        with patch(VALIDATE, side_effect=error):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_HOST: "h", CONF_PORT: 8090}
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {field: key}


async def test_duplicate_updates_host(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="533f43e3", data={CONF_HOST: "old", CONF_PORT: 8090})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(VALIDATE, return_value=RESULT), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "new", CONF_PORT: 8090})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "new"


async def test_ssdp_flow(hass: HomeAssistant) -> None:
    info = SsdpServiceInfo(
        ssdp_usn="uuid:533f43e3::urn:hyperhdr.eu:device:basic:1",
        ssdp_st="urn:hyperhdr.eu:device:basic:1",
        ssdp_location="http://192.168.1.30:8090/description.xml",
        upnp={"friendlyName": "HyperHDR (192.168.1.30)"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    with patch(VALIDATE, return_value=RESULT), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.30"


async def test_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="533f43e3", data={CONF_HOST: "h", CONF_PORT: 8090, CONF_TOKEN: "old"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with patch(VALIDATE, return_value=RESULT), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "t" * 128


async def test_options(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="533f43e3", data={CONF_HOST: "h", CONF_PORT: 8090})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_PRIORITY: 100, "performance": False, "stream_fps": 5, "led_interval": 250}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PRIORITY] == 100
