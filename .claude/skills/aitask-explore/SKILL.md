---
name: aitask-explore
description: Explore the codebase interactively, then create a task for implementation.
---

## Workflow

### Step 0a: Select Execution Profile

Check for available execution profiles:

```bash
ls aitasks/metadata/profiles/*.yaml 2>/dev/null
```

**If no profiles found:** Skip this step (no profile active, all questions asked normally).

**If exactly one profile found:** Auto-load it and inform user: "Using execution profile: \<name\> (\<description\>)".

**If multiple profiles found:**

Read each profile's `name` and `description` fields. Use `AskUserQuestion`:
- Question: "Select an execution profile (pre-configured answers to reduce prompts):"
- Header: "Profile"
- Options:
  - Each profile: label = `name` field, description = `description` field
  - "No profile" (description: "Ask all questions interactively")

**If "No profile" selected:** Proceed with all questions asked normally (no active profile).

Store the selected profile in memory for use throughout remaining steps.

**Error handling:** If a profile file has invalid YAML, warn the user ("Profile '\<filename\>' has invalid format, skipping") and exclude it from the selection list.

### Step 0c: Sync with Remote (Best-effort)

Do a best-effort pull to ensure the local state is up to date:

```bash
git pull --ff-only --quiet 2>/dev/null || true
```

This is non-blocking — if it fails (e.g., no network, merge conflicts), continue silently.

Also run best-effort stale lock cleanup:

```bash
./aiscripts/aitask_lock.sh --cleanup 2>/dev/null || true
```

### Step 1: Exploration Setup

Use `AskUserQuestion` to determine the exploration intent:
- Question: "What would you like to explore?"
- Header: "Explore"
- Options:
  - "Investigate a problem" (description: "Debug an issue, trace a symptom, find a root cause")
  - "Explore codebase area" (description: "Understand a module, map its structure and dependencies")
  - "Scope an idea" (description: "Have an idea to implement but need to discover what code is affected")
  - "Explore documentation" (description: "Find documentation gaps, outdated docs, or missing help text")

The user can also provide free text via the "Other" option.

**Based on the selected option, set the exploration context:**

#### Option: Investigate a problem

- **Follow-up question** (AskUserQuestion): "Describe the symptom and where you notice it"
  - Header: "Problem"
  - Options: free text only (use "Other")
- **Exploration strategy:** Trace data flow through the affected area, check error handling paths, examine logs and exception patterns, identify root cause candidates.
- **Task defaults:** `issue_type: bug`, `priority: high`

#### Option: Explore codebase area

- **Follow-up question** (AskUserQuestion): "Which module or directory should we focus on?"
  - Header: "Area"
  - Options: free text only (use "Other")
- **Exploration strategy:** Map file structure and key classes in the area, trace dependencies (what it imports, what depends on it), identify architectural patterns and conventions used.
- **Task defaults:** `issue_type: feature`, `priority: medium`

#### Option: Scope an idea

- **Follow-up question** (AskUserQuestion): "Describe the idea briefly"
  - Header: "Idea"
  - Options: free text only (use "Other")
- **Exploration strategy:** Find all code touchpoints that would need changes to implement the idea, estimate the blast radius (how many files/modules are affected), identify potential conflicts with existing patterns.
- **Task defaults:** `issue_type: feature`, `priority: medium`

#### Option: Explore documentation

- **Follow-up question** (AskUserQuestion): "What documentation area should we focus on?"
  - Header: "Docs"
  - Options:
    - "Project docs" (description: "README, guides, and standalone documentation files")
    - "Code docs" (description: "Help text, comments, and inline documentation in scripts/code")
    - "Both" (description: "Check all documentation across the project")
- **Exploration strategy:** Find documentation files (README, docs/, *.md), check help text and usage strings in scripts, review code comments for accuracy, identify gaps where documentation is missing or outdated.
- **Task defaults:** `issue_type: documentation`, `priority: medium`

#### Option: Other (free text)

- No additional follow-up question needed (user already described their intent)
- **Exploration strategy:** General-purpose exploration based on the user's description.
- **Task defaults:** `issue_type: feature`, `priority: medium`

### Step 2: Iterative Exploration

Explore the codebase guided by the exploration strategy set in Step 1. Use Read, Glob, Grep, and Task (Explore agents) as needed.

**Exploration loop:**

1. Perform an exploration round based on the strategy and user's focus area
2. Present a brief summary of findings so far to the user
3. Use `AskUserQuestion`:
   - Question: "How would you like to proceed?"
   - Header: "Next step"
   - Options:
     - "Continue exploring" (description: "Keep investigating, you can redirect the focus")
     - "Create a task" (description: "I have enough information, let's create a task from these findings")
     - "Abort" (description: "Stop exploration without creating a task")

4. Handle selection:
   - **"Continue exploring":** Ask the user if they want to redirect focus or continue in the same direction. Loop back to step 1 of this exploration loop.
   - **"Create a task":** Proceed to Step 2b (Related Task Discovery).
   - **"Abort":** Inform user "Exploration ended. No task created." and stop the workflow.

**Notes:**
- Track findings mentally throughout (no file writes during exploration)
- Each exploration round should be meaningful — don't just do one file read, do enough to have something useful to report
- Present findings as a concise bulleted summary after each round

### Step 2b: Related Task Discovery

Before creating a new task, check for existing pending tasks that overlap with the exploration findings. This prevents duplicate tasks and ensures related work is tracked.

**List pending tasks:**

```bash
./aiscripts/aitask_ls.sh -v --status all --all-levels 99 2>/dev/null
```

