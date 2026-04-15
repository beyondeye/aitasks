# Releases

## v0.16.0

v0.16.0 is a big one — 46 tasks landed, headlined by interactive agents you can actually watch, a file-references system that ties tasks to specific lines of code, and smarter plan verification that stops duplicated work across agents.

## Interactive agent launch mode

You can now run agentcrew agents in `interactive` mode instead of headless, which means they spawn inside a tmux window you can attach to and watch live. Flip the mode per-agent from the brainstorm wizard, from the Status tab with `e`, or via the new `ait crew setmode` CLI — each agent type ships with a sensible default that you can override in the Settings TUI.

## File references on tasks

Tasks can now carry a `file_references` list pointing at specific files and line ranges like `foo.py:10-20^30-40`. Open the codebrowser, select a block, press `n`, and a new task is created pre-seeded with that exact range. If the new task overlaps with an existing pending task's file refs, you'll get offered an auto-merge. The board's task-detail modal shows these refs as a clickable row that jumps straight back into the codebrowser at the right line.

## Plan verification tracking

Plans now record which agents have verified them against the current codebase. Combined with the new `plan_verification_required` and `plan_verification_stale_after_hours` profile keys, a pick can skip re-verification when another agent validated the plan recently — no more repeating the same work across agent runs.

## ANSI log viewer and task restart

A new `ait crew logview` TUI tails agent log files with ANSI color rendering, live search, and a raw-mode toggle. Press `L` from the brainstorm Status tab or monitor to open it for the focused agent. And when an agent goes off the rails, `R` on an idle pane in `ait monitor` now kills the window and restarts the task cleanly.

## Monitor preview that actually stays put

The monitor preview remembers where you scrolled on each pane, freezes with a `PAUSED` badge when you scroll up from the tail, and re-engages with `t`. Tmux refreshes run async now, so arrow keys don't get eaten by refresh ticks and the whole TUI stays responsive even with a lot of agents.

---

## v0.15.1

A quick follow-up to v0.15.0 with one notable feature, a shim fix, and the final piece of the TUI switcher docs.

## Scroll back through your agent's output

The monitor preview has been pretty tight until now — you saw the last few lines and that was it. v0.15.1 gives it real scrollback: mouse-wheel through the last 200 lines, toggle a scrollbar with `b`, or cycle to an XL preset that fills the whole terminal. It still follows the tail automatically, so you only lose the auto-scroll when you actually scroll up to read something.

## `ait ide` from a fresh shell just works

If you ever ran `ait ide` and got a confusing "shim loop" error, that was the global shim leaking its recursion guard into the project-local `ait` it handed off to. That's fixed now. If you installed the shim before this release, re-run `ait setup` once to regenerate it — then it's a one-time thing and you're done.

## TUI switcher, now documented

The `j` TUI switcher shipped a few versions ago but the docs didn't catch up until now. There's a new overview page listing all the TUIs you can jump between, and the board, codebrowser, and settings how-tos each explain how `j` fits into their workflow. The monitor footer also got a small rename — "Jump TUI" is now "TUI switcher", which is what everyone was calling it anyway.

---

## v0.15.0

v0.15.0 is a big release centered on live tmux monitoring. Running several code agents in parallel is now a first-class experience, with two new monitor TUIs, a one-keystroke TUI switcher, and a single `ait ide` command to get everything going.

## One-step startup with `ait ide`

Spinning up your workspace used to take four steps: open a terminal, `cd` into the project, start tmux, then start the monitor. Now it's just `ait ide`. The new command creates (or attaches to) your project's tmux session and opens a monitor window for you — whether you're running it fresh outside tmux, inside an existing session, or on a second terminal to get another view of the same workspace.

## Live monitor TUI for agent panes

