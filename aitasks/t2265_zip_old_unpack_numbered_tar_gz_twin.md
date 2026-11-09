---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_relations]
anchor: 1981
followup_kind: upstream_defect
created_at: 2026-11-09 22:33
updated_at: 2026-11-09 22:33
---

## Origin

Spawned from t2254 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_zip_old.sh:386-393` — `cmd_unpack`'s `search_list` omits the numbered `.tar.gz` twin (`_bN/oldM.tar.gz`) that `_find_archive_for_task` / `_search_numbered_then_legacy` fall back to (`lib/archive_utils.sh:345`). `ait zip-old unpack <N>` therefore cannot restore a task from a numbered `.tar.gz` bundle that the resolvers can still read.

## Diagnostic context

t2254 made `aitask_archive.sh` read archived child records from every bundle layout that producers write, and enumerated those layouts first:
- the numbered bundle `archive_path_for_id` returns (`.tar.zst`);
- its `.tar.gz` twin, which `_find_archive_for_task` and `_search_numbered_then_legacy` check "for backward compatibility";
- the legacy `old.tar.zst` / `old.tar.gz`.

`cmd_unpack` builds its own candidate list from `archive_path_for_id` (the `.tar.zst` path only) plus the two legacy files. A task stored in a numbered `.tar.gz` bundle (an un-migrated pre-zst repository; see `tests/test_migrate_archives.sh`) can be found by `resolve_task_file`, but `unpack` reports `NOT_IN_ARCHIVE` for it.

## Suggested fix

Add the numbered `.tar.gz` twin (`${archive_path%.tar.zst}.tar.gz`) to `cmd_unpack`'s `search_list`, between the numbered `.tar.zst` and the legacy files. Skip it when the `.tar.zst` exists, as `_search_all_archives` does. Add a `tests/test_zip_old.sh` case that unpacks a task from a numbered `.tar.gz` bundle.
