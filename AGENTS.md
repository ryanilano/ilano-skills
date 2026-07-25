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

- Shell helpers start with `#!/bin/bash` and `set -e`.
- Python helpers start with `#!/usr/bin/env python3`, import only the standard
  library, and assert a minimum version. Reach for Python when date arithmetic,
  JSON parsing, or a platform API makes bash the wrong tool; otherwise use bash.
- Status messages go to stderr; JSON output goes to stdout. This is for context
  efficiency, not privacy: the harness captures both streams into the
  transcript, so stderr is not a hiding place.
- Clean up temp files with traps.
- A script that reads credentials never prints them, never writes them to a
  cache or log, and never passes them as an argument or environment variable to
  a child process. Report a byte count on a parse failure, never the payload.

## Provenance

- Every skill directory has a `PROVENANCE.yaml` with `origin: original | vendored | fork`.
- Vendored and forked skills pin their source: `upstream_repo`, `upstream_sha`, `upstream_path`.
- Forks also add a `LICENSE.upstream` file and a non-empty `modifications` list.
- Run `scripts/validate.sh` before every commit.

## Editing

- Make surgical changes. Don't rewrite what you weren't asked to touch.
- A piece of information lives in SKILL.md or in `references/`, never both.
