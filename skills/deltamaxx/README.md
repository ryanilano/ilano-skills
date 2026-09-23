# deltamaxx, explained for people

Rewards cards and loyalty programs are built to make you count points. The number that matters is simpler: what you get back, minus what it cost you. deltamaxx calls that the delta and works it out for you.

## What you can ask

- **"Which card for this?"** Name a purchase, like a food delivery order or a flight. It checks, in order: a credit about to expire that covers it, a targeted offer in your card's app, a shopping portal, your best card's rate, and what the airline or hotel adds on top. You get one card, one way to pay, and the total in cents, plus the runner-up.
- **"Is this card worth the fee?"** It counts only what you would actually use, subtracts the fee, and counts perks you already get from another card as zero. You get a yearly figure and the break-even point, like "two round trips with a checked bag".

## Your wallet

Everything it knows comes from one file you own, your wallet: the cards you hold or are considering, your credits, your loyalty status, each with the date it was checked. The first time you use it, it starts the file from a blank template and asks what you have. It never stores card numbers, balances, member numbers or logins.

The file lives at `~/.config/deltamaxx/wallet.md`, or wherever `DELTAMAXX_WALLET` points, so you can keep it in a synced folder. Anything older than 90 days gets flagged so a stale rate doesn't decide for you.

## What it won't do

Apply for, cancel or upgrade a card, or buy miles or status. It tells you the delta; the money decision stays yours.
