---
priority: high
risk_code_health: high
risk_goal_achievement: medium
effort: high
depends: [t1705_4, 1738]
issue_type: feature
status: Done
labels: [tmux, tmux_destructive, codeagent, claudecode, codexcli, session_persistence, python, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1738]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
implemented_with: claudecode/opus5
created_at: 2026-09-04 16:04
updated_at: 2026-09-08 16:37
completed_at: 2026-09-08 16:37
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

Fifth child of t1705 (frozen code agents). Implements **restore** (relaunch
the frozen agent via `claude --resume <sid>` / `codex resume <sid>` in the
stand-in's own pane), **re-pick** (`/aitask-pick <task_id>` in that pane),
**Restore-All**, and the acknowledged two-phase protocol of the parent
plan's §D (**PINNED**; reproduced with t1705_1's findings in
`aiplans/p1705/p1705_5_restore_and_repick_flows.md`). It lands **before** the
viewer (t1705_6): the viewer only shells out to `aitask_frozen.sh restore
<id>` through `run-shell -b`, so nothing here imports the viewer, and the
rollback's stand-in respawn is exercised with `AITASKS_FROZEN_STANDIN_CMD`.

The whole point of the protocol: a restore **never runs inside the pane it
replaces**, tmux accepting the respawn proves nothing, and the only copy of
the capture is deleted **only** on a hook-verified acknowledgement that the
resumed session is the expected one.

**Tmux-stress**: implement and verify from a shell **outside** the `-L ait`
server.

## Deliverables

1. **`aitask_codeagent.sh --resume-session <sid>`** — new global flag
   (template: `OPT_HEADLESS`, `:36`, `:688-691`, consumed at `:483/:496`,
   `show_help` `:633-641`). Consumed in `build_invoke_command` per agent:
   `claudecode` → `claude --model <cli_id> --resume <sid>` (the flag goes
   **after** the model flag and **before** any prompt positional — see the
   `explore-relay` ordering hazard at `:510-513`); `codex` → `codex resume
   <sid>` (model flag position per the codex CLI, verified in t1705_1);
   `opencode` → `die "RESUME_UNSUPPORTED:opencode"` exit 2. Only legal with
   `invoke raw` (no slash command is appended). Resolution stays in
   `lib/agent_string.sh`; `--dry-run` prints the `%q`-quoted argv exactly as
   `resolve_dry_run_command` expects.
2. **`.aitask-scripts/lib/agent_restore.py`** — `restore(record_id, *,
   mode="resume"|"repick") -> RestoreResult`, `restore_all()`. The §D
   sequence verbatim: build argv (resume via `resolve_dry_run_command(root,
   "raw", agent_string=…)` plus `--resume-session`; repick via the existing
   pick launch argv — reuse the `minimonitor_app.py:3021` /
   `monitor_app.py:3612` shape through a shared helper, do not fork it) →
   `restore-begin --mode` (nonce) → the four `AITASK_RESTORE_*` variables
   (`AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n>
   AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid>`) delivered by
   **`respawn-pane -e` — preferred; see the env-passing note below (t1716)** —
   or by the equivalent `env …` command prefix → `set-option -pu
   @aitask_standin_ready` → `respawn-pane -k` (or `launch_in_tmux` into a
   new window named by `unique_window_name` when `pane_id=""`) →
   `restore-launched --nonce --pane --pane-pid` → poll `show` until
   `state=live`, `last_error` for this nonce, or `restore_ack_grace` (20 s,
   config `frozen.restore_ack_grace`) → the four outcomes (`RESTORED:<id>|hook`,
   `RESTORE_FAILED:<id>|session_mismatch`, `RESTORED:<id>|liveness` with
   captures kept, `RESTORE_FAILED:<id>|agent_exited`) with the abort →
   clear ready → respawn stand-in → `standin-respawned --nonce` sequence;
   `NONCE_MISMATCH` anywhere → exit without touching the pane. Test seam
   `AITASKS_RESTORE_FAIL_AT=begin|respawn|ack` and
   `AITASKS_FROZEN_PAUSE_AT=aborting` under `AITASKS_TEST_MODE=1`.
3. **`aitask_frozen.sh restore <id> [--repick] | --all`** — the detached
   coordinator entry. Callers (viewer, minimonitor) invoke it via
   `TmuxClient.run(["run-shell", "-b", "<abs path> restore <id>"])`; it
   `setsid`s itself so it outlives the pane that asked.
4. **Reconcile rows for `restoring` / `aborting`** (§C table) in
   `lib/agent_freeze.py::reconcile` — the viewer-still-here (`standin_pid`)
   case, the `launch_pid` requirement for liveness confirm, mismatch →
   abort, stale-lease `aborting` completion.
5. **Edge cases**: empty session id and no `--repick` →
   `RESTORE_FAILED:no_session` (nothing changes); agent binary missing →
   `RESTORE_FAILED:<id>|binary` before `restore-begin`; transcript missing
   → warn, still try; codex with no hook support (per t1705_1) → resume
   allowed but the ack can only be `liveness` (captures kept) — say so in
   the result line.

