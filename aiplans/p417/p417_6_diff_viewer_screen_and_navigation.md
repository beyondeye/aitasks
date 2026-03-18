---
Task: t417_6_diff_viewer_screen_and_navigation.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_1_*.md through t417_5_*.md, aitasks/t417/t417_7_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Diff Viewer Screen and Navigation (t417_6)

## 1. Create `diff_viewer_screen.py`

File: `.aitask-scripts/diffviewer/diff_viewer_screen.py`

### `DiffViewerScreen(Screen)`

```python
class DiffViewerScreen(Screen):
    BINDINGS = [
        Binding("n", "next_comparison", "Next"),
        Binding("p", "prev_comparison", "Prev"),
        Binding("m", "toggle_mode", "Mode"),
        Binding("u", "unified_view", "Unified"),
        Binding("s", "summary", "Summary"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, main_path: str, other_paths: list[str], mode: str = "classical"):
        super().__init__()
        self._main_path = main_path
        self._other_paths = other_paths
        self._initial_mode = mode
        self._current_mode = mode
        self._active_idx = 0
        self._classical_result: MultiDiffResult | None = None
        self._structural_result: MultiDiffResult | None = None
        self._unified_mode = False
```

### compose()

```python
def compose(self) -> ComposeResult:
    yield Header()
    yield Static("Computing diffs...", id="info_bar")
    yield DiffDisplay(id="diff_display")
    yield Footer()
```

### Background Diff Computation

```python
@work(exclusive=True, thread=True)
def _compute_diffs(self) -> None:
    # Compute both modes eagerly for instant switching
    classical = compute_multi_diff(self._main_path, self._other_paths, mode='classical')
    structural = compute_multi_diff(self._main_path, self._other_paths, mode='structural')
    self.call_from_thread(self._on_diffs_ready, classical, structural)

def _on_diffs_ready(self, classical: MultiDiffResult, structural: MultiDiffResult):
    self._classical_result = classical
    self._structural_result = structural
    self._load_current_view()
```

On mount: call `_compute_diffs()`. Show loading indicator in info bar until ready.

### Info Bar Updates

Format: `"Main: {main_name} vs {other_name} ({mode}, {idx+1}/{total})"`

In unified mode: `"Main: {main_name} — Unified view ({total} comparisons, {mode})"`

### Navigation Actions

- `action_next_comparison`: `_active_idx = (_active_idx + 1) % len(comparisons)`, reload display
- `action_prev_comparison`: `_active_idx = (_active_idx - 1) % len(comparisons)`, reload display
- `action_toggle_mode`: flip between 'classical' and 'structural', reload from cached result
- `action_unified_view`: toggle `_unified_mode`, reload as multi-diff overlay or single comparison
- `action_back`: `self.app.pop_screen()`

### Summary Modal

`action_summary`: push `SummaryScreen(ModalScreen)`:

```
┌────────────────────────────────────┐
│ Diff Summary                       │
│                                    │
│ Mode: Classical                    │
│ Main plan: plan_alpha.md           │
│                                    │
│ Unique to main: 15 lines           │
│ Unique to plan_beta.md: 12 lines   │
│ Unique to plan_gamma.md: 8 lines   │
│                                    │
│ [Close]                            │
└────────────────────────────────────┘
```

Uses `unique_to_main` and `unique_to_others` from `MultiDiffResult`.

## 2. Wire into App

Update `diffviewer_app.py`:
- Import `DiffViewerScreen`
- Update `DiffLaunchDialog` in `plan_manager_screen.py` to push `DiffViewerScreen(main_path, other_paths, mode)` on "Start Diff"

## 3. Verification

- Load 3 plans in PlanManagerScreen, launch diff → loading indicator, then diff renders
- `n`/`p` → cycles comparisons, info bar shows current comparison name and index
- `m` → switches mode instantly (cached), display updates
- `u` → unified overlay with plan identifier gutter colors
- `s` → summary modal with correct line counts
- `escape` → returns to PlanManagerScreen
- Re-enter diff → instant (no recomputation)
- Up/down/pgup/pgdn → cursor moves within diff display

## Final Implementation Notes

- **Actual work done:** Created `diff_viewer_screen.py` with `DiffViewerScreen(Screen)` and `SummaryScreen(ModalScreen)`. DiffViewerScreen eagerly computes both classical and structural diffs in a background worker for instant mode switching. Updated `plan_manager_screen.py` to push DiffViewerScreen from the DiffLaunchDialog callback. Added CSS for info bar and summary modal to `diffviewer_app.py`. Also added `[..] Parent directory` navigation entry to `plan_browser.py` for easier testing/navigation.
- **Deviations from plan:** Used `id="diff_viewer"` for the DiffDisplay widget in DiffViewerScreen (not `id="diff_display"`) to avoid conflicting with the internal Static child id in DiffDisplay. Used `self.app.call_from_thread()` instead of `self.call_from_thread()` since `call_from_thread` is a method on `App`, not `Screen`. Parent directory browser entry is always shown (not just when not at root) and handles empty parent path by falling back to `"."`.
- **Issues encountered:** (1) `work` decorator must be imported from `textual` not `textual.worker`. (2) Duplicate CSS id crash: DiffDisplay's internal Static uses `id="diff_display"`, so the outer widget needed a different id. (3) `call_from_thread` is on `App`, not `Screen` — fixed to use `self.app.call_from_thread()`. (4) Parent directory navigation from root gave empty string to `os.listdir` — fixed with `or "."` fallback.
- **Key decisions:** Both diff modes computed eagerly on screen mount for instant switching. Unified mode reuses `load_multi_diff()`. Summary modal reads `unique_to_main`/`unique_to_others` directly from `MultiDiffResult`.
- **Notes for sibling tasks:** DiffViewerScreen uses `id="diff_viewer"` for its DiffDisplay widget (not `"diff_display"`). The current single-pane diff view shows both files interleaved — a follow-up task (t417_8) should implement a multi-column side-by-side view for better clarity. CSS for DiffViewerScreen and SummaryScreen is in `DiffViewerApp.CSS`.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
