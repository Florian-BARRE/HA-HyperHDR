# Contributing

## Layout

```
custom_components/ha_hyperhdr/
  api.py            WebSocket client of HyperHDR's JSON API (no Home Assistant import).
  state.py          Instance and server state, built from pushed updates (pure).
  hub.py            One connection per running instance, reconnections, coordinators.
  settings.py       The HyperHDR settings exposed as entities, declared once.
  entity.py         Server and instance devices, base entities, error handling.
  config_flow.py    Discovery (SSDP), password for a token, reauth, reconfigure, options.
  light.py …        One file per platform.
  services.py       Configuration and backup services.
  brand/            Icon shown by Home Assistant and HACS.
tests/              Unit tests, and end-to-end tests against a real HyperHDR.
docs/               HyperHDR API map, entities.
```

## Principles

- **Push, never poll.** Subscribe to what HyperHDR sends; the only polled
  entity (average color) is disabled by default.
- **On demand.** Streams (captured picture, LED colors) start when someone
  looks and stop after.
- **The server's schema decides.** Ranges and choices of settings come from
  `config getschema` when available.
- **Plain Python below Home Assistant.** `api.py` and `state.py` import
  nothing from Home Assistant and are tested on their own.

## Tests

```bash
uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest                          # unit tests
HYPERHDR_HOST=127.0.0.1 .venv/bin/pytest  # plus end-to-end against a HyperHDR
```

A local HyperHDR for the end-to-end tests (Linux x86_64):

```bash
curl -sSLO https://github.com/awawa-dev/HyperHDR/releases/download/v22.0.0.0/HyperHDR-22.0.0-Linux-x86_64.tar.gz
mkdir -p hyperhdr data && tar -xzf HyperHDR-22.0.0-Linux-x86_64.tar.gz -C hyperhdr
LD_LIBRARY_PATH=hyperhdr/lib/hyperhdr hyperhdr/bin/hyperhdr -u "$PWD/data" --service
```

The CI does the same on every push and pull request.

## Releasing

1. Set the version in `custom_components/ha_hyperhdr/manifest.json` and
   `pyproject.toml`: `0.2.0b1` for a beta, `0.2.0` for a release.
2. Add its entry to `CHANGELOG.md` (`## [0.2.0b1] - date`) and the link at
   the bottom.
3. Merge into `main` and push.

The **Auto release** workflow sees a version without a release, runs the
checks, and publishes it with the changelog entry and `ha_hyperhdr.zip`
(what HACS installs). Versions ending in `aN`, `bN` or `rcN` are published as
pre-releases: HACS offers them only with "Show beta versions" on.
