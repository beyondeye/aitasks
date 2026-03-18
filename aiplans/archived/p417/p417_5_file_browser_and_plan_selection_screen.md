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

## Final Implementation Notes

- **Actual work done:** Created `plan_browser.py` with `PlanBrowser(VerticalScroll)` and `_BrowserEntry(Static)` focusable entries. Created `plan_manager_screen.py` with `PlanManagerScreen(Screen)`, `_LoadedPlanEntry(Horizontal)`, and `DiffLaunchDialog(ModalScreen)`. Replaced `diffviewer_app.py` placeholder stub with full `DiffViewerApp(App)` including inline CSS for all widgets.
- **Deviations from plan:** Used `_BrowserEntry._find_browser()` with manual ancestor walking instead of Textual's `ancestors_with_type()` which does not exist in the Textual API. Similarly used `_find_ancestor()` helper for button-to-entry ancestor lookup in `plan_manager_screen.py`. The compose structure uses `Vertical` instead of `VerticalScroll` for `#loaded_pane` outer container (VerticalScroll is only for the inner list). PlanBrowser default root is `aiplans/` (test_plans requires manual root override). Breadcrumb uses emoji folder icon rather than clickable back navigation.
- **Issues encountered:** `ancestors_with_type()` method does not exist on Textual widgets — replaced with explicit ancestor loop. Fixed during user review cycle.
- **Key decisions:** History stored as absolute paths for uniqueness. Browser entry navigation uses direct method calls on parent PlanBrowser rather than message posting for simplicity. DiffLaunchDialog "Start Diff" shows a notification placeholder — actual DiffViewerScreen transition will be wired in t417_6.
- **Notes for sibling tasks:** `PlanManagerScreen` stores loaded plans as `list[dict]` with keys `path`, `display_name`, `heading`. `DiffLaunchDialog.dismiss()` returns `(main_path, selected_paths, mode)` tuple on success or `None` on cancel. The `handle_result` callback in `on_diff_as_main` is where t417_6 should replace the notification with `app.push_screen(DiffViewerScreen(...))`. CSS is defined in `DiffViewerApp.CSS` — add DiffViewerScreen styles there.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
