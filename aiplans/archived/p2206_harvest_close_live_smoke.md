---
Task: t2206_harvest_close_live_smoke.md
Base branch: main
Output branch: main
---

# t2206 — Live isolated-tmux smoke for the monitor's `h` (harvest-and-close)

## Context

t2175_5 shipped `h` in the monitor TUIs: capture the agent's pane, harvest it
into the repo's sitrep store, show the result, and only then offer a guarded
close of *that run*. Its unit suite (`tests/test_monitor_sitrep_harvest_close.py`)
mocks both tmux and the harvest; `tests/test_kill_agent_run_guarded.sh` proves
the guarded kill alone against a real server. Nothing proves the composed path
end to end: real gateway `capture-pane` → real `aitask_sitrep_harvest.sh
capture` → real store write → `HarvestReport.ok` → confirm callback → real
`kill_agent_run_guarded`. This task (risk-mitigation "after" follow-up of
t2175_5) adds that live test. No production code changes.

Environment probed at planning time: `$TMUX` unset and no `-L ait` server, so
the test (which calls `require_clean_ait_server`) can run in this session.

## Files

- **New:** `tests/test_monitor_harvest_close_live.sh` — bash driver + one Python
  heredoc (fail-fast `fail()` → exit 1, same shape as
  `tests/test_monitor_shadow_spawn_live.sh` and `tests/test_kill_agent_run_guarded.sh`;
  no `asserts.sh` counters, so the subshell-counter rule does not apply).
- **Edit:** `aidocs/framework/sitrep.md` — one row in the `## Tests` table.
- **Edit:** `tests/test_monitor_sitrep_harvest_close.py` header docstring — name
  the new live test beside `test_kill_agent_run_guarded.sh` as the real-server half.

## Implementation steps

1. **Bash preamble** (in this order — the order is load-bearing):
   - `scratch_cwd.sh` / `enter_scratch_cwd`; skip if no `tmux`.
   - Resolve interpreters **before** HOME moves: `PYTHON_BIN` from
     `tests/lib/venv_python.sh` (`$AITASK_PYTHON`; skip if it lacks `textual`),
     and `export AIT_PYTHON="$(source …/lib/python_resolve.sh && require_ait_python)"`.
   - `REAL_HOME="$HOME"`; take the **before manifest** (step 7).
   - `require_clean_ait_server` then `require_isolated_tmux` (tests/lib/tmux_isolation.sh).
   - Scratch dirs: `SCR=$(mktemp -d "${TMPDIR:-/tmp}/ait_hcl_XXXXXX")` (pwd -P),
     `FIXTURE_DIR=$(mktemp -d /tmp/ait_hcl_tmux_XXXXXX)` (short: socket path
     length, t2142). Trap: kill the fixture server, `chmod -R u+w`, rm both.
   - Export every seam before the server starts (testing_conventions.md
     "Composed acceptance" (a)): `HOME=$SCR/home` (+ `.config/aitasks`),
     `AITASKS_AGENT_SESSIONS_FILE`, `AITASKS_FROZEN_DIR`, `AITASKS_PROJECTS_INDEX`
     (`projects:` only), `GIT_AUTHOR_*`/`GIT_COMMITTER_*`; unset `AITASK_SITREP_DIR`,
     `AITASK_SITREP_HARVEST_PAUSE_FIFO`, `AITASK_SITREP_HARVEST_LOCK_TIMEOUT`,
     `AITASK_SITREP_HARVEST_RUN_ID`, `TMUX_PANE`.
   - Scratch repos via a `new_repo <name>` helper (git init, `aitasks/metadata/project_config.yaml`,
     `aitasks/t154_hcl_followup.md`, commit): `repo_ctrl`, `repo_sub`, `repo_sitrep`,
     `repo_resp`; plus `repo_neg` whose tracked `.gitignore` is
     `!.aitask-sitrep/` + `!.aitask-sitrep/**` (the `store_not_ignorable` fixture
     from `tests/test_sitrep_harvest.sh` §9).
   - Fixture capture `$SCR/banner_<task>.txt`, written per task id, synthetic and
     in the Claude Code captured shape (`tests/fixtures/sitrep_harvest/README.md`):
     a tool call whose output line carries `art:trail-hclsmoke-<token>` (OUTSIDE
     the wrap-up passage → a `watch` item), then a `● ` closing message containing
     the per-run token `HCLSMOKE_<pid>`, then
     `✔ aitask workflow complete — t<task> hcl_smoke` /
     `outcome: archived (commit 5531518) · pushed: yes` /
     `follow-ups created: t154, t155`.
     Expected harvest: question (triage) + task t154 (open — file exists) +
     task t155 (file not found) + watch (trail) → `HARVESTED:capture|added=4|existing=0`.
   - `tmux new-session -d -x 240 -y 80 -s ait_hcl_$$ -n home "tail -f /dev/null"`,
     then run the Python heredoc with `PYTHONPATH` = lib, monitor, board,
     `.aitask-scripts` and `AIT_TEST_*` env (session, socket dir, repos, token).