Filter the output to include only tasks with status `Ready` or `Editing`. Exclude:
- Tasks with children (status shows "Has children") — too complex to fold in
- Child tasks — too complex to fold in
- Tasks with status `Implementing`, `Postponed`, or `Done`

**Assess relevance:** Read the title and brief description (first ~5 lines of body text) of each remaining task. Based on the exploration findings gathered in Step 2, identify tasks whose scope overlaps significantly with the planned new task. A task is "related" if the new task would cover the same goal, fix the same problem, or implement the same feature.

**If no related tasks are found:** Inform the user: "No existing pending tasks appear related to this exploration." Proceed directly to Step 3.

**If related tasks are found:** Present them to the user using `AskUserQuestion` with multiSelect:
- Question: "These existing tasks appear related to your exploration findings. Select any that will be fully covered by the new task (they will be folded in and deleted after implementation):"
- Header: "Related tasks"
- Options: Each related task as a selectable option, with the task filename as label and a brief reason for the match as description. Include a "None — no tasks to fold in" option.

**If user selects "None" or no tasks:** Proceed to Step 3 with no folded tasks.

**If user selects one or more tasks:** Store the list of selected task IDs (e.g., `[106, 129_5]`) as the **folded_tasks** list. Read the full description of each selected task — their content will be incorporated into the new task description in Step 3. Proceed to Step 3.

**Scope rule:** Only standalone parent-level tasks without children may be folded in.

### Step 3: Task Creation

Summarize all exploration findings for the user in a structured format:

```
## Exploration Summary
- **Focus:** <what was explored>
- **Key findings:**
  - <finding 1>
  - <finding 2>
  - ...
- **Suggested task:** <proposed task title>
```

**Propose task metadata** using defaults from the Step 1 table:

Use `AskUserQuestion` to confirm or modify:
- Question: "Here's the proposed task. Confirm or select 'Other' to modify:"
- Header: "Task"
- Options:
  - "Create task as proposed" (description: "<task_name> [priority: <p>, effort: <e>, type: <t>]")
  - "Modify before creating" (description: "Change the title, priority, effort, labels, or description")

**If "Modify before creating":**
- Ask the user what to change via `AskUserQuestion` or free text
- Apply their modifications

**If folded_tasks is non-empty:** Incorporate the full content of each folded task into the new task description. Read each folded task file and merge their requirements, details, and context into the task description. The new task description must be self-contained — it must contain all relevant information from the folded tasks so that at implementation time, the original folded task files never need to be read. Append a reference section at the end:

```markdown
## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t<N>** (`<filename>`)
- ...
```

**Create the task:**

```bash
./aiscripts/aitask_create.sh --batch --commit --name "<name>" --desc-file - --priority <p> --effort <e> --type <issue_type> --labels <l> <<'TASK_DESC'
<task description based on exploration findings, with folded task content incorporated>
TASK_DESC
```

- Read back the created task file to confirm the assigned task ID:
  ```bash
  git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
  ```

**If folded_tasks is non-empty**, set the `folded_tasks` frontmatter field:
```bash
# Set folded_tasks via aitask_update.sh (no --commit, we'll amend)
./aiscripts/aitask_update.sh --batch <task_num> --folded-tasks "<comma-separated IDs>"

# Amend the create commit to include the frontmatter update
git add aitasks/t<task_num>_*.md
git commit --amend --no-edit
```

### Step 4: Decision Point

**Profile check:** If the active profile has `explore_auto_continue` set to `true`:
- Display: "Profile '\<name\>': continuing to implementation"
- Skip the AskUserQuestion below and proceed directly to the handoff

**Default when `explore_auto_continue` is not defined:** `false` (always ask the user).

Otherwise, use `AskUserQuestion`:
- Question: "Task created successfully. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Continue to implementation" (description: "Start implementing the task now via the standard workflow")
  - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

**If "Save for later":**
- Inform user: "Task t\<N\>_\<name\>.md is ready. Run `/aitask-pick <N>` when you want to implement it."
- End the workflow.

**If "Continue to implementation":**
- Proceed to the handoff below.

### Step 5: Hand Off to Shared Workflow

Set the following context variables from the created task, then read and follow `.claude/skills/task-workflow/SKILL.md` starting from **Step 3: Task Status Checks**:

- **task_file**: Path to the created task file (e.g., `aitasks/t42_fix_login_timeout.md`)
- **task_id**: The task number (e.g., `42`)
- **task_name**: The filename stem (e.g., `t42_fix_login_timeout`)
- **is_child**: `false` (explore creates standalone tasks)
- **parent_id**: null
- **parent_task_file**: null
- **active_profile**: The execution profile loaded in Step 0a (or null if no profile)
- **previous_status**: `Ready`
- **folded_tasks**: List of task IDs folded into this task (e.g., `[106, 129_5]`), or empty list if none

---

## Notes

- This skill creates standalone (parent-level) tasks only, not children
- No files are written during the exploration phase — findings are tracked mentally until task creation
- The `explore_auto_continue` profile key controls whether to ask the user about continuing to implementation (default: `false`, always ask)
- When handing off to task-workflow, the created task has status `Ready` — task-workflow's Step 4 will set it to `Implementing`
- For the full Execution Profiles schema and customization guide, see `.claude/skills/task-workflow/SKILL.md`
- **Folded tasks:** When existing pending tasks are folded into a new task (Step 2b), their full content is incorporated into the new task description at creation time. The original folded task files are never read at implementation time — they exist only as references for deletion after the new task is completed (handled by task-workflow Step 9). The `folded_tasks` frontmatter field tracks which task IDs to clean up.
- Only standalone parent-level tasks without children can be folded in. Child tasks and parents-with-children are excluded from the related task scan.
