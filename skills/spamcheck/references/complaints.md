# Where a spam complaint actually goes

Every citation below was read from a primary source on 2026-09-20. Findings are marked
CONFIRMED (quoted from the source), INFERRED, or UNKNOWN. Re-verify before filing;
GBL 349 alone was rewritten five months before this was written.

## First, the thing that decides everything

CONFIRMED. CAN-SPAM reaches only a "commercial electronic mail message," meaning one
whose primary purpose is "the commercial advertisement or promotion of a commercial
product or service." 15 U.S.C. 7702(2)(A). The FTC's own rule carries a footnote saying
the Commission "does not intend for these criteria to treat as a 'commercial electronic
mail message' anything that is not commercial speech." 16 CFR 316.3(a) n.1. The 2005
final rule says it "in the strongest possible terms." 70 FR 3110, 3125.

CONFIRMED. The FTC has answered this directly about campaign email: "The CAN-SPAM Act
applies only to commercial email... It doesn't apply to non-commercial bulk email.
Furthermore, political messages are protected under the First Amendment."
<https://www.ftc.gov/business-guidance/blog/2015/08/candid-answers-can-spam-questions>

CONFIRMED. There is no nonprofit exemption. 70 FR 3112 gives the example of a nonprofit
hospital selling a fee-based screening, and refuses "to create an across-the-board
exemption." Coverage turns on the message, not on who sent it.

UNKNOWN. Whether the FTC has ever asserted jurisdiction over a candidate committee's
email. Nothing in the guide, the Rule, or the 2005 notice addresses it.

## If the message is commercial

CONFIRMED, the duty. The opt-out mechanism must be functioning, clearly and
conspicuously displayed, and must "remain capable of receiving such messages or
communications for **no less than 30 days** after the transmission of the original
message." 15 U.S.C. 7704(a)(3)(A)(i)-(ii).

CONFIRMED, the safe harbor, and it is the reason a single 404 is weak evidence. The
mechanism "does not fail to satisfy the requirements" if it is "unexpectedly and
temporarily unable to receive messages or process requests due to a technical problem
beyond the control of the sender if the problem is corrected within a reasonable time
period." 15 U.S.C. 7704(a)(3)(C). Probe twice, days apart, and record both.

CONFIRMED, the stronger violation. Once a request is received, it is unlawful to send
"more than **10 business days** after the receipt of such request." 15 U.S.C.
7704(a)(4)(A)(i). This needs no argument about outages. Date the click, keep what
arrives after.

CONFIRMED, the mechanics. No fee, no information beyond an email address and opt-out
preferences, and no step other than replying or visiting a single web page.
16 CFR 316.5.

CONFIRMED, and this is the hard part: **there is no private right of action.**
Enforcement belongs to the FTC (7706(a)), the sector regulators in 7706(b), state
attorneys general (7706(f)), and internet access providers (7706(g)). A court put it
plainly: "The Act does not provide a cause of action for private citizens." *Martin v.
CCH, Inc.*, No. 10-cv-3494 (N.D. Ill. Mar. 24, 2011).

CONFIRMED, and worth knowing before you shrug: a state AG needs "a pattern or practice"
to reach the opt-out provisions, not one bad send. 7706(f)(1). Civil penalties run to
$53,088 per email, the 2025 level, held unchanged for 2026 (91 FR 58446).

