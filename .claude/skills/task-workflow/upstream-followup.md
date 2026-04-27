# Upstream Defect Follow-up Procedure

Runs from task-workflow **Step 8b**, after the "Commit changes" branch has committed code and plan files. Offers the user a chance to spawn a standalone aitask for an upstream defect surfaced during diagnosis — when the failure was *seeded* by a separate, pre-existing bug elsewhere (a different script, helper, or module).

## Input context

From the caller (SKILL.md Step 8b):
- `task_file` — path to the current task file.
- `task_id` — task identifier (e.g. `42` or `42_3`).
- `task_slug` — filename stem without the `t<id>_` prefix (e.g. `add_login`).
- `is_child` — boolean.
- `active_profile` — loaded execution profile (may be null).
- `parent_id` — parent task number if `is_child`, else null.

## Procedure

### 1. Resolve the plan file and read the "Upstream defects identified" subsection

Resolve the plan file:

```bash
./.aitask-scripts/aitask_query_files.sh plan-file <task_id>
```

Parse the output: `PLAN_FILE:<path>` means found, `NOT_FOUND` means the plan file does not exist. If `NOT_FOUND`, return to the caller (proceed to Step 8c) — there is nothing to read.

Read `<path>` and locate the bullet `- **Upstream defects identified:**` inside the `## Final Implementation Notes` section. The subsection is the plan-file source of truth: Step 8 plan consolidation writes either `None` (verbatim) or a list of defect bullets of the form `path/to/file.ext:LINE — short summary`.

- **If the subsection is missing, empty, or contains exactly `None`** (case insensitive, whitespace tolerant): no upstream defect identified. Return to the caller (proceed to Step 8c).

- **Otherwise:** parse the defect bullets into a list. Each bullet's location prefix and summary become the input for the offer in step 2.

### 2. User offer

Use `AskUserQuestion`:
- Question: "Diagnosis surfaced an upstream defect: \<first defect bullet verbatim\>. Create a follow-up aitask for it?"
  - If there is more than one bullet, append "(+\<N-1\> more — all will be folded into the new task body)".
- Header: "Upstream"
- Options:
  - "Yes, create follow-up task" (description: "Spawn a new bug aitask documenting the upstream defect, with the diagnostic context from this task")
  - "No, skip" (description: "Note in the plan file only; no separate task")

**If "No, skip":** Return to the caller. The defect remains documented in this task's plan file, which will be archived for future reference.

### 3. Seed the follow-up task

On "Yes, create follow-up task", execute the **Batch Task Creation Procedure** (see `task-creation-batch.md`) with:

- `mode`: `parent`.
- `name`: short snake_case derived from the first defect summary (e.g. `fix_brainstorm_delete_prune_ordering`).
- `description` (multi-line, passed via `--desc-file -` heredoc):

  ```markdown
  ## Origin

  Spawned from t<task_id> during Step 8b review.

  ## Upstream defect

  <verbatim copy of all bullets from the plan file's "Upstream defects identified" subsection — preserves location and summary>

  ## Diagnostic context

  <relevant excerpt from the plan file's Final Implementation Notes showing the chain of reasoning that surfaced the defect — typically the "Issues encountered" + "Deviations from plan" entries>

  ## Suggested fix

  <one or two lines on the likely fix direction; omit this section if not known>
  ```

- `priority`: `medium` (default; bump to `high` only if the defect is actively breaking other flows).
- `effort`: `low` unless the diagnostic context suggests otherwise.
- `issue_type`: `bug`.
- `labels`: copy any topical labels from the current task. The user can adjust later.

After the helper prints `Created: <filepath>`, display:

> "Created follow-up upstream task: \<filepath\>"

Return to the caller (proceed to Step 8c).

## Canonical illustration (t660)

The brainstorm TUI silently quit on plan import. Diagnosis revealed a stale `crew-brainstorm-<N>` git branch left over by a worktree-prune ordering bug in `aitask_brainstorm_delete.sh:109-111`. The plan only added a recovery modal for the symptom; the upstream `delete` bug needed its own task. The user had to manually push for the follow-up — this procedure removes that friction.
