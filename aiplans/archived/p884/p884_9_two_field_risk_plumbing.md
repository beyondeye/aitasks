---
Task: t884_9_two_field_risk_plumbing.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_9_two_field_risk_plumbing
Branch: aitask/t884_9_two_field_risk_plumbing
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 16:59
---

# Plan: t884_9 — Two-field risk frontmatter plumbing (replaces aggregate `risk`)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Doubles the single-field plumbing landed by t884_1 (archived plan:
> `aiplans/archived/p884/p884_1_risk_frontmatter_field_plumbing.md`).

## Context

The original t884_1 (archived) shipped a **single aggregate** `risk` frontmatter
field. Per user redirect, risk is now estimated and stored as **two independent
fields**:

- `risk_code_health` — `high|medium|low`; stability / quality / maintainability /
  blast-radius risk of the planned change.
- `risk_goal_achievement` — `high|medium|low`; whether the planned implementation
  will actually deliver the user's requested goals.

This task **replaces** the single `risk` field with the two fields **everywhere**
the single field was wired (no aggregate kept), mirroring t884_1's plumbing but
doubled. Both fields are scalar, **omitted by default** (planning output, not a
creation input), **display-only** (no sort score, no border color).
`risk_mitigation_tasks` stays a single shared list (unchanged). Pure
refactor/extension — **zero behavior change when both fields are absent**.
It unblocks t884_3 (which `depends` on it).

## Verify-pass findings (2026-06-01)

Anchors confirmed against the current tree; the single-`risk` surface from t884_1
is present and exactly as the plan assumes. Scope is closed — a repo-wide scan
found no other code path reading/writing the single `risk` field
(`aitask_projects.sh` "at your own risk" is an idiom; `profile_editor.py`
`risk_evaluation` is the *profile key* from t884_2, not the frontmatter field;
`aitask_create.sh` has no risk plumbing; nothing under `board/lib/` or `seed/`
references it). Confirmed line anchors are inlined in the Steps below.

## Steps

