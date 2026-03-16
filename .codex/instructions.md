# aitasks Framework — Codex CLI Instructions

<!-- Assembled from seed/aitasks_agent_instructions.seed.md + seed/codex_instructions.seed.md -->

This project uses the aitasks framework for task management.
Tasks are markdown files with YAML frontmatter stored in git.

## Task File Format

Task files use YAML frontmatter with these fields:

```yaml
---
priority: high|medium|low
effort: high|medium|low
depends: [1, 3]
issue_type: bug|feature|chore|documentation|performance|refactor|style|test
status: Ready|Editing|Implementing|Postponed|Done|Folded
labels: [ui, backend]
assigned_to: email
boardcol: now|next|backlog
boardidx: 50
folded_tasks: [2, 4]     # merged child tasks
folded_into: 1            # parent task ID if folded
issue: https://...        # linked issue tracker URL
---
```

## Task Hierarchy

Parent tasks live in `aitasks/` (e.g., `aitasks/t130_feature_name.md`).
Child tasks live in subdirectories: `aitasks/t130/t130_1_subtask.md`,
`t130_2_subtask.md`, etc. Children auto-depend on siblings.

Plans mirror the task structure: parent plans in `aiplans/`, child plans
in `aiplans/p130/p130_1_subtask.md`.

## Git Operations on Task/Plan Files

When committing changes to files in `aitasks/` or `aiplans/`, always use
`./ait git` instead of plain `git`. This ensures correct branch targeting
when task data lives on a separate branch.

- `./ait git add aitasks/t42_foo.md`
- `./ait git commit -m "ait: Update task t42"`
- `./ait git push`

In legacy mode (no separate branch), `./ait git` passes through to plain `git`.

## Commit Message Format

```
<type>: <description> (tNN)
```

Types match `issue_type` values: `bug`, `feature`, `chore`, `documentation`,
`performance`, `refactor`, `style`, `test`. Also `ait` for framework-internal
changes (task/plan file operations).

Code commits use `<type>: <description> (tNN)`. Plan/task file commits use
`ait: <description>`. Never mix code and task/plan files in the same commit.

## Skills

aitasks skills are available in `.agents/skills/`. Each skill is a wrapper
that references the authoritative Claude Code skill in `.claude/skills/`.
Read the wrapper for tool mapping guidance.

Invoke skills with `$skill-name` syntax (e.g., `$aitask-pick 16`).

## Agent Identification

When recording `implemented_with` in task metadata, construct `codex/<name>`.

1. Check `AITASK_AGENT_STRING` env var first — if set, use it directly.
2. If not set, read your configured model:
   `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
3. Run: `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent codex --cli-id <model_id>`
4. Parse the output — the value after the colon is your agent string.

**Do NOT guess your model ID from memory** — Codex models cannot reliably
self-identify. Always use the env var or config file method above.
