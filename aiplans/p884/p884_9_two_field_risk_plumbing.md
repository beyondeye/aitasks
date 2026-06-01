---
Task: t884_9_two_field_risk_plumbing.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_9_two_field_risk_plumbing
Branch: aitask/t884_9_two_field_risk_plumbing
Base branch: main
---

# Plan: t884_9 — Two-field risk frontmatter plumbing (replaces aggregate `risk`)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Doubles the single-field plumbing landed by t884_1 (archived plan:
> `aiplans/archived/p884/p884_1_risk_frontmatter_field_plumbing.md`).

## Goal

Replace the single aggregate `risk` frontmatter field with **two independent
fields** — `risk_code_health` and `risk_goal_achievement` (each
`high|medium|low`) — **everywhere** the single field was wired. Both are
**omitted by default** (planning outputs, never creation inputs), **display-only**
(no sort score, no border color). `risk_mitigation_tasks` is unchanged (single
shared list, dropped on fold).

This is a pure refactor/extension of t884_1's surface; **zero behavior change when
both fields are absent**. It unblocks t884_3 (which `depends` on it).

## Steps

1. **`aitask_create.sh` — no change.** Neither field is a creation-time input
   (both written post-create by t884_3's evaluation step). Mirror t884_1: do not
   add flags/prompts/validation/serialization. The `test_update_risk.sh` guard
   re-asserts created tasks carry neither field.
2. **`aitask_update.sh`** — replace the single `--risk` surface with two:
   - `BATCH_RISK_CODE_HEALTH`/`_SET`, `BATCH_RISK_GOAL_ACHIEVEMENT`/`_SET`;
     `CURRENT_RISK_CODE_HEALTH`, `CURRENT_RISK_GOAL_ACHIEVEMENT` (replace
     `BATCH_RISK`/`CURRENT_RISK`).
   - Flags `--risk-code-health` / `--risk-goal-achievement` (replace `--risk`,
     parse arm ~242); validation `high|medium|low` each, only when non-empty so
     `""` clears (~1461); parse from existing frontmatter (~400).
   - `interactive_update_risk_code_health()` + `interactive_update_risk_goal_achievement()`
     (replace `interactive_update_risk` ~1036); two rows in
     `interactive_select_field` (replace the single "risk" row / 7th param) +
     two field handlers + two summary lines.
   - `write_task_file`: replace the single `risk` positional (`${25}`, emit ~514)
     with two positional params, each emitted conditionally right after
     `priority:`. Wire through all three call sites (batch/interactive/child-
     completion) and the child-completion save/restore block (~897/941).
   - Keep `--risk-mitigation-tasks` and its `${26}` positional unchanged
     (renumber positionals as needed for the added param).
3. **`aitask_ls.sh`** — replace the single `risk_text` (parse ~182/234, render
   ~438) with two parsed values; render `, CH-risk: <v>, GA-risk: <v>` between
   Priority and Effort, each only when set. No `*_score` (stay out of `p_score`).
   Confirm label wording at edit time.
4. **`aitask_board.py`** — replace the single `risk` snapshot key (~2391) with
   `risk_code_health` + `risk_goal_achievement` (both `.get(...)` → None when
   unset); two ReadOnlyFields shown only when set (~2429); two `CycleField`s
   `"Code-health risk"` / `"Goal risk"` (ids `cf_risk_code_health` /
   `cf_risk_goal_achievement`) replacing `CycleField("Risk", …)` ~2442. Accept
   the index-0 unset-renders-as-"low" editor quirk (documented in t884_1); the
   data layer stays omit-by-default (snapshot None, only actively-cycled fields
   written).
5. **`aitask_fold_mark.sh`** — scalars need no fold change (mirror t884_1). Keep
   the `risk_mitigation_tasks` drop-on-fold logic untouched.
6. **Tests:**
   - `test_update_risk.sh` — rework for two flags: (a) `--risk-code-health high`
     writes `risk_code_health: high`; (b) `--risk-goal-achievement medium` writes
     its line; (c) both at once; (d) invalid value exits non-zero; (e) updating an
     unrelated field on a task with no risk leaves **no** risk lines
     (omit-by-default); (f) `--risk-code-health ""` clears; (g) guard: created
     task carries neither field; (h) `--risk-mitigation-tasks` still works +
     round-trips.
   - `test_fold_risk_mitigation_drop.sh` — primary with both risk fields set +
     folded task carrying `risk_mitigation_tasks` → after fold, primary keeps
     **both** risk fields and has no `risk_mitigation_tasks` line.
   - Board rendering stays under the t884_8 manual-verification sibling (no
     automated board test here) — state explicitly.

## Verification

- `aitask_update.sh --batch <id> --risk-code-health medium --risk-goal-achievement high`
  writes both lines; interactive mode offers both; `""` clears each.
- Freshly created task has **neither** field.
- `bash tests/test_update_risk.sh && bash tests/test_fold_risk_mitigation_drop.sh`
  PASS.
- `shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_ls.sh
  .aitask-scripts/aitask_fold_mark.sh tests/test_update_risk.sh
  tests/test_fold_risk_mitigation_drop.sh` clean; run existing update/fold suites.
- `ait board` renders both fields; unset renders without error. *(TUI covered by
  t884_8.)*

## Notes for sibling tasks

- t884_3 Step 7 writes both via `--risk-code-health <ch> --risk-goal-achievement <ga>`.
- t884_4 read-modify-writes `risk_mitigation_tasks` (single list, replace-all).
- t884_5 reads `risk_mitigation_tasks` (unchanged).
- t884_6 (docs) + t884_8 (manual verification) describe TWO risk fields.

See Step 9 (Post-Implementation) in the shared workflow for cleanup/archival/merge.
