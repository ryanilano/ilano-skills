#!/usr/bin/env python3
"""socials-mirror — pull a public figure's OPEN, public profiles into zero-waste
markdown (and JSON). Standard library only.

FRIENDLY, PUBLIC-ONLY, NOT A STALKER TOOL. Rules baked in:
  - Only public, unauthenticated endpoints and public RSS/Atom feeds.
  - Never logs in, never circumvents an auth wall, never uses a private cookie.
  - One-shot snapshot, no monitoring/polling loop.
  - Identifies itself with a User-Agent and rate-limits between requests.
  - X/Twitter and LinkedIn have no clean public API: the skill records the
    canonical profile URL and, if you hand it a public RSS bridge feed for them,
    treats that as a normal feed. It does NOT scrape logged-in content.

Usage:
  socials_mirror.py "Ahmad Awais" \
      --github ahmadawais \
      --bsky ahmadawais.com \
      --rss https://www.reddit.com/user/MrAhmadAwais/.rss \
      --x https://x.com/MrAhmadAwais \
      --linkedin https://www.linkedin.com/in/mrahmadawais \
      --out ./socials --json

Writes <out>/<slug>/{github,bluesky,reddit-or-feed,x,linkedin}.md (+ .json with
--json) and index.md. Read the files it wrote; the last line is the directory.
"""
from __future__ import annotations
import argparse, json, re, sys, time, html as _html
from urllib import request, error, parse
from xml.etree import ElementTree as ET

UA = "socials-mirror/1.0 (public-profile snapshot; +https://commandcode.ai style, respectful)"
DELAY = 0.5  # seconds between network calls, be a good guest


def get(url: str, accept: str = "application/json", timeout: int = 30):
    req = request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get_content_charset() or "utf-8"


def get_json(url: str):
    body, enc = get(url)
    return json.loads(body.decode(enc, "replace"))


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "person"


def md_escape(s):
    return (s or "").replace("|", "\\|")


# ---------------- GitHub (public REST, unauth) ----------------

def github(user: str) -> dict:
    prof = get_json(f"https://api.github.com/users/{parse.quote(user)}")
    time.sleep(DELAY)
    repos = get_json(f"https://api.github.com/users/{parse.quote(user)}/repos"
                     f"?per_page=100&sort=updated&type=owner")
    data = {
        "platform": "github", "url": prof.get("html_url"),
        "name": prof.get("name"), "bio": prof.get("bio"),
        "company": prof.get("company"), "location": prof.get("location"),
        "blog": prof.get("blog"), "followers": prof.get("followers"),
        "following": prof.get("following"), "public_repos": prof.get("public_repos"),
        "created_at": prof.get("created_at"),
        "repos": [{"name": r["name"], "url": r["html_url"], "desc": r.get("description"),
                   "stars": r.get("stargazers_count"), "lang": r.get("language"),
                   "updated": r.get("updated_at")} for r in repos],
    }
    return data


def github_md(d: dict) -> str:
    lines = [f"# GitHub — {md_escape(d.get('name') or '')}  ({d['url']})", "",
             f"{d.get('bio') or ''}", "",
             f"- location: {d.get('location') or '—'}  ·  company: {d.get('company') or '—'}  ·  blog: {d.get('blog') or '—'}",
             f"- {d.get('followers')} followers · {d.get('public_repos')} public repos · since {(d.get('created_at') or '')[:10]}",
             "", "## Repos (most recently updated)", "",
             "| repo | ★ | lang | updated | description |", "|---|---|---|---|---|"]
    for r in sorted(d["repos"], key=lambda x: x.get("updated") or "", reverse=True):
        lines.append(f"| [{r['name']}]({r['url']}) | {r.get('stars',0)} | {r.get('lang') or ''} "
                     f"| {(r.get('updated') or '')[:10]} | {md_escape(r.get('desc') or '')} |")
    return "\n".join(lines) + "\n"


# ---------------- BlueSky (public AppView XRPC, unauth) ----------------

def bluesky(handle: str) -> dict:
    base = "https://public.api.bsky.app/xrpc"
    prof = get_json(f"{base}/app.bsky.actor.getProfile?actor={parse.quote(handle)}")
    time.sleep(DELAY)
    feed = get_json(f"{base}/app.bsky.feed.getAuthorFeed?actor={parse.quote(handle)}&limit=50")
    posts = []
    for item in feed.get("feed", []):
        p = item.get("post", {}).get("record", {})
        posts.append({"text": p.get("text", ""), "created": p.get("createdAt", ""),
                      "uri": item.get("post", {}).get("uri", "")})
    return {"platform": "bluesky", "handle": handle,
            "url": f"https://bsky.app/profile/{handle}",
            "display_name": prof.get("displayName"), "description": prof.get("description"),
            "followers": prof.get("followersCount"), "posts_count": prof.get("postsCount"),
            "posts": posts}


def bluesky_md(d: dict) -> str:
    lines = [f"# BlueSky — {md_escape(d.get('display_name') or d['handle'])}  ({d['url']})", "",
             f"{d.get('description') or ''}", "",
             f"- {d.get('followers')} followers · {d.get('posts_count')} posts", "",
             "## Recent posts", ""]
    for p in d["posts"]:
        lines.append(f"**[{(p['created'] or '')[:16]}]** {p['text']}")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------- RSS / Atom feeds (Reddit .rss, blogs, bridges) ----------------

