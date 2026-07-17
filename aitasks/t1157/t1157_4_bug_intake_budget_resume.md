---
priority: high
effort: high
depends: [t1157_3]
issue_type: enhancement
status: Ready
labels: [workflows, remote, codeagent, crash_recovery, claudecode]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 12:17
updated_at: 2026-07-17 12:17
---

## Context

Fourth child of t1157. Migrate the existing dedicated bug-intake workflow onto the generic host/session/router foundation without diluting its focused UX. Remove the prompt-only three-question ceiling and the unsafe final-confirmation timeout default, coordinate questions with visible active/synthesis budgets, checkpoint incrementally, and support explicit approval plus Resume/Restart from the existing thread.

## Key files to modify

- `.claude/skills/aitask-explorechat/SKILL.md`: budget/checkpoint/proposal contract and no fixed clarification count.
- `.aitask-scripts/chatlink/relay_ask.py` and wrapper: deadline-aware timeout clamping and budget metadata.
- Bug workflow handler extracted from `.aitask-scripts/chatlink/intake.py`/`flow.py`: thread controls, approval, resume/restart/revision.
- `.aitask-scripts/chatlink/render.py`: visible remaining-time/default text and persistent proposal actions.
- `.aitask-scripts/chatlink/task_create.py`: explicit approval token/event required before creation.
- Tests/docs covering current bug behavior and compatibility.

## Reference files

- Existing `aitask-explorechat` flow and t1120 archived plans.
- t1157_1 through t1157_3 configuration/session/router contracts.
- Native `aitask-explore` investigate-problem strategy, but not its implementation handoff.

## Implementation plan

1. Keep bug messages as immediate bug-intake sessions and autonomous focused code exploration. Ask only facts the repository cannot resolve; do not impose a small question count.
2. Apply the default 30-minute attempt budget: 20 active minutes and a 10-minute synthesis reserve. Export absolute deadlines, checkpoint after each meaningful round/answer, and clamp the nine-minute question timeout to remaining active time.
3. Every rendered question states remaining active time, response deadline, named conservative default, and soft-budget outcome. Waiting time counts against the attempt.
4. On soft expiry, stop new questions and synthesize from the latest checkpoint. On hard expiry without a proposal, pause with a clear thread notice and no task.
5. Replace relay-blocking final confirmation with an unapproved persisted proposal. Exit/clean the sandbox, render Approve/Request changes/Resume/Restart/Abort controls, and retain for seven days.
6. Require an explicit, fresh, initiator-owned approval interaction before gateway task creation. Timeout/disconnect/stale controls never approve.
7. Resume starts a new attempt from checkpoint/transcript on latest HEAD and revalidates findings; Restart discards findings; Request Changes starts a 15-minute revision attempt.
8. Keep gateway validation, repo label/type allowlists, sandbox isolation, reactions, and audit provenance.

## Verification

- A scripted bug flow asks and answers more than three useful questions within budget and still proposes successfully.
- Boundary tests cover active timeout clamping, soft synthesis, hard pause, delayed approval outside sandbox lifetime, stale/foreign approval denial, resume/restart/revision, and seven-day expiry.
- No timeout or proposal artifact alone creates a task; one explicit approval creates exactly one.
- Existing bug-intake fixtures and live-smoke command remain compatible after schema migration.
