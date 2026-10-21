"""End to end against a real HyperHDR (HYPERHDR_HOST=127.0.0.1 pytest)."""

from __future__ import annotations

import asyncio
import os
import subprocess
from functools import partial

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_hyperhdr.api import HyperHDRClient
from custom_components.ha_hyperhdr.config_flow import validate
from custom_components.ha_hyperhdr.const import DOMAIN

from .conftest import LIVE_HOST, LIVE_PASSWORD, LIVE_PORT, live

pytestmark = [live, pytest.mark.usefixtures("socket_enabled")]


async def _setup(hass: HomeAssistant, extra: dict | None = None, version: int = 2) -> MockConfigEntry:
    """No password given, as most users: HyperHDR's default one is tried."""
    result = await validate(hass, LIVE_HOST, LIVE_PORT, None)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=result["id"],
        version=version,
        data={CONF_HOST: LIVE_HOST, CONF_PORT: LIVE_PORT, **(extra or {})},
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
    assert result["admin"] is True


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


RESTART = os.environ.get("HYPERHDR_RESTART")
restartable = pytest.mark.skipif(RESTART is None, reason="HYPERHDR_RESTART is not set")


async def _restart_hyperhdr(hass: HomeAssistant) -> None:
    """Restarts the real HyperHDR, as when its machine is turned off and on."""
    await hass.async_add_executor_job(partial(subprocess.run, RESTART, shell=True, check=True))


def _connected_sensor(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    return next(
        item.entity_id
        for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if item.entity_id.endswith("connected")
    )


@restartable
async def test_survives_a_restart_of_hyperhdr(hass: HomeAssistant) -> None:
    """HyperHDR makes a new login token at each start: the integration must
    log in again by itself, with its admin rights, and never ask anything."""
    entry = await _setup(hass)
    hub = entry.runtime_data
    assert hub.admin
    connected = _connected_sensor(hass, entry)
    seen: list[str] = []
    unsubscribe = async_track_state_change_event(
        hass, connected, lambda event: seen.append(event.data["new_state"].state)
    )
    await _restart_hyperhdr(hass)
    for _ in range(600):
        if "off" in seen and hass.states.get(connected).state == "on":
            break
        await asyncio.sleep(0.05)
    unsubscribe()
    assert "off" in seen, "the restart was not noticed"
    assert hass.states.get(connected).state == "on", f"not reconnected: {seen}"
    assert entry.state is ConfigEntryState.LOADED
    assert hub.admin, "admin rights lost after the restart"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN), "a reauthentication was started"
    # An admin command still goes through.
    settings = await hub.primary.client.get_config()
    assert "smoothing" in settings


@restartable
async def test_entry_of_0_1_0b2_recovers_after_a_restart(hass: HomeAssistant) -> None:
    """An entry that kept a user token, which a restart of HyperHDR killed."""
    async with aiohttp.ClientSession() as session:
        client = HyperHDRClient(LIVE_HOST, LIVE_PORT, session=session)
        await client.connect()
        reply = await client.request("authorize", subcommand="login", password=LIVE_PASSWORD)
        stale = reply["info"]["token"]
        await client.close()
    await _restart_hyperhdr(hass)
    entry = await _setup(hass, {CONF_TOKEN: stale}, version=1)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.data == {CONF_HOST: LIVE_HOST, CONF_PORT: LIVE_PORT}
    assert entry.runtime_data.admin
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_server_with_its_own_password(hass: HomeAssistant) -> None:
    """No password given and the server has another one than the default: the
    integration goes on without admin rights, and does not try again."""
    other = "another-password"
    async with aiohttp.ClientSession() as session:
        client = HyperHDRClient(LIVE_HOST, LIVE_PORT, session=session)
        await client.connect()
        await client.login(LIVE_PASSWORD)
        await client.request("authorize", subcommand="newPassword", password=LIVE_PASSWORD, newPassword=other)
        await client.close()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN, unique_id="own-password", version=2, data={CONF_HOST: LIVE_HOST, CONF_PORT: LIVE_PORT}
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hub = entry.runtime_data
        assert entry.state is ConfigEntryState.LOADED
        assert not hub.admin
        assert hub.password is None
        assert all(connection.client.password is None for connection in hub.instances.values())
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        await hass.config_entries.async_unload(entry.entry_id)
    finally:
        async with aiohttp.ClientSession() as session:
            client = HyperHDRClient(LIVE_HOST, LIVE_PORT, session=session)
            await client.connect()
            await client.login(other)
            await client.request("authorize", subcommand="newPassword", password=other, newPassword=LIVE_PASSWORD)
            await client.close()


