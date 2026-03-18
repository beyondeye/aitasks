---
priority: medium
effort: medium
depends: [t417_5]
issue_type: feature
status: Ready
labels: [tui, brainstorming]
created_at: 2026-03-18 12:22
updated_at: 2026-03-18 12:22
---

## Context

This task creates the DiffViewerScreen — the screen that displays diffs with full navigation, mode switching, and comparison cycling. It wires together the DiffDisplay widget (t417_4) with the diff engine (t417_2/t417_3) and integrates into the app flow from PlanManagerScreen (t417_5).

This is where the user spends most of their time: viewing and navigating through diffs between plans.

## Key Files to Create

- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — The diff viewing screen

## Key Files to Modify

- `.aitask-scripts/diffviewer/diffviewer_app.py` — Wire DiffViewerScreen into the app's screen stack
- `.aitask-scripts/diffviewer/plan_manager_screen.py` — Update DiffLaunchDialog to push DiffViewerScreen instead of placeholder

## Reference Files for Patterns

- `.aitask-scripts/codebrowser/codebrowser_app.py` — Background worker pattern with `@work(exclusive=True)` for loading data, progress indicators
- `.aitask-scripts/board/aitask_board.py` — ModalScreen for summary overlay, Footer bindings
- `.aitask-scripts/diffviewer/diff_display.py` (from t417_4) — DiffDisplay widget to embed
- `.aitask-scripts/diffviewer/diff_engine.py` (from t417_2/t417_3) — `compute_multi_diff()` function

## Implementation Plan

1. Create `diff_viewer_screen.py` with `DiffViewerScreen(Screen)`:
   - Constructor takes: `main_path: str`, `other_paths: list[str]`, `mode: str`
   - Layout (compose):
     - Top: `Static` info bar — "Main: plan_alpha.md vs plan_beta.md (Classical, 1/3)"
     - Center: `DiffDisplay` widget filling remaining space
     - Bottom: `Footer` with key bindings shown

2. Implement background diff computation:
   - `on_mount()` calls `_compute_diffs()` worker
   - `@work(exclusive=True, thread=True)` decorated method:
     - Show "Computing diffs..." loading indicator
     - Call `compute_multi_diff(main_path, other_paths, mode='classical')`
     - Call `compute_multi_diff(main_path, other_paths, mode='structural')`
     - Cache both results
     - Post `DiffsReady` message when done
   - On `DiffsReady`: load the active mode's result into DiffDisplay, hide loading indicator

3. Implement comparison cycling:
   - Track `_active_idx: int` (which pairwise comparison is shown)
   - `key_n` / `action_next_comparison`: increment idx (wrap around), update DiffDisplay and info bar
   - `key_p` / `action_prev_comparison`: decrement idx (wrap around), update DiffDisplay and info bar

4. Implement mode toggle:
   - `key_m` / `action_toggle_mode`: switch between cached classical and structural results
   - Update DiffDisplay with the other mode's result for the current comparison idx
   - Update info bar to show current mode

5. Implement unified overlay:
   - `key_u` / `action_unified_view`: toggle unified multi-diff overlay mode
   - In unified mode, `DiffDisplay.load_multi_diff()` shows all comparisons interleaved
   - Info bar shows "Unified view (3 comparisons)"

6. Implement summary modal:
   - `key_s` / `action_summary`: push a `SummaryScreen(ModalScreen)` showing:
     - "Unique to main: X sections / Y lines"
     - For each comparison: "Unique to <plan>: X sections / Y lines"
     - Total equal/different percentages
   - Dismiss with `escape`

7. Navigation:
   - `escape` / `key_b`: pop screen back to PlanManagerScreen
   - Up/down/pgup/pgdn/home/end: delegated to DiffDisplay widget

8. Key bindings:
   ```python
   BINDINGS = [
       Binding("n", "next_comparison", "Next comparison"),
       Binding("p", "prev_comparison", "Prev comparison"),
       Binding("m", "toggle_mode", "Toggle mode"),
       Binding("u", "unified_view", "Unified view"),
       Binding("s", "summary", "Summary"),
       Binding("escape", "back", "Back"),
   ]
   ```

## Verification

- Launch diff from PlanManagerScreen with 3 comparison plans: loading indicator shown, then diff renders
- Press `n`/`p`: cycles through 3 comparisons, info bar updates with plan names and index
- Press `m`: switches between Classical and Structural, display updates immediately (cached)
- Press `u`: shows unified overlay with all comparisons, gutter shows plan colors
- Press `s`: summary modal shows correct unique line/section counts
- Press `escape`: returns to PlanManagerScreen
- Re-enter same diff: cached results load instantly (no recomputation)
- Keyboard navigation (up/down/pgup/pgdn) works within the diff display
