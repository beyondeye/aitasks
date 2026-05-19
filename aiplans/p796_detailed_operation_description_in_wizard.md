---
Task: t796_detailed_operation_description_in_wizard.md
Base branch: main
plan_verified: []
---

# Plan: t796 — Show operation context on brainstorm Wizard steps 2+

## Context

In the `ait brainstorm` TUI's **Actions** tab, picking an operation in Step 1
launches a multi-step "Wizard" that collects parameters for that operation
(node selection, sections, config form, confirm/launch). Once the user moves
past Step 1, the wizard no longer reminds them *which* operation they picked
or *what it will do* — the only on-screen cue is the step-indicator label
like `Step 2 of 4 — Configure: Explore`. The full descriptions live in
`_OPERATION_HELP` but are only reachable from Step 1 via the `?` shortcut
(via `OperationHelpModal`).

The user wants Step 2 onwards to carry operation-context information
forward, so they don't lose track of what they're configuring. Per user
answers to clarifying questions:

- **Display style:** A one-line dim header beneath the step indicator —
  `<Label> — <brief desc>  (? for details)`. Full description stays in the
  existing `OperationHelpModal`.
- **Scope:** Apply to all wizard ops, both Design Ops (explore, compare,
  hybridize, detail, patch) and Session Lifecycle ops (pause, resume,
  finalize, archive, delete).
- **? key:** Extend the `op_help` binding so `?` opens
  `OperationHelpModal` on Step 2 onwards too, using `self._wizard_op`
  instead of the focused `OperationRow`.

## Files to modify

Only one file: `.aitask-scripts/brainstorm/brainstorm_app.py`.

## Implementation steps

### 1. Build an op-key → (label, brief description) lookup

After the `_SESSION_OPS` definition (~line 187), add a module-level dict
that flattens both op lists for O(1) lookup by op key:

```python
_OP_LABELS: dict[str, tuple[str, str]] = {
    op_key: (label, desc) for op_key, label, desc in (_DESIGN_OPS + _SESSION_OPS)
}
```

This avoids re-scanning the two lists on every step render.

### 2. Add a helper that mounts the context header

Add a method on `BrainstormApp` near the other `_actions_show_*` helpers
(after `_actions_show_step1`, ~line 4478):

```python
def _mount_op_context_header(self, container: VerticalScroll) -> None:
    """Mount a one-line dim header showing op name + brief desc.

    Called from step 2 onwards so the user remembers which operation
    they're configuring. Full description stays in OperationHelpModal,
    reachable via the `?` shortcut.
    """
    info = _OP_LABELS.get(self._wizard_op)
    if not info:
        return
    label_text, desc = info
    container.mount(
        Label(
            f"[dim]{label_text} — {desc}  (? for details)[/dim]",
            classes="actions_op_context",
        )
    )
```

### 3. Wire the helper into every Step 2+ renderer

In each of the four renderers below, call
`self._mount_op_context_header(container)` immediately after the step
indicator `Label(...)` mount:

- `_actions_show_node_select` (line ~4531) — Step 2 of node-select ops
  (explore, detail, patch).
- `_actions_show_section_select` (line ~4577) — optional Step 3.
- `_actions_show_config` (line ~4606) — config step (Step 2 for
  compare/hybridize, Step N-1 for explore/patch).
- `_actions_show_confirm` (line ~4851) — final Confirm step.

### 4. Extend the `?` binding to Step 2 onwards

Two changes:

**4a.** In `check_action` (line 2559-2566), broaden the step gate:

```python
if action == "op_help":
    try:
        tabbed = self.query_one(TabbedContent)
    except Exception:
        return None
    if tabbed.active != "tab_actions" or self._wizard_step < 1:
        return None
    return True
```

(Change `self._wizard_step != 1` → `self._wizard_step < 1`.)

**4b.** In `action_op_help` (line 3052-3067), branch on step number to
pick the op key:

