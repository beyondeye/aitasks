---
Task: t2073_1_scratchpad_store_and_archival.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
---

# t2073_1 — scratchpad_store_and_archival

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

### t2073_1 — scratchpad_store_and_archival
No deps; touches no shared dirty file → runs first.
1. New `.aitask-scripts/aitask_scratchpad_store.sh` (structure of
   `aitask_shadow_rejected.sh`: no `task_utils.sh`; `terminal_compat.sh`,
   `registry_lock.sh`, `atomic_write.sh`; `resolve_task_id`; exit codes 0/2/3/4) with
   the lifecycle lock described under "Store lifecycle" — `store_paths_for` derives
   `LOCK_DIR="$SCRATCHPAD_DIR/.locks/$TASK_ID.lockd"`; `lock_or_busy` only
   `mkdir -p "$SCRATCHPAD_DIR/.locks"` (never the store). Verbs, each wholly under
   the lock:
   - `open <id>` — refuse `NO_TASK` unless `${TASK_DIR:-aitasks}/t<id>_*.md` (parent)
     or `t<p>/t<p>_<c>_*.md` (child) exists (shared `task_is_active` function);
     `mkdir` the store; create `.holder.lock`; print `OPENED:<file>`.
   - `save <id>` — read stdin first (outside the lock), then under the lock:
     `task_is_active` fails → `ARCHIVED`; store dir absent → `ABSENT` (both exit 0,
     never mkdir); empty buffer removes `notes.md` (`ait_atomic_render` refuses zero
     bytes) → `SAVED:empty`; else `ait_atomic_render` → `SAVED:<bytes>`.
   - `path <id>` — print the store's identity key, one normalization for existing and
     missing roots, never creating anything: (1) make the root absolute — an absolute
     `AITASK_SCRATCHPAD_DIR` is used as-is, a relative one is prefixed with `$PWD`;
     refuse (exit 2) a root containing a `..` segment; (2) walk up to the deepest
     **existing** ancestor and canonicalize it physically (`cd … && pwd -P`, portable
     to BSD); (3) append the remaining, not-yet-created components and `/<id>`.
     Because `mkdir` only ever creates real directories below that ancestor, the key
     is identical before and after the root/store are created, and symlinked
     ancestors resolve the same way in both states.
   - `prune <id>` — root absent → `PRUNED:absent` (the only pre-lock exit, see
     "Store lifecycle"); otherwise lock (5 s timeout), then under it: store absent →
     `PRUNED:absent`; own-root realpath guard; `find -maxdepth 1 -type f` rm (also
     `.holder.lock`); `rmdir`; release. Never `rm -rf`.
   - Test seam: when `AITASK_SCRATCHPAD_PAUSE_FIFO` is set, `open` pauses after its
     task check and `save` after its existence check (read one line from the fifo).
2. `aitask_archive.sh`: `prune_scratchpad` beside `prune_shadow_rejections`
   (dry-run → `[dry-run] Would prune scratchpad for t<id>`; best-effort `|| true`),
   called next to it at all three sites (`archive_parent`, `archive_child`, parent
   auto-archive). **Folded decision:** `handle_folded_tasks` also prunes the folded
   task's scratchpad (non-dry-run branch after `task_git rm`; dry-run logs) because
   the folded task file is deleted there; shadow pruning there stays out of scope.
3. `aitask_setup.sh`: `setup_scratchpad_gitignore` cloned from
   `setup_shadow_store_gitignore`, registered right after it in `main()`; repo
   `.gitignore` gets the comment + `.aitask-scratchpad/`.
4. Tests: `tests/test_scratchpad_store.sh` (open NO_TASK/OPENED, save round trip,
   empty save, prune own-root guard with a symlinked store → exit 4, `../evil` id →
   exit 2, externally held lifecycle lock → prune `LOCK_BUSY` and deletes nothing,
   concurrent saves serialized + negative control; **interleavings via the pause
   fifo:** `open` paused after its task check, then archive-style move + `prune`
   started (prune blocks until open finishes, then removes the store — nothing
   survives); `save` paused after its existence check while `prune` waits → save
   lands, prune removes it, a following `save` → `ARCHIVED` and no dir is recreated;
   `prune` first, then a paused `save` → `ARCHIVED`; **first open vs archive:** no
   store yet, `open` paused after its task check (before `mkdir`), move + `prune`
   started → prune must wait for the lock and then remove the new store (control: an
   absence check moved before the lock leaves the store behind); **save with a
   surviving directory:** task file moved, store dir left in place → `save` refuses
   `ARCHIVED`; **holder vs prune:** after prune, opening `.holder.lock` without
   `O_CREAT` fails and nothing appears in the store root; **identity key:** `path`
   output identical before and after the root and store exist, for a relative root,
   a nonexistent absolute `AITASK_SCRATCHPAD_DIR`, and a root under a symlinked
   ancestor; `..` in the root → exit 2); `tests/test_archive_scratchpad_prune.sh`
   modelled on `test_archive_shadow_prune.sh` (parent, child, auto-parent, folded,
   `--dry-run` byte-identical, decoy store survives); `test_setup_git.sh` heredoc row.

## Step 9 (Post-Implementation)
Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: low
- New self-contained helper modelled on a tested sibling; archive hooks are best-effort one-liners next to existing ones · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Lifecycle races between open/save and archival prune could resurrect an archived store · severity: medium · → mitigation: none (external lifecycle lock, all prune checks under it, save's active-task check, pause-fifo interleaving tests)
