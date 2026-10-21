# HyperHDR API map

What HyperHDR exposes to a client, read from its source code
([awawa-dev/HyperHDR](https://github.com/awawa-dev/HyperHDR) at commit `4ecd855`,
version `24.0.0-beta.0`, October 2026). The web interface uses this same API,
so anything it shows or sets is reachable. To be checked against a running
HyperHDR before each feature is built.

## Transport

| Channel           | Where                                     | Notes                                                          |
| ----------------- | ----------------------------------------- | -------------------------------------------------------------- |
| WebSocket         | web server port, `8090` (`8092` with SSL) | What the web interface uses. Carries JSON and binary frames.   |
| HTTP JSON-RPC     | `http://host:8090/json-rpc`               | One request per call; no subscriptions.                        |
| JSON server (TCP) | own port (`jss-port` in the SSDP reply)   | Line-delimited JSON.                                           |
| MQTT              | broker set in HyperHDR                    | The JSON API over MQTT (`sources/mqtt`).                       |
| SSDP discovery    | `urn:hyperhdr.eu:device:basic:1`          | Replies carry the ports (`hyperhdr-jss-port`, `-fbs-port`…).   |

Choice for the integration: **one WebSocket**. It is the only channel with
push updates and binary images.

## Push updates

`{"command": "serverinfo", "subscribe": [...]}` returns the full state once,
then HyperHDR pushes changes. Available subscriptions (`CallbackAPI.cpp`):

| Subscription              | Pushes                                                       |
| ------------------------- | ------------------------------------------------------------ |
| `components-update`       | A component turned on or off                                 |
| `priorities-update`       | Sources on the LEDs, which one is visible, auto-select       |
| `adjustment-update`       | Color adjustments                                            |
| `videomodehdr-update`     | HDR tone mapping on or off                                   |
| `imageToLedMapping-update`| Processing mode                                              |
| `grabberstate-update`     | Grabber device and video mode                                |
| `instance-update`         | Instances created, started, stopped, renamed                 |
| `settings-update`         | Any setting changed (admin)                                  |
| `leds-update`             | LED layout                                                   |
| `performance-update`      | Performance counters (see below)                             |
| `sessions-update`         | Other HyperHDR servers found on the network                  |
| `token-update`            | Tokens (admin)                                               |
| `benchmark-update`, `lut-calibration-update` | Calibration tools                         |
| `leds-colors`, `live-video` | Used by the streams below                                  |

## State (`serverinfo`, per instance)

- `priorities`: each source with `priority`, `componentId`, `origin`,
  `owner`, `active`, `visible`, remaining `duration_ms`, color for a solid
  color; `priorities_autoselect`.
- `adjustment`: the color adjustments (see commands).
- `effects` (available), `activeEffects` (name, priority, timeout).
- `activeLedColor`, `components` (name, enabled), `videomodehdr`, `leds`
  (layout), `imageToLedMappingType`.
- Server wide: `ledDevices` (drivers), `grabbers` (available video devices,
  their inputs, video modes and hardware controls, the current device and
  mode, HDR LUT), `systemGrabbers`, `sound`, `instance` (list),
  `currentInstance`, `hostname`, `lastError`, `hasCEC`.

`sysinfo`: a `system` block (details to check on a running HyperHDR) and
HyperHDR's `version`, `build`, `id`, `readOnlyMode`.

## Performance counters

`performance-update` (or `performance-counters` with `all` / `resources`)
reports typed entries (`PerformanceCounters.h`):

| Type                  | Meaning                                                  |
| --------------------- | -------------------------------------------------------- |
| `CPU_USAGE`           | Total and per core                                       |
| `RAM_USAGE`           | Total and used physical memory                           |
| `CPU_TEMPERATURE`     | CPU temperature                                          |
| `SYSTEM_UNDERVOLTAGE` | Undervoltage detected (Raspberry Pi)                     |
| `VIDEO_GRABBER`       | Capture fps, frame time, invalid frames                  |
| `INSTANCE`            | Instance fps in and out                                  |
| `LED`                 | LED device fps, frames dropped                           |

Fields are `name`, `param1`…`param4` (meaning by type, as the overview page
shows them) and a `refresh` delay.

## Images

| Command                                   | What comes back                                                         |
| ----------------------------------------- | ----------------------------------------------------------------------- |
| `ledcolors` / `imagestream-start`, `-stop`| The captured picture, **JPEG** in binary WebSocket frames, rate-limited |
| `ledcolors` / `ledstream-start`, `-stop`  | The LED colors, JSON, with an `interval` (≥ 50 ms)                      |
| `current-state` / `average-color`         | Average color of an instance                                            |

The JPEG is encoded by HyperHDR (`encodeJpeg`, scaled down above 800 px),
so a camera entity can relay it as it comes, without decoding.

## Commands

| Command              | Does                                                                                     |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `componentstate`     | `ALL`, `HDR`, `SMOOTHING`, `BLACKBORDER`, `FORWARDER`, `VIDEOGRABBER`, `SYSTEMGRABBER`, `LEDDEVICE` on/off |
| `color`, `effect`, `image` | A solid color, an effect (with args) or an image on a priority, for a duration    |
| `clear`, `clearall`  | Releases a priority, or all                                                              |
| `sourceselect`       | Forces a priority, or back to automatic                                                  |
| `adjustment`         | Channels (red…black), `gamma`, `luminanceGain`, `saturationGain`, `scaleOutput`, backlight, temperature, `powerLimit` |
| `smoothing`          | Smoothing time                                                                           |
| `videomodehdr`       | HDR tone mapping                                                                         |
| `videomode`          | `2D`, `3DSBS`, `3DTAB`                                                                   |
| `video-controls`     | Hardware brightness, contrast, saturation, hue of the grabber                           |
| `video-crop`         | Crop left, right, top, bottom                                                            |
| `processing`         | Mapping type: `multicolor_mean`, `unicolor_mean`, `advanced`, `weighted`                 |
| `instance`           | Create, delete, start, stop, rename, switch to                                           |
| `config`             | `getconfig`, `setconfig`, `getschema` (admin)                                            |
| `save-db`, `load-db` | Full backup and restore (admin; restore restarts HyperHDR)                               |
| `leddevice`          | Discover, properties, identify                                                           |
| `logging`            | Log stream                                                                               |
| `authorize`          | Login, tokens (create, list, delete), pending requests                                   |
| `benchmark`, `lut-*`, `signal-calibration`, `tunnel` | Calibration and tools                                    |

## Authorization

Local API authentication can be turned on. A client logs in with the admin
password or uses a token (`authorize` / `createToken`); configuration and
backups need admin rights. The token HyperHDR returns for the password (the
user token, longer than 36 characters) is made again each time HyperHDR
starts (`AccessManager`: "update HyperHDR user token on startup"), so it is
only good until the next restart; app tokens (36 characters) last but give no
admin rights. The integration therefore keeps the password, not a token, and
logs in at each connection. Ten refused logins (password or user token) in 10
minutes block every login, the web interface's too, for 10 minutes.