@pytest.mark.skipif(os.environ.get("SSH_TEST_HOST") is None, reason="SSH_TEST_HOST is not set")
async def test_power_off_button(hass: HomeAssistant) -> None:
    """The Power off button, over a real SSH server (scripts/ssh-test-host.sh)."""
    from custom_components.ha_hyperhdr.ssh import check

    user = os.environ.get("SSH_TEST_USER", "hhpi")
    password = os.environ.get("SSH_TEST_PASSWORD", "hh-pass-1234")
    port = int(os.environ.get("SSH_TEST_PORT", "2222"))
    log = os.environ.get("SSH_TEST_LOG", "/tmp/hh-systemctl.log")
    key = await check(LIVE_HOST, port, user, password)
    result = await validate(hass, LIVE_HOST, LIVE_PORT, None)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=result["id"],
        version=2,
        data={CONF_HOST: LIVE_HOST, CONF_PORT: LIVE_PORT},
        options={"ssh_username": user, "ssh_password": password, "ssh_port": port, "ssh_host_key": key},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    buttons = {
        item.unique_id.rsplit("_", 1)[-1]: item.entity_id
        for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if item.domain == "button"
    }
    assert {"poweroff", "reboot"} <= set(buttons)
    await hass.async_add_executor_job(_write, log, "")
    await hass.services.async_call("button", "press", {"entity_id": buttons["poweroff"]}, blocking=True)
    assert (await hass.async_add_executor_job(_read, log)).split() == ["poweroff"]


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as file:
        return file.read()


async def _names(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[list[str], list[str]]:
    from homeassistant.helpers import device_registry as dr

    devices = sorted(
        device.name or "" for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    )
    ids = sorted(item.entity_id for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id))
    return devices, ids


async def test_name_prefix_renames_devices_and_entity_ids(hass: HomeAssistant) -> None:
    """salon-ambilight-hyperhdr: the hub and the strips named the user's way, ids after them."""
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr

    entry = await _setup(hass)
    devices = dr.async_get(hass)
    # A name typed by hand on the strip, and the devices in the living room.
    salon = ar.async_get(hass).async_create("Salon")
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        devices.async_update_device(device.id, area_id=salon.id)
    strip = next(d for d in dr.async_entries_for_config_entry(devices, entry.entry_id) if d.via_device_id)
    devices.async_update_device(strip.id, name_by_user="typed by hand")
    # Home Assistant's default "Entity ID format" puts the area first: the prefix
    # already holds the room, so it must not come twice.

    hass.config_entries.async_update_entry(entry, options={**entry.options, "name_prefix": "salon-ambilight-hyperhdr"})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    names, ids = await _names(hass, entry)
    strip_name = "salon-ambilight-hyperhdr-" + "_".join(entry.runtime_data.instances[0].state.name.split())
    assert names == sorted(["salon-ambilight-hyperhdr-hub", strip_name])
    assert all(device.name_by_user is None for device in dr.async_entries_for_config_entry(devices, entry.entry_id))
    assert "binary_sensor.salon_ambilight_hyperhdr_hub_connected" in ids
    assert "sensor.salon_ambilight_hyperhdr_hub_cpu_temperature" in ids
    strip_slug = strip_name.replace("-", "_").lower()
    assert f"light.{strip_slug}" in ids
    assert f"switch.{strip_slug}_hdr_tone_mapping" in ids
    assert entry.title == "salon-ambilight-hyperhdr"
    assert hass.states.get("sensor.salon_ambilight_hyperhdr_hub_cpu_temperature") is not None

    # Saved again unchanged: nothing moves (a reload does not recreate the ids).
    before = ids
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert (await _names(hass, entry))[1] == before
