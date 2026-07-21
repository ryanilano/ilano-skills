# Codebase Concerns

**Analysis Date:** 2026-07-21

## Tech Debt

**Hand-rolled YAML parsing in validation scripts:**
- Issue: `yaml_get()` (duplicated in both scripts) parses PROVENANCE.yaml with `sed` on flat top-level keys only; `mods_count()` in `scripts/validate.sh` counts list entries with a line-oriented `awk` state machine
- Files: `scripts/validate.sh` (lines 18–27), `scripts/diff-upstream.sh` (lines 36–38)
- Impact: Breaks silently on legitimate YAML variants — quoted values (`origin: "fork"`), inline lists (`modifications: []`), trailing comments (`origin: fork  # note`), or indented keys. A quoted `origin` would be reported as `unknown origin '"fork"'`; an inline empty list passes the fork check it should fail
- Fix approach: Either document the strict flat-YAML subset PROVENANCE.yaml must use (cheapest, matches current usage), or parse with `yq`/`python3 -c "import yaml"` if available

**Duplicated `yaml_get` helper across scripts:**
- Issue: Identical function defined in both scripts with no shared lib
- Files: `scripts/validate.sh`, `scripts/diff-upstream.sh`
- Impact: A parsing fix applied to one script can drift from the other
- Fix approach: Acceptable at 2 scripts; if a third script needs it, extract `scripts/lib.sh`

