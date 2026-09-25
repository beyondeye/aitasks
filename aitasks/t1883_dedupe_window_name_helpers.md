---
priority: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1847
followup_kind: risk_mitigation
created_at: 2026-09-25 12:24
updated_at: 2026-09-25 12:27
---

## Origin

Risk-mitigation ("after") follow-up for t1875, created at Step 8d after implementation landed.

## Risk addressed

code-health — duplicated window-name helpers: "The helpers duplicate reopen's name-lookup, kill and rename logic. This is bounded and cross-referenced, a deliberate trade against a circular import."

## Goal

`lib/agent_restore.py` (t1875) carries local twins of three tmux primitives from `lib/agent_reopen.py`. They could not be imported, because `agent_reopen` imports `agent_restore`:

- `_find_attempt_pane` ↔ reopen's `_find_by_window_name` — a lookup by window name through `list-panes -s -t =<session>:`, returning `found` / `none` / `unknown`;
- `_kill_window_if` / `_kill_if_named` ↔ reopen's `_kill_if_named` — a check-and-kill in one `if-shell -F` dispatch plus an after-read, returning `gone` / `present` / `unknown`;
- `_rename_if_stamped` ↔ reopen's `_rename` — a stamp-guarded rename verified by a re-read.

Move the tmux logic into `lib/agent_frozen_ops.py`, which both coordinators already import, and have both call it. Each coordinator keeps its own seam checks (`AITASKS_RESTORE_FAIL_AT` / `AITASKS_REOPEN_FAIL_AT`) as thin wrappers.

Constraints:
- Keep the seam rule: call the shared helpers through the module, never import-aliased.
- Behaviour must not change. `tests/test_agent_reopen.py`, `tests/test_agent_restore.py` and `bash tests/test_frozen_reopen_live.sh` must pass unchanged.
- The display-message facts the helpers read differ slightly between the two coordinators (reopen's `_facts` versus restore's `_attempt_facts`). Unify them on one shared read, and do not change `PANE_FACT_FORMAT` / `PROBE_PANE_FORMAT` (existing test fixtures script those by arity).
