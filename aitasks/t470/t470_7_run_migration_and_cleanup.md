---
priority: high
effort: low
depends: []
issue_type: chore
status: Ready
labels: [task-archive, archiveformat]
created_at: 2026-03-27 15:44
updated_at: 2026-03-27 15:44
---

Execute the migration script on this repository's archives, run full test suite, update documentation, and clean up old tar.gz files.

## Context

This is the final child task — all code changes (t470_1 through t470_6) must be complete before running. This repo has 10 archives to convert (5 task + 5 plan in aitasks/archived/_b0/ and aiplans/archived/_b0/).

## Actions

### 1. Run migration
```bash
./ait migrate-archives --verbose
```
Expected: converts 10 archives from `old{0-4}.tar.gz` → `old{0-4}.tar.zst` in both `aitasks/archived/_b0/` and `aiplans/archived/_b0/`.

### 2. Verify archives
```bash
for f in aitasks/archived/_b0/old*.tar.zst aiplans/archived/_b0/old*.tar.zst; do
  zstd -dc "$f" | tar -tf - > /dev/null && echo "OK: $f" || echo "FAIL: $f"
done
```

### 3. Run full test suite
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

### 4. Update documentation
- `CLAUDE.md` line 54: `old.tar.gz` → `old.tar.zst`
- `CLAUDE.md` test list: rename `test_resolve_tar_gz.sh` → `test_resolve_tar_zst.sh`

### 5. Delete old tar.gz files
```bash
./ait migrate-archives --delete-old
```
Or manually: `rm aitasks/archived/_b0/old*.tar.gz aiplans/archived/_b0/old*.tar.gz`

### 6. Commit
- Code commit: documentation changes
- Git add converted archives and remove old ones

## Verification
- All tests pass
- No `.tar.gz` files remain in archived directories
- `./ait` commands work end-to-end (query, stats, etc.)
- `grep -r "tar\.gz" .aitask-scripts/` — only backward compat fallback code remains
