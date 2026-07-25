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

### [Headroom](skills/headroom)

Reports Claude subscription headroom across multiple accounts and says which one to work on and whether to spend or conserve. Covers Claude Pro and Max subscriptions bought directly from Anthropic; it cannot report on Bedrock, Vertex, pay-as-you-go API keys, or non-Anthropic providers.

> [!IMPORTANT]
> **This skill reads credentials.** It reads the OAuth token Claude Code stores for each account (macOS Keychain, or `.credentials.json` elsewhere) and makes one HTTPS request to `https://api.anthropic.com/api/oauth/usage`. Your token is never printed, logged, cached, or passed as a command argument, and it never leaves your machine except in that one `Authorization` header. It writes only derived percentages and reset times, to `~/.cache/headroom/`. Full detail is in [its SKILL.md](skills/headroom/SKILL.md).

## Structure

```
skills/
└── skill-name/
    ├── SKILL.md          # required — the skill itself
    ├── assets/           # optional — files the skill ships
    ├── scripts/          # optional — executable helpers
    └── PROVENANCE.yaml   # origin and credit
```

## Credits

All skills here are original unless noted in their PROVENANCE.yaml.
