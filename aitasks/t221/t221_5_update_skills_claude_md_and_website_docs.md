---
priority: medium
effort: medium
depends: [t221_2]
issue_type: refactor
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 11:15
updated_at: 2026-02-23 12:48
---

## Context

This is child task 5 of t221 (Move aitasks/aiplans to separate branch). The parent task implements a symlink + worktree architecture. This child task updates Claude Code skills, creates the `ait-git` safety net skill, updates CLAUDE.md for the aitasks repo itself, and updates website documentation.

Most skills delegate git operations to shell scripts (already updated in t221_2), but the **Task Abort Procedure** in `task-workflow/SKILL.md` has direct git commands that need updating. Additionally, a non-user-invocable skill ensures Claude always knows to use `ait git`.

## Key Files to Modify

1. **`.claude/skills/task-workflow/SKILL.md`** — Update Task Abort Procedure git commands
2. **`.claude/skills/ait-git/SKILL.md`** (NEW) — Non-user-invocable safety net skill
3. **`CLAUDE.md`** — Add `## Git Operations on Task/Plan Files` section
4. **`website/content/docs/board/reference.md`** — Update git operation documentation
5. **`website/content/docs/workflows/parallel-development.md`** — May need branch model updates
6. **`website/content/docs/development/_index.md`** — Document `aitask-data` branch alongside existing `aitask-ids`/`aitask-locks`

## Reference Files for Patterns

- `.claude/skills/task-workflow/SKILL.md` (lines 486-535): Task Abort Procedure with direct `git add aitasks/` + `git commit` calls
- `.claude/skills/aitask-pick/SKILL.md`: Example of non-user-invocable=false skill format
- `CLAUDE.md`: Existing structure with shell conventions, architecture, commit format sections
- `website/content/docs/board/reference.md` (lines 185-201): Board git operation docs

## Implementation Plan

### Step 1: Update Task Abort Procedure in task-workflow/SKILL.md

In the Task Abort Procedure section (lines ~509-525), replace:
```bash
git add aitasks/
git commit -m "ait: Abort t<N>: revert status to <status>"
```
With:
```bash
./ait git add aitasks/
./ait git commit -m "ait: Abort t<N>: revert status to <status>"
```

Also check for any other direct `git add aitasks/` or `git add aiplans/` or `git commit` calls in the skill that operate on task/plan files and update them similarly.

### Step 2: Create `.claude/skills/ait-git/SKILL.md`

Create a new non-user-invocable skill:

```markdown
---
name: ait-git
description: Git commands for aitasks/aiplans directories — use ./ait git instead of plain git
user-invocable: false
---

## Git Operations on Task/Plan Files

When running git commands that operate on files in `aitasks/` or `aiplans/` directories, **always use `./ait git` instead of plain `git`**. This ensures correct branch targeting when task data lives on a separate `aitask-data` branch.

### Usage

```bash
./ait git add aitasks/t42_foo.md
./ait git commit -m "ait: Update task t42"
./ait git push
./ait git status
```

### How it works

- If `.aitask-data/` worktree exists (branch mode): `ait git` routes to `git -C .aitask-data`
- If no worktree (legacy mode): `ait git` passes through to plain `git`

### When to use

- Any `git add`, `git commit`, `git push`, `git rm` involving files under `aitasks/` or `aiplans/`
- When committing task metadata changes (status, assignment, etc.)
- When archiving or creating task files

### When NOT to use

- For code-related git operations (implementation commits go on the main branch as normal)
- For `git log`, `git diff` on code files
- The aitask shell scripts already use `task_git()` internally — no need to wrap script calls
```

### Step 3: Update CLAUDE.md

Add a new section after the "Commit Message Format" section:

```markdown
## Git Operations on Task/Plan Files
When committing changes to files in `aitasks/` or `aiplans/`, use `./ait git`
instead of plain `git`. This ensures correct branch targeting when task data
lives on a separate branch.
- `./ait git add aitasks/t42_foo.md`
- `./ait git commit -m "ait: Update task t42"`
- `./ait git push`
In legacy mode (no separate branch), `ait git` passes through to plain `git`.
```

### Step 4: Update website documentation

Update `website/content/docs/board/reference.md`:
- Change git operation descriptions to mention `ait git` routing
- Note that the board auto-detects branch mode

Update `website/content/docs/development/_index.md`:
- Add `aitask-data` branch to the list of special branches
- Document the symlink + worktree architecture

## Verification Steps

1. **Skill file:** Verify `.claude/skills/ait-git/SKILL.md` is valid markdown with correct frontmatter
2. **Task workflow:** Read task-workflow/SKILL.md, verify all direct git operations on tasks use `./ait git`
3. **CLAUDE.md:** Verify the new section is well-placed and doesn't duplicate
4. **Website build:** `cd website && hugo build --gc --minify` — verify no build errors
