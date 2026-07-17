---
priority: high
effort: high
depends: [t1157_1]
issue_type: feature
status: Ready
labels: [workflows, python, crash_recovery, remote]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 12:15
updated_at: 2026-07-17 12:15
---

## Context

Second child of t1157, after the workflow configuration foundation. Current `SessionRecord` conflates a logical Discord conversation with one sandbox/relay run and carries bug-specific fields. Terminal cleanup deletes relay/workspace state, so interrupted work cannot resume. The parent requires durable workflow sessions, disposable attempts, incremental checkpoints, unapproved proposals, seven-day retention, and Resume/Restart against latest committed HEAD.

## Key files to modify

- `.aitask-scripts/chatlink/sessions_store.py`: versioned durable workflow session and attempt persistence/migration.
- `.aitask-scripts/chatlink/relay.py`, `relay_payload.py`, wrappers: checkpoint and unapproved proposal schemas/transports separate from approved creation.
- `.aitask-scripts/chatlink/reconcile.py`: startup/reconnect planning for paused, awaiting-approval, and interrupted attempts.
- `.aitask-scripts/chatlink/paths.py`: global session/attempt/checkpoint state paths from t1157_1.
- `aidocs/chat/qa_relay_protocol.md`: normative wire/state contracts.
- `tests/test_chatlink_relay.sh`, `tests/test_chatlink_daemon.sh`: schema, migration, expiry, and restart tests.

## Reference files

- Existing `SessionRecord`, `SessionsStore`, `SessionDir`, `Question`, `Answer`, and `TaskPayload` contracts.
- `aiplans/archived/p1120/p1120_1_relay_protocol_library.md` and `p1120_4_chat_native_explore.md` for pinned atomic-spool semantics.
- Parent and t1157_1 task/plan context.

## Implementation plan

1. Separate stable `WorkflowSession` identity (one Discord thread/source) from per-launch `AttemptRecord` identity (relay directory/container/workspace/base commit/deadlines).
2. Persist workflow/project/initiator, thread and source refs, intent, transcript/Q&A outcomes, checkpoint, draft proposal, attempt history, state, last activity, and expiry. Use versioned strict schemas and atomic writes.
3. Define states for running/asking/synthesizing/awaiting_approval/paused/revising/creating/done/failed/aborted/expired and validate legal transitions centrally.
4. Add a bounded checkpoint schema written after each meaningful exploration round and answer. Add a `TaskProposal` schema that is validated but cannot trigger task creation without a separate approval event.
5. Preserve the existing question/answer custom-id wire contract by keeping attempt relay IDs; carry stable workflow-session identity alongside them in gateway-owned records.
6. Migrate legacy records as one bug-intake workflow session with one attempt. Never reinterpret an already-created task or terminal outcome.
7. Add seven-day retention from last activity, stale-control/attempt supersession rules, and latest-HEAD revalidation metadata for resume/restart.
8. Ensure cleanup removes disposable workspace/relay data while retaining the minimal durable session/checkpoint/proposal record until expiry.

## Verification

- Strict round trips and rejection matrices for every new schema/version.
- Legacy record fixtures migrate deterministically and remain terminal/nonterminal as appropriate.
- Crash at every persist/platform/cleanup boundary produces one recoverable or fail-closed state, never duplicate terminal transitions.
- Resume preserves checkpoint/transcript; Restart retains source/thread only; expiry disables both.
- No proposal file alone can call task creation.
