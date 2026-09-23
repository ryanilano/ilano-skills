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

Everything **hot-saves**: no button to press.

- **URL hash.** Picks as `#p=...`, rewritten on every click; notes as `&n=` (base64url JSON), rewritten 400ms after typing stops. Artifact sandboxes block `localStorage`, so the hash is the storage that always works, and it doubles as a resume link: bookmarked on a phone, it reopens with picks and notes.
- **localStorage**, keyed by the page path, mirrors each save where the browser allows it. Opening the bare URL with no hash restores from it; a hash, when present, wins.
- **File.** Save notes writes a `<page>.notes.json` sidecar (through the File System Access API where the browser has it, as a download elsewhere). Once a file is chosen, every hot save rewrites it too. Load notes reads one back.

## Export

Export opens a dialog with markdown to copy: the decisions grouped by choice, each with its note, then a **source text** worklist of every row that needs writing rather than choosing (Union, Graft, Form plus facts, Sequence, Rewrite), with the full text of both sides and the leading side in bold. The resume link closes the export.

## Look

- **Light and dark themes.** It follows the system by default. The Theme button cycles Auto, Light and Dark, sets `data-theme` on `<html>`, and remembers the choice in localStorage. All colours are CSS custom properties defined once per theme at the top of `_CSS`; every text pair meets WCAG AA (4.5:1) in both.
- **Semantic HTML.** Each row is a `<section>` labelled by its `<h2>`; each side is an `<article>` with its draft's name and state ("Chosen", "Not chosen", "Combined", "To rewrite", "Cut") shown as text, never by dimming or colour alone; headings inside the copy are demoted to start at `<h4>`, so the outline stays h1, row, unit. Combine modes are a `<fieldset>` with a `<legend>`; the note has a real `<label>`; choice buttons carry `aria-pressed` and switch from outlined to filled when chosen. Progress is a native `<progress>` with an `<output>` count, and a skip link jumps to the sections.
- **Keyboard and screen readers.** Every control is a real button in a logical tab order, Load notes included. Next undecided moves focus to that row's heading. A polite live region announces file saves, loads, copies and resets; hot saves stay silent so typing is not narrated. Focus stays where it is when a choice is made.
- **Motion and contrast modes.** `prefers-reduced-motion` turns off transitions and smooth scrolling; in forced-colours mode the chosen button gets a system `Highlight` outline. `scroll-padding-top` keeps a focused control clear of the sticky bar.
- **Checked** with axe-core (WCAG 2.2 AA plus best practice) in both themes with every choice type active: no violations.
- **Sizes in rem**, so text zoom scales the layout. It drops to one column below 51.25em (820px).
- A band at the top counts A wins, B wins and rows still undecided.

To restyle, edit the custom properties at the top of `_CSS` in `scripts/cherrypicker.py`. When the human has a house style, ask them for the exact CSS rule rather than guessing it.
