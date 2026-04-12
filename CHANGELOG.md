# Changelog

## v0.15.0

### Features

- **Monitor TUI** (t475_1–t475_4, t477, t485, t486, t487, t490–t492, t501, t504, t505, t516, t518): New `ait monitor` command opens a full-screen dashboard listing tmux code-agent panes with a live content preview. Supports zone-based navigation, direct keystroke forwarding (Tab/Enter), kill-agent via `k`, inline task titles and a task detail dialog, preview size cycling, auto-switch to agents needing attention, and a live task name in the preview footer.
- **Minimonitor TUI** (t496_1–t496_3, t511, t524, t526): New compact `ait minimonitor` companion pane auto-spawns alongside agent windows. Shows a narrow agent list with Tab to focus the sibling agent pane and Enter to send Enter to it.
- **TUI switcher** (t475_2, t475_4, t479, t495, t510, t514): Reusable `j` keybinding opens a TUI switcher overlay across board, monitor, minimonitor, codebrowser, settings, and brainstorm. Includes inline shortcut hints, wrap-around navigation, dynamic brainstorm session discovery, and prioritized ordering.
- **`ait ide` launcher** (t519_1): New `ait ide` subcommand starts a tmux session (or attaches to an existing one) and opens an `ait monitor` window in a single step.
- **Explore operation and shortcut** (t480_1, t480_2): New `explore` codeagent operation, launchable via `x` in the TUI switcher to spin up an exploration agent window.
- **Git TUI integration** (t507_1–t507_4): Configure lazygit, gitui, or tig as a first-class TUI. Auto-detected during `ait setup` (with lazygit install prompt), selectable in the Settings TUI, and launchable via `g` from the switcher.
- **Brainstorm from board** (t497, t509): Launch brainstorm sessions directly from the board TUI with automatic tmux window dedup and a lock guard.
- **Rename task from board** (t500, t503): New `N` keybinding in the board TUI opens a modal to rename tasks with git commit and sync; disabled for locked tasks.
- **Per-run agent/model override** (t521_2, t521_3): The launch dialog gains `(A)gent` and `(U)se last` buttons so you can pick a different agent/model per run, wired through board, codebrowser, history, and monitor launch flows.
- **Pick next sibling from monitor** (t506, t525): Press `n` in monitor to pick the next ready sibling or child task. Works for both parent and child tasks and auto-kills the current agent pane when moving on.
- **Better folding support** (t520): Skills and scripts now support ad-hoc folding and folding of child tasks into unrelated parents.

### Bug Fixes

- **Fix tmux pick arg loss** (t478): Dry-run output now preserves task arguments via `printf '%q'` quoting.
- **Fix tmux session target ambiguity** (t483): Launching tmux windows now disambiguates session vs window targets correctly.
- **Fix board pick dialog** (t493): Arrow keys work in the Select dropdown, window targets are valid, tmux errors are surfaced, the dialog defaults to "New window", and the board auto-switches to the target window after split.
- **Fix child task rename path** (t502): `aitask update` now correctly handles child task file paths during rename.
- **Fix tmux detection in board** (t512): Board now correctly pre-selects the tmux tab when running inside a tmux session.
- **Fix tmux settings save** (t515): Saving tmux settings no longer wipes unrelated keys like `git_tui` or the `monitor` sub-dict.
- **Fix `tar_match` unbound variable** (t527): `task_utils.sh` no longer crashes under `set -u` when archive lookups return empty.
- **Monitor TUI fixes** (t482, t488, t492, t501, t504, t508): Arrow keys in modal dialogs, crash guards during widget rebuild, footer hides when preview is focused, panel vs pane terminology disambiguated, stable panel border, and delayed preview refresh after sending Enter.
- **Minimonitor fixes** (t513, t517, t523): No more auto-switch on arrow navigation, correct window index after tmux window moves, and stable agent selection across refreshes.
- **TUI switcher visual fixes** (t484): Higher-contrast `bright_green` for selected items.

### Improvements

- **Extract monitor shared widgets** (t496_1): Shared monitor components moved to `monitor_shared.py` for reuse by the minimonitor.
- **Extract agent model picker** (t521_1): `AgentModelPickerScreen` extracted to `lib/agent_model_picker.py` so other TUIs can reuse it.

### Documentation

- **Terminal setup rewrite** (t519_2): Terminal setup page now focuses on the `ait ide` workflow, clarifies terminal emulator vs multiplexer, and calls out the shared-session gotcha.
- **Getting started + tmux-ide workflow** (t519_3): Getting-started guide uses `ait ide` as the primary entry point, and a new `workflows/tmux-ide` page walks through a daily session end-to-end.
- **Monitor TUI docs** (t519_4): New `tuis/monitor/` section with overview, how-to, and reference pages.
- **Minimonitor TUI docs** (t519_5): New `tuis/minimonitor/` section with overview and how-to pages.

### Maintenance

- **Fold helper scripts** (t481, t522_1, t522_2, t528): New `aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh` scripts with shared `read_yaml_field` helper; Claude Code fold callers migrated to invoke them directly. Monitor session bar now includes an inline Tab hint. Added `aitask-contribution-review` wrappers for alt-agent frontends.

## v0.14.0

### Features

