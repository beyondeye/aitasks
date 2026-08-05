---
Task: t1427_1_rejection_store_helper.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_2_picker_reject_tristate.md, aitasks/t1427/t1427_3_producer_suppression_rule.md, aitasks/t1427/t1427_4_rejection_docs.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# p1427_1 — Rejection store + `aitask_shadow_rejected.sh` helper

Substrate spike for t1427: the durable per-task concern-rejection store, its
single writer/reader helper, gitignore installation, archive-time pruning, and
whitelist registration. Parent plan
`aiplans/p1427_reject_shadow_concerns_suppress_next_round.md` "Architecture"
section is binding; this plan restates the needed parts so it is
self-contained.

## Store format

`.aitask-shadow/<task_id>/rejected.md` — bare task id (`1427`, `1427_2` — no
`t` prefix, matching `.aitask-gates/`), repo-root-relative, lazy `mkdir -p` by
the writer, git-ignored, never committed. One entry block per rejection:

```markdown
### r<N> | <ISO-8601 UTC> | producer: <name|unknown>
- [<priority> | <region>] <body>
```

`r<N>` is monotonic (max existing + 1). The canonical marker line is stored
verbatim (the shadow matches against the full text). Blocks separated by one
blank line.

## Steps

1. **`.aitask-scripts/aitask_shadow_rejected.sh`** (new; `#!/usr/bin/env
   bash`, `set -euo pipefail` — read `aidocs/framework/shell_conventions.md`
   first). Sources `terminal_compat.sh`, `lib/task_utils.sh`,
   `lib/registry_lock.sh`, `lib/atomic_write.sh`.
   - Task-id validation copied from `aitask_shadow_context.sh:59-86`: strip
     leading `t`, require `^[0-9]+(_[0-9]+)?$`, `die` on malformed (the one
     hard error). Store path `.aitask-shadow/${task_id}/rejected.md`; lock dir
     `"${store_file}.lockd"` (derived from the data path, per
     `aitask_agent_marks.sh:51`).
   - Exit-code contract (copy `aitask_agent_marks.sh:31-34`): 0 ok, 2 usage,
     3 LOCK_BUSY (nothing written), 4 error. Lock-or-busy wrapper modeled on
     `aitask_agent_marks.sh:75-83` (`mkdir -p` the parent, then
     `registry_lock_acquire "$LOCK_DIR" "$timeout" || { echo LOCK_BUSY; exit 3; }`).
     Release is via the acquire-installed EXIT trap — but note
     `atomic_write.sh` deliberately installs no EXIT trap, so there is no
     conflict.
   - `add <task_id> [--producer <name>]` — reads canonical marker lines from
     stdin; each non-empty line MUST match the marker shape (`^- \[` at
     minimum; reuse the grammar loosely — full parse is the Python parser's
     job). Sanitize `--producer` at the write site: reject/strip `|` and
     newlines (delimited-encoding rule: undecidable on read). Locked RMW:
     acquire lock → read current file (missing = empty) → compute next `r<N>`
     → render ENTIRE new content through `ait_atomic_render` (renderer:
     `printf` existing content + new blocks; every fallible command
     `|| return 1`; renderers must not rely on `set -e`). Output `ADDED:<n>`.
   - `list <task_id> [--machine]` — NO lock (atomic rename gives
     whole-old-or-whole-new reads). Default: print the store file verbatim
     (shadow prompt context). `--machine`: emit one
     `REJECTED:<id>|<ts>|<producer>|<marker line>` per entry — marker line
     LAST (it contains `|`; consumers use `split('|', 3)`). Empty/missing
     store → single line `NO_REJECTIONS`. All resolution outcomes exit 0
     (line-protocol convention of `aitask_shadow_context.sh`).
   - `remove <task_id> <id>...` — locked RMW; drop the named entry blocks;
     output `REMOVED:<csv>` for found ids and `NOT_FOUND:<csv>` for missing
     ones (both lines may appear). Ids accepted with or without the `r`
     prefix; normalize.
   - `prune <task_id>` — lock-coordinated delete of the whole task store dir:
     1. Own-root safety first (pattern `aitask_explain_cleanup.sh:57-85`):
        `base=$(realpath .aitask-shadow …)`, `canonical=$(realpath <dir>)`,
        refuse unless `canonical == "$base"/<task_id>` (prefix check).
        Missing dir → `PRUNED:absent`, exit 0.
     2. Acquire the same registry lock (short timeout, e.g. 5s). Busy →
        `LOCK_BUSY`, exit 3, delete NOTHING.
     3. Under the lock: `rm -f` the store file(s) but NOT the held `.lockd`.
     4. `registry_lock_release` (removes the `.lockd`).
     5. Finish with plain `rmdir "<dir>" 2>/dev/null || true` — never
        `rm -rf` — so a concurrent waiter's freshly re-created lock survives
        (dir is then left behind, re-prunable). Output `PRUNED:<task_id>`.
     A post-prune `add` lazily recreating the dir is accepted and documented
     in the helper header comment.
