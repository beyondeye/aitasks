---
Task: t2343_fix_codebrowser_recently_opened_header_count.md
Base branch: main
Output branch: main
---

# t2343 — Keep the codebrowser "Recently Opened (N)" header in sync

## Context

In the codebrowser history screen, the left pane's `Recently Opened (N)` header
(`.aitask-scripts/codebrowser/history_list.py:428`) is recomputed only in
`HistoryLeftPane._update_headers()` (`:471-489`), which runs from `set_data`,
`apply_label_filter` and `update_index`. Opening a task posts a
`HistoryBrowseEvent`; `history_screen.py:336` handles it with
`left.get_recently_opened_list().add_to_history(task_id)`, which re-renders the
list (`RecentlyOpenedList._refresh_display`) but never touches the header. So
after `H` opens t6, the list shows t6 while the header still reads
`Recently Opened (0)` — visible in the applied docs screenshot
`website/static/imgs/codebrowser_task_history.svg` (found by t2278_6).

Fix: make every change to the displayed recent list refresh the header, not
only the add path, by having the list announce its changes and the pane react.

## Implementation steps

1. **`history_list.py` — `RecentlyOpenedList`:**
   - Add a nested message `class Changed(Message)` (Message is already imported
     via `TaskSelected`'s base).
   - Add a `visible_count` property: number of `_history` entries whose
     `task_id` is in `_index_map` (the exact rows `_refresh_display` mounts —
     same rule `_update_headers` uses today).
   - At the end of `_refresh_display()` post `self.Changed()`. This covers every
     route that changes what the list shows: `on_mount`, `set_task_index`
     (index load / progressive chunk) and `add_to_history`.

2. **`history_list.py` — `HistoryLeftPane`:**
   - Extract `_update_recent_header()` that sets `#recent_header` to
     `f"Recently Opened ({recent.visible_count})"`.
   - `_update_headers()` calls it in place of its inline count (keeps the
     synchronous update on the existing paths).
   - Add `on_recently_opened_list_changed(self, event)` → `event.stop()` then
     `self._update_recent_header()` (stop so the message does not bubble to the
     screen/app).

   No change to `history_screen.py` — the caller keeps using
   `get_recently_opened_list().add_to_history(...)`.

3. **Test — new `tests/test_history_recent_header_count.py`** (unittest +
   `App.run_test`, same style as `tests/test_history_progressive_reconcile.py`):
   - Host app mounting `HistoryLeftPane(project_root=<tmpdir>)`; tmpdir via
     `tempfile.TemporaryDirectory` (history file lands under
     `<tmp>/.aitask-history/`).
   - `test_add_to_history_updates_header`: `set_data([t1, t2])` → header
     `Recently Opened (0)`; `add_to_history("t1"-id)` + `pilot.pause()` →
     `Recently Opened (1)`; add a second id → `(2)`; re-add the first → still
     `(2)` (move-to-top, no dup).
   - `test_unknown_task_not_counted`: `add_to_history` of an id not in the
     index → header unchanged (matches rows actually shown).
   - `test_unknown_task_evicts_shown_entry_at_cap` (review concern): pre-write
     history with `MAX_RECENT` (10) valid ids, `set_data` → header `(10)` and
     10 mounted rows. `add_to_history("<unknown>")` + `pilot.pause()` — the
     insert-then-trim in `add_to_history` (`history_list.py:373-375`) evicts
     the oldest shown entry before filtering, so assert header
     `Recently Opened (9)` **and** the mounted row ids
     (`[i.completed_task.task_id for i in recent.query(HistoryTaskItem)]`)
     equal the first 9 seeded ids, in order. This pins header == rows on a
     decreasing transition, not only on increases. (Whether unknown ids
     should be recorded at all is out of scope; the test pins current
     behaviour.)
   - `test_preexisting_history_counted_on_load`: pre-write
     `recently_opened.json` with one valid + one unknown id, `set_data` →
     `(1)`.
   - Read the header text via `str(widget.render())` / `widget.content` —
     whichever the existing Textual version supports (check
     `tests/test_textual_markup_colours.py` for the established accessor).
   - Pre-fix control: run the new add-to-history test against the unfixed
     file (temporarily, in a scratch copy — never `git restore`/stash in the
     shared worktree) to confirm it fails with `(0)`; record result in the
     plan notes.

4. **Regenerate the docs screenshot** (per `aidocs/framework/docs_screenshots.md`):
   - `git status -- website/` first; stop if pages changed by others.
   - **Guard the target SVG itself (review concern).** `apply`'s destination
     check only compares against the hash recorded *at replay time*, so an
     edit another session made to the SVG before the replay would be adopted
     as the baseline and silently overwritten. Before replay:
     ```bash
     svg=website/static/imgs/codebrowser_task_history.svg
     git status --porcelain -- "$svg"            # must print nothing
     git log -1 --format=%h -- "$svg"            # expect f7367ae8a (t2278_6)
     base_sha=$(git show "HEAD:$svg" | sha256sum | cut -d' ' -f1)
     work_sha=$(sha256sum "$svg" | cut -d' ' -f1)
     [ "$base_sha" = "$work_sha" ] || echo "SVG_DIVERGED"
     ```
     Any output from `status`, a different last commit, or `SVG_DIVERGED` →
     **stop and surface it to the user** (name the commit/diff) before
     replaying; do not replace the file.
   - `cd website && ./screenshots.sh replay --scene codebrowser_task_history --png`
     → `BATCH:<id>`; look at the PNG to confirm the header now reads
     `Recently Opened (1)` and the rest still matches the recipe's
     `illustrates:`.
   - Confirm the batch's recorded destination equals the clean baseline: the
     manifest's `codebrowser_task_history` destination `sha256` must equal
     `$base_sha`, and immediately before apply re-run the two checks above
     (status empty, working-file sha256 == `$base_sha`). A mismatch at either
     point → stop and surface the overlap; no apply.
   - `./screenshots.sh preview --batch <id>`, show the user, and only on their
     approval `./screenshots.sh apply --batch <id>` (expect `APPLIED:` with
     `pages=0`, since the page already carries a `static-img`).
   - The recipe itself is not edited (hand edits are forbidden; the route is
     unchanged).

## Verification

- `python3 -m unittest tests/test_history_recent_header_count.py -v` (run with
  the framework venv interpreter) — all pass; pre-fix control fails.
- `python3 -m unittest tests/test_history_progressive_reconcile.py` still
  passes.
- `bash tests/run_all_python_tests.sh --test-dir tests` subset not needed;
  run `tests/test_textual_markup_colours.py` too since it imports
  `history_list`.
- Screenshot PNG visually shows `Recently Opened (1)`.
- `cd website && python3 check_screenshots.py` passes after apply.

## Step 9 (Post-Implementation)

Standard cleanup/archival per task-workflow Step 9 (current-branch mode, no
merge).

## Risk

### Code-health risk: low
- Message posted from `_refresh_display` fires on every progressive chunk
  (`set_task_index`) — one extra cheap `Static.update` per chunk; contained to
  one widget pair · severity: low · → mitigation: none

- Screenshot apply could overwrite another session's uncommitted/newer SVG
  edit, since apply's baseline is recorded at replay time · severity: low
  (residual — addressed by the SVG baseline guard in step 4) · → mitigation:
  none (folded into step 4 at review)

### Goal-achievement risk: low
- Screenshot replay may drift for reasons unrelated to this fix (dataset/TUI
  changes) and need a recipe repair · severity: low · → mitigation: none
  (handled by the screenshot skill's repair loop if it happens; report rather
  than hand-edit)

## Final Implementation Notes
- **Actual work done:** As planned. `RecentlyOpenedList` gained a nested `Changed` message, posted at the end of `_refresh_display()` (so `on_mount`, `set_task_index` and `add_to_history` all announce changes), and a `visible_count` property (history entries present in `_index_map` — exactly the mounted rows). `HistoryLeftPane._update_headers()` now delegates the recent count to a new `_update_recent_header()`, and `on_recently_opened_list_changed` (stops the event) calls it. `history_screen.py` unchanged. New `tests/test_history_recent_header_count.py` (4 pilot tests). Screenshot `website/static/imgs/codebrowser_task_history.svg` regenerated (batch `20261122T155017Z-960510`, `APPLIED ... pages=0`); it now reads `Recently Opened (1)`.
- **Deviations from plan:** None. Two review concerns raised at plan approval were folded in before implementation: (1) the target SVG itself was guarded — clean `git status`, last commit `f7367ae8a`, working-file sha256 == HEAD blob sha256 (`4709d1e6…`) before replay, the manifest's recorded destination sha256 matched that baseline, and the same checks were re-run immediately before `apply`; (2) the eviction test (`test_unknown_task_evicts_shown_entry_at_cap`) asserts both header `(9)` and mounted row ids after an unknown id is pushed onto a full (`MAX_RECENT`=10) list.
- **Issues encountered:** None. Pre-fix control: running the new test file against `git show HEAD:` history_list.py in a scratch copy (no restore/stash in the shared worktree) → 3 of 4 FAIL (`'Recently Opened (0)' != '(1)'` ×2, `'(10)' != '(9)'`); `test_preexisting_history_counted_on_load` passes on both, as expected, since `set_data` already refreshed the header.
- **Key decisions:** Message-based refresh from the list (covers every route that rebuilds rows) rather than a call added at the single `add_to_history` caller. Header text read via `Static.content` (Textual 8.2.7).
- **Upstream defects identified:** None
