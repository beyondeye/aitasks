---
Task: t753_v_shortcut_for_full_screen_view_not_shown_to_user_in_dialog.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan — t753: Surface brainstorm dashboard/dialog shortcuts and add proposal/plan export

## Context

In the `ait brainstorm` TUI, a user on the **Dashboard** tab can focus a node row and press **Enter** to open `NodeDetailModal`, a tabbed dialog (Metadata / Proposal / Plan). Inside that modal, **Shift+V** opens a fullscreen viewer with a minimap (`SectionViewerScreen`). Today both of these context-aware shortcuts are invisible to the user:

- The dialog's **Shift+V** binding is declared correctly (`Binding("V", "fullscreen_plan", "Fullscreen plan")` at `brainstorm_app.py:627`), but the modal's `compose()` does **not** yield a `Footer()` widget (lines 641–665), so no binding hints render anywhere inside the dialog. The App's footer behind the dimmed modal shows App-level bindings, not modal bindings.
- The Dashboard's **Enter → open NodeDetailModal** is implemented as a raw `on_key` handler (`brainstorm_app.py:2244–2248`), not a `Binding`, so it never appears in the App footer regardless of focus.
- There is no facility to export the proposal or plan markdown to an external file.

This task makes both shortcuts visible (as proper `Binding`s with footer-rendered labels) and adds a new context-aware `Shift+E` export shortcut in the dialog. Per user direction: the export action opens a small sub-modal with checkboxes (proposal / plan) and a directory input, the input is pre-filled with the last-used directory remembered for the lifetime of the brainstorm session.

This plan touches **only** `.aitask-scripts/brainstorm/brainstorm_app.py`.

## Files to modify

- `/home/ddt/Work/aitasks/.aitask-scripts/brainstorm/brainstorm_app.py`

## Implementation

### 1. App-level: convert the Dashboard "Enter on NodeRow" into a Binding

**Why:** A footer hint requires a real `Binding`, not just an `on_key` branch. Per the project's "TUI footer must surface keys" rule, the proper fix is to flip the on_key-only handler to a footer-visible Binding.

**Change A — `BrainstormApp.BINDINGS` (around line 1931–1945):**

Add one entry:

```python
Binding("enter", "open_node_detail", "Open detail"),
```

Place it between the tab-switching bindings and the compare bindings — keep alphabetical / logical grouping consistent with what's already there.

**Change B — `BrainstormApp._TAB_SCOPED_ACTIONS` (line 1949):**

Add:

```python
"open_node_detail": "tab_dashboard",
```

**Change C — `BrainstormApp.check_action()` (lines 1986–2013):**

After the existing `_TAB_SCOPED_ACTIONS` lookup (or as a special-cased branch like the existing `op_help` branch at 1996–2003), add a focus-type guard for `open_node_detail` so the binding is shown in the footer **only** when the Dashboard tab is active **and** the currently focused widget is a `NodeRow`. This keeps the footer accurate (the hint disappears if focus moves to the right pane, the `Tabs` strip, or the dimensions list).

```python
if action == "open_node_detail":
    try:
        tabbed = self.query_one(TabbedContent)
    except Exception:
        return None
    if tabbed.active != "tab_dashboard":
        return None
    if not isinstance(self.focused, NodeRow):
        return None
    return True
```

`check_action` already runs every render, so footer state will track focus changes naturally.

**Change D — new action method on `BrainstormApp`:**

```python
def action_open_node_detail(self) -> None:
    from textual.actions import SkipAction
    focused = self.focused
    if isinstance(focused, NodeRow):
        self.push_screen(NodeDetailModal(focused.node_id, self.session_path))
        return
    raise SkipAction()
```

`SkipAction` lets Enter on `GroupRow` / `StatusLogRow` / arbitrary widgets fall through to existing `on_key` handlers (lines 2229–2243) and Textual's default behavior (e.g., Buttons in modals).

**Change E — remove the now-redundant NodeRow branch from `BrainstormApp.on_key()`:**

Delete lines 2244–2248 (the `isinstance(focused, NodeRow)` block). Leave the surrounding `GroupRow` and `StatusLogRow` Enter handlers intact — those are out of scope for this task.

