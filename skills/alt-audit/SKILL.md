---
name: alt-audit
description: Audit a webpage's images and videos for accessibility and write final alt text. Use when the user asks for alt text for a webpage, an alt-text audit, a second opinion on existing alt attributes, aria-label suggestions for videos, or invokes "alt-audit <url>". Supports flags for media filtering (--images-only, --videos-only), site chrome (--include-chrome), and independent review mode (--fresh).
---

# alt-audit

Audit a webpage's media and deliver final alt text plus verdicts in one pass.

## Invocation

```
alt-audit <url> [--images-only] [--videos-only] [--include-chrome] [--fresh]
```

| Flag | Effect |
|------|--------|
| (none) | Audit content images + videos. Skip site chrome (header, nav, footer, sidebar, cookie banners). |
| `--images-only` / `--videos-only` | Restrict to one media type. |
| `--include-chrome` | Also audit chrome media: logos, icons, badges, theme toggles. Default skips them — chrome is usually a shared template and should be audited once per template, not per page. |
| `--fresh` | Write alt text from visual inspection only, BEFORE reading existing alt attributes (independent second opinion). Default mode reads existing alt first and merges. |

## Workflow

1. Run `scripts/extract_media.sh <url> <workspace-dir>` (e.g. `imgs-audit/`). It saves the raw HTML, lists every `<img>`/`<video>` tag with attributes into `media-tags.txt`, and downloads all media files.
2. Filter scope: without `--include-chrome`, drop media referenced in header/nav/footer regions of the HTML and tiny tracking/badge images. Apply `--images-only`/`--videos-only` if given.
3. View every remaining file with ReadMediaFile. Read `.webp` and `.mp4` DIRECTLY — no conversion or frame extraction needed. Do not rely on text-only page fetches; they strip image URLs and all visual content.
4. In `--fresh` mode, write alt text now, then read existing `alt=` attributes from `media-tags.txt`. In default mode, read them first.
5. Write final alt text per item (see Writing rules), then verdicts.

## Writing rules

- Assume media is non-functional (informational/decorative) unless it is wrapped in a link or button; functional media gets alt describing the action, not the image.
- Merge: keep what works in existing alt, fix what is wrong, add visible specifics (brands, devices, legible headline text). Do not invent details that are not visible.
- Replace outright when existing alt duplicates the page H1/title verbatim or describes the image's role instead of its content.
- Decorative candidates (visuals fully explained by adjacent text): recommend `alt=""`.
- Videos: there is no `alt` attribute on `<video>`. Suggest `aria-label` on the element. Check `media-tags.txt` for existing aria-labels — they are often present on nav/buttons but missing on videos. Flag every video with no accessible name as a **Gap**. Muted looping ambient videos also warrant a `prefers-reduced-motion` note.

## Output

Single markdown document inside ONE four-backtick outer fence tagged `markdown`; inner code fences use triple backticks. No text before or after the block, no YAML frontmatter. Structure:

1. `# Alt Text — <page title>` with source URL and scope line.
2. `## Images` — one `###` per image: filename in inline code, then final alt text in a blockquote.
3. `## Videos` — same, with ready-to-paste `<video aria-label="..." ...>` snippets in triple-backtick `html` fences.
4. `## Conclusion` — findings (factual errors found, H1 duplication, video gaps), then a verdict table:

| Verdict | Meaning |
|---------|---------|
| Keep | Existing alt is accurate and complete |
| Refine | Existing kept as base; corrections or specifics added |
| Replace | Existing is wrong, H1-duplicated, or role-not-content |
| Gap | No accessible name exists (typical for videos) |

Number every media item sequentially across images and videos so the table maps 1:1 to the sections above.
