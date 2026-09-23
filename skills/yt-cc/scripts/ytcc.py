#!/usr/bin/env python3
"""yt-cc: transcript-first video board + CLI. Portable (macOS/Linux/WSL), stdlib only.

Three modes, one file:
  ytcc.py <url>                  one video: captions + description + metadata;
                                 prints the saved transcript.md path to stdout
  ytcc.py <channel-or-playlist>  every video on it, newest first, skipping ones
                                 already in the store; prints the store path
  ytcc.py serve                  web board on $YTCC_HOST:$YTCC_PORT (127.0.0.1:8091)

A /@handle, /channel/, /c/, /user/, /playlist or list= URL is taken as a
collection automatically. Flags:
  --channel, --all     force collection mode (a watch?v=...&list=... link)
  -n N, --limit N      newest N only. Use it the first time on an unknown channel
  --delay S            seconds between videos in collection mode (default 1.5)
  --video, -v          also download the mp4 (slow, large)
  -d DIR, --dir DIR    write to DIR instead of the store
  --selftest           check the URL cleaner against known link forms

Any link form works: youtu.be, /shorts/, /live/, m.youtube.com, a bare
11-character video id, a bare @handle. Share and tracking parameters (si=,
feature=, utm_*, fbclid…) are stripped before the URL is used or stored.

Every grab saves the video description, upload date, view count, tags and
chapters. A video with no English captions still gets its description and
metadata saved; the transcript is simply absent.

Env: YTCC_STORE (default $XDG_DATA_HOME/yt-cc), YTCC_HOST, YTCC_PORT,
     YTCC_COOKIES_BROWSER (chrome/safari/brave -> fixes 403 on video download).
Needs: python3 + yt-dlp (PATH or `python3 -m yt_dlp`).
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse


def _env(k, d=""):
    return os.environ.get(k, d).strip()


def store_dir():
    s = _env("YTCC_STORE")
    if s:
        p = Path(s).expanduser()
    else:
        base = _env("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        p = Path(base) / "yt-cc"
    p.mkdir(parents=True, exist_ok=True)
    return p


STORE = store_dir()
HOST = _env("YTCC_HOST") or "127.0.0.1"
PORT = int(_env("YTCC_PORT") or "8091")
COOKIES_BROWSER = _env("YTCC_COOKIES_BROWSER")
TAG_RE = re.compile(r"<[^>]+>")
TS_RE = re.compile(r"^\d\d:\d\d:\d\d\.\d+ --> ")


# ---------------------------------------------------------------------------
# URL cleaning
#
# A pasted link carries the sharer, not the video: youtu.be/ID?si=…, a
# feature=share, utm_* from a newsletter, an fbclid. None of it changes which
# captions come back, but it does leak who shared the link into meta.json and
# every note that quotes the URL. So every URL is cleaned before yt-dlp sees
# it and before it is written anywhere.
#
# The same function accepts the short forms people actually type: a bare
# 11-character video id, a bare @handle, a youtu.be link, a /shorts/ or /live/
# link, and unfolds them to the one canonical form yt-dlp and the store use.
# ---------------------------------------------------------------------------

# Query keys that identify the click or the sharer, never the content.
TRACKING_KEYS = {"si", "feature", "pp", "fbclid", "gclid", "dclid", "msclkid",
                 "igsh", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "ref_url",
                 "source", "s", "_hsenc", "_hsmi", "mkt_tok", "yclid", "twclid"}
# Keys that still mean something on a YouTube watch URL.
WATCH_KEYS = ("v", "list", "t")
YT_HOSTS = ("youtube.com", "youtube-nocookie.com", "youtu.be")
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_HANDLE_RE = re.compile(r"^@[\w.-]{3,}$")
YT_CHANNEL_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
YT_PLAYLIST_RE = re.compile(r"^(?:PL|UU|LL|RD|OL|FL)[A-Za-z0-9_-]{8,}$")


def _keep_query(pairs, allow=None):
    """Drop tracking keys (and utm_*); with `allow`, keep only those keys, in that order."""
    kept = [(k, v) for k, v in pairs
            if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_")]
    if allow is not None:
        by_key = dict(kept)
        kept = [(k, by_key[k]) for k in allow if k in by_key]
    return kept


def clean_url(raw):
    """Canonical form of whatever was pasted. Never raises; unknown input passes through.

    Bare forms:  dQw4w9WgXcQ  ->  https://www.youtube.com/watch?v=dQw4w9WgXcQ
                 @AZisk       ->  https://www.youtube.com/@AZisk
                 PLxxxx…      ->  https://www.youtube.com/playlist?list=PLxxxx…
                 UCxxxx…      ->  https://www.youtube.com/channel/UCxxxx…
    Short forms: youtu.be/ID, /shorts/ID, /live/ID, /embed/ID, m.youtube.com
                 all become www.youtube.com/watch?v=ID (list= and t= kept).
    Every host:  si, feature, utm_*, fbclid and the like are removed.
    """
    s = (raw or "").strip().strip("<>").strip()
    if not s:
        return s
    if YT_ID_RE.match(s):
        return f"https://www.youtube.com/watch?v={s}"
    if YT_HANDLE_RE.match(s):
        return f"https://www.youtube.com/{s}"
    if YT_CHANNEL_RE.match(s):
        return f"https://www.youtube.com/channel/{s}"
    if YT_PLAYLIST_RE.match(s):
        return f"https://www.youtube.com/playlist?list={s}"
    if "://" not in s:
        s = "https://" + s.lstrip("/")
    u = urlparse(s)
    host = u.netloc.lower().split("@")[-1].split(":")[0]
    pairs = parse_qsl(u.query, keep_blank_values=False)
    path = u.path or "/"

    if not (host in YT_HOSTS or any(host.endswith("." + h) for h in YT_HOSTS)):
        return urlunparse((u.scheme, u.netloc, u.path, "", urlencode(_keep_query(pairs)), ""))

    vid = None
    if host == "youtu.be":
        vid = path.strip("/").split("/")[0]
    else:
        m = re.match(r"^/(?:shorts|live|embed|v)/([A-Za-z0-9_-]{11})(?:/|$)", path)
        if m:
            vid = m.group(1)
        elif path.rstrip("/") in ("/watch", "/attribution_link"):
            vid = dict(pairs).get("v")

    if vid and YT_ID_RE.match(vid):
        q = [("v", vid)] + [(k, v) for k, v in _keep_query(pairs, WATCH_KEYS) if k != "v"]
        return "https://www.youtube.com/watch?" + urlencode(q)

    # Channel, playlist, handle and tab URLs: keep the path, keep list=, drop the rest.
    q = _keep_query(pairs, ("list", "index") if path.rstrip("/") == "/playlist" else ("list",))
    path = re.sub(r"/+$", "", path) or "/"
    return urlunparse(("https", "www.youtube.com", path, "", urlencode(q), ""))


def selftest():
    """Exercise clean_url on the forms that show up in practice. Exit 1 on any miss."""
    W = "https://www.youtube.com/watch?v=QbtScohcdwI"
    cases = [
        ("https://youtu.be/TBOtZ3mBktM?si=qih-rLmYPaiSom9s", "https://www.youtube.com/watch?v=TBOtZ3mBktM"),
        ("https://youtu.be/QbtScohcdwI", W),
        ("https://www.youtube.com/watch?v=QbtScohcdwI&feature=share&utm_source=nl", W),
        ("https://m.youtube.com/watch?v=QbtScohcdwI&pp=ygUFYWxleA%3D%3D", W),
        ("https://www.youtube.com/watch?si=abc&t=95&v=QbtScohcdwI", W + "&t=95"),
        ("https://www.youtube.com/watch?v=QbtScohcdwI&list=PLabcdefghij&index=3&si=x",
         W + "&list=PLabcdefghij"),
        ("https://www.youtube.com/shorts/QbtScohcdwI?feature=share", W),
        ("https://www.youtube.com/live/QbtScohcdwI?si=zz", W),
        ("https://www.youtube-nocookie.com/embed/QbtScohcdwI?rel=0", W),
        ("QbtScohcdwI", W),
        ("@AZisk", "https://www.youtube.com/@AZisk"),
        ("youtube.com/@AZisk/videos?si=abc", "https://www.youtube.com/@AZisk/videos"),
        ("https://www.youtube.com/@AZisk/", "https://www.youtube.com/@AZisk"),
        ("https://www.youtube.com/playlist?list=PLabcdefghij&si=abc", "https://www.youtube.com/playlist?list=PLabcdefghij"),
        ("PLabcdefghij", "https://www.youtube.com/playlist?list=PLabcdefghij"),
        ("UCajiMK_CY9icRhLepS8_3ug", "https://www.youtube.com/channel/UCajiMK_CY9icRhLepS8_3ug"),
        ("https://vimeo.com/123456?utm_campaign=x&fbclid=y", "https://vimeo.com/123456"),
        ("https://example.com/talk?id=7&ref=tw", "https://example.com/talk?id=7"),
        ("  <https://youtu.be/QbtScohcdwI?si=1>  ", W),
        ("", ""),
    ]
    bad = [(i, o, clean_url(i)) for i, o in cases if clean_url(i) != o]
    for i, want, got in bad:
        print(f"FAIL {i!r}\n  want {want}\n  got  {got}", file=sys.stderr)
    print(f"clean_url: {len(cases) - len(bad)}/{len(cases)} ok", file=sys.stderr)
    return 1 if bad else 0


def ytdlp_base():
    """Resolve yt-dlp: prefer the binary, fall back to `python3 -m yt_dlp`."""
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                           capture_output=True, timeout=20)
        if r.returncode == 0:
            return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        pass
    return None


YTDLP = ytdlp_base()


def run(args, timeout=180):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def parse_vtt(path):
    """VTT -> [(start_seconds, text)] with rollup dedupe."""
    cues, last = [], ""
    start = 0.0
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if TS_RE.match(line):
            h, m, s = line.split(" --> ")[0].split(":")
            start = int(h) * 3600 + int(m) * 60 + float(s)
            continue
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        text = TAG_RE.sub("", line).strip()
        if text and text != last:
            cues.append((start, text))
            last = text
    return cues


def _mmss(secs):
    secs = int(secs or 0)
    return f"{secs // 60:02d}:{secs % 60:02d}"


def to_markdown(meta, cues):
    """transcript.md: header, description, chapters, then the captions.

    The description goes first because it is often the easy win: links, the
    tool list, the sponsor, the correction the creator pinned. A reader who
    only needs those never has to scroll the transcript.
    """
    up = str(meta.get("upload_date") or "")
    when = f"{up[0:4]}-{up[4:6]}-{up[6:8]}" if len(up) == 8 and up.isdigit() else "?"
    lines = [f"# {meta['title']}", "",
             f"Channel: {meta.get('channel', '?')} · Duration: {meta.get('duration_string', '?')} · Published: {when} · {meta['url']}",
             f"Grabbed: {meta['grabbed']} · Source: {meta['sub_source']}", ""]
    desc = (meta.get("description") or "").strip()
    if desc:
        lines += ["## Description", "", desc, ""]
    chapters = meta.get("chapters") or []
    if chapters:
        lines += ["## Chapters", ""]
        lines += [f"- **[{_mmss(c['t'])}]** {c['title']}" for c in chapters]
        lines.append("")
    if cues:
        lines += ["## Transcript", ""]
    mark = -60
    for start, text in cues:
        if start - mark >= 60:
            mark = start
            lines.append(f"\n**[{int(start // 60):02d}:{int(start % 60):02d}]** {text}")
        else:
            lines.append(text)
    return "\n".join(lines) + "\n"


def grab(url, want_video=False):
    if YTDLP is None:
        return {"error": "yt-dlp not found (PATH or `python3 -m yt_dlp`). "
                         "macOS: brew install yt-dlp · Debian/WSL: pipx install yt-dlp"}
    j = run(YTDLP + ["-J", "--skip-download", "--no-playlist", url])
    if j.returncode != 0:
        return {"error": (j.stderr or "yt-dlp failed").strip()[-400:]}
    info = json.loads(j.stdout)
    vid = info["id"]
    d = STORE / vid
    d.mkdir(parents=True, exist_ok=True)

    run(YTDLP + ["--skip-download", "--no-playlist", "--write-subs",
                 "--write-auto-subs", "--sub-langs", "en.*,en", "--sub-format", "vtt",
                 "-o", str(d / "%(id)s"), url])
    vtts = sorted(d.glob(f"{vid}*.vtt"))
    if vtts:
        manual = [v for v in vtts if ".en.vtt" in v.name or v.name == f"{vid}.en.vtt"]
        src = "manual captions" if manual else "auto captions"
        cues = parse_vtt(vtts[0])
    else:
        src, cues = "no captions", []

    # Everything yt-dlp already handed back in that one -J call. The
    # description is the point: it carries the links, the tool list, the
    # pinned correction. Chapters give a table of contents for free.
    meta = {"id": vid, "title": info.get("title", vid),
            "channel": info.get("channel") or info.get("uploader", "?"),
            "duration_string": info.get("duration_string", "?"),
            "url": info.get("webpage_url", url),
            "upload_date": info.get("upload_date") or "",
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "tags": (info.get("tags") or [])[:30],
            "description": (info.get("description") or "").strip(),
            "chapters": [{"t": int(c.get("start_time") or 0), "title": c.get("title", "")}
                         for c in (info.get("chapters") or [])],
            "grabbed": time.strftime("%Y-%m-%d %H:%M"),
            "sub_source": src, "cue_count": len(cues)}
    # Written even with no captions: a description and its links are worth
    # having, and the Source line says plainly that the transcript is absent.
    (d / "transcript.md").write_text(to_markdown(meta, cues))
    transcript_payload = {"cues": [{"t": round(t, 1), "text": x} for t, x in cues]}
    if want_video and not list(d.glob("video.*")):
        cmd = YTDLP + ["--no-playlist", "-f", "bv*+ba/b",
                       "-S", "res:1080,vcodec:h264,acodec:aac,ext:mp4",
                       "--extractor-args", "youtube:player_client=web_embedded,default",
                       "--merge-output-format", "mp4", "--remux-video", "mp4"]
        if COOKIES_BROWSER:
            cmd += ["--cookies-from-browser", COOKIES_BROWSER]
        cmd += ["-o", str(d / "video.%(ext)s"), url]
        vres = run(cmd, timeout=1800)
        if not list(d.glob("video.*")) and vres.returncode != 0:
            err = ("video download failed (likely YouTube 403/PO-token). "
                   "Set YTCC_COOKIES_BROWSER=chrome (or safari/brave) and retry. Captions still saved.")
            (d / "video_error.txt").write_text(err + "\n" + (vres.stderr or "")[-500:])
    meta["has_video"] = bool(list(d.glob("video.*")))
    thumb = info.get("thumbnail")
    if thumb and not (d / "thumb.jpg").exists():
        try:
            urllib.request.urlretrieve(thumb, d / "thumb.jpg")
        except OSError:
            pass
    (d / "transcript.json").write_text(json.dumps({"meta": meta, **transcript_payload}, indent=1))
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


# ---------------------------------------------------------------------------
# Whole-channel mode
#
# Everything above this line handles exactly one video. `grab()` passes
# --no-playlist to yt-dlp on every call, which is the correct behavior for a
# single URL: if you paste a link that happens to sit inside a playlist, you
# want that one video, not the other four hundred.
#
# The side effect was that there was no way at all to say "take this entire
# channel". That single flag was the whole distance between this skill and a
# backlog of a few thousand Theo or Wendell videos.
#
# The three functions below add that, in the order they run:
#
#   looks_multi()       Is this URL a channel, or one video?
#   enumerate_videos()  Ask YouTube for the list of video IDs. One request.
#   grab_many()         Loop that list through the existing grab(), politely.
#
# Nothing above this line changed, so a single-video grab behaves exactly as
# it always did.
# ---------------------------------------------------------------------------

# Substrings that only ever appear in a URL pointing at a COLLECTION of videos.
#   /@handle      the modern channel URL, e.g. youtube.com/@t3dotgg
#   /channel/UC…  the old channel URL, still used everywhere
#   /c/, /user/   two older channel URL styles YouTube never removed
#   /playlist     an explicit playlist page
#   list=         a playlist ID riding along in the query string
MULTI_HINTS = ("/@", "/channel/", "/playlist", "/c/", "/user/", "list=")


def looks_multi(url):
    """Decide whether a URL means one video or many.

    Returns True for a channel or playlist, False for a single video. This is
    what lets you paste either kind of link and have the right thing happen
    without passing a flag.

    The one genuinely ambiguous case is a URL like:

        youtube.com/watch?v=abc123&list=PLxyz

    which is a single video that YouTube happens to be showing you from inside
    a playlist. There is no universally right answer, so the rule here is: a
    bare watch?v= link is one video, but if a list= is attached, treat it as
    the playlist. Pass --channel to force multi mode either way.
    """
    u = url.lower()

    # A plain watch link with no playlist attached is unambiguously one video.
    if "watch?v=" in u and "list=" not in u:
        return False

    return any(h in u for h in MULTI_HINTS)


def enumerate_videos(url, limit=None):
    """Ask YouTube which videos are on a channel or playlist.

    Returns (videos, error). `videos` is a list of dicts with id, title and
    url, newest first. `error` is None on success, or a string to show the
    user. Returning both rather than raising keeps this consistent with
    grab(), which also reports failure as data.

    The important flag is --flat-playlist. Without it, yt-dlp visits every
    single video to collect its full metadata, so listing a 2,000 video
    channel would cost 2,000 requests before a single transcript is fetched.
    With it, YouTube hands back the whole listing in ONE request, containing
    just enough per video (id and title) to do the work.

    --ignore-errors means one dead or private video in the middle of a channel
    does not abort the entire listing.
    """
    # A bare channel URL (youtube.com/@handle) lists the channel's TABS
    # (Videos, Shorts, Live) as nested playlists, not its videos. Point at
    # the Videos tab unless the caller already named a tab or a playlist.
    u = url.rstrip("/")
    if (any(h in u for h in ("/@", "/channel/", "/c/", "/user/"))
            and "list=" not in u
            and not u.endswith(("/videos", "/shorts", "/streams", "/live", "/playlists"))):
        url = u + "/videos"

    cmd = YTDLP + ["-J", "--flat-playlist", "--ignore-errors"]

    # --playlist-end is yt-dlp's "stop after N", applied while listing rather
    # than after, so a --limit 5 really is a small request.
    if limit:
        cmd += ["--playlist-end", str(limit)]

    # 600s because listing a very large channel genuinely can take minutes,
    # unlike a single video grab which uses the default 180s.
    j = run(cmd + [url], timeout=600)

    # --ignore-errors makes yt-dlp exit non-zero when it skipped something,
    # even though the listing itself succeeded. So only treat a non-zero exit
    # as fatal when there is also no output to parse.
    if j.returncode != 0 and not j.stdout.strip():
        return [], (j.stderr or "yt-dlp failed to list").strip()[-400:]

    try:
        info = json.loads(j.stdout)
    except json.JSONDecodeError as exc:
        return [], f"could not parse listing: {exc}"

    out = []
    for e in info.get("entries") or []:
        # Skipped or unavailable videos come back as null entries.
        if not e:
            continue
        vid = e.get("id")
        if vid:
            out.append({
                "id": vid,
                "title": e.get("title", vid),
                # Flat listings sometimes omit the full URL, so rebuild it from
                # the id. grab() needs a real watch URL, not a bare id.
                "url": e.get("url") or f"https://www.youtube.com/watch?v={vid}",
            })
    return out, None


def grab_many(url, want_video=False, limit=None, delay=1.5):
    """Grab every video in a channel or playlist.

    Returns a summary dict: how many were listed, grabbed, skipped and failed,
    plus the failures themselves so nothing disappears silently.

    Two design choices worth knowing about:

    SAFE TO RE-RUN. Before fetching anything, this checks whether that video
    already has a transcript.json on disk and skips it if so. Running this
    again next week costs one listing request plus whatever is new, so it can
    go on a schedule without re-downloading a backlog every time.

    DELIBERATELY SLOW. `delay` pauses between videos. Running a full channel
    is thousands of requests to somebody else's servers, and the difference
    between 1.5s and 0s is the difference between a polite backlog fetch and
    getting the IP rate-limited halfway through.

    One failure never stops the run. A video with no English captions is
    counted, reported at the end, and the loop moves on.
    """
    vids, err = enumerate_videos(url, limit)
    if err:
        return {"error": err}
    if not vids:
        return {"error": f"no videos found at {url}"}

    done = skipped = failed = 0
    failures = []

    # Progress goes to stderr so stdout stays clean for the final path, which
    # is the repo convention: status to stderr, data to stdout.
    print(f"yt-cc: {len(vids)} video(s) listed", file=sys.stderr)

    for n, v in enumerate(vids, 1):
        # The skip check. transcript.json is written last by grab(), so its
        # presence means that video finished cleanly rather than half-wrote.
        if (STORE / v["id"] / "transcript.json").exists():
            skipped += 1
            continue

        # Reuse the existing single-video path rather than duplicating it, so
        # channel mode and single mode can never drift apart.
        r = grab(v["url"], want_video)

        if "error" in r:
            failed += 1
            failures.append((v["id"], r["error"][:120]))
            print(f"  [{n}/{len(vids)}] FAIL {v['id']}: {r['error'][:90]}", file=sys.stderr)
        else:
            done += 1
            print(f"  [{n}/{len(vids)}] {r['title'][:70]} ({r['cue_count']} cues)", file=sys.stderr)
        time.sleep(delay)
    return {"listed": len(vids), "grabbed": done, "skipped": skipped,
            "failed": failed, "failures": failures}


def cards():
    out = []
    for d in STORE.iterdir():
        m = d / "meta.json"
        if m.exists():
            meta = json.loads(m.read_text())
            meta["mtime"] = m.stat().st_mtime
            out.append(meta)
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


BOARD_CSS = """
:root {
  --yellow:#fff102; --ink:#0b0b0b; --paper:#fff; --dim:#62666e; --rule:#d8d5cd;
  --card:#fff; --link:#0b5fa5; --chip:#f3f1ea; --shadow:rgba(0,0,0,.09);
}
:root[data-theme="dark"] {
  --yellow:#ffe814; --ink:#f2f4f7; --paper:#0e1013; --dim:#8b939f; --rule:#262c35;
  --card:#14181d; --link:#79b8ff; --chip:#1a1f26; --shadow:rgba(0,0,0,.6);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --yellow:#ffe814; --ink:#f2f4f7; --paper:#0e1013; --dim:#8b939f; --rule:#262c35;
    --card:#14181d; --link:#79b8ff; --chip:#1a1f26; --shadow:rgba(0,0,0,.6);
  }
}
* { box-sizing:border-box; }
body { background:var(--paper); color:var(--ink); margin:0;
  font:1rem/1.5 -apple-system,system-ui,"Helvetica Neue",sans-serif; }
