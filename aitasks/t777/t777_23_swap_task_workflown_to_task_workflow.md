---
priority: high
effort: low
depends: [t777_22, t777_6]
issue_type: chore
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-18 12:47
updated_at: 2026-05-19 11:51
---

## Context

Atomic rename of the staged `.claude/skills/task-workflown/` directory back to `.claude/skills/task-workflow/` after t777_6 (pilot pick conversion) lands AND its manual verification passes.

The staging pattern was introduced by t777_7 per the `feedback-stage-under-parallel-name` memory rule: never overwrite an actively-running skill directly. Until this swap runs, the LIVE `task-workflow/` directory stays untouched and continues to serve every skill (aitask-pick, board, monitor, etc.); only the staged `task-workflown/` carries the Jinja-wrapped profile-check sites that t777_6 and later siblings depend on.

## Depends on

- **t777_6** — pilot pick conversion. Must land AND its manual-verification follow-up must have passed (the whole point of staging is to defer the swap until rendered output is proven correct end-to-end).

## Scope (single commit)

1. Delete `.claude/skills/task-workflow/` (the unwrapped originals).
2. `git mv .claude/skills/task-workflown .claude/skills/task-workflow`.
3. String-replace `task-workflown` → `task-workflow` inside every file under `.claude/skills/` (and `.agents/skills/`, `.gemini/skills/`, `.opencode/skills/` if mirroring has happened by then) that references the staged dir. Concretely:
   - `aitask-pick/SKILL.md.j2` (t777_6's pilot template).
   - Any t777_8..t777_15 templates that landed between t777_7 and this swap.
   - `tests/golden/procs/task-workflown/` → `tests/golden/procs/task-workflow/` (rename + path references in the test script).
   - `tests/test_skill_render_task_workflown.sh` → `tests/test_skill_render_task_workflow.sh` (rename + internal path refs).
   - Frontmatter `name: task-workflown` → `name: task-workflow` (in the SKILL.md of the moved directory; the description marker `[t777_7 staged]` should be removed too).
4. Run `./ait skill verify` — must exit 0.
5. Live smoke from a fresh agent session: `/aitask-pick <some_task>` works exactly as before the staging started.

## Verification

- `./ait skill verify` exits 0.
- `bash tests/test_skill_render_task_workflow.sh` (after rename) passes.
- `bash tests/test_skill_template.sh` and `bash tests/test_skill_render.sh` still pass.
- No file still references `task-workflown`: `grep -rln "task-workflown" .claude/ .agents/ .gemini/ .opencode/ tests/ aidocs/ CLAUDE.md` returns nothing.
- Fresh-session smoke of `/aitask-pick` from outside the current tmux session (per the "tmux-stress tasks" CLAUDE.md rule, although this swap is not tmux-stress; the smoke is just routine validation).

## Out of scope

- Re-running the wrap process — the wraps are already in `task-workflown/`. This task only moves them.
- Any new wraps or template changes — those are owned by their respective task IDs.
