---
priority: low
effort: medium
depends: [t195_4, t195_5]
issue_type: performance
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:19
updated_at: 2026-03-01 11:44
---

## Context

This is child task 10 of t195 (Python Code Browser TUI) — a risk mitigation follow-up for Risk 3 (explain generation latency). After the core explain manager and annotation overlay are built, this task improves the UX around explain data generation: pre-caching, generation queuing, progress feedback, and cache staleness detection.

## Key Files to Modify

- **`aiscripts/codebrowser/explain_manager.py`** (MODIFY):
  - Add generation queue: serialize concurrent requests, cancel/deprioritize stale ones
  - Add cache staleness check: compare run timestamp vs `git log -1 --format=%ci -- <directory>`
  - Add `--max-commits 30` parameter for codebrowser invocations (faster than default 50)
  - Add `is_stale(file_path: Path) -> bool`: check if cached data is outdated
- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Pre-cache on tree expansion: hook into `on_tree_node_expanded` to trigger background generation for expanded directories
  - Generation queue: track in-flight generation tasks, cancel if user navigates away
  - Progress indicator: replace "Generating..." with spinner or animated dots, show elapsed time
  - Staleness indicator: show "(outdated)" next to timestamp when cached data is stale
- **`aiscripts/codebrowser/file_tree.py`** (MODIFY):
  - Emit or expose directory expansion events for pre-caching hook

## Reference Files for Patterns

- `aiscripts/codebrowser/explain_manager.py` (from t195_4): Current `generate_explain_data()` and `get_cached_data()` methods
- `aiscripts/board/aitask_board.py` (lines 2590-2640): `@work(thread=True)` and background task patterns
- Textual `Worker` API: supports cancellation via `worker.cancel()`

## Implementation Plan

1. Add `--max-commits` support:
   - In `generate_explain_data()`, pass `MAX_COMMITS=30` as environment variable to the extract script
   - Or: add a `max_commits` parameter to `generate_explain_data()` with default 30

2. Add cache staleness check:
   - `is_stale(file_path: Path) -> bool`:
     - Get cached run timestamp (from directory name suffix)
     - Run `git log -1 --format=%ct -- <directory>` to get last commit time
     - Compare: if last commit > run timestamp → stale
   - Return staleness info alongside cached data

3. Add generation queue:
   - `self._generation_queue: asyncio.Queue` or simple list with lock
   - `self._active_generation: str | None` — directory currently being generated
   - When new generation requested:
     - If same directory already generating → skip (dedup)
     - If different directory generating → mark current as low-priority, queue new
   - Use Textual's Worker API for cancellation: `worker.cancel()`

4. Wire pre-caching in app:
   - Add handler for `DirectoryTree.DirectorySelected` or watch for tree node expansion
   - When directory expanded: check if explain data exists for that directory
   - If not: queue background generation (low priority, don't show "generating..." for pre-cache)

5. Improve progress feedback:
   - Replace static "Generating..." text with Textual's `LoadingIndicator` or a custom spinner
   - Show elapsed time: start a timer on generation start, update info bar every second
   - On completion: show "Generated in X.Xs" briefly, then switch to timestamp display

6. Add staleness indicator:
   - When displaying cached data: also check `is_stale()`
   - If stale: append "(outdated - press r to refresh)" to the info bar timestamp
   - Auto-refresh option: could auto-regenerate stale data in background (opt-in)

## Verification Steps

1. Navigate through multiple directories quickly — no duplicate/overlapping generation requests
2. Expand a directory in the tree — explain data pre-generates in background
3. Select a file in pre-cached directory — annotations appear instantly (no "Generating...")
4. Modify a file in a directory, then select another file in that directory — should show "(outdated)" indicator
5. Press `r` on outdated data — regenerates and indicator disappears
6. During generation, see spinner/progress instead of static text
7. Generation with `--max-commits 30` should be noticeably faster than with 50
