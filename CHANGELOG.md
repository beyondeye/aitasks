# Changelog

## v0.18.3

### Features

- **Polling activity indicator widget** (t653_5): The brainstorm TUI now shows a small dim-cycling indicator next to the initializer banner and Status tab that flashes briefly on each poll, so you can tell the agent is alive even when nothing visible has changed.
- **Brainstorm code-agents default to interactive** (t659): All six brainstorm agent types (initializer, detailer, explorer, comparator, synthesizer, patcher) now launch in interactive (tmux pane) mode by default, so you can watch and intervene during a brainstorm session.
- **Step 8 upstream-defect follow-up offer** (t667): After completing a task, the workflow now offers to spin off a follow-up task for any upstream defects you flagged during implementation, so root-cause issues uncovered while patching aren't lost.

### Bug Fixes

- **Push terminal status from agent crews** (t653_3): Terminal status changes from agent crews (Completed/Aborted/Error) are now committed and pushed to the remote immediately, and an `Error` agent can recover back to `Running` instead of being stuck.
- **Hide `M` shortcut and rebind auto-switch in monitor** (t657): The unused `M` (toggle multi-session) shortcut is hidden from the `ait monitor` footer, and the auto-switch toggle is rebound from `a` to `A` for case-consistency with the other capital-letter modal toggles (`R`, `M`, `L`).
- **Persistent error modal on brainstorm init failure** (t660): `ait brainstorm` no longer silently exits when the initializer fails. A scrollable error modal now surfaces captured stderr/stdout with Retry, Quit, and a "Delete branch & retry" action for the common stale-crew-branch case.
- **Remove `b` scrollbar-toggle shortcut from monitor** (t661): The `b` shortcut on `ait monitor` has been removed; the vertical scrollbar is now always visible.
- **Brainstorm delete cleans up stale crew branches** (t662): `ait brainstorm delete` now correctly prunes the worktree before deleting the branch, so subsequent `ait brainstorm init` calls no longer fail with "branch already exists".
- **Always forward `--launch-mode` in brainstorm addwork** (t663): `ait brainstorm` plan import now always forwards the `--launch-mode` flag to crew workers, so agents launch in the configured mode instead of silently falling back to the default.
- **Brainstorm `n000_needs_apply` requires all four delimiters** (t670): The brainstorm TUI no longer spuriously offers to apply changes on session load; it now requires all four initializer delimiters to be present before reporting "ready to apply".
- **Improve `install.sh` "already installed" error** (t673): `install.sh` now shows an interactive overwrite prompt when run in a TTY against an existing install, and the non-TTY error message spells out all three recovery paths (`ait upgrade latest`, `bash -s -- --force`, `bash install.sh --force`).

### Improvements

- **Separate heartbeat freshness from agent terminal status** (t671): Stale heartbeats no longer mutate `_status.yaml`. The `MissedHeartbeat` status (introduced in v0.18.2) has been removed; consumers should call `get_stale_agents()` / `check_agent_alive()` to observe heartbeat freshness instead. **Migration:** clean any in-flight crews with `ait crew cleanup --crew <id>` before resuming work — values written under the prior runner will be rejected by the trimmed state machine.

### Documentation

- **Encode user-feedback rules into `CLAUDE.md`** (t665): Added 7 conventions covering pane-internal cycling (← / →), TUI-switcher selected-session semantics, single tmux session per project, companion pane auto-despawn, the context-variable pattern over template substitution engines, full install-flow testing for setup helpers, and `ait setup` vs `ait upgrade` verb conventions.
- **Make Step 8 review prompt non-skippable** (t668): The task-workflow Step 8 user-review prompt is now non-skippable — auto-mode and execution-profile overrides do not bypass it, and explicit acceptance is required every iteration.

## v0.18.2

### Features

- **Multi-session aggregate stats** (t655): The `ait stats` TUI now detects multiple aitasks sessions on your machine and shows a Session panel for cycling between them with Left/Right or click. A new `sessions` preset displays a grouped bar chart comparing today/7d/30d activity across all sessions.
- **MissedHeartbeat state for agent crews** (t652): Agent crews now distinguish between transient missed heartbeats and hard failures — agents go to MissedHeartbeat first and can recover back to Running automatically. Errored agents can also be recovered to Completed without requiring manual force overrides.

