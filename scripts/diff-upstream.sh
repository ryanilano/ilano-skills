#!/bin/bash
# Diff a local skill against its upstream, using the pin in its PROVENANCE.yaml.
#
# Usage: diff-upstream.sh <skill> [--latest]
#   <skill>   directory name under skills/
#   --latest  diff against upstream's default branch instead of the pinned SHA
#
# Exit codes: 0 identical, 1 differences found, 2 usage/config error.
# Status to stderr; the diff itself goes to stdout: one "Only in upstream: <path>"
# or "Only in local: <path>" line per one-sided file, then a git diff of the
# changed files (upstream/ against local/). PROVENANCE.yaml, LICENSE.upstream,
# upstream.patch and .git are left out. A fork commits this output as
# skills/<skill>/upstream.patch, and validate.sh checks it on every run.
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

git init -q "$tmp/repo"
git -C "$tmp/repo" remote add origin "$repo"
git -C "$tmp/repo" fetch -q --depth 1 origin "$ref"
git -C "$tmp/repo" checkout -q FETCH_HEAD

if [ ! -d "$tmp/repo/$path" ]; then
  echo "error: upstream_path '$path' is not a directory in $repo @ $ref" >&2
  exit 2
fi

# The output must be the same on every run and every OS, because validate.sh
# compares it byte for byte with a fork's committed upstream.patch. So both
# trees are copied under fixed names (no temp paths in the output), and git
# diff does the comparison (no timestamps, and the same headers and hunks on
# macOS and Linux, where BSD and GNU diff differ).
stage() { # stage <src> <dest>: copy a tree, dropping files that never match upstream
  cp -R "$1" "$2"
  find "$2" \( -name .git -o -name PROVENANCE.yaml -o -name LICENSE.upstream -o -name upstream.patch \) \
    -prune -exec rm -rf {} +
}
mkdir "$tmp/cmp"
stage "$tmp/repo/$path" "$tmp/cmp/upstream"
stage "$ROOT/skills/$skill" "$tmp/cmp/local"
cd "$tmp/cmp"

git_diff() { # fixed options; the user's and system git config are ignored
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -c core.quotePath=true \
    diff --no-index --no-color --no-ext-diff --no-textconv --no-renames --full-index \
    -U3 --inter-hunk-context=0 --diff-algorithm=myers --indent-heuristic \
    "$@" upstream local
}

# git diff --no-index exits 1 when the trees differ; anything higher is an error.
rc=0
git_diff --name-status --diff-filter=AD > "$tmp/only" || rc=$?
if [ "$rc" -le 1 ]; then
  git_diff --diff-filter=MT > "$tmp/changed" || rc=$?
fi
if [ "$rc" -gt 1 ]; then
  echo "error: git diff failed (exit $rc)" >&2
  exit 2
fi

# Files on one side only are named, not printed in full.
LC_ALL=C awk -F '\t' '
  { name = $2; sub(/^upstream\//, "", name); sub(/^local\//, "", name)
    sub(/^"upstream\//, "\"", name); sub(/^"local\//, "\"", name) }
  $1 == "D" { print "Only in upstream: " name }
  $1 == "A" { print "Only in local: " name }' "$tmp/only" > "$tmp/out"
cat "$tmp/changed" >> "$tmp/out"
cat "$tmp/out"
[ -s "$tmp/out" ] && exit 1
exit 0
