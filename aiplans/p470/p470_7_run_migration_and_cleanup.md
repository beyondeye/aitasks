---
Task: t470_7_run_migration_and_cleanup.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_4_*.md, aitasks/t470/t470_5_*.md, aitasks/t470/t470_6_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_7: Run Migration and Final Cleanup

## Overview
Execute the migration on this repo's 10 archives, verify, update docs, delete old files.

## Step 1: Run migration

```bash
./ait migrate-archives --verbose
```

Expected: converts `old{0-4}.tar.gz` → `old{0-4}.tar.zst` in both `aitasks/archived/_b0/` and `aiplans/archived/_b0/`.

## Step 2: Verify archives

```bash
for f in aitasks/archived/_b0/old*.tar.zst aiplans/archived/_b0/old*.tar.zst; do
    zstd -dc "$f" | tar -tf - > /dev/null && echo "OK: $f" || echo "FAIL: $f"
done
```

## Step 3: Run full test suite

```bash
bash tests/test_archive_utils.sh
bash tests/test_archive_scan.sh
bash tests/test_resolve_tar_zst.sh
bash tests/test_zip_old.sh
bash tests/test_query.sh
bash tests/test_claim_id.sh
bash tests/test_t167_integration.sh
python3 -m pytest tests/test_archive_iter_consolidated.py -v
python3 -m pytest tests/test_aitask_stats_py.py -v
```

## Step 4: Update documentation

- `CLAUDE.md` line 54: `old.tar.gz` → `old.tar.zst`
- `CLAUDE.md` test list: rename `test_resolve_tar_gz.sh` → `test_resolve_tar_zst.sh`

## Step 5: Delete old tar.gz files

```bash
./ait migrate-archives --delete-old
# Or manually:
rm -f aitasks/archived/_b0/old*.tar.gz aiplans/archived/_b0/old*.tar.gz
```

## Step 6: Commit and push

- Stage converted archives and doc changes
- Commit with appropriate message
- Push

## Step 7: Final verification

```bash
# No tar.gz files remain
find aitasks/archived aiplans/archived -name "*.tar.gz" | wc -l  # should be 0
# Backward compat code still present for downstream repos
grep -r "tar\.gz" .aitask-scripts/ | grep -v "^Binary" | head -20
```

## Step 9 Reference
Post-implementation: user review, commit, archive parent task, push.

## Final Implementation Notes
- **Actual work done:** Claimed `t470_7`, ran `./ait migrate-archives --verbose`, converted all 10 numbered archive bundles to `.tar.zst`, verified every produced bundle with `zstd -dc | tar -tf -`, updated `CLAUDE.md` to describe `.tar.zst` archive storage, then ran `./ait migrate-archives --delete-old` to remove the old numbered `.tar.gz` sources.
- **Deviations from plan:** The two Python tests were validated with `python3 -m unittest discover ...` instead of `python3 -m pytest ...` because `pytest` is not installed in this environment. The repo already supports this fallback pattern for Python tests.
- **Issues encountered:** `./ait migrate-archives --delete-old` reports existing numbered `.tar.zst` targets as "Skipping numbered archive (target exists)" after the initial conversion pass. This is expected; the command still deletes the old `.tar.gz` sources when `--delete-old` is set.
- **Key decisions:** Kept all remaining `tar.gz` references in tests and migration/backward-compat code intact. The cleanup for this task only removed live archive bundle files, not compatibility fixtures or fallback logic.
