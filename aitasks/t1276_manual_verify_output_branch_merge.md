---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [workflow, git, profiles]
anchor: 1233
created_at: 2026-07-28 01:10
updated_at: 2026-07-28 01:10
boardidx: 48128
---

## Origin

Risk-mitigation ("after") follow-up for t1233, created at Step 8d after
implementation landed.

## Risk addressed

- Goal-achievement: the merge target is resolved by prose instructing an agent to
  read a plan-header field and apply a two-rung fallback, at the one site whose
  failure mode is "merged into the wrong branch".
- Goal-achievement: the automated suite asserts that prose renders and that the
  plan header round-trips, but never executes a real `git merge` into a
  non-primary branch.
- Code-health: the Step 9 checkout pre-flight (tag-shadowing, missing branch,
  branch held by another worktree, symbolic-HEAD assertion) is prose, not code.

## Goal

Run a real worktree task end-to-end under a profile whose `output_branch` is a
non-primary branch, and confirm the whole chain by hand. The automated tests
cannot cover the final hop.

## Verification Checklist

- Create a scratch profile with `create_worktree: true`, `base_branch: main`,
  `output_branch: dev`, and pick a small task under it.
- Step 5 displays "using output branch dev".
- The externalized plan header records `Output branch: dev` (and `Base branch:`
  is untouched).
- Step 9's merge prompt names `dev` AND its provenance (`plan header`).
- The merge actually lands on `dev`; `main` is unchanged.
- `git symbolic-ref --short HEAD` prints `dev` between checkout and merge.
- Pre-flight: delete local `dev` and confirm the workflow stops and asks rather
  than letting `git checkout` create a tracking branch silently.
- Pre-flight: check `dev` out in a second worktree and confirm the workflow
  surfaces the conflict and asks, rather than failing mid-merge.
- Pre-flight: create a TAG named `dev` with no branch `dev` and confirm the
  workflow refuses rather than landing in detached HEAD.
- Repo root already on `dev`: confirm the workflow proceeds (checkout is a safe
  no-op) rather than rejecting its own worktree.
- Unset `output_branch` (leave `base_branch: main`): confirm the merge still goes
  to `main` and behaviour is unchanged from before t1233.
- A legacy plan with no `Output branch:` line merges to `main`, not to its
  `Base branch:` value.
