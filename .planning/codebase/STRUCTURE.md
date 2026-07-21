# Codebase Structure

**Analysis Date:** 2026-07-21

## Directory Layout

```
ilano-skills/
├── .claude-plugin/            # Claude Code plugin + marketplace manifests
│   ├── plugin.json            # Plugin identity: name "ilano", version, license
│   └── marketplace.json       # Marketplace listing pointing at repo root
├── .planning/                 # GSD planning artifacts (this analysis lives here)
│   └── codebase/              # Codebase mapping documents
├── scripts/                   # Repo tooling (bash)
│   ├── validate.sh            # Provenance validation gate — run before every commit
│   └── diff-upstream.sh       # Diff a skill against its pinned upstream
├── skills/                    # The product: one directory per agent skill
│   ├── copyable-markdown/     # Conversation-export skill (formerly markdown-copy)
│   │   ├── SKILL.md           # Skill definition (frontmatter + instructions)
│   │   ├── PROVENANCE.yaml    # origin: original
│   │   └── assets/
│   │       └── copyblock-prompt.md  # Portable prompt handed to users on request
│   └── prompt-pack/           # Task-description → agent-prompt compression skill
│       ├── SKILL.md
│       └── PROVENANCE.yaml    # origin: original
├── AGENTS.md                  # Authoritative repo conventions (skill format, provenance rules)
├── CLAUDE.md                  # Single line: @AGENTS.md (delegates to conventions)
├── LICENSE                    # MIT
├── README.md                  # Install paths, skill catalog, structure summary
└── .gitattributes             # LF normalization (* text=auto)
```

## Directory Purposes

**`skills/`:**
- Purpose: All agent skills; each subdirectory is a complete, self-contained skill
- Contains: One kebab-case directory per skill — the directory name IS the slash command
- Key files: `skills/copyable-markdown/SKILL.md`, `skills/prompt-pack/SKILL.md`

**`skills/{skill-name}/`:**
- Purpose: A single skill's full contents
- Contains: `SKILL.md` (required), `PROVENANCE.yaml` (required), plus optional `assets/` (files the skill ships), `references/` (docs loaded on demand), `scripts/` (executable helpers). Only `assets/` is currently in use (`skills/copyable-markdown/assets/`)
- Key files: `SKILL.md` — YAML frontmatter with `name` (must match directory name) and `description` (states what the skill does, when to use it, and the trigger phrases users type)

**`scripts/`:**
- Purpose: Repo-level maintenance tooling (distinct from per-skill `scripts/` dirs)
- Contains: Bash scripts following the repo script standard (`#!/bin/bash`, `set -e`, stderr status / stdout JSON, trap cleanup)
- Key files: `scripts/validate.sh`, `scripts/diff-upstream.sh`

**`.claude-plugin/`:**
- Purpose: Distribution as a Claude Code plugin (`/plugin marketplace add ryanilano/ilano-skills`, `/plugin install ilano`)
- Contains: `plugin.json` (plugin metadata), `marketplace.json` (marketplace entry with `source: "./"`)
- Key files: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**`.planning/`:**
- Purpose: GSD planning and codebase-mapping artifacts
- Contains: `codebase/` analysis documents
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`

## Key File Locations

**Entry Points:**
- `scripts/validate.sh`: Provenance quality gate — run before every commit
- `scripts/diff-upstream.sh`: Upstream drift check for vendored/forked skills
- `skills/*/SKILL.md`: Agent-facing entry points, triggered by slash command or description trigger phrases

**Configuration:**
- `.claude-plugin/plugin.json`: Plugin name/version/license
- `.claude-plugin/marketplace.json`: Marketplace listing
- `.gitattributes`: LF line-ending normalization for all text files
- `AGENTS.md`: Repo conventions (the effective config for how skills are authored)
- `CLAUDE.md`: Loads `AGENTS.md` via `@AGENTS.md` reference

**Core Logic:**
- `skills/copyable-markdown/SKILL.md`: Copyable-block export skill (4 modes: default solution export, `obsidian`, `terminal`, `wrapped`)
- `skills/prompt-pack/SKILL.md`: Prompt compression skill with fixed output template
- `skills/copyable-markdown/assets/copyblock-prompt.md`: Ready-made portable prompt for non-skill tools

**Testing:**
- No test framework. `scripts/validate.sh` is the only automated check (structural/provenance validation, not behavioral testing of skills)

## Naming Conventions

**Files:**
- `SKILL.md`, `PROVENANCE.yaml`, `LICENSE.upstream` — exact uppercase canonical names, one per skill
- Repo docs: UPPERCASE.md (`README.md`, `AGENTS.md`, `CLAUDE.md`)
- Scripts: kebab-case with `.sh` extension (`diff-upstream.sh`)
- Assets: kebab-case markdown (`copyblock-prompt.md`)

**Directories:**
- Skill directories: kebab-case, and the name doubles as the slash command (`copyable-markdown` → `/copyable-markdown`)
- Per-skill subdirectories: fixed vocabulary — `assets/`, `references/`, `scripts/`

## Where to Add New Code

**New Skill:**
- Primary code: `skills/{new-skill-name}/SKILL.md` — kebab-case directory; frontmatter `name` must equal the directory name; `description` must include real trigger phrases; keep under 500 lines
- Required sibling: `skills/{new-skill-name}/PROVENANCE.yaml` with `origin: original | vendored | fork`. Vendored/forked skills pin `upstream_repo`, `upstream_sha`, `upstream_path`; forks also add `LICENSE.upstream` and a non-empty `modifications` list
- After adding: run `scripts/validate.sh` (must pass before commit) and add the skill to the catalog in `README.md` and the plugin description in `.claude-plugin/marketplace.json` / `.claude-plugin/plugin.json` if it changes
- Detail overflow: put on-demand documentation in `skills/{new-skill-name}/references/` — a piece of information lives in SKILL.md or `references/`, never both

**Skill Assets (files the skill hands to users):**
- Implementation: `skills/{skill-name}/assets/` — reference them from SKILL.md by relative path (pattern: `skills/copyable-markdown/SKILL.md:90`)

**Executable helpers for a skill:**
- Implementation: `skills/{skill-name}/scripts/` — `#!/bin/bash`, `set -e`, status to stderr, JSON to stdout, trap-based temp cleanup. Point SKILL.md at the script rather than inlining its body

**Repo tooling:**
- Shared helpers: `scripts/` at repo root, same script standards. Note `yaml_get` is currently duplicated in both existing scripts — extract a shared lib if adding a third consumer

## Special Directories

**`.claude-plugin/`:**
- Purpose: Claude Code plugin/marketplace manifests
- Generated: No (hand-maintained)
- Committed: Yes

**`.planning/`:**
- Purpose: GSD workflow state and codebase maps
- Generated: Yes (by GSD commands)
- Committed: Yes (per GSD convention)

**`skills/{skill}/assets/`:**
- Purpose: Verbatim artifacts a skill delivers (not loaded as agent instructions)
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-07-21*
