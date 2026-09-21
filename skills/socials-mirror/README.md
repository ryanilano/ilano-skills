# socials-mirror, explained for people

You want to know what a public figure has been building, posting or writing lately.
This takes a snapshot of their public profiles to local markdown in one command, using
only what those platforms serve to anyone without logging in.

## What it reads, and how

- **GitHub**: the public profile and up to a hundred repositories, newest activity
  first.
- **Bluesky**: the profile and about fifty recent posts, full text.
- **Any RSS or Atom feed**: full posts. This is also the clean path for Reddit, whose
  own `.rss` endpoints carry the whole post.
- **X and LinkedIn**: recorded as links only. Neither offers a clean public API and both
  forbid scraping in their terms. If you have a public RSS bridge for an X account, pass
  it as a feed.

It writes one markdown file per platform and an index.

## Why it stops at public data

No login, no cookies, no working around a login wall. If a source needs an account, it
becomes a link in the output, not a scrape. It sets a real user agent and spaces its
requests, because reading someone's profile is no excuse for hammering their server.

## Why it is a snapshot and not a monitor

It runs once when you ask. There is no loop, no schedule, no alerting. It is meant for
a public figure's public work, not for keeping tabs on a private individual.

## If you already subscribe in NetNewsWire

NetNewsWire keeps the full text of every post it has fetched in a local database. The
second script in this folder reads that database, read-only, so a feed you already
follow costs no network at all. It strips access keys out of private feed URLs before
writing anything, so a subscription secret cannot leak into a note.

## Requirements

Python 3, standard library only. The NetNewsWire reader is macOS only.
