---
Task: t1647_1_promote_trail_discovery_seams_to_lib.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_2_*.md … t1647_6_*.md (pending)
Worktree: (none — profile 'fast', current branch)
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1647_1 — Promote trail discovery seams to `lib/trail_discovery.py`

## Context

The trail-merge feature (t1647) needs discovery, dedup, overlap computation
and blob loading outside the board: the preflight helper (t1647_3) and the
`/aitask-merge-trails` skill consume them. They live today as board-internal
functions in `.aitask-scripts/board/aitask_board.py`. This child promotes
them into a shared lib module and makes the board import (and re-export)
them. **Pure refactor — zero behavior change; the full board suite is the
regression guard.**

## Steps

1. **Create `.aitask-scripts/lib/trail_discovery.py`.** Move, docstrings and
   comments intact (they carry load-bearing history — t1365 re-read-from-disk
   rationale, fail-closed contracts):
   - `TRAIL_ARTIFACT_KIND` (~board:1096)
   - `TrailInfo` dataclass (~:1131)
   - `trail_entry_refs` (:1258)
   - `compute_trail_overlaps` (:1294)
   - `_trail_owner_rank` (~:1316)
   - `dedupe_trail_records` (:1329)
   - `_iter_active_task_frontmatter` (~:1345)
   - `_iter_trail_frontmatter_records` (~:1400)
   - `_trail_versions` (~:1437)
   - `load_trail_blob` (:1453)
   - `discover_trails` (:1490)

   Module docstring: cwd = repo root convention (same as
   `lib/trail_gather.py`); read-only contract (only `artifact get` /
   `artifact versions` subprocesses).

2. **Resolve the moved code's dependencies inside the lib module:**
   - `parse_task_filename`, `parse_frontmatter` — import from the same seam
     the board uses (`task_yaml` import block, board ~:53).
   - `_task_id_sort_key` — locate its definition; if board-local, move it
     into `trail_discovery.py` (it is only sorting logic) and have the board
     re-export; if already in a lib module, import.
   - `iter_archived_frontmatter` — `from archive_iter import ...`.
   - `trail_schema` — plain import (already lib).
   - `TASKS_DIR` — the board derives it via `config_utils.task_dir()`;
     resolve the SAME way in the lib module. Do NOT hardcode `aitasks/`.
   - `ARTIFACT_SCRIPT` / `Path(".aitask-scripts")` constants — define
     locally in the module.

3. **Board adoption.** Delete the moved definitions from `aitask_board.py`
   and add `from trail_discovery import TRAIL_ARTIFACT_KIND, TrailInfo,
   trail_entry_refs, compute_trail_overlaps, _trail_owner_rank,
   dedupe_trail_records, _iter_active_task_frontmatter,
   _iter_trail_frontmatter_records, _trail_versions, load_trail_blob,
   discover_trails` next to the existing lib imports (`import trail_schema`
   etc.). Re-export (import into board namespace) is REQUIRED:
   `tests/test_board_bytrail_view.py` reads these as `ab.<name>` and patches
   `subprocess.run` globally — both keep working through re-exports.
   Keep `trail_summary_text`, `run_trail_drift`, `TrailEntryView`, lanes,
   glyphs in the board (rendering-side).

4. **New tests: `tests/test_trail_discovery.py`** — imports the lib module
   directly (no board / Textual import):
   - dedup precedence: active non-folded > active folded > archived; tie →
     lowest owner id (synthetic `TrailInfo` records).
   - `compute_trail_overlaps` on divergent membership (shared and unshared
     refs; note entry key is `task`).
   - `trail_entry_refs` shape.
   - `discover_trails` against a synthetic project dir (tmp cwd with
     `aitasks/` + `aitasks/archived/`, tasks carrying `artifacts:` entries):
     handle dedup across owners, archived-owner flag, `unreadable` reporting
     when one task file is malformed (pin BOTH failure shapes: raising
     parse and None parse).
   - `load_trail_blob` fail-closed: mocked `subprocess.run` failure →
     `doc=None`, non-empty error, versions fallback attempted.

5. **Run the guards.**
   - `bash tests/run_all_python_tests.sh --test-dir tests` — verdict from
     the LAST stderr line.
   - `tests/test_board_bytrail_view.py` must pass UNCHANGED (especially
     `ReadOnlyNegativeControlTests` and the boot-phase spawn control).

## Verification

- Suite green (above).
- `ait board` boots; `z` renders By-Trail with the live trails exactly as
  before (spot check; the MV sibling re-verifies).

## Pinned (from parent plan — do not re-decide)

- No `.sh` wrapper here; t1647_3 owns the whitelisted entry point.
- Reference Step 9 (Post-Implementation) of task-workflow for archival/merge.
