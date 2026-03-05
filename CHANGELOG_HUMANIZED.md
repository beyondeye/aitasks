# Releases

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
