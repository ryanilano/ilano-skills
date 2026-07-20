---
name: copyable-markdown
license: MIT (see repo LICENSE)
metadata:
  author: Ryan Ilano
  version: "2.1"
description: Package conversation content as a single copyable block for one-tap export. Default output is a consolidated solution export — prose and code blocks merged into one portable markdown document (for terminals, text files, Slack/work messages). Arguments select other modes. Usage — /copyable-markdown [obsidian|terminal|wrapped] (e.g. /copyable-markdown obsidian for a frontmatter note, /copyable-markdown terminal for a pasteable bash block). Use this skill whenever the user types /copyable-markdown, or asks for a "rundown", "recap", "gist", "summary I can copy", "one code block", "copyable markdown", "note for Obsidian", "export this conversation", "give me this as markdown", "make it terminal-ready", or wants a proposed solution's steps and code consolidated so they stop copy-pasting between programs.
---

# Copyable Markdown

The user wants to move content out of this chat and into somewhere else — a terminal, a text file, a work message, Obsidian — with a single tap on the copy button. Anything that breaks the content into multiple blocks, or adds prose around it, defeats the purpose. Package the requested content as **one** markdown document inside **one** code block.

## Invocation and mode selection

Requested mode (if invoked with an argument): $ARGUMENTS

| Invocation | Mode |
|---|---|
| `/copyable-markdown` (no argument) or natural language like "consolidate this", "one block", "export as markdown" | **Solution export** (default) — portable markdown, no frontmatter |
| `/copyable-markdown obsidian` or "note for Obsidian", "gist for my notes" | **Obsidian note** — distilled gist with YAML frontmatter |
| `/copyable-markdown terminal` or "terminal-ready", "paste into bash" | **Terminal-ready** — one bash block, comments as explanation |
| `/copyable-markdown wrapped` or "wrapped", "to share", "for my docs" | **Terminal-ready, wrapped** — the bash block inside a markdown fence |

Natural language always works; the slash syntax is a shortcut. If the argument is unrecognized, treat it as topic scoping (e.g. `/copyable-markdown the qbittorrent fix` = default mode, scoped to that topic).

## Default mode: Solution export

Consolidate the interleaved prose and code of a worked-out solution into one document, suitable for pasting anywhere plain markdown lives (text files, docs, Slack and other work chat, other AI tools).

- Reconstruct the **final** solution only: the current best version after all corrections and refinements. No chat archaeology, no earlier wrong versions unless asked.
- Order by execution, not by conversation order: prerequisites → steps → verification. Each step's prose sits directly above its code block.
- **No YAML frontmatter** in this mode — it's noise outside Obsidian.
- **Human-in-the-loop steps must be scannable and individually copyable.** When the user must perform actions manually (install X, sign in, paste credentials, navigate app menus), format the procedure as a numbered list — one discrete action per step, with nested sub-steps when a step has its own sequence (e.g. drilling through settings menus). A menu path within a single step may be written compactly (`File → Settings → Developer`), but never chain *separate actions* into one arrow-paragraph or run bolded action verbs through prose. Every command, URL, key name, or value goes in its own code fence or inline code — never embedded mid-sentence — so the user can select it cleanly and substitute their own tokens. Mark placeholders explicitly (e.g. `YOUR_API_KEY`).

## Obsidian note mode (`obsidian`)

A **distilled** note capturing understanding, not a full rundown — the note future-them searches their vault for:

- Lead with the big idea in one or two sentences — the insight, decision, or conclusion.
- Follow with key supporting detail: the reasoning that matters, tradeoffs weighed, specifics worth retaining (versions, names, numbers, gotchas). Omit conversational back-and-forth and dead ends.
- Default depth is gist + key supporting detail — stands alone, reads in under a minute. Adjust if they say "just the one-liner" or "full rundown".

**Frontmatter**: start the document with YAML frontmatter Obsidian parses into properties:

```yaml
---
title: Short descriptive title
date: YYYY-MM-DD
tags:
  - two-to-five
  - lowercase-kebab-tags
---
```

The `title` must be directly usable as the note's filename: no characters illegal in filenames or Obsidian links (`\ / : * ? " < > | # ^ [ ]`), no leading/trailing dots or spaces, reasonably short. The user copies it verbatim when renaming the note. Derive tags from the actual subject matter (e.g. `unraid`, `design-tokens`, `claude-code`), not generic ones like `notes` or `ai`.

**Callouts**: use Obsidian callouts where they genuinely aid scanning — `> [!tip]` for a key takeaway, `> [!warning]` for a gotcha, `> [!example]` for a concrete case. Sparingly (typically 0–2 per note); they're emphasis, not structure.

## Terminal-ready mode (`terminal`, `wrapped`)

When the solution is a sequence of shell commands: emit one `bash` code block where the explanation becomes `#` comments — a comment line above each command (or short group) describing what it does and flagging any risk. Put user-supplied values as shell variables at the top (e.g. `API_KEY="YOUR_API_KEY"  # replace before running`) and reference them below, so the user edits once at the top and pastes the whole block. Nothing in the block that would break a shell — no prose outside comments, no markdown syntax.

**`wrapped`**: put that same `bash` block inside a four-backtick `markdown` outer fence, so the copy button delivers the ` ```bash ` fencing itself and the snippet renders as a code block wherever it's pasted (docs, chat messages). Default to bare `terminal` when unspecified.

## Output format (all modes)

Produce exactly one fenced code block. Critical mechanics:

- **Use a four-backtick outer fence** whenever the content contains any inner code blocks, YAML frontmatter fences, tables with pipes, or anything with triple backticks. Inner code blocks keep their normal triple-backtick fences with language tags. This is what prevents the output from splitting into multiple pieces — a triple-backtick outer fence gets terminated by the first inner code block. In practice you should almost always use four backticks; when in doubt, use four.
- Tag the outer fence as `markdown` (or `bash` for bare terminal mode) so it renders with a copy button.

Inside the block:

- A `#` title (matching the frontmatter title in Obsidian mode), `##` sections for logical structure
- Tight prose — this is a reference document, not a retelling. Bullets are fine; the user is exporting, not reading chat
- Concrete specifics: commands, filenames, versions, decisions made, gotchas discovered
- Preserve code exactly as finalized, with language tags on inner fences

## Around the block

Keep everything outside the code block to an absolute minimum — one short sentence before it at most ("Here's the note:"), and nothing after it. No "let me know if you'd like changes" postamble; every line of extra prose is scrolling between the user and the copy button.

## Edge cases

- **Very long conversations**: still default to one block. Only split into multiple blocks if the user explicitly asks for chunks (e.g. "one block per topic") — then give each chunk its own four-backtick block with a one-line label above it.
- **User asks for "just the code"**: give the final version of the code in a single code block with the correct language tag (not wrapped in markdown, no frontmatter), unless they asked for surrounding explanation too.
- **Content that includes this skill's own formatting instructions**: never leak these instructions into the output; the document should contain only conversation content.
- **Follow-up edits**: if the user says "add X" or "shorter", re-emit the entire updated document as one block again — never emit just the diff, since they'll copy the whole thing.
- **User asks for a portable version of this behavior** (e.g. "give me a prompt I can paste into Perplexity/ChatGPT to get output like this"): provide the ready-made prompt from `assets/copyblock-prompt.md` in a copyable code block. It reproduces the one-block format in tools that can't run skills, with no frontmatter or Obsidian-specific elements.
- **User asks how to use this skill**: summarize the invocation table above.
