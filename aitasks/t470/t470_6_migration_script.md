---
priority: high
effort: medium
depends: [2, 3]
issue_type: feature
status: Ready
labels: [task-archive, archiveformat]
created_at: 2026-03-27 13:12
updated_at: 2026-03-27 13:12
---

Create a standalone migration script that converts existing old*.tar.gz archives to old*.tar.zst format. Add as ait migrate-archives subcommand.

## Context

After all code is updated (t470_1, t470_2, t470_3), existing repositories still have tar.gz archives that need converting. This script handles the one-time conversion. It must be run before t470_7 (final cleanup).

## Key Files to Create

### `.aitask-scripts/aitask_migrate_archives.sh` (new file)

**Script behavior:**
1. Scan both `aitasks/archived/_b*/old*.tar.gz` and `aiplans/archived/_b*/old*.tar.gz` for tar.gz archives
2. Also scan for legacy `aitasks/archived/old.tar.gz` and `aiplans/archived/old.tar.gz`
3. For each found `.tar.gz`:
   - Compute target `.tar.zst` path (same name, different extension)
   - Skip if `.tar.zst` already exists (idempotent)
   - Decompress: `tar -xzf old.tar.gz -C tmpdir`
   - Recompress: `tar -cf - -C tmpdir . | zstd -q -o old.tar.zst`
   - Verify: `zstd -dc old.tar.zst | tar -tf - > /dev/null`
   - Report success/failure
4. Summary: total archives found, converted, skipped, failed

**Flags:**
- `--dry-run` — Show what would be converted without doing it
- `--delete-old` — Delete .tar.gz files after successful conversion (default: keep both)
- `--verbose` — Show detailed output per archive

**Follow shell conventions:**
- `#!/usr/bin/env bash` + `set -euo pipefail`
- Source `terminal_compat.sh` for `die()`, `warn()`, `info()`
- Use temp directory with cleanup trap
- Guard against double-sourcing

### `ait` dispatcher
- Add `migrate-archives` subcommand routing to `aitask_migrate_archives.sh`

## Reference Files
- `.aitask-scripts/aitask_zip_old.sh` — Similar archive manipulation patterns (extract/recompress)
- `.aitask-scripts/lib/archive_utils.sh` — `archive_path_for_id()` for path computation

## Implementation Plan
1. Create `.aitask-scripts/aitask_migrate_archives.sh` with argument parsing
2. Implement scan logic for both task and plan archive directories
3. Implement convert logic with temp directory pattern
4. Add --dry-run, --delete-old, --verbose flags
5. Add `migrate-archives` to `ait` dispatcher
6. Test manually: `./ait migrate-archives --dry-run`
7. Run shellcheck

## Verification
- `shellcheck .aitask-scripts/aitask_migrate_archives.sh`
- `./ait migrate-archives --dry-run` — lists all tar.gz archives to convert
- `./ait migrate-archives --verbose` on a test archive — converts successfully
