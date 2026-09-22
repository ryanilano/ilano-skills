---
name: socials-mirror
description: "Snapshot a public figure's public profiles (GitHub, Bluesky, any RSS/Atom feed, Reddit .rss, named X posts and threads) to local markdown in one command. Use when asked what someone has been posting, building, or writing, or when given an X, Twitter, tweet or thread link to read. Twitter means X: any twitter.com or x.com link, tweet, or thread goes through the X flags. Public data only; X timelines and LinkedIn are recorded as links. Not for a private individual."
---

# socials-mirror

Public figures, public data, one friendly snapshot. Not a stalker tool.

```bash
python3 scripts/socials_mirror.py "Ahmad Awais" \
    --github ahmadawais \
    --bsky ahmadawais.com \
    --rss https://www.reddit.com/user/MrAhmadAwais/.rss \
    --x https://x.com/MrAhmadAwais \
    --x-post https://x.com/MrAhmadAwais/status/1234567890123456789 \
    --linkedin https://www.linkedin.com/in/mrahmadawais \
    --out ./socials --json
```

Then read the files it wrote (last stdout line is the directory): one `.md` per
platform plus `index.md`, and `.json` with `--json`.

**Twitter is X.** A request that says Twitter, tweet, or twitter.com means the
X flags below; `--twitter`, `--tweet` and `--twitter-thread` are accepted as
aliases of `--x`, `--x-post` and `--x-thread`, and twitter.com links are
rewritten to x.com.

Every flag takes a handle or a URL and normalises it. Share and tracking
parameters (`utm_*`, `trk=`, `s=`, `fbclid`) are stripped from every input, so a
sharer's click never lands in a note. `--selftest` checks this without touching
the network.

| Flag | Accepts | Becomes |
|---|---|---|
| `--github` | `octocat`, `@octocat`, any `github.com/octocat/...` URL | `octocat` |
| `--bsky` | `alice.com`, `alice` or `@alice` (bsky.social appended), a `bsky.app/profile/...` URL, a DID | handle or DID |
| `--x` | `@jack`, `jack`, any x.com or twitter.com URL | `https://x.com/jack` |
| `--x-post` | `20`, `x.com/jack/status/20?s=21`, `twitter.com/i/web/status/20` (repeatable) | the post id, then its full text in `x.md` |
| `--x-thread` | the root post URL or id | every post in the thread, in order, in `x-thread.md`, from Thread Reader's public cache. Not cached there: the root post alone, and stderr says so |
| `--linkedin` | `jane`, `in/jane`, `company/acme`, any linkedin.com URL | `https://www.linkedin.com/in/jane` |
| `--rss` | `u/spez`, `r/selfhosted`, a Reddit profile or subreddit URL (`.rss` appended), any feed URL | a feed URL with no tracking |

## What pulls cleanly, and what doesn't

| Source | How | Notes |
|---|---|---|
| GitHub | public REST (unauth) | profile + up to 100 repos, sorted by last update |
| BlueSky | public AppView XRPC (unauth) | profile + ~50 recent posts, full text |
| RSS/Atom | plain fetch + parse | **the clean path for Reddit**: `https://www.reddit.com/user/<u>/.rss` or `/r/<sub>/.rss` carries full posts. Also blogs and RSS bridges |
| X / Twitter | profile: link only. Named posts: public embed endpoint (unauth) | the timeline is not served without a login (syndication answers 429, Nitter is gone, RSSHub needs an account cookie). Name posts with `--x-post <url-or-id>` (repeatable) and each is mirrored in full: text, date, author, quoted post, media and links. `--x-thread <root>` pulls a whole thread from threadreaderapp.com's public cache when someone has unrolled it there. A public RSS bridge via `--rss` still works as a feed |
| LinkedIn | guest view (unauth) | the logged-out profile or company page (the copy search engines index): name, headline, about, location, followers from its JSON-LD, plus the handful of recent posts the page lists, each fetched from its public embed page for the full text. Capped at 8 posts, spaced, stops on a 999 or 429. The timeline beyond that is not public. If LinkedIn answers with its login wall, the link is recorded instead and stderr says so |

## Rules

1. **Public only.** No login, no cookies, no auth circumvention, no logged-in
   content. A guest page that a site serves to anyone (LinkedIn's logged-out
   profile, X's embed endpoint) counts as public. If a source needs auth, it
   becomes a recorded link, not a scrape.
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

## LinkedIn jobs

```bash
python3 scripts/linkedin_jobs.py <job-url-or-id> [...]                 # full JD per posting
python3 scripts/linkedin_jobs.py --search "design engineer" --location "New York" -n 25
python3 scripts/linkedin_jobs.py --search "staff product designer" --location Remote -n 10 --full
```

Reads LinkedIn's logged-out `jobs-guest` endpoints: the guest job search (ten
cards per request, paged to `-n`) and the guest copy of a posting, which carries
the full description plus seniority, employment type, job function and
industries. LinkedIn throttles guests after a burst — the run stops on the first
HTTP 999 or 429 instead of digging in. Public-only, no login and no cookie, same
rule as the rest of this skill. `--selftest` checks the job-id parser.

## Requirements

`python3`, standard library only. macOS for the NetNewsWire reader (path is
NNW's macOS container).
