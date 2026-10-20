"""State of a HyperHDR instance and of its server, kept from pushed updates.

Plain Python, no Home Assistant import: fed by `serverinfo` once, then by
each pushed update (`components-update`, `settings-update`, …).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

#: Performance report types (HyperHDR `PerformanceCounters.h`).
PERF_VIDEO_GRABBER = 1
PERF_INSTANCE = 2
PERF_LED = 3
PERF_CPU = 4
PERF_RAM = 5
PERF_TEMPERATURE = 6
PERF_UNDERVOLTAGE = 7

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class Priority:
    priority: int
    component: str
    origin: str
    owner: str | None
    active: bool
    visible: bool
    rgb: tuple[int, int, int] | None
    duration_ms: int | None

    @classmethod
    def parse(cls, item: dict[str, Any]) -> Priority:
        rgb = None
        value = item.get("value")
        if isinstance(value, dict) and isinstance(value.get("RGB"), list) and len(value["RGB"]) == 3:
            rgb = tuple(int(channel) for channel in value["RGB"])  # type: ignore[assignment]
        duration = item.get("duration_ms")
        return cls(
            priority=int(item.get("priority", 0)),
            component=str(item.get("componentId", "")),
            origin=str(item.get("origin", "")),
            owner=item.get("owner"),
            active=bool(item.get("active", False)),
            visible=bool(item.get("visible", False)),
            rgb=rgb,
            duration_ms=int(duration) if isinstance(duration, (int, float)) else None,
        )


@dataclass
class Performance:
    """Host health and frame rates, from `performance-update`."""

    cpu: float | None = None
    cpu_cores: list[float] = field(default_factory=list)
    memory_used_mb: int | None = None
    memory_total_mb: int | None = None
    temperature: float | None = None
    undervoltage: bool | None = None
    #: fps by (type, id): video grabber, instance, LED device.
    fps: dict[tuple[int, int], float] = field(default_factory=dict)

    @property
    def memory_percent(self) -> float | None:
        if not self.memory_used_mb or not self.memory_total_mb:
            return None
        return round(self.memory_used_mb / self.memory_total_mb * 100, 1)

    def apply(self, report: dict[str, Any]) -> bool:
        """Applies one report; True when something changed."""
        kind = int(report.get("type", 0))
        name = report.get("name", "")
        before = (self.cpu, self.memory_used_mb, self.temperature, self.undervoltage, dict(self.fps))
        if report.get("remove"):
            self.fps.pop((kind, int(report.get("id", -1))), None)
        elif kind == PERF_CPU:
            data = _json(name)
            total = data.get("total")
            if isinstance(total, (int, float)):
                self.cpu = round(float(total), 1)
            cores = data.get("cores")
            if isinstance(cores, list):
                self.cpu_cores = [float(core) for core in cores if isinstance(core, (int, float))]
        elif kind == PERF_RAM:
            data = _json(name)
            if isinstance(data.get("takenMem"), (int, float)):
                self.memory_used_mb = int(data["takenMem"])
            if isinstance(data.get("totalPhysMem"), (int, float)):
                self.memory_total_mb = int(data["totalPhysMem"])
        elif kind == PERF_TEMPERATURE:
            # Sent as HTML for the web interface: "<span class='…'>52.34</span>".
            match = _NUMBER.search(re.sub(r"<[^>]*>", "", str(name)))
            if match:
                self.temperature = round(float(match.group()), 1)
        elif kind == PERF_UNDERVOLTAGE:
            self.undervoltage = str(name).strip().startswith("1")
        elif kind in (PERF_VIDEO_GRABBER, PERF_INSTANCE, PERF_LED):
            fps = report.get("param1")
            if isinstance(fps, (int, float)):
                self.fps[(kind, int(report.get("id", -1)))] = round(float(fps), 1)
        return before != (self.cpu, self.memory_used_mb, self.temperature, self.undervoltage, self.fps)


def _json(text: Any) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    try:
        data = json.loads(str(text))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class InstanceState:
    """Everything known about one instance."""

    index: int
    name: str = ""
    running: bool = True
    components: dict[str, bool] = field(default_factory=dict)
    priorities: list[Priority] = field(default_factory=list)
    autoselect: bool = True
    adjustment: dict[str, Any] = field(default_factory=dict)
    effects: list[str] = field(default_factory=list)
    active_effects: list[dict[str, Any]] = field(default_factory=list)
    hdr: bool = False
    mapping: str | None = None
    led_count: int = 0
    #: HyperHDR settings (admin), merged from every `settings-update`.
    settings: dict[str, Any] = field(default_factory=dict)
    #: LED colors of the LED stream, flat [r, g, b, r, g, b…].
    led_colors: list[int] = field(default_factory=list)
    leds: list[dict[str, Any]] = field(default_factory=list)

    @property
    def visible(self) -> Priority | None:
        return next((item for item in self.priorities if item.visible), None)

    def priority(self, number: int) -> Priority | None:
        return next((item for item in self.priorities if item.priority == number), None)

    def load(self, info: dict[str, Any]) -> None:
        """Fills the state from a `serverinfo` reply."""
        self.components = {
            str(item.get("name")): bool(item.get("enabled"))
            for item in info.get("components", [])
            if isinstance(item, dict)
        }
        self._priorities(info)
        adjustment = info.get("adjustment")
        if isinstance(adjustment, list) and adjustment and isinstance(adjustment[0], dict):
            self.adjustment = dict(adjustment[0])
        self.effects = sorted(
            str(item.get("name")) for item in info.get("effects", []) if isinstance(item, dict) and item.get("name")
        )
        self.active_effects = [item for item in info.get("activeEffects", []) if isinstance(item, dict)]
        self.hdr = bool(info.get("videomodehdr"))
        mapping = info.get("imageToLedMappingType")
        self.mapping = str(mapping) if mapping else None
        leds = info.get("leds")
        if isinstance(leds, list):
            self.leds = [item for item in leds if isinstance(item, dict)]
            self.led_count = len(self.leds)
        for item in info.get("instance", []):
            if isinstance(item, dict) and item.get("instance") == self.index:
                self.name = str(item.get("friendly_name") or self.name)
                self.running = bool(item.get("running", True))

    def _priorities(self, data: dict[str, Any]) -> None:
        self.priorities = [Priority.parse(item) for item in data.get("priorities", []) if isinstance(item, dict)]
        if "priorities_autoselect" in data:
            self.autoselect = bool(data["priorities_autoselect"])

    def apply(self, message: dict[str, Any]) -> bool:
        """Applies a pushed update; True when this instance's state changed."""
        command = message.get("command")
        data = message.get("data")
        if command == "components-update" and isinstance(data, dict):
            name = str(data.get("name"))
            enabled = bool(data.get("enabled"))
            changed = self.components.get(name) != enabled
            self.components[name] = enabled
            if name == "HDR":
                self.hdr = enabled
            return changed
        if command == "priorities-update" and isinstance(data, dict):
            self._priorities(data)
            if isinstance(data.get("activeEffects"), list):
                self.active_effects = [item for item in data["activeEffects"] if isinstance(item, dict)]
            return True
        if command == "adjustment-update" and isinstance(data, list) and data and isinstance(data[0], dict):
            self.adjustment = dict(data[0])
            return True
        if command == "videomodehdr-update" and isinstance(data, dict):
            self.hdr = bool(data.get("videomodehdr"))
            return True
        if command == "imageToLedMapping-update" and isinstance(data, dict):
            self.mapping = str(data.get("imageToLedMappingType") or self.mapping)
            return True
        if command == "settings-update" and isinstance(data, dict):
            for section, value in data.items():
                self.settings[section] = value
            if isinstance(data.get("leds"), list):
                self.leds = [item for item in data["leds"] if isinstance(item, dict)]
                self.led_count = len(self.leds)
            return True
        if command == "leds-update" and isinstance(data, dict) and isinstance(data.get("leds"), list):
            self.leds = [item for item in data["leds"] if isinstance(item, dict)]
            self.led_count = len(self.leds)
            return True
        if command == "ledcolors-ledstream-update":
            result = message.get("result")
            if isinstance(result, dict) and isinstance(result.get("leds"), list):
                self.led_colors = [int(value) for value in result["leds"]]
                return True
        return False


