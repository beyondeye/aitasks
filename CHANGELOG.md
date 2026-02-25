# Changelog

## v0.7.0

### Features

- **Configurable build verification** (t51): Build verification is now configurable via `project_config.yaml`, allowing each project to define custom build/test commands that run automatically during task implementation.
- **Wrap skill reuses Claude plans** (t207): `/aitask-wrap` now detects and reuses existing Claude Code plan files, avoiding duplicate planning when wrapping uncommitted changes.
- **macOS version checks in setup** (t208): `ait setup` now validates tool versions (bash, git, Hugo, etc.) and warns about missing or outdated dependencies on macOS.
- **Remote task execution** (t215): New `/aitask-pickrem` skill enables fully autonomous task implementation in non-interactive environments (CI, SSH, remote servers) with zero user prompts.
- **Remote sync** (t216_1, t216_2, t216_3): New `ait sync` command synchronizes task and plan files with the remote repository. The board TUI supports sync via the `S` keybinding with conflict resolution dialogs.
- **Remote data branch initialization** (t225): `/aitask-pickrem` now automatically initializes the data branch on first run, removing a manual setup step.
- **Claude Code Web workflow** (t227_1, t227_2, t227_3, t227_4, t227_5, t227_6): New `/aitask-pickweb` and `/aitask-web-merge` skills enable task implementation directly in Claude Code Web. Added task locking with board TUI lock/unlock controls and lock-aware picking. Introduced `userconfig.yaml` for per-user settings.
- **Auto-merge for sync conflicts** (t228_1, t228_2, t228_3, t228_4, t228_5): New auto-merge engine intelligently resolves YAML frontmatter conflicts in task files during sync, with field-specific merge rules. Integrated into `ait sync` and the board TUI.
- **Double-click to expand parent tasks** (t229): Double-clicking a collapsed parent task in the board now expands it to show child tasks instead of opening the detail view.
- **AI agent config file detection** (t234): Environment detection now recognizes AI agent configuration directories (`.claude/`, `.gemini/`, `.codex/`, etc.) when scanning projects.
- **Public `ait lock` command** (t238): Exposed task locking as a public CLI command with email auto-detection and bare task-ID shortcut syntax.

### Bug Fixes

- **Labels included in task commits** (t68): Task creation now correctly includes `labels.txt` changes in git commits, fixing cases where label modifications were silently dropped.
- **sed portability on macOS** (t209): Fixed 7 GNU-specific `sed` usages across 4 scripts that caused failures on macOS. Added `sed_inplace()` helper for portable in-place editing.
- **Stats command macOS compatibility** (t211): Fixed `aitask stats` on macOS by replacing 16 GNU `date -d` calls with a portable date wrapper.
- **Test suite macOS portability** (t212): Fixed test portability issues on macOS including whitespace handling and hardcoded paths.
- **Task ownership on Claude Web** (t220): Fixed task claiming on Claude Code Web with structured exit codes, `--force` flag for stale locks, and a diagnostic script.
- **Child task auto-implementation prevented** (t224): Child task creation no longer triggers automatic implementation, preventing unintended workflow execution.
- **`ait git` permission whitelist** (t226): Added `./ait git` to the default permission whitelist so it works without manual approval.
- **README redesign** (t231): Redesigned README with themed logo, badges, emoji section titles, and updated installation instructions.

### Improvements

- **Shortened remote skill name** (t219): Renamed `aitask-pickremote` to `aitask-pickrem` for consistency.
- **Task data branch support** (t221_1, t221_2, t221_3, t221_4, t221_5): Introduced `./ait git` command and `task_git()` shell helper to route task/plan file operations through a dedicated data branch, enabling parallel development workflows. Updated all scripts, the board TUI, skills, and documentation.
- **Shared YAML utilities** (t228_1): Extracted YAML frontmatter parsing from the board TUI into a shared `task_yaml.py` module for reuse by other Python tools.
- **Renamed own script** (t240): Renamed `aitask_own.sh` to `aitask_pick_own.sh` for clearer naming.
- **Optimized profile scanning** (t241): Added `aitask_scan_profiles.sh` helper to optimize how execution profiles are selected during task implementation.

### Documentation

