#!/usr/bin/env python3
"""Safely mutate a JSON config file. Parser-round-tripped, backed up, verified.

The whole reason this exists: editing settings.json (or any JSON config) by
hand, with sed, or through a shell heredoc is how a config silently goes
malformed and the harness quietly drops it. Every operation here loads the file
through a real JSON parser, mutates the in-memory object, writes it back, and
re-reads to prove it still parses. A malformed result errors before it can be
saved, and every write makes a timestamped backup first.

Usage:
  jsonpatch.py get     <file> <dotted.path>
  jsonpatch.py set     <file> <dotted.path> <json-value>
  jsonpatch.py insert  <file> <dotted.path-to-array> <json-object> [--at N]
  jsonpatch.py append  <file> <dotted.path-to-array> <json-object>
  jsonpatch.py delete  <file> <dotted.path>
  jsonpatch.py add-hook <file> <event> <matcher> <command> [--timeout N] [--first]
  jsonpatch.py validate <file>

Dotted paths index objects by key and arrays by integer, e.g.
  hooks.PreToolUse.0.matcher

--dry-run prints the result to stdout and writes nothing.

Idempotence is the caller's job except for add-hook, which refuses to add a
hook whose command is already present under that event.
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone


def load(path):
    with open(path) as fh:
        return json.load(fh)  # a parse error here means we never touch the file


def backup(path):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = f"{path}.bak-{stamp}"
    shutil.copy(path, dest)
    return dest


def write(path, data, dry_run):
    text = json.dumps(data, indent=2) + "\n"
    if dry_run:
        sys.stdout.write(text)
        return None
    b = backup(path)
    with open(path, "w") as fh:
        fh.write(text)
    with open(path) as fh:
        json.load(fh)  # prove the written file parses
    return b


def walk(data, dotted, make=False):
    """Return (parent, key) for the last segment of a dotted path."""
    parts = dotted.split(".") if dotted else []
    cur = data
    for p in parts[:-1]:
        key = int(p) if p.lstrip("-").isdigit() else p
        if isinstance(cur, list):
            cur = cur[key]
        else:
            if make and key not in cur:
                cur[key] = {}
            cur = cur[key]
    last = parts[-1]
    last = int(last) if last.lstrip("-").isdigit() else last
    return cur, last


def cmd_get(a):
    data = load(a.file)
    parent, key = walk(data, a.path)
    print(json.dumps(parent[key], indent=2))


def cmd_set(a):
    data = load(a.file)
    parent, key = walk(data, a.path, make=True)
    parent[key] = json.loads(a.value)
    b = write(a.file, data, a.dry_run)
    if b:
        print(f"set {a.path}. backup: {b}")


def cmd_insert(a):
    data = load(a.file)
    parent, key = walk(data, a.path, make=True)
    arr = parent[key]
    obj = json.loads(a.value)
    arr.insert(a.at if a.at is not None else len(arr), obj)
    b = write(a.file, data, a.dry_run)
    if b:
        print(f"inserted into {a.path}. length now {len(arr)}. backup: {b}")


def cmd_append(a):
    a.at = None
    cmd_insert(a)


def cmd_delete(a):
    data = load(a.file)
    parent, key = walk(data, a.path)
    del parent[key]
    b = write(a.file, data, a.dry_run)
    if b:
        print(f"deleted {a.path}. backup: {b}")


def cmd_add_hook(a):
    """Add a Claude Code hook under hooks.<event>, idempotent on the command."""
    data = load(a.file)
    events = data.setdefault("hooks", {})
    arr = events.setdefault(a.event, [])
    for entry in arr:
        for h in entry.get("hooks", []):
            if h.get("command") == a.command:
                print(f"already present under {a.event}. nothing to do.")
                return
    hook = {"type": "command", "command": a.command}
    if a.timeout is not None:
        hook["timeout"] = a.timeout
    entry = {"hooks": [hook]}
    if a.matcher:
        entry = {"matcher": a.matcher, "hooks": [hook]}
    arr.insert(0 if a.first else len(arr), entry)
    b = write(a.file, data, a.dry_run)
    if b:
        pos = "first" if a.first else "last"
        print(f"added hook under {a.event} ({pos}). backup: {b}")


def cmd_validate(a):
    load(a.file)
    print("valid")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("file")
        sp.add_argument("--dry-run", action="store_true")

    g = sub.add_parser("get"); g.add_argument("file"); g.add_argument("path"); g.set_defaults(fn=cmd_get)
    s = sub.add_parser("set"); common(s); s.add_argument("path"); s.add_argument("value"); s.set_defaults(fn=cmd_set)
    i = sub.add_parser("insert"); common(i); i.add_argument("path"); i.add_argument("value"); i.add_argument("--at", type=int); i.set_defaults(fn=cmd_insert)
    ap = sub.add_parser("append"); common(ap); ap.add_argument("path"); ap.add_argument("value"); ap.set_defaults(fn=cmd_append)
    d = sub.add_parser("delete"); common(d); d.add_argument("path"); d.set_defaults(fn=cmd_delete)
    h = sub.add_parser("add-hook"); common(h)
    h.add_argument("event"); h.add_argument("matcher"); h.add_argument("command")
    h.add_argument("--timeout", type=int); h.add_argument("--first", action="store_true")
    h.set_defaults(fn=cmd_add_hook)
    v = sub.add_parser("validate"); v.add_argument("file"); v.set_defaults(fn=cmd_validate)

    a = p.parse_args()
    try:
        a.fn(a)
    except (KeyError, IndexError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