### 2. NodeDetailModal: add a Footer + relabel V + add E binding + check_action

**Change A — relabel the V binding to reflect what it actually does:**

`action_fullscreen_plan` at line 815 handles **both** Proposal and Plan tabs, but the binding label "Fullscreen plan" misleadingly suggests it's plan-only. Rename:

- `Binding("V", "fullscreen_plan", "Fullscreen plan")` → `Binding("V", "fullscreen_view", "Fullscreen view")`
- `def action_fullscreen_plan(self)` → `def action_fullscreen_view(self)` (line 815)

This is a self-contained rename inside `NodeDetailModal`; nothing else references `action_fullscreen_plan` (verified during exploration — only the binding string and the method definition).

**Change B — add the new Export binding to `NodeDetailModal.BINDINGS` (lines 624–630):**

```python
Binding("E", "export", "Export..."),
```

Place it right after the `V` binding for visual grouping in the footer.

**Change C — add `NodeDetailModal.check_action` to gate context-aware bindings:**

```python
def check_action(self, action: str, parameters) -> bool | None:
    if action in ("fullscreen_view", "export"):
        try:
            tabbed = self.query_one(TabbedContent)
        except Exception:
            return None
        if tabbed.active not in ("tab_proposal", "tab_plan"):
            return None
    return True
```

This hides both `V` and `E` from the footer when the user is on the Metadata tab (where neither makes sense). `escape`, `tab`, `home` remain visible always.

**Change D — yield a Footer inside the dialog `compose()`:**

In `NodeDetailModal.compose()` (lines 641–665), after the `Horizontal(id="node_detail_buttons")` block, add:

```python
yield Footer()
```

`Footer` is already imported (the App uses it at line 2072). The dialog is `80% × 90%` and uses `dock: top` for the title and `dock: bottom` for the buttons row; adding `Footer()` (which docks bottom by default) will stack a single-row binding strip beneath the buttons row inside the dialog. That gives the modal its own visible footer surfacing `Tab Minimap`, `V Fullscreen view`, `Home Top`, `E Export...` — the App's dimmed footer behind the modal is unaffected.

No CSS change required — Textual's auto-layout handles two `dock: bottom` siblings (they stack). If a height tweak proves necessary at implementation time, the `#node_detail_dialog` block at lines 1799–1805 is the place to adjust.

**Change E — implement `action_export()` on `NodeDetailModal`:**

```python
def action_export(self) -> None:
    tabbed = self.query_one(TabbedContent)
    active_tab = tabbed.active  # "tab_proposal" | "tab_plan" | "tab_metadata"
    # Pre-check the active tab; user can adjust in the modal.
    default_proposal = active_tab == "tab_proposal" or active_tab == "tab_metadata"
    default_plan = active_tab == "tab_plan" or active_tab == "tab_metadata"
    last_dir = getattr(self.app, "_last_export_dir", None) or str(Path.cwd())
    self.app.push_screen(
        ExportNodeDetailModal(
            node_id=self.node_id,
            task_num=self.app.task_num,
            proposal_text=self._proposal_text,
            plan_text=self._plan_text,
            default_proposal=default_proposal,
            default_plan=default_plan,
            default_dir=last_dir,
        ),
        callback=self._on_export_done,
    )

def _on_export_done(self, result) -> None:
    if not result:
        return
    # result = {"dir": str, "written": [paths]}
    self.app._last_export_dir = result["dir"]
    paths = result["written"]
    if paths:
        self.notify("Exported:\n" + "\n".join(paths), timeout=6)
```

### 3. Extract pure helpers (testability)

Add **module-level** pure functions in `brainstorm_app.py` near the top (next to `_next_checkbox_index`, around line 1156 / wherever the existing helper sits — verify exact location during implementation). These are reused by the modal and exercised directly by unit tests.