- **Completed tasks history browser** (t448_1–t448_5, t455, t458, t460): New history screen in the codebrowser TUI (`h` to open) for browsing archived tasks with a searchable list, detail view with plan toggling, label filtering, sibling navigation, left/right arrow cycling, and file navigation back to source code.
- **Process monitoring and hard kill** (t462_1–t462_4): View running agent processes and resource usage in both dashboard (`o` key) and brainstorm (Status tab) TUIs. Pause, kill, or hard-kill unresponsive agents directly from the UI.
- **Unified agent launch dialog with tmux support** (t468_1–t468_5): All agent launch actions (pick, create, explain, QA) now use a shared dialog with Direct and tmux execution tabs. Configure defaults in the new Tmux settings tab.
- **Runner control in brainstorm TUI** (t447_2): View runner status and start/stop the crew runner from the brainstorm Status tab with color-coded indicators.
- **Crew worktree auto-push** (t447_3): Crew worktree changes are automatically pushed after adding work, enabling cross-machine collaboration.
- **Reset errored agents in brainstorm** (t459): Press `w` to reset agents stuck in Error state back to Waiting from the brainstorm Status tab.
- **Brainstorm keyboard navigation** (t464, t466): Letter-key tab shortcuts (d/g/c/a/s), improved wizard navigation, tab-bar focus cycling, and consistent arrow key navigation throughout.
- **QA agent integration** (t465_1–t465_3): Added `qa` as a codeagent operation. Press `a` in the history screen to launch a QA agent, or `H` in the codebrowser to jump to the history entry for the task at the current line.
- **Prompt file passing in agentcrew** (t453): Agent prompts are now passed via temporary files with a "Your Files" section mapping shorthand names to file paths.
- **Archive migration command** (t470_6): New `ait migrate-archives` command converts existing tar.gz archives to the faster tar.zst format.

### Bug Fixes

- **Fix crew runner startup** (t447_4): Fixed `ModuleNotFoundError` preventing the crew runner from starting.
- **Fix plan retrieval from tar archives** (t448_7): Plans inside tar archives now display correctly in the history view.
- **Fix agent stale detection on launch** (t451): Agents write a heartbeat immediately on launch, preventing false stale warnings during startup.
- **Reset errored agents on runner restart** (t452): Agents in Error state are automatically reset to Waiting when the runner restarts, with manual reset via `w` in the dashboard.
- **Fix history screen focus issues** (t463): Fixed focus loss after back navigation, sibling selection, and child task navigation.
- **Fix archived child task queries** (t467): Archived task queries now correctly resolve child task IDs.
- **Fix board expand/collapse** (t476): Fixed children not expanding or collapsing after initial board load.

### Improvements

- **Migrate archives to tar.zst** (t469–t471, t470_1–t470_4): Migrated the entire archive system from tar.gz to Zstandard compression for faster performance. All bash and Python utilities updated with full backward compatibility for existing tar.gz archives.
- **Extract shared modules** (t447_1, t468_1–t468_2): Runner control and agent launch functionality extracted into reusable shared modules used across dashboard, brainstorm, and codebrowser TUIs.

### Documentation

- **History view documentation** (t448_6): Comprehensive docs for the codebrowser history feature including keyboard shortcuts, how-to guides, and screenshots.
- **Settings in getting started guide** (t449): Added settings reference to the getting started documentation.
- **QA and history navigation docs** (t465_4): Updated codebrowser reference and how-to docs with QA agent and history navigation features.

### Performance

- **Per-column board refresh** (t472): Column updates refresh only the affected column instead of the entire board, eliminating visual flicker.
- **Adjacent task DOM swap** (t473): Moving tasks within a column uses efficient DOM-level widget swapping instead of full column rebuilds.

### Tests

- **Fix brainstorm tests** (t450): Updated test expectations to match post-t434 session initialization behavior.

### Maintenance

- **Add zstd dependency** (t470_5): Added zstd to `ait setup` dependency installation and website documentation.
- **Run archive migration** (t470_7): Converted all repository archive bundles from tar.gz to tar.zst format.

## v0.13.0

### Features

- **Diff Viewer TUI** (t417): Added a complete plan diff viewer with classical and structural diff modes, side-by-side and interleaved layouts, word-level intra-line highlighting, markdown syntax highlighting, unified multi-comparison view, plan merge with selective hunk acceptance, and a file browser for plan selection.
- **Brainstorm Engine** (t419) *(WIP)*: Built the brainstorm engine with a DAG operations library, session management CLI, agent type templates (explorer, comparator, synthesizer, detailer, patcher), configurable agent model settings, and TUI scaffolding with tabbed navigation.
- **Brainstorm TUI** (t423) *(WIP)*: Added a full brainstorm TUI with a dashboard showing node list and detail pane, ASCII art DAG visualization, node detail modal with metadata/proposal/plan tabs, dimension comparison matrix, an actions wizard for launching brainstorm operations, and crew/agent status monitoring.
- **QA Skill** (t428): Introduced `/aitask-qa` as a standalone skill for analyzing test coverage gaps, with tiered testing modes (quick/standard/exhaustive), a health score system, verification gate, and configurable profile keys in the settings TUI.
- **Default Execution Profiles** (t426): Added support for default profile assignment per skill in project config, `--profile` override argument on all 8 interactive and auto-select skills, and a per-skill profile picker in the settings TUI.
- **Agent Log Browsing** (t439) *(WIP)*: Added log capture for agent subprocesses, shared log utilities, and log browsing screens in both the AgentCrew Dashboard and Brainstorm TUI.
- **Loading Indicators** (t421): Added loading overlay animations for async board operations like sync, commit, lock, unlock, archive, and delete.
- **Brainstorm Delete** (t441) *(WIP)*: Added `ait brainstorm delete` subcommand for cleaning up brainstorm sessions with proper branch and worktree removal.
- **Test and Lint Commands in Settings** (t428_4): Added `test_command` and `lint_command` configuration keys to project settings with preset support in the TUI.
- **AgentCrew Operation Groups** (t419_2) *(WIP)*: Added operation groups to AgentCrew for organizing and scheduling agents by group with priority ordering.

### Bug Fixes

