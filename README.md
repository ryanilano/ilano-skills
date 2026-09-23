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

Packages conversation content as one copyable block — a consolidated solution export by default, or `obsidian` for a frontmatter note, `terminal` for a pasteable bash block. Formerly markdown-copy. Plain-language walkthrough in [the skill README](skills/copyable-markdown/README.md).

### [Prompt Pack](skills/prompt-pack)

Compresses a loose task description into a structured, token-efficient prompt for an agentic coding tool. You orchestrate; the agent executes. Plain-language walkthrough in [the skill README](skills/prompt-pack/README.md).

### [docs-mirror](skills/docs-mirror)

Mirrors a whole documentation site or an RSS/Atom feed to local markdown in one command. Plain HTTP, no browser, no per-page model call. Honors robots.txt and rate-limits by default. Plain-language walkthrough in [the skill README](skills/docs-mirror/README.md).

### [yt-cc](skills/yt-cc)

Pulls a video's captions to local markdown in one command, and serves a searchable board of everything grabbed. No video download, no transcription API. Plain-language walkthrough in [the skill README](skills/yt-cc/README.md).

### [socials-mirror](skills/socials-mirror)

Snapshots a public figure's public profiles (GitHub, Bluesky, any RSS/Atom feed, Reddit `.rss`) to markdown in one command. Public data only, no login, one-shot. Also reads NetNewsWire's local cache with zero network. Plain-language walkthrough in [the skill README](skills/socials-mirror/README.md).

### [ffmpeg](skills/ffmpeg)

Video, audio and image-sequence editing through one JSON-returning helper (`fftools.py`, 18 commands, by MastroMimmo, MIT). Forked: the script is upstream's, the skill text is rewritten steps-first with the catalog disclosed to `references/`. Pairs with yt-cc's `--video`. Plain-language walkthrough in [the skill README](skills/ffmpeg/README.md).

### [tool-call-repair](skills/tool-call-repair)

Validate-then-repair for malformed LLM tool-call inputs, so open and cheaper models stop bouncing off strict schemas. Independent Python reimplementation of Ahmad Awais's documented technique; stdlib only. Plain-language walkthrough in [the skill README](skills/tool-call-repair/README.md).

### [spamcheck](skills/spamcheck)

You clicked unsubscribe and the mail kept coming. This reads one saved email and says whether that is the sender's fault, which law it touches, and who can act on it. It checks the hidden `List-Unsubscribe` header that powers the Unsubscribe button in Gmail and Apple Mail, probes the link for a real status code, and classifies the message commercial or political first, because CAN-SPAM only reaches commercial mail. It also dates your unsubscribe click, so the ten business day rule becomes usable. Never opens a mailbox, never sends anything. Plain-language walkthrough in [the skill README](skills/spamcheck/README.md); legal citations quoted from primary sources in `references/`.

### [cherrypicker](skills/cherrypicker)

Two drafts of the same piece, one decision per section. Lays both side by side, aligned by what each passage does rather than by line, with A, B, Both (four ways to combine), Rewrite or Cut on every row, and exports the decisions plus a worklist of what still needs writing. Picks and notes hot-save into the page's URL as you go, so it resumes on a tablet. Plain-language walkthrough in [the skill README](skills/cherrypicker/README.md).

## Vendored skills

Byte-identical copies of other people's skills, pinned to a commit. `scripts/validate.sh` diffs each one against its upstream on every run, and `scripts/diff-upstream.sh <skill> --latest` shows what upstream changed since. Each directory carries the upstream license as `LICENSE.upstream` and a `PROVENANCE.yaml` with the repo, SHA, path and fetch time.

| Skill | What it does | Source | Author | License | Pinned commit |
|---|---|---|---|---|---|
| [humanizer](skills/humanizer) | Edit loop that removes the tells of AI prose, from Wikipedia's "Signs of AI writing" | [blader/humanizer](https://github.com/blader/humanizer) | Siqi Chen | MIT | `9862685` (v3.0.0, 2026-09-06) |
| [writing-fragments](skills/writing-fragments) | Explore: interview the author, append fragments to one file, no structure yet | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `3cca18b` (2026-09-04) |
| [writing-beats](skills/writing-beats) | Exploit: grow the article one beat at a time, author picks the next beat | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `3cca18b` (2026-09-04) |
| [writing-shape](skills/writing-shape) | Exploit: pick an opening, grow the article block by block, ground every concept first | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `3cca18b` (2026-09-04) |
| [writing-for-agents](skills/writing-for-agents) | The reference for any document an agent reads: context pointers, the two loads, information hierarchy, leading words, pruning | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `74ca5fe` (2026-09-17) |

How the writing skills chain: writing-fragments builds the pile, writing-shape or writing-beats turns the pile into an article, humanizer edits the result. The three Pocock writing skills are user-invoked only (`disable-model-invocation: true` upstream).

writing-for-agents is different in kind: it is the reference the original skills in this repo are written and pruned against, and it fires on its own whenever a skill, `AGENTS.md`, or `CLAUDE.md` is being edited. Every original skill here was audited against it on 2026-09-17.

## Structure

```
skills/
└── skill-name/
    ├── SKILL.md          # required — the skill itself
    ├── PROVENANCE.yaml   # required — origin and credit
    ├── assets/           # optional — files the skill ships
    ├── references/       # optional — docs loaded on demand
    └── scripts/          # optional — executable helpers
```

## Credits

Skills under "Skills" are original, except ffmpeg, which is a fork of [MastroMimmo/ffmpeg-skill](https://github.com/MastroMimmo/ffmpeg-skill) (MIT) with the modifications listed in its PROVENANCE.yaml. Skills under "Vendored skills" belong to their authors, named in each directory's PROVENANCE.yaml and LICENSE.upstream.
