---
name: spamcheck
description: Audit one email's or text message's opt-out and say what is actually broken, whether it is a scam, and where to report it. Use when a sender's unsubscribe link 404s or does nothing, when asked whether an email breaks CAN-SPAM or a text breaks the TCPA, when texts keep coming after STOP, when a text looks like a toll, package or bank scam, or when a complaint to the FTC, FCC, FEC, a state AG or a sending platform needs the evidence assembled. Reads a saved or pasted message; never touches a mailbox or a phone.
---

# spamcheck

One command. It prints a report and writes it to a file.

```bash
python3 scripts/spamcheck.py --eml message.eml --probe
```

`--probe` is the important flag. Without it nothing is requested over the network and
the status-code column stays empty, which is the one piece of evidence a complaint
actually turns on.

**`--probe` only touches the `List-Unsubscribe` header URLs, and that is deliberate.**
RFC 8058 one-click requires a POST, so a GET against a header URL cannot opt you out.
Footer links are the opposite: most of them act on a plain GET, so requesting one can
actually unsubscribe you and can confirm to a spammer that your address is live. Those
links are listed in the report but never requested unless you pass `--probe-body` and
mean it. The script issues HEAD and GET only, never POST, and never sends mail.

## Three ways in

```bash
python3 scripts/spamcheck.py --eml saved.eml --probe        # a saved message
pbpaste | python3 scripts/spamcheck.py --paste --probe      # a pasted raw message
python3 scripts/spamcheck.py --url "https://..." --probe    # just check one link
```

Exit 0 means nothing actionable. Exit 1 means at least one finding at medium or high.
Exit 2 means bad input. The report lands in the current directory with a timestamped
name unless `-o` says otherwise, or `SPAMCHECK_REPORTS` names a folder. Add `--json`
for machine output.

## Get the raw message first

The script is only as good as what it is fed. A message body copied out of a mail
client loses every header, which throws away the `List-Unsubscribe` check, the single
most useful signal in here.

- Gmail web: open the message, the three-dot menu, **Show original**, then **Copy to
  clipboard**. That is the full raw source.
- Apple Mail: **View > Message > Raw Source**, or drag the message to the Desktop to
  get a `.eml`.
- If all you have is the footer text, `--url` on the unsubscribe link still gets you
  the status code, which is most of what you need.

## What it checks

1. **`List-Unsubscribe` header** (RFC 2369). Absent means no mail client can offer an
   opt-out button at all.
