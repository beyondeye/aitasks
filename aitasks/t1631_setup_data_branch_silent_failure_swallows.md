---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [worktree, git]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-26 22:22
updated_at: 2026-08-27 11:21
---

## Origin

Spawned from t1627 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1496 — `git fetch origin aitask-data
  2>/dev/null || true` sets `branch_exists=true` unconditionally afterwards, so
  a failed fetch is recorded as "branch found" and Step 2 then dies on an
  invalid reference. Left out of t1627's scope deliberately: it is a probe
  rather than a warn/return path, and there is no deterministic way to make only
  the fetch fail in a fixture. Its symptom is now at least legible, since Step 2
  reports git's real error.`
- `.aitask-scripts/aitask_setup.sh:1524-1526 — `cp -a … 2>/dev/null || true` in
  the migration branch of Step 3 silently swallows a failed copy of the user's
  existing `aitasks/`/`aiplans/` data, then proceeds to Step 5, which
  `git rm -r`s the originals from main. A partial copy is therefore
  indistinguishable from a complete one at the point the source is deleted.`

## Diagnostic context

t1627 fixed the message on `setup_data_branch`'s worktree-add failure path and
swept the two neighbouring `warn` sites that discarded git's stderr. These two
sites share the same defect class — a failure is discarded and the flow
continues on an assumption the failure invalidated — but were left out because
neither is a `warn`/`return` path and neither could be driven deterministically
from a fixture without further work.

The second is materially more serious than the first. The migration branch is
the one path in `setup_data_branch` that **deletes user data**: Step 3 copies
`aitasks/` and `aiplans/` into the new data worktree, and Step 5 then runs
`git rm -r --quiet aitasks/ aiplans/` plus `rm -rf` on main. With `cp -a`'s
status discarded, a copy that failed part-way (permissions, a full disk, an
unreadable file) reaches Step 5 looking exactly like a complete one, and the
originals are removed. There is no verification between the copy and the
delete.

The first is a correctness/legibility bug rather than a data-loss one: the
remote probe at :1494 decides `branch_exists=true` from `ls-remote`, then the
fetch that actually materializes the ref is allowed to fail silently. Step 2
subsequently fails with git's "invalid reference: aitask-data" — which t1627
now surfaces, so the user at least sees a real error instead of the old
impossible remedy.

## Suggested fix

For :1496 — capture the fetch's stderr, `warn` with it, and do not claim
`branch_exists=true` on a failed fetch (fall through to the local `show-ref`
check, which is the honest answer).

For :1524-1526 — check `cp -a`'s exit status and abort the migration before
Step 5 if it failed, leaving the user's data on main untouched. Consider
verifying the copy (file count or `diff -r`) before the `git rm`, since the
delete is irreversible from setup's point of view. Note the same
`2>/dev/null || true` shape appears on the `aiplans` copy directly below.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-27T08:22:09Z status=pass attempt=1 type=human
