---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [workflow, git, profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1233
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-07-28 01:10
updated_at: 2026-08-17 11:26
boardidx: 53248
---

## Origin

Risk-mitigation ("after") follow-up for t1233, created at Step 8d after
implementation landed. Recorded as non-goal 1 of that task.

## Risk addressed

- Goal-achievement: the plan header's `Base branch:` records
  `detect_primary_branch()` rather than the Step-5 resolved base branch, so the
  two branch fields in one header derive from different sources.

## Problem

`.aitask-scripts/aitask_plan_externalize.sh` writes `Base branch: $primary`,
where `primary=$(detect_primary_branch)`. It never consults the resolved base
branch. So a profile setting `base_branch: develop` produces a header reading
`Base branch: main`.

Two consequences:

1. `remote-drift-check.md` sources `base_branch` from that header line, so the
   drift check watches the repository primary instead of the branch the worktree
   is cut from. (Phrased as "will be cut from" once t1536 lands — see the
   cross-reference section below; at drift-check time the fork no longer exists
   yet.)
2. Within one header, `Base branch:` and `Output branch:` are derived
   differently — t1233 made the output field authoritative (profile
   `output_branch`, else the resolved base branch via
   `--output-branch-default[-file]`, else primary), while the base field stayed
   on the old detection-only path.

This was deliberately left out of t1233 to keep that change additive: fixing it
alters what existing users' headers record and therefore which branch the drift
check watches.

## Goal

Give `Base branch:` the same resolved-context treatment `Output branch:` already
has, so both fields in a header come from one source.

## Suggested direction

- Add `--base-branch <name>` (validated by the existing `validate_branch_name`)
  and read `base_branch` from `--profile` for the header field, not only as the
  output fallback.
- Thread the Step-5 resolved base branch through both externalize call-sites,
  reusing the `<branch-flags>` contract and the non-shell value-file channel for
  interactively chosen names.
- Decide whether `remote-drift-check.md` should then compare base vs output
  differently, since they may now legitimately differ more often.

## Acceptance

- A profile with `base_branch: develop` produces `Base branch: develop`.
- `tests/test_plan_externalize.sh` Test 1 and Test 13 (master-primary repo)
  updated and passing.
- The drift check watches the resolved base branch.
- With no base branch resolved, behaviour is unchanged (detected primary).

## Escalated by t1536 — implement this task FIRST

**t1536_defer_worktree_fork_until_after_plan_approval** moves the
`git worktree add` out of Step 5: Step 5 keeps only the branch *resolution*, and
the fork runs at the top of Step 7, after plan approval and after the Remote
Drift Check clears.

That change turns this task from a **reporting** bug into a **fork-correctness**
bug:

- Today the fork happens at Step 5, so the on-disk `aitask/<task_name>` branch is
  the ground truth for what was cut and this header field only misdirects the
  drift check.
- After t1536, the plan header is the *carrier* of branch context across the gap
  between resolution (Step 5) and fork (Step 7). Re-entry Routing is explicit
  that "a resumed session carries none of the Step 5 branch variables … resolve
  both branches **from the plan header only** — never from `profile.base_branch`"
  (`.claude/skills/task-workflow/SKILL.md:256`).
- t1536 creates a resumable state that does not exist today — plan approved, no
  worktree yet (stopped at the checkpoint, or crashed between approval and the
  fork). Resuming there means re-entry must *create* the worktree from the header
  value. With this task unfixed, a profile setting `base_branch: develop` would
  cut the worktree from `main`: the wrong branch, not merely a wrong label.

**Sequencing:** implement this task before t1536. Both add a validated flag to
`aitask_plan_externalize.sh` threaded through the same `<branch-flags>` contract
at the same two call-sites (`plan-externalization.md:22-41`) — this one adds
`--base-branch`, t1536 adds `--worktree`. Doing this one first makes t1536's flag
a small addition to an already-threaded channel; the reverse order threads the
channel twice. t1536's description records `depends: [1277]` as the expected
planning-time outcome.

**Also revisit the open question in "Suggested direction"** ("Decide whether
`remote-drift-check.md` should then compare base vs output differently") in light
of t1536: after the move, the drift check runs while the fork is still
hypothetical, which changes what a base-branch drift warning means and what the
user can usefully do about it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-17T08:26:35Z status=pass attempt=1 type=human