@dataclass
class ServerState:
    """Server-wide state: identity, instances, grabber, host health."""

    id: str = ""
    version: str = ""
    hostname: str = ""
    system: dict[str, Any] = field(default_factory=dict)
    instances: dict[int, tuple[str, bool]] = field(default_factory=dict)
    grabber: dict[str, Any] = field(default_factory=dict)
    performance: Performance = field(default_factory=Performance)
    #: Global settings (video grabber, network…), admin.
    settings: dict[str, Any] = field(default_factory=dict)

    def load_sysinfo(self, info: dict[str, Any]) -> None:
        hyperhdr = info.get("hyperhdr") or {}
        self.id = str(hyperhdr.get("id") or self.id)
        self.version = str(hyperhdr.get("version") or self.version)
        self.system = dict(info.get("system") or {})

    def load(self, info: dict[str, Any]) -> None:
        self.hostname = str(info.get("hostname") or self.hostname)
        self._instances(info.get("instance"))
        grabbers = info.get("grabbers")
        if isinstance(grabbers, dict):
            self.grabber = grabbers

    def _instances(self, items: Any) -> bool:
        if not isinstance(items, list):
            return False
        instances = {
            int(item["instance"]): (str(item.get("friendly_name", "")), bool(item.get("running", False)))
            for item in items
            if isinstance(item, dict) and isinstance(item.get("instance"), int)
        }
        changed = instances != self.instances
        self.instances = instances
        return changed

    def apply(self, message: dict[str, Any]) -> bool:
        command = message.get("command")
        data = message.get("data")
        if command == "performance-update" and isinstance(data, dict):
            if isinstance(data.get("broadcast"), list):
                return any([self.performance.apply(item) for item in data["broadcast"] if isinstance(item, dict)])
            return self.performance.apply(data)
        if command == "instance-update":
            return self._instances(data)
        if command == "grabberstate-update" and isinstance(data, dict):
            self.grabber = {**self.grabber, "current": {**self.grabber.get("current", {}), **data}}
            return True
        if command == "settings-update" and isinstance(data, dict):
            self.settings.update(data)
            return True
        return False
