# prompt-pack, explained for people

You described a task in a chat, loosely, with backstory and hedging, the way people
talk. Now you want a different coding agent to go do it. This skill turns that
description into a short structured prompt the other agent can act on without
guessing.

## What comes out

One code block you can paste, with four headings:

- **Objective**: one sentence describing the end state.
- **Context**: which files to read first, what the stack is, what not to touch.
- **Task**: read, analyze, produce, in that order.
- **Output**: the exact deliverable and a check that says when it is done.

## Why it is shaped this way

1. **Objective is one sentence** because two sentences usually means two tasks, and
   agents drift when they are given two.
2. **"Read first" is listed** because an agent that starts editing before it has read
   the right files invents things. Naming the narrowest set of files pins the work.
3. **Acceptance has to be checkable.** "Tests pass" or "the file exists" can be
   verified. "Looks good" cannot, and an agent will declare it done anyway.

## Why it never fills in a gap

If you did not say which framework, which version or which operating system, the pack
does not guess. It writes a line at the top that says what is missing, so you fill it
in before you send it. An invented file path costs the other agent more time than a
missing one.

## Plan mode

If you want the other agent to propose a plan rather than edit files, say so. The pack
changes the deliverable to an ordered plan and tells the agent not to touch anything.

## Ask for it

Say "pack this", "turn this into a prompt for Claude Code" or "tighten this prompt".
