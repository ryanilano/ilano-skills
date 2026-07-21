<!-- refreshed: 2026-07-21 -->
# Architecture

**Analysis Date:** 2026-07-21

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Consumption Surfaces                     │
├──────────────────┬──────────────────┬───────────────────────┤
│  skills CLI      │ Claude Code      │  Manual copy to       │
│  `npx skills add`│ plugin install   │  `~/.claude/skills/`  │
│                  │ `.claude-plugin/`│                       │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Skill Content Layer                       │
│  `skills/{skill-name}/SKILL.md` (+ optional `assets/`)       │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Provenance & Validation Layer                               │
│  `skills/*/PROVENANCE.yaml` enforced by `scripts/validate.sh`│
│  and `scripts/diff-upstream.sh`                              │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Skill definitions | Instruction content consumed by AI agents at runtime | `skills/copyable-markdown/SKILL.md`, `skills/prompt-pack/SKILL.md` |
| Skill assets | Portable artifacts a skill hands to users on demand | `skills/copyable-markdown/assets/copyblock-prompt.md` |
| Provenance records | Declare each skill's origin (`original`/`vendored`/`fork`) and upstream pin | `skills/*/PROVENANCE.yaml` |
| Provenance validator | Pre-commit gate enforcing provenance rules across all skills | `scripts/validate.sh` |
| Upstream differ | Compares a vendored/forked skill against its pinned upstream SHA | `scripts/diff-upstream.sh` |
| Plugin manifest | Declares the `ilano` Claude Code plugin (name, version, license) | `.claude-plugin/plugin.json` |
| Marketplace manifest | Registers the plugin for `/plugin marketplace add` | `.claude-plugin/marketplace.json` |
| Repo conventions | Authoring rules for skills in this repo | `AGENTS.md` (loaded via `CLAUDE.md`) |

## Pattern Overview

**Overall:** Content-as-code monorepo of agent skills — no application runtime. Each skill is a self-contained directory of markdown instructions distributed through three parallel channels (skills CLI, Claude Code plugin, manual copy), with a thin bash tooling layer that enforces provenance metadata.

**Key Characteristics:**
- Skills are declarative documents, not executable code; the "runtime" is the consuming AI agent harness
- Every skill directory carries mandatory provenance metadata; validation is a hard gate (`scripts/validate.sh` before every commit, per `AGENTS.md`)
- Progressive disclosure convention: SKILL.md holds the workflow; details go to `references/`, shippable files to `assets/`, executables to `scripts/` (per-skill)
- Zero dependencies: only bash, git, sed, awk, and diff are required by the tooling

## Layers

**Consumption / Distribution Layer:**
- Purpose: Expose skills to end users through three install paths
- Location: `.claude-plugin/` (plugin path), `README.md` (documents all three paths)
- Contains: `plugin.json`, `marketplace.json`
- Depends on: Skill content layer (`plugins[0].source: "./"` in `marketplace.json` points at the repo root)
- Used by: `npx skills add ryanilano/ilano-skills`, Claude Code `/plugin install ilano`, manual copy

**Skill Content Layer:**
- Purpose: The actual product — agent-consumable instruction documents
- Location: `skills/{skill-name}/`
- Contains: `SKILL.md` (required, YAML frontmatter + instructions), optional `assets/`
- Depends on: Nothing at runtime; conventions in `AGENTS.md`
- Used by: AI agent harnesses that load the skill when its trigger phrases match

**Provenance & Validation Layer:**
- Purpose: Guarantee origin/credit metadata is present and truthful for every skill
- Location: `scripts/`, plus per-skill `PROVENANCE.yaml`
- Contains: `validate.sh` (rule enforcement), `diff-upstream.sh` (upstream comparison)
- Depends on: `PROVENANCE.yaml` flat-key format; git for shallow-fetching upstreams
- Used by: Contributors, pre-commit (manual invocation per `AGENTS.md`)

## Data Flow

### Skill Consumption Path

1. User installs via one of three channels documented in `README.md` (CLI, plugin, manual copy)
2. Agent harness reads the skill's frontmatter `description` to decide when to trigger (`skills/copyable-markdown/SKILL.md:7`, `skills/prompt-pack/SKILL.md:3`)
3. On trigger, the harness loads the SKILL.md body as instructions; `$ARGUMENTS` substitution selects modes (`skills/copyable-markdown/SKILL.md:16`)
4. Skill may direct the agent to serve an asset file (`skills/copyable-markdown/assets/copyblock-prompt.md`, referenced at `skills/copyable-markdown/SKILL.md:90`)

### Provenance Validation Flow

1. `scripts/validate.sh` iterates every directory under `skills/` (`scripts/validate.sh:29`)
2. Reads `origin` from each `PROVENANCE.yaml` with a sed-based flat-key extractor (`scripts/validate.sh:18`)
3. Branches per origin: `original` passes; `fork` requires `LICENSE.upstream` + non-empty `modifications` list; `vendored` shells out to `scripts/diff-upstream.sh` (`scripts/validate.sh:41-64`)
4. `diff-upstream.sh` shallow-fetches `upstream_repo` at `upstream_sha` into a temp dir and diffs against the local skill, excluding `PROVENANCE.yaml`, `LICENSE.upstream`, `.git` (`scripts/diff-upstream.sh:65-74`)
5. Emits status to stderr and a JSON summary to stdout; non-zero exit on any failure (`scripts/validate.sh:67-73`)

