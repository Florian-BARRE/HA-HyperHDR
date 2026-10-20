"""Constants of the HyperHDR integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_hyperhdr"
MANUFACTURER: Final = "HyperHDR"

CONF_INSTANCE: Final = "instance"
CONF_PRIORITY: Final = "priority"
CONF_PERFORMANCE: Final = "performance"
CONF_STREAM_FPS: Final = "stream_fps"
CONF_LED_INTERVAL: Final = "led_interval"
CONF_USE_SSL: Final = "use_ssl"

DEFAULT_PRIORITY: Final = 128
DEFAULT_STREAM_FPS: Final = 10
DEFAULT_LED_INTERVAL: Final = 200
#: HyperHDR's own default admin password, tried when none is given.
DEFAULT_PASSWORD: Final = "hyperhdr"
#: Oldest HyperHDR version supported.
MIN_VERSION: Final = (21, 0)

#: Seconds before reconnecting, growing up to the last one.
RECONNECT_DELAYS: Final = (1, 2, 5, 10, 30, 60)
#: A stream nobody looks at stops after this many seconds.
STREAM_IDLE: Final = 15

SSDP_ST: Final = "urn:hyperhdr.eu:device:basic:1"

#: Effect names of the light that are not HyperHDR effects.
EFFECT_SOLID: Final = "Solid"
EFFECT_CAPTURE: Final = "Capture"

ORIGIN: Final = "Home Assistant"

#: HyperHDR components and their keys (entity names come from translations).
COMPONENT_LED_DEVICE: Final = "LEDDEVICE"
COMPONENT_ALL: Final = "ALL"
COMPONENT_HDR: Final = "HDR"
