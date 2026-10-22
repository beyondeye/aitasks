---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codex, frozen, session_persistence]
anchor: 2040
followup_kind: upstream_defect
created_at: 2026-10-22 10:45
updated_at: 2026-10-22 10:45
---

## Origin

Spawned from t2109 during Step 8b review. Low priority by the user's call: a
very rare edge case.

## Upstream defect

- `.aitask-scripts/aitask_session_hook.sh:194 — a SAME-kind agent started inside another (e.g. `claude -p` run from a claude agent's Bash tool) inherits TMUX_PANE, @aitask_record and AITASK_AGENT_STRING, passes the process-tree guard (the pane process is its ancestor), and its SessionStart rebinds the pane's record to the nested session, so a restore resumes the nested session instead of the pane's own. The t2109 conflict refusal catches only a DIFFERENT kind; found by code reading.`

## Diagnostic context

- HARD CONTRACT 5 (t2047) requires only that the pane's `#{pane_pid}` be an
  ANCESTOR of the hook. A nested agent's hook satisfies that.
- t2109 added step 5c: when a well-formed `AITASK_AGENT_STRING` names a kind
  other than the payload's transcript-shape kind, the hook records nothing.
  That catches a nested agent of a different CLI (a `codex exec` from a claude
  Bash tool), but a nested agent of the SAME CLI agrees on both, so it still
  upserts with `--id <@aitask_record>` and overwrites the pane record's session
  id and transcript.
- A headless `claude -p` does fire SessionStart: the fixture README records a
  headless capture with the same keys minus `model`.
- Not reproduced live; found by reading the hook against t2047's guard.

## Suggested fix

Measure first: does the payload of a headless/nested agent differ from the
pane agent's (e.g. `claude -p` omits `model`; `source`)? If not, compare the
hook's nearest agent ancestor with the pane process itself: record only when
the agent that fired the hook IS the pane's own agent process, or that agent
is the pane shell's foreground job. Refuse otherwise, which is the fail-safe
direction (HARD CONTRACT 5).