- **Release blog and RSS feed** (t186): Added a blog section with release posts, RSS feed, and automated blog post generation to the documentation site.
- **Redesigned About page** (t187): Redesigned the About page with hero cover, origin story, project stats badges, and contributor profiles.
- **Explore skill file selection docs** (t199): Updated explore skill documentation to cover the new file selection modes.
- **Explain skill file selection docs** (t200): Added file selection documentation to the explain skill page.
- **Project root directory guidance** (t204): Added guidance across 12 skill pages about running Claude from the project root directory.
- **Development dependencies** (t210): Documented ShellCheck and Hugo as development dependencies with platform-specific install instructions.
- **macOS fully supported** (t213): Comprehensive macOS compatibility audit — fixed remaining portability issues and updated docs to mark macOS as fully supported.
- **Workflow cross-references** (t232): Added workflow cross-references to all skill documentation pages and standardized section naming.
- **Apache 2.0 license** (t233): Changed the project license from MIT to Apache License 2.0.
- **Remote execution docs** (t235): Created comprehensive documentation for the `/aitask-pickrem` skill.
- **Claude Web docs** (t236): Created documentation for `/aitask-pickweb` with comparison tables and workflow diagrams.
- **Board lock documentation** (t237): Documented the board's lock/unlock feature including pre-lock workflow and multi-agent coordination guides.
- **Board screenshot images** (t242): Added board SVG screenshots to the documentation site with click-to-zoom functionality.

### Tests

- **Task git and migration tests** (t221_6): Created test suites for the task git helper and data branch migration, verified no regressions across all test suites.
- **Auto-merge unit tests** (t228_5): Added 25 Python unit tests for the auto-merge script covering conflict parsing, merge rules, and body merging.

## v0.6.0

### Features

- **Code explanation skill** (t91): Added the `/aitask-explain` skill for generating code explanations with evolution tracking, including data extraction, processing pipeline, and run management.
- **HTML/CSS environment detection** (t178): Added automatic detection of HTML/CSS projects (including SCSS, Sass, and Less) for review guide matching.
- **File selection skill** (t189): Added a reusable `user-file-select` skill with keyword search, fuzzy name matching, and functionality search for use by other skills.
- **Board auto-refresh** (t193): Added periodic auto-refresh and a settings screen to the board TUI with configurable refresh intervals.
- **Wrap skill** (t196_1): Added the `/aitask-wrap` skill for retroactively documenting uncommitted changes as tracked tasks with implementation plans.

### Bug Fixes

- **Hugo site deployment** (t188): Fixed the documentation site not rebuilding automatically when a new release is published.
- **Internal skill visibility** (t201): Fixed the `user-file-select` skill being incorrectly listed as user-invocable.
- **File selection digit conflict** (t202): Fixed digit input conflicts in user-file-select when selecting files via AskUserQuestion.
- **Gemini CLI batch mode** (t203): Fixed the Gemini CLI tools extraction script launching interactive mode instead of batch mode.
- **Install missing directory** (t205): Fixed installation failure caused by a missing `aireviewguides` directory.
- **Install PATH on macOS** (t206): Fixed `ait` command not being found after curl-pipe installation on macOS due to missing PATH configuration.

### Improvements

- **Explain file selection** (t190): Integrated user-file-select into aitask-explain for better file discovery.
- **Explore area selection** (t191): Integrated user-file-select into aitask-explore for better codebase area selection.

### Documentation

- **Explain runs command** (t192): Added the `explain-runs` command to the ait dispatcher and website documentation.
- **Explain skill docs** (t194): Added skill reference and workflow guide for the aitask-explain skill.
- **Wrap skill docs** (t196_2): Added skill reference page and retroactive tracking workflow guide for aitask-wrap.
- **Wrap usage guide** (t196_3): Added detailed walkthroughs and usage scenarios to the retroactive tracking workflow guide.
- **CLI tool extraction** (t197): Added extraction scripts and reference documentation for Codex CLI and Gemini CLI tools.
- **Settings screen docs** (t198): Added documentation for the board auto-refresh and settings screen features.

## v0.5.0

### Features

