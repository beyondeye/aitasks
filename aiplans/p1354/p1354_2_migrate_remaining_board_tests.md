---
Task: t1354_2_migrate_remaining_board_tests.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_1_board_fixture_harness.md, aitasks/t1354/t1354_3_parallel_test_lane.md, aitasks/t1354/t1354_4_retrospective_measure.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1354_2 — Migrate remaining live-tree board tests + regression guard

## Goal

Migrate the remaining board modules that boot against the live `aitasks/` tree
(~200s combined at the 2026-07-31 baseline) to the t1354_1 harness
(`tests/lib/board_fixture.py`), and add a regression guard so live-tree
coupling cannot creep back. **Read the archived t1354_1 plan first**
(`aiplans/archived/p1354/p1354_1_*.md`, or `aiplans/p1354/` if not yet
archived) — it records the harness API and the cwd-seam strategy.

## Steps

1. **Re-enumerate + baseline**: grep `tests/test_*.py` for
   `os.chdir(REPO_ROOT)` without a TASK_DIR/tmpdir override; re-measure each
   hit per-file. 2026-07-31 list with timings:
   detail_collapsible 39.0s, filter_row_layout 38.4s, view_filter 32.6s
   (docstring :43-49 admits live-tree dependence), topic_view 27.3s,
   scroll_focus_jump 21.7s, toggle_children_gate 17.0s, empty_column_focus
   15.7s, detail_nested_actions 14.5s, detail_arrow_nav 10.0s.
2. **Migrate file by file** (one file per reviewable step). Each module has
   its own `setUpClass` (no shared base across files). Rule: where a test's
   property depends on tree volume/shape (populated columns, children,
   archived tasks, topic groups), the fixture must reproduce that shape —
   check every assertion; former live-tree `skipTest` guards become
   unconditional assertions.
3. **Optional, only if cheap**: read-only live-metadata readers
   `tests/test_settings_brainstorm_descriptions.py:27`,
   `tests/test_profile_editor_shadow_tier.py:150`.
4. **Regression guard** (new `tests/test_board_fixture_guard.py`): statically
   scan `tests/test_board_*.py` sources for `chdir(REPO_ROOT)` (or equivalent)
   without a TASK_DIR override in the same module; explicit allowlist for
   justified exceptions (`tests/test_board_header_row_live.py` drives the real
   board by design). Attribute findings per file in the failure message.
5. **Negative control inside the guard test**: write a synthetic violating
   module into the test's own tmpdir, run the scanner over it, assert it is
   flagged with the expected identity (a passing negctrl means the guard is
   wrong). Never mutate a real test file to prove the guard.

## Verification

- All migrated files green; per-file before/after timings recorded here
  (~200s → ~30-40s expected).
- Guard green on the real tree; negctrl asserts the expected violation id.
- Full suite green.
