---
priority: high
effort: high
depends: [t2074_1]
issue_type: refactor
status: Ready
labels: [ait_setup, install, setup, git, data_integrity]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:31
updated_at: 2026-10-20 17:01
---

## Context

Part of t2074 (rescoped: **branch-mode layout hardening**; legacy mode stays
supported and **unchanged**). This child makes `ait setup` detect damaged
branch-mode layouts and repair them safely. The binding contract is **C4** and
the **bounded worktree repair** in
`aiplans/p2074_branch_mode_layout_hardening.md`. Read both first.

Depends on t2074_1 (classifiers).

**Unchanged:** the legacy decline prompt (`aitask_setup.sh:1643-1658`), the
legacy fallbacks, and the legacy migration.

## Implementation

1. **Replace the :1571 shortcut** in `setup_data_branch`.
   - Read both classifiers before any write.
   - "Configured" means C1a `branch` **and** C1b `ready`.
   - If C1a is `branch` but C1b is not `ready`, dispatch on C1b:
     - `dangling`, `misdirected` or absent links → link repair;
     - `mixed`, or a real file at a link path → refuse;
     - `unlinked` → `--link-worktree` guidance.
   - If C1a is not `branch`, dispatch on C1a.
2. **`ait_repair_data_links <root> <data> [--with-data-link]`.** Extract it
   from the two-phase `ait_link_worktree_data` (`lib/data_symlinks.sh:190`).
   - **Preflight:** report every real-file or real-dir conflict, and change
     nothing.
   - **Apply:** repoint mismatched links (the raw literal for
     `aitasks`/`aiplans`, the canonical target for `.aitask-data`), create
     absent links, and warn with the old target. Never touch the old target's
     contents.
   - Do not use `ait_ensure_data_symlinks`: it keeps resolving links.
   - `--link-worktree` keeps its `LINKED` / `ALREADY_LINKED` / exit-2
     contract.
3. **Refuse, with move-aside steps that never delete:** `foreign_repo`,
   `wrong_branch`, `mixed`, unique files in a stale dir, and `indeterminate`.
4. **Bounded worktree repair** for `stale_marker` and `missing_storage`.
   **Never run `git worktree prune`**: it is repository-wide.
   - **Identify** the single record whose path canonicalizes to
     `<root>/.aitask-data`. Cross-check `<common>/worktrees/<name>/gitdir`.
   - **Case (A): no registration, and `aitask-data` is not checked out
     anywhere.**
     1. The path must be absent or an empty dir.
     2. The branch must exist locally, or be fetched from origin as in
        `setup_data_branch` Step 1.
     3. Run an **ordinary** `git worktree add` (setup Step 2), then repair the
        links.
     4. If there is no branch, refuse with restore instructions.
   - **Case (B): exactly one registration.** Run a read-only preflight first.
     Proceed only if all three hold:
     - `GIT_INDEX_FILE=<admin>/index git --git-dir=<common> diff-index --cached --quiet refs/heads/aitask-data`
       succeeds. A missing or unreadable index counts as a failure.
     - `_ait_inprogress_state_at <admin>` reports nothing.
     - `<admin>/HEAD` is `ref: refs/heads/aitask-data`.

     If the preflight fails, refuse, change nothing, and print these steps in
     order: restore the dir or run `git worktree repair <moved path>`; inspect
     with `GIT_INDEX_FILE=<admin>/index git diff --cached aitask-data`; only
     then remove the registration by hand. No backup mechanism is added.
   - **Every other case:** refuse. This covers multiple records, a `locked`
     record, or the branch checked out by a different registration.
   - **Re-registration** uses `git worktree add --force <root>/.aitask-data aitask-data`
     with a single `--force`, never two. A dir that was moved back is
     re-linked with `git worktree repair <root>/.aitask-data`.
   - **Confirmation for `missing_storage` case (B):** interactive runs must
     confirm with the prompt "if you moved `.aitask-data`, answer no and
     restore it instead". Non-interactive runs refuse.
   - **Probe table:** measure what `add --force` does to the same path's admin
     dir, and whether `repair` touches other records. Pin the result in a
     test. If git cannot replace exactly one registration, drop the automatic
     path and refuse.
5. **Missing-storage messages:**
   - a branch exists → run `ait setup`;
   - no branch → restore from a backup or another clone;
   - row-1 mixed → refuse to touch the real dir, and print compare-and-merge
     steps.

## Tests

- **Same-fixture recovery.** For every C4 row: refuse, recover, then re-read
  the classifiers and get `branch`/`ready`.
- **"Configured".** A misdirected primary link is not "already configured" and
  gets repaired.
- **Misdirected link to an existing dir.** The final target is the literal,
  and the old dir's manifest is byte-identical.
- **Real-dir conflict.** Refused, nothing changed.
- **Case (A):**
  - (i) a local branch: ordinary add gives `branch`/`ready`, and the tip is
    unchanged;
  - (ii) a remote-only branch: fetched, then restored;
  - (iii) no branch: refused, nothing changed;
  - (iv) a non-empty `.aitask-data` without `.git`: refused.
- **Case (B) preservation.** With the dir moved aside, test (a) staged ≠
  working ≠ tip, (b) `MERGE_HEAD` or `rebase-merge` present in the admin dir,
  and (c) a detached HEAD.
  - Each is refused, and the admin dir (index included) is byte-identical.
  - The moved copy still re-links via `git worktree repair`, and its staged
    change is still in `git diff --cached`.
  - Positive control: with a clean index the repair proceeds after
    confirmation, and refuses when non-interactive.
  - Missing `index` or `HEAD`: refused, nothing changed.
  - Planted control: an unguarded `add --force` on (a) must fail the manifest
    comparison.
- **Two-worktree isolation.** The data dir is deleted, and an unrelated linked
  worktree is moved aside with staged changes.
  - After repair, the unrelated admin dir is byte-identical in every file,
    index included. It is still listed and still re-links.
  - Planted control: a plain `git worktree prune` must fail this comparison.
- **Legacy stays green.** `tests/test_data_branch_setup.sh` (decline and
  fallbacks unchanged) and the `tests/test_init_data.sh` link cases.

## Verification

- `bash tests/test_data_branch_setup.sh`, `bash tests/test_init_data.sh`, and
  the new repair tests.
- `shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/data_symlinks.sh`.
