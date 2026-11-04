---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework, codeagent]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-04 23:21
updated_at: 2026-11-04 23:21
---

## Origin

Spawned from t2198 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_audit_wrappers.sh:474-487 — helper_present_in_touchpoint() ignores the decision for Codex touchpoints 3/6 (a decision = "forbidden" rule audits as covered, reproduced in a scratch fixture) and matches Claude touchpoints 1/4 anywhere in the file (a permissions.deny entry would audit as covered); fix: require decision = "allow" for 3/6 and permissions.allow membership for 1/4 (parse the JSON), with forbidden/deny negative controls — apply-helper-whitelist short-circuits on the pattern match too, so it would not repair a forbidden rule`

## Diagnostic context

A plan review in t2198 raised this, and I confirmed it in an isolated fixture
(a git-initialised scratch dir holding copies of the five touchpoint files). With seed Codex's
`aitask_gate_record.sh` rule changed from `decision = "allow"` to
`decision = "forbidden"`, `audit-helper-whitelist aitask_gate_record.sh` still
reported nothing for touchpoint 6. The matcher only greps for
`pattern = ["./.aitask-scripts/<helper>"]`. For touchpoints 1/4 it greps
`Bash(./.aitask-scripts/<helper>:*)` anywhere in the file, so an entry under
`permissions.deny` / `permissions.ask` would also count as covered. Neither
Claude file has those keys today, so that half is a latent problem. Touchpoint 7
already requires `": "allow"`.

t2198 added `tests/test_helper_whitelist_coverage.sh`. It calls the real audit,
and its header documents this claim boundary. Once the matcher here is fixed,
that test gets the stronger check without any change.

## Suggested fix

In `helper_present_in_touchpoint()`, require `decision = "allow"` on the
matching `prefix_rule` line for 3/6. For 1/4, check membership of
`permissions.allow` by parsing the JSON, not by grepping the file. Add negative
controls: an explicit `forbidden` Codex rule and a Claude `deny` entry.
`insert_codex_prefix_rule` / `apply-helper-whitelist` short-circuit on the
pattern match, so decide what apply should do when a non-allow rule exists:
report it, never silently add a second rule.
