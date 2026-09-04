---
priority: high
effort: high
depends: [t1705_3]
issue_type: feature
status: Ready
labels: [tmux, tmux_destructive, codeagent, minimonitor, aitask_monitor, session_persistence, python, testing]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:04
updated_at: 2026-09-04 16:04
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

Fourth child of t1705 (frozen code agents). Implements the **freeze**
transaction and the **reconcile** pass: capture the agent pane's scrollback,
stamp the pane, write the record through its lease-owned states, and
`respawn-pane -k` the agent's own pane into the stand-in viewer command —
while the companion minimonitor and the window survive. Everything here is
governed by the parent plan's §B/§C (**PINNED**; reproduced with t1705_1's
spike findings in `aiplans/p1705/p1705_4_freeze_engine.md`) and driven
through the store shipped by t1705_2 (`aitask_agent_sessions.sh` verbs). The
viewer command itself lands in t1705_6; until then `standin_command()`
names a binary that does not exist and the `freeze` verb is not user-facing
(t1705_7 wires the keys).

**Tmux-stress**: implement and verify from a shell **outside** the user's
`-L ait` server (`aidocs/framework/tui_conventions.md` §"Tmux-stress tasks").
`respawn-pane` has no call sites in the tree yet; the cleanup hook is
raw-tmux by design and kills windows.

## Deliverables

