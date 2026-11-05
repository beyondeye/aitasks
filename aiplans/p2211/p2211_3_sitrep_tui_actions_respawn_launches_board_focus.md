---
Task: t2211_3_sitrep_tui_actions_respawn_launches_board_focus.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_3 — TUI deterministic actions, respawn, launches, board focus

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. The task file
holds the CLI wire contracts and pattern references.

## Steps

1. **Gate + rebase check.** t2211_2 and t2037_2 landed. Re-read `sitrep_tui_app.py`
   (t2211_1), `monitor_core.find_sitrep_roles`, `sitrep_close.py` (`HarvestReport`
   parsing), `agent_launch_utils.py` (`launch_or_focus_trails`, `launch_in_tmux`,
   `focus_existing_agent_window`), `agent_command_screen.build_pick_screen`,
   `board/aitask_board.py` main + load path, and `trails_app.action_pick_task`. `git diff
   HEAD -- <files>` must be empty.
2. **Command runner.** One `_run_cli(argv, timeout)` in the TUI that runs off-loop with cwd =
   root and returns `(rc, stdout, stderr)`; a timeout counts as a failure. It is used by
   every action below.
3. **Harvest + refresh.**
   - Key `r` and on mount run, in one worker: `aitask_sitrep_harvest.sh all --root .`, then
     `aitask_sitrep_refresh.sh --root .` (timeout = budget 60 + 15).
   - A guard flag refuses a second run while one is in flight.
   - Parse the lines (reuse/extract the `sitrep_close.py` parser) into a result panel, then
     reload.
4. **Dismiss.**
   - Key `x` on an open item opens a `GuardedModalScreen` with a reason `Input`. Confirm
     runs `dismiss c<N> --outcome <reason> --expect-rev <rev>`.
   - `STATE:` → reload. `STALE:c<N>|<rev>` → reload and re-show the dialog with "changed
     since you looked (rev a→b)".
   - Exit 3 → "busy, retry". Exit 2/4 → error.
   - Cancel writes nothing.
5. **Restore.** When the store is unusable (banner), key `R` offers `restore todo` / `restore
   qa` in a confirm dialog, then shows `RESTORED:` / `no-damaged-copy` and reloads.
6. **Agent status + respawn.**
   - Poll `find_sitrep_roles` every 3 s off-loop; the header shows the agent state.
   - Key `A` is shown only when there is no agent (`check_action`). The action re-checks,
     then runs `aitask_sitrep.sh open --root <root> --session <own session>` (45 s) and
     toasts `sitrep_open_message`.
7. **Launches from details.**
   - Task item (`ref` matches `t<N>[_<M>]`, same repo): `p` → pick, the trails
     `action_pick_task` flow; `b` → `launch_or_focus_board(session, root, id)`.
   - Push item (`parse_push_ref`): `P` → a modal showing the exact command plus a copy via
     `tui_clipboard`, never executed.
   - Foreign-project refs (`<proj>#<N>`): pick and board are hidden.
8. **Board `--focus`.**
   - `aitask_board.py` main parses `--focus <id>`. After the first data load it selects the
     card (child ids resolve to the child card; missing/archived → toast).
   - A running board pane accepts a handoff pane option (e.g. `@aitask_board_focus=<id>`,
     added to the `tmux_gateway.md` inventory), read on its refresh tick, then cleared.
   - `launch_or_focus_board` in `agent_launch_utils.py` focuses an existing `board` window
     in the session and sets the option, else `launch_in_tmux("./ait board --focus <id>",
     new window "board")`.
9. **Dynamic bindings.** `check_action` covers kind/state/agent-presence/store-usable, with
   `refresh_bindings()` on selection change, reload and agent-state change. Every action
   re-checks its precondition at the top.
10. **Tests.**
    - `tests/test_sitrep_tui_actions.py`: fixture store via the real writer; stub the runner
      for harvest/refresh output samples; STALE path; cancel = no write; LOCK_BUSY; restore;
      bindings matrix per kind/state; respawn decode of each `SITREP_*` line; push command
      shown, with an assertion that it is not run.
    - Board focus test: argv parsing, card selected after load (run_test with a fixture task
      dir), handoff option consumed.

## Verification

- The tests above; `bash tests/run_all_python_tests.sh` (last line); `bash
  tests/test_no_raw_tmux.sh`; `shellcheck` on changed scripts.
- Manual, in a real sitrep window:
  - `r` shows harvest/refresh results;
  - `x` dismisses with a reason;
  - kill the agent: `A` respawns it;
  - `b` on a task opens/focuses the board on that card;
  - `p` launches a pick.

## Step 9

Commit with `feature: … (t2211_3)` and archive.
