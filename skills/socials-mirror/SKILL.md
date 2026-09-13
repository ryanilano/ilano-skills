---
name: socials-mirror
description: "Snapshot a PUBLIC figure's open, public profiles into zero-waste markdown (and JSON) — GitHub, BlueSky, and any RSS/Atom feed (Reddit .rss, blogs, bridges). Use when you want a clean read on someone's public work and posts (a creator, a founder, an author Ryan cites) in one small set of files. Friendly and public-only by design: no login, no auth circumvention, no scraping of logged-in content, no monitoring loop. X/Twitter and LinkedIn are auth-walled, so it records their profile link and mirrors a user-supplied public RSS bridge if given. Do NOT use to surveil a private individual."
---

# socials-mirror

Public figures, public data, one friendly snapshot. Not a stalker tool.

```bash
python3 scripts/socials_mirror.py "Ahmad Awais" \
    --github ahmadawais \
    --bsky ahmadawais.com \
    --rss https://www.reddit.com/user/MrAhmadAwais/.rss \
    --x https://x.com/MrAhmadAwais \
    --linkedin https://www.linkedin.com/in/mrahmadawais \
    --out ./socials --json
```

Then read the files it wrote (last stdout line is the directory): one `.md` per
platform plus `index.md`, and `.json` with `--json`.

## What pulls cleanly, and what doesn't

| Source | How | Notes |
|---|---|---|
| GitHub | public REST (unauth) | profile + up to 100 repos, sorted by last update |
| BlueSky | public AppView XRPC (unauth) | profile + ~50 recent posts, full text |
| RSS/Atom | plain fetch + parse | **the clean path for Reddit**: `https://www.reddit.com/user/<u>/.rss` or `/r/<sub>/.rss` carries full posts. Also blogs and RSS bridges |
| X / Twitter | link only | no clean public API; ToS forbids scraping logged-in content. Pass a public RSS bridge via `--rss` to mirror it as a feed |
| LinkedIn | link only | auth-walled; ToS forbids scraping. Link recorded only |

## Rules

1. **Public only.** No login, no cookies, no auth circumvention, no logged-in
   content. If a source needs auth, it becomes a recorded link, not a scrape.
2. **Be friendly, not a stalker.** One-shot snapshot of a public figure's public
   work. No monitoring loop, no aggregating private individuals.
3. **RSS is the kindest and cleanest.** One request, full posts. Reddit's own
   `.rss` (the NetNewsWire path) beats fighting their OAuth. Reddit API access
   exists if you ever need comments/history, but the awkward OAuth flow is not
   worth it when `.rss` already carries the full post.
4. **Rate-limit and identify.** A `User-Agent` is set and calls are spaced; do
   not hammer someone's server for a profile read.

## Requirements

`python3`, standard library only.
