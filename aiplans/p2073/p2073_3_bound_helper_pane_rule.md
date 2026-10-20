---
Task: t2073_3_bound_helper_pane_rule.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-20 15:52
---

# t2073_3 — bound_helper_pane_rule (verified 2026-10-20)

## Context

Child of t2073 (minimonitor scratchpad pane). The rule "is this pane a helper or a
real agent" is hard-coded for two markers (`@aitask_shadow_target`,
`@aitask_monitor_kind`) and repeated in Python discovery, the frozen-aware window
classifier, the bash companion-cleanup hook, and the minimonitor auto-spawn
occupancy check. The upcoming scratchpad pane (`@aitask_scratchpad_target=<agent
pane>`, spawned by t2073_4) must behave like a shadow: excluded from discovery and
snapshots, never counted as a real agent, killed when its target dies, never killed
when a sibling dies while its target lives. This child introduces **one bound-helper
rule** used by both kinds, and fixes the folded t1388 bug (minimonitor
`_find_sibling_pane_id` rung 2 is helper-blind).

Full parent design: `aiplans/p2073_minimonitor_scratchpad_pane.md`.

## Verification findings (what changed since the plan was written)

- **Step-0 coordination gate already passes.** t2065 landed (69267df56) and
  `git diff --quiet -- .aitask-scripts/monitor/minimonitor_app.py` is clean. Re-run
  the gate immediately before the rung-2 edit anyway (concurrent sessions).
- All line anchors still hold: `SHADOW_TARGET_OPTION` monitor_core.py:448,
  `FROZEN_AWARE_PANE_FORMAT`/`_FROZEN_AWARE_ARITY` :1068-1072,
  `classify_window_panes` :1087, `_LIST_PANES_FORMAT` :2527, `_LIST_PANES_ARITIES`
  :2560, `_parse_list_panes` :2562 (shadow branch :2617),
  `agent_launch_utils._companion_check_and_split` :2425-2509 (format :2467),
  cleanup job 1 :67-77 / job 2 :79-127, `_find_sibling_pane_id` minimonitor_app.py:3008.
- `_LIST_PANES_FORMAT` hard-codes `"#{@aitask_shadow_target}"` as a literal; it
  stays a literal at index 8 (positional format), the new field is appended.
- `tests/test_agent_freeze.py`'s fake `list-panes` renders any `-F` spec from the
  pane dict with `""` for missing keys, so existing fixtures survive the format change
  unedited; add one scratchpad case instead of touching every dict.
- No existing unit test drives `_companion_check_and_split` → new occupancy unit
  with a `_TMUX` stub.
- No other classifier sites: `is_live_companion_marker` / `_is_companion_pane` call
  sites are exactly the ones listed (monitor_core :1126, :2500, :2656, :3704 —
  the last is `find_companion_pane_id`, which looks for companions, not helpers).
- Out of scope (unchanged): `shadow_query_args` / `find_shadow_pane*` (shadow-only
  lookups), `monitor_app.py`, `monitor_shared.py`, `applink/router.py`,
  `shadow_agent.md`.

## Implementation steps

### 1. New `.aitask-scripts/lib/helper_panes.py` (stdlib only)
```python
SHADOW_TARGET_OPTION = "@aitask_shadow_target"          # moved from monitor_core
SCRATCHPAD_TARGET_OPTION = "@aitask_scratchpad_target"  # value = bound agent pane id
SCRATCHPAD_STORE_OPTION = "@aitask_scratchpad_store"    # canonical abs store dir; "" for unsaved
BOUND_HELPER_TARGET_OPTIONS = (SHADOW_TARGET_OPTION, SCRATCHPAD_TARGET_OPTION)

def is_bound_helper(*targets: str) -> bool:
    return any(t.strip() for t in targets)
```
Module docstring: the bound-helper rule (helper excluded from discovery/snapshots,
never a real agent, killed with its target, not with a sibling), the bash copy in
`aitask_companion_cleanup.sh` kept in step by `test_cleanup_rule_parity.sh` + the
option tripwire, and why it lives in lib (both `monitor_core` and
`agent_launch_utils` consume it; lib→TUI imports banned).

`monitor_core.py`: replace the `SHADOW_TARGET_OPTION = ...` assignment (keep the
explanatory comment) with `from helper_panes import (SHADOW_TARGET_OPTION,
SCRATCHPAD_TARGET_OPTION, SCRATCHPAD_STORE_OPTION, BOUND_HELPER_TARGET_OPTIONS,
is_bound_helper)  # noqa: F401  (re-export)`, placed with the other lib imports
(~:59). `tmux_monitor.py`: add the four new names to the re-export list next to
`SHADOW_TARGET_OPTION` (t2073_4 imports via that shim).

