# Proposed entities

**Proposal, to be agreed before the code.** Built on [the API map](api.md).
One Home Assistant device for the HyperHDR server, one per instance.

Entities marked _off_ are disabled by default (enable them when needed);
_config_ ones sit in the device's configuration section.

## Server device

| Entity                       | Type          | From                                 |
| ---------------------------- | ------------- | ------------------------------------ |
| Connected                    | binary sensor | WebSocket state                      |
| CPU usage                    | sensor (%)    | `CPU_USAGE`                          |
| CPU temperature              | sensor (°C)   | `CPU_TEMPERATURE`                    |
| Memory used                  | sensor (%)    | `RAM_USAGE`                          |
| Undervoltage                 | binary sensor | `SYSTEM_UNDERVOLTAGE` (problem)      |
| Version                      | sensor        | `sysinfo` (an update entity later)   |
| Grabber, video mode          | sensors       | `grabbers.current` (device, resolution, fps) |
| Capture rate                 | sensor (fps)  | `VIDEO_GRABBER`                      |
| Captured picture             | camera        | `imagestream`, on demand             |
| Hardware brightness, contrast, saturation, hue | numbers, _config_ | `video-controls`  |
| Crop left, right, top, bottom | numbers, _config_, _off_ | `video-crop`               |

## Instance device (one per instance)

| Entity                       | Type          | From                                       |
| ---------------------------- | ------------- | ------------------------------------------ |
| Ambilight                    | light         | color, brightness, effects on a priority   |
| Instance                     | switch        | `ALL`                                      |
| LED output                   | switch        | `LEDDEVICE`                                |
| Video capture                | switch        | `VIDEOGRABBER`                             |
| System capture               | switch, _off_ | `SYSTEMGRABBER`                            |
| Smoothing                    | switch        | `SMOOTHING`                                |
| Black borders                | switch        | `BLACKBORDER`                              |
| Forwarder                    | switch, _off_ | `FORWARDER`                                |
| HDR tone mapping             | switch        | `videomodehdr`                             |
| Source                       | select        | `sourceselect`: auto or a visible priority |
| Video mode                   | select, _config_ | `2D`, `3DSBS`, `3DTAB`                  |
| Processing                   | select, _config_ | mapping type                            |
| Visible source               | sensor        | `priorities` (component, origin)           |
| Average color                | sensor        | `average-color`                            |
| Output rate                  | sensor (fps)  | `INSTANCE`, `LED`                          |
| Brightness (luminance gain), saturation, gamma, backlight | numbers, _config_ | `adjustment` |
| Smoothing time               | number, _config_ | `smoothing`                             |
| Clear                        | button        | `clear` the integration's priority         |
| LED colors                   | camera, _off_ | `ledstream`, drawn as an image, on demand  |

## Services

| Service                 | Does                                              |
| ----------------------- | ------------------------------------------------- |
| `get_config` / `set_config` | Reads or writes HyperHDR's configuration (admin) |
| `set_color`, `set_effect`   | With a priority and a duration                |
| `backup`                | Saves HyperHDR's database to a file               |

## Resources

- One WebSocket per server, subscriptions only: nothing is polled.
- Performance counters only while a performance entity is enabled.
- Streams only while a camera is viewed; the JPEG comes encoded from
  HyperHDR and is passed through.
