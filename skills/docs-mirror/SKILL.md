---
name: docs-mirror
description: "Mirror a documentation site or an RSS/Atom feed to local markdown in one command. Use when you need two or more pages from one site, when the user says scrape, mirror, or grab the docs, or when the target is a blog or feed. Not for a single page."
---

# docs-mirror

Two or more pages from one site, or any blog or feed, means run this once and read the files it writes.

```bash
python3 scripts/docs-mirror.py <url>
```

It prints the output directory on the last line. Read `README.md` there first (every page with title and size), then open only the files you need. Re-running is nearly free: each response is hashed and unchanged pages are skipped, so run it again rather than assuming a mirror is current.

| Flag | Use |
|---|---|
| `--out DIR` | where to write. Default `$DOCS_MIRROR_BASE/<host>-docs` (or `<host>-feed` in feed mode), falling back to `$XDG_DATA_HOME/docs-mirror`, then `~/.local/share/docs-mirror`. Set `DOCS_MIRROR_BASE` to a synced folder (Dropbox, Syncthing) so every machine and agent reads one copy |
| `--only TEXT` | only URLs (docs mode) or titles (feed mode) containing TEXT |
| `--jobs N` | parallel requests, default 8 |
| `--cap N` | max pages/entries, default 400 |
| `--feed` | treat the URL as a feed, or go find the site's feed |
| `--delay S` | seconds between requests, shared across all jobs. Default 0.3 |
| `--ignore-robots` | skip robots.txt. **Only for a site you own** |

## Blogs and feeds

Prefer a feed to a crawl for any blog: one request for the whole archive. A feed URL is auto-detected when it ends `.xml`, `.rss`, `.atom`, `/feed`, `/rss`, `/atom`, or the body starts as XML with `<rss` or `<feed>`.

```bash
docs-mirror https://blog.example.com/index.xml        # feed, auto-detected
docs-mirror https://blog.example.com --feed           # find the feed for me
```

`--feed` against a bare domain tries, in order: the page's `<link rel="alternate" type="application/rss+xml">` autodiscovery tag, then `/index.xml`, `/feed`, `/feed.xml`, `/rss.xml`, `/atom.xml`.

Most feeds carry the whole article (RSS `<content:encoded>` or `<description>`, Atom `<content>`), so a 20-post blog is normally one HTTP request, not 21. The script uses the feed body when it is substantial and fetches the page only when the feed shipped a summary; the README reports which happened per post. RSS 2.0 and Atom both handled. Feed mode writes `YYYY-MM-DD-title-slug.md` with frontmatter `title`, `date`, `author`, `url`, `feed` (metadata a crawl cannot recover).

Measured on a 20-post engineering blog, 2026-09-07: 38,728 words, one request.

## Scrape kindly

Both defaults hold unless the user says otherwise:

1. **robots.txt is fetched and honored.** A disallowed start URL exits 4 and stops. In docs mode, excluded URLs are dropped from the crawl and the count is printed. A short mirror is the answer, not a reason for `--ignore-robots`.
2. **Requests are spaced by `--delay`, shared across workers.** The clock is global, so `--jobs 12` cannot defeat it. Raise it for a small site.

## Exit codes

| Code | Meaning | Do this |
|---|---|---|
| 0 | Pages written | Read them |
| 1 | Every page failed | Check the URL and network, and report the failure rather than empty docs |
| 2 | Nothing discovered | Not a docs root or an empty feed. Try the parent path |
| 3 | Pages returned no prose | The site renders client-side and the content is not in the HTML. Use a headless browser or the site's API |
| 4 | robots.txt says no | Stop, unless the user owns the site |

The script never writes an empty file and calls it success, so an empty file is a bug to report, not an empty page.

## Why this exists

Fetching pages one at a time costs one model call per page, and the model re-emits every page. Server-rendered sites (Next.js, Mintlify, Docusaurus, VitePress, MkDocs) put the prose in the first HTTP response, so mirroring is cheap HTTP plus local parsing and no page passes through a model unless you read it. Measured on a 53-page product docs site, 2026-09-02: 0 failures, one command.

## Portability

One Python 3 file, standard library only: no pip, node, browser, or API key. Same on macOS and Linux. Tests cover the HTML-to-markdown conversion (tables, fenced code, entity handling, index rows) and run offline in under a second:

```bash
python3 scripts/test_docs_mirror.py
```
