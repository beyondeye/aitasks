---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [workflow, git, profiles]
gates: [risk_evaluated]
anchor: 1233
created_at: 2026-07-28 01:10
updated_at: 2026-07-28 01:10
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
   was actually cut from.
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
