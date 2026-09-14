---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux, frozen, session_persistence, test_infrastructure]
anchor: 1705
followup_kind: verification_failure
created_at: 2026-09-14 17:18
updated_at: 2026-09-14 17:18
---

## Origin

Discovered while running t1806 (the live-suite verification of t1802, commit 85ed142f6). Not a t1802 defect: the failure happens at restore preflight, before any t1802 code runs.

## Symptom

`bash tests/test_restore_flows_live.sh` failed Case 1 on its first run from a cold `-L ait` server (8 assertions, all downstream of `RESTORE_FAILED:<rid>|no_session`) and passed 84/84 on an immediate re-run. Cases 2 through 13 never failed.

## Mechanism (reproduced deterministically)

`make_frozen` in `tests/test_restore_flows_live.sh` launches the fake agent, sleeps 0.3s, upserts the record with `--session-id sess-orig`, then freezes. The fixture's own upsert never stamps `@aitask_record` on the pane; only the SessionStart hook does (step 8 of `aitask_session_hook.sh`), and it also sets `@aitask_agent_session` (step 9). On a cold first launch the hook's python3 payload build takes longer than 0.3s, so at freeze time the pane carries neither option.

`_resolve_record` in `.aitask-scripts/lib/agent_freeze.py` then takes path 2 (no stamp) and runs the fallback upsert with `--session-id ""` (the pane option is unset). The store's `upsert` selects the fixture's record by pane identity and `_apply_upsert_fields` treats `session_id=""` as a value, not "not supplied", so `codeagent_session_id` goes from `sess-orig` to empty. The freeze then stamps the pane. The late hook, if it lands at all, is refused because the record is no longer live. `restore` sees an empty session id and returns `no_session`.

Reproduction with the suite's own fixtures, `FAKE_AGENT_HOOK_DELAY=3` exported through the tmux global environment: before freeze `@aitask_record=''`; after freeze `codeagent_session_id=''` while `agent_string='claudecode/opus5'` survives (the t1802 guard); restore returns `RESTORE_FAILED:<rid>|no_session`. Waiting for the stamp before freezing keeps `sess-orig` and the restore is hook-verified.

## Two layers to fix

1. **Product, same class as t1802.** The freeze engine's fallback upsert can blank a good `codeagent_session_id` whenever a record exists for the pane but the pane is unstamped (a hook whose stamp failed, or any caller that upserts without stamping). t1802 made a blank `agent_string` a no-op in `_apply_upsert_fields`; the hook already makes a blank session id a no-op at its own layer (contract 4), but the store does not, and the freeze fallback bypasses the hook. Either make a blank `session_id` "not supplied" in the store (check the `restore_of` resume-mismatch comparison, which deliberately compares `session_id or ""`), or have `_resolve_record` omit `--session-id` when the pane option is unset. Add a unit test that freezes an unstamped pane whose record already carries a session id and asserts the id survives.

2. **Fixture.** `make_frozen` (and the acceptance suite's equivalent, if it has one) should wait for the hook's `@aitask_record` stamp on the pane before freezing, or stamp the pane itself after its upsert, instead of relying on `sleep 0.3`. The acceptance suite passed on the same cold server, so check whether it already waits.

## Files

- `.aitask-scripts/lib/agent_freeze.py` (`_resolve_record`, fallback upsert)
- `.aitask-scripts/lib/agent_sessions.py` (`_apply_upsert_fields`, `upsert`)
- `tests/test_restore_flows_live.sh` (`make_frozen`)
- `tests/lib/frozen_fixtures.sh`
