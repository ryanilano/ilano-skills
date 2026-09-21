#!/bin/bash
# Diff a local skill against its upstream, using the pin in its PROVENANCE.yaml.
#
# Usage: diff-upstream.sh <skill> [--latest]
#   <skill>   directory name under skills/
#   --latest  diff against upstream's default branch instead of the pinned SHA
#
# Exit codes: 0 identical, 1 differences found, 2 usage/config error.
# Status to stderr; the diff itself goes to stdout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  echo "usage: $(basename "$0") <skill> [--latest]" >&2
  exit 2
}

skill=""
latest=0
for arg in "$@"; do
  case "$arg" in
    --latest) latest=1 ;;
    -*) usage ;;
    *) [ -z "$skill" ] && skill="$arg" || usage ;;
  esac
done
[ -n "$skill" ] || usage

prov="$ROOT/skills/$skill/PROVENANCE.yaml"
if [ ! -f "$prov" ]; then
  echo "error: skills/$skill/PROVENANCE.yaml not found" >&2
  exit 2
fi

yaml_get() {
  sed -n "s/^${2}:[[:space:]]*//p" "$1" | head -n 1
}

origin="$(yaml_get "$prov" origin)"
if [ "$origin" = "original" ]; then
  echo "error: '$skill' is an original skill — no upstream to diff against" >&2
  exit 2
fi

repo="$(yaml_get "$prov" upstream_repo)"
sha="$(yaml_get "$prov" upstream_sha)"
path="$(yaml_get "$prov" upstream_path)"
if [ -z "$repo" ] || [ -z "$sha" ] || [ -z "$path" ]; then
  echo "error: skills/$skill/PROVENANCE.yaml needs upstream_repo, upstream_sha, and upstream_path" >&2
  exit 2
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if [ "$latest" -eq 1 ]; then
  echo "fetching $repo @ default branch..." >&2
  ref="HEAD"
else
  echo "fetching $repo @ $sha..." >&2
  ref="$sha"
fi

git init -q "$tmp"
git -C "$tmp" remote add origin "$repo"
git -C "$tmp" fetch -q --depth 1 origin "$ref"
git -C "$tmp" checkout -q FETCH_HEAD

diff -ru \
  --exclude PROVENANCE.yaml \
  --exclude LICENSE.upstream \
  --exclude .git \
  "$tmp/$path" "$ROOT/skills/$skill"
