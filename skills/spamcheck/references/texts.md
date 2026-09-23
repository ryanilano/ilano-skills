# Unwanted text messages: what the law actually says

Read from primary sources on 2026-09-23. Labels:

- **CONFIRMED**: quoted from the primary source and re-read at the source on that date.
- **QUOTED**: quoted from the primary source by a first research pass, not re-read in the second.
- **INFERRED** or **UNKNOWN**: say so plainly.

Re-verify before filing. One rule below is scheduled to change (see "Watch" at the end).

## First: a text is a "call", and the law is the TCPA, not CAN-SPAM

QUOTED. The FCC has treated texts as calls since 2003: the rule "encompasses both voice calls and text calls to wireless numbers including, for example, short message service (SMS) calls." FCC 03-153 ¶165. <https://docs.fcc.gov/public/attachments/FCC-03-153A1.pdf>

CONFIRMED. The autodialer rule bars any call "using any automatic telephone dialing system or an artificial or prerecorded voice" to a cellular number without prior express consent. 47 U.S.C. 227(b)(1)(A)(iii). An autodialer is equipment with the capacity "(A) to store or produce telephone numbers to be called, using a random or sequential number generator; and (B) to dial such numbers." 227(a)(1). <https://www.law.cornell.edu/uscode/text/47/227>

QUOTED. The Supreme Court narrowed that: "a necessary feature of an autodialer under §227(a)(1)(A) is the capacity to use a random or sequential number generator to either store or produce phone numbers to be called." *Facebook, Inc. v. Duguid*, 592 U.S. 395 (2021). <https://www.supremecourt.gov/opinions/20pdf/19-511_p86b.pdf>

INFERRED. From one phone you cannot tell whether an autodialer was used. After *Duguid*, most list-based marketing texts are argued to fall outside the autodialer rule, which is why the Do Not Call route below matters more.

## Unlike email, a recipient can sue

CONFIRMED. Autodialer violations: "an action to recover for actual monetary loss from such a violation, or to receive $500 in damages for each such violation, whichever is greater," and for a willful or knowing violation "not more than 3 times the amount." 47 U.S.C. 227(b)(3).

CONFIRMED. Do Not Call violations: "A person who has received more than one telephone call within any 12-month period by or on behalf of the same entity in violation of the regulations" may sue, with the same $500 and treble terms. 227(c)(5). QUOTED: it carries a defense for a sender with "reasonable practices and procedures to effectively prevent telephone solicitations."

## Saying STOP: the revocation rule

CONFIRMED. "A called party may revoke prior express consent ... by using any reasonable method to clearly express a desire not to receive further calls or text messages from the caller or sender." 47 CFR 64.1200(a)(10). <https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-64/subpart-L/section-64.1200>

CONFIRMED. The words that count per se: "using the words "stop," "quit," "end," "revoke," "opt out," "cancel," or "unsubscribe" sent in reply to an incoming text message." Same paragraph.

CONFIRMED. The clock: "All requests to revoke prior express consent ... made in any reasonable manner must be honored within a reasonable time not to exceed ten business days from receipt of such request." Senders "may not designate an exclusive means to request revocation of consent." Same paragraph.

CONFIRMED. One confirmation text is allowed if it "merely confirms the text recipient's revocation request and does not include any marketing or promotional information, and is the only additional message sent." "If the confirmation text is sent within five minutes of receipt, it will be presumed to fall within the consumer's prior express consent." 64.1200(a)(12).

This is what spamcheck's STOP ledger counts. `--opt-out <number>` records the date you replied; the report counts business days to each later text, excluding weekends and federal holidays.

## Do Not Call and quiet hours: sales texts only

CONFIRMED. "No person or entity shall initiate any telephone solicitation to: (1) Any residential telephone subscriber before the hour of 8 a.m. or after 9 p.m. (local time at the called party's location), or (2) A residential telephone subscriber who has registered his or her telephone number on the national do-not-call registry." 64.1200(c).

CONFIRMED. Those rules reach texts: they "are applicable to any person or entity making telephone solicitations or telemarketing calls or text messages to wireless telephone numbers." 64.1200(e). QUOTED, the 2023 order: "Texters must have the consumer's prior express invitation or permission before sending a marketing text to a wireless number in the DNC Registry." FCC 23-107 ¶26.

CONFIRMED. What counts as a solicitation: "the initiation of a telephone call or message for the purpose of encouraging the purchase or rental of, or investment in, property, goods, or services," excluding a message "(A) to any person with that person's prior express invitation or permission, (B) to any person with whom the caller has an established business relationship, or (C) by a tax exempt nonprofit organization." 47 U.S.C. 227(a)(4).

