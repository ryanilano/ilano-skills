---
name: socials-mirror
description: "Snapshot a public figure's public profiles (GitHub, Bluesky, any RSS/Atom feed, Reddit .rss) to local markdown in one command. Use when asked what someone has been posting, building, or writing. Public data only; X and LinkedIn are recorded as links. Not for a private individual."
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
   `.rss` carries the full post, so the OAuth API is never needed for a profile read.
4. **Rate-limit and identify.** A `User-Agent` is set and calls are spaced; do
   not hammer someone's server for a profile read.

## NetNewsWire cache (zero network)

If NetNewsWire is already subscribed to a feed and refreshing it, the full post
text is in a local SQLite cache — read that instead of re-fetching.

```bash
python3 scripts/nnw_export.py --list                    # every feed + cached count
python3 scripts/nnw_export.py --feed engadget --since 2026-09-01 --out ./feeds --json
python3 scripts/nnw_export.py --all --out ./feeds       # everything (large)
```

Reads `~/Library/Containers/com.ranchero.NetNewsWire-Evergreen/.../Accounts/*/DB.sqlite3`
read-only (safe while NNW is open), maps feed IDs to titles via the account OPML,
prefers `contentHTML`→text. **Redacts secrets** (`?key=`/`token=`/… query params)
from every feed URL in output, so a private feed key never leaks. Prefer this
over live RSS for any feed you already subscribe to — it's free and offline.

## Requirements

`python3`, standard library only. macOS for the NetNewsWire reader (path is
NNW's macOS container).
