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
- **X, which is Twitter**: the two names mean the same thing here, and the tool accepts
  either spelling on its flags and either domain in a link. The profile is recorded as a
  link, because X serves no timeline to anyone who is not logged in. Any post you name by URL or id is mirrored in full, using the same
  public endpoint the embed widget uses, with no account involved. A whole thread comes
  from Thread Reader's public cache when someone has unrolled it there; otherwise you get
  the root post and a note saying so. If you have a public RSS bridge for an X account,
  pass it as a feed.
- **LinkedIn**: the logged-out copy of a profile or company page, which is what a search
  engine sees: name, headline, the about text, location, follower count, and the few
  recent posts the page lists, each with its full text. LinkedIn throttles guests after
  a burst, so the tool takes at most eight posts, waits between them, and stops the
  moment it is refused. If the page comes back as a login wall, you get the link and a
  note instead.

It writes one markdown file per platform and an index.

## Give it what you have

Each source takes a bare handle or a pasted link. A handle gets its site filled in
(a Bluesky name without a dot becomes a bsky.social account, a Reddit `u/name` becomes
the feed for that user). A pasted link loses its share and tracking tags, so the note
records the profile, not the person who sent you the link.

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

## Job descriptions

LinkedIn shows a logged out visitor two useful things, and a third script in this folder
reads both of them. The first is job search. Give it what you would type into the search
box, a phrase and a place, and it writes a table of postings with the title, the company,
the location and how long ago each one went up. The second is a single posting. Give it
the link and it writes the whole job description, along with the seniority level, the
employment type, the job function and the industries. LinkedIn slows down visitors who
ask for too much at once, so the script stops the moment it is refused rather than
pushing harder. Nothing here needs an account or a password.

## Requirements

Python 3, standard library only, for all three scripts. The NetNewsWire reader is macOS only.