INFERRED. A political text that sells nothing is not a telephone solicitation, so neither Do Not Call nor quiet hours reach it. There is no separate political exemption; it simply falls outside the definition.

## Political texts

CONFIRMED. Peer-to-peer platforms: "if a calling platform is not capable of originating a call or sending a text without a person actively and affirmatively manually dialing each one, that platform is not an autodialer and calls or texts made using it are not subject to the TCPA's restrictions on calls and texts to wireless phones." FCC DA 20-670. <https://docs.fcc.gov/public/attachments/DA-20-670A1.pdf>

QUOTED. The FEC's disclaimer rule reaches "public communications" and "electronic mail of more than 500 substantially similar communications when sent by a political committee" (11 CFR 110.11(a)); texts are not named. The only on-point advisory opinion applied the small-items exception: "the SMS technology places similar limits on the length of a political advertisement as those that exist with bumper stickers." FEC AO 2002-09. INFERRED: a campaign text usually needs no "paid for by" under federal rules. State law may differ and was not researched.

So for a political text, replying STOP is the practical remedy, and spamcheck says so rather than citing a rule that does not reach it.

## Scam texts

CONFIRMED. FTC on toll scams: "Don't click on any links in, or respond to, unexpected texts." and "Use your phone's "report junk" option to report unwanted texts to your messaging app or forward them to 7726 (SPAM)." <https://consumer.ftc.gov/consumer-alerts/2025/01/got-text-about-unpaid-tolls-its-probably-scam>

CONFIRMED. FTC general guidance: if a text "asks you to give some personal or financial information, don't click on any links. Legitimate companies won't ask for information about your account by text." <https://consumer.ftc.gov/articles/how-recognize-and-report-spam-text-messages>

This is why spamcheck never opens a link from a text and, for a scam, advises against replying STOP: the FTC's advice is not to respond at all.

## Where to report

CONFIRMED, the FTC's three routes: "Copy the message and forward it to 7726 (SPAM)." "Report it on the messaging app you use." "Report it to the FTC at ReportFraud.ftc.gov." Same FTC page.

| Where | For | Checked 2026-09-23 |
|---|---|---|
| Forward to **7726** | every unwanted text; your carrier blocks the sender | FTC page above |
| <https://reportfraud.ftc.gov/> | scams and fraud | loads (200) |
| <https://www.donotcall.gov/report.html> | sales texts to a number on the registry | loads (200) |
| <https://consumercomplaints.fcc.gov/> | unwanted texts, TCPA | UNKNOWN: blocks automated checks (403); open it in a browser |

## Carrier rules (not law)

QUOTED. CTIA Messaging Principles and Best Practices (May 2023): "Message Senders should state in the message how and what words effect an opt-out. Standardized 'STOP' wording should be used for opt-out instructions, however opt-out requests with normal language (i.e., stop, end, unsubscribe, cancel, quit, 'please opt me out') should also be read and acted upon." <https://api.ctia.org/wp-content/uploads/2023/05/230523-CTIA-Messaging-Principles-and-Best-Practices-FINAL.pdf>

A missing "Reply STOP" line breaks the carrier guideline, not a statute; spamcheck rates it low for that reason. A carrier can still suspend the sender for it.

## New York

QUOTED. GBL 399-z defines a "telemarketing sales call" as "a telephone call or electronic messaging text made directly or indirectly by a telemarketer," and bars unsolicited sales calls to a number on the national registry for thirty-one days or more, with calling hours "between 8:00 A.M. and 9:00 P.M." <https://legislation.nysenate.gov/pdf/laws/GBS399-Z/>

## Watch: the revocation rule is moving

CONFIRMED. Part of the 2024 rule, treating a STOP to one kind of message as a STOP to all of a sender's unrelated robocalls and robotexts, is delayed "until January 31, 2027." FCC DA 26-12. <https://docs.fcc.gov/public/attachments/DA-26-12A1.pdf>

CONFIRMED, a draft only. The FCC circulated an order for its **September 30, 2026** meeting that would "Allow callers to interpret a revocation request as applying only to the specific category of informational robocalls" and "Allow callers to designate an exclusive means to revoke consent." The fact sheet says it "does not constitute any official action." <https://docs.fcc.gov/public/attachments/DOC-424844A1.pdf>

UNKNOWN until after 2026-09-30: whether it is adopted. If it is, the "may not designate an exclusive means" sentence above changes, and so should spamcheck's STOP advice. Re-read 64.1200(a)(10) on eCFR after that date.
