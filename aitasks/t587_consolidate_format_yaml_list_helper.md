---
priority: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [framework]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 11:17
updated_at: 2026-04-19 11:34
---

Move format_yaml_list() from aitask_create.sh:1182 and aitask_update.sh:393 into lib/task_utils.sh (alongside the existing parse_yaml_list / normalize_task_ids inverses). Delete both local copies. Collapse format_labels_yaml() and format_file_references_yaml() in aitask_create.sh:1192 and :1202 (byte-identical synonyms) into calls to the shared format_yaml_list. Add a unit test covering empty, single-entry, and multi-entry cases — extend tests/test_task_utils.sh if it exists, otherwise create tests/test_format_yaml_list.sh mirroring the bash-test style of tests/test_fold_file_refs_union.sh. Discovered while implementing t583_2; scope kept out of that task to keep the new-field diff focused. No new behavior — pure consolidation.
