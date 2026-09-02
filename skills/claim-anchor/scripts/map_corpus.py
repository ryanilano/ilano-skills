#!/usr/bin/env python3
"""Map a documentation corpus to every linkable heading anchor it exposes.

Given a site root, discovers pages via sitemap (falling back to a crawl of the
root page's same-origin links), then fetches each page and emits its real
heading ids together with a text excerpt of the section under each one.

The excerpt is the point. A heading id proves an anchor exists; the excerpt is
what lets the caller decide whether that section actually states the claim
being linked. Verifying only that a URL returns 200 is how decorative links
survive review.

Status to stderr, JSON to stdout:

  {"root": ..., "discovered_via": "sitemap|crawl", "pages": [
     {"url": ..., "title": ..., "anchors": [
        {"id": ..., "level": 2, "heading": ..., "excerpt": "first N chars under it"}
     ]}
  ]}

Usage:
  map_corpus.py <site-root-url> [--max-pages N] [--excerpt N] [--include SUBSTR]
"""
import argparse
import json
import re
import sys
import html as htmllib
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

assert sys.version_info >= (3, 9), "python 3.9+ required"

UA = "claim-anchor/1.0"


def fetch(url, timeout=20):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")


def strip_noise(doc):
    """Drop script/style/nav/header/footer so excerpts are prose, not chrome."""
    doc = re.sub(r"(?is)<(script|style|template)[^>]*>.*?</\1>", " ", doc)
    doc = re.sub(r"(?is)<(nav|header|footer)[^>]*>.*?</\1>", " ", doc)
    return doc


def text_of(fragment):
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))
    # Starlight and several other doc themes inject a visually-hidden
    # "Section titled ..." span next to every heading. It is not prose and it
    # doubles every heading in the excerpt.
    t = re.sub(r"Section titled\s*[“\"'].*?[”\"']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def discover(root, max_pages, include):
    """Sitemap first, crawl second. Report which one was used."""
    origin = f"{urlparse(root).scheme}://{urlparse(root).netloc}"
    urls, via = [], None

    for name in ("sitemap-0.xml", "sitemap.xml", "sitemap-index.xml"):
        try:
            body = fetch(urljoin(root.rstrip("/") + "/", name))
        except (URLError, HTTPError):
            continue
        locs = re.findall(r"<loc>([^<]+)</loc>", body)
        nested = [u for u in locs if u.endswith(".xml")]
        for n in nested[:20]:
            try:
                locs += re.findall(r"<loc>([^<]+)</loc>", fetch(n))
            except (URLError, HTTPError):
                pass
        page_urls = [u for u in locs if not u.endswith(".xml")]
        if page_urls:
            urls, via = page_urls, f"sitemap ({name})"
            break

    if not urls:
        try:
            body = fetch(root)
        except (URLError, HTTPError) as e:
            print(f"cannot reach {root}: {e}", file=sys.stderr)
            return [], "unreachable"
        hrefs = re.findall(r'href="([^"#]+)"', body)
        seen = {}
        for h in hrefs:
            u = urljoin(root, h)
            if u.startswith(origin) and not re.search(r"\.(css|js|png|jpe?g|svg|webp|xml|ico)$", u):
                seen[u] = True
        urls, via = list(seen), "crawl (no sitemap found)"

    urls = sorted({u for u in urls if not include or include in u})
    if len(urls) > max_pages:
        print(f"corpus has {len(urls)} pages, capping at {max_pages}. "
              f"Narrow with --include or raise --max-pages; the rest are NOT mapped.",
              file=sys.stderr)
        urls = urls[:max_pages]
    return urls, via


def anchors_for(doc, excerpt_len):
    """Every heading with an id, plus the text that follows it up to the next heading."""
    body = strip_noise(doc)
    out = []
    heads = list(re.finditer(r'<h([1-6])[^>]*\bid="([^"]+)"[^>]*>(.*?)</h\1>', body, re.S))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        out.append({
            "id": m.group(2),
            "level": int(m.group(1)),
            "heading": text_of(m.group(3)),
            "excerpt": text_of(body[m.end():end])[:excerpt_len],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--excerpt", type=int, default=700)
    ap.add_argument("--include", default="", help="only map URLs containing this substring")
    a = ap.parse_args()

    urls, via = discover(a.root, a.max_pages, a.include)
    print(f"discovered {len(urls)} pages via {via}", file=sys.stderr)

    pages = []
    for u in urls:
        try:
            doc = fetch(u)
        except (URLError, HTTPError) as e:
            print(f"  skip {u}: {e}", file=sys.stderr)
            continue
        title = re.search(r"(?is)<title[^>]*>(.*?)</title>", doc)
        pages.append({
            "url": u,
            "title": text_of(title.group(1)) if title else "",
            "anchors": anchors_for(doc, a.excerpt),
        })
        print(f"  {len(pages[-1]['anchors']):3d} anchors  {u}", file=sys.stderr)

    json.dump({"root": a.root, "discovered_via": via, "pages": pages}, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