- **Parallel Task Creation Race Condition** (t429): Fixed race condition when creating child tasks in parallel by adding POSIX `mkdir`-based locking around the critical section.
- **Brainstorm TUI Bootstrap** (t434): Fixed brainstorm TUI failing to create a root node on init, added brief preview display, and fixed wizard click handling.
- **Task Data Push Conflicts** (t436): Added retry-rebase logic to task push/sync for handling concurrent pushes to the aitask-data branch.
- **Task Creation Batch Procedure** (t435): Refactored task creation invocation into a shared procedure to prevent agents from struggling with shell quoting in batch mode.
- **DAG Tab Crash** (t430): Fixed crash in DAG tab caused by method name conflicting with Textual internals.
- **Enter Key in Dialogs** (t425): Added Enter key confirmation to all TUI modal dialogs with text input fields.
- **SIGPIPE in Recent Archived** (t442): Fixed crash when piping sorted output under `set -euo pipefail` in the recent-archived query.
- **Crew Init Orphan Branches** (t445): Changed AgentCrew worktrees to use orphan branches, avoiding unnecessary history from the main branch.
- **Git Log in Branch Mode** (t446): Fixed bare `git log` commands in skills to use `./ait git log` when task data lives on a separate branch.
- **Diff Viewer Visual Tweaks** (t417_13): Added colored line numbers and content padding to the diff viewer display.

### Improvements

- **Numbered Archive Scheme** (t433): Replaced the single monolithic `old.tar.gz` with numbered per-range archives for faster lookups, parallel-safe archiving, and O(1) task resolution.
- **Decouple Test Followup** (t428_2): Removed the embedded Step 8b test-followup from the task workflow, replaced by the standalone `/aitask-qa` skill.
- **Avoid Duplicate Agent Query** (t432): Eliminated redundant agent/model detection by passing the resolved agent string through the task workflow context.

### Documentation

- **Brainstorm Engine Architecture** (t419_1) *(WIP)*: Published the complete architecture specification for the brainstorm engine covering data formats, templates, context assembly, and orchestration flow.
- **Default Profiles Documentation** (t426_6): Added documentation for default profile configuration, `--profile` override, and resolution order.
- **QA Skill Documentation** (t428_5): Added skill reference page, QA testing workflow guide, and updated settings documentation.

### Tests

- **Archive Library Tests** (t433_2): Added comprehensive tests for the v2 archive path library.
- **Archive Integration Tests** (t433_6): Added end-to-end integration tests for the v2 archive system.

### Maintenance

- **Organize aidocs** (t418): Moved documentation files into brainstorming and agentcrew subdirectories.
- **Pin Dependencies** (t420): Pinned all Python dependency versions and upgraded to Textual 8.x.
- **Remove Deprecated Step 8b** (t431): Deleted the deprecated test-followup-task procedure file.

## v0.12.2

### Maintenance

- **Review scripts for macOS compat** (t416): Added `from __future__ import annotations` to codebrowser Python files to ensure compatibility with macOS system Python.

## v0.12.1

### Features

- **Plan visualization in board** (t415): The TUI board detail screen now supports toggling between task content and the associated implementation plan, with a visual border color indicator and context-aware editing.

### Bug Fixes

- **Simplified satisfaction feedback procedure** (t414_1): Agent and CLI ID can now be passed directly as flags to the verified update script, replacing the error-prone 3-file chain that agents frequently failed to follow in context-heavy conversations.

## v0.12.0

### Features

- **AgentCrew data model and initialization** (t386_1): Added `ait crew init` and `ait crew addwork` commands to create and populate multi-agent crew sessions with task decomposition, dependency tracking, and worktree management.
- **AgentCrew status and heartbeat system** (t386_2): Added `ait crew status` and `ait crew command` for monitoring agent health, tracking heartbeats, and sending commands to running agents.
- **AgentCrew runner orchestrator** (t386_3): Added `ait crew runner` to automatically launch, monitor, and manage agents through their lifecycle with DAG-aware scheduling, configurable concurrency limits, and graceful shutdown.
- **AgentCrew reporting and cleanup** (t386_4): Added `ait crew report` with summary/detail/output views and `ait crew cleanup` for tearing down completed crew sessions.
- **AgentCrew TUI dashboard** (t386_5): Added `ait crew dashboard` with real-time auto-refreshing crew list, agent card views sorted by dependency order, and runner management controls.
- **Task revert analysis** (t398_1): Added commit, file, and area analysis capabilities for identifying the scope and impact of task changes before reverting.
- **Task revert skill** (t398_2): Added `/aitask-revert` interactive skill for safely reverting completed task changes, supporting both complete and partial reversions with detailed impact analysis.
- **Post-revert integration** (t398_3): Enhanced the revert skill with task/plan file resolution and refined disposition templates for handling archived artifacts after revert.
- **Partial revert child mapping** (t398_6): Enhanced partial revert to support child-task-level selection for parent tasks, showing per-child area breakdowns for granular revert decisions.
- **Historical context gathering in planning** (t369_3): Added `gather_explain_context` profile key to control how many historical task explanations are gathered during the planning phase.
- **Satisfaction feedback in explore** (t390): Added satisfaction feedback prompt to the "Save for later" path in `/aitask-explore`.
- **Verified skill stats and build presets** (t393): Added verified skill statistics display and a `verify_build` preset editor with 17 common project type presets to the settings TUI.

### Bug Fixes

