# spamcheck, explained for people

You clicked unsubscribe and the mail kept coming. Or the link gave you an error. Or
the button in Gmail did nothing. This tool tells you which of those is actually the
sender's fault, which law it touches, and who can do something about it. It reads one
saved email. It never opens your mailbox and never sends anything.

## Why the headers matter more than the footer link

There are two unsubscribe mechanisms in every bulk email, and most people only know
about one.

The footer link is the one you see. The other is hidden in the email headers, called
`List-Unsubscribe`. That header is what lets Gmail, Apple Mail and Outlook draw an
Unsubscribe button next to the sender's name. If the header is missing or broken, the
button is missing or broken, and no amount of clicking the footer fixes it.

So the tool starts with the header, because that is where the silent failures live.

## The seven things it checks, and why each one is there

1. **Is there a `List-Unsubscribe` header at all?** Without it, no mail client can offer
   a one-click opt-out. Gmail and Yahoo have required it from bulk senders since 2024.

2. **Does it advertise one-click?** A second header, `List-Unsubscribe-Post`, tells the
   mail client it can unsubscribe you with a single request. Without it the button may
   open a page, or do nothing.

3. **Does the header link actually work?** With `--probe`, the tool requests each header
   URL and records the real HTTP status. A 404 or 500 here is the evidence a complaint
   turns on. This is safe to do: a one-click unsubscribe needs a POST, and the tool only
   sends HEAD and GET, so probing cannot opt you out by accident.

4. **Is there an email address where a web link should be?** Some platforms put an
   inbound mail address in the header slot that should hold an https URL. Mail clients
   post to that URL, they do not mail it. The button renders and fails silently. Found on
   a real send.

5. **Is one-click advertised over a dead link?** This is the combination that explains
   most "the unsubscribe button does nothing" complaints. The header says one-click, the
   client draws the button, the target errors. The sender's fault, not the mail
   provider's.

6. **Is there a postal address in the body?** Commercial email has to carry one.
   Political email does not. Recorded either way, charged only for commercial.

7. **Is there a "paid for by" line?** Only checked on political mail. Missing it is an
   FEC matter, not a CAN-SPAM one.

## Why it classifies the email before naming any law

CAN-SPAM only covers commercial email. It does not cover campaign email, and there is
no nonprofit exemption in either direction: a charity selling something is covered, a
candidate asking for money is not. So before the tool cites a rule it counts markers in
the message and calls it commercial, political, nonprofit or unclear. If it says
unclear, decide for yourself and do not lean on the citations.

Getting this wrong is how people send confident complaints citing a law that does not
reach the sender.

## Why footer links are listed but not clicked

Footer links usually unsubscribe you on a plain visit. Requesting one to check its
status can complete the unsubscribe, and it confirms to the sender that your address is
live. The tool lists them and leaves them alone unless you pass `--probe-body` and mean
it.

## Why you should record the date you clicked

The strongest rule in the statute is not about broken links. It is a calendar: once you
ask to be removed, the sender has ten business days to stop. Mail arriving after that is
unlawful with no argument about servers being briefly down.

It only works if you know the date. `--opt-out example.com` writes it down. From then on
every audit of that sender counts business days, skipping weekends and federal
holidays, and tells you the moment they cross the line.

## What it will not tell you

It will not tell you that you have a case. A single failed link is weak evidence; the
law forgives temporary outages. And a recipient cannot sue under CAN-SPAM at all.
Enforcement belongs to the FTC, a state attorney general or the sending platform. The
tool assembles the evidence and names who can act. Whether to file is yours.

Every legal citation is quoted from the primary source in `references/complaints.md`,
with the date it was read.

## Text messages too

Paste a text instead of an email and it runs a different set of checks, because texts
run under a different law. The TCPA and the FCC's rules cover texts, not CAN-SPAM, and
unlike email a person can sue: $500 a text, up to three times that if the sender knew.

First it asks whether the text is a scam: an unpaid toll, a package that could not be
delivered, a locked bank account. If so, the advice is short. Do not tap the link, do
not reply (not even STOP, because a reply tells them the number is real), forward it to
7726 so your carrier can block it, report it to the FTC, and delete it.

If it is ordinary marketing, it checks what matters for texts: whether it says who sent
it and how to stop it, whether a sales text arrived before 8 a.m. or after 9 p.m., and,
once you record the day you replied STOP, whether they kept texting past the ten
business days the FCC allows. Political texts get the honest answer: the Do Not Call
list and quiet hours do not cover them, and replying STOP is the real fix.

It never opens a link from a text. Every citation is quoted from its primary source in
`references/texts.md`.

```bash
pbpaste | python3 scripts/spamcheck.py --sms --sender 22395 --received "2026-09-23 21:40"
python3 scripts/spamcheck.py --opt-out 22395 --note "replied STOP"
```

## Run it

```bash
python3 scripts/spamcheck.py --eml message.eml --probe
python3 scripts/spamcheck.py --opt-out example.com --note "footer link"
python3 scripts/spamcheck.py --opt-outs
```

To get the raw message: in Gmail, open the message, three-dot menu, Show original, Copy
to clipboard. In Apple Mail, View, Message, Raw Source, or drag the message to the
Desktop for a `.eml` file.
