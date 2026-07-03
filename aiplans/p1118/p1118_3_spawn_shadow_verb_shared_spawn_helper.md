---
Task: t1118_3_spawn_shadow_verb_shared_spawn_helper.md
Parent Task: aitasks/t1118_mobile_shadow_agent_driving_over_applink.md
Sibling Tasks: aitasks/t1118/t1118_1_*.md, aitasks/t1118/t1118_2_*.md, aitasks/t1118/t1118_4_*.md, aitasks/t1118/t1118_5_*.md
Archived Sibling Plans: aiplans/archived/p1118/p1118_*_*.md
Worktree: aiwork/t1118_3_spawn_shadow_verb_shared_spawn_helper
Branch: aitask/t1118_3_spawn_shadow_verb_shared_spawn_helper
Base branch: main
---

# Plan: `spawn_shadow` verb + shared spawn helper (t1118_3)

Implements parent-plan D2.1. Contract: `aidocs/applink/shadow_driving.md`.

## Steps

1. **Extract the shared helper.** Move the body of
   `minimonitor_app.action_launch_shadow` (~:1046-1147) into a headless
   function, e.g. `spawn_shadow_for_pane(monitor, project_root, followed_pane,
   task_id=None) -> tuple[str|None, str|None]` (`(shadow_pane_id, error)`),
   living in `lib/agent_launch_utils.py` (no Textual imports; `monitor_core`
   would also work — pick whichever avoids an import cycle with
   `agent_launch_utils`). Covers, in order:
   - one-shadow guard (reverse lookup via the `match_shadow_pane` pattern,
     minimonitor_app.py:99-119 — move/port the pure matcher next to the helper);
   - `resolve_dry_run_command(project_root, "shadow", followed_pane[, task_id])`
     (`agent_launch_utils.py:188`);
   - placement: `_load_project_tmux_config` → `shadow_same_window` (default
     True) / `shadow_pane_width` (default 60) → `TmuxLaunchConfig(...)` exactly
     as the minimonitor code does today;
   - `launch_in_tmux(full_cmd, cfg)` → `resolve_pane_id_by_pid`;
   - stamp `@aitask_shadow_target = followed_pane` on the new pane (gateway);
   - `attach_shadow_cleanup_hook(followed_pane, shadow_pane)` (:1303).
2. **Minimonitor becomes a thin caller:** `action_launch_shadow` resolves
   `followed_pane`/`task_id`/`target_root` (UI concerns) and calls the helper;
   keeps its notify() UX on the returned error/success.
3. **Router verb** (`applink/router.py`): add `spawn_shadow` to
   `IMPLEMENTED_COMMAND_VERBS` + `_dispatch`:
   - `pane_id` via `_req_pane_id`; roster check `self._monitor.get_pane(pane_id)`
     → `BAD_PAYLOAD` "unknown pane" if absent;
   - existing-shadow → `err BAD_PAYLOAD detail={"reason":"shadow_exists",
     "shadow_pane": <id>}`;
   - call the shared helper (server resolves task_id via `_resolve_pane_task`
     and project root — client input is only the `%N` pane id);
   - success → `{"ok": true, "shadow_pane": <id>}`; audit-log attempts and
     rejections (SPAWN_TUI_REJECTED precedent, router.py:444-451).
   - NOT two-phase (non-destructive; `spawn_tui` precedent).
4. **Profiles (same commit):** `spawn_shadow` in
   `aitasks/metadata/applink_profiles/full.yaml` + `profiles.py:DEFAULT_ALLOWED`;
   flip the `permissions.md` row from pending to implemented.

## Verification

- `tests/test_applink_router.sh` additions (StubMonitor): missing/malformed
  pane_id, unknown pane, `PERMISSION_DENIED` below `full`, `shadow_exists`
  guard, success shape.
- Helper unit test with construction spies (no live tmux): dry-run command
  resolved, launch config fields (split direction/size/target), stamp and
  cleanup hook invoked in order; guard short-circuits before any launch
  (no-side-effect-before-validation).
- Minimonitor regression: `tests/test_shadow_spawn_config.sh` family green;
  `tests/test_no_raw_tmux.sh` green.

## Post-implementation

Step 9 (task-workflow): archive via `aitask_archive.sh 1118_3`, push.
