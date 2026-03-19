---
Task: t417_7_plan_merge_feature.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_1_*.md through t417_6_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Plan Merge Feature (t417_7)

## 1. Create `merge_engine.py`

File: `.aitask-scripts/diffviewer/merge_engine.py`

### `MergeSession`

```python
class MergeSession:
    def __init__(self, main_lines: list[str], multi_diff: MultiDiffResult):
        self.main_lines = main_lines
        self.multi_diff = multi_diff
        # Keyed by (plan_path, hunk_index) → accepted bool
        self.accepted: dict[tuple[str, int], bool] = {}
        self._init_hunks()

    def _init_hunks(self):
        """Initialize all non-equal hunks as rejected (False)."""
        for comp in self.multi_diff.comparisons:
            for i, hunk in enumerate(comp.hunks):
                if hunk.tag != 'equal':
                    self.accepted[(comp.other_path, i)] = False

    def accept_hunk(self, plan_path: str, idx: int): ...
    def reject_hunk(self, plan_path: str, idx: int): ...
    def accept_all_from(self, plan_path: str): ...
    def get_conflicts(self) -> list[tuple[str, int, str, int]]: ...
```

### `get_conflicts()`

Detect overlapping main_ranges from different plans that are both accepted:
- Build list of accepted hunks with their main_range
- Sort by main_range start
- Check for overlaps: if hunk A's main_range end > hunk B's main_range start and they're from different plans → conflict

### `apply_merge(session: MergeSession) -> list[str]`

