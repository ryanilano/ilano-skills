# Coding Conventions

**Analysis Date:** 2026-07-21

## Repository Nature

This is a **skills repository**: content is Markdown (skill instructions), YAML (frontmatter and provenance), JSON (plugin manifests), and Bash (validation scripts). There is no application source code, no TypeScript/JavaScript, and no package manifest. Conventions below reflect that reality; the authoritative rules live in `AGENTS.md` (loaded via `CLAUDE.md`, which contains only `@AGENTS.md`).

## Naming Patterns

**Directories (skills):**
- kebab-case; the directory name IS the slash command (per `AGENTS.md`)
- Examples: `skills/copyable-markdown/`, `skills/prompt-pack/`

**Files:**
- Required skill files are UPPERCASE with fixed names: `SKILL.md`, `PROVENANCE.yaml`
- Fork-only file: `LICENSE.upstream`
- Scripts are kebab-case with `.sh` extension: `scripts/validate.sh`, `scripts/diff-upstream.sh`
- Assets are kebab-case markdown: `skills/copyable-markdown/assets/copyblock-prompt.md`

**Bash identifiers:**
- Variables and functions are lowercase snake_case: `checked`, `failures`, `yaml_get`, `mods_count` (`scripts/validate.sh`)
- `ROOT` is the one uppercase variable, used for the repo root path in both scripts

**YAML frontmatter (SKILL.md):**
- `name` must exactly match the skill directory name (per `AGENTS.md`)
- `description` states what the skill does AND when to trigger it, including literal user trigger phrases (see both `skills/*/SKILL.md`)

## Code Style

**Formatting:**
- No formatter or linter configured (no `.prettierrc`, `.eslintrc`, `biome.json`, or shellcheck config detected)
- Line endings normalized to LF via `.gitattributes` (`* text=auto`)
- Bash: 2-space indentation, `case`/`esac` blocks with `;;` on their own line

**Bash strictness:**
- Scripts open with `#!/bin/bash` followed by a comment block documenting purpose, usage, and exit codes, then `set -euo pipefail` (both files in `scripts/`)
- Note: `AGENTS.md` mandates only `set -e`; existing scripts use the stricter `set -euo pipefail` — match the existing scripts

## Skill Document Structure

**SKILL.md layout (follow `skills/copyable-markdown/SKILL.md` as the reference):**
1. YAML frontmatter (`name`, `description`; optionally `license`, `metadata.author`, `metadata.version`)
2. `#` title matching the skill's human name
3. Opening paragraph stating the user's goal and the skill's core promise
4. `##` sections for invocation/modes, workflow, output format, and edge cases
5. Tables for mode/invocation mappings, numbered lists for workflows

**Context efficiency rules (from `AGENTS.md`):**
- SKILL.md under 500 lines
- Progressive disclosure: overview/workflow in SKILL.md, details in `references/`
- Prefer pointing to a script over pasting its body inline
- A piece of information lives in SKILL.md OR `references/`, never both

## Import Organization

Not applicable — no compiled/interpreted module code. Bash scripts reference each other by path relative to `$ROOT` (e.g. `validate.sh` invokes `"$ROOT/scripts/diff-upstream.sh"`).

## Error Handling

**Bash scripts:**
- `set -euo pipefail` for fail-fast behavior
- Accumulating validators (`scripts/validate.sh`): a `fail()` helper prints `FAIL: <message>` to stderr and increments a counter; the script checks everything, then exits non-zero if any failure occurred
- One-shot scripts (`scripts/diff-upstream.sh`): documented exit codes (0 identical, 1 differences, 2 usage/config error), `usage()` helper printing to stderr, `error:` prefix on config errors

**Skill instructions:**
- "Flag gaps, never invent" — `skills/prompt-pack/SKILL.md` mandates `# NEEDS: <thing>` markers instead of fabricated details; adopt this posture in new skill content

## Logging / Output

**Bash convention (mandated by `AGENTS.md` and followed by both scripts):**
- Status/progress messages go to **stderr** (`echo "..." >&2`)
- Machine-readable output goes to **stdout** — `validate.sh` emits a JSON summary (`{"ok": ..., "skills_checked": ..., "failures": ...}`); `diff-upstream.sh` emits the raw diff

## Comments

**Bash:**
- Header comment block after shebang: what the script does, usage, exit codes (`scripts/diff-upstream.sh:2-9`)
- Function-level inline comments describing signature and behavior: `yaml_get() { # yaml_get <file> <key> — first value of a top-level flat key }` (`scripts/validate.sh:18`)
- No comments on self-evident lines

## Function Design (Bash)

- Small single-purpose helpers (`yaml_get`, `mods_count`, `fail`, `usage`)
- Helpers take positional parameters; document them in the trailing comment
- Temp files use `mktemp -d` with a `trap 'rm -rf "$tmp"' EXIT` cleanup (`scripts/diff-upstream.sh:54-55`; also mandated by `AGENTS.md`)

## Provenance Rules

Every skill directory MUST contain `PROVENANCE.yaml` with `origin: original | vendored | fork`:
- `original`: just `origin` and `author` (see `skills/prompt-pack/PROVENANCE.yaml`); optional `note` field for history (see `skills/copyable-markdown/PROVENANCE.yaml`)
- `vendored`/`fork`: pin the source with `upstream_repo`, `upstream_sha`, `upstream_path`
- `fork`: additionally requires `LICENSE.upstream` file and a non-empty `modifications` list
- Enforced by `scripts/validate.sh` — run it before every commit (per `AGENTS.md`)

## Editing Discipline

- Make surgical changes; don't rewrite what you weren't asked to touch (`AGENTS.md`)
- README `Skills` section (`README.md`) lists each skill with a one-line description — update it when adding/renaming skills

---

*Convention analysis: 2026-07-21*
