#!/usr/bin/env bash
# Starts, stops or restarts a HyperHDR for the live tests.
#   HYPERHDR_DIR   the unpacked HyperHDR (bin/, lib/), default ./hyperhdr
#   HYPERHDR_DATA  its data folder, default ./data
#   HYPERHDR_LOG   its log file, default ./hyperhdr.log
set -euo pipefail
dir="${HYPERHDR_DIR:-$PWD/hyperhdr}"
data="${HYPERHDR_DATA:-$PWD/data}"
log="${HYPERHDR_LOG:-$PWD/hyperhdr.log}"

ready() {
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:8090/json-rpc?request=%7B%22command%22:%22sysinfo%22%7D" > /dev/null && return 0
    sleep 1
  done
  echo "HyperHDR did not start" >&2
  return 1
}

running() {
  pgrep -f "$dir/bin/hyperhdr" > /dev/null
}

start() {
  mkdir -p "$data"
  # HyperHDR refuses to start while its previous run is still shutting down.
  for _ in $(seq 1 10); do
    LC_ALL=C.UTF-8 LD_LIBRARY_PATH="$dir/lib/hyperhdr" setsid nohup "$dir/bin/hyperhdr" -u "$data" --service >> "$log" 2>&1 < /dev/null &
    sleep 2
    if running; then
      ready
      return
    fi
  done
  echo "HyperHDR did not start" >&2
  return 1
}

stop() {
  pkill -f "$dir/bin/hyperhdr" || true
  for _ in $(seq 1 40); do
    if ! running && ! curl -s -o /dev/null "http://127.0.0.1:8090/"; then
      return 0
    fi
    sleep 0.5
  done
  echo "HyperHDR did not stop" >&2
  return 1
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  *) echo "usage: $0 start|stop|restart" >&2; exit 2 ;;
esac
