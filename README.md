# HA-HyperHDR

A Home Assistant integration for [HyperHDR](https://github.com/awawa-dev/HyperHDR),
the ambient lighting software: its lights, components, color settings, the
health of the machine it runs on and the picture it captures, in Home
Assistant, at almost no cost in resources.

[![Validate](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/validate.yml/badge.svg)](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/validate.yml)
[![Tests](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/tests.yml/badge.svg)](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/tests.yml)

> **Status: in development, not released yet.** Tested against a real
> HyperHDR 22 on every change.

## Why

Home Assistant's Hyperion integration does not set up with HyperHDR, and the
community [hyperhdr-ha](https://github.com/mjoshd/hyperhdr-ha) integration
covers the lights, components and smoothing but not the host's state, the
captured picture or most settings. This one follows what HyperHDR's own web
interface offers, through the same API.

## Light on resources

- **One WebSocket per instance**, kept open. HyperHDR pushes every change
  (components, sources, adjustments, settings, instances); nothing is polled.
- **Host health** (CPU, temperature, memory, undervoltage) and frame rates
  come with HyperHDR's own performance updates, once a minute.
- **The cameras stream only while someone looks.** The captured picture
  arrives as JPEG from HyperHDR and is passed through without decoding; the
  stream stops 15 s after the last viewer.
- Reconnects by itself (1 s, then up to a minute between tries).

## Installation

HACS, once released: _HACS → ⋮ → Custom repositories →_
`https://github.com/Florian-BARRE/HA-HyperHDR`, category _Integration_,
install **HyperHDR**, restart Home Assistant.

Then _Settings → Devices & services_: HyperHDR is usually discovered on the
network; otherwise _Add integration → HyperHDR_ with the address of the
machine and the web port (8090).

**Admin password.** It unlocks the settings, the captured picture and the
configuration services. Left empty, HyperHDR's default password is tried;
without admin rights the lights, components, adjustments, sources and host
health still work. The password is not stored: HyperHDR gives a token in
exchange, and asks again (reauthentication) if the password changes.

Needs HyperHDR 21 or newer, and Home Assistant 2026.8 or newer.

## Devices and entities

One device for the server, one per running HyperHDR instance. Entities
marked _off_ are disabled by default; _admin_ ones need the admin password.

### Server

| Entity                                   | Type          | Notes                                          |
| ---------------------------------------- | ------------- | ---------------------------------------------- |
| Connected                                | binary sensor | Stays available when the connection drops      |
| Undervoltage                             | binary sensor | Raspberry Pi power supply                      |
| CPU, CPU temperature, Memory             | sensors       | From HyperHDR's performance updates            |
| Capture rate                             | sensor (fps)  |                                                |
| Grabber, Video mode                      | sensors       | Current device and resolution                  |
| Version                                  | sensor        |                                                |
| Captured picture                         | camera        | _admin_, on demand                             |
| Grabber brightness, contrast, saturation, hue | numbers  | _off_, _admin_                                 |
| Crop top, bottom, left, right            | numbers       | _off_, _admin_                                 |
| Signal detection                         | switch        | _off_, _admin_                                 |

### Each instance

| Entity                                      | Type     | Notes                                                       |
| ------------------------------------------- | -------- | ----------------------------------------------------------- |
| _(instance name)_                           | light    | On/off is the instance; color and effects above the capture |
| LED output, Video capture, Smoothing, Black border detection, HDR tone mapping | switches | HyperHDR components |
| System capture, Forwarder                   | switches | _off_                                                       |
| Source                                      | select   | Automatic, or a source forced on the LEDs                   |
| Processing, Color temperature               | selects  |                                                             |
| Smoothing type, Black border mode           | selects  | _admin_                                                     |
| Brightness, Saturation, Gamma, Backlight threshold | numbers | Color adjustments                                      |
| Power limit, Output scale                   | numbers  | _off_                                                       |
| Smoothing time                              | number   | _admin_                                                     |
| Smoothing frequency, Black border threshold | numbers  | _off_, _admin_                                              |
| Continuous output, Anti-flickering filter, Background effect, Boot effect, Automatic tone mapping | switches | _admin_ |
| Visible source                              | sensor   | What drives the LEDs now, with every source as attributes   |
| Output rate, LEDs                           | sensors  |                                                             |
| LED rate                                    | sensor   | _off_                                                       |
| Average color                               | sensor   | _off_, read every 15 s while enabled (HyperHDR does not push it) |
| Give back to capture                        | button   | Clears the integration's color or effect                    |
| Clear all sources                           | button   | _off_                                                       |
| LED colors                                  | camera   | _off_, the LEDs drawn on their layout, on demand            |

Ranges and choices of the settings come from the server's own schema, so a
newer HyperHDR brings its new options.

### The light

- **On / off** is the instance (HyperHDR's `ALL` component).
- **A color or an effect** goes on the integration's priority (128 by
  default, above the capture at 240). The effect `Capture` gives the LEDs back
  to the capture; `Solid` keeps the last color.
- **Brightness** is the luminance gain (full brightness = 1.0).

## Services

| Service                        | Does                                                                  |
| ------------------------------ | --------------------------------------------------------------------- |
| `ha_hyperhdr.set_color`        | A color on a light, with a priority and a duration (ms)               |
| `ha_hyperhdr.set_effect`       | An effect, with a priority and a duration                             |
| `ha_hyperhdr.clear`            | Removes a priority (the integration's by default)                     |
| `ha_hyperhdr.get_config`       | Returns an instance's whole configuration (_admin_)                   |
| `ha_hyperhdr.set_config`       | Writes settings; a section may be partial, HyperHDR merges it (_admin_) |
| `ha_hyperhdr.backup`           | Returns HyperHDR's full backup (_admin_)                              |

```yaml
action: ha_hyperhdr.set_config
data:
  config_entry_id: 01J…
  config:
    smoothing:
      time_ms: 200
```

## Options

| Option                       | Default  | What it does                                                 |
| ---------------------------- | -------- | ------------------------------------------------------------ |
| Priority of Home Assistant   | 128      | Priority of colors and effects set from Home Assistant       |
| Host health and frame rates  | on       | Subscribes to HyperHDR's performance updates                 |
| Captured picture rate        | 10 fps   | Frame rate of the captured picture while it is viewed        |
| LED colors refresh           | 200 ms   | Refresh of the LED colors camera while it is viewed          |

## Documentation

- [HyperHDR API map](docs/api.md): what HyperHDR exposes, read from its source.
- [Entities](docs/entities.md): the entities as first proposed.

## Development

```bash
uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements_test.txt
.venv/bin/pytest                          # unit tests
HYPERHDR_HOST=127.0.0.1 .venv/bin/pytest  # plus end-to-end against a HyperHDR
```

The CI starts a real HyperHDR (Linux build) and runs the end-to-end tests
against it.

## Related

- [Vivid Cards](https://github.com/Florian-BARRE/vivid-cards): Lovelace cards
  for Home Assistant; a HyperHDR card working with this integration is planned.

## License

[MIT](LICENSE)
