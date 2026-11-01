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

echo "Building pentair_rs485 v${VERSION}..."

python3 -m compileall "$COMPONENT_DIR" -q

mkdir -p "$RELEASES_DIR"
rm -f "$VERSIONED_ZIP"

(
  cd "$ROOT/custom_components"
  zip -r "$VERSIONED_ZIP" pentair_rs485 \
    -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
)

cp "$VERSIONED_ZIP" "$LATEST_ZIP"

echo "Saved: $VERSIONED_ZIP"
echo "Latest: $LATEST_ZIP"
ls -lh "$VERSIONED_ZIP"
