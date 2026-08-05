---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1377_1]
issue_type: feature
status: Done
labels: [aitask_monitormini, tui, board_columns]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-08-04 09:54
updated_at: 2026-08-05 18:40
completed_at: 2026-08-05 18:40
---

## Context

`ait minimonitor`'s `p` (pick-by-number) flow is a fixed 3-step chain:
`TaskNumberInputModal` -> `TaskPickConfirmDialog` -> `AgentCommandScreen`. This
child adds a **choice** at step 2: pick the task (today's path, unchanged) or move
it to a board column.

t1377_1 built the headless seam (`lib/board_columns.py` +
`aitask_board_column.sh`); this child is its first consumer. Column creation is
deliberately **not** here — it is t1377_3.

**Acceptance criterion 1 of the parent is byte-for-byte invariance of the pick
path.** That is the sharpest constraint on this change.

## Key Files to Modify

- **`.aitask-scripts/monitor/monitor_shared.py`** — widen `TaskPickConfirmDialog`'s
  dismissal; add `ColumnPickerModal` + `_ColumnRow`.
- **`.aitask-scripts/monitor/minimonitor_app.py`** — route on the action tag; add
  the subprocess helper; invalidate the task cache.
- **`tests/test_minimonitor_pick_by_number.py`** — extend.

## Reference Files for Patterns

- `monitor_shared.py` `NextSiblingDialog` — the exact three-button precedent,
  dismissing `("pick", id)` / `("choose", parent)` / `None`, with a `.narrow`
  variant that stacks buttons vertically.
- `monitor_shared.py` `ChooseSiblingModal` + `_SiblingRow` — the list-picker
  precedent: focusable rows, `on_key` handling `enter` / `up` / `down` with
  `prevent_default()` + `stop()`, `_focus_neighbor` clamping, `VerticalScroll` list,
  help line, OK/Cancel, and a one-line `.narrow` block.
- `monitor_shared.py` `AgentMarksMixin._run_marks_cmd` — **the** subprocess-helper
  shape: `asyncio.create_subprocess_exec`, hard timeout, kill-then-reap on timeout,
  `OSError` -> `(1, "ERROR:...")`. Total by contract: never raises, always
  terminates. Tests override this method.
- `minimonitor_app.py` `_root_for_snap` — how a per-pane `target_root` is resolved
  (session -> project mapping). This is why the seam is root-scoped.
- `tests/test_agent_command_dialog_narrow.py`, `tests/test_concern_picker_modal.py`
  — the narrow region-fit / `_screen_text` harnesses.

## Implementation Plan

### 1. `TaskPickConfirmDialog` — widen the dismissal

It already dismisses a tuple, so this is an extension, not a rewrite:

- `("pick", kill_followed_agent)` — today's confirm path
- `("column", None)` — the new action
- `None` — cancel

Add `Button("Move to column…", id="btn-pick-column")` inside `#pick-buttons`.

**Keep `action_dismiss_dialog` returning `None`.** It is overridden precisely so
the inherited `q` / Esc binding can never yield a truthy result; that override must
survive.

**Narrow CSS.** `#pick-buttons` already stacks vertically under `.narrow`, but the
row now carries three buttons plus a checkbox in a ~40-column, very short pane. The
`#pick-confirm-row { dock: bottom }` rule is what makes the *body scroll* — not the
buttons — give up space; verify it still holds at three buttons.

### 2. `ColumnPickerModal` + `_ColumnRow` in `monitor_shared.py`

Model directly on `ChooseSiblingModal` / `_SiblingRow`. Rows render the column
swatch, title and id, and mark the task's **current** column. Dismisses a `col_id`
string or `None`.

**Every minimonitor modal ships a `.narrow` variant** — a hard convention in this
package. Implement it the same three ways every sibling does:

1. `narrow: bool = False` constructor kwarg stored as `self._narrow`;
2. `if self._narrow: self.add_class("narrow")` as the **first statement** of
   `compose()`;
3. a commented `ClassName.narrow #some-id { ... }` block at the bottom of that
   class's own `DEFAULT_CSS`.

`narrow` is a **host-role flag, not a width test** (see
`aidocs/framework/tui_conventions.md`) — do not "fix" it to call
`is_narrow_terminal`.

### 3. `minimonitor_app.py`

- `_on_pick_confirmed` routes on the action tag. The `"pick"` branch keeps today's
  body **unchanged**; `"column"` fetches the column list and pushes the picker.
- Add `_run_board_column_cmd(args)` mirroring `_run_marks_cmd`: async subprocess,
  hard timeout, kill+reap, `OSError` normalised to an error tuple. The caller treats
  the result as data and `notify()`s — it must never raise into a keypress handler.
  This is the injectable seam tests override.
- **Use `target_root`, not `self._project_root`**, for both the column list and the
  move. In multi-session mode the followed pane may belong to another project.
- On success: `self._task_cache.invalidate(target_id, sess)` then
  `notify(f"Moved t{id} -> {title}")`. `TaskInfoCache`'s `(st_mtime_ns, st_size)`
  identity gate would reject the stale entry anyway, but every explicit gesture in
  this flow invalidates first, and the sub-second same-size edge is real.
- On an `ERROR:` line or timeout: `notify(..., severity="warning")`.

## Verification Steps

```bash
bash tests/run_all_python_tests.sh     # read ONLY the last line for the verdict
python3 tests/test_minimonitor_pick_by_number.py
```

Tests to add to `tests/test_minimonitor_pick_by_number.py`:

- **AC1 anchor** — the `"pick"` branch builds the **same** `AgentCommandScreen`
  arguments as today. `SharedLaunchImplementationTests` already compares `n` and `p`
  argument-for-argument; extend that comparison rather than writing a looser one.
- `"column"` launches **no** agent.
- The seam is invoked with `target_root` when the followed pane belongs to another
  session — a cross-project negative control.
- An `ERROR:` result and a timeout each surface a warning and write nothing.
- Narrow render at 40 columns for both the now-3-button confirm row and the new
  picker, asserted on **composited screen text** (a region-fit check passes on an
  ellipsised label), each with the `.narrow`-removal negative control the file
  already uses.

## Coordination

This child touches only `monitor/`, which no other in-flight task is editing. It
depends on t1377_1's seam being committed. Live acceptance (a real ~40-column tmux
pane) is covered by the aggregate manual-verification sibling.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T14:39:15Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T15:38:27Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-05T15:40:47Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:76c8802adbc18b35

> **✅ gate:risk_evaluated** run=2026-08-05T15:40:47Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1377_2/risk_evaluated_2026-08-05T15:40:47Z-risk_evaluated-a1.log`
