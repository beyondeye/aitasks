---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [worktree, git]
gates: [risk_evaluated]
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-26 14:38
updated_at: 2026-08-26 14:38
---

## Origin

Spawned from t1616 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_init_data.sh:60-103 — a bare (no-flag) invocation
  inside a linked task worktree dies with "Failed to create worktree" instead of
  reporting a usable state. Its ALREADY_INIT probe tests the relative
  `.aitask-data/.git`, which is absent in an unlinked worktree, so control falls
  through to `git worktree add .aitask-data aitask-data` for a branch already
  checked out in the primary — which git refuses.`

## Diagnostic context

t1616 added `--link-worktree <dir>`, a *separate* code path that resolves the
main root from the supplied directory and creates the layout there. It
deliberately did not change the bare invocation, so this rough edge is
pre-existing and untouched.

The mechanism, traced during t1616:

1. Check 1 probes `[[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]`
   relative to `$PWD`. In an **unlinked** worktree neither exists, so it is not
   `ALREADY_INIT`.
2. Check 2 (`LEGACY_MODE`) tests whether `aitasks` is a real directory. In a
   worktree of a branch-mode project it is absent entirely, so this does not
   fire either.
3. Check 3 finds the `aitask-data` branch (it is a real branch of the shared
   repo), so the script proceeds.
4. Step 4 runs `git worktree add .aitask-data aitask-data`, which fails because
   that branch is already checked out at the primary's `.aitask-data`. The
   script then `die`s with "Failed to create worktree. Run: git worktree add
   .aitask-data aitask-data" — advice that cannot work.

The failure is loud rather than silent, so this is a usability defect rather
than a correctness one: the message names an impossible remedy and does not
mention the flag that actually applies.

## Suggested fix

Detect the linked-worktree case before Step 4 and report it as its own state
rather than attempting the add. The main root is already derivable the way
`--link-worktree` does it (`git rev-parse --path-format=absolute
--git-common-dir`, then `dirname`); when `$PWD` is not that root, emit a
distinct token and point at `--link-worktree <dir>`. Reuse `ait_canon_path` and
the guard block already in the same script rather than adding a parallel
derivation.

Add a case to `tests/test_init_data.sh` alongside the existing
`--link-worktree` family (cases 10-22), asserting the new token and that no
`git worktree add` was attempted.
