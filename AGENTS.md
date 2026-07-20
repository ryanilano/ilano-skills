# Conventions

Rules for working in this repo. Follow them exactly.

## Directory structure

```
skills/
└── {skill-name}/          # kebab-case; the directory name IS the slash command
    ├── SKILL.md           # required
    ├── PROVENANCE.yaml    # required — origin and credit
    ├── assets/            # optional — files the skill ships (templates, prompts)
    ├── references/        # optional — docs loaded on demand
    └── scripts/           # optional — executable helpers
```

## SKILL.md format

- YAML frontmatter with `name` (must match the directory name) and `description`.
- The description states what the skill does and when to use it — include the trigger phrases users actually type.

## Context efficiency

- Keep SKILL.md under 500 lines.
- Progressive disclosure: overview and workflow in SKILL.md, details in `references/`.
- Prefer scripts over inline code — point to a script instead of pasting its body.

## Script standards

- Start with `#!/bin/bash` and `set -e`.
- Status messages go to stderr; JSON output goes to stdout.
- Clean up temp files with traps.

## Provenance

- Every skill directory has a `PROVENANCE.yaml` with `origin: original | vendored | fork`.
- Vendored and forked skills pin their source: `upstream_repo`, `upstream_sha`, `upstream_path`.
- Forks also add a `LICENSE.upstream` file and a non-empty `modifications` list.
- Run `scripts/validate.sh` before every commit.

## Editing

- Make surgical changes. Don't rewrite what you weren't asked to touch.
- A piece of information lives in SKILL.md or in `references/`, never both.
