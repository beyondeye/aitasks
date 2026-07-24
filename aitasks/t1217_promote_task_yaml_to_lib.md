---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [reporting]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1235, 1236]
assigned_to: dario-e@beyond-eye.com
anchor: 1162
implemented_with: claudecode/opus4_8
created_at: 2026-07-22 16:21
updated_at: 2026-07-24 15:18
---

## Origin

Risk-mitigation ("after") follow-up for t1162_1, created at Step 8d after implementation landed. Scope corrected after filing: the original description named 3 importers and estimated `effort: low`; an audit found **6 importers across 5 packages** plus 2 tests, so the effort was raised to `medium`.

## Risk addressed

`lib/work_report_gather.py` imports from `board/task_yaml.py`, inverting the layer direction — `lib/` is the shared base layer and should not depend on a higher-level package, so moving or renaming `task_yaml.py` silently breaks the gatherer · severity: medium

t1162_1 deliberately chose reuse over re-derivation: the gatherer imports the board's own `parse_frontmatter`, `BOARD_KEYS` and `normalize_board_idx` so board/gatherer equivalence holds by construction rather than by two implementations agreeing. That was the right call for correctness, but it left the dependency pointing the wrong way.

**The inversion is systemic, not something t1162_1 introduced.** Three unrelated TUI packages already `sys.path.insert` into `board/` purely to import this shared frontmatter parser. `task_yaml.py` is a base-layer module that happens to live in `board/`; its own docstring says it was "Extracted from aitask_board.py for reuse by aitask_merge.py and other tools". This task makes its location match its actual role.

## Goal

Move `.aitask-scripts/board/task_yaml.py` → `.aitask-scripts/lib/task_yaml.py` and update every importer.

### Importers (6)

| File | Imports | Notes |
|---|---|---|
| `board/aitask_board.py:53` | `_TaskSafeLoader`, `_FlowListDumper`, `_normalize_task_ids`, `FRONTMATTER_RE`, `BOARD_KEYS`, `normalize_board_idx`, `parse_frontmatter`, `serialize_frontmatter` | same-package import today; needs `lib` on `sys.path` (it already resolves `lib` for `config_utils`) |
| `board/aitask_merge.py:30` | `parse_frontmatter`, `serialize_frontmatter`, `BOARD_KEYS` | same-package import today |
| `lib/work_report_gather.py:55` | `BOARD_KEYS`, `normalize_board_idx`, `parse_frontmatter` | **can drop the `board/` sys.path insert entirely** — this is the inversion being repaid |
| `codebrowser/history_data.py:20` | `parse_frontmatter` | already inserts `lib` at line 18 → just drop the `board` insert at line 17 |
| `diffviewer/plan_loader.py:9` | `parse_frontmatter` | inserts **only** `board` (line 8) → must gain a `lib` insert |
| `monitor/monitor_core.py:50` | `parse_frontmatter` | already inserts both `lib` and `board` (line 37) → drop `board` if nothing else needs it |

### Tests referencing the module path (2)

- `tests/test_update_multiline_yaml.sh:206` — `sys.path.insert(0, sys.argv[1] + "/.aitask-scripts/board")` then `import task_yaml`
- `tests/test_board_topic_group.py:472` — `from task_yaml import parse_frontmatter, _normalize_task_id`
- `tests/lib/work_report_equiv.py` — sys.path setup inserts `board` and `lib`

## Sequencing

Land this **after t1162 completes**. Verified at filing time: no remaining t1162 child references `task_yaml`, `parse_frontmatter`, `BOARD_KEYS` or `normalize_board_idx`, so nothing in t1162 depends on this. But **t1162_4 edits `aitask_board.py` substantially** for the board `w` flow, and this task edits that file's import block — doing both concurrently is needless churn. Not a hard dependency: if t1162 stalls, this can proceed independently.

## Verification

- `bash tests/test_work_report_gather.sh` — all assertions, including the board-equivalence oracle
- All `tests/test_board_*.py` (13 files)
- `tests/test_stats_multistage.py`, `tests/test_stats_data.sh`, `tests/test_update_multiline_yaml.sh`, `tests/test_chatlink_relay.sh`
- **Regression coverage for the three newly-identified consumers** — codebrowser, diffviewer and monitor import this parser and are easy to miss: run their test files, and smoke-launch each TUI (`ait codebrowser`, `ait monitor`) to confirm the import resolves at runtime, not just under test
- `grep -rn "from task_yaml import\|import task_yaml" .aitask-scripts/ tests/` — every hit resolves via `lib`, none via a `board/` sys.path insert
- `grep -rn "board" .aitask-scripts/*/[a-z]*.py | grep sys.path` — no package inserts `board/` solely to reach `task_yaml`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-24T10:59:08Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T12:16:03Z status=pass attempt=1 type=human