2. **`aitask_setup.sh`**: add `setup_shadow_store_gitignore()` directly after
   `setup_gate_logs_gitignore` (~line 1987), same shape (`grep -qxF
   ".aitask-shadow/"` idempotence; append with rationale comment
   `# Shadow concern-rejection store (per-task, local-only; pruned at archive)`;
   best-effort `git add/commit … || true`). Call it in the main sequence right
   after `setup_gate_logs_gitignore` (~line 3719), separated by `echo ""`.
3. **Repo-root `.gitignore`**: add the comment + `.aitask-shadow/` line next
   to `.aitask-gates/` in the same commit (setup functions only install into
   OTHER projects / fresh clones).
4. **`aitask_archive.sh`**: in `archive_parent` (after `release_lock`,
   ~line 250) and `archive_child` (same position in its flow), add:
   `"$SCRIPT_DIR/aitask_shadow_rejected.sh" prune "$task_num" 2>/dev/null || true`
   (best-effort; a LOCK_BUSY prune leaves the store for a later prune —
   archival never blocks).
5. **Whitelist**: `./.aitask-scripts/aitask_audit_wrappers.sh
   apply-helper-whitelist aitask_shadow_rejected.sh`, then
   `audit-helper-whitelist aitask_shadow_rejected.sh` must report no MISSING
   (5 touchpoints; alphabetical insertion lands after
   `aitask_shadow_context.sh`).
6. **`tests/test_shadow_rejected.sh`** (new; self-contained, `assert_eq` /
   `assert_contains` helpers + PASS/FAIL summary like sibling bash tests; run
   in a temp repo root so `.aitask-shadow/` never touches the real one):

   ### Pre-phase (risk mitigations)
   1. **[contended_append_negative_control]** Two-writer contention: launch
      two `add` invocations concurrently (background jobs, distinct marker
      lines), wait, then assert BOTH entries are present with distinct ids
      (no lost update). Negative control: re-run with lock acquisition
      bypassed (e.g. stub `registry_lock_acquire` to a no-op via a sourced
      override or an env-controlled test hook) and prove the suite exits 1 —
      document the negative-control run in Final Implementation Notes.

   Then: add/list round-trip; `--machine` protocol with `|`-laden bodies
   (split-last-field survives); remove found/not-found; malformed-id refusal
   (exit ≠ 0); LOCK_BUSY path (hold the lock in a background process, assert
   `add` exits 3 and writes nothing); prune own-root refusal (negative
   control: attempt prune with a crafted traversal id fails validation
   before any deletion); prune-vs-add coordination (hold lock via a
   backgrounded add-in-progress or manual `registry_lock_acquire`, assert
   `prune` exits 3 and the store survives); `NO_REJECTIONS` sentinel. Each
   regression assertion proven able to exit 1 (flip one expected value during
   development — do not commit the flip).

## Reference patterns (read before writing code)

- `aitask_agent_marks.sh:31-83` — exit codes, lock derivation, lock-or-busy.
- `aitask_gate_pass.sh:91-107` — `ait_atomic_render` renderer shape (explicit
  `if`, never `[[ … ]] && echo` as the final command).
- `registry_lock.sh:44-88` — acquire/steal/release semantics (mkdir mutex,
  owner token, dead-PID-only steal).
- `atomic_write.sh` header comments — reader-visible atomicity is NOT writer
  serialization; that is exactly why every mutation here holds the lock.
- `aitask_explain_cleanup.sh:22-92` — own-root + marker guards for deletion.
- `aidocs/framework/aitasks_extension_points.md` — before touching
  `aitask_setup.sh` / the install flow.

## Verification

- `bash tests/test_shadow_rejected.sh` — all green; summary printed.
- `shellcheck .aitask-scripts/aitask_shadow_rejected.sh` clean.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist
  aitask_shadow_rejected.sh` — no MISSING lines.
- Manual smoke: `echo '- [high | test region] body' |
  ./.aitask-scripts/aitask_shadow_rejected.sh add 9999 --producer manual`,
  `list 9999`, `list 9999 --machine`, `remove 9999 r1`, `prune 9999`; confirm
  `.aitask-shadow/` is git-ignored throughout (`git status --porcelain` empty).

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
