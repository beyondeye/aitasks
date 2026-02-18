# t129: Dynamic Task Skills — Implementation Plan

## Context

The current aitask workflow requires a pre-defined task file before running `/aitask-pick`. This creates friction for two common scenarios:

1. **Exploration**: The user wants to explore a problem or codebase area without knowing exactly what task to create yet
2. **Code Review**: The user wants Claude to review code and identify issues, then create tasks from findings

Both workflows end with a dynamically-created task that can either proceed immediately to implementation (using the aitask-pick machinery) or be saved for later. To avoid duplicating Steps 3-9 of aitask-pick in each new skill, we'll extract those steps into a shared workflow file.

## Approach

Split into **6 child tasks**:

1. **t129_1**: Extract shared workflow from aitask-pick (foundation — must be done first)
2. **t129_2**: Create `/aitask-explore` skill (user-driven exploration → task creation)
3. **t129_3**: Review guides infrastructure (seed templates, metadata directory, `ait setup` integration)
4. **t129_4**: Create `/aitask-review` skill (Claude-driven code review using review guides)
5. **t129_5**: Document `/aitask-explore` in README.md (motivation, workflow, sample usage)
6. **t129_6**: Document `/aitask-review` in README.md (motivation, workflow, review guides, sample usage)

**Dependencies**: t129_1 must be done first. t129_2 and t129_3 are independent (both depend only on t129_1). t129_4 depends on t129_3. t129_5 depends on t129_2. t129_6 depends on t129_4.

---

## Child Task 1: Refactor aitask-pick — Extract Shared Workflow

### Goal
Extract Steps 3-9 and shared procedures from `aitask-pick/SKILL.md` into a new internal skill `task-workflow`, then update aitask-pick to reference it.

### Files to Create/Modify
- **Create**: `.claude/skills/task-workflow/SKILL.md` (~500 lines) — internal skill, not user-invocable
- **Modify**: `.claude/skills/aitask-pick/SKILL.md` (reduce from ~872 to ~370 lines)

### Implementation Steps

1. **Create `.claude/skills/task-workflow/SKILL.md`**:
   - Add YAML frontmatter marking it as internal:
     ```yaml
     ---
     name: task-workflow
     description: Shared implementation workflow used by aitask-pick, aitask-explore, and aitask-review. Handles task assignment, environment setup, planning, implementation, review, and archival.
     user-invocable: false
     ---
     ```
   - Add a **Context Requirements** section documenting what the calling skill must provide:
     ```markdown
     ## Context Requirements

     The calling skill MUST establish these variables before entering this workflow:
     - **task_file**: Full path to the task file (e.g., `aitasks/t130_my_task.md`)
     - **task_id**: Task number (e.g., `130` or `130_2` for child tasks)
     - **task_name**: Name extracted from filename (e.g., `t130_my_task`)
     - **is_child**: Whether this is a child task (true/false)
     - **parent_id**: Parent task number (if child task)
     - **active_profile**: The loaded execution profile (if any), or "none"
     - **previous_status**: Task status before entering this workflow (for abort revert)
     ```
   - Copy Steps 3-9 verbatim from current aitask-pick SKILL.md
   - Copy Task Abort Procedure, Issue Update Procedure, Lock Release Procedure
   - Copy the Execution Profiles schema reference and Notes section (only the parts relevant to Steps 3-9)
   - Ensure all profile checks reference `active_profile` consistently

2. **Update `.claude/skills/aitask-pick/SKILL.md`**:
   - Keep Steps 0a (profile loading), 0b (direct task selection), 0c (remote sync), 1 (label filtering), 2 (list and select task)
   - After Step 2 (task selected), add a handoff section:
     ```markdown
     ### Handoff to Shared Workflow

     At this point, a task has been selected. Set the following context, then read and follow
     the shared workflow in `.claude/skills/task-workflow/SKILL.md`:

     - **task_file**: `aitasks/<selected_filename>`
     - **task_id**: `<extracted_task_number>`
     - **task_name**: `<extracted_from_filename>`
     - **is_child**: `<true if child task was selected>`
     - **parent_id**: `<parent number if child>`
     - **active_profile**: `<loaded profile from Step 0a>`
     - **previous_status**: `Ready` (the status before picking)
     ```
   - Keep the execution profile loading and notes that are specific to aitask-pick's Steps 0-2

