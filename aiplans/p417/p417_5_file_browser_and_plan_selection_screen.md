---
Task: t417_5_file_browser_and_plan_selection_screen.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_1_*.md through t417_4_*.md, aitasks/t417/t417_6_*.md, t417_7_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: File Browser and Plan Selection Screen (t417_5)

## 1. Create `plan_browser.py`

File: `.aitask-scripts/diffviewer/plan_browser.py`

### `PlanBrowser(VerticalScroll)`

A list-based file browser for `.md` files:

```python
class PlanBrowser(VerticalScroll):
    class PlanSelected(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def __init__(self, root_dir: str = "aiplans/", **kwargs):
        super().__init__(**kwargs)
        self._root_dir = root_dir
        self._current_dir = root_dir
        self._history: list[str] = []  # last 10 paths
```

**Features:**
- Shows current directory contents: `[DIR] subdirectory/` and `filename.md`
- Breadcrumb at top: `aiplans/ > p417/` with click-to-navigate-back
- History section at top (before directory listing): "Recent:" followed by last 10 opened files
- Click/Enter on directory → navigate into it
- Click/Enter on `.md` file → post `PlanSelected(absolute_path)` message
- Also allow browsing into `.aitask-scripts/diffviewer/test_plans/` for test data

**History persistence:**
- Load from `aitasks/metadata/diffviewer_history.json` on mount
- Save on every `PlanSelected` emission
- Format: `{"recent": ["path1", "path2", ...]}`
- Max 10 entries, most recent first
- Skip entries whose files no longer exist

**Styling:** Each entry is a focusable `Static` widget. Directories bold, files normal. Focused item gets highlight background.

## 2. Create `plan_manager_screen.py`

File: `.aitask-scripts/diffviewer/plan_manager_screen.py`

### `PlanManagerScreen(Screen)`

Layout:
```
┌─────────────────────────────────────────────────────┐
│ ait diffviewer                              Header  │
├────────────────────┬────────────────────────────────┤
│ File Browser       │ Loaded Plans                   │
│ [40% width]        │ [60% width]                    │
│                    │                                │
│ Recent:            │ plan_alpha.md                  │
│  plan_alpha.md     │  "Implement User Auth"         │
│  plan_beta.md      │  [Remove] [Diff as Main]       │
│                    │                                │
│ aiplans/           │ plan_beta.md                   │
│  [DIR] p417/       │  "Implement User Auth (v2)"    │
│  [DIR] archived/   │  [Remove] [Diff as Main]       │
│  p144_ait_clear... │                                │
│                    │ plan_gamma.md                  │
│                    │  "Architecture Approach"        │
│                    │  [Remove] [Diff as Main]        │
├────────────────────┴────────────────────────────────┤
│ Footer: q=Quit  Enter=Select  r=Remove     Bindings │
└─────────────────────────────────────────────────────┘
```

**compose():**
```python
def compose(self) -> ComposeResult:
    yield Header()
    with Horizontal(id="main_container"):
        yield PlanBrowser(id="browser")
        with VerticalScroll(id="loaded_plans"):
            yield Label("Loaded Plans", id="loaded_title")
            # Plan entries added dynamically
    yield Footer()
```

**Loaded plan entries:**
Each loaded plan is a `Horizontal` container with:
- `Label` showing filename + first heading from parsed frontmatter
- `Button("Remove", variant="error", classes="plan-remove")`
- `Button("Diff as Main", variant="primary", classes="plan-diff")`

**Event handling:**
- `on_plan_browser_plan_selected(event)`: load plan, add to list, prevent duplicates
- Remove button click: remove entry from loaded list
- "Diff as Main" button click: push `DiffLaunchDialog` with this plan as main

### `DiffLaunchDialog(ModalScreen)`

```
┌──────────────────────────────┐
│ Configure Diff               │
│ Main plan: plan_alpha.md     │
│                              │
│ Compare against:             │
│ [x] plan_beta.md             │
│ [x] plan_gamma.md            │
│ [ ] plan_delta.md            │
│                              │
│ Mode: (o) Classical          │
│       ( ) Structural         │
│                              │
│ [Start Diff]    [Cancel]     │
└──────────────────────────────┘
```

- Checkboxes for each loaded plan (except the main plan)
- Radio buttons for diff mode
- "Start Diff" → push DiffViewerScreen (or placeholder if t417_6 not done yet)
- "Cancel" → dismiss

## 3. Update `diffviewer_app.py`

Replace the placeholder stub from t417_1 with the real App:

```python
class DiffViewerApp(App):
    TITLE = "ait diffviewer"
    CSS = """..."""  # Inline CSS for all screens

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen(PlanManagerScreen())
```

**CSS sections:**
- PlanManagerScreen layout (horizontal split 40/60)
- PlanBrowser styling (directory bold, file normal, focused highlight)
- Loaded plan entries (horizontal layout, button spacing)
- DiffLaunchDialog (centered modal, checkbox/radio styling)

## 4. Verification

- `python3 .aitask-scripts/diffviewer/diffviewer_app.py` → app launches, PlanManagerScreen visible
- Browser shows `aiplans/` contents, navigate into subdirectories and back
- Select a test plan → appears in loaded list with filename + heading
- Add same plan twice → prevented (notification)
- Click Remove → plan disappears from list
- Click "Diff as Main" → DiffLaunchDialog appears with other plans as checkboxes
- Select targets, choose mode, click "Start Diff" → screen transition
- Quit with `q`
- Reopen app → history shows previously loaded plans in browser

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
