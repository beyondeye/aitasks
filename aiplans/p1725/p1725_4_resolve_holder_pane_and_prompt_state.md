---
Task: t1725_4_resolve_holder_pane_and_prompt_state.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_1_*.md, aitasks/t1725/t1725_2_*.md, aitasks/t1725/t1725_3_*.md, aitasks/t1725/t1725_5_*.md, aitasks/t1725/t1725_6_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
---

# t1725_4 — resolve the holder's pane and prompt state

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
section "Child 4". Finding 3. Depends on t1725_3 (record fields `pane`,
`pane_state`; the `--require-waiting` hook that fails closed until this lands).

## Files

`.aitask-scripts/lib/tmux_exec.sh` (+ `ait_tmux_pane_for_pid`),
`.aitask-scripts/aitask_live_endpoint.sh` (`resolve_pane_for_pid` ~180-215 moves out),
`.aitask-scripts/aitask_sync.sh` (fill `PROT_PANE` / `PROT_PANE_STATE`; the
`_commit_group` re-probe), new `.aitask-scripts/lib/pane_state_probe.py`,
`.aitask-scripts/monitor/prompt_patterns.py`, `.aitask-scripts/monitor/monitor_core.py`
(`classify_content` ~222), `.aitask-scripts/lib/tmux_exec.py` (`tmux_socket_args`).
Guards: `tests/test_no_raw_tmux.sh`, `tests/test_live_endpoint*.sh`; fixture
`tests/lib/tmux_isolation.sh`; snippet shapes in `tests/test_prompt_detection.py`.

## Steps

1. Move `resolve_pane_for_pid` into `lib/tmux_exec.sh` as `ait_tmux_pane_for_pid
   <pid>` (echo `<pane_id>\t<session>:<window_id>.<pane_id>`; bounded ancestor walk;
   gateway socket only). `aitask_live_endpoint.sh` calls it; its explanatory comment
   moves with the code.
2. `lib/pane_state_probe.py` — CLI and module. `pane_state_probe.py <pane_id>` prints
   exactly one line (`waiting_<kind>` / `active` / empty), exit 0 always. Capture via
   `tmux_socket_args()` + `capture-pane -p -e -t <id> -S -200`; classify with
   `prompt_patterns.all_patterns()` + `monitor_core.classify_content`. Verify first
   that importing `monitor_core` pulls no Textual App; if it does, import
   `strip_ansi` + `_prompt_detection_text` only and run the scoped pattern loop
   locally. Idle is not attempted.
3. `aitask_sync.sh`: for `live_lock` / `unknown_liveness` records on this host with a
   numeric pid, fill `PROT_PANE` (helper) and `PROT_PANE_STATE` (probe via
   `python_resolve`) — best-effort, empty on failure, one call each per task,
   memoized across the task's paths; both `_pct_encode`d.
4. Wire the `--require-waiting` re-probe in `_commit_group` (after 5a.3, before the
   commit): not `waiting_*` → `_protect "holder_not_waiting"` with the observed state.
5. `shellcheck`; `bash tests/test_no_raw_tmux.sh`.

### Post-phase (risk mitigations)

6. [pane_unresolvable_degrades_to_pid] Deferred sweep with a live lock whose pid is
   not a descendant of any gateway pane (the test shell on the isolated socket) →
   the record still emits with pid, email, host filled and `pane` / `pane_state`
   empty. (TUI half lands in t1725_5's screen test.)

## Verification

- `tests/test_tmux_pane_for_pid.sh` (isolated socket): own pid resolves; a child
  process resolves via the walk; unrelated pid → exit 1; session `a|b` round-trips on
  the wire.
- `tests/test_pane_state_probe.py` (capture stubbed): AskUserQuestion snippet →
  `waiting_claude_askuserquestion`; plain output → `active`; capture failure → `""`;
  CLI prints one line, exit 0, in all three.
- Sweep-level: live lock anchored to a pane whose screen shows the snippet → record
  carries the pane target and `waiting_claude_askuserquestion`.
- `--require-waiting` end-to-end: screen rewritten from the snippet to plain output
  between the deferred sync and the retry (`--commit-for-task <id>
  --require-waiting`) → `holder_not_waiting`, nothing committed; left waiting →
  committed.
- `bash tests/test_live_endpoint*.sh`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_sync_deferral_and_quarantine.sh`,
  `bash tests/run_all_python_tests.sh --test-dir tests`.

## Step 9

Standard post-implementation; parent t1725 archives after the last child.
