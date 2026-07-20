---
name: prompt-pack
description: Compress a free-form, conversational task description into a structured, token-efficient prompt ready to paste into an agentic coding tool (Claude Code, Cline, or similar). Use this whenever the user has described a coding or repo task loosely and wants it turned into a clean agent prompt — triggers include "make this into a prompt," "pack this for Cline/Claude Code," "turn this into an agent task," "tighten this prompt," or any time the user dumps a rambling task description and wants the executable core extracted. Also use proactively when a user's request is clearly destined for another agent rather than for you to execute directly.
---

# Prompt Pack

Turn a loose, conversational task description into a compact prompt for a *different* coding agent to run. The user orchestrates; the agent executes. A good pack is skimmable in seconds and noticeably shorter than the conversation it came from.

## Optimize for

1. **Semantic core** — cut pleasantries, hedging, backstory, repetition. Keep only what changes agent behavior.
2. **Execution order** — read → analyze → produce. Front-load grounding before action.
3. **Anchored output** — name the exact deliverable, its format, location, and a checkable acceptance condition. Unanchored prompts cause drift and invented work.

## Workflow

1. **Extract intent** from the description. Reuse any files, constraints, or stack already given in the conversation — don't make the agent rediscover them.
2. **Confirm target + mode** if unstated; default to Claude Code execute mode. (See Targets and modes.)
3. **Fill the template** below — imperative voice, no prose paragraphs.
4. **Flag gaps, never invent.** Don't fabricate file paths, frameworks, versions, or environment details (OS, distro, versions, hardware). If one is missing or a command depends on it, add a `# NEEDS: <thing>` line at the top instead of guessing.
5. **Return one fenced code block** — copy-pasteable, with nothing after it except a one-line note if a `# NEEDS` flag exists.

## Output template

Exact skeleton. Omit a line only if it genuinely has no content; never pad.

```
# Objective
<one sentence: the end state, not the activity>

# Context
- Read first: <files/dirs to ground in, most specific first>
- Stack: <only constraining facts — lang, framework, versions IF KNOWN>
- Constraints: <scope guards, do-not-touch, conventions>

# Task
1. Read: <what to inspect before acting>
2. Analyze: <what to decide>
3. Produce: <what to write/change>

# Output
- Deliverable: <exact artifact + format + path>
- Acceptance: <verifiable done condition — tests pass, file exists, lint clean>
```

- **Objective = one sentence.** Two means two tasks — say so.
- **Read first** is the anti-drift lever: list the narrowest set of files that pins the work.
- **Acceptance must be checkable** ("renders without console errors"), not aspirational ("looks good").

## Targets and modes

Targets agentic tools with full repo access (Claude Code, Cline, and similar) — they read the codebase and edit files themselves. Adjust only for mode:

- **Execute** (Claude Code agent, Cline Act — default): template as-is.
- **Plan** (Claude Code plan, Cline Plan, read-only): append `Output a plan only; do not edit files.`, change Deliverable to `an ordered implementation plan`, and emphasize the Analyze step.

Unfamiliar target: confirm it has autonomous file access before using this template; if not, ask how they intend to run the prompt.

## Example

Input: *"my Astro site's mobile nav is a mess — the hamburger works but the menu doesn't trap focus and screen readers skip it. It's in the components folder somewhere."*

```
# Objective
Make the mobile nav menu keyboard- and screen-reader-accessible.

# Context
- Read first: src/components/ (locate the nav/hamburger component)
- Stack: Astro
- Constraints: WCAG 2.1 AA; don't restyle; preserve hamburger toggle behavior

# Task
1. Read: the nav component and its open/close logic
2. Analyze: focus trap while open, focus restore on close, ARIA roles/state for toggle and menu
3. Produce: the accessibility fixes in place

# Output
- Deliverable: edited nav component file(s)
- Acceptance: focus trapped while open; Esc closes and restores focus to toggle; toggle exposes aria-expanded; menu announced by screen readers
```

For **plan mode**: same pack with `Deliverable: an ordered implementation plan`, an inventory-style Acceptance, and a trailing `Output a plan only; do not edit files.`
