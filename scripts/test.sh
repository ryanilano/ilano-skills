#!/bin/bash
# Test suite for scripts/validate.sh and scripts/diff-upstream.sh.
# Builds disposable fixture repos under mktemp and runs the scripts against
# synthetic skills — fully offline (vendored checks use a local file:// upstream).
# Status to stderr; JSON summary to stdout. Exits non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

FIX="$TMP/fixture"
passed=0
failed=0

t_pass() { echo "ok: $1" >&2; passed=$((passed + 1)); }
t_fail() { echo "FAIL: $1" >&2; failed=$((failed + 1)); }

reset_fixture() {
  rm -rf "$FIX"
  mkdir -p "$FIX/skills"
  cp -R "$ROOT/scripts" "$FIX/scripts"
}

make_skill() { # make_skill <name> <origin> — minimal well-formed skill
  local d="$FIX/skills/$1"
  mkdir -p "$d"
  printf -- '---\nname: %s\ndescription: test skill\n---\n' "$1" > "$d/SKILL.md"
  printf 'origin: %s\n' "$2" > "$d/PROVENANCE.yaml"
}

check_validate() { # check_validate <desc> <expected_rc> [stderr_pattern]
  local desc="$1" want_rc="$2" pattern="${3:-}" rc=0
  "$FIX/scripts/validate.sh" > "$TMP/out" 2> "$TMP/err" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then
    t_fail "$desc (exit $rc, wanted $want_rc)"
  elif [ -n "$pattern" ] && ! grep -q "$pattern" "$TMP/err"; then
    t_fail "$desc (stderr missing '$pattern'): $(cat "$TMP/err")"
  else
    t_pass "$desc"
  fi
}

check_diff_upstream() { # check_diff_upstream <desc> <expected_rc> <stderr_pattern> [args...]
  local desc="$1" want_rc="$2" pattern="$3" rc=0
  shift 3
  "$FIX/scripts/diff-upstream.sh" "$@" > "$TMP/out" 2> "$TMP/err" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then
    t_fail "$desc (exit $rc, wanted $want_rc)"
  elif [ -n "$pattern" ] && ! grep -q "$pattern" "$TMP/err"; then
    t_fail "$desc (stderr missing '$pattern'): $(cat "$TMP/err")"
  else
    t_pass "$desc"
  fi
}

# --- validate.sh: structure and provenance branches ---------------------------

reset_fixture
make_skill good-skill original
check_validate "valid original skill passes" 0 "OK: 1 skill"

reset_fixture
make_skill no-prov original
rm "$FIX/skills/no-prov/PROVENANCE.yaml"
check_validate "missing PROVENANCE.yaml fails" 1 "missing PROVENANCE.yaml"

reset_fixture
make_skill no-origin original
printf 'upstream_repo: x\n' > "$FIX/skills/no-origin/PROVENANCE.yaml"
check_validate "empty origin fails" 1 "no origin field"

reset_fixture
make_skill bad-origin banana
check_validate "unknown origin fails" 1 "unknown origin 'banana'"

reset_fixture
make_skill no-skillmd original
rm "$FIX/skills/no-skillmd/SKILL.md"
check_validate "missing SKILL.md fails" 1 "missing SKILL.md"

reset_fixture
make_skill wrong-name original
printf -- '---\nname: other-name\ndescription: test skill\n---\n' > "$FIX/skills/wrong-name/SKILL.md"
check_validate "SKILL.md name/dirname mismatch fails" 1 "does not match directory name"

# --- validate.sh: fork branch --------------------------------------------------

reset_fixture
make_skill forked fork
check_validate "fork without LICENSE.upstream fails" 1 "LICENSE.upstream is missing"

reset_fixture
make_skill forked fork
touch "$FIX/skills/forked/LICENSE.upstream"
check_validate "fork with empty modifications fails" 1 "modifications list is empty"

