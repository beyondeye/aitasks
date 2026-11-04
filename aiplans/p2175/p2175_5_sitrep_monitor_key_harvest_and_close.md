---
Task: t2175_5_sitrep_monitor_key_harvest_and_close.md
Parent Task: aitasks/t2175_sitrep_a_per_repo_persisted_todo_list_with_pointer_based_context.md
Sibling Tasks: aitasks/t2175/t2175_6_sitrep_harvest_fallback_and_failure_corpus.md
Archived Sibling Plans: aiplans/archived/p2175/p2175_*_*.md
Base branch: main
Output branch: main
---

# t2175_5 — Monitor key: harvest-and-close (+ sitrep key, indicator, maintenance harvest)

## Context

Sitrep (t2175) exists so a finished/frozen agent window can be closed without
losing its follow-up info. Harvest (t2175_2), refresh (t2175_3) and the sitrep
skill/window (t2175_4) are landed. What is missing is the TUI surface: a key
that harvests the selected agent, shows what was captured, and only then offers
to close it — refusing when capture or harvest failed. Plus: open/focus the
sitrep window from the monitor, minimonitor and TUI switcher; a cheap "open
Pick-now items" indicator; and the maintenance `harvest all` job the t2175_2/3
notes asked for (so kept frozen records become droppable/purgeable).

User decisions (this session): live agents = **capture the pane, then kill**
(no freeze); keys **`h`** = harvest-and-close, **`S`** = sitrep (monitor,
minimonitor, switcher); the sitrep key **switches to** the window everywhere.
User restated: capture first, then confirm closing; block closing if capture or
harvest fails; skip harvesting live sitrep windows.

Facts this plan relies on (verified in code):
- `aitask_sitrep_harvest.sh` wire lines: `HARVEST_ITEM:<src>|c<N>|added|exists|<kind>|<ref>`,
  `HARVEST_WARN:<src>|<reason>`, final `HARVESTED:` / `HARVEST_NONE:<src>|<reason>` /
  `HARVEST_FAILED:<src>|<reason>`; exit 0 ok (incl. NONE), 1 failed, 2 usage.
  `record <id> --force` re-applies idempotently and prints the item lines
  (without `--force` the detached post-freeze harvest usually already wrote the
  receipt → `already_harvested`, no items). `capture --root R [--agent W]
  [--task T] [--operation op]` reads stdin, writes **no** receipt, and does
  **not** skip sitrep windows (`record`/`all` do, via `is_sitrep_window`).
- `aitask_frozen.sh drop <id>` harvests again before deleting
  (`DROP_REFUSED:<id>|harvest:<why>` on failure) and must go through
  `run-shell -b` — the existing `AgentMarksMixin._drop_frozen(snap)`
  (`monitor/monitor_shared.py` ~1355) + `_poll_frozen_outcome`/`drop_verdict`
  already do this; reused as is.
- Live kill: `MonitorApp._on_kill_confirmed(confirmed, pane_id)` and
  `MiniMonitorApp._on_own_kill_confirmed(confirmed, pane_id)` re-read
  `_kill_target_state(pane_id)` and then call `kill_agent_pane_smart`, whose
  `kill-pane`/`kill-window` is unguarded by process identity — so the live
  close keeps their state re-check and post-kill tail but uses a new guarded
  kill (step 2i). `MonitorApp._current_agent_snapshot` returns any focused
  card, including `OTHER`/`TUI` ones, which `_kill_target_state` calls `live`.
- `_run_marks_cmd` kills only its direct child on timeout and has no stdin; the
  harvest wrapper spawns Python children, so a harvest needs a group-killing
  runner (as `agent_freeze._harvest_record` does).
- `monitor/sitrep_open.py` (`ait sitrep open`) targets the session holding
  `$TMUX_PANE`; the switcher (in `lib/`) must not import `monitor/`
  (`tests/test_no_lib_to_tui_import.sh`), so all three surfaces go through the
  CLI with a new `--session`.

## Implementation steps

### 1. `monitor/sitrep_open.py` + `aitask_sitrep.sh`: `--session <name>`
- New optional `--session` (argparse, `allow_abbrev=False` already). Value must
  be non-empty, no control chars, no `:`/`.` prefix tricks — validate with a
  small `session_arg` type, then confirm existence through the gateway
  (`has-session -t =<name>`); missing → `SITREP_REFUSED:no_session`.
  Given → used instead of `pane_session($TMUX_PANE)`; the `$TMUX` requirement
  stays.
- Update both headers' usage/wire text (`ait sitrep [open] … [--session <s>]`).