### Bug Fixes

- **Self-healing brainstorm TUI on initializer failures** (t653_1): When the initializer apply fails, the brainstorm TUI now shows a persistent banner with a `ctrl+r` retry shortcut and re-attempts the apply automatically every 30 seconds and on session reopen, instead of getting stuck.
- **Tolerant initializer YAML and retry CLI** (t653_2): The initializer apply now auto-quotes problematic scalar values (em-dashes, special characters) so brainstorm sessions don't get stuck on YAML parse errors. A new `ait brainstorm apply-initializer <id>` CLI lets you manually retry stuck sessions.
- **Cross-session monitor and minimonitor** (t656): The monitor and minimonitor TUIs now correctly resolve task data, log paths, and next-sibling launches for code agents running in foreign aitasks sessions, instead of looking them up in the wrong project.
- **`ait crew` whitelist across all code agents** (t650_1): The `./ait crew` subcommand is now properly whitelisted for Claude Code, Gemini CLI, and OpenCode (both runtime and seed configs), eliminating the per-invocation permission prompts.
- **Brainstorm template procedure references** (t650_2): Brainstorm templates now reference the heartbeat, progress, and status procedures by their explicit section name instead of pseudo-verb shorthand, so code agents reliably execute the documented procedures during brainstorm runs.

## v0.18.1

### Features

- **Manual-verification render-then-ask flow** (t639): The manual-verification skill now re-renders the full numbered checklist with state markers on every iteration and accepts batch updates (e.g. `1 pass, 3 defer`) through the Other field, so you can triage many items in one answer instead of stepping through them individually.
- **Issue-type filter view in the board TUI** (t645): A new `t` view mode in `ait board` opens a multi-select dialog to filter tasks by issue type (feature/bug/refactor/etc.). Picks persist per-project and a summary line under the view selector shows the active filter; pressing `t` again reopens the picker.
- **`ait setup` warns and requires acknowledgment when no git remote** (t648): When `origin` is missing during setup, the ID-counter and lock-branch steps now surface a one-time warning explaining that branch-tracked features won't sync, and require an explicit acknowledgment before continuing. Lock operations also now distinguish "branch missing on remote" from transient "remote unreachable" failures.

### Bug Fixes

- **`ait upgrade` now commits framework files in branch-mode setups** (t644): Upgrades on projects using a separate `aitask-data` branch were leaving framework files uncommitted because the install script's symlink handling skipped them. Upgrades now correctly commit `.aitask-scripts/`, `.claude/`, etc. on the main branch and `aitasks/metadata/` + `aireviewguides/` on the data branch.
- **Crew runner restored; TUI surfaces launch failures** (t647): Fixed a silent crash where the crew runner couldn't import its `lib/` modules. The TUI now also captures runner launch logs and verifies the process is actually alive before reporting success, so future launch failures show as an error toast instead of a silent no-op.
- **TUI switcher uses the selected session's project root** (t649): When switching between aitasks sessions and spawning a new TUI window, the switcher now passes `-c <project_root>` to tmux based on the *selected* session, so cross-session launches no longer inherit the wrong project's working directory.
- **`tests/test_crew_runner.sh` no longer hangs** (t651): The test fixture now copies the full `.aitask-scripts/` tree instead of cherry-picking files, fixing a hang caused by missing helper modules pulled in after the test was written.

## v0.18.0

### Features

- **Multi-session tmux primitives** (t634_1): Foundation for cross-session awareness across aitasks TUIs — discovery of tmux sessions rooted in aitasks projects and teleport-style pane focus helpers.
- **Multi-session `ait monitor`** (t634_2): The monitor TUI now aggregates code-agent panes across every aitasks session by default. Sessions are grouped under divider rows, and an `M` binding toggles multi-session view on and off.
- **Cross-session TUI switcher** (t634_3): The TUI switcher overlay (`j`) now lists every running aitasks session. `←` / `→` cycles between them, and `Enter` (or any shortcut key) teleports tmux to the selected session automatically.
- **Multi-session `ait minimonitor`** (t634_4): The minimonitor now aggregates agent panes across every aitasks session by default, with session divider rows and the same `M` toggle as the full monitor. The title bar gains a compact `multi: Ns · Ma N idle` summary.
- **Register `gpt-5.5` for codex and opencode** (t636): `gpt-5.5` is selectable for the codex agent directly and for the opencode agent via the OpenAI and OpenCode providers.

