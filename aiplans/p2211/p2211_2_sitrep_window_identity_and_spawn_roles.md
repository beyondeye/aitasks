---
Task: t2211_2_sitrep_window_identity_and_spawn_roles.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md, aitasks/t2211/t2211_7_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-07 22:25
---

# t2211_2 — Window identity + four-way spawn roles (verified 2026-11-07)

## Context

`ait sitrep` opens one `agent-sitrep` window: the sitrep agent plus a forced
minimonitor companion. t2211_1 shipped the sitrep TUI (`ait sitrep tui --root R`,
exit 2 = bad `--root`, exit 1 + `ROOT_FAILED:` = unresolvable root; the app sets
nothing on tmux). This child puts the TUI into the window as a second **role**:
its own stamp, one per root for both roles, four-way spawn/repair under the
existing lock, and the agreed layout:

```
+----------------+------+
| sitrep agent   | mini |
+----------------+ mon  |
| sitrep TUI 40% |      |
+----------------+------+
```

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`.

## Verification findings (premises re-derived against HEAD)

- **Gate met.** t2037_2 is archived (landed `3594c2798`); `git status` shows no
  hunks in `monitor_core.py`, `status_client.py`, `sitrep_close.py`,
  `agent_launch_utils.py`, `helper_panes.py`, `minimonitor_app.py`,
  `agent_freeze.py`, `aitask_companion_cleanup.sh`. Re-check `git diff HEAD --`
  on these right before the first edit (other sessions are active).
- Current line numbers (monitor_core.py): `FROZEN_AWARE_PANE_FORMAT` L1107
  (7 fields, `_FROZEN_AWARE_ARITY` L1112), `pane_is_helper` L1128,
  `classify_window_panes` L1147, `_LIST_PANES_FORMAT` L2801 (16 fields,
  `_LIST_PANES_ARITIES=(9,10,11,15,16)` L2838), `_parse_list_panes` L2840,
  `_collapse_window_for` L4125, `_stamp_or_remove` L4421, sitrep section
  L4939-5163, `RunIdentity` L5211 / `RUN_IDENTITY_FORMAT` L5229.
  agent_launch_utils.py: `TmuxLaunchConfig` L96 (`split_size: int|None`),
  `_split_window_argv` L2171, `launch_split_pane` L2205,
  `attach_companion_cleanup_hook` L2402, `_scan_companion_window` L2587,
  `_companion_check_and_split` L2679, `maybe_spawn_minimonitor` L2745.
  minimonitor_app.py: `_check_auto_close` L2226, `_find_sibling_pane_id` L3819.
- **Status client:** `MonitorClient` delegates `tmux_run`, `discover_window_panes*`
  to the local monitor; snapshots come from the server's `TmuxMonitor` producer,
  which runs the same `_parse_list_panes`. So every fix below covers both routes.
  Caveat: a status server started before this change keeps listing the TUI until
  it restarts — the `h` boundary guard (step 3d) still refuses it.
- The TUI's cmdline (`…/sitrep_tui/sitrep_tui_app.py`) never matches
  `_COMPANION_KEYWORDS` (`minimonitor`, `monitor_app`); its start command is not
  `ait minimonitor`. So the TUI is already a **real occupant** everywhere the
  retention rule runs.
- All three `S` decoders (monitor, minimonitor, switcher `_open_sitrep_async`)
  go through `sitrep_cli.sitrep_open_message` — one change covers them.
- (review round 1) `minimonitor_app._find_own_agent_snapshot` (~L2463) follows
  the FIRST AGENT snapshot among its window's members in pane-index order, and
  discovery keeps frozen stand-ins. So a replacement split under a frozen agent
  would be shadowed by it — hence the empty-slot rule in step 5.
- (review round 1) `_split_window_argv` (L2171) never emits `-d`;
  `select_window=False` only skips the later `select-window`. A split therefore
  activates its new pane — hence `split_detached` in step 5.

### Consumer table (stamp read path per row; frozen-first everywhere)

| consumer | required | today (prediction) | how it reads the stamp after this change |
|---|---|---|---|
| discovery `_parse_list_panes` (monitor/minimonitor cards, `_pane_cache`, applink) | not an agent | RED — listed as AGENT (window `agent-sitrep`) | new 17th `_LIST_PANES_FORMAT` field; non-frozen + stamp → dropped like a scratchpad |
| `match_sitrep_pane` fallback | not an agent | RED — unstamped-for-agent, sitrep window, cwd=root | new 8th `FROZEN_AWARE_PANE_FORMAT` field via `SITREP_PANE_FORMAT`; skipped in both passes |
| minimonitor `_find_sibling_pane_id` rung 2 | not an agent | RED — returned when the agent is gone / listed first | `WindowPane.is_sitrep_tui` from `classify_window_panes` |
| `h` harvest-and-close | refuse | RED — `is_sitrep_window` → `skipped("sitrep_agent")` → close offered | `RUN_IDENTITY_FORMAT` 5th field; `_harvest_for_close` fails `not_an_agent` |
| `_scan_companion_window` | real occupant, not "present" | green | unchanged (no read) — pinned |
| cleanup job 2 (`aitask_companion_cleanup.sh`) | real occupant | green | unchanged (no read) — pinned by a parity row |
| `kill_agent_pane_smart` / `_collapse_window_for` / `count_other_real_agents` | real occupant | green | `is_helper` unchanged — pinned |
| `agent_freeze._other_real_agents` | real occupant | green | `is_helper` unchanged — pinned (unit + parity coordinator) |
| minimonitor `_check_auto_close` | company (not alone) | green | raw `_WINDOW_PANES_FORMAT` count — pinned |

"Two predicates": `is_helper` (retention) is NOT changed; the new
`is_sitrep_tui` is consulted by the four listing consumers only. The cleanup
script's `-F` formats are not built from `FROZEN_AWARE_PANE_FORMAT` and job 2
needs no stamp, so they stay unchanged; the parity test gains a TUI row instead.

### Pre-phase (risk mitigations)

1. [sitrep_tui_consumer_table_characterization] Before any production edit, add
   `ConsumerTableTests` to `tests/test_sitrep_window.py` (literal option name
   `"@aitask_sitrep_tui_root"`, format-driven fakes so the rows follow the
   requested `-F`), one test per row of the table above, each with a TUI pane
   stamped for `/repo`:
   - discovery: `TmuxMonitor.__new__`-built monitor (or a real one with no tmux
     calls) → `_parse_list_panes(render(_LIST_PANES_FORMAT, rows), "s")` — the
     TUI pane is absent from the result and from `_pane_cache`;
   - matcher: agent gone, TUI unstamped-for-agent in `agent-sitrep` with cwd=root
     → `match_sitrep_pane` is `None`;
   - rung 2: the `test_minimonitor_sibling_fallback` pattern
     (`MiniMonitorApp.__new__`, `_find_own_window_snapshot = lambda: None`,
     `TMUX_PANE` patched) with `[minimonitor, TUI]` → `None`, and
     `[minimonitor, TUI, agent]` → agent;
   - `h`: `SitrepCloseMixin._harvest_for_close` (the
     `test_monitor_sitrep_harvest_close` harness) on a TUI snapshot whose
     identity read carries the stamp → `failed("not_an_agent")`, harvest script
     never run;
   - `_scan_companion_window` on `_companion_pane_format()` rows `[agent, TUI]` →
     `present False, real_panes 2`;
   - `classify_window_panes` → TUI `is_helper False`;
     `count_other_real_agents(..., agent)` → 1;
   - `agent_freeze._other_real_agents` through its gateway seam with a
     format-driven fake → 1;
   - `_check_auto_close`: fake monitor whose `discover_window_panes_async`
     returns `[minimonitor, TUI]` → `exit` never called, streak 0.
   Also add the parity row (step 9). Run them; record the red ones in the Final
   Implementation Notes (expected: discovery, matcher, rung 2, `h`). All green at
   the end.
2. [arity_fixture_sweep] Before editing any format, grep `.aitask-scripts/` and
   `tests/` for every reader or fake that fixes the field count of
   `FROZEN_AWARE_PANE_FORMAT`, `_LIST_PANES_FORMAT` or `RUN_IDENTITY_FORMAT`:
   `len(parts) != …` / `len(p) != …` guards, tuple unpacking of a split row,
   hand-built tab-joined rows and f-string lines (`ident_line`), shell `-F`
   copies, and literal arity constants (`CURRENT_ARITY`). Format-driven fakes
   (render from the requested `-F`) are fine and only need the new spec key where
   a test asserts on it. Record the inventory (file:line → action) in the Final
   Implementation Notes and fix every hit in the same change as the format edit.
   Done when a re-grep finds no unconverted hit and the arity tests pass.
3. [layout_geometry_spike] Before writing the spawn code, on an isolated tmux
   server (`tests/lib/tmux_isolation.sh`, own `-L` socket, `new-session -d -x 200
   -y 50`) with `tail -f /dev/null` panes, run the exact planned argv for: (a)
   cold — `new-window -d`, `split-window -d -v -l 40% -t A`, `split-window -h
   -f -l 40 -t A`; (b) add-TUI — `new-window -d`, `split-window -h -f -l 40 -t
   A`, then `split-window -d -v -l 40% -t A`; (c) respawn — window with `T` +
   full-height minimonitor, `split-window -d -v -b -l 60% -t T`; (d) respawn, no
   companion — `T` alone, `split-window -d -v -b -l 60% -t T`, then
   `split-window -h -f -l 40 -t A`; (e) relocate — window with frozen-stamped
   `F` over `T` + full-height minimonitor, `new-window -d` with `A`, `join-pane
   -d -v -l 40% -s T -t A`, then `split-window -h -f -l 40 -t A` (read `T`'s
   `@aitask_sitrep_tui_root` after the join). Read the step-12 coordinate
   format plus `#{pane_active}` after each and check the step-12 invariants and
   that the `-d` steps left the active pane unchanged. Record the measured
   tables in the Final Implementation Notes; if any invariant fails, change the
   split flags/sizes in steps 5–6 first (and say so in the notes). The
   implementation then uses these exact argv.

