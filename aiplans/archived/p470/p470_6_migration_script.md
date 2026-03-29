---
Task: t470_6_migration_script.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_2_*.md, aitasks/t470/t470_3_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_6: Migration Script

## Overview
Create a standalone script that migrates archive storage to the new tar.zst scheme via `ait migrate-archives`.

Behavior split:
- Numbered archives (`_b*/old*.tar.gz`) convert in place to `.tar.zst`
- Legacy root archives (`old.tar.gz`) are unpacked and rebucketed into numbered `_bN/oldM.tar.zst` bundles

## Step 1: Add `.aitask-scripts/aitask_migrate_archives.sh`

Implement:
- argument parsing for `--dry-run`, `--delete-old`, `--verbose`, `-h/--help`
- numbered archive conversion with verification and optional source deletion
- legacy root archive rebucketing based on parent task id, preserving child subdirectory paths
- merge support when rebucketing into an existing `.tar.zst` numbered bundle
- summary counters: `found`, `converted`, `skipped`, `failed`

## Step 2: Add `migrate-archives` to `ait`

Update help text and dispatch routing so `./ait migrate-archives ...` executes the new script.

## Step 3: Add automated coverage

Create `tests/test_migrate_archives.sh` covering:
- syntax and help output
- numbered archive dry-run and real conversion
- `--delete-old` cleanup for numbered archives
- legacy task archive rebucketing
- legacy plan archive rebucketing
- merge into an existing `.tar.zst` bundle
- skip behavior when target `.tar.zst` already exists
- dispatcher routing through `./ait`

## Step 4: Verify

```bash
shellcheck .aitask-scripts/aitask_migrate_archives.sh
bash tests/test_migrate_archives.sh
./ait migrate-archives --dry-run
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.

## Final Implementation Notes
- **Actual work done:** Added `.aitask-scripts/aitask_migrate_archives.sh`, wired `migrate-archives` into `ait`, and added `tests/test_migrate_archives.sh`. The command converts numbered tar.gz archives to tar.zst and rebuckets legacy `old.tar.gz` task/plan archives into numbered `.tar.zst` bundles.
- **Deviations from plan:** The original plan only converted legacy root archives in place. During planning this was expanded so legacy `old.tar.gz` archives are rebucketed instead of producing `old.tar.zst`. Also added dedicated automated tests instead of relying only on manual verification.
- **Issues encountered:** `shellcheck` needed inline `SC1091` suppression for dynamic `source` paths. Also had to make skip behavior compatible with `--delete-old` so already-migrated `.tar.gz` files can still be cleaned up safely.
- **Key decisions:** Numbered archives are processed before legacy rebucketing so rebucketing can safely merge into existing `.tar.zst` targets and fail if a numbered `.tar.gz` still exists for the same bundle. Legacy source archives are only deleted after the full rebucketing operation succeeds.
- **Notes for sibling tasks:** `t470_7` can use `./ait migrate-archives --dry-run` to preview the real repo migration, then `./ait migrate-archives --delete-old` for final cleanup. The command already preserves child directory structure inside rebucketed bundles, so follow-up verification should focus on end-to-end archive readers and documentation.
