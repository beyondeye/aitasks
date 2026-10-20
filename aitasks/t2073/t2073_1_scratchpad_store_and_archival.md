---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [scratchpad]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2073
implemented_with: claudecode/opus5_5
created_at: 2026-10-20 10:31
updated_at: 2026-10-20 11:15
---

## Context

Child of t2073 (minimonitor scratchpad pane). The scratchpad is a notes editor pane
bound to a followed code agent. For aitask agents its notes persist per task and are
dropped when the task is archived. This child builds the **persistence layer only**:
a bash store helper, archival pruning and the setup gitignore rule. The Textual app
(t2073_2) and the minimonitor key (t2073_4) consume it. Full design and the reasons
behind each rule: `aiplans/p2073_minimonitor_scratchpad_pane.md` ("Store", "One writer
per store", "Store lifecycle").

This child touches none of the files another in-flight task is editing, so it can
start immediately.

## Key Files to Modify

- NEW `.aitask-scripts/aitask_scratchpad_store.sh` — verbs `open`, `save`, `path`,
  `prune`; store `${AITASK_SCRATCHPAD_DIR:-.aitask-scratchpad}/<id>/notes.md`.
- `.aitask-scripts/aitask_archive.sh` — `prune_scratchpad` beside
  `prune_shadow_rejections` (~:203); call it at the three sites (`archive_parent`
  ~:274, `archive_child` ~:516, parent auto-archive ~:569) and in
  `handle_folded_tasks` (~:322; non-dry-run branch after `task_git rm`, dry-run logs).
- `.aitask-scripts/aitask_setup.sh` — `setup_scratchpad_gitignore` cloned from
  `setup_shadow_store_gitignore` (~:2898), registered right after it in `main()` (~:5111).
- `.gitignore` — comment + `.aitask-scratchpad/` next to `.aitask-shadow/` (~:27).
- NEW `tests/test_scratchpad_store.sh`, NEW `tests/test_archive_scratchpad_prune.sh`,
  `tests/test_setup_git.sh` (Test 27 HELPERS heredoc ~:834-841, add a row).

## Reference Files for Patterns

- `.aitask-scripts/aitask_shadow_rejected.sh` — structure to copy (`resolve_task_id`
  :142, `store_paths_for` :157, `lock_or_busy` :166, `cmd_prune` :442). Do NOT copy
  `lock_or_busy`'s `mkdir -p "$STORE_DIR"`: here the lock lives outside the store.
- `lib/registry_lock.sh` (`registry_lock_acquire <dir> [timeout]` → 0 held / 1 busy),
  `lib/atomic_write.sh` `ait_atomic_render <file> <renderer_fn>` (refuses zero bytes).
- `tests/test_shadow_rejected.sh` (`hold_lock`/`release_held_lock` live-pid holder,
  env isolation), `tests/test_archive_shadow_prune.sh` (fake repo + bare remote,
  decoy store id 41, four cases).

## Implementation Plan

1. Store helper. No `task_utils.sh` (its EXIT trap conflicts with registry_lock).
   `LOCK_DIR="$SCRATCHPAD_DIR/.locks/$TASK_ID.lockd"`; `lock_or_busy` only
   `mkdir -p "$SCRATCHPAD_DIR/.locks"`. Exit codes 0 ok / 2 usage-bad id /
   3 LOCK_BUSY / 4 ERROR.
   - `open <id>`: under the lock, refuse `NO_TASK` unless the active task file exists
     (`${TASK_DIR:-aitasks}/t<id>_*.md`, or `t<p>/t<p>_<c>_*.md` for a child; shared
     `task_is_active`). Then `mkdir` the store, create `.holder.lock`, print
     `OPENED:<notes file>`.
   - `save <id>`: read stdin outside the lock, then under it: inactive task →
     `ARCHIVED`; store dir absent → `ABSENT` (both exit 0, never mkdir); empty
     buffer → remove notes.md → `SAVED:empty`; else `ait_atomic_render` →
     `SAVED:<bytes>`.
   - `path <id>`: print the identity key without creating anything:
     - make the root absolute (an absolute override is used as-is, a relative one is
       prefixed with `$PWD`; a `..` segment → exit 2);
     - walk up to the deepest existing ancestor and canonicalize it with
       `cd … && pwd -P` (portable; no `realpath -m`);
     - append the remaining components and `/<id>`.
     The key must be identical before and after the root and store are created.
   - `prune <id>`:
     - root absent → `PRUNED:absent` (the only exit before the lock);
     - otherwise take the lock (5 s timeout) and, under it: store absent →
       `PRUNED:absent`; own-root realpath guard (exit 4); `find -maxdepth 1 -type f`
       rm; `rmdir`; release.
     - Never `rm -rf`.
   - Test seam: when `AITASK_SCRATCHPAD_PAUSE_FIFO` is set, `open` pauses after its
     task check and `save` after its existence check (read one line from the fifo).
2. Archive hooks (`prune_scratchpad`: dry-run message
   `[dry-run] Would prune scratchpad for t<id>`; best-effort `|| true`), including
   folded tasks.
3. Setup gitignore helper and repo `.gitignore` line.

## Verification Steps

- `bash tests/test_scratchpad_store.sh`:
  - open NO_TASK / OPENED; save round trip; empty save;
  - own-root guard via a symlinked store → exit 4; `../evil` id → exit 2;
  - an externally held lock → prune LOCK_BUSY and deletes nothing;
  - concurrent saves serialized, with a negative control;
  - pause-fifo interleavings: open-vs-prune (including the first open, before any
    store exists, with a control showing that a pre-lock absence check leaves the
    store behind), save-vs-prune, prune-then-save → ARCHIVED;
  - save refuses ARCHIVED when the task file was moved but the dir survives;
  - after prune, opening `.holder.lock` without O_CREAT fails;
  - `path` is stable across creation for a relative root, a missing absolute
    override and a symlinked ancestor; `..` → exit 2.
- `bash tests/test_archive_scratchpad_prune.sh`: parent, child, auto-parent and
  folded archival prune; `--dry-run` leaves the store byte-identical; the decoy store
  survives.
- `bash tests/test_setup_git.sh`, `bash tests/test_shadow_rejected.sh`,
  `bash tests/test_archive_shadow_prune.sh`.
- `shellcheck .aitask-scripts/aitask_scratchpad_store.sh .aitask-scripts/aitask_archive.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T08:15:35Z status=pass attempt=1 type=human
