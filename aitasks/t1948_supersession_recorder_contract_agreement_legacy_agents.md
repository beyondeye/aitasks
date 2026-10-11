---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent, models, model_selection]
gates: [risk_evaluated]
anchor: 1916
followup_kind: upstream_defect
created_at: 2026-10-11 19:12
updated_at: 2026-10-11 19:12
---

## Origin

Spawned from t1940 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/model_supersession.py:_declare` — for claudecode/codex a cross-family edge is still only `WARN:family`, yet `ShippedTableTests` rejects it, so a `promote-config` that records such an edge would produce a table failing its own contract (pre-existing recorder/contract disagreement; opencode is now strict).

## Diagnostic context

t1940 made the supersession recorder and the shipped-table contract agree for
OpenCode:

- `STRICT_AGENTS = ("opencode",)`.
- `_declare` emits `BLOCKED:unlisted_old` / `BLOCKED:family` /
  `BLOCKED:variant` for every edge that `edge_contract_problems()` (the single
  statement of the contract, now used by
  `ShippedTableTests.test_every_edge_meets_the_contract`) would reject.

claudecode/codex were deliberately left on the legacy path:

- A cross-family edge records with `WARN:family`.
- An unregistered predecessor is not checked at all.
- `promote-config` can record edges implicitly, from seed defaults, so
  making it block would change promotion behaviour. That was out of t1940's
  scope.

The result: the recorder can still write a claudecode/codex edge that the
contract test rejects, and nothing catches it until the shipped-table test
runs.

## Suggested fix

Decide the policy for the legacy agents. One option is to extend
`STRICT_AGENTS` (blocking `family` and `unlisted_old` at record time) and have
`promote-config` surface the block through `SUPERSESSION_BLOCKED_HELP` (the
user can still pass `--no-supersession`). The other is to keep WARN and
document that the contract test is the gate.

Update the existing `test_family_warning_and_cross_agent_skip` (it pins WARN
today) and the legacy-predecessor pin in `OpencodeRecordTests`.
