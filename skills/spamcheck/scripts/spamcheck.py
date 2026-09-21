#!/usr/bin/env python3
"""spamcheck - audit one email's unsubscribe machinery and name what is actually broken.

Standard library only. Nothing is sent. Nothing is deleted. The only network calls
are HEAD/GET probes of the unsubscribe URLs that the message itself supplied, and
they are off unless you pass --probe.

    python3 spamcheck.py --eml message.eml
    python3 spamcheck.py --paste < pasted.txt
    python3 spamcheck.py --url https://example.org/unsubscribe/abc --probe

Exit 0 = nothing actionable found. Exit 1 = at least one finding. Exit 2 = bad input.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser, Parser
from urllib import error, request

UA = "spamcheck/1.0 (+unsubscribe compliance audit; contact the sender)"
TIMEOUT = 20

# ---------------------------------------------------------------- classification

COMMERCIAL_HINTS = [
    "% off", "sale", "shop now", "buy now", "add to cart", "free shipping",
    "coupon", "promo code", "order now", "limited time", "subscribe and save",
    "our new product", "pricing", "upgrade your plan", "webinar",
]
POLITICAL_HINTS = [
    "paid for by", "actblue", "winred", "contribute", "chip in", "donate",
    "grassroots", "campaign", "for congress", "for senate", "for ny",
    "committee", "fec", "ballot", "primary", "re-elect", "reelect",
]
NONPROFIT_HINTS = [
    "501(c)(3)", "tax-deductible", "your gift", "charitable", "foundation",
]

# US street-address shape: number, words, then STATE ZIP. Deliberately loose; a
# false positive here is safer than telling someone a lawful email is unlawful.
ADDRESS_RE = re.compile(
    r"\d{1,6}\s+[\w.\-' ]{3,40}\b"
    r"(?:st(?:reet)?|ave(?:nue)?|road|rd|blvd|boulevard|lane|ln|drive|dr|way|"
    r"suite|ste|floor|fl|p\.?\s*o\.?\s*box|pmb|court|ct|plaza|parkway|pkwy)\b"
    r"[\s\S]{0,80}?\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b",
    re.I,
)
PAIDFOR_RE = re.compile(r"paid\s+for\s+by\s+[^\n<]{3,120}", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)


def is_transactional(msg):
    """True for auto-replies and account/ticket notices.

    These are 'transactional or relationship' messages under 15 U.S.C. 7702(17),
    exempt from the opt-out and postal-address requirements entirely. Flagging a
    support ticket acknowledgement for a missing unsubscribe link is the fastest
    way to make this tool useless, so the check runs before classification.
    """
    auto = (msg.get("Auto-Submitted", "") or "").strip().lower()
    if auto and auto != "no":
        return True, f"Auto-Submitted: {auto}"
    if msg.get("X-Auto-Response-Suppress"):
        return True, "X-Auto-Response-Suppress present"
    prec = (msg.get("Precedence", "") or "").strip().lower()
    if prec in ("auto_reply", "auto-reply"):
        return True, f"Precedence: {prec}"
    if msg.get("In-Reply-To"):
        return True, "In-Reply-To present, so this is a reply to something you sent"
    return False, ""


def classify(text):
    """Return (kind, why). Kind drives which law is even in play."""
    low = text.lower()
    pol = sum(1 for h in POLITICAL_HINTS if h in low)
    com = sum(1 for h in COMMERCIAL_HINTS if h in low)
    npo = sum(1 for h in NONPROFIT_HINTS if h in low)
    if pol >= 2 and pol >= com:
        return "political", f"{pol} political markers vs {com} commercial"
    if npo >= 2 and npo > com:
        return "nonprofit", f"{npo} nonprofit markers vs {com} commercial"
    if com >= 1:
        return "commercial", f"{com} commercial markers vs {pol} political"
    return "unclear", f"political={pol} commercial={com} nonprofit={npo}"


# ---------------------------------------------------------------- opt-out ledger

LEDGER = os.path.expanduser(
    os.environ.get("SPAMCHECK_LEDGER",
                   "~/.local/share/spamcheck/optouts.jsonl"))


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 \
        else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def federal_holidays(year):
    """OPM's 11 federal holidays, with the weekend-observance shift applied.

    Computed rather than hardcoded so the count stays correct in any year. This
    is what makes a business-day figure defensible if anyone checks it.
    """
    fixed = [date(year, 1, 1), date(year, 6, 19), date(year, 7, 4),
             date(year, 11, 11), date(year, 12, 25)]
    observed = set()
    for d in fixed:
        if d.weekday() == 5:
            d -= timedelta(days=1)
        elif d.weekday() == 6:
            d += timedelta(days=1)
        observed.add(d)
    observed.add(_nth_weekday(year, 1, 0, 3))    # MLK, 3rd Monday January
    observed.add(_nth_weekday(year, 2, 0, 3))    # Washington, 3rd Monday February
    observed.add(_last_weekday(year, 5, 0))      # Memorial, last Monday May
    observed.add(_nth_weekday(year, 9, 0, 1))    # Labor, 1st Monday September
    observed.add(_nth_weekday(year, 10, 0, 2))   # Columbus, 2nd Monday October
    observed.add(_nth_weekday(year, 11, 3, 4))   # Thanksgiving, 4th Thursday
    return observed


def business_days_between(start, end):
    """Business days strictly after `start`, through `end`. Weekends and the
    federal holidays are excluded. Returns 0 if end is not after start."""
    if end <= start:
        return 0
    hol = federal_holidays(start.year) | federal_holidays(end.year)
    n, d = 0, start + timedelta(days=1)
    while d <= end:
        if d.weekday() < 5 and d not in hol:
            n += 1
        d += timedelta(days=1)
    return n


def org_domain(host):
    """Crude registrable-domain guess, enough to match e.example.com to example.com."""
    parts = [p for p in host.lower().strip(".").split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def ledger_rows():
    if not os.path.exists(LEDGER):
        return []
    rows = []
    with open(LEDGER, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def ledger_add(domain, when, note):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    row = {"domain": domain.lower().lstrip("@"), "clicked": when.isoformat(),
           "note": note or "", "recorded": datetime.now(timezone.utc)
           .isoformat().replace("+00:00", "Z")}
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def ledger_match(from_header):
    """Return the earliest recorded click for this sender, or None."""
    m = re.search(r"@([\w.\-]+)", from_header or "")
    if not m:
        return None
    host = m.group(1)
    want = {host.lower(), org_domain(host)}
    hits = [r for r in ledger_rows()
            if r.get("domain", "") in want or org_domain(r.get("domain", "")) in want]
    return min(hits, key=lambda r: r["clicked"]) if hits else None


# ---------------------------------------------------------------- parsing

def load_message(args):
    if args.eml:
        with open(args.eml, "rb") as fh:
            return BytesParser(policy=policy.default).parse(fh)
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit("nothing on stdin; pipe the raw message or use --eml")
    return Parser(policy=policy.default).parsestr(raw)


def body_text(msg):
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "text":
                try:
                    parts.append(part.get_content())
                except Exception:
                    pass
    else:
        try:
            parts.append(msg.get_content())
        except Exception:
            parts.append(str(msg.get_payload()))
    return "\n".join(str(p) for p in parts)


def header_unsub(msg):
    """RFC 2369 List-Unsubscribe plus RFC 8058 one-click."""
    raw = msg.get("List-Unsubscribe", "") or ""
    urls, mailtos = [], []
    for item in re.findall(r"<([^>]+)>", raw):
        (mailtos if item.lower().startswith("mailto:") else urls).append(item)
    post = (msg.get("List-Unsubscribe-Post", "") or "").strip()
    one_click = "one-click" in post.lower()
    return {
        "present": bool(raw.strip()),
        "raw": raw.strip(),
        "https_urls": urls,
        "mailtos": mailtos,
        "post_header": post,
        "rfc8058_one_click": one_click,
    }


def body_unsub(text):
    """Links whose URL or surrounding text smells like an opt-out."""
    hits = []
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(".,);]")
        window = text[max(0, m.start() - 220): m.end() + 60].lower()
        if any(k in url.lower() for k in
               ("unsub", "optout", "opt-out", "opt_out", "preferences",
                "email_preference", "manage", "remove")) or \
           any(k in window for k in
               ("unsubscribe", "stop receiving", "opt out", "click here",
                "update your email", "change your name")):
            host = url.split("://", 1)[-1].split("/", 1)[0].lower()
            if host.endswith("w3.org") or host.endswith("schema.org"):
                continue          # DTD and schema refs, never opt-out links
            if url.rstrip().endswith("="):
                continue          # truncated query, no token to act on
            if url not in hits:
                hits.append(url)
    return hits


# ---------------------------------------------------------------- probing

def probe(url):
    """Follow redirects, report the real status. Never sends a POST."""
    out = {"url": url, "status": None, "final_url": None, "error": None,
           "elapsed_ms": None}
    started = time.time()
    for method in ("HEAD", "GET"):
        req = request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with request.urlopen(req, timeout=TIMEOUT) as resp:
                out["status"] = resp.status
                out["final_url"] = resp.geturl()
                out["error"] = None
                break
        except error.HTTPError as exc:
            out["status"] = exc.code
            out["final_url"] = exc.url if hasattr(exc, "url") else url
            out["error"] = None
            if method == "GET" or exc.code != 405:
                break
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
            if method == "GET":
                break
    out["elapsed_ms"] = int((time.time() - started) * 1000)
    return out


# ---------------------------------------------------------------- findings

def audit(msg, text, probed):
    """Return findings, most actionable first. Each names the rule and the fix."""
    f = []
    hdr = header_unsub(msg)

    trans, trans_why = is_transactional(msg)
    if trans:
        f.append(dict(
            id="transactional", severity="info",
            title="Transactional or relationship message, not bulk mail",
            detail=f"{trans_why}. A message facilitating a transaction you agreed "
                   "to, or notifying you about an account, membership or support "
                   "request, is a 'transactional or relationship message'. It is "
                   "carved out of the definition of commercial electronic mail, so "
                   "the opt-out mechanism and postal address requirements do not "
                   "apply. Only the header-falsity prohibition does. No findings "
                   "about unsubscribe machinery are raised for this message.",
            rule="15 U.S.C. 7702(17); 7704(a)(1)",
        ))
        return f, "transactional", trans_why, hdr

    kind, why = classify(text + " " + (msg.get("From", "") or ""))

    if not hdr["present"]:
        f.append(dict(
            id="no-list-unsubscribe", severity="high",
            title="No List-Unsubscribe header",
            detail="RFC 2369 header absent, so no mail client can offer a one-click "
                   "opt-out. Bulk senders to Gmail and Yahoo have been required to "
                   "supply it since their 2024 bulk sender rules.",
            rule="RFC 2369; Gmail/Yahoo bulk sender requirements",
        ))
    elif hdr["https_urls"] and not hdr["rfc8058_one_click"]:
        f.append(dict(
            id="no-one-click", severity="medium",
            title="List-Unsubscribe present but not one-click",
            detail="No List-Unsubscribe-Post: List-Unsubscribe=One-Click, so the "
                   "header link is not RFC 8058 one-click and the mail client "
                   "button may do nothing useful.",
            rule="RFC 8058",
        ))

    for u in hdr["https_urls"]:
        tail = u.split("://", 1)[-1]
        if "@" in tail:
            f.append(dict(
                id="mailto-in-https-slot", severity="high",
                title="List-Unsubscribe https target is really an email address",
                detail=f"{u} carries an @ in the path or query, so an inbound-mail "
                       "address has been put where an https endpoint belongs. Mail "
                       "clients POST to this URL, they do not mail it. This is a "
                       "sender or platform misconfiguration and it breaks the "
                       "unsubscribe button in every client that honors the header.",
                rule="RFC 2369 sec. 3.2; RFC 8058 sec. 3",
            ))

    dead = [p for p in probed if p["status"] and p["status"] >= 400]
    dead_header = [p for p in dead if p["url"] in hdr["https_urls"]]
    if dead_header and hdr["rfc8058_one_click"]:
        f.append(dict(
            id="one-click-advertised-but-dead", severity="high",
            title="One-click unsubscribe is advertised and the target is dead",
            detail="List-Unsubscribe-Post declares one-click support, so every mail "
                   "client draws an Unsubscribe button, and the https target it "
                   "posts to returns an error. The button silently does nothing. "
                   "This is the single most common reason an unsubscribe control "
                   "appears to be ignored, and it is the sender's fault, not the "
                   "mail provider's.",
            rule="RFC 8058 sec. 3.1; 15 U.S.C. 7704(a)(3)(A) if commercial",
        ))
    unreachable = [p for p in probed if p["error"]]
    for p in dead:
        f.append(dict(
            id="unsub-http-error", severity="high",
            title=f"Unsubscribe URL returns HTTP {p['status']}",
            detail=f"{p['url']} -> {p['status']}. For a COMMERCIAL message this is "
                   "the violation on its face: the opt-out mechanism must be "
                   "functioning and must remain capable of receiving requests for "
                   "no less than 30 days after the send. Note the safe harbor: it "
                   "does not fail if it is unexpectedly and temporarily down from "
                   "a technical problem beyond the sender's control and is fixed "
                   "in a reasonable time. Probe twice, days apart, before calling "
                   "it persistent.",
            rule="15 U.S.C. 7704(a)(3)(A)(i)-(ii); safe harbor at 7704(a)(3)(C); "
                 "16 CFR 316.5. Platform acceptable-use policy applies regardless "
                 "of category.",
        ))
    for p in unreachable:
        f.append(dict(
            id="unsub-unreachable", severity="medium",
            title="Unsubscribe URL could not be reached",
            detail=f"{p['url']}: {p['error']}. Re-run before relying on it; a "
                   "transient network failure is not a violation.",
            rule="inconclusive",
        ))

    if not ADDRESS_RE.search(text):
        f.append(dict(
            id="no-postal-address",
            severity="high" if kind == "commercial" else "low",
            title="No physical postal address found in the message",
            detail="CAN-SPAM requires a valid physical postal address in every "
                   "commercial message. For political and nonprofit mail this is "
                   "not required, so it is recorded here as a fact, not a charge.",
            rule="15 U.S.C. 7704(a)(5)(A)(iii) (commercial messages only)",
        ))

    if kind == "political" and not PAIDFOR_RE.search(text):
        f.append(dict(
            id="no-paid-for-by", severity="high",
            title="Political message with no 'paid for by' disclaimer",
            detail="A political committee must carry a disclaimer on 'electronic "
                   "mail of more than 500 substantially similar communications'. "
                   "It must clearly state the communication was paid for by the "
                   "authorized committee, and be clear and conspicuous rather than "
                   "difficult to read or easily overlooked. You cannot see the send "
                   "volume from one inbox, so treat the 500 threshold as inferred. "
                   "Note that a broken unsubscribe link is NOT an FEC violation; a "
                   "missing disclaimer is. Filing requires a NOTARIZED complaint "
                   "with your real name and address, emailed to EnfComplaint@fec.gov.",
            rule="11 CFR 110.11(a)(1), (b)(1), (c)(1); filing at 11 CFR 111.4(b)",
        ))

    if kind in ("political", "nonprofit"):
        f.append(dict(
            id="canspam-scope", severity="info",
            title=f"CAN-SPAM likely does not apply ({kind} message)",
            detail=f"Classified {kind} ({why}). CAN-SPAM reaches commercial "
                   "electronic mail, meaning messages whose primary purpose is "
                   "advertising a commercial product or service. The FTC has said "
                   "so directly about campaign mail, and the 2005 final rule "
                   "states the Commission does not intend the criteria to regulate "
                   "non-commercial speech. Route the complaint to the sending "
                   "platform, not the FTC. There is no entity-type exemption: a "
                   "nonprofit selling something commercial IS covered, so the call "
                   "turns on the message, not the sender.",
            rule="15 U.S.C. 7702(2)(A); 16 CFR 316.3(a) n.1; 70 FR 3110, 3125",
        ))

    rec = ledger_match(msg.get("From", ""))
    if rec:
        sent = None
        raw_date = msg.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            sent = parsedate_to_datetime(raw_date).date()
        except Exception:
            sent = None
        clicked = date.fromisoformat(rec["clicked"])
        if sent and sent > clicked:
            n = business_days_between(clicked, sent)
            if n > 10:
                f.append(dict(
                    id="past-honor-window", severity="high",
                    title=f"Sent {n} business days after you opted out",
                    detail=f"You recorded an opt-out for {rec['domain']} on "
                           f"{clicked}. This message is dated {sent}, which is "
                           f"{n} business days later, past the 10 business day "
                           "limit. Weekends and federal holidays are already "
                           "excluded. This is the cleanest violation available: "
                           "it needs no argument about whether a link was "
                           "temporarily down."
                           + (f" Note: {rec['note']}" if rec.get("note") else ""),
                    rule="15 U.S.C. 7704(a)(4)(A)(i)",
                ))
            else:
                f.append(dict(
                    id="within-honor-window", severity="info",
                    title=f"{n} business day(s) since your opt-out, still inside 10",
                    detail=f"Opt-out recorded for {rec['domain']} on {clicked}; this "
                           f"message is dated {sent}. They are still within the "
                           "window, so this one is lawful. Keep every message "
                           "that arrives from here on: the first past day 10 is the violation.",
                    rule="15 U.S.C. 7704(a)(4)(A)(i)",
                ))
    elif msg.get("From"):
        f.append(dict(
            id="no-optout-recorded", severity="info",
            title="No opt-out click on record for this sender",
            detail="The 10 business day rule is the strongest thing in the statute "
                   "and it only works if the click is dated. Record it: "
                   "spamcheck.py --opt-out <domain>",
            rule="15 U.S.C. 7704(a)(4)(A)(i)",
        ))

    if kind == "commercial":
        f.append(dict(
            id="no-private-right", severity="info",
            title="You cannot sue over this yourself",
            detail="CAN-SPAM has no private right of action for a recipient. "
                   "Enforcement belongs to the FTC, the sector regulators in "
                   "7706(b), a state attorney general, or an internet access "
                   "provider. A state AG needs a PATTERN OR PRACTICE for the "
                   "opt-out provisions, not one bad send. Civil penalties run up "
                   "to $53,088 per email (2025 level, held for 2026), which is why "
                   "a report is still worth filing even though you collect none "
                   "of it. Martin v. CCH, No. 10-cv-3494 (N.D. Ill. 2011).",
            rule="15 U.S.C. 7706(a), (f)(1), (f)(3), (g)",
        ))
        f.append(dict(
            id="honor-window", severity="info",
            title="The 10 business day clock is the cleaner violation",
            detail="If you already clicked unsubscribe, the sender has 10 business "
                   "days to stop. Mail arriving after that window needs no argument "
                   "about transient outages, unlike a 404. Date your click and keep "
                   "every message that arrives afterward.",
            rule="15 U.S.C. 7704(a)(4)(A)(i)",
        ))

    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    f.sort(key=lambda x: order.get(x["severity"], 9))
    return f, kind, why, hdr


# ---------------------------------------------------------------- reporting

def render(report):
    L = []
    a = L.append
    a(f"# spamcheck report")
    a("")
    a(f"- Generated: {report['generated_utc']}")
    a(f"- From: `{report['from']}`")
    a(f"- Subject: {report['subject']}")
    a(f"- Classified: **{report['kind']}** ({report['why']})")
    a("")
    a("## Findings")
    a("")
    if not report["findings"]:
        a("None. The opt-out machinery on this message works.")
    for i, f in enumerate(report["findings"], 1):
        a(f"{i}. **[{f['severity']}] {f['title']}**")
        a(f"   - {f['detail']}")
        a(f"   - Rule: {f['rule']}")
    a("")
    a("## Unsubscribe surfaces")
    a("")
    h = report["list_unsubscribe"]
    a(f"- `List-Unsubscribe` present: {h['present']}")
    if h["raw"]:
        a(f"  - raw: `{h['raw']}`")
    a(f"- RFC 8058 one-click: {h['rfc8058_one_click']}")
    if report["probed"]:
        a("")
        a("| URL | Status | Final URL | ms |")
        a("| --- | --- | --- | --- |")
        for p in report["probed"]:
            st = p["status"] if p["status"] is not None else (p["error"] or "?")
            a(f"| {p['url']} | {st} | {p['final_url'] or ''} | {p['elapsed_ms']} |")
    else:
        a("")
        a("Not probed. Re-run with `--probe` to record real status codes, which is "
          "the evidence any complaint turns on.")
    skipped = report.get("body_links_not_probed") or []
    if skipped:
        a("")
        a(f"{len(skipped)} unsubscribe link(s) found in the body were NOT requested. "
          "Footer links usually act on GET, so probing them can actually unsubscribe "
          "you and can confirm your address is live. Pass `--probe-body` only if you "
          "want that:")
        for u in skipped:
            a(f"- `{u[:120]}`")
    a("")
    return "\n".join(L)


def default_report_path():
    stamp = datetime.now()
    name = "spamcheck-" + stamp.strftime("%Y-%m-%d-%-I.%M%p").lower() + ".md"
    base = os.environ.get("SPAMCHECK_REPORTS", ".")
    return os.path.join(os.path.expanduser(base), name)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--eml", help="path to a saved .eml message")
    src.add_argument("--paste", action="store_true",
                     help="read the raw message from stdin")
    src.add_argument("--url", action="append", default=[],
                     help="probe a bare unsubscribe URL; repeatable")
    ap.add_argument("--probe", action="store_true",
                    help="request the List-Unsubscribe HEADER urls only. Safe: RFC "
                         "8058 one-click requires POST, so a GET cannot opt you out")
    ap.add_argument("--probe-body", action="store_true",
                    help="ALSO request unsubscribe links scraped from the body. NOT "
                         "safe: most footer links act on GET, so this can actually "
                         "unsubscribe you and can confirm your address is live to a "
                         "spammer. Off by default on purpose")
    ap.add_argument("--opt-out", metavar="DOMAIN",
                    help="record that you clicked unsubscribe for this sender "
                         "domain today, then exit. This date is what makes the 10 "
                         "business day rule usable")
    ap.add_argument("--date", metavar="YYYY-MM-DD",
                    help="with --opt-out, the date you actually clicked")
    ap.add_argument("--note", help="with --opt-out, where or how you clicked")
    ap.add_argument("--opt-outs", action="store_true",
                    help="list every recorded opt-out and exit")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    ap.add_argument("-o", "--out", help="write the markdown report here")
    args = ap.parse_args()

    if args.opt_outs:
        rows = sorted(ledger_rows(), key=lambda r: r["clicked"])
        if not rows:
            print(f"no opt-outs recorded yet ({LEDGER})")
            return 0
        print(f"{'clicked':<12} {'domain':<34} note")
        for r in rows:
            print(f"{r['clicked']:<12} {r['domain']:<34} {r.get('note','')}")
        print(f"\n{len(rows)} recorded in {LEDGER}")
        return 0

    if args.opt_out:
        try:
            when = date.fromisoformat(args.date) if args.date else date.today()
        except ValueError:
            sys.exit("--date wants YYYY-MM-DD")
        if when > date.today():
            sys.exit("that date is in the future")
        row = ledger_add(args.opt_out, when, args.note)
        print(f"recorded: {row['domain']} opted out {row['clicked']}"
              + (f" ({row['note']})" if row["note"] else ""))
        print(f"appended to {LEDGER}")
        return 0

    if args.url and not (args.eml or args.paste):
        probed = [probe(u) for u in args.url]
        report = dict(generated_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                      **{"from": "", "subject": "", "kind": "unknown",
                         "why": "url-only mode"},
                      findings=[f for f in (
                          [dict(id="unsub-http-error", severity="high",
                                title=f"Unsubscribe URL returns HTTP {p['status']}",
                                detail=f"{p['url']} -> {p['status']}",
                                rule="objective, reproducible")
                           for p in probed if p["status"] and p["status"] >= 400]
                      )],
                      list_unsubscribe=dict(present=False, raw="", https_urls=[],
                                            mailtos=[], post_header="",
                                            rfc8058_one_click=False),
                      probed=probed)
    else:
        if not (args.eml or args.paste):
            ap.error("give --eml FILE, --paste, or --url URL")
        msg = load_message(args)
        text = body_text(msg)
        hdr = header_unsub(msg)
        body_links = body_unsub(text)
        targets = []
        for u in hdr["https_urls"] + args.url:
            if u not in targets:
                targets.append(u)
        if args.probe_body:
            for u in body_links:
                if u not in targets:
                    targets.append(u)
        probed = [probe(u) for u in targets] if (args.probe or args.probe_body) else []
        findings, kind, why, hdr = audit(msg, text, probed)
        report = dict(
            generated_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **{"from": msg.get("From", "") or "", "subject": msg.get("Subject", "") or ""},
            kind=kind, why=why, findings=findings,
            list_unsubscribe=hdr, probed=probed,
            candidate_urls=targets,
            body_links_not_probed=[] if args.probe_body else body_links,
        )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        md = render(report)
        path = args.out or default_report_path()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(md + "\n")
            print(md)
            print(f"\nwrote {path}")
        except OSError:
            print(md)

    return 1 if any(f["severity"] in ("high", "medium")
                    for f in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
