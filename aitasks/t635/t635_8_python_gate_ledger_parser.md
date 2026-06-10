---
priority: medium
effort: medium
depends: [t635_1]
issue_type: feature
status: Ready
labels: [gates, python, tui]
created_at: 2026-06-10 18:54
updated_at: 2026-06-10 18:54
---

## Context

Phase 3 of `aidocs/gates/integration-roadmap.md` (decision D6: derive from
ledger only — no new status value, no cached frontmatter summary). The TUIs
need to read per-task gate state cheaply, which means parsing Gate Runs
marker blocks from task bodies.

## Scope

- Shared Python module (under `.aitask-scripts/lib/`) that parses the Gate
  Runs section and derives current per-gate state per the framework doc
  rule (scan back-to-front, first block per gate name = current state).
- Single derivation source of truth on the Python side: board (t635_9),
  monitor (t635_10), and any future TUI import this module — they must not
  fork the parsing logic. Keep behavior aligned with the bash
  `ait gates status` derivation (t635_1); add a cross-check test that runs
  both against the same fixture task files.
- Performance: board already scans all task files; parsing must not
  regress board startup (markers are greppable by design —
  `^> \*\*` prefilter before full parse).

## References

- `aidocs/gates/integration-roadmap.md` (Phase 3, D6)
- `aidocs/gates/aitask-gate-framework.md` ("Gate run marker format",
  "Format rules")
- `aidocs/framework/tui_conventions.md`
