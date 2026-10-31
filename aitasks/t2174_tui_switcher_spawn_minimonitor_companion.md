---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [tui, switcher, minimonitor, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-31 19:00
updated_at: 2026-10-31 19:01
---

## Goal

Let the user spawn a minimonitor companion pane beside **any** framework TUI
(trails, board, codebrowser, settings, stats, syncer, brainstorm, applink,
chatlink, frozenagent, ...) from the TUI switcher overlay (`j`), so jumping back
to a specific code-agent window from a TUI window no longer means reopening the
switcher and scanning the list.

Today a minimonitor companion is auto-spawned only for code-agent windows
(`agent-` / `create-` prefixes) and for the git TUI. Every other TUI window has
no companion, so switching back from it to a given agent is awkward.

## Requested behaviour

- A new quick-jump key in the TUI switcher overlay: **spawn a minimonitor
  companion in the window of the TUI the switcher was opened from**.
- The option is **shown only when no minimonitor is already present** in that
  window. When one exists (live, or still booting), the hint is hidden and the
  key does nothing.
- The presence check must be fast. Exploration found it costs one tmux call (see below).

## Findings from exploration

### Spawning beside a TUI is already supported
- `maybe_spawn_minimonitor` (`.aitask-scripts/lib/agent_launch_utils.py:2647`)
  takes `force_companion=True`, which skips the companion-prefix check and the
  TUI-name/brainstorm exclusion, and `agent_pane=`, which pins the split, cleanup
  hook and refocus to a known pane id. The `auto_spawn`, existing-minimonitor
  and 3-real-pane overcrowding gates still apply, under `_companion_spawn_lock`.
- Precedent: `TuiSwitcherOverlay._launch_git_with_companion`
  (`.aitask-scripts/lib/tui_switcher.py:1413`) already runs a minimonitor beside
  a TUI (git) with `force_companion=True`.
- Cleanup when the TUI quits already works: `attach_companion_cleanup_hook`
  (armed inside `maybe_spawn_minimonitor`) sets `remain-on-exit on` plus a
  `pane-died` hook on the host pane. `aitask_companion_cleanup.sh` then kills
  the companion when no real sibling remains. Backstop: the minimonitor's own
  verified-empty-window auto-close (`_check_auto_close`,
  `.aitask-scripts/monitor/minimonitor_app.py:1892`).

### Fast "already present?" check
- The eligibility rule lives in `_companion_check_and_split`
  (`agent_launch_utils.py:2532`). It runs one `list-panes` with
  `#{pane_id}|#{@aitask_monitor_kind}|<helper targets>|#{@aitask_frozen}|#{pane_dead}|#{pane_start_command}`.
  A live marker (`monitor_marker_alive`) or a non-dead pane whose start command
  is `ait minimonitor` (still booting, t2039) means a companion is present.
- Pull out a **read-only** helper (e.g. `companion_present(pane_target) -> bool | None`)
  that shares this classification. **Do not duplicate it.** The split path and
  the probe must agree. The helper must not self-heal stale markers. Treat a
  failed tmux read as "unknown" and hide the option: fail closed.
- Target the window by **`$TMUX_PANE`** (`list-panes -t $TMUX_PANE`). An
  untargeted `list-panes` resolves to the session's *current* window, not the
  caller's (measured at t2039, see the comment in `aitask_minimonitor.sh`).
- Cost: one tmux subprocess at overlay mount. `TuiSwitcherOverlay.on_mount` →
  `_populate_list_for` already makes a synchronous `get_tmux_windows` call, so
  this is the same order of cost.

### Where it plugs in
- All switcher hosts get the overlay through `TuiSwitcherMixin`
  (`tui_switcher.py:1467`): board (incl. its trail screen), trails, codebrowser,
  settings, stats, syncer, brainstorm, applink, chatlink, frozenagent, monitor,
  minimonitor (12 apps).
- Quick-jumps are `_QUICK_JUMP_BINDINGS` (`tui_switcher.py:393`), registered
  under `shared.tui_switcher` so they can be customized in the `?` editor and in
  Settings → Shortcuts. The new binding goes there. Hide or disable it with
  `check_action` on the overlay when ineligible.
- Free default keys (not in `_QUICK_JUMP_BINDINGS` / `_OVERLAY_RESERVED_KEYS`):
  `M`, `w`, `o`, `p`, `d`, `h`, `k`, `u`, `v`, `z`. Proposed: **`M`** (minimonitor).
- **Hint budget:** the `_HINT_ITEMS` row is already about 122 columns wide
  (comment at `tui_switcher.py:236`; `tests/test_tui_switcher_footer_fit.sh`,
  `tests/test_tui_switcher_hint_text.py`). Put the new hint on the shorter
  second line (`Enter switch ... close`) or on its own conditional line, shown
  only when eligible, and keep the footer-fit tests green, including at the
  minimonitor's narrow width.

## Design decisions to settle in planning
1. **Ineligible hosts:** never offer it in `monitor` / `minimonitor`
   (`current_tui_name`). The marker gate would refuse there anyway, but the hint
   must not show.
2. **Target window = the host TUI's own window** (`$TMUX_PANE`), even while the
   switcher is browsing another session or project (left/right). Resolve
   session and window index from `$TMUX_PANE` (`display-message -t $TMUX_PANE`)
   and pass `window_index=` + `agent_pane=$TMUX_PANE`. **Do not** look the
   window up by name, because `maybe_spawn_minimonitor` picks the *last*
   same-named window. The pane must be on the gateway server (compare
   `current_tmux_session()` / t1951).
3. **`auto_spawn: false`:** an explicit user request should probably bypass it,
   since the flag is about *automatic* spawning. That needs a new keyword
   argument on `maybe_spawn_minimonitor` (e.g. `explicit=True`), not a reuse of
   `force_companion`. Confirm with the user in planning.
4. **Overcrowding gate (3+ real panes):** keep it. When it or the lock refuses,
   notify the user. The overlay's snapshot is advisory; the locked check in
   `maybe_spawn_minimonitor` decides.
5. **Project root:** pass the host's project root (the cwd of the running TUI),
   not `_selected_project_root()` (that is the browsed project).
6. After a spawn: dismiss the overlay. Focus returns to the TUI pane
   (`maybe_spawn_minimonitor` refocuses `agent_pane`).

## Risks / things to check
- `remain-on-exit on` is now set on TUI panes that get a companion. Check that
  each TUI's normal quit still closes the window: the cleanup hook kills the
  dead primary and the companion. git already does this, but verify one
  Textual TUI live.
- Minimonitor Tab / Enter (`_find_sibling_pane_id`) would resolve to the TUI
  pane as the "followed" sibling. Make sure that is harmless, or that the
  minimonitor degrades cleanly when its window has no agent.
- The TUI's width shrinks by `tmux.minimonitor.width` (default 40). Narrow
  layouts in some TUIs may need a quick look.
- Raw tmux calls must go through the gateways (`lib/tmux_exec.py`;
  `tests/test_no_raw_tmux.sh`). Read `aidocs/framework/tmux_gateway.md` and
  `aidocs/framework/tui_conventions.md` before editing.

## Tests
- Unit tests for the read-only presence probe: live marker, stale marker,
  booting start command, dead companion, bound helpers, tmux failure → unknown.
- Overlay: hint and binding hidden in monitor/minimonitor and when a companion
  is present; shown otherwise. The key with an ineligible window is a no-op.
- Spawn uses `$TMUX_PANE`'s window, not the browsed session.
- Footer-fit and hint-text tests updated.
- If practical, a live tmux test: spawn from a TUI, quit the TUI, and check
  that the window closes.

## Docs
- `website/content/docs/tuis/minimonitor/_index.md` and `how-to.md`: a
  minimonitor can now be spawned beside any TUI from the switcher.
- `website/content/docs/tuis/monitor/_index.md` (switcher section, line ~76),
  and any switcher key list. Run `website/check_links.py --build` after editing.
