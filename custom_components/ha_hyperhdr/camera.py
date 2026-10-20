"""Cameras: the picture HyperHDR captures, and the colors of the LEDs.

Both streams run only while someone looks: the first frame request starts
them, they stop a few seconds after the last one. The captured picture comes
from HyperHDR as JPEG and is passed through as is; the LED colors are drawn
on their layout.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import time
from collections.abc import Callable

from aiohttp import web
from homeassistant.components.camera import Camera, async_get_still_stream
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HyperHDRError
from .const import STREAM_IDLE
from .entity import HyperHDRInstanceEntity, HyperHDRServerEntity
from .hub import HyperHDRConfigEntry, HyperHDRHub, InstanceConnection, _Stream

PARALLEL_UPDATES = 0

CAPTURE = EntityDescription(key="capture", translation_key="capture")
LEDS = EntityDescription(key="led_colors", translation_key="led_colors", entity_registry_enabled_default=False)

#: Size of the LED preview.
PREVIEW_SIZE = (320, 180)
#: Longest wait for the first frame of a stream.
FIRST_FRAME_TIMEOUT = 3.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyperHDRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    entities: list[Camera] = []
    # The image stream needs admin rights.
    if hub.admin:
        entities.append(CaptureCamera(hub, CAPTURE))
    entities.extend(LedCamera(hub, connection, LEDS) for connection in hub.instances.values())
    async_add_entities(entities)


class _OnDemand:
    """Keeps a stream running while frames are asked for."""

    def __init__(self, hass: HomeAssistant, stream: _Stream) -> None:
        self._hass = hass
        self._stream = stream
        self._held = False
        self._timer: asyncio.TimerHandle | None = None
        self.frame: bytes | None = None
        self.frame_at = 0.0
        self._new = asyncio.Event()

    @callback
    def push(self, frame: bytes) -> None:
        self.frame = frame
        self.frame_at = time.monotonic()
        self._new.set()

    async def touch(self) -> None:
        """A viewer asked for a frame: run the stream a little longer."""
        if not self._held:
            await self._stream.acquire()
            self._held = True
        if self._timer:
            self._timer.cancel()
        self._timer = self._hass.loop.call_later(STREAM_IDLE, lambda: self._hass.async_create_task(self.release()))

    async def release(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._held:
            self._held = False
            await self._stream.release()

    async def wait_frame(self, timeout: float) -> bytes | None:
        """The next frame, or the last one if none comes in time."""
        self._new.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._new.wait(), timeout)
        return self.frame


class CaptureCamera(HyperHDRServerEntity, Camera):
    """The picture HyperHDR captures."""

    _attr_frame_interval = 0.1

    def __init__(self, hub: HyperHDRHub, description: EntityDescription) -> None:
        HyperHDRServerEntity.__init__(self, hub, description)
        Camera.__init__(self)
        self._demand = _OnDemand(hub.hass, hub.image_stream)
        self.content_type = "image/jpeg"
        self._remove: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove = self.hub.add_image_listener(self._demand.push)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove:
            self._remove()
        await self._demand.release()
        await super().async_will_remove_from_hass()

    @property
    def is_streaming(self) -> bool:
        return self.hub.image_stream.active

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        try:
            await self._demand.touch()
        except HyperHDRError:
            return self._demand.frame
        if self._demand.frame and time.monotonic() - self._demand.frame_at < 1:
            return self._demand.frame
        return await self._demand.wait_frame(FIRST_FRAME_TIMEOUT)

    async def handle_async_mjpeg_stream(self, request: web.Request) -> web.StreamResponse:
        interval = 1 / max(1, self.hub.stream_fps)

        async def next_frame() -> bytes | None:
            await self._demand.touch()
            return await self._demand.wait_frame(max(interval * 4, 1))

        return await async_get_still_stream(request, next_frame, self.content_type, interval)


def render_leds(colors: list[int], leds: list[dict], size: tuple[int, int] = PREVIEW_SIZE) -> bytes:
    """Draws each LED's area of the picture in its color (runs in an executor)."""
    from PIL import Image, ImageDraw

    width, height = size
    image = Image.new("RGB", size, (12, 12, 12))
    draw = ImageDraw.Draw(image)
    for index, led in enumerate(leds):
        base = index * 3
        if base + 2 >= len(colors):
            break
        try:
            box = (
                round(float(led.get("hmin", 0)) * width),
                round(float(led.get("vmin", 0)) * height),
                round(float(led.get("hmax", 0)) * width) - 1,
                round(float(led.get("vmax", 0)) * height) - 1,
            )
        except (TypeError, ValueError):
            continue
        if box[2] < box[0] or box[3] < box[1]:
            continue
        draw.rectangle(box, fill=tuple(colors[base : base + 3]))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


class LedCamera(HyperHDRInstanceEntity, Camera):
    """The colors of the LEDs, drawn on their layout."""

    def __init__(self, hub: HyperHDRHub, connection: InstanceConnection, description: EntityDescription) -> None:
        HyperHDRInstanceEntity.__init__(self, hub, connection, description)
        Camera.__init__(self)
        self._demand = _OnDemand(hub.hass, connection.led_stream)
        self.content_type = "image/jpeg"
        self._remove: Callable[[], None] | None = None
        self._rendered: tuple[int, bytes] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove = self.connection.add_led_listener(lambda colors: self._demand.push(b""))

    async def async_will_remove_from_hass(self) -> None:
        if self._remove:
            self._remove()
        await self._demand.release()
        await super().async_will_remove_from_hass()

    @property
    def is_streaming(self) -> bool:
        return self.connection.led_stream.active

    async def _render(self) -> bytes | None:
        colors = list(self.state_data.led_colors)
        if not colors:
            return None
        key = hash(tuple(colors))
        if self._rendered and self._rendered[0] == key:
            return self._rendered[1]
        image = await self.hass.async_add_executor_job(render_leds, colors, list(self.state_data.leds))
        self._rendered = (key, image)
        return image

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        try:
            await self._demand.touch()
        except HyperHDRError:
            return await self._render()
        if not self.state_data.led_colors:
            await self._demand.wait_frame(FIRST_FRAME_TIMEOUT)
        return await self._render()

    async def handle_async_mjpeg_stream(self, request: web.Request) -> web.StreamResponse:
        interval = max(0.05, self.hub.led_interval / 1000)

        async def next_frame() -> bytes | None:
            await self._demand.touch()
            await self._demand.wait_frame(max(interval * 4, 1))
            return await self._render()

        return await async_get_still_stream(request, next_frame, self.content_type, interval)
