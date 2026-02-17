# Changelog

## v0.4.0

### Features

- **Auto-bootstrap new projects** (t127): Running `ait setup` in a directory without an existing installation now auto-bootstraps aitasks by downloading and running the installer.
- **Explore auto-continue** (t129_4): Added an auto-continue option in the explore workflow that proceeds to task creation without additional prompts.
- **Profile refresh** (t129_5): Profiles are now refreshed during long conversations to ensure settings stay current in context.
- **Rename install.sh to aitask_setup.sh** (t133): Renamed the installer to `aitask_setup.sh` with a backward-compatible wrapper for existing projects.
- **Copy-from-project installation** (t134): New "Copy from existing project" mode in setup for installing aitasks from a local reference project instead of downloading.
- **Atomic task locking** (t136): Added task locking to prevent multiple users or machines from working on the same task simultaneously.
- **Task abort procedure** (t137_1): Tasks can now be cleanly aborted with automatic lock release, status revert, and worktree cleanup.
- **Lock release procedure** (t137_3): Task locks are automatically released on both successful completion and abort.
- **Folded task cleanup** (t137_4): Folded (merged) tasks are automatically deleted during archival of the primary task.
- **aitask-fold command** (t139): New `/aitask-fold` command to identify and merge related tasks into a single consolidated task.
- **aitask-explore command** (t141): New `/aitask-explore` command for interactive codebase exploration with automatic task creation.
- **Board filtering and sorting** (t143_2): Board supports filtering by labels, sorting options, and persistent settings.
- **Shared plan file utility** (t144_1): Extracted plan file resolution into a shared utility for reuse across scripts.
- **Tar.gz archive fallback** (t144_2): Plan and task file resolution now falls back to searching compressed tar.gz archives.
- **Safety-aware zip-old** (t144_3): Rewrote zip-old selection logic to preserve siblings of active tasks and task dependencies.
- **Folded status and metadata** (t145): Added `Folded` status and `folded_into` metadata property for tracking merged tasks in the board and scripts.
- **Board column customization** (t147): Columns can be added, edited, and deleted via the command palette or by clicking column headers.
- **Release process documentation** (t149): Updated release process to include running `/aitask-zipold` after creating a new release.

### Bug Fixes

- **ait help text** (t104): Added the missing `changelog` command to the `ait` help output.
- **ait setup fixes** (t128): Fixed VERSION file location, removed CHANGELOG.md from installs, and added auto-commit for framework files during setup.

### Improvements

- **Shared task workflow** (t129_1): Extracted the shared task-workflow skill from duplicated code across aitask-pick and aitask-explore.
- **Updated calling skills** (t129_2): Updated aitask-pick and aitask-explore to use the new shared workflow.

### Documentation

- **Windows/WSL install docs** (t106): Added inline Windows/WSL note to README and authentication cross-reference to install documentation.
- **Context monitoring docs** (t107): Added context monitoring section with claude-hud plugin recommendation to workflows documentation.

## v0.3.0

### Features

- **Framework updater** (t85_11): Added `ait install` command for updating aitasks to the latest or a specific version, with automatic daily update checks that notify when a newer release is available.
- **Atomic task ID counter** (t108): Task IDs are now assigned from a shared atomic counter on a separate git branch, preventing duplicate IDs when multiple PCs create tasks against the same repo. Tasks are created as local drafts first and finalized with a real ID on commit.
- **Atomic task locking** (t110): Added a lock mechanism that prevents two PCs from picking the same task simultaneously, using compare-and-swap semantics on a separate `aitask-locks` git branch.

### Bug Fixes

- **Git init in setup** (t102): `ait setup` now detects when the project directory is not a git repository and offers to initialize one with an initial commit of framework files.
- **Windows install fix** (t105): Fixed `install.sh` failing silently when piped via `curl | bash` on Windows/WSL by adding TTY detection to all interactive prompts in setup.

### Documentation

- **Typical workflows** (t100): Added a "Typical Workflows" section to README covering idea capture, task decomposition, GitHub issue workflow, parallel development, multi-tab terminal setup, and monitoring during implementation.
- **Draft workflow docs** (t109): Documented the draft/finalize task creation workflow and atomic task ID counter behavior in README.
- **Follow-up task workflow** (t111): Documented how to create follow-up tasks during or after implementation, leveraging Claude Code's full session context.
- **Task locking docs** (t125): Documented the atomic task locking mechanism in the README Development section.

## v0.2.0

### Features

- **Comprehensive README** (t85_10): Added full project documentation covering installation, command reference, Claude Code skills, platform support, and task file format.
- **Terminal compatibility detection** (t89): Added automatic detection of terminal capabilities on Windows/WSL with helpful upgrade suggestions for unsupported terminals.
- **Execution profiles** (t92): Added YAML-based execution profiles for task picking that pre-answer workflow prompts, with built-in "default" and "fast" presets.
- **Centralized task types** (t94): Added "refactor" issue type and moved all task type definitions into a single configuration file for easy customization.
- **Skills as source of truth** (t95): Release workflow now builds distributable skills from `.claude/skills/`, ensuring the repository is the single source of truth.
- **Default Claude Code permissions** (t96): New installations automatically configure Claude Code tool permissions, with interactive merge during `ait setup`.
- **Changelog generation** (t97): Added `aitask-changelog` skill to generate release notes from completed tasks and archived plans, with a shared task utilities library.
- **Board child collapse** (t101): The 'x' shortcut now works when a child card is focused in the task board, collapsing back to the parent task.

### Bug Fixes

- **Board create shortcut** (t93): Fixed the 'n' keyboard shortcut in the task board that failed to launch task creation due to an incorrect script path.
- **Missing documentation type** (t98): Added the "documentation" task type to seed and active task type definitions.

### Documentation

- **CRUD commands and skills** (t99_1): Documented `ait create`, `ait ls`, and `ait update` commands with interactive workflows and batch mode options.
- **Utility commands and skills** (t99_2): Documented `ait setup`, `ait board`, `ait stats`, and `ait clear-old` commands and related skills.
- **Integration commands and changelog skill** (t99_3): Documented `ait issue-import`, `ait issue-update`, `ait changelog` commands and the `/aitask-changelog` skill.
- **Pick skill documentation** (t99_4): Expanded `/aitask-pick` documentation with a full workflow overview and key capability descriptions.
- **Architecture documentation** (t99_5): Added architecture overview, directory layout, and library script reference to the Development section.
- **README consolidation** (t99_6): Merged all documentation snippets into a comprehensive README, growing from 314 to ~720 lines.
- **README corrections** (t103): Added table of contents, fixed section hierarchy, and updated release process documentation.
