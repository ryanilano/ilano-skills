# Technology Stack

**Analysis Date:** 2026-07-21

## Languages

**Primary:**
- Markdown - Skill definitions (`skills/*/SKILL.md`), prompt assets (`skills/copyable-markdown/assets/copyblock-prompt.md`), repo docs (`README.md`, `AGENTS.md`)
- Bash - Validation and tooling scripts (`scripts/validate.sh`, `scripts/diff-upstream.sh`)

**Secondary:**
- YAML - Provenance metadata (`skills/*/PROVENANCE.yaml`) and SKILL.md frontmatter
- JSON - Claude Code plugin manifests (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`)

## Runtime

**Environment:**
- Bash (scripts declare `#!/bin/bash` with `set -euo pipefail`); requires standard Unix tools: `sed`, `awk`, `diff`, `mktemp`, `git`
- No language runtime (Node, Python, etc.) is required to use or validate the repo

**Package Manager:**
- None - no `package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, or `pyproject.toml`
- Lockfile: Not applicable

## Frameworks

**Core:**
- Agent Skills standard (agentskills.io) - Skill format: directory name = slash command, `SKILL.md` with YAML frontmatter (`name`, `description`)
- Claude Code plugin system - `.claude-plugin/plugin.json` (plugin `ilano`, version 0.1.0, MIT) and `.claude-plugin/marketplace.json` (marketplace `ilano-skills`)

**Testing:**
- No test framework - validation is `scripts/validate.sh` (provenance rule checks, JSON summary to stdout, status to stderr, non-zero exit on failure)

**Build/Dev:**
- No build step - skills are consumed as plain files
- `scripts/diff-upstream.sh` - dev tool to diff a vendored/forked skill against its pinned upstream (`diff-upstream.sh <skill> [--latest]`)

## Key Dependencies

**Critical:**
- Git - `scripts/diff-upstream.sh` performs `git init` / `git fetch --depth 1` of upstream repos into a temp dir; also required by validate.sh when any skill has `origin: vendored`
- None otherwise - the two current skills (`copyable-markdown`, `prompt-pack`) are `origin: original` with no upstream

**Infrastructure:**
- Not applicable - no runtime services or libraries

## Configuration

**Environment:**
- No environment variables required; no `.env` files exist
- Skill behavior configured entirely via `SKILL.md` frontmatter and arguments (e.g. `/copyable-markdown [obsidian|terminal|wrapped]`)

**Build:**
- `.gitattributes` - normalizes all text files to LF (`* text=auto`)
- `.claude-plugin/plugin.json` - plugin identity/version for Claude Code
- `.claude-plugin/marketplace.json` - marketplace listing pointing plugin source at repo root (`"source": "./"`)

## Platform Requirements

**Development:**
- POSIX-like system with Bash, coreutils, and Git
- Convention: run `scripts/validate.sh` before every commit (per `AGENTS.md`)

**Production:**
- Distribution targets (per `README.md`):
  - `npx skills add ryanilano/ilano-skills` (Agent Skills CLI via npx - Node needed only by end users installing this way)
  - Claude Code plugin: `/plugin marketplace add ryanilano/ilano-skills` then `/plugin install ilano`
  - Manual copy of a `skills/` folder into `~/.claude/skills/`

---

*Stack analysis: 2026-07-21*
