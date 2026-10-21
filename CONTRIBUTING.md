# Contributing

## Layout

```
custom_components/ha_hyperhdr/
  api.py            WebSocket client of HyperHDR's JSON API (no Home Assistant import).
  state.py          Instance and server state, built from pushed updates (pure).
  hub.py            One connection per running instance, reconnections, coordinators.
  ssh.py            Clean power off / restart of the machine over SSH (no HA dependency).
  settings.py       The HyperHDR settings exposed as entities, declared once.
  entity.py         Server and instance devices, base entities, error handling.
  config_flow.py    Discovery (SSDP), password (kept, never a token), reauth, reconfigure, options.
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
mkdir -p hyperhdr && tar -xzf HyperHDR-22.0.0-Linux-x86_64.tar.gz -C hyperhdr
scripts/hyperhdr.sh start           # also: stop, restart
```

Then, for the tests that restart HyperHDR (as when its machine is turned off
and on) and the SSH power off against a real OpenSSH and sudo:

```bash
sudo scripts/ssh-test-host.sh       # sshd on 2222, a sudo user, a systemctl that only writes down
HYPERHDR_HOST=127.0.0.1 HYPERHDR_RESTART="scripts/hyperhdr.sh restart" SSH_TEST_HOST=127.0.0.1 .venv/bin/pytest
```

`ssh-test-host.sh` replaces `systemctl` for sudo (`/usr/local/sbin`): run it on a
throwaway machine or container only. The CI does all of this on every push and
pull request.

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
