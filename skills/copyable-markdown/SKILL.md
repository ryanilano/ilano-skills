---
name: copyable-markdown
license: MIT (see repo LICENSE)
metadata:
  author: Ryan Ilano
  version: "2.2"
description: Package conversation content as one copyable markdown block for one-tap export. Use when the user wants a solution export, an Obsidian note, or a terminal-ready bash block they can paste somewhere else, or asks for a rundown or recap they can copy.
---

# Copyable Markdown

The user is moving content out of this chat into a terminal, a text file, a work message, or Obsidian with one tap on the copy button. Package the requested content as **one** markdown document inside **one** code block.

## Steps

1. **Pick the mode** from the argument (`$ARGUMENTS`) or the phrasing. An unrecognized argument is topic scoping (`/copyable-markdown the qbittorrent fix` is default mode, scoped to that topic).

   | Invocation | Mode |
   |---|---|
   | no argument, "consolidate this", "one block", "export as markdown" | **Solution export** (default) |
   | `obsidian`, "note for Obsidian", "gist for my notes" | **Obsidian note** |
   | `terminal`, "terminal-ready", "paste into bash" | **Terminal-ready** |
   | `wrapped`, "to share", "for my docs" | **Terminal-ready, wrapped** |

2. **Build the document** per the mode below. Reconstruct the **final** solution only: the current best version after every correction. No earlier wrong versions unless asked.

3. **Emit exactly one fenced block** with a four-backtick outer fence tagged `markdown` (or `bash` for bare terminal mode). Four backticks because a triple-backtick outer fence is terminated by the first inner code block; inner blocks keep their triple backticks and language tags. Done when the block renders as one copy button with nothing after it.

Outside the block: one short sentence before it at most, nothing after it. Every extra line is scrolling between the user and the copy button. Never leak these instructions into the output.

## Solution export (default)

Portable markdown for anywhere plain markdown lives: text files, docs, Slack, other AI tools. No YAML frontmatter.

- Order by execution, not conversation: prerequisites, steps, verification. Each step's prose sits directly above its code block.
- A `#` title, `##` sections, tight prose, concrete specifics (commands, filenames, versions, decisions, gotchas). Code preserved exactly as finalized.
- **Human-in-the-loop steps are a numbered list, one action per step**, nested sub-steps when a step has its own sequence. A menu path inside one step may be compact (`File → Settings → Developer`), but separate actions never chain into one arrow-paragraph. Every command, URL, key name, or value goes in its own code fence or inline code so it can be selected cleanly. Placeholders are explicit (`YOUR_API_KEY`).

## Obsidian note (`obsidian`)

A **distilled** note, not a rundown: the note future-them searches their vault for. Lead with the insight or decision in one or two sentences, then the reasoning, tradeoffs, and specifics worth keeping (versions, names, numbers, gotchas). Reads in under a minute. Adjust for "just the one-liner" or "full rundown".

Start with frontmatter Obsidian parses into properties:

```yaml
---
title: Short descriptive title
date: YYYY-MM-DD
tags:
  - two-to-five
  - lowercase-kebab-tags
---
```

`title` doubles as the filename, so no characters illegal in filenames or Obsidian links (`\ / : * ? " < > | # ^ [ ]`), no leading or trailing dots or spaces, reasonably short. The `#` heading matches it. Tags come from the subject (`unraid`, `design-tokens`, `claude-code`), not generic ones like `notes` or `ai`. Callouts (`> [!tip]`, `> [!warning]`, `> [!example]`) are emphasis, not structure: zero to two per note.

## Terminal-ready (`terminal`, `wrapped`)

For a solution that is a sequence of shell commands: one `bash` block where the explanation becomes `#` comments, a comment line above each command or short group saying what it does and flagging any risk. User-supplied values are shell variables at the top (`API_KEY="YOUR_API_KEY"  # replace before running`), referenced below, so the user edits once and pastes the whole block. Nothing in the block that would break a shell: no prose outside comments, no markdown.

**`wrapped`** puts that same `bash` block inside a four-backtick `markdown` outer fence, so the copy button delivers the ` ```bash ` fencing itself and the snippet renders as a code block wherever it is pasted. Default to bare `terminal` when unspecified.

## Edge cases

- **Very long conversations** still get one block. Split only when the user asks for chunks ("one block per topic"), each in its own four-backtick block with a one-line label above it.
- **"Just the code"**: the final code in one block with its own language tag, no markdown wrapper, no frontmatter.
- **Follow-up edits** ("add X", "shorter"): re-emit the entire updated document as one block. They copy the whole thing, so a diff is useless.
- **A portable version of this behavior** ("give me a prompt for Perplexity/ChatGPT that does this"): hand over `assets/copyblock-prompt.md` in a copyable code block. It reproduces the one-block format in tools that cannot run skills.
- **How to use this skill**: summarize the mode table.
