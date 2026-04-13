---
Task: t461_4_brainstorm_status_edit.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_2_*.md, aitasks/t461/t461_3_*.md, aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md, aiplans/archived/p461/p461_2_*.md, aiplans/archived/p461/p461_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_4 — Brainstorm status-tab edit launch_mode

## Goal

On the brainstorm TUI's status tab, let the user press `e` on a
focused `AgentStatusRow` to open a small modal that toggles the
agent's `launch_mode` between `headless` and `interactive`. The modal
shells out to `ait crew setmode` (from t461_2) so the CLI and TUI
share one mutation code path.

## Files

### Modified

1. `.aitask-scripts/brainstorm/brainstorm_app.py`
   - `AgentStatusRow` class (~507-521): add `e` keybinding
   - New `AgentModeEditModal(ModalScreen)` class near
     `NodeDetailModal` (~164-248) as a structural template
   - New action handler on the row / app
   - `_mount_agent_row()` / row label — optional visual badge for
     current mode
   - Status tab footer / help strings

## Implementation steps

### 1. `AgentModeEditModal`

Structure:
```python
class AgentModeEditModal(ModalScreen[Optional[str]]):
    BINDINGS = [Binding("escape", "dismiss(None)")]

    def __init__(self, crew_id: str, agent_name: str,
                 current_mode: str, agent_status: str):
        super().__init__()
        self.crew_id = crew_id
        self.agent_name = agent_name
        self.current_mode = current_mode
        self.agent_status = agent_status

    def compose(self) -> ComposeResult:
        with Vertical(id="mode-modal"):
            yield Label(f"Agent: {self.agent_name}")
            yield Label(f"Status: {self.agent_status}")
            if self.agent_status != "Waiting":
                yield Static(
                    "Launch mode can only be changed on Waiting agents.",
                    id="mode-readonly-note",
                )
                yield Button("Close", id="close", variant="primary")
            else:
                yield Label(f"Current: {self.current_mode}")
                with Horizontal():
                    yield Button(
                        "Headless",
                        id="mode-headless",
                        variant="primary" if self.current_mode == "headless" else "default",
                    )
                    yield Button(
                        "Interactive",
                        id="mode-interactive",
                        variant="primary" if self.current_mode == "interactive" else "default",
                    )
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mode-headless":
            self.dismiss("headless")
        elif event.button.id == "mode-interactive":
            self.dismiss("interactive")
        else:
            self.dismiss(None)
```

Add minimal CSS (follow `NodeDetailModal`'s pattern).

### 2. Bind `e` on `AgentStatusRow`

```python
class AgentStatusRow(Static):
    BINDINGS = [
        Binding("w", "reset_agent", "Reset error"),
        Binding("e", "edit_mode", "Edit mode"),
    ]

    def action_edit_mode(self) -> None:
        app = self.app  # type: BrainstormApp
        # Read current status / launch_mode from yaml
        status_path = app.session_dir / f"{self.agent_name}_status.yaml"
        import yaml
        data = yaml.safe_load(status_path.read_text()) or {}
        current_mode = data.get("launch_mode", "headless")
        agent_status = data.get("status", "Unknown")
        crew_id = app.crew_id  # or wherever crew_id is stored
        modal = AgentModeEditModal(
            crew_id=crew_id, agent_name=self.agent_name,
            current_mode=current_mode, agent_status=agent_status,
        )
        app.push_screen(modal, self._on_mode_result)

    def _on_mode_result(self, new_mode: Optional[str]) -> None:
        if new_mode is None:
            return
        app = self.app
        result = subprocess.run(
            ["./ait", "crew", "setmode",
             "--crew", app.crew_id,
             "--name", self.agent_name,
             "--mode", new_mode],
            capture_output=True, text=True, cwd=str(app.repo_root),
        )
        if result.returncode == 0 and "UPDATED:" in result.stdout:
            app.notify(f"Launch mode updated → {new_mode}")
            app._refresh_status_tab()
        else:
            app.notify(
                f"setmode failed: {result.stderr.strip() or 'unknown error'}",
                severity="error",
            )
```

Note: replace `app.crew_id`, `app.session_dir`, `app.repo_root` with
whatever attribute names `BrainstormApp` already exposes (read the
class to find them).

### 3. Row badge for current mode

In the row label format string, append:
- nothing when `launch_mode == "headless"` (default, don't clutter)
- `  [interactive]` in a subtle color when `launch_mode == "interactive"`

Read `launch_mode` from the cached agent data the row already tracks.

### 4. Footer / help text

Add `e: Edit mode` to the status-tab help footer next to the existing
`w: Reset error` entry.

## Verification

1. Open `ait brainstorm <task>` on a crew with a Waiting agent.
2. Focus the row, press `e`. Modal opens with current mode shown.
3. Click Interactive. Modal closes, toast "Launch mode updated →
   interactive" appears, row re-renders with the `[interactive]` badge.
4. Grep the status yaml: `launch_mode: interactive`.
5. `git log -1`: a commit `ait: Set launch_mode=interactive ...` from
   the setmode script.
6. With a Running agent (you may need to let the runner start one),
   press `e`: modal opens in read-only mode with the explanatory note.
7. Rename the setmode script temporarily and press `e`: confirm error
   toast appears with the underlying error.

## Dependencies

- Hard: t461_2 for the `ait crew setmode` CLI.
- Soft: t461_1 for the `launch_mode` field; without it the badge just
  shows empty / headless.

## Notes for sibling tasks

- This edit flow only handles Waiting agents. A follow-up task could
  add in-flight mode changes (stop agent, flip mode, restart) but that
  is out of scope for t461.
