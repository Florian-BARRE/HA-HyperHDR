# HA-HyperHDR

A Home Assistant integration for [HyperHDR](https://github.com/awawa-dev/HyperHDR),
the ambient lighting software: everything its web interface shows and sets,
in Home Assistant, at almost no cost in resources.

> **Status: in development.** Nothing to install yet. The first step is a map
> of HyperHDR's API and the list of entities it will give; the code follows.

## Goals

- **Everything that matters, as entities**: components (capture, LED output,
  smoothing, black borders…), HDR tone mapping, brightness and the usual
  adjustments, effects, priorities, instances.
- **The state of HyperHDR and of its host**: the source on the LEDs, the
  average color, the version, and the health of the machine it runs on
  (CPU, temperature, memory) where HyperHDR reports it.
- **Images on demand**: the LED colors and the captured picture as camera
  entities, streamed only while someone looks at them.
- **The full configuration** through two services (read and write), instead
  of hundreds of entities for settings set once.
- **Light on resources**: one websocket kept open, HyperHDR pushes its
  changes; no polling, nothing running while nothing changes.
- **Easy setup**: discovery on the network, a config flow, the admin password
  when HyperHDR asks for one.

## Why another integration

Home Assistant's Hyperion integration does not set up with HyperHDR, and the
community [hyperhdr-ha](https://github.com/mjoshd/hyperhdr-ha) integration
covers the lights, components, smoothing and LED streams but not the host's
state, the captured picture or the rest of the configuration. This one aims
at the whole of what the HyperHDR interface offers.

## Roadmap

1. Map HyperHDR's JSON API (commands, subscriptions, system information,
   image streams) and agree on the entities.
2. Connection, discovery and config flow.
3. Components, adjustments, effects, priorities, instances.
4. Host state and HyperHDR information.
5. Camera entities for the LED colors and the captured picture.
6. Configuration services.
7. HACS release.

## Related

- [Vivid Cards](https://github.com/Florian-BARRE/vivid-cards): Lovelace
  cards for Home Assistant, whose Ambilight card will use this integration.

## License

[MIT](LICENSE)