### Verification
- Run `/aitask-pick` on a test task and verify the full workflow still works (profile loading → task selection → plan → implementation → archival)
- Verify that the shared file is correctly read and followed
- Verify abort procedure still works

---

## Child Task 2: Create `/aitask-explore` Skill

### Goal
Create a user-driven exploration skill where the user explores the codebase, eventually crystallizes findings into a task, and optionally continues to implementation.

### Files to Create
- **Create**: `.claude/skills/aitask-explore/SKILL.md`

### Workflow Design

```
Step 0a: Select Execution Profile (same as aitask-pick)
Step 0c: Sync with Remote (same as aitask-pick)

Step 1: Exploration Setup
  - Ask user: "What would you like to explore?" (free text via AskUserQuestion "Other")
  - Options for exploration type:
    - "Investigate a problem" (e.g., "why is X slow?", "where does Y break?")
    - "Explore codebase area" (e.g., "understand the auth module")
    - "General exploration" (e.g., "look for improvement opportunities")

Step 2: Iterative Exploration
  - Claude explores the codebase based on user's focus
  - After each exploration round, ask user:
    - "Continue exploring" (keep going, user may redirect)
    - "I have enough, create a task" (proceed to task creation)
    - "Abort exploration" (stop without creating a task)
  - Take notes on findings throughout

Step 3: Task Creation
  - Summarize exploration findings
  - Propose:
    - Task title (name for the task file)
    - Priority (suggest based on findings)
    - Effort (suggest based on findings)
    - Labels (suggest based on area explored)
    - Description (comprehensive, based on exploration notes)
  - Ask user to confirm or modify
  - Create task using: aitask_create.sh --batch --commit [with all fields]
  - Read back the created task file to get the assigned task ID

Step 4: Decision Point
  - AskUserQuestion:
    - "Task created: t<N>_<name>.md. How would you like to proceed?"
    - Options:
      - "Continue to implementation" → set context, read shared workflow
      - "Save for later" → commit and inform user
```

### Profile Keys
The explore skill reuses existing profile keys:
- `default_email`, `run_location`, `create_worktree`, `base_branch`, `plan_preference`, `post_plan_action`
- New optional key: `explore_auto_continue: true` — skip the "Continue/Save" decision and always continue to implementation

### Integration with Shared Workflow
When "Continue to implementation" is selected:
- Set context variables (task_file, task_id, task_name, etc.)
- The task was just created with status "Ready", so `previous_status` = "Ready"
- Read and follow `.claude/skills/task-workflow/SKILL.md`
- Step 3 (status checks) will pass through since the task is fresh
- Step 4 (assign) will update status to "Implementing" as usual

### Verification
- Test the exploration flow end-to-end
- Test the "save for later" path (task file should be committed)
- Test the "continue to implementation" path (should seamlessly enter shared workflow)
- Test the "abort exploration" path (no task created)

---

## Child Task 3: Review Guides Infrastructure

### Goal
Create the review guides system: file format definition, seed templates, metadata directory, and `ait setup` integration. This provides the foundation that the `/aitask-review` skill will consume.

### Files to Create/Modify
- **Create**: `seed/reviewguides/` directory with template review guide files (9 files)
- **Create**: `aireviewguides/` directory (populated during `ait setup`)
- **Modify**: `aiscripts/aitask_setup.sh` — add review guide selection/installation step

### Review Guide File Format

Each review guide is a markdown file in `aireviewguides/`:

```yaml
---
name: Code Conventions
description: Check naming, formatting, and pattern consistency
environment: [python]  # optional; list of environments this mode targets
---

## Review Instructions

### Naming Conventions
- Check that function/method names use snake_case
- Check that class names use PascalCase
- Check that constants use UPPER_SNAKE_CASE
...

### Code Organization
- Check that imports are grouped (stdlib, third-party, local)
- Check that modules have a clear single responsibility
...
```

**Frontmatter fields:**
- `name` (required): Display name shown during mode selection
- `description` (required): Short description of what this mode reviews
- `environment` (optional): List of environments/languages this mode is relevant for (e.g., `[python]`, `[android, kotlin]`, `[cpp, cmake]`). When omitted, the mode is universal (shown for all projects)

