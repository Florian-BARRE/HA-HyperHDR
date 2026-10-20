"""The Ambilight of each instance as a light.

On / off is the instance itself (component `ALL`), as in Home Assistant's
Hyperion integration. A color or an effect goes on the integration's own
priority, above the capture; the `Capture` effect clears it so the screen
drives the LEDs again. Brightness is the luminance gain (100 % = 1.0).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback, async_get_current_platform
from homeassistant.util import color as color_util

from .const import COMPONENT_ALL, EFFECT_CAPTURE, EFFECT_SOLID
from .entity import HyperHDRInstanceEntity, hyperhdr_command
from .hub import HyperHDRConfigEntry

PARALLEL_UPDATES = 0

LIGHT = LightEntityDescription(key="light", name=None)
ATTR_PRIORITY = "priority"
ATTR_DURATION = "duration"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    async_add_entities(HyperHDRLight(hub, connection, LIGHT) for connection in hub.instances.values())
    platform = async_get_current_platform()
    priority = vol.All(vol.Coerce(int), vol.Range(min=1, max=253))
    duration = vol.All(vol.Coerce(int), vol.Range(min=0))
    platform.async_register_entity_service(
        "set_color",
        {
            vol.Required(ATTR_RGB_COLOR): vol.All(vol.ExactSequence((cv.byte,) * 3), vol.Coerce(tuple)),
            vol.Optional(ATTR_PRIORITY): priority,
            vol.Optional(ATTR_DURATION): duration,
        },
        "async_set_color",
    )
    platform.async_register_entity_service(
        "set_effect",
        {
            vol.Required(ATTR_EFFECT): cv.string,
            vol.Optional(ATTR_PRIORITY): priority,
            vol.Optional(ATTR_DURATION): duration,
        },
        "async_set_effect",
    )
    platform.async_register_entity_service("clear", {vol.Optional(ATTR_PRIORITY): priority}, "async_clear")


class HyperHDRLight(HyperHDRInstanceEntity, LightEntity):
    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT

    @property
    def _own(self):
        return self.state_data.priority(self.hub.priority)

    @property
    def is_on(self) -> bool:
        return self.state_data.components.get(COMPONENT_ALL, False)

    @property
    def brightness(self) -> int:
        gain = self.state_data.adjustment.get("luminanceGain", 1)
        try:
            return max(1, min(255, round(float(gain) * 255)))
        except (TypeError, ValueError):
            return 255

    @property
    def hs_color(self) -> tuple[float, float]:
        own = self._own
        if own and own.rgb:
            return color_util.color_RGB_to_hs(*own.rgb)
        return (0.0, 0.0)

    @property
    def effect_list(self) -> list[str]:
        return [EFFECT_CAPTURE, EFFECT_SOLID, *self.state_data.effects]

    @property
    def effect(self) -> str | None:
        own = self._own
        if own is None:
            return EFFECT_CAPTURE
        if own.component == "EFFECT":
            # HyperHDR names the running effect as the owner of its priority.
            if own.owner:
                return str(own.owner)
            active = next(
                (item for item in self.state_data.active_effects if item.get("priority") == own.priority),
                None,
            )
            return str(active["name"]) if active and active.get("name") else own.origin
        return EFFECT_SOLID

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        visible = self.state_data.visible
        return {
            "priority": self.hub.priority,
            "visible_priority": visible.priority if visible else None,
            "visible_source": visible.component if visible else None,
        }

    @hyperhdr_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.client
        if not self.is_on:
            await client.set_component(COMPONENT_ALL, True)
        if ATTR_BRIGHTNESS in kwargs:
            await client.set_adjustment(luminanceGain=round(kwargs[ATTR_BRIGHTNESS] / 255, 3))
        effect = kwargs.get(ATTR_EFFECT)
        rgb: tuple[int, int, int] | None = None
        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
        elif ATTR_RGB_COLOR in kwargs:
            rgb = tuple(kwargs[ATTR_RGB_COLOR])  # type: ignore[assignment]
        if effect == EFFECT_CAPTURE:
            await client.clear(self.hub.priority)
        elif effect and effect != EFFECT_SOLID:
            await client.set_effect(effect, self.hub.priority)
        elif rgb is not None or effect == EFFECT_SOLID:
            own = self._own
            color = rgb or (own.rgb if own and own.rgb else (255, 255, 255))
            await client.set_color(color, self.hub.priority)

    @hyperhdr_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.set_component(COMPONENT_ALL, False)

    @hyperhdr_command
    async def async_set_color(
        self, rgb_color: tuple[int, int, int], priority: int | None = None, duration: int | None = None
    ) -> None:
        """Service: a color on a priority, for a duration (ms, 0 = until cleared)."""
        await self.client.set_color(tuple(rgb_color), priority or self.hub.priority, duration or None)

    @hyperhdr_command
    async def async_set_effect(self, effect: str, priority: int | None = None, duration: int | None = None) -> None:
        await self.client.set_effect(effect, priority or self.hub.priority, duration or None)

    @hyperhdr_command
    async def async_clear(self, priority: int | None = None) -> None:
        await self.client.clear(priority or self.hub.priority)
