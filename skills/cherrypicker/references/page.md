# The generated page

One self-contained HTML file, no dependencies. Everything below is in `scripts/cherrypicker.py`.

## Choices per row

| Button | Pick | Meaning |
|---|---|---|
| Label A | `a` | Draft A's copy wins |
| Label B | `b` | Draft B's copy wins |
| Both | `y` | Combine them; opens a mode chooser |
| Rewrite | `r` | Neither survives as written |
| Cut | `n` | The row leaves the page |

Both has four modes: **Union** (all of both, then the human edits), **Graft** (a piece of one side set into the other), **Form plus facts** (one side's shape, the other's facts), **Sequence** (both, in an order the human picks). Clicking an active choice again clears it. Every row also has a free-text note.

## Persistence

- **Picks** live in the URL hash as `#p=...`, rewritten on every click. Artifact sandboxes block `localStorage`, so the hash is the storage and doubles as a resume link: bookmarked on a phone, it reopens where it was left.
- **Notes** are too long for a hash. Save notes writes a `<page>.notes.json` sidecar (through the File System Access API where the browser has it, as a download elsewhere); Load notes reads it back. The page warns before closing with unsaved notes.

## Export

Export opens a dialog with markdown to copy: the decisions grouped by choice, each with its note, then a **source text** worklist of every row that needs writing rather than choosing (Union, Graft, Form plus facts, Sequence, Rewrite), with the full text of both sides and the leading side in bold. The resume link closes the export.

## Look

- Light theme is forced with `color-scheme: light`, so a device in dark mode does not invert it.
- The layout drops to a single column below 820px.
- A band at the top counts A wins, B wins and rows still undecided.

To restyle, edit the `_CSS` string in `scripts/cherrypicker.py`. When the human has a house style, ask them for the exact CSS rule rather than guessing it.
