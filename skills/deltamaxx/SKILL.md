---
name: deltamaxx
description: "Maximize the delta (value back minus cost) on rewards programs: credit cards, airline and hotel loyalty, shopping portals, targeted offers. Use when the user names a purchase or merchant, asks which card or program to use, asks whether a card, fee or status is worth it, or says deltamaxx."
---

# deltamaxx

Every decision is a **delta**: value back minus cost (annual fees, cash price, fees on award tickets, and anything given up by choosing this over the next-best option). Maximize the delta, not the points count. A big pile of points bought with a fee that never earns back is a negative delta.

The user's programs live in their **wallet**: cards held and being considered, loyalty memberships, monthly credits, each row dated with its source. It is the only source of truth; read it first, every time.

- **Where:** `$DELTAMAXX_WALLET` if set, else `~/.config/deltamaxx/wallet.md`.
- **No wallet yet:** copy [`assets/wallet-template.md`](assets/wallet-template.md) there, ask the user which cards and programs they hold, and fill it in before answering.

## Steps: one purchase ("which card, which program?")

1. **Read the wallet in full.** Mark any row older than 90 days as **stale**.
2. **Classify the purchase:** merchant, category, domestic or abroad, online or in person, and which loyalty programs touch it (airline, hotel, rideshare, restaurant).
3. **Stack the layers**, in this order, and total them:
   1. **Expiring credits:** a monthly credit that covers this merchant and has money left this period wins first. Unused credit is lost.
   2. **Targeted offers:** Amex Offers and similar live in the issuer's app, so say where to check.
   3. **Portal or partner link:** an airline shopping portal, or a merchant link a card issuer provides.
   4. **Card earn:** the best held card's rate for the category, and how to pay (a mobile wallet rather than the physical card, where the rate differs).
   5. **Program earn and status:** miles or points from the airline or hotel itself, and elite-qualifying credit.
4. **Value everything in cents.** 1 cent per point or mile unless the wallet gives a value. Cash back is face value.
5. **Answer:** what to use and how to pay, with the total delta, the runner-up, and any stale row flagged with the issuer page to check.

Done when the answer names one card, one route and one delta figure, and every rate used came from the wallet or was verified today.

## Steps: "is this card, fee or status worth it?"

1. From the wallet and the user's stated habits (for example, 3 to 5 trips a year on one airline), list what they would **actually use**: bags, credits they would spend anyway, earn on their real spending.
2. Delta = value used − fee − what an equal card they already hold would earn anyway. Count **overlap** as zero: a Global Entry credit they already get elsewhere adds nothing.
3. A credit only counts if they would spend that money anyway. Credits are a coupon book, not cash.
4. Answer with the yearly delta, the break-even usage (for example, "two round trips with a checked bag"), and the overlaps.

## Keeping the wallet honest

- When the user states a card, credit, offer, membership or status, add it to the wallet with today's date and its source. When a rate is re-checked, update its date.
- Verify on the program's own page first (the issuer's or airline's site). Blogs are a second source only.
- Only names, rates, credits and status tiers go in the wallet. Card numbers, balances, member numbers and logins stay out.
- Choosing the card is everyday routine. Applying for, cancelling or upgrading a card, or buying miles or status, is a money decision that stays with the user.