1. **`aitask_create.sh` — no change.** Neither field is a creation-time input
   (both written post-create by t884_3's evaluation step). Mirror t884_1: do not
   add flags/prompts/validation/serialization. (Verified: create.sh has zero
   `risk` references today.) The `test_update_risk.sh` guard re-asserts created
   tasks carry neither field.

2. **`aitask_update.sh`** — replace the single `--risk` surface with two:
   - **Vars (~23-26, ~78-79, ~337-339):** add `BATCH_RISK_CODE_HEALTH`/`_SET`,
     `BATCH_RISK_GOAL_ACHIEVEMENT`/`_SET`; `CURRENT_RISK_CODE_HEALTH`,
     `CURRENT_RISK_GOAL_ACHIEVEMENT` (replace `BATCH_RISK`/`BATCH_RISK_SET`/
     `CURRENT_RISK`). Keep both `RISK_MITIGATION_TASKS` vars unchanged. Reset both
     new CURRENT_* to `""` (no default) in `parse_yaml_frontmatter` (~337).
   - **Help text (~121):** replace the `--risk LEVEL` block with
     `--risk-code-health LEVEL` and `--risk-goal-achievement LEVEL` blocks; keep
     `--risk-mitigation-tasks` text as-is.
   - **Flag parse (~242):** replace the `--risk)` arm with `--risk-code-health)`
     and `--risk-goal-achievement)` arms (each sets value + `_SET=true`). Keep
     `--risk-mitigation-tasks)` (~243).
   - **Frontmatter parse (~400):** replace `risk) CURRENT_RISK=...` with
     `risk_code_health)` and `risk_goal_achievement)` arms. Keep
     `risk_mitigation_tasks)` (~401).
   - **`write_task_file` (~498, ~514):** replace positional `risk="${25}"` with
     `risk_code_health="${25}"` + `risk_goal_achievement="${26}"`; shift
     `risk_mitigation_tasks` to `"${27}"`. Replace the single conditional `risk:`
     emit (~514) with two conditional emits, **each right after `priority:`**
     (~513), order code-health then goal-achievement. Keep the
     `risk_mitigation_tasks` conditional emit (~542).
   - **All three call sites** pass the new trio (code_health, goal_achievement,
     mitigation) as the last positional args — update each:
     - child-completion write (~924-931, passes `$CURRENT_*`),
     - interactive write (~1399-1406, passes `$new_risk` + `$CURRENT_RISK_MITIGATION_TASKS`),
     - batch write (~1718-1724, passes `$new_risk` + `$new_risk_mitigation_tasks`).
   - **Child-completion save/restore block (~896-898, ~941-942):** replace
     `saved_risk`/`CURRENT_RISK` with two saved vars + two CURRENT_* restores.
   - **Interactive (~1009, ~1036-1039, ~1279, ~1293, ~1312-1320, ~1418):**
     replace `interactive_update_risk()` with two functions
     (`interactive_update_risk_code_health` / `..._goal_achievement`); replace
     the single `risk` row in `interactive_select_field` (7th param `$7`) with two
     rows (params `$7`/`$8`) + update the caller (~1293) to pass both new vars;
     replace the single `risk)` field handler (~1312) with two handlers; replace
     the single `new_risk` local (~1279) with two; replace the `Risk:` summary
     line (~1418) with two summary lines.
   - **`has_update` (~1487):** replace the single `BATCH_RISK_SET` check with two.
   - **Validation (~1531-1537):** replace the single `risk` validation with two
     `high|medium|low` blocks, each validated only when `_SET` and non-empty
     (so `""` clears). Keep the `--risk-mitigation-tasks` block.
   - **`new_*` computation (~1571-1576):** replace the single `new_risk` (use
     BATCH only when `_SET`, else current) with two analogous blocks.
   - Keep `--risk-mitigation-tasks` and its logic entirely unchanged (only its
     positional index shifts 26→27).

3. **`aitask_ls.sh`** — replace the single `risk_text` (init ~183, parse ~234,
   reset ~343, render ~438) with two values `risk_code_health_text` /
   `risk_goal_achievement_text`. Parse arms `risk_code_health)` /
   `risk_goal_achievement)` mapping high/medium/low → High/Medium/Low. Render
   `, CH-risk: <v>, GA-risk: <v>` between Priority and Effort, **each only when
   set**. No `*_score` — stay out of `p_score` (display-only).

4. **`aitask_board.py`** — replace the single `risk` snapshot key (~2391) with
   `risk_code_health` + `risk_goal_achievement` (both `.get(...)` → None when
   unset). Two ReadOnlyFields shown only when set (~2429-2430). Two `CycleField`s
   `"Code-health risk"` / `"Goal risk"` (ids `cf_risk_code_health` /
   `cf_risk_goal_achievement`, field_keys `risk_code_health` /
   `risk_goal_achievement`) replacing `CycleField("Risk", …)` (~2442-2444).
   `save_changes` (~2607) is generic over `_current_values` keys — two new keys
   flow through with no further change. Accept the index-0 unset-renders-as-"low"
   editor quirk (documented in t884_1); data layer stays omit-by-default
   (snapshot None, only actively-cycled fields written). `BOARD_KEYS` is
   `("boardcol","boardidx")` only — no change.

5. **`aitask_fold_mark.sh`** — scalars need no fold change (mirror t884_1). The
   `--risk-mitigation-tasks ""` clear on the folded task (~241) and the
   "not unioned" comment (~223-225) stay untouched.

6. **Tests:**
   - **`test_update_risk.sh`** — rework header/comments for two flags; cases:
     (a) `--risk-code-health high` writes `risk_code_health: high`;
     (b) `--risk-goal-achievement medium` writes its line;
     (c) both at once writes both;
     (d) invalid value (each flag) exits non-zero;
     (e) unrelated update on a risk-less task leaves **no** `risk_code_health:`
     and **no** `risk_goal_achievement:` lines (omit-by-default);
     (f) `--risk-code-health ""` clears only that field;
     (g) **guard:** created task carries **neither** new field
     (`assert_no_field … risk_code_health` + `… risk_goal_achievement`);
     (h) `--risk-mitigation-tasks` still works + round-trips.
     Helpers (`assert_no_field`/`read_frontmatter_field`) use anchored `^field:`
     regex — reuse as-is (no collision: `^risk_code_health:` ≠ `^risk_goal_achievement:`).
   - **`test_fold_risk_mitigation_drop.sh`** — primary seeded with **both** risk
     fields (`risk_code_health: medium`, `risk_goal_achievement: high`) + folded
     task carrying `risk_mitigation_tasks` → after fold, primary keeps **both**
     risk fields and has no `risk_mitigation_tasks` line; folded task's list
     cleared; folded task status=Folded. Update header/comment ("keeps primary's
     risk" → "both risk fields").
   - Board rendering stays under the t884_8 manual-verification sibling (no
     automated board test here) — stated explicitly.

## Verification

- `aitask_update.sh --batch <id> --risk-code-health medium --risk-goal-achievement high`
  writes both lines; only one flag writes only that line; interactive mode offers
  both; `--risk-code-health ""` clears just that field.
- Freshly created task has **neither** field.
- `bash tests/test_update_risk.sh && bash tests/test_fold_risk_mitigation_drop.sh`
  PASS.
- `shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_ls.sh
  .aitask-scripts/aitask_fold_mark.sh tests/test_update_risk.sh
  tests/test_fold_risk_mitigation_drop.sh` clean; run existing update/fold suites.
- `ait board` renders both fields (read-only for Done/Folded, CycleField
  otherwise); unset renders without error. *(TUI covered by t884_8.)*

## Notes for sibling tasks

- t884_3 Step 7 writes both via `--risk-code-health <ch> --risk-goal-achievement <ga>`.
- t884_4 read-modify-writes `risk_mitigation_tasks` (single list, replace-all).
- t884_5 reads `risk_mitigation_tasks` (unchanged).
- t884_6 (docs) + t884_8 (manual verification) describe TWO risk fields.

See Step 9 (Post-Implementation) in the shared workflow for cleanup/archival/merge.

## Final Implementation Notes

- **Actual work done:** Implemented the plan exactly across the 4 scripts + 2
  tests.
  - `aitask_update.sh`: replaced `BATCH_RISK`/`BATCH_RISK_SET`/`CURRENT_RISK`
    with `BATCH_RISK_CODE_HEALTH`/`_SET`, `BATCH_RISK_GOAL_ACHIEVEMENT`/`_SET`,
    `CURRENT_RISK_CODE_HEALTH`, `CURRENT_RISK_GOAL_ACHIEVEMENT`. New flags
    `--risk-code-health` / `--risk-goal-achievement` (each validated only when
    `_SET` and non-empty, so `""` clears). `write_task_file` gained two
    positionals (`${25}` code-health, `${26}` goal-achievement) emitted
    conditionally right after `priority:`; `risk_mitigation_tasks` shifted to
    `${27}`. Wired through all three call sites (child-completion ~948,
    interactive ~1441, batch ~1771) + the child-completion save/restore block.
    Interactive: two `interactive_update_risk_*` functions, two rows in
    `interactive_select_field` (params `$7`/`$8`, fzf height 17→18), two field
    handlers, two summary lines (`CH-risk:` / `GA-risk:`). `--risk-mitigation-tasks`
    left entirely unchanged (only its positional index moved).
  - `aitask_ls.sh`: two display values (`risk_code_health_text` /
    `risk_goal_achievement_text`), rendered `, CH-risk: <v>, GA-risk: <v>`
    between Priority and Effort, each only when set; no `*_score`.
  - `aitask_board.py`: two snapshot keys (`.get(...)` → None when unset), two
    ReadOnlyFields (shown only when set), two CycleFields `"Code-health risk"` /
    `"Goal risk"` (ids `cf_risk_code_health` / `cf_risk_goal_achievement`).
    Generic `save_changes` round-trips both new keys with no further change.
  - `aitask_fold_mark.sh`: confirmed no change needed (scalars don't fold; the
    `risk_mitigation_tasks` drop-on-fold is unchanged).
  - Tests reworked: `test_update_risk.sh` (21/21) and
    `test_fold_risk_mitigation_drop.sh` (5/5).
- **Deviations from plan:** None of substance. Bumped the interactive
  `fzf --height` 17→18 to fit the extra risk row (the only detail beyond the
  written plan).
- **Issues encountered:** None. Confirmed the test helpers' anchored `^field:`
  regex does not collide across `risk_code_health` / `risk_goal_achievement` /
  `risk_mitigation_tasks`, so they were reused unchanged.
- **Key decisions:** Display labels `CH-risk` / `GA-risk` (ls), `Code-health
  risk` / `Goal risk` (board). Code-health emitted before goal-achievement,
  both right after `priority:`.
- **Verification:** Both reworked suites pass; shellcheck shows zero new
  warnings vs the committed baseline (identical SC-code counts); 10 existing
  update/fold suites pass; a live `aitask_ls.sh` smoke test in a scratch dir
  confirmed both/one/neither-field rendering. Board TUI rendering deferred to
  the t884_8 manual-verification sibling (no automated board test added).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - t884_3 (writes both): `aitask_update.sh --batch <id> --risk-code-health <ch>
    --risk-goal-achievement <ga>`. Omit a flag (or pass `""`) to leave/clear it.
    Each accepts only `high|medium|low`.
  - t884_4 (`risk_mitigation_tasks`): unchanged single list, replace-all;
    read-modify-write via `--risk-mitigation-tasks "a,b,c"`.
  - Board: an unset risk renders as "low" in either CycleField editor (index-0
    fallback) but is NOT persisted unless the user actively cycles it — accepted
    display-only quirk (no "unset" sentinel), same as t884_1.
  - `aitask_create.sh` remains untouched; `test_update_risk.sh` guards that
    created tasks carry neither field.