2. **RFC 8058 one-click**, meaning `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.
   Present-but-not-one-click is the usual reason a mail client's unsubscribe button
   appears to do nothing.
3. **The `List-Unsubscribe` URLs**, probed for a real status code and final URL after
   redirects. Body links are found and listed but not requested by default.
4. **An email address in the https slot.** An inbound-mail address put where an https
   endpoint belongs is a live misconfiguration: clients POST to that URL, they do not
   mail it. Observed in the wild on a real send.
5. **One-click advertised over a dead target.** `List-Unsubscribe-Post` present while
   the https URL errors means every mail client draws an Unsubscribe button that
   silently does nothing. This is the usual reason an unsubscribe control "does not
   work," and it is the sender's fault, not the mail provider's.
6. **A physical postal address** in the body, which commercial mail is required to
   carry and political mail is not.
7. **A "paid for by" disclaimer**, but only on messages it classifies as political.

## Phishing is checked first

Before any unsubscribe audit, every email is checked for the signs of a scam: a
failing DMARC (or SPF and DKIM both failing) in the receiving server's
`Authentication-Results`, a brand name in the From display name sent from someone
else's domain, a Reply-To on a different domain, a link whose visible text names one
site while it opens another, risky link hosts, and phishing bait in the copy.

When those add up, the message is classified **scam**, gets no CAN-SPAM findings, and
**nothing is probed, not even with `--probe`**: a phisher's unsubscribe link is just
another link to their server. The report gives the FTC's advice instead: do not click
or reply, forward to reportphishing@apwg.org, report at ReportFraud.ftc.gov, delete.
A single signal (say, a Reply-To mismatch from a mailing service) is reported as an
observation without changing the classification.

## Record the click, or the best rule in the statute is unusable

The strongest provision is not the broken link. It is the **10 business day** honor
window: once you ask to be removed, mail arriving after that is unlawful, with no
argument available about whether a server was briefly down. It only works if the click
is dated, and nobody remembers.

```bash
python3 scripts/spamcheck.py --opt-out example.com --note "footer link"
python3 scripts/spamcheck.py --opt-outs
```

Append-only JSONL at `~/.local/share/spamcheck/optouts.jsonl`, override with
`SPAMCHECK_LEDGER`. Pass `--date YYYY-MM-DD` if you clicked earlier and are catching up.

From then on, every audit of that sender compares the message's `Date` header to your
click and counts business days, excluding weekends and the eleven federal holidays,
which are computed rather than hardcoded so the figure stays defensible. Subdomains
match their parent, so `example.com` covers `e.example.com`.

## Transactional mail is skipped on purpose

An auto-reply, a receipt, a support ticket acknowledgement or an account notice is a
"transactional or relationship message" under 15 U.S.C. 7702(17), carved out of the
definition of commercial mail. The opt-out and postal address requirements do not touch
it. The script detects these from `Auto-Submitted`, `X-Auto-Response-Suppress`,
`Precedence` and `In-Reply-To`, classifies them `transactional`, and raises nothing
else.

This check exists because the first live support acknowledgement fed to the tool got
flagged for a missing unsubscribe header and a missing "paid for by" disclaimer, having
matched political keywords in the copy of your own email quoted back at you. Flagging a
Zendesk receipt is the fastest way to make a tool like this worthless.

## The classification is the whole point

Before naming a law, the script decides whether the message is **commercial**,
**political**, **nonprofit** or **unclear**, by counting markers in the body and the
From line. This is not decoration. It changes which law is even in play, and getting
it wrong is how people send confident complaints citing a statute that does not reach
the sender.

Check the classification line at the top of the report before you use any finding. If
it says `unclear`, decide it yourself and do not lean on the rule citations.

## Where to complain

Routing depends entirely on the classification above. Full citations, quoted from
primary sources, are in `references/complaints.md`. The short version:

| Message is | Who can actually act | Where |
| --- | --- | --- |
| **commercial** | FTC, a state AG, an internet access provider. **Not you.** | <https://reportfraud.ftc.gov/> and, in NY, the AG's Bureau of Internet and Technology form |
| **political** | The sending platform. The FEC only for a missing "paid for by" disclaimer, and only above 500 substantially similar messages | Platform support first; FEC needs a **notarized** complaint emailed to EnfComplaint@fec.gov |
| **nonprofit** | Depends on the message, not the sender. A nonprofit selling something commercial is covered | As commercial, if the primary purpose is commercial |
| **any of them** | The sending platform, every time | Their acceptable-use policy; a broken opt-out is a deliverability problem for them |

Three things to say out loud before anyone files anything:

1. **There is no private right of action under CAN-SPAM.** A recipient cannot sue.
   15 U.S.C. 7706; *Martin v. CCH*, No. 10-cv-3494 (N.D. Ill. 2011). Filing is about
   getting a regulator to act, not about collecting.
2. **A single 404 is weak evidence.** The statute forgives a mechanism that is
   "unexpectedly and temporarily" down from a problem beyond the sender's control.
   15 U.S.C. 7704(a)(3)(C). Probe twice, days apart, and keep both reports.
3. **The strong violation is the calendar, not the link.** Once you click unsubscribe
   the sender has **10 business days** to stop. 15 U.S.C. 7704(a)(4)(A)(i). Mail
   arriving after that needs no argument about outages. Date the click.

## Text messages

A text runs under different law than email: the TCPA and the FCC's rules, not
CAN-SPAM, and unlike CAN-SPAM a recipient can sue. Paste the text; give the sender
and the arrival time so the time-based checks can run.

```bash
pbpaste | python3 scripts/spamcheck.py --sms --sender 22395 --received "2026-09-23 21:40"
python3 scripts/spamcheck.py --sms-file text.txt --sender "+1 212 555 0142"
python3 scripts/spamcheck.py --opt-out 22395 --note "replied STOP"
```

**Links in a text are never opened**, not with `--probe`, not with `--probe-body`. A
scam text exists to be tapped, and any request confirms the number is live. The report
lists each link with what makes it risky: a shortener, a raw IP, punycode, a brand name
inside someone else's domain, a pile of hyphens, a throwaway TLD.

It classifies the text first, the same way it classifies email, plus one more class:

- **scam**: toll, package, bank or prize bait. The advice changes completely: do not tap,
  do not reply (not even STOP, which confirms the number), forward to 7726, report to
  the FTC, delete. Unsubscribe law is irrelevant to a fraudster.
- **commercial**: checks for an opt-out instruction, a named sender, the 8 a.m. to 9 p.m.
  window for sales texts, and, once you record your STOP, the 10 business day honor window.
- **political**: the Do Not Call registry and quiet hours do not reach it; the
  autodialer rule still does, and peer-to-peer campaign texts mostly fall outside it.

It also reads the sender: short code, toll-free, ordinary number, foreign number, or an
email address pushed through a carrier gateway, which is a scam tell.

Record your STOP reply with `--opt-out <number>` the same way as an email click. Every
citation, quoted from its primary source, is in [`references/texts.md`](references/texts.md).

## What it will not do

- It will not open a mailbox or read a phone. Feed it a file or a paste.
- It will not send a complaint, an unsubscribe request, a STOP reply, or any mail.
- It will not tell you that you have a case. It assembles evidence and names the
  rule that the evidence bears on. Whether to file is yours.
- A single failed probe is not proof. Re-run before relying on it; transient network
  failures look identical to a dead endpoint on one try.

## Known limits

- The postal-address detector is deliberately loose and US-shaped. A false positive
  (thinking an address is present when it is not) is the safe direction, and that is
  the direction it errs.
- Marker counting is a heuristic, not a legal determination of "primary purpose."
- HTML-only messages are parsed as text, so a link buried in an attribute rather
  than the visible body may be missed. `--url` covers that case.