def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return _html.unescape(s).strip()


def feed(url: str) -> dict:
    body, enc = get(url, accept="application/rss+xml, application/atom+xml, application/xml")
    root = ET.fromstring(body)
    tag = root.tag.lower()
    entries = []
    if tag.endswith("rss") or root.find("channel") is not None:
        ch = root.find("channel")
        title = (ch.findtext("title") or "").strip()
        for it in ch.findall("item"):
            body_txt = it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") \
                       or it.findtext("description") or ""
            entries.append({"title": (it.findtext("title") or "").strip(),
                            "link": (it.findtext("link") or "").strip(),
                            "date": (it.findtext("pubDate") or "").strip(),
                            "text": _strip_html(body_txt)})
    else:  # Atom
        ns = "{http://www.w3.org/2005/Atom}"
        title = (root.findtext(f"{ns}title") or "").strip()
        for e in root.findall(f"{ns}entry"):
            link_el = e.find(f"{ns}link")
            body_txt = (e.findtext(f"{ns}content") or e.findtext(f"{ns}summary") or "")
            entries.append({"title": (e.findtext(f"{ns}title") or "").strip(),
                            "link": link_el.get("href") if link_el is not None else "",
                            "date": (e.findtext(f"{ns}updated") or e.findtext(f"{ns}published") or "").strip(),
                            "text": _strip_html(body_txt)})
    return {"platform": "feed", "url": url, "title": title, "entries": entries}


def feed_md(d: dict, label: str) -> str:
    lines = [f"# {label} — {md_escape(d.get('title') or '')}  ({d['url']})", "",
             f"{len(d['entries'])} entries, full text where the feed carried it.", ""]
    for e in d["entries"]:
        lines.append(f"## {md_escape(e['title'])}  ")
        lines.append(f"{e['date']} · {e['link']}")
        lines.append("")
        lines.append(e["text"])
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------- auth-walled: record the link, do not scrape ----------------

def linkonly_md(platform: str, url: str) -> str:
    return (f"# {platform}\n\n"
            f"Public profile: {url}\n\n"
            f"> {platform} has no clean public API and its terms forbid scraping "
            f"logged-in content. This skill records the canonical link only. If a "
            f"public RSS bridge feed exists for this profile, pass it with --rss "
            f"and it will be mirrored as a normal feed.\n")


def write(out_dir, name, ext, content):
    import os
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.{ext}")
    with open(path, "w") as f:
        f.write(content)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mirror a public figure's open socials, friendly and public-only.")
    ap.add_argument("name")
    ap.add_argument("--github")
    ap.add_argument("--bsky")
    ap.add_argument("--rss", action="append", default=[], help="feed URL (repeatable); Reddit .rss, blogs, bridges")
    ap.add_argument("--x", help="X/Twitter profile URL (link recorded, not scraped)")
    ap.add_argument("--linkedin", help="LinkedIn profile URL (link recorded, not scraped)")
    ap.add_argument("--out", default="./socials")
    ap.add_argument("--json", action="store_true", help="also write structured .json per platform")
    args = ap.parse_args(argv)

    import os
    out_dir = os.path.join(args.out, slugify(args.name))
    print(f"public-only snapshot of {args.name} → {out_dir}", file=sys.stderr)
    index = [f"# {args.name} — public socials snapshot",
             f"Captured {time.strftime('%Y-%m-%d %H:%M %Z')}. Public data only; no auth, no scraping of logged-in content.", ""]
    written = []

    def do(label, fetch, md_fn, base):
        try:
            d = fetch()
            p = write(out_dir, base, "md", md_fn(d))
            written.append(p)
            if args.json:
                write(out_dir, base, "json", json.dumps(d, indent=2))
            index.append(f"- **{label}**: [{base}.md]({base}.md)")
            print(f"  ok  {label}", file=sys.stderr)
        except (error.HTTPError, error.URLError, ET.ParseError, ValueError, KeyError) as e:
            index.append(f"- **{label}**: FAILED ({type(e).__name__}: {e})")
            print(f"  fail {label}: {e}", file=sys.stderr)
        time.sleep(DELAY)

    if args.github:
        do("GitHub", lambda: github(args.github), github_md, "github")
    if args.bsky:
        do("BlueSky", lambda: bluesky(args.bsky), bluesky_md, "bluesky")
    for i, url in enumerate(args.rss):
        label = "Reddit" if "reddit.com" in url else f"Feed {i+1}"
        base = "reddit" if "reddit.com" in url else f"feed-{i+1}"
        do(label, lambda u=url: feed(u), lambda d: feed_md(d, label), base)
    if args.x:
        write(out_dir, "x", "md", linkonly_md("X / Twitter", args.x)); index.append("- **X/Twitter**: [x.md](x.md) (link only)")
    if args.linkedin:
        write(out_dir, "linkedin", "md", linkonly_md("LinkedIn", args.linkedin)); index.append("- **LinkedIn**: [linkedin.md](linkedin.md) (link only)")

    write(out_dir, "index", "md", "\n".join(index) + "\n")
    print(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
