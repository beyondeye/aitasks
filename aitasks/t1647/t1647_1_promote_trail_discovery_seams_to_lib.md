---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [trails, aitask_board, python]
gates: [risk_evaluated]
anchor: 1647
created_at: 2026-09-01 18:49
updated_at: 2026-09-01 18:49
---

## Context

First child of t1647 (trail-to-trail merge). The merge feature needs trail
discovery, dedup, overlap computation, and blob loading OUTSIDE the board —
in the preflight helper (t1647_3) and, transitively, the `/aitask-merge-trails`
skill. Today those seams are board-internal functions in
`.aitask-scripts/board/aitask_board.py`. Promote them into a shared lib module
the board then imports, so the skill duplicates nothing and both surfaces read
the same definitions.

This child is pure refactor: **zero behavior change**, board suite stays green.

## What moves (source: `.aitask-scripts/board/aitask_board.py`, anchors at
planning time — re-verify, the file churns)

Into new `.aitask-scripts/lib/trail_discovery.py`:

- `TRAIL_ARTIFACT_KIND` constant (~:1096) and the `ARTIFACT_SCRIPT` path
  constant it needs (module convention: cwd = repo root, same as
  `lib/trail_gather.py`).
- `TrailInfo` dataclass (~:1131)
- `trail_entry_refs` (:1258)
- `compute_trail_overlaps` (:1294)
- `_trail_owner_rank` (:1316)
- `dedupe_trail_records` (:1329)
- `_iter_active_task_frontmatter` (:1345)
- `_iter_trail_frontmatter_records` (:1400)
- `_trail_versions` (:1437)
- `load_trail_blob` (:1453)
- `discover_trails` (:1490)

Stays in the board: `trail_summary_text`, `run_trail_drift`, `TrailEntryView`,
lane building, glyphs — all rendering/board-only concerns.

## Dependencies of the moved code (resolve as lib imports)

- `parse_task_filename`, `parse_frontmatter` — check current import source in
  the board (`task_yaml` import block ~:53); import the same seams in the lib
  module.
- `_task_id_sort_key` — find its definition (board-local or lib); if
  board-local, move it too (used by `_trail_owner_rank`) or import.
- `iter_archived_frontmatter` — from `archive_iter` (already a lib module).
- `trail_schema` — already lib.
- `TASKS_DIR` — the board derives it from config (`task_dir()` in
  `config_utils`); the lib module must resolve the same way, NOT hardcode
  `aitasks/`.

## Board adoption (critical for tests)

The board REPLACES the moved definitions with re-exports:
`from trail_discovery import TRAIL_ARTIFACT_KIND, TrailInfo, trail_entry_refs,
compute_trail_overlaps, dedupe_trail_records, load_trail_blob,
discover_trails, ...` (the board's lib-import path setup already reaches
`.aitask-scripts/lib/`). Re-export is mandatory:
`tests/test_board_bytrail_view.py` accesses these as `ab.<name>` and patches
`subprocess.run` globally — both keep working through re-exports. The
docstring history (t1365 re-read-from-disk rationale, fail-closed contracts)
moves WITH the functions.

## Tests

- New `tests/test_trail_discovery.py` — imports `lib/trail_discovery.py`
  directly (no board, no Textual): owner-rank dedup precedence (active >
  active-folded > archived; tie -> lowest id), `compute_trail_overlaps` on
  divergent membership, `trail_entry_refs`, discovery against a synthetic
  task dir (tmp cwd with `aitasks/` + archived halves; include one malformed
  task file to pin the `unreadable` reporting), fail-closed `load_trail_blob`
  (subprocess mocked).
- Existing `tests/test_board_bytrail_view.py` must pass UNCHANGED — the
  `ReadOnlyNegativeControlTests` and the boot-phase spawn control are the
  regression guard for this refactor.
- Run the python suite: `bash tests/run_all_python_tests.sh` (verdict = LAST
  stderr line only).

## Verification

- `python3 -c "import trail_discovery"` resolves via the framework
  interpreter with lib on path (use the runner, not bare python).
- `bash tests/run_all_python_tests.sh --test-dir tests` green; specifically
  test_board_bytrail_view.py and the new test_trail_discovery.py.
- `ait board` boots and By-Trail (`z`) renders the live trails as before
  (manual spot check; the aggregate MV sibling re-checks).

## Pinned decisions (from parent plan — do not re-decide)

- No `.sh` entry point in this child — t1647_3 owns the whitelisted wrapper.
- Board keeps behavioral ownership of rendering; lib owns
  discovery/dedup/overlap/load only.

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.
