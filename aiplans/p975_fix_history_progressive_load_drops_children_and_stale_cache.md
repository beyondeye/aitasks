---
Task: t975_fix_history_progressive_load_drops_children_and_stale_cache.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Fix History progressive-load drops children & stale-cache-on-reopen (t975)

## Context

In `ait codebrowser`'s History screen, completed **child tasks never appear** in
the Completed Tasks list. The root cause is **not** indexing — children *are*
indexed — but the progressive-loading display logic:

1. `load_task_index_progressive` (`history_data.py:212`) flushes a chunk every
   200 files; `iter_all_archived_markdown` yields loose **parents first**, so
   chunk 1 is almost all parents. Each chunk re-sorts the growing index by
   commit date.
2. `HistoryTaskList.update_index` (`history_list.py:234`) only refreshes the
   "Load more" counter — it leaves already-mounted rows untouched. When a later
   chunk brings a recent child that re-sorts into positions 0–19 (already paged
   past), the displayed window never reconciles, so the child can never appear,
   even via "Load more". The general defect: **any** task whose sort position
   improves between chunks is silently skipped; children are the systematic
   victims.
3. On re-opening the screen within a session, `HistoryScreen` reuses the cached
   `app._history_index` (`history_screen.py:106,118`) and never reloads, so
   tasks archived mid-session (by agents in other tmux windows) stay invisible
   until the user manually presses `r`.

The manual `r` refresh's first-chunk path (`_on_reload_chunk`, is_first branch)
already implements the correct preserve-and-re-render pattern; this fix
generalizes it to the progressive path and adds a background auto-reload on open.

## Approach

Two focused changes, both in `.aitask-scripts/codebrowser/`.

### Fix 1 — Reconcile the displayed window on every progressive chunk

Rewrite `HistoryTaskList.update_index` (`history_list.py:234`) so that, instead
of only touching the indicator, it **re-renders the currently displayed window
from the freshly re-sorted index**, preserving the number of loaded items
(`_offset`), scroll position, and the focused row. Keep a fast path so we only
re-mount when the window content actually changed (avoids needless flicker on
the common case where a later chunk only appends older tasks below the fold):

- Recompute `_full_index`, `_child_counts`, and filtered `_index` (label filter
  honored, as today via `filter_index_by_labels`).
- `displayed = min(self._offset or self._chunk_size, len(self._index))`.
- Compare `[item.task_id for current HistoryTaskItem rows]` vs
  `[t.task_id for t in self._index[:displayed]]`. **If equal** → just refresh the
  "Load more" indicator and return (preserves today's cheap path).
- **If changed** → capture `scroll_y` and the focused row's `task_id` (only if it
  belongs to this list), remove all `HistoryTaskItem`s, re-mount the first
  `displayed` rows from the new `_index` (reusing module-level
  `_compute_child_counts`), set `_offset = displayed`, refresh the indicator, and
  restore scroll + focus via a short `set_timer(0.05, …)` (the existing
  `_load_chunk` already defers layout-sensitive work this way).

Because `_on_index_chunk` (subsequent chunks) and `_on_reload_chunk` (non-first
chunks) both already call `left.update_index(index)`, this single change fixes
**both** the initial progressive load and the manual `r` refresh's later chunks.
The first-chunk paths keep using `set_data` (full render) unchanged.

### Fix 2 — Auto-refresh on open with a cached index

In `HistoryScreen._populate_and_restore` (`history_screen.py:123`), after
rendering the cache, kick off a background reload so mid-session archives appear
without manual `r`, with debounce + change-only notification:

- Add `self.app._history_cached_at = time.monotonic()` wherever the index is
  cached (`_on_index_chunk`, `_on_reload_chunk`), and initialize
  `self._history_cached_at = 0.0` in `codebrowser_app.py` (next to the other
  `_history_*` attrs, ~line 421).
- New `_maybe_auto_reload()`: if `time.monotonic() - app._history_cached_at` is
  under a `AUTO_RELOAD_DEBOUNCE_S = 5.0` threshold, skip (handles quick screen
  toggles); otherwise record `self._reload_baseline_ids = {task_ids}` and launch
  the reload worker in **auto** mode.
- Reuse the existing `_reload_data`/`_on_reload_chunk` machinery by threading an
  `auto: bool = False` flag through both. In auto mode: **do not** push the
  blocking `HistoryRefreshModal`, and skip the modal-dismiss timer. The
  first-chunk `set_data` + restore (scroll/labels/task/showing_plan) already
  preserves the just-restored view, so the background reload is seamless. Guard
  the scroll-restore race: if `task_list.scroll_y == 0` but
  `self._restore_scroll_y > 0`, use the latter.
- At the end of `_reload_data` when `auto`, `call_from_thread` a
  `_finish_auto_reload()` that compares the final index's task_ids against
  `_reload_baseline_ids` and `self.notify("History updated", timeout=2)` only if
  they differ (the "indicator only when the reload actually changes the index"
  requirement).

`_reload_data` is already `exclusive=True, group="history_reload"`, so a manual
`r` press cleanly supersedes an in-flight auto reload.

## Files to modify

- `.aitask-scripts/codebrowser/history_list.py` — rewrite `update_index`
  (reconcile-and-re-render with fast path + scroll/focus preserve).
