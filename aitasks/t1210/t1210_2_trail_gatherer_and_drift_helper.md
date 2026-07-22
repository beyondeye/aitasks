---
priority: high
effort: high
depends: [t1210_1]
issue_type: feature
status: Ready
labels: [bash_scripts, python, task-planning]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-07-22 16:15
updated_at: 2026-07-22 16:15
---

## Context

**T2** of the Implementation Trails decomposition (RFC §14 in
`aidocs/implementation_trail_design.md`; parent t1210). The deterministic
read-only gatherer + drift checker: the riskiest spike of the feature (digest
normalization fidelity and named drift reasons), deliberately landed before
any skill or UI work. RFC §7 (gathering algorithm) and §8 (freshness model)
are the spec.

## Key files to create/modify

- `.aitask-scripts/aitask_trail_gather.sh` (new) — thin whitelistable bash
  entry delegating to the Python lib (same split as
  `.aitask-scripts/aitask_work_report_gather.sh` → `lib/work_report_gather.py`
  from t1162_1).
- `.aitask-scripts/lib/trail_gather.py` (new) — scope/owner resolution, input
  snapshot collection, digest via `lib/trail_schema.py` (t1210_1), and the
  drift verb.
- `tests/test_trail_gather.py` (new).

## Reference files for patterns

- `aidocs/implementation_trail_design.md` §7 (algorithm steps 1–2), §8.1–8.2
  (digest inputs and the drift-reason enum — PINNED: the codes must match the
  schema's `freshness.drift_reasons[].code` enum exactly).
- `.aitask-scripts/lib/work_report_gather.py` — line-protocol output style,
  frontmatter reading, board-state access (t1162_1; check its landed state
  first — it was Implementing when the RFC was written).
- `aidocs/framework/cross_repo_references.md` — task-ref notation +
  `aitask_project_resolve.sh` for cross-repo refs.
- `aidocs/framework/shell_conventions.md` — mandatory for the new `.sh`.

## Implementation plan

1. Verbs (line-protocol stdout, one record per line):
   - `snapshot --scope <task|topic|multi_topic> <ids...>` → normalized input
     records + `DIGEST:<hex>` line.
   - `drift --trail <file-or-handle>` → recompute digest against the stored
     `generation.input_digest`/`inputs`; emit `CURRENT` or `STALE` followed by
     `DRIFT:<code>|<task_ref>|<detail>` lines (codes from the schema enum).
2. Topic resolution must reuse the board's anchor-resolution semantics
   (canonical seam: match `topic_key()` behavior in
   `.aitask-scripts/board/aitask_board.py:323-341`; do NOT fork a divergent
   rule — extract/shim if needed).
3. Polling never mutates: `drift` reads only; it must not rewrite the artifact
   or any staleness stamp (negative control test).
4. Unit tests over synthetic task fixtures: digest stability (boardidx change
   → no drift), each drift code producible, deleted input → `input_missing`,
   presence-tracked inputs.

## Verification

- `bash tests/test_trail_gather.py` equivalent via
  `python3 -m unittest tests.test_trail_gather -v` green.
- Negative controls: boardidx-only change yields CURRENT; drift run leaves the
  trail file byte-identical.
- `shellcheck .aitask-scripts/aitask_trail_gather.sh` clean.
