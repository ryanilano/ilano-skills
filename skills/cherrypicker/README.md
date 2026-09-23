# cherrypicker, explained for people

You have two drafts of the same thing. One has the better opening, the other has the better ending, and somewhere in the middle they say the same point in different words under different headings. A diff tool is useless here: it shows every line as changed, because to it they are.

cherrypicker turns the two drafts into one page. Each row pairs the passages that are doing the same job, one draft on the left and one on the right, and you press a button per row.

## The choices

- **A** or **B**: that draft's copy wins.
- **Both**: keep something from each. Pick how: all of both, a piece of one grafted into the other, one's structure with the other's facts, or both in an order you choose.
- **Rewrite**: neither version is right yet.
- **Cut**: the section goes.

Each row also has a note field for anything you want done there.

## What you get at the end

Export gives you markdown: every decision grouped by choice, with your notes, then a worklist of every row that needs writing rather than choosing, with the full text of both sides ready to edit.

## Things it does for you

- **Rows that exist in only one draft are shown on purpose.** That is the copy a quick merge silently loses.
- **It saves as you go.** Your picks and notes live in the page's address, so bookmarking it on a phone or tablet reopens exactly where you left off. The browser keeps a copy too, and you can also save your notes to a file.
- **It works on a tablet.** The layout goes to one column on narrow screens, and a helper script can serve the page to your own devices over Tailscale.
- **Light or dark.** It follows your device's setting, and a Theme button lets you pin either one.
- **It works with a screen reader and keyboard.** Every row, draft and choice is labelled, the buttons report whether they are selected, and a skip link jumps past the header.

## Who does what

The agent reads both drafts and decides which passages pair up. You make every editorial call. The agent can suggest a pick per row, and the suggestion shows above the text, but the button is yours.
