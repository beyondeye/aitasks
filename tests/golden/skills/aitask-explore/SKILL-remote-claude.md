---
name: aitask-explore-remote
description: Explore the codebase interactively, then create a task for implementation.
---

## Workflow

> **Runtime context variables** (maintained across steps during this run —
> analogous to the pre-Jinja execution-profile context variables, *not* Jinja
> keys). All default to empty; they are set only if Step 1's **Cross-repo scope
> detection** finds a match:
> - `cross_repo_scope` — registered cross-repo project name the exploration
>   became scoped to (`""` = single-repo). Drives Step 2 and the Step 3 option.
> - `cross_repo_root` — filesystem root of `cross_repo_scope`.
> - `cross_repo_files` — cross-repo file paths resolved from `<name>:<path>`
>   notation, used as high-priority reads in Step 2.
> - `cross_repo_xdeps` — cross-repo dependency task IDs parsed from `<name>#<id>`
>   notation (CSV), pre-filled as `--xdeps` in Step 3.

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

- **Follow-up question** (AskUserQuestion): "How would you like to specify the area?"
  - Header: "Area"
  - Options:
    - "Search for files" (description: "Find files by keywords, names, or functionality using file search")
    - "Describe the area" (description: "Type a module name, directory, or description")
- **If "Search for files":** Read and follow `.claude/skills/user-file-select/SKILL.md` to get specific files, then use those file paths as the focus area for exploration.
- **If "Describe the area":** Ask (AskUserQuestion): "Which module or directory should we focus on?" with Header: "Area" and free text only (use "Other"). This preserves the original behavior.
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

#### Cross-repo scope detection

After the exploration intent and its free-text description are captured (from
the follow-up question above, or the top-level "Other" text), check whether the
exploration is scoped to a registered cross-repo project. **Do NOT run this
before the first `AskUserQuestion` above** — that prompt must fire with no I/O
latency; this detection runs only once the user's description is in hand.

1. Read the resolved project registry:
   ```bash
   ./.aitask-scripts/aitask_project_resolve.sh list
   ```
   Collect `<name>` from each `PROJECT:<name>:<path>:RESOLVED` line whose
   `<path>` is **not** the current repo root. Skip `STALE` entries.
2. Scan the user's free-text description for any of: a resolved `<name>`
   mention, `<name>#<id>` notation, or `<name>:<relative/path>` notation
   (documented in `aidocs/framework/cross_repo_references.md`).
3. **On a match**, set the runtime context variables:
   - `cross_repo_scope = <name>`.
   - Resolve its root: `./.aitask-scripts/aitask_project_resolve.sh <name>` →
     `RESOLVED:<root>`; set `cross_repo_root = <root>`.
   - For each `<name>:<relative/path>`, append `<root>/<relative/path>` to
     `cross_repo_files`.
   - For each `<name>#<id>`, append `<id>` to `cross_repo_xdeps`; optionally
     resolve its title for a richer exploration question:
     `./.aitask-scripts/aitask_query_files.sh --project <name> task-file <id>`.
4. **No match** → leave all four variables empty and continue as a normal
   single-repo exploration.

### Step 2: Iterative Exploration

Explore the codebase guided by the exploration strategy set in Step 1. Use Read, Glob, Grep, and Task (Explore agents) as needed.

**Exploration loop:**

1. Perform an exploration round based on the strategy and user's focus area.
   **If `cross_repo_scope` is set,** make this a cross-repo round: in addition to
   exploring the local repo, spawn an `Explore` subagent rooted in
   `cross_repo_root` and include any `cross_repo_files` as high-priority reads,
   so findings span both repos
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

Before checking for overlapping tasks, do a best-effort sync so the scan and the subsequent task ID assignment see the current remote state:

```bash
./.aitask-scripts/aitask_pick_own.sh --sync
```

This is non-blocking — if it fails (e.g., no network, merge conflicts), it continues silently.

Then check for existing pending tasks that overlap.

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** The exploration findings gathered in Step 2
- **Purpose text:** "will be fully covered by the new task (they will be folded in and deleted after implementation)"
- **Min eligible:** 1
- **Selection mode:** ai_filtered

If the procedure returns task IDs, store them as `folded_tasks` for Step 3. Read the full description of each selected task — their content will be incorporated into the new task description in Step 3.

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
  - **Include this option ONLY when `cross_repo_scope` is non-empty:** "Create as cross-repo paired task" (description: "Exploration is scoped to `<cross_repo_scope>`; sets `xdeprepo` so planning designs a paired decomposition spanning both repos")

