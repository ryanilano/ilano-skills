---
name: yt-cc
description: Pull a video's captions, description and metadata to local markdown in one command, then read it; a channel or playlist URL pulls every video on it. Use when the user pastes a video or channel link, asks what a video says, or wants quotes or a claim checked against it. Also serves a local board of every transcript grabbed. Not for what is shown on screen rather than spoken (code, a diagram, a UI, a slide read silently).
---

# yt-cc

One command, one file, stdlib only. It prints the transcript path to stdout.

```bash
python3 scripts/ytcc.py "<url>"
```

Read the file it prints. That is the whole flow. Everything else on this page is
for when the first line does not do what you need.

Paste the link as you got it. A `youtu.be/ID?si=…` share link, a `/shorts/` or
`/live/` link, `m.youtube.com`, a bare 11-character video id, or a bare
`@handle` all resolve to the same canonical URL, and share and tracking
parameters (`si=`, `feature=`, `utm_*`, `fbclid`) are stripped before the URL
is used or written to `meta.json`. The cleaned URL is echoed to stderr when it
differs from what was pasted.

## What comes back

A directory per video under the store, named by video ID:

| File | What it is |
|---|---|
| `transcript.md` | H1, a channel/duration/published/URL line, a source line, `## Description` (the creator's own text: links, tools, corrections), `## Chapters` when the video has them, then `## Transcript` with `**[MM:SS]**` marks about once a minute |
| `transcript.json` | the same cues as `{"t": seconds, "text": "..."}`, for programmatic use |
| `meta.json` | title, channel, duration, url, upload_date, view_count, like_count, tags, description, chapters, cue count, caption source |
| `thumb.jpg` | poster frame, when the extractor supplies one |
| `video.mp4` | only with `--video` |

The `Source:` line in `transcript.md` says **manual captions**, **auto
captions**, or **no captions**. Manual means a human wrote them and the text is
worth quoting verbatim. Auto means machine captions: usable for meaning, weak on
proper nouns and punctuation. Say which one you used when you quote it.

## A whole channel or playlist

```bash
python3 scripts/ytcc.py "https://www.youtube.com/@handle" -n 25
```

A `/@handle`, `/channel/`, `/c/`, `/user/`, `/playlist` or `list=` URL is
taken as a collection without a flag. It lists the videos in one request
(newest first), skips any already in the store, grabs the rest 1.5 s apart,
prints a summary to stderr and the store path to stdout. Re-running next week
costs one listing plus whatever is new. Use `-n` the first time on an
unfamiliar channel: find out it has 3,000 videos before fetching 3,000.

## Flags

| Flag | Use |
|---|---|
| `-n N` (`--limit`) | newest N only, in collection mode |
| `--channel` (`--all`) | force collection mode for a `watch?v=...&list=...` link |
| `--delay S` | seconds between videos in collection mode. Default 1.5; raise it if YouTube starts rate-limiting |
| `--video` (`-v`, `+video`) | also download the mp4. Slow, large, and only needed when the answer is visual |
| `-d DIR` (`--dir`, `--store`) | write to DIR instead of the default store |
| `serve` | run the web board instead of grabbing |
| `--selftest` | check the URL cleaner against known link forms, no network |
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

1. **The saved file is the evidence.** Answer a video question from
   `transcript.md` (its description and its captions), not from a fetch of the
   video page, the title, or a search result.
2. **A video with no English captions still gets its description and metadata
   saved.** The `Source:` line says `no captions` and there is no `## Transcript`
   section. Say so; answer from the description if it answers the question.
   `--video` saves the file so a different tool can work on it.
   The description is often the easy win: links, the tool list, the pinned
   correction. Read it before the transcript.
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
