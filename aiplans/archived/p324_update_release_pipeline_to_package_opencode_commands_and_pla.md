---
Task: t324_update_release_pipeline_to_package_opencode_commands_and_pla.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Package OpenCode commands and planmode prerequisites (t324)

## Context

The release bundle currently stages OpenCode skill wrappers and only one shared helper file (`opencode_tool_mapping.md`). Task `t324` requires extending the pipeline so OpenCode command wrappers and the plan-mode prerequisites helper are packaged and installed consistently.

## Implementation Steps

1. Update `.github/workflows/release.yml` OpenCode build step:
   - Copy `.opencode/commands/` into a new `opencode_commands/` staging directory when present.
   - Copy `.opencode/skills/opencode_planmode_prereqs.md` into `opencode_skills/` alongside `opencode_tool_mapping.md`.
   - Include `opencode_commands/` in the release tarball list.

2. Update `install.sh` in `install_opencode_staging`:
   - Ingest staged `opencode_commands/` from the tarball and store it under `aitasks/metadata/opencode_commands/`.
   - Continue storing staged OpenCode skills and copy both helper docs (`opencode_tool_mapping.md`, `opencode_planmode_prereqs.md`) into `aitasks/metadata/opencode_skills/`.

3. Update `aiscripts/aitask_setup.sh` in `setup_opencode`:
   - Install staged commands from `aitasks/metadata/opencode_commands/` to `.opencode/commands/`.
   - Install both helper docs from staged skills into `.opencode/skills/`.

## Verification

- Run `bash -n install.sh aiscripts/aitask_setup.sh` for syntax sanity.
- Optionally validate workflow YAML structure by visual inspection and command path consistency.

## Step 9 Reminder

After implementation and user review, complete post-implementation workflow steps: finalize plan notes, commit code with `chore: ... (t324)`, archive task with `./aiscripts/aitask_archive.sh 324`, then push via `./ait git push`.

## Post-Review Changes

### Change Request 1 (2026-03-06 13:09)
- **Requested by user:** Run tests that validate packaging/unpackaging for the newly added OpenCode files and update existing OpenCode setup tests as needed.
- **Changes made:** Extended `tests/test_opencode_setup.sh` to cover packaging and staging of `opencode_planmode_prereqs.md` and `.opencode/commands/`, then executed the test suite successfully.
- **Files affected:** `tests/test_opencode_setup.sh`

## Final Implementation Notes
- **Actual work done:** Extended OpenCode release packaging to include `.opencode/commands/` and `opencode_planmode_prereqs.md`, updated installer staging to persist commands and both shared helper docs, and updated setup flow to install command wrappers plus both helper docs from metadata staging.
- **Deviations from plan:** Added a robustness improvement in `setup_opencode` so it no longer assumes skills staging always exists when command staging is present.
- **Issues encountered:** The existing OpenCode setup test did not validate the newly required artifacts; expanded test coverage to ensure regressions are caught.
- **Key decisions:** Kept staging split across `opencode_skills/` and `opencode_commands/` for clarity and minimal impact on existing skill packaging flow.
