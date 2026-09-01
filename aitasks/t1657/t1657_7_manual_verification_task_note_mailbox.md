---
priority: medium
effort: medium
depends: [t1657_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1657_3, 1657_4, 1657_5]
anchor: 1657
followup_kind: manual_verification
created_at: 2026-09-01 12:42
updated_at: 2026-09-01 12:42
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1657_3] First pick of a task with unread notes: entries are displayed, attributed, and show base/at/dirty; nothing is marked read yet.
- [ ] [t1657_3] Choose "Keep unread" at the acknowledgement prompt, then pick the task again: the same entries surface a second time.
- [ ] [t1657_3] Choose "Acknowledge", then pick the task again: the entries do NOT surface. Overall each note is shown exactly once.
- [ ] [t1657_3] Under a non-interactive profile (remote/headless), notes auto-acknowledge and the receipt records mode=auto.
- [ ] [t1657_3] A note is rendered as advisory: sender shown as claimed, dirty=yes visibly warns, and nothing in the note triggers action on its own.
- [ ] [t1657_4] With a second live Claude session holding the target task on this host, sending a note reaches it live; the message names the same note id present in the target's ## Inbox.
- [ ] [t1657_4] The sender performed NO manual tmux inspection or session enumeration - only a task id was supplied.
- [ ] [t1657_4] Target unlocked: LIVE_NONE:unlocked, and the durable note is still appended and committed.
- [ ] [t1657_4] Target held by a dead PID: LIVE_NONE:holder_dead, durable note intact.
- [ ] [t1657_4] Target held by a Codex session (implemented_with set to a codex string): LIVE_NONE:agent_unsupported, durable note intact.
- [ ] [t1657_4] Target locked during the Step 4 -> Step 7 window (implemented_with empty): LIVE_NONE:agent_unknown, reported as unavailable rather than as an error.
- [ ] [t1657_4] Live delivery is reported as queued, never as read.
- [ ] [t1657_5] In a FRESH session that has not read the t1657 plan, `ait note` is discoverable from the always-loaded instructions alone.
- [ ] [t1657_5] In that same fresh session, the aitask-note skill appears in the skill listing with a description that conveys WHEN to use it, not just what it does.
- [ ] [t1657_5] Invoking the skill with an explicit target sends a note end-to-end with zero prompts.
- [ ] [t1657_5] Invoking the skill without a target routes through Related Task Discovery to pick the recipient.
- [ ] [t1657_5] A live-delivery failure after a successful durable write is reported as success with live delivery unavailable, not as a partial failure.
