---
name: file-pr
description: File a concise pull request. Use when the user asks to file or open a PR.
---

# File PR

Name two remotes. The push remote is where the branch goes. The base remote is
the repo the PR opens on. They are the same remote unless the branch goes to a
fork, where the push remote is the fork and the base remote is upstream. Read
the base remote with `git remote get-url <base-remote>` and take its
`<owner>/<repo>`; that picks the host CLI. A GitHub base uses `gh`. A Forgejo or
Gitea base uses `tea`; check `tea logins list` has a login for that host.

Before filing, check whether a PR for this branch already exists
(`gh pr list --repo <owner>/<repo> --head <branch>`, or
`tea pr list --repo <owner>/<repo> --fields index,head,url` and
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

Before pushing, check for secrets and private details in everything that will
leave the machine: the commits being pushed (`git log -p <base>..HEAD`, diffs
and messages) and the title, description, quotes, and attachments. A secret
that reaches the remote counts as leaked even if the PR is never opened.

Push the branch before creating the PR: every create command below needs it on
the remote, and if the user declines the push, stop. Pushing stays the user's call. State the exact command,
`git push <push-remote> HEAD:<branch>`, with what it sends (commit count and
range, from `git log --oneline <base>..HEAD`), and wait for a yes, unless the
user already said to push in this request.

Creating the PR on the remote is the action the user asked for. Open a real PR
rather than a draft so review bots run. On GitHub, run
`gh pr create --repo <owner>/<repo> --head <head> --base <base> --title <title> --body-file <file>`.
On Forgejo or Gitea, run
`tea pr create --repo <owner>/<repo> --remote <base-remote> --head <head> --base <base> --title <title> --description-file <file>`.
`<owner>/<repo>` is the base remote's. `<head>` is the branch name, or
`<fork-owner>:<branch>` when the branch was pushed to a fork.
On GitHub, if `gh pr create` fails because the GraphQL rate limit is used up,
open it through REST on the base repo with
`gh api repos/<owner>/<repo>/pulls -f title=... -f head=<head> -f base=... -F body=@<file>`. If the user also asked
to watch it through review and CI, use a PR watcher or review skill if one is
available.

Do not post a follow-up PR comment unless it serves the user's request. When a
comment is needed and a PR comment skill is available, use it.

Credit: Theo Browne, from [t3dotgg/tstack](https://github.com/t3dotgg/tstack) (MIT).
