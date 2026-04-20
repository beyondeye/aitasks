---
Task: t597_4_config_modal_and_persistence.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_2_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-20 09:40
---

# Plan: t597_4 — Config modal + layered persistence

## Context

Adds the pane-config modal (preset picker + custom layout builder) and the
layered-config persistence for the stats TUI. Replaces the `HARDCODED_LAYOUT`
seed in `stats_app.py` with a config-driven `active_layout`.

This is child 4 of 6 for t597 (the stats TUI). Siblings t597_1 (data refactor),
t597_2 (skeleton + switcher), t597_3 (12 pane widgets) are all archived. This
task makes the TUI configurable; t597_5 then removes the obsolete `--plot`
flag and t597_6 is the aggregate manual-verification sibling.

## Verification Findings (2026-04-20)

Assumptions in the existing plan were re-checked against the current tree:

- ✅ `config_utils.py` exports every helper the plan uses: `load_layered_config`,
  `split_config`, `save_project_config`, `save_local_config`, `local_path_for`
  (lines 36, 74, 115, 124, 158).
- ✅ `.aitask-data/.gitignore` line 8 already covers
  `aitasks/metadata/*.local.json` — no `.gitignore` edit required.
- ✅ `stats_app.py` has the `action_config()` stub (line 153) and the
  priority-binding memory comment (lines 137–143); 12 panes register cleanly.
- ✅ Board layered-config reference pattern at `aitask_board.py:229–251`.
- ✅ Modal reference patterns at `settings_app.py` lines 1221 (ProfilePicker),
  1259 (NewProfile), 1349 (SaveProfileConfirm).
- ❗ `aitasks/metadata/stats_config.json` does not exist yet — new file.
- ❗ `stats_config.json` must be committed via `./ait git` (it lives under
  `aitasks/metadata/`, a symlink to `.aitask-data/`). The commit goes in a
  separate `./ait git` commit from the Python code changes.

## Implementation Plan

### 1. `stats_config.py` — schema + I/O

New file: `.aitask-scripts/stats/stats_config.py`.

**Critical design rule** — runtime saves write ONLY the user-level
(`stats_config.local.json`, gitignored) layer. The project-level
`stats_config.json` (tracked, shared) is treated as **read-only at runtime**.
This keeps shared project state out of the TUI's save path so it never
produces uncommitted changes the user hasn't asked for, and there is no
auto-commit or auto-push from the TUI.

```python
from __future__ import annotations
from lib.config_utils import (
    load_layered_config,
    save_local_config,
    local_path_for,
)

METADATA_FILE = "aitasks/metadata/stats_config.json"

DEFAULT_PRESETS: dict[str, list[str]] = {
    "overview": ["overview.summary", "overview.daily", "overview.weekday"],
    "labels":   ["labels.top", "labels.issue_types", "labels.heatmap"],
    "agents":   ["agents.per_agent", "agents.per_model", "agents.verified"],
    "velocity": ["velocity.daily", "velocity.rolling", "velocity.parent_child"],
}

DEFAULTS: dict = {
    "presets": DEFAULT_PRESETS,
    "active": "overview",
    "days": 7,
    "week_start": "mon",
    "custom": {},
}

# Keys that live in the user-level (gitignored) file. Everything else stays
# in the project file and is never written at runtime.
_USER_KEYS = {"active", "days", "week_start", "custom"}


def load() -> dict:
    """Load the merged layered config (defaults <- project <- user)."""
    return load_layered_config(METADATA_FILE, defaults=DEFAULTS)


def save(config: dict) -> None:
    """Persist ONLY the user-layer keys to `stats_config.local.json`.

    The project-level `stats_config.json` is not touched at runtime — it
    ships with the repo and is edited only via explicit, out-of-TUI actions.
    """
    user_data = {k: config[k] for k in _USER_KEYS if k in config}
    save_local_config(str(local_path_for(METADATA_FILE)), user_data)


def resolve_active_layout(config: dict) -> list[str]:
    active = config.get("active", "overview")
    presets = config.get("presets", DEFAULT_PRESETS)
    customs = config.get("custom", {})
    if active in customs:
        return list(customs[active])
    if active in presets:
        return list(presets[active])
    return list(presets.get("overview", DEFAULT_PRESETS["overview"]))
```

Notes:
- No `save_project_config` import — runtime code has no path that writes
  project state. If a future task adds a "publish preset" flow, it can
  import `save_project_config` there.
- Dropped `active_pane_id` from the earlier draft — remembering the
  highlighted sidebar row across relaunches isn't worth the extra
  round-trips in t597_4. Can be added later without migration.

### 2. `modals/name_input.py`

New file. `ModalScreen[str | None]` with one `Input` and OK/Cancel buttons.
Returns the trimmed name or `None` on cancel/empty.

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
            name = self.query_one("#name_input", Input).value.strip()
            self.dismiss(name or None)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### 3. `modals/config_modal.py`

