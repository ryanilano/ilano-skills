---
domd-id: 45b3a731-b02c-4c34-9d3f-2dbaff2dcf36
name: claim-anchor
description: Link the claims in a piece to the exact section of a docs corpus that proves each one, and report every claim that has no receipt. Use when the user asks to link a post or case study to docs, add citations or receipts, make a piece "greppable" or traceable, audit which claims are unsupported, check that existing links actually say what the sentence claims, or invokes "claim-anchor <file-or-url> <corpus-root>". Also use before publishing anything whose claims are backed by a separate docs site, changelog, or notes corpus.
---

# claim-anchor

Join two layers a writer authored separately: the **argument** (the post, the
case study) and the **record** (the docs site, the changelog, the notes). Links
at phrase granularity let a reader drop into the record exactly where they doubt
a claim and come back without losing the line.

This is for the curious reader, not the doubting one. It is navigation, not
defence. Never frame the output as claims surviving scrutiny, and never write
about a hostile reader; the author did not ask for armour, they asked for a
piece someone can move around inside.

**Useful side effect, worth reporting plainly:** the pass shows which parts of
the argument have a written trail and which do not. That is information about
the record. Three things it can mean, none of them an accusation:

- The record exists but is not published. Publish it, or link a private path and
  say so.
- The record was never written. Write it, or say the idea is ahead of the notes.
- The idea is further along in the author's head than on paper. Worth knowing
  while drafting.

## Invocation

```
claim-anchor <file-or-url> <corpus-root> [--include SUBSTR] [--section "Heading"] [--verify-only]
```

- No flags: map the corpus, propose anchors, verify, report what had no trail.
- `--include SUBSTR`: only map corpus URLs containing SUBSTR. Use on large
  sites.
- `--section "Heading"`: only anchor claims under that heading in the source.
- `--verify-only`: skip proposing, just check the links already in the source.

## Workflow

1. **Pick the corpus, out loud, before anything else.** State which corpus you
   are about to map and why. Getting this wrong produces links that resolve fine
   and still say nothing. Ask if two corpora are plausible; this is a judgment
   call, not a lookup.
2. **Map it.** `scripts/map_corpus.py <corpus-root> [--include ...]` writes JSON
   to stdout: every page, every real heading `id`, and an excerpt of the section
   under it. The excerpt is what makes step 3 possible.
3. **Extract the claims** from the source. A claim is a sentence asserting
   something checkable: a number, a date, a behaviour, a decision, a security
   property. Skip opinion and narration.
4. **Match claim to section** using the excerpts, never the heading text alone.
   A heading that sounds right is not evidence.
5. **Choose the anchor words.** The four or five words carrying the claim, not
   the sentence, not the paragraph. `47.3 KB`, not "The port ships one
   self-hosted Inter variable woff2 latin subset at 47.3 KB." See Anchor rules.
6. **Write the links** into the source.
7. **Verify.** `scripts/verify_links.py <file-or-url> --host <corpus-host>`.
   Exits non-zero on a dead URL or a missing fragment. Read every `weak` and
   every `none` yourself; the score is triage, not a verdict.
8. **Report the unanchored claims** as a list. This is required output, not an
   appendix.

## Anchor rules

- **Deep link or do not link.** Point at a heading anchor, never a bare page. A
  page-level link hands the reader the same search problem the link was meant to
  solve.
- **Anchor the claim, not the sentence.** Whole-sentence links say "this general
  area is sourced somewhere." Four-word links say which four words.
- **One link per claim.** Two links in one sentence means two claims; split them
  or pick the load-bearing one.
- **Never link a heading whose section you have not read.** The excerpt from
  step 2 is there so this costs nothing.
- **Numbers must match exactly.** If the sentence says 47.3 KB and the target
  says 47 KB, that is an unanchored claim, not a close-enough link.
- **Do not invent an anchor.** If the right section has no `id`, report it as a
  docs task. Fabricating a fragment produces a link that scrolls nowhere and
  still returns 200.

## Verification is three checks, not one

This is about not sending a reader somewhere useless. A link checker does the
first one only.

1. **The URL resolves.** Proves the page exists and nothing more.
2. **The fragment matches a real `id`.** A wrong fragment still returns 200 and
   silently drops the reader at the top of the page.
3. **The target section actually says the thing.** The only check that catches a
   link to a section that sounded right and is not.

`verify_links.py` scores check 3 as `strong`, `weak`, `none`, or `unknown` by
matching the anchor's own terms and numbers against the target section's text.
**Any number in the anchor text that the target does not state forces `none`**,
regardless of how well the words match.

## Reporting

Report in this order:

1. **What had no trail**, each with which of the three cases it is. Report it as
   information, not as a problem with the writing.
2. The links written, as `anchor text -> /path#fragment`.
3. Verification counts: checked, dead, missing anchor, unsupported.

Say that check 3 ran and what it found. "All links verified" without
distinguishing the three checks hides the only one that matters.

## References

- `references/testing.md`, the control cases, and why a green run means nothing
  until the check has been shown able to fail.
