---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, documentation]
created_at: 2026-04-21 12:28
updated_at: 2026-04-21 12:28
boardidx: 40
---

For any task whose scope includes documentation review, coherence, or accuracy, the planning phase must launch at least one Explore agent with an explicit **source-vs-docs verification** mission — not just docs-vs-docs. Bake the concrete drift list into the plan as first-class scope items per child task.

## Context & motivation

This task was created during t612 (consolidation of Claude Code auto-memory into durable docs). The memory entry `feedback_docs_vs_source.md` recorded the following incident on t594:

> User rejected a documentation-sweep plan built from a docs-vs-docs quality pass alone, explicitly saying "you are encouraged to check the actual source code of the framework and verify documentation content against actual source code." Running the source-vs-docs verification then surfaced concrete drift that no docs-vs-docs sweep could have found — a fabricated `Ctrl+Backslash` keybinding in the Board TUI reference page, 12+ missing `ait update` flags, an undocumented Settings `t` key for the Tmux tab, and a fast-profile behavior contradiction (docs said "stops after plan approval", YAML said `post_plan_action: ask`).

Source code is the authority; adjacent doc pages are not. Docs drift as code evolves; a docs-vs-docs sweep finds wording repetitions but misses fabricated claims, renamed flags, removed features, and added-but-undocumented behavior.

This rule belongs in `.claude/skills/task-workflow/planning.md` (and possibly `.claude/skills/aitask-explore/SKILL.md` under the "Explore documentation" exploration strategy) because it is workflow-internal and should port to `.opencode/`, `.gemini/`, `.codex/`, `.agents/` via the normal skill-mirroring procedure.

## Required changes

1. In `.claude/skills/task-workflow/planning.md`, add a dedicated section (or extend the Phase 1 exploration guidance) for documentation-scope tasks:
   - During planning, launch at least one Explore agent whose explicit mission is source-vs-docs verification.
   - Give it the authoritative source locations for each doc area:
     - TUI docs → TUI Python source (`.aitask-scripts/board/*.py`, `.aitask-scripts/monitor/*.py`, `.aitask-scripts/settings/*.py`, `.aitask-scripts/lib/tui_switcher.py`).
     - Skill docs → `.claude/skills/<name>/SKILL.md` and shared `.claude/skills/task-workflow/*.md`.
     - Command docs → `.aitask-scripts/aitask_*.sh` flag parsers.
     - Frontmatter/schema docs → `CLAUDE.md` + the relevant create/update scripts.
     - Profile/config docs → `aitasks/metadata/profiles/*.yaml`, `aitasks/metadata/*_config.{json,yaml}`.
   - Require the agent to produce concrete citations on both sides (doc path:line quote + source path:line quote) — not impressions.
   - Bake the drift list into the plan as first-class scope items per child task. Each child task's plan should include the specific drift items and authoritative source paths so a fresh-context implementer doesn't need to rediscover them.
   - Child task verification steps should include source-vs-docs diff commands where practical (e.g., `diff <(grep --flags script.sh) <(grep --flags docs.md)`).

2. In `.claude/skills/aitask-explore/SKILL.md`, under the "Explore documentation" exploration strategy (Step 1, Option: Explore documentation), extend the strategy to explicitly include source-vs-docs verification — not just doc-area mapping.

## Follow-up aitasks (create during implementation)

Create sibling/follow-up aitasks to mirror the planning.md / aitask-explore updates into the ported trees:

- `.opencode/skills/task-workflow/planning.md` and `.opencode/skills/aitask-explore/`
- `.gemini/skills/task-workflow/planning.md` and `.gemini/skills/aitask-explore/` (and/or `.gemini/commands/` equivalent)
- `.codex/prompts/` and `.agents/skills/task-workflow/planning.md`

## Acceptance

- [ ] `task-workflow/planning.md` includes the source-vs-docs verification requirement for doc-scope tasks
- [ ] `aitask-explore/SKILL.md` "Explore documentation" strategy mentions source-vs-docs verification with authoritative source locations
- [ ] Follow-up aitasks exist for each non-Claude agent tree

## Origin

Extracted from `~/.claude/projects/-home-ddt-Work-aitasks/memory/feedback_docs_vs_source.md` during t612 (the memory file has since been deleted).
