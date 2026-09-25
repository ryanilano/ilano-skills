---
name: ffmpeg
description: Edit video, audio and image sequences with ffmpeg through one JSON-returning helper (cut, merge, compress, GIF, subtitles, thumbnails, speed, watermark, stabilize, convert). Use for any media file manipulation, including a video.mp4 that yt-cc saved.
---

# ffmpeg

Every operation goes through `scripts/fftools.py`, which wraps ffmpeg and ffprobe and returns JSON. Run it with no arguments for the command list; `references/commands.md` has one worked example per command, the raw-ffmpeg recipes the helper does not cover, and the CRF and container tables.

```bash
python3 scripts/fftools.py info input.mp4
```

## Steps

1. **Probe first.** `info` on every input: duration, resolution, codecs, size. Output settings come from these numbers, not from guesses.
2. **Operate.** One helper command per edit; chain edits by feeding one output into the next. Reach for raw `ffmpeg` only when no helper command fits (`references/commands.md`, "Raw ffmpeg").
3. **Verify.** `info` on the output. Done when the JSON shows the expected duration, resolution and codecs, and no `error` key.
4. **Show.** Open each image (thumbnail, frame) and read it so the user sees it. For video, report the path and size.

## Rules

- **Stream copy when the codecs match, re-encode when they do not.** `merge` defaults to copy; add `--reencode` when `info` shows different codecs across inputs.
- **CRF is the quality knob.** 18 archival, 23 default, 28 sharing, 32 social. Each +6 roughly halves the file.
- **A timeout on a long video is not a failure.** Re-run with `--preset ultrafast`, or cut first and process the piece.
- **Absolute paths in, absolute paths out.** "No such file" is a path problem, not a codec problem.

## With yt-cc

`yt-cc "<url>" --video` leaves `video.mp4` beside the transcript in the store, and the transcript's `**[MM:SS]**` marks give you the timestamps: `cut` the quoted passage, `thumbnail` the moment, `gif` the demo.

## Requirements

`ffmpeg` and `ffprobe` on PATH (`brew install ffmpeg`). `stabilize` needs the vidstab filter compiled in; `ffmpeg -filters | grep vidstab` says whether it is.
