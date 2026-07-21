---
priority: medium
effort: medium
depends: [1194]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1194]
assigned_to: dario-e@beyond-eye.com
anchor: 1171
created_at: 2026-07-21 11:07
updated_at: 2026-07-21 13:11
completed_at: 2026-07-21 13:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1194

## Verification Checklist

- [x] Build a tarball and run `bash install.sh --local-tarball <tarball> --dir <scratch-project>`; confirm the run completes without error. — PASS 2026-07-21 13:07 auto: built release-equivalent tarball aitasks-v0.28.0.tar.gz per release.yml; install.sh --local-tarball --dir <scratch> exited 0
- [x] In the scratch project, confirm `aitasks/metadata/doc_update_guide.md` exists and matches `seed/doc_update_guide.md` (the docs_updated gate resolves this path at runtime, after seed/ is deleted). — PASS 2026-07-21 13:07 auto: aitasks/metadata/doc_update_guide.md present and byte-identical to seed/doc_update_guide.md (diff -q clean)
- [x] In the same project, confirm `aitasks/metadata/code_areas.yaml` exists and still carries its full comment/format header (it must be copied, never yaml-merged). — PASS 2026-07-21 13:07 auto: code_areas.yaml byte-identical to seed; full comment/format header intact (copied, not yaml-merged)
- [x] Confirm the pre-existing seeds still land: task_types.txt, project_config.yaml, chatlink_config.yaml, codeagent_config.json, models_*.json, gates.yaml, profiles/*.yaml, the codex/opencode/claude config seeds, and claude_settings.seed.json (renamed, NOT claude_settings.local.json). — PASS 2026-07-21 13:07 auto: all pre-existing seeds present incl. profiles/{default,fast,remote}.yaml and codex/opencode/claude config seeds; claude_settings.seed.json present, claude_settings.local.json absent
- [x] Confirm `seed/` was deleted by the installer, and that re-running install.sh --force does NOT overwrite a hand-edited doc_update_guide.md or code_areas.yaml. — PASS 2026-07-21 13:07 auto: seed/ absent after both installs; --force kept hand-edited doc_update_guide.md and code_areas.yaml (sha256 unchanged, 'exists (kept)' logged)
- [x] In a clean clone of the framework (seed/ present, install.sh never run), run `ait setup` and confirm aitasks/metadata/ ends up with the same file set as the tarball install above. — PASS 2026-07-21 13:09 auto: ait setup on a source-tree fixture (seed/ present, install.sh never run) produced an identical seed file set to the tarball install (20/20 incl. doc_update_guide.md + code_areas.yaml, profiles/*.yaml); only by-design extras differ - userconfig.yaml (per-user, setup-only) and the codex/opencode staging dirs (tarball-only transport; setup logs 'No Codex CLI staging files found - skipping' because the source tree owns .agents/skills and .opencode/skills directly)
- [x] Verify the t1147 invariant end-to-end: with seed/ absent but .aitask-scripts/gates_reference.yaml present, `ait setup` still produces aitasks/metadata/gates.yaml. — PASS 2026-07-21 13:09 auto: seedless fixture (no seed/, gates_reference.yaml present) - ait setup exited 0 and produced aitasks/metadata/gates.yaml byte-identical to .aitask-scripts/gates_reference.yaml; no seed-derived metadata fabricated (only gates.yaml + userconfig.yaml present), confirming the gate copy precedes the seed-dir guard