**Skill list duplicated in plugin manifests and README:**
- Issue: The skill roster ("copyable-markdown and prompt-pack") is hardcoded in two description strings plus the README skill list
- Files: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`
- Impact: Adding or renaming a skill requires touching three prose locations; nothing checks they agree (the "formerly markdown-copy" rename already required this kind of sweep)
- Fix approach: Keep descriptions roster-free ("Original agent skills by Ryan Ilano") or add a check to `scripts/validate.sh` that each `skills/*/` name appears in README

**Inconsistent SKILL.md frontmatter between skills:**
- Issue: `skills/copyable-markdown/SKILL.md` carries `license` and `metadata` (author, version "2.1") frontmatter keys; `skills/prompt-pack/SKILL.md` has only `name` and `description`
- Files: `skills/copyable-markdown/SKILL.md`, `skills/prompt-pack/SKILL.md`
- Impact: No functional break, but there is no single convention for what frontmatter a skill in this repo ships; AGENTS.md only mandates `name` + `description`
- Fix approach: Decide whether `license`/`metadata` are standard and either add them to prompt-pack or drop them from copyable-markdown

## Known Bugs

**Misleading failure message for vendored config errors:**
- Symptoms: `scripts/validate.sh` reports "content differs from upstream at pinned SHA" when the real problem is a config error (missing `upstream_repo`/`upstream_sha`, unreachable network, or a bad `upstream_path`)
- Files: `scripts/validate.sh` (lines 52–57), `scripts/diff-upstream.sh` (exit code contract lines 8, exit 2 paths)
- Trigger: `diff-upstream.sh` distinguishes exit 1 (diff found) from exit 2 (usage/config error), but `validate.sh` calls it with `> /dev/null 2>&1` and treats any non-zero the same, discarding both the exit-code distinction and the stderr explanation
- Workaround: Run `scripts/diff-upstream.sh <skill>` directly to see the real error. Latent today — no vendored skill exists yet — but it will bite the first time one is added

**`upstream_path` defaulting to repo root:**
- Symptoms: With `upstream_path` unset, `diff-upstream.sh` diffs the entire upstream repository root against the single skill directory, producing a wall of spurious differences
- Files: `scripts/diff-upstream.sh` (line 74, `"$tmp/${path:-.}"`)
- Trigger: Any vendored/fork PROVENANCE.yaml that omits `upstream_path` while the upstream repo contains more than that one skill
- Workaround: Always set `upstream_path`; consider making it required alongside `upstream_repo`/`upstream_sha` in the line 49 check

## Security Considerations

**Validation fetches arbitrary git remotes from committed metadata:**
- Risk: `validate.sh` (via `diff-upstream.sh`) runs `git fetch` against whatever URL is in a skill's `upstream_repo` field. A malicious or typo'd PROVENANCE.yaml causes network access to an attacker-chosen host during "validation"
- Files: `scripts/diff-upstream.sh` (lines 65–68)
- Current mitigation: Single-author repo; both current skills are `origin: original`, so the code path is never taken today
- Recommendations: If external contributions are ever accepted, restrict `upstream_repo` to `https://` URLs (reject `ext::`/`file://`/ssh transports) before fetching

**No secret exposure detected:**
- Risk: None found — repo contains only markdown, YAML, JSON manifests, and two shell scripts; no `.env`, credentials, or tokens present
- Files: Not applicable
- Current mitigation: Nothing sensitive to leak
- Recommendations: None

## Performance Bottlenecks

**Network fetch per vendored skill during validation:**
- Problem: `validate.sh` performs a full `git init` + shallow fetch + checkout for every `origin: vendored` skill, sequentially
- Files: `scripts/validate.sh` (lines 52–57), `scripts/diff-upstream.sh` (lines 54–68)
- Cause: Upstream comparison requires the pinned SHA's tree; no caching between runs
- Improvement path: Irrelevant at current scale (0 vendored skills). If vendored skills accumulate, cache fetched trees under a temp dir keyed by `repo@sha`, or skip vendored checks offline with a `--offline` flag. Note: `git fetch --depth 1 origin <sha>` also requires the remote to permit fetching arbitrary SHAs (GitHub does; not all hosts do)

## Fragile Areas

**`validate.sh` enforces only a subset of AGENTS.md rules:**
- Files: `scripts/validate.sh`, `AGENTS.md`
- Why fragile: AGENTS.md states "SKILL.md required," "`name` must match the directory name," "keep SKILL.md under 500 lines," and "information lives in SKILL.md or `references/`, never both" — none of which validate.sh checks. It validates provenance only. A skill with a missing SKILL.md or mismatched `name` passes validation cleanly
- Safe modification: Extend the per-skill loop in `validate.sh` with a SKILL.md existence check and a frontmatter `name` == dirname check (both are two-line additions to the existing loop)
- Test coverage: None — see Test Coverage Gaps

**Fork and vendored validation paths are dead code today:**
- Files: `scripts/validate.sh` (lines 44–57)
- Why fragile: Both existing skills are `origin: original`, so the `fork` (LICENSE.upstream + modifications) and `vendored` (upstream diff) branches have never executed against real data. First real fork/vendored skill is where the YAML-parsing and exit-code bugs above will surface
- Safe modification: When adding the first non-original skill, run `validate.sh` and `diff-upstream.sh <skill>` manually (unredirected) and inspect stderr before trusting the JSON summary
- Test coverage: None

**copyable-markdown four-backtick fence protocol:**
- Files: `skills/copyable-markdown/SKILL.md` (Output format section), `skills/copyable-markdown/assets/copyblock-prompt.md`
- Why fragile: The one-block guarantee depends entirely on the model honoring the four-backtick outer fence rule; content containing its own four-backtick fences (e.g., exporting a document about this very skill) would still split the block, and nothing can enforce it mechanically
- Safe modification: Keep the fence instructions in SKILL.md and `assets/copyblock-prompt.md` in sync — they duplicate the same rules in different words, and drift between them changes behavior for portable-prompt users only
- Test coverage: Not testable by script; behavioral only

## Scaling Limits

**Manual validation discipline:**
- Current capacity: 2 skills, single author, validation run by hand
- Limit: AGENTS.md mandates "Run `scripts/validate.sh` before every commit," but no CI (`.github/` absent) or git hook enforces it — the guarantee degrades as skill count or contributor count grows
- Scaling path: Add a GitHub Actions workflow that runs `scripts/validate.sh` on push/PR (script already exits non-zero on failure and emits JSON, so it is CI-ready as-is)

## Dependencies at Risk

**None detected:**
- Risk: Repo has zero runtime dependencies — no package manifests, lockfiles, or vendored libraries. Scripts require only bash, sed, awk, git, diff, mktemp (POSIX + git baseline)
- Impact: Not applicable
- Migration plan: Not applicable

## Missing Critical Features

**No CI pipeline:**
- Problem: No `.github/workflows/`, no pre-commit hook; provenance and structure rules are enforced only by author memory
- Blocks: Safe acceptance of external PRs; guaranteed-valid `main` for consumers installing via `npx skills add ryanilano/ilano-skills` or the plugin marketplace

**No SKILL.md structural validation:**
- Problem: The repo's own SKILL.md format rules (frontmatter shape, name/dirname match, 500-line cap) have no automated check
- Blocks: Catching a broken skill before it ships to plugin installers

## Test Coverage Gaps

**Shell scripts entirely untested:**
- What's not tested: All branches of `validate.sh` (missing PROVENANCE, empty origin, unknown origin, fork requirements, vendored diff) and `diff-upstream.sh` (arg parsing, `--latest`, missing pin fields, path defaulting)
- Files: `scripts/validate.sh`, `scripts/diff-upstream.sh`
- Risk: Regressions in validation logic pass unnoticed precisely because validation is the safety net; the fork/vendored branches have never run against real data
- Priority: Medium — small surface, but it is the repo's only automated quality gate. A bats or plain-bash fixture test with a fake `skills/` tree would cover every branch cheaply

---

*Concerns audit: 2026-07-21*
