---
Task: t251_allow_viewing_details_of_tasks_that_originated_changes.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Detail Pane for Codebrowser (t251)

## Context

The codebrowser TUI shows which task originated each code line via annotation gutters (task IDs like `t175`), but you can't view the actual plan/task content. The explain run directories already contain full copies of task and plan files (`aiexplains/codebrowser/<run>/tasks/tN.md` and `plans/pN.md`). This feature adds a right-side detail pane that shows the plan markdown content for the task annotating the current cursor line, with automatic updates on cursor/selection changes.

## Layout

```
+-- Header -------------------------------------------------------+
| FileTree (35/28/22) | CodePane (1fr)        | DetailPane (30)    |
|                     | +- file_info_bar ---+ | +- header -------+ |
|                     | | code_viewer (1fr) | | | Markdown()     | |
|                     | +------------------+  | +---------------+  |
+-- Footer -------------------------------------------------------+
```

Width priority: code column gets at least 80 chars before detail pane gets width. Detail pane default 30 chars, expandable to half-screen.

## Files Modified

1. **`aiscripts/codebrowser/annotation_data.py`** (+9 lines) — Added `TaskDetailContent` dataclass
2. **`aiscripts/codebrowser/explain_manager.py`** (+111 lines) — Added `get_task_detail()` method with LRU caching, `tasks:` section YAML parsing, frontmatter stripping
3. **`aiscripts/codebrowser/detail_pane.py`** (NEW, 93 lines) — DetailPane widget with Markdown rendering
4. **`aiscripts/codebrowser/codebrowser_app.py`** (+152 lines) — Layout, bindings, event wiring, width management

## Implementation Details

### Step 1: Data Model (`annotation_data.py`)
Added `TaskDetailContent` dataclass with fields: `task_id`, `plan_content`, `task_content`, `has_plan`, `has_task`.

### Step 2: Content Resolution + LRU Caching (`explain_manager.py`)
- Two global LRU caches using `OrderedDict`: content cache (max 100) and YAML index cache (max 20)
- `get_task_detail()` resolves file_path to run_dir, looks up task in `tasks:` section of reference.yaml
- Reads `plans/pN.md` and `tasks/tN.md` from run directory, strips YAML frontmatter
- `_lru_get`/`_lru_put` helpers for cache operations with oldest-hit eviction

### Step 3: DetailPane Widget (`detail_pane.py`)
- `DetailPane(VerticalScroll)` with Static header + Markdown content + placeholder
- `_current_task_id` field prevents redundant Markdown re-renders on same-task cursor moves
- Methods: `update_content()`, `show_multiple_tasks()`, `clear()`

### Step 4: App Integration (`codebrowser_app.py`)
- Hidden by default, toggled with `d` key, expanded with `D` (Shift+d)
- Width management: code column gets 80+ chars first, detail gets remainder (min 15 or auto-hides)
- Cursor-to-content resolution via annotation lookup on `CursorMoved` events
- Async content loading via `@work(exclusive=True, group="detail_load")` worker
- Focus cycle updated: tree -> code -> detail (if visible) -> tree

## Keyboard Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| `d` | toggle_detail | Show/hide detail pane |
| `D` | expand_detail | Toggle 30-char / half-screen width |
| `Tab` | toggle_focus | Cycle: tree -> code -> detail -> tree |

## Performance & Caching

- Same annotation range: `_current_task_id` check prevents redundant Markdown re-renders
- Same task, different range: LRU cache hit, no file IO
- New task: single file read via async worker, then cached (LRU, max 100)
- Cross-file reuse: task loaded for file A reused when file B has same annotation
- YAML index cache: parsed once per run_dir (LRU, max 20)

## Final Implementation Notes

- **Actual work done:** Implemented all 4 steps as planned — data model, LRU-cached content resolution, DetailPane widget with Markdown rendering, and full app integration with responsive width management.
- **Deviations from plan:** None significant. Implementation followed the plan closely.
- **Issues encountered:** None — existing architecture (CursorMoved messages, annotation data, explain run directories with pre-copied task/plan files) provided clean integration points.
- **Key decisions:** Detail pane hidden by default (user activates with `d`). Code column gets 80-char minimum before detail pane gets width. LRU eviction with OrderedDict (max 100 content entries, 20 YAML index entries). Frontmatter stripping via regex to show clean content.