## Tests (`tests/test_restore_flows_live.sh`, isolated tmux with `require_clean_ait_server` first — the fixture arms the real cleanup hook; plus
`tests/test_codeagent_resume_session.sh`)

Fake agent binary (`tests/lib/fake_agent.sh` from t1705_1, extended): honours
`--resume <sid>` / `resume <sid>`, **execs the shipped
`aitask_session_hook.sh` with a synthetic payload carrying the session id it
was given and the env it inherited** (so the real hook → real store path is
what acknowledges), then sleeps; `FAKE_AGENT_EXIT=1` makes it exit
immediately; `FAKE_AGENT_SESSION=<other>` makes it report a different
session. Cases: happy resume (`ack=hook`, captures deleted, stamp cleared,
`@aitask_record` on the pane); happy repick (new session adopted); agent
exits → `aborting` → stand-in back → `frozen`, capture intact,
`restore_attempts=1`; session mismatch → `last_error` persisted → abort via
`last_error`, **the 20 s liveness fallback must not fire** (assert elapsed
< grace); no hook (fake agent with `FAKE_AGENT_NO_HOOK=1`) → liveness
confirm after grace, captures **kept**, `ack=liveness`; gone-pane restore →
new window, old record acknowledged, no second record; coordinator
`SIGKILL`ed after clearing ready but before respawn → reconcile aborts by
`standin_pid`, never confirms; coordinator `SIGSTOP`ped in `aborting` → a
second `restore` is `TRANSITION_REFUSED`, reconcile past the grace
finishes, resumed coordinator gets `NONCE_MISMATCH`; Restore-All with one
failing record continues and reports both.
`test_codeagent_resume_session.sh`: dry-run argv for all three agents,
ordering vs the model flag, `RESUME_UNSUPPORTED:opencode`.

## Key files

- New: `lib/agent_restore.py`, the two test files; edit `aitask_frozen.sh`
  (restore verbs), `aitask_codeagent.sh`, `lib/agent_freeze.py` (reconcile
  rows), `tests/lib/fake_agent.sh`.
- The pick-launch argv helper extraction touches `monitor/minimonitor_app.py`
  and `monitor/monitor_app.py` minimally (a shared function in
  `lib/agent_launch_utils.py`); t1705_7 wires the keys.

## Env passing to the restored agent — decided by evidence (t1716)