- **Wrong skill references in contribute** (t375): Fixed incorrect skill reference in `/aitask-contribute` summary message pointing to non-existent skills.
- **Instructions template CLI syntax** (t386_11): Fixed 6 incorrect CLI syntax examples in the AgentCrew auto-generated agent instructions template.
- **Contribution review list and dedup** (t388): Added `list-issues` and `check-imported` subcommands to `/aitask-contribution-review` for querying open issues and detecting already-imported contributions.
- **Check-imported crash** (t389): Fixed a pipefail crash in `check-imported` when no matching task files exist.
- **Find-related grep crash** (t391): Fixed a pipefail crash in `find-related` when no `#N` references exist in task files.
- **Silent mode exit code** (t392): Fixed incorrect exit code in contribution check's silent mode that could mask failures.
- **Obsolete child task management** (t400): Added unified Delete/Archive flow to the board TUI for managing obsolete child tasks, with dependency checking and superseded status tracking.
- **Agent detection encapsulation** (t401_1): Encapsulated model JSON lookup into a reusable script, replacing inline detection logic across all agent instruction files.
- **Archived task querying** (t403): Added `archived-task` subcommand and tar.gz archive unpacking support for the revert skill to access completed task data.
- **Smart test follow-up** (t406): The test follow-up question now auto-skips when tests were already created during the current task implementation.
- **Crew script permissions** (t411): Fixed missing execute permissions on crew scripts and added crew help text to `ait help`.
- **Folded task cleanup** (t413): Fixed folded task cleanup and consolidated YAML list parsing for more reliable task folding.

### Improvements

- **Deduplicated commit attribution** (t385): Removed duplicated commit format rules from the Code-Agent Attribution procedure by referencing the canonical Contributor Attribution section.
- **Modular procedures** (t395): Split the monolithic procedures file into individual procedure files for easier maintenance and cross-referencing.
- **Shared profile selection** (t402): Extracted execution profile selection into shared procedure files referenced by all skills, eliminating duplicated instructions.
- **Consolidated lock pre-check** (t405): Merged the lock pre-check logic directly into the pick workflow, reducing an extra script invocation during task claiming.
- **Reverted historical context feature** (t407): Removed the `gather_explain_context` planning feature introduced in t369_3 after it proved unnecessary.
- **Deferred profile selection in explore** (t412): Moved execution profile selection in `/aitask-explore` from the start to after task creation, so the profile is only selected when actually needed.

### Documentation

- **Contribution flow documentation** (t355_7): Added comprehensive contribution flow docs covering fingerprint metadata, overlap scoring, review skill workflow, and per-platform CI/CD setup.
- **Verified scores reference** (t365_5): Added a dedicated verified scores reference page with cross-links from 6 existing documentation pages.
- **AgentCrew architecture guide** (t386_6): Added architecture documentation covering the full AgentCrew system design, file schemas, status state machines, and a work2do operational guide.
- **Revert skill documentation** (t398_4): Added website skill reference page and workflow guide for `/aitask-revert` with comparison table and example walkthroughs.
- **Explore workflow documentation** (t404): Added `/aitask-explore` references to the idea capture and terminal setup documentation pages.
- **Contribution skills index** (t409): Added missing contribution skills (`/aitask-contribute`, `/aitask-contribution-review`) to the website skills index page.

### Maintenance

- **Revert skill whitelist registration** (t398_5): Added whitelist entries and skill wrappers for `/aitask-revert` across all supported code agents (Claude Code, Gemini CLI, Codex CLI, OpenCode).

## v0.11.0

### Features

- **Verified score updater** (t303_1): Added a score updater that records user satisfaction feedback per AI model and skill, building rolling averages over time.
- **Satisfaction feedback procedure** (t303_2): Added a reusable feedback workflow that prompts users to rate task completion quality, with profile-based control via `enableFeedbackQuestions`.
- **Feedback in task workflow skills** (t303_3): Integrated satisfaction feedback into all shared-workflow skills so every task completion can optionally collect quality ratings.
- **Model refresh feedback preservation** (t303_4): Model refresh now preserves verified feedback history and displays aggregated stats when listing models.
- **Feedback in standalone skills** (t303_5): Added satisfaction feedback prompts to standalone skills like explain, changelog, and review guide management.
- **Contribution fingerprint metadata** (t355_1): Contribution issues now include fingerprint metadata (affected areas, file paths, change type) for smarter overlap detection.
- **Fingerprint metadata parser** (t355_2): Extended the contribution metadata parser to read fingerprint fields for downstream overlap analysis.
- **Contribution overlap checking** (t355_3): Added automated overlap checking that detects when incoming contributions duplicate existing tasks, with GitHub, GitLab, and Bitbucket support.
- **Contribution CI/CD templates** (t355_4): Added CI/CD templates for GitHub Actions, GitLab CI, and Bitbucket Pipelines to automatically check contributions on new issues.
- **Merge issues in import** (t355_5): Added `--merge-issues` to combine multiple related contribution issues into a single task with cross-references and contributor attribution.
- **Contribution review skill** (t355_6): Added a new skill for reviewing incoming contributions, discovering related issues, and importing them as grouped or single tasks.
- **Time-windowed verified stats** (t365_2): Verified stats now track performance across time windows (all-time, monthly, weekly) with automatic migration from the previous format.
- **Verified score discoverability in settings** (t365_3): The settings TUI now shows verified scores per model with time-window breakdowns, cross-provider aggregation, and a top-verified model picker.
- **Verified rankings and plots in stats** (t365_4): Added verified model rankings and bar chart visualizations to `ait stats` output.
- **Pick command dialog in board** (t367): Added a pick command dialog to the board TUI, making it easy to launch task picks from terminal multiplexers.
- **Task detail keyboard shortcuts** (t368): Added keyboard shortcuts for all buttons in the board's task detail dialog.
- **Explain format context formatter** (t369_1): Added a Python formatter for historical task context used by the explain feature.
- **Explain context orchestrator** (t369_2): Added a shell orchestrator for gathering and caching historical context for file explanations.
- **Optional test follow-up tasks** (t372): Added an optional post-implementation step to automatically create follow-up testing tasks, controlled via execution profiles.
- **Task overlap detection in contribution review** (t376_2): Added task overlap detection to contribution review and extracted shared fold procedures for consistent merge behavior across skills.
- **Update existing task from contributions** (t376_3): Contribution review can now update existing tasks with new contribution content instead of always creating new tasks.
- **CI workflow Node.js fix** (t387): Upgraded CI workflow actions to fix Node.js 20 deprecation warnings and added missing `jq` dependency.

