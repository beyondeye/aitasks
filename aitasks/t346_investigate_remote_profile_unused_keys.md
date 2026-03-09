---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [execution_profiles]
created_at: 2026-03-09 15:01
updated_at: 2026-03-09 15:01
boardidx: 90
boardcol: now
---

Investigate whether the `skip_task_confirmation` and `complexity_action` keys in `aitasks/metadata/profiles/remote.yaml` should remain as-is, be removed from the canonical remote profile and related docs, or gain real workflow support.

Current findings from the investigation done during t342:
- `run_location` is no longer part of the active `/aitask-pick` workflow and appears to be a stale/legacy key.
- In `.claude/skills/aitask-pickrem/SKILL.md`, `skip_task_confirmation` is explicitly documented as hardcoded/not used in remote mode.
- `complexity_action` is documented in the remote profile schema, but the current remote workflow appears to hardcode single-task behavior instead of reading this key.
- `/aitask-pickweb` ignores many remote-only keys; verify whether these two keys should also be considered ignored-only compatibility fields or should be cleaned up.

Relevant files to inspect:
- `.claude/skills/aitask-pickrem/SKILL.md`
- `.claude/skills/aitask-pickweb/SKILL.md`
- `.claude/skills/task-workflow/profiles.md`
- `website/content/docs/skills/aitask-pickrem.md`
- `website/content/docs/skills/aitask-pick/_index.md`
- `aitasks/metadata/profiles/remote.yaml`

Expected outcome of this follow-up task:
- confirm which of these keys are intentionally retained for compatibility versus actually supported by workflow logic
- decide whether to remove stale references/profile fields or implement missing behavior
- document the chosen direction and then apply the corresponding fix in a separate implementation step if needed

Decision is still pending. Do not assume removal versus implementation until that direction is chosen.
