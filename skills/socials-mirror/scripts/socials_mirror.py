#!/usr/bin/env python3
"""socials-mirror — pull a public figure's OPEN, public profiles into zero-waste
markdown (and JSON). Standard library only.

FRIENDLY, PUBLIC-ONLY, NOT A STALKER TOOL. Rules baked in:
  - Only public, unauthenticated endpoints and public RSS/Atom feeds.
  - Never logs in, never circumvents an auth wall, never uses a private cookie.
  - One-shot snapshot, no monitoring/polling loop.
  - Identifies itself with a User-Agent and rate-limits between requests.
  - X serves no timeline without a login, so --x reads public copies: the
    author's page on Thread Reader (threads anyone unrolled there) and any
    Nitter-style RSS mirror you name. Individual X posts you name (--x-post)
    come from the public embed endpoint. It does NOT scrape logged-in content.

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

Every flag takes a handle or a URL: --github @octocat or github.com/octocat,
--bsky alice (bsky.social is appended) or a bsky.app link, --x @jack,
--linkedin in/jane, --rss u/spez or r/selfhosted (.rss appended). Share and
tracking parameters (utm_*, trk=, s=, fbclid…) are stripped from every input.
--selftest checks the cleaners without touching the network.
"""
from __future__ import annotations
import argparse, json, re, sys, time, html as _html
from urllib import request, error, parse
from xml.etree import ElementTree as ET

UA = "socials-mirror/1.0 (public-profile snapshot; +https://commandcode.ai style, respectful)"
DELAY = 0.5  # seconds between network calls, be a good guest


# ---------------- input cleaning: handles in, canonical out ----------------
#
# People paste what they have: a profile URL with ?utm_source=share on it, a
# bare handle, an @handle, a linkedin.com/in/... link with ?trk=... after it.
# Every --flag accepts any of those and normalises to the one form the fetcher
# or the recorded link needs. Tracking parameters are stripped so the sharer's
# click never lands in a note.

TRACKING_KEYS = {"si", "feature", "fbclid", "gclid", "dclid", "msclkid", "igsh", "igshid",
                 "mc_cid", "mc_eid", "ref", "ref_src", "ref_url", "source", "s", "trk",
                 "trkinfo", "share_id", "_hsenc", "_hsmi", "mkt_tok", "yclid", "twclid",
                 "originalsubdomain", "rdt", "share_to"}


