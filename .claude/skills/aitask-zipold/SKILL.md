---
name: aitask-zipold
description: Archive old task and plan files to tar.gz archives, keeping only the most recent.
---

## Usage

Run the archive script:

```bash
./aiscripts/aitask_zip_old.sh
```

### Options

- `--dry-run` / `-n`: Preview what would be archived without making changes
- `--no-commit`: Archive files but don't commit to git
- `--verbose` / `-v`: Show detailed progress
- `--help` / `-h`: Show usage information

### Examples

Preview what will be archived:
```bash
./aiscripts/aitask_zip_old.sh --dry-run
```

Archive with verbose output:
```bash
./aiscripts/aitask_zip_old.sh --verbose
```

Archive without committing:
```bash
./aiscripts/aitask_zip_old.sh --no-commit
```

## What It Does

1. Scans `aitasks/archived/` for parent task files matching `t*_*.md`
2. Scans `aitasks/archived/t*/` for child task files matching `t*_*_*.md`
3. Scans `aiplans/archived/` for parent plan files matching `p*_*.md`
4. Scans `aiplans/archived/p*/` for child plan files matching `p*_*_*.md`
5. Keeps the most recent file (highest number) uncompressed in each directory/subdirectory
6. Archives all other files to `old.tar.gz`, preserving directory structure
7. Verifies archive integrity before deleting originals
8. Commits changes to git (unless `--no-commit`)

## Directory Structure

The script handles the parent/child task hierarchy:

```
aitasks/archived/
  ├── t22_old_parent.md           # Kept (most recent parent)
  ├── t21_older_parent.md         # Archived to old.tar.gz
  ├── t1/                         # Child task directory
  │   ├── t1_3_latest_child.md    # Kept (most recent child of t1)
  │   ├── t1_2_older_child.md     # Archived to old.tar.gz
  │   └── t1_1_oldest_child.md    # Archived to old.tar.gz
  └── old.tar.gz                  # Contains archived files with subdirectories

aiplans/archived/
  ├── p22_old_parent_plan.md
  ├── p1/                         # Child plan directory
  │   └── p1_3_latest_child.md
  └── old.tar.gz
```

## Archive Structure

The `old.tar.gz` preserves the directory hierarchy:

```
old.tar.gz/
  ├── t21_older_parent.md         # Parent tasks at root
  ├── t20_even_older.md
  ├── t1/                         # Child directories preserved
  │   ├── t1_2_older_child.md
  │   └── t1_1_oldest_child.md
  └── t5/
      └── t5_1_child.md
```

## Notes

- The most recent file in each directory/subdirectory is kept uncompressed
- This ensures `aitask-create` can determine the next task number correctly
- Child task directories that become empty after archiving are automatically removed
- If `old.tar.gz` already exists, new files are appended to it
- If an existing archive is corrupted, a backup is created before starting fresh
- Archive integrity is verified before deleting original files
