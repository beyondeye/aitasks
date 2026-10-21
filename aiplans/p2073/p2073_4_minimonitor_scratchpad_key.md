---
Task: t2073_4_minimonitor_scratchpad_key.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-20 18:57
---

# t2073_4 — minimonitor_scratchpad_key (verified plan)

## Context

Child of t2073 (minimonitor scratchpad pane). The store (t2073_1), the
`ait scratchpad` app (t2073_2) and the bound-helper pane rule (t2073_3) have
landed. This child adds the entry point: minimonitor key **`o`** opens a
scratchpad in a **vertical split of the followed agent's pane**, bound to that
agent. Position and height are configurable. Only one pad is allowed per store
(project + task), and one per followed agent pane. A non-task agent gets an
**unsaved** pad plus a "not saved" notification. The full monitor gets no
action (user decision). Parent design: `aiplans/p2073_minimonitor_scratchpad_pane.md`.

### Verification findings (what changed since the plan was written)

- **The t2065 gate passes.** `minimonitor_app.py` has no uncommitted hunks, and
  t2065 is committed (69267df56). Re-run `git diff --quiet -- <file>` just before
  the first edit anyway; this is a shared worktree.
- **Vocabulary exists**: `lib/helper_panes.py` has `SCRATCHPAD_TARGET_OPTION` and
  `SCRATCHPAD_STORE_OPTION`, and `monitor_core` re-exports them (:63-66).
  `FROZEN_OPTION` lives at `monitor_core.py:497`. Import these names; never
  re-spell them.
- **Consumers are done**: discovery, `classify_window_panes`, the occupancy check,
  cleanup jobs 1/2 and the rung-2 fallback already treat a pane stamped
  `@aitask_scratchpad_target` as a bound helper. Only the spawn side is left.
- **Frozen-first** (t2073_3 note, and the project rule that every helper filter
  checks `@aitask_frozen` first): the duplicate lookup reads `@aitask_frozen`
  and skips frozen panes. A respawned stand-in keeps the old pane options, so a
  retained marker must never refuse a spawn. This needs a test with a control.
- **Store-key helper**: `aitask_scratchpad_store.sh path <id>` prints the
  canonical absolute store dir and creates nothing. It canonicalizes the deepest
  existing ancestor and appends the rest, so the key stays the same before and
  after the store is created. Call **this framework's** copy (`_SCRIPT_DIR`) with
  `cwd=target_root`. The minimonitor's `_BOARD_COLUMN_SH` does the same. This
  also lets tests run the real helper against temp roots.
- **Command shape**: plain TUIs launch as `ait <tui> …` with cwd set to the
  project root (`_COMPANION_ARGV`, `agent_sessions.standin_command`).
  `launch_in_tmux` passes `-v -b -l <rows>` for a vertical split with
  `split_before` (agent_launch_utils.py:2116-2124).
- **No separate key registry**: `shortcut_scopes.py:57` discovers minimonitor
  `BINDINGS` from the module, so adding the `Binding` is enough.
  `KEY_HINTS_TEXT` coverage is enforced by `test_minimonitor_concern_action.py`.
- **Stricter duplicate rule**: a pad matches when its store key equals the one
  being opened (when non-empty) **or** its target equals the followed pane. So
  one agent pane never gets two pads, even if its task id resolution changed
  between presses. The app's `flock` remains the authoritative one-writer guard.
  This lookup only prevents the obvious duplicate.

### Review concerns addressed (both blocking, both verified valid)

