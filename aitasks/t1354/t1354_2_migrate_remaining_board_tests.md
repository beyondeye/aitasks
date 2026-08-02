---
priority: medium
effort: medium
depends: [t1354_1]
issue_type: performance
status: Implementing
labels: [test, tui, board]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
created_at: 2026-07-31 07:56
updated_at: 2026-08-02 06:24
---

## Context

Second child of t1354 (parent plan `aiplans/p1354_speed_up_python_test_suite.md`).
Child 1 (t1354_1) built `tests/lib/board_fixture.py` and proved the pattern on
the two worst files. This child migrates the remaining live-tree board modules
(~200s combined at the 2026-07-31 sweep) and adds the regression guard so the
live-tree coupling cannot creep back. Read t1354_1's archived plan
(`aiplans/archived/p1354/p1354_1_*.md` once archived, else `aiplans/p1354/`)
for the harness API and the seam strategy it settled on.

## Key Files to Modify

2026-07-31 enumeration (re-enumerate at task start — grep for
`os.chdir(REPO_ROOT)` in `tests/test_*.py` files lacking any
`TASK_DIR`/tmpdir override), with per-file sweep times:

- `tests/test_board_detail_collapsible.py` (39.0s)
- `tests/test_board_filter_row_layout.py` (38.4s)
- `tests/test_board_view_filter.py` (32.6s — docstring :43-49 explicitly says it runs against the live tree)
- `tests/test_board_topic_view.py` (27.3s)
- `tests/test_board_scroll_focus_jump.py` (21.7s)
- `tests/test_board_toggle_children_gate.py` (17.0s)
- `tests/test_board_empty_column_focus.py` (15.7s)
- `tests/test_board_detail_nested_actions.py` (14.5s)
- `tests/test_board_detail_arrow_nav.py` (10.0s)
- NEW `tests/test_board_fixture_guard.py` (or similar) — the regression guard

Optional, only if cheap (read-only live-metadata readers, low cost):
`tests/test_settings_brainstorm_descriptions.py:27` (reads live
`codeagent_config.json`), `tests/test_profile_editor_shadow_tier.py:150`
(globs live profiles).

## Reference Files for Patterns

- `tests/lib/board_fixture.py` — the harness from t1354_1 (its docstring documents boot-mode vs patch-mode usage).
- Each module above has its own `setUpClass` doing `os.chdir(REPO_ROOT)` + `import aitask_board` — no shared base class exists across files; migration is per-file mechanical but each assertion must be checked.
- Negative-control conventions: the guard must be proven able to fail (seed a violating file in the guard test's own tmpdir and assert the guard reports THAT file — never revert/mutate a real test file to prove it).

## Implementation Plan

1. Re-enumerate + re-measure baseline per file; record in the plan.
2. Migrate file by file to the harness (one file per commit-reviewable step). Migration rule: where a test's property depends on tree volume/shape (populated columns, children, archived tasks, topic groups), the fixture must reproduce that shape — check each assertion rather than assuming; former live-tree `skipTest` guards become unconditional assertions.
3. Add the regression guard test: statically scan `tests/test_board_*.py` sources for `chdir(REPO_ROOT)` (or equivalent) without a TASK_DIR override in the same module; allowlist any justified exception explicitly (e.g. `tests/test_board_header_row_live.py` drives the real board by design). Attribute findings per-file in the failure message.
4. Negative control inside the guard test: write a synthetic violating module to a tmpdir, run the scanner over it, assert it is flagged with the expected identity; also assert the real tree currently passes.

## Verification Steps

- All migrated files green; per-file before/after timings recorded in the plan.
- Guard test: green on the real tree; negctrl asserts the expected violation id (a passing negctrl means the guard is wrong).
- Full suite green; board-test cumulative time drop recorded (~200s → ~30-40s expected).
