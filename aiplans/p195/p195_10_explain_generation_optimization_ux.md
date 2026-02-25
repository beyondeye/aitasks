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
