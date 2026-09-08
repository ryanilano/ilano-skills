#!/usr/bin/env python3
"""yt-cc: transcript-first video board + CLI. Portable (macOS/Linux/WSL), stdlib only.

Two modes, one file:
  ytcc.py                 -> web dashboard on $YTCC_HOST:$YTCC_PORT (default 127.0.0.1:8091)
  ytcc.py <url> [--video] -> headless grab; prints the saved transcript.md path to stdout

Captions via yt-dlp (no video download unless --video / +video). Store is XDG-based and
configurable ($YTCC_STORE). Front the server with `tailscale serve` for phone/tablet access.

Env: YTCC_STORE, YTCC_HOST, YTCC_PORT, YTCC_COOKIES_BROWSER (chrome/safari/brave -> fixes 403).
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
from urllib.parse import parse_qs, urlparse


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


def to_markdown(meta, cues):
    lines = [f"# {meta['title']}", "",
             f"Channel: {meta.get('channel', '?')} · Duration: {meta.get('duration_string', '?')} · {meta['url']}",
             f"Grabbed: {meta['grabbed']} · Source: {meta['sub_source']}", ""]
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
    if not vtts and not want_video:
        return {"error": "no English captions on this video, and video not requested. "
                         "Add --video to save the file anyway, or use ASR."}

    meta = {"id": vid, "title": info.get("title", vid),
            "channel": info.get("channel") or info.get("uploader", "?"),
            "duration_string": info.get("duration_string", "?"),
            "url": info.get("webpage_url", url),
            "grabbed": time.strftime("%Y-%m-%d %H:%M"),
            "sub_source": src, "cue_count": len(cues)}
    if cues:
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


def page(msg=""):
    e = html.escape
    card_html = "".join(f"""
<div class="card">
  {("<video controls preload='none' poster='/thumb/" + e(c['id']) + ".jpg' src='/video/" + e(c['id']) + ".mp4'></video>") if c.get('has_video') else ("<a href='/t/" + e(c['id']) + ".md'><img src='/thumb/" + e(c['id']) + ".jpg' alt='' loading='lazy' onerror=\"this.style.display='none'\"></a>")}
  <div class="body">
    <div class="t">{e(c['title'])}</div>
    <div class="dim">{e(c.get('channel', '?'))} · {e(c.get('duration_string', '?'))} · {e(c.get('sub_source', ''))}</div>
    <div class="row">
      <a class="btn" href="/t/{e(c['id'])}.md">MD</a>
      <a class="btn" href="/t/{e(c['id'])}.json">JSON</a>
      <button class="btn" onclick="copyT('{e(c['id'])}','md',this)">copy md</button>
      <button class="btn" onclick="copyT('{e(c['id'])}','json',this)">copy json</button>
      {("<a class='btn' href='/video/" + e(c['id']) + ".mp4' download>video</a>") if c.get('has_video') else ""}
      <a class="btn src" href="{e(c['url'])}">source ↗</a>
    </div>
  </div>
</div>""" for c in cards())
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>yt-cc</title><style>
:root {{ color-scheme: dark; }}
body {{ background:#0d0f12; color:#d7dce2; font:16px/1.45 -apple-system,system-ui,sans-serif;
       margin:0 auto; padding:1rem; max-width:64rem; }}
h1 {{ font-size:1.2rem; margin:0 0 .75rem; }}
form {{ display:flex; gap:.5rem; margin-bottom:1rem; }}
input {{ flex:1; background:#161a20; color:#d7dce2; border:1px solid #232830;
        border-radius:6px; padding:.6rem .8rem; font-size:1rem; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(15rem,1fr)); gap:1rem; }}
.card {{ background:#12151a; border:1px solid #1e232b; border-radius:8px; overflow:hidden; }}
.card img, .card video {{ width:100%; aspect-ratio:16/9; object-fit:cover; display:block; background:#000; }}
.body {{ padding:.6rem .7rem .8rem; }}
.t {{ font-weight:600; font-size:.9rem; margin-bottom:.3rem; }}
.dim {{ color:#5b6470; font-size:.75rem; margin-bottom:.55rem; }}
.row {{ display:flex; gap:.4rem; flex-wrap:wrap; }}
.btn {{ background:#1d2733; color:#8fb8d8; border:0; border-radius:4px; font-size:.75rem;
       padding:.25rem .55rem; text-decoration:none; cursor:pointer; }}
.btn:active {{ background:#2a3a4d; }}
.btn.src {{ background:#233; color:#7fd1c7; }}
.msg {{ background:#14231c; border:1px solid #1f4232; color:#8fd8b0; border-radius:6px;
       padding:.5rem .8rem; margin-bottom:1rem; font-size:.85rem; }}
.msg.err {{ background:#231414; border-color:#42201f; color:#e08f8f; }}
.vid {{ display:flex; align-items:center; gap:.3rem; color:#8fb8d8; font-size:.85rem; white-space:nowrap; }}
button.grab {{ background:#7fd1c7; color:#0d0f12; font-weight:700; border:0;
              border-radius:6px; padding:.6rem 1rem; cursor:pointer; }}
</style></head><body>
<h1>yt-cc · transcripts for humans and bots</h1>
<form method="post" action="/grab">
  <input name="url" placeholder="paste a video URL, get captions" required>
  <label class="vid"><input type="checkbox" name="video" value="1"> 1080p mp4</label>
  <button class="grab">grab</button>
</form>
{msg}
<div class="grid">{card_html or "<p class='dim'>nothing grabbed yet</p>"}</div>
<script>
async function copyT(id, kind, btn) {{
  const r = await fetch('/t/' + id + '.' + kind);
  await navigator.clipboard.writeText(await r.text());
  const old = btn.textContent; btn.textContent = 'copied';
  setTimeout(() => btn.textContent = old, 1200);
}}
</script></body></html>"""


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
        url = (q.get("url") or [""])[0].strip()
        want_video = bool(q.get("video"))
        r = grab(url, want_video) if url else {"error": "no url"}
        if "error" in r:
            return self._send(page(f"<div class='msg err'>{html.escape(r['error'])}</div>"))
        self._send(page(f"<div class='msg'>grabbed: {html.escape(r['title'])} ({r['cue_count']} cues, {html.escape(r['sub_source'])})</div>"))

    def log_message(self, *a):
        pass


def cli_grab(url, want_video):
    r = grab(url, want_video)
    if "error" in r:
        print("yt-cc: " + r["error"], file=sys.stderr)
        return 1
    md = STORE / r["id"] / "transcript.md"
    print(md if md.exists() else STORE / r["id"] / "transcript.json")
    print(f"grabbed: {r['title']} ({r['cue_count']} cues, {r['sub_source']})", file=sys.stderr)
    return 0


def main(argv):
    want_video = False
    serve = False
    url = None
    global STORE
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("--video", "-v", "+video"):
            want_video = True
        elif a in ("-h", "--help", "help"):
            print(__doc__)
            return 0
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
            url = a
        i += 1

    if url and not serve:
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