### 2. Frozen-aware classifier (`monitor_core.py` ~:1068-1131)
- `FROZEN_AWARE_PANE_FORMAT`: append `f"#{{{SCRATCHPAD_TARGET_OPTION}}}"` as the
  last field; `_FROZEN_AWARE_ARITY = 7`.
- `classify_window_panes`: unpack `..., dead, scratch_target = parts`; the
  `is_helper` clause becomes `not frozen.strip() and (is_bound_helper(shadow_target,
  scratch_target) or is_live_companion_marker(monitor_kind) or
  _is_companion_process(pid))`. Frozen-first rule unchanged. Update docstring
  ("a shadow or scratchpad bound to an agent").
- Covers `kill_agent_pane_smart` and `agent_freeze._other_real_agents`.

### 3. Discovery (`monitor_core.py` ~:2527-2680)
- `_LIST_PANES_FORMAT`: append `f"#{{{SCRATCHPAD_TARGET_OPTION}}}"` (index 15) with
  an "APPENDED, never inserted" comment (t2073_3).
- `_LIST_PANES_ARITIES = (9, 10, 11, 15, 16)` in the same change; update its
  docstring (16 = current).
- `_parse_list_panes` — **the frozen-first rule applies to discovery too**, exactly
  as in `classify_window_panes`: a `@aitask_frozen` stand-in is never a helper, so
  none of the helper branches may fire on it. After `seen.add(pane_id)`:
  ```python
  scratch_target = parts[15].strip() if len(parts) > 15 else ""
  if not frozen_record:
      if scratch_target:
          continue   # scratchpad helper: dropped entirely, NEVER routed into `shadows`
      if is_shadow_target(parts[8]):
          ...existing shadow branch (unchanged body)...
  category = self.classify_pane(window_name)
  if not frozen_record and self._is_companion_pane(...):
      continue
  ```
  - Ordinary scratchpads (no `@aitask_frozen`) are still dropped entirely, and never
    routed into `shadows` (where `commit_snapshots` would make them compete with the
    real shadow).
  - A frozen stand-in carrying a retained scratchpad target / shadow target / live
    companion marker is listed as an ordinary agent-facing pane and enters
    `_pane_cache` / `_snapshots`. Without this, discovery omits it,
    `_find_own_window_snapshot` resolves a LATER agent in the window, and
    `_find_sibling_pane_id` returns that agent from rung 1 without ever reaching the
    corrected rung 2.
  - Extending the gate to the pre-existing shadow and companion branches (not only
    the new scratchpad exclusion) is deliberate: the goal is one helper rule, and a
    discovery that is frozen-first for one marker but not the others would
    disagree with `classify_window_panes` on the same pane. The frozen stand-in
    viewer stamps no `@aitask_monitor_kind` itself (`MONITOR_KINDS` =
    minimonitor/monitor), so the gate cannot surface a real companion.
  - Update the method docstring (helper set + frozen precedence).

### 4. Occupancy check (`lib/agent_launch_utils._companion_check_and_split`)
- `from helper_panes import BOUND_HELPER_TARGET_OPTIONS, is_bound_helper`.
- Format: `#{pane_id}|#{monitor_kind}|` + `"|".join(f"#{{{o}}}" for o in
  BOUND_HELPER_TARGET_OPTIONS)` + `|#{@aitask_frozen}|#{pane_dead}|#{pane_start_command}`
  (`pane_start_command` stays LAST).
- Parse: partition the helper targets in a loop over the tuple into a list;
  `if not is_bound_helper(*targets): real_panes += 1`. Update the comment
  ("Bound helper panes (shadow t986, scratchpad t2073) … must NOT count").

