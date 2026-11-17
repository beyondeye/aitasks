---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [ait_setup, install_scripts, bash_scripts, refactor]
created_at: 2026-11-17 13:04
updated_at: 2026-11-17 13:04
---

Split the install and setup scripts into focused modules. They have grown to the point where changing them and fixing bugs in them is difficult.

## Current size (measured 2026-11-17)

- `.aitask-scripts/aitask_setup.sh`: 7226 lines, 163 functions, 323 KB — one file.
- `install.sh`: 2063 lines, 67 functions.

`aitask_setup.sh` mixes unrelated concerns in one file: OS detection and CLI tool installation, the data/lock branch layout, a dozen gitignore writers, Python venv / PyPy / optional dependency tiers, the engine binary, the global shim, per-agent configuration and settings merges (Claude, Codex, OpenCode), review guides, per-user home migration, and the scoped metadata commit machinery.

## Goal

A thin `aitask_setup.sh` whose `main()` reads as the ordered list of steps, with each concern in its own sourced module under `.aitask-scripts/lib/` (for example `setup_cli_tools.sh`, `setup_python.sh`, `setup_git_layout.sh`, `setup_gitignore.sh`, `setup_agents.sh`, `setup_home.sh`), following `lib/engine_install.sh`, which is already extracted this way.

## Requirements

- **Behaviour-preserving.** No change to prompts, output lines, exit codes, commit contents or ordering. Move code; do not redesign it in the same task.
- **Decompose into child tasks, one concern per child**, so each move is small, reviewable and independently revertible. Start with the concerns that have the best existing test coverage.
- **Tests keep working.** Many tests source `aitask_setup.sh` and call individual functions, or build scaffolds that copy specific files. Read the source-on-startup / test-scaffold rule in `aidocs/framework/shell_conventions.md` first; every new module must be added wherever scaffolds copy the script. Baseline every setup/install test before the first move and re-run after each child.
- **`install.sh` is constrained differently:** it runs standalone via `curl | bash`, before any framework file exists, so it cannot source a library from the tarball until after extraction. Decide per function whether it must stay in the bootstrap file or can move to a post-extraction stage that sources shared modules. Functions duplicated between `install.sh` and the framework libs (for example the latest-version resolver mirrored from `lib/github_release.sh`) should end up with one owner where the bootstrap constraint allows.
- **Shared predicates.** The "is X installed / correct" checks that `ait doctor` (t2325) needs should come out as read-only functions separate from the code that installs or repairs, so doctor and setup call the same predicate.
- Release packaging, `retired_scripts_manifest.txt` and any whitelist that enumerates script paths must learn the new files.

## Sequencing

This is best done before t2326 (unattended setup, which has to audit every step of `main()`) and before t2327 (shared install mode, which changes what setup writes into the project). t2325 (`ait doctor`) overlaps on predicate extraction — coordinate so the predicates are extracted once. Pending setup bug fixes that touch the same functions should land before the corresponding module is moved, or be rebased onto it, not edited concurrently.
