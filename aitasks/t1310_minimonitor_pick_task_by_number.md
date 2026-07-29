---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [tui, monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-07-29 07:49
updated_at: 2026-07-29 10:27
---

## Problem

At the end of a codeagent run the agent typically reports follow-up tasks it
created, or suggests a task to pick next — as bare task numbers. Acting on that
today means leaving the agent's window, opening `ait board`, locating the task
card, and pressing `p`. That is a slow detour for what should be a two-keystroke
action from the minimonitor already docked beside the agent.

`ait minimonitor` has no way to target an arbitrary task: every pick path
derives its target from the followed pane (`n` → `find_next_sibling`) or from a
list. There is no "type a task number" entry anywhere in the repo's TUIs.

## Goal

Add a task-pick command to `ait minimonitor` that takes a task number directly:

1. **Dialog 1 — task selector.** Prompts for an aitask number (e.g. `1234` or
   `1234_2`; accept a leading `t` and strip it). Resolves it and reports a clear
   error if it does not exist.
2. **Dialog 2 — task detail + confirm.** Shows the resolved task's details
   (title, priority, effort, type, status, body) with **OK** / **Cancel**
   buttons and a **checkbox**: "also kill the followed codeagent".
3. **On OK** — launch `/aitask-pick <id>` exactly as the existing `n` command
   does; if the checkbox was ticked, kill the followed agent afterwards using the
   same mechanism `n` uses.

## Existing code to reuse (do not reinvent)

All paths relative to the repo root.

**Launch tail — reuse verbatim.** `_launch_pick_for_own()` in
`.aitask-scripts/monitor/minimonitor_app.py:988-1052` is the complete,
narrow-mode pick launcher:

```
full_cmd = resolve_dry_run_command(target_root, "pick", target_id)
screen   = AgentCommandScreen(f"Pick Task t{target_id}", full_cmd, prompt_str,
             default_window_name=f"agent-pick-{target_id}",
             project_root=target_root, operation="pick",
             operation_args=[target_id], default_agent_string=…,
             skill_name="pick", default_profile=…, narrow=True)
# on confirm:
launch_in_tmux(screen.full_command, pick_result)
if pick_result.new_window:
    maybe_spawn_minimonitor(pick_result.session, pick_result.window)
```

Prefer factoring the shared portion out of `_launch_pick_for_own` rather than
copying it, so `n` and the new command cannot drift.

**Ordering is load-bearing.** Per the docstring at `minimonitor_app.py:991-998`,
the minimonitor shares the followed agent's window, so killing that window tears
down the minimonitor itself. **Launch first, kill second** — the new command must
preserve this order.

**Task resolution + detail rendering.**
- `TaskInfoCache.get_task_info(task_id, session_name)` —
  `.aitask-scripts/monitor/monitor_core.py:2547` — resolves *any* task id to a
  `TaskInfo` (`monitor_core.py:2402`: task_id, task_file, title, priority,
  effort, issue_type, status, body, plan_content, task_file_abs). Cross-project
  aware via the session→project-root map. Returns `None` for a missing task —
  that is the "task does not exist" signal for dialog 1.
- `TaskDetailDialog(info)` — `.aitask-scripts/monitor/monitor_shared.py:147` —
  already renders exactly that `TaskInfo` (header, meta line, Markdown body, `p`
  toggles task/plan). It is read-only and dismisses with no value, and it has no
  `narrow` variant. Either extend it with an optional confirm/checkbox footer
  (keeping the existing `i`/`I` call sites dismissing as they do today) or build
  a new dialog that reuses its layout. Whichever route, add the `.narrow` CSS
  variant — the minimonitor pane is ~40 columns.
- Project root per pane: `_root_for_snap()` — `minimonitor_app.py:515`.
  Followed agent: `_find_own_agent_snapshot()` — `minimonitor_app.py:494`.

**Kill mechanism — reuse `n`'s, unchanged.**
`TmuxMonitor.kill_agent_pane_smart(pane_id)` —
`.aitask-scripts/monitor/monitor_core.py:2275` — kills just the pane when other
real agent panes remain in the window, else kills the whole window (which also
tears down the companion minimonitor and any shadow). Clear
`self._focused_pane_id` after, as `_launch_pick_for_own` does at
`minimonitor_app.py:1048-1049`.

**DECIDED — no busy/idle probe.** The existing `n` mechanism is the accepted
safeguard level for this task. Do **not** add an `is_idle` / `awaiting_input`
gate. The safeguards are the ones `n` already provides: the explicit user
confirmation steps, the stale-snapshot guard ("Followed agent no longer
exists"), and `kill_agent_pane_smart`'s pane-vs-window logic. The difference
from `n` is that the kill here is driven by the user's checkbox rather than by
`n`'s task-status heuristic (`"_" not in task_id or not current_info or
status == "Done"`), so the user makes the call explicitly.

**Input primitives.** No shared "enter a task id" modal exists.
- Minimal single-`Input` modal pattern: `_RepointInputScreen` —
  `.aitask-scripts/lib/stale_entry_modal.py:31` (Input at `:67`).
- Filterable list alternative: `FuzzySelect` —
  `.aitask-scripts/lib/agent_model_picker.py:118`, backed by
  `.aitask-scripts/lib/fuzzy_filter.py` (`match`, `rank`).
- `Checkbox` precedent: `.aitask-scripts/brainstorm/widgets.py:331` and
  `.aitask-scripts/diffviewer/plan_manager_screen.py:58` (none yet in
  `monitor_shared.py`).

## Keybinding

`p` is free in `minimonitor_app.py:187-201` (`tab enter k n e E c j q s i I m M d`
are taken; `?` comes from `ShortcutsMixin`).

Minimonitor has **no `check_action`** — bare single-key bindings are gated by
Textual's modal binding chain plus the `isinstance(self.screen, ModalScreen)`
early return in `on_key` (`minimonitor_app.py:742`) and per-action target checks.
Follow that existing pattern; do not introduce a `check_action` for this alone.

Keys are user-remappable: `ShortcutsMixin.__init__` calls
`register_app_bindings("minimonitor", BINDINGS)`
(`.aitask-scripts/lib/shortcuts_mixin.py:83-134`). Adding the `Binding` to
`MiniMonitorApp.BINDINGS` is sufficient for registration; never hardcode the
literal `"p"` elsewhere — resolve it via
`resolve_key("minimonitor", <action_id>)`
(`.aitask-scripts/lib/keybinding_registry.py:144`).

## Acceptance criteria

- [ ] A new minimonitor binding (`p`, remappable) opens a task-number input
      dialog scoped to the followed agent's project root.
- [ ] A non-existent / malformed task number produces a clear `notify(...,
      severity="warning")` and no launch.
- [ ] A valid number opens a detail dialog showing the task's title, priority,
      effort, type, status and body, with OK / Cancel and a "kill followed
      codeagent" checkbox (default unchecked).
- [ ] Cancel (button or `Esc`) at either dialog leaves everything untouched.
- [ ] OK launches `/aitask-pick <id>` through the same
      `resolve_dry_run_command` → `AgentCommandScreen(narrow=True)` →
      `launch_in_tmux` → `maybe_spawn_minimonitor` path as `n`.
- [ ] The kill (when the checkbox is ticked) happens **after** a successful
      launch, via `kill_agent_pane_smart`, and is skipped when the launch fails
      or the user cancels `AgentCommandScreen`.
- [ ] Both new dialogs render correctly at the minimonitor's ~40-column pane
      width (`.narrow` CSS variant), verified with a render-level assertion, not
      only by construction.
- [ ] The shared launch logic is factored so `n` and the new command use one
      implementation.
- [ ] Existing `i` / `I` task-info behaviour is unchanged if
      `TaskDetailDialog` is extended.

## Testing notes

- Follow `aidocs/framework/tui_conventions.md`.
- Prefer render-level assertions (`widget.render().plain`) over construction-only
  checks — the narrow-width regression class this repo has hit repeatedly
  (t998, t1012, t1122, t1187) is invisible to construction tests.
- Add a negative control proving the narrow-width test actually fails when the
  `.narrow` CSS variant is removed.

## Documentation

`website/content/docs/tuis/minimonitor/how-to.md:202-216` holds the key table.
It is **already stale** — it lists an `r` refresh key that has no binding and
omits `k`, `n`, `E`, `d`, `m`. Add the new key and fix the existing drift in the
same pass.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T07:27:06Z status=pass attempt=1 type=human