```python
def action_op_help(self) -> None:
    from textual.actions import SkipAction
    if isinstance(self.screen, ModalScreen):
        raise SkipAction
    try:
        tabbed = self.query_one(TabbedContent)
    except Exception:
        raise SkipAction
    if tabbed.active != "tab_actions" or self._wizard_step < 1:
        raise SkipAction
    if self._wizard_step == 1:
        focused = self.focused
        if not isinstance(focused, OperationRow):
            raise SkipAction
        op_key = focused.op_key
    else:
        op_key = self._wizard_op
    if not op_key or op_key not in _OPERATION_HELP:
        raise SkipAction
    self.push_screen(OperationHelpModal(op_key))
```

### 5. Update the source-trace comment

The comment at line ~195 currently reads:

> Surfaced via the "?" shortcut in Actions wizard Step 1 (OperationHelpModal).

Update to reflect broader scope:

> Surfaced inline on Step 2+ (one-line header via `_mount_op_context_header`)
> and via the "?" shortcut on every wizard step (OperationHelpModal).

Also touch the comment block above `OperationHelpModal` (line ~1350) so it
no longer says "Triggered by the `?` shortcut from Step 1" — make it "from
any Actions wizard step".

### 6. Optional CSS polish

No new CSS class is strictly required — `[dim]…[/dim]` markup carries the
styling. The `classes="actions_op_context"` hook is added for forward
compatibility if a future task wants to add padding/margin; no rule is
defined in this task to keep the diff minimal.

## Notable design points

- **Reuses existing data.** Header text is built from `_DESIGN_OPS` /
  `_SESSION_OPS` (the same source used to render Step 1 rows) and full
  help from `_OPERATION_HELP` (the same source the modal already uses).
  No new content is authored; only routing changes.
- **No behavior regression for Step 1.** `check_action`/`action_op_help`
  preserve the existing step-1 path (focused-row lookup); Step 2+ takes
  the new `self._wizard_op` path.
- **Modal already supports session ops.** `_OPERATION_HELP` already has
  entries for pause/resume/finalize/archive/delete (their entries lack
  `reads_from_parent`/`produces`, which the modal's
  `_render_markdown` handles gracefully by skipping those sections).
- **No changes to non-Claude-Code skill mirrors.** This is a Python TUI
  source-code change; it does NOT touch `.claude/skills/`, so Codex /
  Gemini / OpenCode mirroring rules in `CLAUDE.md` do not apply.

## Verification

Manual TUI smoke test (no automated tests cover the wizard rendering
today):

1. **Set up an active brainstorm session** so design ops are enabled:
   ```bash
   ./ait brainstorm init <name>   # if no active session
   ```
2. **Open the Actions tab** (`ait brainstorm tui`, press `a`).
3. **Step 1 → Step 2 (node-select path):** Focus `Explore`, press Enter,
   pick a node. Confirm Step 2 (node select) shows:
   - The step indicator line.
   - A dim line `Explore — Create new design variants from a base node  (? for details)`.
4. **Press `?`** on Step 2. The `OperationHelpModal` for `explore` should
   open. Esc to close.
5. **Step 3 (section-select, optional):** If sections exist, press Enter
   on the node to advance — confirm the dim header still shows on the
   sections step.
6. **Config step:** Advance further; the dim header should remain.
7. **Confirm step:** The final step shows the same header above the
   summary block.
8. **Non-node-select ops:** Repeat for `Compare` (Step 2 = config) and
   `Hybridize` — header should show on their config + confirm steps.
9. **Session lifecycle:** From Step 1 select `Pause` (or another enabled
   lifecycle op). Confirm the confirm-step header reads
   `Pause — Pause the active session  (? for details)` and that `?`
   opens the modal.
10. **Esc back to Step 1:** The header should disappear (Step 1 still
    shows the `Select Operation` indicator, no inline header — it's
    redundant when each row already has its own label and desc).

## Step 9 (Post-Implementation)

Follow the standard task-workflow Step 9 — no special branch/worktree
created (profile `fast` → working on current branch), so the merge sub-
section is skipped; archival proceeds via `aitask_archive.sh 796`.
