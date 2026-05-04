---
Task: t737_better_labels_in_brainstorm_patch.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Better labels in brainstorm patch wizard step 3

## Context

In `ait brainstorm`, step 3 of the patch-operation wizard renders the patch
request input as a bare `[bold]Patch Request[/]` label sitting above an empty
TextArea. From the user's perspective:

1. The label looks like a section title, not an instruction. There is no
   visible cue that the empty box below is the field where the patch request
   must be typed.
2. The Next button is always enabled. If the user clicks it with an empty
   TextArea, they only learn the field is required *after* the click via a
   `notify(..., severity="warning")` toast at `_actions_collect_config`
   (line 3152–3154). The button's enabled state should mirror the actual
   precondition.

This task tightens both UX gaps for the patch wizard specifically (the
mandate / merge-rules wizard steps have the same pattern, but they are out of
scope per the task description and `feedback_extract_new_procedures_to_own_file`
discipline — keep scope tight).

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` (the only code file touched)

## Code changes

### 1. `_config_patch_no_node` (lines 3039–3045)

Make the input affordance unambiguous and start the Next button disabled:

```python
def _config_patch_no_node(self, container: VerticalScroll) -> None:
    """Patch config (node already selected): patch request."""
    node_id = self._wizard_config.get("_selected_node", "?")
    container.mount(Label(f"[bold]Node:[/] {node_id}"))
    container.mount(
        Label("[bold]Patch Request[/] — describe the change to apply to this node")
    )
    container.mount(
        Label("[dim]Type your patch request in the text area below.[/]")
    )
    container.mount(TextArea("", classes="ta_patch_request"))
    container.mount(
        Button(
            "Next ▶",
            variant="primary",
            classes="btn_actions_next",
            disabled=True,
        )
    )
```

Three changes:
- The bold label gains a trailing instructional clause so it reads as a
  prompt rather than a section title.
- A `[dim]` helper line explicitly points at the TextArea below
  (matches the existing `[dim]...` hint convention used at line 2877 for node
  navigation and line 2923 for section selection).
- The TextArea gets `classes="ta_patch_request"` so the new `Changed` handler
  can target it without affecting the mandate / merge-rules TextAreas in
  sibling wizard steps.
- The Next button starts `disabled=True`, mirroring the node-select step
  (line 2896) where Next is also disabled until input is provided.

### 2. New TextArea.Changed handler

Add a method on `BrainstormApp` (place it next to the existing
`@on(Button.Pressed, ".btn_actions_next")` handler at lines 3297–3332 to keep
wizard handlers grouped):

```python
@on(TextArea.Changed, ".ta_patch_request")
def _on_patch_request_changed(self, event: TextArea.Changed) -> None:
    """Enable Next button only when the patch request TextArea is non-empty."""
    has_text = bool(event.text_area.text.strip())
    try:
        self.query_one(".btn_actions_next", Button).disabled = not has_text
    except Exception:
        pass
```

Notes on the handler:
- Uses `text.strip()` so whitespace-only input does not falsely enable Next.
  This matches the validation in `_actions_collect_config` at line 3151
  (`config["patch_request"] = container.query_one(TextArea).text.strip()`).
- The CSS-selector form `.ta_patch_request` scopes the listener to the patch
  TextArea only — explore mandate and hybridize merge-rules TextAreas are
  unaffected.
- The `try/except` mirrors the existing defensive `query_one` pattern at
  lines 2647–2650 / 3382–3385.
- `TextArea` is already imported at line 33 and `on` at line 35, so no new
  imports are needed.

## Behavior after change

- When the patch wizard reaches step 3 (config), the TextArea is clearly
  marked as the input field and the Next button is greyed out.
- As soon as the user types at least one non-whitespace character, Next
  becomes enabled. Clearing the field (or leaving only whitespace) re-disables
  it.
- The existing `notify("Patch request cannot be empty", severity="warning")`
  fallback in `_actions_collect_config` remains as defense-in-depth (Next
  pressed via keyboard shortcut without focus, etc.).

## Verification

1. Manual TUI verification (primary — this is a Textual TUI behavior):
   ```bash
   ./.aitask-scripts/aitask_brainstorm_tui.sh
   ```
   Pick or create a brainstorm session with at least one node, navigate to
   the Actions tab, choose the **Patch** operation, advance to step 2 and
   pick a node, then advance to step 3 (Configure: Patch). Verify:
   - The instructional label and `[dim]` hint are visible.
   - The Next button starts disabled (greyed out).
   - Typing a single character enables Next.
   - Deleting all characters (or leaving only spaces) re-disables Next.
   - Clicking Next with content advances to the confirm step as before.

2. Regression check on sibling wizard ops — the class-scoped handler must
   not affect them:
   - Pick **Explore** op → step 3 (mandate) Next button still behaves as
     before (always enabled at mount).
   - Pick **Hybridize** op → step 2 (merge rules) Next button still behaves
     as before.

3. Existing automated tests:
   ```bash
   bash tests/test_brainstorm_cli.sh
   ```
   ```bash
   /home/ddt/.aitask/venv/bin/python -m pytest tests/test_brainstorm_wizard_sections.py -v
   ```
   Both should still pass — no signatures or pure-logic helpers change.

4. Lint:
   ```bash
   shellcheck .aitask-scripts/aitask_*.sh  # no shell changes, sanity-check only
   ```

## Step 9 (Post-Implementation) reference

After review and commit, follow the standard archival flow per
`.claude/skills/task-workflow/SKILL.md` Step 9 (no separate branch — current
branch). Run the project's `verify_build` if configured, then
`./.aitask-scripts/aitask_archive.sh 737`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Two edits inside
  `.aitask-scripts/brainstorm/brainstorm_app.py`:
  1. `_config_patch_no_node` (around line 3039) — replaced the bare
     `[bold]Patch Request[/]` label with an instructional bold label
     ("Patch Request — describe the change to apply to this node") plus a
     `[dim]` helper line ("Type your patch request in the text area below.").
     The TextArea now carries `classes="ta_patch_request"` and the Next button
     is mounted with `disabled=True`.
  2. New `@on(TextArea.Changed, ".ta_patch_request") _on_patch_request_changed`
     handler placed immediately after `_on_actions_next` (around line 3346).
     Toggles `.btn_actions_next` `disabled` based on `event.text_area.text.strip()`.
- **Deviations from plan:** None.
- **Issues encountered:** None. The decorator + class-scoped CSS selector
  pattern was already in use elsewhere in the file (e.g. the existing
  `@on(Button.Pressed, ".btn_actions_next")` handler), so no new imports were
  needed.
- **Key decisions:** Kept scope tight to the patch wizard only. Explore-mandate
  and hybridize-merge-rules wizard steps share the same UX pattern but were
  intentionally not modified per the task description; if the user wants the
  same treatment there, those should be follow-up tasks rather than scope
  creep here.
- **Upstream defects identified:** None.
- **Verification performed:**
  - Static: `python -c "import ast; ast.parse(...)"` passes; full module
    imports cleanly via `BrainstormApp` and the new method is present.
  - Unit tests: all 76 brainstorm unit tests pass
    (`test_brainstorm_dag`, `test_brainstorm_sections`, `test_brainstorm_schemas`,
    `test_brainstorm_session`, `test_brainstorm_wizard_sections`).
  - Manual TUI verification: deferred to the user — the implementing agent
    cannot drive Textual TUIs interactively from a non-TTY shell. The
    "Verification" section above documents the steps to run.
