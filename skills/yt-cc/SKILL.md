---
name: yt-cc
description: Pull a video's transcript to local markdown with one command, then read it. Captions come from yt-dlp with no video download, so a two-hour talk costs one HTTP round trip and no model tokens. Use when the user pastes a video link, asks what a video says, wants it summarized or analyzed, wants quotes pulled, or wants to check a claim someone made on video. Also serves a local web board of everything grabbed so far. Do NOT use when the answer is shown on screen rather than spoken, such as code, a diagram, a UI, or a prompt being read silently from a slide.
---

# yt-cc

One command, one file, stdlib only. It prints the transcript path to stdout.

```bash
python3 scripts/ytcc.py "<url>"
```

Read the file it prints. That is the whole flow. Everything else on this page is
for when the first line does not do what you need.

## What comes back

A directory per video under the store, named by video ID:

| File | What it is |
|---|---|
| `transcript.md` | H1, a channel/duration/URL line, a source line, then the text with `**[MM:SS]**` marks about once a minute |
| `transcript.json` | the same cues as `{"t": seconds, "text": "..."}`, for programmatic use |
| `meta.json` | title, channel, duration, url, cue count, caption source |
| `thumb.jpg` | poster frame, when the extractor supplies one |
| `video.mp4` | only with `--video` |

The `Source:` line in `transcript.md` says **manual captions**, **auto
captions**, or **no captions**. Manual means a human wrote them and the text is
worth quoting verbatim. Auto means machine captions: usable for meaning, weak on
proper nouns and punctuation. Say which one you used when you quote it.

## Flags

| Flag | Use |
|---|---|
| `--video` (`-v`, `+video`) | also download the mp4. Slow, large, and only needed when the answer is visual |
| `-d DIR` (`--dir`, `--store`) | write to DIR instead of the default store |
| `serve` | run the web board instead of grabbing |
| `--help` | usage |

## Environment

| Variable | Default | Why you would set it |
|---|---|---|
| `YTCC_STORE` | `$XDG_DATA_HOME/yt-cc`, else `~/.local/share/yt-cc` | keep transcripts with a project instead of in the home store |
| `YTCC_COOKIES_BROWSER` | unset | `chrome`, `safari`, or `brave`. Fixes HTTP 403 on video download by borrowing browser cookies |
| `YTCC_HOST` / `YTCC_PORT` | `127.0.0.1` / `8091` | where the board listens |

## The board

```bash
python3 scripts/ytcc.py serve
```

Serves every grabbed video as a card at `http://127.0.0.1:8091`, newest first,
with search. It binds loopback. To reach it from a phone or tablet, front it
with `tailscale serve` rather than binding it to all interfaces.

## Requirements

`python3` and `yt-dlp`. The script finds `yt-dlp` on PATH, or falls back to
`python3 -m yt_dlp`, and tells you how to install it if neither works
(`brew install yt-dlp` on macOS, `pipx install yt-dlp` on Debian or WSL).

## Rules

1. **Never answer a video question from the page description, the title, or a
   search result.** Run this and read the transcript. A summary of a summary is
   not evidence.
2. **A video with no English captions exits non-zero and writes nothing.** That
   is a real answer, not a tool failure. Do not report the video as empty; say
   it has no caption track. `--video` saves the file so a different tool can
   work on it.
3. **Say which caption source you used** when you quote or make a claim from the
   text, because auto captions mishear names.
4. **Re-running a URL is cheap.** The store is keyed by video ID and existing
   files are reused. Run it again rather than assuming a transcript is stale.
5. **Content shown on screen is unrecoverable from any transcript.** Code on a
   slide, a diagram, a UI being demoed, a prompt read silently. If that is the
   question, this is the wrong tool and no amount of retrying changes it.

## Why this exists

Watching costs an hour per hour. Feeding video frames to a model costs real
money per minute. A caption track is text the publisher already produced and
already serves, and pulling it is one HTTP request. Measured on a 256-video
corpus: 7,399 minutes of talk, 8.3 MB of markdown, no API spend.
