#!/usr/bin/env bash
# Build versioned release zip + update the "latest" alias.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPONENT_DIR="$ROOT/custom_components/pentair_rs485"
MANIFEST="$COMPONENT_DIR/manifest.json"
RELEASES_DIR="$ROOT/releases"

if [[ ! -f "$MANIFEST" ]]; then
  echo "manifest.json not found at $MANIFEST" >&2
  exit 1
fi

VERSION="$(python3 -c "import json; print(json.load(open('$MANIFEST'))['version'])")"
VERSIONED_ZIP="$RELEASES_DIR/pentair_rs485_v${VERSION}.zip"
LATEST_ZIP="$ROOT/pentair_rs485_ha.zip"
DISPLAY_DIR="$ROOT/custom_components/pentair_pump_display"
DISPLAY_ZIP="$RELEASES_DIR/pentair_pump_display_v${VERSION}.zip"
DISPLAY_LATEST="$ROOT/pentair_pump_display.zip"

echo "Building pentair_rs485 v${VERSION}..."

python3 -m compileall "$COMPONENT_DIR" -q
if [[ -d "$DISPLAY_DIR" ]]; then
  python3 -m compileall "$DISPLAY_DIR" -q
fi

mkdir -p "$RELEASES_DIR"
rm -f "$VERSIONED_ZIP" "$DISPLAY_ZIP"

(
  cd "$ROOT/custom_components"
  zip -r "$VERSIONED_ZIP" pentair_rs485 \
    -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
)

if [[ -d "$DISPLAY_DIR" ]]; then
  echo "Building pentair_pump_display v${VERSION}..."
  (
    cd "$ROOT/custom_components"
    zip -r "$DISPLAY_ZIP" pentair_pump_display \
      -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
  )
  cp "$DISPLAY_ZIP" "$DISPLAY_LATEST"
  echo "Display: $DISPLAY_ZIP"
fi

# HACS downloads this zip: both integrations so the house HA can
# add only the Lovelace card, and the pool HA still gets the pump.
echo "Building HACS zip (rs485 + display)..."
rm -f "$LATEST_ZIP"
(
  cd "$ROOT/custom_components"
  zip -r "$LATEST_ZIP" pentair_rs485 pentair_pump_display \
    -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
)

echo "Saved: $VERSIONED_ZIP"
echo "Latest: $LATEST_ZIP"
ls -lh "$VERSIONED_ZIP"
