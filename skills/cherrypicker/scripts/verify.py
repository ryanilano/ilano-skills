#!/usr/bin/env python3
"""
Headless check of a built cherrypicker page.

  python3 verify.py merge.html [--shot check.png] [--browser webkit]

Loads the page in a headless browser (Chromium by default), picks version B
on the first row, types a note, reloads, and confirms both were hot-saved
(URL hash, then localStorage on a bare-URL reopen) with no page errors.
Writes a screenshot so the layout can be looked at, not just trusted.

Prints one JSON line to stdout; status to stderr. Exit 0 when the page passes.
Requires: pip install playwright && playwright install chromium (or the
browser named by --browser)
"""

import argparse
import json
import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Missing dependency. Run:  pip install playwright && playwright install chromium")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page')
    ap.add_argument('--shot', default=None, help='screenshot path (default: <page>.png)')
    ap.add_argument('--browser', default='chromium', choices=('chromium', 'firefox', 'webkit'),
                    help='Playwright browser to use (default: chromium)')
    args = ap.parse_args()

    path = os.path.abspath(args.page)
    shot = args.shot or os.path.splitext(path)[0] + '.png'
    errors = []

    with sync_playwright() as p:
        browser = getattr(p, args.browser).launch()
        page = browser.new_page(viewport={'width': 834, 'height': 1100})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('file://' + path)
        rows = page.locator('.row').count()
        page.click('#r0 .picker [data-p="b"]')
        page.fill('#r0 .panel textarea', 'keep the second line')
        page.wait_for_timeout(800)            # past the hot-save debounce
        page.reload()
        count = page.text_content('#count')
        pick = page.get_attribute('#r0', 'data-pick')
        note = page.input_value('#r0 .panel textarea')
        page.goto('file://' + path)           # bare URL: restore from localStorage
        note_local = page.input_value('#r0 .panel textarea')
        page.screenshot(path=shot, full_page=False)
        browser.close()

    want = 'keep the second line'
    ok = (not errors and pick == 'b' and count == '1 / %d' % rows
          and note == want and note_local == want)
    print(json.dumps({'ok': ok, 'rows': rows, 'count': count, 'row0_pick': pick,
                      'note_after_reload': note, 'note_from_local': note_local,
                      'errors': errors, 'screenshot': shot}))
    if not ok:
        print('FAIL: expected row 0 pick "b", count "1 / %d", the note hot-saved '
              'through a reload and a bare-URL reopen, no errors' % rows, file=sys.stderr)
        sys.exit(1)
    print('OK: pick and note survive reload; look at %s before delivering' % shot,
          file=sys.stderr)


if __name__ == '__main__':
    main()
