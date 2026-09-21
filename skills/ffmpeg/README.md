# ffmpeg, explained for people

ffmpeg does almost anything to a video, audio or image file, and its command lines are
notoriously hard to get right. This skill puts one small Python helper in front of it.
Each common job is a named command that returns JSON, so an assistant can run it,
check the result and move on without guessing at flags.

## What the helper covers

Cut, merge, compress, convert, change speed, make a GIF, burn in subtitles, pull a
thumbnail or frames, add a watermark, stabilize shaky footage, and inspect a file.
Anything beyond that falls back to raw ffmpeg, with worked recipes in
`references/commands.md`.

## Why it always inspects first

Every job starts by probing the input for duration, resolution, codecs and size.
Output settings come from those numbers rather than from assumptions. When the job is
done it probes the output too, so "done" means the JSON shows the expected duration and
codecs and no error.

## Why it copies streams when it can

If two clips share the same codecs, merging them can copy the streams without
re-encoding. That is fast and lossless. Only when codecs differ does it re-encode, and
the helper tells you when that is needed.

## The one quality knob

Compression uses CRF. Lower is better quality and bigger. Roughly: 18 for archiving,
23 as a default, 28 for sharing, 32 for social. Each step of six about halves the file
size.

## Two things that look like errors and are not

A timeout on a long video means use a faster preset or cut first. "No such file" is
almost always a relative path; the helper wants absolute paths in and out.

## With yt-cc

If yt-cc saved a video alongside its transcript, the transcript's timestamps tell you
where to cut, where to grab a frame, and which demo to turn into a GIF.

## Origin

Forked from an MIT-licensed ffmpeg skill; the upstream license and the list of changes
are in this folder. The helper script is unchanged from upstream.

## Requirements

`ffmpeg` and `ffprobe` on the path. Stabilization needs the vidstab filter compiled in.
