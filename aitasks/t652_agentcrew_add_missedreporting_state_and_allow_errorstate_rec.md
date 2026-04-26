---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-26 13:12
updated_at: 2026-04-26 13:49
boardidx: 30
---

## What happened

During the brainstorm-635 crew run, the initializer_bootstrap agent was launched interactively. The agent was processing a long task (reading large files, thinking) and did not send a heartbeat in time. agentcrew_runner.py set the agent status to Error automatically. The agent's actual work was correct and complete — but:
1. The status was set to Error mid-work, before the agent had a chance to report.
2. From Error, the only allowed transition is Error → Waiting → Ready → Running → Completed — a 4-hop path that should not be needed for a simple correction.

## Proposed changes

### 1. Intermediate "MissedHeartbeat" state (before Error)

Instead of immediately setting status to Error on heartbeat timeout, introduce an intermediate state (e.g. `MissedHeartbeat`) with a grace window:
- On first missed heartbeat deadline: transition Running → MissedHeartbeat (not Error)
- If heartbeat arrives within the grace window: transition MissedHeartbeat → Running (auto-recovery)
- If grace window expires with no heartbeat: then transition MissedHeartbeat → Error

This prevents false-positive Error assignments for agents doing legitimate long-running work (large file reads, LLM thinking, etc.).

The grace window and heartbeat interval should be configurable per crew or globally.

### 2. Allow recovery from incorrectly-assigned Error

Add a transition Error → Running (or Error → Completed directly) for cases where the agent can prove it finished work. Options:
- Allow Error → Completed directly (simplest — agent marks itself done regardless of how it got to Error)
- Add a `--force` flag to `ait crew status set` that bypasses transition validation for explicit human or agent override
- Or: the 4-hop path (Error → Waiting → Ready → Running → Completed) is the current workaround and works, but it is noisy and unintuitive

## Questions to resolve
- What should the MissedHeartbeat grace window be? (Suggestion: 2× the heartbeat interval)
- Should MissedHeartbeat appear in crew-level status roll-up as Running or as a warning state?
- Is Error → Completed a safe direct transition, or should it always go through Running to ensure the runner has a chance to observe the completion?
- Should the runner log a warning when it auto-transitions to MissedHeartbeat so operators know without checking every agent file?
