# copyable-markdown, explained for people

You worked something out in a chat and now you want it somewhere else: a terminal, a
note in Obsidian, a message to a colleague. Most chat tools give you a copy button per
code block, so a long answer means six copies and six pastes. This skill packages the
whole thing as one block with one copy button.

## What it produces

One markdown document inside one code fence. Nothing before it but a single sentence,
nothing after it. The fence uses four backticks so the code blocks inside it keep their
own three-backtick fences and still render as code wherever you paste.

## The three modes, and when each one fits

1. **Solution export**, the default. A portable document ordered by execution:
   prerequisites, steps, verification. Every command, path and value sits in its own
   code fence so it can be selected cleanly. Steps you do by hand are a numbered list,
   one action per step.
2. **Obsidian note**. A distilled note, not a rundown. It opens with the decision or
   insight, then the reasoning and the specifics worth keeping. It starts with
   frontmatter Obsidian reads as properties: a title safe to use as a filename, a date,
   and two to five tags drawn from the subject.
3. **Terminal-ready**. A single bash block. The explanation becomes comment lines above
   each command. Values you need to supply are variables at the top, so you edit once
   and paste the whole thing.

## Why it rebuilds the final version only

A conversation wanders. You tried one fix, it failed, you tried another. The export
contains the last working version and nothing else, unless you ask for the history.

## Why follow-ups re-emit the whole block

If you say "shorter" or "add the rollback step", you get the entire updated document
again, not a diff. You are going to copy the whole thing, so a partial update is
useless.

## Ask for it

Say "one block", "export this as markdown", "note for Obsidian" or "paste into bash".
A topic after the command scopes it: `/copyable-markdown the nginx fix`.
