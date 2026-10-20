"""The HyperHDR settings exposed as entities, declared once.

A setting is read from the state HyperHDR pushes and written with the
lightest command that does it: `adjustment`, `processing`,
`componentstate`, or a partial `setconfig` (admin) that HyperHDR merges into
the section. Ranges and choices come from the server's own schema when it is
known, so a newer HyperHDR brings its new options without an update here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from homeassistant.helpers.entity import EntityCategory

from .api import HyperHDRClient
from .hub import HyperHDRHub
from .state import InstanceState

Scope = Literal["instance", "server"]
#: How a setting is written: `config` needs admin rights.
Writer = Literal["config", "adjustment", "processing"]


@dataclass(frozen=True, kw_only=True)
class Setting:
    key: str
    section: str
    field: str
    writer: Writer = "config"
    scope: Scope = "instance"
    category: EntityCategory | None = EntityCategory.CONFIG
    enabled: bool = True
    icon: str | None = None

    @property
    def needs_admin(self) -> bool:
        return self.writer == "config"

    def read(self, hub: HyperHDRHub, state: InstanceState | None) -> Any:
        if self.writer == "adjustment":
            return state.adjustment.get(self.field) if state else None
        if self.writer == "processing":
            return state.mapping if state else None
        settings = hub.server.settings if self.scope == "server" or state is None else state.settings
        section = settings.get(self.section)
        if isinstance(section, list):
            section = section[0] if section and isinstance(section[0], dict) else {}
        if not isinstance(section, dict):
            return None
        return section.get(self.field)

    async def write(self, client: HyperHDRClient, value: Any) -> None:
        if self.writer == "adjustment":
            await client.set_adjustment(**{self.field: value})
        elif self.writer == "processing":
            await client.set_mapping(str(value))
        else:
            await client.set_config({self.section: {self.field: value}})

    def schema(self, hub: HyperHDRHub) -> dict[str, Any]:
        if self.section == "color":
            node = hub.schema_property("color", "channelAdjustment")
            items = node.get("items", {}) if isinstance(node, dict) else {}
            return items.get("properties", {}).get(self.field, {}) if isinstance(items, dict) else {}
        return hub.schema_property(self.section, self.field)


@dataclass(frozen=True, kw_only=True)
class NumberSetting(Setting):
    minimum: float
    maximum: float
    step: float
    unit: str | None = None
    #: Shown value = stored value * scale (fractions as percent).
    scale: float = 1
    mode: Literal["slider", "box", "auto"] = "slider"
    #: Keep these bounds even if the schema allows more (a usable slider).
    fixed_range: bool = False


@dataclass(frozen=True, kw_only=True)
class SelectSetting(Setting):
    options: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class SwitchSetting(Setting):
    pass


NUMBERS: tuple[NumberSetting, ...] = (
    NumberSetting(
        key="brightness_gain",
        section="color",
        field="luminanceGain",
        writer="adjustment",
        minimum=0,
        maximum=2,
        step=0.01,
        scale=100,
        unit="%",
        fixed_range=True,
        icon="mdi:brightness-6",
    ),
    NumberSetting(
        key="saturation_gain",
        section="color",
        field="saturationGain",
        writer="adjustment",
        minimum=0,
        maximum=2,
        step=0.01,
        scale=100,
        unit="%",
        fixed_range=True,
        icon="mdi:palette",
    ),
    NumberSetting(
        key="gamma",
        section="color",
        field="gamma",
        writer="adjustment",
        minimum=0.5,
        maximum=4,
        step=0.05,
        fixed_range=True,
        icon="mdi:gamma",
    ),
    NumberSetting(
        key="backlight",
        section="color",
        field="backlightThreshold",
        writer="adjustment",
        minimum=0,
        maximum=0.2,
        step=0.001,
        scale=100,
        unit="%",
        fixed_range=True,
        icon="mdi:lightbulb-on-10",
    ),
    NumberSetting(
        key="power_limit",
        section="color",
        field="powerLimit",
        writer="adjustment",
        minimum=0,
        maximum=1,
        step=0.01,
        scale=100,
        unit="%",
        enabled=False,
        icon="mdi:flash-triangle",
    ),
    NumberSetting(
        key="scale_output",
        section="color",
        field="scaleOutput",
        writer="adjustment",
        minimum=0,
        maximum=2,
        step=0.01,
        scale=100,
        unit="%",
        enabled=False,
        icon="mdi:arrow-expand-vertical",
    ),
    NumberSetting(
        key="smoothing_time",
        section="smoothing",
        field="time_ms",
        minimum=25,
        maximum=5000,
        step=5,
        unit="ms",
        mode="box",
        icon="mdi:timer-outline",
    ),
    NumberSetting(
        key="smoothing_frequency",
        section="smoothing",
        field="updateFrequency",
        minimum=20,
        maximum=200,
        step=1,
        unit="Hz",
        enabled=False,
        icon="mdi:sine-wave",
    ),
    NumberSetting(
        key="blackborder_threshold",
        section="blackborderdetector",
        field="threshold",
        minimum=0,
        maximum=100,
        step=1,
        unit="%",
        enabled=False,
        icon="mdi:border-none-variant",
    ),
    NumberSetting(
        key="grabber_brightness",
        section="videoGrabber",
        field="hardware_brightness",
        scope="server",
        minimum=-255,
        maximum=255,
        step=1,
        mode="box",
        enabled=False,
        icon="mdi:brightness-5",
    ),
    NumberSetting(
        key="grabber_contrast",
        section="videoGrabber",
        field="hardware_contrast",
        scope="server",
        minimum=-255,
        maximum=255,
        step=1,
        mode="box",
        enabled=False,
        icon="mdi:contrast-box",
    ),
    NumberSetting(
        key="grabber_saturation",
        section="videoGrabber",
        field="hardware_saturation",
        scope="server",
        minimum=-255,
        maximum=255,
        step=1,
        mode="box",
        enabled=False,
        icon="mdi:palette-outline",
    ),
    NumberSetting(
        key="grabber_hue",
        section="videoGrabber",
        field="hardware_hue",
        scope="server",
        minimum=-255,
        maximum=255,
        step=1,
        mode="box",
        enabled=False,
        icon="mdi:looks",
    ),
    *(
        NumberSetting(
            key=f"crop_{side.lower()}",
            section="videoGrabber",
            field=f"crop{side}",
            scope="server",
            minimum=0,
            maximum=500,
            step=1,
            unit="px",
            mode="box",
            enabled=False,
            icon="mdi:crop",
        )
        for side in ("Top", "Bottom", "Left", "Right")
    ),
)

SELECTS: tuple[SelectSetting, ...] = (
    SelectSetting(
        key="processing",
        section="color",
        field="imageToLedMappingType",
        writer="processing",
        options=("advanced", "multicolor_mean", "unicolor_mean", "weighted"),
        icon="mdi:image-filter-center-focus",
    ),
    SelectSetting(
        key="color_temperature",
        section="color",
        field="temperatureSetting",
        writer="adjustment",
        options=("disabled", "cold", "neutral", "warm", "custom"),
        icon="mdi:thermometer",
    ),
    SelectSetting(
        key="smoothing_type",
        section="smoothing",
        field="type",
        options=("Stepper", "YuvInterpolator", "RgbInterpolator", "HybridInterpolator", "HybridRgbInterpolator"),
        icon="mdi:chart-bell-curve-cumulative",
    ),
    SelectSetting(
        key="blackborder_mode",
        section="blackborderdetector",
        field="mode",
        options=("default", "classic", "osd", "letterbox"),
        enabled=False,
        icon="mdi:border-outside",
    ),
)

SWITCHES: tuple[SwitchSetting, ...] = (
    SwitchSetting(key="continuous_output", section="smoothing", field="continuousOutput", icon="mdi:repeat"),
    SwitchSetting(key="anti_flickering", section="smoothing", field="antiFlickeringFilter", icon="mdi:filter-outline"),
    SwitchSetting(key="background_effect", section="backgroundEffect", field="enable", icon="mdi:wallpaper"),
    SwitchSetting(key="boot_effect", section="foregroundEffect", field="enable", icon="mdi:play-box-outline"),
    SwitchSetting(
        key="auto_tone_mapping",
        section="automaticToneMapping",
        field="enable",
        icon="mdi:hdr-off",
    ),
    SwitchSetting(
        key="signal_detection",
        section="videoGrabber",
        field="signalDetection",
        scope="server",
        enabled=False,
        icon="mdi:signal",
    ),
)


def schema_bounds(setting: NumberSetting, hub: HyperHDRHub) -> tuple[float, float]:
    """Bounds of a number, narrowed or widened by the server schema."""
    if setting.fixed_range:
        return setting.minimum, setting.maximum
    node = setting.schema(hub)
    low = node.get("minimum", setting.minimum)
    high = node.get("maximum", setting.maximum)
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)) or low >= high:
        return setting.minimum, setting.maximum
    return float(low), float(high)


def schema_options(setting: SelectSetting, hub: HyperHDRHub) -> list[str]:
    node = setting.schema(hub)
    enum = node.get("enum")
    if isinstance(enum, list) and enum and all(isinstance(item, str) for item in enum):
        return list(enum)
    return list(setting.options)