New file. `ModalScreen[str | None]` returning the new active layout name (or
`None` if unchanged/cancelled).

All writes from this modal go to `config["active"]` and `config["custom"][...]`
only — both are user-layer keys. `stats_config.save(config)` persists only the
`stats_config.local.json` file. **Presets are not editable from this modal.**

Layout (Horizontal):
- **Left pane** — `ListView` of entries:
  - Header row `"Presets"` (disabled), then each preset name (read-only).
  - Header row `"Custom"` (disabled), then each saved custom name.
  - Trailing row `"+ New custom"`.
- **Right pane** — `SelectionList[str]` of all `PANE_DEFS` keys grouped by
  category (use `pane.category` for group labels; one `Option` per pane id
  with `pane.title` as display text).
- **Bottom bar** — `Horizontal` with buttons:
  - `Apply` — always visible; persist `config["active"]` = highlighted name,
    `stats_config.save(config)`, dismiss with the name.
  - `Save as custom` — visible only when editing a `+ New custom` row or an
    existing custom; writes `config["custom"][name] = [checked_ids]` and
    Applies.
  - `Delete` — visible only when a custom row is highlighted; removes from
    `config["custom"]` after a `ConfirmModal` (or inline Yes/No).
  - `Close` — dismiss with `None`.

Key bindings (scoped to the modal):
- `d` on a custom row = same as Delete.
- `escape` = Close.
- `enter` on `+ New custom` = push `NameInputModal`.

Behaviors:
- Left row change:
  - On preset → right pane reflects that preset's pane ids, `SelectionList`
    disabled (read-only preview — presets cannot be modified here).
  - On custom → right pane pre-checks the custom's pane ids, enabled.
  - On `+ New custom` → push `NameInputModal`; when the name returns, clear
    the right pane selection and enable it for editing.

Reference patterns to mirror:
- `settings_app.py:1221` `ProfilePickerScreen` — the overall modal/list idiom.
- `settings_app.py:1259` `NewProfileScreen` — input flow for a new name.
- `settings_app.py:1349` `SaveProfileConfirmScreen` — confirm before destructive
  save/overwrite.

### 4. `modals/__init__.py`

Empty package marker — just allows `from stats.modals.config_modal import ConfigModal`.

### 5. `stats_app.py` integration

Replace the `HARDCODED_LAYOUT` path with a config-driven one:

```python
from stats import stats_config
from stats.modals.config_modal import ConfigModal

class StatsApp(TuiSwitcherMixin, App):
    def __init__(self) -> None:
        super().__init__()
        self.current_tui_name = "stats"
        self.stats_data: StatsData | None = None
        self.config: dict = stats_config.load()
        self.active_layout: list[str] = [
            pid for pid in stats_config.resolve_active_layout(self.config)
            if pid in PANE_DEFS
        ]

    def action_config(self) -> None:
        def _on_done(new_active: str | None) -> None:
            if new_active is None:
                return
            # Reload to pick up any edits made inside the modal (custom saves).
            self.config = stats_config.load()
            self.active_layout = [
                pid for pid in stats_config.resolve_active_layout(self.config)
                if pid in PANE_DEFS
            ]
            self._rebuild_sidebar()
        self.push_screen(ConfigModal(self.config), _on_done)

    def _rebuild_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        sidebar.clear()
        for pid in self.active_layout:
            sidebar.append(ListItem(Label(PANE_DEFS[pid].title),
                                    id=_pane_id_to_widget_id(pid)))
        if self.active_layout:
            self._show_pane(self.active_layout[0])
            sidebar.index = 0
```

Keep `HARDCODED_LAYOUT` as a fallback constant for empty-config first-run
safety (used by `DEFAULTS["presets"]["overview"]` — they match). Delete the
inline module-level constant and replace with the `DEFAULT_PRESETS` import.

### 6. Ship the project preset file

Create `aitasks/metadata/stats_config.json` as a **one-time implementation
commit** — the TUI never rewrites this file at runtime:

```json
{
  "presets": {
    "overview": ["overview.summary", "overview.daily", "overview.weekday"],
    "labels":   ["labels.top", "labels.issue_types", "labels.heatmap"],
    "agents":   ["agents.per_agent", "agents.per_model", "agents.verified"],
    "velocity": ["velocity.daily", "velocity.rolling", "velocity.parent_child"]
  }
}
```

The user's active layout and custom layouts land in the gitignored
`stats_config.local.json` on first modal save. No auto-push from the TUI.

### 7. Gitignore

No action required — `.aitask-data/.gitignore` line 8
(`aitasks/metadata/*.local.json`) already covers `stats_config.local.json`.
Verify again post-implementation that `git status` does not list the local
file after a modal save.