### 2. `monitor/monitor_shared.py`: harvest runner, report, dialog, flow
a. **Group-killing runner seam** `async def _run_sitrep_harvest(self, args, *,
   stdin: bytes | None = None, timeout: float) -> tuple[int, str]` on
   `AgentMarksMixin`: `create_subprocess_exec(_SITREP_HARVEST_SH, *args,
   stdin=PIPE if stdin is not None else DEVNULL, stdout=PIPE, stderr=STDOUT,
   start_new_session=True)`; on timeout `os.killpg(proc.pid, SIGKILL)` then
   reap; total by contract like `_run_marks_cmd` (`ERROR:` strings, never
   raises) — **except cancellation**: an `asyncio.CancelledError` branch
   (separate from the timeout, the `monitor/desync_summary.py` `_fetch_async`
   shape) kills and reaps the owned process group, then re-raises. Textual
   cancels workers at app exit and `wait_for` does not touch the child, so
   without it a `start_new_session` group would outlive the TUI with no
   supervisor. One `_terminate_group(proc)` helper serves both exits
   (`killpg(proc.pid, SIGKILL)` only while `proc.returncode is None`, then
   `wait()`, `ProcessLookupError` suppressed). Constants: `_SITREP_HARVEST_SH`, `_HARVEST_ONE_TIMEOUT = 150.0`
   (above lock wait 20 s + writer 60 s + 20 s git/projects calls; the drop's own
   harvest budget is 120 s), `_HARVEST_ALL_TIMEOUT = 300.0`,
   `_HARVEST_CAPTURE_LINES = 50000` (freeze's default depth, comment cites
   `agent_freeze`).
b. **Pure parser** `parse_harvest_output(rc, out) -> HarvestReport`
   (frozen dataclass: `items: tuple[(cid, status, kind, ref)]`, `warns`,
   `final_kind` ∈ `HARVESTED|HARVEST_NONE|HARVEST_FAILED|missing`, `reason`,
   `rc`; property `ok` = `rc == 0 and final_kind in {HARVESTED, HARVEST_NONE}`).
   Only the LAST final line counts; a missing final line, `rc != 0`, or an
   `ERROR:` runner result → not ok (`reason` names it). Constructors for the
   two non-harvest outcomes: `HarvestReport.skipped("sitrep_agent")` (ok, no
   harvest run) and `HarvestReport.failed(reason)` (capture failure).
c. **Item titles (best effort)**: `_harvest_item_titles(root, cids) -> dict`
   run via `asyncio.to_thread`: `sitrep_harvest.canonical_root(root)` →
   `sitrep_todo.load_todo_for_read(<canon>/.aitask-sitrep)`; any exception →
   `{}` (titles are display only; the report stands without them).
