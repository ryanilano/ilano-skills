---
name: cherrypicker
description: "Build a side-by-side page for merging two drafts of the same writing, one decision per section, with the decisions exported as markdown. Use when someone has two versions of a document to reconcile, asks which draft is better, or when a repo holds two near-duplicate content files competing for one slot. Not for code diffs or three or more versions."
---

# cherrypicker

A line diff answers which bytes changed. Two drafts of one essay need a different answer: which version says each thing better, when the two use different headings, order and section counts. This skill lays both drafts side by side, **aligned** by what each passage does, with a picker on every row. The human makes every editorial call; your work is the alignment.

Requires `pip install markdown`. Step 5 also needs `pip install playwright && playwright install chromium`.

## Steps

### 1. Read both drafts in full

Alignment is judgment: pairing "the opening pitch" in one file with "Background" in the other needs both texts in your head. Done when you can say, for every section of each draft, what it is arguing.

### 2. List the units

```bash
python3 scripts/cherrypicker.py units A.md B.md
```

Prints an indexed table per file: one unit per heading (levels 2 to 4), plus one per pull quote or callout, since a pull quote is its own decision. MDX is handled: frontmatter, imports, `{/* comments */}` and layout wrappers are stripped, and headings indented inside JSX still count. Add `--json` for machine-readable output.

### 3. Write the alignment

A JSON list of rows, each row one decision:

```json
[
  {"title": "The opening pitch", "a": [0], "b": [0]},
  {"title": "The security story", "a": [], "b": [7, 8, 9],
   "rec": "Only B tells it. Keep it.", "pick": "b"},
  {"title": "Proof links", "a": [9], "b": [19],
   "rec": "A's links, B's framing.", "pick": "y", "mode": "f", "win": "b"}
]
```

| Field | Meaning |
|---|---|
| `title` | What the passage does, in your words. "The opening pitch" beats either file's heading, because the files named the same thing differently |
| `a`, `b` | Unit indexes from step 2. An empty list makes a **one-sided** row: copy that exists in one draft only and would vanish in a silent merge. These are often the most valuable rows on the page |
| `rec` | Optional. Your recommendation, shown above the columns |
| `pick` | Optional, with `rec`. The button you would press: `a`, `b`, `y` (Both), `r` (Rewrite), `n` (Cut) |
| `mode` | Optional, with `pick: "y"`. How to combine: `u` Union, `g` Graft, `f` Form plus facts, `s` Sequence |
| `win` | Optional. `a` or `b`, the side that leads a combined row |

Group several units into one row when they make one argument. Done when every unit of both files sits in some row: `build` prints `WARNING uncovered units` on stderr for any unit left out, and an uncovered unit is copy the human never sees. If you drop one on purpose, say so in your reply.

### 4. Build

```bash
python3 scripts/cherrypicker.py build A.md B.md --align align.json --out merge.html \
  --label-a "v1" --label-b "v2" --title "Case study merge"
```

Labels land on the picker buttons beside Both, Rewrite and Cut, so make them short, meaningful and distinct from those three: "v1" and "v2", or the two branch names. Done when it prints `wrote merge.html` with no uncovered-unit warning you did not intend.

### 5. Verify

```bash
python3 scripts/verify.py merge.html
```

Picks a row, reloads, and checks the pick survived with no page errors. Done when it exits 0 **and** you have looked at the screenshot it writes: a page that passes but reads badly still fails.

### 6. Deliver

Hand the human the HTML file, and persist it in whatever durable-artifact mechanism the harness offers, since they return to it over several sittings. When they revise the alignment, rebuild and update that same artifact.

To read it on a tablet over Tailscale, the human runs `scripts/serve-tailscale.sh merge.html` on a machine in their tailnet; it prints an HTTPS URL only that tailnet can reach. It refuses to start if the machine already has `tailscale serve` mounts, because it takes the root mount and turns 443 off on exit. From a cloud sandbox, write the files where the human can reach them and give them the command: nothing served from the sandbox reaches their devices.

## Reference

How the page stores picks, what each button does, and how to restyle it: [`references/page.md`](references/page.md).
