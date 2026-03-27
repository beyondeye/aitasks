# t470: Migrate Archive Format tar.gz to tar.zst

## Context

Benchmark results (t469) show tar.zst is 2x faster than tar.gz across all archive operations with slightly better compression. The pipe approach (`zstd -dc file | tar -tf -`) is decided for universal use — no platform detection needed, works on both macOS and Linux, and is ~15% faster than GNU tar's native `--zstd` flag.

This is a high-effort task that requires decomposition into child tasks. The codebase has ~10 shell scripts, 1 Python module, 1 skill file, and ~9 test files referencing tar.gz.

## Child Task Decomposition (7 tasks)

### t470_1: Core bash library migration (archive_utils.sh + archive_scan.sh + tests)

**Files to modify:**
- `.aitask-scripts/lib/archive_utils.sh` — Rename functions: `_search_tar_gz()` → `_search_archive()`, `_extract_from_tar_gz()` → `_extract_from_archive()`. Add internal helpers `_archive_list()` and `_archive_extract_file()` for pipe commands. Update `archive_path_for_id()` to return `.tar.zst`. Update globs `old*.tar.gz` → `old*.tar.zst` (with `.tar.gz` fallback). Auto-detect format by file extension in helpers.
- `.aitask-scripts/lib/archive_scan.sh` — Update `scan_max_task_id()`, `search_archived_task()`, `iter_all_archived_files()` to use new function names, new globs, pipe commands. Change output format `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:` (format-agnostic — archive format details must not leak into consumers/skills).
- `tests/test_archive_utils.sh` — Update `create_test_archive()` to create `.tar.zst` fixtures. Update all 48 assertions.
- `tests/test_archive_scan.sh` — Update fixtures and 12 assertions.

**Dependencies:** None
**Complexity:** High

### t470_2: Consumer scripts migration (task_utils.sh, query, revert, stats_legacy)

**Files to modify:**
- `.aitask-scripts/lib/task_utils.sh` — Update 8 call sites from `_search_tar_gz`/`_extract_from_tar_gz` to new names. Update `old.tar.gz` fallback paths.
- `.aitask-scripts/aitask_query_files.sh` — Update help text and output format doc strings.
- `.aitask-scripts/aitask_revert_analyze.sh` — Update `_find_file_location()`: rename function calls, change `old.tar.gz` path refs, update `tar_gz` location type to `archive` (format-agnostic).
- `.aitask-scripts/aitask_stats_legacy.sh` — Update `ARCHIVE_TAR` path and `collect_from_tarball()` direct tar commands to pipe approach.
- `.claude/skills/aitask-revert/SKILL.md` — Update to format-agnostic output: `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:`, `tar_gz` → `archive`. Skills must not reference internal archive format details.
- `tests/test_resolve_tar_gz.sh` — Rename to `test_resolve_tar_zst.sh`, update 14 test cases.
- `tests/test_query.sh` — Update archived-task tests (lines 298-355): fixtures and assertions.
- `tests/test_claim_id.sh` — Update tar.gz fixture creation (line 291).
- `tests/test_t167_integration.sh` — Update tarball reference (line 74).

**Dependencies:** t470_1
**Complexity:** Medium

### t470_3: aitask_zip_old.sh + aitask_create.sh migration

**Files to modify:**
- `.aitask-scripts/aitask_zip_old.sh` — Update `_archive_single_bundle()` (create/extract/verify), `cmd_unpack()` (list/extract/rebuild), git add globs. All tar commands → pipe approach.
- `.aitask-scripts/aitask_create.sh` — Update `ARCHIVE_FILE` path and 2 `tar -tzf` commands. Try `.tar.zst` first, fall back to `.tar.gz`.
- `tests/test_zip_old.sh` — Update 26 test cases: fixture creation, archive verification, path assertions.

**Dependencies:** t470_1
**Complexity:** High

### t470_4: Python archive_iter.py migration

