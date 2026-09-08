---
name: docs-mirror
description: "Mirror an entire documentation site OR an RSS/Atom feed to local markdown in one command. Use whenever you need more than two pages from the same site, or the user says scrape, pull, mirror, grab the docs, or names a blog or feed. Discovers pages by feed, sitemap, or link crawl, fetches them with plain HTTP, honours robots.txt, and writes one markdown file per page plus an index. Do NOT use for a single page, or for a site already mirrored and unchanged."
---

# docs-mirror

Run this. Do not fetch pages one at a time.

```bash
python3 scripts/docs-mirror.py <url>
```

Then read the files it wrote. It prints the output directory on the last line.

| Flag | Use |
|---|---|
| `--out DIR` | where to write. Default `<host>-docs`, or `<host>-feed` in feed mode |
| `--only TEXT` | only URLs (docs mode) or titles (feed mode) containing TEXT |
| `--jobs N` | parallel requests, default 8 |
| `--cap N` | max pages/entries, default 400 |
| `--feed` | treat the URL as a feed, or go find the site's feed |
| `--delay S` | seconds between requests, shared across all jobs. Default 0.3 |
| `--ignore-robots` | skip robots.txt. **Only for a site you own** |

## Blogs and feeds

A feed URL is detected automatically — anything ending `.xml`, `.rss`, `.atom`,
`/feed`, `/rss`, `/atom`, or any body that starts as XML with `<rss` or `<feed>`.

```bash
docs-mirror https://blog.example.com/index.xml        # feed, auto-detected
docs-mirror https://blog.example.com --feed           # find the feed for me
```

With `--feed` against a bare domain it tries, in order: the page's
`<link rel="alternate" type="application/rss+xml">` autodiscovery tag, then
`/index.xml`, `/feed`, `/feed.xml`, `/rss.xml`, `/atom.xml`.

**Most feeds carry the whole article.** RSS `<content:encoded>` or
`<description>`, Atom `<content>`. So a 20-post blog is normally **one HTTP
request**, not 21. The script uses the feed body when it is substantial and
only fetches the page when the feed shipped a summary. The README says which
happened:

> 20 came whole from the feed; 0 needed the page fetched.

Measured on a 20-post engineering blog, 2026-09-07: 38,728 words, one request.

Feed mode writes `YYYY-MM-DD-title-slug.md` with real frontmatter — `title`,
`date`, `author`, `url`, `feed` — because feeds carry metadata a crawl cannot
recover. RSS 2.0 and Atom are both handled.

## Scrape kindly

This hits someone else's server. Two defaults enforce that, and neither is
optional unless you say so:

1. **robots.txt is fetched and honoured.** A disallowed start URL exits 4 and
   stops. In docs mode, excluded URLs are dropped from the crawl and the count
   is printed. `--ignore-robots` exists for sites you own; do not reach for it
   because a mirror came back short.
2. **Requests are spaced by `--delay`, shared across workers.** The clock is
   global, so `--jobs 12` cannot defeat it. Default 0.3s. Raise it for a small
   site; a personal blog does not need eight parallel connections.

A feed is the kindest possible scrape: one request for the whole archive. Reach
for `--feed` before a crawl whenever the target is a blog.

## Why this exists

Fetching pages one at a time costs one model call per page. Fifty pages is
fifty calls, and the model reads and re-emits every page it fetches. That is
the expensive way to obtain text that is already public and already plain.

Server-rendered sites put the prose in the first HTTP response. Next.js,
Mintlify, Docusaurus, VitePress, and MkDocs all populate `<article>` before any
JavaScript runs. So fifty pages is fifty cheap HTTP requests and local parsing,
and no page passes through a model unless you choose to read it.

Measured on a 53-page product docs site, 2026-09-02: 0 failures, one command.

## Rules

1. **Two or more pages from one site means run this.** Do not decide page by
   page.
2. **A blog or a feed means run this with `--feed`.** One request beats twenty.
3. **Read the output directory, not the network.** After it runs, open the
   files. Do not fetch the same pages again.
4. **Read `README.md` in the output directory first.** It lists every page with
   its title and size. Open only the files you need.
5. **Re-running is nearly free.** Each response is hashed; unchanged pages are
   skipped. Run it again rather than assuming a mirror is current.
6. **Never report an empty file as an empty page.** See exit codes below.

## Exit codes

| Code | Meaning | Do this |
|---|---|---|
| 0 | Pages written | Read them |
| 1 | Every page failed | Check the URL and network. Do not report the docs as empty |
| 2 | Nothing discovered | Not a docs root or an empty feed. Try the parent path |
| 3 | Pages returned no prose | The site renders client-side. curl cannot get it. Use a headless browser or the site's API. Do not retry this tool |
| 4 | robots.txt says no | Stop. Do not work around it unless the user owns the site |

Exit 3 is the one that matters. It means the content is genuinely not in the
HTML, which is a different problem, not a failure of this script. It never
writes an empty file and calls it a success.

## Portability

One Python 3 file, standard library only. No pip install, no node, no browser,
no API key. It runs the same on macOS and Linux, and the instructions above are
plain commands so they read the same to any model on any endpoint.

`scripts/test_docs_mirror.py` covers the HTML-to-markdown conversion (tables,
fenced code, entity handling, index rows) and runs offline in under a second:

```bash
python3 scripts/test_docs_mirror.py
```