**File here**, both verified 200 on 2026-09-20:
- FTC: <https://reportfraud.ftc.gov/>
- NY AG, Bureau of Internet and Technology, the better fit for an email-system failure
  than the consumer-fraud form:
  <https://formsnym.ag.ny.gov/OAGOnlineSubmissionForm/faces/OAGBITHome>
  (hub: <https://ag.ny.gov/file-complaint>)

## If the message is political

CAN-SPAM is out. What remains is the disclaimer rule, and a broken unsubscribe link is
not an FEC violation at all.

CONFIRMED, the trigger. Disclaimers are required on "electronic mail of more than 500
substantially similar communications when sent by a political committee."
11 CFR 110.11(a)(1). Email is not a "public communication" (11 CFR 100.26), which is
why it needed its own hook. The statute, 52 U.S.C. 30120, does not say "email" at all.

CONFIRMED, the content. It must "clearly state that the communication has been paid for
by the authorized political committee," 110.11(b)(1), and be "clear and conspicuous...
not... difficult to read... or easily overlooked," 110.11(c)(1).

CONFIRMED, the cost of filing. A complaint "shall be sworn to and signed in the presence
of a notary public and shall be notarized," and must carry your full name and address.
11 CFR 111.4(b). All statements are subject to the perjury statutes and 18 U.S.C. 1001.
There is no web form. It is an emailed notarized PDF to **EnfComplaint@fec.gov**.
<https://www.fec.gov/legal-resources/enforcement/complaints-process/how-to-file-complaint-with-fec/>

UNKNOWN in any single inbox: whether a given send passed 500 substantially similar
messages. Inferable for a statewide blast, not observable.

## The state-law angle, New York

CONFIRMED and time-sensitive: **GBL 349 was rewritten, revision dated 2026-04-03**, and
retitled "Unfair, deceptive, or abusive acts and practices unlawful." Subsection (a) now
declares unfair, deceptive, or abusive acts unlawful.

CONFIRMED and load-bearing: the private right of action did **not** widen with it.
349(h) still reads "any deceptive act or deceptive practice." The new unfair and abusive
prongs are for the Attorney General under 349(b). A broken unsubscribe link reads more
naturally as *unfair* than as *deceptive*, so the easiest theory to plead is the one a
private plaintiff cannot bring.

CONFIRMED, the money, and it is why this is leverage rather than a payday: "actual
damages or fifty dollars, whichever is greater," trebled at the court's discretion "up
to one thousand dollars" for a willful or knowing violation, plus discretionary
attorney's fees. GBL 349(h).

CONFIRMED, the defense they will raise: 349(d) is a complete defense where the practice
complies with FTC rules and regulations. Not triggered for political mail, which is
outside CAN-SPAM, but expect it for commercial mail.

INFERRED, high confidence, on preemption: 15 U.S.C. 7707(b)(2)(A) expressly preserves
"State laws that are not specific to electronic mail." GBL 349 is a general consumer
statute, so it never reaches the "expressly regulates... electronic mail" threshold in
7707(b)(1) and the falsity carve-out never has to be argued.

INFERRED, and this is the real obstacle: 349 requires conduct "in the conduct of any
business, trade or commerce." A campaign soliciting political contributions is arguably
not in trade or commerce at all. UNKNOWN: no primary New York case applying or refusing
349 to political campaign email could be read. Treat as open.

## The platform is the fastest real fix

CONFIRMED. Action Network's Acceptable Use Policy bars groups from "Sending email to
users who have requested to be removed from a mailing list," and from sending "in
violation of the CAN-SPAM Act, the GDPR" and other anti-spam law. Violations "will be
considered a **material breach** of the master agreement."
<https://actionnetwork.org/acceptable/>

CONFIRMED and useful: the unsubscribe block is platform-generated. "We automatically add
an unsubscribe link at the bottom of all emails... This section is not editable... Please
do not try to hide this section." So on that platform a broken link is a vendor or token
failure, not a campaign decision, and the vendor is the party who can fix it.

CONFIRMED by live probe on 2026-09-20: `https://actionnetwork.org/unsubscribe/<token>`
302s to `admin.actionnetwork.org`, and an invalid token lands on a sign-in page rather
than a 404. Three bogus tokens were tried; none produced a 404. **A genuine 404 on that
host therefore means the emailed URL never reached the unsubscribe route at all**, most
likely a mangled click-tracking redirect or a truncated link. Capture the exact URL.

Report a group to **support@actionnetwork.org**. There is no dedicated abuse address on
the Terms, AUP, Privacy or Contact pages.

## When the emailed link is dead and you just want off

1. Try the Unsubscribe control the mail client draws near the sender name. It rides the
   `List-Unsubscribe` header, a different mechanism than the footer link, so it can work
   when the footer is broken. Gmail's button has been observed not working on at least
   one account, so verify rather than assume.
2. Register the exact receiving address on the platform and turn the list off from the
   account. Action Network: sign up, then Edit Subscriptions.
3. Mail the platform's support address and ask for suppression, naming the group.

Scope limit, CONFIRMED: unsubscribing removes you from that one list, not from every
group using the platform.
