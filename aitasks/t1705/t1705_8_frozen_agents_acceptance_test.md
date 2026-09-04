---
priority: high
effort: medium
depends: [t1705_7]
issue_type: test
status: Ready
labels: [tmux, tmux_destructive, codeagent, session_persistence, test_infrastructure, testing]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:08
updated_at: 2026-09-04 16:08
---

## Step 0 — tmux preflight (run BEFORE anything else; blocking)

This task destructively manipulates tmux (`respawn-pane -k`, real `pane-died`
cleanup hooks, `kill-window`/`kill-server` on an isolated server). Its live
tests call `tests/lib/tmux_isolation.sh::require_clean_ait_server`, which
refuses to run from inside tmux or while the dedicated `-L ait` server has any
pane. Check this **first**, before planning or editing a file:

```bash
[ -z "${TMUX:-}" ] && echo "PREFLIGHT_OK: not inside tmux" || { echo "PREFLIGHT_BLOCKED: this session runs inside tmux ($TMUX)"; }
tmux -L ait list-panes -a -F '#{pane_id} #{window_name}' 2>/dev/null && echo "NOTE: the -L ait server has panes — stop 'ait ide' / close them before running the live suites" || echo "PREFLIGHT_OK: -L ait server idle"
```

- `PREFLIGHT_BLOCKED` → **do not implement.** Execute the workflow's **Task
  Abort Procedure** (`task-abort.md`) so the task reverts to `Ready` with its
  plan kept, and tell the user to re-pick from a terminal that is NOT inside
  tmux. Do not set `AIT_LIVE_TMUX_TEST_FORCE=1` — it is for a dedicated CI
  box only.
- `-L ait` server has panes → implementation may proceed, but the live suites
  will refuse until that server is stopped; say so in the Final
  Implementation Notes if verification had to wait.

## Context

Eighth child of t1705 (frozen code agents). The feature succeeds only if
hooks, live-record binding, capture, pane stamping, cleanup abstention,
viewer launch, restore and cleanup all agree — and every earlier child
proves only its own seam. This child is the **end-to-end acceptance test
through the shipped wrappers only**, on an isolated tmux server, with a fake
agent binary standing in for `claude`/`codex` so it runs unattended. It is
the parent's risk mitigation for cross-child drift (parent plan `## Risk`,
"per-child tests can pass with incompatible joins"). Real-agent behaviour is
the manual-verification sibling's job. **Tmux-stress**: run from outside the
`-L ait` server.

## What "through the shipped wrappers" means

No test may call a Python mutator directly. The path is: `install.sh --dir
<scratch>` + `ait setup` (hooks installed by t1705_3) → an agent launched
with `aitask_codeagent.sh --agent-string claudecode/opus5 invoke raw` (the
fake `claude` on `PATH` receives the real argv) → the fake binary execs the
**real** `aitask_session_hook.sh` with a synthetic SessionStart payload and
the env it inherited (`AITASK_AGENT_STRING`, `AITASK_RESTORE_*`) → the real
store → `aitask_frozen.sh freeze` → the **real** `ait frozenagent --record`
stand-in in the pane → `aitask_frozen.sh restore` as the real detached
`run-shell -b` coordinator → the fake binary honouring `--resume <sid>`
(prints the id it got, calls the hook with that session id, sleeps) →
`drop`. `AITASKS_FROZEN_STANDIN_CMD` is **not** set here — the real viewer
must come up and self-stamp.

## Cases (`tests/test_frozen_agents_acceptance.sh`)

1. **Launch + hook binding**: after launch, `aitask_agent_sessions.sh list`
   shows one `live` record for `(root, agent-pick-1, slot 0)` with
   `pane_pid` = `#{pane_pid}`, `codeagent_session_id` = the fake's id,
   `agent_string` from the env; the pane carries `@aitask_record=<id>` and
   `@aitask_agent_session`.
2. **Freeze**: `aitask_frozen.sh freeze <pane>` → record `frozen`,
   `standin_pid` set, capture files present (0600, line count = fake
   output), the pane runs the real viewer, `@aitask_frozen` and
   `@aitask_standin_ready` set, companion pane alive, `capture-pane` of the
   stand-in pane shows the header line with the window name.
