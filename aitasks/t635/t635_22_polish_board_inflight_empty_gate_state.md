---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [gates, aitask_board, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-16 12:50
updated_at: 2026-06-30 17:33
---

Fix the board In-Flight view polish issues found during live tmux inspection
after t635_9.

## Problem

The new In-Flight action view is classifying active Implementing tasks
correctly, including non-gated tasks, but two UI details need cleanup:

- The per-row operation hint line is effectively blank because labels such as
  `[p pick]` are interpreted as Rich/Textual markup instead of literal text.
- The fallback copy "no gate ledger" is too technical for board users. It
  should use friendlier wording such as "No gate information yet" or an
  equivalent concise phrase.

## Acceptance Criteria

- In-Flight rows visibly show their available operations, including pick/resume
  and human gate actions where applicable.
- Literal shortcut hints render correctly and are not swallowed by markup
  parsing.
- Tasks with status Implementing but no Gate Runs section still appear in Agent
  can continue, but their user-facing text says "No gate information yet" or
  similarly clear non-technical wording.
- Tests cover both the rendered operation hint text and the no-gate copy.
- Existing board view/filter tests remain green.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T14:33:13Z status=pass attempt=1 type=human
