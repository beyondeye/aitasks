---
priority: high
effort: high
depends: []
issue_type: refactor
status: Done
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 16:34
updated_at: 2026-06-01 17:16
completed_at: 2026-06-01 17:16
---

## Context

Foundation rework for the t884 two-dimension risk redesign. The original t884_1
(archived) shipped a **single aggregate** `risk` frontmatter field. Per user
redirect, risk is now estimated and stored as **two independent fields**:

- `risk_code_health` — `high|medium|low`; stability / quality / maintainability
  / blast-radius risk of the planned change.
- `risk_goal_achievement` — `high|medium|low`; whether the planned implementation
  will actually deliver the user's requested goals (approach soundness,
  requirement coverage, technical feasibility, completeness).

This task **replaces** the single `risk` field with the two fields **everywhere**
(no aggregate kept), mirroring t884_1's plumbing but doubled. Both fields are
scalar, **omitted by default** (planning output, not a creation input),
**display-only** (no sort score, no border color). `risk_mitigation_tasks` stays
a single shared list (unchanged).

t884_3 (risk-evaluation planning step) and downstream siblings depend on these
flags/serialization existing. t884_3 was reverted to Ready and now `depends` on
this task.

## Key Files to Modify

- `.aitask-scripts/aitask_update.sh` — replace the single `--risk` plumbing with
  two flags `--risk-code-health` / `--risk-goal-achievement`:
  - Two BATCH/`_SET` var pairs + two `CURRENT_*` vars (replace `BATCH_RISK`/
    `CURRENT_RISK`).
  - Two flag parse arms (replace `--risk`, ~242); two validation blocks
    `high|medium|low`, validated only when non-empty so `""` clears (~1461).
  - Two `interactive_update_*` functions (replace `interactive_update_risk`
    ~1036) + two rows in `interactive_select_field` (replace the 7th-param
    "risk" row) + two field handlers + two summary lines.
  - `write_task_file`: replace positional `${25}` (risk) with two positional
    params, emitted conditionally right after `priority:` (drop the old single
    `risk:` emit ~514). Wire through all three call sites + the child-completion
    save/restore block (~897/941).
  - Keep `--risk-mitigation-tasks` exactly as-is.
- `.aitask-scripts/aitask_ls.sh` — replace the single `risk_text` parse (~182,
  ~234) and render (~438) with two values; render as `, CH-risk: <v>, GA-risk:
  <v>` between Priority and Effort, each only when set. No score (stay out of
  `p_score`). Confirm exact label wording at edit time.
- `.aitask-scripts/board/aitask_board.py` — replace the single `risk` snapshot
  key (~2391) with two; two ReadOnlyFields shown only when set (~2429); two
  `CycleField`s `"Code-health risk"` / `"Goal risk"` (replace the single
  `CycleField("Risk", …)` ~2442). Same index-0 unset-renders-as-"low" editor
  quirk accepted (documented in t884_1); data layer stays omit-by-default.
- `.aitask-scripts/aitask_fold_mark.sh` — scalars → no fold change needed (mirror
  t884_1). `risk_mitigation_tasks` still dropped on fold (unchanged).
- `tests/test_update_risk.sh` — rework for two flags/fields.
- `tests/test_fold_risk_mitigation_drop.sh` — primary keeps **both** risk fields.

## Reference Files for Patterns

- `aiplans/archived/p884/p884_1_risk_frontmatter_field_plumbing.md` — the exact
  single-field plumbing this task doubles (var names, line anchors, the
  conditional-emit / `_SET`-clears-on-empty pattern, the board CycleField
  caveat).
- `aitask_update.sh` `verifies` / `xdeprepo` conditional-emit handling — model
  for omit-by-default serialization.

## Implementation Plan

1. `aitask_update.sh`: introduce the two flags + vars + validation + interactive
   entries + two conditional `write_task_file` emits; remove the single `--risk`
   surface. Keep `--risk-mitigation-tasks`.
2. `aitask_ls.sh`: two display values.
3. `aitask_board.py`: two snapshot keys, two ReadOnlyFields, two CycleFields.
4. `aitask_fold_mark.sh`: confirm scalars need no change; keep the
   `risk_mitigation_tasks` drop.
5. Rework both test files; `shellcheck` the edited scripts.

## Verification Steps

- `aitask_update.sh --batch <id> --risk-code-health medium
  --risk-goal-achievement high` sets both fields; interactive mode offers both;
  `--risk-code-health ""` clears it.
- A freshly created task carries **neither** field (create.sh untouched —
  guard test).
- Fold a task carrying `risk_mitigation_tasks` into a primary → primary keeps
  both its risk fields; the list is NOT carried over.
- `bash tests/test_update_risk.sh && bash tests/test_fold_risk_mitigation_drop.sh`
  both PASS.
- `shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_ls.sh
  .aitask-scripts/aitask_fold_mark.sh tests/test_update_risk.sh
  tests/test_fold_risk_mitigation_drop.sh` clean.
- `ait board` renders both risk fields (read-only for Done/Folded, CycleField
  otherwise); tasks with no risk render without error. *(TUI rendering covered
  by the t884_8 manual-verification sibling.)*

## Notes for sibling tasks

- t884_3 writes both fields at Step 7 via
  `--risk-code-health <ch> --risk-goal-achievement <ga>`.
- t884_4 read-modify-writes `risk_mitigation_tasks` (single list, replace-all).
- t884_6 docs + t884_8 manual verification now describe TWO risk fields.