```python
def _dialog_export_visible(active_tab: str) -> bool:
    """check_action helper: V (fullscreen_view) and E (export) are shown only
    on Proposal / Plan tabs of NodeDetailModal."""
    return active_tab in ("tab_proposal", "tab_plan")


def _open_node_detail_visible(active_tab: str, focused_is_node_row: bool) -> bool:
    """check_action helper: Enter Open-detail is shown only when the
    Dashboard tab is active AND a NodeRow is currently focused."""
    return active_tab == "tab_dashboard" and focused_is_node_row


def _validate_export_dir(dir_str: str) -> tuple[Path | None, str | None]:
    """Resolve and ensure the export directory exists.

    Returns (path, None) on success, (None, error_message) on failure.
    Trailing/leading whitespace is stripped; ~ is expanded.
    """
    s = (dir_str or "").strip()
    if not s:
        return None, "Output directory is required"
    target = Path(s).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, f"Cannot create directory: {exc}"
    if not target.is_dir():
        return None, f"Not a directory: {target}"
    return target, None


def _export_filename(task_num: str, node_id: str, kind: str) -> str:
    """kind is 'proposal' or 'plan'."""
    return f"brainstorm_t{task_num}_{node_id}_{kind}.md"


def _write_node_exports(
    target_dir: Path,
    task_num: str,
    node_id: str,
    proposal_text: str,
    plan_text: str,
    do_proposal: bool,
    do_plan: bool,
) -> list[str]:
    """Write requested files to target_dir. Returns list of written paths.

    Raises OSError on write failure (caller surfaces via notify).
    """
    written: list[str] = []
    if do_proposal:
        p = target_dir / _export_filename(task_num, node_id, "proposal")
        p.write_text(proposal_text, encoding="utf-8")
        written.append(str(p))
    if do_plan:
        p = target_dir / _export_filename(task_num, node_id, "plan")
        p.write_text(plan_text, encoding="utf-8")
        written.append(str(p))
    return written
```

The `check_action` branches in step 1 (Change C) and step 2 (Change C) should call these helpers rather than inlining the logic.

### 4. New `ExportNodeDetailModal` class

Add a new `ModalScreen` subclass in `brainstorm_app.py` immediately after `NodeDetailModal` (so it sits next to its only caller). It's a small, self-contained dialog.

**Class skeleton:**

```python
class ExportNodeDetailModal(ModalScreen):
    """Modal: pick what to export (proposal/plan) and the output directory."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        node_id: str,
        task_num: str,
        proposal_text: str,
        plan_text: str,
        default_proposal: bool,
        default_plan: bool,
        default_dir: str,
    ):
        super().__init__()
        self.node_id = node_id
        self.task_num = task_num
        self._proposal_text = proposal_text
        self._plan_text = plan_text
        self._default_proposal = default_proposal and bool(proposal_text)
        self._default_plan = default_plan and bool(plan_text)
        self._default_dir = default_dir

    def compose(self) -> ComposeResult:
        with Container(id="export_modal_dialog"):
            yield Label(
                f"Export node detail: {self.node_id}",
                id="export_modal_title",
            )
            yield Label("Output directory:")
            yield Input(
                value=self._default_dir,
                placeholder="/path/to/dir",
                id="export_modal_dir",
            )
            yield Checkbox(
                f"Proposal{'' if self._proposal_text else ' (empty)'}",
                value=self._default_proposal,
                id="export_modal_chk_proposal",
                disabled=not self._proposal_text,
            )
            yield Checkbox(
                f"Plan{'' if self._plan_text else ' (empty)'}",
                value=self._default_plan,
                id="export_modal_chk_plan",
                disabled=not self._plan_text,
            )
            with Horizontal(id="export_modal_buttons"):
                yield Button("Export", variant="primary", id="btn_export_ok")
                yield Button("Cancel", variant="default", id="btn_export_cancel")
            yield Footer()

    @on(Button.Pressed, "#btn_export_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_export_ok")
    def _confirm(self) -> None:
        dir_str = self.query_one("#export_modal_dir", Input).value.strip()
        do_proposal = self.query_one("#export_modal_chk_proposal", Checkbox).value
        do_plan = self.query_one("#export_modal_chk_plan", Checkbox).value
        if not (do_proposal or do_plan):
            self.notify("Select at least one of Proposal / Plan", severity="warning")
            return
        if not dir_str:
            self.notify("Output directory is required", severity="warning")
            return
        target = Path(dir_str).expanduser()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.notify(f"Cannot create directory: {exc}", severity="error")
            return
        if not target.is_dir():
            self.notify(f"Not a directory: {target}", severity="error")
            return
        written: list[str] = []
        try:
            if do_proposal:
                p = target / f"brainstorm_t{self.task_num}_{self.node_id}_proposal.md"
                p.write_text(self._proposal_text, encoding="utf-8")
                written.append(str(p))
            if do_plan:
                p = target / f"brainstorm_t{self.task_num}_{self.node_id}_plan.md"
                p.write_text(self._plan_text, encoding="utf-8")
                written.append(str(p))
        except OSError as exc:
            self.notify(f"Write failed: {exc}", severity="error")
            return
        self.dismiss({"dir": str(target), "written": written})
```

