# HA-HyperHDR

A Home Assistant integration for [HyperHDR](https://github.com/awawa-dev/HyperHDR),
the ambient lighting software: its lights, components, color settings, the
health of the machine it runs on and the picture it captures, in Home
Assistant, at almost no cost in resources.

[![Validate](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/validate.yml/badge.svg)](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/validate.yml)
[![Tests](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/tests.yml/badge.svg)](https://github.com/Florian-BARRE/HA-HyperHDR/actions/workflows/tests.yml)

> **Status: beta.** Tested against a real HyperHDR 22 on every change; betas
> come first, so turn on "Show beta versions" in HACS to get them.

## Why

Home Assistant's Hyperion integration does not set up with HyperHDR, and the
community [hyperhdr-ha](https://github.com/mjoshd/hyperhdr-ha) integration
covers the lights, components and smoothing but not the host's state, the
captured picture or most settings. This one follows what HyperHDR's own web
interface offers, through the same API.

## Light on resources

- **One WebSocket per instance**, kept open. HyperHDR pushes every change
  (components, sources, adjustments, settings, instances); nothing is polled.
- **Host health** (CPU, temperature, memory, undervoltage): HyperHDR measures
  it only when asked, so the integration asks every 30 s (its web interface
  asks every second). Frame rates are pushed by HyperHDR, once a minute.
- **The cameras stream only while someone looks.** The captured picture
  arrives as JPEG from HyperHDR and is passed through without decoding; the
  stream stops 15 s after the last viewer.
- Reconnects by itself (1 s, then up to a minute between tries).

## Installation

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Florian-BARRE&repository=HA-HyperHDR&category=integration)

1. Click the button above: it opens HACS in your Home Assistant on this
   repository and offers to add it (answer **Add**).
   Without the button: HACS → ⋮ (top right) → **Custom repositories** →
   repository `https://github.com/Florian-BARRE/HA-HyperHDR`, type
   **Integration** → **Add**.
2. On the HyperHDR page in HACS, click **Download** (bottom right). For a
   beta: ⋮ → **Redownload** → turn on **Show beta versions**, pick the
   latest → **Download**.
3. Restart Home Assistant.
4. HyperHDR is usually discovered on the network (_Settings → Devices &
   services_). Otherwise:

   [![Open your Home Assistant instance and start setting up HyperHDR.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ha_hyperhdr)

   with the address of the machine and the web port (8090).

**Admin password.** It unlocks the settings, the captured picture and the
configuration services. Left empty, HyperHDR's default password is tried;
without admin rights the lights, components, adjustments, sources and host
health still work. A password you give is kept in Home Assistant and sent at
each connection; left empty, nothing is kept. HyperHDR's own login token is
not kept: HyperHDR makes a new one each time it starts, so a token would stop
working after every restart of the machine. A refused default password is not
sent again (HyperHDR blocks every login after 10 refused ones); a refused
password of yours asks for the new one (reauthentication).

**Turning the machine off.** Nothing to do: the integration reconnects by
itself when HyperHDR comes back, as often as needed.

**Powering the machine off cleanly.** Before cutting the power of a Raspberry
Pi, it should shut down. HyperHDR's API cannot do it, so the integration does
it over SSH, with nothing to install on the machine:

1. SSH turned on: in Raspberry Pi Imager, _Services_ tab, "Enable SSH" with
   password authentication (or `sudo raspi-config` → Interface options → SSH).
2. In the integration's options, _Power off and restart (SSH)_: the user and
   password set in Imager. Saving checks them, with a harmless `sudo true`, and
   learns the machine's SSH key.

Two buttons then appear on the server device, **Power off** and **Restart**:
they run `sudo systemctl poweroff` (or `reboot`). The password is also handed
to sudo, so it works whether sudo asks for it or not (Raspberry Pi OS's first
user does not). The machine's SSH key is checked at each use; after
reinstalling the machine, save the SSH options again.

Needs HyperHDR 21 or newer, and Home Assistant 2026.8 or newer.

## Devices and entities

One device for the server, one per running HyperHDR instance. Entities
marked _off_ are disabled by default; _admin_ ones need the admin password.

### Server

| Entity                                   | Type          | Notes                                          |
| ---------------------------------------- | ------------- | ---------------------------------------------- |
| Connected                                | binary sensor | Stays available when the connection drops      |
| Undervoltage                             | binary sensor | Raspberry Pi power supply                      |
| CPU, CPU temperature, Memory             | sensors       | Every 30 s                                     |
| Capture rate                             | sensor (fps)  |                                                |
| Grabber, Video mode                      | sensors       | Current device and resolution                  |
| Version                                  | sensor        |                                                |
| Power off, Restart                       | buttons       | Once SSH is set up in the options              |
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

### Names and entity ids

Home Assistant makes an entity id once, when the entity first appears, and
renaming a device afterwards does not change it. To name everything your own
way at once, set **Name prefix** in the options. With
`salon-ambilight-hyperhdr`:

| Device              | Name                                       | Entity ids                                  |
| ------------------- | ------------------------------------------ | ------------------------------------------- |
| The server          | `salon-ambilight-hyperhdr-hub`             | `sensor.salon_ambilight_hyperhdr_hub_cpu_…` |
| A strip `salon canapé WLED` | `salon-ambilight-hyperhdr-salon_canapé_WLED` | `light.salon_ambilight_hyperhdr_salon_canape_wled` |

Hyphens part the levels, underscores join the words of a strip's name (its
HyperHDR instance name: rename the instance in HyperHDR to change it). Entity
ids can hold neither hyphens nor accents, Home Assistant makes them `_` and
plain letters. Saving the prefix renames the devices, dropping names typed by
hand on them, and recreates the entity ids from the device and entity names,
without the area. Automations, scripts, dashboards and ESPHome configurations
that use the old ids must be updated.

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
| Host health and frame rates  | on       | Host measured every 30 s, frame rates pushed every minute    |
| Captured picture rate        | 10 fps   | Frame rate of the captured picture while it is viewed        |
| LED colors refresh           | 200 ms   | Refresh of the LED colors camera while it is viewed          |
| Name prefix                  | none     | Names the devices `<prefix>-hub` and `<prefix>-<strip>`; see below |
| Power off and restart (SSH)  | off      | User, password and port to power the machine off over SSH    |

## Documentation

- [HyperHDR API map](docs/api.md): what HyperHDR exposes, read from its source.
- [Entities](docs/entities.md): the entities as first proposed.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md): layout, tests against a real
HyperHDR, and how releases (and betas) are published.

## Related

- [Vivid Cards](https://github.com/Florian-BARRE/vivid-cards): Lovelace cards
  for Home Assistant; a HyperHDR card working with this integration is planned.

## License

[MIT](LICENSE). The HyperHDR icon in `brand/` is HyperHDR's own
([awawa-dev/HyperHDR](https://github.com/awawa-dev/HyperHDR), MIT).
