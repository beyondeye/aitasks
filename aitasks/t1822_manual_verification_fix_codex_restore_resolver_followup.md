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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2040** id=2026-10-18T06:47:16Z.9a8f9656ef0055640ead3f95 from=t2040 from_verified=yes at=2026-10-18T06:47:16Z base=ec827299895e26e38e2cbcb6141b98f5c560eec3 base_branch=main dirty=no host=omg16
>
> | Your macOS checklist item ("freeze a codex agent and confirm nothing is captured AND an existing hook-captured id is NOT cleared") may no longer hold as written. Context from t2040 (code commit ec8272998):
> | 
> | - MEASURED on codex 0.163.0, but on Linux, not macOS: the interactive TUI fires the SessionStart hook at the session's FIRST TURN. Codex 0.153.4 fired it only under `codex exec`. t2040 also makes the store accept a late hook on a settled restore instead of refusing it.
> | - EXPECTED, NOT measured on macOS: on codex >= 0.163 with the hook installed, a macOS codex agent that has taken a turn gets a hook-recorded session id, so "nothing is captured" would be false for it.
> | - What should still hold on macOS: the freeze-time /proc capture finds nothing (`MISS_NO_PROCESS`) and therefore does NOT clear a stored id. That is the half worth verifying. To see the "nothing captured" case, freeze before the first turn.
> | - The macOS capture path itself (`lsof`/`ps` fallback for `codex_session_for_pid`) was split out of t2040 as t2048.
> | 
> | Suggestion only: version-qualify the item (codex version, hook installed or not) when you verify it.
