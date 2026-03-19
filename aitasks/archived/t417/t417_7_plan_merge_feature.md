---
priority: medium
effort: high
depends: [t417_6]
issue_type: feature
status: Done
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-18 12:23
updated_at: 2026-03-19 17:17
completed_at: 2026-03-19 17:17
---

## Context

This task adds the plan merge feature — the ability to create a new plan by selectively accepting diff hunks from comparison plans. The user views hunks with accept/reject toggles, sees a live preview of the merged result, and saves to a new file with automatic naming.

This is the final feature that transforms the diff viewer from a read-only comparison tool into an active plan editing tool, enabling users to synthesize the best parts of multiple brainstorming plans.

## Key Files to Create

- `.aitask-scripts/diffviewer/merge_engine.py` — Merge logic (session, apply, naming, conflicts)
- `.aitask-scripts/diffviewer/merge_screen.py` — Merge UI (hunk list + live preview + save dialog)

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Add keybinding to enter merge mode
- `.aitask-scripts/diffviewer/diffviewer_app.py` — Register MergeScreen

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py` — `CommitMessageScreen(ModalScreen)` pattern for SaveMergeDialog (text input + buttons), `TaskDetailScreen` pattern for complex screen with multiple interactive elements
- `.aitask-scripts/board/aitask_merge.py` — Existing merge logic for task frontmatter conflicts (reference for conflict detection approach)
- `.aitask-scripts/diffviewer/diff_engine.py` (from t417_2/t417_3) — DiffHunk data model
- `.aitask-scripts/diffviewer/diff_display.py` (from t417_4) — DiffDisplay widget to reuse in read-only mode

## Implementation Plan

1. Create `merge_engine.py`:
   - `MergeSession` class:
     - `__init__(main_lines, multi_diff_result)` — initializes with main plan as base
     - `accepted_hunks: dict[tuple[str, int], bool]` — keyed by (plan_path, hunk_index), default False
     - `accept_hunk(plan_path, hunk_idx)` / `reject_hunk(plan_path, hunk_idx)` — toggle acceptance
     - `accept_all_from(plan_path)` — accept all hunks from one comparison plan
     - `get_conflicts() -> list[tuple]` — detect overlapping hunks from different plans that are both accepted (same main_range overlap)
   - `apply_merge(session) -> list[str]`:
     - Start with main_lines as base
     - Apply accepted hunks in order of main_range position
     - For 'insert' hunks: insert other_lines at the appropriate position
     - For 'delete' hunks: remove the main_lines range
     - For 'replace' hunks: substitute other_lines for main_lines range
     - Skip conflicting hunks (warn user)
   - `suggest_filename(main_path, accepted_plans) -> str`:
     - Extract plan names from paths
     - Generate: `<main_name>_merged_<other1>_<other2>.md`
     - Example: `plan_alpha_merged_beta_gamma.md`

2. Create `merge_screen.py` with `MergeScreen(Screen)`:
   - Constructor takes: `MultiDiffResult`, `MergeSession`
   - Layout (compose):
     - Left pane (50%): Hunk list — each hunk shown as a condensed diff snippet with `[Accept]`/`[Reject]` toggle. Use `Static` widgets with click handlers. Accepted hunks highlighted green, rejected dim.
     - Right pane (50%): Live preview — `Markdown` widget (or plain `Static`) showing the current merged output. Updates on every accept/reject toggle.
     - Bottom: Footer with keybindings
   - Track cursor position in hunk list for keyboard navigation

3. Implement keybindings:
   ```python
   BINDINGS = [
       Binding("a", "accept_hunk", "Accept"),
       Binding("r", "reject_hunk", "Reject"),
       Binding("shift+a", "accept_all", "Accept all from plan"),
       Binding("space", "toggle_hunk", "Toggle"),
       Binding("w", "write_merge", "Write merged file"),
       Binding("escape", "cancel", "Cancel"),
   ]
   ```

4. Implement live preview:
   - On every accept/reject action, call `apply_merge(session)` to get merged lines
   - Update the right pane preview widget with the new content
   - For performance: only re-render if the merged output actually changed

5. Implement conflict detection:
   - When user accepts a hunk that conflicts with another accepted hunk (overlapping main_range from different plans), show a notification: "Conflict: this hunk overlaps with an accepted hunk from <other_plan>. The other hunk will be deselected."
   - Auto-deselect the conflicting hunk

6. Create `SaveMergeDialog(ModalScreen)`:
   - Title: "Save Merged Plan"
   - `Input` widget pre-filled with suggested filename from `suggest_filename()`
   - Directory selector (default: same directory as main plan)
   - Summary: "Accepted N hunks from M plans"
   - "Save" button → write file, dismiss, notify "Saved to <path>"
   - "Cancel" button → dismiss without saving
   - The merged file gets the main plan's frontmatter with added `merged_from: [plan_beta.md, plan_gamma.md]` field

7. Wire into DiffViewerScreen:
   - Add `Binding("e", "enter_merge", "Merge mode")` to DiffViewerScreen
   - `action_enter_merge`: create MergeSession from current MultiDiffResult, push MergeScreen

## Verification

- Enter merge mode from DiffViewerScreen: hunk list displays with accept/reject toggles
- Accept a hunk: it highlights green, live preview updates to show the merged content
- Reject a hunk: it dims, live preview reverts
- Accept conflicting hunks from different plans: notification shown, conflicting hunk auto-deselected
- Press `A`: all hunks from current comparison plan accepted, preview updates
- Press `w`: SaveMergeDialog appears with suggested filename
- Save: file written to disk, content matches expected merge
- Saved file has valid YAML frontmatter with `merged_from` field
- Parse saved file with `task_yaml.parse_frontmatter()` — succeeds
- Press `escape` from merge screen: returns to DiffViewerScreen without saving