a { color:inherit; }
:focus-visible { outline:3px solid var(--link); outline-offset:2px; }
.masthead :focus-visible { outline-color:#0b0b0b; }
.vh { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);
  white-space:nowrap; }
.skip { position:absolute; left:-9999px; top:0; background:var(--ink); color:var(--paper);
  padding:.6rem 1rem; z-index:20; }
.skip:focus { left:1rem; top:1rem; }
@media (prefers-reduced-motion:reduce) {
  *,*::before,*::after { transition:none!important; scroll-behavior:auto!important; }
}
.masthead { background:var(--yellow); }
.mast-inner { max-width:78rem; margin:0 auto; padding:.6rem 1.25rem;
  display:flex; align-items:center; gap:1.5rem; }
.wordmark { font:800 2.1rem/1 Charter,"Iowan Old Style",Georgia,serif; color:#0b0b0b;
  letter-spacing:-.03em; text-decoration:none; }
.wordmark span { color:#0b0b0b; }
.mastnav { display:flex; gap:0; flex:1; flex-wrap:wrap;
  font:700 .78rem/1 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.04em; }
.mastnav a { color:#0b0b0b; text-decoration:none; padding:.4rem .9rem;
  border-left:1px solid rgba(0,0,0,.35); }
.mastnav a:first-child { border-left:0; }
.mastnav a:hover { text-decoration:underline; }
.tbtn { background:transparent; border:1px solid rgba(0,0,0,.5); color:#0b0b0b;
  border-radius:99px; min-width:2.75rem; min-height:2.75rem; cursor:pointer; font-size:.9rem; flex:none; }
.strip { max-width:78rem; margin:0 auto; padding:1rem 1.25rem .9rem;
  font:.78rem/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--dim);
  letter-spacing:.02em; }