def strip_tracking(url: str) -> str:
    """Drop tracking query keys and utm_* from any URL. Never raises."""
    u = parse.urlsplit((url or "").strip())
    q = [(k, v) for k, v in parse.parse_qsl(u.query, keep_blank_values=False)
         if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_")]
    return parse.urlunsplit((u.scheme, u.netloc, u.path.rstrip("/") or u.path, parse.urlencode(q), ""))


def _parts(s: str):
    """(host, path) of a URL or a bare handle. A bare handle has host ''."""
    s = (s or "").strip().strip("<>").strip()
    if "://" not in s and re.match(r"^(?:www\.)?[\w.-]+\.[a-z]{2,}(/|$)", s, re.I):
        s = "https://" + s
    if "://" not in s:
        return "", s.strip("/")
    u = parse.urlsplit(s)
    host = u.netloc.lower().split("@")[-1].split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    return host, u.path.strip("/")


def github_user(s: str) -> str:
    """'octocat', '@octocat', 'github.com/octocat', 'https://github.com/octocat/repo' -> 'octocat'."""
    host, path = _parts(s)
    name = path.split("/")[0] if host.endswith("github.com") or not host else ""
    return name.lstrip("@")


def bsky_handle(s: str) -> str:
    """'alice.com', '@alice', 'bsky.app/profile/alice.com', 'did:plc:…' -> handle or DID.

    A bare name with no dot is a bsky.social account, so the host is appended.
    """
    host, path = _parts(s)
    if host.endswith("bsky.app"):
        segs = path.split("/")
        name = segs[1] if len(segs) >= 2 and segs[0] == "profile" else ""
    elif not host:
        name = path
    else:
        name = host  # a custom-domain handle typed as 'https://alice.com'
    name = name.lstrip("@").strip("/")
    if name.startswith("did:") or "." in name or not name:
        return name
    return f"{name}.bsky.social"


def x_url(s: str) -> str:
    """'@jack', 'jack', 'twitter.com/jack?s=21', 'https://x.com/jack/status/1' -> 'https://x.com/jack'."""
    host, path = _parts(s)
    if host and not (host.endswith("x.com") or host.endswith("twitter.com")):
        return strip_tracking(s)
    name = path.split("/")[0].lstrip("@")
    return f"https://x.com/{name}" if name else ""


def linkedin_url(s: str) -> str:
    """'in/jane', 'jane', 'linkedin.com/in/jane/?trk=x', 'company/acme' -> canonical linkedin.com URL."""
    host, path = _parts(s)
    if host and not host.endswith("linkedin.com"):
        return strip_tracking(s)
    segs = [p for p in path.split("/") if p]
    if not segs:
        return ""
    if segs[0] in ("in", "company", "school", "pub"):
        kind, slug = segs[0], segs[1] if len(segs) > 1 else ""
    else:
        kind, slug = "in", segs[0]
    slug = parse.unquote(slug).lstrip("@")
    return f"https://www.linkedin.com/{kind}/{slug}" if slug else ""


def feed_url(s: str) -> str:
    """Reddit shorthand and profile links become their .rss form; other feeds lose tracking.

    'u/name', '/user/name', 'r/sub', 'reddit.com/user/name' -> https://www.reddit.com/<...>/.rss
    A URL that already ends in .rss, .xml, /feed or /atom is left alone except for tracking keys.
    """
    host, path = _parts(s)
    if not host:
        m = re.match(r"^(?:u|user)/([\w-]+)$", path) or re.match(r"^(r)/([\w]+)$", path)
        if m:
            kind = "user" if m.group(1) not in ("r",) else "r"
            name = m.group(m.lastindex)
            return f"https://www.reddit.com/{kind}/{name}/.rss"
        return strip_tracking("https://" + path)
    if host.endswith("reddit.com"):
        segs = [p for p in path.split("/") if p]
        if len(segs) >= 2 and segs[0] in ("user", "u", "r") and not path.endswith(".rss"):
            kind = "user" if segs[0] in ("user", "u") else "r"
            return f"https://www.reddit.com/{kind}/{segs[1]}/.rss"
    return strip_tracking(s)


def selftest() -> int:
    cases = [
        (github_user, "octocat", "octocat"),
        (github_user, "@octocat", "octocat"),
        (github_user, "https://github.com/octocat/Hello-World?tab=readme", "octocat"),
        (github_user, "github.com/octocat", "octocat"),
        (bsky_handle, "alice.com", "alice.com"),
        (bsky_handle, "@alice", "alice.bsky.social"),
        (bsky_handle, "alice", "alice.bsky.social"),
        (bsky_handle, "https://bsky.app/profile/alice.com?utm_source=share", "alice.com"),
        (bsky_handle, "https://bsky.app/profile/did:plc:abc123/post/xyz", "did:plc:abc123"),
        (x_url, "@jack", "https://x.com/jack"),
        (x_url, "jack", "https://x.com/jack"),
        (x_url, "https://twitter.com/jack?s=21&t=abc", "https://x.com/jack"),
        (x_url, "https://x.com/jack/status/20?ref_src=twsrc", "https://x.com/jack"),
        (linkedin_url, "in/jane", "https://www.linkedin.com/in/jane"),
        (linkedin_url, "jane", "https://www.linkedin.com/in/jane"),
        (linkedin_url, "https://www.linkedin.com/in/jane/?trk=public_profile&utm_source=share",
         "https://www.linkedin.com/in/jane"),
        (linkedin_url, "https://linkedin.com/company/acme", "https://www.linkedin.com/company/acme"),
        (feed_url, "u/spez", "https://www.reddit.com/user/spez/.rss"),
        (feed_url, "r/selfhosted", "https://www.reddit.com/r/selfhosted/.rss"),
        (feed_url, "https://www.reddit.com/user/spez/?utm_source=share", "https://www.reddit.com/user/spez/.rss"),
        (feed_url, "https://www.reddit.com/r/selfhosted/.rss", "https://www.reddit.com/r/selfhosted/.rss"),
        (feed_url, "https://blog.example.com/feed.xml?utm_campaign=x&fbclid=y", "https://blog.example.com/feed.xml"),
        (feed_url, "https://example.com/rss?category=ai&ref=tw", "https://example.com/rss?category=ai"),
        (tweet_id, "20", "20"),
        (tweet_id, "https://x.com/jack/status/20?s=21&t=abc", "20"),
        (tweet_id, "https://twitter.com/i/web/status/1234567890123456789/photo/1", "1234567890123456789"),
        (tweet_id, "https://x.com/jack", ""),
        (lambda s: _embed_token(s)[:4], "20", "6dq1"),               # widget JS gives 6dq1a2xwd93
        (lambda s: _embed_token(s)[:9], "1234567890123456789", "2zqic77uq"),
    ]
    bad = [(f.__name__, i, o, f(i)) for f, i, o in cases if f(i) != o]
    for fn, i, want, got in bad:
        print(f"FAIL {fn}({i!r})\n  want {want}\n  got  {got}", file=sys.stderr)
    print(f"input cleaning: {len(cases) - len(bad)}/{len(cases)} ok", file=sys.stderr)
    return 1 if bad else 0


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


# ---------------- X / Twitter: named posts via the public embed endpoint ----------------
#
# A profile timeline is not served to anyone without a login (the syndication
# timeline answers 429 to unauthenticated callers, Nitter instances are gone,
# RSSHub's route needs an account cookie). A single post is different: the
# same endpoint the official embed widget uses returns the full text, date,
# author, quoted post and media for any public post, no auth, no cookie. So
# --x records the profile link, and --x-post <url-or-id> mirrors the posts you
# name. Public, unauthenticated, one request per post.

TWEET_ID_RE = re.compile(r"(?:status(?:es)?/|^)(\d{1,25})(?:\?|/|$)")


def tweet_id(s: str) -> str:
    """'20', 'https://x.com/jack/status/20?s=21', 'twitter.com/i/web/status/20' -> '20'."""
    s = (s or "").strip().strip("<>")
    m = TWEET_ID_RE.search(s)
    return m.group(1) if m else ""


def _embed_token(tid: str) -> str:
    """The token the embed widget derives from the id: ((id/1e15)*pi) in base 36, no dots or zeros."""
    n = (int(tid) / 1e15) * 3.141592653589793
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    whole, frac = int(n), n - int(n)
    out = ""
    while whole:
        out = digits[whole % 36] + out
        whole //= 36
    out += "."
    for _ in range(24):  # enough to survive the leading zeros of a small id
        frac *= 36
        d = int(frac)
        out += digits[d]
        frac -= d
    return re.sub(r"0+|\.", "", out) or "0"


def x_post(ref: str) -> dict:
    tid = tweet_id(ref)
    if not tid:
        raise ValueError(f"no post id in {ref!r}")
    d = get_json(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&token={_embed_token(tid)}")
    if d.get("__typename") == "TweetTombstone" or not d.get("id_str"):
        raise ValueError(f"post {tid} is unavailable (deleted, private, or age-gated)")
    u = d.get("user") or {}
    quoted = d.get("quoted_tweet") or {}
    media = [m.get("media_url_https") or m.get("expanded_url")
             for m in d.get("mediaDetails") or [] if m]
    urls = [e.get("expanded_url") for e in (d.get("entities") or {}).get("urls") or [] if e]
    return {"id": tid, "url": f"https://x.com/{u.get('screen_name', 'i')}/status/{tid}",
            "author": u.get("name"), "handle": u.get("screen_name"),
            "created": d.get("created_at", ""), "text": d.get("text", ""),
            "likes": d.get("favorite_count"), "reply_to": d.get("in_reply_to_screen_name"),
            "quoted": {"handle": (quoted.get("user") or {}).get("screen_name"),
                       "text": quoted.get("text", ""),
                       "url": f"https://x.com/{(quoted.get('user') or {}).get('screen_name', 'i')}/status/{quoted.get('id_str', '')}"}
                      if quoted else None,
            "media": media, "links": urls}


def x_posts(refs: list) -> dict:
    posts, failed = [], []
    for r in refs:
        try:
            posts.append(x_post(r))
        except (error.HTTPError, error.URLError, ValueError, KeyError) as e:
            failed.append((r, f"{type(e).__name__}: {e}"))
        time.sleep(DELAY)
    if not posts and failed:
        raise ValueError("; ".join(f"{r}: {why}" for r, why in failed))
    return {"platform": "x", "posts": posts, "failed": failed}


def x_thread(ref: str) -> dict:
    """A whole thread from threadreaderapp.com's public cache, root post id in.

    X serves no thread to anyone without a login. Thread Reader is a public
    unroller that keeps a cached copy of any thread someone has asked it to
    unroll, and serves it as plain HTML. If the thread was never unrolled
    there, this raises and the caller falls back to the root post alone.
    """
    tid = tweet_id(ref)
    if not tid:
        raise ValueError(f"no post id in {ref!r}")
    body, enc = get(f"https://threadreaderapp.com/thread/{tid}.html", accept="text/html")
    page = body.decode(enc, "replace")
    blocks = re.split(r'<div id="tweet_\d+" class="content-tweet[^"]*"', page)[1:]
    if not blocks:
        raise ValueError(f"thread {tid} is not in the Thread Reader cache; only the root can be mirrored")
    author = re.search(r'data-screenname="([^"]+)"', page)
    handle = author.group(1) if author else "i"
    posts = []
    for b in blocks:
        m = re.search(r'data-tweet="(\d+)"', b)
        pid = m.group(1) if m else ""
        b = b.split('<sup class="tw-permalink"', 1)[0]
        b = b.split('dir="auto">', 1)[1] if 'dir="auto">' in b else b
        vids = re.findall(r'<source src="(https://video\.twimg\.com/[^"]+)"', b)
        imgs = re.findall(r'<img[^>]+src="(https://pbs\.twimg\.com/media/[^"]+)"', b)
        links = [l for l in re.findall(r'<a[^>]+href="(https?://[^"]+)"', b)
                 if not any(h in l for h in ("threadreaderapp.com", "twitter.com", "x.com/", "t.co/"))]
        b = re.sub(r"<video.*?</video>", "", b, flags=re.S)
        b = re.sub(r"<br\s*/?>", "\n", b)
        txt = _html.unescape(re.sub(r"<[^>]+>", "", b)).strip()
        txt = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", txt))
        best = [v for v in vids if "720x" in v or "1280x" in v or "1080x" in v] or vids[:1]
        posts.append({"id": pid, "url": f"https://x.com/{handle}/status/{pid}", "handle": handle,
                      "text": txt, "media": imgs + best, "links": links})
    return {"platform": "x", "thread_root": tid, "handle": handle,
            "source": f"https://threadreaderapp.com/thread/{tid}.html", "posts": posts, "failed": []}


def x_thread_index(handle: str) -> list:
    """The author's page on Thread Reader: every thread someone unrolled there.

    Public HTML, no login. It lists the most recent unrolled threads (about 15
    per page) with id, date, post count and a preview. This is the one public
    view of an X timeline left: X serves none without a login.
    """
    body, enc = get(f"https://threadreaderapp.com/user/{parse.quote(handle)}", accept="text/html")
    page = body.decode(enc, "replace")
    out = []
    for card in re.split(r'(?=<div class="col-12" data-controller="link" data-link-href="/thread/)', page)[1:]:
        m = re.search(r'data-link-href="/thread/(\d+)\.html"', card)
        if not m:
            continue
        when = re.search(r'data-time="(\d+)"', card)
        count = re.search(r"(\d+)\s+tweets", card)
        # The preview is everything after the card-tweetsv2 opening tag; a
        # thumbnail sits in its own nested div, so dropping that first keeps a
        # nested </div> from cutting the text short.
        prev = card.split('class="card-tweetsv2"', 1)[1].split(">", 1)[1] if 'class="card-tweetsv2"' in card else ""
        prev = re.sub(r'<div class="thumb-div">.*?</div>', "", prev, flags=re.S)
        text = _html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", prev))).strip()
        out.append({"id": m.group(1),
                    "date": time.strftime("%Y-%m-%d", time.gmtime(int(when.group(1)))) if when else "",
                    "posts": int(count.group(1)) if count else None,
                    "preview": re.sub(r"\n{3,}", "\n\n", text)[:600],
                    "url": f"https://x.com/{handle}/status/{m.group(1)}",
                    "reader": f"https://threadreaderapp.com/thread/{m.group(1)}.html"})
    return out


def x_mirror_feed(handle: str, templates: list) -> dict | None:
    """First Nitter-style RSS mirror that answers with a real feed, or None.

    Templates look like https://mirror.example/{handle}/rss. None ships as a
    default: every public mirror checked on 2026-09-23 was down or suspended
    (nitter.net and others did not answer, xcancel.com returned HTTP 451).
    """
    for t in templates:
        url = t.replace("{handle}", parse.quote(handle))
        try:
            d = feed(url)
            if d["entries"]:
                return d
        except (error.HTTPError, error.URLError, ET.ParseError, ValueError) as e:
            print(f"  X mirror {url} did not answer with a feed ({type(e).__name__})", file=sys.stderr)
        time.sleep(DELAY)
    return None


def x_profile(profile_url: str, full: int, templates: list) -> dict:
    handle = profile_url.rstrip("/").rsplit("/", 1)[-1]
    d = {"platform": "x", "profile": profile_url, "handle": handle,
         "threads": [], "threads_full": [], "mirror": None, "failed": []}
    try:
        d["threads"] = x_thread_index(handle)
    except (error.HTTPError, error.URLError, ValueError) as e:
        d["failed"].append(("threadreaderapp user page", f"{type(e).__name__}: {e}"))
    for t in d["threads"][:max(0, full)]:
        time.sleep(DELAY)
        try:
            d["threads_full"].append(x_thread(t["id"]))
        except (error.HTTPError, error.URLError, ValueError) as e:
            d["failed"].append((t["id"], f"{type(e).__name__}: {e}"))
    if templates:
        d["mirror"] = x_mirror_feed(handle, templates)
    return d


def x_profile_md(d: dict) -> str:
    lines = ["# X / Twitter", "", f"Public profile: {d['profile']}", "",
             "> X serves no timeline without a login. What is here comes from public "
             "copies: the threads anyone has unrolled on Thread Reader, and an RSS "
             "mirror if one was given and answered.", ""]
    if d["threads"]:
        lines += [f"## Threads unrolled on Thread Reader ({len(d['threads'])})", "",
                  f"Source: https://threadreaderapp.com/user/{d['handle']}", ""]
        for t in d["threads"]:
            n = f"{t['posts']} posts" if t.get("posts") else ""
            lines += [f"- **{t['date']}** · {n} · {t['url']} · [reader]({t['reader']})",
                      "  " + t["preview"].replace("\n", " ")[:280], ""]
    else:
        lines += ["No threads by this author are cached on Thread Reader.", ""]
    for th in d["threads_full"]:
        lines += [f"## Thread {th['thread_root']} ({len(th['posts'])} posts)", "", f"Source: {th['source']}", ""]
        for i, p in enumerate(th["posts"], 1):
            lines += [f"### {i}/{len(th['posts'])}", "", p.get("text", ""), ""]
            for m in p.get("media") or []:
                lines.append(f"- media: {m}")
            for u in p.get("links") or []:
                lines.append(f"- link: {u}")
            lines += [f"- post: {p['url']}", ""]
    if d.get("mirror"):
        m = d["mirror"]
        lines += [f"## Recent posts via RSS mirror ({len(m['entries'])})", "", f"Source: {m['url']}", ""]
        for e in m["entries"]:
            lines += [f"**[{e['date']}]** {e['link']}", "", e["text"], ""]
    for r, why in d.get("failed") or []:
        lines.append(f"- FAILED {r}: {why}")
    return "\n".join(lines) + "\n"


def x_md(profile_url: str, d: dict) -> str:
    lines = ["# X / Twitter", ""]
    if profile_url:
        lines += [f"Public profile: {profile_url}", "",
                  "> The timeline is not served without a login, so it is recorded as a link. "
                  "Posts named with --x-post are mirrored below from the public embed endpoint.", ""]
    if d.get("thread_root"):
        lines += [f"## Thread from https://x.com/{d['handle']}/status/{d['thread_root']} ({len(d['posts'])} posts)", "",
                  f"Source: {d['source']} (public cache; X serves no thread without a login).", ""]
        for i, p in enumerate(d["posts"], 1):
            lines += [f"### {i}/{len(d['posts'])}", "", p.get("text", ""), ""]
            for m in p.get("media") or []:
                lines.append(f"- media: {m}")
            for u in p.get("links") or []:
                lines.append(f"- link: {u}")
            lines += [f"- post: {p['url']}", ""]
        return "\n".join(lines) + "\n"
    if d.get("posts"):
        lines += [f"## Posts ({len(d['posts'])})", ""]
        for p in d["posts"]:
            who = f"@{p['handle']}" if p.get("handle") else ""
            lines.append(f"**[{(p.get('created') or '')[:16]}]** {who} · {p['url']}")
            if p.get("reply_to"):
                lines.append(f"replying to @{p['reply_to']}")
            lines += ["", p.get("text", ""), ""]
            if p.get("quoted"):
                q = p["quoted"]
                lines += [f"> quoting @{q.get('handle')}: {q.get('text', '')}", f"> {q.get('url')}", ""]
            for m in p.get("media") or []:
                lines.append(f"- media: {m}")
            for u in p.get("links") or []:
                lines.append(f"- link: {u}")
            if p.get("media") or p.get("links"):
                lines.append("")
    for r, why in d.get("failed") or []:
        lines.append(f"- FAILED {r}: {why}")
    return "\n".join(lines) + "\n"


# ---------------- LinkedIn: the guest view, then the link ----------------
#
# LinkedIn serves a logged-out "guest" copy of a profile, a company page and a
# single post: the same pages a search engine indexes. The profile carries a
# JSON-LD Person block (name, headline, about, location, follower count) and
# links to the owner's most recent posts; each post has a small public embed
# page with the full text. No login, no cookie, no API. LinkedIn does throttle
# guests hard (an HTTP 999 or a redirect to an authwall after a burst), so the
# fetch is capped at a handful of posts, spaced, and falls back to the recorded
# link with a note when refused. The timeline beyond that handful is not
# public and is not fetched.

LI_POST_CAP = 8


def _li_get(url: str) -> str:
    body, enc = get(url, accept="text/html")
    page = body.decode(enc, "replace")
    if "authwall" in page[:4000] or "<title>LinkedIn Login" in page or "Sign Up | LinkedIn" in page[:6000]:
        raise ValueError("LinkedIn answered with its login wall")
    return page


def _li_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    txt = _html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", txt))


def linkedin_post(activity_id: str) -> dict:
    page = _li_get(f"https://www.linkedin.com/embed/feed/update/urn:li:activity:{activity_id}")
    body = re.search(r'class="[^"]*attributed-text-segment-list__content[^"]*"[^>]*>(.*?)</p>', page, re.S)
    when = re.search(r"<time[^>]*>(.*?)</time>", page, re.S)
    reacts = re.search(r'data-num-reactions="(\d+)"', page)
    author = re.search(r'data-tracking-control-name="public_post_feed-actor-name"[^>]*>(.*?)</a>', page, re.S)
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    return {"id": activity_id,
            "url": f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
            "author": _li_text(author.group(1)) if author else "",
            "title": _html.unescape(title.group(1)).split("|")[0].strip() if title else "",
            "when": _li_text(when.group(1)) if when else "",
            "reactions": int(reacts.group(1)) if reacts else None,
            "text": _li_text(body.group(1)) if body else ""}


def linkedin_public(url: str) -> dict:
    """Guest view of a profile or company page plus its listed recent posts."""
    page = _li_get(url)
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    kind = "company" if "/company/" in url or "/school/" in url else "person"
    info = {}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        for n in d.get("@graph", [d]):
            if n.get("@type") in ("Person", "Organization"):
                jt = n.get("jobTitle")
                info = {"name": n.get("name"), "headline": ", ".join(jt) if isinstance(jt, list) else jt,
                        "about": n.get("description"),
                        "location": (n.get("address") or {}).get("addressLocality"),
                        "followers": (n.get("interactionStatistic") or {}).get("userInteractionCount"),
                        "site": n.get("url") or n.get("sameAs")}
                break
        if info:
            break
    og = re.search(r'<meta property="og:description" content="([^"]*)"', page)
    if not info.get("about") and og:
        info["about"] = _html.unescape(og.group(1))
    own = re.findall(r'https://www\.linkedin\.com/posts/' + re.escape(slug) + r'_[\w%.-]*?activity-(\d+)', page)
    ids, seen = [], set()
    for i in own:
        if i not in seen:
            seen.add(i); ids.append(i)
    posts, failed = [], []
    for i in ids[:LI_POST_CAP]:
        time.sleep(DELAY)
        try:
            posts.append(linkedin_post(i))
        except (error.HTTPError, error.URLError, ValueError) as e:
            failed.append((i, f"{type(e).__name__}: {e}"))
            if isinstance(e, error.HTTPError) and e.code in (999, 429):
                break  # throttled; stop rather than dig the hole deeper
    return {"platform": "linkedin", "kind": kind, "url": url, "profile": info,
            "posts": posts, "listed": len(ids), "failed": failed}


def linkedin_md(d: dict) -> str:
    p = d.get("profile") or {}
    lines = [f"# LinkedIn — {md_escape(p.get('name') or '')}  ({d['url']})", "",
             "Guest view: what LinkedIn serves without a login (the same pages search engines index). "
             "The full timeline is not public; only the recent posts the profile page lists are here.", ""]
    if p.get("headline"):
        lines.append(f"**{md_escape(p['headline'])}**")
    if p.get("about"):
        lines += ["", p["about"]]
    facts = [x for x in (p.get("location"), f"{p['followers']:,} followers" if isinstance(p.get("followers"), int) else None,
                         p.get("site") if isinstance(p.get("site"), str) else None) if x]
    if facts:
        lines += ["", "- " + "  ·  ".join(str(f) for f in facts)]
    if d.get("posts"):
        lines += ["", f"## Recent posts ({len(d['posts'])} of {d['listed']} listed)", ""]
        for x in d["posts"]:
            head = " · ".join(v for v in (x.get("when"), f"{x['reactions']:,} reactions" if isinstance(x.get("reactions"), int) else None) if v)
            lines += [f"### {md_escape(x.get('title') or x['id'])}", f"{head} · {x['url']}", "", x.get("text", ""), ""]
    for i, why in d.get("failed") or []:
        lines.append(f"- FAILED {i}: {why}")
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
    ap.add_argument("name", nargs="?")
    ap.add_argument("--github", help="user, @user, or a github.com URL")
    ap.add_argument("--bsky", help="handle, @name (bsky.social appended), or a bsky.app URL")
    ap.add_argument("--rss", action="append", default=[],
                    help="feed URL (repeatable); Reddit .rss, blogs, bridges. u/name and r/sub shorthand accepted")
    # Twitter is X. Every X flag has a --twitter spelling so a request phrased
    # either way lands on the same code.
    ap.add_argument("--x", "--twitter", dest="x",
                    help="X/Twitter handle or URL: the author's threads from Thread Reader's "
                         "public cache, plus an RSS mirror if given (X serves no timeline "
                         "without a login)")
    ap.add_argument("--x-post", "--tweet", "--twitter-post", action="append", default=[], dest="x_posts",
                    help="a post/tweet URL or id (repeatable); full text mirrored via the public embed endpoint")
    ap.add_argument("--x-thread", "--twitter-thread", dest="x_thread",
                    help="root post URL or id; the whole thread from Thread Reader's public cache, root only if not cached")
    ap.add_argument("--x-threads", type=int, default=5, metavar="N",
                    help="with --x: pull the N most recent threads the author has on Thread "
                         "Reader in full (default 5; 0 lists them only)")
    ap.add_argument("--x-rss-mirror", action="append", default=[], metavar="TEMPLATE",
                    help="Nitter-style RSS mirror to try for --x, e.g. "
                         "https://mirror.example/{handle}/rss (repeatable; also "
                         "SOCIALS_X_RSS, comma separated). None is built in")
    ap.add_argument("--linkedin", help="LinkedIn slug, in/slug, company/slug, or URL: guest view (profile + listed recent posts), link only if refused")
    ap.add_argument("--out", default="./socials")
    ap.add_argument("--json", action="store_true", help="also write structured .json per platform")
    ap.add_argument("--selftest", action="store_true", help="check the input cleaners and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.name:
        ap.error("name is required")

    # Normalise every input once, here, so the fetchers and the recorded links
    # never see a share parameter or a bare handle.
    if args.github:
        args.github = github_user(args.github)
    if args.bsky:
        args.bsky = bsky_handle(args.bsky)
    if args.x:
        args.x = x_url(args.x)
    if args.linkedin:
        args.linkedin = linkedin_url(args.linkedin)
    args.rss = [feed_url(u) for u in args.rss]

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
    if args.x_thread:
        def thread_or_root():
            try:
                return x_thread(args.x_thread)
            except (error.HTTPError, error.URLError, ValueError) as e:
                print(f"  thread not cached ({e}); mirroring the root post only", file=sys.stderr)
                return x_posts([args.x_thread] + args.x_posts)
        do("X/Twitter thread", thread_or_root, lambda d: x_md(args.x, d), "x-thread")
    if args.x_posts:
        do("X/Twitter", lambda: x_posts(args.x_posts), lambda d: x_md(args.x, d), "x")
    elif args.x and not args.x_thread:
        import os as _os
        templates = args.x_rss_mirror + [t.strip() for t in
                                         _os.environ.get("SOCIALS_X_RSS", "").split(",") if t.strip()]
        do("X/Twitter", lambda: x_profile(args.x, args.x_threads, templates), x_profile_md, "x")
    if args.linkedin:
        def li_or_link():
            try:
                return linkedin_public(args.linkedin)
            except (error.HTTPError, error.URLError, ValueError) as e:
                print(f"  LinkedIn guest view refused ({e}); recording the link only", file=sys.stderr)
                return None
        d = li_or_link()
        if d:
            do("LinkedIn", lambda: d, linkedin_md, "linkedin")
        else:
            write(out_dir, "linkedin", "md", linkonly_md("LinkedIn", args.linkedin)); index.append("- **LinkedIn**: [linkedin.md](linkedin.md) (link only)")

    write(out_dir, "index", "md", "\n".join(index) + "\n")
    print(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