Algorithm:
1. Start with `output = list(session.main_lines)`
2. Collect all accepted hunks, sort by main_range start (descending — apply from end to start to preserve indices)
3. For each accepted hunk:
   - `delete`: remove `output[main_range[0]:main_range[1]]`
   - `insert`: insert `other_lines` at `main_range[0]`
   - `replace`: replace `output[main_range[0]:main_range[1]]` with `other_lines`
   - `moved`: skip (moved sections don't change content, just position)
4. Return output

### `suggest_filename(main_path, accepted_plans) -> str`

```python
# main: "test_plans/plan_alpha.md", accepted from beta and gamma
# → "test_plans/plan_alpha_merged_beta_gamma.md"
main_stem = Path(main_path).stem  # "plan_alpha"
other_stems = [Path(p).stem.replace("plan_", "") for p in accepted_plans]
return f"{main_stem}_merged_{'_'.join(other_stems)}.md"
```

## 2. Create `merge_screen.py`

File: `.aitask-scripts/diffviewer/merge_screen.py`

### `MergeScreen(Screen)`

Layout:
```
┌────────────────────────────┬──────────────────────────────┐
│ Hunks (50%)                │ Preview (50%)                │
│                            │                              │
│ [x] plan_beta hunk 1       │ # Context                   │
│     -old line              │                              │
│     +new line              │ The authentication system... │
│                            │                              │
│ [ ] plan_beta hunk 2       │ ## Step 1                    │
│     -removed section       │ (merged content from beta)   │
│                            │                              │
│ [x] plan_gamma hunk 1      │ ## Step 2                    │
│     +added section         │ (original from alpha)        │
│                            │                              │
├────────────────────────────┴──────────────────────────────┤
│ a=Accept r=Reject A=Accept All w=Write Esc=Cancel         │
└───────────────────────────────────────────────────────────┘
```

**Left pane — Hunk list:**
- Each non-equal hunk shown as a condensed diff snippet (max 5 lines preview)
- Checkbox indicator: `[x]` accepted (green highlight), `[ ]` rejected (dim)
- Group hunks by source plan with headers: `"--- from plan_beta.md ---"`
- Cursor navigation: up/down to move between hunks

**Right pane — Live preview:**
- Shows the full merged output as rendered markdown (using Textual's `Markdown` widget or plain `Static`)
- Updates on every accept/reject toggle by calling `apply_merge(session)`

### Keybindings

```python
BINDINGS = [
    Binding("a", "accept_hunk", "Accept"),
    Binding("r", "reject_hunk", "Reject"),
    Binding("A", "accept_all", "Accept all from plan"),
    Binding("space", "toggle_hunk", "Toggle"),
    Binding("w", "write_merge", "Write"),
    Binding("escape", "cancel", "Cancel"),
]
```

### Conflict Handling

On accept: check `session.get_conflicts()`. If the newly accepted hunk conflicts with another:
- Auto-reject the conflicting hunk
- Show notification: "Conflict: deselected hunk from {plan} (overlapping range)"

### `SaveMergeDialog(ModalScreen)`

```
┌──────────────────────────────────────┐
│ Save Merged Plan                     │
│                                      │
│ Filename: [plan_alpha_merged_beta  ] │
│ Directory: [aiplans/               ] │
│                                      │
│ Accepted: 5 hunks from 2 plans      │
│                                      │
│ [Save]              [Cancel]         │
└──────────────────────────────────────┘
```

- Pre-filled with `suggest_filename()` output
- Editable Input fields for filename and directory
- On save:
  - Write merged lines to file
  - Add `merged_from: [plan_beta.md, plan_gamma.md]` to frontmatter
  - Notify: "Saved to {path}"
  - Pop back to DiffViewerScreen

## 3. Wire into DiffViewerScreen

Add to `diff_viewer_screen.py`:
```python
Binding("e", "enter_merge", "Merge mode"),
```

`action_enter_merge`:
- Create `MergeSession` from current `MultiDiffResult` and main plan lines
- Push `MergeScreen(session)`

## 4. Verification

- From DiffViewerScreen press `e` → MergeScreen opens with hunk list
- Accept a hunk → checkbox shows `[x]`, green highlight, preview updates
- Reject it back → `[ ]`, dim, preview reverts
- Accept conflicting hunks → notification, other auto-deselected
- Press `A` → all hunks from focused plan accepted
- Press `w` → SaveMergeDialog with suggested filename
- Save → file written, parse with task_yaml → valid frontmatter with merged_from field
- Content matches expected merge of accepted hunks
- `escape` → back to DiffViewerScreen without saving

## Post-Review Changes

### Change Request 1 (2026-03-19 14:30)
- **Requested by user:** Preview pane should show line numbers, highlight affected lines for current hunk, and scroll to position when navigating hunks
- **Changes made:** Added `apply_merge_annotated()` (returns per-line source annotations) and `compute_hunk_preview_range()` to merge_engine.py. Updated `_render_preview()` in merge_screen.py to use Rich Table with line numbers, orange highlighting for current hunk range, green for other accepted hunks, and auto-scroll preview to highlighted region. Cursor navigation now also re-renders preview.
- **Files affected:** merge_engine.py, merge_screen.py

### Change Request 2 (2026-03-19 14:35)
- **Requested by user:** After saving merged file, diff view should refresh — merged file becomes the new main, original main joins the comparison set, other files stay
- **Changes made:** MergeScreen dismisses with saved path. DiffViewerScreen callback swaps main_path to the merged file, adds old main to other_paths, and recomputes diffs.
- **Files affected:** merge_screen.py, diff_viewer_screen.py

### Change Request 3 (2026-03-19 14:45)
- **Requested by user:** Plan gutter label ("A", "B" etc.) was incorrectly shown for main-file lines (delete lines) — should only appear on other-file lines. Also: "unified mode" keybinding is a no-op stub.
- **Changes made:** Updated DiffDisplay gutter logic: **interleaved** — plan label shows on "insert"/"moved" lines (other-file), "M" marker on "delete" lines (main-file), nothing on "equal". **Side-by-side** — plan label on all non-equal lines (both columns visible). Created sibling task t417_12 for implementing the stubbed unified diff mode.
- **Files affected:** diff_display.py

## Final Implementation Notes
- **Actual work done:** Created merge_engine.py (MergeSession, apply_merge, apply_merge_annotated, compute_hunk_preview_range, suggest_filename, get_conflicts) and merge_screen.py (MergeScreen with split hunk-list/preview layout, SaveMergeDialog). Wired into DiffViewerScreen via "e" keybinding. Added CSS to DiffViewerApp. Also fixed pre-existing DiffDisplay gutter label behavior.
- **Deviations from plan:** Added apply_merge_annotated() and compute_hunk_preview_range() (not in original plan) for line-number preview with highlighting and scroll-to-position. Added post-save refresh that swaps merged file as new main (not in original plan). Fixed gutter label logic in diff_display.py (pre-existing issue, surfaced during testing).
- **Issues encountered:** DiffDisplay gutter labels were showing for main-file lines (delete/replace tags) — fixed by differentiating interleaved (only insert/moved show plan label) vs side-by-side (all non-equal show label). Unified mode is a non-functional stub — deferred to sibling task.
- **Key decisions:** Used apply_merge_annotated with forward-walking algorithm for preview annotations (cleaner than tracking offsets separately). Used Rich Table for preview rendering with line numbers. Orange highlight for current hunk, green for other accepted hunks. MergeScreen uses dismiss() with path result instead of pop_screen() for cleaner callback flow.
- **Notes for sibling tasks:** The gutter logic in diff_display.py now has differentiated behavior between interleaved and side-by-side modes. Unified mode (keybinding "u") is stubbed — both branches of _load_current_view call the same code. t417_12 should implement proper unified view showing all comparisons simultaneously.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