3. **Failed restore** (`FAKE_AGENT_EXIT=1`): `aitask_frozen.sh restore <id>`
   → `RESTORE_FAILED:<id>|agent_exited`, record `frozen`, capture intact,
   viewer back and ready, `restore_attempts=1`, elapsed < `restore_ack_grace`.
4. **Mismatched restore through the detached path** (`FAKE_AGENT_SESSION=other`):
   the coordinator is the real `run-shell -b` process; the hook reports the
   other id → `last_error="<nonce>:session_mismatch"` → `RESTORE_FAILED:…|session_mismatch`,
   capture intact, stand-in back, and **the liveness fallback did not fire**
   (assert elapsed < grace and `ack` is empty).
5. **Successful restore**: fake binary receives `--resume <sid>` and the
   `AITASK_RESTORE_*` env, calls the hook → `RESTORED:<id>|hook`, record
   `live`, `ack=hook`, capture files deleted, `@aitask_frozen` cleared,
   `@aitask_record` still the same id, `pane_pid` updated.
6. **Gone-pane restore**: freeze again, `kill-window`, `restore` → a new
   window with the recorded name (or `-2` suffix if it collides), the **old**
   record acknowledged (`id` unchanged, no second record, `window_slot`
   unchanged), captures deleted.
7. **Dead coordinator**: freeze; start `restore` with
   `AITASKS_FROZEN_PAUSE_AT=aborting` after a forced `FAKE_AGENT_EXIT=1`;
   `SIGKILL` the coordinator; a second `restore` is `TRANSITION_REFUSED`;
   advance past `stale_op_grace` (config it to 2 s for the test);
   `aitask_frozen.sh reconcile` → `frozen`, viewer back; the killed
   coordinator's nonce is dead.
8. **Coordinator killed after clearing ready, before respawn**
   (`AITASKS_FROZEN_PAUSE_AT=respawn` + `SIGKILL`): reconcile recognises the
   viewer by `standin_pid`, aborts, respawns, never confirms.
9. **Ambiguous relocation after a "server restart"**: two fake agents in
   one window (slot 0 and 1), kill the server, recreate the window with one
   fake agent → `UPSERTED:…|created_slot2|ambiguous_relocation`; after
   `reconcile`, the two stale records are `dead_pane`-purged.
10. **Drop**: `aitask_agent_sessions.sh drop <id>` (via minimonitor's path is
    t1705_7's test; here the CLI) → record gone, capture dir gone, pane
    options cleared.
11. **Repeated `ait setup`** in the scratch project leaves exactly one
    SessionStart entry (a cheap re-check of t1705_3's guarantee in the
    composed environment).

Each case is a `( … )` subshell with `assert_counters_init`/`_load`; the
script tears down the isolated server in a trap. Budget: the whole run must
finish in < 3 min with `restore_ack_grace=5` and `stale_op_grace=2` set via
the scratch project's `project_config.yaml` `frozen:` block.

## Key files

- **New** `tests/test_frozen_agents_acceptance.sh`; **edit**
  `tests/lib/fake_agent.sh` (from t1705_1/5) if a knob is missing.
- **Edit** `aidocs/framework/testing_conventions.md` — a short "composed
  acceptance through shipped wrappers" paragraph pointing at this file as
  the pattern.

## Reference patterns

- `tests/test_restore_flows_live.sh` (t1705_5) and `tests/test_freeze_engine_live.sh`
  (t1705_4) — reuse their helpers by sourcing a shared
  `tests/lib/frozen_fixtures.sh` (extract it here if the two duplicated it).
- `tests/test_session_hook_install.sh` (t1705_3) — the scratch-install recipe.
- `tests/lib/tmux_isolation.sh`, `tests/lib/asserts.sh`.
- Memory/convention: "verification needs independent ground truth" — the
  ground truth here is the pane and file state observed through tmux and
  the filesystem, never the store's own claims alone.

## Verification

```bash
bash tests/test_frozen_agents_acceptance.sh        # outside the -L ait server; prints per-case PASS/FAIL and a timing line
bash tests/test_no_raw_tmux.sh
```