`ait monitor` is a full-screen dashboard showing every tmux code-agent pane in your session with a live preview of what each one is doing. You can forward keystrokes straight into a paused agent, kill a runaway session with `k`, pull up task context with `i`, and flip auto-switch on to let the dashboard follow whichever agent needs attention next. Preview size cycles between S/M/L so you can balance overview and detail.

## Minimonitor side panel

Every time you launch an agent, a compact minimonitor now auto-spawns right beside it as a side panel. It lists the agents running in the same window, and two bindings do the heavy lifting: Tab jumps tmux focus to the agent pane next to you, and Enter sends an Enter keystroke to that sibling pane — perfect for unsticking a paused Claude without leaving your current context.

## Jump anywhere with `j`

A new TUI switcher (`j` from any dashboard) gives you a single keystroke to hop between the board, monitor, codebrowser, settings, brainstorm, and your running code agents. It also picks up your configured git TUI (lazygit, gitui, or tig) automatically, with inline key hints showing you the one-letter shortcut for each destination.

## Pick-as-you-go workflows

Several small-but-nice workflow additions land together: press `n` in the monitor to pick the next ready sibling (or first ready child) and close out the finished agent, press `N` in the board to rename a task with a clean git commit, and hit `(A)gent` in the launch dialog to override the model for a single run without touching your defaults.

---

## v0.14.0

v0.14.0 is a big one — headlined by a full history browser, process monitoring, and a unified tmux-aware launch dialog across all TUIs.

## Browse Your Completed Tasks

The codebrowser now has a history screen (press `h`) that lets you browse every archived task. Search and filter by labels, read the full task details and implementation plans, navigate to sibling tasks, and jump straight to the source files that were changed. It's the fastest way to understand why code looks the way it does.

## Process Monitoring and Hard Kill

Both the AgentCrew dashboard and brainstorm TUI now show running agent processes with resource stats. If an agent is stuck, you can pause, kill, or hard-kill it right from the UI — no more hunting for PIDs in a terminal.

## Unified Launch Dialog with tmux Support

Every agent launch action — pick, create, explain, QA — now goes through a shared dialog with Direct and tmux tabs. Configure your preferred tmux session and split settings once in the new Tmux settings tab, and every launch respects them.

## QA Agent from History

Added `qa` as a first-class codeagent operation. Press `a` in the history screen to launch a QA agent for any completed task, or press `H` in the codebrowser to jump directly from an annotated line to its task history.

## Archives Are Now Zstandard

The entire archive system has been migrated from tar.gz to tar.zst. Compression and decompression are noticeably faster, and all existing tar.gz archives are still readable. Run `ait migrate-archives` to convert your repo.

---

## v0.13.0

v0.13.0 is a big one — the diff viewer is fully operational, brainstorming has its own TUI, and there's a dedicated QA skill so you stop forgetting to write tests.

## Diff Viewer TUI

You can now visually compare implementation plans side-by-side (or interleaved) with `ait diffviewer`. It supports classical line-by-line diffs and structural section-aware diffs, word-level highlighting so you can spot exactly what changed within a line, markdown syntax coloring, and a unified mode for comparing multiple plans at once. There's even a merge screen where you can cherry-pick individual hunks from one plan into another.

## Brainstorm Engine & TUI

The brainstorm system is taking shape. You can initialize a brainstorm session for any task, and it creates a DAG of exploration nodes — each produced by a specialized agent (explorer, comparator, synthesizer, detailer, patcher). The TUI gives you a dashboard with node details, an ASCII art DAG graph, a dimension comparison matrix, and a wizard for launching new brainstorm operations. Still a work in progress, but the foundation is solid.

## Standalone QA Skill

`/aitask-qa` replaces the old embedded test-followup step with something much more capable. It analyzes your changes, identifies test coverage gaps, optionally runs your test suite, and produces a health score. Three tiers — quick, standard, and exhaustive — let you choose how deep to go. It can even create follow-up tasks for missing test coverage automatically.

## Default Execution Profiles

