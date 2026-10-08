---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [install, install_scripts, framework]
gates: [risk_evaluated]
created_at: 2026-10-08 23:35
updated_at: 2026-10-08 23:35
---

## Problem

`ait upgrade` / `install.sh` never removes `.aitask-scripts/` files that the
framework retired or moved. A leftover module can then **shadow** its moved
replacement and crash the TUI that imports it.

Observed 2026-10-08 in the registered project `thinking_app`, on framework
v0.36.1:

```
File ".../thinking_app/.aitask-scripts/board/aitask_board.py", line 65, in <module>
ImportError: cannot import name 'normalize_board_idx' from 'task_yaml'
  (/home/ddt/Work/thinking_app/.aitask-scripts/board/task_yaml.py)
```

- t1217 (`979b88968`, 2026-07-24) moved `task_yaml.py` from
  `.aitask-scripts/board/` to `.aitask-scripts/lib/`.
- thinking_app still has `.aitask-scripts/board/task_yaml.py`: 4616 bytes,
  mtime Jul 10, **tracked in thinking_app's git**. Its current
  `lib/task_yaml.py` (Oct 5) defines `normalize_board_idx`; the old board copy
  does not.
- `aitask_board.py` inserts `board/` **ahead of** `lib/` on `sys.path`
  (L13 inserts `lib`, then L17 inserts `board/` at index 0). The stale copy
  therefore wins the import.
- Since v0.36.1 the board imports `normalize_board_idx`, so every fresh
  `ait board` in thinking_app crashes at import. A board started before the
  upgrade keeps running until restarted. That is why the board in the
  `thinkingapp` tmux session still looked fine.
- The user hit this through the TUI switcher (`j` → board from the
  minimonitor in the `aitasks` session). The switcher only reached thinking_app
  because of the session-root mis-mapping in t1922. The crash itself is
  independent: any fresh thinking_app board fails.

## Cause

- `install.sh` extracts the release tarball over `$INSTALL_DIR`
  (`tar -xzf … -C "$INSTALL_DIR"`, ~L1503). Extraction is purely additive.
- The only retirement cleanup is `prune_retired_skills()`
  (`aitask_prune_retired_skills.sh`, invoked ~L967), and it covers **skill
  surfaces only**. Nothing prunes retired `.aitask-scripts/` files, so every
  project upgraded across a move or delete keeps the old file. It is also
  committed into the project's git, because `commit_framework_files` stages
  framework paths.

## Goal

- **Prune retired framework scripts on upgrade and setup**, following the
  existing retired-skills design:
  - a manifest of retired `.aitask-scripts/` paths;
  - ownership decided **by content hash**, so a user-modified file is kept and
    reported, never deleted;
  - deletions surfacing through the existing framework-commit staging.
- **Seed the manifest** with at least the t1217 move (`board/task_yaml.py`).
  Audit the git history for other deleted or moved paths under
  `.aitask-scripts/` (`git log --diff-filter=D --name-only -- .aitask-scripts/`)
  and add the hashes of every shipped version of each.
- **Consider defence in depth for the import shadowing.** The board puts its
  own directory ahead of `lib/`, so any future stale or user file in `board/`
  named like a `lib/` module shadows it again. Either assert at startup that
  shared modules resolve from `lib/`, or reorder the path, after checking the
  "board package" import contract in `aidocs/framework/tui_conventions.md`.
  Do the same check for the other TUIs that insert their own directory first.
- Read `aidocs/framework/aitasks_extension_points.md` first, since this edits
  the install flow.

## Tests

- **Fixture project upgrade:** it contains a pristine retired file (removed
  and staged), a user-modified retired file (kept with a warning), and an
  unrelated user file (untouched).
- **Regression for the shadowing:** with a `board/task_yaml.py` lacking
  `normalize_board_idx` present, the board's import of `task_yaml` must resolve
  to `lib/` or fail with a clear diagnostic, never an opaque ImportError.

## Workaround for an affected project

In that project, delete `.aitask-scripts/board/task_yaml.py`
(`git rm .aitask-scripts/board/task_yaml.py`, then commit it by name). Other
projects upgraded from before t1217 likely carry the same file.
