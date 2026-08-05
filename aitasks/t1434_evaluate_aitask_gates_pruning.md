---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [shadow]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-05 17:18
updated_at: 2026-08-05 17:18
---

Evaluate and propose an appropriate pruning/GC procedure for `.aitask-gates/`.

## Context

Nothing prunes `.aitask-gates/` today — not `aitask_archive*.sh`, not any
`ait` subcommand; it grows monotonically (one directory per gated task,
holding per-run verifier sidecar `.log` files). Requested during t1427
planning: t1427_1 introduced archive-time pruning for the sibling store
`.aitask-shadow/<task_id>/` (lock-coordinated `prune` subcommand in
`aitask_shadow_rejected.sh`, invoked best-effort from `archive_parent` /
`archive_child` in `aitask_archive.sh`) — use that seam as prior art and
decide whether `.aitask-gates/` should adopt the same policy or a different
one.

## Considerations to evaluate

- Unlike shadow rejections, gate sidecar logs may have POST-archival value:
  the in-body "Gate Runs" summary is committed, but the raw logs are the only
  detailed record of verifier output. Decide whether archive-time deletion is
  acceptable, or whether age-based GC (like `.aitask-explain/` —
  `aitask_explain_cleanup.sh` is the template, including its own-root safety
  check and marker-file guard) fits better.
- Locking: gate logs are written by `lib/gate_verifier_lib.sh` with plain
  `>`/`>>` (no lock). Assess whether pruning needs coordination with an
  in-flight gate run (e.g. skip dirs for tasks that are still active).
- Whether pruning should be automatic (archival hook), scheduled
  (cleanup command), or manual-only — and where the command should live.

## Deliverable

A decision with reasoning, plus either the implementation (if small) or a
follow-up implementation task with the chosen design.
