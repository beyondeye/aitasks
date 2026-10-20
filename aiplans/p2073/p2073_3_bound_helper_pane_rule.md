---
Task: t2073_3_bound_helper_pane_rule.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
---

# t2073_3 — bound_helper_pane_rule

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

### t2073_3 — bound_helper_pane_rule (helper rule + t1388)
No deps. Step 0 (only before the rung-2 edit): t2065 gate on `minimonitor_app.py`.
1. New `lib/helper_panes.py`: `SHADOW_TARGET_OPTION` (moved from `monitor_core`),
   `SCRATCHPAD_TARGET_OPTION`, `SCRATCHPAD_STORE_OPTION`,
   `BOUND_HELPER_TARGET_OPTIONS`, `is_bound_helper`. `monitor_core.py` imports and
   re-exports them (`tmux_monitor.py`'s re-export keeps working);
   `agent_launch_utils.py` imports them directly. Test: `monitor_core.BOUND_HELPER_TARGET_OPTIONS
   is helper_panes.BOUND_HELPER_TARGET_OPTIONS`, `_companion_check_and_split`'s format
   is built from the same tuple, and `test_no_lib_to_tui_import.sh` passes with no new
   exception.
2. `FROZEN_AWARE_PANE_FORMAT`: append `#{@aitask_scratchpad_target}`;
   `_FROZEN_AWARE_ARITY = 7`; `classify_window_panes` unpacks it and ORs it into
   `is_helper` inside the existing `not frozen.strip()` clause (frozen rules unchanged).
   Covers `kill_agent_pane_smart` and `agent_freeze._other_real_agents`.
3. `_LIST_PANES_FORMAT`: append the field (index 15); `_LIST_PANES_ARITIES` gains 16
   in the same change; `_parse_list_panes` `continue`s on a non-empty `parts[15]`
   before the shadow branch (pane id still added to `seen`).
4. `lib/agent_launch_utils._companion_check_and_split`: add the field before
   `pane_start_command` (must stay last); a scratchpad does not count as a real pane.
5. `aitask_companion_cleanup.sh`: job 1 reads `#{pane_id}|#{@aitask_shadow_target}|
   #{@aitask_scratchpad_target}` and kills panes where either equals `$primary`;
   job 2 appends `|#{@aitask_scratchpad_target}` (read as `scratch`, last field) and
   skips it with the shadow helper. Keep the literal `if [ -n "$frozen" ]; then`
   (parity test seds it).
6. `minimonitor_app._find_sibling_pane_id` rung 2: list `#{pane_id}\t#{pane_pid}\t
   <helper targets>\t#{@aitask_monitor_kind}` (no `stdout.strip()`), skip self,
   bound helpers (`is_bound_helper`) and companions (`is_live_companion_marker`) —
   decision: companions ARE filtered, so a second minimonitor is never chosen.
   Docstring states the t986 guarantee for both rungs.
7. Tests: `test_cleanup_rule_parity.sh` (new `scratchpad)` role binding to `$first`,
   rows `agent + scratchpad + companion` → window, `agent + agent + scratchpad` →
   pane, scratchpad bound to the survivor, plus job-1 kill assertion);
   `test_list_panes_arity_characterization.py` (`CURRENT_ARITY = 16`, scratchpad row
   excluded); `test_monitor_companion_filter.py` `_line` values dict;
   `test_agent_freeze.py` fake pane dicts; `test_multi_agent_window_substrate.sh`
   `is_bound_helper` units; occupancy unit for `_companion_check_and_split`; the
   bash/Python option tripwire; t1388 test driving rung 2 directly (rung 1 forced to
   `None`) on `[minimonitor, shadow, agent]` and `[minimonitor, scratchpad, agent]`
   → agent id, with a negative control proving the unfiltered fallback fails.
8. aidocs: `tmux_gateway.md` option inventory rows (after `@aitask_monitor_kind`);
   `tui_conventions.md` companion sections — rename the "two-marker shape" to the
   bound-helper rule and add a "scratchpad is a fourth companion-pane case" subsection.

## Step 9 (Post-Implementation)
Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: medium
- The helper rule changes discovery, classify_window_panes, the cleanup hook and the occupancy check together; a missed copy or an un-widened arity set silently drops every pane or keeps the minimonitor alive · severity: medium · → mitigation: none (parity table, arity test, bash/Python option tripwire, identity test)
- minimonitor_app.py has uncommitted t2065 hunks · severity: medium · → mitigation: none (Step 0 pre-edit gate)

### Goal-achievement risk: low
None identified.
