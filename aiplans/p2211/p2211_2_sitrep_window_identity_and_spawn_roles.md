---
Task: t2211_2_sitrep_window_identity_and_spawn_roles.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_2 — Window identity + four-way spawn roles

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. The task file
holds the verified current-machinery map (line numbers to re-verify).

## Steps

1. **Gate + rebase check.**
   - t2037_2 must be landed (it has uncommitted `monitor_core.py` hunks). Re-read
     `monitor_core.py`, `status_client.py`, `sitrep_close.py`, `sitrep_harvest.py`,
     `agent_launch_utils.py`, `helper_panes.py`, `minimonitor_app.py`, `agent_freeze.py`
     and `aitask_companion_cleanup.sh`.
   - `git diff HEAD -- <files>` must be empty.

### Pre-phase (risk mitigations)

1. [sitrep_tui_consumer_table_characterization] Before any production edit:
   - write the consumer table into this plan (consumer → required classification → how it
     reads `@aitask_sitrep_tui_root`) and the table-driven tests in
     `tests/test_sitrep_window.py` (+ a row in `tests/test_cleanup_rule_parity.sh`);
   - rows:

     | consumer | required classification |
     |---|---|
     | discovery card listing | not an agent |
     | `match_sitrep_pane` fallback | not an agent |
     | `_find_sibling_pane_id` | not an agent |
     | `h` gating | not an agent |
     | `_scan_companion_window` | real occupant; not "companion present" |
     | cleanup job 2 | real occupant |
     | `kill_agent_pane_smart` / `_collapse_window_for` / `count_other_real_agents` | real occupant |
     | `agent_freeze._other_real_agents` | real occupant |

     Frozen-first holds on every row;
   - run the rows, record the red ones in this plan, then implement until all are green.

## Main steps

2. **Stamp.** `TUI_ROOT_OPTION = "@aitask_sitrep_tui_root"` in `lib/helper_panes.py` (beside
   `SITREP_ROOT_OPTION`, documented as identity, with the listing exclusion described).
   Add it to the `tmux_gateway.md` option inventory.
3. **Listing exclusion.**
   - Extend the pane format(s) the listing consumers read with `#{@aitask_sitrep_tui_root}`.
     If `FROZEN_AWARE_PANE_FORMAT` grows, update every reader's arity check in the same
     change (`classify_window_panes`, `_SITREP_SPLIT`, cleanup `-F`, the parity test).
   - Add a predicate `is_sitrep_tui_pane(stamp)` and apply it in discovery, the
     `match_sitrep_pane` fallback, `_find_sibling_pane_id` and the `h` gating.
   - Retention consumers keep counting the pane as real. Assert that explicitly; it is not
     merely untouched.
4. **`find_sitrep_roles(monitor, root)`** reads `list-panes -a` once. It returns the
   agent via `match_sitrep_pane` and the TUI via the stamp == root (live, not dead, not
   frozen), searched in any window. A failed query returns `ok=False`.
5. **`spawn_sitrep`** four-way under `_sitrep_spawn_lock`, per the task's table. A TUI launch
   helper (`launch_split_pane` with `-v -l 40%` + `-t <agent>`; for the agent respawn `-v -b
   -t <tui>`, cwd=root). Each new pane is stamped via `_stamp_or_remove`, and a stamp
   failure gives `refused stamp:<outcome>` as today. The TUI command is `ait sitrep tui
   --root <root>`; make it patchable for tests like `resolve_dry_run_command`. The
   respawned agent gets `attach_companion_cleanup_hook`. Add `spawn_test_pause` seams per
   path.
6. **Geometry.**
   - Add `full_height` kwarg to `maybe_spawn_minimonitor` → `_companion_check_and_split`
     (adds `-f`).
   - Call it with `full_height=True` outside the lock on `spawned` / `added_tui` /
     `respawned_agent`.
   - Pin other callers' argv unchanged.
7. **Wire lines.**
   - `SitrepSpawn` statuses `added_tui`, `respawned_agent`;
   - `sitrep_open.py` prints `SITREP_ADDED_TUI:` / `SITREP_RESPAWNED_AGENT:` (exit 0);
   - `sitrep_cli.sitrep_open_message` decodes them;
   - check that the switcher / monitor toasts read the decoded message.
8. **Agent-exit behaviour.** Test that the cleanup leaves the minimonitor + TUI, kills the
   dead agent, and that `_check_auto_close` does not close.
9. **Live tests** `tests/test_sitrep_window_live.sh`.
   - Scenarios: cold start; agent-only → `added_tui`; TUI-only → `respawned_agent`; TUI-only
     with no companion → column restored; both alive → `focused`.
   - Race proofs per starting state using `AITASK_SITREP_SPAWN_PAUSE_FIFO`: exactly one
     agent and one TUI per root.
   - Coordinate assertions as in the task: agent at 0,0; TUI under it with the same width;
     minimonitor at `left=agent.width+1`, top 0, full window height.
   - A mutant dropping `-f` makes cold start red.

## Verification

- `bash tests/test_sitrep_window_live.sh`, `bash tests/test_cleanup_rule_parity.sh`,
  `bash tests/test_kill_agent_run_guarded.sh`, `bash tests/test_no_raw_tmux.sh`.
- `bash tests/run_all_python_tests.sh` (last-line verdict) covering
  `tests/test_sitrep_window.py`, `tests/test_helper_panes.py`, the companion/minimonitor
  tests and `tests/test_agent_freeze.py`.
- Manual: `ait sitrep` cold start gives three panes in the agreed layout. Kill the agent:
  the TUI + minimonitor stay. `ait sitrep` then respawns the agent above the TUI.

## Step 9

Commit with `feature: … (t2211_2)` and archive.
