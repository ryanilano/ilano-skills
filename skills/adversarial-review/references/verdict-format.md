# Verdict format

```
## Intent
<one or two sentences>

## Verdict: PASS | CONTESTED | REJECT | INCOMPLETE
<one line>
Reviewers: <lens (model): replied | failed: reason>, ... Judge: <self | fable child | opus child>

## Findings
<high, then medium, then low>
- <id> [severity] <claim> (<file>:<line>)
  Lens: <who raised it>.
  Fix: <concrete action>

## What held up
<from the reviewers' HELD lines>

## Lead judgment
<id>: accept | reject | contested. Checked at <file:line | low, not checked>. <one-line reason>

## Ledger (when there were rounds)
| id | severity | lens | outcome: fixed / fixed, unreviewed / rejected / contested / open |
```

- INCOMPLETE: a planned reviewer or the judge failed, or a reply lacks the LENS line, the VERDICT line
  or the findings block (trailing text, such as a Plan agent's file list, is ignored). Wins over the others.
- Check the model in each LENS line against the reviewers line.
- REJECT: an accepted high finding is open and unfixed. Wins over CONTESTED.
- CONTESTED: a high finding the judge marked contested (not confirmed at its line, or reviewers
  disagree), or an accepted high logged `fixed, unreviewed`. A contested finding blocks PASS.
- PASS: none of the above. The verdict line names every accepted medium still open.
