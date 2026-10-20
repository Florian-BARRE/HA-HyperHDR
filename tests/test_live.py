"""End to end against a real HyperHDR (HYPERHDR_HOST=127.0.0.1 pytest)."""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_hyperhdr.config_flow import validate
from custom_components.ha_hyperhdr.const import DOMAIN

from .conftest import LIVE_HOST, LIVE_PASSWORD, LIVE_PORT, live

pytestmark = [live, pytest.mark.usefixtures("socket_enabled")]


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    result = await validate(hass, LIVE_HOST, LIVE_PORT, LIVE_PASSWORD)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=result["id"],
        data={CONF_HOST: LIVE_HOST, CONF_PORT: LIVE_PORT, CONF_TOKEN: result["token"]},
        title="HyperHDR",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _wait(hass: HomeAssistant, entity_id: str, state: str, timeout: float = 5) -> None:
    for _ in range(int(timeout * 20)):
        current = hass.states.get(entity_id)
        if current and current.state == state:
            return
        await asyncio.sleep(0.05)
    current = hass.states.get(entity_id)
    raise AssertionError(f"{entity_id} is {current.state if current else None}, expected {state}")


async def test_validate(hass: HomeAssistant) -> None:
    result = await validate(hass, LIVE_HOST, LIVE_PORT, LIVE_PASSWORD)
    assert result["version"]
    assert result["token"] and len(result["token"]) > 36


