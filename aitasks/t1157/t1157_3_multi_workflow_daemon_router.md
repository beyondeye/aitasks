---
priority: high
effort: high
depends: [t1157_2]
issue_type: feature
status: Ready
labels: [workflows, python, remote, sanboxing, crash_recovery]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 12:15
updated_at: 2026-07-17 12:15
---

## Context

Third child of t1157. With host configuration and durable session/attempt records available, generalize the singleton bug-specific daemon into one event router serving multiple workflow instances, projects, channels, and guilds through one adapter connection. This child incorporates the routing and cross-workspace process-management requirements merged from t1127.

## Key files to modify

- `.aitask-scripts/chatlink/daemon.py`: construct the host registry/router once, subscribe once, reconcile all projects/workflows.
- `.aitask-scripts/chatlink/intake.py`: split generic routing/session launch/interaction ownership from bug-specific behavior.
- `.aitask-scripts/chatlink/flow.py`: route question, checkpoint, proposal, death, and approval events by workflow session/attempt.
- `.aitask-scripts/chatlink/reconcile.py`: multi-project/multi-attempt startup and reconnect plans.
- `.aitask-scripts/lib/sandbox_launch.py`: route workspace snapshots, labels, reaping, and handles by logical project plus attempt.
- `.aitask-scripts/chatlink/task_create.py`: project-routed creation entry point without weakening validation.
- `tests/test_chatlink_daemon.sh`, `tests/test_chatlink_flow.sh`, `tests/test_sandbox_launch.sh`.

## Reference files

- Existing sequential `_merged_events` single-consumer invariant and level-triggered flow pump.
- Generic `ChatAdapter.subscribe`, `ConversationRef`, command/component normalization.
- Folded t1127 content embedded in the parent task.

## Implementation plan

1. Introduce a workflow-handler registry/interface for trigger matching, session opening, agent launch specification, question/proposal rendering, and completion policy. Keep platform APIs below this layer.
2. Build one router from the aggregated host configuration. Message-driven workflow triggers must be unique; unknown channels/interactions fail quiet with audit context.
3. Preserve one sequential mutation consumer while merging adapter events, flow events, attempt-death signals, and budget/control events. Background scanners remain read/enqueue-only.
4. Resolve each workflow's logical project through the registry, create a committed-HEAD snapshot in that project, launch with project/workflow/attempt labels, and route proposal approval/task creation back to that project.
5. Scope concurrency/rate ceilings by configured policy while retaining a safe host-wide ceiling. Reap containers by project/attempt without touching another host/repo.
6. Reconcile all watched conversations and nonterminal attempts after restart. Persist cursors per conversation/workflow and prevent one project or corrupt record from stopping other workflows.
7. Maintain legacy single-workflow daemon behavior through the compatibility configuration from t1157_1.

## Verification

- One mock adapter, two guilds, two projects, multiple workflow channels: messages and interactions route to the correct project with no cross-talk.
- Duplicate/stale events and payload-vs-death races reach one terminal/paused state exactly once.
- Queue overflow regenerates events; store mutation spies prove the single-writer invariant.
- Foreign-project containers are never counted, killed, or reaped.
- Existing single-repo chatlink daemon/flow/sandbox suites remain green.
