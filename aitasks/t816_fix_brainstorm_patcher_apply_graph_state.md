---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_brainstorm]
created_at: 2026-05-20 11:20
updated_at: 2026-05-20 11:20
---

## Origin

Spawned from t807 during Step 8b review.

## Upstream defect

- `tests/test_brainstorm_apply_patcher_cli.sh` — the `FAIL: graph state not advanced` sub-check fails on the pristine tree (HEAD 8e483a4e), independent of t807. The patcher CLI apply path does not advance `br_graph_state.yaml`'s `current_head` after a successful patch apply.

## Diagnostic context

Surfaced during t807 verification: `bash tests/test_brainstorm_apply_patcher_cli.sh` reports `Total: 7  Passed: 6  Failed: 1`, with the single failure being `FAIL: graph state not advanced`. Confirmed pre-existing by `git stash`-ing all working-tree changes and re-running on a clean HEAD — the failure reproduces, so it is unrelated to t807's `hybridize`→`synthesize` rename. The positive-apply sub-checks pass (`APPLIED:...:NO_IMPACT`, new node YAML created, patched plan written, idempotent re-run), so apply itself works — only the graph-state head advance is missing.

## Suggested fix

Compare the patcher apply path (`apply_patcher_output` in `.aitask-scripts/brainstorm/brainstorm_session.py`, invoked by `.aitask-scripts/aitask_brainstorm_apply_patcher.sh`) against the synthesizer/explorer apply paths, which do advance `current_head` / append to `history` in `br_graph_state.yaml`. The patcher apply likely skips the graph-state update step that the other operations perform.
