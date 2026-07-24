---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [workflow, git, profiles]
created_at: 2026-07-24 15:03
updated_at: 2026-07-24 15:03
---

## Problem

The task-workflow lets the user control the branch a task worktree is **created
from** (`base_branch`), but not the branch the finished work is **merged into**.
The merge target is hardcoded.

`.claude/skills/task-workflow/SKILL.md:581-585` (Step 9, Post-Implementation):

```bash
git checkout main
git merge aitask/<task_name>
```

These are the only `git checkout` / `git merge` occurrences in the whole skill
directory. There is no variable, and no fallback to the `Base branch:` value
already recorded in the plan metadata header.

## Where `base_branch` is used today (all pre-merge)

1. **Step 5, worktree creation** — `SKILL.md:252-263` resolves it (from the
   profile key, else an `AskUserQuestion` whose recommended option is literally
   `"main (Recommended)"`), then feeds it to
   `git worktree add -b aitask/<task_name> aiwork/<task_name> <base-branch>`
   (`SKILL.md:265-272`).
2. **Plan metadata header** — `planning.md:385` and `:398` record it as a
   `Base branch:` line in the plan file.
3. **Remote drift check** — `remote-drift-check.md:9,24` reads it back from that
   plan header and passes it to `aitask_remote_drift_check.sh`.

So `base_branch` never reaches Step 9. A project that bases worktrees on a
long-lived integration branch still gets its work merged into `main`.

## Motivation

A project whose `main` is the production branch (e.g. `thinking_backend`, where
publishing a GitHub Release from `main` auto-deploys to prod) wants all task
work to land on a `dev` integration branch instead. Today the only ways to
achieve that are:

- set `create_worktree: false`, so Step 9's merge block (guarded by "If a
  separate branch was created:", `SKILL.md:555`) never runs — but this gives up
  worktree isolation for parallel tasks; or
- override the merge target in the project's `CLAUDE.md` — advisory only, since
  the skill text still says `main` and the agent must choose to disobey it.

Neither is enforced by the framework. There is no git-level workaround: git has
no branch aliasing, and `post-checkout` / `pre-merge-commit` hooks fire after
the target is resolved.

## Proposal

Introduce an **output branch** (merge target) as a first-class, separately
configurable value, defaulting to `base_branch` when unset so existing
behaviour is unchanged.

- Add an `output_branch` profile key alongside `create_worktree` /
  `base_branch`. When unset, it falls back to the resolved `base_branch`; when
  that is also unset, to the current interactive default.
- Resolve it at Step 5, next to `base_branch`, using the same
  profile-key-else-`AskUserQuestion` pattern, and record it in the plan metadata
  header as an `Output branch:` line (parent and child header templates).
- Consume it at Step 9: replace the hardcoded `git checkout main` with the
  resolved output branch, read from the plan metadata header (the same way
  `remote-drift-check.md` reads `Base branch:`), so a resumed workflow
  (`POSTIMPL` re-entry) still merges to the right place.
- Update the Step 9 merge-approval `AskUserQuestion` wording — it currently
  hardcodes "Proceed with merge of code changes to main branch?" — to name the
  actual resolved target. The gate stays NON-SKIPPABLE.
- Consider whether the drift check should watch the output branch as well as
  the base branch when the two differ (a base that has not moved does not imply
  the merge target has not moved).

## Files in scope

- `.claude/skills/task-workflow/SKILL.md` — Step 5 (~230-280), Step 9 (~555-590)
- `.claude/skills/task-workflow/planning.md` — plan metadata headers (~379-399)
- `.claude/skills/task-workflow/profiles.md` — profile schema table (~29) and example (~110)
- `.claude/skills/task-workflow/remote-drift-check.md` — if drift coverage is extended
- `.aitask-scripts/lib/profile_editor.py` — `base_branch` field docs (~134-139); add the `output_branch` entry
- `aitasks/metadata/profiles/*.yaml` — profile files that may set the new key

The canonical `task-workflow/` files are Jinja sources (`{% if profile.* %}`);
the `-default-`, `-fast-`, `-remote-` and per-agent (`codex_skills/`,
`opencode_skills/`) variants are rendered from them. Re-render via
`.aitask-scripts/aitask_skill_rerender.sh` and check coverage with the
`aitask-audit-wrappers` skill. Remote/web profiles currently list `base_branch`
among the ignored keys — decide whether `output_branch` joins that list.

## Acceptance

- A profile setting `output_branch: dev` causes Step 9 to merge into `dev`,
  with `base_branch` free to differ.
- With `output_branch` unset, behaviour is byte-identical to today.
- The merge-approval prompt names the real target branch.
- All rendered skill variants agree with the canonical source.
