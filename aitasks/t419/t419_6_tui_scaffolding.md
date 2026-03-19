---
priority: medium
effort: medium
depends: [t419_5, 1, 3]
issue_type: feature
status: Implementing
labels: [brainstorming, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-18 14:58
updated_at: 2026-03-19 21:56
---

## Context
The brainstorm engine (t419) needs a TUI for interactive orchestration of the design space exploration. This task scaffolds the Textual app — placeholder screens and widgets — so follow-up tasks can implement the full interactive logic. The TUI is based on the crew dashboard pattern.

## Key Files to Read
- aidocs/brainstorming/brainstorm_engine_architecture.md — TUI screen layout and orchestration flow (created by t419_1)
- .aitask-scripts/agentcrew/agentcrew_dashboard.py — crew dashboard TUI (base patterns: App class, Screen class, bindings, data layer, status colors)
- .aitask-scripts/aitask_crew_dashboard.sh — bash wrapper pattern (python detection, package checks, exec)
- .aitask-scripts/diffviewer/diffviewer_app.py — diffviewer placeholder app pattern
- .aitask-scripts/diffviewer/plan_loader.py — plan file parsing (reuse for loading proposals)

## Reference Files for Patterns
- .aitask-scripts/agentcrew/agentcrew_dashboard.py lines 1-56 — imports, constants, data layer setup
- .aitask-scripts/aitask_crew_dashboard.sh — full bash wrapper (copy and adapt)
- .aitask-scripts/aitask_diffviewer.sh — alternative bash wrapper pattern

## Deliverable

### aitask_brainstorm_tui.sh — Bash Wrapper
- Same pattern as aitask_crew_dashboard.sh
- Checks for python venv or system python
- Checks for textual and pyyaml packages
- Warns on incapable terminals
- Accepts task number as argument
- Execs brainstorm_app.py with arguments

### brainstorm_app.py — Textual App Skeleton
- BrainstormApp(App) class with:
  - TITLE = "ait brainstorm"
  - Key bindings: q=quit, d=dag view, n=node detail, c=compare, ?=help
  - CSS styling (reuse status colors from crew dashboard)
  - Accepts task_num as CLI argument
  - Loads session data on startup using brainstorm_session.py

### Placeholder Screens (can be empty Screen subclasses with labels):
- DAGScreen — will show the proposal DAG tree
- NodeDetailScreen — will show a single node metadata + proposal
- CompareScreen — will integrate diff viewer for comparing proposals
- ActionScreen — will show available operations (explore, compare, hybridize, detail, finalize)

### Integration Points (documented but not implemented):
- Import path for diffviewer components
- Import path for brainstorm_dag.py and brainstorm_session.py
- Import path for brainstorm_crew.py (for triggering operations)

### Dispatcher Entry
- Add brainstorm TUI launch to ait dispatcher (when ait brainstorm task_num is called without a subcommand)

## Verification
- ait brainstorm 999 launches the TUI (after init)
- TUI shows app title and placeholder screens
- Key bindings switch between placeholder screens
- No import errors (all referenced modules exist or are handled gracefully)
- shellcheck passes on aitask_brainstorm_tui.sh
