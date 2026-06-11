---
priority: medium
effort: medium
depends: [672]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [672]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 13:51
updated_at: 2026-06-11 09:18
completed_at: 2026-06-11 09:18
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t672

## Verification Checklist

- [x] Launch a brainstorm session whose initializer agent fails (status Error/Aborted); confirm the polling indicator (#initializer_polling_indicator) stops and is no longer flashing. — PASS 2026-06-11 09:18 auto: Error/Aborted branch sets _initializer_done=True (poll guard @8509 stops further flash) and calls #initializer_polling_indicator.stop() @8553-8558 (brainstorm_app.py)
- [x] Confirm the error toast no longer contains "Watching for output" and still shows the "press ctrl+r or run `ait brainstorm apply-initializer <N>`" retry hint. — PASS 2026-06-11 09:18 auto: notify @8559-8564 = 'Press ctrl+r or run `ait brainstorm apply-initializer <N>` to retry.'; grep 'Watching for output' -> NO MATCH
- [x] Confirm ctrl+r still forces an apply retry (action_retry_initializer_apply) after the agent has failed. — PASS 2026-06-11 09:18 auto: Binding('ctrl+r','retry_initializer_apply') @3513 -> action_retry_initializer_apply @4810 -> _try_apply_initializer_if_needed(force=True); unchanged, not gated by _initializer_done
- [x] Confirm that when the agent wrote a complete delimited output (all four NODE_YAML/PROPOSAL delimiters) before failing, the one-shot apply on the Error/Aborted branch still imports the proposal into n000_init. — PASS 2026-06-11 09:18 auto: Error branch @8566 calls _try_apply_initializer_if_needed() -> n000_needs_apply (four-delimiter gate @408) -> apply_initializer_output @469 rewrites br_nodes/n000_init.yaml + br_proposals/n000_init.md
- [x] Confirm no background timer keeps re-polling after Error/Aborted (no 30s slow-watcher) — PASS 2026-06-11 09:18 auto: grep 'set_interval(30, self._poll_initializer)' -> NO MATCH; Error branch stops timer + _initializer_done=True, no reinstall. Only 30s timer is _status_refresh_timer (status-tab refresh, not initializer re-poll)