**State Management:**
- None. The repo is stateless content; scripts use throwaway temp dirs cleaned via `trap` (`scripts/diff-upstream.sh:55`)

## Key Abstractions

**Skill:**
- Purpose: A named, self-contained unit of agent instructions; the directory name IS the slash command
- Examples: `skills/copyable-markdown/`, `skills/prompt-pack/`
- Pattern: kebab-case directory + required `SKILL.md` (frontmatter `name` must match directory) + required `PROVENANCE.yaml`

**Provenance Record:**
- Purpose: Machine-checkable origin and credit declaration
- Examples: `skills/copyable-markdown/PROVENANCE.yaml`, `skills/prompt-pack/PROVENANCE.yaml`
- Pattern: Flat top-level YAML keys (`origin`, `author`, and for non-original: `upstream_repo`, `upstream_sha`, `upstream_path`, `modifications`). Both current skills are `origin: original`

**Skill Asset:**
- Purpose: A portable artifact the skill delivers verbatim to the user (not loaded as instructions)
- Examples: `skills/copyable-markdown/assets/copyblock-prompt.md`
- Pattern: Stored under the skill's `assets/`; referenced by relative path from SKILL.md

## Entry Points

**`scripts/validate.sh`:**
- Location: `scripts/validate.sh`
- Triggers: Run manually before every commit (mandated by `AGENTS.md`)
- Responsibilities: Validate provenance rules for every skill; JSON summary to stdout, status to stderr

**`scripts/diff-upstream.sh <skill> [--latest]`:**
- Location: `scripts/diff-upstream.sh`
- Triggers: Called by `validate.sh` for vendored skills, or manually to check upstream drift
- Responsibilities: Fetch upstream at pinned SHA (or default branch with `--latest`) and diff; exit 0 identical, 1 differs, 2 usage/config error

**`SKILL.md` frontmatter descriptions:**
- Location: `skills/*/SKILL.md`
- Triggers: Slash command matching the directory name, or natural-language trigger phrases listed in the `description`
- Responsibilities: Define when and how the consuming agent activates the skill

## Architectural Constraints

- **Threading:** Not applicable — no runtime; scripts are single sequential bash processes
- **Global state:** None; `diff-upstream.sh` uses isolated `mktemp -d` workspaces with trap cleanup
- **Circular imports:** Not applicable; only dependency edge is `validate.sh` → `diff-upstream.sh`
- **Network dependency:** Validating a `vendored` skill requires network access to shallow-fetch the upstream repo (`scripts/diff-upstream.sh:67`); `original` skills validate offline
- **YAML parsing is flat-key only:** `yaml_get` (duplicated in both scripts) reads only top-level `key: value` lines via sed — nested YAML in `PROVENANCE.yaml` would be silently invisible to validation
- **Content exclusivity:** A piece of information lives in SKILL.md or in `references/`, never both (`AGENTS.md`)
- **SKILL.md size cap:** under 500 lines (`AGENTS.md`)

## Anti-Patterns

### Duplicated `yaml_get` helper

**What happens:** The same sed-based YAML extractor is defined independently in `scripts/validate.sh:18` and `scripts/diff-upstream.sh:36`
**Why it's wrong:** Divergence risk — a fix to key parsing in one script won't propagate to the other
**Do this instead:** Acceptable at current scale (2 scripts); if a third script needs it, extract to a sourced `scripts/lib.sh`

### Documenting skill structure in two places

**What happens:** The skill directory contract appears in both `AGENTS.md` (full form, with `references/` and `scripts/`) and `README.md:32-38` (abbreviated form, omitting them)
**Why it's wrong:** The repo's own rule is single-source-of-truth for information; the two diagrams can drift
**Do this instead:** Treat `AGENTS.md` as authoritative for the contract; keep `README.md` a user-facing summary and update both when the layout changes

## Error Handling

**Strategy:** Fail fast with `set -euo pipefail` in both scripts; accumulate-and-report in the validator loop.

**Patterns:**
- `validate.sh` collects failures per skill via `fail()` (`scripts/validate.sh:13`) and continues checking remaining skills, then exits non-zero with a JSON failure count
- `diff-upstream.sh` distinguishes exit codes: 0 identical, 1 diff found, 2 usage/config error (`scripts/diff-upstream.sh:8`)
- Temp-dir cleanup guaranteed via `trap ... EXIT` (`scripts/diff-upstream.sh:55`)

## Cross-Cutting Concerns

**Logging:** Convention repo-wide: human status messages to stderr, machine-readable JSON to stdout (`AGENTS.md`; implemented in both scripts)
**Validation:** `scripts/validate.sh` is the single quality gate; required before every commit
**Authentication:** Not applicable — no services, no secrets. Upstream fetches use anonymous git

---

*Architecture analysis: 2026-07-21*
