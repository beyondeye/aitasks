---
priority: medium
effort: medium
depends: []
issue_type: test
status: Folded
labels: [chat_surface, python, testing]
folded_into: 1157
anchor: 1120
created_at: 2026-07-10 09:06
updated_at: 2026-07-17 11:50
boardidx: 110
---

## Origin

Risk-mitigation ("after") follow-up for t1120_6, created at Step 8d after implementation landed.

## Risk addressed

Daemon-loop sequential-dispatch races + completion-vs-death misclassification:

- Daemon-loop integration (third merged-event source + death-path amendment) touches the load-bearing sequential-dispatch core; a pump mutating outside the loop or double-handling death would corrupt session state (code-health, medium).
- Completion-vs-death race: the sandbox watchdog fires on every container exit, so a missed payload check misclassifies successful sessions as failed (goal-achievement, medium).

## Goal

Soak/stress test for the chatlink flow: N concurrent mock sessions (MockChatAdapter + FakeLauncher, no live platform) with randomized event interleavings — intake, question spool writes, select/modal answers, payload writes, death signals — and repeated daemon kill-restart cycles over the same store. Assert:

- no cross-talk between sessions (answers/payloads route strictly by custom_id session_id);
- no double terminal transitions (each session reaches exactly one of done/failed exactly once, across restarts);
- correct completion-vs-death routing under racing orders (payload_ready vs death signal in both orders, including arrival during restart reconciliation);
- the pump's bounded queue and level-triggered scan never lose a session permanently (dropped events are regenerated);
- the sequential-dispatch invariant holds (no interleaved handler mutations — e.g. via a store-save spy asserting single-writer ordering).

Seed harness: `tests/test_chatlink_flow.sh` (t1120_6) — the Env class, spy create script, and wait_until helpers are directly reusable; add a seeded RNG so failures are reproducible from the printed seed.