### 8. Priority-binding guards (as-needed)

The existing `action_refresh`/`action_config`/... handlers on `StatsApp` don't
currently discriminate between the default screen and a pushed modal. When the
modal is pushed, Textual's screen stack should give modal bindings priority,
but per the project's `feedback_textual_priority_bindings` memory, `App.query_one`
walks the entire stack — so app-level actions can inadvertently fire for the
wrong screen.

Tactical approach: after wiring up the modal, manually test `r` / `c` / arrow
keys while the modal is open. If any fire app-level actions instead of modal
bindings, add `SkipAction` guards:

```python
from textual.actions import SkipAction
from textual.screen import ModalScreen

def action_config(self) -> None:
    if isinstance(self.screen, ModalScreen):
        raise SkipAction()
    self.push_screen(ConfigModal(self.config), self._on_config_done)
```

Only add guards that the manual test actually shows needing — no speculative
guarding.

## Verification

```bash
# Layered load returns the shipped presets.
python3 -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from stats import stats_config
cfg = stats_config.load()
assert set(cfg['presets']) == {'overview','labels','agents','velocity'}, cfg['presets']
assert cfg['active'] == 'overview'
print('PASS')
"

# TUI flow
ait stats-tui
#   c  → modal opens; presets listed
#   pick 'labels' → Apply → sidebar = labels panes
#   c → + New custom → name 'myview' → check 2–3 panes → Save as custom
#       → sidebar updates to 'myview' panes
#   q
ait stats-tui
#   sidebar starts on 'myview' panes (persistence)
#   c → highlight 'myview' → Delete → confirm → layout falls back to overview
#   q

# On-disk hygiene
cat aitasks/metadata/stats_config.json        # presets only, no user state
cat aitasks/metadata/stats_config.local.json  # active + custom
git status | grep stats_config                # .local.json NOT listed
./ait git status | grep stats_config          # .local.json NOT listed

shellcheck .aitask-scripts/aitask_stats_tui.sh
```

## Commits (implementation-time only)

Two commits, kept separate per CLAUDE.md "Never mix code files and aitasks/aiplans":

1. **Code commit (regular `git`):**
   - Files: `.aitask-scripts/stats/stats_config.py`,
     `.aitask-scripts/stats/modals/__init__.py`,
     `.aitask-scripts/stats/modals/config_modal.py`,
     `.aitask-scripts/stats/modals/name_input.py`,
     `.aitask-scripts/stats/stats_app.py`
   - Message: `feature: Add stats TUI config modal and layered persistence (t597_4)`

2. **Preset data commit (`./ait git`):**
   - File: `aitasks/metadata/stats_config.json`
   - Message: `feature: Ship stats TUI preset definitions (t597_4)`

Both pushes are done manually at archive time as part of the normal Step 9
flow. The TUI itself never commits or pushes.

## Out of Scope

- Removing the `ait stats --plot` flag and updating docs (t597_5).
- Manual end-to-end verification of the full feature (t597_6).
- Changing the weekly `week_start` or `days` window behavior at render time —
  the config schema reserves keys for these, but wiring them into
  `collect_stats()` is deferred.
- Editing presets from within the TUI. Presets are shipped project state and
  remain read-only at runtime; a future task can add an explicit
  "publish preset" flow if that becomes useful.

## Post-Review Changes

### Change Request 1 (2026-04-20)

- **Requested by user:**
  1. Replace the config modal with an inline layout-picker panel at the
     bottom-left of the main screen; Tab to switch focus between the
     sidebar (top-left) and the layout picker (bottom-left).
  2. Remove the Enter-to-switch behavior for panes in the sidebar — highlight
     alone should render the pane.
  3. Give the config UI proper keyboard shortcuts for confirm (no mouse/button
     reliance).
  4. Fix: the TUI switcher's `t` shortcut didn't switch to the stats TUI.

- **Changes made:**
  - `stats_app.py` redesigned:
    - Left column split with `Vertical` into `#sidebar` (top, 1fr) and
      `#layout_panel` (bottom, max-height 50%). Right = content.
    - `Tab` / `Shift+Tab` cycle focus between sidebar and layout picker.
      `c` is a direct shortcut to focus the picker.
    - Sidebar highlight now triggers `_show_pane` via
      `on_list_view_highlighted` (no Enter needed).
    - Layout picker: `Enter` applies the highlighted preset or custom;
      `n` opens the new-custom flow; `e` edits a custom; `d` deletes one.
      A `●` marker shows which layout is active.
    - The old blocking config modal is replaced by this inline panel.
  - `modals/config_modal.py` deleted. Replaced with
    `modals/pane_selector.py` — a narrower modal shown only when
    creating/editing a custom; `Space` toggles, `Enter` saves, `Esc`
    cancels. `name_input.py` is unchanged.
  - `lib/tui_switcher.py`: added `Binding("t", "shortcut_stats", ...)`,
    `action_shortcut_stats()`, and the `(t)` hint in the footer label.

