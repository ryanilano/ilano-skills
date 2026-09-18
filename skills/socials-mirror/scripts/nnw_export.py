#!/usr/bin/env python3
"""nnw_export — export articles NetNewsWire has ALREADY fetched, from its local
SQLite cache. Zero network: reads what your feeds pulled (every 15 min), no
re-scraping, no auth. Standard library only.

Why: if NetNewsWire is already subscribed to a feed and refreshing it, the full
post text is sitting in a local DB. Read that instead of hitting the server
again. Complements socials-mirror (which fetches public profiles live).

Usage:
  nnw_export.py --list                       # every feed + article count
  nnw_export.py --feed engadget              # export feeds matching text (title or url)
  nnw_export.py --feed 9to5mac --since 2026-09-01 --limit 50 --out ./feeds --json
  nnw_export.py --all --out ./feeds          # everything (large)

Secrets: any private key/token in a feed URL (e.g. ?key=…) is redacted in output.
Reads read-only (mode=ro); safe to run while NetNewsWire is open.
"""
from __future__ import annotations
import argparse, glob, html as _html, json, os, re, sqlite3, sys, time
from xml.etree import ElementTree as ET

NNW_BASE = os.path.expanduser(
    "~/Library/Containers/com.ranchero.NetNewsWire-Evergreen/Data/Library/"
    "Application Support/NetNewsWire/Accounts")

_SECRET_Q = re.compile(r"(?i)([?&](?:key|token|secret|password|auth|sig|apikey)=)[^&#]+")


def redact(url: str) -> str:
    return _SECRET_Q.sub(r"\1[REDACTED]", url or "")


def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s or "")
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", _html.unescape(s)).strip()


def author_names(authors_json: str) -> str:
    if not authors_json:
        return ""
    try:
        arr = json.loads(authors_json)
        return ", ".join(a.get("name", "") for a in arr if a.get("name")) or ""
    except (ValueError, TypeError, AttributeError):
        return ""


def iso(epoch) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(epoch)))
    except (ValueError, TypeError):
        return ""


def opml_feeds(path: str) -> dict:
    """xmlUrl -> {title, htmlUrl}."""
    out = {}
    if not os.path.exists(path):
        return out
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return out
    for o in root.iter("outline"):
        xml = o.get("xmlUrl")
        if xml:
            out[xml] = {"title": o.get("title") or o.get("text") or xml,
                        "html": o.get("htmlUrl") or ""}
    return out


def accounts() -> list[tuple[str, str, str]]:
    """(account_name, db_path, opml_path) for every local account."""
    res = []
    for db in glob.glob(os.path.join(NNW_BASE, "*", "DB.sqlite3")):
        acct = os.path.basename(os.path.dirname(db))
        res.append((acct, db, os.path.join(os.path.dirname(db), "Subscriptions.opml")))
    return res


def query(db: str, where: str, params: tuple, limit: int = None):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        sql = ("SELECT title, feedID, authors, datePublished, url, externalURL, "
               "contentHTML, contentText, summary FROM articles " + where +
               " ORDER BY datePublished DESC")
        p = list(params)
        if limit:
            sql += " LIMIT ?"; p.append(limit)
        return [dict(r) for r in con.execute(sql, tuple(p))]
    finally:
        con.close()


def article_text(row: dict) -> str:
    return strip_html(row.get("contentHTML")) or (row.get("contentText") or "").strip() \
        or strip_html(row.get("summary"))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "feed"


def cmd_list():
    rows = []
    for acct, db, opml in accounts():
        feeds = opml_feeds(opml)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            counts = dict(con.execute("SELECT feedID, count(*) FROM articles GROUP BY feedID"))
        finally:
            con.close()
        for fid, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            title = feeds.get(fid, {}).get("title", fid)
            rows.append((n, acct, title, redact(fid)))
    print(f"{'n':>5}  {'account':<8}  title  ·  url")
    for n, acct, title, url in rows:
        print(f"{n:>5}  {acct:<8}  {title}  ·  {url}")
    print(f"\n{len(rows)} feeds across {len(accounts())} accounts.", file=sys.stderr)


def cmd_export(args):
    since_epoch = None
    if args.since:
        since_epoch = int(time.mktime(time.strptime(args.since, "%Y-%m-%d")))
    total = 0
    out_root = args.out
    for acct, db, opml in accounts():
        feeds = opml_feeds(opml)
        where, params = "WHERE 1=1", []
        if args.feed:
            # match feedID or feed title
            matching = [fid for fid, meta in feeds.items()
                        if args.feed.lower() in fid.lower() or args.feed.lower() in meta["title"].lower()]
            if not matching:
                continue
            where += " AND feedID IN (%s)" % ",".join("?" * len(matching))
            params += matching
        if since_epoch:
            where += " AND datePublished >= ?"; params.append(since_epoch)
        rows = query(db, where, tuple(params), limit=args.limit)
        # group by feed
        byfeed: dict[str, list] = {}
        for r in rows:
            byfeed.setdefault(r["feedID"], []).append(r)
        for fid, arts in byfeed.items():
            meta = feeds.get(fid, {"title": fid, "html": ""})
            d = os.path.join(out_root, slug(meta["title"]))
            os.makedirs(d, exist_ok=True)
            lines = [f"# {meta['title']}  ({redact(fid)})",
                     f"account: {acct} · {len(arts)} articles from NetNewsWire's local cache", ""]
            jrows = []
            for r in arts:
                title, au, dt = r["title"] or "(untitled)", author_names(r["authors"]), iso(r["datePublished"])
                link = redact(r["externalURL"] or r["url"] or "")
                text = article_text(r)
                lines += [f"## {title}", f"{dt}{' · ' + au if au else ''} · {link}", "", text, ""]
                jrows.append({"title": r["title"], "author": au, "date": dt,
                              "url": link, "text": text})
            with open(os.path.join(d, "articles.md"), "w") as f:
                f.write("\n".join(lines) + "\n")
            if args.json:
                with open(os.path.join(d, "articles.json"), "w") as f:
                    json.dump({"feed": meta["title"], "url": redact(fid), "account": acct,
                               "articles": jrows}, f, indent=2)
            total += len(arts)
            print(f"  {meta['title']}: {len(arts)}", file=sys.stderr)
    print(out_root)
    print(f"exported {total} articles.", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export NetNewsWire's already-fetched articles from its local cache. Zero network.")
    ap.add_argument("--list", action="store_true", help="list every feed and its cached article count")
    ap.add_argument("--feed", help="export feeds whose title or url contains this text")
    ap.add_argument("--all", action="store_true", help="export every feed (large)")
    ap.add_argument("--since", help="only articles on/after YYYY-MM-DD")
    ap.add_argument("--limit", type=int, help="max articles per account")
    ap.add_argument("--out", default="./nnw-export")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not accounts():
        print("No NetNewsWire accounts found under the container.", file=sys.stderr)
        return 2
    if args.list:
        cmd_list(); return 0
    if args.feed or args.all:
        cmd_export(args); return 0
    ap.print_help(); return 1


if __name__ == "__main__":
    sys.exit(main())
