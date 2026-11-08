---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_relations, setup]
gates: [risk_evaluated]
anchor: 1981
followup_kind: upstream_defect
created_at: 2026-11-08 10:46
updated_at: 2026-11-08 10:46
---

## Origin

Spawned from t1981_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:5915-5967` — `ensure_*` writes are committed at :5915 (`commit_setup_metadata_writes`), but the venv (PyYAML) is only set up afterwards (`setup_python_venv`). Any setup question that writes YAML through Python must therefore run after the venv and commit itself. t1981_3's `ask_relations_activation` calls `_flush_metadata_batch` directly for this reason. It is an ordering constraint rather than a bug, and it is easy to get wrong: a later question would have its write committed by `commit_framework_data_files` at best, or left uncommitted.

## Diagnostic context

While adding the relations activation question to `ait setup` (t1981_3), the natural placement next to the other `ensure_*` passes, before `commit_setup_metadata_writes`, was impossible. The question writes `relations.enabled` through `lib/relations_config.py`, which imports PyYAML, and on a fresh install that is only available once `setup_python_venv` has run. The helper was therefore placed after `report_testmap_state` and commits its own write through `_flush_metadata_batch 0 aitasks/metadata/project_config.yaml`.

## Suggested fix

Either add a second, late `commit_setup_metadata_writes` pass after the venv-dependent questions, so `_note_metadata_write` works there too, or document the constraint next to `commit_setup_metadata_writes` and in `aidocs/framework/aitasks_extension_points.md` ("editing aitask_setup.sh").
