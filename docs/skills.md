# Claude Code Skills

aitasks provides Claude Code skills that automate the full task workflow. These skills are invoked as slash commands within Claude Code.

## Table of Contents

- [Skill Overview](#skill-overview)
- [/aitask-pick](#aitask-pick-number)
  - [Execution Profiles](#execution-profiles)
- [/aitask-explore](#aitask-explore)
- [/aitask-fold](#aitask-fold)
- [/aitask-create](#aitask-create)
- [/aitask-stats](#aitask-stats)
- [/aitask-changelog](#aitask-changelog)

---

## Skill Overview

| Skill | Description |
|-------|-------------|
| `/aitask-pick` | The central skill — select and implement the next task (planning, branching, implementation, archival) |
| `/aitask-explore` | Explore the codebase interactively, then create a task from findings |
| `/aitask-fold` | Identify and merge related tasks into a single task |
| `/aitask-create` | Create tasks interactively via Claude Code |
| `/aitask-stats` | View completion statistics |
| `/aitask-changelog` | Generate changelog entries from commits and plans |

## /aitask-pick [number]

The central skill of the aitasks framework and the core of the development workflow. This is a full development workflow skill that manages the complete task lifecycle from selection through implementation, review, and archival.

**Usage:**
```
/aitask-pick            # Interactive task selection from prioritized list
/aitask-pick 10         # Directly select parent task t10
/aitask-pick 10_2       # Directly select child task t10_2
```

**Workflow overview:**

1. **Profile selection** — Loads an execution profile from `aitasks/metadata/profiles/` to pre-answer workflow questions and reduce prompts. See the [Execution Profiles](#execution-profiles) section below for configuration details
2. **Task selection** — Shows a prioritized list of tasks (sorted by priority, effort, blocked status) with pagination, or jumps directly to a task when a number argument is provided
3. **Child task handling** — When a parent task with children is selected, drills down to show child subtasks. Gathers context from archived sibling plan files so each child task benefits from previous siblings' implementation experience
4. **Status checks** — Detects edge cases: tasks marked Done but not yet archived, and orphaned parent tasks where all children are complete. Offers to archive them directly
5. **Assignment** — Tracks who is working on the task via email, sets status to "Implementing", commits and pushes the status change
6. **Environment setup** — Optionally creates a separate git branch and worktree (`aiwork/<task_name>/`) for isolated implementation, or works directly on the current branch
7. **Planning** — Enters Claude Code plan mode to explore the codebase and create an implementation plan. If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
8. **Implementation** — Follows the approved plan, updating the plan file with progress and any deviations
9. **User review** — Presents a change summary for review. Supports an iterative "need more changes" loop where each round of feedback is logged in the plan file before re-presenting for approval
10. **Post-implementation** — Archives task and plan files, updates parent task metadata for child tasks, optionally updates/closes linked GitHub issues, and merges the branch if a worktree was used

**Key capabilities:**

- **Direct task selection** — `/aitask-pick 10` selects a parent task; `/aitask-pick 10_2` selects a specific child task. Both formats skip the interactive selection step and show a brief summary for confirmation (skippable via profile)
- **Task decomposition** — During planning, if a task is assessed as high complexity, offers to break it into child subtasks. Each child task is created with detailed context (key files, reference patterns, implementation steps, verification) so it can be executed independently in a fresh context
- **Plan mode integration** — Uses Claude Code's built-in plan mode for codebase exploration and plan design. When an existing plan file is found, offers: "Use current plan" (skip planning), "Verify plan" (check against current code), or "Create from scratch". Plan approval via ExitPlanMode is always required
- **Review cycle** — After implementation, the user reviews changes before any commit. The "Need more changes" option creates numbered change request entries in the plan file, then loops back to review. Each iteration is tracked with timestamps
- **Issue update integration** — When archiving a task that has a linked `issue` field, offers to update the GitHub issue: close with implementation notes, comment only, close silently, or skip. Uses `ait issue-update` which auto-detects associated commits and extracts plan notes
- **Abort handling** — Available at multiple checkpoints (after planning, after implementation). Reverts task status, optionally deletes the plan file, cleans up worktree/branch if created, and commits the status change
- **Branch/worktree support** — Optionally creates an isolated git worktree at `aiwork/<task_name>/` on a new `aitask/<task_name>` branch. After implementation, merges back to the base branch and cleans up the worktree and branch

### Execution Profiles

The `/aitask-pick` skill asks several interactive questions before reaching implementation (email, local/remote, worktree, plan handling, etc.). Execution profiles let you pre-configure answers to these questions so you can go from task selection to implementation with minimal input.

Profiles are YAML files stored in `aitasks/metadata/profiles/`. Two profiles ship by default:

- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use first stored email, work locally on current branch, reuse existing plans

When you run `/aitask-pick`, the profile is selected first (Step 0a). If only one profile exists, it's auto-loaded. With multiple profiles, you're prompted to choose.

#### Profile Settings

| Key | Type | Description |
|-----|------|-------------|
| `name` | string (required) | Display name shown during profile selection |
| `description` | string (required) | Description shown below profile name during selection |
| `skip_task_confirmation` | bool | `true` = auto-confirm task selection |
| `default_email` | string | `"first"` = use first email from emails.txt; or a literal email address |
| `run_location` | string | `"locally"` or `"remotely"` |
| `create_worktree` | bool | `true` = create worktree; `false` = work on current branch |
| `base_branch` | string | Branch name for worktree (e.g., `"main"`) |
| `plan_preference` | string | `"use_current"`, `"verify"`, or `"create_new"` |
| `post_plan_action` | string | `"start_implementation"` = skip post-plan prompt |
| `explore_auto_continue` | bool | `true` = auto-continue from explore to implementation (used by `/aitask-explore`) |

Omitting a key means the corresponding question is asked interactively. Plan approval (ExitPlanMode) is always mandatory and cannot be skipped.

#### Creating a Custom Profile

```bash
cp aitasks/metadata/profiles/fast.yaml aitasks/metadata/profiles/my-profile.yaml
```

Edit the file to set your preferences:

```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: first
run_location: locally
create_worktree: true
base_branch: main
plan_preference: use_current
post_plan_action: start_implementation
```

Profiles are preserved during `install.sh --force` upgrades (existing files are not overwritten).

---

## /aitask-explore

Explore the codebase interactively with guided investigation, then create a task from findings. This skill bridges the gap between "I think something needs work" and a well-defined task with context.

**Usage:**
```
/aitask-explore
```

**Workflow overview:**

1. **Profile selection** — Same profile system as `/aitask-pick`
2. **Exploration setup** — Choose an exploration mode:
   - **Investigate a problem** — Debug an issue, trace a symptom, find a root cause. Creates bug tasks by default
   - **Explore codebase area** — Understand a module, map its structure and dependencies
   - **Scope an idea** — Discover what code is affected by a proposed change
   - **Explore documentation** — Find documentation gaps, outdated docs, or missing help text
3. **Iterative exploration** — Claude explores the codebase using the selected strategy. After each round, presents findings and offers to continue exploring, create a task, or abort
4. **Task creation** — Summarizes all findings and creates a task file with metadata pre-filled based on the exploration type
5. **Optional handoff** — After task creation, choose to continue directly to implementation (via the standard `/aitask-pick` workflow) or save the task for later

**Key capabilities:**

- **Guided exploration strategies** — Each exploration mode has a tailored investigation approach. Problem investigation traces data flow and error handling; codebase exploration maps dependencies and patterns; idea scoping estimates blast radius
- **Iterative discovery** — Multiple exploration rounds with user-directed focus. Redirect the investigation at any point based on intermediate findings
- **Context-rich task creation** — Tasks created from exploration include specific findings, file paths, and investigation context that would be tedious to write manually
- **Seamless handoff** — When continuing to implementation, the full exploration context flows into the planning phase

**Profile key:** `explore_auto_continue` — Set to `true` to skip the "continue to implementation or save" prompt and automatically proceed to implementation.

**Folded tasks:**

During task creation, `/aitask-explore` scans pending tasks (`Ready`/`Editing` status) for overlap with the new task. If related tasks are found, you're prompted to select which ones to "fold in" — their content is incorporated into the new task's description, and the originals are automatically deleted when the new task is archived after implementation.

Only standalone parent tasks (no children) can be folded. The `folded_tasks` frontmatter field tracks which tasks were folded in. During planning, there's no need to re-read the original folded task files — all relevant content is already in the new task.

To fold tasks outside of the explore workflow, use [`/aitask-fold`](#aitask-fold) — a dedicated skill for identifying and merging related tasks.

---

## /aitask-fold

Identify and merge related tasks into a single task, then optionally execute it. This skill provides the same folding capability as `/aitask-explore` but as a standalone workflow — no codebase exploration required.

**Usage:**
```
/aitask-fold                    # Interactive: discover and fold related tasks
/aitask-fold 106,108,112        # Explicit: fold specific tasks by ID
```

**Workflow overview:**

1. **Profile selection** — Same profile system as `/aitask-pick`
2. **Task discovery** — In interactive mode, lists all eligible tasks (`Ready`/`Editing` status, no children, standalone parents only), identifies related groups by shared labels and semantic similarity, and presents them for multi-select. In explicit mode, validates the provided task IDs and skips discovery
3. **Primary task selection** — Choose which task survives as the primary. All other tasks' content is merged into it, and the originals are deleted after archival
4. **Content merging** — Non-primary task descriptions are appended under `## Merged from t<N>` headers. The `folded_tasks` frontmatter field tracks which tasks were folded in (appends to existing if present)
5. **Optional handoff** — Continue directly to implementation (via the standard `/aitask-pick` workflow) or save the merged task for later

**Key capabilities:**

- **Two invocation modes** — Interactive discovery for finding related tasks, or explicit task IDs for quick folding when you already know what to merge
- **Graceful validation** — Invalid or ineligible tasks are warned and skipped rather than aborting. The workflow only aborts if fewer than 2 valid tasks remain
- **Append-safe** — If the primary task already has `folded_tasks` from a previous fold, new IDs are appended rather than replacing
- **Same cleanup mechanism** — Uses the same `folded_tasks` frontmatter field as `/aitask-explore`. Post-implementation cleanup (deletion of folded task files) is handled by the shared task-workflow Step 9

**Profile key:** `explore_auto_continue` — Reuses the same key as `/aitask-explore`. Set to `true` to skip the "continue to implementation or save" prompt.

---

## /aitask-create

Create a new task file with automatic numbering and proper metadata via Claude Code prompts.

**Usage:**
```
/aitask-create
```

**Workflow:** Claude Code guides you through task creation using `AskUserQuestion` prompts:

1. **Parent selection** — Choose standalone or child of existing task
2. **Task number** — Auto-determined from active, archived, and compressed tasks
3. **Metadata** — Priority, effort, dependencies (with sibling dependency prompt for child tasks)
4. **Task name** — Free text with auto-sanitization
5. **Definition** — Iterative content collection with file reference insertion via Glob search
6. **Create & commit** — Writes task file with YAML frontmatter and commits to git

This is the Claude Code-native alternative — metadata collection happens through Claude's UI rather than terminal fzf.

---

## /aitask-stats

View task completion statistics via Claude Code.

**Usage:**
```
/aitask-stats
```

Runs `./aiscripts/aitask_stats.sh` and displays the results. Provides the same 7 types of statistics as `ait stats`:

- Summary counts (7-day, 30-day, all-time)
- Daily breakdown with optional task IDs
- Day-of-week averages
- Per-label weekly trends (4 weeks)
- Label day-of-week breakdown (30 days)
- Task type weekly trends
- Label + issue type trends

Supports all command-line options (`-d`, `-v`, `--csv`, `-w`). For CSV export, provides guidance on opening the file in LibreOffice Calc with pivot tables and charts.

---

## /aitask-changelog

Generate a changelog entry by analyzing commits and archived plans since the last release. Orchestrates the `ait changelog` command with AI-powered summarization.

**Usage:**
```
/aitask-changelog
```

**Workflow:**

1. **Gather release data** — Runs `ait changelog --gather` to collect all tasks since the last release tag, with their issue types, plan files, commits, and implementation notes
2. **Summarize plans** — Reads each task's archived plan file and generates concise user-facing summaries (what changed from the user's perspective, not internal details)
3. **Draft changelog entry** — Groups summaries by issue type under `### Features`, `### Bug Fixes`, `### Improvements` headings. Format: `- **Task name** (tNN): summary`
4. **Version number** — Reads `VERSION` file, calculates next patch/minor, asks user to select or enter custom version
5. **Version validation** — Ensures the selected version is strictly greater than the latest version in CHANGELOG.md (semver comparison)
6. **Overlap detection** — Checks if any gathered tasks already appear in the latest changelog section. If overlap found, offers: "New tasks only", "Replace latest section", or "Abort"
7. **Review and finalize** — Shows the complete formatted entry for approval. Options: "Write to CHANGELOG.md", "Edit entry", or "Abort"
8. **Write and commit** — Inserts the entry into CHANGELOG.md (after the `# Changelog` header) and commits

**Key features:**
- User-facing summaries: focuses on what changed, not implementation details
- Version validation prevents duplicate or regressive version numbers
- Overlap detection handles incremental changelog updates when some tasks were already documented
- Supports both new CHANGELOG.md creation and insertion into existing files