2. **Python: containment + fixtures.** Assert `alu._TMUX.socket_args == []` and a
   `display-message #{socket_path}` round trip lands under `FIXTURE_DIR` (copied
   from the shadow live test) before anything mutates. Helpers (raw tmux via
   `subprocess` with `TMUX_TMPDIR` = fixture dir — a test fixture, not app code):
   `agent_window(name, banner)` = `new-window -d -P -F "#{pane_id} #{pane_pid}"
   -n <name> "sh -c 'cat <file>; exec tail -f /dev/null'"` plus a companion
   stand-in split `sh -c 'exec -a AIT_HCL_COMPANION_SENTINEL sleep 86400'`;
   `wait_for_text(pane, needle)` polls `capture-pane -p -J` until the banner's
   first line is visible (readiness, not a sleep; fail at a 10 s deadline);
   `pane_alive`, `pane_pid`, `window_exists`, `pid_alive` (`os.kill(pid, 0)`).
   Patch `mc._is_companion_process` to match the sentinel (as
   `test_kill_agent_run_guarded.sh` does) so discovery classifies the stand-in
   as a companion.

3. **Python: the real app host.** `mk_app(monitor, snap, root)` builds
   `MonitorApp.__new__(MonitorApp)` (shadow-test pattern) with: the real
   `TmuxMonitor(session=SESSION)`; `_snapshots` from a `PaneSnapshot` whose
   `pane` is the **discovered** `TmuxPaneInfo` (`monitor.discover_panes()`,
   which also fills `_pane_cache`); `_session_root_map = {SESSION: root}` so the
   real `_strict_root_for_snap` resolves; `_focused_pane_id`; `_task_cache=None`.
   Only UI seams are stubbed: `_current_agent_snapshot` → the snap (Textual
   focus does not exist on a `__new__` app), `notify` (recorded), `push_screen`
   (records `(screen, callback)`), `call_later` (recorded), and
   `_dispatch_harvest_close` (records its args — the worker seam the unit suite
   also stubs). Two **pass-through spies** record calls without changing them:
   `monitor._tmux_async` and `app._run_sitrep_harvest` (argv + stdin).
   Flow helper `harvest(app)`: `action_harvest_close()` → assert exactly one
   dispatch → `await app._harvest_close(*dispatched)` → return the pushed
   `(dialog, callback)`.

