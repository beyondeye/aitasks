---
Task: t1120_3_gateway_daemon_core.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_1_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_3_gateway_daemon_core
Branch: aitask/t1120_3_gateway_daemon_core
Base branch: main
---

Contracts: snapshot of parent plan §PINNED — provisional until t1120_1 freeze.

# Plan: t1120_3 — Chatlink gateway daemon core

Deliverables (7 items), load-bearing chat-layer semantics, and verification
list are in the task file (`aitasks/t1120/t1120_3_gateway_daemon_core.md`).
Read archived plans of t1120_1 (relay lib API, freeze status) and t1120_2
(config/policy/paths APIs) first.

## Module split (pinned — mirrors applink)

- `chatlink/daemon.py` — entry: load config (refuse-to-start if missing —
  fail-closed), construct adapter (injected; production `DiscordAdapter.
  connect(token)`, tests `MockChatAdapter`), run startup reconciliation, then
  intake loop; signal handling per `applink/headless.py:75-186`.
- `chatlink/intake.py` — pure-ish pipeline over injected collaborators
  (adapter, policy, sessions_store, launcher, clock): event filtering,
  authorization, rate ceiling, thread creation, session mint/dispatch.
- `chatlink/sessions_store.py` — session records (JSON files per session under
  `chatlink_sessions/sessions/<session_id>.json`, atomic writes): initiator id,
  thread ConversationRef dict, bug-report MessageRef dict, state
  (`spawning|asking|working|awaiting_payload|done|failed`), interaction
  outcomes (persisted on receipt), timestamps.
- `chatlink/reconcile.py` — **pure** reconnect-reconciliation:
  `plan_reconnect_actions(persisted_sessions, fetched_events) -> [Action]`
  and `plan_startup_actions(persisted_sessions, live_session_ids, relay_scan)
  -> [Action]` — no I/O; daemon executes returned actions.
- `chatlink/audit.py` — applink `audit.py` pattern (lazy logger →
  `chatlink_sessions/chatlink_audit.log`, NullHandler fallback, ids
  truncated).
- `aitask_chatlink.sh` + `ait` dispatcher entry (`ait chatlink --headless`);
  dependency preflight (chat tier installed) mirroring
  `aitask_monitor.sh:14-42`'s headless-for-applink interception. Read
  `aidocs/framework/shell_conventions.md` +
  `aidocs/framework/aitasks_extension_points.md` first.

## Key async invariants (binding — concurrency safety contract)

- Loop-only mutation: session records mutated solely from the daemon's single
  event loop; relay spool I/O via `asyncio.to_thread`.
- Interaction outcomes persisted (atomic write) **before** any subsequent
  `await` on the same session (INTERACTION_RECEIVED non-replayable).
- Fail-closed everywhere: unknown custom_id ⇒ audit + ignore; half-created
  session at startup ⇒ failed, never resumed.
- Bounded: intake honors `max_concurrent_sandboxes` + per-user rate ceiling
  (drop with audit + optional ephemeral notice when exceeded).
- Deterministic test seam: injected clock/launcher; `MockChatAdapter` logical
  clock.

## Implementation order

1. `sessions_store.py` (+ tests) — pure persistence.
2. `reconcile.py` (+ tests) — pure planners, table-driven cases.
3. `intake.py` (+ tests vs MockChatAdapter, fake launcher).
4. `audit.py`, `daemon.py` wiring (+ no-Textual import guard test).
5. `aitask_chatlink.sh` + dispatcher entry (+ launcher argv test).

The launcher seam is **stubbed** here: `chatlink/spawn_seam.py` defining the
`launch(spec)/handle/reap_orphans` protocol signature (contract 8) with a
`FakeLauncher` for tests; t1120_5 provides the real backend. The Q&A pumping
between spool and Discord components is minimal here (enough to test
persistence + reconciliation); full orchestration is t1120_6's `flow.py`.

## Testing

Bash test script(s) per the task file's Verification list, all against
`MockChatAdapter` seams (`inject_message`, `inject_interaction`,
`simulate_disconnect`, `set_identity_claims`); negative controls: unauthorized
deny + audit, self/bot echo dropped, disconnect mid-question (re-prompt, no
replay), half-created session fail-closed, ordering assertion for
persist-before-await (spy store recording call order), rate ceiling.

## Step 9 reference

Post-implementation follows task-workflow Step 9.
