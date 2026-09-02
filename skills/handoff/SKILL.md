---
domd-id: 82b7cbf8-e5c0-4313-8296-fd42e13c3696
name: handoff
description: Write a session handoff the next window restates back, so context passes on without the user re-pasting links, branch state, or decisions. Use when the user says "hand this off", "pass the context on", "write a handoff", "I'm going to a new window", "restate this next time", "context is getting long", "save where we are", or invokes "handoff". Also use unprompted when a session is clearly ending and real state exists that a fresh window would otherwise make the user re-explain.
---

# handoff

Produce one dated file that carries an entire session forward, and one line the user pastes into a new window. **The user should never have to re-paste a URL, a branch name, a decision, or an explanation of what broke.**

## The whole point

A handoff fails when the next window makes the user say it all again. So the file is written **for an agent to restate**, not for a human to re-read. It opens with an instruction telling the next agent to repeat a specific block back verbatim.

**The user pastes one line. The file does the rest.**

## Invocation

```
handoff [since-ref] [--repo path] [--no-restate]
```

- `since-ref`: commit to scope the log from. Defaults to the last 20 commits.
- `--repo`: repo to inspect. Defaults to the current directory.
- `--no-restate`: skip the restate instruction, for a file that is a record rather than a relay.

## Workflow

1. **Gather measured state.** `scripts/gather_state.sh [repo]`, with `HANDOFF_SINCE=<ref>` to scope the log. It returns JSON: branch, HEAD, ahead/behind, uncommitted paths, the commit log, and any tailscale-served surfaces. **Never write a state figure you did not get from this script or another command in this session.**
2. **Confirm every URL you are about to hand over.** A dead link in a handoff costs the next session a round trip. `curl -sk -o /dev/null -w '%{http_code}'` each one. Drop or mark anything that is not 200.
3. **Compose the restate block.** Links first, then what got done, then what is open. See Restate block below.
4. **Write the file** to the user's durable notes location, dated, following whatever conventions that folder documents. Read its rules file before writing.
5. **Give the user the paste line**, and nothing else in the reply except the file path.

## The restate block

This is the part the next agent repeats. Keep it to what the user would otherwise have to say out loud again.

- **Live URLs, tappable**, each verified this session. Never a bare path or a bare host.
- **What got done**, as a short list of outcomes, not a commit dump. Commits go lower in the file.
- **What is open, unranked.** Never order the user's priorities for them; list and stop.

Write it so it can be pasted back with no edits. Do not put session narrative, apologies, or your own framing inside it.

## What else the file must carry

- **Verified git state** in a small table: branch, HEAD, ahead/behind, pushed, deployed, uncommitted paths. Say which are uncommitted **on purpose**.
- **Guards and traps**, exactly: hooks that block pushes, files that are imported nowhere, flags that change what a build contains, anything that has already burned a session.
- **The commit list**, in a fenced block, below the restate block.
- **Agent errors this session, in full.** Every one already admitted in the conversation. A handoff that omits them is a handoff that flatters the model, and the next window repeats them.
- **Standing rules that emerged this session**, with the note or file that holds the reasoning.
- **An index of notes written**, split by tier if the user keeps private material separately. **Never put private-tier contents in a shared-tier file. A pointer without the sensitive detail is the correct move.**
- **First task for the next window**, one sentence.

## Rules

- **Measured, never recalled.** Every number came from a command run in this session. If a claim was checked and did not confirm, say "checked and did not confirm" rather than dropping it or asserting it.
- **Never carry a name, quote, or figure across a privacy boundary** the user has set. If the durable notes have a public tier and a private tier, the handoff lives in the public one and points at the private one by path.
- **Do not summarise the user's own words.** Quote them.
- **No AI attribution anywhere**, in the file or in any commit it describes.

## Paste line

End the reply with exactly one line the user can copy, naming the file and telling the new window to read it and restate the block. Nothing after it.