- **Store environment (concern 1).** `split-window` starts the pad in the tmux
  **server/session** environment, not the minimonitor's. On top of that, `ait`
  `cd`s to its own directory (`ait:9`) and runs the target root's own copy of
  the helper. So an `AITASK_SCRATCHPAD_DIR` that is set (or unset) only in the
  minimonitor would make the stamped key and the store the editor opens diverge.
  **Fix: pin the root in the editor's command.** For a task pad,
  `scratchpad_command` prefixes `env AITASK_SCRATCHPAD_DIR=<dirname(store_key)>`.
  That value is the canonical absolute root the lookup itself resolved: the
  override when one is set, or `<target_root>/.aitask-scratchpad` (physical) in
  the default case. The editor's helper then canonicalizes
  `<canonical root>/<id>` to the same key whatever its environment, its cwd or
  its framework copy. `env` execs, so the pane-pid contract of `launch_in_tmux`
  holds. An unsaved pad touches no store and gets no prefix.
- **Pane identity (concern 2).** `launch_in_tmux` returns only a pid, and
  `resolve_pane_id_by_pid` folds "query failed" and "pane gone" into one `None`.
  **Fix: get the id from the launch itself.** A new
  `agent_launch_utils.launch_split_pane(command, config) -> (pane_id, pane_pid, err)`
  runs `split-window -P -F '#{pane_id}\t#{pane_pid}'`. Its argv comes from a
  `_split_window_argv` builder shared with `launch_in_tmux`'s split branch, so
  `launch_in_tmux` behaves byte-for-byte as before.