### Seed Review Guide Templates

Create the following seed templates in `seed/reviewguides/`:

| File | Name | Environment | Focus |
|------|------|-------------|-------|
| `code_conventions.md` | Code Conventions | (universal) | Naming, formatting, patterns |
| `code_duplication.md` | Code Duplication | (universal) | DRY violations, copy-paste code |
| `refactoring.md` | Refactoring Opportunities | (universal) | Complex functions, tight coupling, long methods |
| `security.md` | Security Review | (universal) | Input validation, injection, secrets, OWASP |
| `performance.md` | Performance Review | (universal) | Unnecessary allocations, N+1 patterns, missing caching |
| `error_handling.md` | Error Handling | (universal) | Missing error checks, poor messages, unhandled edge cases |
| `python_best_practices.md` | Python Best Practices | [python] | Type hints, f-strings, context managers, pathlib |
| `android_best_practices.md` | Android Best Practices | [android, kotlin] | Lifecycle, coroutines, compose patterns |
| `shell_scripting.md` | Shell Script Quality | [bash, shell] | Quoting, error handling, portability |

### Setup Integration (`ait setup`)

Add a new step to `aiscripts/aitask_setup.sh` (after existing steps):

1. List all seed review guide files from `seed/reviewguides/`
2. Show user the list with names, descriptions, and environments
3. Let user select which to install (multi-select with fzf, or "Install all")
4. Copy selected files to `aireviewguides/`
5. Skip files that already exist in the target directory (preserve user customizations)

### Verification
- Verify seed review guide files have valid YAML frontmatter
- Run `ait setup` and verify the review guide installation step works
- Verify existing files are not overwritten during setup
- Verify the metadata/reviewguides/ directory is correctly populated

---

## Child Task 4: Create `/aitask-review` Skill

### Goal
Create the Claude-driven code review skill that uses the review guides from child task 3 to perform targeted reviews, present findings, and create tasks.

### Files to Create
- **Create**: `.claude/skills/aitask-review/SKILL.md`

### Prerequisites
- Child task 3 (review guides infrastructure) must be complete
- Review guide files must exist in `aireviewguides/`

### Workflow Design

```
Step 0a: Select Execution Profile (same as aitask-pick)
Step 0c: Sync with Remote (same as aitask-pick)

Step 1: Review Setup
  1a. Ask user for target paths/modules (AskUserQuestion with free text)
      - E.g., "src/auth/", "the API layer", "everything"

  1b. Load installed review guides from aireviewguides/
      - Read each .md file's frontmatter (name, description, environment)
      - Optionally auto-detect project environment:
        - Check for pyproject.toml/setup.py → python
        - Check for build.gradle/build.gradle.kts → android/kotlin
        - Check for CMakeLists.txt → cpp/cmake
        - Check for package.json → javascript/typescript
        - Check for *.sh scripts → bash/shell
      - Filter modes: show environment-matching modes first, then universal,
        then non-matching (labeled as "other environments")
      - AskUserQuestion multiSelect: "Select review guides to apply:"
        - Each option: label = name, description = description from frontmatter

  1c. Read the full content of each selected review guide file
      - These become the review instructions that Claude follows in Step 2

Step 2: Automated Review
  - Claude systematically explores the specified target paths
  - For EACH selected review guide, follow its review instructions
  - Compile findings with:
    - Review guide (which mode generated this finding)
    - Severity (high/medium/low)
    - Location (file:line)
    - Description (what's wrong and why)
    - Suggested fix (brief)

Step 3: Findings Presentation
  - Present findings grouped by review guide and severity
  - Ask user to select which findings to address (AskUserQuestion multiSelect)
  - If no findings: inform user and end

Step 4: Task Creation
  - AskUserQuestion:
    - "How should the selected findings become tasks?"
    - Options:
      - "Single task with all findings" → create one task
      - "Separate task per finding" → create multiple tasks
      - "Group by review guide" → create one task per mode
  - Create task(s) using aitask_create.sh --batch --commit
  - If multiple tasks created, offer to make them children of a parent task

Step 5: Decision Point
  - If single task:
    - "Continue to implementation" or "Save for later"
  - If multiple tasks:
    - "Pick one to start implementing" → AskUserQuestion to select
    - "Save all for later" → commit and inform user
```

