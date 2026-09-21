# docs-mirror, explained for people

You need more than one page from a documentation site, or a whole blog. Fetching pages
one at a time through an AI assistant is slow, and every page passes through the model
whether you read it or not. This tool pulls the site to local markdown in one command,
then the assistant reads only the files it needs.

## What it does

Give it a URL. It crawls the docs from that root, or reads a blog's feed, and writes one
markdown file per page into a folder, plus a `README.md` index listing every page with
its title and size. It prints the folder path when it is done.

Running it again is nearly free. Every page is hashed and unchanged pages are skipped.

## Why it prefers a feed for blogs

Most RSS and Atom feeds carry the full text of every post. That means a twenty-post
blog is one request, not twenty one. The tool detects a feed from the URL or finds one
from the site's own link tag, and only fetches an individual page when the feed shipped
a summary instead of the article.

## Why it behaves politely by default

It reads `robots.txt` and honors it. If the site says no, it stops and tells you. It
spaces requests out, and the spacing is shared across all parallel workers so raising
the worker count cannot flood a server. There is an override for a site you own, and
only for that.

## What the exit codes mean

- **0**: pages written, go read them.
- **1**: every page failed. Check the URL and the network.
- **2**: nothing found. Probably not a docs root, or an empty feed.
- **3**: pages came back with no prose. The site renders in the browser, so the text is
  not in the HTML. This tool cannot help; a headless browser or the site's API can.
- **4**: `robots.txt` said no.

It never writes an empty file and calls it success.

## Requirements

Python 3, nothing else. No packages, no browser, no API key. Same on macOS and Linux.
