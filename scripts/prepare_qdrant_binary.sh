#!/usr/bin/env bash
set -euo pipefail
destination="${1:-/mnt/tools/qdrant/qdrant}"
: "${QDRANT_BINARY_URL:?Set QDRANT_BINARY_URL to an approved mirror or upstream release asset}"
: "${QDRANT_BINARY_SHA256:?Set QDRANT_BINARY_SHA256 to the approved checksum}"
mkdir -p "$(dirname "$destination")"
curl --fail --location --proto '=https' --tlsv1.2 "$QDRANT_BINARY_URL" --output "$destination.tmp"
echo "$QDRANT_BINARY_SHA256  $destination.tmp" | sha256sum --check -
mv "$destination.tmp" "$destination"; chmod 0755 "$destination"
echo "Prepared verified Qdrant binary at $destination"

