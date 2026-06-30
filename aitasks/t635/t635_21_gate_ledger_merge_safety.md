---
priority: low
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t635_1]
issue_type: enhancement
status: Implementing
labels: [gates, task_workflow]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 13:33
updated_at: 2026-06-30 11:36
---

## Context

Forward-looking gap surfaced during **t635_2** (checkpoint recording) planning.
Gate-run blocks are append-only at EOF and a task is *locked* while worked, so
single-lane recording (t635_2) merges cleanly under the existing `ait git`
rebase (`task_push`) + `aitask_merge.py` frontmatter auto-merge. The gap appears
once a gate can be **passed from a different PC than the lock-holder** — async
human gates (t635_15), remote projection (t635_16) — when two machines may
append to the same `## Gate Runs` section of one task concurrently.

Today `aitask_merge.py merge_body()` (`.aitask-scripts/board/aitask_merge.py`)
treats any body divergence as unresolved (wraps both sides in conflict markers),
and there is **no `.gitattributes`** in the repo, so two concurrent gate-block
appends would surface as a manual body conflict during `ait sync` / `task_push`
rebase — exactly the friction the ledger is meant to avoid.

This is roadmap **"open design problem 3"**
(`aidocs/gates/integration-roadmap.md`). It is NOT a blocker for t635_2
(single-lane recording is safe) but **must land before t635_15** (first phase
with cross-PC gate passing).

## Scope

Make concurrent appends to a task's `## Gate Runs` section merge automatically.

- **Option A — git `merge=union` driver** via a new `.gitattributes`. Evaluate
  whether union-merging whole task `.md` files is safe (it would also union
  prose body edits — likely too broad) vs. a custom merge driver scoped to the
  `## Gate Runs` region only.
- **Option B (likely preferred) — teach `aitask_merge.py` to union-merge** the
  append-only gate blocks. It already runs during `aitask_sync.sh` rebase
  (`try_auto_merge`); extend `merge_body()` to detect `## Gate Runs` and union
  the blockquote blocks (dedup by `run=` timestamp), leaving the rest of the
  body on the existing conflict-marker path.
- Decide A vs B (or hybrid) at planning. B composes with the existing auto-merge
  infra and avoids global `.gitattributes` semantics.

## Key files to modify

- `.aitask-scripts/board/aitask_merge.py` — `merge_body()` (conflict path),
  `merge_frontmatter()` (union precedent for `labels`/`depends`).
- `.aitask-scripts/aitask_sync.sh` — `try_auto_merge()` rebase invocation.
- `.aitask-scripts/lib/gate_ledger.py` — `parse_gate_runs` / `derive_status`
  (reuse for dedup-by-`run`; do NOT fork — t635_8 owns the shared parser).
- `.gitattributes` (new, only if Option A).

## Reference patterns

- Frontmatter union precedent: `aitask_merge.py merge_frontmatter()` unions
  `labels`/`depends` — mirror for gate blocks.
- Append-only marker contract: `aidocs/gates/aitask-gate-framework.md`
  §"Gate run marker format" ("always append; never rewrite"). Derivation is
  last-run-per-gate-wins, so a merged superset of blocks must still derive the
  correct current status.

## Implementation plan

1. Decide Option A vs B (planning).
2. Implement union merge for the gate section.
3. Tests: simulate two divergent gate appends to the same task, rebase/merge,
   assert both blocks survive, ordering is deterministic, and
   `aitask_gate.sh status` still derives correctly (last-run-wins) from the
   merged file. Model on `tests/test_aitask_merge.py` + `tests/test_sync.sh`.

## Verification

- New test: concurrent gate appends auto-merge with no manual conflict.
- `tests/test_aitask_merge.py` + `tests/test_sync.sh` stay green.

## Coordination

- Roadmap open problem 3 (`aidocs/gates/integration-roadmap.md`).
- **Blocks t635_15** (t635_15 `depends` includes t635_21).
- Reuse `lib/gate_ledger.py` derivation (t635_8 owns the shared parser — do not
  fork).
- Surfaced by **t635_2** (see its reverse pointer).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T08:36:46Z status=pass attempt=1 type=human
