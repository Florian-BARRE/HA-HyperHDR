# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
