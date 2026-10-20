---
Task: t2073_4_minimonitor_scratchpad_key.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
---

# t2073_4 — minimonitor_scratchpad_key

Full parent design: `aiplans/p2073_minimonitor_scratchpad_pane.md`. The two parent
sections below are copied verbatim so this plan stands alone.

## Coordination with in-flight tasks (applies to every child)

- **t2065** (Implementing) has uncommitted hunks in `monitor/minimonitor_app.py`,
  `monitor/monitor_app.py`, `monitor/monitor_shared.py`, `applink/router.py`.
- t2072 landed during planning (da2eb3666); its files are clean again and no child
  edits them.
- Pre-edit gate for any shared file: `git diff --quiet -- <file>` AND its commit is
  visible in `git log`. Do all non-overlapping work first; if the gate still fails,
  stop and ask the user. No child edits `monitor_app.py`, `monitor_shared.py`,
  `router.py` or `shadow_agent.md`. Only t2073_3 (rung 2) and t2073_4 (key) edit
  `minimonitor_app.py` → both carry the gate as step 0.

## Shared design decisions

- **Layering:** the helper-pane vocabulary lives in a new library module
  `.aitask-scripts/lib/helper_panes.py` (stdlib only), because both
  `monitor/monitor_core.py` and `lib/agent_launch_utils.py` consume it and
  `monitor_core` already imports `agent_launch_utils` (lib → TUI imports are banned by
  `test_no_lib_to_tui_import.sh`). `SHADOW_TARGET_OPTION` moves there too;
  `monitor_core` (and `tmux_monitor`, which re-exports it today) re-export the names
  so existing imports keep working.
- **New pane options** (defined in `lib/helper_panes.py`):
  `SCRATCHPAD_TARGET_OPTION = "@aitask_scratchpad_target"` (value = bound agent pane
  id; the helper classifier + lifecycle binding) and
  `SCRATCHPAD_STORE_OPTION = "@aitask_scratchpad_store"` (the **canonical absolute
  store directory** of a task pad, empty for an unsaved pad; used only by the
  one-per-store duplicate lookup). A bare task id is NOT used: one tmux server hosts
  several projects, and task numbers are repository-local, so project A's t42 must not
  block project B's t42.
- **One helper rule:** `BOUND_HELPER_TARGET_OPTIONS = (SHADOW_TARGET_OPTION,
  SCRATCHPAD_TARGET_OPTION)` + `is_bound_helper(*targets) -> bool` in
  `lib/helper_panes.py`.
  Every Python format that classifies helpers is built from that tuple. The bash
  copy (`aitask_companion_cleanup.sh`) is kept in step by `test_cleanup_rule_parity.sh`
  plus a source tripwire asserting each option of the tuple appears in the script's
  `-F` formats.
- **Discovery:** scratchpad panes are dropped entirely in `_parse_list_panes` (like
  companions) — **never** routed into the `shadows` list, where `commit_snapshots`
  would make them compete with the real shadow for `_shadow_snapshots[<agent>]`.
- **Store:** gitignored `.aitask-scratchpad/<id>/notes.md` (env
  `AITASK_SCRATCHPAD_DIR`), written only through `aitask_scratchpad_store.sh` (registry
  lock + `ait_atomic_render`), modelled verbatim on `aitask_shadow_rejected.sh`.
- **One writer per store:** (a) spawn-time live lookup over `list-panes -a` keyed on
  `@aitask_scratchpad_store` (task pads; canonical path, so per project) or
  `@aitask_scratchpad_target` (unsaved pads; pane ids are server-unique), refusing on
  an unverifiable query; (b) authoritative app-held `fcntl.flock` on
  `<store>/.holder.lock` (kernel-released on any death, so no stale-pid problem).
  **Only `open` creates that file**, inside its lifecycle-locked critical section; the
  app opens it with `O_RDWR` and **no `O_CREAT`**, so an app racing archival can never
  re-create anything in a pruned store (missing file → "not saved — task archived").
  **Ownership comes before content:** the app takes the flock FIRST and only then reads
  `notes.md`, so a previous writer's final save is always visible to its successor. On
  contention the app takes a separate **read-only path** (snapshot read, `TextArea`
  `read_only=True`, never saves, header "read-only: open elsewhere") and never later
  promotes itself. Every `save` subprocess inherits the flock fd (`pass_fds`), so the
  lock stays held until an orphaned in-flight save of a killed app finishes — a
  successor cannot read before that write lands.
- **Autosave with a deadline:** on every change, arm a save for
  `min(last_change + 1.0 s, first_unsaved_change + 3.0 s)` — the 1 s debounce can be
  postponed by continuous typing, the 3 s max dirty age cannot. Saves are serialized
  (a change during an in-flight save keeps the dirty flag and its original
  `first_unsaved_change`, and re-arms after the save returns). Save on `ctrl+s`, on exit
  and on SIGHUP (best-effort). **Stated loss window on a hard kill: at most the last
  3 s of edits, plus the edits carried by one in-flight save (bounded by the helper's
  5 s timeout); everything older is on disk.**
