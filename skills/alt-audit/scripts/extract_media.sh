#!/usr/bin/env bash
# extract_media.sh <url> <outdir>
# Saves raw HTML, lists all <img>/<video> tags to media-tags.txt, downloads media files.
set -euo pipefail

url="${1:?usage: extract_media.sh <url> <outdir>}"
outdir="${2:?usage: extract_media.sh <url> <outdir>}"
mkdir -p "$outdir"

html="$outdir/page.html"
curl -sL "$url" -o "$html"

origin=$(printf '%s' "$url" | sed -E 's#(https?://[^/]+).*#\1#')

grep -oE '<(img|video)[^>]*>' "$html" > "$outdir/media-tags.txt" || true

grep -oE 'src="[^"]+"' "$outdir/media-tags.txt" \
  | sed -E 's/^src="//; s/"$//' \
  | grep -v '^data:' \
  | sort -u \
  | while read -r src; do
      case "$src" in
        http*) full="$src" ;;
        *)     full="$origin$src" ;;
      esac
      curl -sL -o "$outdir/$(basename "$src")" "$full" || true
    done

printf 'origin: %s\nmedia tags: %s\ndownloaded files:\n' "$origin" "$(wc -l < "$outdir/media-tags.txt" | tr -d ' ')"
ls -la "$outdir"
