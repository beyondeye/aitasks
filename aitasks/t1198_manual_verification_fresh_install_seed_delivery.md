---
priority: medium
effort: medium
depends: [1194]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1194]
created_at: 2026-07-21 11:07
updated_at: 2026-07-21 11:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1194

## Verification Checklist

- [ ] Build a tarball and run `bash install.sh --local-tarball <tarball> --dir <scratch-project>`; confirm the run completes without error.
- [ ] In the scratch project, confirm `aitasks/metadata/doc_update_guide.md` exists and matches `seed/doc_update_guide.md` (the docs_updated gate resolves this path at runtime, after seed/ is deleted).
- [ ] In the same project, confirm `aitasks/metadata/code_areas.yaml` exists and still carries its full comment/format header (it must be copied, never yaml-merged).
- [ ] Confirm the pre-existing seeds still land: task_types.txt, project_config.yaml, chatlink_config.yaml, codeagent_config.json, models_*.json, gates.yaml, profiles/*.yaml, the codex/opencode/claude config seeds, and claude_settings.seed.json (renamed, NOT claude_settings.local.json).
- [ ] Confirm `seed/` was deleted by the installer, and that re-running install.sh --force does NOT overwrite a hand-edited doc_update_guide.md or code_areas.yaml.
- [ ] In a clean clone of the framework (seed/ present, install.sh never run), run `ait setup` and confirm aitasks/metadata/ ends up with the same file set as the tarball install above.
- [ ] Verify the t1147 invariant end-to-end: with seed/ absent but .aitask-scripts/gates_reference.yaml present, `ait setup` still produces aitasks/metadata/gates.yaml.
