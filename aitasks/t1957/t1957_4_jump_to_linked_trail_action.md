---
priority: medium
effort: high
depends: [1957_2, 1957_3]
issue_type: feature
status: Ready
labels: [trails, board, tmux, cross_repo]
gates: [risk_evaluated]
anchor: 1957
created_at: 2026-10-12 21:32
updated_at: 2026-10-12 21:32
---

## Context

Part of t1957 (parent plan:
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`). Depends on
t1957_2 (`ait trails --trail`, pane-addressed focus mailbox,
`launch_or_focus_trails`) and t1957_3 (`trail_links.scan_linked_trails` →
`LinkScan(links, errors, complete)`). This child adds the user-facing action:
from a trail in this repo, list the linked trails in other repos and jump to one
— switch to that project's tmux session and open/focus the trail in its
`ait trails`.

Shortcut-scope rule (`aidocs/framework/tui_conventions.md`, "The board
package"): `ait trails` shares `TRAIL_BINDINGS` with the board (scope
`"board"`); a new binding is the SAME `Binding` object on both hosts. The board
places `TRAIL_BINDING["<action>"]` at its own position among its rows
(`aitask_board.py`). `L` is currently unbound on both App classes (the board's
`l`/`L` lock keys live on the detail *screen*) — re-check.

User decision: when the target project has no running tmux session, **bootstrap
it** with `lib/tmux_bootstrap.sh` (as the TUI switcher does for registered
sessions in `TuiSwitcherOverlay._ensure_session_live`, `lib/tui_switcher.py`
~639).

## Key Files to Modify

- `.aitask-scripts/board/board_trail_screen.py` — `TRAIL_BINDINGS` entry,
  `action_trail_linked`, `_trail_link_worker`, `_on_trail_links`, jump worker,
  `_trail_link_gen` invalidation points.
- `.aitask-scripts/board/board_trail_view.py` — `LinkedTrailsScreen` modal.
- `.aitask-scripts/board/trails_app.py`, `.aitask-scripts/board/aitask_board.py`
  — binding declaration + `check_action` (visible only in By-Trail with an
  active trail).
- `.aitask-scripts/lib/agent_launch_utils.py` — `bootstrap_project_session(root)`.
- `.aitask-scripts/lib/tui_switcher.py` — `_ensure_session_live` calls the new
  helper, keeping its own result / STALE-modal handling.
- Tests: `tests/test_board_bytrail_view.py`, `tests/test_trails_app.py`,
  `tests/test_trail_screen_host_protocol.py`, switcher tests.

## Reference Files for Patterns

- `TrailSelectScreen` and `_open_trail_select` / `_trail_discovery_worker`
  (`board_trail_screen.py` ~933-960) for modal + worker shape.
- Gen stamps: `_bump_trail_gen`, `_supersede_trail_workers` (~327),
  `_switch_trail_session` (~460), `_close_trail_session` (~468),
  `_activate_trail` (~1061).
- `owned_lookup_session` (`agent_launch_utils.py` ~527); tmux targets
  `tmux_session_target` / `tmux_window_target`; switch-client in
  `tui_switcher.py` ~1404-1422.
- `TRAIL_ACTION_CAPABILITIES` / `_has_trail_capability` (not needed if both
  hosts support the action — they do, the mixin implements it).

## Implementation Plan

1. Binding `Binding("L", "trail_linked", "Linked Trails")` in `TRAIL_BINDINGS`;
   declared on both hosts; `check_action` shows it only in By-Trail with an
   active trail.
2. `action_trail_linked`: capture origin `handle` and a fresh
   `self._trail_link_gen = self._bump_trail_gen()`; start
   `@work(thread=True) _trail_link_worker(gen, handle)` → `scan_linked_trails`
   (notice "Searching linked trails in N projects…"). UI-thread callback
   `_on_trail_links(gen, handle, scan)` drops the result unless:
   `gen == self._trail_link_gen`, `base_filter == "bytrail"`, the active trail's
   handle == origin, and the origin session is still open. Invalidation: new
   `L` press; `_supersede_trail_workers` resets it; `_switch_trail_session` /
   `_close_trail_session` / `_activate_trail` bump it. Dropped → nothing shown.
3. Valid result → `LinkedTrailsScreen`: rows `project · handle · name ·
   reasons`; each `ProjectScanError` as a disabled row ("<project>: could not
   search (stale path / not registered / export failed / timed out)"). Empty +
   complete → "No linked trails in other projects"; empty + incomplete → "No
   linked trails found — N project(s) could not be searched" with error rows
   (never the definitive message).
4. On select → thread worker (guard at the execution boundary): re-resolve root;
   `owned_lookup_session(root)`; None → `bootstrap_project_session(root)` then
   re-lookup (bootstrap failure → notify, stop); version-skew check (target
   `.aitask-scripts/board/trails_app.py` lacks `--trail` → notify "<Y> runs an
   older aitasks; run `ait upgrade` there", still switch session);
   `launch_or_focus_trails(session, root, handle)`; then
   `switch-client -t =<session>` via the gateway. Not in tmux → notify the
   manual command `ait projects exec <Y> -- ait trails --trail <h>`.
5. Tests: binding identity on both hosts; modal rows incl. incomplete scan and
   both empty messages; scan supersession (search on A then switch to B / close
   A / leave By-Trail before the result lands → no modal; two searches
   completing out of order → only the newest opens); jump worker with stubbed
   resolver/gateway: live session, bootstrap path, bootstrap failure,
   not-in-tmux, version skew; switcher `_ensure_session_live` regression.

## Verification

- `python3 -m pytest tests/test_board_bytrail_view.py tests/test_trails_app.py tests/test_trail_screen_host_protocol.py -q` plus the switcher test files touched; `bash tests/test_no_raw_tmux.sh`.
- Manual (manual-verification sibling): from `ait trails` here, `L` lists the
  `aitasks_mobile` linked trail; selecting it switches to that session with the
  trail focused; with that session stopped, the jump bootstraps it.