### 5. `aitask_companion_cleanup.sh`
- Job 1: `-F '#{pane_id}|#{@aitask_frozen}|#{@aitask_shadow_target}|#{@aitask_scratchpad_target}'`,
  `read -r pane pfrozen target scratch`; skip `[ -n "$pfrozen" ]` FIRST (frozen-first
  rule: a stand-in is never a helper, so a retained helper target on it must not get
  it killed — today's shadow-only job 1 lacks this guard too), then kill when
  `[ "$target" = "$primary" ] || [ "$scratch" = "$primary" ]`. Rename comment
  "Kill bound helper panes (shadow, scratchpad)…". Helper targets stay the LAST
  fields so the tripwire sees them in the `-F` string.
- Job 2: append `|#{@aitask_scratchpad_target}` → `read -r pane target kind frozen
  scratch`; replace `[ -n "$target" ] && continue  # shadow helper` with
  `{ [ -n "$target" ] || [ -n "$scratch" ]; } && continue   # bound helper`.
- Keep the literal `if [ -n "$frozen" ]; then` (the parity negative control seds it).
- `shellcheck` clean; raw tmux stays allowed here only.

### 6. Rung 2 of `minimonitor_app._find_sibling_pane_id` (t1388) — re-run Step-0 gate first
- Gate: `git diff --quiet -- .aitask-scripts/monitor/minimonitor_app.py` and t2065
  in `git log`; if it fails, stop and ask the user.
- **Reuse the one classifier — no third copy of the rule.** Rung 2 lists
  `["list-panes", "-t", self._own_window_id, "-F", FROZEN_AWARE_PANE_FORMAT]` and
  runs the output (unstripped) through `classify_window_panes`, then returns the
  first `WindowPane` with `pane_id != own_pane and not is_helper`. That inherits,
  with no local re-derivation:
  - the bound-helper rule (shadow + scratchpad, step 2);
  - the companion two-rung identity (live `@aitask_monitor_kind` marker, then
    cmdline);
  - **the frozen-first precedence**: a `@aitask_frozen` stand-in is never a
    helper, even when a retained `@aitask_monitor_kind` / helper-target marker
    from whatever ran in the pane before the respawn would otherwise classify it
    as one (the `frozen_marked` shape `test_cleanup_rule_parity.sh` already
    models). An ad-hoc rung-2 filter without the frozen field would skip that
    stand-in, report "no pane", or send Enter to a later agent.
  - the "no `stdout.strip()`" handling of an empty trailing field.
  Dead panes are not filtered (the pre-fix rung did not filter them either; they are
  real occupants under the shared rule).
- **Decision (t1388 AC):** companions ARE filtered (via the shared classifier), so a
  second minimonitor is never chosen. Recorded in the docstring.
- Docstring: the t986 guarantee ("a shadow, scratchpad or other helper pane is never
  mistaken for the agent") now holds for both rungs, and rung 2 is a call site of
  `classify_window_panes`, so it agrees with `kill_agent_pane_smart`,
  `agent_freeze._other_real_agents` and the cleanup hook by construction. The
  "No other pane in this window" notify becomes "No agent pane in this window".
- Imports: `FROZEN_AWARE_PANE_FORMAT`, `classify_window_panes` from
  `monitor.monitor_core` (existing import block). This also makes
  `tui_conventions.md` / the `classify_window_panes` docstring list rung 2 as a
  fourth call site.

### 7. Tests
- `tests/test_cleanup_rule_parity.sh`:
  - `build_window` role `scratchpad)` → `stamp "$pane" @aitask_scratchpad_target "$first"`; header role list updated.
  - Rows: `agent + scratchpad + companion` → window (0);
    `agent + agent + scratchpad + companion` dying 1 → pane.
  - New block "bound helpers: job 1": window `agent agent scratchpad companion`;
    dying `ids[1]` (scratchpad bound to the survivor) → assert scratchpad id NOT in
    `$KILL_LOG`; dying `ids[0]` → assert scratchpad id IS in `$KILL_LOG` (job 1).
  - Tripwire: for every option printed by Python `BOUND_HELPER_TARGET_OPTIONS`,
    assert it appears in both `-F` formats of the cleanup script (job 1 and job 2
    lines).
- `tests/test_list_panes_arity_characterization.py`: `CURRENT_ARITY = 16`, extend
  arity expectations; a scratchpad-marked row is excluded from both returned lists;
  a `frozen + scratchpad`, a `frozen + shadow` and a `frozen + live companion marker`
  row each land in the agent-facing list (not `shadows`, not dropped) with
  `frozen_record` set; a non-frozen shadow row still lands in `shadows`.
- `tests/test_monitor_companion_filter.py`: `_line` values dict gains the scratchpad
  key (built from the format); new case "scratchpad-bound pane is a helper".
- `tests/test_agent_freeze.py`: one case — a scratchpad pane bound to the stand-in is
  not a real sibling (drop escalates to the window rule exactly as for a shadow).
- `tests/test_multi_agent_window_substrate.sh`: `is_bound_helper` units (no args,
  all empty/whitespace → False; either target set → True).
- NEW `tests/test_helper_panes.py`: identity
  (`monitor_core.BOUND_HELPER_TARGET_OPTIONS is helper_panes.BOUND_HELPER_TARGET_OPTIONS`,
  same for `tmux_monitor`); every option in the tuple appears in
  `FROZEN_AWARE_PANE_FORMAT` and in the format `_companion_check_and_split` sends
  (captured via a `_TMUX` stub); occupancy unit: `[agent, agent, scratchpad]` does not
  hit the 3-real-pane refusal (split attempted) while `[agent, agent, agent]` does.
- NEW `tests/test_minimonitor_sibling_fallback.py` (t1388): `MiniMonitorApp.__new__`,
  `_find_own_window_snapshot` forced to `None`, `TMUX_PANE` = minimonitor pane, a
  format-driven tmux stub rendering the requested `-F` from a pane model:
  `[minimonitor, shadow, agent]` and `[minimonitor, scratchpad, agent]` → agent id;
  `[minimonitor, minimonitor2(marker), agent]` → agent id; helpers only → None;
  the agent as the LAST record with every trailing field empty → still found.
  **Frozen precedence** (with `monitor_marker_alive` / `_is_companion_process`
  patched so the retained marker reads as LIVE):
  `[minimonitor, frozen + live @aitask_monitor_kind, agent]` and
  `[minimonitor, frozen + @aitask_scratchpad_target, agent]` → the **frozen** pane
  id (first non-helper), not the later agent and not None.
  Negative controls: (a) the pre-fix rule (first non-self pane id) on the
  shadow/scratchpad fixtures returns the helper; (b) a frozen-blind filter (the same
  rule with the `@aitask_frozen` field blanked in the stub) on the frozen fixtures
  returns the later agent — proving both fixtures discriminate.
  **Discovery → rung-1 navigation** (no forced fallback): feed a real
  `TmuxMonitor._parse_list_panes` (`exclude_pane` = the minimonitor pane) a 16-field
  stdout for `[minimonitor, frozen + scratchpad target, agent]` in one `agent-*`
  window; build `_snapshots` from the returned agent-facing panes in discovery order;
  call the real `_find_sibling_pane_id` with the real `_find_own_window_snapshot` →
  the **frozen** pane id. Companion case: `[minimonitor, plain scratchpad, agent]`
  through the same path → agent id (ordinary scratchpads still excluded). Negative
  control: the same pipeline with the frozen field blanked returns the later agent.
- `tests/test_cleanup_rule_parity.sh` also gets a `frozen + scratchpad` role variant
  row (`agent + frozen_scratch + companion` dying 0 → pane; `frozen_scratch` =
  `@aitask_frozen` + `@aitask_scratchpad_target=$first`), pinning that a frozen
  stand-in carrying a retained scratchpad target is still a real sibling in bash and
  Python alike, plus an assertion that job 1 did NOT kill it (its id absent from
  `$KILL_LOG`).

### 8. aidocs
- `aidocs/framework/tmux_gateway.md` option inventory (after the
  `@aitask_monitor_kind` row, ~:192): rows for `@aitask_scratchpad_target` (set by
  the scratchpad spawn to the followed agent's pane id; cleared on pane death; read
  by agent-list filters, frozen-aware classifier, occupancy check, companion
  cleanup; "this pane is a scratchpad bound to that agent") and
  `@aitask_scratchpad_store` (canonical store dir; read by the one-per-store
  duplicate lookup). Note the one-place definition in `lib/helper_panes.py`.
- `aidocs/framework/tui_conventions.md` companion sections (~:747-924): replace the
  "two-marker shape" wording with the bound-helper rule (`BOUND_HELPER_TARGET_OPTIONS`
  + `is_bound_helper`, every consumer listed), and add a "The scratchpad is a fourth
  companion-pane case" subsection after the frozen stand-in one; mention rung 2 of
  `_find_sibling_pane_id` as a consumer.

## Verification
- `bash tests/test_cleanup_rule_parity.sh` (outside tmux, `-L ait` stopped)
- `python3 tests/test_helper_panes.py`, `python3 tests/test_minimonitor_sibling_fallback.py`,
  `python3 tests/test_list_panes_arity_characterization.py`,
  `python3 tests/test_monitor_companion_filter.py`, `python3 tests/test_agent_freeze.py`
- `bash tests/test_multi_agent_window_substrate.sh`, `bash tests/test_no_lib_to_tui_import.sh`,
  `bash tests/test_no_raw_tmux.sh`, `bash tests/test_companion_cleanup_ordering.sh`
- `shellcheck .aitask-scripts/aitask_companion_cleanup.sh`
- Full Python suite `bash tests/run_all_python_tests.sh` — read the last line.

## Step 9 (Post-Implementation)
Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: medium
- The helper rule changes discovery, `classify_window_panes`, the cleanup hook and the occupancy check together; a missed copy or an un-widened arity set silently drops every pane or keeps the minimonitor alive · severity: medium · → mitigation: none — covered in-plan by step 7 (parity table + job-1 block, arity characterization, bash/Python option tripwire, identity test)
- Rung 2 now reads more fields; a whole-buffer strip or wrong arity would make `tab`/`enter` report "no pane" · severity: low · → mitigation: none — covered in-plan by the t1388 test (last-record-unmarked fixture + negative control)

### Goal-achievement risk: low
None identified.
