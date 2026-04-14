---
Task: t461_4_brainstorm_status_edit.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md, aiplans/archived/p461/p461_2_*.md, aiplans/archived/p461/p461_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_4 — Brainstorm status-tab: edit `launch_mode` on an agent

## Context

Task 461 adds interactive launch mode for agentcrew code agents.
Sibling t461_1 added the `launch_mode` schema + runner branch; t461_2
added the `ait crew setmode` CLI; t461_3 added the brainstorm wizard
toggle (sets mode at agent creation time).

This task closes the remaining gap: let the user change the launch
mode of an **existing** agent from inside the brainstorm TUI, without
leaving to the shell. Typical flow: the user creates an agent headless
via the wizard, then decides mid-session "I want to watch this one
live" — they focus the agent row on the Status tab, press `e`, pick
Interactive, and the next runner tick launches that agent in a tmux
window.

The TUI mutation path must shell out to `ait crew setmode` (not
rewrite the yaml directly), so CLI and TUI share a single mutation
code path, validation set, and commit audit trail.

## Goal

- Press `e` on a focused `AgentStatusRow` in the brainstorm Status tab
  → open a modal showing current mode and two buttons (Headless /
  Interactive).
- Modal dismiss → `./ait crew setmode` is invoked; on success, toast
  + delayed refresh of the status tab; on failure, error toast with
  stderr.
- Read-only modal for non-Waiting agents (setmode would refuse
  anyway), with an explanatory line.
- Row help hint `(e: edit mode)` appears when a Waiting agent is
  focused (matching the existing `(w: reset)` hint pattern).

Note: A `[interactive]` badge on the row label is **out of scope for
this task** — rows currently don't cache `launch_mode`, adding it
requires plumbing through `_mount_agent_row()` → `AgentStatusRow`
which bloats the change. The modal itself already shows current mode
on open, which is where users actually check. A follow-up task can
add the badge if it turns out to be needed.

## Files to modify

1. `.aitask-scripts/brainstorm/brainstorm_app.py` — all changes are
   in this file:
   - New `AgentModeEditModal` class (near `NodeDetailModal`, ~line 181)
   - `AgentStatusRow.render()` (lines 534-538) — conditional hint for
     Waiting agents
   - `BrainstormApp.on_key()` (~line 1159) — new `e` key branch after
     the `w` branch
   - New `_edit_agent_mode()` method on `BrainstormApp` (near
     `_reset_agent`, ~line 1539)
   - New callback `_on_mode_edit_result()` on `BrainstormApp`
   - Small CSS block for `#mode_modal_dialog` (near `#node_detail_dialog`
     CSS)

No other files need to change. `ait crew setmode` (t461_2) already
supplies the mutation + commit; `read_yaml` (from
`agentcrew.agentcrew_utils`) is already imported.

## Key facts verified against the current codebase

- `AgentStatusRow` — lines 524-548, `class AgentStatusRow(Static,
  can_focus=True)`, fields `agent_name`, `agent_status`, `crew_id`,
  `_display_line`. **No class-level `BINDINGS`** — keybindings for
  focused rows are handled centrally in `BrainstormApp.on_key()`.
- `BrainstormApp.on_key()` — the `w` key handler is at lines 1159-1172
  and is the template to mirror for `e`.
- `_reset_agent()` — lines 1539-1553. Uses `self.session_path` (Path),
  `update_yaml_field`, then calls `self._delayed_refresh_status()`
  which schedules `self._refresh_status_tab` after 2 seconds.
- `NodeDetailModal` — lines 181-267, uses `ModalScreen`, `Container`,
  `Horizontal`, `Label`, `Button`, `Static`. **`Vertical` is NOT
  imported** — the imports block at lines 17-36 has only `Container`,
  `Horizontal`, `VerticalScroll` from `textual.containers`.
- `read_yaml` is already imported from `agentcrew.agentcrew_utils`
  (line 67). **Do not `import yaml`** — use `read_yaml(str(path))`.
- `AIT_PATH` module constant exists at line 92:
  `str(Path(__file__).resolve().parent.parent.parent / "ait")`.
