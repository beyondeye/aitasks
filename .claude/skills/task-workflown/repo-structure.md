# Repository Structure: Symlinks and Data Worktree

This project may use a separate `aitask-data` branch for task/plan file storage.
When this is active, the repository has an unusual layout that code agents must
understand.

## Architecture

- `.aitask-data/` — A git worktree checked out on the `aitask-data` orphan branch
- `aitasks/` — **Symlink** → `.aitask-data/aitasks/` (task files)
- `aiplans/` — **Symlink** → `.aitask-data/aiplans/` (plan files)

These symlinked directories belong to a **different git branch** than the source
code you are implementing. They appear at the project root for convenience but
are managed separately.

## Rules for Implementation

1. **Do NOT run `git add`, `git commit`, or `git diff` on files inside `aitasks/`
   or `aiplans/`** — use `./ait git` instead, which routes commands to the correct
   worktree and branch
2. **Do NOT be alarmed** by `aitasks/` and `aiplans/` appearing as symlinks in
   `ls -la` or `git status` output — this is expected behavior
3. **Do NOT attempt to resolve, delete, or recreate** the symlinks
4. **Focus implementation work on source code files only** — the workflow handles
   task/plan file operations via `./ait git` in Steps 8 and 9
5. **Never mix** code files and `aitasks/`/`aiplans/` files in the same `git add`
   or commit

## Detection

- If `.aitask-data/` exists (contains `.git`): the project is in **branch mode**
  — symlinks are active, `./ait git` routes to the data worktree
- If `.aitask-data/` does not exist: the project is in **legacy mode** — task
  files live on the main branch, `./ait git` passes through to plain `git`, and
  this document does not apply

## Common Confusion Points

- `git status` may show `aitasks/` and `aiplans/` as untracked or ignored — this
  is normal when they are symlinks to a separate worktree
- Running `git log -- aitasks/somefile.md` in the main worktree will show no
  history — the file's history is on the `aitask-data` branch
- File watchers or IDE indexers may follow the symlinks into `.aitask-data/` —
  this is harmless but can look confusing
