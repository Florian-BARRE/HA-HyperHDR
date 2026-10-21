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
#: Names of the devices: "<prefix>-hub" and "<prefix>-<strip>" (options).
CONF_NAME_PREFIX: Final = "name_prefix"
#: Clean power off and restart of HyperHDR's machine, over SSH (options).
CONF_SSH_USERNAME: Final = "ssh_username"
CONF_SSH_PASSWORD: Final = "ssh_password"
CONF_SSH_PORT: Final = "ssh_port"
#: The machine's SSH host key, learnt when SSH is set up and checked afterwards.
CONF_SSH_HOST_KEY: Final = "ssh_host_key"
#: Set on entries that kept a token (0.1.0b2 and before), until they connect again.
CONF_LEGACY_TOKEN: Final = "legacy_token"

DEFAULT_PRIORITY: Final = 128
DEFAULT_STREAM_FPS: Final = 10
DEFAULT_LED_INTERVAL: Final = 200
#: HyperHDR's own default admin password, tried when none is given.
DEFAULT_PASSWORD: Final = "hyperhdr"
#: Oldest HyperHDR version supported.
MIN_VERSION: Final = (21, 0)

#: Seconds before reconnecting, growing up to the last one.
RECONNECT_DELAYS: Final = (1, 2, 5, 10, 30, 60)
#: HyperHDR measures the host only when asked: seconds between two requests.
HOST_HEALTH_INTERVAL: Final = 30
#: The CPU load is the difference between two readings: the first one only
#: starts the measure, the second one comes this many seconds later.
HOST_HEALTH_FIRST_DELAY: Final = 2
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
