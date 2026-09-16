---
priority: medium
effort: medium
depends: [1804]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1804]
anchor: 1797
followup_kind: manual_verification
created_at: 2026-09-16 23:26
updated_at: 2026-09-16 23:26
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1804

## Verification Checklist

- [ ] Freeze a live codex agent pane, then check its store record (`./.aitask-scripts/aitask_agent_sessions.sh show <id>`): codeagent_session_id is set AND agent_string reads codex/<the model it was launched with>.
- [ ] Restore that frozen agent and confirm the pane relaunches as `codex resume <sid>` and replays THAT agent's own conversation — not another session's.
- [ ] Run two codex agents in the same repo, freeze both, and confirm each record captured its own distinct session id (the t1797 symptom: one of them used to get the other's).
- [ ] Freeze a codex agent that has taken no turn yet: no session id is recorded (it has no rollout open yet) and a restore reports no_session, i.e. the re-pick path.
- [ ] Freeze a claude agent and confirm its hook-captured session id is left untouched by the codex capture.
- [ ] Type /new in a codex TUI, freeze again, and confirm the record's session id updates to the new conversation rather than keeping the old one.
- [ ] On macOS (if available): freeze a codex agent and confirm nothing is captured AND an existing hook-captured id is NOT cleared.
