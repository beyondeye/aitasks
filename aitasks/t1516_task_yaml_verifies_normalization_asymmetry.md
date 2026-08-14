---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_metadata, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1468
followup_kind: upstream_defect
created_at: 2026-08-13 23:29
updated_at: 2026-08-14 16:21
---

## Origin

Spawned from t1468_6 during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/task_yaml.py:151` — `parse_frontmatter` normalizes task-id
lists for `depends` / `children_to_implement` / `folded_tasks` but **not** for
`verifies`, while `aitask_update.sh`'s serializer **does** canonicalize
`verifies` on write. The asymmetry means any read-modify-write silently
rewrites `verifies: ['635_11']` to `verifies: [t635_11]`.

## Diagnostic context

Surfaced by the t1468_6 `followup_kind` backfill, which drove
`aitask_update.sh --batch --followup-kind` over 167 tasks. Its delta assertion
compared each file before/after and flagged 19 files whose `verifies` field had
changed although the backfill never touched it:

- `t1015` `['635_11']` -> `['t635_11']`
- `t1243_15` `['1243_3', ...]` -> `['t1243_3', ...]` (11 ids)
- plus 17 more, all aggregate manual-verification tasks.

No data is lost — the two forms denote the same task ids, and the `t`-prefixed
form is the canonical one the writer emits. The problem is that a *reader*
comparing the two forms sees a spurious diff, and any tool that round-trips a
task file produces an unrelated change in its output. The backfill had to widen
its own delta check to tolerate this (`_norm_scalar` in
`.aitask-scripts/lib/followup_backfill_classify.py`), which is a workaround for
the asymmetry rather than a fix.

## Suggested fix

Add `verifies` (and audit `risk_mitigation_tasks` for the same issue) to the
normalization tuple at `task_yaml.py:151`, so read and write agree on the
canonical form. Check `tests/test_aitask_merge.py` and the board fixtures for
assertions that pin the un-normalized shape before changing it.
