---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-22 16:21
updated_at: 2026-07-22 16:21
---

## Origin

Risk-mitigation ("after") follow-up for t1162_1, created at Step 8d after implementation landed.

## Risk addressed

`lib/work_report_gather.py` imports from `board/task_yaml.py` and `stats/stats_data.py`, inverting the layer direction — `lib/` is the shared base layer and now depends on two higher-level packages, so moving or renaming either module silently breaks the gatherer · severity: medium

t1162_1 deliberately chose reuse over re-derivation: the gatherer imports the board's own `parse_frontmatter`, `BOARD_KEYS` and `normalize_board_idx` so board/gatherer equivalence holds by construction rather than by two implementations agreeing. That was the right call for correctness, but it left the dependency pointing the wrong way.

## Goal

Move `.aitask-scripts/board/task_yaml.py` to `.aitask-scripts/lib/task_yaml.py` and update its importers so the shared base layer no longer depends on `board/`:

- `.aitask-scripts/board/aitask_board.py` (imports `_TaskSafeLoader`, `_FlowListDumper`, `_normalize_task_ids`, `FRONTMATTER_RE`, `BOARD_KEYS`, `normalize_board_idx`, `parse_frontmatter`, `serialize_frontmatter`)
- `.aitask-scripts/board/aitask_merge.py`
- `.aitask-scripts/lib/work_report_gather.py` (can then drop the `board/` sys.path insert)
- `tests/lib/work_report_equiv.py` (sys.path setup)

The module's own docstring already describes it as "Extracted from aitask_board.py for reuse by aitask_merge.py and other tools" — the move makes its location match its actual role.

Note the `stats/stats_data.py` import stays as-is; only the `board/` inversion is in scope here.

## Verification

- `bash tests/test_work_report_gather.sh` — 103/103, including the board-equivalence oracle
- All `tests/test_board_*.py` (13 files)
- `tests/test_stats_multistage.py`, `tests/test_stats_data.sh`, `tests/test_update_multiline_yaml.sh`, `tests/test_chatlink_relay.sh`
- `grep -rn "from task_yaml import\|import task_yaml" .aitask-scripts/ tests/` returns no stale `board/`-relative resolution