4. **Case A — happy path, two passes** (`ctrl` with `await
   monitor.start_control_client()`, `sub` without; each pass in its own
   `asyncio.run(...)` that also closes the client; repos `repo_ctrl` /
   `repo_sub`, windows `agent-pick-153` / `agent-pick-163`, so the stores are
   independent). Assert:
   - dispatch state `"live"` (real `_kill_target_state` read the live
     `@aitask_frozen` option) and root = realpath of the repo;
   - the `_tmux_async` spy saw `display-message` (identity) before and after,
     and one `capture-pane -p -J -t <pane> -S -50000`;
   - the harvest spy argv is exactly `capture --root <repo> --agent agent-pick-<n>
     --task <n> --operation pick`, and its stdin contains the token;
   - `dialog._report.ok`, `final_kind == "HARVESTED"`, `added == 4`,
     item kinds `{question, task, task, watch}`, task refs `{t154, t155}`;
   - the store is real: `aitask_sitrep_todo.sh list` with
     `AITASK_SITREP_DIR=<repo>/.aitask-sitrep` lists those items, the token is in
     a retained file under the store, and `git -C <repo> status --porcelain` is
     empty (the helper's local `info/exclude` rule held);
   - confirm: `callback(True)` → the agent pane is gone, its window and the
     companion stand-in remain, the `home` pane remains, a `Closed agent-pick-<n>`
     toast was recorded, and the pane left `monitor._pane_cache`.

5. **Case B — failing harvest keeps the pane** (`repo_neg`, `agent-pick-170`,
   subprocess route): report not ok, `final_kind == "HARVEST_FAILED"`,
   `reason == "store_not_ignorable"`, verdict starts `HARVEST FAILED`, an
   `error` toast; the identity is **non-None** (so the refusal below is the
   report check, not a missing identity); `callback(True)` kills nothing — pane,
   pid and companion alive; no `.aitask-sitrep` under `repo_neg`.

6. **Case C — `agent-sitrep` is never harvested** (`repo_sitrep`, window
   `agent-sitrep`, showing the same banner so a harvest *would* find items):
   `final_kind == "skipped"`; the harvest spy recorded no call; the
   `_tmux_async` spy recorded no `capture-pane`; `<repo_sitrep>/.aitask-sitrep`
   does not exist. (Case A is the positive control: the same banner in an
   `agent-pick-*` window is captured and harvested.)

7. **Case D — `respawn-pane -k` between harvest and confirm** (`repo_resp`,
   `agent-pick-180`): harvest ok; then `respawn-pane -k -t <pane>
   "sh -c 'echo HCL_NEWRUN; exec tail -f /dev/null'"`, wait until `pane_pid`
   differs and `HCL_NEWRUN` is visible; `callback(True)` → pane alive, the new
   pid alive, a `changed since the harvest` warning toast recorded. Control:
   re-read a fresh identity and `monitor.kill_agent_run_guarded(fresh)` returns
   `("killed", False)` — so "changed" came from the guard, not a broken kill.

8. **Isolation manifest** (bash, around the whole run). `manifest()` = sorted
   `<sha256>  <path>` (via `$AIT_PYTHON -c`, portable) of every file under
   `$REPO_ROOT/.aitask-sitrep/` (if present) and, under
   `$REAL_HOME/.config/aitasks/`, `agent_sessions.json` plus every `*.harvested`
   receipt. After the run: equal → `ISOLATION:manifest_unchanged`. Different →
   list the differing paths and FAIL if any of them contains the run token or
   `hclsmoke` (our leak); otherwise print `ISOLATION:concurrent_writer` with the
   list (the monitor's maintenance tick legitimately rewrites this repo's store)
   and pass. Also assert every scratch store write landed under `$SCR`.

9. **Docs.** `aidocs/framework/sitrep.md` Tests table row:
   `tests/test_monitor_harvest_close_live.sh` — "`h` end to end against a private
   tmux server: real capture → real `harvest capture` → store items → guarded
   close (pane only); a failed harvest keeps the pane; `agent-sitrep` is never
   captured; a respawn after the harvest is refused". Header comment of the new
   test documents the destructive-class reasoning, the run command, and that it
   is opt-in (not in `run_all_python_tests.sh`). Update the unit test's
   docstring pointer.

### Post-phase (risk mitigations)

1. [harvest_close_live_mutants] With the live test green and the tree clean
   except for this task's files, apply each mutant below to
   `.aitask-scripts/monitor/sitrep_close.py` **one at a time**, run
   `bash tests/test_monitor_harvest_close_live.sh`, and require a non-zero exit
   whose `FAIL:` line names the expected case; then `git checkout --
   .aitask-scripts/monitor/sitrep_close.py` and require `git diff --quiet --
   .aitask-scripts/monitor/sitrep_close.py` before the next mutant:
   - (a) `sitrep_skip_removed` — in `_harvest_for_close`, drop the
     `is_sitrep_window(window)` branch → case C must FAIL (capture + harvest seen);
   - (b) `confirm_ignores_ok` — in `_on_harvest_close_confirmed`, drop
     `or not report.ok` → case B must FAIL (pane killed after a failed harvest);
   - (c) `kill_unguarded` — in `_guarded_close`, replace
     `self._monitor.kill_agent_run_guarded(identity)` with
     `(("killed" if self._monitor.kill_pane(pane_id) else "failed"), False)` →
     case D must FAIL (the respawned process dies).
   Record each mutant's FAIL line in the Final Implementation Notes. A mutant
   that stays GREEN is a defect in the test: fix the test before Step 8.

## Verification

- `bash tests/test_monitor_harvest_close_live.sh` → ends `PASS:` and prints
  `ISOLATION:manifest_unchanged` (or the justified `concurrent_writer` line).
- `shellcheck tests/test_monitor_harvest_close_live.sh`.
- Regression neighbours: `bash tests/test_kill_agent_run_guarded.sh`,
  `bash tests/test_sitrep_harvest.sh`,
  `python3 tests/test_monitor_sitrep_harvest_close.py`.
- `bash tests/test_no_raw_tmux.sh` (tests/ is not scanned; confirms nothing
  under `.aitask-scripts/` changed shape).

## Post-implementation

Step 9 of the task workflow: Step 8 review, code commit
`test: Add live harvest-and-close smoke (t2206)` (path-scoped), plan commit via
`aitask_task_commit.sh`, archive t2206, push via `./ait git`.

## Risk

### Code-health risk: low
- A new opt-in live test and two documentation lines; no production code changes. The test owns a private tmux server and scratch HOME/repos, so a fixture slip cannot reach the developer's server or store · severity: low · → mitigation: none (require_clean_ait_server + require_isolated_tmux, the containment round-trip, and the before/after manifest are part of the plan body)

### Goal-achievement risk: low
- A live smoke can pass vacuously — a "never captured" case is green if nothing is ever captured, and a "refused kill" case is green if the kill path is broken — so the test would not prove the composed path · severity: low (residual — addressed by inline post-phase harvest_close_live_mutants plus the in-test positive controls: case A for C, the fresh-identity kill for D, the non-None identity for B) · → mitigation: inline post-phase harvest_close_live_mutants
- The test is an opt-in bash file outside `run_all_python_tests.sh`, so it only protects when someone runs it (and it refuses inside tmux or with `-L ait` alive) · severity: low · → mitigation: none (same posture as the other live tmux tests; recorded in `aidocs/framework/sitrep.md`)

### Planned mitigations
- timing: post-phase | name: harvest_close_live_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — vacuous live assertions | desc: run three sitrep_close.py mutants (sitrep skip removed, confirm ignores report.ok, unguarded kill) against the live test and require each to FAIL, restoring the file after each

## Final Implementation Notes
- **Actual work done:** `tests/test_monitor_harvest_close_live.sh` (new) drives `MonitorApp.action_harvest_close()` → `_harvest_close` → the confirm callback → `_close_live_after_harvest` → `kill_agent_run_guarded` against a private tmux server, with the real gateway capture and the real `aitask_sitrep_harvest.sh capture` writing scratch stores. Cases A (ctrl + subprocess routes: 4 items — triage question, t154 open, t155 not found, trail watch — store git-ignored, pane-only close keeping window + companion), B (`store_not_ignorable`: no store, confirm refuses with a valid identity), C (`agent-sitrep`: no capture, no harvest, no store), D (`respawn-pane -k` before confirm: `changed`, new process alive; fresh-identity control kill). Row added to `aidocs/framework/sitrep.md` Tests; unit-test docstring now points at the live test. Run result: all cases OK, `ISOLATION:manifest_unchanged`, `PASS`.
- **Deviations from plan:** case B reads the bound run identity through a third pass-through spy on `_harvest_for_close` (records its return value) instead of inspecting the callback; the containment check compares realpaths (macOS reports `/tmp` as `/private/tmp` — the first run failed on exactly that, before any mutation).
- **Issues encountered:** the system `python3` lacks textual, so the unit file must be run with the venv interpreter (`~/.aitask/venv/bin/python`).
- **Key decisions:** only UI seams are stubbed (focused-card lookup, notify / push_screen / call_later, the worker dispatch seam); `_tmux_async`, `_run_sitrep_harvest` and `_harvest_for_close` are wrapped by recording pass-through spies. Fixture readiness is polled (banner / respawn text visible, pid changed), never slept. The manifest fails only when a changed real file carries this run's token or trail id, otherwise reports `concurrent_writer` (the monitor's maintenance tick legitimately rewrites this repo's store).
- **Post-phase harvest_close_live_mutants (all red, file restored clean after each):**
  - `sitrep_skip_removed` → `FAIL: C: report HarvestReport(final_kind='HARVESTED', … added=4 …)`
  - `confirm_ignores_ok` → `FAIL: B: a failed harvest's confirm killed the agent`
  - `kill_unguarded` → `FAIL: D: the confirm killed the respawned process`
- **Verification run:** live test PASS; `tests/test_kill_agent_run_guarded.sh` PASS; `tests/test_sitrep_harvest.sh` 139/139; `tests/test_no_raw_tmux.sh` 5/5; shellcheck: SC1091 infos only (same as sibling live tests). `tests/test_monitor_sitrep_harvest_close.py` (venv): 66 run, FAILED (failures=4) — identical at HEAD, see the upstream defect below.
- **Upstream defects identified:**
  - `tests/test_monitor_sitrep_harvest_close.py:985` — `KeyDispatchTests` sets `self.root = Path(self._tmp.name) / "repo"` without `realpath`, while `_strict_root_for_snap` canonicalizes through `agent_marks.mark_key` (realpath); on macOS the tempdir under `/var` resolves to `/private/var`, so `test_monitor_h_and_S_act_on_the_focused_card` and `test_minimonitor_h_and_S_act_on_the_followed_agent` (keys h and S, 4 subtests) fail on every run.
