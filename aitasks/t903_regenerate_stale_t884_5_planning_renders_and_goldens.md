---
priority: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [agents_md]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-02 10:21
updated_at: 2026-06-02 10:37
---

## Origin

Spawned from t901 during Step 8b review. Surfaced while regenerating rendered
skills/goldens for the aidocs reorganization — `aitask_skill_rerender.sh` and
`tests/test_skill_render_task_workflow.sh` revealed pre-existing drift from
commit t884_5 ("enhancement: Force-reverify task plan when a risk mitigation
lands"), unrelated to t901.

## Upstream defect

- `.claude/skills/task-workflow-remote-/planning.md`, `.opencode/skills/task-workflow-remote-/planning.md`, `.agents/skills/task-workflow-remote-codex-/planning.md` — stale renders: missing the "Step 6.0a Force-reverify" content present in their source `.claude/skills/task-workflow/planning.md` since commit t884_5 (rendered variants were not regenerated in that commit).
- `tests/golden/procs/task-workflow/SKILL-fast.md` and `tests/golden/procs/task-workflow/planning-fast.md` — stale goldens: `tests/test_skill_render_task_workflow.sh` Test 1 fails at HEAD for the `fast` profile (40- and 444-line diffs, no aidocs paths involved); a `.md.j2`/closure edit landed without regenerating these `fast` goldens.

## Diagnostic context

During t901, running `aitask_skill_rerender.sh {default,fast,remote}`
incidentally regenerated the 3 `planning.md` rendered variants (they were
stale). Those edits were reverted to HEAD to keep the t901 commit scoped to
the aidocs reorg. Separately, `bash tests/test_skill_render_task_workflow.sh`
fails 2 assertions at HEAD ("golden SKILL × fast", "golden planning × fast")
— confirmed pre-existing by rendering the committed HEAD sources against the
committed goldens (diffs contain no aidocs paths).

## Suggested fix

Run `aitask_skill_rerender.sh` for all profiles to refresh the rendered
`planning.md` variants, and regenerate the `fast`-profile procedure goldens
(`SKILL-fast.md`, `planning-fast.md`) via the loop in
`tests/test_skill_render_task_workflow.sh` (and the regenerate-goldens loop in
`aidocs/framework/skill_authoring_conventions.md`). Review the diffs, then
confirm `test_skill_render_task_workflow.sh` is green and
`aitask_skill_verify.sh` passes.