### Bug Fixes

- **Respect default session in agent launch dialog** (t640): The launch dialog now honors the caller's `default_tmux_window` and remembers the last-used tmux session and window **per project** instead of sharing a single global memory across all projects.
- **Rename `ait install` → `ait upgrade`; fix skills missing from release tarball** (t641): Framework updates now use `ait upgrade` (`ait install` remains as a deprecated alias). Also fixes a packaging bug where skills whose names didn't start with `aitask-` (e.g. `task-workflow`, `ait-git`, `user-file-select`) were silently excluded from release tarballs and installer copies.

### Documentation

- **Multi-session documentation polish** (t634_5): Monitor, minimonitor, and TUIs index docs now describe cross-session aggregation, the `M` toggle, session divider rows, and cross-session teleport behavior.

### Style Changes

- **Remove redundant magenta session prefix in `ait monitor`** (t643): Monitor pane rows no longer emit a magenta `[project]` tag prefix; session grouping is conveyed by the divider rows alone.

## v0.17.4

### Bug Fixes

- **Preserve project settings on `ait install`** (t637): `ait install --force` no longer clobbers user-edited seed configs. `project_config.yaml`, `codeagent_config.json`, `models_*.json`, and execution profiles are deep-merged (existing values win, new seed keys are added); `task_types.txt`, `reviewtypes.txt`, `reviewlabels.txt`, and `reviewenvironments.txt` use line-union semantics; existing review-guide `.md` files are never overwritten.
- **Auto-commit framework updates only when tracked** (t637): `ait install` now gates its safety-net commit on whether `.aitask-scripts/VERSION` is already tracked. If tracked, framework updates (adds **and** modifications) are committed with a version-stamped message (`ait: Update aitasks framework to vX.Y.Z`); if untracked, the installer never touches git. The installer never pushes on its own.
- **Ship scoped `.gitignore` inside `.aitask-scripts/`** (t637): A framework-owned `.aitask-scripts/.gitignore` is now installed alongside the framework to keep `__pycache__/`, `*.pyc`, and `*.pyo` artifacts out of downstream project repos. The auto-commit path also opportunistically drops any previously-tracked `__pycache__` paths from the project's index.

## v0.17.3

### Bug Fixes

- **Exact tmux session targeting** (t632): Fixed a cross-project bug where tmux commands could target the wrong session when session names shared a common prefix; all session-denominated tmux calls now use exact-match targeting.
- **Task IDs start at 1** (t631): Task IDs in new projects now start at 1 instead of 10 — the initial buffer that forced fresh projects to begin at t10 has been removed.
- **`__pycache__/` added to `.gitignore` during setup** (t630): `ait setup` now automatically adds `__pycache__/` to your project's `.gitignore`, preventing Python cache directories from being committed.

### Documentation

- **Initializer brainstorm agent type** (t573_4): Added documentation for the `initializer` brainstorm agent type, covering how it's registered and the "initialize from an imported proposal" flow that triggers it.

## v0.17.2

### Features

- **Import proposal flow in brainstorm init (t573_3)**: When starting a new brainstorm session you can now pick an existing markdown proposal instead of starting blank. The init modal offers a three-way choice (Blank / Import Proposal… / Cancel); the import path opens a markdown-filtered file picker, runs an initializer agent, and applies its output to seed the session.

### Bug Fixes

- **Test scratch-repo setup (t626)**: Fixed test scaffolds that copied `task_utils.sh` without the companion `archive_utils.sh`, which caused several test suites to fail at source time. All 11 affected tests now set up scratch repos correctly.
- **`install.sh` missing seed config (t628)**: `install.sh` now installs `project_config.yaml` from the seed files when bootstrapping a new project, fixing missing-config errors on fresh installs.
- **`commit_framework_files` stopping at 20 files (t629)**: Fixed a SIGPIPE that caused framework-file commits to terminate after the 20th file — all framework files are now committed on update.

## v0.17.1

### Features

