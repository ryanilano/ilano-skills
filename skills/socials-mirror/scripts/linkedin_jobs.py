#!/usr/bin/env python3
"""linkedin_jobs — LinkedIn job descriptions and job searches, logged out, to markdown.
Standard library only. Sibling of socials_mirror.py: same public-only rules.

LinkedIn serves two things to a client with no account: a guest job-search
endpoint (ten cards per page) and a small guest copy of any posting with the
full description and its criteria (seniority, employment type, function,
industries). Both are what a search engine indexes. No login, no cookie.

Usage:
  linkedin_jobs.py <job-url-or-id> [...]                 # full JD per posting
  linkedin_jobs.py --search "design engineer" --location "New York" -n 25
  linkedin_jobs.py --search "staff product designer" --location Remote -n 10 --full
  linkedin_jobs.py --selftest

Writes <out>/<slug>.md (one per posting, or one search listing) and prints the
paths. --full on a search also fetches every listed posting, spaced. LinkedIn
throttles guests after a burst (HTTP 999 or 429): the run stops on the first
one rather than digging in.
"""
from __future__ import annotations
import argparse, html as _html, json, os, re, sys, time
from urllib import request, error, parse

UA = "socials-mirror/1.0 (public-profile snapshot; +https://commandcode.ai style, respectful)"
DELAY = 1.0
GUEST = "https://www.linkedin.com/jobs-guest/jobs/api"
JOB_ID_RE = re.compile(r"(?:jobs/view/|jobPosting[:/]|currentJobId=|^)(?:[\w%-]*?-)?(\d{6,12})(?:[/?&#]|$)")


def get(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with request.urlopen(req, timeout=30) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:80] or "job"


def text_of(fragment: str) -> str:
    f = re.sub(r"<br\s*/?>", "\n", fragment)
    f = re.sub(r"</(p|li|h\d|div)>", "\n", f)
    f = re.sub(r"<li[^>]*>", "- ", f)
    t = _html.unescape(re.sub(r"<[^>]+>", "", f))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", t)).strip()


def job_id(s: str) -> str:
    """'4466698390', 'linkedin.com/jobs/view/4466698390', 'jobs/view/r-d-engineer-at-x-4466698390?refId=…' -> '4466698390'."""
    s = (s or "").strip().strip("<>")
    m = JOB_ID_RE.search(s)
    return m.group(1) if m else ""


def job(jid: str) -> dict:
    page = get(f"{GUEST}/jobPosting/{jid}")
    if "authwall" in page[:4000]:
        raise ValueError("LinkedIn answered with its login wall")
    def one(pat, flags=re.S):
        m = re.search(pat, page, flags)
        return text_of(m.group(1)) if m else ""
    crit = re.findall(r'<h3 class="description__job-criteria-subheader">(.*?)</h3>\s*'
                      r'<span class="description__job-criteria-text[^"]*">(.*?)</span>', page, re.S)
    desc = re.search(r'class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', page, re.S)
    return {"id": jid, "url": f"https://www.linkedin.com/jobs/view/{jid}",
            "title": one(r'<h2 class="[^"]*top-card-layout__title[^"]*"[^>]*>(.*?)</h2>'),
            "company": one(r'<a class="[^"]*topcard__org-name-link[^"]*"[^>]*>(.*?)</a>'),
            "location": one(r'<span class="[^"]*topcard__flavor--bullet[^"]*"[^>]*>(.*?)</span>'),
            "posted": one(r'<span class="[^"]*posted-time-ago__text[^"]*"[^>]*>(.*?)</span>'),
            "applicants": one(r'<(?:span|figcaption) class="[^"]*num-applicants__caption[^"]*"[^>]*>(.*?)</(?:span|figcaption)>'),
            "criteria": {_html.unescape(a).strip(): _html.unescape(b).strip() for a, b in crit},
            "description": text_of(desc.group(1)) if desc else ""}