- **Review modes infrastructure** (t129_3): Added 9 seed review guide templates and an interactive setup wizard for installing review guides into projects.
- **Code review skill** (t129_4): Added the `/aitask-review` skill for performing structured code reviews with configurable review guides, multiple target selection modes, and automatic task creation from findings.
- **GitLab support** (t136): Added full GitLab support for importing issues as tasks and updating issues with task status, with automatic platform detection from git remotes.
- **Bitbucket support** (t146): Added full Bitbucket support for importing issues as tasks and updating issues with task status.
- **Additional task types** (t162): Added `chore`, `style`, and `test` task types with full support across the CLI, board, stats, and documentation.
- **Review vocabulary files** (t163_1): Added review types and labels vocabulary files for standardized review guide classification.
- **Review guide metadata** (t163_2): Added `reviewtype` and `reviewlabels` metadata fields to all review guide files for better categorization.
- **Review guide scan script** (t163_3): Added a scan script for analyzing review guide metadata completeness and finding similar guides.
- **Review guide classify skill** (t163_4): Added the `/aitask-reviewguide-classify` skill for assigning metadata to review guide files and finding similar existing guides.
- **Review guide merge skill** (t163_5): Added the `/aitask-reviewguide-merge` skill for comparing and merging similar review guides, with both single-pair and batch modes.
- **Review guide import skill** (t169): Added the `/aitask-reviewguide-import` skill for importing external content (files, URLs, or GitHub directories) as review guides.
- **New environment detection** (t175): Added environment detection for C#, Dart, Flutter, iOS, and Swift projects.
- **Hugo documentation site** (t176_1): Created a Hugo documentation website with the Docsy theme for hosting project documentation.
- **Documentation migration** (t176_2): Migrated all existing documentation to the new Hugo website with proper cross-links and navigation.
- **Landing page** (t176_3): Added a branded landing page with feature highlights, quick install instructions, and project logo.
- **Site deployment workflow** (t176_4): Added automated Hugo site deployment to GitHub Pages on release tag pushes.
- **Implementing children visibility** (t180): Parent task cards in the board now show which child tasks are currently being implemented.

### Bug Fixes

- **Internal skill visibility** (t164): Fixed the `/aitask-create2` skill being incorrectly listed as user-invocable when it's an internal-only skill.
- **Folded task issue updates** (t165): Fixed folded tasks with linked issues not getting updated during archival.
- **Setup commit handling** (t167): Fixed framework files not being committed to git during initial project setup.

### Improvements

- **Remove aitask-zipold skill** (t151): Removed the redundant `/aitask-zipold` skill in favor of the `ait zip-old` CLI command.
- **Standardized commit messages** (t157): Standardized commit message prefixes across all scripts and skills to use the `<type>: <description> (tNN)` format.
- **Review skill helper scripts** (t158): Extracted review skill logic into reusable helper scripts for commit fetching and environment detection.
- **Review guides directory structure** (t159): Reorganized review guide files from a flat directory into a categorized tree structure with subdirectories and gitignore-based filtering.
- **Board typing modernization** (t160): Replaced deprecated `typing.List` and `typing.Dict` imports with built-in `list` and `dict` in the board TUI.
- **Remove legacy metadata format** (t168): Removed support for the legacy single-line task metadata format, keeping only YAML frontmatter.
- **Reviewmode to reviewguide rename** (t172_1, t172_2, t172_3, t172_4, t172_5): Renamed all "reviewmode" references to "reviewguide" across directories, scripts, skills, and documentation for consistent terminology.

### Documentation

- **Exploration-driven development guide** (t129_5): Added a workflow guide for exploration-driven development with use cases and a concrete walkthrough.
- **Code review walkthrough** (t129_6): Added a walkthrough and practical tips to the code review workflow guide.
- **Board TUI documentation** (t148): Added comprehensive documentation for the `ait board` TUI covering tutorials, how-to guides, and feature reference.
- **Board docs cross-references** (t161): Added cross-references to board documentation across all relevant doc files.
- **Code review skills documentation** (t171): Added documentation pages for all four code review skills and the code review workflow.
- **Review guide format reference** (t174): Added a reference page documenting the review guide file format, directory structure, and environment detection algorithms.
- **Documentation restructure** (t176_5): Restructured all documentation into Hugo subpages with a new hierarchy, navigation, and getting started guide.
- **Website fixes** (t181): Fixed documentation navigation links, added an overview page, and corrected various website content issues.
- **Task folding workflow** (t182): Added a task consolidation (folding) workflow guide and updated related documentation.
- **Multi-platform references** (t183): Updated documentation to reference GitHub, GitLab, and Bitbucket where multi-platform support exists.
- **Board prerequisites cleanup** (t184): Removed the manual prerequisites section from board documentation since dependencies are handled automatically.
- **Releases workflow** (t185): Added a releases workflow documentation page covering the full release pipeline.