- **Initializer brainstorm agent** (t573_1): New `initializer` agent type and `apply_initializer_output()` ingestion helper that bootstrap a brainstorm session's root node from an imported markdown proposal, reformatting it into a structured node with dimension metadata.
- **`--proposal-file` flag for brainstorm init** (t573_2): `ait brainstorm init` now accepts a `--proposal-file` flag to seed a brainstorm session from an external markdown document, auto-registering the initializer agent and starting the crew runner.
- **Minimonitor companion in git TUI window** (t622): The TUI switcher now spawns a minimonitor companion pane alongside the git TUI (lazygit) window, with smart cleanup that preserves the companion when other panes are still active in the same window.

### Bug Fixes

- **`ait setup` reliability fixes** (t624): Multiple improvements to `ait setup` — installs `AGENTS.md` with the shared aitasks layer, prompts for a default tmux session name, includes more framework files in the initial commit with a more visible confirmation and captured error output, writes config files through symlinks instead of replacing inodes, and adds post-write verification so silent failures surface as actionable warnings. Also refreshes the seed `CLAUDE.md`/`GEMINI.md`/`AGENTS.md` content with Folded Task Semantics and Manual Verification sections.

## v0.17.0

### Features

- **Manual verification workflow** (t583_1, t583_2, t583_3, t583_5, t583_7): Added a full Pass/Fail/Skip/Defer manual-verification loop with a new `verifies` frontmatter field, follow-up task helpers, archival gate with automatic carry-over, and plan/implementation-time prompts for generating follow-up tasks.
- **Stats TUI** (t597_2, t597_3, t597_4): New `ait stats-tui` interactive statistics TUI (switcher shortcut `t`) with 12 panes across Overview/Labels/Agents/Velocity categories, including counters, charts, heatmaps, ranking tables, and an inline layout picker with user-only persistence.
- **More zoom levels in monitor** (t598): Added three XL zoom levels to the monitor TUI that size the agent list to fit exactly 3, 6, or 9 agents on screen.
- **Missing profile keys in settings TUI** (t611): Added five previously-missing execution-profile keys (child plan action, manual-verification follow-up mode, review modes and auto-continue, QA tier) to the settings TUI.

### Bug Fixes

- **Section viewer rendering and bindings** (t571_11): Fixed rendering glitches and broken Tab/arrow navigation in the shared section viewer, with a richer two-line row format in fullscreen mode.
- **Context-aware codebrowser footer** (t584): The codebrowser footer now reorders keybindings based on the currently focused pane.
- **Monitor shortcut in TUI switcher** (t596): The Monitor TUI is now reachable via `m` in the TUI switcher.
- **Stuck data-worktree detection** (t599): Added detection for a stuck `.aitask-data` worktree state with a new `./ait git-health` command and clear recovery hints when commits or pushes would fail.
- **Verified-rankings pane default** (t603): The stats TUI verified-rankings pane now defaults to the highest-run operation, with left/right arrow navigation to cycle through operations.
- **Carry-over task description** (t605): Fixed a bug where manual-verification carry-over task creation silently dropped the description; silent-mode stdout now reliably emits only the new task path.
- **Duplicate verification checklist heading** (t619): Fixed a bug where the manual-verification task wrapper emitted a duplicate `## Verification Checklist` heading.
- **GitHub username in website docs** (t620): Fixed incorrect GitHub username in website links across five pages so they now point to the correct `beyondeye/aitasks` repository.

### Improvements

- **Shared section viewer across TUIs** (t571_5, t571_8, t571_9, t571_10): New shared section-navigation widget library with minimap, click-to-scroll, and `V` fullscreen shortcut, integrated into the codebrowser detail/history panes, Brainstorm node-detail modal, and board task-detail screen.
- **Codebrowser footer binding order** (t586): The codebrowser footer now displays keybindings in a stable primary order with pane-specific extensions, keeping related keys adjacent.
- **Consolidated YAML-list helper** (t587): Consolidated duplicated YAML-list formatting logic into a single shared helper for more consistent task file output.
- **Stats data module split** (t597_1): Split stats data-collection logic into a dedicated module in preparation for the stats TUI, with no change to CLI behavior.
- **Centralized TUI registry** (t601): Centralized the TUI registry so the monitor correctly recognizes the stats TUI as a managed window; TUI-name config now merges over defaults.
- **Reliable manual-verification follow-up prompt** (t602): Moved the follow-up prompt to a reliable post-implementation step with richer discovery, added a new `manual_verification_followup_mode` profile key, and skipped the prompt in fast/remote profiles.
- **Verification parser skips section headers** (t604): Verification parsing now skips section-header bullets, carry-over task slugs use `_carryover`, and the verification loop gained a Stop-here pause option.
- **Unified verify/pause prompt** (t617): Merged the manual-verification pause prompt into the main Pass/Fail/Skip/Defer question with an "Other" free-text branch for intent-based abort routing.

