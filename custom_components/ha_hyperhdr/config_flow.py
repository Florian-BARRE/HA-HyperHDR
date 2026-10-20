"""Config flow: found on the network or typed in, admin password optional."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .api import DEFAULT_PORT, HyperHDRAuthError, HyperHDRClient, HyperHDRCommandError, HyperHDRError
from .const import (
    CONF_LED_INTERVAL,
    CONF_PERFORMANCE,
    CONF_PRIORITY,
    CONF_STREAM_FPS,
    DEFAULT_LED_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_PRIORITY,
    DEFAULT_STREAM_FPS,
    DOMAIN,
    MIN_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class CannotConnect(Exception):
    pass


class InvalidAuth(Exception):
    pass


class AuthRequired(Exception):
    pass


class TooOld(Exception):
    def __init__(self, version: str) -> None:
        super().__init__(version)
        self.version = version


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3]) or (0,)


async def validate(hass: HomeAssistant, host: str, port: int, password: str | None) -> dict[str, Any]:
    """Connects, logs in, checks the version. Returns id, version, hostname, token."""
    client = HyperHDRClient(host, port, session=async_get_clientsession(hass, verify_ssl=False))
    try:
        await client.connect()
    except HyperHDRError as err:
        raise CannotConnect from err
    try:
        token: str | None = None
        try:
            token = await client.login(password=password or DEFAULT_PASSWORD)
        except HyperHDRAuthError as err:
            if password:
                raise InvalidAuth from err
            # Not the default password: no admin rights, the basics still work.
        try:
            info = await client.sys_info()
            server = await client.server_info()
        except HyperHDRCommandError as err:
            raise AuthRequired from err
        hyperhdr = info.get("hyperhdr") or {}
        version = str(hyperhdr.get("version", ""))
        if _version(version) < MIN_VERSION:
            raise TooOld(version)
        return {
            "id": str(hyperhdr.get("id") or f"{host}:{port}"),
            "version": version,
            "hostname": str(server.get("hostname") or host),
            "token": token,
        }
    except HyperHDRError as err:
        raise CannotConnect from err
    finally:
        await client.close()


class HyperHDRConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._name: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> HyperHDROptionsFlow:
        return HyperHDROptionsFlow()

    async def _check(self, host: str, port: int, password: str | None, errors: dict[str, str]) -> dict[str, Any] | None:
        try:
            return await validate(self.hass, host, port, password or None)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors[CONF_PASSWORD] = "invalid_auth"
        except AuthRequired:
            errors[CONF_PASSWORD] = "auth_required"
        except TooOld:
            errors["base"] = "too_old"
        except Exception:
            _LOGGER.exception("Unexpected error while checking HyperHDR %s", host)
            errors["base"] = "unknown"
        return None

    def _data(self, host: str, port: int, result: dict[str, Any]) -> dict[str, Any]:
        return {CONF_HOST: host, CONF_PORT: port, CONF_TOKEN: result["token"]}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            result = await self._check(host, port, user_input.get(CONF_PASSWORD), errors)
            if result:
                await self.async_set_unique_id(result["id"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
                return self.async_create_entry(
                    title=f"HyperHDR {result['hostname']}", data=self._data(host, port, result)
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_PASSWORD): PASSWORD,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        location = urlparse(discovery_info.ssdp_location or "")
        if not location.hostname:
            return self.async_abort(reason="cannot_connect")
        self._host = location.hostname
        self._port = location.port or DEFAULT_PORT
        unique = discovery_info.ssdp_usn.split("::")[0].removeprefix("uuid:") if discovery_info.ssdp_usn else None
        if unique:
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._port})
        self._name = discovery_info.upnp.get("friendlyName") or self._host
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        assert self._host is not None
        if user_input is not None:
            result = await self._check(self._host, self._port, user_input.get(CONF_PASSWORD), errors)
            if result:
                await self.async_set_unique_id(result["id"], raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._port})
                return self.async_create_entry(
                    title=f"HyperHDR {result['hostname']}", data=self._data(self._host, self._port, result)
                )
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): PASSWORD}),
            description_placeholders={"name": self._name or self._host, "host": f"{self._host}:{self._port}"},
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            result = await self._check(
                entry.data[CONF_HOST], entry.data[CONF_PORT], user_input.get(CONF_PASSWORD), errors
            )
            if result:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: result["token"]})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD}),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            result = await self._check(host, port, user_input.get(CONF_PASSWORD), errors)
            if result:
                await self.async_set_unique_id(result["id"])
                self._abort_if_unique_id_mismatch(reason="wrong_server")
                return self.async_update_reload_and_abort(entry, data=self._data(host, port, result))
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_PASSWORD): PASSWORD,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)


class HyperHDROptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={key: int(value) if isinstance(value, float) else value for key, value in user_input.items()}
            )
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_PRIORITY, default=options.get(CONF_PRIORITY, DEFAULT_PRIORITY)): NumberSelector(
                    NumberSelectorConfig(min=1, max=253, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_PERFORMANCE, default=options.get(CONF_PERFORMANCE, True)): BooleanSelector(),
                vol.Required(CONF_STREAM_FPS, default=options.get(CONF_STREAM_FPS, DEFAULT_STREAM_FPS)): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=30, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="fps"
                    )
                ),
                vol.Required(
                    CONF_LED_INTERVAL, default=options.get(CONF_LED_INTERVAL, DEFAULT_LED_INTERVAL)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=50, max=2000, step=50, mode=NumberSelectorMode.SLIDER, unit_of_measurement="ms"
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
