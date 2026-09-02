# Testing claim-anchor

**A green run proves nothing until the check has been shown able to fail.** Run
the control before trusting a clean pass, and always after touching `score()` in
`verify_links.py`.

## Building the control

Point `$CORPUS` at any docs site you can reach, then write five links against
it. Four must fail, each on a different mechanism.

```markdown
The build ships fonts at [47.3 KB]($CORPUS/performance/#the-scoreboard).
The build ships fonts at [980.2 KB]($CORPUS/performance/#the-scoreboard).
A [first skeleton]($CORPUS/why-the-port/#an-id-that-does-not-exist) landed.
The [deploy guide]($CORPUS/no-such-page/) says so.
Auth used [scrypt from the start]($CORPUS/seo/#_top).
```

Line 1 uses a real number the target section states. Line 2 keeps the same real
URL and fragment and swaps in a number the target never mentions. Line 3 keeps a
real page and invents the fragment. Line 4 is a dead URL. Line 5 is a real page,
real anchor, and a claim that section has nothing to do with.

Expected, in order: `strong` with `anchor=True`, then `none` with `anchor=True`,
then `unknown` with `anchor=False`, then a `404`, then `none` with
`anchor=True`. Exit code 1.

## The regression this control caught

**Line 2 originally scored `strong`, which is exactly the failure the tool
exists to prevent.**

`score()` pooled the numbers found in the anchor text with the numbers found in
the surrounding sentence window. The window reaches 220 characters either side,
so on adjacent lines it pulled the real number in from the line above. The
fabricated number then satisfied "at least one number in the claim appears in
the target" and was reported as strongly supported.

The fix separates them. Every number inside the anchor text must appear in the
target section, or the result is `none` no matter how well the words match.
Numbers from the surrounding sentence are supporting signal only. If `score()`
is ever rewritten, build the control again before believing it.

## Testing map_corpus.py

Run it against a corpus that publishes a sitemap and confirm the anchors come
back with usable excerpts rather than heading text alone.

```bash
python3 scripts/map_corpus.py "$CORPUS" --include /docs/ > corpus.json
```

`discovered_via` should name the sitemap file it found. Pick a page you know
carries specific figures and confirm those figures appear in that section's
excerpt. If excerpts come back empty, the theme is rendering headings without
`id` attributes, and the corpus cannot be deep-linked at all. That is a finding
to report, not a bug to work around.

The crawl fallback only fires when no sitemap is found. It is breadth-one from
the root page and misses anything not linked there, which is why it reports
`discovered_via: crawl`. Say so when reporting coverage.

## Caps are reported, never silent

`map_corpus.py` stops at `--max-pages` (default 60) and prints what it dropped
to stderr. If that line appears, the corpus was not fully mapped, and any
"nothing in the corpus covers this" conclusion is scoped to the pages that were
actually mapped. Say which.