### Documentation

- **Landing page and docs overhaul** (t585_1, t585_2, t585_3, t585_4, t585_5): Redesigned the website landing page around the "agentic IDE in your terminal" positioning, added a new 12-page Concepts section, rewrote the overview and top-level README around the shared 6-theme structure, and swept remaining legacy references.
- **Website-wide consistency sweep** (t594_1, t594_2, t594_3, t594_4, t594_5, t594_6): Swept the TUIs, Skills, Workflows, Concepts, and Commands sections for drift; documented five missing frontmatter fields and 16 missing `ait create`/`ait update` flags; reorganized Workflows into four categories; unified cross-cutting wording; and added consistent "Next" footers across the onboarding path.
- **Per-page maturity and depth labels** (t594_7): Added Hugo `maturity` and `depth` taxonomies with per-page badges across 89 docs pages so readers can see experimental/stabilizing and main/intermediate/advanced labels at a glance.
- **Brainstorm design docs update** (t571_6): Updated the brainstorm engine architecture docs to describe structured sections, the shared section viewer, and how section targeting flows through the wizard and agent prompts.
- **Manual verification workflow docs** (t583_4, t583_8): Added a new manual-verification workflow procedure to the task-workflow skill, a website workflow page, and documented the 5-touchpoint whitelisting convention for new helper scripts in CLAUDE.md.
- **README documentation map** (t595): Updated the README map to match the current website sidebar, adding Overview, Concepts, and TUI Applications entries.
- **Claude memory consolidated into CLAUDE.md** (t612): Consolidated per-memory Claude Code notes into CLAUDE.md so canonical conventions live with the project docs.

### Tests

- **Manual-verification issue type and tests** (t583_6): Registered the `manual_verification` issue type and added a test suite covering the verification follow-up helper across five scenarios.

### Maintenance

- **Remove `ait stats --plot` flag** (t597_5): Removed the deprecated `ait stats --plot` flag and interactive-chart code paths in favor of the new stats TUI, and added a Stats TUI documentation page.
- **Simplify pycache gitignore** (t621): Simplified the repo's gitignore to ignore Python `__pycache__` directories repo-wide.

## v0.16.1

### Features

- **Fuzzy file search in codebrowser** (t566): Added an in-TUI fuzzy file search box so you can quickly jump to any tracked file by partial name using recursive multi-alignment scoring.
- **Delete session from brainstorm TUI** (t568): Added a "Delete" session operation with double-confirmation modal so brainstorm sessions can be killed directly from the TUI.
- **Copy file path in codebrowser** (t570): Press `c` to copy the currently open file's relative or absolute path to the clipboard.
- **Word wrap toggle in codebrowser** (t572): Press `w` to toggle between truncate and wrap modes for long lines in the file view.
- **Minimonitor companion pane for `ait create`** (t574): Launching `ait create` from the board, codebrowser, or TUI switcher now automatically spawns a minimonitor companion pane alongside the new window.
- **`aitask-add-model` skill** (t579_2): New skill for registering AI code models and promoting them to defaults, with dry-run diffs, shared config/seed sync, and manual-review reporting.
- **Claude Opus 4.7 registered and promoted to default** (t579_3): Added both `opus4_7` and `opus4_7_1m` (1M context) variants; `opus4_7_1m` is now the default for pick, explore, and brainstorm ops.

### Bug Fixes

- **Enable brainstorm button for folded tasks** (t561): The brainstorm button in the board TUI is no longer disabled for folded tasks (only for Done/read-only/locked ones).
- **Fix `n` shortcut in codebrowser with no file selected** (t567): `n` now works with no file selected, defaults to the full file range, and opens the new window in the current tmux window.
- **Fix stale tmux window index in codebrowser** (t575): The codebrowser re-detects its tmux window index at action time, so `ait create` companion spawns always target the correct window.
- **Sync monitor preview after refresh** (t576): The monitor's content preview now updates correctly after focus is restored during auto-refresh.
- **Fix minimonitor auto-selection on window switch** (t577): The minimonitor now re-selects its own window's agent whenever the pane regains focus.
- **File tree refresh in codebrowser** (t580): Press `R` to refresh the codebrowser file tree against the current tracked-file set, picking up newly created or deleted files.

