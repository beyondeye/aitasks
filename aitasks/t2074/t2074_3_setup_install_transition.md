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
updated_at: 2026-10-20 12:34
---

## Context

This is part of t2074, which removes legacy repository mode. Setup becomes the
**only** converter and the repair tool. The binding contract is **C4** (the
recovery matrix), C1a/C1b and C6 in
`aiplans/p2074_remove_legacy_repository_mode_support.md`; read them first.

User decision: existing legacy installs are refused at runtime and told to run
`ait setup`. Setup migrates, using the existing fail-closed `needs_migration`
path. Declining the migration aborts setup and changes nothing. `ait upgrade`
installs files and prints a notice; it **never** migrates.

Depends on t2074_1 (the classifiers).

## Current state

In `.aitask-scripts/aitask_setup.sh::setup_data_branch` (1563-2057):
- :1571 reports "already configured" as soon as `.aitask-data/.git` exists.
- :1643-1658 is the `[Y/n]` opt-out prompt; a decline returns with the legacy
  layout left in place.
- These failures fall back to the legacy layout:
  - :1716-1721 (fetch failure)
  - :1747-1764 (worktree add)
  - `abort_data_branch_setup` (:1485, called from :1779/:1785/:1899/:1919)
- `_ait_data_branch_exclude_re` (:4244) and `commit_framework_data_files`
  (:4479) have legacy early returns.

In `install.sh`:
- `create_data_dirs` (:517) creates a real `aitasks/` before setup. That is
  fine: setup migrates it.
- `ensure_data_root` (:457-511) turns a dangling link into a real dir.
- :1244 and :1500 are legacy early returns.

`aitask_upgrade.sh` delegates to `install.sh --force` (:152).

## Implementation

1. Replace the :1571 shortcut. Read both classifiers before any write.
   - **Configured** means C1a = `branch` and C1b = `ready`.
   - When C1a = `branch` and C1b is not `ready`, dispatch on C1b:
     - repair the primary links for `dangling`, `misdirected` or absent;
     - refuse on a conflict (`mixed`, or a real file at a link path);
     - give `--link-worktree` guidance for `unlinked`.
   - When C1a ≠ `branch`:
     - `uninitialized`: create the branch.
     - `legacy`: migrate, with one confirmation. A decline exits non-zero
       with "task data unchanged; legacy layout unsupported".
     - `broken:stale_marker` with no unique files: prune or repair, then
       re-add.
     - `foreign_repo`, `wrong_branch`, unique files in a stale dir, and
       `indeterminate:topology`: refuse, change nothing, and print exact
       move-aside steps that never delete.
2. Extract the two-phase preflight/apply logic of `ait_link_worktree_data`
   (`lib/data_symlinks.sh:190`) into a shared
   `ait_repair_data_links <root> <data> [--with-data-link]`. Use it from both
   `--link-worktree` and setup's primary repair.
   - It **repoints** misdirected links. `ait_ensure_data_symlinks` keeps any
     resolving link, so do not use it for repair.
   - It refuses every real file or dir conflict before changing anything.
   - `--link-worktree` keeps its `LINKED` / `ALREADY_LINKED` / exit-2 contract.
3. Remove the fresh-setup `[Y/n]` opt-out; nothing remains to decline.
   Non-interactive runs auto-accept, as now.
4. The fallbacks at 1716, 1747 and in `abort_data_branch_setup` become teardown
   followed by a **non-zero setup exit**, with the originals intact.
5. Keep the exclude-regex and data-commit early returns only as pre-conversion
   guards, and fix their comments.
6. In `install.sh`, `ensure_data_root` refuses instead of creating a real dir,
   pointing to `ait setup`. A legacy project gets a prominent conversion notice
   on install and upgrade, and no migration.
7. A missing `origin` stays fully supported: the local orphan branch is created
   and pushes are skipped.
8. Send a note to t1619 (its "decline branch" checklist item is now obsolete),
   with the committed SHA.

## Tests

- `tests/test_data_branch_setup.sh`:
  - Tests 26, 26b, 27 and 31 now also assert the non-zero exit.
  - T14 and T23 (legacy fallback wording) become refusal assertions.
  - T5 and T25 (no remote, unreachable remote) stay green.
- `tests/test_install_create_data_dirs.sh` T2/T4 become refusal.
- `tests/test_t644_branch_mode_upgrade.sh` scenario C: the upgrade prints the
  notice and leaves the data unchanged.
- `tests/test_setup_hooks_only.sh` and `tests/test_agent_instructions.sh` T43:
  update them.
- **"Configured" test:** a valid data worktree with a misdirected primary
  `aitasks` link must not report "already configured", and must be repaired.
- **Recovery tests**, on the same damaged fixture: refusal, then the advertised
  recovery, then re-read both classifiers, which must say `branch` / `ready`.
  - Cover every C4 row.
  - A misdirected link to an existing dir: the final target is the expected
    literal, and the old target's content manifest is byte-identical.
  - A real-dir conflict: refused, nothing changed.
  - An unlinked crew worktree: `--link-worktree`, then `ready`.
  - Every "refuse" row asserts nothing changed, by comparing a before/after
    content manifest (type, symlink target, mode, sha256) and the git
    snapshots.

## Verification

- `bash tests/test_data_branch_setup.sh`
- `bash tests/test_init_data.sh`
- `bash tests/test_install_create_data_dirs.sh`
- `bash tests/test_t644_branch_mode_upgrade.sh`
- `bash tests/test_setup_hooks_only.sh`
- `bash tests/test_agent_instructions.sh`
- `shellcheck .aitask-scripts/aitask_setup.sh install.sh`
- by hand: a fresh `ait setup` in a temp repo, once with `origin` and once
  without
