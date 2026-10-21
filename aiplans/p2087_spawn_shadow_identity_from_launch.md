---
Task: t2087_spawn_shadow_identity_from_launch.md
Base branch: main
Output branch: main
---

# t2087 — spawn_shadow: take the shadow's pane identity from the launch

## Context

`monitor_core.spawn_shadow` launches the shadow with `launch_in_tmux` (pid only),
then looks the pane up with `resolve_pane_id_by_pid`. That lookup's `None` merges
"list-panes failed" (gateway `(-1, "")`) with "no pane has this pid". On `None`
the spawn only warns and returns, leaving a **live, unstamped** shadow: it lists
as an agent, evades the duplicate guard (`find_shadow_pane_status`), and the
cleanup hook never kills it. t2073_4 fixed the same hole for the scratchpad with
`launch_split_pane` (id from `-P -F`) plus identity-gated recovery
(`_recover_pad_pane`) and a probe-backed stamp (`_stamp_or_remove`). This task
moves `spawn_shadow` onto the same machinery, for BOTH placement branches.

## Implementation

### 1. `.aitask-scripts/lib/agent_launch_utils.py`

- Extract the id/pid parsing from `launch_split_pane` into
  `_parse_pane_id_pid(out) -> (pane_id | None, pane_pid | None)` (unchanged
  semantics: split before trim, `%<n>` id, positive-int pid). `launch_split_pane`
  calls it.
- Extract the new-window argv from `launch_in_tmux` into
  `_new_window_argv(command, config, fmt)` (same flags: `-P -F <fmt>`, `-d` iff
  `not select_window`, `-t <session>:`, `-n <window>`, `-c cwd`, command
  unwrapped). `launch_in_tmux`'s new-window branch uses it with `#{pane_pid}` —
  argv byte-identical to today.
- Add `launch_window_pane(command, config) -> (pane_id, pane_pid, error)`: the
  new-window sibling of `launch_split_pane`, format `#{pane_id}\t#{pane_pid}`,
  error `"tmux new-window failed (rc=N)"`, same per-field validation contract and
  the same unwrapped-command docstring note.

### 2. `.aitask-scripts/monitor/monitor_core.py`

- Generalize the t2073_4 helpers to helper-neutral names and move them (with the
  row regex and tries/spacing constants) just above `spawn_shadow`, so both
  spawns read them from one place:
  - `_recover_pad_pane` → `_recover_launched_pane` (body unchanged; docstring
    says "launched helper pane");
  - `_SCRATCHPAD_RECOVER_TRIES/_SPACING` → `_LAUNCH_RECOVER_TRIES/_SPACING`;
  - `_probe_pane`, `_stamp_or_remove` keep their names; docstrings drop "pad".
  `spawn_scratchpad` updated to the new names; behaviour unchanged.
- `spawn_shadow`:
  - launcher = `launch_split_pane` when `same_window`, else `launch_window_pane`;
    `shadow_pane, pid, err = launcher(full_cmd, cfg)`. `err` → same error notify,
    no refresh (unchanged contract).
  - no id → `_recover_launched_pane(monitor, pid)`:
    - `exited` → warning "Shadow exited immediately — nothing was launched",
      refresh, return None;
    - `unknown` → error "Shadow launched (pid N), but its pane could not be
      classified — it may appear in the agent list; close any stray pane by
      hand" (pid part omitted when absent), refresh, return None. Never claimed
      gone, never stamped.
  - stamp via `_stamp_or_remove(monitor, shadow_pane, SHADOW_TARGET_OPTION,
    followed_pane)`; non-`ok` outcomes map through a new
    `_SHADOW_REMOVAL_MESSAGES` (`exited` warning / `removed` error — keeps the
    current "could not be classified — removed it. No shadow is running." text /
    `stuck` error "…removal could not be confirmed — close it by hand"), refresh,
    return None.
  - hook, notify, phase stamp, refresh: unchanged.
  - drop the now-unused `resolve_pane_id_by_pid` import from monitor_core (still
    used by syncer / learner from agent_launch_utils). Update the docstring
    paragraph on the stamp.

### 3. Tests

