---
priority: medium
effort: medium
depends: [t2299_2]
issue_type: feature
status: Ready
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
anchor: 2299
created_at: 2026-11-15 12:54
updated_at: 2026-11-15 12:54
---

## Context

This is the third of four children of t2299. Two siblings come first:

- **t2299_1** added the `recover:t<N>` ref, the `incarnation` origin key, the atomic `recovery-apply` verb, and the format-3 store.
- **t2299_2** added `lib/sitrep_crash.py`, with `recovery_verdict`, the strict input readers and `format_outcome` / `parse_outcome`. It also added the `aitask_sitrep_harvest.sh crashed` verb.

This child does three things:

- makes **refresh** re-check recovery items deterministically;
- runs the detector from the **monitor maintenance tick** and from the **sitrep TUI**;
- routes the TUI's **pick** on a recovery item to the real reclaim flow.

Read both siblings' archived plans and the parent plan in `aiplans/p2299/` first.

Advisory only. Nothing here reclaims, unlocks or edits task status.

## Key files to modify

### `.aitask-scripts/lib/sitrep_refresh.py`

- **Target selection.** In `select_targets` (:218-235), give `kind=task` items with a `recover:` ref `check="recovery"`. t2299_1 left them excluded.
- **Checker dispatch.** `Checker.check` (:679) currently falls through to the trail check, so make the dispatch explicit.
- **Reading inputs.** The worker (`cmd_worker` :775) reads the lock source and the task facts once per run, through `sitrep_crash`'s strict adapter, and never fetches. Each recovery target's verdict comes from `sitrep_crash.recovery_verdict`.
- **Mapping the verdict onto refresh's `Verdict(state, outcome)`:**
  - The open rows (5–8) map to `open` plus the outcome.
  - Rows 3 and 9 map to `done`.
  - Rows 1, 2 and 4 map to `unknown`. Never map them to `done`.
  - A thrown exception maps to `unknown "check error: …"`.
- **Writing.** Writes go through the existing `set-state --batch` (`run_writer` :976). Each line is `c<N>|<rev>|<state>|<ts>|<outcome>`. The batch already `KEEP`s dismissed items.
- **What refresh never does.**
  - It never reopens a done item: reopening needs the incarnation, and the incarnation lives in `recovery-apply`, which belongs to the detector.
  - It never changes title, group or context.
  - The worker protocol and the `REFRESH_*` output grammar are unchanged; only the new `kind` / `check` value appears.

### `.aitask-scripts/monitor/monitor_shared.py`

- Add `_maybe_detect_sitrep_crashes`, modelled on `_maybe_refresh_sitrep` (:1828):
  - one run per store root, using `_sitrep_store_roots` (:1867);
  - each run is `aitask_sitrep_harvest.sh crashed --root <r>`;
  - each run goes through `run_owned_group` (`monitor/sitrep_close.py:100`), because the detector holds the harvest mutex;
  - use a new `_SITREP_CRASH_TIMEOUT`;
  - use the same inflight / due-at fields: class-level defaults (:679-682), initialised in `_init_agent_marks` (:771-780) with `_MARKS_PURGE_INTERVAL` / `_MARKS_PURGE_STARTUP_GRACE`.
  - Swallow failures.
- Call it in `_dispatch_refresh_maintenance` (:734-739), **between** `_maybe_harvest_sitrep` and `_maybe_refresh_sitrep`, so a single pass refreshes what it detected.

### `.aitask-scripts/sitrep_tui/sitrep_tui_actions.py`

- In `_harvest_refresh` (:721), the order becomes: `harvest all` → `crashed --root <root>` → refresh. The refresh always runs, even after a failed detector run.
- Add `summarize_crashed` (next to `summarize_harvest_all` :122) for the `CRASH_ITEM` / `CRASH_SKIP` / `CRASH_WARN` / `CRASHED` / `CRASH_NONE` / `CRASH_FAILED` lines, and include its result in the ResultDialog / notify text.

### `.aitask-scripts/sitrep_tui/sitrep_tui_model.py`

- **`classify` (:297-322).** Return a new key `recover` for an open `kind=task` item whose ref is `recover:`. This check comes before the `pick` / `pick_xref` / `pick_noref` checks.
- **`NEXT_STEPS` (:222-276).** Add a "What to do" / "How" pair for `recover`, built from the category that `sitrep_crash.parse_outcome(item.outcome)` returns (display only):
  - **crashed:** "Resume: {k_pick} launches /aitask-pick <N> (reclaim → crash recovery survey). Do not git restore/stash the tree."
  - **orphan:** "Resume or clean up: {k_pick} launches /aitask-pick <N>."
  - **stale_lock:** "Check the holder, then release the lock yourself: `ait lock --unlock <N>`." The text is shown and never run, as push is.
  - **unparseable outcome:** a generic text.
- **`task_ref_id` (:1133-1141).** Also return the id for a `recover:` ref (via `sitrep_todo.parse_recover_ref`).
- Keep `{k_*}` placeholders resolved to the effective keys.

### `_item_action_ok` (actions :623-625) and `action_pick_task` (:1031-1070)

- Admit `classify in ("pick", "recover")`. Both re-check at the dialog callback.
- Reuse `focus_existing_agent_window` and `build_pick_screen(root, task_id, narrow=True)` unchanged, so pick launches `/aitask-pick <N>`.
- `open_in_board` works through `task_ref_id`.

## Reference patterns

- The trail / push check classes in refresh (`trail_verdict`, `reminder_verdict` are pure, injected functions).
- The push item's "show the command, never run it" handling in the TUI (the `P` key).
- `tests/test_monitor_sitrep_refresh.py` `_Host(AgentMarksMixin)` (:39), and the `DispatchTests` source-order check.

## Verification

- **`tests/test_sitrep_refresh.py`**
  - `select_targets` routes `recover:` items to `recovery`.
  - A table test maps every decision row to the batch line's state.
  - Unreadable inputs give `unknown` and never `done`.
  - A dismissed item is not written (`KEPT`).
- **`tests/test_sitrep_refresh.sh`**, end to end against a scratch lock ref:
  - a lock release retires the item to `done` (row 9);
  - a live reclaim gives `done` (row 3);
  - an archived task with a lock and a Done task with a lock stay open `stale_lock` across repeated refresh passes, alternated with `harvest crashed` passes, and the outcome is byte-stable;
  - released → `done`, and further passes leave it unchanged;
  - an unreadable lock blob gives `unknown`, and the title and context are untouched.
- **`tests/test_monitor_sitrep_refresh.py`**
  - The dispatch order is harvest → detect → refresh.
  - One detect run per store root, and none for a root with no store.
  - The run is not due before the grace period, and runs do not stack.
  - A raising root does not stop the other roots.
- **`tests/test_sitrep_tui_actions.py`**
  - `p` on a crashed or orphan recovery item opens the pick dialog for `/aitask-pick <N>`, with the item re-resolved first.
  - The stale-lock How text names the unlock command, and nothing runs it.
  - The `r` order is harvest → crashed → refresh, and refresh runs even after a failed detector run.
- **`tests/test_sitrep_tui_app.py`**: the What-to-do / How text for each category.
- Run the whole sitrep Python and shell suites (listed in `aidocs/framework/sitrep.md` "Tests").
- **Live check** after the tests pass: open `ait sitrep tui` in this repo, press `r`, and confirm the recovery items appear. This is also offered as a manual-verification sibling.

Never `git restore` / `git stash` / checkout: the shared tree holds other tasks' uncommitted work. Commit only this task's paths.