Tired of picking the same profile every time you run `/aitask-pick`? You can now set default profiles per skill in your project config, and override them with `--profile` on any command. The settings TUI has a nice per-skill picker for it too.

## Numbered Archives

The archive system got a major overhaul under the hood. Instead of one giant `old.tar.gz` that grows forever, tasks are now stored in numbered per-range archives. Lookups are O(1) instead of scanning the entire archive, and parallel archiving is safe. The migration is transparent — old archives still work.

---

## v0.12.2

A quick patch release focused on macOS compatibility.

## macOS Compatibility Fix

If you're running aitasks on macOS, the codebrowser Python files now include future annotations so they work correctly with the system Python version. A small fix, but one less thing to worry about when setting up on a Mac.

---

## v0.12.1

A smaller release this time with two quality-of-life improvements — one for the board UI and one under the hood for agent reliability.

## View Implementation Plans Right in the Board

You can now toggle between viewing a task and its implementation plan directly in the TUI board detail screen. Hit `v` to switch views — the border turns orange so you always know which file you're looking at. Editing is context-aware too, so pressing edit while viewing a plan opens the plan file, not the task.

## More Reliable Satisfaction Feedback

The satisfaction feedback procedure that agents follow after completing tasks has been simplified from a 3-file chain down to a single script call with `--agent` and `--cli-id` flags. This means agents are far less likely to get lost or hallucinate script names when wrapping up tasks in long conversations.

---

## v0.12.0

v0.12.0 brings multi-agent orchestration and the ability to undo any task you've ever completed. Two big additions that change how you work with aitasks.

## AgentCrew: Run Multiple Agents in Parallel

You can now decompose a large task into subtasks and have multiple AI agents work on them simultaneously — each in its own git worktree. `ait crew init` sets up the session, `ait crew addwork` assigns subtasks with dependencies, and `ait crew runner` handles the rest: launching agents in the right order, monitoring heartbeats, and managing concurrency. There's even a full TUI dashboard (`ait crew dashboard`) so you can watch everything happen in real time.

## Revert Any Completed Task

Made a change three weeks ago that turned out to be a bad idea? `/aitask-revert` analyzes the commits, files, and code areas touched by any task, then lets you choose a complete or partial revert. For parent tasks with children, you can even pick which child tasks to keep and which to undo. The skill creates a fully-documented revert task with all the context an agent needs to safely roll back the changes.

## Smarter Contribution Management

The contribution workflow got several quality-of-life improvements: `list-issues` and `check-imported` subcommands let you query what's pending and what's already been pulled in, several crash-causing pipefail bugs are fixed, and the website now properly lists all three contribution skills in one place.

## Board TUI: Delete and Archive Obsolete Tasks

The board now has a unified Delete/Archive flow for child tasks that have become obsolete. It checks dependencies, warns you about tasks that depend on the one you're removing, and marks archived tasks as "superseded" so you know why they were shelved.

---

## v0.11.0

v0.11.0 is a big one — it introduces a complete contribution management pipeline, a satisfaction feedback system that tracks how well each AI model performs, and a bunch of board and settings TUI improvements.

## Contribution Pipeline

You can now receive external contributions as GitHub/GitLab/Bitbucket issues and have them automatically checked for overlap with your existing tasks. CI/CD templates handle the automation, and a new contribution review skill walks you through analyzing, merging, and importing contributions. You can even merge multiple related issues into a single task or update an existing task with new contribution content.

## Satisfaction Feedback & Verified Scores

Every task completion can now optionally ask you to rate how well the AI did. These ratings feed into per-model verified scores tracked across time windows — all-time, monthly, and weekly. The settings TUI shows you which models perform best for which operations, and `ait stats` now includes verified model rankings with bar chart visualizations. Over time, this helps you pick the right model for the job.

## Explain Context

The explain feature now gathers historical task context automatically. When you ask for an explanation of a file, it pulls in relevant past tasks and plans to give you richer context about why the code looks the way it does.

