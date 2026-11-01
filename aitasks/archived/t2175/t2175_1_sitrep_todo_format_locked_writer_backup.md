---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Done
labels: [sitrep]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-10-31 19:58
updated_at: 2026-11-01 22:32
completed_at: 2026-11-01 22:32
---

# todo.md format, locked writer and backup

First child of t2175 (read its description for the settled design); everything else builds on this.

## Scope
- Define the `.aitask-sitrep/todo.md` format: Part 1 (situation per theme; items grouped Pick now / Next / Waiting / Recently done; item = id, kind `task|action|question|watch`, state `open|done|dismissed|unknown`, title, `checked_at`, agent-derived marker) and Part 2 (per-item context entry with a FIXED schema: background, origin, sources, related items; never status/counts/summaries). Dated Q&A lives in a separate log file, not in context.
- One helper script (name it per `aidocs/framework/aitasks_extension_points.md`) as the SOLE writer: verbs to add/update/set-state/dismiss items, upsert a context entry, append Q&A, and read. Hold the `registry_lock.sh` mutex, write via the atomic-write helper, keep a rolling `todo.md.bak`. Model exit codes and "validate path before acquiring" on `aitask_shadow_rejected.sh` (0 ok, 2 bad request, 3 busy/retryable, 4 store unusable/do not retry).
- Per-section writes so a Part 1 refresh never overwrites a context entry being rewritten.
- Gitignore rule installed by `aitask_setup.sh` like `setup_shadow_store_gitignore()`; keep `seed/` in step. Decide in this task whether the logical file is stored as one or two physical files (read joins them).
- Cap context entry size; long material stays behind a pointer.

## Tests
Bash test with concurrent writers, crash-mid-write, lock busy vs unusable, backup restore, schema rejection of status/count fields in context entries.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-01T15:46:18Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-01T20:31:39Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-01T20:32:31Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:2a4b6e14f08ef98d

> **✅ gate:risk_evaluated** run=2026-11-01T20:32:31Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2175_1/risk_evaluated_2026-11-01T20:32:31Z-risk_evaluated-a1.log`
