---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1747_4, t1747_5, t1747_6, t1747_7]
anchor: 1733
followup_kind: risk_mitigation
created_at: 2026-09-08 18:35
updated_at: 2026-09-11 15:11
---

## Origin

Risk-mitigation ("after") follow-up for t1733, created at Step 8d after implementation landed.

## Risk addressed

Addresses the goal-achievement risk recorded in `aiplans/p1733_fold_amend_guard_fails_open_on_unreadable_head.md`:

> This closes the fail-open probe at the **second** of an unknown number of sites
> in the same class. A sweep found at least two further authorization sites with
> the same `|| true` shape gating a destructive action — `aitask_sync.sh`
> `_rebase_advance` (a failed `diff --diff-filter=U` reads as "no conflicts" and
> proceeds to `rebase --skip`, which **discards a commit**) and
> `aitask_setup.sh:3585-3596` (a failed dirtiness probe reads as clean). Fixing
> only this site leaves the class alive. · severity: medium

## Goal

Audit every framework site where a fail-open (or-true suppressed) git probe gates
a **destructive or authorizing** action, and apply the rule
`lib/task_utils.sh::task_git_commit_scoped` already states: capture the probe's
exit status separately so a failed probe reads as *unverified*, never as *clean*.

Two instances of the class have already been closed and are the reference
implementations:

- `.aitask-scripts/aitask_issue_import.sh:657-666` (t1599_4)
- `.aitask-scripts/aitask_fold_mark.sh` `_fold_amend_guard` (t1733) — see
  `aiplans/archived/` for `p1733_*` once archived

### Known candidates (confirmed by inspection during t1733, not yet fixed)

- `.aitask-scripts/aitask_sync.sh:988` — `_rebase_advance` reads unresolved paths
  as `task_git diff --name-only --diff-filter=U 2>/dev/null || true`. A failed
  probe yields an empty list, is taken as "no unresolved files", and the function
  proceeds to `rebase --skip` — which **discards a commit**. This is the
  highest-severity candidate: the fail-open outcome is data loss, not just a
  wrong decision.
- `.aitask-scripts/aitask_setup.sh:3591-3594` — the dirtiness probe suppresses
  `git ls-files --others --exclude-standard`, `git ls-files --modified` and
  `git diff --cached --name-only` failures with `|| true`, so an unreadable
  worktree reads as **clean**. Check what that cleanliness answer gates before
  deciding the fix.

Sites at `aitask_sync.sh:1008` and `:1025` share the same shape and should be
assessed in the same pass.

### Scope discipline

The sweep is over **authorization sites** — probes whose answer decides whether a
destructive or history-rewriting action proceeds. A `|| true`-suppressed probe
that only feeds an informational display (e.g. `aitask_remote_drift_check.sh`,
`aitask_change_surface.sh`, `aitask_revert_analyze.sh`) is **not** in scope;
tightening those would add noise without removing risk. Enumerate the candidate
set first, classify each as authorizing vs informational, and record the
classification — including the sites deliberately left alone and why.

## Verification

For each site actually changed:

- A **negative control** that observes the fail-open behavior against a mutant
  restoring the `|| true` shape, following the pattern in
  `tests/test_fold_mark.sh` (`install_prefix_amend_probe` — it regresses only the
  probe, verifies its own substitution landed, and asserts the rest of the guard
  survived, so a control cannot pass vacuously).
- The **fixture precondition asserted, not assumed**: an empty or failed probe
  result is a symptom several unrelated fixture accidents produce, so each test
  must pin that its fixture really has the shape it claims before invoking the
  code under test.
- The **permit direction** must stay green — a tightened probe must not start
  refusing legitimate operations.
- For `_rebase_advance` specifically, the discriminating case must be one where
  the `rebase --skip` **would otherwise have succeeded**, so the test proves a
  failed probe does not authorize the commit-discarding path.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:risk_evaluated** run=2026-09-09T08:11:33Z status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: planning-time risk evaluation: code_health=low, goal_achievement=medium