### Profile Keys
Reuses existing keys plus:
- `review_auto_continue: true` — auto-continue to implementation after review
- `review_default_modes: "code_conventions,security"` — pre-select review guides by filename (without .md)

### Integration with Shared Workflow
Same as aitask-explore: set context variables and read shared workflow.

For multiple tasks created as children:
- Creates a parent task (e.g., "Code review: auth module")
- Creates children for each finding/category
- If user picks one to implement, use `/aitask-pick <parent>_<child>` pattern

### Verification
- Test with seed review guides installed
- Test environment auto-detection and filtering
- Test single-task and multi-task creation paths
- Test "save for later" path
- Test review guide selection with multiSelect
- Test that custom review guides in metadata/reviewguides/ are picked up

---

## Child Task 5: Document `/aitask-explore` in README.md

### Goal
Add comprehensive documentation for the `/aitask-explore` skill to `README.md`, covering motivation, workflow description, and sample usage scenarios.

### Files to Modify
- **Modify**: `README.md`

### Implementation Steps

1. **Update Table of Contents** — Add entry for `/aitask-explore` under "Claude Code Integration"
2. **Update Claude Code Integration table** — Add row: `| /aitask-explore | Start with exploration, create a task when ready, optionally continue to implementation |`
3. **Add `/aitask-explore` section** in Claude Code Integration (after `/aitask-pick`), following the existing documentation pattern:
   - **Usage block** with invocation syntax
   - **Motivation paragraph** — Explain the friction of defining tasks upfront; the value of exploring first when you don't know what the task is yet
   - **Workflow overview** — Numbered steps matching the skill's actual flow (profile → exploration setup → iterative exploration → task creation → decision point)
   - **Key capabilities** — Bullet list: iterative exploration with redirects, automatic task creation from findings, seamless handoff to aitask-pick's implementation pipeline, abort without task creation
4. **Add a new "Typical Workflows" subsection**: "Exploration-Driven Development" — Describe the scenario where a developer doesn't know exactly what to build, explores a problem area with Claude, and crystallizes findings into an actionable task. Include a concrete example walkthrough.

### Verification
- Verify markdown renders correctly (headings, tables, code blocks)
- Verify TOC links work
- Cross-reference with actual SKILL.md to ensure documentation matches implementation

---

## Child Task 6: Document `/aitask-review` in README.md

### Goal
Add comprehensive documentation for the `/aitask-review` skill to `README.md`, covering motivation, workflow description, and sample usage scenarios.

### Files to Modify
- **Modify**: `README.md`

### Implementation Steps

1. **Update Table of Contents** — Add entry for `/aitask-review` under "Claude Code Integration"
2. **Update Claude Code Integration table** — Add row: `| /aitask-review | AI-driven code review that identifies issues and creates tasks from findings |`
3. **Add `/aitask-review` section** in Claude Code Integration (after `/aitask-explore`), following the existing documentation pattern:
   - **Usage block** with invocation syntax
   - **Motivation paragraph** — Explain the value of automated code review: discovering code conventions violations, duplication, refactoring opportunities, and security issues without manual inspection; turning findings into actionable tasks
   - **Workflow overview** — Numbered steps: profile → review setup (target paths, review guide selection) → automated review → findings presentation → task creation (single/split/by-mode) → decision point
   - **Review guides system** — Document the review guide file format (YAML frontmatter with name, description, environment), the `aireviewguides/` directory, seed templates, environment auto-detection, and how to create custom review guides
   - **Seed review guides** — List all provided seed templates with descriptions
   - **Key capabilities** — Bullet list: configurable review guides, environment-aware filtering, targeted or broad reviews, severity-based findings, flexible task creation, parent/child structure for multi-task output, seamless handoff to implementation, custom review guide authoring
4. **Add a new "Typical Workflows" subsection**: "Code Review Workflow" — Describe the scenario where a developer wants to improve code quality in a specific module. Include a concrete example: reviewing the auth module using "Security Review" and "Code Conventions" modes, selecting findings, creating tasks, and optionally starting implementation immediately. Also describe how to create a project-specific review guide.

### Verification
- Verify markdown renders correctly (headings, tables, code blocks)
- Verify TOC links work
- Cross-reference with actual SKILL.md to ensure documentation matches implementation
