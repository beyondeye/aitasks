---
priority: high
effort: high
depends: [t1705_4]
issue_type: feature
status: Ready
labels: [tmux, tmux_destructive, codeagent, claudecode, codexcli, session_persistence, python, testing]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:04
updated_at: 2026-09-04 16:04
---

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
   `restore-begin --mode` (nonce) → `env AITASK_RESTORE_RECORD=<id>
   AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m>
   AITASK_RESTORE_EXPECT_SESSION=<sid>` prefix → `set-option -pu
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

## Tests (`tests/test_restore_flows_live.sh`, isolated tmux; plus
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