- **Unknown is not gone (concern 3, verified).** `tmux_exec.TmuxClient.run`
  returns `(-1, "")` on a timeout or transport failure. An empty probe output
  therefore proves nothing unless the query itself succeeded, and a successful
  query finds nothing useful for an invalid pid. Rule: **absence is reported
  only from a valid identity plus a successful, interpretable query.**
  Everything else is *unknown*. Unknown is reported with whatever identity we
  have and manual-cleanup guidance, and never as "exited" or "removed".
  - **Identity validity.** `launch_split_pane` parses each field
    independently: a pane id must match `^%\d+$`, and a pid must be a positive
    int. Anything else becomes `None`.
  - **Pane probe** `_probe_pane(monitor, pane) -> "live" | "gone" | "unknown"`
    runs `display-message -p -t <pane> '#{pane_id}'`. The result is `live`
    when rc is 0 and the output equals `<pane>`, and `gone` when rc is 0 and
    the output is empty. tmux exits 0 with empty output for a gone pane (the
    trap documented in `frozen_fixtures.sh`), which is why the output is the
    signal. Any other rc or output → `unknown`.
  - **Missing pane id, bounded recovery.** If the pid is `None` too, there is
    no identity to query. Report *unknown* straight away: "Scratchpad launched
    but tmux returned no pane id or pid — check the agent's window and close
    any stray pane by hand". If the pid is valid, run at most 3
    `list-panes -a -F '#{pane_id} #{pane_pid}'` queries through the gateway,
    0.05 s apart. `-a` makes the answer independent of session-target
    resolution. A match → continue stamping on that id. rc 0 and parseable
    with no matching pid → *exited* (no stamp, kill or hook). Every attempt
    failing → *unknown*, naming the pid.
  - **Stamp failure** after the two failed writes. The pre-kill probe decides:
    - `gone` → *exited*, with no kill;
    - `live` **or** `unknown` → best-effort `kill-pane -t <pane>`. We hold a
      valid id for a pane we created milliseconds ago, so an unknown probe must
      not skip the cleanup. Then probe again: only `gone` reports *removed*;
      `live` or `unknown` reports *stuck* ("could not confirm pane <id> was
      removed — close it by hand").
  - Outcome vocabulary of `_stamp_or_remove`:
    `"ok" | "exited" | "removed" | "stuck"`. Every outcome except `"ok"`
    notifies, calls `schedule_refresh()` and returns `None`.
- **Out of scope:** `spawn_shadow` has the same resolve-by-pid hole. Offer a
  follow-up task at Step 8 to move it onto `launch_split_pane` and the same
  recovery. Its owning code is not this task's.

## Implementation

### 1. `monitor/monitor_core.py` (next to the shadow lookup and `spawn_shadow`)

```python
SCRATCHPAD_POSITIONS = ("top", "bottom")
SCRATCHPAD_DEFAULT_POSITION = "bottom"
SCRATCHPAD_DEFAULT_HEIGHT = 12
_SCRATCHPAD_STORE_SH = <_SCRIPT_DIR>/aitask_scratchpad_store.sh   # resolve like other script paths in the module
_SCRATCHPAD_PATH_TIMEOUT = 5.0

def scratchpad_query_args() -> list[str]:
    # list-panes -a -F '#{pane_id}\t#{@aitask_scratchpad_target}\t#{@aitask_scratchpad_store}\t#{@aitask_frozen}'

def match_scratchpad_pane(out, followed_pane, store_key) -> str | None:
    # pure; pad rows to 4 fields; skip a non-empty frozen field FIRST;
    # match (store_key and store == store_key) or target == followed_pane

def find_scratchpad_pane_status(monitor, followed_pane, store_key) -> tuple[bool, str | None]:
    # same shape as find_shadow_pane_status: (False, None) on monitor None / rc != 0

def scratchpad_store_key(target_root: Path, task_id: str) -> str | None:
    # subprocess.run([str(_SCRATCHPAD_STORE_SH), "path", task_id], cwd=target_root,
    #   capture_output=True, text=True, timeout=...); None on OSError, timeout,
    #   rc != 0, or output that is not exactly one absolute path line

def scratchpad_command(task_id: str | None, target_pane: str,
                       store_root: str | None = None) -> str:
    # task:    "env AITASK_SCRATCHPAD_DIR=<store_root> ait scratchpad --task <id> --target <pane>"
    # unsaved: "ait scratchpad --unsaved --target <pane>"
    # shlex.quote each value; a task pad without an absolute store_root raises
    # ValueError (a programming error, never a silent unpinned launch).
    # Live cases A-D replace this one function; case E runs it for real.

def scratchpad_placement(tmux_cfg: dict) -> tuple[str, int]:
    # position: str(value).strip().lower() in SCRATCHPAD_POSITIONS, else the default
    # height: an int >= 1 (bool rejected, int("12") accepted), else the default

def spawn_scratchpad(monitor, *, followed_pane, followed_window, session, task_id,
                     target_root, companion_pane, select_window, notify,
                     schedule_refresh) -> str | None:
```

`spawn_scratchpad` mirrors `spawn_shadow`. The docstring repeats the
never-reads-`TMUX_PANE` and companion-pane contract, adds the frozen-first
note, and states the launch-to-stamp window, during which the app's flock is
the authority. In order:

1. Return `None` if `monitor is None`.
2. For a task pad: `store_key = scratchpad_store_key(target_root, task_id)`.
   `None` → error "Could not resolve the scratchpad store for t<id> — not opening".
   Return without launching. An unsaved pad uses `store_key = ""`.
3. `ok, existing = find_scratchpad_pane_status(...)`. If `not ok`, warn "Could
   not verify whether a scratchpad is already open — not opening". If `existing`,
   warn "A scratchpad is already open for t<id>" (or "…for this agent"). Return
   either way.
4. `position, height = scratchpad_placement(load_project_tmux_config(target_root))`.
   Build `TmuxLaunchConfig(session=session, window=followed_window, new_session=False,
   new_window=False, split_direction="vertical", split_before=(position == "top"),
   split_size=height, split_target_pane=followed_pane, cwd=str(target_root),
   select_window=select_window)`.
5. `launch_split_pane(scratchpad_command(task_id, followed_pane,
   os.path.dirname(store_key) or None), cfg)`. On error, notify an error and
   return without calling `schedule_refresh`.
6. If no valid pane id came back, run `_recover_pad_pane(monitor, pid)`. That
   is the identity-gated, bounded recovery above. It returns `("found", id)`,
   `("exited", None)` (only with a valid pid and a successful query) or
   `("unknown", None)`.
7. A small helper `_stamp_or_remove(monitor, pane, option, value)` writes the
   option and retries once. If both writes fail, it applies the
   probe → kill → re-probe rule above and returns
   `"ok" | "exited" | "removed" | "stuck"`. Stamp
   `SCRATCHPAD_TARGET_OPTION=followed_pane`, then (task pads only)
   `SCRATCHPAD_STORE_OPTION=store_key`. Any outcome other than `"ok"` gets the
   matching notification, then `schedule_refresh()` and `return None`.
8. `attach_companion_cleanup_hook(followed_pane, companion_pane or pad)`.
   `"unverified"` → warn "…close the scratchpad by hand when the agent exits".
   Otherwise notify "Opened scratchpad for t<id>" or "Opened scratchpad (not saved)".
9. `schedule_refresh()` and return the pad pane id.

### 1b. `lib/agent_launch_utils.py`

- Extract `_split_window_argv(command, config, fmt) -> list[str]` from
  `launch_in_tmux`'s split branch (:2116-2124), with `fmt="#{pane_pid}"` there.
- Add `launch_split_pane(command, config) -> tuple[str | None, int | None, str | None]`.
  It runs the builder with `fmt="#{pane_id}\t#{pane_pid}"` through `_TMUX.run`
  and does the same `select-window` handling. It parses the first line into
  `(pane_id, pid)`; an id must match `^%\d+$`, and unparsable parts become
  `None`, and each field is validated independently. A nonzero rc gives
  `(None, None, "tmux split-window failed (rc=N)")`.
  The docstring carries the same unwrapped-command contract as `launch_in_tmux`.

### 2. Config

- `.aitask-scripts/settings/settings_app.py` `TMUX_CONFIG_SCHEMA`, after
  `shadow_pane_width` (~:344):
  - `scratchpad_position`: enum `top,bottom`, default `bottom`;
  - `scratchpad_height`: int, default `12`.
  The summary and detail strings follow the shadow entries.
- `seed/project_config.yaml`: two commented doc blocks after the
  `shadow_pane_width` block (~:533), in the same style. Describe minimonitor `o`
  and the fallback when a value is invalid.

### 3. Tests that do not need `minimonitor_app.py`

NEW `tests/test_minimonitor_scratchpad_spawn.py` (unittest, with
`TmuxSocketContainmentMixin`). It patches `mc.launch_split_pane`,
`resolve_pane_id_by_pid`, `attach_companion_cleanup_hook` and
`load_project_tmux_config`. The fake monitor builds `list-panes` rows **from the
requested `-F`** (the `_render_panes` shape in `test_minimonitor_instance_guard.py`),
and `set-option` return codes are scripted per option. Real
`aitask_scratchpad_store.sh path` runs against temp roots. One root is reached
through a symlink so that canonicalization matters. Cases:

1. An unverifiable lookup (`list-panes` rc≠0) refuses, and nothing is launched.
2. A duplicate store key in the same project is refused.
3. The same task number in a second project (a different canonical key) is
   allowed. A second press in the first project is then refused.
4. The key is stable across store creation. Press 1 runs with no
   `.aitask-scratchpad/`. The store dir is then created, and press 2's key
   equals press 1's, so it is refused.
5. A failed `path` call refuses the spawn. Trigger it with a real helper failure
   (`AITASK_SCRATCHPAD_DIR` containing `..` → exit 2). Also unit-test
   `scratchpad_store_key` returning `None` for a nonzero exit and for
   non-absolute output.
6. Unsaved pads: a duplicate on the same target is refused, and a different
   followed pane is allowed.
7. Frozen first: a frozen pane carrying a matching store or target marker is
   skipped, so the spawn proceeds. The control is the same row without the
   frozen marker, which is refused.
8. A failure of the target stamp kills the pane (`kill-pane -t <pad>`). A
   failure of the store stamp (after a good target stamp) kills it too. One
   retry each.
9. Placement: `top` → `split_before=True`; `bottom`, invalid or missing →
   `False`. Also check `split_direction == "vertical"`, the split target is the
   followed pane, and `cwd` is the root.
10. Height: 12 by default and for `"tall"`, `0`, `-3` and `True`; `20` and `"20"` → 20.
11. The command string for task and unsaved pads, and the hook called with
    `companion_pane or pad`.
12. **The store root is pinned (concern 1).** The command carries
    `AITASK_SCRATCHPAD_DIR=<dirname(stamped key)>` with the override set
    **and** with it unset (default root = the physical
    `<root>/.aitask-scratchpad`). The stamped key equals what the real helper
    prints for that pinned root under a **different** ambient
    `AITASK_SCRATCHPAD_DIR`. Unsaved pads get no prefix, and a task pad without
    a root raises.
13. **Successful launch, failed identification (concerns 2 and 3).** Launch
    returns `(None, 999, None)`:
    (a) a recovery query finds pid 999 → it stamps `%9` and arms the hook;
    (b) rc 0, parseable, with no such pid → *exited*, with no set-option, no
    kill-pane and no hook;
    (c) every query fails (rc -1) → exactly 3 queries, *unknown* naming pid 999,
    no hook, and `schedule_refresh` called.
    Launch returns `(None, None, None)`, i.e. output with **neither** a valid
    id nor a pid: **zero** recovery queries, *unknown* with manual-cleanup
    guidance, no stamp and no hook. The message must not contain
    "exited"/"removed".
14. **Stamp failure, the probe matrix (concern 3).** Each row gives the
    pre-kill probe, then the post-kill probe:
    - `gone` → *exited*, and no `kill-pane` is issued;
    - `live`, then `gone` → `kill-pane`, *removed*;
    - `live`, then rc -1 (a failed post-kill probe) → *stuck* naming the pane,
      never "removed";
    - rc -1 (a failed pre-kill probe), then `gone` → `kill-pane` still issued,
      *removed*;
    - rc -1, then rc -1 → *stuck*;
    - rc 0 with unexpected output → treated as *unknown*.
    Each row asserts the issued tmux calls and the notification text.
15. `launch_split_pane`: parses `"%9\t999"`. Partial or invalid output is
    handled: `"x\t999"` → `(None, 999)`, `"%9\tabc"` → `("%9", None)`, empty
    output → `(None, None)`. A nonzero rc gives an error. The argv equals
    `launch_in_tmux`'s apart from `-F`, asserted on what the gateway receives.

### 4. `monitor/minimonitor_app.py` (after re-running the gate)

- Import `spawn_scratchpad` next to `spawn_shadow` (:51).
- Add `Binding("o", "open_scratchpad", "Notes", show=False)` after the `E` binding.
- `action_open_scratchpad()` resolves the followed agent with
  `_find_own_agent_snapshot()`. If there is none, warn "No followed agent for a
  scratchpad". If the pane id is empty, warn as the shadow action does. It reads
  `task_id = self._task_cache.get_task_id_for_pane(snap.pane)`. When that is
  `None`, notify "Not a task agent — notes will not be saved" (warning). Then
  call `self._spawn_scratchpad(followed_pane, task_id, self._root_for_snap(snap), snap)`.
  There is no pre-check: there is no dialog, so the single live check inside
  `spawn_scratchpad` is enough.
- `_spawn_scratchpad(...)` is the per-app adapter. It passes
  `companion_pane=os.environ.get("TMUX_PANE") or None`, `select_window=True`,
  `notify=self.notify` and `schedule_refresh=lambda: self.call_later(self._refresh_data)`.
  Its comment states the same companion-despawn policy as `_spawn_shadow`.
- `KEY_HINTS_TEXT` gets `o:notes` on an existing line, either `f:freeze  Z:all`
  or `k:kill  n:next  e/E:shadow`. **Measure** the rendered `#mini-key-hints`
  height at (15, 30) for each candidate and keep it ≤ 29. Pick the one that adds
  the fewest rows, and extend the band comment by one sentence recording the
  choice. The line count must not grow:
  `test_minimonitor_top_chrome_render.py` pins it.
- Mocked app tests go in the new test file: binding `o` → `open_scratchpad`,
  `o:` appears in the hints, a non-task agent gets `--unsaved` plus the
  notification, a task agent gets `--task 42 --target %1`, and the adapter
  passes `TMUX_PANE` and `select_window=True`.

### 5. Live test: NEW `tests/test_scratchpad_spawn_live.sh`

The test isolates tmux (`require_clean_ait_server`, then `require_isolated_tmux`)
and sources `tests/lib/frozen_fixtures.sh` with its contract variables. It uses
the file-backed counters (`assert_counters_init` / `assert_counters_load`)
because cases run in subshells. A Python driver calls the real
`spawn_scratchpad` through the real gateway. The **only** seam is
`mc.scratchpad_command`, which returns `tail -f /dev/null`. The freeze, restore
and fake-agent setup copy `test_freeze_engine_live.sh` / `test_restore_flows_live.sh`.

- **A**: the pad is absent from `TmuxMonitor.discover_panes()`. Its target
  (and, for a task pad, its store) options are stamped, and the agent's
  `pane-died` hook names the cleanup script.
- **B**: the agent's **process** exits, so `pane-died` fires. The pad is killed,
  and the minimonitor companion despawns. A control pad bound to a different
  agent survives.
- **C**: after freeze (`aitask_frozen.sh freeze`) the pad still exists and its
  target still equals the agent pane id, which is unchanged. The same holds
  after restore.
- **D**: freeze, then drop the record with `kill_agent_pane_smart` on the frozen
  pane (the path of freeze-engine case 9). The pad is **left behind**. Assert
  this and comment it as the known gap the `kill_bound_helpers_on_direct_kill`
  follow-up closes.
- **E (concern 1, the real editor command and no seam)**: the fixture project
  root symlinks `ait` and `.aitask-scripts` to this checkout and holds an
  active `aitasks/t9001_fixture.md` plus `aitasks/metadata/project_config.yaml`.
  A fixture `bin/ait` (`exec "$PWD/ait" "$@"`) is on the server's PATH. The
  server's **global** environment sets `AITASK_SCRATCHPAD_DIR=$T/server_pad`.
  - E1: the driver runs with `AITASK_SCRATCHPAD_DIR=$T/driver_pad`.
  - E2: the driver runs with it unset.
  In both, the real `ait scratchpad` must open its store at the **stamped**
  key: wait (bounded) for `<key>/.holder.lock`. `$T/server_pad/9001` must
  stay absent.
  - **Control E0**: the same editor command **without** the pin opens under
    `server_pad`. This proves the environments really differ and that the pin
    is what makes E1/E2 pass.
- **F (concern 2)**: `launch_split_pane` returns the id of the pane tmux
  actually created (checked against a `list-panes` read-back).

## Verification

- `python3 tests/test_minimonitor_scratchpad_spawn.py`
- `python3 tests/test_minimonitor_concern_action.py` (hint coverage) and
  `python3 tests/test_minimonitor_top_chrome_render.py`
- `python3 tests/test_helper_panes.py`,
  `python3 tests/test_settings_project_config_value_types.py`,
  `python3 tests/test_monitor_shadow_pick.py`, `python3 tests/test_minimonitor_shadow_pick.py`
- `bash tests/test_scratchpad_spawn_live.sh` (run outside tmux, with the `-L ait` server stopped)
- Every existing test module that exercises `launch_in_tmux` (`grep -l launch_in_tmux tests/`), to confirm the builder extraction did not change behaviour
- `bash tests/test_no_raw_tmux.sh`; `shellcheck` on the new `.sh` test
- A note to t2073_5 (docs): the editor's store root follows the minimonitor's effective `AITASK_SCRATCHPAD_DIR`, pinned explicitly on the command
- The full Python suite (`bash tests/run_all_python_tests.sh`): read the last line only.

## Step 9 (Post-Implementation)

Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: low
- `spawn_scratchpad` mirrors `spawn_shadow`. The minimonitor change is one binding, an action and an adapter, and the new lookup is a pure, tested function · severity: low · → mitigation: none
- `launch_in_tmux`'s split branch now builds its argv through a shared builder. The behaviour is unchanged, and the existing launch tests plus the argv-parity test 15 pin it · severity: low · → mitigation: none
- The hint band can grow by one wrapped row at narrow widths. It is measured, not eyeballed, and pinned by existing tests · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Bound helpers survive the direct `kill-pane` paths (the pane branch of `kill_agent_pane_smart`, and a frozen-record drop) because no `pane-died` fires. Live case D asserts this · severity: medium · → mitigation: kill_bound_helpers_on_direct_kill
- Between launch and stamp, a concurrent second press cannot see the first pad. The app's `flock` makes the second pad read-only, so there is no data loss · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: kill_bound_helpers_on_direct_kill | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: bound helpers survive direct kill-pane paths | desc: Kill panes bound to an agent (shadow/scratchpad target options) when kill_agent_pane_smart's pane branch or a frozen-record drop kills that agent directly, with tests for both paths

## Post-Review Changes

### Change Request 1 (2026-10-20 18:40)
- **Requested by user:** `scratchpad_placement` truncated a fractional YAML height (`1.5` → 1) and let `.inf` / `-.inf` raise `OverflowError`. `_recover_pad_pane` read any rc=0 listing as evidence: `garbage` and `%9 broken` gave "exited", and `bogus 999` gave "found bogus".
- **Changes made:**
  - The height is validated before any conversion: only an `int` (not a bool) or a string of decimal digits is accepted, and every float falls back to 12.
  - Recovery trusts a listing only when every row matches `%<n> <positive pid>`. A malformed listing is retried within the bound and then reported unknown. A bad pid gives unknown with zero queries.
  - Regressions: floats including inf/-inf/nan, `+5`, `1.5`, and six malformed listings. A spawn-level test confirms `bogus 999` never reaches stamping. All of these fail against the pre-fix code.
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`, `tests/test_minimonitor_scratchpad_spawn.py`

### Change Request 2 (2026-10-21 08:10)
- **Requested by user:** `launch_split_pane` stripped the whole output before splitting, so `"\t999\n"` lost its pid and returned `(None, None)`.
- **Changes made:** split the first non-blank line on the tab, then trim each field. Added the cases `"\t999\n"`, `"\n\t999\n"` and padded fields; the two empty-id cases fail against the old code.
- **Files affected:** `.aitask-scripts/lib/agent_launch_utils.py`, `tests/test_minimonitor_scratchpad_spawn.py`

## Final Implementation Notes
- **Actual work done:**
  - **`monitor_core.py` scratchpad section:**
    - constants and `scratchpad_query_args`;
    - `match_scratchpad_pane`: pure, frozen-first, matching on the store key or the target;
    - `find_scratchpad_pane_status`: fails closed;
    - `scratchpad_store_key`: runs this framework's `aitask_scratchpad_store.sh path` with `cwd=target_root`;
    - `scratchpad_command`: a task pad pins `env AITASK_SCRATCHPAD_DIR=<dirname(key)>`;
    - `scratchpad_placement`;
    - `_probe_pane`: live/gone/unknown;
    - `_recover_pad_pane`: bounded, identity-gated;
    - `_stamp_or_remove`: ok/exited/removed/stuck;
    - `spawn_scratchpad`.
  - **`agent_launch_utils.py`:** `_split_window_argv` and `_select_split_window` are shared with `launch_in_tmux`, which behaves as before. The new `launch_split_pane` returns `(pane_id, pid, err)` from `-P -F '#{pane_id}\t#{pane_pid}'`.
  - **`minimonitor_app.py`:** `Binding("o", "open_scratchpad", "Notes")`, `action_open_scratchpad`, and the `_spawn_scratchpad` adapter (companion = `TMUX_PANE`, `select_window=True`). The `o:notes` hint goes on the `e/E:shadow` line.
  - **Config:** `tmux.scratchpad_position` (top|bottom, default bottom) and `tmux.scratchpad_height` (default 12) in `TMUX_CONFIG_SCHEMA`, plus seed doc blocks.
  - **Tests:** `tests/test_minimonitor_scratchpad_spawn.py` (34 mocked tests that run the real store helper against temp roots, one of them symlinked) and `tests/test_scratchpad_spawn_live.sh` (cases A–F).
- **Deviations from plan:**
  1. `spawn_scratchpad` is imported in minimonitor straight from `monitor.monitor_core`, not through the `monitor.tmux_monitor` shim, whose docstring says new code goes in `monitor_core`.
  2. Live case D uses the `aitask_frozen.sh drop` verb, with a real sibling agent so that the drop takes the `kill-pane` branch. Without a sibling, the drop kills the whole window and the pad with it.
  3. The live test has **not been run in this session.** The session ran inside the user's live `-L ait` server, and the test's `require_clean_ait_server` guard correctly refused (exit 2). I did not override that guard. It is shellcheck-clean (`-x -P SCRIPTDIR`) and `bash -n` clean. It must be run from a terminal outside tmux with the `-L ait` server stopped.
- **Issues encountered:**
  - Every line `o:notes` could join costs one wrapped row at (15, 30): 28 → 29, exactly the budget. At 40 columns the band stays at 10 rows. The measurement script rendered each candidate with the `test_minimonitor_top_chrome_render._run` harness.
  - Three review rounds tightened the plan before implementation: the env pin, the pane id taken from the launch, and unknown ≠ gone.
- **Key decisions:**
  - Duplicate rule: one pad per store **or** per agent pane.
  - The store root is pinned on the command line, because the pad runs in the tmux server's environment and `ait` `cd`s to its own root.
  - Absence is reported only from a valid identity plus a successful, interpretable query.
  - Cleanup still runs a best-effort `kill-pane` when the probe is unknown, but reports "stuck" unless a second probe proves the pane gone.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:spawn_shadow` (~:4040-4070) — `spawn_shadow` resolves its new pane by pid (`resolve_pane_id_by_pid`), whose `None` merges "query failed" with "pane gone". A failure there leaves a live, unstamped shadow that lists as an agent. The same hole was fixed here for the scratchpad with `launch_split_pane` and identity-gated recovery.
- **Notes for sibling tasks:**
  - **For t2073_5 (docs):**
    - The key is `o`, labelled "Notes".
    - The config keys are `tmux.scratchpad_position` and `tmux.scratchpad_height`; an invalid value falls back to its default.
    - A non-task agent gets an unsaved pad plus the notification "Not a task agent — notes will not be saved".
    - Only one pad is allowed per task store, or per agent pane.
    - The editor's store root follows the minimonitor's effective `AITASK_SCRATCHPAD_DIR`, which is pinned on the command.
    - Known gap: a frozen-record drop, or `kill_agent_pane_smart`'s pane branch, leaves the pad open. The `kill_bound_helpers_on_direct_kill` follow-up fixes it.
    - The website settings reference doesn't list `shadow_pane_width` either.
  - **For whoever picks up the live test:** `tests/test_scratchpad_spawn_live.sh` must be run once outside tmux. Case E is the only end-to-end proof that the real `ait scratchpad` opens the stamped store under a differing server environment.
