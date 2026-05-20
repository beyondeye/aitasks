---
Task: t810_fix_patcher_cli_next_node_id_assertion.md
Base branch: main
plan_verified: []
---

# Plan: Fix patcher CLI test `next_node_id` assertion (t810)

## Context

`tests/test_brainstorm_apply_patcher_cli.sh` is a CLI round-trip test for
`aitask_brainstorm_apply_patcher.sh`. Its "graph state advanced" assertion
(lines 101-108) checks two things on one `grep` chain after a patcher apply:

- `current_head: n001_cli_test` — **passes** (`set_head` runs in the apply core).
- `next_node_id: 2` — **fails**.

`apply_patcher_output` → `_apply_node_output()` in
`.aitask-scripts/brainstorm/brainstorm_session.py:964-967` deliberately does
**not** touch `next_node_id`. The code comment is explicit:

```
set_head(wt, new_node_id)
# next_node_id is consumed at registration time (see
# register_explorer / register_synthesizer / register_patcher in
# brainstorm_crew.py).
```

`next_node_id()` (`brainstorm_dag.py:136`) is only called by the three
`register_*` functions in `brainstorm_crew.py` (lines 530/615/699). The apply
path takes `node_id` verbatim from the agent output's `METADATA` block
(`n001_cli_test`), so the seeded `next_node_id: 1` is correct and unchanged
after apply. The test's expectation of `2` is wrong — the **test** is the
defective side, not the apply code. Result: 6/7 passing, pre-existing, unrelated
to t808 (confirmed by running against the pre-t808 baseline).

## Approach

Fix the test assertion (exactly one side, per the task — the test side). Rather
than just dropping the `next_node_id` check, assert the *correct* contract:
`next_node_id` stays at the seeded `1` after a patcher apply. This locks the
documented "consumed at registration time" behavior so a future regression
(an apply path wrongly incrementing the counter) is still caught. Also fix the
now-misleading PASS/FAIL message text ("graph state advanced" → head update).

## Change

**File:** `tests/test_brainstorm_apply_patcher_cli.sh` (lines 101-108)

Replace:

```bash
if grep -q "current_head: n001_cli_test" "$CREW_DIR/br_graph_state.yaml" \
   && grep -q "next_node_id: 2" "$CREW_DIR/br_graph_state.yaml"; then
    echo "PASS: graph state advanced"
    PASS=$((PASS + 1))
else
    echo "FAIL: graph state not advanced"
    FAIL=$((FAIL + 1))
fi
```

with:

```bash
# Head moves to the new node; next_node_id is left untouched by apply
# (it is consumed at agent-registration time, see register_patcher in
# brainstorm_crew.py), so it stays at the seeded value of 1.
if grep -q "current_head: n001_cli_test" "$CREW_DIR/br_graph_state.yaml" \
   && grep -q "next_node_id: 1" "$CREW_DIR/br_graph_state.yaml"; then
    echo "PASS: head updated, next_node_id untouched by apply"
    PASS=$((PASS + 1))
else
    echo "FAIL: head not updated or next_node_id wrongly changed"
    FAIL=$((FAIL + 1))
fi
```

No source-code change — `apply_patcher_output` behavior is correct as-is.

## Verification

Run the test; expect 7/7:

```bash
bash tests/test_brainstorm_apply_patcher_cli.sh
```

Expected tail: `Total: 7   Passed: 7   Failed: 0` and exit 0.

## Step 9

After approval/implementation: review, commit (`bug: ... (t810)`), and proceed
through Post-Implementation (archival, merge approval) per the shared workflow.
