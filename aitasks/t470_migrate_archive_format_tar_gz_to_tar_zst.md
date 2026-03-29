---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [task-archive, archiveformat]
children_to_implement: [t470_2, t470_3, t470_4, t470_5, t470_6, t470_7]
created_at: 2026-03-26 22:42
updated_at: 2026-03-29 09:10
boardidx: 90
---

Migrate all archive operations from tar.gz to tar.zst format across the entire aitasks codebase.

## Context

Benchmark results (see aidocs/benchmarks/archive_format_results.md, task t469) show tar.zst is the best migration target from tar.gz:
- **2x faster** than tar.gz for all operations (list, exists, extract)
- **Slightly better compression** (0.29x vs 0.30x ratio)
- **4.2x faster archive creation** (19.6ms vs 82.1ms)
- **Easiest migration path** from tar.gz (same tar-based tooling, just different compressor)

While zip was fastest for listing/existence checks (14x faster), it doesn't translate to proportional end-to-end speedup since archive operations include extraction, frontmatter parsing, and other processing beyond just listing. tar.zst provides consistent 2x improvement across ALL operations with minimal code changes.

## Scope

### Bash scripts to migrate
- `.aitask-scripts/lib/archive_utils.sh` — Core archive primitives: `_search_tar_gz()`, `_extract_from_tar_gz()`, `_find_archive_for_task()`, `_search_all_archives()`, `_search_numbered_then_legacy()`. All use `tar -tzf`/`tar -xzf` commands.
- `.aitask-scripts/lib/archive_scan.sh` — Scanner functions: `scan_max_task_id()`, `search_archived_task()`, `iter_all_archived_files()`. Use `tar -tzf` for listing.
- `.aitask-scripts/lib/task_utils.sh` — `resolve_task_file()`, `resolve_plan_file()` with 4-tier lookup including tar.gz fallback.
- `.aitask-scripts/aitask_zip_old.sh` — Creates/manages numbered archive bundles. Uses `tar -czf`/`tar -xzf`/`tar -tzf` extensively. This is the primary archive creation script.
- `.aitask-scripts/aitask_query_files.sh` — Query subcommands that check archives (`archived-task`, `archived-children`, `recent-archived`).
- `.aitask-scripts/aitask_revert_analyze.sh` — Locates files in archives for revert analysis.
- `.aitask-scripts/aitask_stats_legacy.sh` — Legacy stats using old.tar.gz.
- `.aitask-scripts/aitask_brainstorm_archive.sh` — Brainstorm session archival (if it uses tar.gz).

### Python scripts to migrate
- `.aitask-scripts/lib/archive_iter.py` — `iter_all_archived_tar_files()`, `iter_all_archived_markdown()`, `iter_archived_frontmatter()`, `archive_path_for_id()`. Uses Python `tarfile` module with `r:gz` mode.

### Setup and dependencies
- `ait setup` must install `zstd` on macOS via Homebrew (`brew install zstd`)
- `ait setup` should add automatic migration of existing `old*.tar.gz` files to `old*.tar.zst`
- Linux: `zstd` is available in all major distro package managers (apt, dnf, pacman)

### macOS compatibility — DECIDED: use pipe approach universally
- BSD tar does NOT support `--zstd` flag. Must use pipe approach: `tar -cf - -C dir . | zstd > archive.tar.zst` for creation, `zstd -dc archive.tar.zst | tar -tf -` for listing, etc.
- GNU tar on Linux supports `--zstd` natively, but benchmarks (t469) show the **pipe approach is ~15% faster** than native `--zstd` on Linux across all operations (list: 4.7ms vs 5.6ms, extract: 4.6ms vs 5.3ms, create: 18.9ms vs 19.5ms). Archive sizes are identical (955KB).
- The pipe approach benefits from parallel decompression — `zstd` decompresses in one process while `tar` parses in another.
- **Decision: use pipe approach universally.** No platform detection needed. Simpler code, cross-platform, and faster on Linux too.

### Command patterns (pipe approach — use these everywhere)

| Operation | Current (tar.gz) | New (tar.zst pipe) |
|-----------|-------------------|---------------------|
| **Create** | `tar -czf archive.tar.gz -C dir .` | `tar -cf - -C dir . \| zstd -q -o archive.tar.zst` |
| **List files** | `tar -tzf archive.tar.gz` | `zstd -dc archive.tar.zst \| tar -tf -` |
| **Extract single** | `tar -xzf archive.tar.gz -O file` | `zstd -dc archive.tar.zst \| tar -xf - -O file` |
| **Extract all** | `tar -xzf archive.tar.gz -C dir` | `zstd -dc archive.tar.zst \| tar -xf - -C dir` |
| **Verify** | `tar -tzf archive.tar.gz > /dev/null` | `zstd -dc archive.tar.zst \| tar -tf - > /dev/null` |

For Python (`archive_iter.py`): use `subprocess.Popen` pipe chain (same pattern as CLI), or `zstd -dc archive | tar -tf -` via shell. The Python `tarfile` module does not natively support zstd, so subprocess is required.

### Archive naming convention change
- Current: `_b{dir}/old{bundle}.tar.gz`
- New: `_b{dir}/old{bundle}.tar.zst`
- Legacy fallback: keep `old.tar.gz` fallback logic for repositories that haven't migrated yet

### Tests to update
- `tests/test_archive_utils.sh` — Tests archive utility functions
- `tests/test_archive_scan.sh` — Tests archive scanning
- `tests/test_resolve_tar_gz.sh` — Tests file resolution from archives (rename to test_resolve_tar_zst.sh)
- `tests/test_zip_old.sh` — Tests aitask_zip_old.sh bundling
- `tests/test_archive_iter_consolidated.py` — Python archive iteration tests

### Migration strategy
1. Update all code to read/write tar.zst format
2. Keep backward compatibility: code should fall back to tar.gz if tar.zst not found (transition period)
3. Add tar.gz → tar.zst migration command/script
4. Update ait setup for dependency installation
5. Run migration on this repo's archives
6. Delete old tar.gz files only as final step after all code is verified

### Skills
Skills should NOT directly manipulate archives — they access archived tasks via bash scripts. Verify no skill files contain direct tar/archive commands. If any do, update them to use the bash script APIs instead.

This task should be decomposed into child tasks covering: bash lib migration, Python migration, aitask_zip_old.sh update, setup/dependency changes, test updates, migration script, actual migration of this repo, and final cleanup (tar.gz deletion).
