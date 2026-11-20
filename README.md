# ilano-skills

Agent skills I make and use, built on the open [Agent Skills](https://agentskills.io) standard.

## Install

```
npx skills add ryanilano/ilano-skills
```

Install, verify and uninstall steps for Claude Code, OpenCode, Codex, Qwen Code, Gemini CLI and a plain copy are in [INSTALL.md](INSTALL.md).

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

### [spamcheck](skills/spamcheck)

You clicked unsubscribe and the mail kept coming. This reads one saved email and says whether that is the sender's fault, which law it touches, and who can act on it. It checks the hidden `List-Unsubscribe` header that powers the Unsubscribe button in Gmail and Apple Mail, probes the link for a real status code, and classifies the message commercial or political first, because CAN-SPAM only reaches commercial mail. It also dates your unsubscribe click, so the ten business day rule becomes usable. Also reads text messages: spots toll, package and bank scams, checks STOP handling, quiet hours and the ten business day window under the TCPA, and never opens a link from a text. Never opens a mailbox, never sends anything. Plain-language walkthrough in [the skill README](skills/spamcheck/README.md); legal citations quoted from primary sources in `references/`.

### [cherrypicker](skills/cherrypicker)

Two drafts of the same piece, one decision per section. Lays both side by side, aligned by what each passage does rather than by line, with A, B, Both (four ways to combine), Rewrite or Cut on every row, and exports the decisions plus a worklist of what still needs writing. Picks and notes hot-save into the page's URL as you go, so it resumes on a tablet. Plain-language walkthrough in [the skill README](skills/cherrypicker/README.md).

### [deltamaxx](skills/deltamaxx)

Which card for this purchase, and is that card worth its fee? Works out the delta, value back minus cost, from a wallet file you own: expiring credits first, then targeted offers, portals, card earn and loyalty status, all in cents. Counts overlapping perks once and credits you wouldn't spend as zero. Instructions only; no card numbers, balances or logins ever stored. Plain-language walkthrough in [the skill README](skills/deltamaxx/README.md).

## Skills by other authors

Copies of other people's skills, pinned to a commit, each with its local changes listed under `modifications` in its `PROVENANCE.yaml`. `scripts/diff-upstream.sh <skill>` shows exactly what differs from the pin, and `--latest` shows what upstream changed since. Each directory commits that expected diff as `upstream.patch`, and every `scripts/validate.sh` run (CI included) diffs again and fails when the result no longer matches, so an edit that is not in the patch is caught. ffmpeg, under "Skills", is checked the same way. Each directory carries the upstream license as `LICENSE.upstream` and a `PROVENANCE.yaml` with the repo, SHA, path and fetch time.

| Skill | What it does | Source | Author | License | Pinned commit | Local change |
|---|---|---|---|---|---|---|
| [humanizer](skills/humanizer) | Edit loop that removes the tells of AI prose, from Wikipedia's "Signs of AI writing" | [blader/humanizer](https://github.com/blader/humanizer) | Siqi Chen | MIT | `b48c832` (v4.0.0, 2026-11-09) | A "Review only" mode: asking for a review, a check or a list of tells gets the tells listed and nothing changed until you ask for a rewrite |
| [writing-fragments](skills/writing-fragments) | Explore: interview the author, append fragments to one file, no structure yet | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `3cca18b` (2026-09-04) | A credit line at the end of SKILL.md |
| [writing-beats](skills/writing-beats) | Exploit: grow the article one beat at a time, author picks the next beat | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `3cca18b` (2026-09-04) | A credit line at the end of SKILL.md |
| [writing-shape](skills/writing-shape) | Exploit: pick an opening, grow the article block by block, ground every concept first | [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock | MIT | `3cca18b` (2026-09-04) | A credit line at the end of SKILL.md |
| [unslop](skills/unslop) | 25 AI-writing patterns in five groups plus a voice pass; typed only (`/unslop`) | [poteto/noodle](https://github.com/poteto/noodle) | Lauren Tan | MIT | `82d2921` (2026-03-19) | Report mode by default: lists the patterns and changes nothing unless asked; rewrites only text known to be agent-written; typed only, since its upstream triggers overlap humanizer |
| [adversarial-review](skills/adversarial-review) | Skeptic, Architect and Minimalist reviewers sized to the change, then a judge who did not write the work accepts or rejects each finding | [poteto/noodle](https://github.com/poteto/noodle) | Lauren Tan (round budget from Theo Browne's sol-loop, [t3dotgg/tstack](https://github.com/t3dotgg/tstack)) | MIT | `82d2921` (2026-03-19) | Reviewers are Claude subagents instead of the opposite model's CLI; independent judge; offline review targets for GitHub, Forgejo and Gitea PRs; INCOMPLETE verdict; rounds with a ledger. Full list in PROVENANCE.yaml |
| [how](skills/how) | Explain how a subsystem, feature or flow works: read-only explorers fan out, one explainer writes Overview, Key Concepts, How It Works, Where Things Live, Gotchas; optional architecture critique | [poteto/how](https://github.com/poteto/how) | Lauren Tan | MIT | `b1ef429` (2026-04-14) | Cursor model names and subagent parameters replaced by a model-tier table mapped to Claude Code (sonnet explorers, opus explainer, fable or opus critics), a context-pointer description, and a credit line |
| [modernize](skills/modernize) | Rebase an aging PR only after judging whether it should still land: MODERNIZE, REWORK or CLOSE | [t3dotgg/tstack](https://github.com/t3dotgg/tstack) | Theo Browne | MIT | `11e37a7` (2026-11-11) | Works on Forgejo/Gitea (`tea` or plain git) as well as GitHub; asks before any push unless you already said to push; no dependency on tstack's other skills |
| [file-pr](skills/file-pr) | File a concise PR: problem-first description, a title that says why, secret check before filing | [t3dotgg/tstack](https://github.com/t3dotgg/tstack) | Theo Browne | MIT | `11e37a7` (2026-11-11) | Works on Forgejo/Gitea (`tea`) as well as GitHub; no model or harness footer in the PR body; no dependency on tstack's other skills |

How the writing skills chain: writing-fragments builds the pile, writing-shape or writing-beats turns the pile into an article, humanizer edits the result. The three Pocock writing skills are user-invoked only (`disable-model-invocation: true` upstream). unslop is a lighter, typed-only alternative to humanizer; run one or the other on a draft.

How the code skills fit: how explains a part of the codebase, file-pr opens the PR, adversarial-review gives a hard review before it opens or merges, and modernize revives an old PR.

writing-for-agents, the reference the original skills here are written and pruned against, is no longer vendored. Install Matt Pocock's plugin for it: `claude plugin install mattpocock-skills@claude-plugins-official` ([mattpocock/skills](https://github.com/mattpocock/skills)). Every original skill here was audited against it on 2026-09-17 and again on 2026-11-12 at upstream `49dd158`.

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

Skills under "Skills" are original, except ffmpeg, which is a fork of [MastroMimmo/ffmpeg-skill](https://github.com/MastroMimmo/ffmpeg-skill) (MIT) with the modifications listed in its PROVENANCE.yaml. Skills under "Skills by other authors" belong to their authors, named in each directory's PROVENANCE.yaml and LICENSE.upstream.
