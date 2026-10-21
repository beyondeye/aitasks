---
Task: t2073_minimonitor_scratchpad_pane.md
Base branch: main
Output branch: main
---

# t2073 — Minimonitor scratchpad pane (decomposed into 5 children)

## Context

While driving a code agent the user wants a small notes editor bound to that agent,
so pasted fragments of agent/shadow output survive without scrolling back. It must
open from minimonitor in a vertical split of the followed agent pane, persist per
task for aitask agents, be dropped at archival, and behave like a bound helper pane
(never listed as an agent, closed with its agent, never keeps the minimonitor alive).
The folded t1388 bug (minimonitor `_find_sibling_pane_id` rung 2 is helper-blind) is
fixed by the same generalized helper rule.

User decisions (planning): split into 5 children; key **`o`**; non-task agents get an
**unsaved scratchpad** with a visible "not saved" marker; **minimonitor only** (full
monitor untouched).

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

## Children

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

### t2073_5 — scratchpad_docs (website)
Depends on t2073_4. Per `documentation_conventions.md` (current state only):
`website/content/docs/tuis/scratchpad/{_index,how-to,reference}.md` (what it is,
opening with `o`, placement + config, keys, storage path, persistence for aitask
agents, unsaved pads for others, archival drop, autosave + loss window, one pad per
task); `tuis/minimonitor/how-to.md` "How to Open a Scratchpad" next to the shadow
section + key quick reference + `_index.md`; `tuis/_index.md` and
`commands/_index.md` list `ait scratchpad`; `tuis/monitor/reference.md` tmux key table
rows; `tuis/frozenagent/how-to.md` note that a bound pad survives freeze/restore. Run
`hugo build --gc --minify` and `python3 check_links.py --build` in `website/`.

## Step 9 (Post-Implementation)
Each child archives through its own Step 9; the parent auto-archives with the last
child, which also deletes the folded t1388.

## Verification
Per child as listed; overall: `bash tests/test_cleanup_rule_parity.sh`,
`bash tests/test_scratchpad_store.sh`, `bash tests/test_archive_scratchpad_prune.sh`,
`bash tests/test_scratchpad_autosave_live.sh`, `bash tests/test_scratchpad_spawn_live.sh`,
`bash tests/run_all_python_tests.sh` (read the last line), `shellcheck` on new/changed
scripts, `bash tests/test_tui_clipboard_seam.sh`, `bash tests/test_no_raw_tmux.sh`,
website `check_links.py --build`.

## Risk

### Code-health risk: medium
- The helper rule is changed in discovery, `classify_window_panes`, the cleanup hook and the auto-spawn occupancy count together; a missed copy, or an arity set not widened, silently drops every pane or keeps the minimonitor alive · severity: medium · → mitigation: none (covered in t2073_3 by the parity table, the arity test and the bash/Python option tripwire)
- `minimonitor_app.py` is edited while t2065 has uncommitted hunks in it · severity: medium · → mitigation: none (pre-edit gate in t2073_3/t2073_4 step 0)

### Goal-achievement risk: medium
- Bound helpers (shadow and scratchpad) survive direct `kill-pane` paths (`kill_agent_pane_smart`'s pane branch, frozen-record drop) because no `pane-died` fires; "closed when its agent dies" holds only for agent exit and the hook path · severity: medium · → mitigation: kill_bound_helpers_on_direct_kill
- The autosave loss window relies on the save timer firing inside a live Textual loop; a hard kill may lose changes not included in the latest successfully saved buffer, including edits queued during a pending save; the ~3 s autosave start target (no save pending) is not a maximum loss window · severity: low · → mitigation: none (stated window + continuous-typing and hard-kill tests in t2073_2)
- Store lifecycle races (open/save/app-holder vs archival prune) could resurrect an archived task's store · severity: low (residual — addressed by the external per-task lifecycle lock, all prune checks under it, open-only holder creation, save's active-task check and the move-before-prune order, with pause-fifo interleaving tests in t2073_1) · → mitigation: none

### Planned mitigations
The parent never runs Step 8d once it is decomposed, so this `after` line is carried
verbatim into `aiplans/p2073/p2073_4_minimonitor_scratchpad_key.md`. That child's
Step 8d creates it.

- timing: after | name: kill_bound_helpers_on_direct_kill | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: bound helpers survive direct kill-pane paths | desc: Kill panes bound to an agent (shadow/scratchpad target options) when kill_agent_pane_smart's pane branch or a frozen-record drop kills that agent directly, with tests for both paths