.strip b { color:var(--ink); }
.wrap { max-width:78rem; margin:0 auto; padding:0 1.25rem 5rem; }
.three { display:grid; grid-template-columns:17rem minmax(0,1fr) 19rem; gap:2rem;
  align-items:start; padding-top:.5rem; }
.boxhead { font:700 .78rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:.14em; text-transform:uppercase; margin:0 0 1rem; }
.starthere { border:1px solid var(--rule); padding:1.1rem 1.15rem 1.25rem; }
.startlist { list-style:none; margin:0; padding:0; }
.startlist li { display:grid; grid-template-columns:1.5rem 1fr; gap:.6rem;
  padding:.75rem 0; border-top:1px solid var(--rule); }
.startlist li:first-child { border-top:0; padding-top:0; }
.num { width:1.4rem; height:1.4rem; border-radius:50%; background:var(--yellow); color:#0b0b0b;
  font:700 .72rem/1.4rem ui-monospace,monospace; text-align:center; }
.startlist a { font:600 .92rem/1.35 Charter,Georgia,serif; text-decoration:none;
  display:block; margin-bottom:.2rem; }
.startlist a:hover { text-decoration:underline; }
.tiny { display:block; font-size:.68rem; color:var(--dim);
  font-family:ui-monospace,monospace; letter-spacing:.02em; }
