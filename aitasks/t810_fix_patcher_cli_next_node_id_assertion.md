---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [brainstorm, test]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-20 07:55
updated_at: 2026-05-20 11:25
---

## Origin

Spawned from t808 during Step 8b review.

## Upstream defect

tests/test_brainstorm_apply_patcher_cli.sh:101-108 — the "graph state
advanced" assertion expects `next_node_id: 2` in `br_graph_state.yaml`
after a patcher apply, but `apply_patcher_output` (by design, per the
"next_node_id is consumed at registration time" comment in
`brainstorm_session.py`) never increments `next_node_id`. The test fails
with "FAIL: graph state not advanced".

## Diagnostic context

While reconciling the patcher apply path into the shared
`_apply_node_output()` core (t808), the patcher CLI test was run to
confirm no regression. It reported 6/7 passing. Running the same test
against the pre-t808 baseline (`git stash`) produced the identical 6/7
result — so the failure is pre-existing and unrelated to the t808
refactor.

The assertion checks two things on one line:
- `current_head: n001_cli_test` — passes (set_head works).
- `next_node_id: 2` — fails. `apply_patcher_output` does not touch
  `next_node_id`; the seeded `br_graph_state.yaml` keeps `next_node_id: 1`.

This mirrors explorer/synthesizer apply, which also leave `next_node_id`
to be consumed at agent-registration time (`register_patcher` /
`register_explorer` in `brainstorm_crew.py`).

## Suggested fix

Decide which side is correct and fix exactly one:
- If `next_node_id` is genuinely advanced at registration time (most
  likely — the apply functions all carry the same comment), the test
  assertion is wrong: drop the `next_node_id: 2` check, or seed the test
  fixture to call the registration path first.
- If the apply path *should* advance `next_node_id`, that is a real bug
  in `apply_patcher_output` (and likely the explorer/synthesizer applies
  too) — but the consistent code comments suggest the test is the
  defective side.