## Board TUI Polish

The board got several quality-of-life improvements: a pick command dialog that works cleanly in tmux/terminal multiplexers, keyboard shortcuts on all task detail buttons, and better integration with the pick workflow.

---

## v0.10.0

v0.10.0 brings a major new contribution workflow, smarter commit attribution, and a bunch of quality-of-life improvements across the board.

## Contribute Back Without Forking

The new `/aitask-contribute` command lets you open structured issues against upstream repositories directly from your local changes — no fork required. It works with GitHub, GitLab, and Bitbucket, and even parses contributor metadata when issues are imported back. If your project defines `code_areas.yaml`, you get hierarchical area drill-down to scope your contributions precisely.

## Code Agent Commit Attribution

Commit messages now automatically include accurate code-agent and model attribution. Whether you're using Claude Code, Codex CLI, Gemini CLI, or OpenCode, the `Co-Authored-By` trailer reflects the actual agent and model that wrote the code. You can customize the coauthor email domain via `project_config.yaml`.

## Code Agent and Model Statistics

`ait stats` now tracks which code agents and LLM models are doing the work. You get breakdowns by agent, by model, weekly trend tables, and four new plot histograms. Great for understanding how your team's AI tooling usage evolves over time.

## Code Area Maps

A new `code_areas.yaml` file lets you define your project's structure, and the `/aitask-contribute` workflow now supports both framework-level and project-level contributions with automatic codemap generation and area drill-down.

## Python Codemap Scanner

The codemap scanning engine has been rewritten from bash to Python, bringing better performance and new filtering options like `--include-framework-dirs` and `--ignore-file`.

---

## v0.9.0

v0.9.0 is a big one — full Gemini CLI and OpenCode support, a cleaner directory layout, and several workflow fixes that make multi-agent development smoother.

## Gemini CLI and OpenCode Are First-Class Citizens

Both Gemini CLI and OpenCode now have complete skill and command wrapper sets, matching what Claude Code and Codex CLI already had. Run `ait setup` in any project and the framework automatically detects which agents you have installed, configuring each one with the right skills, permissions, and instructions. Gemini CLI commands also moved to TOML format with automatic permission policy merging, so setup is truly hands-off.

## Model Discovery and Status Tracking

The new `ait opencode-models` command scans your OpenCode installation to discover available models and catalog them with provider-prefixed identifiers. Models can now carry an active/unavailable status — unavailable ones are dimmed in the settings TUI and excluded from the model picker, so you never accidentally select a model that's gone offline.

## Directory Rename: aiscripts to .aitask-scripts

The framework's internal scripts directory has been renamed from `aiscripts/` to `.aitask-scripts/`, keeping implementation details hidden as a dotfile. All documentation, skills, tests, and configs have been updated to match. If you have custom scripts referencing the old path, they'll need a quick update.

## Workflow Fixes

Parent tasks no longer get stuck in a locked state after creating child tasks. Child task planning checkpoints work correctly now, and agent attribution properly records which code agent did the work instead of defaulting to "claude". Small fixes, but they add up to a noticeably smoother experience when working with task hierarchies.

---

## v0.8.3

v0.8.3 is a stability and polish release focused on making Codex CLI integration rock-solid and improving the stats experience.

## Python-powered Stats with Charts

The `ait stats` command has been rewritten in Python, making it noticeably faster. Even better, you can now get visual charts right in your terminal with `--plot` — just enable the optional `plotext` dependency during `ait setup`.

## Codex CLI Gets Proper Guardrails

If you're using Codex CLI with aitasks, interactive skills now properly require plan mode before running. No more cryptic failures when Codex tries to prompt you mid-execution. We also fixed broken YAML in skill definitions and added agent attribution tracking across all remote/async workflows.

## Safer Task Ownership

Before diving into implementation, the workflow now double-checks that you actually own the task — both the status and the assigned_to field. This prevents the frustrating scenario where two agents accidentally work on the same task.