### Improvements

- **Section parser for brainstorm plans** (t571_1): New parser and validator for structured section markers in brainstorm proposal/plan files.
- **Structured section markers in brainstorm templates** (t571_2): Brainstorm agents now emit and consume structured section markers so downstream operations can target individual sections.
- **Section-aware brainstorm operations** (t571_3): `target_sections` parameter threaded through explore/compare/detail/patch operations for focused refinement.
- **Section selection in brainstorm TUI wizard** (t571_4): New wizard step lets you pick which sections of a proposal or plan to explore, compare, detail, or patch — enabling focused refinement of individual parts of a design.
- **Shared section-format reference for crew templates** (t578): Crew templates now support include directives, with the section-format reference extracted to a single shared partial reused by all brainstorm agents.
- **Add-model skill design audit** (t579_1): Catalogued every model reference in the repo and designed the `aitask-add-model` skill API.
- **Externalized brainstorm agent defaults** (t579_5): Brainstorm agent defaults now come from `codeagent_config.json` — model swaps only touch one file.

### Documentation

- **Document the aitask-from-file workflow** (t565): New "Create Tasks from Code" workflow page covering the `file_references` field, the codebrowser `n` flow, auto-merge safety layers, and reverse navigation from the board's File Refs row.
- **Update tests and docs for Opus 4.7 default** (t579_4): Updated all tests, aidocs, and user-facing documentation to reflect `opus4_7_1m` as the new default Claude Code model.

### Maintenance

- **Migrate persistent guidance from auto-memory to CLAUDE.md** (t582): Consolidated 13 durable team conventions and project facts from auto-memory into the project `CLAUDE.md` for reliable in-context guidance.

## v0.16.0

### Features

- **Interactive agent launch mode** (t461_1–t461_9): Agentcrew agents can now run in `interactive` mode (spawned in a tmux window you can attach to) alongside the existing `headless` mode. Brainstorm wizard gains a launch-mode toggle on the confirm screen, the Status tab shows an `e` shortcut to edit an agent's mode, per-agent-type defaults are configurable in the Settings TUI, and a new `ait crew setmode` CLI flips a Waiting agent between modes. Also introduces two new `openshell_headless` / `openshell_interactive` modes (launch semantics tracked as follow-up).
- **File references frontmatter field** (t540_1–t540_8): Tasks can now carry a `file_references` list pointing at specific files (and optional line ranges like `foo.py:10-20^30-40`). Codebrowser gains an `n` keybinding to create a task from the current selection or cursor line, an opened-file history pane, and a focus mechanism for jumping to specific ranges. The board TaskDetail modal shows a File Refs row that launches the codebrowser on press. Creating a task with `--file-ref` can auto-merge related pending tasks that touch the same file, and folds union file references across merged tasks.
- **Plan verification tracking** (t547_1–t547_3, t550): Plans now carry a `plan_verified` list recording which agents verified them against the current codebase. Profile keys `plan_verification_required` and `plan_verification_stale_after_hours` (exposed as int fields in the Settings TUI) let picks auto-skip verification when a plan has been validated recently by another agent.
- **ANSI log viewer** (t461_6): New `ait crew logview` TUI renders agent log files with ANSI color support, live tailing, search, and raw-mode toggle. Launchable via `L` from the brainstorm Status tab and monitor.
- **Task restart from monitor** (t556): Press `R` on an idle agent pane in `ait monitor` to kill the window and re-launch the task in a fresh agent.
- **Opened-file history in codebrowser** (t541): New left-sidebar recent-files list (capped at 15) persists across sessions. Three-way focus cycling between recent list, file tree, and code viewer.
- **Jump from minimonitor to full monitor** (t534): Press `m` in minimonitor to open `ait monitor` with the companion agent pane pre-focused.
- **Cascade archive/delete for parent tasks** (t531): Archiving or deleting a parent task from the board now cascades to its children with a transparent confirm dialog listing each affected file and its fate.
- **Use labels from previous task** (t540_6): Interactive task creation offers a `>> Use labels from previous task` menu entry that seeds the picker with your last selection, persisted per-user in `userconfig.yaml`.
- **Brainstorm TUI task context** (t537): The brainstorm TUI title bar now shows the owning task ID and name.
- **Refresh codebrowser history** (t552): Press `r` in the codebrowser history screen to reload archived task data with a progress modal and completion toast.
- **Plan externalize --force flag** (t542): The plan-externalize helper gains `--force` to overwrite an existing external plan file, used proactively at Step 6 while Step 8 remains idempotent.
- **Child task border style** (t554): Child task cards on the board use a dashed border (parents stay solid) for at-a-glance hierarchy visibility.

