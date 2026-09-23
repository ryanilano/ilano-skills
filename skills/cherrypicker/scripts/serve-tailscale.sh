#!/bin/bash
# Serve a cherrypicker page to your own devices over Tailscale.
#
#   ./serve-tailscale.sh merge.html [port]
#
# Why this exists: the comparison page is meant to be read on a tablet or phone
# while the laptop stays on the source files. Tailscale gives you an HTTPS URL
# that only your tailnet can reach — no port forwarding, no public exposure, no
# copying files onto the device.
#
# Stop serving with:  tailscale serve --https=443 off
set -euo pipefail

FILE="${1:-merge.html}"
PORT="${2:-8099}"

[ -f "$FILE" ] || { echo "No such file: $FILE" >&2; exit 1; }
command -v tailscale >/dev/null || {
  echo "tailscale CLI not found." >&2
  echo "On macOS with the App Store build, enable it once:" >&2
  echo "  sudo ln -s /Applications/Tailscale.app/Contents/MacOS/Tailscale /usr/local/bin/tailscale" >&2
  exit 1
}

DIR="$(cd "$(dirname "$FILE")" && pwd)"
BASE="$(basename "$FILE")"

# Guard: this script takes the ROOT https mount and turns 443 off on exit.
# On a machine that already serves something, that replaces load-bearing
# mounts (measured failure mode, 2026-08-07). Refuse rather than clobber.
if tailscale serve status 2>/dev/null | grep -q .; then
  echo "This machine already has tailscale serve mounts:" >&2
  tailscale serve status >&2
  echo >&2
  echo "Refusing to touch them. Serve on a dedicated port instead, which leaves" >&2
  echo "the existing mounts alone:" >&2
  echo "  tailscale serve --bg --https=8443 http://127.0.0.1:${PORT}" >&2
  exit 1
fi

# Serve the containing directory, so the page keeps working if it ever grows
# sibling assets.
( cd "$DIR" && python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
HTTP_PID=$!
trap 'kill $HTTP_PID 2>/dev/null || true; tailscale serve --https=443 off >/dev/null 2>&1 || true' EXIT

sleep 1
tailscale serve --bg "http://127.0.0.1:${PORT}" >/dev/null

HOST="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["Self"]["DNSName"].rstrip("."))')"

echo
echo "  Open this on any device signed into your tailnet:"
echo
echo "    https://${HOST}/${BASE}"
echo
echo "  Picks autosave into the URL — bookmark it on the tablet and it reopens"
echo "  exactly where you left off."
echo
echo "  Ctrl-C to stop serving."
wait $HTTP_PID
