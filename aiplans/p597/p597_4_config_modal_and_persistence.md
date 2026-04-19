---
Task: t597_4_config_modal_and_persistence.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_2_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
---

# Plan: t597_4 — Config modal + layered persistence

## Context

Adds the pane-config modal (preset picker + custom layout builder) and the layered-config persistence (project presets in `aitasks/metadata/stats_config.json`, user state in `stats_config.local.json`). Replaces the hardcoded `ACTIVE_LAYOUT` from t597_3 with a config-driven sidebar.

Mirrors the board's layered-config pattern (`aitask_board.py` lines 235–251) and the settings TUI's modal/profile picker pattern.

## Implementation Plan

### 1. `stats_config.py` — schema + I/O

```python
from pathlib import Path
from lib.config_utils import (
    load_layered_config,
    split_config,
    save_project_config,
    save_local_config,
    local_path_for,
)

METADATA_FILE = "aitasks/metadata/stats_config.json"

DEFAULT_PRESETS = {
    "overview": ["overview.summary", "overview.daily", "overview.weekday"],
    "labels":   ["labels.top", "labels.issue_types", "labels.heatmap"],
    "agents":   ["agents.per_agent", "agents.per_model", "agents.verified"],
    "velocity": ["velocity.daily", "velocity.rolling", "velocity.parent_child"],
}

DEFAULTS = {
    "presets": DEFAULT_PRESETS,
    "active": "overview",
    "active_pane_id": None,
    "days": 7,
    "week_start": "mon",
    "custom": {},
}

_PROJECT_KEYS = {"presets"}
_USER_KEYS = {"active", "active_pane_id", "days", "week_start", "custom"}


def load() -> dict:
    return load_layered_config(METADATA_FILE, defaults=DEFAULTS)


def save(config: dict) -> None:
    project_data, user_data = split_config(config, _PROJECT_KEYS, _USER_KEYS)
    save_project_config(METADATA_FILE, project_data)
    save_local_config(local_path_for(METADATA_FILE), user_data)


def resolve_active_layout(config: dict) -> list[str]:
    active = config.get("active", "overview")
    presets = config.get("presets", DEFAULT_PRESETS)
    customs = config.get("custom", {})
    if active in customs:
        return list(customs[active])
    if active in presets:
        return list(presets[active])
    # Fallback
    return list(presets.get("overview", DEFAULT_PRESETS["overview"]))
```

(Verify the helper names against `lib/config_utils.py` — if names differ, adapt. The pattern is what matters.)

### 2. `modals/name_input.py`

```python
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, Button, Label


class NameInputModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str = "Layout name:", initial: str = ""):
        super().__init__()
        self.prompt = prompt
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="name_input_dialog"):
            yield Label(self.prompt)
            yield Input(value=self.initial, id="name_input")
            with Horizontal():
                yield Button("OK", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(self.query_one("#name_input", Input).value.strip() or None)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### 3. `modals/config_modal.py`

`ModalScreen[Optional[str]]` returning the new active layout name (or `None` if unchanged/cancelled).

Layout:
- Left: `OptionList` of preset names + saved customs + `+ New custom`. Header rows for "Presets" / "Custom".
- Right: `SelectionList` of all `PANE_DEFS` keys grouped by category. Disabled (read-only) when a preset is selected; enabled when editing/creating a custom.
- Bottom buttons: `Apply`, `Save as new custom` (visible only when editing right-hand selection), `Delete` (visible only on a custom row), `Close`.

Behaviors:
- Selecting a preset → right pane shows that preset's panes (read-only).
- Selecting a custom → right pane pre-checks that custom's panes (editable).
- Selecting `+ New custom` → push `NameInputModal`; on name returned, switch right pane to empty `SelectionList` (editable); on Save, store under `config["custom"][name]` and set active.
- `Apply` → set `config["active"]` to the highlighted layout name, persist via `stats_config.save()`, dismiss with the new name.
- `Delete` (on a custom) → confirm via `AskUserQuestion`-equivalent (Textual: a small confirm modal); remove from `config["custom"]`, persist, refresh.
- `d` keybinding shortcut on the left list = same as Delete button (only when a custom is highlighted).

### 4. `stats_app.py` integration

```python
from stats import stats_config
from stats.modals.config_modal import ConfigModal

class StatsApp(...):
    def on_mount(self) -> None:
        self.config = stats_config.load()
        self._refresh_sidebar()
        self._load_data()
        ...

    def _refresh_sidebar(self) -> None:
        layout = stats_config.resolve_active_layout(self.config)
        sidebar = self.query_one("#sidebar", ListView)
        sidebar.clear()
        for pid in layout:
            if pid in PANE_DEFS:
                sidebar.append(ListItem(Label(PANE_DEFS[pid].title), id=pid.replace(".", "_")))

    def action_config(self) -> None:
        def _on_done(new_active: str | None) -> None:
            if new_active is None:
                return
            self.config["active"] = new_active
            self._refresh_sidebar()
            # Optionally re-show first pane in the new layout
        self.push_screen(ConfigModal(self.config), _on_done)
```

### 5. Ship project preset file

Create `aitasks/metadata/stats_config.json`:

```json
{
  "presets": {
    "overview":  ["overview.summary", "overview.daily", "overview.weekday"],
    "labels":    ["labels.top", "labels.issue_types", "labels.heatmap"],
    "agents":    ["agents.per_agent", "agents.per_model", "agents.verified"],
    "velocity":  ["velocity.daily", "velocity.rolling", "velocity.parent_child"]
  }
}
```

Commit via `./ait git add aitasks/metadata/stats_config.json && ./ait git commit -m "ait: Add stats TUI presets (t597_4)"`. (Wait — frontmatter says `feature` not `ait`. The presets file is **shipped data**, treat it as part of the implementation commit; not a separate `ait:` admin commit.)

### 6. .gitignore

Verify `.gitignore` covers `aitasks/metadata/*.local.json` (the existing `*.local.json` rule likely does). If not, append:

```
aitasks/metadata/stats_config.local.json
```

### 7. Priority binding caveat (memory)

Per `feedback_textual_priority_bindings`: when the modal is open, app-level `c`, `up`, `down`, `r` must NOT swallow keys destined for the modal. Inside each `action_*` in `StatsApp`:

```python
def action_config(self) -> None:
    if not isinstance(self.screen, type(self.default_screen)):
        from textual.actions import SkipAction
        raise SkipAction()
    # ... open modal
```

(Or simpler: add `priority=False` and rely on Textual's default screen-stack ordering — verify which approach matches the rest of the codebase.)

## Verification

```bash
ait stats-tui
# Press c → modal. Pick "Labels" → Apply → sidebar shows label panes.
# c → "+ New custom" → name "myview" → check "overview.daily" + "agents.per_model" → Save → sidebar updates.
# q → quit.
ait stats-tui                                # "myview" still active (persistence works)

cat aitasks/metadata/stats_config.json       # 4 presets present, no user state
cat aitasks/metadata/stats_config.local.json # active="myview", custom contains "myview"
git status                                   # stats_config.local.json NOT listed (gitignored)
git ls-files aitasks/metadata/ | grep stats  # only stats_config.json tracked
```

## Out of Scope

- Removing `--plot` (t597_5).
- Manual end-to-end verification (t597_6).
