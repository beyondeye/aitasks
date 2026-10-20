---
Task: t2073_2_scratchpad_app.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
---

# t2073_2 — scratchpad_app

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
  and on SIGHUP (best-effort). **On a hard kill, changes not included in the latest
  successfully saved buffer may be lost, including edits queued during a pending
  save.** Autosave targets starting within roughly three seconds when no save is
  pending; this is not a maximum loss window. The helper's 5 s figure bounds only
  its lock wait; no save duration is bounded (t2073_1).
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

### t2073_2 — scratchpad_app (`ait scratchpad`)
Depends on t2073_1. No shared dirty file.
1. `.aitask-scripts/scratchpad/__init__.py`, `scratchpad_app.py`: sys.path setup as
   `frozenagent_app.py`; `ScratchpadApp(ShortcutsMixin, App)`,
   `_shortcuts_scope = "scratchpad"`. CLI: `--task <id>` or `--unsaved`, optional
   `--target <pane>` (header only). Layout: one-line header (`t<id> · saved|saving…|
   unsaved changes|NOT SAVED (no task)|read-only: open elsewhere|not saved — store
   removed`) + a `TextArea` subclass whose `action_copy` routes the selection (whole
   buffer when nothing selected) through `tui_clipboard.copy_to_system_clipboard`
   (never `app.copy_to_clipboard`). Bindings (modifier keys only; letters go to the
   editor): `ctrl+s` save now, `ctrl+q` quit (flush first), `ctrl+c` copy;
   `ctrl+v`/bracketed paste from TextArea.
2. Persistence, in this order on mount: `open` via the store helper (asyncio
   subprocess seam shaped like `monitor_shared._run_rejected_cmd`, timeout, never
   raises) → `os.open(<store>/.holder.lock, O_RDWR)` (no `O_CREAT`; missing → "not
   saved — task archived", no writes) → `fcntl.flock(LOCK_EX|LOCK_NB)` → **only then**
   read `notes.md` into the editor. `ARCHIVED`/`ABSENT` from a later save switches the
   header to "not saved — task archived" and stops autosave. Busy → read-only path (snapshot read,
   `read_only=True`, no saves ever, no later promotion). Autosave per "Autosave with a
   deadline": `TextArea.Changed` records `last_change` (and `first_unsaved_change`
   when clean) and re-arms one `set_timer` at `min(last+1.0, first+3.0)`; `save` pipes
   text to the helper with `pass_fds=(holder_fd,)`; serialized with a dirty flag;
   flush on `ctrl+q`/unmount and SIGHUP (best-effort). Unsaved mode never calls the
   helper and takes no lock.
3. `.aitask-scripts/aitask_scratchpad.sh` cloned from `aitask_frozenagent.sh`; `./ait`
   help line, case entry and update-check skip list (next to `frozenagent`);
   `lib/tui_registry.py` `("scratchpad", None, None, False)`;
   `lib/shortcut_scopes.KNOWN_BINDING_SOURCES` entry; `tests/test_no_lib_to_tui_import.sh`
   `TUI_PACKAGES`; `tests/test_shortcuts_registry_coverage.sh` `TUIS`.
4. Tests: `tests/test_scratchpad_app.py` (run_test, `AITASK_SCRATCHPAD_DIR` tmp: loads
   existing notes; typing saves after the debounce; **continuous typing at 0.2 s
   intervals for 5 s produces a save within 3 s of the first edit** while no save
   is pending (a start target, not a maximum loss window) (and a control
   with the deadline disabled shows none — proves the deadline, not the debounce,
   saved); serialized saves; unsaved mode writes nothing; holder-lock busy →
   read-only and never saves; **ownership-before-read handoff:** patch the flock
   acquisition to write newer content to `notes.md` immediately before it returns and
   assert the editor shows the newer content (a read-before-lock implementation shows
   the stale one — negative control); the save subprocess receives the holder fd;
   ABSENT → header says not saved; copy calls `copy_to_system_clipboard` — patched);
   `tests/test_scratchpad_autosave_live.sh` (isolated tmux per
   `tests/lib/tmux_isolation.sh`: (a) send-keys text, wait > debounce, `kill-pane`,
   assert notes.md has it; (b) send a token every 0.2 s for 6 s without pausing, then
   `kill-pane` immediately, assert every token sent more than 3 s + save latency before
   the kill is on disk; (c) control: kill before the first deadline leaves the old
   content — documents the window);
   `test_tui_clipboard_seam.sh` still passes.

## Step 9 (Post-Implementation)
Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: low
- New isolated TUI package; registry/dispatcher edits are additive · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Autosave must survive a hard pane kill within the stated window (a hard kill may lose changes not included in the latest successfully saved buffer, including edits queued during a pending save; the ~3 s autosave start target (no save pending) is not a maximum loss window); timer behaviour under continuous typing is the failure mode · severity: medium · → mitigation: none (max-dirty-age deadline + continuous-typing unit and live hard-kill tests)
- Writer ownership must precede the first read, or a successor can overwrite newer notes · severity: medium · → mitigation: none (flock-before-read order, pass_fds on saves, handoff test with negative control)
