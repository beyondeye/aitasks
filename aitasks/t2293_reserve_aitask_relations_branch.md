---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, artifacts]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-11-13 07:54
updated_at: 2026-11-13 07:54
---

## Origin
Spawned from t1912_1 during Step 8b review.

## Upstream defect
- `.aitask-scripts/lib/artifact_registry.py:58 — RESERVED_REFS omits aitask-relations (the relations orphan branch), so a gitbranch artifact store can be configured onto it while the branch does not exist yet; the same omission is in aitask_web_merge.sh:222 is_skip_branch and the seed/project_config.yaml reserved-ref comment`

## Diagnostic context
t1912_1 added the new `aitask-stats` orphan branch to every reserved-ref list:
- `lib/artifact_registry.py` `RESERVED_REFS`;
- the `seed/project_config.yaml` ~L357 comment;
- the `settings/settings_app.py` ~L453 gitbranch help text;
- `aitask_web_merge.sh` `is_skip_branch`, the set the `RESERVED_REFS` comment
  names as its source.

That sweep showed `aitask-relations` is missing from all of them, even though
`lib/relations_store.py:66-67` defines it as `refs/heads/aitask-relations`.

- `validate-ref` refuses an *existing* ordinary branch, so the hole matters only
  while the relations branch does not exist yet. That is the default state,
  since relations analysis is off by default.
- In that window, a gitbranch artifact store pointed at `aitask-relations` is
  accepted. Enabling relations later would then share one branch between two
  stores with different layouts.

## Suggested fix
- Add `aitask-relations` next to `aitask-stats` in `RESERVED_REFS`, the seed
  comment, the settings help text and `is_skip_branch`.
- Extend the reserved-ref loop in `tests/test_artifact_gitbranch_backend.sh`
  (~L145) to cover it.