reset_fixture
make_skill forked fork
touch "$FIX/skills/forked/LICENSE.upstream"
printf 'origin: fork\nmodifications:\n  - changed a thing\n' > "$FIX/skills/forked/PROVENANCE.yaml"
check_validate "well-formed fork passes" 0 "OK: 1 skill"

# --- vendored branch, against a local file:// upstream --------------------------

setup_upstream() { # creates $UP and $UPSHA with skill content under myskill/
  UP="$TMP/upstream"
  rm -rf "$UP"
  git init -q "$UP"
  mkdir -p "$UP/myskill"
  printf -- '---\nname: vendored-skill\ndescription: test skill\n---\n' > "$UP/myskill/SKILL.md"
  git -C "$UP" -c user.email=test@test -c user.name=test add -A
  git -C "$UP" -c user.email=test@test -c user.name=test commit -qm 'upstream content'
  git -C "$UP" config uploadpack.allowAnySHA1InWant true
  UPSHA="$(git -C "$UP" rev-parse HEAD)"
}

make_vendored() { # make_vendored <sha> — vendored-skill pinned to <sha>
  mkdir -p "$FIX/skills/vendored-skill"
  printf -- '---\nname: vendored-skill\ndescription: test skill\n---\n' > "$FIX/skills/vendored-skill/SKILL.md"
  {
    printf 'origin: vendored\n'
    printf 'upstream_repo: file://%s\n' "$UP"
    printf 'upstream_sha: %s\n' "$1"
    printf 'upstream_path: myskill\n'
  } > "$FIX/skills/vendored-skill/PROVENANCE.yaml"
}

reset_fixture
setup_upstream
make_vendored "$UPSHA"
check_validate "vendored skill matching upstream passes" 0 "OK: 1 skill"

reset_fixture
setup_upstream
make_vendored "$UPSHA"
echo "local drift" >> "$FIX/skills/vendored-skill/SKILL.md"
check_validate "vendored skill with drifted content fails as diff" 1 "content differs from upstream"

reset_fixture
setup_upstream
make_vendored "0000000000000000000000000000000000000000"
check_validate "vendored skill with unfetchable SHA reports check failure, not drift" 1 "upstream check could not run"

reset_fixture
setup_upstream
make_vendored "$UPSHA"
sed -i.bak '/upstream_path/d' "$FIX/skills/vendored-skill/PROVENANCE.yaml" && rm -f "$FIX/skills/vendored-skill/PROVENANCE.yaml.bak"
check_validate "vendored skill missing upstream_path reports check failure" 1 "upstream check could not run"

# --- diff-upstream.sh: argument and config handling ------------------------------

reset_fixture
setup_upstream
make_vendored "$UPSHA"
make_skill plain original

check_diff_upstream "no arguments is a usage error" 2 "usage:"
check_diff_upstream "unknown flag is a usage error" 2 "usage:" --bogus
check_diff_upstream "unknown skill is a config error" 2 "not found" no-such-skill
check_diff_upstream "original skill has no upstream" 2 "no upstream to diff against" plain
check_diff_upstream "matching vendored skill exits 0" 0 "" vendored-skill

sed -i.bak '/upstream_path/d' "$FIX/skills/vendored-skill/PROVENANCE.yaml" && rm -f "$FIX/skills/vendored-skill/PROVENANCE.yaml.bak"
check_diff_upstream "missing upstream_path is a config error" 2 "needs upstream_repo, upstream_sha, and upstream_path" vendored-skill

# --- summary ---------------------------------------------------------------------

total=$((passed + failed))
if [ "$failed" -gt 0 ]; then
  echo "FAILED: $failed of $total test(s)" >&2
  printf '{"ok": false, "tests": %d, "failures": %d}\n' "$total" "$failed"
  exit 1
fi

echo "OK: $total test(s) passed" >&2
printf '{"ok": true, "tests": %d, "failures": 0}\n' "$total"
