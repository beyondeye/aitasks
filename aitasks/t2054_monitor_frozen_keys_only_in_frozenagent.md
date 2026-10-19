---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, monitor, frozen_agents, keybindings]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2049
created_at: 2026-10-19 08:32
updated_at: 2026-10-19 09:18
---

## Symptom

In a frozen agent's window (e.g. `agent-pick-2018`), the user clicks the
minimonitor and presses `p` to pick a task by number (for example one of the
follow-ups the frozen agent reported). Instead, the stand-in window is torn down
and the frozen task is **re-picked**, with no confirmation. It happened
consistently (4+ times, several windows), and it looks as if the keystroke went
to the frozen-agent pane.

## Root cause

The keystroke does reach the minimonitor. tmux routing is normal: mouse on,
`MouseDown1Pane` = `select-pane -t = ; send-keys -M`, no focus hooks, and the
minimonitor only calls `select-pane` on Tab. The minimonitor's own `p` is
branched on the frozen state (t1705_7):

- `.aitask-scripts/monitor/minimonitor_app.py` `action_pick_task_by_number`
  (~:3373): when the followed agent is frozen it calls
  `self.action_repick_frozen()`, which is
  `aitask_frozen.sh restore <id> --repick` via
  `monitor_shared._start_frozen_restore` (~:1249). It never shows the
  pick-by-number prompt and asks for no confirmation.

So in a frozen agent's window the minimonitor cannot pick a different task by
number, which is exactly the end-of-run case `p` exists for (t1310).

Aggravating factor: stand-in processes started before t2049 (e.g. pid 24484 for
`0a902614`, started 2026-10-18 10:16, before the t2049 commit at 10:46) still
bind `p` = Re-pick inside `ait frozenagent` itself. Clicking into the stand-in by
mistake therefore produces the same outcome. No code change is needed for that;
it goes away as the stand-ins are restarted.

## Decision (user-confirmed)

Frozen-specific restore/re-pick shortcuts belong to `ait frozenagent` only
(`R` restore, `P` re-pick — t2049). The monitors keep the shortcut meanings they
have with a regular code agent.

### In scope

1. **minimonitor `p`**: always pick-by-number. Remove the frozen re-pick branch
   in `action_pick_task_by_number`, including its docstring mention of
   t1705_7.
2. **minimonitor `R`**: remove the `Binding("R", "restore_frozen", …)`
   (~:1246) and the `#mini-key-hints` text that lists it. The hints/bindings
   parity is test-pinned.
3. **full monitor `p`**: remove `Binding("p", "repick_frozen", …)`
   (`monitor_app.py` ~:558). The monitor has no other `p` meaning.
4. **full monitor `R`**: in `action_restart_task` (~:3811), the frozen branch
   must no longer call `action_restore_frozen()`. On a frozen card, `R` refuses
   with a hint toast that points to `ait frozenagent` (R restore / P re-pick),
   rather than falling through to the idle check with a misleading reason.
5. **Freeze toast** `monitor_shared.py` ~:1161
   (`"Frozen — press R to restore, p to re-pick"`): reword it to point at the
   frozen-agent viewer, whose keys are `R` / `P`.
6. Remove `action_restore_frozen` / `action_repick_frozen` / `_frozen_target`
   / `_start_frozen_restore` from `monitor_shared.py` if they become unused, and
   remove their keybinding-registry entries (`lib/keybinding_registry.py`,
   `tests/test_shortcuts_registry_coverage.sh`). Check for persisted user key
   overrides for those action ids (`(scope, action)` rows) and decide how they
   degrade.
7. **Docs** (current-state only):
   - `website/content/docs/tuis/minimonitor/how-to.md` (~:332–:360 frozen
     section, ~:442 key table row for `p`)
   - `website/content/docs/tuis/monitor/reference.md` (~:42 `p` row, ~:169
     frozen message text)
   - `website/content/docs/tuis/monitor/how-to.md` (~:274–:288)
   - `website/content/docs/workflows/freeze-and-restore-agents.md`: the
     sentence t2049 added saying the monitors use `p` on a frozen card
   - `website/content/docs/tuis/frozenagent/reference.md`: the `P` row note
     "`p` in `ait monitor` / `ait minimonitor`, where `P` is the frozen
     filter"
   - Explain the replacement flow: Tab into the stand-in pane (minimonitor), or
     focus/switch to the frozen window (monitor), then use the viewer's `R` / `P`.
   - Run `cd website && python3 check_links.py --build`.
8. **Tests**: update `tests/test_monitor_frozen_filter.py` and any monitor or
   minimonitor tests that pin `p`/`R` on frozen snapshots. Add regressions:
   - minimonitor `p` on a frozen followed agent opens `TaskNumberInputModal`
     and dispatches no `restore` (`run-shell` argv).
   - minimonitor `R` is unbound (pressing it dispatches nothing).
   - monitor `p` on a frozen card dispatches nothing.
   - monitor `R` on a frozen card dispatches no restore and shows the hint.
   - Negative control: with the old branches restored, these tests fail.

### Out of scope (unchanged by decision)

- `k` on a frozen followed agent/card stays routed to the leased
  `aitask_frozen.sh drop` behind its confirm dialog.
- `f` / `Z` (freeze / freeze all) and `P` (parked/frozen visibility filter)
  stay as they are.
- `ait frozenagent` bindings (`R`, `P`, `k`) are unchanged.

## Notes

- `Enter` in the minimonitor sends Enter to the sibling pane. On a frozen agent
  that pane is the stand-in, where Enter is only meaningful in list mode
  (`action_open`), so it is inert in viewer mode. Leave it unchanged.
- `n` (pick next for own) has no frozen branch. When the followed task is Done
  it kills the stand-in via `kill_agent_pane_smart`, whose frozen path is an
  unleased store write (see the `_drop_frozen` docstring). It is not part of this
  task. Mention it in Final Implementation Notes as an upstream-defect candidate
  if it is confirmed.
