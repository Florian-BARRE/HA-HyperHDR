# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0b6] - 2026-10-21

### Fixed

- Name prefix: entity ids are made from the English names, whatever Home
  Assistant's language, as the README and ESPHome configurations expect. In a
  Home Assistant in French, 0.1.0b5 made
  `binary_sensor.salon_ambilight_hyperhdr_hub_connecte` instead of
  `…_hub_connected`, `…_hub_temperature_du_cpu` instead of
  `…_hub_cpu_temperature`. Entries named by 0.1.0b5 are named again, once,
  after the update.

## [0.1.0b5] - 2026-10-21

### Added

- Name prefix, in the options: with `salon-ambilight-hyperhdr`, the server
  becomes `salon-ambilight-hyperhdr-hub` and each strip
  `salon-ambilight-hyperhdr-<its HyperHDR name, spaces as _>`. Saving it renames
  the devices (names typed by hand on them go) and recreates the entity ids
  from the device and entity names, without the area (the prefix holds the
  room): `sensor.salon_ambilight_hyperhdr_hub_cpu_temperature`. Automations and
  dashboards using the old ids must be updated.

## [0.1.0b4] - 2026-10-21

### Added

- Power off and restart the machine cleanly, over SSH: in the options, the
  user and password of the machine (nothing to install on it, SSH turned on).
  Saving checks them and learns the machine's SSH key; **Power off** and
  **Restart** buttons then appear on the server device. They run
  `sudo systemctl poweroff` / `reboot`, the password handed to sudo.

### Fixed

- The options said the host health came every minute: it is every 30 s.

### Changed

- Tests: SSH against a server run by the tests, and against a real OpenSSH
  with a real sudo in CI (`scripts/ssh-test-host.sh`, where `systemctl` only
  writes down what it is asked).

## [0.1.0b3] - 2026-10-21

### Fixed

- After HyperHDR restarted (its machine turned off and on), the integration
  failed to set up with "No Authorization" and asked to reconfigure. It kept
  the login token HyperHDR gives for the admin password, but HyperHDR makes a
  new one each time it starts. The integration now keeps no token: it logs in
  at each connection, with the password given, else HyperHDR's default one.
  Entries made before are moved over by themselves.
- A refused default password is not sent again (HyperHDR blocks every login,
  its web interface's too, after 10 refused ones): the integration goes on
  without admin rights.

### Changed

- The live tests restart the real HyperHDR (`scripts/hyperhdr.sh`).

## [0.1.0b2] - 2026-10-20

### Fixed

- CPU, memory, CPU temperature and undervoltage stayed unknown: HyperHDR
  measures the host only when asked, and the integration now asks every 30 s.

### Changed

- CI: `actions/checkout` v6 and `setup-uv` v7 (Node 24).
- README: buttons to add the repository in HACS and to start the setup.

## [0.1.0b1] - 2026-10-20

First beta, to test from HACS ("Show beta versions").

### Added

- The integration: config flow with network discovery (SSDP), admin password
  exchanged for a token, reauthentication, reconfiguration and options.
- One WebSocket per running instance, push updates only, automatic
  reconnection.
- A server device (connection, undervoltage, CPU, temperature, memory,
  capture rate, grabber, video mode, version, captured picture camera, grabber
  and crop settings) and a device per instance (light, components, source,
  color adjustments, smoothing and black border settings, visible source,
  rates, LED colors camera, clear buttons).
- Services: `set_color`, `set_effect`, `clear`, `get_config`, `set_config`,
  `backup`.
- English and French translations, diagnostics.
- Tests: unit tests, and end-to-end tests against a real HyperHDR 22 in CI.
- Docs: HyperHDR API map and entities.

[0.1.0b6]: https://github.com/Florian-BARRE/HA-HyperHDR/releases/tag/v0.1.0b6
[0.1.0b5]: https://github.com/Florian-BARRE/HA-HyperHDR/releases/tag/v0.1.0b5
[0.1.0b4]: https://github.com/Florian-BARRE/HA-HyperHDR/releases/tag/v0.1.0b4
[0.1.0b3]: https://github.com/Florian-BARRE/HA-HyperHDR/releases/tag/v0.1.0b3
[0.1.0b2]: https://github.com/Florian-BARRE/HA-HyperHDR/releases/tag/v0.1.0b2
[0.1.0b1]: https://github.com/Florian-BARRE/HA-HyperHDR/releases/tag/v0.1.0b1
