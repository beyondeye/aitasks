---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [ait_cli, aitask_create, cross_repo]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-25 17:17
updated_at: 2026-05-25 17:38
---

## Context

First implementation step of t826's brainstorm: introduces the canonical
project-identity field in `project_config.yaml`, a per-user persistent
registry (`~/.config/aitasks/projects.yaml`), a logical-name resolver, and
the consumer surface needed to spawn cross-repo tasks without hardcoding
sibling-directory paths. After this child lands, the next child (t826_2) can
wire the TUI switcher to surface registered-but-inactive projects, and the
last child (t826_3) can document the user-facing workflow.

Background from parent brainstorm:
- The framework already has `tmux set-environment -g
  AITASKS_PROJECT_<session>=<root>` set by `ait ide:109`, and
  `discover_aitasks_sessions()` in
  `.aitask-scripts/lib/agent_launch_utils.py:255` that enumerates live tmux
  sessions. The piece this task adds is **persistence across tmux
  lifetimes** plus a logical-name lookup that doesn't require both projects
  to be open.

## Key Files to Modify

- `seed/project_config.yaml` — add commented `project: { name, git_remote }` template block.
- `aitasks/metadata/project_config.yaml` — populate the new block for this repo.
- `ait` — add `projects)` dispatcher case (around line 190); add `projects` to the no-update-check exemption (line 169).
- `.aitask-scripts/aitask_ide.sh:109` — after the existing `tmux set-environment` call, invoke `"$SCRIPTS_DIR/aitask_projects.sh" add "$(pwd)" >/dev/null 2>&1 || true`.
- `.aitask-scripts/aitask_create.sh` — add `--project <name>` batch-mode flag (resolve → `cd` → `exec` into resolved root; mutually exclusive with `--parent`; require `--batch`).
- `CLAUDE.md` — add short "Cross-Repo Coordination" pointer under Project-Specific Notes.

## Key Files to Create

- `.aitask-scripts/aitask_project_resolve.sh` — internal resolver helper. Argument `<name>`. Output: `RESOLVED:<root>` / `NOT_FOUND:<name>` / `STALE:<name>:<path>`. Resolution order: (1) live tmux scan via `discover_aitasks_sessions`, (2) per-user index, (3) `AITASKS_PROJECT_<name>` env var.
- `.aitask-scripts/aitask_projects.sh` — `ait projects` dispatcher. Verbs: `list`, `add [<path>]`, `resolve <name>`, `exec <name> -- <cmd>`.
- `aidocs/cross_repo_references.md` — design + authoring convention reference (registry schema, resolver semantics, cross-repo notation `aitasks#835_3` preferred / `aitasks#t835_3` accepted, pattern `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`).
- `tests/test_project_resolve.sh` — matrix: resolve-by-live-session, resolve-by-index, NOT_FOUND, STALE, fallback through legacy env var.
- `tests/test_projects_cmd.sh` — smoke: list/add/resolve/exec round-trip using a fake-repo scaffold.
- `tests/test_create_project_flag.sh` — `aitask_create.sh --batch --project <name>` creates the task in the resolved root, rejects `--project` without `--batch`, rejects `--project` combined with `--parent`.

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_launch_utils.py:74-85` (`AitasksSession` dataclass) and `:255-316` (`discover_aitasks_sessions`) — already-implemented live-tmux enumeration; reuse from Python invocation in the resolver helper.
- `.aitask-scripts/aitask_query_files.sh` — canonical `KEY:value` stdout-parsing convention for helper output.
- `.aitask-scripts/aitask_ide.sh:109` (existing `tmux set-environment` line) — site for the auto-population hook.
- `tests/lib/test_scaffold.sh::setup_fake_aitask_repo` — required scaffolding for any new helper test (per CLAUDE.md, system libs in `./ait`'s source-on-startup chain must also be added here; this task adds NO new lib, so scaffold needs no update, but verify before merging).
- Existing batch-flag handler in `aitask_create.sh` (`--parent`, `--name`, etc.) — pattern for adding `--project`.

## Implementation Plan

1. **Schema** — write `seed/project_config.yaml` template addition; populate `aitasks/metadata/project_config.yaml`.
2. **Resolver** — implement `aitask_project_resolve.sh`. Shell out to `python3 -c` to call `discover_aitasks_sessions()` for the live-tmux path. Read YAML index via simple grep/awk (no PyYAML dep needed for a flat list).
3. **`ait projects` dispatcher** — implement `aitask_projects.sh` with the 4 verbs. `add` writes atomically (`mktemp` + `mv`). `list` annotates each row with `LIVE` / `OK` / `STALE`. `exec` resolves then `exec`s with `cd`.
4. **Wire** — `ait:169` exemption + `ait:190` case; `aitask_ide.sh:109` post-hook.
5. **`aitask_create.sh --project`** — flag parser; mutual-exclusion checks; resolve → `cd` → `exec` self with cleaned-up argv (drop `--project <name>` from forwarded args).
6. **Docs** — `aidocs/cross_repo_references.md` (registry schema + notation convention); `CLAUDE.md` pointer.
7. **Tests** — three test scripts above. Run them; iterate to green.
8. **Lint** — `shellcheck .aitask-scripts/aitask_project_resolve.sh .aitask-scripts/aitask_projects.sh` and modified files.

## Verification Steps

- `bash tests/test_project_resolve.sh && bash tests/test_projects_cmd.sh && bash tests/test_create_project_flag.sh` — all pass.
- `shellcheck .aitask-scripts/aitask_project_resolve.sh .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_ide.sh ait` — clean.
- Manual end-to-end on the workstation:
  1. `cd /home/ddt/Work/aitasks && ait projects add` — confirm entry in `~/.config/aitasks/projects.yaml` with `name: aitasks`.
  2. `cd /home/ddt/Work/aitasks_mobile && ait projects add` — confirm second entry.
  3. `ait projects list` — both shown with statuses.
  4. `ait projects resolve aitasks` — prints `/home/ddt/Work/aitasks`.
  5. `ait projects exec aitasks -- pwd` — prints the resolved root.
  6. From `aitasks_mobile`: `ait create --batch --project aitasks --name cross_repo_test --type chore --priority low --effort low --commit` — confirm task lands in `/home/ddt/Work/aitasks/aitasks/`. Clean up the test task afterward.

## Out of Scope

- Adding `project:` block to sister `aitasks_mobile/aitasks/metadata/project_config.yaml` — user does this in the sister repo (or via a separate cross-repo bump task once `ait projects add` is shippable).
- Parser/tooling for the `aitasks#835_3` notation.
- Cross-project parent linkage (`--project X --parent Y`).
- Auto-clone from `git_remote` when resolver returns `NOT_FOUND`.
- `ait projects remove` / `ait projects prune` verbs.

## References

- Parent plan: `aiplans/p826_brainstorm_cross_repo_project_references.md`
- Origin pain point: `aitasks_mobile/aitasks/archived/t13/t13_2_sister_qr_add_hostname_field.md` (the sister task was `aitasks#822_5`, plan had to spell out `../aitasks/` everywhere).
