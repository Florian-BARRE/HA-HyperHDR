"""State built from HyperHDR messages, as recorded from HyperHDR 22."""

from __future__ import annotations

from custom_components.ha_hyperhdr.state import InstanceState, Performance, ServerState

SERVERINFO = {
    "components": [
        {"enabled": True, "name": "ALL"},
        {"enabled": False, "name": "HDR"},
        {"enabled": True, "name": "SMOOTHING"},
        {"enabled": False, "name": "LEDDEVICE"},
    ],
    "priorities": [
        {
            "active": True,
            "componentId": "EFFECT",
            "origin": "probe@127.0.0.1",
            "owner": "Atomic swirl",
            "priority": 128,
            "visible": True,
        },
        {"active": False, "componentId": "VIDEOGRABBER", "origin": "System", "priority": 240, "visible": False},
    ],
    "priorities_autoselect": True,
    "adjustment": [{"luminanceGain": 0.9, "gamma": 1.5}],
    "effects": [{"name": "Rainbow swirl"}, {"name": "Atomic swirl"}],
    "videomodehdr": 0,
    "imageToLedMappingType": "advanced",
    "leds": [{"hmin": 0, "hmax": 1, "vmin": 0, "vmax": 0.08}],
    "instance": [{"friendly_name": "First LED instance", "instance": 0, "running": True}],
    "hostname": "pi",
    "grabbers": {"active": "V4L2:auto", "current": {"device": "", "videoMode": ""}},
}


def test_instance_load_and_updates() -> None:
    state = InstanceState(index=0)
    state.load(SERVERINFO)
    assert state.name == "First LED instance"
    assert state.components == {"ALL": True, "HDR": False, "SMOOTHING": True, "LEDDEVICE": False}
    assert state.effects == ["Atomic swirl", "Rainbow swirl"]
    assert state.visible and state.visible.owner == "Atomic swirl"
    assert state.led_count == 1

    assert state.apply({"command": "components-update", "data": {"enabled": True, "name": "HDR"}})
    assert state.hdr is True
    assert not state.apply({"command": "components-update", "data": {"enabled": True, "name": "HDR"}})
    assert state.apply({"command": "adjustment-update", "data": [{"luminanceGain": 0.5}]})
    assert state.adjustment["luminanceGain"] == 0.5
    assert state.apply({"command": "settings-update", "data": {"smoothing": {"time_ms": 180}}})
    assert state.settings["smoothing"]["time_ms"] == 180
    assert state.apply({"command": "ledcolors-ledstream-update", "result": {"leds": [1, 2, 3]}, "tan": 4})
    assert state.led_colors == [1, 2, 3]


def test_performance_reports() -> None:
    perf = Performance()
    assert perf.apply({"type": 4, "name": '{"cores":[0.08,0.07],"total":7.95}', "id": -1})
    assert perf.cpu == 8.0
    assert perf.apply({"type": 5, "name": '{"aspect":8,"takenMem":722,"totalPhysMem":8029}', "id": -1})
    assert perf.memory_percent == 9.0
    # The temperature comes as HTML for the web interface.
    assert perf.apply({"type": 6, "name": "<span class='stats-report-ok fw-bold'>52.34</span>", "id": -1})
    assert perf.temperature == 52.3
    assert perf.apply({"type": 7, "name": "0", "id": -1})
    assert perf.undervoltage is False
    assert perf.apply({"type": 1, "name": "USB", "param1": 59.94, "id": 0})
    assert perf.fps[(1, 0)] == 59.9
    assert perf.apply({"type": 1, "id": 0, "remove": 1})
    assert (1, 0) not in perf.fps


def test_server_state() -> None:
    server = ServerState()
    server.load_sysinfo({"hyperhdr": {"id": "abc", "version": "22.0.0"}, "system": {"architecture": "arm64"}})
    server.load(SERVERINFO)
    assert (server.id, server.version, server.hostname) == ("abc", "22.0.0", "pi")
    assert server.instances == {0: ("First LED instance", True)}
    assert server.apply(
        {"command": "performance-update", "data": {"broadcast": [{"type": 4, "name": '{"total": 12}'}]}}
    )
    assert server.performance.cpu == 12
    assert server.apply({"command": "grabberstate-update", "data": {"device": "USB3", "videoMode": "1920x1080x60"}})
    assert server.grabber["current"]["device"] == "USB3"
    assert server.apply(
        {
            "command": "instance-update",
            "data": [
                {"friendly_name": "A", "instance": 0, "running": True},
                {"friendly_name": "B", "instance": 1, "running": True},
            ],
        }
    )
    assert 1 in server.instances
