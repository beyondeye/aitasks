---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [skills, aitask_explore, task_workflow]
gates: [risk_evaluated]
created_at: 2026-10-15 23:04
updated_at: 2026-10-15 23:04
---

## Goal

When aitask-explore finishes creating a task, it asks "Continue to
implementation / Save for later" with the question text
`"Task created successfully. How would you like to proceed?"`. The prompt
should also name the task that was just created. Proposed text:
`"Task t<N> created successfully. How would you like to proceed?"`. The user
can then see which task they are deciding about, and which id to pass to
`/aitask-pick` later, without scrolling back.

## Where the text comes from

- The prompt is rendered by the shared Jinja macro `auto_continue_block` in
  `.aitask-scripts/skill_templates/_auto_continue_block.j2`. The macro emits
  `- Question: "{{ question }}"`, and each caller supplies its own `question=`
  string.
- `.claude/skills/aitask-explore/SKILL.md.j2` (Step 4, ~line 323) passes
  `question="Task created successfully. How would you like to proceed?"`.
- The task ID is already known at that point: Step 3 reads back the created file
  (`./ait git log -1 --name-only ... | grep '^aitasks/t'`) to confirm the
  assigned ID.
- **Precedent:** `.claude/skills/aitask-fold/SKILL.md.j2:78` already includes
  the ID: `"Tasks folded successfully into t\\<primary_id\\>. How would you like to proceed?"`.
  Follow the same escaping style (`t\\<N\\>` in the macro argument).

## Scope: make the sibling skills consistent

The same bare text appears in the other post-creation decision points. Update
all of them so the prompt reads the same everywhere:

| Skill template | Current question | Proposed |
|---|---|---|
| `aitask-explore/SKILL.md.j2` (macro call) | `Task created successfully. …` | `Task t\<N\> created successfully. …` |
| `aitask-pr-import/SKILL.md.j2:259` (macro call) | `Task created successfully. …` | `Task t\<N\> created successfully. …` |
| `aitask-revert/SKILL.md.j2:626` (macro call) | `Revert task created successfully. …` | `Revert task t\<N\> created successfully. …` |
| `aitask-review/SKILL.md.j2:243` (inline, not the macro) | single task: `Task created successfully. …` | `Task t\<N\> created successfully. …`. For the parent+children branch (`Tasks created. …`), consider `Tasks created under parent t\<N\>. …` |

Optional, at the implementer's discretion: the macro's auto-continue display
line (`Profile '<name>': continuing to implementation`) could also carry the ID.
No committed profile sets `explore_auto_continue`, so this is low value.

## Cross-agent coverage

The Codex (`.agents/skills/aitask-explore-*-codex-/`) and OpenCode variants are
rendered from the same `.claude/skills/<skill>/SKILL.md.j2` source by
`aitask_skill_render.sh --agent <agent>`. A single template edit therefore
covers every agent, and no separate porting task is needed.

## Tests and goldens that pin the exact string

- `tests/test_skill_render_aitask_explore.sh:96`
- `tests/test_skill_render_aitask_pr_import.sh:92`
- `tests/test_skill_render_aitask_revert.sh:95`
- `tests/test_skill_render_aitask_review.sh:94`

Update each `assert_contains` to the new text. Regenerate the affected goldens
in the same commit:
`tests/golden/skills/{aitask-explore,aitask-pr-import,aitask-revert,aitask-review}/SKILL-{default,fast,remote}-claude.md`
(see "Regenerate goldens after any `.md.j2` or closure edit" in
`aidocs/framework/skill_authoring_conventions.md`). Also update the
`question` parameter doc in the `_auto_continue_block.j2` header comment if its
example wording changes.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- The four `tests/test_skill_render_aitask_*.sh` files pass.
- Render explore for each profile
  (`./.aitask-scripts/aitask_skill_render.sh aitask-explore --profile <p> --agent claude`)
  and confirm the Step 4 question contains `t\<N\>`.