---

## v0.8.2

v0.8.2 brings Codex CLI into the aitasks family — if you use OpenAI's Codex CLI, your aitask skills now work there too.

## Codex CLI Support

All 17 aitask skills now have Codex CLI wrappers. Run them with `$skill-name` syntax just like you would in Claude Code. A shared tool mapping file handles the translation between Claude Code and Codex CLI conventions, so skills behave consistently across both agents.

## Unified Install Pipeline

Running `ait setup` now automatically detects which AI code agents you have installed and configures each one. Codex CLI gets its skills, config, and instructions assembled from a layered seed system. A new marker-based system (`>>>aitasks`/`<<<aitasks`) makes instruction injection idempotent — your existing config files stay clean, and aitasks content is neatly delimited and replaceable.

## macOS Compatibility

A sweep of all 33 bash tests on macOS caught and fixed a real symlink path bug in `ait setup` plus several stale test assertions. If you ran into issues with `ait setup` in macOS temp directories, this release fixes it.

---

## v0.8.1

A small but important patch release fixing usability issues when working without a git remote and cleaning up the auto-update experience.

## Works Without a Remote

You can now use `ait create` and task locking in repositories that don't have a remote configured yet. The task ID counter runs locally and seamlessly upgrades to the remote-based atomic counter the moment you add a remote — no manual steps needed.

## Smarter Update Checks

The auto-update notification no longer suggests "upgrading" to an older version. Version comparisons now use proper semver ordering instead of string comparison, so you'll only see update prompts when there's actually a newer release available.

---

## v0.8.0

v0.8.0 is a big one — three major features that change how you work with aitasks day-to-day, plus a ton of polish across the board.

## Pull Request Import Pipeline

You can now import pull requests directly as aitasks. Run `ait primport` and point it at a PR from GitHub, GitLab, or Bitbucket — it creates a structured task with the PR metadata, contributor info, and a ready-to-go implementation plan. When you're done and archive the task, the original PR gets closed automatically. Contributor attribution flows through to your commits too, so the original author gets credit.

## Settings TUI

No more hand-editing JSON config files. The new `ait settings` command opens a full terminal UI where you can manage profiles, board settings, model configurations, and more — all in one place. It supports layered configuration (project vs. user), export/import, and even shows verification scores for AI models so you know which ones have been tested.

## Code Agent Wrapper

aitasks now works with any AI code agent, not just Claude Code. The new `ait codeagent` command is a universal entry point that routes to whichever agent you've configured — Claude Code, Gemini CLI, Codex CLI, or others. The board and settings TUIs use it automatically, and the new `implemented_with` frontmatter field tracks which agent built each task.

## Board View Modes

The board now has All/Git/Implementing view filters so you can quickly focus on what matters — tasks with uncommitted changes, tasks currently being worked on, or everything at once. The search placeholder even updates to tell you what you're filtering by.

## Refresh Models Skill

Keeping model configs up to date used to be manual. The new `/aitask-refresh-code-models` skill researches the latest AI code agent models via the web and updates your configuration files automatically.

---

## v0.7.1

v0.7.1 introduces the code browser — a brand new TUI for exploring your codebase with full task traceability — along with a batch of board improvements and developer experience fixes.

## Code Browser TUI

The headline feature of this release is a full code browser you can launch with `ait codebrowser`. It gives you a file tree on the left and a syntax-highlighted code viewer on the right, complete with task annotation gutters that show exactly which tasks modified each line. Navigate with keyboard or mouse, select code ranges, and jump straight into the explain skill for deeper analysis.

## Task Annotations at a Glance

Every line of code now carries its history. The code browser's gutter column shows color-coded task IDs so you can instantly see who changed what and why. Click any annotated line and a detail pane shows the full task description and implementation plan — no context switching needed.

## Smarter Explain Runs