**Files to modify:**
- `.aitask-scripts/lib/archive_iter.py` — Update `archive_path_for_id()` to `.tar.zst`. Update globs in `iter_numbered_archives()`, `iter_legacy_archive()`. Replace `tarfile.open(path, "r:gz")` with subprocess pipe: `zstd -dc` piped to `tarfile.open(fileobj=proc.stdout, mode="r|")`. Auto-detect by extension for backward compat.
- `tests/test_archive_iter_consolidated.py` — Update `_make_tar_gz()` to create `.tar.zst` fixtures via subprocess. Update 19 test cases.
- `tests/test_aitask_stats_py.py` — Update archive creation (line 150-153).

**Dependencies:** None (independent of bash tasks)
**Complexity:** Medium

### t470_5: ait setup dependency installation

**Files to modify:**
- `.aitask-scripts/aitask_setup.sh` — Add `zstd` to tool lists for all OS detection paths (brew, apt, dnf, pacman).

**Dependencies:** None
**Complexity:** Low

### t470_6: Migration script (tar.gz → tar.zst converter)

**Files to create:**
- `.aitask-scripts/aitask_migrate_archives.sh` — New script. For each `old*.tar.gz` in `aitasks/archived/_b*/` and `aiplans/archived/_b*/`: decompress, recompress as `.tar.zst`, verify, report. Support `--dry-run` flag. Add as `ait migrate-archives` subcommand.

**Dependencies:** t470_1, t470_2, t470_3 (all code updated before migration)
**Complexity:** Medium

### t470_7: Run migration on this repo + final cleanup

**Actions:**
- Run migration script on 10 archive files (5 task + 5 plan)
- Run full test suite
- Update `CLAUDE.md` reference (`old.tar.gz` → `old.tar.zst`)
- Delete old `.tar.gz` files
- Git commit converted archives

**Dependencies:** All previous (t470_1 through t470_6)
**Complexity:** Low

## Dependency Graph

```
t470_1 (core libs) ──→ t470_2 (consumers) ──→ t470_6 (migration script) ──→ t470_7 (run + cleanup)
                   └──→ t470_3 (zip_old)  ──┘
t470_4 (Python)    ─────────────────────────────────────────────────────────→ t470_7
t470_5 (setup)     ─────────────────────────────────────────────────────────→ t470_7
```

Parallelizable: {t470_1, t470_4, t470_5}, then {t470_2, t470_3}, then t470_6, then t470_7.

## Key Design Decisions

1. **Universal pipe approach** — No `--zstd` flag, no platform detection. Always: `zstd -dc file | tar -tf -` (read), `tar -cf - -C dir . | zstd -q -o file` (write).
2. **Backward compatibility** — Functions auto-detect format by extension. Try `.tar.zst` first, fall back to `.tar.gz`. This enables gradual migration across repos.
3. **Function renaming** — `_search_tar_gz()` → `_search_archive()`, `_extract_from_tar_gz()` → `_extract_from_archive()`. Generic names since they handle both formats.
4. **Output format (format-agnostic)** — `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:`. Location type `tar_gz` → `archive`. Archive format is an implementation detail that must not leak into skill definitions or consumer-facing output.
5. **Python approach** — Use `subprocess.Popen(["zstd", "-dc", path])` piped to `tarfile.open(fileobj=proc.stdout, mode="r|")` for streaming tar read.

## Verification

After all child tasks complete:
- Run all archive-related tests: `test_archive_utils.sh`, `test_archive_scan.sh`, `test_resolve_tar_zst.sh`, `test_zip_old.sh`, `test_query.sh`, `test_claim_id.sh`, `test_archive_iter_consolidated.py`, `test_aitask_stats_py.py`
- Run shellcheck: `shellcheck .aitask-scripts/aitask_zip_old.sh .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/archive_scan.sh`
- Verify `ait` commands end-to-end: create task, archive, query, stats, unpack

## Step 9 Reference
Post-implementation: archive child tasks, update parent status, push.
