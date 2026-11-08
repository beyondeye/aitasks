---
Task: t2230_fix_tui_switcher_stale_window_index_companion_target.md
Base branch: main
Output branch: main
---

# t2230 — Switcher: stop acting on listing-time window indexes; make the board isolation control hermetic

## Context

t2227 fixed the minimonitor/monitor_core acting on a window index captured at
listing time: a `renumber-windows` shift (a window closing between listing and
action) moves another window onto that index. The TUI switcher has the same
class in two places, and t2227's full-suite triage also found an unrelated
non-hermetic test.

1. **`_switch_to` (Enter on a Code Agents / Other row)** — `_WindowListItem`
   stores the `#{window_index}` from `get_tmux_windows()` at populate time, and
   `_switch_to` runs `select-window -t =<session>:<index>`. If a window closes
   while the overlay is open, Enter selects the NEIGHBOURING window. Real defect.
   A second route to the same outcome: the select is fire-and-forget and the
   cross-session `switch-client` + dismiss run regardless, so a select that
   fails still lands the user on the other session's active window (step 2).
2. **`action_spawn_minimonitor` (Shift+M)** — `_CompanionTarget.window_index`
   is resolved at mount (`gateway_pane_window($TMUX_PANE)`) and passed as
   `window_index=` to `maybe_spawn_minimonitor`. Exploration shows the split is
   already fail-closed: `agent_pane=target.pane` is passed, `_companion_check_and_split`
   lists `=<session>:<index>` and refuses when the pane is not in it, the split
   target and refocus are the pane id, and the companion lock is per-SERVER. So
   the stale index never misplaces the companion — it produces a **spurious
   refusal** ("Minimonitor not added…") after a renumber. Still the t2227 class:
   fix by re-resolving the window from the pane id at action time.
3. **`tests/test_board_movement.py:1291`** — the control asserts no real task
   file ends with `_fixture.md`. The real fixture names are exactly
   `t{9000+i}_fixture.md` (`board_fixture.fixture_name`), and
   `aitasks/t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md` is a
   live task ending in `_fixture.md`, so it fails today. The root defect is that
   the control enumerates the live repo at all (non-empty requirement, name
   heuristics); it is rebuilt on two temp roots (step 5).

### Audit of the other `agent_launch_utils` window_index sites (no change)
- `focus_existing_window` (:616) — `find_window_by_name` then `select-window` by
  that index inside one call: short race, not the t2227 class.
- `switch_to_pane_anywhere` (:2048-2078) — `display-message` index read then used
  in the same call: short race.
- `_lookup_window_name` (:2468) — callers (board :5507, codebrowser :1670) feed it
  the index `launch_in_tmux` just returned, used immediately: short race.
- `maybe_spawn_minimonitor` (:2837) — consumes whatever the caller passes; only
  the switcher passes a carried-over index (fixed in the caller, step 3 below).

**Coordination:** `.aitask-scripts/lib/agent_launch_utils.py` has uncommitted
hunks from in-flight t2211_2 (incl. `maybe_spawn_minimonitor` /
`_companion_check_and_split`). This plan deliberately does **not** edit that
file. Files edited — all clean vs HEAD at planning time, re-check
`git diff --quiet HEAD -- <file>` immediately before each first edit:
`.aitask-scripts/lib/tui_switcher.py`, `tests/test_tui_switcher_companion_spawn.py`,
`tests/test_tui_switcher_multi_session.sh`, `tests/test_tui_switcher_brainstorm_session.sh`,
`tests/test_tui_group_nav.py`, `tests/test_board_movement.py`. If any is dirty
at edit time, stop and ask.

## Implementation