Explain runs are now automatically named after their source directory and old runs get cleaned up automatically. No more manually tracking or pruning stale explain data — just run the explain pipeline and the system handles the rest.

## Board Quality-of-Life

The board gets column collapse/expand for less clutter, optimized lock refreshes for snappier interactions, and a smarter unlock flow that resets task status and assignment in one step.

## Multi-Platform Repository Support

Review guide imports and the new repo fetch library now work seamlessly across GitHub, GitLab, and Bitbucket with automatic platform detection — no manual configuration needed.

---

## v0.7.0

v0.7.0 is a big one — this release makes aitasks work everywhere: on macOS, on remote servers, and even in Claude Code Web.

## Run Tasks from Anywhere

The new `/aitask-pickrem` skill lets you run task implementation on remote servers, CI pipelines, or SSH sessions — completely hands-free. No interactive prompts, no fzf, just autonomous execution. Pair it with the new `ait sync` command to keep your task files in sync across machines, and the auto-merge engine handles any YAML frontmatter conflicts automatically.

## Claude Code Web Support

You can now implement tasks directly in Claude Code Web with `/aitask-pickweb`. It stores task data locally to avoid branch conflicts, and when you're done, `/aitask-web-merge` brings everything back to main. The board TUI gained lock/unlock controls so you can reserve tasks before starting a Web session, preventing anyone else from grabbing them.

## Full macOS Compatibility

macOS is now fully supported. We fixed every GNU-specific `sed`, `date`, `grep`, and `mktemp` usage across all scripts and tests. A new `sed_inplace()` helper and portable date wrapper ensure everything works with macOS's BSD tools out of the box. `ait setup` now validates your tool versions too.

## Task Data Branch

Task and plan files can now live on a dedicated git branch, so your task metadata doesn't clutter feature branch diffs. The new `./ait git` command routes task file operations through this branch transparently. All scripts, the board TUI, and skills have been updated to use it.

## Smart Sync with Auto-Merge

The new `ait sync` command handles pulling and pushing task data, and when conflicts arise in YAML frontmatter, the auto-merge engine resolves them intelligently using field-specific rules. Press `S` in the board TUI to sync without leaving the interface.

---

## v0.6.0

aitasks v0.6.0 is out, and it's a feature-packed release. Here are the highlights.

## Code Explanation Skill

Ever wanted to document how a piece of code evolved over time? The new `/aitask-explain` skill generates structured code explanations with evolution tracking. Point it at a file or module, and it produces a narrative that captures not just what the code does, but how it got there — complete with data extraction pipelines and run management for iterative analysis.

## Retroactive Task Wrapping

Already made changes but forgot to create a task first? The `/aitask-wrap` skill has you covered. It looks at your uncommitted work, figures out what you did, and retroactively creates a proper task with an implementation plan — so your project history stays clean even when you code first and organize later.

## Smarter File Selection

A new internal `user-file-select` capability makes it easier for other skills to help you find the right files. It combines keyword search, fuzzy name matching, and functionality-based search, and it's already integrated into both the explain and explore workflows.

## Board Auto-Refresh

The board TUI now refreshes itself periodically, with a new settings screen where you can dial in your preferred interval. No more manual refreshes to see what your teammates (or your other Claude sessions) are up to.

---

## v0.5.0

v0.5.0 is the biggest release yet. Code review capabilities, support for all three major git platforms, and a proper documentation website.

## AI-Powered Code Reviews

The `/aitask-review` skill brings structured code reviews to your workflow. Point it at a file, a directory, or your recent changes, and it runs a review using configurable review guides — sets of rules and patterns that define what to look for. It comes with 9 seed templates out of the box, plus Google style guides for 7 languages. Findings become tasks automatically, so nothing falls through the cracks.

There's a whole ecosystem of supporting skills for managing review guides: `/aitask-reviewguide-classify` for tagging guides with metadata, `/aitask-reviewguide-merge` for combining similar ones, and `/aitask-reviewguide-import` for pulling in guides from external sources.

