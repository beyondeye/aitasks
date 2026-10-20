---
priority: medium
effort: medium
depends: [t2073_2, t2073_3]
issue_type: feature
status: Implementing
labels: [aitask_monitormini, tmux, scratchpad]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2073
created_at: 2026-10-20 10:32
updated_at: 2026-10-20 17:21
---

## Context

Child of t2073 (minimonitor scratchpad pane). This child wires the user-facing entry
point: minimonitor key **`o`** opens a scratchpad (the `ait scratchpad` app from
t2073_2) in a **vertical split of the followed agent's pane**, bound to that agent
through the bound-helper rule from t2073_3. Position and height are configurable.
Only one pad may be open per store (per project and task), or per followed pane for
unsaved pads. The full monitor gets no action (user decision). For a non-task agent
(window not `agent-(pick|qa|resume)-<id>`) the key opens an **unsaved** pad with a
visible "not saved" marker (user decision). Full design:
`aiplans/p2073_minimonitor_scratchpad_pane.md`.

Depends on t2073_2 (app) and t2073_3 (helper rule, `lib/helper_panes.py` options).

**Step 0 — coordination gate:** t2065 has uncommitted hunks in
`.aitask-scripts/monitor/minimonitor_app.py`. Before the first edit of that file, run
`git diff --quiet -- <file>` and confirm t2065's commit is in `git log`. Do the
`monitor_core.py`, config and test work first. If the gate still fails, stop and ask
the user.

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_core.py`:
  - `scratchpad_query_args()`: `list-panes -a -F
    '#{pane_id}\t#{@aitask_scratchpad_target}\t#{@aitask_scratchpad_store}'`.
  - `find_scratchpad_pane_status(monitor, followed_pane, store_key)` → `(ok, pane)`.
    It refuses on an unverifiable query. A task pad matches on an equal, non-empty
    store key; an unsaved pad matches on target == followed pane.
  - `spawn_scratchpad(monitor, *, followed_pane, followed_window, session, task_id,
    target_root, companion_pane, select_window, notify, schedule_refresh)`, mirroring
    `spawn_shadow` (~:3899-4052):
    - the store key comes from `aitask_scratchpad_store.sh path <id>` run with
      `cwd=target_root`; a failure refuses the spawn;
    - live re-check;
    - `launch_in_tmux` with `TmuxLaunchConfig(split_direction="vertical",
      split_target_pane=followed_pane, split_size=<rows>,
      split_before=(position=="top"), new_window=False, cwd=target_root,
      select_window=...)`;
    - `resolve_pane_id_by_pid`;
    - stamp `@aitask_scratchpad_target` (retry once, kill the pane on failure), then
      stamp `@aitask_scratchpad_store` for task pads (same handling);
    - `attach_companion_cleanup_hook(followed_pane, companion_pane or pad_pane)`.

    Command: `ait scratchpad --task <id> --target <pane>` or
    `ait scratchpad --unsaved --target <pane>`.
- Config:
  - `tmux.scratchpad_position` (enum `top|bottom`, default `bottom`);
  - `tmux.scratchpad_height` (int rows, default 12; an invalid value falls back to
    the default).

  Read them via `load_project_tmux_config`. Add both to
  `.aitask-scripts/settings/settings_app.py` `TMUX_CONFIG_SCHEMA` next to
  `shadow_pane_width` (~:344), and as a commented doc block in
  `seed/project_config.yaml` (near ~:520).
- `.aitask-scripts/monitor/minimonitor_app.py` (after the gate):
  - `Binding("o", "open_scratchpad", "Notes", show=False)` in BINDINGS (~:1211);
  - `action_open_scratchpad`: followed agent via `_find_own_agent_snapshot`, task id
    via `TaskInfoCache.get_task_id_for_pane`; `None` → unsaved pad plus the
    notification "not a task agent — notes will not be saved";
  - `_spawn_scratchpad` adapter with `companion_pane=os.environ.get("TMUX_PANE") or
    None` and `select_window=True`;
  - `KEY_HINTS_TEXT` (~:866): add `o:notes` to an existing line, then MEASURE the
    band at (15, 30) as the comment there demands (≤ 29 rows; the row count is pinned
    by `test_minimonitor_top_chrome_render.py`).

## Reference Files for Patterns

- `minimonitor_app.action_launch_shadow` / `_spawn_shadow` (~:3762-3913).
- `monitor_core.find_shadow_pane_status` / `shadow_query_args` (~:607-646).
- `tests/test_monitor_shadow_pick.py` (mocked spawn tests, config fallback at :388-406).
- `tests/test_monitor_shadow_spawn_live.sh` (live, isolated tmux).
- `tests/test_minimonitor_concern_action.py:3205` — every binding key must appear in
  `KEY_HINTS_TEXT`.

## Implementation Plan

1. `monitor_core.py` lookup and spawn.
2. Config schema and seed doc.
3. Tests that don't need `minimonitor_app.py`.
4. Gate, then the binding, action, adapter and key hint.
5. The live test.

## Verification Steps

- NEW `tests/test_minimonitor_scratchpad_spawn.py` (mocked):
  - refuses on an unverifiable lookup;
  - refuses a duplicate store key in the same project;
  - allows the same task number in a second project and refuses a second pad in the
    first;
  - a second press refuses the first pad even when the store root did not exist at
    the first press;
  - refuses when the `path` call fails;
  - refuses a duplicate pane for an unsaved pad;
  - kills the pane on each stamp failure;
  - sets `split_before` for top;
  - height default and fallback;
  - non-task agent → `--unsaved`.
- The key-hint coverage test and `test_minimonitor_top_chrome_render.py` pass.
- NEW `tests/test_scratchpad_spawn_live.sh` (isolated tmux):
  - the pad is absent from `discover_panes`;
  - the pad is killed when its agent exits, and the minimonitor despawns;
  - the pad survives freeze and restore (same pane id);
  - dropping the frozen record leaves the pad behind. Assert this and record it as the
    known gap; the planned mitigation below fixes it.
- Full Python suite (read the last line); `bash tests/test_no_raw_tmux.sh`.

## Risk mitigation carried from the parent plan

The parent plan confirmed an **after** mitigation, created at this child's Step 8d:
`kill_bound_helpers_on_direct_kill`. When `kill_agent_pane_smart`'s pane branch, or a
frozen-record drop, kills an agent directly, also kill the panes bound to it (shadow
and scratchpad target options). Both paths run `kill-pane`, which fires no
`pane-died` hook. Include tests for both paths.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2073_3** id=2026-10-20T14:17:47Z.12bef74e1e9101b7f731de23 from=t2073_3 from_verified=yes at=2026-10-20T14:17:47Z base=3e796adac862dee9e68940941c91a0f63fbc3b3a base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2073_3 (code commit 3e796adac on main; tree-relative claims below are dated by that commit).
> | 
> | 1. Shared vocabulary exists. lib/helper_panes.py defines SHADOW_TARGET_OPTION, SCRATCHPAD_TARGET_OPTION, SCRATCHPAD_STORE_OPTION, BOUND_HELPER_TARGET_OPTIONS and is_bound_helper. monitor.monitor_core and monitor.tmux_monitor re-export the same objects. Suggest importing from there instead of re-spelling the option names.
> | 
> | 2. Consumers are already in place. Discovery (_parse_list_panes), classify_window_panes, the occupancy check (_companion_check_and_split), cleanup jobs 1/2 and minimonitor _find_sibling_pane_id rung 2 all treat a pane stamped @aitask_scratchpad_target as a bound helper. The spawn side is what remains: stamp-or-kill the target option, then arm attach_companion_cleanup_hook.
> | 
> | 3. Possible gap in your plan (my reading — please verify). The spawn-time one-pad-per-store live lookup over `list-panes -a` keyed on @aitask_scratchpad_store / @aitask_scratchpad_target does not say how it treats a pane carrying @aitask_frozen. Every other helper consumer now checks @aitask_frozen FIRST: a stand-in keeps the pane-scoped options of whatever ran there before respawn-pane, so a retained marker is never trusted as helper identity. A stand-in that retained a scratchpad marker is probably rare. Still, a lookup that counts it would refuse a spawn for a pad that is not running. Consider skipping @aitask_frozen panes in that lookup, with a test.
> | 
> | 4. Test fakes. A fake answering list-panes positionally broke when the occupancy format grew (tests/test_minimonitor_instance_guard.py). It now renders rows from the requested -F (_render_panes). New fakes for the spawn path may want the same shape.
> | 
> | 5. Moment-relative, as of this moment only: .aitask-scripts/monitor/minimonitor_app.py had no uncommitted hunks when t2073_3 edited it. Re-run the t2065 gate (`git diff --quiet -- <file>`) yourself before editing.

> **👁 note:read** id=2026-10-20T14:21:43Z.1217dc155f9821d37e982093 by=t2073_4 at=2026-10-20T14:21:43Z mode=explicit ids=2026-10-20T14:17:47Z.12bef74e1e9101b7f731de23