**If "Modify before creating":**
- Ask the user what to change via `AskUserQuestion` or free text
- Apply their modifications

**If "Create as cross-repo paired task":**
- Confirm the cross-repo dependency task IDs: default to `cross_repo_xdeps` (if
  any were detected); allow the user to edit or clear them via free text
  ("Other"). Store the result as `<xdeps>` (may be empty — `xdeprepo` alone is
  the valid intent-only form per `validate_xdeps_pair`).
- Set `<xdeprepo> = cross_repo_scope`, then create the task with the cross-repo
  flags (see "Create the task" below). Apply any other metadata changes the user
  also requested, as in "Modify before creating".

**If folded_tasks is non-empty:** Build the merged description using `aitask_fold_content.sh` with `--primary-stdin` (the primary task does not exist yet):

```bash
merged_desc=$(printf '%s\n' "<primary description from exploration>" | \
  ./.aitask-scripts/aitask_fold_content.sh --primary-stdin <folded_file1> <folded_file2> ...)
```

Use `$merged_desc` as the `description` argument for the Batch Task Creation Procedure below.

**Create the task:**

Execute the **Batch Task Creation Procedure** (see `.claude/skills/task-workflow/task-creation-batch.md`) with:
- mode: `parent`
- name: `"<name>"`
- priority: `<p>`
- effort: `<e>`
- issue_type: `<issue_type>`
- labels: `"<l>"`
- description: task description (or merged description if folded_tasks is non-empty)

**Cross-repo flags:** When the "Create as cross-repo paired task" option was
chosen, append to the `aitask_create.sh --batch` invocation:
`--xdeprepo "<xdeprepo>"`, and — only when `<xdeps>` is non-empty —
`--xdeps "<xdeps>"`. Pass `--xdeps` only together with `--xdeprepo` (the
validator enforces both-or-neither; `--xdeprepo` alone is the intent-only form).
The created task then carries `xdeprepo` in its frontmatter.

**No dispatch needed here.** When Step 5 hands off to
`.claude/skills/task-workflow/SKILL.md`, the existing cross-repo wiring fires on
the `xdeprepo` trigger: `planning.md` §6.1 runs the Cross-Repo Planning
Procedure (design) and Step 7 runs the Cross-Repo Child Assignment Procedure
(creation, after approval). This skill dispatches neither procedure itself.

Read back the created task file to confirm the assigned task ID:
```bash
./ait git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

**If folded_tasks is non-empty**, mark the folded tasks using `aitask_fold_mark.sh` with `--commit-mode amend` so the marking folds into the task-creation commit:

```bash
./.aitask-scripts/aitask_fold_mark.sh --commit-mode amend <new_task_num> <folded_id1> <folded_id2> ...
```

The script automatically handles transitive folds and removes folded child tasks from their parent's `children_to_implement`.

### Step 4: Decision Point


Use `AskUserQuestion`:
- Question: "Task created successfully. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Continue to implementation" (description: "Start implementing the task now via the standard workflow")
  - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

**If "Save for later":**
- Inform user: "Task t\<N\>_\<name\>.md is ready. Run `/aitask-pick <N>` when you want to implement it."
- Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name` = `"explore"`.
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
- **active_profile**: `{ name: remote }` (baked in at render time)
- **active_profile_filename**: `remote.yaml`
- **previous_status**: `Ready`
- **folded_tasks**: List of task IDs folded into this task (e.g., `[106, 129]`), or empty list if none
- **skill_name**: `"explore"`

---

## Notes

- This skill creates standalone (parent-level) tasks only, not children
- No files are written during the exploration phase — findings are tracked mentally until task creation
- The `explore_auto_continue` profile key controls whether to ask the user about continuing to implementation (default: `false`, always ask)
- When handing off to task-workflow, the created task has status `Ready` — task-workflow's Step 4 will set it to `Implementing`
- For the full Execution Profiles schema and customization guide, see `.claude/skills/task-workflow/SKILL.md`
- **Folded tasks:** When existing pending tasks are folded into a new task (Step 2b), their full content is incorporated using the **Task Fold Content Procedure** (structured `## Merged from t<N>` headers) and marked using the **Task Fold Marking Procedure** (both in `.claude/skills/task-workflow/`). The original folded task files are set to status `Folded` with a `folded_into` property pointing to the new task. They exist only as references for deletion after the new task is completed (handled by task-workflow Step 9). The `folded_tasks` frontmatter field tracks which task IDs to clean up.
- Only standalone parent-level tasks without children can be folded in. Child tasks and parents-with-children are excluded from the related task scan.
