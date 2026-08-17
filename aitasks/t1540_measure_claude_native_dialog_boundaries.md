---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-17 12:45
updated_at: 2026-08-17 12:45
---

## Origin

Spawned from t1518 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/review_loop.py:DELIBERATELY_UNANCHORED_KINDS` — Claude's
  `claude_help_bar`, `claude_proceed` and `claude_trust_folder` have no measured
  boundary, so a Claude pane parked at a tool-permission dialog classifies
  `UNKNOWN` and the auto-recheck loop silently never fires. This is the same
  under-detection t1518 closed for Codex and OpenCode, still open for Claude.
  Pre-existing; closing it needs its own live measurement of Claude's dialogs.

## Diagnostic context

t1518 added native-dialog boundary rows for Codex and OpenCode so that a followed
pane parked at a permission dialog can tell real work from a selection redraw.
Building the completeness guard for that work (`ArmedAgentKindCoverageTests.
test_every_armed_agent_kind_resolves`) forced every prompt kind an armed agent can
report to either resolve to a boundary or be listed in `DELIBERATELY_UNANCHORED_KINDS`
with a written reason. Three Claude kinds had to be listed there, which is how the
gap became visible: it was previously indistinguishable from a forgotten row.

Only `claude_plan_approval` has a measured boundary today. `claude_help_bar` is the
one that matters most in practice — t1474 recorded that it, not `claude_proceed`, is
what actually matches Claude's tool-permission dialogs, because the question text
renders above `_PROMPT_DETECTION_TAIL_LINES`.

## Suggested fix

Follow the recipe in `aidocs/framework/shadow_agent.md` §"Recipe: measuring a new
agent's readiness surfaces", as t1518 did: drive a live Claude pane on a private
tmux socket, provoke each dialog, and check the candidate boundary line appears
exactly once, only while the dialog is live, and above everything that changes
during selection. Then add rows to `NATIVE_DIALOG_BOUNDARIES` and remove the
corresponding `DELIBERATELY_UNANCHORED_KINDS` entries — the completeness guard
keeps the two in step. See t1518's archived plan for the measurement table format
and the harness gotchas (ground-truth channel, chunked send-keys, fixture hygiene).
