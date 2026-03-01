---
Task: t195_10_explain_generation_optimization_ux.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_4_*.md, aitasks/t195/t195_5_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_10 — Explain Generation Optimization and UX

## Steps

### 1. Pre-caching on tree expansion
- Hook `on_tree_node_expanded` event
- Check if directory has cached data
- If not: queue low-priority background generation

### 2. Generation queue
- Track `_active_generation` and `_pending_queue`
- Serialize concurrent requests
- Use Textual `Worker.cancel()` for cancellation

### 3. Progress indicator
- Replace "Generating..." with spinner/animated dots
- Show elapsed time (timer updated every second)

### 4. Cache staleness detection
- `is_stale()`: compare run timestamp vs `git log -1 --format=%ct -- <dir>`
- Show "(outdated)" in info bar
- `r` key still forces refresh

### 5. Reduce commit depth
- Pass `MAX_COMMITS=30` env to extract script for codebrowser
- Faster generation for recent-task-focused use case

## Verification
- Tree expansion triggers pre-caching
- No duplicate concurrent generations
- Spinner visible during generation
- "(outdated)" shows when data is stale
- `--max-commits 30` is faster

## Final Implementation Notes
- **Actual work done:** All 5 planned steps implemented as specified. Added `--max-commits 30` parameter, cache staleness detection via `git log` comparison, generation queue with pre-caching on directory expansion, progress timer with elapsed time display (0.5s interval), and staleness indicator in info bar.
- **Deviations from plan:** Used `--max-commits` CLI flag instead of `MAX_COMMITS` env var — the extract script already supported this flag. Used `set_interval(0.5)` timer for progress updates instead of a Textual LoadingIndicator widget (simpler, less widget overhead). Did not use `Worker.cancel()` for the queue — instead used a cooperative check (`is_generating()`) in the pre-cache worker to defer when busy.
- **Issues encountered:** None significant. The `DirectoryTree.DirectorySelected` event fires correctly for pre-caching. The `@work(exclusive=False, group="precache")` decorator allows pre-cache to run alongside the main exclusive generation worker.
- **Key decisions:** Generation queue is lightweight (set-based) rather than a full asyncio.Queue, since pre-cache is fire-and-forget. Git timestamp results cached per dir_key and invalidated on generation/refresh. "Generated in X.Xs" message shown briefly (2s) then switches to normal timestamp.
- **Notes for sibling tasks:** This is the final child task for t195. All codebrowser features are now complete: file tree, code viewer with syntax highlighting, explain data generation, annotation overlay, cursor navigation, Claude Code integration, rendering hardening, viewport windowing, and now generation optimization/UX.
