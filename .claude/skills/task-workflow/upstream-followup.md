# Upstream Defect Follow-up Procedure

Runs from task-workflow **Step 8b**, after the "Commit changes" branch has committed code and plan files. Offers the user a chance to spawn a standalone aitask for an upstream defect surfaced during diagnosis — a separate, pre-existing bug in a different script/helper/module, whether or not it caused the current symptom.

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

- **Fast path — canonical bullet has defect entries:** parse the bullets into a list. Each bullet's location prefix and summary become the input for the offer in step 2. Skip the sanity-check below.

- **Sanity-check path — canonical bullet is missing, empty, or contains exactly `None`** (case insensitive, whitespace tolerant): the bullet may be misclassified (a related defect was dismissed because it didn't *cause* the current symptom) or mis-located (a related defect was documented in a side bullet, free prose, or an "Out of scope" section instead of the canonical bullet — see the t687 illustration at the bottom of this file). Re-read the plan file end-to-end and answer this question explicitly:

  > "Did diagnosis surface any pre-existing defect in another script, helper, or module — whether or not it caused the current symptom — that should become its own follow-up task? Look in every section of the plan body, including 'Out of scope', 'Issues encountered', 'Deviations from plan', side bullets, and free prose. Ignore style/lint cleanups, refactor opportunities, test gaps, and unrelated TODOs (the same exclusions the canonical bullet uses)."

  If the answer is **no**: return to the caller (proceed to Step 8c).

  If the answer is **yes**: synthesize one bullet per defect in the canonical format `path/to/file.ext:LINE — short summary`, falling back to `path/to/file.ext — short summary` (no line number) if the plan body doesn't pin one down. Use these synthesized bullets as the input for the offer in step 2. **Do not modify the plan file** — the re-read is a runtime sanity check, not a write-back. The next time Step 8 plan consolidation runs (in a future task), the contract language in `SKILL.md` will steer the agent to write the bullet canonically from the start.

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

## Canonical illustration (t687) — sanity-check path

Setup wrote `None` to the canonical bullet and recorded a related trailing-slash defect (`aitasks/` / `aiplans/` symlinks not matched by trailing-slash `.gitignore` entries) under a side bullet `- **Trailing-slash follow-up:**`. The fast path saw `None` and would have short-circuited, silently burying the defect in the archived plan. The sanity-check path inspects the plan body, finds the side-bullet defect, and surfaces it as a normal follow-up offer. The plan file is left untouched — only the runtime offer is affected.