async def test_setup_and_entities(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    by_domain: dict[str, list[str]] = {}
    for item in entities:
        by_domain.setdefault(item.domain, []).append(item.entity_id)
    print({domain: sorted(ids) for domain, ids in by_domain.items()})
    assert by_domain["light"]
    assert len(by_domain["switch"]) >= 6
    assert hass.states.get(by_domain["light"][0]).state in ("on", "off")
    connected = [eid for eid in by_domain["binary_sensor"] if eid.endswith("connected")]
    assert hass.states.get(connected[0]).state == "on"


async def test_components_and_settings_round_trip(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    registry = er.async_get(hass)
    ids = {
        item.unique_id.split("_", 1)[1]: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    border = ids["0_black_border"]
    before = hass.states.get(border).state
    target = "off" if before == "on" else "on"
    await hass.services.async_call("switch", f"turn_{target}", {"entity_id": border}, blocking=True)
    await _wait(hass, border, target)
    await hass.services.async_call("switch", f"turn_{before}", {"entity_id": border}, blocking=True)
    await _wait(hass, border, before)

    hdr = ids["0_hdr"]
    await hass.services.async_call("switch", "turn_on", {"entity_id": hdr}, blocking=True)
    await _wait(hass, hdr, "on")
    await hass.services.async_call("switch", "turn_off", {"entity_id": hdr}, blocking=True)
    await _wait(hass, hdr, "off")

    gain = ids["0_brightness_gain"]
    await hass.services.async_call("number", "set_value", {"entity_id": gain, "value": 80}, blocking=True)
    await _wait(hass, gain, "80.0")
    await hass.services.async_call("number", "set_value", {"entity_id": gain, "value": 100}, blocking=True)
    await _wait(hass, gain, "100.0")

    smoothing = ids["0_smoothing_time"]
    await hass.services.async_call("number", "set_value", {"entity_id": smoothing, "value": 210}, blocking=True)
    await _wait(hass, smoothing, "210.0")
    await hass.services.async_call("number", "set_value", {"entity_id": smoothing, "value": 150}, blocking=True)
    await _wait(hass, smoothing, "150.0")

    smoothing_type = ids["0_smoothing_type"]
    await hass.services.async_call(
        "select", "select_option", {"entity_id": smoothing_type, "option": "rgbinterpolator"}, blocking=True
    )
    await _wait(hass, smoothing_type, "rgbinterpolator")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": smoothing_type, "option": "hybridrgbinterpolator"}, blocking=True
    )
    await _wait(hass, smoothing_type, "hybridrgbinterpolator")


async def test_light_color_effect_and_source(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    registry = er.async_get(hass)
    ids = {
        item.unique_id.split("_", 1)[1]: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    light = ids["0_light"]
    await hass.services.async_call("light", "turn_on", {"entity_id": light, "rgb_color": [255, 0, 0]}, blocking=True)
    for _ in range(100):
        state = hass.states.get(light)
        if state.attributes.get("effect") == "Solid" and state.attributes.get("hs_color") == (0.0, 100.0):
            break
        await asyncio.sleep(0.05)
    state = hass.states.get(light)
    assert state.attributes["effect"] == "Solid", state.attributes
    assert state.attributes["hs_color"] == (0.0, 100.0)
    source = hass.states.get(ids["0_visible_source"])
    assert source.state == "color", source

    effect = next(name for name in state.attributes["effect_list"] if name not in ("Solid", "Capture"))
    await hass.services.async_call("light", "turn_on", {"entity_id": light, "effect": effect}, blocking=True)
    for _ in range(100):
        if hass.states.get(light).attributes.get("effect") == effect:
            break
        await asyncio.sleep(0.05)
    assert hass.states.get(light).attributes["effect"] == effect

    await hass.services.async_call("button", "press", {"entity_id": ids["0_clear"]}, blocking=True)
    for _ in range(100):
        if hass.states.get(light).attributes.get("effect") == "Capture":
            break
        await asyncio.sleep(0.05)
    assert hass.states.get(light).attributes["effect"] == "Capture"


async def test_get_config_service(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    response = await hass.services.async_call(
        DOMAIN, "get_config", {"config_entry_id": entry.entry_id}, blocking=True, return_response=True
    )
    assert "smoothing" in response["config"]


async def test_reconnects(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    hub = entry.runtime_data
    registry = er.async_get(hass)
    connected = next(
        item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.entity_id.endswith("connected")
    )
    # Drop the socket under the client's feet, as a network cut would.
    ws = hub.primary.client._ws
    await ws.close()
    await _wait(hass, connected, "off")
    await _wait(hass, connected, "on", timeout=10)


async def test_cameras_on_demand(hass: HomeAssistant) -> None:
    import base64

    from homeassistant.components.camera import async_get_image

    entry = await _setup(hass)
    hub = entry.runtime_data
    registry = er.async_get(hass)
    ids = {
        item.unique_id.split("_", 1)[1]: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    # Something to capture: an image on a priority, as a grabber would send.
    width, height = 64, 36
    pixels = bytes((x * 4) % 256 if c == 0 else 120 for _ in range(height) for x in range(width) for c in range(3))
    client = hub.primary.client

    async def feed() -> None:
        for _ in range(30):
            await client.request(
                "image",
                priority=50,
                origin="test",
                duration=2000,
                imagewidth=width,
                imageheight=height,
                imagedata=base64.b64encode(pixels).decode(),
                format="rgb",
            )
            await asyncio.sleep(0.1)

    feeder = asyncio.create_task(feed())
    assert not hub.image_stream.active
    image = await async_get_image(hass, ids["capture"])
    assert image.content_type == "image/jpeg"
    assert image.content[:2] == b"\xff\xd8"
    assert hub.image_stream.active

    # The LED camera: enable it, then read a drawn frame.
    registry.async_update_entity(ids["0_led_colors"], disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    hub = entry.runtime_data
    client = hub.primary.client
    image = await async_get_image(hass, ids["0_led_colors"])
    assert image.content[:2] == b"\xff\xd8"
    assert hub.primary.led_stream.active
    feeder.cancel()
    await client.clear(50)


async def test_second_instance(hass: HomeAssistant) -> None:
    import aiohttp

    from custom_components.ha_hyperhdr.api import HyperHDRClient

    async with aiohttp.ClientSession() as session:
        admin = HyperHDRClient(LIVE_HOST, LIVE_PORT, session=session)
        await admin.connect()
        await admin.login(password=LIVE_PASSWORD)
        await admin.request("instance", subcommand="createInstance", name="Test instance")
        info = await admin.server_info()
        index = max(item["instance"] for item in info["instance"])
        await admin.request("instance", subcommand="startInstance", instance=index)
        await asyncio.sleep(1.5)
        try:
            entry = await _setup(hass)
            hub = entry.runtime_data
            assert index in hub.instances
            lights = [state.entity_id for state in hass.states.async_all("light")]
            assert len(lights) == 2, lights
            await hass.config_entries.async_unload(entry.entry_id)
        finally:
            await admin.request("instance", subcommand="stopInstance", instance=index)
            await asyncio.sleep(0.5)
            await admin.request("instance", subcommand="deleteInstance", instance=index)
            await admin.close()


async def test_host_health(hass: HomeAssistant) -> None:
    """HyperHDR measures the host only when asked: the CPU load and the memory
    fill in a few seconds after the setup."""
    entry = await _setup(hass)
    registry = er.async_get(hass)
    ids = {
        item.unique_id.split("_", 1)[1]: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    for key in ("cpu", "memory"):
        entity_id = ids[key]
        for _ in range(100):
            state = hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                break
            await asyncio.sleep(0.1)
        state = hass.states.get(entity_id)
        assert state is not None
        assert 0 <= float(state.state) <= 100, f"{entity_id} is {state.state}"
