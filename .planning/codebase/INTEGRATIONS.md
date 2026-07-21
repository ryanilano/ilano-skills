# External Integrations

**Analysis Date:** 2026-07-21

## APIs & External Services

**Skill distribution:**
- Agent Skills registry (agentskills.io) - end-user install path via `npx skills add ryanilano/ilano-skills` (`README.md`)
  - SDK/Client: none in-repo; the `skills` CLI is run by consumers, not by this codebase
  - Auth: none
- Claude Code plugin marketplace - repo doubles as a marketplace (`.claude-plugin/marketplace.json`) exposing the `ilano` plugin (`.claude-plugin/plugin.json`)
  - SDK/Client: none; Claude Code reads the manifests directly
  - Auth: none

**Upstream skill repositories (dev-time only):**
- `scripts/diff-upstream.sh` fetches arbitrary upstream Git repos (pinned by `upstream_repo` + `upstream_sha` in a skill's `PROVENANCE.yaml`) via `git fetch --depth 1` to verify vendored/forked skill content
  - Currently unused at runtime: both skills (`skills/copyable-markdown/PROVENANCE.yaml`, `skills/prompt-pack/PROVENANCE.yaml`) declare `origin: original`, so no upstream is pinned
  - Auth: relies on whatever Git credentials the developer's environment provides (public repos need none)

## Data Storage

**Databases:**
- None

**File Storage:**
- Local filesystem only - skills are plain files; `diff-upstream.sh` uses a `mktemp -d` scratch dir cleaned by an EXIT trap

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- None - no authentication anywhere in the codebase

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- Script convention (per `AGENTS.md` and both scripts): status/errors to stderr, machine-readable JSON summary to stdout (`scripts/validate.sh` emits `{"ok": ..., "skills_checked": ..., "failures": ...}`)

## CI/CD & Deployment

**Hosting:**
- GitHub (`ryanilano/ilano-skills`) - the repo itself is the distribution artifact; installs pull directly from it

**CI Pipeline:**
- None - no `.github/` directory or CI config; validation is manual via `scripts/validate.sh` before commits

## Environment Configuration

**Required env vars:**
- None

**Secrets location:**
- Not applicable - no secrets, no `.env` files present

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-07-21*