- **Store lifecycle is serialized by one per-task lock that lives OUTSIDE the store
  dir** (`$SCRATCHPAD_DIR/.locks/<id>.lockd`, `registry_lock`), so no verb needs to
  `mkdir` the store just to lock it (the shadow helper's `lock_or_busy` does
  `mkdir -p STORE_DIR` — not copied):
  - `open` — under the lock: refuse `NO_TASK` unless the active task file exists,
    then `mkdir` the store and create `.holder.lock`. Archival moves the task file
    **before** it prunes (`archive_move` precedes `prune_*` at every site), so an
    `open` either runs wholly before the move (its store is pruned later) or sees the
    moved file and refuses. No resurrection.
  - `save` — under the lock: refuse `ARCHIVED` unless the active task file exists
    (checked even when a directory survives), then `ABSENT` if the store dir is
    gone; never `mkdir`. The app shows "not saved — task archived / store removed".
  - `prune` — the store-absence check, own-root guard, sweep and `rmdir` all run
    **under the lock** (an absence check before the lock would miss a first `open`
    paused between its task check and its `mkdir`). The one early return is a
    missing **root** dir: every lifecycle verb creates `<root>/.locks` before taking
    the lock, so no critical section can be in flight, and any later `open` runs
    after `archive_move` and refuses `NO_TASK` — this also keeps archival from
    creating `.aitask-scratchpad/` in repos that never used a scratchpad.
  - Deterministic coverage: a test-only pause seam (`AITASK_SCRATCHPAD_PAUSE_FIFO`,
    honoured only when set) stops a verb at a named point inside the lock, so tests
    interleave `open`-vs-`prune` and `save`-vs-`prune` exactly, and an externally held
    lock proves prune never deletes while a lifecycle op holds it.
- **Known gap, documented not fixed:** direct `kill-pane` paths fire no `pane-died`
  (`kill_agent_pane_smart`'s pane branch, `agent_freeze.drop_record` via
  `kill_if_stamped`), so bound helpers — shadows today, scratchpads too — survive
  those kills. Freeze/restore use `respawn-pane -k` on the same pane id, so the binding
  survives them. → after-mitigation follow-up (see Risk).

## This child

### t2073_4 — minimonitor_scratchpad_key
Depends on t2073_3 and t2073_2. Step 0: t2065 gate on `minimonitor_app.py`.
1. `monitor_core.py`: `scratchpad_query_args()` (`list-panes -a -F
   '#{pane_id}\t#{@aitask_scratchpad_target}\t#{@aitask_scratchpad_store}'`) /
   `find_scratchpad_pane_status(monitor, followed_pane, store_key)` → `(ok, pane)`:
   a task pad matches on equal non-empty `store_key` (canonical store dir from the
   helper's `path` verb, run with `cwd=target_root`; a failed `path` call refuses the
   spawn); an unsaved pad matches on `target == followed_pane`; `spawn_scratchpad(monitor, *, followed_pane,
   followed_window, session, task_id, target_root, companion_pane, select_window,
   notify, schedule_refresh)` mirroring `spawn_shadow`: config, live re-check (refuse
   unverifiable/duplicate), `launch_in_tmux` with `TmuxLaunchConfig(split_direction=
   "vertical", split_target_pane=followed_pane, split_size=<rows>, split_before=
   (position == "top"), new_window=False, cwd=target_root, select_window=...)`,
   `resolve_pane_id_by_pid`, stamp target (retry once, kill pane on failure), stamp
   store key for task pads (same), `attach_companion_cleanup_hook(followed_pane, companion_pane or pad_pane)`.
   Command: `ait scratchpad --task <id> --target <pane>` or `--unsaved --target <pane>`.
2. Config: `tmux.scratchpad_position` (enum `top|bottom`, default `bottom`) and
   `tmux.scratchpad_height` (int rows, default 12; invalid → default) — read in
   `spawn_scratchpad`; `settings_app.TMUX_CONFIG_SCHEMA` entries next to
   `shadow_pane_width`; `seed/project_config.yaml` commented doc block.
3. `minimonitor_app.py`: `Binding("o", "open_scratchpad", "Notes", show=False)`;
   `action_open_scratchpad` (followed agent via `_find_own_agent_snapshot`; task id via
   `TaskInfoCache.get_task_id_for_pane`; `None` → unsaved pad + notification "not a
   task agent — notes will not be saved"); `_spawn_scratchpad` adapter passes
   `companion_pane=os.environ.get("TMUX_PANE") or None`, `select_window=True`.
   `KEY_HINTS_TEXT`: add `o:notes` to an existing line, then MEASURE at (15, 30) per the
   comment (≤ 29 rows) and keep the row count pinned by
   `test_minimonitor_top_chrome_render.py`.
4. Tests: `tests/test_minimonitor_scratchpad_spawn.py` (mocked, like
   `test_monitor_shadow_pick.py`: refuses unverifiable lookup, duplicate by store key
   in the same project, **allows the same task number in a second project (different
   canonical store) and refuses a second pad in the first**, **a second press refuses
   the first pad when the store root did not exist at the first press** (key stable
   across creation), refuses when the `path` call fails, duplicate by pane for unsaved, kill on each stamp failure, `split_before` for top,
   height default/fallback, non-task → `--unsaved`); key-hint coverage test passes;
   `tests/test_scratchpad_spawn_live.sh` (isolated tmux: pad absent from
   `discover_panes`, killed when its agent dies, minimonitor despawns with it; survives
   freeze/restore on the same pane id; record **drop** leaves it behind → asserted and
   documented as the known gap).

## Step 9 (Post-Implementation)
Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: low
- spawn_scratchpad mirrors spawn_shadow; minimonitor edit is a binding + adapter · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Bound helpers survive direct kill-pane paths (kill_agent_pane_smart pane branch, frozen-record drop) because no pane-died fires · severity: medium · → mitigation: kill_bound_helpers_on_direct_kill

### Planned mitigations
- timing: after | name: kill_bound_helpers_on_direct_kill | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: bound helpers survive direct kill-pane paths | desc: Kill panes bound to an agent (shadow/scratchpad target options) when kill_agent_pane_smart's pane branch or a frozen-record drop kills that agent directly, with tests for both paths