def search(keywords: str, location: str = "", limit: int = 25) -> list:
    out, start = [], 0
    while len(out) < limit:
        q = parse.urlencode({"keywords": keywords, "location": location, "start": start})
        page = get(f"{GUEST}/seeMoreJobPostings/search?{q}")
        cards = re.findall(r'data-entity-urn="urn:li:jobPosting:(\d+)"(.*?)</li>', page, re.S)
        if not cards:
            break
        for jid, body in cards:
            def one(pat):
                m = re.search(pat, body, re.S)
                return text_of(m.group(1)) if m else ""
            out.append({"id": jid, "url": f"https://www.linkedin.com/jobs/view/{jid}",
                        "title": one(r'class="base-search-card__title"[^>]*>(.*?)</h3>'),
                        "company": one(r'class="base-search-card__subtitle"[^>]*>(.*?)</h4>'),
                        "location": one(r'class="job-search-card__location"[^>]*>(.*?)</span>'),
                        "posted": one(r'<time[^>]*>(.*?)</time>')})
            if len(out) >= limit:
                break
        start += len(cards)
        time.sleep(DELAY)
    return out


def job_md(j: dict) -> str:
    facts = [x for x in (j.get("company"), j.get("location"), j.get("posted"), j.get("applicants")) if x]
    lines = [f"# {j.get('title') or j['id']}", "", "  ·  ".join(facts), "", j["url"], ""]
    if j.get("criteria"):
        lines += ["| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in j["criteria"].items()] + [""]
    lines += ["## Description", "", j.get("description", ""), ""]
    return "\n".join(lines)


def search_md(keywords: str, location: str, rows: list) -> str:
    lines = [f"# LinkedIn jobs: {keywords}" + (f" in {location}" if location else ""), "",
             f"{len(rows)} postings, guest search, {time.strftime('%Y-%m-%d %H:%M %Z')}.", "",
             "| Title | Company | Location | Posted | Link |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['title']} | {r['company']} | {r['location']} | {r['posted']} | {r['url']} |")
    return "\n".join(lines) + "\n"


def write(out_dir: str, name: str, content: str, ext: str = ".md") -> str:
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"{name}{ext}")
    with open(p, "w") as f:
        f.write(content)
    return p


def selftest() -> int:
    cases = [("4466698390", "4466698390"),
             ("https://www.linkedin.com/jobs/view/4466698390/?refId=abc&trackingId=xyz", "4466698390"),
             ("https://www.linkedin.com/jobs/view/r-d-engineer-at-oetiker-group-4466698390", "4466698390"),
             ("https://www.linkedin.com/jobs/search/?currentJobId=4466698390&keywords=x", "4466698390"),
             ("urn:li:jobPosting:4466698390", "4466698390"),
             ("https://www.linkedin.com/in/someone", "")]
    bad = [(i, o, job_id(i)) for i, o in cases if job_id(i) != o]
    for i, want, got in bad:
        print(f"FAIL job_id({i!r}) want {want!r} got {got!r}", file=sys.stderr)
    print(f"job_id: {len(cases) - len(bad)}/{len(cases)} ok", file=sys.stderr)
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LinkedIn job descriptions and searches, logged out, to markdown.")
    ap.add_argument("jobs", nargs="*", help="job URL or id")
    ap.add_argument("--search", help="keywords for a guest job search")
    ap.add_argument("--location", default="", help="location text for the search")
    ap.add_argument("-n", "--limit", type=int, default=25, help="search results to list (10 per request)")
    ap.add_argument("--full", action="store_true", help="also fetch every listed posting's full JD")
    ap.add_argument("--out", default="./jobs")
    ap.add_argument("--json", action="store_true", help="also write .json beside each .md")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.jobs and not a.search:
        ap.error("give a job URL/id or --search")

    ids = [job_id(j) for j in a.jobs]
    if a.search:
        rows = search(a.search, a.location, a.limit)
        name = slugify(f"search-{a.search}-{a.location}")
        print(write(a.out, name, search_md(a.search, a.location, rows)))
        if a.json:
            write(a.out, name, json.dumps(rows, indent=2), ".json")
        if a.full:
            ids += [r["id"] for r in rows]
        print(f"  {len(rows)} postings listed", file=sys.stderr)

    rc = 0
    for jid in [i for i in ids if i]:
        try:
            j = job(jid)
            name = slugify(f"{j.get('company')}-{j.get('title')}-{jid}")
            print(write(a.out, name, job_md(j)))
            if a.json:
                write(a.out, name, json.dumps(j, indent=2), ".json")
        except (error.HTTPError, error.URLError, ValueError) as e:
            print(f"  fail {jid}: {e}", file=sys.stderr)
            rc = 1
            if isinstance(e, error.HTTPError) and e.code in (999, 429):
                print("  throttled by LinkedIn; stopping", file=sys.stderr)
                break
        time.sleep(DELAY)
    return rc


if __name__ == "__main__":
    sys.exit(main())