Both mechanisms that could carry the four `AITASK_RESTORE_*` variables into the
respawned agent are **measured**, by Cases 3 and 3b of
`tests/test_frozen_standin_spike.sh` (t1705_1's probe, extended by **t1716**):

| mechanism | `#{pane_pid}` == agent pid | variable delivered |
|---|---|---|
| `env VAR=… <cmd>` prefix in the command string (Case 3) | yes | yes |
| `respawn-pane -e VAR=value` (Case 3b, t1716) | yes | yes |

**Prefer `-e`.** tmux sets the variable in the spawned process's environment
itself, so the command string carries no wrapper at all and nothing has to exec
through `env`. It needs no tmux version bump — `-e` is present on the 3.6a this
was measured against:

```
respawn-pane [-k] [-c start-directory] [-e environment] [-t target-pane]
             [shell-command [argument ...]]
```

The `env` prefix stays proven and is the fallback for a build without `-e`.

⚠ **Why `#{pane_pid}` is the assertion that matters for either choice.**
`launch_in_tmux`'s contract is that the pane's pid **is** the agent process,
because a wrapper that *outlives* the agent would make a dead agent's lock keep
reading as alive (`pid_anchor`, t1465) — a quieter failure than the false-crash
bug that contract replaced. Any change to how this task delivers the variables
must re-check that property, not just that the variables arrive.

Re-run the evidence with `bash tests/test_frozen_standin_spike.sh` (~8s, no
agent binaries needed). Full cross-child contract:
`## Spike findings (t1705_1) — PINNED` in
`aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`.

## Reference patterns

- `aitask_codeagent.sh` `build_invoke_command` (:405-584), `explore-relay`
  env-prefix rebuild (:489-520), `cmd_invoke` (:586-614).
- `lib/agent_launch_utils.py` `launch_in_tmux` (:1326-1407, the
  unwrapped-command contract), `resolve_dry_run_command` (:234-264),
  `unique_window_name` (:1452-1467), `resolve_pane_id_by_pid` (:1410-1433).
- `monitor/monitor_shared.py:629-673` `_run_marks_cmd` — subprocess seam
  shape (total by contract, never raises).
- `tests/test_agent_marks_concurrency.sh` — background-process test shape.

## Verification

```bash
bash tests/test_codeagent_resume_session.sh
bash tests/test_restore_flows_live.sh               # outside the -L ait server
bash tests/test_freeze_engine_live.sh               # still green
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh; shellcheck .aitask-scripts/aitask_codeagent.sh .aitask-scripts/aitask_frozen.sh
```

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1738** id=2026-09-08T10:49:41Z.291cc92a1e98b5fa76ba3331 from=t1738 from_verified=yes at=2026-09-08T10:49:41Z base=c623a7e0d11ac3cd0577d3fe13eadf351340387b base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | ADVISORY (single-line by necessity: `ait note` truncates the target task file when the body contains newlines on macOS — see the end of this note). t1738 has landed. The store/tmux plumbing your plan flagged as a duplication risk now lives in `.aitask-scripts/lib/agent_frozen_ops.py`, which both engines import. SURFACE (all pinned by `tests/test_agent_frozen_ops.py`): store, store_show, nonce_from, run, pane_facts, pane_location, set_option, unset_option, respawn, int_or_zero, test_mode, make_fail_at, pause_at, StageFailure, SESSIONS_SH, PANE_FACT_FORMAT, PANE_FACT_KEYS, EXIT_LOCK_BUSY, EXIT_TRANSITION_REFUSED, EXIT_NONCE_MISMATCH, EXIT_LEASE_HELD. SEAM RULE (the part that bites if missed): `store` and `_TMUX` are module-level mutables the tests swap in place, so call the shared FUNCTIONS through the module (`import agent_frozen_ops as frozen_ops; frozen_ops.store(...)`) and never import-alias them — `from agent_frozen_ops import store as _store` binds the original object and silently bypasses the swap. `tests/test_agent_frozen_ops.py` fails on any engine module holding a global bound to the original store/_TMUX object, and it looks up `agent_restore` dynamically, so it starts covering your module the moment it exists with no edit to that test. Constants and StageFailure are never swapped and may be imported by name. For `tests/test_agent_restore.py` the seam install is: `agent_frozen_ops.store = fake_wrapper; agent_frozen_ops._TMUX = fake_tmux`. FAILURE SEAM: make_fail_at is a factory precisely so the two engines are isolated — bind yours as `_fail_at = frozen_ops.make_fail_at("AITASKS_RESTORE_FAIL_AT")`; pause_at stays a plain function on the shared AITASKS_FROZEN_PAUSE_AT. ONE DECISION WORTH REVISITING IN YOUR PLAN: p1705_5 `## Files` says "Edit lib/agent_freeze.py — grace accessor only (V1/V2): add restore_ack_grace()"; putting it there makes agent_restore import the repair module for one accessor, which is the coupling this mitigation exists to avoid — agent_frozen_ops is the natural home. I did NOT move RESTORE_ACK_GRACE / _epoch / _stale_grace; they are still in agent_freeze.py and that call is yours. UNVERIFIED AGAINST REAL TMUX — PLEASE RUN THE LIVE SUITE: `bash tests/test_freeze_engine_live.sh` was NOT run for t1738. require_clean_ait_server refused because the implementing session ran inside the -L ait server with five live agent panes, and AIT_LIVE_TMUX_TEST_FORCE=1 would have armed real pane-died hooks against those panes (aitask_companion_cleanup.sh runs raw tmux with no socket flag by design, so no env override sandboxes it). You already carry that suite in your own tmux preflight and will be working the same engine, so you are the natural place for the first live run of the extracted plumbing — run it from a shell OUTSIDE tmux before relying on the refactor. WHAT DID PASS at t1738 commit c623a7e0d: run_all_python_tests.sh 6982 tests PASSED (runner=unittest); test_agent_freeze.py 53 passed with no assertion changed (only the _install seam re-point); test_agent_frozen_ops.py 28 passed with both negative controls verified to fail as designed; test_no_raw_tmux.sh 5 passed. aitask_frozen.sh is unchanged and still execs agent_freeze.py, so your V8 shell-level restore dispatch is unaffected. FINALLY, AN UPSTREAM DEFECT FOUND WHILE SENDING THIS: `ait note` with a multiline body TRUNCATES THE TARGET TASK FILE TO 0 BYTES on macOS — lib/ledger_block.sh:227 and :246 pass the body via `awk -v body=...`, BSD awk rejects a newline in a -v assignment and exits 2 with no output, and the following `mv "$tmp" "$file"` is unconditional. It destroyed this very file once; it was restored from git (commit 8d47a8e3b). Until that is fixed, send notes with single-line bodies only.

> **👁 note:read** id=2026-09-08T12:21:00Z.6d2cb9de6d005ce35ffd5e0b by=t1705_5 at=2026-09-08T12:21:00Z mode=explicit ids=2026-09-08T10:49:41Z.291cc92a1e98b5fa76ba3331

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T07:18:52Z status=pass attempt=1 type=human
>
> Note: deferred

> **✅ gate:plan_approved** run=2026-09-08T08:40:15Z status=pass attempt=2 type=human

> **✅ gate:plan_approved** run=2026-09-08T12:37:59Z status=pass attempt=3 type=human

> **✅ gate:review_approved** run=2026-09-08T13:36:25Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-08T13:37:40Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:6a538f36d2c3b3b2

> **✅ gate:risk_evaluated** run=2026-09-08T13:37:40Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1705_5/risk_evaluated_2026-09-08T13:37:40Z-risk_evaluated-a1.log`