- `.aitask-scripts/codebrowser/history_screen.py` — `_maybe_auto_reload`,
  `_finish_auto_reload`, `auto` flag through `_reload_data`/`_on_reload_chunk`,
  cache-timestamp writes, scroll-race guard; call `_maybe_auto_reload` at the end
  of `_populate_and_restore`.
- `.aitask-scripts/codebrowser/codebrowser_app.py` — init `_history_cached_at = 0.0`.
- `tests/test_history_progressive_reconcile.py` (new) — headless Textual pilot.

## Test

New `tests/test_history_progressive_reconcile.py`, modeled on
`tests/test_brainstorm_dimension_row_expand.py` (host `App` mounting the widget,
`async with app.run_test()` pilot):

- Build a chunk-1 index of parents only (e.g. t973, t972, t953 …) and a fuller
  final index where recent children (t891_1/2/3) sort into the top-20 by
  `commit_date`. Construct `CompletedTask` instances directly.
- Mount a `HistoryTaskList`, call `set_index(chunk1, counts)`, assert displayed
  rows == chunk-1 top-20 (no children). Then call `update_index(final_index)`
  and assert the displayed `HistoryTaskItem` rows now include the children,
  interleaved by date, with `_offset` preserved.
- Assert the fast path: calling `update_index` with an index whose top-`displayed`
  window is unchanged does not change the mounted rows.
- Assert "Load more" never skips: after `update_index`, the union of displayed
  ids + remaining (from one `_load_chunk`) covers the full index with no gaps.

Run: `python3 -m pytest tests/test_history_progressive_reconcile.py -v`
(and `bash tests/run_all_python_tests.sh` for regression).

Manual: `./ait codebrowser` → `H` (History); confirm recent children (t891_3,
t952_4) appear interleaved once loading completes; toggle the screen off/on after
another session archives a task and confirm it shows without pressing `r`;
verify label filter, scroll restore, recently-opened, `[+N children]` badge, and
manual `r` still work.

## Notes / caveats

- **Uncommitted unrelated changes in the working tree.** `git status` shows
  pre-existing edits (a `spawn_in_terminal` refactor) in `history_screen.py`,
  `codebrowser_app.py`, and several other TUIs from another in-progress
  session. At commit time (Step 8) I will stage **only the t975 hunks** (via
  `git add -p` on the two shared files) so the unrelated refactor is not swept
  into this bug-fix commit. I'll surface this at the review step.
- Step 9 cleanup/archival and merge are handled by the standard workflow.

## Risk

### Code-health risk: medium
- `update_index` is a load-bearing display path; the rewrite changes row
  re-mount behavior, so a focus-loss or scroll-jump regression is plausible if
  the preserve logic is mishandled · severity: medium · → mitigation: in-scope
  headless test + Step 8c manual verification
- Widget re-mount on progressive chunks could introduce visible flicker · severity:
  low · → mitigation: fast-path that skips re-mount when the window is unchanged

### Goal-achievement risk: low
- None identified — root cause is empirically verified and confirmed in-code;
  the fix generalizes the already-correct `_on_reload_chunk` pattern and every
  acceptance criterion maps to a concrete change.

## Final Implementation Notes

- **Actual work done:** Implemented both fixes exactly as planned.
  - `history_list.py`: rewrote `HistoryTaskList.update_index` to reconcile the
    displayed window against the re-sorted index — recomputes `_index`/
    `_child_counts`, compares the current row IDs to the new top-`displayed`
    window, fast-path returns (indicator-only refresh) when unchanged, and
    otherwise re-mounts the window while preserving `_offset`, scroll, and the
    focused row. Extracted `_refresh_load_more()` and added
    `_restore_window_view()`.
  - `history_screen.py`: added `AUTO_RELOAD_DEBOUNCE_S = 5.0`,
    `_reload_baseline_ids`, `_maybe_auto_reload()` (called at the end of
    `_populate_and_restore`), `_finish_auto_reload()` (change-only notify),
    threaded an `auto` flag through `_reload_data`/`_on_reload_chunk`, wrote the
    cache timestamp on every chunk, guarded the scroll-restore race, and
    suppressed the blocking modal on the auto path.
  - `codebrowser_app.py`: initialized `_history_cached_at = 0.0`.
  - Added `tests/test_history_progressive_reconcile.py` (3 headless pilots).
- **Deviations from plan:** None substantive. The "uncommitted unrelated
  changes" caveat became moot: between planning and commit, another session
  committed/reset the `spawn_in_terminal` refactor, so the two shared files
  (`history_screen.py`, `codebrowser_app.py`) ended up containing only t975
  changes — no selective `git add -p` was needed.
- **Issues encountered:** `pytest` is not installed in the venv; ran the suite
  via `python3 -m unittest`. New tests (3) and existing `test_history_data`
  (28) all pass.
- **Key decisions:** Routed both the initial progressive load and manual `r`
  reload through the same reconciling `update_index` (single fix point), kept a
  fast path to avoid needless re-mounts/flicker, and reused the existing
  `_reload_data`/`_on_reload_chunk` worker for auto-refresh via an `auto` flag
  rather than duplicating a worker.
- **Upstream defects identified:** None