- `BrainstormApp` attributes: `self.session_path` (Path, not
  `session_dir`), `self.session_data` (dict; `crew_id` is
  `self.session_data.get("crew_id", "")`). There is no
  `self.repo_root` — use `AIT_PATH`'s parent directory if a cwd is
  needed, or simply omit `cwd=` and rely on the default (setmode
  resolves the crew via its own lookup, so cwd does not matter).
- `ait crew setmode` CLI — flags `--crew`, `--name`, `--mode`; stdout
  `UPDATED:<name>:<mode>` on success; non-zero exit + stderr message
  when the agent is not in Waiting state. Verified at
  `.aitask-scripts/aitask_crew_setmode.sh`.
- Agent status yaml carries `launch_mode` (added by t461_1's
  `aitask_crew_addwork.sh`), between `group:` and `status:`.

## Implementation steps

### 1. New class `AgentModeEditModal`

Insert immediately after `NodeDetailModal` (around line 268), before
`class ConfirmDialog`. Use `Container` (not `Vertical`), mirror
`NodeDetailModal`'s compose/CSS structure.

```python
class AgentModeEditModal(ModalScreen):
    """Modal to toggle an agent's launch_mode between headless and interactive."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        agent_name: str,
        agent_status: str,
        current_mode: str,
    ):
        super().__init__()
        self.agent_name = agent_name
        self.agent_status = agent_status
        self.current_mode = current_mode

    def compose(self) -> ComposeResult:
        with Container(id="mode_modal_dialog"):
            yield Label(
                f"Launch mode: {self.agent_name}",
                id="mode_modal_title",
            )
            yield Static(
                f"Current: [bold]{self.current_mode}[/bold]  "
                f"Status: {self.agent_status}",
                id="mode_modal_current",
            )
            if self.agent_status != "Waiting":
                yield Static(
                    "[dim]launch_mode can only be changed on Waiting agents. "
                    "Close this dialog and reset the agent first if needed.[/]",
                    id="mode_modal_note",
                )
                with Horizontal(id="mode_modal_buttons"):
                    yield Button("Close", variant="default", id="btn_mode_close")
            else:
                with Horizontal(id="mode_modal_buttons"):
                    yield Button(
                        "Headless",
                        variant="primary" if self.current_mode == "headless" else "default",
                        id="btn_mode_headless",
                    )
                    yield Button(
                        "Interactive",
                        variant="primary" if self.current_mode == "interactive" else "default",
                        id="btn_mode_interactive",
                    )
                    yield Button("Cancel", variant="default", id="btn_mode_cancel")

    @on(Button.Pressed, "#btn_mode_headless")
    def _pick_headless(self) -> None:
        self.dismiss("headless")

    @on(Button.Pressed, "#btn_mode_interactive")
    def _pick_interactive(self) -> None:
        self.dismiss("interactive")

    @on(Button.Pressed, "#btn_mode_cancel")
    @on(Button.Pressed, "#btn_mode_close")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

The dismiss value is the selected mode string, or `None` on cancel/
close/non-Waiting.

### 2. `AgentStatusRow.render()` — conditional hint for Waiting agents

Update lines 534-538 to also show the `e: edit mode` hint when the
focused agent is in Waiting state. Keep the existing Error/reset hint
untouched:

```python
def render(self) -> str:
    line = self._display_line
    if self.has_focus:
        if self.agent_status == "Error":
            line += "  [dim](w: reset)[/dim]"
        elif self.agent_status == "Waiting":
            line += "  [dim](e: edit mode)[/dim]"
    return line
```

The hint is only shown for Waiting agents, which matches the actual
capability of setmode and avoids promising a feature that will reject.

### 3. `BrainstormApp.on_key()` — new `e` key branch

Insert immediately after the existing `w` branch (after line 1172):

```python
        # e: edit launch_mode on a Waiting agent
        if event.key == "e":
            focused = self.focused
            if isinstance(focused, AgentStatusRow):
                if focused.agent_status != "Waiting":
                    self.notify(
                        f"Can only edit launch_mode on Waiting agents "
                        f"(current: {focused.agent_status})",
                        severity="warning",
                    )
                else:
                    self._edit_agent_mode(focused)
                event.prevent_default()
                event.stop()
                return