- `tests/test_monitor_shadow_pick.py`:
  - `_FakeMon`: answer `display-message` from a live set (pane live until a
    `kill-pane` removes it), plus an optional `recover=(rc, out)` answer for the
    `list-panes -a -F "#{pane_id} #{pane_pid}"` recovery query.
  - `_SpawnMocks`: patch `mc.launch_split_pane` and `mc.launch_window_pane`
    (default `("%9", 999, None)`), `launch` property = whichever was called; drop
    the `resolve_pane_id_by_pid` patch (monitor_core no longer imports it).
    `launch=(None, "boom")` → `(None, None, "boom")`.
  - Update `test_unclassifiable_pane_…` to the new recovery path; keep
    `test_stamp_failure_retries_then_kills_the_pane` (now probe live → kill →
    probe gone).
  - New `ShadowIdentityTests` (mocked regressions):
    split id from launch → no recovery query and stamp on that id; window branch
    uses `launch_window_pane` (split mock uncalled) and stamps its id; no id +
    recovery finds `%9 999` → stamped + hook; no id + well-formed listing without
    the pid → "exited", no stamp/kill/hook; no id + every recovery query fails →
    3 bounded queries, no stamp/hook, error names pid, never "exited"/"removed",
    one refresh; no id + no pid → zero recovery queries; stamp fails + first
    probe gone → no kill, "exited"; stamp fails + probes stay live → kill once,
    "close it by hand", not "removed".
- `tests/test_minimonitor_shadow_pick.py`: ConfirmPath tests patch
  `launch_split_pane` → `("%9", 999, None)` instead of `launch_in_tmux` +
  `resolve_pane_id_by_pid`; assert the stamp targets the launch's id with no
  pid lookup. Add one regression: no id + failed recovery → no stamp, no hook,
  "could not be classified" warning.
- `tests/test_shadow_phase_restamp.py`, `tests/test_minimonitor_concern_action.py`
  (LaunchShadowGuardTests): repoint their monkeypatches at the new launchers so
  they stay non-vacuous.
- `tests/test_minimonitor_scratchpad_spawn.py`: rename `_recover_pad_pane` refs.
- `tests/test_launch_in_tmux_pane_pid.py`: `LaunchWindowPaneTests` — parsing
  table, rc≠0 error, argv equals `launch_in_tmux`'s new-window argv except the
  format, `-d` present iff `select_window=False`.
- Comment-only refresh: `tests/lib/tmux_socket_containment.py` docstring and the
  header of `tests/test_monitor_shadow_spawn_live.sh` (name the new launchers).

## Verification

- `python3 tests/test_monitor_shadow_pick.py`, `tests/test_minimonitor_shadow_pick.py`,
  `tests/test_shadow_phase_restamp.py`, `tests/test_minimonitor_concern_action.py`,
  `tests/test_minimonitor_scratchpad_spawn.py`, `tests/test_launch_in_tmux_pane_pid.py`
- Real tmux, both placement branches: `bash tests/test_monitor_shadow_spawn_live.sh`,
  `bash tests/test_scratchpad_spawn_live.sh`, `bash tests/test_shadow_spawn_config.sh`
- Negative control: temporarily revert spawn_shadow to the pid lookup in a scratch
  copy / mutant and confirm the "every recovery query fails" + "window branch
  uses launch_window_pane" regressions go red.
- `bash tests/test_no_raw_tmux.sh`; full `bash tests/run_all_python_tests.sh`
  (last-line verdict).

## Follow-up (created post-approval, before the Step 8 commit)

Plan review found an older launch-error-boundary hole, kept out of this task's
scope: `TmuxClient.run` (`lib/tmux_exec.py:254`) maps `subprocess.TimeoutExpired`
to `(-1, "")`, the same answer as `FileNotFoundError` / `OSError`. A timeout does
not prove tmux failed to create the pane — creation can complete and only the
reply is lost — yet `launch_split_pane` / `launch_window_pane` (and
`launch_in_tmux`) report it as an ordinary `err`, so `spawn_shadow` and
`spawn_scratchpad` return immediately with no refresh and no recovery, possibly
leaving a live, unstamped helper pane.

Create one `bug` task (anchor 2073, `followup_kind: upstream_defect`, labels
`aitask_monitormini, tmux`) via the Batch Task Creation Procedure, describing:
distinguish an *uncertain* launch outcome (timeout) from a definite failure at the
launcher boundary (e.g. via the gateway's `run_result` `TmuxResult` status or a
dedicated timeout signal), surface it in the user-facing message, refresh the
display, advise checking for a stray pane, and pin it with a timeout regression
for both spawns. **Do not blindly retry the launch.** Severity medium, effort low.

## Step 9 (Post-Implementation)

Commit code (`bug: … (t2087)`) and plan separately; archive via the standard
Step 9 flow on the current branch.

## Risk

### Code-health risk: low
None identified. The change mirrors the t2073_4 pattern already pinned by tests,
keeps `launch_in_tmux`'s argv byte-identical, and both placement branches are
exercised against real tmux by the existing live test.

### Goal-achievement risk: low
None identified. Both branches get launch-returned identity, and the
unknown ≠ gone rule is pinned by mocked regressions with a negative control.
