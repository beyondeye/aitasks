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
./ait git commit -m "ait: Update task t42" -- aitasks/t42_foo.md
./ait git push
./ait git status
```

**The `-- <path>` is not optional.** `./ait git` is `task_git` in a subprocess, so
a `commit` with no pathspec commits the **entire** `.aitask-data` index — and that
index is shared by every session on the machine. Whatever a concurrent session has
staged at that instant lands in your commit, under a message naming your task.

### Scoped commits: prefer the helper

For task and plan files, prefer:

```bash
./.aitask-scripts/aitask_task_commit.sh -m "ait: Update task t42" aitasks/t42_foo.md
```

It replaces the `add` + `commit` pair. It stages only paths git does not track
yet (an `add` of a **tracked** path would replace the index entry another session
staged for it), unstages exactly those again if the commit fails, and refuses any
path outside `aitasks/`/`aiplans/`. It never pushes — `./ait git push` stays a
separate step.

<a id="helper-outcome-contract"></a>
**Outcome contract — read the whole output, and branch on the exit status; the
status is the authority.**

| Exit | Meaning |
|---|---|
| 0 | Committed. `COMMITTED:<n>:<subject>` |
| 2 | Nothing committed: `NOCHANGE` (the expected idempotent re-run), or `REFUSED:out_of_scope:<path>` — a path outside `aitasks/`/`aiplans/` reached the call; fix the caller, never retry |
| 1 | `FAILED:<detail>` — the file is written but uncommitted; report it |

**`SKIPPED:unknown:<path>` lines can precede any of those, including a successful
`COMMITTED:`.** The helper skips a path that is neither tracked nor on disk and
commits the rest, so a call can exit 0 having silently dropped a file you named.
Every call site must say which of its paths are **required** and which are
**optional**: a `SKIPPED:` naming a required path is a failure even at exit 0 —
report it and do not treat the commit as complete.

### How it works

- If `.aitask-data/` worktree exists (branch mode): `ait git` routes to `git -C .aitask-data`
- If no worktree (legacy mode): `ait git` passes through to plain `git`

### When to use

- Any `git add`, `git commit`, `git push`, `git rm` involving files under `aitasks/` or `aiplans/`
- When committing task metadata changes (status, assignment, etc.)
- When archiving or creating task files

### When NOT to use

- For code-related git operations. Implementation commits go on the main branch with plain `git` — and name their paths too, because `main` is shared by every session in this checkout the same way (`git commit -m "<msg>" -- <paths>`; see "Never instruct a bare `git commit` on `main`" in `aidocs/framework/skill_authoring_conventions.md`).
- For `git log`, `git diff` on code files
- The aitask shell scripts already use `task_git()` internally — no need to wrap script calls
