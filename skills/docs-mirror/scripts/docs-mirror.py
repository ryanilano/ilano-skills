#!/usr/bin/env python3
"""
Mirror a documentation site OR an RSS/Atom feed to local markdown with plain
HTTP. No browser, no per-page model call.

Most modern docs sites — Next.js, Mintlify, Docusaurus, VitePress, MkDocs —
server-render their prose. The <article> element is fully populated in the
first HTTP response, before any JavaScript runs. Reading 50 pages is therefore
50 cheap HTTP requests plus local parsing, not 50 model calls.

Blogs are better still: most RSS/Atom feeds carry the FULL article body in
<content:encoded> or <description>. One request gets every post. This script
uses that body when it is substantial and only falls back to fetching the page
when the feed ships a summary.

    docs-mirror https://example.com/docs
    docs-mirror https://example.com/docs --out ~/docs/example
    docs-mirror https://example.com/docs --only reference --jobs 12
    docs-mirror https://blog.example.com/index.xml          # feed, auto-detected
    docs-mirror https://blog.example.com --feed             # find the feed for me

Discovery order: explicit feed, feed autodiscovery (with --feed), sitemap.xml,
then a same-prefix link crawl. Re-runs hash each response and skip unchanged
pages, so repeating is nearly free.

Scrape kindly. robots.txt is honoured by default and there is a per-request
delay. Use --ignore-robots only against a site you own.

Exits non-zero and says so loudly if pages come back without prose — that is
the signal the site really is client-rendered and needs a different tool. It
never writes an empty file and calls it a success.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")

# Below this many characters of extracted prose, a page is assumed to have
# failed rather than to be short.
MIN_PROSE = 200

# Politeness. A shared clock so --jobs parallelism cannot defeat the delay.
_throttle_lock = threading.Lock()
_next_slot = [0.0]
_DELAY = 0.0


def _wait_turn() -> None:
    if _DELAY <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        slot = max(now, _next_slot[0])
        _next_slot[0] = slot + _DELAY
    if slot > now:
        time.sleep(slot - now)


def get(url: str, timeout: int = 30) -> tuple[int, str, str]:
    """Returns (status, final_url, body). Never raises on HTTP errors."""
    _wait_turn()
    req = urllib.request.Request(
        url, headers={"User-Agent": UA,
                      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except (urllib.error.URLError, OSError) as e:
        return 0, url, f"__ERR__{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# Kindness: robots.txt
# --------------------------------------------------------------------------

def robots_for(url: str):
    """Returns a RobotFileParser, or None if robots.txt could not be read."""
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    status, _, body = get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=15)
    if status != 200 or body.startswith("__ERR__"):
        return None
    rp.parse(body.splitlines())
    return rp


# --------------------------------------------------------------------------
# Discovery: feeds
# --------------------------------------------------------------------------

FEED_HINT = re.compile(r"(\.xml|\.rss|\.atom|/feed/?$|/rss/?$|/atom/?$)", re.I)

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"


def looks_like_feed(url: str, body: str = "") -> bool:
    if FEED_HINT.search(url):
        return True
    head = body[:600].lstrip()
    return head.startswith("<?xml") and ("<rss" in body[:2000] or "<feed" in body[:2000])


def find_feed(base: str) -> str | None:
    """RSS autodiscovery: the <link rel=alternate> in the page head."""
    status, final, body = get(base)
    if status != 200 or body.startswith("__ERR__"):
        return None
    if looks_like_feed(final, body):
        return final
    for m in re.finditer(r"<link\b[^>]*>", body[:20000], re.I):
        tag = m.group(0)
        if not re.search(r'rel=["\']?alternate', tag, re.I):
            continue
        if not re.search(r'type=["\']?application/(rss|atom)\+xml', tag, re.I):
            continue
        href = re.search(r'href=["\']([^"\']+)', tag, re.I)
        if href:
            return urllib.parse.urljoin(final, href.group(1))
    for guess in ("/index.xml", "/feed", "/feed.xml", "/rss.xml", "/atom.xml"):
        p = urllib.parse.urlsplit(base)
        cand = f"{p.scheme}://{p.netloc}{guess}"
        st, fin, bd = get(cand)
        if st == 200 and looks_like_feed(fin, bd):
            return fin
    return None


def parse_feed(feed_url: str) -> list[dict]:
    """RSS 2.0 and Atom. Returns entries with whatever body the feed carries."""
    status, _, body = get(feed_url, timeout=60)
    if status != 200 or body.startswith("__ERR__"):
        return []
    try:
        root = ET.fromstring(body.encode("utf-8", "replace"))
    except ET.ParseError as e:
        print(f"  feed parse error: {e}", file=sys.stderr)
        return []

    out: list[dict] = []

    def text(el, *names):
        for n in names:
            v = el.findtext(n)
            if v and v.strip():
                return v.strip()
        return ""

    for it in root.findall(".//item"):                       # RSS 2.0
        c = it.find(CONTENT + "encoded")
        out.append({
            "url": text(it, "link", "guid"),
            "title": text(it, "title") or "untitled",
            "date": text(it, "pubDate"),
            "author": text(it, DC + "creator", "author"),
            "body": (c.text if c is not None and c.text else "") or text(it, "description"),
        })
    for en in root.findall(f".//{ATOM}entry"):               # Atom
        link = ""
        for L in en.findall(ATOM + "link"):
            if L.get("rel", "alternate") == "alternate":
                link = L.get("href", "")
                break
        c = en.find(ATOM + "content")
        s = en.find(ATOM + "summary")
        auth = en.find(ATOM + "author")
        out.append({
            "url": link,
            "title": text(en, ATOM + "title") or "untitled",
            "date": text(en, ATOM + "published", ATOM + "updated"),
            "author": (auth.findtext(ATOM + "name") or "").strip() if auth is not None else "",
            "body": (c.text if c is not None and c.text else "")
                    or (s.text if s is not None and s.text else ""),
        })
    return [e for e in out if e["url"] or e["body"]]


def norm_date(s: str) -> str:
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# Discovery: sitemap and crawl
# --------------------------------------------------------------------------

def from_sitemap(base: str, prefix: str) -> list[str]:
    root = f"{urllib.parse.urlsplit(base).scheme}://{urllib.parse.urlsplit(base).netloc}"
    urls: list[str] = []
    for candidate in ("/sitemap.xml", "/sitemap-0.xml", "/docs/sitemap.xml"):
        status, _, body = get(root + candidate)
        if status != 200 or "<loc>" not in body:
            continue
        for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", body):
            if loc.startswith(prefix):
                urls.append(loc)
        if urls:
            break
    return sorted(set(urls))


def crawl(start: str, prefix: str, cap: int = 400, rp=None) -> list[str]:
    """Breadth-first over same-prefix links. Used when there is no sitemap."""
    seen = {start}
    queue = [start]
    out: list[str] = []
    while queue and len(seen) < cap:
        url = queue.pop(0)
        if rp is not None and not rp.can_fetch(UA, url):
            continue
        status, final, body = get(url)
        if status != 200 or body.startswith("__ERR__"):
            continue
        out.append(final)
        for href in re.findall(r'href="([^"#?]+)', body):
            nxt = urllib.parse.urljoin(final, href)
            nxt = nxt.rstrip("/") or nxt
            if nxt.startswith(prefix) and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return sorted(set(out))


# --------------------------------------------------------------------------
# HTML -> markdown, scoped to the article body
# --------------------------------------------------------------------------

BLOCK_END = re.compile(
    r"</(p|div|section|h[1-6]|li|tr|pre|blockquote|table|thead|tbody)>", re.I)


def body_of(doc: str) -> str:
    for tag in ("article", "main"):
        m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", doc, re.S | re.I)
        if m:
            return m.group(1)
    m = re.search(r'<div\b[^>]*class="[^"]*\b(prose|markdown|content|doc)\b[^"]*"[^>]*>(.*)',
                  doc, re.S | re.I)
    return m.group(2) if m else doc


def to_markdown(frag: str) -> str:
    s = frag
    s = re.sub(r"(?is)<(script|style|svg|noscript|template|nav|footer|aside)"
               r"[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)

    # Fenced code first — tags inside it must not be rewritten. Blocks are
    # parked behind a placeholder so the whitespace normalisation at the end of
    # this function cannot eat their indentation, then restored verbatim.
    blocks: list[str] = []

    def fence_for(text: str, floor: int) -> str:
        """CommonMark: a fence must be longer than any backtick run inside."""
        return "`" * max([floor] + [len(r) + 1 for r in re.findall(r"`+", text)])

    def code_block(m: re.Match) -> str:
        inner = html.unescape(re.sub(r"(?s)<[^>]+>", "", m.group(1))).strip("\n")
        fence = fence_for(inner, 3)
        blocks.append(f"{fence}\n{inner}\n{fence}")
        return f"\n\n\x00CB{len(blocks) - 1}\x00\n\n"
    s = re.sub(r"(?is)<pre\b[^>]*>(.*?)</pre>", code_block, s)

    def span(text: str, raw: str | None = None) -> str:
        """A code span, delimited and padded so its own backticks survive."""
        tick = fence_for(text, 1)
        pad = " " if text.startswith("`") or text.endswith("`") else ""
        return f"{tick}{pad}{raw if raw is not None else text}{pad}{tick}"

    def code_span(m: re.Match) -> str:
        raw = re.sub(r"(?s)<[^>]+>", "", m.group(1)).strip()
        if not raw:
            return ""
        # Entities become real characters further down, so the delimiter is
        # measured against what the reader will finally see, not the source.
        return span(html.unescape(raw), raw)
    s = re.sub(r"(?is)<code\b[^>]*>(.*?)</code>", code_span, s)
    s = re.sub(r'(?is)<img\b[^>]*?alt="([^"]*)"[^>]*?src="([^"]*)"[^>]*>',
               lambda m: f"\n\n![{m.group(1)}]({m.group(2)})\n\n", s)
    s = re.sub(r'(?is)<img\b[^>]*?src="([^"]*)"[^>]*>',
               lambda m: f"\n\n![]({m.group(1)})\n\n", s)
    s = re.sub(r'(?is)<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
               lambda m: f"[{re.sub(r'(?s)<[^>]+>', '', m.group(2)).strip()}]({m.group(1)})", s)
    s = re.sub(r"(?is)<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", s)
    s = re.sub(r"(?is)<(em|i)\b[^>]*>(.*?)</\1>", r"*\2*", s)

    for n in range(1, 7):
        s = re.sub(rf"(?is)<h{n}\b[^>]*>(.*?)</h{n}>",
                   lambda m, n=n: "\n\n" + "#" * n + " "
                                  + re.sub(r"(?s)<[^>]+>", "", m.group(1)).strip() + "\n\n", s)

    s = re.sub(r"(?i)<li\b[^>]*>", "\n- ", s)
    # Tables. A grid of pipes with no |---| delimiter row is not a table in
    # CommonMark, it is one paragraph of pipes, so whole <table> elements are
    # rebuilt here: header, delimiter, rows, with any | inside a cell escaped.
    def cell_text(x: str) -> str:
        x = re.sub(r"(?i)<br\s*/?>", " ", x)
        x = re.sub(r"(?s)<[^>]+>", " ", x)
        # A code block cannot live in a table row; flatten it to a code span.
        x = re.sub(r"\x00CB(\d+)\x00",
                   lambda m: flatten(blocks[int(m.group(1))]), x)
        x = x.replace("|", "\\|")
        x = re.sub(r"(?i)&(#0*124|#x0*7c|verbar|vert);", lambda m: "\\|", x)
        return re.sub(r"\s+", " ", x).strip()

    def flatten(block: str) -> str:
        body = " ".join("\n".join(block.splitlines()[1:-1]).split())
        # Re-escaped so the html.unescape below leaves it exactly as it is.
        return span(body, html.escape(body, quote=False)) if body else ""

    def table_block(m: re.Match) -> str:
        header: list[str] | None = None
        rows: list[list[str]] = []
        for i, chunk in enumerate(re.split(r"(?is)<tr\b[^>]*>", m.group(1))[1:]):
            raw = re.split(r"(?i)</tr>", chunk)[0]
            cells = [cell_text(re.split(r"(?i)</t[hd]>", c)[0])
                     for c in re.split(r"(?is)<t[hd]\b[^>]*>", raw)[1:]]
            if not cells:
                continue
            if i == 0 and re.search(r"(?is)<th\b", raw):
                header = cells
            else:
                rows.append(cells)
        if header is None and not rows:
            return "\n\n"
        width = max(len(r) for r in ([header] if header else []) + rows)
        if header is None:                       # GFM has no headerless table
            header = [""] * width
        def row(cells: list[str]) -> str:
            return "| " + " | ".join((cells + [""] * width)[:width]) + " |"
        return ("\n\n" + "\n".join([row(header), "|" + "---|" * width]
                                   + [row(r) for r in rows]) + "\n\n")
    s = re.sub(r"(?is)<table\b[^>]*>(.*?)</table>", table_block, s)
    # Anything left is a cell outside a table; keep its text visible.
    s = re.sub(r"(?i)<t[hd]\b[^>]*>", " | ", s)
    s = re.sub(r"(?i)</tr>", " |\n", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)

    s = BLOCK_END.sub("\n", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"\x00CB(\d+)\x00", lambda m: blocks[int(m.group(1))], s)
    return s.strip() + "\n"


def title_of(doc: str, url: str) -> str:
    m = re.search(r"<title>(.*?)</title>", doc, re.S | re.I)
    if m:
        t = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        for sep in (" | ", " — ", " - ", " · "):
            if sep in t:
                t = t.split(sep)[0].strip()
        if t:
            return t
    return urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or "index"


def slug(url: str, prefix: str) -> str:
    p = urllib.parse.urlsplit(url).path.rstrip("/")
    base = urllib.parse.urlsplit(prefix).path.rstrip("/")
    rel = p[len(base):].strip("/") if p.startswith(base) else p.strip("/")
    return (rel.replace("/", "__") or "index")


def text_slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:70].strip("-") or "untitled"


def yaml_q(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', "'") + '"'


def md_cell(s: str) -> str:
    """A pipe inside a table cell has to be escaped or it ends the cell."""
    return s.replace("|", "\\|")


# --------------------------------------------------------------------------
# Feed mirroring
# --------------------------------------------------------------------------

def mirror_feed(feed_url: str, out: Path, jobs: int, only: str | None,
                cap: int, rp) -> int:
    entries = parse_feed(feed_url)
    if only:
        entries = [e for e in entries if only.lower() in (e["title"] + e["url"]).lower()]
    if not entries:
        print("no entries in feed", file=sys.stderr)
        return 2
    entries = entries[:cap]
    print(f"{len(entries)} entries from feed {feed_url}", file=sys.stderr)

    out.mkdir(parents=True, exist_ok=True)
    state_file = out / ".hashes.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}

    # Entries whose feed body is only a summary need the real page fetched.
    def resolve(e: dict) -> dict:
        raw = e["body"] or ""
        md = to_markdown(raw) if raw else ""
        if len(md) < MIN_PROSE and e["url"]:
            if rp is None or rp.can_fetch(UA, e["url"]):
                st, fin, doc = get(e["url"])
                if st == 200 and not doc.startswith("__ERR__"):
                    md = to_markdown(body_of(doc))
                    e["fetched"] = True
        e["md"] = md
        return e

    written = skipped = thin = 0
    index: list[tuple[str, str, str, str, int]] = []
    fetched = 0

    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for e in ex.map(resolve, entries):
            date = norm_date(e["date"])
            name = f"{date + '-' if date else ''}{text_slug(e['title'])}.md"
            md = e["md"]
            if e.get("fetched"):
                fetched += 1
            if len(md) < MIN_PROSE:
                print(f"  THIN  {len(md):>5}c  {e['url'] or e['title']}", file=sys.stderr)
                thin += 1
                continue
            h = hashlib.sha256(md.encode()).hexdigest()[:16]
            path = out / name
            key = e["url"] or e["title"]
            if state.get(key) == h and path.exists():
                skipped += 1
                index.append((date, e["title"], name, e["url"], len(md.split())))
                continue
            fm = [
                "---",
                f"title: {yaml_q(e['title'])}",
                f"date: {date}",
                "type: reference",
                "source: mirror",
                f"author: {yaml_q(e['author'])}",
                f"url: {e['url']}",
                f"feed: {feed_url}",
                "---",
                "",
                f"# {e['title']}",
                "",
                (f"{e['author']} — " if e["author"] else "") + (date or "undated") + "  ",
                f"Source: <{e['url']}>" if e["url"] else "",
                "",
                "---",
                "",
                md,
            ]
            path.write_text("\n".join(fm))
            state[key] = h
            written += 1
            index.append((date, e["title"], name, e["url"], len(md.split())))
            print(f"  ok    {len(md):>6,}c  {e['title'][:60]}")

    state_file.write_text(json.dumps(state, indent=2))

    index.sort(reverse=True)
    host = urllib.parse.urlsplit(feed_url).netloc
    lines = [f"# {host} — feed mirror", "",
             f"{len(index)} posts from <{feed_url}>.",
             f"{len(index) - fetched} came whole from the feed; "
             f"{fetched} needed the page fetched because the feed shipped a summary.",
             "", "| Date | Post | Words |", "|---|---|---|"]
    for date, title, name, url, words in index:
        lines.append(f"| {date} | [{md_cell(title)}]({name}) | {words:,} |")
    (out / "README.md").write_text("\n".join(lines) + "\n")

    print(f"\n{written} written, {skipped} unchanged, {thin} thin, "
          f"{fetched} page-fetched -> {out}/", file=sys.stderr)
    if thin and thin >= max(3, len(entries) // 2):
        print("\nMOST ENTRIES HAD NO PROSE in the feed and no fetchable page.",
              file=sys.stderr)
        return 3
    return 0 if written or skipped else 1


def main() -> int:
    global _DELAY
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="docs root, site root, or feed URL")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--only", default=None, help="only URLs/titles containing this")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--cap", type=int, default=400)
    ap.add_argument("--feed", action="store_true",
                    help="treat the URL as a feed, or find the site's feed")
    ap.add_argument("--delay", type=float, default=0.3,
                    help="seconds between requests, shared across jobs (default 0.3)")
    ap.add_argument("--ignore-robots", action="store_true",
                    help="skip robots.txt. Only for a site you own")
    a = ap.parse_args()

    _DELAY = max(0.0, a.delay)
    start = a.url.rstrip("/")
    prefix = start

    rp = None
    if not a.ignore_robots:
        rp = robots_for(start)
        if rp is None:
            print("robots.txt unreadable; proceeding politely", file=sys.stderr)
        elif not rp.can_fetch(UA, start):
            print(f"robots.txt disallows {start} for this user-agent. Stopping.\n"
                  "Use --ignore-robots only if you own this site.", file=sys.stderr)
            return 4

    # ---- feed path -------------------------------------------------------
    feed_url = None
    if a.feed or looks_like_feed(start):
        feed_url = start if looks_like_feed(start) else find_feed(start)
        if not feed_url:
            print("no feed found; falling back to sitemap/crawl", file=sys.stderr)

    if feed_url:
        out = a.out or Path(urllib.parse.urlsplit(feed_url).netloc.replace(".", "-") + "-feed")
        print(f"mirroring feed {feed_url} …", file=sys.stderr)
        return mirror_feed(feed_url, out, a.jobs, a.only, a.cap, rp)

    # ---- docs path -------------------------------------------------------
    out = a.out or Path(urllib.parse.urlsplit(start).netloc.replace(".", "-") + "-docs")
    print(f"discovering under {prefix} …", file=sys.stderr)
    urls = from_sitemap(start, prefix)
    how = "sitemap"
    if not urls:
        urls = crawl(start, prefix, a.cap, rp)
        how = "crawl"
    if a.only:
        urls = [u for u in urls if a.only in u]
    if rp is not None:
        before = len(urls)
        urls = [u for u in urls if rp.can_fetch(UA, u)]
        if before != len(urls):
            print(f"robots.txt excluded {before - len(urls)} URLs", file=sys.stderr)
    if not urls:
        print("no pages discovered", file=sys.stderr)
        return 2
    print(f"{len(urls)} pages via {how}", file=sys.stderr)

    out.mkdir(parents=True, exist_ok=True)
    state_file = out / ".hashes.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}

    written = skipped = failed = thin = 0
    index: list[tuple[str, str, int]] = []

    def one(url: str):
        status, final, doc = get(url)
        return url, status, final, doc

    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for url, status, final, doc in ex.map(one, urls):
            name = slug(url, prefix)
            if status != 200 or doc.startswith("__ERR__"):
                print(f"  FAIL  {status:>3}  {url}", file=sys.stderr)
                failed += 1
                continue

            h = hashlib.sha256(doc.encode()).hexdigest()[:16]
            path = out / f"{name}.md"
            if state.get(url) == h and path.exists():
                skipped += 1
                index.append((url, title_of(doc, url), path.stat().st_size))
                continue

            md = to_markdown(body_of(doc))
            if len(md) < MIN_PROSE:
                print(f"  THIN  {len(md):>5}c  {url}", file=sys.stderr)
                thin += 1
                continue

            title = title_of(doc, url)
            path.write_text(f"---\nsource: {url}\ntitle: {yaml_q(title)}\n---\n\n{md}")
            state[url] = h
            written += 1
            index.append((url, title, path.stat().st_size))
            print(f"  ok    {len(md):>6,}c  {url}")

    state_file.write_text(json.dumps(state, indent=2))

    lines = [f"# {urllib.parse.urlsplit(start).netloc} docs", "",
             f"Mirrored from {prefix} — {len(index)} pages, discovered by {how}.",
             "", "| page | title | bytes |", "|---|---|---|"]
    for url, title, size in sorted(index):
        lines.append(f"| [{slug(url, prefix)}]({slug(url, prefix)}.md) "
                     f"| {md_cell(title)} | {size:,} |")
    (out / "README.md").write_text("\n".join(lines) + "\n")

    print(f"\n{written} written, {skipped} unchanged, {thin} thin, "
          f"{failed} failed -> {out}/", file=sys.stderr)

    # Thin pages are the signal that the site is genuinely client-rendered.
    # Say so rather than leaving a directory of near-empty files.
    if thin and thin >= max(3, len(urls) // 4):
        print("\nMOST PAGES CAME BACK WITHOUT PROSE. This site renders client-side; "
              "curl will not get the content. Use a headless browser or the "
              "site's own API instead.", file=sys.stderr)
        return 3
    return 1 if failed and not written else 0


if __name__ == "__main__":
    raise SystemExit(main())
