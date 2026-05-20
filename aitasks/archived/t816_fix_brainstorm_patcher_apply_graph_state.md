---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-20 11:20
updated_at: 2026-05-20 12:00
completed_at: 2026-05-20 12:00
---

## Origin

Spawned from t807 during Step 8b review.

## Upstream defect

- `tests/test_brainstorm_apply_patcher_cli.sh` — the `FAIL: graph state not advanced` sub-check fails on the pristine tree (HEAD 8e483a4e), independent of t807. The patcher CLI apply path does not advance `br_graph_state.yaml`'s `current_head` after a successful patch apply.

## Diagnostic context

Surfaced during t807 verification: `bash tests/test_brainstorm_apply_patcher_cli.sh` reports `Total: 7  Passed: 6  Failed: 1`, with the single failure being `FAIL: graph state not advanced`. Confirmed pre-existing by `git stash`-ing all working-tree changes and re-running on a clean HEAD — the failure reproduces, so it is unrelated to t807's `hybridize`→`synthesize` rename. The positive-apply sub-checks pass (`APPLIED:...:NO_IMPACT`, new node YAML created, patched plan written, idempotent re-run), so apply itself works — only the graph-state head advance is missing.

## Suggested fix

Compare the patcher apply path (`apply_patcher_output` in `.aitask-scripts/brainstorm/brainstorm_session.py`, invoked by `.aitask-scripts/aitask_brainstorm_apply_patcher.sh`) against the synthesizer/explorer apply paths, which do advance `current_head` / append to `history` in `br_graph_state.yaml`. The patcher apply likely skips the graph-state update step that the other operations perform.

## Resolution — no work needed (resolved by t810)

The diagnosis above is **incorrect** and the task is a duplicate of t810.

- `bash tests/test_brainstorm_apply_patcher_cli.sh` now passes 7/7 on the
  current tree.
- `apply_patcher_output` routes through the shared `_apply_node_output`
  core (`brainstorm_session.py:725-733`), which calls `set_head()`
  unconditionally (line 965). `set_head` (`brainstorm_dag.py:126-133`)
  sets `current_head` and appends to `history`. The patcher apply path
  has always advanced the head — identical to explorer/synthesizer.
- The real defect was in the **test**: the original assertion was a
  compound `grep current_head … && grep "next_node_id: 2"`. The
  `current_head` clause passed; the `next_node_id: 2` clause failed
  (apply correctly does not bump `next_node_id` — it is consumed at
  agent-registration time). The old combined failure message
  `FAIL: graph state not advanced` conflated both checks, misleading the
  t807 reviewer into filing this task against the apply path.
- Commit `b6ef56b7` ("bug: Fix patcher CLI test next_node_id assertion
  (t810)") corrected the assertion to `next_node_id: 1` and split the
  message. t816 (created 11:20) and t810 (landed 11:35) were two
  diagnoses of the same failing test; t810's was the correct one.

Archived as resolved with no code changes.
