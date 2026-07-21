# Testing Patterns

**Analysis Date:** 2026-07-21

## Test Framework

**Runner:**
- Plain bash: `scripts/test.sh` (added 2026-07-21) — no Jest/Vitest/Bats dependency. Builds disposable fixture repos under `mktemp` and asserts exit codes + stderr patterns for `validate.sh` and `diff-upstream.sh`, fully offline (vendored checks use a local `file://` upstream with `uploadpack.allowAnySHA1InWant`).
- Quality is otherwise enforced through **validation scripts**.

**Assertion Library:**
- None — hand-rolled `check_validate` / `check_diff_upstream` helpers in `scripts/test.sh`

**Run Commands:**
```bash
scripts/test.sh                              # Test suite for the validation scripts (runs in CI)
scripts/validate.sh                          # Validate structure + provenance for every skill (the pre-commit gate)
scripts/diff-upstream.sh <skill>             # Diff a vendored/forked skill against its pinned upstream SHA
scripts/diff-upstream.sh <skill> --latest    # Diff against upstream's default branch instead
```

## Validation as Testing

**`scripts/validate.sh` is the closest thing to a test suite.** Per `AGENTS.md`, it must run before every commit. It checks, for each directory under `skills/`:

- `PROVENANCE.yaml` exists
- `origin` is one of `original | vendored | fork`
- `origin: fork` → `LICENSE.upstream` present AND `modifications` list non-empty
- `origin: vendored` → content byte-matches upstream at the pinned SHA (via `diff-upstream.sh`)

**Pass/fail contract:**
- Status messages to stderr; JSON summary to stdout: `{"ok": true, "skills_checked": N, "failures": 0}`
- Exits non-zero on any failure — suitable for CI or hooks

## Test File Organization

**Location:**
- `scripts/test.sh` — the test suite for the validation scripts
- Validation logic lives in `scripts/`

**Naming:**
- Validation/tooling scripts: kebab-case `.sh` files in `scripts/`

**Structure:**
```
scripts/
├── validate.sh        # Structure + provenance validator — run before every commit
├── diff-upstream.sh   # Upstream drift checker for vendored/forked skills
└── test.sh            # Fixture-based tests for the two scripts above
```

## Validation Script Structure

**Pattern (from `scripts/validate.sh`):**
```bash
#!/bin/bash
# <purpose, rules enforced>
# Status to stderr; JSON summary to stdout. Exits non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checked=0
failures=0

fail() {
  echo "FAIL: $1" >&2
  failures=$((failures + 1))
}

for dir in "$ROOT"/skills/*/; do
  # ... accumulate failures rather than exiting on the first one ...
done

if [ "$failures" -gt 0 ]; then
  printf '{"ok": false, "skills_checked": %d, "failures": %d}\n' "$checked" "$failures"
  exit 1
fi
```

**Key patterns:**
- Check-everything-then-fail: accumulate failures with `fail()`, report all at once
- `FAIL: <skill>: <reason>` message format on stderr
- Deterministic JSON summary on stdout for machine consumption

## Mocking

**Framework:** None.

**Isolation pattern:** `scripts/diff-upstream.sh` isolates upstream comparison in a throwaway git clone:
```bash
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git init -q "$tmp"
git -C "$tmp" remote add origin "$repo"
git -C "$tmp" fetch -q --depth 1 origin "$ref"
git -C "$tmp" checkout -q FETCH_HEAD

diff -ru --exclude PROVENANCE.yaml --exclude LICENSE.upstream --exclude .git \
  "$tmp/${path:-.}" "$ROOT/skills/$skill"
```
Follow this shape for any new script needing scratch state: `mktemp -d` + `trap ... EXIT` cleanup (also mandated by `AGENTS.md`).

**Network dependency:** vendored-skill validation fetches from the upstream repo — `validate.sh` requires network access when any skill has `origin: vendored`. Currently both skills are `origin: original`, so `validate.sh` runs fully offline.

## Fixtures and Factories

Not applicable — no test data. The skills themselves (`skills/*/PROVENANCE.yaml`) are the inputs `validate.sh` operates on.

## Coverage

**Requirements:** None enforced; no coverage tooling exists or applies.

**What validation does NOT check (gaps):**
- SKILL.md 500-line limit (stated in `AGENTS.md`, unenforced; presence and `name`-matches-directory are enforced as of 2026-07-21)
- Script standards (`set -e`, stderr/stdout discipline) — unenforced; no shellcheck
- JSON manifest validity (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`)

## Test Types

**Unit Tests:** Not used.

**Integration Tests:** `scripts/validate.sh` acts as an integration check across all skills; `diff-upstream.sh` integration-checks vendored content against live upstream git repos.

**E2E Tests:** Not used. Skills are exercised manually by invoking them in Claude Code (e.g. `/copyable-markdown`, prompt-pack triggers).

## CI/CD

`.github/workflows/validate.yml` (added 2026-07-21) runs `scripts/validate.sh` and `scripts/test.sh` on pushes to `main` and on PRs. Locally, the `AGENTS.md` instruction still applies: "Run `scripts/validate.sh` before every commit."

## Adding Checks

When adding a new validation rule:
- Extend `scripts/validate.sh` (or add a sibling script in `scripts/` following the same stderr-status / stdout-JSON / non-zero-exit contract)
- Keep the accumulate-then-report pattern so one bad skill doesn't hide others
- Keep the JSON summary schema stable: `{"ok": bool, "skills_checked": N, "failures": N}`

---

*Testing analysis: 2026-07-21*
