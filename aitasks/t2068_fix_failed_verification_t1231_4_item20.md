---
priority: medium
effort: medium
depends: [1231_3]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1065
followup_kind: verification_failure
created_at: 2026-10-19 16:37
updated_at: 2026-10-19 16:37
---

## Failed verification item from t1231_3

> [t1231_3] Confirm the settings reference tables now match the live TUI — every tab, every key, including the previously-missing Shortcuts row.

### Source

- **Manual-verification task:** `aitasks/t1231/t1231_4_manual_verification_configurable_git_branch_artifact_backend.md` (item #20)
- **Origin feature task:** t1231_3
- **Origin archived plan:** `aiplans/archived/p1231/p1231_3_artifact_documentation.md`

### Commits that introduced the failing behavior

- a8a32dffc documentation: Document ait artifact, its backends and the Artifacts settings tab (t1231_3)

### Files touched by those commits

- aidocs/unified_artifact_design.md
- seed/project_config.yaml
- tests/test_website_doc_lists.sh
- website/content/docs/commands/artifact.md
- website/content/docs/commands/_index.md
- website/content/docs/concepts/artifacts.md
- website/content/docs/concepts/attachments.md
- website/content/docs/concepts/git-branching-model.md
- website/content/docs/concepts/implementation-trails.md
- website/content/docs/concepts/_index.md
- website/content/docs/development/task-format.md
- website/content/docs/skills/aitask-trail.md
- website/content/docs/tuis/settings/how-to.md
- website/content/docs/tuis/settings/_index.md
- website/content/docs/tuis/settings/reference.md
- website/content/docs/workflows/implementation-trails.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1231_4 item #20.