### Bug Fixes

- **Gemini CLI allowlist setup** (t361): Fixed Gemini CLI policy setup with proper per-skill activation entries and a consent-based global allowlist installation flow.
- **Skip reviewguide in setup** (t364): Added a skip option when selecting review guides during `ait setup`.
- **OpenCode provider mapping** (t365_1): Fixed OpenCode model attribution to use correct provider-aware naming instead of legacy aliases.
- **Verified stats display** (t366): Fixed verified stats not appearing in settings by correcting the internal operation key mismatch.
- **Pick for OpenCode/Codex** (t371): Fixed task pick command generation for OpenCode and Codex CLI agents.
- **Unsafe die patterns** (t378): Fixed 23 unsafe `cmd || die` patterns across 8 scripts that could cause silent exits under `set -e`.
- **Double commenting on contributions** (t381): Fixed contribution check workflow firing twice on issue creation by switching to label-only event triggers.
- **Duplicate overlap comment parsing** (t382): Fixed overlap comment parsing to correctly handle duplicate overlap comments by using the last one.
- **Missing feedback in child decomposition** (t383): Fixed satisfaction feedback being skipped when tasks are decomposed into child tasks during pick.

### Improvements

- **Rename aiexplains directory** (t370): Renamed `aiexplains/` to `.aitask-explain/` for consistency with the `.aitask-*` naming convention.
- **Extract related task discovery** (t376_1): Extracted related task discovery into a shared reusable procedure for explore, fold, and contribution review skills.

### Maintenance

- **macOS compatibility review** (t351): Fixed macOS compatibility issues in awk multiline handling, Python type syntax, and updated stale test assertions across all scripts.

## v0.10.0

### Features

- **Upstream contribution workflow** (t321_1, t321_2, t321_4, t321_6): Added `/aitask-contribute` command to open structured issues against upstream repositories directly from local changes, with multi-platform support for GitHub, GitLab, and Bitbucket. Issue imports now parse contributor metadata from contribution issues.
- **Agent commit coauthor support** (t339_1, t339_2, t339_3, t339_4, t339_6): Commit messages now include accurate code-agent and model attribution for all supported agents (Claude Code, Codex CLI, Gemini CLI, OpenCode). The coauthor domain is configurable via `project_config.yaml`.
- **Project config editing in settings** (t339_7): Added regression tests for the Settings TUI Project Config tab's YAML helpers.
- **Code area maps and project contributions** (t341_1, t341_2, t341_3): Added `code_areas.yaml` for defining project structure, automatic codemap generation, and dual-mode contribute workflow supporting both framework and project-level contributions with hierarchical area drill-down.
- **Code agent and model statistics** (t353): `ait stats` now shows breakdowns by code agent and LLM model, including weekly trends and plot histograms.
- **AI agent whitelist updates** (t362): Updated agent configuration whitelists to include newly added scripts.

### Bug Fixes

- **Codex CLI model resolution** (t340): Fixed model identification for Codex CLI agents by adding config-file fallback when environment detection fails.
- **Seed execution profiles out of sync** (t342): Synced seed execution profiles (`fast.yaml`, `remote.yaml`) with the canonical metadata versions.
- **Consolidated duplicate create skills** (t347): Merged `aitask-create` and `aitask-create2` into a single unified skill with full batch mode support.
- **Child task sorting in board** (t350): Fixed child tasks sorting lexicographically instead of numerically in the board TUI.
- **Contribution label failure** (t354): Contributions no longer fail when the target repository lacks the expected issue label; the script retries without the label automatically.
- **OpenCode planning detail** (t357_1): Enhanced OpenCode plan mode requirements to produce more detailed implementation plans with explicit file paths and code snippets.
- **Agent confusion with symlinked directories** (t358): Added repo-structure documentation to prevent code agents from misinterpreting `aitasks/` and `aiplans/` symlinks.
- **Stats plot title and spacing** (t359): Fixed chart titles and sizing in `ait stats --plot` output with terminal-aware rendering and visual spacing between charts.
- **Workflow skipping review after child creation** (t360): Fixed the task workflow incorrectly proceeding to review/archive steps after creating child tasks instead of stopping.

### Documentation

- **Multi-agent documentation review** (t320): Updated 26 documentation pages to remove Claude-only narration and align with the multi-agent architecture.
- **Contribution workflow documentation** (t321_3): Added skill docs, workflow guide covering all three contribution paths, and README updates.
- **Documentation site links** (t336): Updated all README links from GitHub Pages to the new `aitasks.io` domain.
- **Agent commit attribution docs** (t339_5): Added dedicated commit attribution documentation explaining how agent coauthors work across all supported agents.
- **Gemini CLI and Codex CLI known issues** (t356): Documented known limitations for Gemini CLI and Codex CLI agents on the installation known-issues page.
- **OpenCode plan mode caveats** (t357_2): Added OpenCode-specific known issues including plan mode locking skip and shallow plan workarounds.
- **Contribute docs for project repos** (t363): Updated contribution documentation to reflect support for both framework and project-level contributions.

### Performance

- **Python codemap scanner** (t348): Rewrote the codemap scanning from bash to Python for better performance, with new filtering options and framework directory exclusion.

## v0.9.0

### Features