**Imports to verify / add at the top of `brainstorm_app.py`:**

- `Footer` — already imported (used at line 2072).
- `Checkbox`, `Input` — verify they are imported from `textual.widgets`. If not, add them to the existing `textual.widgets` import line.
- `Path` from `pathlib` — already imported.
- `on` decorator — already used in `NodeDetailModal.close_detail` at line 836.

The `_confirm` method should reuse the helpers from step 3 — call `_validate_export_dir(...)` to handle path validation/creation, then call `_write_node_exports(...)` inside a try/except OSError to write files and produce the `written` list. This keeps the modal thin and the logic testable.

**CSS for the export modal** — add to the App's CSS block (the same block that contains `#node_detail_dialog` at line 1799). Mirror the launch-mode modal style at lines 1832–1844:

```css
#export_modal_dialog {
    width: 60;
    height: auto;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}

#export_modal_title {
    text-style: bold;
    text-align: center;
    width: 100%;
    padding-bottom: 1;
}

#export_modal_buttons {
    height: 3;
    align: center middle;
    padding-top: 1;
}
```

### 5. Session memory for last export directory

In `BrainstormApp.__init__` (around line 1954), add:

```python
self._last_export_dir: str | None = None
```

Place it near the other lightweight session-state attributes (e.g., `self._expanded_groups`). It's read/written by `NodeDetailModal._on_export_done` and `NodeDetailModal.action_export` and persists for the brainstorm app's lifetime — exactly the "remember for this session, in memory" behavior the user requested.

## Automated tests

Add a new test file `tests/test_brainstorm_node_export.py` following the established pattern of `tests/test_brainstorm_compare_modal.py` (pure-logic helpers) and `tests/test_brainstorm_init_failure_modal.py` (modal smoke tests + helper coverage). All tests are pytest/unittest-compatible and live alongside the rest of the project's Python tests.

The file imports the new helpers and the new `ExportNodeDetailModal` class:

```python
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import (  # noqa: E402
    ExportNodeDetailModal,
    _dialog_export_visible,
    _export_filename,
    _open_node_detail_visible,
    _validate_export_dir,
    _write_node_exports,
)
```

### Test classes

1. **`DialogExportVisibleTests`** — `_dialog_export_visible`:
   - Returns `True` for `"tab_proposal"`, `"tab_plan"`.
   - Returns `False` for `"tab_metadata"`, `""`, arbitrary unknown ids (e.g., `"tab_other"`).

2. **`OpenNodeDetailVisibleTests`** — `_open_node_detail_visible`:
   - Returns `True` only when `active_tab == "tab_dashboard" and focused_is_node_row is True`.
   - Returns `False` for any other tab regardless of focus flag.
   - Returns `False` for `tab_dashboard` when focus flag is `False`.

3. **`ExportFilenameTests`** — `_export_filename`:
   - `_export_filename("753", "init_001", "proposal") == "brainstorm_t753_init_001_proposal.md"`.
   - Same for `kind="plan"`.

4. **`ValidateExportDirTests`** — `_validate_export_dir`:
   - Empty string → `(None, "Output directory is required")`.
   - Whitespace-only string → same as empty.
   - Path that doesn't exist but parent is writable → `mkdir -p`s it, returns `(Path, None)`.
   - Path that already exists as a directory → returns `(Path, None)` without error.
   - Path that exists as a regular file → `(None, "Not a directory: ...")`. Use `tempfile.NamedTemporaryFile` to set up.
   - Path with `~` → expansion happens (compare resolved path against `Path.home()` prefix).