1. **`.aitask-scripts/lib/agent_freeze.py`** — `freeze_pane(pane_id, *,
   cap=None) -> FreezeResult`, `freeze_all()`, `reconcile()`. All tmux via
   `TmuxClient` (`lib/tmux_exec.py`); all store writes via the shell
   wrapper (`subprocess.run([".../aitask_agent_sessions.sh", verb, …])`,
   never importing the store's mutators — the wrapper is the sole writer).
   The §C sequence, verbatim: resolve record (`@aitask_record` →
   `show`; else `upsert` fallback) → capture (`capture-pane -p -e -J -t
   <pane> -S -<cap>`, cap from `project_config.yaml`
   `frozen.capture_max_lines`, default 50000, into
   `$AITASKS_FROZEN_DIR/<id>/capture.ansi`, stripped `.txt` via
   `monitor/ansi_utils`) → `freeze-begin` → stamp `@aitask_frozen=<id>`,
   unset `@aitask_standin_ready` → `respawn-pane -k -t <pane>
   '<standin_command(id)>'` → read `#{pane_id}\t#{pane_pid}` →
   `freeze-commit --nonce --pane --pane-pid`. Failure handling per stage,
   `FREEZE_FAILED:<stage>` reporting, `NONCE_MISMATCH` → exit without
   touching the pane. Test seams `AITASKS_FREEZE_FAIL_AT`,
   `AITASKS_FROZEN_PAUSE_AT` (SIGSTOP self), honoured only under
   `AITASKS_TEST_MODE=1`.
2. **`.aitask-scripts/aitask_frozen.sh`** — `freeze <pane_id> | --all`,
   `reconcile`, later `restore` (t1705_5). Thin bash entry over the Python
   module (`require_ait_python`), so TUIs and `run-shell -b` can call it.
   Not skill-invoked → no allow-list entries; **no** `ait` dispatcher entry
   yet (t1705_6 adds `ait frozenagent`; a user-facing `ait frozen`
   dispatcher case is decided in t1705_9/10 docs — default no).
3. **`reconcile`** — the §C table, lease-gated (`lease-take`; skip on
   `LEASE_HELD`), fed by its own `list-panes` pass over every
   `discover_aitasks_sessions()` session, also emitting the observation
   file (`ROOT`/`WINDOW`/`PANE`/`INCOMPLETE`) and calling `purge --observed`.
   The indeterminate rows **do not transition** — pin that.
4. **List-panes format arity** — append `#{@aitask_frozen}`,
   `#{@aitask_record}`, `#{@aitask_standin_ready}`, `#{pane_dead}` to
   `monitor_core._LIST_PANES_FORMAT` (:2124-2127), `kill_agent_pane_smart`'s
   format (:3236-3239), `aitask_companion_cleanup.sh` (:47, :79) and
   `agent_launch_utils.maybe_spawn_minimonitor` occupancy (:1725); update
   the arity constants pinned in `tests/test_monitor_companion_filter.py:106`,
   `:548`, `:606`, `tests/test_agent_marks_generation.py:160`,
   `tests/test_multi_agent_window_substrate.sh:386`. Add
   `TmuxMonitor.last_discovered_panes()` (pane_id, pane_pid, pane_dead per
   window) beside `last_discovered_agents()`, and `TmuxPaneInfo` gains
   `frozen_record`, `record_id`, `standin_ready`, `pane_dead` fields
   (renderers are t1705_7's job; here they are only parsed and exposed).
5. **Cleanup contract** — `aitask_companion_cleanup.sh`: abstain entirely
   when the dying pane (`$primary`) carries `@aitask_frozen`; count a
   `@aitask_frozen`-stamped sibling as a **real agent**. Same two rules in
   `monitor_core.count_other_real_agents` / `kill_agent_pane_smart`
   (:3220-3277): a frozen pane counts as real; killing a frozen pane =
   `drop <id>` (captures removed) then the existing kill-by-sibling-rule.
   Rebase on **t1699** (in flight) before touching
   `tests/test_kill_agent_pane_smart.sh`.
6. **Freeze-All** — iterate `discover_aitasks_sessions()` × agent panes
   (`classify_pane` == AGENT, not shadow, not already frozen), freeze each,
   report per-pane results, never abort the batch.

## Pre-phase (inline risk mitigation — `characterize_list_panes_arity`)

Before step 4, add `tests/test_list_panes_arity_characterization.py`: pin
the current 11-field `_LIST_PANES_FORMAT` parse, prove that a field
**appended** after the current tail parses while a field **inserted** before
`history_size` shifts it (the defect the arity rule exists for), and that a
trailing empty `@option` still yields the right field count (the `strip()`
regression t1686 fixed). Run it green against unmodified `monitor_core.py`
and commit it before the format changes.

## Post-phase (inline risk mitigation — `cleanup_rule_parity_test`)

`tests/test_cleanup_rule_parity.sh`: one table of pane records
(live agent / frozen stand-in / shadow / companion / dead pane, in every
position incl. last) driven through **both** `aitask_companion_cleanup.sh`
(isolated tmux, instrumented `tmux kill-pane` wrapper on `PATH`) and
`count_other_real_agents`; assert the two agree on "kill window" vs "kill
pane" for every row, and that a dying stamped pane makes the script abstain.

## Failure-injection tests (`tests/test_freeze_engine_live.sh`, isolated tmux)

Extend t1705_1's probe (`tests/test_frozen_standin_spike.sh` is the control):
happy path (record `frozen`, `standin_pid` recorded, companion alive, capture
files 0600 with the right line count); fail at each `AITASKS_FREEZE_FAIL_AT`
stage → the §C rollback outcome (agent still running, no stamp, record
`live`, no capture files); coordinator `SIGKILL`ed between stamp and respawn
→ reconcile past `stale_op_grace` aborts by `pane_pid` match; coordinator
`SIGSTOP`ped at `begin` → concurrent reconcile **skips** (fresh lease),
after the grace with the owner killed it takes over, and the resumed
coordinator's `freeze-commit` gets `NONCE_MISMATCH` and leaves the pane
alone; stand-in dead (`pane_dead=1`) → reconcile respawns it; window gone
while `freezing` → `freeze-commit --pane "" --pane-pid 0`. Use
`AITASKS_FROZEN_STANDIN_CMD` to point the stand-in at a script that stamps
`@aitask_standin_ready` itself (the viewer does not exist yet).

## Key files

- New: `lib/agent_freeze.py`, `aitask_frozen.sh`, the three test files above.
- Edit: `monitor/monitor_core.py` (format, `TmuxPaneInfo`, `last_discovered_panes`,
  `count_other_real_agents`, `kill_agent_pane_smart`, option constants beside
  `SHADOW_TARGET_OPTION` :385), `aitask_companion_cleanup.sh`,
  `lib/agent_launch_utils.py:1723-1747`, the five arity tests.

## Reference patterns

- `monitor/monitor_core.py:626`, `:2558` — existing `capture-pane` argv;
  `:1951-1976` `get_pane_option` and its `(ok, value)` rationale; `:3482-3497`
  the shadow stamp that **kills the pane if the stamp fails** (freeze must
  instead abort and leave the agent running).
- `aitask_shadow_capture.sh:236-268` — one-round-trip `display-message`
  self-identification.
- `monitor/monitor_shared.py:361-384`, `:629-673` — maintenance-tick
  dispatch and subprocess seam (`reconcile` will be dispatched from there in
  t1705_7; here it only needs to be safe to call every 600 s).
- `tests/lib/tmux_isolation.sh`, `tests/test_shadow_capture.sh`,
  `tests/test_kill_agent_pane_smart.sh`.
- `aidocs/framework/tmux_gateway.md` — do not extend the raw-tmux allowlist.

## Verification

```bash
bash tests/test_list_panes_arity_characterization.py-run   # via run_all_python_tests.sh --test-dir
bash tests/run_all_python_tests.sh
bash tests/test_freeze_engine_live.sh            # outside the -L ait server
bash tests/test_cleanup_rule_parity.sh           # outside the -L ait server
bash tests/test_frozen_standin_spike.sh          # still green (control)
bash tests/test_kill_agent_pane_smart.sh tests/test_multi_agent_window_substrate.sh tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/aitask_frozen.sh .aitask-scripts/aitask_companion_cleanup.sh
```
