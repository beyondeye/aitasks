---
Task: t990_board_detail_view_missing_cross_repo_xdeps.md
Worktree: .
Branch: current
Base branch: current
---

# t990: Show Cross-Repo Dependencies in Board Detail View

## Summary
Add cross-repo dependency visibility to the board task detail popup so
`xdeps`/`xdeprepo` appear in the "Dependencies & hierarchy" section, matching
the task card's existing status formatting.

## Implementation Plan
- Add a `CrossRepoDepsField` near the existing board detail relation field
  classes in `.aitask-scripts/board/aitask_board.py`.
- Render canonical frontmatter refs only when both `xdeprepo` and `xdeps` are
  present:
  - `Done` -> `repo#id`
  - active status -> `repo#id [Status]`
  - missing/unreachable -> `repo#id (UNREACHABLE)`
  - strip optional leading `t` from xdep IDs, matching the card path.
- Add an `xdeps`/`xdeprepo` branch in
  `TaskDetailScreen._build_relations_fields`.
  - With a manager: yield `CrossRepoDepsField`.
  - Without a manager: yield a plain `ReadOnlyField` with raw `repo#id` refs.
  - If only one of `xdeprepo`/`xdeps` exists, show nothing, preserving the
    both-or-neither invariant.
- On Enter:
  - One ref opens via the existing `KanbanApp._open_cross_repo_task(repo, id)`.
  - Multiple refs reuse `CrossRepoRefPickerScreen`.
- Keep `TaskCard.compose` behavior unchanged; use it only as the behavior
  reference for detail-view display semantics.

## Verification
- Add/extend board detail tests to cover:
  - A task with `xdeprepo` + `xdeps` shows one cross-repo dependency field in
    `#sec_relations`.
  - Display formatting covers `Done`, active status, and unreachable statuses.
  - IDs are normalized without leading `t`.
  - Pressing Enter on a single-ref `CrossRepoDepsField` calls the existing
    read-only opener with the expected repo/id.
- Run targeted board tests:
  - `python -m pytest tests/test_board_detail_collapsible.py tests/test_board_picker_tab_nav.py -v`
    with the repo's resolved aitask Python/PYTHONPATH setup.
- Run `bash tests/test_xdeps_parser.sh` as a parser/status-surfacing regression
  guard.

## Step 9
After user review and approval, commit code changes separately from task/plan
files, then run archival through `./.aitask-scripts/aitask_archive.sh 990` per
the shared task workflow.

## Risk

### Code-health risk: low
- The change is additive, localized to the board detail relation path, and
  reuses existing field/picker/open-popup patterns. · severity: low · →
  mitigation: none

### Goal-achievement risk: low
- The task points to the exact missing branch, and existing card/status behavior
  defines the target behavior. · severity: low · → mitigation: none

## Final Implementation Notes
- **Actual work done:** Added a focusable `CrossRepoDepsField` to the board
  detail relation field set and wired `TaskDetailScreen._build_relations_fields`
  to show `xdeprepo`/`xdeps` in the "Dependencies & hierarchy" section when
  both fields are present. Also fixed `CrossRepoTaskScreen` so opened
  cross-repo tasks parse YAML frontmatter, render metadata as read-only text,
  and feed only the task body to the Markdown widget.
- **Deviations from plan:** Added the cross-repo popup frontmatter/body split
  after live review showed the opened linked task detail was rendering raw
  YAML frontmatter as Markdown. `TaskCard.compose` behavior was left unchanged
  and used only as the display-behavior reference.
- **Issues encountered:** The resolved aitask Python environment does not have
  `pytest` installed, so targeted Python tests were run through `unittest`, the
  same fallback used by `tests/run_all_python_tests.sh`.
- **Key decisions:** The detail field only renders canonical frontmatter
  cross-repo dependencies, preserves the both-or-neither invariant, normalizes
  leading `t` from xdep IDs, and reuses the existing read-only cross-repo opener
  / picker behavior on Enter. The cross-repo popup keeps its read-only behavior
  and does not acquire locks or route through the editable local task detail
  flow.
- **Verification:** `python -m unittest tests.test_board_detail_collapsible
  tests.test_board_picker_tab_nav -v` passed; `bash tests/test_xdeps_parser.sh`
  passed; `python -m py_compile .aitask-scripts/board/aitask_board.py` passed.
- **Upstream defects identified:** None.

## Post-Review Changes

### Change Request 1 (2026-06-15 10:29)
- **Requested by user:** The new cross-repo dependency field worked, but opening
  a linked cross-repo task showed a broken metadata section because the popup
  rendered raw YAML frontmatter as Markdown.
- **Changes made:** `CrossRepoTaskScreen` now parses task frontmatter, renders
  metadata in a separate read-only `Static`, and renders only the body through
  `Markdown`.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_detail_collapsible.py`.
