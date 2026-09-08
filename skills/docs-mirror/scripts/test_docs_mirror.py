#!/usr/bin/env python3
"""
Self-contained checks for the markdown the docs-mirror emitter produces.

Stdlib only, no network. Run it:

    python3 ~/.claude/skills/docs-mirror/test_docs_mirror.py

Every case here is a CommonMark/GFM rule the emitter used to break:
code spans need a delimiter longer than any backtick run inside them, a table
is not a table without its |---| delimiter row, and a literal | inside a cell
has to be escaped or it ends the cell early.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("docs-mirror.py")
spec = importlib.util.spec_from_file_location("docs_mirror", SCRIPT)
dm = importlib.util.module_from_spec(spec)
sys.modules["docs_mirror"] = dm
spec.loader.exec_module(dm)

failures: list[str] = []


def check(name: str, html_in: str, want: str) -> None:
    got = dm.to_markdown(html_in).strip()
    if got == want.strip():
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}")
        print(f"        want: {want.strip()!r}")
        print(f"        got:  {got!r}")
        failures.append(name)


def check_that(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
    if not ok:
        failures.append(name)
        if detail:
            print(f"        {detail}")


print("code spans")

# (a) A code span whose content contains a backtick. CommonMark: the delimiter
# must be longer than the longest run inside, and the content is padded with a
# space when it starts or ends with a backtick.
check("backtick inside a code span",
      "<p>Run <code>echo `hi`</code> now.</p>",
      "Run `` echo `hi` `` now.")

check("backtick in the middle only",
      "<p>The <code>a`b</code> token.</p>",
      "The ``a`b`` token.")

check("a run of two backticks needs three",
      "<p>Look at <code>x ``y`` z</code>.</p>",
      "Look at ```x ``y`` z```.")

check("entities are measured as the reader sees them",
      "<p>Quote <code>&#96;x&#96;</code>.</p>",
      "Quote `` `x` ``.")

check("plain code span is left alone",
      "<p>Use <code>--out DIR</code>.</p>",
      "Use `--out DIR`.")

print("tables")

# (b) A header and two rows. Without the |---| row this is one paragraph.
TABLE = """
<table>
  <thead><tr><th>Flag</th><th>Use</th></tr></thead>
  <tbody>
    <tr><td>--out DIR</td><td>where to write</td></tr>
    <tr><td>--jobs N</td><td>parallel requests</td></tr>
  </tbody>
</table>
"""
check("header plus two rows, with the delimiter row",
      TABLE,
      "| Flag | Use |\n"
      "|---|---|\n"
      "| --out DIR | where to write |\n"
      "| --jobs N | parallel requests |")

# (c) A literal pipe inside a cell has to be escaped.
check("a pipe inside a cell is escaped",
      "<table><tr><th>Pattern</th><th>Means</th></tr>"
      "<tr><td>a|b</td><td>a or b</td></tr></table>",
      "| Pattern | Means |\n"
      "|---|---|\n"
      "| a\\|b | a or b |")

check("a pipe written as an entity is escaped too",
      "<table><tr><th>H</th></tr><tr><td>x&#124;y</td></tr></table>",
      "| H |\n|---|\n| x\\|y |")

check("a code span in a cell keeps its pipe escaped",
      "<table><tr><th>Flag</th><th>Use</th></tr>"
      "<tr><td><code>--only a|b</code></td><td>filter</td></tr></table>",
      "| Flag | Use |\n"
      "|---|---|\n"
      "| `--only a\\|b` | filter |")

check("a headerless table still gets a header and delimiter",
      "<table><tr><td>one</td><td>two</td></tr>"
      "<tr><td>three</td><td>four</td></tr></table>",
      "| | |\n"                    # empty cells; valid GFM either way
      "|---|---|\n"
      "| one | two |\n"
      "| three | four |")

check("short rows are padded to the table width",
      "<table><tr><th>a</th><th>b</th><th>c</th></tr>"
      "<tr><td>1</td></tr></table>",
      "| a | b | c |\n"
      "|---|---|---|\n"
      "| 1 | | |")

check("a cell with a line break stays on one line",
      "<table><tr><th>H</th></tr><tr><td>one<br>two</td></tr></table>",
      "| H |\n|---|\n| one two |")

# Structural check: whatever the input, the delimiter row must match the
# header's column count, or no parser will see a table.
grid = dm.to_markdown(TABLE).strip().splitlines()
check_that("delimiter row is row 2 and matches the header width",
           re.fullmatch(r"\|(?:\s*:?-{3,}:?\s*\|)+", grid[1]) is not None
           and grid[1].count("|") == grid[0].count("|"),
           f"header={grid[0]!r} delim={grid[1]!r}")

print("fenced code blocks")

check("a fence is longer than any backtick run inside",
      "<pre>```\nnot a fence\n```</pre>",
      "````\n```\nnot a fence\n```\n````")

check("indentation inside a code block survives",
      "<pre><code>def f():\n    return 1</code></pre>",
      "```\ndef f():\n    return 1\n```")

check("code block entities are unescaped exactly once",
      "<pre>&amp;lt;div&amp;gt;</pre>",
      "```\n&lt;div&gt;\n```")

check("a code block inside a cell becomes a code span",
      "<table><tr><th>H</th></tr><tr><td><pre>a = 1\nb = 2</pre></td></tr></table>",
      "| H |\n|---|\n| `a = 1 b = 2` |")

print("prose is unchanged")

check("headings, links, lists and emphasis still work",
      "<h2>Title</h2><p>See <a href=\"/x\">x</a> and <strong>bold</strong>.</p>"
      "<ul><li>one</li><li>two</li></ul>",
      # the blank line between items is pre-existing: a loose list
      "## Title\n\nSee [x](/x) and **bold**.\n\n- one\n\n- two")

check_that("no placeholder leaks into the output",
           "\x00" not in dm.to_markdown(
               "<p>a</p><pre>code</pre><table><tr><th>h</th></tr>"
               "<tr><td><pre>x</pre></td></tr></table>"))

print("README index rows")

check_that("md_cell escapes a pipe in an index title",
           dm.md_cell("Pipes | and | more") == "Pipes \\| and \\| more",
           dm.md_cell("Pipes | and | more"))

print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    raise SystemExit(1)
print("all checks passed")
