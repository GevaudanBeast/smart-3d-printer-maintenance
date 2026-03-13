#!/usr/bin/env bash
# Generate a release zip for the printer_maintenance integration.
# Usage: ./scripts/package.sh [version]
# If version is omitted, it is read from manifest.json.

set -euo pipefail

COMPONENT="printer_maintenance"
SRC="custom_components/${COMPONENT}"
DIST="dist"

# Resolve version
if [[ $# -ge 1 ]]; then
  VERSION="$1"
else
  VERSION=$(python3 -c "import json; print(json.load(open('${SRC}/manifest.json'))['version'])")
fi

ZIP_NAME="${COMPONENT}-${VERSION}.zip"

mkdir -p "${DIST}"
rm -f "${DIST}/${ZIP_NAME}"

zip -r "${DIST}/${ZIP_NAME}" "${SRC}"

echo "Package created: ${DIST}/${ZIP_NAME}"
