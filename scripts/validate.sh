#!/bin/bash
# Validate structure and provenance rules for every skill under skills/.
#   - every skill has SKILL.md whose frontmatter name matches the directory name
#   - every skill has PROVENANCE.yaml with a known origin
#   - origin: fork    -> LICENSE.upstream present, modifications list non-empty
#   - origin: vendored -> content matches upstream at the pinned SHA
# Status to stderr; JSON summary to stdout. Exits non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checked=0
failures=0

fail() {
  echo "FAIL: $1" >&2
  failures=$((failures + 1))
}

yaml_get() { # yaml_get <file> <key> — first value of a top-level flat key
  sed -n "s/^${2}:[[:space:]]*//p" "$1" | head -n 1
}

mods_count() { # count non-empty entries in the modifications list
  awk '/^modifications:/ { in_mods = 1; next }
       in_mods && /^[^ ]/ { in_mods = 0 }
       in_mods && /^[[:space:]]*-[[:space:]]*[^[:space:]]/ { count++ }
       END { print count + 0 }' "$1"
}

for dir in "$ROOT"/skills/*/; do
  [ -d "$dir" ] || continue
  skill="$(basename "$dir")"
  checked=$((checked + 1))
  prov="$dir/PROVENANCE.yaml"

  if [ ! -f "$dir/SKILL.md" ]; then
    fail "$skill: missing SKILL.md"
  else
    skill_name="$(yaml_get "$dir/SKILL.md" name)"
    if [ "$skill_name" != "$skill" ]; then
      fail "$skill: SKILL.md name '$skill_name' does not match directory name"
    fi
  fi

  if [ ! -f "$prov" ]; then
    fail "$skill: missing PROVENANCE.yaml"
    continue
  fi

  origin="$(yaml_get "$prov" origin)"
  case "$origin" in
    original)
      ;;
    fork)
      if [ ! -f "$dir/LICENSE.upstream" ]; then
        fail "$skill: origin is fork but LICENSE.upstream is missing"
      fi
      if [ "$(mods_count "$prov")" -eq 0 ]; then
        fail "$skill: origin is fork but modifications list is empty"
      fi
      ;;
    vendored)
      echo "checking $skill against upstream at pinned SHA..." >&2
      if ! "$ROOT/scripts/diff-upstream.sh" "$skill" > /dev/null 2>&1; then
        fail "$skill: origin is vendored but content differs from upstream at pinned SHA"
      fi
      ;;
    "")
      fail "$skill: PROVENANCE.yaml has no origin field"
      ;;
    *)
      fail "$skill: unknown origin '$origin' (expected original | vendored | fork)"
      ;;
  esac
done

if [ "$failures" -gt 0 ]; then
  printf '{"ok": false, "skills_checked": %d, "failures": %d}\n' "$checked" "$failures"
  exit 1
fi

echo "OK: $checked skill(s) validated" >&2
printf '{"ok": true, "skills_checked": %d, "failures": 0}\n' "$checked"
