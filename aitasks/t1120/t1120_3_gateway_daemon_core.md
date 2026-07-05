---
priority: high
effort: high
depends: [t1120_2]
issue_type: feature
status: Implementing
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
implemented_with: claudecode/fable5
created_at: 2026-07-05 11:59
updated_at: 2026-07-05 23:55
---

## Context

Third child of t1120. The chatlink gateway daemon: a Textual-free headless
process that owns the `ChatAdapter.subscribe()` loop on the bug-intake channel,
creates threads from authorized bug reports, and persists session state. Applink
is the architectural template (headless daemon, no Textual imports). Parent
plan: `aiplans/p1120_discord_bug_report_channel_integration.md` (§PINNED +
"Crash ownership & startup reconciliation").

**Contracts: snapshot of parent plan §PINNED — provisional until t1120_1
freeze.** Consumes contracts 1-6 (session_id, spool, schemas, custom_id routing,
modal dance, timeout/cancel), 9-11 (policy, config/secrets, ceilings).

## Load-bearing chat-layer semantics

- `subscribe()` is broadcast, at-least-once WHILE CONNECTED; **no replay across
  disconnect; INTERACTION_RECEIVED is non-replayable** → persist interaction
  outcomes on receipt, before any further await.
- Reconnect recovery is re-query: `fetch_history(after=)` diff for missed
  messages; missed interaction windows ⇒ re-prompt (edit message, re-post
  components).
- Drop `Event.actor.is_self` / `is_bot` events (self-trigger-loop protection).
- Thread creation: `create_conversation(ConversationKind.THREAD,
  parent=<MessageRef>)`; persist the returned `ConversationRef` via
  `to_dict()` (the reconnect token).

## Key deliverables

1. `chatlink/daemon.py` — Textual-free daemon (applink `headless.py:75-186`
   skeleton): validate config first (zero side effects), start subscribe loop,
   idle on signals (SIGINT/SIGTERM stop).
2. `chatlink/intake.py` — intake pipeline: MESSAGE_CREATED on intake channel →
   drop self/bot → `policy.decide()` (deny ⇒ ephemeral denial or ignore, per
   config; audit) → per-user rate-limit ceiling → create thread → mint session
   (via relay lib) → hand to spawn seam (stubbed until t1120_5; injectable
   launcher for tests).
3. `chatlink/sessions_store.py` — session state persistence under
   `aitasks/metadata/chatlink_sessions/` (atomic writes; interaction outcomes
   persisted on receipt; fail-closed resolution of half-created sessions).
4. **Pure reconnect-reconciliation unit** (separately tested):
   `fetch_history(after=)` diff + persisted-outcome replay guard — pure
   function over (persisted state, fetched events) → actions.
5. **Startup session-reconciliation pass** (before intake): sessions with no
   live agent ⇒ marked failed; pending questions get `cancelled` answers
   (spool hygiene); best-effort Discord message cleanup (disable components,
   ❌ reaction); half-created state resolved fail-closed (never resume a
   half-session). Container reaping itself is t1120_5's `reap_orphans` —
   invoked through the injectable launcher seam.
6. `chatlink/audit.py` — audit logger (applink `audit.py` pattern: lazy,
   NullHandler fallback, secrets truncated).
7. Launcher `ait chatlink --headless` via new `aitask_chatlink.sh` — read
   `aidocs/framework/shell_conventions.md` and
   `aidocs/framework/aitasks_extension_points.md` first (new helper script +
   dispatcher wiring).

## Reference files for patterns

- `.aitask-scripts/applink/headless.py` (daemon skeleton, no-Textual contract
  asserted by `tests/test_applink_headless.sh`), `server.py` (state machine,
  ceilings), `router.py` (pure dispatch), `audit.py`, `paths.py`.
- `.aitask-scripts/chat/mock.py:679-757` — test seams: `inject_message`,
  `inject_interaction`, `simulate_disconnect`, `set_identity_claims`,
  `set_window_closed`, `inject_reaction`.
- `.aitask-scripts/chat/adapter.py:434-449` — reconnect/replay semantics.

## Verification

All tests against `MockChatAdapter` (no live-platform calls):
- Intake happy path (authorized message → thread + session); unauthorized ⇒
  deny path + audit (negative control); self/bot echo dropped.
- Interaction outcome persisted before subsequent awaits (ordering assertion).
- `simulate_disconnect` negative controls: missed message recovered via
  history diff; missed interaction ⇒ re-prompt, no replay assumed.
- Startup reconciliation: half-created session ⇒ failed (fail-closed); pending
  question ⇒ cancelled answer written; stale relay dir removed after terminal
  state persisted.
- Rate-limit ceiling enforced (t985-style bound test).
- No-Textual import contract test (mirror `test_applink_headless.sh`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-05T20:55:23Z status=pass attempt=1 type=human
