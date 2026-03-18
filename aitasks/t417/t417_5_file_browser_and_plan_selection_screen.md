---
priority: medium
effort: medium
depends: [t417_4]
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-18 12:22
updated_at: 2026-03-18 18:28
---

## Context

This task creates the home screen of the diff viewer TUI: a file browser for finding and loading plan files, a loaded-plans management list, and the diff launch dialog. This is the primary user-facing screen where plans are selected before diffing.

It also creates the main `DiffViewerApp(App)` class that ties everything together.

## Key Files to Create

- `.aitask-scripts/diffviewer/plan_browser.py` — File browser widget with history
- `.aitask-scripts/diffviewer/plan_manager_screen.py` — Home screen (browser + loaded plans)
- `.aitask-scripts/diffviewer/diffviewer_app.py` — Main App class, CSS, screen stack

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py` — Multi-screen App class, ModalScreen dialogs, CSS organization, the `ColumnSelectScreen` and `DependencyPickerScreen` patterns for list selection
- `.aitask-scripts/codebrowser/file_tree.py` — Custom directory tree widget (ProjectFileTree)
- `.aitask-scripts/codebrowser/codebrowser_app.py` — App with screen stack pattern
- `.aitask-scripts/aitask_diffviewer.sh` (from t417_1) — Launcher that calls diffviewer_app.py

## Implementation Plan

1. Create `plan_browser.py` with `PlanBrowser(VerticalScroll)`:
   - Shows `.md` files from a configurable root directory (default: `aiplans/`)
   - List-based (not tree) — shows current directory contents with `[DIR]` prefix for subdirectories
   - Click/Enter on directory → navigate into it. Breadcrumb/back button at top
   - Click/Enter on `.md` file → posts `PlanSelected(path)` message
   - **History section** at top: shows last 10 opened files (most recent first)
   - History persisted in `aitasks/metadata/diffviewer_history.json` (simple JSON list of paths)
   - Load/save history on mount/unmount
   - Styling: focused item highlighted, directories in bold, files in normal weight

2. Create `plan_manager_screen.py` with `PlanManagerScreen(Screen)`:
   - Layout: `Horizontal` container with two panes
     - Left pane (40% width): `PlanBrowser` widget
     - Right pane (60% width): Loaded plans list + action buttons
   - Right pane shows each loaded plan as a `Horizontal` container:
     - `Label` with plan filename + first heading line
     - `Button("Remove", variant="error")` — removes from loaded list
     - `Button("Diff as Main", variant="primary")` — sets as main plan and opens DiffLaunchDialog
   - Handle `PlanSelected` message from browser: load the plan (parse frontmatter + first heading), add to loaded list, update history
   - Prevent duplicate additions (same path)
   - `DiffLaunchDialog(ModalScreen)`:
     - Title: "Configure Diff: <main_plan_name>"
     - Checkbox list of all other loaded plans as comparison targets
     - Radio button group: "Classical" / "Structural" diff mode
     - "Start Diff" button → pushes DiffViewerScreen (or placeholder)
     - "Cancel" button → dismisses dialog

3. Create `diffviewer_app.py` with `DiffViewerApp(App)`:
   - `TITLE = "ait diffviewer"`
   - `CSS` — inline CSS for all screens (follow board app pattern)
   - Default screen: `PlanManagerScreen`
   - Global bindings: `q` quit, `?` help, `escape` back
   - `SCREENS` map for screen navigation
   - Entry point: `if __name__ == "__main__": DiffViewerApp().run()`

## Verification

- `python3 .aitask-scripts/diffviewer/diffviewer_app.py` launches app, shows PlanManagerScreen
- File browser shows `aiplans/` contents and test_plans/ contents
- Navigate into subdirectory and back
- Select a plan file: it appears in the loaded plans list on the right
- Adding the same plan twice: prevented (no duplicate)
- Click "Remove" on a loaded plan: it disappears
- Click "Diff as Main": DiffLaunchDialog appears showing other loaded plans
- Check comparison targets, select mode, click "Start Diff": transitions (to placeholder or DiffViewerScreen if t417_6 is done)
- Close and reopen app: history section in browser shows previously loaded plans
- `q` quits the app