## GitLab and Bitbucket Support

aitasks is no longer GitHub-only. Full issue import and status update support now works with GitLab and Bitbucket too. The framework auto-detects your platform from the git remote URL, so you don't need to configure anything — just use `ait issue-import` and `ait issue-update` as before.

## Documentation Website

The project now has a proper Hugo/Docsy documentation site with structured navigation, search, and a clean landing page. All the docs that used to live in the README have been reorganized into a proper hierarchy.

## Environment Detection

The review system can now auto-detect C#, Dart, Flutter, iOS, Swift, and Hugo projects, making review guide matching smarter across a wider range of tech stacks.

---

## v0.4.0

v0.4.0 is a big one. It makes getting started easier, adds new ways to investigate your codebase, and gives you more control over how you organize tasks.

## Auto-Bootstrap for New Projects

Setting up aitasks used to require downloading the installer manually. Now just run `ait setup` in any directory and it bootstraps everything automatically — the framework files, the task directory structure, all of it. One command, done.

## Interactive Codebase Exploration

The new `/aitask-explore` skill is for when you have a vague idea and need to figure out the right approach. Point it at a problem area, and it guides you through an interactive investigation of your code — asking follow-up questions, exploring related files, and eventually creating a well-scoped task from what you discover. It even checks for existing tasks that might overlap with your idea and offers to fold them together.

## Task Folding

The `/aitask-fold` skill lets you merge related tasks into a single one. If you've accumulated a few tasks that are really about the same thing, fold them together instead of juggling duplicates. The folded tasks get marked with a `Folded` status and a pointer to the primary task, so you can always trace back to the originals.

## Board Column Customization

The board TUI now lets you add, edit, and delete columns via a command palette (Ctrl+P) or by clicking column headers. Pick from 8 colors to make your board visually distinct.

---

## v0.3.0

aitasks v0.3.0 is all about making multi-device and multi-developer workflows rock-solid.

## Atomic Task IDs

Task IDs used to be assigned locally, which meant two people creating tasks at the same time could end up with the same ID. Not anymore. IDs now come from a shared atomic counter on a separate git branch, so every task gets a unique number no matter how many PCs are creating tasks against the same repo. Tasks start as local drafts and get their final ID when you commit.

## Concurrent Task Locking

Here's a scenario that used to be annoying: you pick a task on your laptop, and your coworker picks the same task on their desktop. With the new lock mechanism, that can't happen. When you pick a task, it acquires a lock using compare-and-swap semantics on a dedicated `aitask-locks` git branch. If someone else already grabbed it, you'll know immediately.

## Framework Updater

Keeping aitasks up to date just got easier. The new `ait install` command updates the framework to the latest (or a specific) version. It also runs a daily background check and quietly notifies you when a newer release is available — no nagging, just a heads-up next time you run a command.

---

## v0.2.0

aitasks v0.2.0 lays the groundwork for a polished developer experience. Here's what's new.

## Comprehensive Documentation

The project now ships with full documentation covering installation, command reference, Claude Code skills, platform support, and the task file format. Whether you're setting up for the first time or looking up a specific command, everything is in one place.

## Execution Profiles

Tired of answering the same workflow prompts every time you pick a task? Execution profiles let you pre-configure your answers. The built-in "fast" profile skips confirmations, uses your stored email, and jumps straight to implementation. Create your own profiles by dropping a YAML file in `aitasks/metadata/profiles/`.

## Automatic Changelog Generation

The new `/aitask-changelog` skill harvests your commit messages and archived plan files to generate release notes automatically. Since `/aitask-pick` already enforces a commit convention with task IDs, the raw material for release notes is created as a side effect of your regular development work. No extra documentation effort needed at release time.

## Board Improvements

The task board TUI gets a quality-of-life improvement: pressing `x` when a child card is focused now collapses back to the parent task, making navigation more intuitive.

---
