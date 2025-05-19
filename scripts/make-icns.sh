#!/usr/bin/env bash
set -euo pipefail

SRC="src/resources/icon.png"      # 1024×1024 PNG with transparency
DST="src/resources/icon.icns"

if [[ ! -f "$SRC" ]]; then
    echo "❌  $SRC not found" >&2
    exit 1
fi

# -------------------------------------------------------------------------------------------------
# macOS path ───────────────────────────────────────────────────────────────────────────────────────
# Uses the native utilities that are always present on GitHub's macOS runners.
# -------------------------------------------------------------------------------------------------
if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "🖼  Generating .icns with sips & iconutil (macOS)…"
    tmp_dir="$(mktemp -d)"
    iconset="$tmp_dir/icon.iconset"
    mkdir "$iconset"

    # Generate the PNGs that macOS expects inside an .iconset directory
    for size in 16 32 128 256 512; do
        sips -z  "$size"  "$size"  "$SRC" \
             --out "$iconset/icon_${size}x${size}.png" >/dev/null
        double=$(( size * 2 ))
        sips -z  "$double" "$double" "$SRC" \
             --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
    done
    cp "$SRC" "$iconset/icon_512x512@2x.png"   # 1024 px (Hi-DPI)

    # Convert folder → .icns
    iconutil -c icns "$iconset" -o "$DST"
    rm -rf "$tmp_dir"