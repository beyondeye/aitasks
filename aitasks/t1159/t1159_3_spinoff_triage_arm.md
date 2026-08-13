---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [1]
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-11 15:34
updated_at: 2026-08-13 12:32
---

Add the "spin off as separate task" triage arm to the concern picker: a fourth per-row state that, on confirm, creates a draft aitask per spun-off concern via `aitask_create.sh --batch`. Closes the folded-t1017 steerability requirement of t1159 (parent design: `aiplans/p1159_shadow_review_loop_automation.md`; child plan: `aiplans/p1159/p1159_3_spinoff_triage_arm.md`). Depends on t1159_1 only (the modal's `block_meta` keyword ordering); independent of t1159_2 — can run in parallel with it.

## Context

t1017 (folded into t1159): shadow reviews surface secondary concerns that either bloat the plan (user iterates until "complete" but unsteerable) or get lost. The picker already has per-row tri-state from t1427 (`_ConcernRow`: none ☐ / forward ☑ / rejected ✗; bulk keys removed by design). This child adds the fourth mutually-exclusive state "spinoff" (`»`, key `t`) routing a concern to "park as its own task" — keeping the user in control of what enters the plan vs what gets tracked separately.

## Key decisions (user-confirmed at parent planning — do not reopen)

- Picker creates tasks DIRECTLY (shell-out), as DRAFTS (no `--commit`): offline-safe inside a TUI worker, reversible, anti-bloat. Drafts land in `aitasks/new/` and have NO ids until finalization — report DRAFT PATHS, notify "N concern(s) parked as drafts in aitasks/new/ — finalize with 'ait create'".
- Provenance: `--followup-of <task_id>` (the REVIEWED task from picker context — anchors to its topic root) + `--followup-kind review_finding` (canonical vocabulary `lib/followup_kinds.py`, validated pre-write). Confirm at implementation that both flags flow through the draft (no --commit) path; if --followup-of needs a live task lookup that fails on the draft path, record the anchor in the description and flag it.
- Collision-safe naming (REQUIRED): `get_draft_filename()` timestamps at MINUTE precision (`date '+%Y%m%d_%H%M'`, aitask_create.sh:601-607) and `ait_atomic_render` silently replaces an existing path — loss made persistent if the concern was also store-marked. A batch index alone is not enough (second confirmation same minute), nor is a worker-start epoch second (concurrent instances/workers). Use a per-batch cross-process nonce: `uuid.uuid4().hex[:8]` + 1-based index → name `shadow_<region>_<nonce>_<i>`, with suffix-preserving truncation (truncate the region segment, never nonce/index, under the name-length cap).
- Loop hygiene: after successful creation, `aitask_shadow_rejected.sh add <task_id> --producer spinoff` (helper accepts arbitrary --producer, sanitized at write site) so the next review round suppresses the now-tracked concern. Reuses the t1427 store exactly as designed — task-scoped, no layout change.

## Key files to modify

- `.aitask-scripts/monitor/monitor_shared.py`:
  - `_CONCERN_MARKS` (~line 1911): add `"spinoff": "[bold cyan]»[/]"` (single-width U+00BB; verify against the `_NARROW_PREFIX_COLS` budget contract stated on the dict).
  - `_ConcernRow` (1923-2099): fourth mutually-exclusive state `"spinoff"`, key `t` in `on_key` (with prevent_default/stop like space/`r`), property `spun_off`. Update quad-state docstring.
  - `ConcernPickResult` (1868-1883): add field `spun_off: list[Concern]` WITH NO DEFAULT — contract-completeness rule: amend EVERY constructor (`ConcernPickerModal._result()` at 2607-2612 ordering by original_index) and every test literal in `tests/test_concern_picker_modal.py` + `tests/test_minimonitor_concern_action.py` in the SAME commit.
  - `ConcernPickerModal`: help texts (`_CONCERN_HELP_FULL`/`_CONCERN_HELP_COMPACT`) gain `t:spin off as task`; `_context_line()` wording "forward, reject, or spin off".
  - `apply_concern_pick_result` (`ShadowRejectionsMixin`, 665-705): after forward/reject handling, `spun_off` → worker `_spawn_concern_tasks(result.spun_off, task_id)`; no task id → visible warning, no subprocess. Extract a `_run_create_cmd` subprocess seam beside `_run_rejected_cmd` (~620-645, same timeout discipline) so tests spy it without executing bash.
- Per-concern invocation: `aitask_create.sh --batch --silent --name <unique> --desc-file - --priority <c.priority> --labels shadow-concern --followup-of <task_id> --followup-kind review_finding`, description embeds `concern_marker_line(c)` (canonical `.body` — FORWARD role) + one line of provenance prose ("Spun off from a shadow review concern on t<task_id>."). `--silent` prints exactly one line: the created path.

## Reference files for patterns

- `monitor_shared.py:707-736` `_persist_concern_dispositions` (stdin-fed subprocess + exit-code vocabulary at 738-760: 3=LOCK_BUSY retryable, 4=unusable, 2=bad request).
- `tests/test_concern_picker_modal.py` (pure modal harness), `tests/test_minimonitor_concern_action.py` (`_FakeMon`, spy notify/push_screen).
- `tests/test_concern_body_display_contract.py` — t1294 AST guard: REGISTER the new spin-off description builder as a FORWARD surface (it reads `.body` via `concern_marker_line`).

## Verification

- Modal: `t` toggles spinoff; mutual exclusivity across all four states; `spun_off` carries original input order; all-empty result distinct from None (cancel); help text names `t`.
- Spin-off flow: `_run_create_cmd` spy called once per concern with `--batch --silent --desc-file -` + `--followup-of`/`--followup-kind` in argv and the canonical marker line on stdin; draft-path (not id) reporting; no-task-id → warning, no subprocess; store `add --producer spinoff` follows success only.
- Collision tests: two same-region concerns in ONE confirmation → distinct paths, both created; TWO distinct confirmations frozen to the identical epoch second (patched clock) → distinct paths, first batch's drafts intact.
- AST guard registration passes; `bash tests/run_all_python_tests.sh` — final stderr verdict line only.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T09:32:17Z status=pass attempt=1 type=human
