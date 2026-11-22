---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codeagent, models]
gates: [risk_evaluated]
anchor: 1884
followup_kind: upstream_defect
created_at: 2026-11-22 10:46
updated_at: 2026-11-22 10:46
---

## Origin

Spawned from t1885 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_opencode_models.sh:merge_with_existing` — the cli_id-keyed rename (registry `legacy_name` → derived name) renames the registry row, but the aitask-stats history stays keyed under the old name. The renamed model loses its usage and verification history, and the old name's history is orphaned.
- `tests/test_opencode_models_reserved.sh:run_refresh` / `tests/test_opencode_models_merge.sh:run_refresh` — forward an inherited `TASK_DIR`, so a run with `TASK_DIR` set writes the real registry it names (the same isolation defect fixed in the new collision test).

## Diagnostic context

t1885 added a row-identity guard to `aitask_opencode_models.sh` (refuses repeated names, a name shared with a different cli_id, repeated registry cli_ids). Review established that the usage and verification history now lives on the `aitask-stats` orphan branch, keyed `models.<name>` (`lib/model_stats_store.py`; `aidocs/framework/model_stats_store.md`). Renaming a registry row therefore never moves its history. The guard's recovery text avoids advising renames for that reason.

The guard deliberately still allows the merge's cli_id-keyed rename: a registry row `legacy_foo_bar` / `opencode/foo-bar` becomes `opencode_foo_bar` on refresh (pinned by `tests/test_opencode_models_merge.sh` test 2 and `tests/test_opencode_models_collision.sh` T6b). That path moves the inline `verified` / legacy counters with the row, but not the aitask-stats history stored under `legacy_foo_bar`.

Separately, `tests/test_opencode_models_collision.sh` pins `TASK_DIR=aitasks` in its `run_refresh` and checks an outside sentinel registry, because the script resolves `METADATA_DIR="${TASK_DIR:-aitasks}/metadata"`. The two older sibling tests have the same `run_refresh` shape without the pin.

## Suggested fix

- On a cli_id-keyed rename, move (or merge) the aitask-stats entry from the old name to the new one through `model_stats_store.update`. Alternatively, refuse the rename when the old name has history on the branch, with recovery text, as the t1885 guard does.
- Pin `TASK_DIR=aitasks` in the two sibling tests' `run_refresh` and add the same outside-sentinel check.