.grabform { display:flex; gap:.4rem; flex-wrap:wrap; margin-top:1.1rem;
  padding-top:1rem; border-top:1px solid var(--rule); }
.grabform input[name=url] { flex:1 1 100%; background:var(--chip); color:var(--ink);
  border:1px solid var(--rule); padding:.5rem .6rem; font-size:.85rem; border-radius:2px; }
.vid { font-size:.72rem; color:var(--dim); display:flex; align-items:center; gap:.3rem; }
.grab { background:var(--ink); color:var(--paper); border:0; padding:.45rem 1rem;
  font:700 .75rem/1 ui-monospace,monospace; letter-spacing:.08em; text-transform:uppercase;
  cursor:pointer; margin-left:auto; }
.hero { min-width:0; }
.hero-img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; background:#000; }
.kicker { font:700 .7rem/1 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.14em;
  text-transform:uppercase; color:var(--dim); margin:1rem 0 .6rem; text-align:center; }
.hero-h { font:700 2.5rem/1.08 Charter,"Iowan Old Style",Georgia,serif; letter-spacing:-.025em;
  margin:0 0 .6rem; text-align:center; }
.hero-h a { text-decoration:none; }
.hero-h a:hover { text-decoration:underline; }
.hero-sub { font:1.05rem/1.4 Charter,Georgia,serif; color:var(--dim); text-align:center;
  margin:0 0 .7rem; }
.hero-by { font:.72rem/1 ui-monospace,monospace; letter-spacing:.06em; text-transform:uppercase;
  color:var(--dim); text-align:center; margin:0; }
.hero-by a { color:var(--link); }
.rail { border-left:1px solid var(--rule); padding-left:1.5rem; }
.railitem { display:grid; grid-template-columns:1fr 5.5rem; gap:.75rem;
  padding:.9rem 0; border-bottom:1px solid var(--rule); align-items:start; }
.railitem:first-child { padding-top:0; }
.label { font:700 .64rem/1 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.12em;
  text-transform:uppercase; color:var(--dim); margin:0 0 .35rem; }
.railitem h3 { font:700 .95rem/1.25 Charter,Georgia,serif; margin:0; }
.railitem h3 a { text-decoration:none; }
.railitem h3 a:hover { text-decoration:underline; }
.railthumb img { width:5.5rem; height:3.2rem; object-fit:cover; display:block; background:#000; }
.railthumb.noimg img { display:none; }
.ruler { border:0; border-top:2px dotted var(--rule); margin:2.75rem 0 1.5rem; }
.allhead { display:flex; align-items:center; gap:1rem; margin-bottom:1.25rem; flex-wrap:wrap; }
.allhead .boxhead { margin:0; }
#filter { flex:1; min-width:12rem; max-width:22rem; background:var(--chip); color:var(--ink);
  border:1px solid var(--rule); padding:.45rem .65rem; font-size:.85rem; border-radius:2px; }
#filter:focus-visible { outline:3px solid var(--link); outline-offset:2px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(16rem,1fr));
  gap:2rem 1.5rem; align-items:start; }
