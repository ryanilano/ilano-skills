# ilano-skills

Agent skills I make and use, built on the open [Agent Skills](https://agentskills.io) standard.

## Install

```
npx skills add ryanilano/ilano-skills
```

Or as a Claude Code plugin:

```
/plugin marketplace add ryanilano/ilano-skills
/plugin install ilano
```

Or just copy a folder from [skills/](skills/) into `~/.claude/skills/`.

## Skills

### [Copyable Markdown](skills/copyable-markdown)

Packages conversation content as one copyable block — a consolidated solution export by default, or `obsidian` for a frontmatter note, `terminal` for a pasteable bash block. Formerly markdown-copy.

### [Prompt Pack](skills/prompt-pack)

Compresses a loose task description into a structured, token-efficient prompt for an agentic coding tool. You orchestrate; the agent executes.

## Structure

```
skills/
└── skill-name/
    ├── SKILL.md          # required — the skill itself
    ├── assets/           # optional — files the skill ships
    └── PROVENANCE.yaml   # origin and credit
```

## Credits

All skills here are original unless noted in their PROVENANCE.yaml.
