#!/usr/bin/env python3
"""Verify claim-anchored links three ways, not one.

For every link found in a source file (markdown/MDX) or fetched page:

  1. the URL resolves                      -> status
  2. the #fragment matches a real id       -> anchor_ok
  3. the target section states the claim   -> support

Check 3 is the one that matters and the one a link checker never does. A URL
that returns 200 proves a page exists. It does not prove the page says what the
sentence claims. Support is scored by how much of the link's own anchor text,
and any numbers in the sentence around it, appear in the target section.

The score is a triage signal, not a verdict. `weak` means read it yourself.

Status to stderr, JSON to stdout. Exits 1 if any link is dead, any fragment is
missing, or --strict is set and any link scores `none`.

Usage:
  verify_links.py <file.md|url> [--host SUBSTR] [--strict] [--context N]
"""
import argparse
import json
import re
import sys
import html as htmllib
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

assert sys.version_info >= (3, 9), "python 3.9+ required"

UA = "claim-anchor/1.0"
MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
HTML_LINK = re.compile(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.S)
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "is", "are",
    "was", "were", "it", "its", "that", "this", "for", "with", "as", "by",
    "from", "not", "no", "but", "into", "them", "they", "every",
}


def fetch(url, timeout=25):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")


def text_of(fragment):
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))
    t = re.sub(r"Section titled\s*[“\"'].*?[”\"']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def section_text(doc, frag):
    """Text under the heading carrying `frag`, up to the next heading of any level."""
    doc = re.sub(r"(?is)<(script|style|template)[^>]*>.*?</\1>", " ", doc)
    m = re.search(rf'<h([1-6])[^>]*\bid="{re.escape(frag)}"[^>]*>.*?</h\1>', doc, re.S)
    if not m:
        return None
    rest = doc[m.end():]
    nxt = re.search(r"<h[1-6][^>]*\bid=", rest)
    return text_of(rest[: nxt.start()] if nxt else rest)


def tokens(s):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.\-/]*", s.lower()) if w not in STOP and len(w) > 1}


def score(anchor_text, sentence, target):
    """How much of the claim shows up in the target section."""
    if target is None:
        return "unknown", {}
    tl = target.lower()
    want = tokens(anchor_text)
    hit = {w for w in want if w in tl}

    # Numbers are the highest-signal token: if the anchor text claims 47.3 KB,
    # the target section either says 47.3 or it does not support the claim.
    #
    # The anchor's OWN numbers and the surrounding sentence's are scored
    # separately, and that separation is load-bearing. Pooling them let a
    # fabricated "980.2 KB" score `strong` because the sentence window had
    # bled a real "47.3" in from the adjacent line. Caught by the control case
    # in references/testing.md, which is why that control exists.
    anchor_nums = set(re.findall(r"\d+(?:\.\d+)?", anchor_text))
    anchor_missing = {n for n in anchor_nums if n not in tl}
    sent_nums = set(re.findall(r"\d+(?:\.\d+)?", sentence)) - anchor_nums
    sent_hit = {n for n in sent_nums if n in tl}

    detail = {
        "anchor_terms": f"{len(hit)}/{len(want)}",
        "anchor_numbers": f"{len(anchor_nums) - len(anchor_missing)}/{len(anchor_nums)}"
        if anchor_nums else "none in anchor text",
        "missing_numbers": sorted(anchor_missing),
    }

    # A number in the linked words that the target never states is the whole
    # failure mode this tool exists for. Nothing else can rescue it.
    if anchor_missing:
        return "none", detail

    ratio = len(hit) / len(want) if want else 0
    if (anchor_nums or sent_hit) and ratio >= 0.4:
        return "strong", detail
    if ratio >= 0.6:
        return "strong", detail
    if ratio >= 0.3:
        return "weak", detail
    return "none", detail


def links_from(src):
    """(anchor_text, url, surrounding_sentence) for each link in a file or page."""
    if re.match(r"^https?://", src):
        _, body = fetch(src)
        raw = [(text_of(t), u) for u, t in HTML_LINK.findall(body)]
        flat = text_of(body)
    else:
        body = open(src, encoding="utf-8").read()
        raw = [(t, u) for t, u in MD_LINK.findall(body)]
        flat = re.sub(r"\s+", " ", body)
    out = []
    for text, url in raw:
        i = flat.find(text)
        sent = flat[max(0, i - 220): i + 220] if i >= 0 else ""
        out.append((text, url, sent))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="markdown/MDX path, or a URL to fetch")
    ap.add_argument("--host", default="", help="only check links whose URL contains this")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any 'none' support")
    ap.add_argument("--context", type=int, default=240)
    a = ap.parse_args()

    results, cache = [], {}
    for text, url, sent in links_from(a.source):
        if a.host and a.host not in url:
            continue
        base, _, frag = url.partition("#")
        if base not in cache:
            try:
                cache[base] = fetch(base)
            except HTTPError as e:
                cache[base] = (e.code, "")
            except URLError as e:
                cache[base] = (0, f"{e}")
        status, doc = cache[base]

        if not doc:
            target = None
        elif frag:
            target = section_text(doc, frag)
        else:
            # Whole-page link. Strip chrome and inline scripts first, or the
            # excerpt is the theme's boot script rather than the page's prose.
            target = text_of(re.sub(r"(?is)<(script|style|template|nav|header|footer)[^>]*>.*?</\1>", " ", doc))
        anchor_ok = None if not frag else (target is not None)
        sup, detail = score(text, sent, target)

        results.append({
            "anchor_text": text,
            "url": url,
            "status": status,
            "anchor_ok": anchor_ok,
            "support": sup,
            "detail": detail,
            "target_excerpt": (target or "")[: a.context],
        })
        flag = "ok " if status == 200 and anchor_ok is not False and sup in ("strong", "weak") else "!! "
        print(f"{flag}{status} {sup:7} anchor={anchor_ok}  \"{text[:44]}\"  {url}", file=sys.stderr)

    json.dump({"source": a.source, "checked": len(results), "links": results}, sys.stdout, indent=2)
    print()

    dead = [r for r in results if r["status"] != 200]
    lost = [r for r in results if r["anchor_ok"] is False]
    unsupported = [r for r in results if r["support"] == "none"]
    print(f"\n{len(results)} checked | {len(dead)} dead | {len(lost)} missing anchor | "
          f"{len(unsupported)} unsupported", file=sys.stderr)
    sys.exit(1 if dead or lost or (a.strict and unsupported) else 0)


if __name__ == "__main__":
    main()