.card { background:var(--card); min-width:0; }
.posterlink { display:block; position:relative; line-height:0; }
.poster { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; background:#05070a; }
.posterlink.noimg .poster { display:none; }
.posterlink.noimg::before { content:""; display:block; aspect-ratio:16/9; background:var(--chip); }
.dur { position:absolute; right:.4rem; bottom:.4rem; background:rgba(4,6,9,.85); color:#fff;
  font:.65rem/1 ui-monospace,monospace; padding:.2rem .35rem; }
.body { padding:.7rem 0 0; }
.t { font:700 1rem/1.28 Charter,Georgia,serif; margin:0 0 .35rem; }
.t a { text-decoration:none; }
.t a:hover { text-decoration:underline; }
.dim { color:var(--dim); font:.7rem/1.4 ui-monospace,monospace; letter-spacing:.02em;
  margin:0 0 .6rem; }
.row { display:flex; gap:.3rem; flex-wrap:wrap; padding-top:.55rem;
  border-top:1px dotted var(--rule); }
.btn { background:transparent; color:var(--dim); border:1px solid var(--rule); border-radius:2px;
  font:.68rem/1 ui-monospace,monospace; letter-spacing:.04em; text-transform:uppercase;
  padding:.3rem .5rem; text-decoration:none; cursor:pointer; }
.btn:hover { background:var(--yellow); color:#0b0b0b; border-color:var(--yellow); }
.btn.src:hover { background:var(--ink); color:var(--paper); border-color:var(--ink); }
.msg { border-left:4px solid var(--yellow); background:var(--chip); padding:.65rem .9rem;
  margin:1rem 0; font-size:.85rem; }
.msg.err { border-left-color:#d2413a; }
@media (max-width:70rem) {
  .three { grid-template-columns:1fr; gap:2.5rem; }
  .rail { border-left:0; padding-left:0; border-top:2px dotted var(--rule); padding-top:1.5rem; }
  .hero-h { font-size:2.1rem; }
}
@media (max-width:34rem) {
  .wordmark { font-size:1.7rem; }
  .hero-h { font-size:1.65rem; }
  .grid { grid-template-columns:1fr; gap:1.75rem; }
  .wrap, .strip, .mast-inner { padding-left:.9rem; padding-right:.9rem; }
}
"""


def total_minutes():
    """Sum duration_string across the store. Accepts H:MM:SS, M:SS, and "9 min"."""
    total = 0
    for c in cards():
        d = str(c.get("duration_string") or "")
        if ":" in d:
            parts = [int(x) for x in d.split(":") if x.isdigit()]
            if len(parts) == 3:
                total += parts[0] * 60 + parts[1]
            elif len(parts) == 2:
                total += parts[0]
        else:
            m = re.match(r"(\d+)", d)
            if m:
                total += int(m.group(1))
    return f"{total:,}"


def page(msg=""):
    e = html.escape
    cs = cards()

    def views_of(c):
        n = c.get("view_count")
        if not isinstance(n, int):
            return ""
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M views"
        if n >= 1_000:
            return f"{n // 1000}K views"
        return f"{n} views"

    def when_of(c):
        d = str(c.get("upload_date") or "")
        return f"{d[0:4]}.{d[4:6]}.{d[6:8]}" if len(d) == 8 and d.isdigit() else ""

    def meta_line(c):
        return " · ".join(x for x in (when_of(c), views_of(c)) if x)

    def poster(c, cls="poster"):
        cid = e(c["id"])
        if c.get("has_video"):
            return (f"<video class='{cls}' controls preload='none' poster='/thumb/{cid}.jpg' "
                    f"src='/video/{cid}.mp4'></video>")
        # The poster repeats the title link beside it, so it is hidden from
        # assistive tech and the tab order rather than announced twice.
        return (f"<a class='posterlink' href='/read/{cid}' aria-hidden='true' tabindex='-1'>"
                f"<img class='{cls}' src='/thumb/{cid}.jpg' alt='' loading='lazy' "
                f"onerror=\"this.closest('.posterlink').classList.add('noimg')\">"
                f"<span class='dur'>{e(c.get('duration_string', ''))}</span></a>")

    hero = cs[0] if cs else None
    rail = cs[1:6]
    rest = cs[6:]

    channels = {}
    for c in cs:
        channels[c.get("channel", "?")] = channels.get(c.get("channel", "?"), 0) + 1
    chan_nav = ("<a href='/channel'>Channels</a><a href='/topic'>Topics</a>"
                + "".join(f"<a href='/channel/{slugify(k)}'>{e(k)}</a>"
                          for k, _ in sorted(channels.items(), key=lambda kv: -kv[1])[:3]))

    hero_html = f"""
<section class="hero">
  {poster(hero, "poster hero-img")}
  <p class="kicker">{e(hero.get('channel', ''))}</p>
  <h2 class="hero-h"><a href="/read/{e(hero['id'])}">{e(hero['title'])}</a></h2>
  <p class="hero-sub">{e(hero.get('duration_string', ''))} · {e(hero.get('sub_source', ''))} · {e(meta_line(hero))}</p>
  <p class="hero-by">Transcript · <a href="{e(hero['url'])}" target="_blank" rel="noopener">watch the original<span class="vh"> (opens in a new tab)</span></a></p>
</section>""" if hero else "<section class='hero'><p class='dim'>nothing grabbed yet</p></section>"

    start_here = "".join(f"""
  <li><span class="num">{i}</span>
      <a href="/read/{e(c['id'])}">{e(c['title'])}</a>
      <span class="tiny">{e(c.get('channel', ''))} · {e(c.get('duration_string', ''))}</span></li>"""
        for i, c in enumerate(cs[:4], 1))

    rail_html = "".join(f"""
  <article class="railitem">
    <div class="railtext">
      <p class="label">{e(c.get('channel', ''))}</p>
      <h3><a href="/read/{e(c['id'])}">{e(c['title'])}</a></h3>
    </div>
    <a class="railthumb posterlink" href="/read/{e(c['id'])}" aria-hidden="true" tabindex="-1">
      <img src="/thumb/{e(c['id'])}.jpg" alt="" loading="lazy"
           onerror="this.closest('.posterlink').classList.add('noimg')"></a>
  </article>""" for c in rail)

    grid_html = "".join(f"""
<article class="card" data-channel="{e(c.get('channel', ''))}" data-title="{e(c['title'].lower())}">
  {poster(c)}
  <div class="body">
    <p class="label">{e(c.get('channel', '?'))}</p>
    <h3 class="t"><a href="/read/{e(c['id'])}">{e(c['title'])}</a></h3>
    <p class="dim">{e(meta_line(c))}{' · ' if meta_line(c) else ''}{e(c.get('sub_source', ''))}</p>
    <div class="row">
      <a class="btn" href="/read/{e(c['id'])}">read</a>
      <button class="btn" onclick="copyT('{e(c['id'])}','md',this)">copy</button>
      <a class="btn" href="/t/{e(c['id'])}.md">raw</a>
      {("<a class='btn' href='/video/" + e(c['id']) + ".mp4' download>video</a>") if c.get('has_video') else ""}
      <a class="btn src" href="{e(c['url'])}" target="_blank" rel="noopener">source <span aria-hidden="true">↗</span><span class="vh"> (opens in a new tab)</span></a>
    </div>
  </div>
</article>""" for c in rest)

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>yt-cc</title><style>{BOARD_CSS}</style></head><body>
<a class="skip" href="#main">Skip to content</a>
<header>
  <div class="masthead"><div class="mast-inner">
    <a class="wordmark" href="/" aria-label="yt-cc, front page">yt<span aria-hidden="true">·</span>cc</a>
    <nav class="mastnav" aria-label="Browse">{chan_nav}<a href="#all">Archive</a></nav>
    <button type="button" class="tbtn" id="theme" aria-label="Switch between light and dark theme"><span aria-hidden="true">◐</span></button>
  </div></div>
  <p class="strip"><b>Making sense of it all:</b> {len(cs)} transcripts / {total_minutes()} minutes / captions only, nothing streamed</p>
</header>

<main class="wrap" id="main">
  <h1 class="vh">yt-cc transcripts</h1>
  {msg}
  <div class="three">
    <aside class="starthere" aria-labelledby="start-h">
      <h2 class="boxhead" id="start-h">Start here</h2>
      <ol class="startlist">{start_here}</ol>
      <form method="post" action="/grab" class="grabform">
        <label class="vh" for="grab-url">Video URL to grab</label>
        <input id="grab-url" name="url" type="url" inputmode="url" placeholder="paste a video URL" required>
        <label class="vid"><input type="checkbox" name="video" value="1"> also save the mp4</label>
        <button type="submit" class="grab">Grab</button>
      </form>
    </aside>
    {hero_html}
    <aside class="rail" aria-labelledby="rail-h"><h2 class="vh" id="rail-h">Recent</h2>{rail_html}</aside>
  </div>

  <hr class="ruler">
  <section aria-labelledby="all">
  <div class="allhead">
    <h2 class="boxhead" id="all">The archive</h2>
    <label class="vh" for="filter">Filter the archive by title or channel</label>
    <input id="filter" type="search" placeholder="filter by title or channel" autocomplete="off">
    <p class="vh" id="filter-count" role="status" aria-live="polite"></p>
  </div>
  <div class="grid">{grid_html}</div>
  </section>
</main>

<script>
const root = document.documentElement, btn = document.getElementById('theme');
const saved = localStorage.getItem('ytcc-theme');
if (saved) root.setAttribute('data-theme', saved);
btn.onclick = () => {{
  const now = root.getAttribute('data-theme')
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = now === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('ytcc-theme', next);
}};
async function copyT(id, kind, b) {{
  const r = await fetch('/t/' + id + '.' + kind);
  await navigator.clipboard.writeText(await r.text());
  const old = b.textContent; b.textContent = 'copied'; setTimeout(() => b.textContent = old, 1200);
}}
const f = document.getElementById('filter');
f && f.addEventListener('input', () => {{
  const q = f.value.toLowerCase().trim();
  let shown = 0;
  document.querySelectorAll('.grid .card').forEach(c => {{
    const hit = !q || c.dataset.title.includes(q)
      || (c.dataset.channel || '').toLowerCase().includes(q);
    c.hidden = !hit; if (hit) shown++;
  }});
  document.getElementById('filter-count').textContent = q ? shown + ' shown' : '';
}});
</script></body></html>"""


# ----------------------------------------------------------------- markdown -> html
# A GitHub-flavoured subset, enough for transcripts and notes: headings, bold,
# italic, inline code, links, fenced and indented code, blockquotes, lists,
# tables, rules, and the **[MM:SS]** timestamp marks yt-cc writes. Stdlib only,
# because adding a markdown dependency to a zero-install tool is not worth it.

_MD_INLINE = [
    (re.compile(r"`([^`]+)`"), lambda m: f"<code>{html.escape(m.group(1))}</code>"),
    (re.compile(r"\*\*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\*\*\s*"),
     lambda m: f"<span class='ts' id='t{m.group(1).replace(':', '-')}'>{m.group(1)}</span>"),
    (re.compile(r"\*\*([^*]+)\*\*"), lambda m: f"<strong>{m.group(1)}</strong>"),
    (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])"), lambda m: f"<em>{m.group(1)}</em>"),
    (re.compile(r"~~([^~]+)~~"), lambda m: f"<del>{m.group(1)}</del>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"),
     lambda m: f"<a href='{html.escape(m.group(2), quote=True)}'>{m.group(1)}</a>"),
    (re.compile(r"(?<![\"'>=])\b(https?://[^\s<>\"')]+)"),
     lambda m: f"<a href='{html.escape(m.group(1), quote=True)}'>{m.group(1)}</a>"),
]


def md_inline(text):
    out = html.escape(text)
    for pat, fn in _MD_INLINE:
        out = pat.sub(fn, out)
    return out


def md_to_html(src):
    """Markdown subset to HTML. Never raises; unknown syntax passes through as text."""
    lines = src.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    para, list_stack = [], []

    def flush_para():
        if para:
            body = md_inline(" ".join(para).strip())
            if body:
                out.append(f"<p>{body}</p>")
            para.clear()

    def close_lists(to=0):
        while len(list_stack) > to:
            out.append(f"</{list_stack.pop()}>")

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            lang = stripped[3:].strip()
            flush_para(); close_lists()
            body, i = [], i + 1
            while i < n and not lines[i].strip().startswith(fence):
                body.append(lines[i]); i += 1
            cls = f" class='lang-{html.escape(lang, quote=True)}'" if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(body))}</code></pre>")
            i += 1
            continue

        if not stripped:
            flush_para(); close_lists()
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(); close_lists()
            lvl = len(m.group(1))
            text = m.group(2).rstrip("#").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
            out.append(f"<h{lvl} id='{slug}'>{md_inline(text)}</h{lvl}>")
            i += 1
            continue

        if re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$", stripped):
            flush_para(); close_lists()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush_para(); close_lists()
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].lstrip())
                i += 1
            out.append(f"<blockquote>{md_to_html(chr(10).join(quote))}</blockquote>")
            continue

        # table: a header row followed by a delimiter row of dashes and pipes
        if "|" in stripped and i + 1 < n and re.match(r"^\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1].strip()):
            flush_para(); close_lists()
            def cells(row):
                row = row.strip().strip("|")
                return [c.strip() for c in row.split("|")]
            head = cells(lines[i])
            align = []
            for spec in cells(lines[i + 1]):
                if spec.startswith(":") and spec.endswith(":"):
                    align.append(" style='text-align:center'")
                elif spec.endswith(":"):
                    align.append(" style='text-align:right'")
                else:
                    align.append("")
            rows, i = [], i + 2
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            th = "".join(f"<th{align[j] if j < len(align) else ''}>{md_inline(c)}</th>"
                         for j, c in enumerate(head))
            body = "".join(
                "<tr>" + "".join(f"<td{align[j] if j < len(align) else ''}>{md_inline(c)}</td>"
                                 for j, c in enumerate(r)) + "</tr>" for r in rows)
            out.append(f"<div class='tablewrap'><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>")
            continue

        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para()
            depth = len(m.group(1)) // 2 + 1
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            while len(list_stack) > depth:
                out.append(f"</{list_stack.pop()}>")
            if len(list_stack) < depth:
                out.append(f"<{kind}>"); list_stack.append(kind)
            elif list_stack and list_stack[-1] != kind:
                out.append(f"</{list_stack.pop()}>"); out.append(f"<{kind}>"); list_stack.append(kind)
            item = m.group(3)
            box = re.match(r"^\[([ xX])\]\s+(.*)$", item)
            if box:
                checked = " checked" if box.group(1).lower() == "x" else ""
                state = "Done" if checked else "Not done"
                out.append(f"<li class='task'><input type='checkbox' disabled{checked} aria-label='{state}'> {md_inline(box.group(2))}</li>")
            else:
                out.append(f"<li>{md_inline(item)}</li>")
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush_para(); close_lists()
    return "\n".join(out)


READER_CSS = """
:root {
  --bg:#fbfaf8; --fg:#16181d; --dim:#5f6672; --rule:#e3e0da; --card:#fff;
  --accent:#0b0b0b; --yellow:#fff102; --code-bg:#f2efe9; --link:#0b5fa5; --mark:#5c574c;
}
:root[data-theme="dark"] {
  --bg:#0f1216; --fg:#e6e9ee; --dim:#8d95a3; --rule:#232a34; --card:#151a21;
  --accent:#ffe814; --yellow:#ffe814; --code-bg:#1a212a; --link:#79b8ff; --mark:#a3acb9;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#0f1216; --fg:#e6e9ee; --dim:#8d95a3; --rule:#232a34; --card:#151a21;
    --accent:#ffe814; --yellow:#ffe814; --code-bg:#1a212a; --link:#79b8ff; --mark:#a3acb9;
  }
}
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--fg); margin:0;
  font:1.1875rem/1.65 Charter,"Iowan Old Style","Source Serif Pro",Georgia,"Times New Roman",serif;
  -webkit-font-smoothing:antialiased; }
:focus-visible { outline:3px solid var(--link); outline-offset:2px; }
.vh { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);
  white-space:nowrap; }
.skip { position:absolute; left:-9999px; top:0; background:var(--fg); color:var(--bg);
  padding:.6rem 1rem; z-index:20; font-family:-apple-system,system-ui,sans-serif; font-size:.9rem; }
.skip:focus { left:1rem; top:1rem; }
.caution { font-family:-apple-system,system-ui,sans-serif; font-size:.8rem; color:var(--fg);
  border-left:4px solid var(--yellow); padding:.35rem .7rem; margin:1rem 0 0; }
html { scroll-padding-top:4rem; }
@media (prefers-reduced-motion:reduce) {
  *,*::before,*::after { transition:none!important; scroll-behavior:auto!important; }
}
.topbar { position:sticky; top:0; z-index:9; background:color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter:saturate(1.4) blur(8px); border-bottom:1px solid var(--rule); }
.topbar .inner { max-width:46rem; margin:0 auto; padding:.7rem 1.25rem;
  display:flex; align-items:center; gap:.75rem;
  font-family:-apple-system,system-ui,sans-serif; font-size:.8rem; }
.topbar a { color:var(--dim); text-decoration:none; }
.topbar a:hover { color:var(--fg); }
.spacer { flex:1; }
.tbtn { background:transparent; border:1px solid var(--rule); color:var(--dim);
  border-radius:99px; padding:.25rem .7rem; font:inherit; cursor:pointer; min-height:2.75rem; min-width:2.75rem; }
.tbtn:hover { color:var(--fg); border-color:var(--mark); }
.progress { position:fixed; top:0; left:0; height:3px; background:var(--yellow); width:0; z-index:10; }
article { max-width:46rem; margin:0 auto; padding:2.5rem 1.25rem 6rem; }
.kicker { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.7rem; font-weight:700;
  letter-spacing:.14em; text-transform:uppercase; color:var(--fg); margin-bottom:.75rem;
  display:inline-block; background:var(--yellow); color:#0b0b0b; padding:.2rem .5rem; }
h1 { font-size:2.4rem; line-height:1.12; letter-spacing:-.02em; margin:0 0 .75rem;
  font-weight:700; }
.byline { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.75rem; color:var(--dim);
  border-bottom:2px dotted var(--rule); padding-bottom:1.1rem; margin-bottom:2rem;
  letter-spacing:.02em; }
.byline a { color:var(--link); text-decoration:underline; text-underline-offset:.15em; }
.stats { display:flex; gap:1.5rem; flex-wrap:wrap; margin:.7rem 0 0; }
.stat { display:flex; flex-direction:column-reverse; }
.stat dd { margin:0; font-family:-apple-system,system-ui,sans-serif; font-size:1.05rem;
  color:var(--fg); font-weight:650; font-variant-numeric:tabular-nums; }
.stat dt { font-size:.62rem; letter-spacing:.12em; text-transform:uppercase; color:var(--dim);
  font-family:ui-monospace,monospace; }
article p { margin:0 0 1.25rem; }
article p:first-of-type::first-letter { float:left; font-size:3.6rem; line-height:.8;
  padding:.3rem .55rem .1rem 0; font-weight:700; color:var(--fg); }
h2,h3,h4 { font-family:Charter,"Iowan Old Style",Georgia,serif; letter-spacing:-.015em;
  margin:2.5rem 0 .85rem; line-height:1.22; font-weight:700; }
h2 { font-size:1.4rem; } h3 { font-size:1.15rem; } h4 { font-size:1rem; }
a { color:var(--link); }
.ts { display:inline-block; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:.68rem; color:var(--mark); background:var(--code-bg); border-radius:4px;
  padding:.1rem .4rem; margin-right:.5rem; vertical-align:.12em; letter-spacing:.02em; }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.85em;
  background:var(--code-bg); padding:.12em .35em; border-radius:4px; }
pre { background:var(--code-bg); border:1px solid var(--rule); border-radius:8px;
  padding:1rem; overflow-x:auto; }
pre code { background:none; padding:0; font-size:.8rem; line-height:1.55; }
blockquote { margin:1.75rem 0; padding:.2rem 0 .2rem 1.25rem; border-left:4px solid var(--yellow);
  color:var(--dim); font-style:italic; }
blockquote p:last-child { margin-bottom:0; }
ul,ol { margin:0 0 1.25rem; padding-left:1.4rem; }
li { margin-bottom:.4rem; }
li.task { list-style:none; margin-left:-1.2rem; }
hr { border:0; border-top:2px dotted var(--rule); margin:2.5rem 0; }
.tablewrap { overflow-x:auto; margin:0 0 1.5rem; }
table { border-collapse:collapse; width:100%; font-family:-apple-system,system-ui,sans-serif;
  font-size:.85rem; }
th,td { border:1px solid var(--rule); padding:.5rem .65rem; text-align:left; }
th { background:var(--code-bg); font-weight:650; }
tbody tr:nth-child(even) { background:color-mix(in srgb, var(--code-bg) 45%, transparent); }
@media (max-width:34rem) {
  body { font-size:1.09375rem; }
  h1 { font-size:1.85rem; }
  article { padding:1.75rem 1.1rem 4rem; }
}
@media print {
  .topbar,.progress { display:none; }
  body { background:#fff; color:#000; }
}
"""


def reader(vid):
    """One transcript rendered as a reading page. None when the video is unknown."""
    d = STORE / vid
    mdf, metaf = d / "transcript.md", d / "meta.json"
    if not mdf.exists():
        return None
    meta = json.loads(metaf.read_text()) if metaf.exists() else {}
    raw = mdf.read_text(errors="replace")

    # The first three lines are yt-cc's own header; the page renders them as a byline.
    body = raw.split("\n")
    if body and body[0].startswith("# "):
        title = body[0][2:].strip()
        rest = body[1:]
        while rest and (not rest[0].strip() or rest[0].startswith(("Channel:", "Grabbed:"))):
            rest.pop(0)
        raw = "\n".join(rest)
    else:
        title = meta.get("title", vid)

    e = html.escape
    words = len(raw.split())
    n = meta.get("view_count")
    views = (f"{n/1_000_000:.1f}M" if isinstance(n, int) and n >= 1_000_000
             else f"{n//1000}K" if isinstance(n, int) and n >= 1000
             else str(n) if isinstance(n, int) else "–")
    up = str(meta.get("upload_date") or "")
    when = f"{up[0:4]}-{up[4:6]}-{up[6:8]}" if len(up) == 8 and up.isdigit() else "–"
    src = meta.get("sub_source", "")
    caution = ("<p class='caution'>"
               "Machine transcription · verify names and numbers before quoting</p>"
               if "auto" in src else "")

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<style>{READER_CSS}</style></head><body>
<a class="skip" href="#main">Skip to transcript</a>
<div class="progress" id="prog" aria-hidden="true"></div>
<header><nav class="topbar" aria-label="Transcript"><div class="inner">
  <a href="/"><span aria-hidden="true">← </span>all transcripts</a>
  <span class="spacer"></span>
  <a href="/t/{e(vid)}.md">raw markdown</a>
  <a href="{e(meta.get('url', '#'))}" target="_blank" rel="noopener">source <span aria-hidden="true">↗</span><span class="vh"> (opens in a new tab)</span></a>
  <button type="button" class="tbtn" id="theme" aria-label="Switch between light and dark theme"><span aria-hidden="true">◐</span></button>
</div></nav></header>
<main id="main">
<article>
  <p class="kicker">{e(meta.get('channel', 'transcript'))}</p>
  <h1>{e(title)}</h1>
  <div class="byline">
    Transcript of <a href="{e(meta.get('url', '#'))}" target="_blank" rel="noopener">this video<span class="vh"> (opens in a new tab)</span></a>
    · {e(src or 'captions')}
    <dl class="stats">
      <div class="stat"><dt>runtime</dt><dd>{e(meta.get('duration_string', '–'))}</dd></div>
      <div class="stat"><dt>words</dt><dd>{words:,}</dd></div>
      <div class="stat"><dt>min read</dt><dd>{max(1, words // 238)}</dd></div>
      <div class="stat"><dt>views</dt><dd>{e(views)}</dd></div>
      <div class="stat"><dt>published</dt><dd>{e(when)}</dd></div>
    </dl>
    {caution}
  </div>
  {md_to_html(raw)}
</article>
</main>
<script>
const root = document.documentElement, btn = document.getElementById('theme');
const saved = localStorage.getItem('ytcc-theme');
if (saved) root.setAttribute('data-theme', saved);
btn.onclick = () => {{
  const now = root.getAttribute('data-theme')
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = now === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('ytcc-theme', next);
}};
const prog = document.getElementById('prog');
addEventListener('scroll', () => {{
  const h = document.body.scrollHeight - innerHeight;
  prog.style.width = (h > 0 ? scrollY / h * 100 : 0) + '%';
}}, {{passive: true}});
</script></body></html>"""


# ----------------------------------------------------------------- channels and topics
# Topics are derived, not curated: a small keyword map over titles. It is a
# router, not a classifier, and every video can land in several topics. The
# point is a second way to page through 250 transcripts, not a taxonomy.

TOPICS = [
    ("models", ["gpt", "claude", "llama", "gemini", "qwen", "deepseek", "mistral",
                "o1", "o3", "sonnet", "opus", "haiku", "kimi", "grok", "model"]),
    ("agents", ["agent", "mcp", "cursor", "copilot", "codex", "devin", "cline",
                "claude code", "autonomous", "tool use"]),
    ("hardware", ["gpu", "cpu", "nvidia", "amd", "radeon", "rtx", "ryzen", "epyc",
                  "threadripper", "vram", "motherboard", "build", "rack", "server",
                  "cooling", "psu", "ssd", "nvme", "memory", "ram", "chip"]),
    ("networking", ["network", "router", "switch", "10g", "25g", "fiber", "vlan",
                    "haproxy", "proxy", "dns", "firewall", "wifi", "ethernet"]),
    ("self-hosting", ["self-host", "selfhost", "homelab", "proxmox", "docker",
                      "kubernetes", "truenas", "unraid", "nas", "home server", "local"]),
    ("security", ["security", "hack", "exploit", "cve", "breach", "vulnerab",
                  "malware", "phish", "privacy", "encrypt", "password", "attack"]),
    ("web dev", ["react", "next.js", "nextjs", "typescript", "javascript", "css",
                 "tailwind", "svelte", "vue", "node", "framework", "frontend",
                 "backend", "database", "postgres", "sql", "api"]),
    ("business", ["startup", "funding", "acquisition", "ipo", "layoff", "hiring",
                  "salary", "market", "pricing", "revenue", "billion", "million"]),
    ("industry", ["openai", "anthropic", "google", "microsoft", "meta", "apple",
                  "amazon", "tesla", "intel", "arm", "tsmc", "sam altman"]),
]


def topics_for(title):
    t = (title or "").lower()
    return [name for name, words in TOPICS if any(w in t for w in words)]


def slugify(x):
    return re.sub(r"[^a-z0-9]+", "-", (x or "").lower()).strip("-")[:60] or "other"


def grouped():
    """(channel -> cards, topic -> cards). Both sorted by size, biggest first."""
    by_channel, by_topic = {}, {}
    for c in cards():
        by_channel.setdefault(c.get("channel", "unknown"), []).append(c)
        hits = topics_for(c.get("title"))
        for t in (hits or ["unsorted"]):
            by_topic.setdefault(t, []).append(c)
    order = lambda d: dict(sorted(d.items(), key=lambda kv: -len(kv[1])))
    return order(by_channel), order(by_topic)


def browse_page(kind, key=None):
    """kind is 'channel' or 'topic'. Without a key, the index of all of them."""
    e = html.escape
    by_channel, by_topic = grouped()
    groups = by_channel if kind == "channel" else by_topic
    other = "topic" if kind == "channel" else "channel"

    def card_of(c):
        cid = e(c["id"])
        return f"""
<article class="card">
  <a class="posterlink" href="/read/{cid}" aria-hidden="true" tabindex="-1">
    <img class="poster" src="/thumb/{cid}.jpg" alt="" loading="lazy"
         onerror="this.closest('.posterlink').classList.add('noimg')">
    <span class="dur">{e(c.get('duration_string', ''))}</span></a>
  <div class="body">
    <p class="label">{e(c.get('channel', ''))}</p>
    <h2 class="t"><a href="/read/{cid}">{e(c['title'])}</a></h2>
    <div class="row">
      <a class="btn" href="/read/{cid}">read</a>
      <a class="btn src" href="{e(c['url'])}" target="_blank" rel="noopener">source <span aria-hidden="true">↗</span><span class="vh"> (opens in a new tab)</span></a>
    </div>
  </div>
</article>"""

    if key is None:
        body = "<div class='grouplist'>" + "".join(f"""
<a class="groupcard" href="/{kind}/{slugify(k)}">
  <span class="gcount">{len(v)}</span>
  <span class="gname">{e(k)}</span>
  <span class="gsub">{e(v[0]['title'][:64])}…</span>
</a>""" for k, v in groups.items()) + "</div>"
        head = f"All {kind}s"
        sub = f"{len(groups)} {kind}s across {len(cards())} transcripts"
    else:
        match = next((k for k in groups if slugify(k) == key), None)
        if match is None:
            return None
        items = groups[match]
        body = "<div class='grid'>" + "".join(card_of(c) for c in items) + "</div>"
        head = match
        mins = sum(1 for _ in items)
        sub = f"{len(items)} transcripts in this {kind}"

    nav = " ".join(f"<a href='/{kind}/{slugify(k)}'>{e(k)} <b>{len(v)}</b></a>"
                   for k, v in list(groups.items())[:12])

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(head)} · yt-cc</title><style>{BOARD_CSS}
.grouplist {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(14rem,1fr)); gap:1rem; }}
.groupcard {{ border:1px solid var(--rule); padding:1rem 1.1rem; text-decoration:none;
  display:block; transition:background .15s; }}
.groupcard:hover {{ background:var(--yellow); color:#0b0b0b; }}
.gcount {{ display:block; font:700 2rem/1 Charter,Georgia,serif; }}
.gname {{ display:block; font:700 .78rem/1.3 ui-monospace,monospace; letter-spacing:.1em;
  text-transform:uppercase; margin:.35rem 0 .4rem; }}
.gsub {{ display:block; font:.75rem/1.35 Charter,Georgia,serif; color:var(--dim); }}
.groupcard:hover .gsub {{ color:#333; }}
.pills {{ display:flex; gap:.4rem; flex-wrap:wrap; margin:0 0 1.75rem; }}
.pills a {{ border:1px solid var(--rule); padding:.3rem .6rem; text-decoration:none;
  font:.7rem/1 ui-monospace,monospace; letter-spacing:.05em; text-transform:uppercase; }}
.pills a:hover {{ background:var(--yellow); color:#0b0b0b; border-color:var(--yellow); }}
.pills b {{ color:var(--dim); }}
.pagehead {{ font:700 2.4rem/1.1 Charter,"Iowan Old Style",Georgia,serif;
  letter-spacing:-.025em; margin:.5rem 0 .3rem; }}
</style></head><body>
<a class="skip" href="#main">Skip to content</a>
<header>
<div class="masthead"><div class="mast-inner">
  <a class="wordmark" href="/" aria-label="yt-cc, front page">yt<span aria-hidden="true">·</span>cc</a>
  <nav class="mastnav" aria-label="Browse">
    <a href="/">Front</a><a href="/channel">Channels</a><a href="/topic">Topics</a>
  </nav>
  <button type="button" class="tbtn" id="theme" aria-label="Switch between light and dark theme"><span aria-hidden="true">◐</span></button>
</div></div>
<p class="strip"><b>{e(head)}</b> / {e(sub)} / <a href="/{other}">browse by {other} instead</a></p>
</header>
<main class="wrap" id="main">
  <h1 class="pagehead">{e(head)}</h1>
  <nav class="pills" aria-label="Largest {kind}s">{nav}</nav>
  {body}
</main>
<script>
const root = document.documentElement, btn = document.getElementById('theme');
const saved = localStorage.getItem('ytcc-theme');
if (saved) root.setAttribute('data-theme', saved);
btn.onclick = () => {{
  const now = root.getAttribute('data-theme')
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = now === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('ytcc-theme', next);
}};
</script></body></html>"""


def not_found_page():
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Not found · yt-cc</title><style>{BOARD_CSS}</style></head><body>
<main class="wrap" id="main"><h1 class="hero-h">Not found</h1>
<p><a href="/">Back to all transcripts</a></p></main></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/":
            return self._send(page())
        b = re.match(r"^/(channel|topic)(?:/([\w-]+))?/?$", p)
        if b:
            out = browse_page(b.group(1), b.group(2))
            if out:
                return self._send(out)
            return self._send(not_found_page(), code=404)
        r = re.match(r"^/read/([\w-]{6,20})$", p)
        if r:
            html_page = reader(r.group(1))
            if html_page:
                return self._send(html_page)
            return self._send(not_found_page(), code=404)
        m = re.match(r"^/t/([\w-]{6,20})\.(md|json)$", p)
        if m:
            f = STORE / m.group(1) / f"transcript.{m.group(2)}"
            if f.exists():
                ct = "text/markdown; charset=utf-8" if m.group(2) == "md" else "application/json"
                return self._send(f.read_bytes(), ct)
        v = re.match(r"^/video/([\w-]{6,20})\.mp4$", p)
        if v:
            f = STORE / v.group(1) / "video.mp4"
            if f.exists():
                size = f.stat().st_size
                rng = self.headers.get("Range")
                start, end = 0, size - 1
                if rng:
                    mm = re.match(r"bytes=(\d*)-(\d*)", rng)
                    if mm:
                        if mm.group(1):
                            start = int(mm.group(1))
                        if mm.group(2):
                            end = int(mm.group(2))
                length = end - start + 1
                self.send_response(206 if rng else 200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if rng:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                with open(f, "rb") as fh:
                    fh.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = fh.read(min(262144, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
        t = re.match(r"^/thumb/([\w-]{6,20})\.jpg$", p)
        if t:
            f = STORE / t.group(1) / "thumb.jpg"
            if f.exists():
                return self._send(f.read_bytes(), "image/jpeg")
        self._send("not found", "text/plain", 404)

    def do_POST(self):
        if urlparse(self.path).path != "/grab":
            return self._send("not found", "text/plain", 404)
        n = int(self.headers.get("Content-Length", 0))
        q = parse_qs(self.rfile.read(n).decode())
        url = clean_url((q.get("url") or [""])[0])
        want_video = bool(q.get("video"))
        r = grab(url, want_video) if url else {"error": "no url"}
        if "error" in r:
            return self._send(page(f"<div class='msg err' role='alert'>{html.escape(r['error'])}</div>"))
        self._send(page(f"<div class='msg' role='status'>grabbed: {html.escape(r['title'])} ({r['cue_count']} cues, {html.escape(r['sub_source'])})</div>"))

    def log_message(self, *a):
        pass


def cli_grab(url, want_video):
    r = grab(url, want_video)
    if "error" in r:
        print("yt-cc: " + r["error"], file=sys.stderr)
        return 1
    print(STORE / r["id"] / "transcript.md")
    note = "; description and metadata saved, no transcript" if not r["cue_count"] else ""
    print(f"grabbed: {r['title']} ({r['cue_count']} cues, {r['sub_source']}{note})", file=sys.stderr)
    return 0


def cli_grab_many(url, want_video, limit, delay):
    """Command-line wrapper around grab_many: run it, then print the summary.

    Mirrors cli_grab above. The summary and any failures go to stderr, and the
    store directory goes to stdout, so `ytcc.py <channel> | xargs ...` still
    gets a clean path to work with.
    """
    r = grab_many(url, want_video, limit, delay)
    if "error" in r:
        print("yt-cc: " + r["error"], file=sys.stderr)
        return 1

    print(f"listed {r['listed']}, grabbed {r['grabbed']}, "
          f"already had {r['skipped']}, failed {r['failed']}", file=sys.stderr)

    # Show the first ten failures rather than all of them. On a 2,000 video
    # channel a handful with no English captions is normal and a full dump
    # would bury the summary line.
    for vid, why in r["failures"][:10]:
        print(f"  failed {vid}: {why}", file=sys.stderr)

    print(STORE)

    # Exit 0 if anything is on disk for this channel, including videos that
    # were already there. A re-run that grabs nothing new is a success, not a
    # failure, which matters if this is wired into a scheduled job.
    return 0 if r["grabbed"] or r["skipped"] else 1


def main(argv):
    want_video = False
    serve = False
    url = None
    limit = None
    delay = 1.5
    force_many = False
    global STORE
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("--video", "-v", "+video"):
            want_video = True
        # Force whole-channel mode even when the URL looks like one video.
        # Useful for a watch?v=…&list=… link where you really do want the
        # whole playlist and do not want to rely on looks_multi guessing.
        elif a in ("--channel", "--playlist", "--all"):
            force_many = True

        # --limit 25 / -n 25: only take the newest N. Always use this the
        # first time you point at an unfamiliar channel, so you find out it
        # has 3,000 videos before you start fetching all 3,000.
        elif a in ("-n", "--limit"):
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            if nxt.isdigit():
                limit = int(nxt)
                i += 1  # consume the number as well as the flag

        # --delay 3: seconds to wait between videos. Raise it if YouTube
        # starts rate-limiting you partway through a large backlog.
        elif a == "--delay":
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            try:
                delay = float(nxt)
                i += 1
            except ValueError:
                pass  # a bad number just leaves the default in place
        elif a in ("-h", "--help", "help"):
            print(__doc__)
            return 0
        elif a == "--selftest":
            return selftest()
        elif a in ("serve", "--serve"):
            serve = True
        elif a in ("-d", "--dir", "--store"):
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            if nxt and not nxt.startswith("-") and "://" not in nxt and "youtu" not in nxt:
                STORE = Path(nxt).expanduser()
                STORE.mkdir(parents=True, exist_ok=True)
                i += 1
        elif a.startswith("http") or "youtu" in a:
            url = a
        elif a == "grab":
            pass
        elif url is None:
            # A bare video id, @handle, playlist id or channel id. clean_url
            # unfolds it below.
            url = a
        i += 1

    if url and not serve:
        # Strip the sharer out of the link and unfold short forms first, so
        # the store, meta.json and yt-dlp all see one canonical URL.
        cleaned = clean_url(url)
        if cleaned != url:
            print(f"yt-cc: using {cleaned}", file=sys.stderr)
        url = cleaned
        # The fork in the road. A channel or playlist URL goes to the multi
        # path; anything else keeps the original one-video behavior. You can
        # paste either kind of link and not think about it.
        if force_many or looks_multi(url):
            return cli_grab_many(url, want_video, limit, delay)
        return cli_grab(url, want_video)

    if YTDLP is None:
        print("WARN: yt-dlp not found (PATH or `python3 -m yt_dlp`); grabs will fail.", file=sys.stderr)
        print("  macOS: brew install yt-dlp · Debian/WSL: pipx install yt-dlp", file=sys.stderr)
    print(f"yt-cc-dash on http://{HOST}:{PORT}   store: {STORE}")
    print(f"  yt-dlp: {' '.join(YTDLP) if YTDLP else 'MISSING'}")
    try:
        ThreadingHTTPServer((HOST, PORT), H).serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
