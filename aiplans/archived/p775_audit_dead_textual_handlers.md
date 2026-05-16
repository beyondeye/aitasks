---
Task: t775_audit_dead_textual_handlers.md
Base branch: main
plan_verified: []
---

# t775 — Audit dead Textual handlers (camel_to_snake adjacent-uppercase pitfall)

## Context

In t749_6, three handlers on `DAGDisplay` (a widget class with adjacent
uppercase letters) were discovered to be dead in production: Textual's
auto-dispatch uses `camel_to_snake(SenderClass)` which collapses
`DAGDisplay → dagdisplay` (no underscore between `DAG` and `Display`), so
hand-written `on_dag_display_*` handlers were silently skipped. The fix
in t749_6 was switching to `@on(DAGDisplay.NodeSelected)` etc.

This follow-up audits the rest of `.aitask-scripts/` for the same class
of bug — other widget/message classes whose names contain adjacent
uppercase characters and whose handlers might be similarly dead.

## Audit method

For each Python source file under `.aitask-scripts/`:

1. Enumerated every class definition (top-level + nested) whose name
   contains a run of ≥2 uppercase letters anywhere
   (`[A-Za-z]*[A-Z]{2,}[A-Za-z]*`).
2. Enumerated every `def on_<snake>` handler and inspected the type
   annotation on its `event` parameter (`Sender.Inner` form), to spot
   handlers whose name does not match the auto-dispatch derivation
   `on_{camel_to_snake(Sender)}_{camel_to_snake(Inner)}`.
3. Verified all `Message` subclasses (top-level and inner) — both
   sender class names and message class names participate in the
   auto-dispatch resolution.

Authoritative resolution check:

```bash
python3 -c "from textual.case import camel_to_snake; print(camel_to_snake('DAGDisplay'))"
# -> dagdisplay
```

Verified other candidate class names (`AgentCard`, `NodeRow`,
`CycleField`, `FuzzySelect`, `SectionMinimap`, `SectionRow`,
`OperationRow`, `DimensionRow`, `ColorSwatch`, `TaskSelected`,
`TrackedFilesRefreshed`, `RecentFileSelected`, `NavigateToFile`,
`HistoryBrowseEvent`, `OperationOpened`, `Activated`, `OptionList`,
`DataTable`, `ListView`, `TabbedContent`, `DirectoryTree`,
`CodeViewer`, …) — all convert cleanly with a `_` at each camel
boundary.

## Audit results

- **Only one** class in `.aitask-scripts/` has adjacent uppercase
  letters: `DAGDisplay` (`brainstorm/brainstorm_dag_display.py:402`).
- Its three message handlers in `brainstorm/brainstorm_app.py:3849-3870`
  (`on_dag_display_node_selected`, `on_dag_display_head_changed`,
  `on_dag_display_operation_opened`) **already** carry `@on(...)`
  decorators wiring them by message class (committed in t749_6) — so
  they fire correctly despite the name mismatch.
- **Zero additional dead handlers** found anywhere else under
  `.aitask-scripts/`.

## Implementation plan

No code changes. The audit is the deliverable. The plan file (this
file) becomes the record of the audit; the Final Implementation Notes
section below records what was checked, so a future maintainer hitting
the same class of bug can quickly see this audit was done and what its
scope was.

### Step 9 — Post-implementation

Standard archival per `task-workflow/SKILL.md` Step 9. No worktree
(profile `fast` → `create_worktree: false`). No code commit (no source
changes). Single plan commit via `./ait git`, then `aitask_archive.sh
775`.

## Out of scope

- Adding a regression-prevention test (an AST scanner that catches
  future occurrences automatically): single occurrence with a known
  cause does not warrant speculative validation infrastructure. If the
  same pitfall surfaces a second time, that would be the moment to
  reconsider.
- Adding `@on(...)` decorators to non-conflicting handlers — they
  already work via auto-dispatch and require no change.

## Final Implementation Notes
(filled in at Step 8)

- **Actual work done:** Audit of `.aitask-scripts/**/*.py` for the
  `camel_to_snake` adjacent-uppercase pitfall. Verified only
  `DAGDisplay` is affected; its handlers in `brainstorm_app.py` were
  already fixed in t749_6 via `@on(...)` decorators.
- **Deviations from plan:** Initial draft proposed adding a regression
  test; user pushed back ("Is adding new test actually needed if this
  happened only in a single case?") — dropped the test, kept audit
  only.
- **Issues encountered:** None.
- **Key decisions:** No code changes — audit confirmed no further dead
  handlers exist.
- **Upstream defects identified:** None.