### Bug Fixes

- **Claude Code plan externalization** (t440): Claude's internal plan file is now externalized to `aiplans/` before archival via a shared `aitask_plan_externalize.sh` helper, preventing plan loss when Claude forgets.
- **Monitor preview per-pane scroll** (t532, t548, t553): Scroll position is now preserved per-pane when switching focus in `ait monitor`, anchored by top-line text so it survives content refresh. Preview freezes with a `PAUSED` badge when you scroll away from the tail, and a `t` key re-engages tail-follow. An async tmux refresh (t544) and an in-place fast rebuild path (t545) eliminate freezes and arrow-key loss during refresh ticks.
- **Narrow git add in archive script** (t533): `aitask_archive.sh` no longer stages unrelated sibling task/plan changes during archival — each file is added by explicit path.
- **Agentcrew import error from any cwd** (t536, t539): `ait crew status`, `dashboard`, and `report` now resolve imports correctly regardless of working directory; all four agentcrew scripts share a single package-style import pattern.
- **Codebrowser tab focus cycling** (t549): Fixed focus loops between sidebar, file tree, code viewer, and detail pane.
- **Fast profile stops after plan approval** (t555): The `fast` execution profile now defaults to `post_plan_action: ask` so you can approve or abort a plan before implementation starts.
- **Disable runner buttons after press** (t447_5): Brainstorm Status tab Start/Stop runner buttons are immediately disabled on press to prevent double-clicks.
- **Brainstorm launch-mode layout** (t546): Settings TUI indents the per-agent-type launch-mode rows and adds specific labels so they visually nest under the parent setting.
- **Draft finalize test harness** (t543): Fixed `test_draft_finalize.sh` regression caused by missing helper lib copies.
- **Script whitelists** (t538, t551): Added `aitask_fold_*`, `aitask_plan_externalize.sh`, and `aitask_plan_verified.sh` to Claude, OpenCode, and Gemini CLI whitelists.

### Improvements

- **Centralized launch mode vocabulary** (t461_8): Single source of truth in `lib/launch_modes.py` + `lib/launch_modes_sh.sh` so adding a new launch mode requires touching one file.
- **Minimonitor lifecycle on agent kill/restart** (t557): Introduced `kill_agent_pane_smart` so killing, restarting, or moving to a sibling agent correctly tears down the agent window (and its minimonitor companion) vs just the pane, depending on sibling count.

### Maintenance

- **Unify agentcrew package imports** (t539): All four agentcrew scripts use `from agentcrew.<module> import ...` with consistent sys.path setup.

## v0.15.1

### Features

- **Monitor preview scrollback and zoom** (t529): The monitor TUI preview now supports mouse-wheel scrolling through 200 lines of scrollback, an XL zoom preset that fills the terminal, and a `b` toggle for the scrollbar. Tail-follow keeps the view pinned to the latest output unless you scroll up.

### Bug Fixes

- **Fix shim active guard leak** (t530): The global `ait` shim no longer leaks `_AIT_SHIM_ACTIVE` into the project-local `ait` it execs, fixing spurious shim-loop errors when chaining commands like `ait ide`. Existing users should re-run `ait setup` to regenerate their installed shim.

### Documentation

- **TUI switcher docs and footer label** (t519_6): New "Available TUIs" overview page lists all built-in TUIs, and board/codebrowser/settings how-to pages now document the `j` TUI switcher. The monitor footer label is renamed from "Jump TUI" to "TUI switcher" for clarity.

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