- **Gemini CLI skill wrappers** (t131_1): Added 17 skill wrappers for Gemini CLI, enabling the full aitasks skill set to work natively with Gemini CLI.
- **Gemini CLI command wrappers** (t131_2): Added 17 command wrappers for Gemini CLI, providing slash-command access to all aitasks workflows.
- **Gemini CLI setup/install/release pipeline** (t131_3): Integrated Gemini CLI into the setup, install, and release pipelines so new projects get Gemini CLI support out of the box.
- **OpenCode skill wrappers** (t319_1): Added 17 skill wrappers for OpenCode, bringing full aitasks skill coverage to the OpenCode agent.
- **OpenCode setup/install pipeline** (t319_2): Integrated OpenCode into the setup and install pipelines with automated config merging and seed file deployment.
- **OpenCode model discovery** (t319_4): Added `ait opencode-models` command to discover and catalog available OpenCode models with provider-prefixed identifiers.
- **Model status field support** (t319_5): Models can now be marked as active or unavailable, with unavailable models dimmed in the TUI and excluded from selection.
- **OpenCode command wrappers** (t323): Added 17 command wrappers and plan-mode prerequisites for OpenCode, completing slash-command support.
- **Gemini CLI TOML migration and permission policies** (t335): Migrated Gemini CLI commands from Markdown to TOML format and added automatic permission policy merging during setup.

### Bug Fixes

- **Child task checkpoint and agent attribution** (t322): Fixed child tasks skipping the planning checkpoint and agent attribution incorrectly defaulting to "claude" instead of the actual code agent.
- **Test data branch setup failures** (t328): Fixed missing seed file copy in `setup_data_branch()` that caused 7 test failures.
- **Parent task locked after child creation** (t330): Parent tasks are now properly unlocked when child tasks are created, preventing the parent from remaining stuck in a locked state.
- **Skill definition conflicts** (t332): Consolidated Gemini CLI and Codex CLI skill wrappers into a single unified set under `.agents/skills/`, eliminating file conflicts during setup.

### Improvements

- **Rename aiscripts to .aitask-scripts — core** (t326_1): Renamed the `aiscripts/` directory to `.aitask-scripts/` to keep framework internals hidden as a dotfile directory.
- **Rename aiscripts to .aitask-scripts — docs and configs** (t326_2): Updated all skill files, documentation, seed templates, and website content to reference the new `.aitask-scripts/` path.
- **Rename aiscripts to .aitask-scripts — tests and cleanup** (t326_3): Updated all test files, removed the backward-compatibility symlink, and fixed three functional bugs the symlink had been masking.

### Documentation

- **Gemini CLI website documentation** (t131_4): Added Gemini CLI to the installation page, updated the overview to highlight multi-agent support, and updated the about page.
- **OpenCode documentation update** (t319_3): Updated the skills overview, getting started guide, and homepage to document OpenCode's invocation syntax and wrapper layout.
- **Terminal setup workflow** (t327): Moved terminal setup and git authentication documentation into dedicated installation sub-pages for easier discovery.
- **Agent known issues** (t329): Added an installation known-issues page documenting Claude Code and Codex CLI caveats.
- **Remove OpenCode recommendation** (t333): Removed the outdated suggestion to use OpenCode as an alternative for OpenAI models from the installation docs.
- **Homepage code agent copy** (t334): Refined the homepage feature card to describe workflow-oriented agent integration rather than invocation syntax details.

### Maintenance

- **OpenCode release packaging** (t324): Extended the release pipeline to bundle OpenCode command wrappers and plan-mode prerequisite files.
- **Agent instruction seed cleanup** (t331): Trimmed Gemini CLI, Codex CLI, and OpenCode seed files to contain only agent identification, removing duplicated preamble content.

## v0.8.3

### Bug Fixes

- **Exclude Python cache from setup commits** (t309): The `ait setup` framework commit scan no longer accidentally stages `__pycache__` and `.pyc` files.
- **Fix Codex skill YAML frontmatter** (t310): Fixed invalid YAML in the `aitask-explain` skill definition that broke Codex CLI wrapper parsing.
- **Require plan mode for Codex interactive skills** (t311): Added plan mode prerequisites to 14 interactive Codex CLI skill wrappers, preventing runtime failures in non-plan contexts.
- **Add agent attribution to wrap/pickrem/pickweb** (t314): Agent attribution is now recorded for tasks completed via `aitask-wrap`, `aitask-pickrem`, and `aitask-pickweb` workflows.
- **Pre-implementation ownership guard** (t316): Task workflow and pickrem now verify task ownership (status and assigned_to) before starting implementation, preventing accidental work on tasks owned by another user.

### Performance

- **Migrate ait stats to Python** (t222): Rewrote the stats command in Python for better performance, with optional `plotext`-based chart rendering configurable via `ait setup`.

### Documentation

- **Update code agent skill docs** (t130_3): Website documentation now covers multi-agent invocation syntax, distinguishing Claude `/skill` from Codex `$skill` commands.
- **Tool extraction scripts** (t312): Added scripts for extracting Claude Code and OpenCode tool definitions for reference documentation.
- **Refresh tool references** (t313): Updated Codex and Gemini CLI tool description references in `aidocs/`.
- **Document stats plot and setup flow** (t315): Clarified `--plot` usage, missing-dependency warnings, and the setup prompt for enabling plot support.
- **Document Codex continue guidance** (t317): Added explicit continuation guidance to skill docs for Codex CLI's post-implementation flow.

## v0.8.2

### Features

- **Codex CLI skill wrappers** (t130_1): Added 17 Codex CLI skill wrappers with a shared tool mapping file and a layered instructions architecture, enabling aitask skills to work natively with OpenAI's Codex CLI using `$skill-name` syntax.
- **Codex CLI install pipeline** (t130_2): Added end-to-end install pipeline for Codex CLI support, including release packaging, `ait setup` integration, TOML config merging, and a unified marker-based instruction management system (`>>>aitasks`/`<<<aitasks`) for idempotent agent configuration across all supported CLIs.

### Improvements