### Pre-phase (risk mitigations)
1. [probe_window_id_target] On a scratch `tmux -L t2230probe-$$` server (scratch
   dir, never the user's server; kill only that `-L` server at the end): create
   session `s` with `renumber-windows on`, windows `a`,`b`,`c`; record
   `list-windows -t =s: -F '#{window_id}\t#{window_index}\t#{window_name}'`;
   kill `a`; confirm (a) `select-window -t =s:@<id of c>` selects `c` (check
   `display-message -p -t =s: '#{window_name}'`), (b) `select-window -t =s:<old index of c>`
   now does NOT select `c` (the bug, control), (c) `select-window -t =s:@<id of killed a>`
   exits non-zero, (d) `display-message -p -t <pane id of c> '#{session_name}\t#{window_index}'`
   reports the post-renumber index. Paste the script + output into Final
   Implementation Notes. If (a) or (c) fails, stop and re-plan.

### Main steps
1. **`tui_switcher.py` — window listing with ids.** Add a private helper next
   to the module helpers:
   ```python
   def _session_windows(session: str) -> list[tuple[str, str, str]]:
       """``(window_id, window_index, name)`` for ``session``'s windows; [] on failure.
       The id (``@N``) is the action identity — never the index, which a
       ``renumber-windows`` shift reassigns between listing and Enter (t2230)."""
       rc, out = _TMUX.run(["list-windows", "-t", tmux_session_target(session),
                            "-F", "#{window_id}\t#{window_index}\t#{window_name}"])
       if rc != 0:
           return []
       rows = []
       for line in out.splitlines():
           parts = line.split("\t", 2)
           if len(parts) == 3 and re.fullmatch(r"@\d+", parts[0]):
               rows.append((parts[0], parts[1], parts[2]))
       return rows
   ```
   (`tmux_session_target` imported from `agent_launch_utils` if not already;
   `_TMUX` and `re` already exist in the module.) In `_populate_list_for`,
   replace `get_tmux_windows(session)` with `_session_windows(session)`;
   `_running_names` from the name field; the classify loop iterates
   `(win_id, _idx, win_name)` and `agents`/`others` hold `(win_id, win_name)`.
   Drop the `get_tmux_windows` import if it becomes unused.
2. **`_WindowListItem` / `_switch_to`.** `_WindowListItem(window_name, window_id)`
   stores `self.window_id`. Both selection handlers (lines ~1205/1214) call
   `self._switch_to(item.window_name, True, item.window_id)`. `_switch_to`'s
   parameter becomes `window_id: str | None = None` and targets
   `tmux_window_target(self._session, window_id if window_id else name)` →
   `=<session>:@N`. TUI rows keep name targeting.

   **Gate the rest of the switch on the select succeeding.** Today the
   `running` branch fires `select-window` with `_TMUX.spawn` (Popen, exit status
   ignored) and then unconditionally runs `_teleport_if_cross()` and
   `dismiss(name)` — so when the selected window in ANOTHER session has closed,
   `select-window` fails but `switch-client` still lands the user on that
   session's active window, which is the same wrong-window outcome via another
   route. Change the `running` branch to:
   ```python
   rc, _ = _TMUX.run(["select-window", "-t", target])
   if rc != 0:
       self.app.notify(f"Window {name} is no longer there", severity="warning")
       return                      # no teleport, overlay stays open
   ```
   before `_teleport_if_cross()`/`dismiss`. This applies to every `running`
   select (window-id rows and name-targeted TUI rows alike — a TUI window that
   closed while the overlay was open has the same teleport-to-wrong-window
   path). `_TMUX.run` folds OSError/timeout into `rc=-1`, so the failure path
   is reached by tmux errors too; the `except (FileNotFoundError, OSError)`
   stays for the launch branches.
3. **`_CompanionTarget` / `action_spawn_minimonitor`.** Reduce `_CompanionTarget`
   to `(pane, project_root)` — the mount-time session/index are no longer
   carried, so nothing can act on them. `_resolve_companion_target` still runs
   `gateway_pane_window` (gateway-server verification) and `companion_present`.
   At action time:
   ```python
   location = gateway_pane_window(target.pane, os.environ.get("TMUX", ""))
   if location is None:
       self.app.notify("Minimonitor not added: this TUI's pane could not be located", severity="warning")
       return
   session, window_index = location
   companion = maybe_spawn_minimonitor(session, self._current_tui,
       window_index=window_index, force_companion=True, explicit=True,
       project_root=target.project_root, agent_pane=target.pane)
   ```
   The index is read and consumed within one action (short race), and the
   existing `agent_pane`-membership check in `_companion_check_and_split` closes
   the residual window fail-closed. Update the docstrings to say the pane id is
   the identity.
4. **Tests — switcher.**
   - `tests/test_tui_switcher_companion_spawn.py`: `_TARGET = _CompanionTarget("%9", Path(...))`;
     `ResolveCompanionTargetTests` assert `target.pane == "%9"`;
     `SpawnActionTests` patch `ts.gateway_pane_window` and assert the spawn uses
     the **action-time** location (mount said `("s1","4")`, action says
     `("s1","2")` → `window_index == "2"`, session `"s1"`); new test: action-time
     `gateway_pane_window` → None ⇒ no spawn, warning, overlay kept.
   - New renumber regression (same file or a new `RenumberedWindowSelectTests`
     class): a fake `_TMUX.run` returns listing `@5\t1\tagent-a`, `@7\t2\tagent-b`;
     populate, take the `agent-b` item, then simulate the renumber (the fake now
     says `@7` is at index 1) and press Enter: the `select-window` argv targets
     `=s1:@7`, never `=s1:2`. **Pre-fix control:** the same test against HEAD's
     code must fail (run it once against a `git show HEAD:` copy in scratch,
     record the failure in Final Implementation Notes).
   - `_session_windows` parser tests: tab-containing names kept whole, malformed
     / non-`@N` rows skipped, rc≠0 → [].
   - `tests/test_tui_switcher_multi_session.sh`: the `running=True` cases now
     patch `tui_switcher._TMUX.run` (records argv, returns `(0, "")`) alongside
     `subprocess.Popen` (switch-client still goes through `spawn`):
     `_switch_to(..., window_id="@2")` → `select-window -t =s1:@2` / `=s2:@2`,
     then `switch-client` for the cross case. **New disappeared-target cases**
     (same-session and cross-session): `_TMUX.run` returns `(1, "")` → zero
     `switch-client` Popens, `dismiss` not called, one warning notified.
     Pre-fix control: the cross-session disappeared case run against HEAD's
     `_switch_to` shows a `switch-client` and a dismiss (record it).
   - `tests/test_tui_switcher_brainstorm_session.sh` and `tests/test_tui_group_nav.py`:
     patch `tui_switcher._session_windows` (3-tuples) instead of
     `get_tmux_windows`; the `_WindowListItem` lambda signature `(name, wid)`.
   - `tests/test_markup_colour_contract.py:487` `_WindowListItem("shellwin", "3")`
     stays valid (positional); change the literal to `"@3"` for clarity.
5. **`tests/test_board_movement.py` — hermetic control, no live repo.** The
   control proves one thing: `aitask_board.TASKS_DIR` is a module constant
   (`Path("aitasks")`, resolved against the cwd) fixed at import, so a later
   `TASK_DIR` override is ignored and the in-process variant reads the cwd's
   tree, not the override's. Two controlled temp roots show that without
   touching the live repo:
   ```python
   cwd_root = Path(tempfile.mkdtemp(prefix="aitask_board_negctrl_cwd_"))
   override_root = Path(tempfile.mkdtemp(prefix="aitask_board_negctrl_ovr_"))
   for d in (cwd_root, override_root):
       self.addCleanup(shutil.rmtree, d, ignore_errors=True)
       (d / "aitasks").mkdir()
   (cwd_root / "aitasks" / "t1_cwd_sentinel.md").write_text("cwd\n")
   (override_root / "aitasks" / "t2_override_sentinel.md").write_text("override\n")
   prev_cwd, prev = os.getcwd(), os.environ.get("TASK_DIR")
   self.addCleanup(os.chdir, prev_cwd)
   os.chdir(cwd_root)
   with mock.patch.dict(os.environ, {"TASK_DIR": str(override_root / "aitasks")}):
       self.assertEqual(aitask_board.TASKS_DIR, Path("aitasks"))      # override ignored
       read_root = (Path.cwd() / aitask_board.TASKS_DIR).resolve()
       self.assertEqual(read_root, (cwd_root / "aitasks").resolve())
       self.assertNotEqual(read_root, Path(os.environ["TASK_DIR"]).resolve())
       seen = sorted(p.name for p in read_root.glob("*.md"))
       self.assertEqual(seen, ["t1_cwd_sentinel.md"])                   # never the override's
   os.chdir(prev_cwd)
   self.assertEqual(os.environ.get("TASK_DIR"), prev)
   self.assertEqual(os.getcwd(), prev_cwd)
   ```
   Distinct sentinel contents per root; cwd and `TASK_DIR` both restored (the
   suite runs in one interpreter; `--dist loadfile` keeps the chdir within
   this module's worker). Update the class docstring (it no longer reads "the
   REAL tree"). No assertion depends on live task names or counts, so the
   t2226 collision cannot recur. Confirm: HEAD fails today with t2226 present;
   new version passes. Negative control for the new test: temporarily point
   the read root at `TASK_DIR` (scratch copy) → the `seen` assertion fails.

## Verification
- `python3 -m pytest tests/test_tui_switcher_companion_spawn.py tests/test_tui_group_nav.py tests/test_markup_colour_contract.py tests/test_board_movement.py -q`
  (or `python3 tests/<file>` where the module is script-style).
- `bash tests/test_tui_switcher_multi_session.sh`, `bash tests/test_tui_switcher_brainstorm_session.sh`.
- `bash tests/test_no_raw_tmux.sh` (the new list-windows goes through `_TMUX`).
- `grep -n "window_index" .aitask-scripts/lib/tui_switcher.py` — only the
  action-time local in `action_spawn_minimonitor` remains.
- Pre-phase probe output recorded in the plan.

## Step 9
Post-implementation: commit code (`bug: … (t2230)`), plan via
`aitask_task_commit.sh`, archive per task-workflow Step 9.

## Risk

### Code-health risk: low
- Switcher window rows change shape (index → id) and three test files patch the switcher's listing; a missed patch would let a test reach a real tmux server · severity: low · → mitigation: TBD (covered by step 4's explicit patch list + `grep get_tmux_windows tests/`)
- `select-window` moves from non-blocking `spawn` to blocking `run` (bounded by the gateway's default timeout) — a slow tmux now delays Enter slightly instead of risking a wrong teleport · severity: low · → mitigation: TBD (accepted; correctness over a sub-100 ms latency)
- The board control now `chdir`s; a leaked cwd would break later tests in the same worker · severity: low · → mitigation: TBD (addCleanup + explicit restore + final cwd assertion in step 5)

### Goal-achievement risk: low
(Reassessed after inlining probe_window_id_target: the assumption is proven before any edit, with a stop-and-replan exit.)
- The fix assumes tmux resolves `=<session>:@N` as a window-id target in a session-anchored form, and that a closed window's id fails rather than falling back to another window · severity: medium · → mitigation: inline pre-phase probe_window_id_target

### Planned mitigations
- timing: pre-phase | name: probe_window_id_target | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (tmux `=session:@N` target assumption) | desc: scratch `tmux -L` probe of window-id targeting across renumber-windows, with an index-based control
