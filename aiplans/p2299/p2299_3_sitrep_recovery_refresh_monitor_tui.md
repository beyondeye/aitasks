---
Task: t2299_3_sitrep_recovery_refresh_monitor_tui.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_1_*.md, aitasks/t2299/t2299_2_*.md, aitasks/t2299/t2299_4_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
---

# Plan: refresh, monitor tick and TUI routing for recovery items (t2299_3)

## Context

t2299_1 and t2299_2 store recovery items and maintain them from the
`harvest crashed` detector. This child does three things:
- refresh keeps their live state current through the shared `recovery_verdict`;
- the monitor and the TUI run the detector at the right point;
- `p` on a recovery item opens `/aitask-pick <N>`.

The task file holds the line-level facts. Read both siblings' archived plans
first, since the names of the shared functions come from there.

## Steps

1. **Refresh target** (`lib/sitrep_refresh.py`).
   - Replace t2299_1's exclusion with `Target(check="recovery")`.
   - Add an explicit `"recovery"` branch to `Checker.check`, and make the trail branch explicit too.
   - In the worker, build `RecoveryInputs` once per run, lazily on the first recovery target. It holds `sitrep_crash.read_locks(root)` and `read_tasks(root, ids)`.
   - If building `RecoveryInputs` raises `SourceError`, every recovery target gets `unknown "<source> unavailable"`.
   - `check_recovery(target)` calls `recovery_verdict` and maps it:
     - rows 5-8 → `open`;
     - rows 3 and 9 → `done`;
     - rows 1, 2 and 4 → `unknown`.
   - Its outcome comes from `format_outcome`.
   - Refresh never reopens: a target that is already `done` is never selected, because only `open` and `unknown` items are selected (`select_targets` :218).
2. **Monitor** (`monitor/monitor_shared.py`).
   - Constants: `_SITREP_CRASH_SH` and `_SITREP_CRASH_TIMEOUT` (e.g. 120).
   - Class defaults: `_sitrep_crash_inflight`, `_sitrep_crash_due_at`.
   - Initialise them in `_init_agent_marks`.
   - Add `_maybe_detect_sitrep_crashes`. For each root in `_sitrep_store_roots(...)`, call `run_owned_group([HARVEST_SH, "crashed", "--root", root], timeout=…)`. A failure is swallowed per root, and the next root still runs.
   - Insert the call into `_dispatch_refresh_maintenance` between the harvest and the refresh.
3. **TUI actions** (`sitrep_tui/sitrep_tui_actions.py`).
   - `_harvest_refresh` runs harvest all, then crashed (with `model.CRASH_TIMEOUT`), then refresh. Refresh runs even after either earlier step fails.
   - Add `summarize_crashed(lines) -> str`, e.g. "recovery: 15 crashed, 2 orphans, 1 stale lock (3 new, 1 reopened)" or "recovery check failed: <reason>".
   - Show its result in the ResultDialog and the notify.
4. **TUI model** (`sitrep_tui/sitrep_tui_model.py`).
   - `classify`: an open `kind=task` item with `st.parse_recover_ref(ref)` returns `"recover"`. Place this check before the pick checks.
   - `NEXT_STEPS["recover"]`: a template that `next_step` formats with the category from `sitrep_crash.parse_outcome` and the task id. Keep the per-category texts in a dict, and use the fallback text when the outcome is unparseable.
   - `task_ref_id`: also accept recover refs.
   - Check that the lib import (`sitrep_crash`) is allowed from `sitrep_tui/`. The TUI already imports `sitrep_todo`, `sitrep_refresh` and `sitrep_cli`.
5. **Pick gate.** `_item_action_ok("pick_task")` and the dialog callback re-check accept `classify in ("pick", "recover")`.
   - For stale locks the How text shows `ait lock --unlock <N>`. Nothing runs it.
   - Do not wire the stale-lock text to the push `P` command action unless that action is generic. If it is not, plain text in How is enough.
6. **Tests:** see the task's Verification section. In `test_sitrep_refresh.sh`, reuse t2299_2's lock-fixture helpers. If they live inside the shell test, copy the minimal helper or source a shared fixture file.

## Verification

- `python3 -m pytest tests/test_sitrep_refresh.py tests/test_monitor_sitrep_refresh.py tests/test_sitrep_tui_actions.py tests/test_sitrep_tui_app.py tests/test_monitor_sitrep_harvest_close.py -q`
- `bash tests/test_sitrep_refresh.sh`
- `bash tests/test_sitrep_crash.sh`
- The whole sitrep suite from `aidocs/framework/sitrep.md` "Tests".
- Manual: run `ait sitrep tui` in this repo and press `r`. Recovery items appear, and `p` on one opens the pick dialog. Cancel the dialog; do not launch.

## Risk

### Code-health risk: medium
- **Monitor tick cost.** A third subprocess per pass, per root, holding the harvest mutex, can delay `h` harvests. · severity: medium · → mitigation: same interval as harvest; owned-group timeout; one run per root
- **TUI `r` latency.** Grows by one detector run. · severity: low · → mitigation: TBD
- **Test fragility.** Refresh's dispatch order test reads source with `inspect.getsource`, which is brittle under refactors. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- **Pick launch path.** A pick on a recovery item launches `/aitask-pick <N>`. That command's Step 4 handles `RECLAIM_CRASH` / `RECLAIM_STATUS`, so the reclaim flow comes for free. · severity: low · → mitigation: TBD

## Step 9

Post-implementation: commit this task's paths only (`feature: … (t2299_3)`), then archive via Step 9.
