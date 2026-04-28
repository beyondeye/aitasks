---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [release, changelog]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 17:28
updated_at: 2026-04-28 17:30
---

## Problem

`./create_new_release.sh` does `git push origin main --tags` without a
preceding pull. When the remote `main` has commits the local branch
doesn't, the push fails after the tag has already been pushed,
leaving the release in an inconsistent state (tag present on remote,
branch behind). This just happened on the v0.19.0 release: the tag
`v0.19.0` pushed successfully, then `main` was rejected as
non-fast-forward, requiring a manual merge + push.

The same issue applies to `/aitask-changelog`: the skill commits
`CHANGELOG.md` based on the local commit graph (Step 1 gathers
commits via `aitask_changelog.sh --gather` on local refs), so if
remote has unpulled commits, those tasks are silently missing from
the generated changelog. The skill never fetches/pulls before
gathering.

## Fix

### create_new_release.sh

Before doing any work, sync with remote so the script fails fast on
divergence rather than after pushing the tag:

- After the initial argument validation, run `git fetch origin` and
  check whether local `main` is behind `origin/main`. If behind, run
  `git pull --rebase origin main` (or merge if rebase isn't safe).
- If divergence cannot be cleanly resolved (e.g., conflicts), abort
  with a clear message before the version bump.
- The pre-push pull guarantees the final `git push origin main
  --tags` succeeds atomically.

### aitask-changelog skill

Add a **Step 0: Sync with remote** before Step 1 (Gather Release
Data):

- Run `git fetch origin` and inform the user if local `main` is
  behind.
- Offer to run `git pull --rebase origin main` (`AskUserQuestion` —
  "Sync now / Skip / Abort").
- Without this, the changelog can silently miss tasks that have
  landed on remote but not been pulled locally.

## Acceptance criteria

- `create_new_release.sh` aborts before tagging if it cannot
  fast-forward, OR pulls cleanly first; the tag-and-push step never
  leaves the remote in a half-pushed state again.
- `/aitask-changelog` Step 0 runs a fetch + offers a pull before
  Step 1, so gathered commits reflect the full remote history.
- Manual test: simulate a remote-ahead scenario (locally reset main
  by one commit, run the release script, verify it pulls/aborts
  cleanly instead of partial-push).

## References

- create_new_release.sh:74 — the offending push line
- .claude/skills/aitask-changelog/SKILL.md — Step 1 onwards
- v0.19.0 release incident (2026-04-28): tag pushed, main rejected,
  manual `git merge origin/main && git push` to recover.
