#!/bin/bash
# gather_state.sh — collect verified session state for a handoff note.
#
# Everything here is measured, not recalled. Uses /usr/bin/git explicitly
# because shell wrappers and tool-output rewriters have reported commits that
# never happened; the real binary is the only thing worth quoting in a handoff.
#
# Status to stderr, JSON to stdout.
#
# Usage: gather_state.sh [repo-dir]   (defaults to $PWD)
set -e

REPO="${1:-$PWD}"
GIT=/usr/bin/git
TS="$(command -v tailscale || echo /opt/homebrew/bin/tailscale)"

say() { printf '%s\n' "$*" >&2; }
json_str() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/ /g'; }

cd "$REPO" 2>/dev/null || { say "cannot cd to $REPO"; exit 1; }

if ! $GIT rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  say "not a git work tree: $REPO"
  printf '{"repo":"%s","git":null}\n' "$(json_str "$REPO")"
  exit 0
fi

ROOT="$($GIT rev-parse --show-toplevel)"
BRANCH="$($GIT rev-parse --abbrev-ref HEAD)"
HEAD_SHA="$($GIT rev-parse --short HEAD)"
UPSTREAM="$($GIT rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo '')"
BASE="${UPSTREAM:-origin/main}"
AHEAD=0; BEHIND=0
if $GIT rev-parse --verify "$BASE" >/dev/null 2>&1; then
  AHEAD="$($GIT rev-list --count "$BASE..HEAD")"
  BEHIND="$($GIT rev-list --count "HEAD..$BASE")"
fi
say "repo   $ROOT"
say "branch $BRANCH at $HEAD_SHA, $AHEAD ahead of $BASE, $BEHIND behind"

# Uncommitted paths, so a handoff never claims a clean tree that is not clean.
DIRTY="$($GIT status --porcelain | sed 's/^...//' | head -20)"
[ -n "$DIRTY" ] && say "uncommitted: $(printf '%s' "$DIRTY" | tr '\n' ' ')"

# Commits since a caller-supplied marker, or the last 20.
SINCE="${HANDOFF_SINCE:-}"
if [ -n "$SINCE" ] && $GIT rev-parse --verify "$SINCE" >/dev/null 2>&1; then
  LOG="$($GIT log --oneline "$SINCE..HEAD")"
else
  LOG="$($GIT log --oneline -20)"
fi
COUNT="$(printf '%s' "$LOG" | grep -c . || true)"
say "commits in scope: $COUNT"

# Served surfaces, and whether each backend is actually listening. A handoff
# that lists a dead URL is worse than one that lists none.
SERVE=""
if [ -x "$TS" ]; then
  SERVE="$("$TS" serve status 2>/dev/null | grep -E '^https?://|proxy' || true)"
  [ -n "$SERVE" ] && say "tailscale serve: $(printf '%s' "$SERVE" | grep -c 'proxy') proxied path(s)"
fi

esc_block() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}'; }

cat <<JSON
{
  "measured_utc": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "measured_local": "$(date '+%Y-%m-%d %H:%M %Z')",
  "repo": "$(json_str "$ROOT")",
  "branch": "$(json_str "$BRANCH")",
  "head": "$(json_str "$HEAD_SHA")",
  "compared_against": "$(json_str "$BASE")",
  "ahead": $AHEAD,
  "behind": $BEHIND,
  "uncommitted": "$(esc_block "$DIRTY")",
  "commits": "$(esc_block "$LOG")",
  "commit_count": $COUNT,
  "serve": "$(esc_block "$SERVE")"
}
JSON