d. **`HarvestResultDialog(GuardedModalScreen)`** (own `DEFAULT_CSS`, sized for
   the 40-column minimonitor like `FreezeConfirmDialog`; body in a
   `VerticalScroll`): header names the agent (window name) and its state
   (frozen / live; live and not completed → "still active — output after this
   capture is not kept"). Body built with `Content.from_markup(template,
   **vars)` so titles/refs/reasons are never parsed as markup (t2017): one line
   per item `c<N> <added|exists> <kind> <ref> — <title>`, then `warning:
   <reason>` lines, then the verdict (`Harvested: a added, e existing` /
   `Nothing to harvest (<reason>)` / `Sitrep agent — not harvested` /
   `HARVEST FAILED: <reason> — the agent is kept`). Buttons: ok →
   `Drop`/`Close agent` (destructive variant) + `Keep`; not ok → `Close` only
   (no affirmative button exists). `escape` → `False`. Dismisses with a bool.
e. **Flow on the mixin**:
   - `action_harvest_close()` (shared, both apps): snap =
     `self._current_agent_snapshot()`; none → warn. **Agent cards only**:
     `snap.pane.category != PaneCategory.AGENT` → warn "h acts on agent cards
     only", nothing captured or dispatched (the monitor's
     `_current_agent_snapshot` returns any focused card, and
     `_kill_target_state` calls an ordinary shell `live`). Bind `pane_id` NOW
     (t2065). `state = self._kill_target_state(pane_id)`; `unverified` → warn,
     stop.
     `root = self._strict_root_for_snap(snap)`; `None` → warn "project root
     unknown — not harvested", stop. In-flight guard
     `_harvest_close_inflight` → "harvest already running". Then
     `self._dispatch_harvest_close(snap, state, root)` — a single **sync seam**
     that `run_worker(..., group="sitrep-harvest", exit_on_error=False)`
     (tests stub it, per testing_conventions).
   - **Run identity** (a pane id is a container; a freeze/restore respawns a
     different process into the same id): `RunIdentity(pane_id, pane_pid,
     server_pid, frozen_record)`, read by ONE async gateway call
     `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}\t#{pid}\t#{@aitask_frozen}'`.
     The worker reads it BEFORE capture/harvest and AGAIN after; any field
     differing → `HarvestReport.failed("agent_changed_during_harvest")`. A
     frozen target additionally needs `frozen_record == snap.frozen_record_id`
     (else `failed("record_changed")`); a live target needs `frozen_record`
     empty. The identity travels with the report into the dialog callback.
   - worker `_harvest_close(snap, state, root)` (flag cleared in `finally`):
     - frozen: `record <frozen_record_id> --force`.
     - live, `is_sitrep_window(window_name)` → `HarvestReport.skipped(...)`,
       no capture, no harvest.
     - live otherwise: capture via the gateway async call
       (`self._monitor._tmux_async(["capture-pane","-p","-J","-t",pane_id,"-S",f"-{_HARVEST_CAPTURE_LINES}"])`,
       no `-e`); `rc != 0` or empty → `HarvestReport.failed("capture_failed")`,
       no harvest. Else `capture --root <root> --agent <window> [--task <id>]
       [--operation <op>]` with the text on stdin (`task_ref_from_window_name`
       → op/id; `_task_cache.get_task_id_for_pane` fallback for the id).
     - titles (2c), then `push_screen(HarvestResultDialog(...), callback=…)`.
     - notify a one-line summary too (`markup=False`).
   - callback `_on_harvest_close_confirmed(ok_pressed, report, identity,
     state)`: returns unless `ok_pressed and report.ok` (the dialog has no
     confirm for a failed report; this re-check is the guard). Then
     **revalidate the run** before closing:
     - frozen → the current snapshot for `identity.pane_id` must be frozen
       with `frozen_record_id == identity.frozen_record`; otherwise warn
       "record changed since the harvest — press h again" and stop. Only then
       `self._drop_frozen(snap)` (the drop's own leased re-harvest and receipt
       sha check cover a capture that changed inside the same record).
     - live → `self._close_live_after_harvest(identity)`.
   - `_close_live_after_harvest(identity)`: abstract on the mixin
     (`NotImplementedError`), implemented per app (steps 3/4): re-read
     `_kill_target_state(identity.pane_id)` (must be `live`), then
     `self._monitor.kill_agent_run_guarded(identity)` (step 2i) — never the
     unguarded smart kill. `killed` → the app's existing post-kill tail
     (focus reset, notify, refresh; minimonitor's collapsed-window case);
     `changed` → warn "the agent in <window> changed since the harvest — not
     closed; press h again"; `unknown` / `failed` → error, nothing claimed.
f. **Maintenance `harvest all`**: `_maybe_harvest_sitrep()` with its own
   `_sitrep_harvest_inflight` / `_sitrep_harvest_due_at` (init in
   `_init_agent_marks`, same startup grace + `_MARKS_PURGE_INTERVAL` cadence),
   running `_run_sitrep_harvest(["all"], timeout=_HARVEST_ALL_TIMEOUT)`; all
   errors swallowed; placed in `_maintenance()` **before**
   `_maybe_refresh_sitrep()` (replacing the reserved comment). Global `all`
   (no `--root`): kept records of every repo are released, each into its own
   store, as `all` is specified.
g. **Indicator helper** `SitrepNowCounter.count(root) -> int | None`: reads
   `<canonical root>/.aitask-sitrep/todo.md` bytes; cache keyed on the sha256
   of those bytes (content, not stat) → reparse with `sitrep_todo.parse_todo`
   only on change; counts items `group == "now" and state == "open"`; no store
   / unreadable / FormatError → `None`. Canonical root resolved once per root
   and memoized (git subprocess). Called from `_refresh_data` off the loop
   (`asyncio.to_thread`), same pattern as the pre-fetched desync value.
h. **Sitrep open** `action_open_sitrep()`: root/session from the selected
   snapshot (`_strict_root_for_snap`, `snap.pane.session_name`), else the app's
   own project root and session; dispatch seam `_dispatch_sitrep_open(root,
   session)` → worker running `aitask_sitrep.sh open --root R --session S` via
   `_run_marks_cmd(..., script=_SITREP_SH, timeout=45.0)`; map the first wire
   line: `SITREP_SPAWNED`/`SITREP_FOCUSED` → info, `SITREP_WARN` appended,
   `SITREP_FOCUS_FAILED` → warning, `SITREP_REFUSED:<r>` / `ERROR:` → error.

i. **Guarded run kill** in `monitor/monitor_core.py`:
   `TmuxMonitor.kill_agent_run_guarded(identity) -> (status, killed_window)`,
   status ∈ `killed | changed | failed | unknown`. It shares the
   pane-vs-window decision with `_kill_agent_pane` (extract the
   `count_other_real_agents` decision into `_collapse_window_for(pane_id)`;
   `k`'s path keeps its behaviour), then dispatches the chosen
   `kill-pane -t <p>` / `kill-window -t <p>` as ONE
   `if-shell -F -t <p> <cond> '<kill>'` with `cond` = `@aitask_frozen` empty ∧
   `#{pane_pid} == identity.pane_pid` ∧ `#{pid} == identity.server_pid`
   (nested binary `&&`, built by a condition builder extracted from
   `helper_panes._guard_condition` so both share one grammar), then reads back
   `display-message -p -t <p> '#{pane_id}\t#{pid}'`: pane absent on the same
   server → `killed` (then the bound-helper sweep, as the smart kill does);
   present → `changed`; an unreachable/failed read → `unknown` (never "gone").

### 3. `monitor/monitor_app.py`
- `BINDINGS`: `Binding("h", "harvest_close", "Harvest")`,
  `Binding("S", "open_sitrep", "Sitrep")` (show=True; footer rule). Pane-list
  zone only through the existing `check_action`.
- `_close_live_after_harvest(identity)` per 2e (its post-kill tail mirrors
  `_on_kill_confirmed`'s success branch).
- Session bar: pass the counter's value for the monitor's own project root
  into `_rebuild_session_bar`; render `sitrep N now` only when N > 0.

### 4. `monitor/minimonitor_app.py`
- `BINDINGS`: `h` → `harvest_close`, `S` → `open_sitrep` (show=False like all).
- `_close_live_after_harvest(identity)` per 2e (tail mirrors
  `_on_own_kill_confirmed`, incl. no toast after a collapsed window).
- `KEY_HINTS_TEXT`: fold `h:harvest` and `S:sitrep` into existing lines
  (candidates `f:freeze  Z:all  h:harvest`, `L:loop ?:keys M:multi S:sitrep`),
  then **measure** `#mini-key-hints` at (15, 30) ≤ 29 and keep TEN rows
  (existing `test_minimonitor_top_chrome_render` / own-header width test);
  reword labels if a line wraps. No minimonitor indicator (its session bar is
  hidden by default).

### 5. `lib/tui_switcher.py`
- `_QUICK_JUMP_BINDINGS += Binding("S", "shortcut_sitrep", "Sitrep", show=False)`.
- `action_shortcut_sitrep()`: stale/live-session checks as the other
  shortcuts, root = `_selected_project_root()`, session = `self._session`
  (shortcut-on-selected rule); seam `_dispatch_sitrep_open(root, session)`
  → `app.run_worker` of an asyncio subprocess `aitask_sitrep.sh open --root R
  --session S` (timeout 45 s), result notified on the app; overlay dismissed.
  Add `S` to the overlay's hint text if it lists quick keys.

### 6. Docs
- `aidocs/framework/sitrep.md`: new "The monitor surface" section (h flow:
  capture → harvest → dialog → close; sitrep skip; refusal; `S`; indicator;
  maintenance `all` before refresh; the group-killing runner). Tests table rows.
- Website: `tuis/monitor/reference.md` key table (`h`, `S`, session-bar term),
  `tuis/minimonitor/_index.md` (keys row), switcher quick-key docs (grep for
  the `x`/`f` quick-key rows), `workflows/sitrep.md` "Closing a finished agent"
  subsection. Current-state prose only. `python3 check_links.py --build`.

### 7. Tests
- **New `tests/test_monitor_sitrep_harvest_close.py`** (no real workers: a
  `_Host(AgentMarksMixin)` with `_run_sitrep_harvest`, `_tmux_async`,
  `push_screen`, `_drop_frozen`, `_close_live_after_harvest` recorded):
  - parser: each final kind; items/warns; last-final-wins; missing final →
    not ok; `rc=1` with `HARVESTED` → not ok; `ERROR:` → not ok.
  - frozen → `record <id> --force`; live → capture args + `--root/--agent/
    --task/--operation` + stdin = captured text; sitrep window (`agent-sitrep`,
    `agent-sitrep-2`) → no capture, no harvest, ok report; near miss
    `agent-sitrepx` harvested; capture rc≠0 → failed, harvest never called;
    `unverified` / no strict root → nothing run; an `OTHER` card and a `TUI`
    card with a valid root and `live` state → no capture, no harvest, no
    dispatch, no close.
  - run identity: pid differs between the pre- and post-harvest reads →
    `failed("agent_changed_during_harvest")`, no dialog confirm; frozen record
    id differs from the snapshot's → `failed("record_changed")`.
  - callback: failed report + True → no drop/close; ok frozen with the same
    record → `_drop_frozen`; ok frozen whose current snapshot names a
    DIFFERENT record (re-frozen between harvest and confirm) → no drop; ok live
    → close hook receives the BOUND identity even after focus moved.
  - guarded kill (fake `tmux_run`): the only kill dispatched is the one
    `if-shell -F` carrying the bound `pane_pid` and server pid (no bare
    `kill-pane`/`kill-window`); same-pane process replacement (read-back shows
    the pane present) → `changed`, helpers not swept; read-back failure →
    `unknown`; pane gone → `killed` + helper sweep; window-collapse route uses
    `kill-window` inside the same guard. Condition builder output equals the
    helper sweep's grammar for the shared halves.
  - runner seam (real subprocess): stdin delivered; a fake script whose
    grandchild sleeps → timeout kills the whole group (grandchild gone);
    **cancellation**: run the seam as a task, wait until the script has
    written child+grandchild pids, cancel the task → `CancelledError`
    propagates and both pids are gone (bounded poll).
  - maintenance: harvest runs before refresh in one pass; not stacked; flag
    cleared after a raise; cadence.
  - counter: same bytes → no reparse; changed bytes → recount; missing store →
    None; malformed → None.
- **Textual `run_test`** (stub the dispatch seams): `HarvestResultDialog` —
  failed has no `#btn-confirm`; ok has destructive confirm; markup chars in a
  title render literally; escape → False. MonitorApp / MiniMonitorApp: `h`
  and `S` reach `_dispatch_harvest_close` / `_dispatch_sitrep_open` with the
  focused/followed agent; no live workers at block exit.
- `tests/test_sitrep_window.py`: `--session` passes through to `spawn_sitrep`;
  unknown/empty/control-char session refused (exit 1 / 2, no spawn).
- Switcher: `S` registered under `shared.tui_switcher`; action dispatches the
  selected session + root (stubbed seam). Shortcut-scope drift guard green.

### Post-phase (risk mitigations)
1. [harvest_close_guard_mutants] In a fresh `mktemp -d` copy per mutant, apply
   one mutant per guard and confirm its named test turns RED (unmutated control
   copy GREEN), recording each in the Final Implementation Notes:
   `dialog_confirm_on_failure` (failed report renders `#btn-confirm`),
   `callback_ignores_ok`, `ok_ignores_rc`, `sitrep_skip_removed` (live
   `agent-sitrep` gets captured/harvested), `capture_failure_harvests`,
   `pane_id_from_focus` (callback re-reads `_focused_pane_id`),
   `kill_state_recheck_bypassed` (hook skips `_kill_target_state`),
   `kill_unguarded` (hook calls the unguarded `kill_agent_pane_smart`),
   `guard_drops_pid` (condition omits `pane_pid`), `identity_not_rechecked`
   (no post-harvest identity read), `frozen_record_unchecked` (callback drops
   without the record-id match), `category_guard_removed` (OTHER card
   harvested), `runner_kills_child_only` (grandchild survives the timeout),
   `cancel_leaks_group` (CancelledError branch removed), `harvest_after_refresh`
   (maintenance order swapped).

## Verification
- `python3 -m pytest tests/test_monitor_sitrep_harvest_close.py tests/test_sitrep_window.py tests/test_monitor_sitrep_refresh.py -q`
- minimonitor hint/parity/height: `tests/test_minimonitor_concern_action.py`,
  `tests/test_minimonitor_top_chrome_render.py`, `tests/test_minimonitor_own_header_session.py`
- `tests/test_shortcut_scopes.py`, `tests/test_tui_switcher*.py`,
  `bash tests/test_no_raw_tmux.sh`, `bash tests/test_no_lib_to_tui_import.sh`,
  `tests/test_monitor_markup_literal_sinks.py`, `tests/test_monitor_refresh_no_sync_tmux.py`
- `bash tests/test_sitrep_harvest.sh`, `bash tests/test_sitrep_window_live.sh`
- full suite `bash tests/run_all_python_tests.sh` (last line only);
  `shellcheck .aitask-scripts/aitask_sitrep.sh`; `cd website && python3 check_links.py --build`

## Post-implementation
Step 9 of the task workflow: commit (code + docs, path-scoped), archive
t2175_5, push via `./ait git`. Then `./ait note` t2175_6: the TUI result
dialog is where "safely preserved, awaiting review" vs "failed" must become
distinguishable (it renders `HARVEST_*` lines through `parse_harvest_output`);
live `capture` writes no receipt.

## Risk

### Code-health risk: low
- The live close reuses the apps' kill-time state re-check and post-kill tail around a new guarded kill; a stale or re-read pane id, or a skipped kill-time state re-check, kills the wrong agent or takes the unleased frozen kill path · severity: low (residual — run identity bound at keypress/harvest, `_kill_target_state` re-read before the guarded kill, both red-proven by inline post-phase harvest_close_guard_mutants) · → mitigation: inline post-phase harvest_close_guard_mutants
- New group-killing subprocess runner (`start_new_session` + `killpg`); a wrong kill target, a child-only kill, or a missing cancellation branch leaves harvest Python processes holding the store mutex past the TUI · severity: low (residual — killpg only while the child is unreaped, one helper for timeout and cancel; grandchild-survival tests on both exits red-proven) · → mitigation: inline post-phase harvest_close_guard_mutants
- New guarded kill route in `monitor_core` (`kill_agent_run_guarded`) plus extraction of the pane-vs-window decision and the if-shell condition builder shared with `helper_panes` · severity: low (residual — `k`'s smart kill keeps its behaviour via the extracted decision; existing kill/helper-sweep tests pin it; guard halves red-proven) · → mitigation: inline post-phase harvest_close_guard_mutants
- A killed harvest (timeout, cancel at app exit) can stop mid-run; the store writes are atomic and mutexed, so the cost is a retry on the next pass · severity: low · → mitigation: none (same shape as `agent_freeze._harvest_record`'s group kill)
- `harvest all` now runs from every monitor and minimonitor maintenance pass, writing into other repos' stores · severity: low · → mitigation: none (per-store mutex, receipts make the steady state a no-op, `lock_busy` swallowed; same shape as the existing refresh job)
- Wide but shallow surface: monitor_shared, both apps, switcher (shared by every TUI), sitrep_open CLI, docs; minimonitor hint band budget · severity: low · → mitigation: none (existing parity/height/drift/layering tests pin each surface)

### Goal-achievement risk: medium
- The close must be refused whenever capture or harvest failed: a dialog that still offers confirm, or an `ok` that ignores rc / a missing final line, closes an agent whose output was not saved · severity: low (residual — no confirm button on a failed report plus a callback re-check of `report.ok`, each red-proven) · → mitigation: inline post-phase harvest_close_guard_mutants
- The live path must skip sitrep windows itself (`capture` does not), or the sitrep screen is fed back into its own store · severity: low (residual — `is_sitrep_window` branch before capture, near-miss name harvested, red-proven) · → mitigation: inline post-phase harvest_close_guard_mutants
- The close must act only on the agent run that was harvested: a non-agent card (shell, TUI), or a process replaced in the same pane by a freeze/restore (or a re-frozen record) between harvest and confirm, would be closed on an earlier, unrelated report · severity: low (residual — AGENT-category guard, run identity read before and after the harvest, record-id match before drop, and a kill dispatched as one if-shell gated on pane_pid + server pid + unfrozen, then read back; each red-proven) · → mitigation: inline post-phase harvest_close_guard_mutants
- Unit tests mock both tmux and the harvest; nothing proves the real gateway capture → real `harvest capture` → real guarded kill end to end, nor the if-shell condition against a real server · severity: medium · → mitigation: harvest_close_live_smoke
- A live capture now and a later record harvest of the same text (after a freeze) can yield a second, linked triage item for a Stopped banner without a marker (different passage key) · severity: low · → mitigation: none (the designed uncertain-case outcome from t2175_2: duplicates are linked, never lost)
- 50000-line capture depth can miss early `Created:` lines in very long sessions · severity: low · → mitigation: none (same depth as freeze; banner follow-ups cover pick runs)

### Planned mitigations
- timing: post-phase | name: harvest_close_guard_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — close/kill path and runner; goal-achievement — refusal gate and sitrep skip | desc: one mutant per guard (confirm on failure, callback ignores ok, ok ignores rc, sitrep skip removed, capture failure harvests, pane id from focus, kill-state recheck bypassed, unguarded kill, guard drops pid, identity not rechecked, frozen record unchecked, category guard removed, child-only kill, cancel leaks group, harvest after refresh) must turn its named test red
- timing: after | name: harvest_close_live_smoke | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — unit tests mock tmux and harvest | desc: isolated-tmux live test (require_clean_ait_server + require_isolated_tmux, scratch repo/HOME) driving real capture, real `harvest capture` and the real guarded kill: items stored and pane killed; failing harvest keeps the pane; sitrep-named window writes nothing; a `respawn-pane -k` between harvest and confirm makes the guarded kill report `changed` and leave the new process running

## Post-Review Changes

### Change Request 1 (2026-11-04)
- **Requested by user:** verify and address two review findings: (1)
  `kill_agent_run_guarded` chose `kill-window` from the CACHED window
  (`_collapse_window_for`) but dispatched `kill-window -t <pane>`, i.e. the
  pane's CURRENT window — a pane moved into another agent's window before
  discovery refreshed would take that window (and the unharvested agent) with
  it; (2) the test probe `_gone` read an unreadable `/proc` as "gone", so on
  macOS surviving children would pass the group-kill assertions. Both verified.
- **Changes made:** (1) `TmuxMonitor._live_collapse_target(pane_id)` reads the
  pane's live `#{window_id}` and lists THAT window by id; a window kill pins
  `#{window_id}` and `#{window_panes}` (the listing's row count) in the
  `if-shell` condition (`run_identity_condition(..., extra=)`) and targets
  `kill-window -t @N`; every undecidable read is a pane-only kill. The cached
  `_collapse_window_for` now serves only `kill_agent_pane_smart`. (2) `_gone`
  falls back to `ps -o stat=` without `/proc` and treats an unknown state as
  alive.
- **Tests:** live `test_kill_agent_run_guarded.sh` case 6 (join-pane the
  harvested pane into another agent's window with the cache still naming the
  source: only the pane dies, the destination window and agent survive, both
  routes); unit: live-window pin, moved pane judged by its live window (the
  cached window never listed), five undecidable reads → pane kill; `_gone`
  without `/proc`, without `/proc` and `ps`, and an exited process. New mutants
  `collapse_from_cache` (the reported bug: live + unit RED),
  `window_pin_dropped`, `gone_unknown_is_gone` — all RED.
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`,
  `.aitask-scripts/lib/helper_panes.py`, `tests/test_kill_agent_run_guarded.sh`,
  `tests/test_monitor_sitrep_harvest_close.py`, `aidocs/framework/sitrep.md`.

### Change Request 2 (2026-11-04)
- **Requested by user:** verify and address: CR1's window pin (`#{window_id}` +
  `#{window_panes}`) still does not prove the window's OTHER occupants — one
  `swap-pane` exchanging the checked helper with an unrelated agent leaves
  every emitted condition true, so `kill-window` would destroy that agent
  unharvested. Verified: an `if-shell -F` condition is evaluated in the target
  pane's context only and cannot see other panes' identities.
- **Changes made:** `kill_agent_run_guarded` never kills a window: one guarded
  `kill-pane` (unfrozen + pane_pid + server pid), the read-back, then the
  guarded bound-helper sweep. A companion minimonitor closes itself once it is
  verifiably alone (`MiniMonitorApp._check_auto_close`), matching the "kill the
  companion only, never the window" rule. CR1's `_live_collapse_target` and the
  `run_identity_condition(extra=)` parameter were removed; the second element
  of the result is always False.
- **Tests:** live case 5 now asserts the last agent's window and companion stay;
  case 6 (moved pane) kept; new case 7: `swap-pane` of the harvested agent's
  bound helper with an unrelated agent after the identity read — the incoming
  agent survives, the harvested pane and its helper die; unit: no
  `kill-window` is ever dispatched and the window is never listed, even when
  the cache shows the pane alone with helpers. Mutant `window_kill_reintroduced`
  (a cached-collapse `kill-window` branch) RED on the live and the unit test;
  CR1's `collapse_from_cache` / `window_pin_dropped` retired with the code they
  targeted.
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`,
  `.aitask-scripts/lib/helper_panes.py`, `.aitask-scripts/monitor/minimonitor_app.py`,
  `tests/test_kill_agent_run_guarded.sh`,
  `tests/test_monitor_sitrep_harvest_close.py`, `aidocs/framework/sitrep.md`.

## Final Implementation Notes
- **Actual work done:**
  - `monitor/sitrep_close.py` (new): `run_owned_group` (own process group,
    group kill on timeout AND cancellation, cancellation re-raised),
    `HarvestReport` / `parse_harvest_output`, `item_titles`,
    `SitrepNowCounter` (sha256 content key), `HarvestResultDialog`
    (`GuardedModalScreen`, no confirm button on a failed report), and
    `SitrepCloseMixin` (`h`: agent-card guard, state/root checks, run identity
    before+after, frozen `record --force` / live gateway capture → `capture`,
    sitrep-window skip, confirm re-check, frozen record match → `_drop_frozen`,
    live `_guarded_close`; `S`: `ait sitrep open --root --session`).
  - `monitor/monitor_core.py`: `RunIdentity`, `RUN_IDENTITY_FORMAT`,
    `parse_run_identity`; `_collapse_window_for` extracted (tri-state) from
    `_kill_agent_pane`; `kill_agent_run_guarded` (one pane-only `if-shell -F`
    gated on unfrozen + pane_pid + server pid, read-back →
    killed/changed/unknown/failed, then the guarded helper sweep).
  - `lib/helper_panes.py`: `all_of` (nested `&&`), `run_identity_condition`
    (target-pane halves only),
    `READBACK_FORMAT`, `readback_state`; the helper sweep uses them.
  - `monitor/monitor_shared.py`: `_run_sitrep_harvest` seam,
    `_maybe_harvest_sitrep` (global `harvest all`) before `_maybe_refresh_sitrep`.
  - Apps: `h` / `S` bindings in both; per-app `_close_live_after_harvest`;
    monitor session-bar `sitrep N now`; minimonitor key hints.
  - `lib/tui_switcher.py`: `S` quick-jump (`shortcut_sitrep`) + async runner.
  - `monitor/sitrep_open.py` / `aitask_sitrep.sh`: `--session <name>` (validated,
    exact `has-session`); `lib/sitrep_cli.py`: shared `sitrep_open_message`.
  - Docs: `aidocs/framework/sitrep.md` (The monitor surface, tests rows);
    website monitor reference, minimonitor index, TUIs index, workflows/sitrep.
- **Deviations from plan:**
  - The flow lives in a new `monitor/sitrep_close.py` rather than growing the
    6000-line `monitor_shared.py`; the runner seam and maintenance job stay on
    `AgentMarksMixin`.
  - `sitrep_open_message` lives in `lib/sitrep_cli.py` so the switcher (lib/,
    must not import monitor/) and the monitor share one wording.
  - Minimonitor hints: `h`/`S` cost two wrapped rows at (15, 30) (measured 31 >
    29); paid back by `I:info (followed)` and `d:detect ≈strip =raw`
    (measured 29).
  - `_collapse_window_for` returns `None` when undecidable so the smart kill
    keeps its exact old behaviour (plain pane kill, no record drop) on a cache
    miss or failed listing. It is NOT shared with the guarded kill (plan step
    2i said it would be): after CR2 the guarded kill never kills a window.
  - Added `tests/test_kill_agent_run_guarded.sh` (private tmux server, both
    routes): proves the guard condition against a real server now; the spawned
    `harvest_close_live_smoke` still owns the end-to-end capture → harvest →
    close run.
  - The switcher's hint row is unchanged (`S` unadvertised there, like `i`/`f`;
    documented in the TUIs index).
- **Issues encountered:** a test fixture's backgrounded grandchild inherited
  stdout (communicate waited for its EOF) — redirected; the monitor sorts cards,
  so the key test focuses the card by pane id.
- **Mutants (harvest_close_guard_mutants):** 18 mutants after CR2, each in a fresh
  `mktemp -d` copy of `.aitask-scripts` + `tests`; unmutated control GREEN; all
  RED on their named test: dialog_confirm_on_failure, callback_ignores_ok,
  ok_ignores_rc, sitrep_skip_removed, capture_failure_harvests,
  pane_id_from_focus, kill_state_recheck_bypassed, kill_unguarded_monitor,
  kill_unguarded_minimonitor, guard_drops_pid (unit AND the live shell test),
  identity_not_rechecked, frozen_record_unchecked, category_guard_removed,
  runner_kills_child_only, cancel_leaks_group, harvest_after_refresh;
  CR1: gone_unknown_is_gone; CR2: window_kill_reintroduced (live + unit).
  (CR1's collapse_from_cache / window_pin_dropped were RED too, and retired
  in CR2 with the window-kill code they targeted.)
- **Verification:** Python suite PASSED (runner=pytest, exit=0);
  `test_monitor_sitrep_harvest_close.py` 62 passed; `test_sitrep_window.py` 42;
  bash: test_no_raw_tmux, test_sitrep_harvest, test_kill_agent_pane_smart,
  test_kill_agent_run_guarded, test_sitrep_window_live (22), test_website_doc_lists,
  test_no_lib_to_tui_import — all green; shellcheck clean (warning level);
  `check_links.py --build` SWEEP: PASSED. `test_cleanup_rule_parity.sh` not run
  (refuses inside tmux by design; `pane_is_helper` untouched).
- **Upstream defects identified:** None
- **Key decisions:** capture → show → confirm, never confirm on a failed
  report (no affirmative button + callback re-check); live close = capture the
  pane then a guarded PANE-ONLY kill (never a window: other occupants cannot be
  proved at dispatch); run identity bound at harvest, record match before a
  frozen drop; harvest in its own process group (timeout + cancel kill the
  group); `S` everywhere through `ait sitrep open --root --session`.
- **Notes for sibling tasks:**
  - t2175_6 (fallback corpus): the result dialog renders `parse_harvest_output`
    (`monitor/sitrep_close.py`); a new "preserved, awaiting review" outcome
    needs its own `final_kind` / `verdict()` wording there, distinct from
    `HARVEST_FAILED` (which blocks the close). Live `capture` writes no receipt,
    so `h` gates the close on the report alone.
  - The live smoke follow-up (`harvest_close_live_smoke`) can reuse
    `tests/test_kill_agent_run_guarded.sh`'s fixture shape for the kill half.