## Main steps

2. **Stamp + predicate** (`lib/helper_panes.py`): `SITREP_TUI_ROOT_OPTION =
   "@aitask_sitrep_tui_root"` beside `SITREP_ROOT_OPTION` (named for clarity over
   the task's `TUI_ROOT_OPTION` — `monitor_core` already has a TUI category).
   Docstring: identity, set by `spawn_sitrep`; NOT a helper marker (absent from
   `BOUND_HELPER_TARGET_OPTIONS`; the pane is a real occupant), but excluded from
   agent listings. Add `is_sitrep_tui_pane(frozen: str, tui_root: str) -> bool`
   = `not frozen.strip() and bool(tui_root.strip())` (frozen-first). Re-export
   both from `monitor_core` (the existing import block, L75).
3. **Listing exclusion** (`monitor/monitor_core.py`):
   a. `FROZEN_AWARE_PANE_FORMAT` APPENDS `#{@aitask_sitrep_tui_root}`;
      `_FROZEN_AWARE_ARITY = 8`; `WindowPane.is_sitrep_tui: bool = False`;
      `classify_window_panes` unpacks 8 fields and sets
      `is_sitrep_tui=is_sitrep_tui_pane(frozen, tui)`; `is_helper` untouched.
      Update the docstring/comment that names the field list.
   b. `SITREP_PANE_FORMAT` (built from a.) gets the TUI field for free;
      `_SITREP_SPLIT` stays `_FROZEN_AWARE_ARITY + 2`; `match_sitrep_pane`
      unpacks the extra field and `continue`s on `is_sitrep_tui_pane` right after
      the frozen/dead skip (both passes).
   c. `_LIST_PANES_FORMAT` APPENDS the stamp as field 17; `_LIST_PANES_ARITIES`
      gains 17; `_parse_list_panes` reads `parts[16]` guarded by `len(parts) > 16`
      and drops a non-frozen stamped pane entirely (same place and shape as the
      scratchpad drop). Update `tests/test_list_panes_arity_characterization.py`
      `CURRENT_ARITY` 16 → 17 in the same change.
   d. `RUN_IDENTITY_FORMAT` APPENDS the stamp; `RunIdentity.sitrep_tui_root: str
      = ""` (defaulted, last); `parse_run_identity` requires 5 fields. In
      `sitrep_close._harvest_for_close`, right after `before` is read: a
      non-frozen identity with a TUI stamp → `HarvestReport.failed(
      "not_an_agent")` (nothing captured, nothing closed). Update
      `ident_line` in `tests/test_monitor_sitrep_harvest_close.py` to emit 5
      fields. `kill_agent_run_guarded` stays pane-only and unchanged.
   e. `minimonitor_app._find_sibling_pane_id` rung 2 skips
      `pane.is_helper or pane.is_sitrep_tui`; extend its docstring. Retention
      callers (`_collapse_window_for`, `agent_freeze._other_real_agents`) keep
      reading `is_helper` only.
4. **`find_sitrep_roles(monitor, root, canon=None) -> (ok, agent, tui)`**: one
   `sitrep_query_args()` read (rc≠0 → `(False, None, None)`); agent =
   `match_sitrep_pane(...)`; tui = new pure `match_sitrep_tui_pane(out, root)`:
   first row with a valid `%N`, not frozen, not dead, TUI stamp == root, in any
   window. `find_sitrep_pane_status` becomes a thin wrapper over it (contract
   kept).
5. **Four-way `spawn_sitrep`** under `_sitrep_spawn_lock`:
   - `sitrep_tui_command(root) -> str` = `"ait sitrep tui --root " +
     shlex.quote(root)` (module function, patchable like
     `resolve_dry_run_command` / `scratchpad_command`).
   - `TmuxLaunchConfig.split_size` widens to `int | str | None` (percent
     strings; argv is already `str(...)`), and a new `split_detached: bool =
     False` makes `_split_window_argv` add tmux `-d` (the new pane does not
     become active). Both default to today's argv for every other caller —
     pinned by an argv test of an unchanged caller.
   - Helper `_pane_place(monitor, pane) -> Place(session, window_id,
     window_index, window_name) | None`: one `display-message -p -t <pane>
     '#{session_name}\t#{window_id}\t#{window_index}\t#{window_name}'`, all four
     non-empty, else None (→ `refused place_unreadable`).
   - Helper `_split_role(monitor, command, anchor, place, *, before, size, root,
     option)`: `launch_split_pane(command, TmuxLaunchConfig(place.session,
     place.window_name, False, False, split_direction="vertical",
     split_before=before, split_size=size, split_target_pane=anchor, cwd=root,
     select_window=False, split_detached=True))`, `_recover_launched_pane` on a
     missing id, `_stamp_or_remove(monitor, pane, option, root)`; returns
     `(pane, why)` with why in `launch:<err>|launch:exited|launch:unclassified|
     stamp:<outcome>`. **Every role split is detached**, so no split ever moves
     the window's active pane.
   - **In-place respawn needs an empty agent slot.** For a live TUI with no live
     agent, read the TUI's window once (`list-panes -t <tui> -F
     FROZEN_AWARE_PANE_FORMAT` → `classify_window_panes`; rc≠0 →
     `refused lookup_failed`). Occupants = panes that are not the TUI, not
     `is_helper` and not `is_sitrep_tui`. A frozen stand-in (the frozen sitrep
     agent, kept by frozen-first), a dead pane or a user's shell is an occupant.
     - **no occupant** → respawn in place (`respawned_agent`).
     - **any occupant** → **relocate**: the frozen session and the TUI's window
       are left alone except that the TUI moves out. Launch a fresh
       `agent-sitrep[-n]` window with the agent exactly as the cold path
       (stamped), then `join-pane -d -v -l 40% -s <tui> -t <agent>` — the TUI
       pane (process, scrollback and both stamps travel with it) lands under the
       new agent; `-d` keeps the active pane. Status `spawned`, detail item
       `tui_moved`, `SitrepSpawn.tui` = the moved pane. A failed join →
       warning `tui_not_moved` (the TUI stays where it was: still one live TUI
       per root, never a second). This keeps the t2175_4 rule "a frozen sitrep
       never blocks a new one", and each window then holds exactly one
       agent-listed pane — the old one the frozen stand-in, the new one the new
       agent — so each window's minimonitor (`_find_own_agent_snapshot`, first
       AGENT member in pane-index order) follows the intended agent. The old
       window keeps its frozen stand-in + companion (a frozen sibling is a real
       occupant for cleanup and auto-close).
   - **Focus preservation (repairs).** On `added_tui` / `respawned_agent`,
     before the first mutation read the anchor window's active pane
     (`display-message -p -t <place.window_id> '#{pane_id}'`). After the
     companion step (outside the lock):
     - `select_window=True` → `switch_to_pane_anywhere(agent)`; failure →
       warning `focus_failed`;
     - `select_window=False` → re-read the active pane; if it changed (the
       companion split and `maybe_spawn_minimonitor`'s refocus are the only
       remaining movers) and the original is still in that window,
       `select-pane -t <original>`. A failed restore → warning
       `focus_not_restored`.
     The cold and relocate paths create a new window (`new-window -d` under
     no-select, as today) whose active pane is the agent.
   - Flow after `find_sitrep_roles` (`ok=False` → `refused lookup_failed`):
     | agent | tui | action | status |
     |---|---|---|---|
     | yes | yes | today's focus | `focused` / `focus_failed` |
     | — | — | `spawn_test_pause("spawn:after_lookup")`; today's agent window + stamp; then `_split_role(tui_cmd, agent, before=False, size="40%", SITREP_TUI_ROOT_OPTION)`; a TUI failure is a warning `tui_not_spawned:<why>` (agent stands) | `spawned` |
     | yes | — | pause; `_split_role(tui_cmd, agent, before=False, "40%")`; failure → `refused tui:<why>` | `added_tui` |
     | — | yes, slot empty | pause; `resolve_dry_run_command`; `_split_role(agent_cmd, tui, before=True, "60%", SITREP_ROOT_OPTION)`; failure → `refused <why>` as today | `respawned_agent` |
     | — | yes, slot occupied | pause; cold agent window + stamp; `join-pane -d -v -l 40% -s <tui> -t <agent>` | `spawned` (+ `tui_moved` / `tui_not_moved`) |
   - `SitrepSpawn` gains `tui: str | None = None` (defaulted; existing positional
     constructions keep working); `pane` stays the agent pane on every status;
     `window` = `<session>:<window_name>` from `_pane_place` for the new paths;
     `detail` = comma-joined warnings.
   - Outside the lock, on `spawned` (cold and relocate) / `added_tui` /
     `respawned_agent`: `maybe_spawn_minimonitor(place.session,
     place.window_name, window_index=place.window_index, agent_pane=agent,
     project_root=root, explicit=True, force_companion=True,
     full_height=True)` with `place` = the agent's window. `None` → the window
     already has its companion (or a gate refused): on `respawned_agent` look the
     companion up (`window_companion_pane(agent)`, step 6) and
     `attach_companion_cleanup_hook(agent, it)`; no companion found → warning
     `companion_not_spawned` (no hook; the agent pane then closes normally on
     exit). On `spawned` keep today's `companion_not_spawned`. Then the focus
     step above.
6. **Geometry** (`lib/agent_launch_utils.py`): keyword-only `full_height: bool =
   False` on `maybe_spawn_minimonitor` → `_companion_check_and_split`, which
   inserts `-f` after `-h` only when set. `_CompanionScan` gains
   `companion_panes: tuple[str, ...]` (live-marked or booting) and a read-only
   `window_companion_pane(pane) -> str | None` reuses `_companion_pane_format` +
   the scan. Argv pin: an existing `_companion_check_and_split` caller gets
   exactly today's argv (`split-window -h -P -F #{pane_id} -l <w> [-c] -t <p> ait
   minimonitor`) and `full_height=True` adds only `-f`.
7. **Wire lines.** `sitrep_open.py`: `added_tui` → `SITREP_ADDED_TUI:<agent>|<s>:<w>`,
   `respawned_agent` → `SITREP_RESPAWNED_AGENT:<agent>|<s>:<w>`, both exit 0;
   one `SITREP_WARN:<item>` line per comma-separated detail item on every exit-0
   status that carries one. `sitrep_cli.sitrep_open_message`: "Sitrep TUI added
   to the sitrep window" / "Sitrep agent restarted beside its TUI"; all warnings
   joined `", "`. Update the wire-line lists in the `sitrep_open.py` docstring
   and the `aitask_sitrep.sh` header.
8. **Agent exit** is already right (TUI = real sibling for job 2; company for
   `_check_auto_close`): pinned by the consumer rows, the parity row and live
   scenario K.
9. **Parity** (`tests/test_cleanup_rule_parity.sh`): role `sitrep_tui` (stamp
   `@aitask_sitrep_tui_root /repo`), rows `agent + sitrep_tui + companion` →
   `pane` and `sitrep_tui + agent + companion, agent dies` → `pane`.
10. **Docs.** `aidocs/framework/tmux_gateway.md` option inventory: a
    `@aitask_sitrep_tui_root` row. `aidocs/framework/sitrep.md` "The sitrep
    window": the two roles, the four-way table, the empty-slot rule and the
    frozen-agent relocation (frozen session preserved, the TUI moves, one TUI per
    root, one agent-listed pane per window), the no-select focus rule, the two
    predicates, the new wire lines, layout and agent-exit behaviour (website
    pages stay with t2211_6).
11. **Unit tests** (`tests/test_sitrep_window.py`, `FakeMon` extended:
    `display-message` answers the place format, `split-window` records argv and
    returns `%N\t<pid>`, `_SPEC_KEYS` gains the TUI key): matcher rows with a
    TUI pane; `find_sitrep_roles` (failed query, TUI in another window, frozen /
    dead TUI ignored, TUI for another root ignored); the four-way table incl.
    each failure branch and warnings; the in-place-vs-relocate decision for a
    frozen stand-in, a dead pane, a shell and an empty slot; the relocate
    `join-pane -d` argv and its `tui_not_moved` branch; `-d` on every role
    split; the no-select restore (`select-pane -t <original>` issued only when
    the active pane changed, never under `select_window=True`, which calls
    `switch_to_pane_anywhere(agent)` instead) and `focus_not_restored`;
    `full_height` only from `spawn_sitrep`;
    `OpenCliTests` for the two new lines + multi-warn; `sitrep_open_message`.
12. **Live tests** (`tests/test_sitrep_window_live.sh`; driver also patches
    `mc.sitrep_tui_command` → `tail -f /dev/null`; session created `-x 200 -y 50`).
    A–G keep their assertions (A now expects 3 panes); H is rewritten below.
    The driver runs `select_window=False`, so every repair scenario is a
    no-select repair. A `discovery_view` helper runs `TmuxMonitor(session)
    .discover_panes()` against the isolated server and prints, per window, the
    agent-listed pane ids — the exact input of each window's minimonitor
    `_find_own_agent_snapshot`. New:
    - I cold start → coordinates (one `list-panes -F '#{pane_id} #{pane_left}
      #{pane_top} #{pane_width} #{pane_height} #{window_width} #{window_height}
      #{pane_active}'` read): agent `0,0`; TUI `left 0`, `top =
      agent.top+agent.height+1`, `width = agent.width`; minimonitor `left =
      agent.width+1`, `top 0`, `height = window_height`; `agent.h + TUI.h + 1 =
      window_height`; the agent is active; discovery lists only the agent.
    - J agent-only (kill the TUI; `select-pane -t <minimonitor>` first so a
      moved focus is observable) → `added_tui`, same coordinates, the
      minimonitor is still the active pane.
    - K agent exits with the real cleanup hook (the live hook is NOT stubbed in
      this scenario) → TUI + minimonitor remain, agent pane gone.
    - L TUI-only with companion (`select-pane -t <minimonitor>` first) →
      `respawned_agent`, coordinates, the minimonitor is still active, the new
      agent has a `pane-died` hook invoking the cleanup script, discovery lists
      only the new agent.
    - M TUI-only, companion gone (the TUI is then the window's only, active pane)
      → `respawned_agent`, column restored (coordinates), the TUI is still active
      although the companion spawn refocused the agent.
    - N both alive → `focused`.
    - H (rewritten) frozen agent beside its live TUI: from a three-pane window,
      stamp the agent `@aitask_frozen` → `spawned` in `agent-sitrep-<n>`,
      detail `tui_moved`; the frozen pane is untouched (same id, still stamped
      frozen and sitrep-root) and its old window holds frozen + companion only;
      the new window holds new agent + the SAME TUI pane id + companion with
      the step-I coordinates; exactly one live TUI stamp for the root;
      discovery lists the frozen pane alone in the old window and the new agent
      alone in the new one. H2: a frozen agent with no TUI anywhere → cold
      `spawned` (agent + new TUI), the frozen window untouched.
    - Race proofs (the scenario C fifo pattern) for cold, agent-only and TUI-only
      starts: exactly one agent stamp and one TUI stamp for the root afterwards.
    - Negative control: a mutant driver forcing `full_height=False` turns the
      cold-start minimonitor `height = window_height` assertion red.

### Post-implementation (Step 9)

Commit `feature: … (t2211_2)` with only the touched paths, archive via Step 9.
Final Implementation Notes for t2211_3: respawn = `spawn_sitrep` (status
`respawned_agent`); `find_sitrep_roles` is the role lookup; `SitrepSpawn.tui`;
the TUI stamp constant. For t2211_6: the new wire lines and layout.

## Verification

- `bash tests/test_sitrep_window_live.sh`, `bash tests/test_cleanup_rule_parity.sh`,
  `bash tests/test_kill_agent_run_guarded.sh`, `bash tests/test_kill_agent_pane_smart.sh`,
  `bash tests/test_no_raw_tmux.sh`, `shellcheck` on changed scripts.
- `bash tests/run_all_python_tests.sh --test-dir tests` — last-line verdict
  (covers `test_sitrep_window.py`, `test_helper_panes.py`,
  `test_list_panes_arity_characterization.py`, `test_monitor_companion_filter.py`,
  `test_minimonitor_sibling_fallback.py`, `test_agent_freeze.py`,
  `test_monitor_sitrep_harvest_close.py`).
- Manual: `ait sitrep` cold start → three panes in the agreed layout; kill the
  agent → TUI + minimonitor stay; `ait sitrep` → agent respawned above the TUI.

## Risk

### Code-health risk: low
- Growing `FROZEN_AWARE_PANE_FORMAT` / `_LIST_PANES_FORMAT` / `RUN_IDENTITY_FORMAT` changes the arity of load-bearing parsers; a reader or fake left at the old arity silently drops rows (a dropped sibling row makes `count_other_real_agents` 0 → window kill) · severity: low (residual — addressed by inline pre-phase arity_fixture_sweep; every field is APPENDED, so no existing index shifts) · → mitigation: inline pre-phase arity_fixture_sweep
- The four listing consumers must honour a second predicate while retention keeps `is_helper`; a consumer wired to the wrong one either lists the TUI or collapses its window · severity: low (residual — addressed by inline pre-phase sitrep_tui_consumer_table_characterization, one red/green row per consumer) · → mitigation: inline pre-phase sitrep_tui_consumer_table_characterization

### Goal-achievement risk: low
- The layout depends on tmux `-f` + percentage `-l` behaviour across the three spawn orders (cold, add-TUI, respawn-above); a wrong assumption gives the wrong layout while counts still pass · severity: low (residual — addressed by inline pre-phase layout_geometry_spike, then pinned by coordinate assertions and the `-f` mutant) · → mitigation: inline pre-phase layout_geometry_spike
- (review round 1) A frozen sitrep agent beside its live TUI must neither be split over nor shadow its replacement: the relocate path (new window + `join-pane -d` of the TUI) adds a tmux interaction not used elsewhere, and its stamp-travel and focus behaviour are assumptions · severity: low (spike case (e) measures it before coding; live scenario H pins window contents, the single TUI stamp and the per-window discovery view) · → mitigation: inline pre-phase layout_geometry_spike
- (review round 1) No-select repairs must not move the window's active pane: role splits had no `-d`, and the companion spawn refocuses the agent · severity: low (detached splits + a measured restore; live J/L/M assert `#{pane_active}` identity, unit tests the restore branches) · → mitigation: none (covered by steps 5, 11, 12)

### Planned mitigations
- timing: pre-phase | name: sitrep_tui_consumer_table_characterization | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: second-predicate wiring per consumer | desc: table-driven consumer tests fed a TUI-stamped pane, red rows recorded before production edits (confirmed at parent planning)
- timing: pre-phase | name: arity_fixture_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: format arity change | desc: inventory and convert every fixed-arity reader/fake of the three grown formats in the same change
- timing: pre-phase | name: layout_geometry_spike | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tmux -f / percentage -l layout assumptions | desc: measure pane coordinates of the exact planned argv for all spawn orders on an isolated server before coding
