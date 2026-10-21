"""Buttons: give the LEDs back to the capture; power the machine off or restart it."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HyperHDRInstanceEntity, HyperHDRServerEntity, hyperhdr_command
from .hub import HyperHDRConfigEntry
from .ssh import PowerAction, SSHAuthError, SSHConnectionError, SSHError, SSHHostKeyError, SSHSudoError

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


@dataclass(frozen=True, kw_only=True)
class PowerDescription(ButtonEntityDescription):
    action: PowerAction


POWER_BUTTONS = (
    PowerDescription(key="poweroff", translation_key="poweroff", icon="mdi:power", action="poweroff"),
    PowerDescription(
        key="reboot",
        translation_key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        action="reboot",
    ),
)

#: Errors of the SSH power commands, by translation key.
SSH_ERRORS: tuple[tuple[type[SSHError], str], ...] = (
    (SSHAuthError, "ssh_invalid_auth"),
    (SSHHostKeyError, "ssh_host_key"),
    (SSHSudoError, "ssh_sudo"),
    (SSHConnectionError, "ssh_cannot_connect"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    entities: list[ButtonEntity] = [
        ClearButton(hub, connection, description) for connection in hub.instances.values() for description in BUTTONS
    ]
    # Only once SSH is set up in the options (they reload the entry).
    if hub.ssh_configured:
        entities.extend(PowerButton(hub, description) for description in POWER_BUTTONS)
    async_add_entities(entities)


class ClearButton(HyperHDRInstanceEntity, ButtonEntity):
    entity_description: ClearDescription

    @hyperhdr_command
    async def async_press(self) -> None:
        if self.entity_description.everything:
            await self.client.clear_all()
        else:
            await self.client.clear(self.hub.priority)


class PowerButton(HyperHDRServerEntity, ButtonEntity):
    """Powers the machine off (or restarts it) cleanly, over SSH."""

    entity_description: PowerDescription

    @property
    def available(self) -> bool:
        # SSH does not need HyperHDR: the machine may be up with HyperHDR stopped.
        return True

    async def async_press(self) -> None:
        try:
            await self.hub.async_power(self.entity_description.action)
        except SSHError as err:
            key = next((key for kind, key in SSH_ERRORS if isinstance(err, kind)), "ssh_cannot_connect")
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=key, translation_placeholders={"error": str(err)}
            ) from err