- **Refactored agent setup** (t308): Extracted agent-specific setup into dedicated methods (`setup_claude_code()`, `setup_codex_cli()`, etc.) with automatic CLI detection, so each agent is only configured when its CLI is installed.

### Tests

- **macOS bash test fixes** (t307): Fixed 7 failing bash tests on macOS, including a real symlink path resolution bug in `ait setup` and stale assertions from recent behavior changes.

## v0.8.1

### Bug Fixes

- **Task creation and locking without git remote** (t305): Task creation and locking now work in repositories without a configured remote. The ID counter operates locally and automatically upgrades to remote-based coordination when a remote is later added.
- **Auto-update version comparison** (t306): Fixed the auto-update check incorrectly suggesting downgrades by replacing string comparison with proper semver ordering.

### Documentation

- **Project root requirement clarity** (t302): Improved documentation and script messaging to clearly explain that `ait setup` and the curl installer must be run from the git repository root directory.

## v0.8.0

### Features

- **No-recurse flag for extract script** (t195_11): Added a `--no-recurse` flag to the code extraction script, allowing single-directory processing without traversing subdirectories.
- **PR contributor metadata fields** (t260_1): Tasks now track pull request URL, contributor name, and contributor email in frontmatter metadata.
- **PR/contributor display in board** (t260_2): The board TUI shows PR links and contributor information for imported tasks.
- **PR import script** (t260_3): New `ait primport` command imports pull requests from GitHub, GitLab, and Bitbucket as structured aitasks.
- **PR review skill** (t260_4): Added a skill to create aitasks directly from pull request reviews.
- **PR close/archive integration** (t260_5): Closing or archiving a PR-originated task now automatically closes the associated pull request.
- **Contributor attribution** (t260_6): PR-originated task commits include contributor attribution from the original pull request author.
- **Dynamic search placeholder** (t260_8): Board search placeholder text updates dynamically based on the active view mode.
- **Code agent wrapper** (t268_1): New `ait codeagent` command provides a unified entry point for invoking any supported AI code agent.
- **Per-user config overrides** (t268_2): Added `*.local.json` support for user-specific configuration that won't be committed to git.
- **Shared config library** (t268_3): New shared config library handles layered configuration loading across all TUI applications.
- **Code agent TUI integration** (t268_5): Board and settings TUIs now use the codeagent wrapper instead of hardcoded agent commands.
- **Settings TUI** (t268_6): New `ait settings` command launches a centralized TUI for managing all configuration — profiles, board settings, models, and more.
- **Implemented-with tracking** (t268_7): Task frontmatter now records which code agent was used for implementation via the `implemented_with` field.
- **Refresh code models skill** (t268_9): New skill that researches the latest AI code agent models and updates model configuration files automatically.
- **View mode filter** (t273): Board now supports All/Git/Implementing view modes to quickly filter tasks by status.
- **Bitbucket Cloud support** (t278): Fixed and validated PR import and close workflows for Bitbucket Cloud repositories.
- **Verified model scores** (t280): The settings TUI model selector now shows verification scores for tested models.
- **User-scoped profiles and revert** (t281): Profiles tab supports user-scoped profiles and a revert button to undo unsaved changes.
- **Profile save confirmation** (t284): Added a confirmation dialog before saving profile changes to prevent accidental overwrites.
- **Mouse click for CycleField** (t286_1, t286_2): CycleField widgets in both settings and board TUIs now respond to mouse clicks for easier interaction.
- **Updated project description** (t296): README now lists all supported AI code agents in the project description.
- **Board settings revert** (t299): Added a revert button to the board settings tab in the settings TUI.

### Bug Fixes

- **Settings TUI navigation fixes** (t272): Fixed tab navigation, model picker display, and configuration layer indicators in the settings TUI.
- **Keyboard hints in settings** (t275): Fixed settings TUI navigation shortcuts and added keyboard hint bars to all tabs.
- **Agent identifier rename** (t276_1, t276_2): Renamed internal agent identifiers from `claude`/`gemini` to `claudecode`/`geminicli` for clarity across scripts, configs, skills, and docs.
- **GitLab cross-repo imports** (t277_1): Fixed `glab api` flag handling and added `--repo` override for importing PRs from other repositories.
- **Cross-repo PR operations** (t277_2): Added `--repo` support to PR close and issue update commands for cross-repo GitLab workflows.
- **Settings refresh crash** (t283): Fixed a DuplicateIds crash that occurred when refreshing the settings TUI.
- **Tab switching shortcuts** (t285): Fixed tab switching keyboard shortcuts and keyboard hint placement in the settings TUI.
- **Missing scripts in whitelist** (t294): Added 5 missing scripts to the seed setup whitelist.
- **PR import interactive mode** (t295): Fixed the draft/commit flow in interactive PR import and improved UX prompts.
- **Issue import finalization** (t298): Fixed task finalization behavior when importing issues interactively.
- **Folded task archival** (t301): Fixed handling of folded tasks during child and transitive archival operations.

### Improvements

- **Board config split** (t268_4): Split board configuration into separate project and user layers for cleaner config management.
- **Profiles tab redesign** (t279): Redesigned the Profiles tab with a selector, groups, and field descriptions for better usability.
- **Settings export/import** (t292): Hardened and finalized the settings TUI export/import functionality.
- **Remove pr-close from dispatcher** (t297): Removed the standalone `pr-close` command, consolidating functionality into the archive workflow.

### Documentation

- **PR import workflow docs** (t260_7): Documented the complete PR import workflow and related commands.
- **Code agent and settings docs** (t268_8): Added documentation for the codeagent wrapper and settings TUI.
- **Parallel task planning guide** (t288): New guide explaining the parallel task planning workflow for complex multi-step tasks.
- **Codeagent wrapper docs** (t290): Updated website documentation with codeagent wrapper references and cross-links.
- **Board filtering docs** (t291): Documented view mode filtering and PR metadata display in board documentation.
- **README license fix** (t293): Removed duplicate LICENSE reference from README.
- **Skills page reorganization** (t300): Documented the refresh-models skill and reorganized the skills documentation page.

