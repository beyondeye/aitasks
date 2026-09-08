---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [tmux, tmux_destructive, codeagent, session_persistence, python, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-08 11:41
updated_at: 2026-09-08 11:49
---

## Origin

Risk-mitigation ("before") for t1705_5, created at Step 7 from the approved plan's risk evaluation.

## Risk addressed

**addresses:** code-health — new coordinator duplicates private helpers from agent_freeze.py

Verbatim from the `## Risk` → *Code-health risk: high* section of
`aiplans/p1705/p1705_5_restore_and_repick_flows.md`:

> - `agent_restore.py` is a new ~400-line coordinator that duplicates several
>   private helpers from `agent_freeze.py` (`_store`, `_pane_facts`, `_respawn`,
>   `_set_option`, the test seams). Copying them forks two engines that must stay
>   in agreement about the store wire protocol; importing them couples the
>   coordinator to a module deliberately written to work without it · severity: medium (residual — deferred to a blocking "before" task, so this plan does not land the duplication) · → mitigation: extract_freeze_store_helpers

## Goal

Extract the store/tmux plumbing that `lib/agent_freeze.py` keeps private into a
module **both** engines import, so the incoming restore coordinator
(`lib/agent_restore.py`, t1705_5) *shares* the store wire protocol rather than
forking it.

t1705_5 is **blocked on this task** (`depends:`) and must not be implemented
until it lands — that is the whole point of the "before" timing: the duplication
is cheapest to avoid before the second engine exists, not after.

### Why neither of the two obvious options is acceptable on its own

- **Copy the helpers into `agent_restore.py`** → two engines that must stay in
  exact agreement about the store's wire protocol (verb names, argument shapes,
  the `NONCE_MISMATCH` / `TRANSITION_REFUSED` / `LEASE_HELD` exit codes, the
  test seams). They will drift, and the drift is silent.
- **Have `agent_restore.py` import `agent_freeze`'s privates** → couples the
  coordinator to a module that was *deliberately* written to work without it.
  `agent_freeze.py`'s own docstring records the split: *"The restore
  COORDINATOR is t1705_5; this is only the repair side."* Reconcile must keep
  settling abandoned restores with no coordinator present.

The third option — a shared module both import — is what this task builds.

### Scope

In `.aitask-scripts/lib/agent_freeze.py`, the members named by the risk bullet:

- `_store(...)` — the `aitask_agent_sessions.sh` wrapper-invocation seam
- `_pane_facts(...)` — the `display-message -p` `#{pane_id}` / `#{pane_pid}` read
- `_respawn(...)` — the `respawn-pane` call through the tmux gateway
- `_set_option(...)` — the pane-option set/unset (`-p` / `-pu`)
- the test seams — `_test_mode()`, `_fail_at()`, `_pause_at()`

Verify the exact current member list and signatures against the tree before
designing; the bullet was written at plan time and the freeze engine has since
shipped (t1705_4).

### Constraints

- **Behaviour-preserving.** `tests/test_freeze_engine_live.sh` and the whole
  Python suite must stay green with no test edits that weaken an assertion.
  The freeze engine is already shipped and green; this task must not be
  visible in its behaviour.
- **The new module must not import `agent_freeze`** — the dependency arrow runs
  the other way, or reconcile's independence from the coordinator is lost.
- Route every `tmux` call through the gateway (`lib/tmux_exec.py`);
  `tests/test_no_raw_tmux.sh` enforces it.
- Failure-injection env seams keep their current names and their
  `AITASKS_TEST_MODE=1` gating — `tests/test_freeze_engine_live.sh` drives them
  by name, and t1705_5 adds `AITASKS_RESTORE_FAIL_AT` to the same shape.

## Verification

```bash
bash tests/test_freeze_engine_live.sh     # outside the -L ait server
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
```

## Tmux preflight

Inherits t1705_5's constraint: `test_freeze_engine_live.sh` calls
`require_clean_ait_server`, which refuses to run from inside tmux or while the
dedicated `-L ait` server has any pane. Verify from a shell **outside** that
server.
