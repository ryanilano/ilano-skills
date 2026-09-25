#!/bin/bash
# Validate structure and provenance rules for every skill under skills/.
#   - every skill has SKILL.md whose frontmatter name matches the directory name
#   - every skill has PROVENANCE.yaml with a known origin
#   - origin: fork    -> LICENSE.upstream present, modifications list non-empty
#   - origin: vendored -> content matches upstream at the pinned SHA
#   - origin: reimplemented-technique -> original code, credited technique; no upstream to diff
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
    original|reimplemented-technique)
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
      rc=0
      diff_err="$("$ROOT/scripts/diff-upstream.sh" "$skill" 2>&1 > /dev/null)" || rc=$?
      if [ "$rc" -eq 1 ]; then
        fail "$skill: origin is vendored but content differs from upstream at pinned SHA"
      elif [ "$rc" -ne 0 ]; then
        errline="$(printf '%s\n' "$diff_err" | grep -m 1 '^error:' || true)"
        fail "$skill: upstream check could not run (exit $rc): ${errline:-run scripts/diff-upstream.sh $skill for details}"
      fi
      ;;
    "")
      fail "$skill: PROVENANCE.yaml has no origin field"
      ;;
    *)
      fail "$skill: unknown origin '$origin' (expected original | vendored | fork | reimplemented-technique)"
      ;;
  esac
done

# Harness manifests: version and description are copied by hand into each one,
# so they must match .claude-plugin/plugin.json. Skipped when that file is absent
# (a skills-only checkout). Each mismatch is printed as one line and counted.
if [ -f "$ROOT/.claude-plugin/plugin.json" ] && ! command -v python3 > /dev/null; then
  fail "python3 not on PATH; cannot check harness manifests"
elif [ -f "$ROOT/.claude-plugin/plugin.json" ]; then
  echo "checking harness manifests for version and description drift..." >&2
  while IFS= read -r msg; do
    [ -n "$msg" ] && fail "$msg"
  done < <(python3 - "$ROOT" <<'PY'
import json, os, sys

root = sys.argv[1]
# (label, file, path to the plugin object inside it)
manifests = [
    (".claude-plugin/plugin.json", ".claude-plugin/plugin.json", []),
    (".claude-plugin/marketplace.json plugins[0]", ".claude-plugin/marketplace.json", ["plugins", 0]),
    (".codex-plugin/plugin.json", ".codex-plugin/plugin.json", []),
    ("kimi.plugin.json", "kimi.plugin.json", []),
    ("qwen-extension.json", "qwen-extension.json", []),
    ("gemini-extension.json", "gemini-extension.json", []),
]
values = {}
for label, rel, path in manifests:
    try:
        with open(os.path.join(root, rel)) as f:
            obj = json.load(f)
        for key in path:
            obj = obj[key]
        values[label] = (obj.get("version"), obj.get("description"))
    except FileNotFoundError:
        print(f"manifest {rel} is missing")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        print(f"manifest {label} could not be read: {e!r}")

ref_label = manifests[0][0]
if ref_label in values:
    ref_version, ref_desc = values[ref_label]
    for label, (version, desc) in values.items():
        if version != ref_version:
            print(f"manifest {label} version {version!r} differs from {ref_label} {ref_version!r}")
        if desc != ref_desc:
            print(f"manifest {label} description differs from {ref_label}")
PY
)
fi

if [ "$failures" -gt 0 ]; then
  printf '{"ok": false, "skills_checked": %d, "failures": %d}\n' "$checked" "$failures"
  exit 1
fi

echo "OK: $checked skill(s) validated" >&2
printf '{"ok": true, "skills_checked": %d, "failures": 0}\n' "$checked"
