---
name: file-pr
description: File a concise pull request. Use when the user asks to file or open a PR.
---

# File PR

Read the remote you will push to with `git remote get-url <remote>`. A GitHub
remote uses `gh`. A Forgejo or Gitea remote uses `tea`, adding
`--remote <remote>` when the repo has several; check `tea logins list` has a
login for that host.

Before filing, check whether a PR for this branch already exists
(`gh pr list --head <branch>`, or `tea pr list --fields index,head,url` and
match the head). Review the diff locally against the base branch (usually
`origin/main`) to make sure its contents match the goal.

PR titles usually become commit messages, so follow the repository's title
conventions. Look at recently merged PRs and Git history for examples. Prefer a
concise, human-readable title that explains why the change matters:

BAD

> ❌ perf(server): negotiate permessage-deflate on the websocket

GOOD

> ✅ perf(server): cut websocket frame size by 70%+ with gzipping

Open the description with a simple explanation of the problem based on the
user's original prompt, then briefly explain the solution. Do not lead with an
implementation inventory:

BAD

> ❌ Removed implicit workspace carry-over from every "new thread" entry point (cmd+n / cmd+shift+o, sidebar v1/v2 buttons, command palette). New threads inherit only the project from context; branch, worktree, and env mode always come from the configured defaults. Deleted buildContextualThreadOptions, startNewThreadInProjectFromContext, and the v1 sidebar's seed-context machinery.

GOOD

> ✅ My "new worktree" default was ignored when starting new threads on existing worktrees. Super unintuitive. Now your preferences always apply.

The description ends with the solution. It carries no model, harness, or
session footer.

Before submission, check the title, description, quotes, and attachments for
secrets and private details.

Creating the PR on the remote is the action the user asked for. Open a real PR
rather than a draft so review bots run. On Forgejo or Gitea, run
`tea pr create --head <branch> --base <base> --title <title> --description-file <file>`.
On GitHub, if `gh pr create` fails because the GraphQL rate limit is used up,
open it through REST with
`gh api repos/<owner>/<repo>/pulls -f title=... -f head=... -f base=... -F body=@<file>`. If the user also asked
to watch it through review and CI, use a PR watcher or review skill if one is
available.

Do not post a follow-up PR comment unless it serves the user's request. When a
comment is needed and a PR comment skill is available, use it.

Credit: Theo Browne, from [t3dotgg/tstack](https://github.com/t3dotgg/tstack) (MIT).