### Performance

- **Post-implementation speedup** (t166): Consolidated post-implementation archival operations into a single script for faster task completion.
- **Task startup improvement** (t173): Consolidated task ownership operations into a single script for faster task startup.

### Maintenance

- **Google style guides** (t179): Added 8 Google style guide review templates for C++, C#, Dart, Go, HTML/CSS, JavaScript, and TypeScript.

## v0.4.0

### Features

- **Auto-bootstrap new projects** (t127): Running `ait setup` in a directory without aitasks now automatically bootstraps the framework, eliminating the need to manually download and run the installer.
- **Interactive codebase exploration** (t129_2): Added `/aitask-explore` skill for investigating problems, exploring code areas, scoping ideas, or reviewing documentation — with guided follow-up questions and automatic task creation.
- **Task deletion in board** (t137): Added a delete action to the board TUI with confirmation prompts, child task detection, and read-only display for completed tasks.
- **Folded task navigation in board** (t142): Folded tasks are now displayed in the board task detail view with read-only navigation to view their contents.
- **Task folding skill** (t143_1): Added `/aitask-fold` skill to identify and merge related tasks into a single task, reducing duplication and organizing work.
- **Archive fallback for task/plan resolution** (t144_2): Task and plan file lookups now search inside tar.gz archives, so references to archived tasks still resolve correctly.
- **Safety-aware archive selection** (t144_3): Rewrote the zip-old selection logic to preserve archived files that are siblings of active parent tasks or dependencies of active tasks.
- **Folded status and folded_into property** (t145): Added a `Folded` status and `folded_into` metadata field so folded tasks are clearly marked and traceable to their target task.
- **Board column customization** (t147): Board columns can now be added, edited, and deleted via a command palette (Ctrl+P) or by clicking column headers, with color selection from an 8-color palette.

### Bug Fixes

- **Missing changelog in help** (t104): Added the `changelog` command to the `ait` help text.
- **Setup file handling fixes** (t128): Fixed `ait setup` to relocate VERSION into `aiscripts/`, remove CHANGELOG.md from installs, and auto-commit framework files.
- **Duplicate task prevention in explore** (t135): The `/aitask-explore` skill now discovers related existing tasks and offers to fold them instead of creating duplicates.
- **Execution profile loss during handoff** (t141): Fixed the execution profile being lost when transitioning from task selection to implementation by adding a profile refresh step.
- **Exit trap corrupting exit codes** (t150): Fixed an EXIT trap in bash scripts that was overwriting the intended exit code, causing `create_new_release.sh` to misreport failures.

### Improvements

- **Shared workflow extraction** (t129_1): Extracted the common implementation workflow (steps 3-9) into a reusable `task-workflow` skill, reducing duplication across skills.
- **Renamed clear-old to zip-old** (t144_1): Renamed the `clear-old` command and script to `zip-old` across the entire codebase for clarity.

### Documentation

- **Windows/WSL install notes** (t106): Added inline Windows/WSL guidance and authentication cross-references to the install documentation.
- **Context monitoring docs** (t107): Documented the context monitoring workflow with a claude-hud recommendation in the workflows guide.
- **README restructure** (t133): Restructured the README from 1155 lines into a concise landing page plus 6 focused documentation files under `docs/`.
- **Windows docs corrections** (t134): Moved authentication section to README, fixed terminal recommendation order, and trimmed outdated known issues.
- **Folded tasks documentation** (t140): Documented the `folded_tasks` frontmatter field, exploration workflow, and parallel exploration patterns.
- **Fold skill documentation** (t143_2): Added complete `/aitask-fold` reference documentation to the skills guide.
- **Post-release archival step** (t149): Added a zip-old step to the release process documentation.

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
