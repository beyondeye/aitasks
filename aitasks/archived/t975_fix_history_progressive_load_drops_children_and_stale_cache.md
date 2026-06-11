---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [codebrowser, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 12:29
updated_at: 2026-06-11 12:57
completed_at: 2026-06-11 12:57
---

## Problem

In the `ait codebrowser` History screen, completed **child tasks never appear** in the Completed Tasks list — only parent tasks show. For fully implemented parents this is acceptable (the parent row carries a `[+N children]` badge), but for partially implemented parents (e.g. t891 with t891_1..3 archived while the parent is still active) the completed work is completely invisible.

Additionally, re-opening the History screen within a session **reuses a stale in-memory index** with no automatic refresh — tasks archived mid-session (e.g. by agents in other tmux windows) stay invisible until the user manually presses `r`.

## Root cause (verified empirically)

Child tasks ARE indexed (537 of 1209 in this repo at exploration time) but are dropped by the progressive-loading display logic:

1. **Scan order biases the first chunk to parents.** `iter_all_archived_markdown` (`.aitask-scripts/lib/archive_iter.py:74-90`) yields loose parent files first, then loose child files in `archived/t<N>/` subdirs, then tar bundles. `load_task_index_progressive` (`.aitask-scripts/codebrowser/history_data.py:212`) flushes a chunk every 200 files, so chunk 1 contains all recent loose parents but almost no recent children.

2. **Progressive updates never reconcile displayed rows.** `HistoryTaskList.update_index` (`.aitask-scripts/codebrowser/history_list.py:234`) deliberately keeps already-mounted rows and only updates the "Load more" counter, while `_offset` (e.g. 20) is applied against the NEW re-sorted index. Recent children sort into positions 0-19 of the new index — positions the display has already paged past — so they can never appear, not even via "Load more".

   Verified: the live pane's top-20 exactly equals chunk 1's top-20 (all parents: t973, t972, t953, ...); the 10 entries missing vs the final index's top-20 are exactly the recent child tasks (t891_1/2/3, t822_3, t756_7, t952_2-6). The general defect: ANY task whose sort position improves between progressive chunks is silently skipped — children are the systematic victims due to scan order.

3. **Stale cache on reopen.** `HistoryScreen` reuses `app._history_index` when given (`.aitask-scripts/codebrowser/history_screen.py:92,106`) and triggers no background reload; only the manual `r` binding (`_reload_data`) refreshes.

Note: manual `r` refresh works correctly — `_on_reload_chunk` calls `left.set_data(index)` on the first chunk, which fully re-renders the list (preserving scroll/labels/selection). That is the model for the fix.

## Required fix

1. **Reconcile displayed rows when progressive chunks arrive.** Make `update_index` (or its caller `_on_index_chunk` in history_screen.py) re-render the displayed window from the new sorted index instead of leaving stale rows in place — preserving scroll position, focus, and the number of loaded chunks (the existing `_on_reload_chunk` first-chunk path already implements this preserve-and-re-render pattern and can likely be reused). Alternatively, track displayed rows by task_id rather than numeric offset so "Load more" cannot skip entries that sorted above the current page.

2. **Auto-refresh on open with cached index.** When the History screen mounts with a non-None `cached_index`, render the cache immediately for responsiveness, then kick off a background reload (the existing `_reload_data` worker) so mid-session archives appear without manual `r`. Consider showing the lightweight refresh indicator only when the reload actually changes the index, and debouncing (e.g. skip auto-reload if the cache is only a few seconds old, such as quick screen toggles).

## Acceptance criteria

- Opening the History screen on this repo shows recent child tasks (e.g. t891_3, t952_4) interleaved by commit date in the Completed Tasks list once loading completes.
- "Load more" never skips index entries.
- Re-entering the History screen after a task was archived elsewhere shows the new task without pressing `r`.
- Existing behavior preserved: label filter, scroll restore, recently-opened list, `[+N children]` badge, manual `r` refresh.
- Headless Textual test covering the progressive-chunk reconciliation (drive `set_data` + `update_index` with chunk sequences where children appear only in later chunks).
