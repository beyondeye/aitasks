---
priority: medium
effort: medium
depends: [975]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [975]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 12:57
updated_at: 2026-06-12 07:50
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t975

## Verification Checklist

- [x] Open `ait codebrowser` -> press `H`; once loading completes, confirm recent CHILD tasks (e.g. t891_3, t952_4) appear interleaved by commit date in Completed Tasks (not just parents) — PASS 2026-06-12 07:50 auto: live codebrowser History (h) shows children t891_1/2/3/4, t952_5/6, t822_3, t756_7 interleaved by commit date with parents (1215 total); headless test_children_surface_after_later_chunk asserts the reconcile mechanism
- [x] Scroll the Completed Tasks list and click/activate "Load more" repeatedly; confirm no index entry is ever skipped and there are no duplicate rows — PASS 2026-06-12 07:50 auto: test_load_more_never_skips asserts displayed+one-load-more covers full index with no gaps; live list window shows no duplicate ids; offset model in _load_chunk
- [defer] While the History screen is open in one session, archive a task from another tmux window; toggle the History screen off (`h`/`esc`) and back on; confirm the newly archived task appears WITHOUT pressing `r` (and a brief "History updated" notice shows) — DEFER 2026-06-12 07:50 auto: needs a 2nd session archiving a real task mid-session + observing auto-refresh and the 'History updated' toast on reopen. notify-on-change (_finish_auto_reload) + debounce are code-confirmed, but the cross-session/destructive flow is not safely automatable — human check
- [x] Quick-toggle the History screen off and on within ~5s; confirm it does NOT re-scan (debounce) and the view is stable — PASS 2026-06-12 07:50 auto: _maybe_auto_reload returns early when monotonic age < AUTO_RELOAD_DEBOUNCE_S=5.0 (history_screen.py:164-166) so a quick toggle does not re-scan; deterministic, code-verified
- [x] Confirm preserved behaviors: label filter (`l`), scroll-position restore on reopen, Recently Opened list, the `[+N children]` parent badge, and manual `r` refresh all still work — PASS 2026-06-12 07:50 auto: live shows [+7 children] badge (t756), Recently Opened(10), l/r bindings; code paths intact: apply_label_filter restore (history_screen.py:136,276), _restore_scroll, RecentlyOpenedList. Scroll-restore-on-reopen code-confirmed, not exercised live
- [defer] Watch the list during the initial progressive load; confirm no visible flicker and that keyboard focus / selection is not lost when later chunks arrive — DEFER 2026-06-12 07:50 auto: 'no visible flicker' is a visual UX judgement during async progressive load. Fast-path (test_unchanged_window_uses_fast_path, no re-mount) and focus-preserve (_restore_window_view) mitigate and are tested, but flicker/selection-loss needs human eyes — human check