5. **`WriteNodeExportsTests`** — `_write_node_exports` (uses `tempfile.TemporaryDirectory`):
   - Both flags True → both files written, list contains both paths in deterministic order (proposal first, plan second).
   - Only proposal True → only `*_proposal.md` written; no `*_plan.md` exists.
   - Only plan True → only `*_plan.md` written.
   - Both flags False → empty list, no files written.
   - File contents exactly match the input strings (including newlines, unicode).
   - Filenames follow the `brainstorm_t<task>_<node>_<kind>.md` convention.

6. **`ExportNodeDetailModalSmokeTests`** — instantiation only (mirror `InitFailureModalSmokeTests`):
   - Construct with `proposal_text="..."`, `plan_text=""`, `default_proposal=True`, `default_plan=True`.
     - The default-plan flag should be coerced to `False` because `plan_text` is empty (`self._default_plan = default_plan and bool(plan_text)`).
   - Construct with both texts non-empty and both default flags True → both stored as `True`.
   - `node_id`, `task_num`, `_default_dir` round-trip unchanged.

### Wiring tests into the runner

`tests/run_all_python_tests.sh` typically discovers `test_*.py` files automatically (verify by reading it during implementation). If discovery is automatic, no further wiring is needed. If it's an explicit list, append `test_brainstorm_node_export.py` to the list.

### Running the tests

```bash
python3 -m pytest tests/test_brainstorm_node_export.py -v
# or
python3 -m unittest tests.test_brainstorm_node_export
```

Both forms must pass before the implementation is considered complete.

## Verification

1. **Build/syntax check** — `python3 -c "import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_app.py').read())"`
2. **Launch brainstorm on an existing crew** with `./ait brainstorm <task_num>` against a session that has at least one node with a proposal and plan generated.
3. **Dashboard tab footer** — focus the Dashboard tab, focus a `NodeRow` with arrow keys; the App footer must show `Enter Open detail`. Move focus off the row (e.g., Tab to the right pane) — the hint must disappear.
4. **Enter still works on GroupRow / StatusLogRow** — switch to the Status tab, focus a `GroupRow` and press Enter; group must expand/collapse as before. Focus a `StatusLogRow`, press Enter; `LogDetailModal` must open as before.
5. **NodeDetailModal footer** — press Enter on a `NodeRow`; the dialog opens. Its footer (inside the modal) must show `Tab Minimap`, `V Fullscreen view`, `Home Top` on the Proposal/Plan tabs and additionally `E Export...`. Switch to the Metadata tab — `V` and `E` must disappear from the footer; `Tab` and `Home` remain.
6. **Fullscreen view via V** — on the Proposal tab, press `Shift+V`; `SectionViewerScreen` must open with the proposal markdown + minimap. Repeat on Plan tab.
7. **Export flow — proposal only** — on the Proposal tab, press `Shift+E`; the export modal opens with the directory pre-filled to cwd, `Proposal` pre-checked, `Plan` unchecked. Click Export. Verify `brainstorm_t<task>_<node>_proposal.md` exists in cwd with the proposal markdown content.
8. **Export flow — both** — open `Shift+E` again; the directory should now be pre-filled to whatever was used last (cwd in step 7). Edit the dir to a fresh path (e.g., `/tmp/bt_export_<id>`), check both Proposal and Plan, click Export. Verify the directory was created (`mkdir -p` style) and both `*_proposal.md` and `*_plan.md` exist with the right contents.
9. **Export flow — third invocation** — open `Shift+E` once more; the directory must be pre-filled to the path from step 8 (session memory).
10. **Export — empty content** — find a node whose plan has not been generated (proposal returns `*No plan generated.*`); press `Shift+E` — the Plan checkbox should be disabled and labeled `Plan (empty)`.
11. **Export — invalid dir** — type a path with no write permissions; click Export — a clear error notify should appear and the modal must stay open.
12. **Export — cancel** — open the modal, press Esc or click Cancel; nothing must be written and no `_last_export_dir` change should happen if no Export ever succeeded prior.

## Step 9 (Post-Implementation)

After review and approval, follow Step 9 of `task-workflow/SKILL.md` for archival. Plan file path will be `aiplans/p753_v_shortcut_for_full_screen_view_not_shown_to_user_in_dialog.md`.