- **Files affected:**
  - `.aitask-scripts/stats/stats_app.py` (major rewrite)
  - `.aitask-scripts/stats/modals/pane_selector.py` (new; replaces
    `config_modal.py`)
  - `.aitask-scripts/stats/modals/config_modal.py` (deleted)
  - `.aitask-scripts/lib/tui_switcher.py` (added stats shortcut)

### Change Request 2 (2026-04-20)

- **Requested by user:** When pressing Enter to apply a new layout in the
  layout picker, the sidebar showed the PREVIOUS layout's panes (stale).
  Panes only caught up after focusing the sidebar and arrowing through it.

- **Changes made:** `_rebuild_sidebar()` and its call sites were made `async`
  so the sidebar's `ListView.clear()` and `extend()` awaitables complete
  before the first pane is shown. The stale-highlight event from setting
  `sidebar.index = 0` against not-yet-mounted items no longer wins against
  the intended render. Updated callers: `_activate_layout_item`,
  `action_delete_custom`, and the `PaneSelectorModal` `on_done` callback.

- **Files affected:**
  - `.aitask-scripts/stats/stats_app.py`

## Final Implementation Notes

- **Actual work done:**
  - Added `stats/stats_config.py` (layered load; `save()` writes only user
    layer to `stats_config.local.json`; `resolve_active_layout()` falls back
    to `overview` when missing).
  - Added `stats/modals/name_input.py` (single-input modal; `enter` submits,
    `escape` cancels).
  - Added `stats/modals/pane_selector.py` (`SelectionList` of all 12 panes
    grouped by category; category rows disabled; `space` toggles, `enter`
    saves, `esc` cancels; preserves `PANE_DEFS` ordering for the returned
    ids so the sidebar renders predictably).
  - Redesigned `stats/stats_app.py`:
    - Left column: `#sidebar` (top, 1fr) + `#layout_panel` (bottom, max
      50%), right: `#content`. `Tab`/`Shift+Tab` cycle focus between the
      two left lists; `c` jumps to the layout picker.
    - Sidebar uses `_SidebarItem` carrying `pane_id` as an attribute; the
      `ListView.Highlighted` handler renders the pane immediately (no
      Enter).
    - Layout panel lists presets + customs + `+ New custom`, with a `●`
      marker on the active layout. `Enter` applies, `n` starts the
      new-custom flow, `e` edits a custom, `d` deletes one.
    - `_rebuild_sidebar()` is async and awaits clear+extend to avoid the
      stale-pane bug.
  - Shipped `aitasks/metadata/stats_config.json` (4 presets). Project file
    is read-only at runtime; `.aitask-data/.gitignore` already covers
    `aitasks/metadata/*.local.json`.
  - Fixed `lib/tui_switcher.py`: added `t` → stats shortcut binding,
    `action_shortcut_stats`, and the `(t)` hint in the footer.

- **Deviations from plan:**
  - Replaced the modal-first design in the original plan with an inline
    bottom-left layout picker, per the user's redesign request (see
    Post-Review Changes). The full-modal `ConfigModal` was deleted; its
    role for creating/editing customs moved to the narrower
    `PaneSelectorModal`.

- **Issues encountered:**
  - Stale highlight after Enter on a new layout — root cause: `ListView`
    mutations are async; setting `index = 0` before clear/extend settled
    fired the Highlighted event against stale items. Fix: make the
    rebuild chain async and await the DOM updates.

- **Key decisions:**
  - User-only runtime save: `stats_config.save()` deliberately drops
    project-scope keys so modal interactions never touch shared state
    (per user feedback — no auto-commit/auto-push).
  - Sidebar items use a `ListItem` subclass carrying `pane_id` as an
    attribute instead of a widget id. This avoids `DuplicateIds` errors
    during rebuild when panes overlap between layouts.
  - `PaneSelectorModal` preserves `PANE_DEFS` iteration order for its
    return value so custom layouts render in the same canonical order
    as presets.

- **Notes for sibling tasks:**
  - **t597_5 (--plot removal):** README/docs edits should mention
    `ait stats-tui` only; the TUI is now the interactive entry point for
    charts.
  - **t597_6 (manual verification):** Key flows to exercise:
    `t` shortcut switches to stats from any other TUI; `Tab` cycles focus
    between sidebar and layout picker; Enter on a preset/custom swaps
    the sidebar immediately; `n` → NameInput → PaneSelector → save
    persists to `stats_config.local.json`; `d` deletes a custom and
    falls back to `overview` when the active layout was removed;
    `cat aitasks/metadata/stats_config.json` should remain unchanged
    after modal interactions; `git status` must never list
    `stats_config.local.json`.