### Performance

- **Explain generation optimization** (t195_10): Improved code browser explain generation with commit limiting, cache staleness detection, pre-caching on directory expansion, and a progress timer.

### Maintenance

- **Profile path resolution** (t282): Updated skills to resolve local profile paths from the active profile context variable.

## v0.7.1

### Features

- **Code browser TUI** (t195_1): Added a new code browser TUI application with a two-pane layout for browsing project files alongside syntax-highlighted code.
- **File tree browser** (t195_2): The code browser displays a file tree of git-tracked files, filtering out hidden files and build artifacts.
- **Syntax highlighting** (t195_3): Code viewer automatically detects file languages and renders syntax highlighting with line numbers.
- **Explain data auto-generation** (t195_4): The code browser integrates with the explain data pipeline to display task history and annotations for each line of code.
- **Task annotation overlay** (t195_5): A gutter column shows which tasks modified each line of code, with color-coded task IDs for quick visual reference.
- **Cursor navigation and selection** (t195_6): Added keyboard navigation and text selection with smart viewport scrolling in the code browser.
- **Claude Code explain integration** (t195_7): Select code ranges in the code browser and launch the explain skill directly with context about the selected code.
- **Multi-platform repo fetch library** (t214_1): Built a repository file fetching library supporting GitHub, GitLab, and Bitbucket with automatic platform detection and graceful fallbacks.
- **Board unlock resets assignment** (t248): Unlocking a task in the board now prompts to reset the task status back to "Ready" and clear the assignment.
- **Click-to-select in code browser** (t250): Added mouse support for clicking to move the cursor and click-dragging to select code ranges.
- **Task detail pane** (t251): Added a detail pane showing task and plan content for the task that annotated the current line, with automatic updates as you navigate.
- **Foolproofing task name input** (t253): When creating a task, entering a long description in the name field prompts to use it as the description instead.
- **Binary file support in code browser** (t255_2): The code browser now recognizes binary files and displays their commit history instead of attempting to show unreadable content.
- **Explain cleanup command** (t258_1): Added a cleanup command to remove old explain run directories, keeping only the newest version of each source directory's data.
- **Explain auto-naming** (t258_2): Explain runs are now automatically named based on the source directory for easier organization and cleanup.
- **Updated peripheral scripts** (t258_4): Updated related scripts and documentation to work with the new explain run naming scheme and automatic cleanup.

### Bug Fixes

- **Multi-platform reviewguide import** (t214_3): The review guide import workflow now supports repositories on GitHub, GitLab, and Bitbucket instead of only GitHub.
- **Separate git operations for code and plans** (t239): Fixed workflow to use separate git commands for code changes and plan files, preventing failed commits when task data lives on a separate branch.
- **Eliminated permission prompts for child tasks** (t246): Consolidated file queries to eliminate repeated permission prompts when Claude Code discovers child tasks.
- **Dotfiles visible in code browser** (t252): Fixed the file tree to show git-tracked dotfiles like `.claude/` while still hiding `.git/` and untracked hidden files.
- **Binary file handling in extraction** (t255_1): Fixed the explain data extraction pipeline to detect and skip binary files instead of producing corrupt output.
- **Responsive code browser layout** (t256): Made the code browser layout responsive so all columns remain visible on smaller terminal widths.
- **Simplified explain manager** (t258_3): Removed duplicate directory naming logic from the Python explain manager, now that the shell script handles it.
- **Phantom tasks in board** (t264): Fixed a bug where archived tasks would reappear as corrupted stubs in the board after being moved to the archive.

### Improvements

- **Refactored task workflow skill** (t244): Split the large task-workflow skill into multiple files for better maintainability while keeping the core workflow accessible.

### Documentation

- **Documented setup.sh design** (t214_4): Documented why certain code in setup.sh is intentionally duplicated rather than sourced, making maintenance clearer.
- **Automated latest releases on website** (t243): The website landing page now automatically shows the three latest releases, eliminating manual updates after each release.
- **Reorganized ait help output** (t245): Reorganized the `ait` command help output into logical categories (TUI, Task Management, Integration, Reporting, Tools, Infrastructure) for improved discoverability.
- **Updated task querying docs** (t254): Updated documentation to describe how to query and update existing tasks during implementation.
- **Updated explain skill docs** (t258_5): Updated all documentation to reflect automatic explain run cleanup and the new directory naming convention.
- **Code browser documentation** (t267): Added code browser TUI tutorials and keyboard reference, and reorganized the website to group both board and code browser under a new "TUIs" section.

### Performance

- **Large file viewport windowing** (t195_9): Optimized rendering for large files (2000+ lines) by displaying only a 200-line viewport window, enabling smooth navigation in very large codebases.
- **Optimized board lock refresh** (t261): Lock status now refreshes only when needed (on mount, manual refresh, or after sync) instead of on every board operation. Also added Ctrl+Up/Ctrl+Down shortcuts to move tasks to column top/bottom.
- **Column collapse/expand** (t262): Added column collapse/expand to the board so you can hide columns to reduce clutter, with keyboard shortcut and command palette support.

### Tests

- **Code viewer rendering hardening** (t195_8): Improved handling of edge cases including binary files, very long lines, empty files, and fixed mouse drag selection when scrolled.

### Maintenance

- **Replaced raw ls in skills** (t247): Replaced remaining raw `ls` commands in skills with a structured query script, preventing permission prompts and improving reliability.
- **Verified seed whitelist** (t249): Ensured all scripts referenced by skill workflows are whitelisted in the seed configuration, preventing permission prompts in new installations.

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