```

### 4. `BrainstormApp._edit_agent_mode()` — push the modal

Insert near `_reset_agent` (around line 1539). Reads the current mode
from the status yaml using the already-imported `read_yaml`, then
pushes the modal with a callback:

```python
    def _edit_agent_mode(self, row: "AgentStatusRow") -> None:
        """Open the launch_mode edit modal for a Waiting agent row."""
        import os

        name = row.agent_name
        sf = os.path.join(str(self.session_path), f"{name}_status.yaml")
        if not os.path.isfile(sf):
            self.notify(
                f"Status file not found for {name}",
                severity="error",
            )
            return
        data = read_yaml(sf) or {}
        current_mode = data.get("launch_mode", "headless")
        status = data.get("status", row.agent_status)
        self.push_screen(
            AgentModeEditModal(
                agent_name=name,
                agent_status=status,
                current_mode=current_mode,
            ),
            lambda result, _name=name, _current=current_mode:
                self._on_mode_edit_result(_name, _current, result),
        )
```

The lambda captures `name` and `current_mode` so the callback can
no-op when the user picked the same mode (idempotent; the CLI
would also no-op but we avoid a subprocess round-trip).

### 5. `BrainstormApp._on_mode_edit_result()` — apply via setmode CLI

Insert immediately after `_edit_agent_mode`:

```python
    def _on_mode_edit_result(
        self, agent_name: str, current_mode: str, new_mode
    ) -> None:
        """Callback after AgentModeEditModal closes."""
        if new_mode is None or new_mode == current_mode:
            return
        crew_id = self.session_data.get("crew_id", "")
        if not crew_id:
            self.notify("No crew_id in session", severity="error")
            return
        try:
            result = subprocess.run(
                [
                    AIT_PATH, "crew", "setmode",
                    "--crew", crew_id,
                    "--name", agent_name,
                    "--mode", new_mode,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as e:
            self.notify(f"setmode failed to launch: {e}", severity="error")
            return
        if result.returncode == 0 and f"UPDATED:{agent_name}:{new_mode}" in result.stdout:
            self.notify(f"Launch mode → {new_mode} for {agent_name}")
            self._delayed_refresh_status()
        else:
            err = (result.stderr or result.stdout).strip() or "unknown error"
            self.notify(f"setmode failed: {err}", severity="error")
```

Notes:
- `subprocess` is already imported at the top of the file (line 5).
- `AIT_PATH` is the module constant at line 92.
- No `cwd=` is passed: setmode uses `resolve_crew` to find the
  worktree, which does not depend on cwd.
- Success path calls `_delayed_refresh_status()` — reuses the same
  2-second refresh used by `_reset_agent`, so the Status tab picks up
  the new value. The modal has already dismissed by the time this
  runs.

### 6. CSS for the modal

Find the existing CSS block that styles `#node_detail_dialog`
(grep for `#node_detail_dialog` in `brainstorm_app.py`). Add a
sibling block near it:

```css
#mode_modal_dialog {
    align: center middle;
    width: 60;
    height: auto;
    padding: 1 2;
    background: $surface;
    border: solid $primary;
}

#mode_modal_title {
    text-style: bold;
    padding-bottom: 1;
}

#mode_modal_current {
    padding-bottom: 1;
}

#mode_modal_note {
    padding-bottom: 1;
}

#mode_modal_buttons {
    height: auto;
    align: center middle;
}

#mode_modal_buttons Button {
    margin: 0 1;
}
```

Match the exact CSS indentation and selectors used by the existing
`#node_detail_dialog` block — copy-paste and tweak rather than
inventing new style rules.

## Verification

### Static

1. `python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py` — must pass.
2. `python3 -c "import sys; sys.path.insert(0, '.aitask-scripts'); import brainstorm.brainstorm_app as ba; assert hasattr(ba, 'AgentModeEditModal'); assert hasattr(ba.BrainstormApp, '_edit_agent_mode'); assert hasattr(ba.BrainstormApp, '_on_mode_edit_result'); print('OK')"` — smoke import.

### Manual (requires a live brainstorm crew with a Waiting agent)

3. `./ait brainstorm <task>` on a task whose session has at least one
   Waiting agent (e.g., create an explorer and do not start the
   runner yet).
4. Switch to the Status tab. Focus the agent row via arrow/tab.
5. Confirm the help hint `(e: edit mode)` appears next to the row.
6. Press `e`. The modal opens; current mode is shown; `Headless` and
   `Interactive` buttons appear, with the current one styled as
   primary.
7. Click `Interactive` (or use keyboard). The modal dismisses. Toast:
   "Launch mode → interactive for \<name\>". 2 seconds later the
   status tab re-renders.
8. Verify the yaml: `grep launch_mode .aitask-crews/crew-<id>/<name>_status.yaml`
   → `launch_mode: interactive`.
9. Verify the commit: `cd .aitask-crews/crew-<id> && git log -1`
   → message contains `Set launch_mode=interactive`.
10. Press `e` again on the same (now interactive) row. Modal opens
    with Interactive styled primary. Click Cancel. No toast, no
    commit.
11. Click the row through to a Running state (start the runner briefly
    or synthetically set status=Running in yaml). Press `e`. Modal
    opens in read-only form with the explanatory note and a single
    Close button. Close it; no mutation.
12. Rename `aitask_crew_setmode.sh` temporarily and press `e` on a
    Waiting agent, pick Interactive. Confirm an error toast appears
    and the app does not crash.

### Regression

13. Press `w` on an Error-state agent; confirm the reset flow still
    works unchanged.
14. Existing brainstorm tests are smoke-only (py_compile); ensure the
    py_compile step above still passes.

## Step 9 — Post-implementation

- No worktree created — work is on `main`.
- On commit, follow the standard task-workflow Step 9 archival via
  `./.aitask-scripts/aitask_archive.sh 461_4`. Commit message for the
  code change: `feature: Add launch_mode edit modal to brainstorm status tab (t461_4)`.
- The child plan file will be archived to `aiplans/archived/p461/`
  by the archive script. `t461_5` is next in line (it depends on
  `t461_4`).

## Dependencies

- t461_2 (merged) — provides `ait crew setmode`. The modal only
  works because this CLI exists.
- t461_1 (merged) — provides the `launch_mode` yaml field that the
  modal reads.

## Notes for sibling tasks (t461_5, t461_6)

- The modal reads `launch_mode` fresh from yaml each time via
  `read_yaml` — so once t461_5 ships per-type defaults, the modal
  will automatically reflect whatever effective mode the runner would
  use (because t461_5 stores the effective value in the same yaml).
- If t461_6 (ANSI log viewer) wants to bind its own key on
  `AgentStatusRow`, follow the same pattern: add a branch in
  `BrainstormApp.on_key()` after the `e` branch, not a class-level
  `BINDINGS` on the row. The row has no BINDINGS; all focused-row
  keybindings go in `on_key()`.
- A `[interactive]` badge on the row label was considered and
  deliberately left out of this task to keep the diff minimal. If
  t461_6 adds a `launch_mode` field to `AgentStatusRow` (e.g. to
  show its own badge or to decide whether to offer log tail), this
  task's edit flow will pick up the cached value "for free" since
  `_delayed_refresh_status` re-mounts all rows.

## Final Implementation Notes

- **Actual work done:** All 6 edits to
  `.aitask-scripts/brainstorm/brainstorm_app.py` as planned, no other
  files touched. Diff: +173/-2.
  1. New `AgentModeEditModal(ModalScreen)` inserted after
     `NodeDetailModal` (uses `Container`/`Horizontal` from the
     already-imported textual.containers, `@on(Button.Pressed, ...)`
     decorators to dispatch dismiss values).
  2. `AgentStatusRow.render()` extended with an `elif` for the
     Waiting state that appends `  [dim](e: edit mode)[/dim]`. The
     existing `if ... == "Error"` branch is preserved unchanged.
  3. New `e` key branch in `BrainstormApp.on_key()`, mirroring the
     `w` branch exactly (same shape, same warn-on-wrong-state
     pattern, same `event.prevent_default(); event.stop(); return`).
  4. `_edit_agent_mode()` reads the status yaml via `read_yaml`
     (already imported at line 67), extracts `launch_mode` (default
     `"headless"`) and `status`, and pushes
     `AgentModeEditModal` with a lambda callback that captures the
     current mode so the callback can no-op when the user picks the
     same mode.
  5. `_on_mode_edit_result()` shells out to `AIT_PATH, "crew",
     "setmode", ...` with `capture_output=True, text=True,
     check=False`, checks for `UPDATED:<name>:<mode>` in stdout, and
     either toasts success + `_delayed_refresh_status()` or an
     error with stderr/stdout tail. `OSError` is caught so an
     exec failure (missing script) cannot crash the TUI.
  6. CSS block `#mode_modal_dialog` added right after
     `#node_detail_buttons`, using the same `thick $primary` border
     and `$surface` background as the existing node-detail modal but
     with `width: 60; height: auto` since the content is small.

- **Deviations from plan:** None material. CSS used `thick $primary`
  (not `solid $primary`) and `width: 60; height: auto` (no `align`
  property on the dialog itself — `ModalScreen` centers children by
  default; adding `align: center middle` on the dialog would misalign
  the inner column layout). `width: 60` chosen to match the
  `60`-column visual weight of button-row dialogs in the file; the
  absolute value (not percentage) keeps the modal compact regardless
  of terminal size.

- **Issues encountered:** None. Static checks passed on the first
  run (`python3 -m py_compile` + smoke import asserting
  `AgentModeEditModal`, `_edit_agent_mode`, `_on_mode_edit_result`
  all exist).

- **Key decisions:**
  - **Shell out, don't reimplement.** The callback calls `./ait crew
    setmode` rather than mutating yaml in-process. This keeps the
    validation regex, Waiting-state gate, and auto-commit logic in a
    single place (`aitask_crew_setmode.sh` from t461_2). A bug in
    mode validation or commit-message format fixes in one place, not
    two.
  - **No `cwd=` on the subprocess call.** setmode calls
    `resolve_crew` which uses the project-relative
    `.aitask-crews/crew-<id>` layout, independent of cwd. Passing
    cwd explicitly would add a failure mode (e.g., `session_path`
    happens to be a crew worktree, not the repo root) for zero
    benefit.
  - **No-op guard on same-mode selection.** The lambda captures
    `current_mode` so if the user opens the modal on a headless
    agent and picks Headless, no subprocess runs and no toast fires.
    setmode's own commit guard would also catch this, but avoiding
    the fork is cleaner.
  - **Hint gated to Waiting state only.** The `(e: edit mode)` hint
    does not show on Running / Error / Completed rows because the
    setmode CLI rejects those — showing the hint would advertise a
    feature that errors immediately. Error rows still get their
    existing `(w: reset)` hint.
  - **Badge left out.** Adding an `[interactive]` badge to row
    labels would require extending `AgentStatusRow.__init__` to
    accept `launch_mode` and plumbing it through `_mount_agent_row`
    — a second refactor that's orthogonal to the edit flow. The
    modal shows the current mode prominently on open, which is the
    information the user actually needs at decision time. Revisit
    if user feedback asks for at-a-glance mode visibility.

- **Notes for sibling tasks:**
  - **t461_5 (per-type defaults)** can rely on this task's read
    path: `_edit_agent_mode` calls `read_yaml` and falls back to
    `"headless"` when `launch_mode` is absent. Once t461_5 writes
    per-type defaults into the yaml at `addwork` time, the modal
    picks up those values for free.
  - **t461_6 (log viewer)** — when wiring `L` on `AgentStatusRow`,
    add a new `if event.key == "L":` branch in
    `BrainstormApp.on_key()` after the `e` branch. Do NOT add class
    `BINDINGS` to `AgentStatusRow` — the row has none, by
    convention. The `@on(Button.Pressed, "#some_id")` decorator
    pattern used in `AgentModeEditModal` is the cleanest way to
    wire modal buttons; `LogDetailModal` already uses the same
    pattern so both TUIs will be consistent.
  - The `subprocess.run([AIT_PATH, "crew", ...])` pattern in
    `_on_mode_edit_result` is the template for any future TUI →
    CLI bridge. Capture stdout/stderr, check for a structured
    success marker (`UPDATED:...`), fall back to error toast with
    `stderr or stdout` tail. Swallow `OSError` so the TUI never
    dies from an exec failure.
  - CSS: `#mode_modal_dialog` uses `width: 60` (columns, not
    percent) — small dialogs with short content look better with
    absolute width than with `%`. Copy this pattern for other
    future small modals.
