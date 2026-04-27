---
Task: t667_task_workflow_step8_upstream_followup_offer.md
Worktree: (current branch — profile fast)
Branch: main
Base branch: main
---

# Plan: Step 8 upstream-defect follow-up offer (t667)

## Context

When implementation reveals that the failure was *seeded* by an upstream
defect (a different script/module that should have prevented the state we
hit), the agent currently buries it in plan-file prose at most. On t660 this
caused the user to manually push for both (a) a recovery affordance and (b)
acknowledgment of the upstream `aitask_brainstorm_delete.sh:109-111`
worktree-prune ordering bug. The user rated the skill 1-2 (Poor) because
the follow-up offer had to be extracted by hand.

This task encodes the rule into the task-workflow as an explicit,
non-skippable peer step right before Step 8c (manual verification
follow-up). It is structural (a numbered step in SKILL.md, with the
procedure body in its own file) per CLAUDE.md "Skill / Workflow Authoring
Conventions": guard variables alone cannot enforce a fire-once obligation;
only a numbered step the agent cannot skip can.

**Storage choice — plan file is the source of truth.** The upstream defect
description and location live in a new "Upstream defects identified"
subsection of the plan file's Final Implementation Notes. Step 8b's
procedure file reads from that subsection. Benefits:
- No new context variables (lower drift risk).
- Persists across context resumes and is human-auditable in the archived
  plan.
- Even if the user skips the follow-up offer, the defect stays documented.

**Procedure-file split — mirror Step 8c (`manual-verification-followup.md`).**
Per user direction: do not inline the offer body in SKILL.md. Create
`.claude/skills/task-workflow/upstream-followup.md`; SKILL.md's Step 8b
becomes a short dispatcher that points at it.

## Files to modify / create

- **Create** `.claude/skills/task-workflow/upstream-followup.md` — new
  procedure file (mirrors `manual-verification-followup.md` shape).
- **Modify** `.claude/skills/task-workflow/SKILL.md` — add Step 8b
  dispatcher, update Step 8c opener, add procedure-list entry, tweak the
  Final Implementation Notes template.

No helper-script changes. No other agents' files (cross-agent parity is a
follow-up; see Notes).

## Changes

### A. New file: `.claude/skills/task-workflow/upstream-followup.md`

Mirror the structure of `manual-verification-followup.md`. Contents:

```markdown
# Upstream Defect Follow-up Procedure

Runs from task-workflow **Step 8b**, after the "Commit changes" branch has
committed code and plan files. Offers the user a chance to spawn a
standalone aitask for an upstream defect surfaced during diagnosis — when
the failure was *seeded* by a separate, pre-existing bug elsewhere
(different script, helper, or module).

## Input context

From the caller (SKILL.md Step 8b):
- `task_file` — path to the current task file.
- `task_id` — task identifier (e.g. `42` or `42_3`).
- `task_slug` — filename stem without the `t<id>_` prefix (e.g.
  `add_login`).
- `active_profile` — loaded execution profile (may be null).
- `parent_id` — parent task number if `is_child`, else null.

## Procedure

### 1. Resolve the plan file and read the "Upstream defects identified" subsection

Resolve the plan file:

```bash
./.aitask-scripts/aitask_query_files.sh plan-file <task_id>
```

Parse `PLAN_FILE:<path>` (or `NOT_FOUND`). If `NOT_FOUND`, return to the
caller — there is nothing to read.

Read `<path>` and extract the lines under the bullet
`- **Upstream defects identified:**` inside the `## Final Implementation
Notes` section. The subsection is plan-file source-of-truth: Step 8 plan
consolidation writes either `None` (verbatim) or a list of defect bullets
of the form `path/to/file.ext:LINE — short summary`.

- **If the subsection is missing, empty, or contains exactly `None`** (case
  insensitive, whitespace tolerant): no upstream defect identified. Return
  to the caller (proceed to Step 8c).

- **Otherwise:** parse the defect bullets into a list. Each bullet's
  location-prefix and summary become the input for the offer below.

### 2. User offer

Use `AskUserQuestion`:
- Question: "Diagnosis surfaced an upstream defect: \<first defect bullet
  verbatim\>. Create a follow-up aitask for it?" — if there is more than
  one bullet, append "(+\<N-1\> more — all will be folded into the new
  task body)".
- Header: "Upstream"
- Options:
  - "Yes, create follow-up task" (description: "Spawn a new bug aitask
    documenting the upstream defect, with the diagnostic context from this
    task")
  - "No, skip" (description: "Note in the plan file only; no separate
    task")

**If "No, skip":** Return to the caller. The defect remains documented in
this task's plan file, which will be archived for future reference.

### 3. Seed the follow-up task

On "Yes, create follow-up task", execute the **Batch Task Creation
Procedure** (see `task-creation-batch.md`) with:

- `mode`: `parent`.
- `name`: short snake_case derived from the first defect summary (e.g.,
  `fix_brainstorm_delete_prune_ordering`).
- `description` (multi-line, passed via `--desc-file -` heredoc):

  ```markdown
  ## Origin

  Spawned from t<task_id> during Step 8b review.

  ## Upstream defect

  <verbatim copy of all bullets from the plan file's "Upstream defects
  identified" subsection — preserves location and summary>

  ## Diagnostic context

  <relevant excerpt from the plan file's Final Implementation Notes
  showing the chain of reasoning that surfaced the defect — typically
  the "Issues encountered" + "Deviations from plan" entries>

  ## Suggested fix

  <one or two lines on the likely fix direction; omit this section if not
  known>
  ```

- `priority`: `medium` (default; bump to `high` only if the defect is
  actively breaking other flows).
- `effort`: `low` unless the diagnostic context suggests otherwise.
- `issue_type`: `bug`.
- `labels`: copy any topical labels from the current task. The user can
  adjust later.

After the helper prints `Created: <filepath>`, display:

> "Created follow-up upstream task: \<filepath\>"

Return to the caller (proceed to Step 8c).

## Canonical illustration (t660)

The brainstorm TUI silently quit on plan import. Diagnosis revealed a
stale `crew-brainstorm-<N>` git branch left over by a worktree-prune
ordering bug in `aitask_brainstorm_delete.sh:109-111`. The plan only added
a recovery modal for the symptom; the upstream `delete` bug needed its
own task. The user had to manually push for the follow-up — this
procedure removes that friction.
```

### B. SKILL.md edits

#### B1. "Consolidate the plan file" template (~lines 308-314)

Existing Final Implementation Notes template ends with the
"Notes for sibling tasks" bullet. Insert a new bullet between
"Key decisions" and "Notes for sibling tasks":

```markdown
- **Upstream defects identified:** Did diagnosis surface an upstream defect
  — a separate, pre-existing bug in a different script/helper/module whose
  behavior *seeded* the symptom this task fixed? List each as a bullet of
  the form `path/to/file.ext:LINE — short summary` (e.g. `aitask_brainstorm_delete.sh:109-111
  — worktree-prune ordering bug leaves stale crew-brainstorm-<N> branch`).
  Write `None` (verbatim) if no upstream defect was identified — this is
  read by Step 8b. Do not list style/lint cleanups, refactor opportunities,
  test gaps (those go through `/aitask-qa`), or unrelated TODOs.
```

The "None"-vs-list distinction is what `upstream-followup.md` parses.
Writing `None` verbatim is a positive assertion that the agent reflected
and found nothing — distinct from accidentally omitting the subsection.

#### B2. Step 8 "Commit changes" branch — change "Proceed to Step 8c" to "Proceed to Step 8b"

Tiny edit (~line 344).

#### B3. Insert new Step 8b dispatcher between Step 8 and Step 8c

```markdown
### Step 8b: Upstream Defect Follow-up

Entered from Step 8 after the "Commit changes" branch has committed code
and plan files. Offers the user a chance to spawn a standalone aitask for
an upstream defect surfaced during diagnosis (when the failure was
*seeded* by a separate, pre-existing bug elsewhere).

Execute the **Upstream Defect Follow-up Procedure** (see
`upstream-followup.md`) with:
- `task_file`, `task_id`, `is_child`, `active_profile`, `parent_id` from
  the current context.
- `task_slug` — filename stem with the `t<id>_` prefix stripped
  (e.g. `aitasks/t42_add_login.md` → `add_login`).

When the procedure returns, proceed to Step 8c.
```

This mirrors the existing Step 8c dispatcher exactly.

#### B4. Step 8c opener — acknowledge the new predecessor (~lines 366-374)

Replace the current opener:

> Entered from Step 8 after the "Commit changes" branch has committed code
> and plan files. …

with:

> Entered from Step 8b (or directly from Step 8 if 8b was a no-op). At
> this point code and plan files have already been committed. …

(Keep the rest of Step 8c unchanged.)

#### B5. Procedures list (~lines 516-533)

Add a new entry alongside the manual-verification-followup line:

```markdown
- **Upstream Defect Follow-up Procedure** (`upstream-followup.md`) — Post-implementation prompt offering to create a standalone bug aitask for an upstream defect surfaced during diagnosis. Reads the plan file's "Upstream defects identified" subsection. Referenced from Step 8b.
```

## Why a numbered structural peer step (not a profile key, not buried inside Step 8)

Per `CLAUDE.md` "Skill / Workflow Authoring Conventions":

> Guard variables … do NOT force a single execution, so they can't be used
> to "remind agents to fire a prompt." Rule of thumb: if the concern is
> "agents might forget to fire X", restructure control flow … and make it
> a numbered step.

Step 8b is a top-level numbered peer of Step 8c. The procedure body lives
in its own file, mirroring the manual-verification-followup pattern. The
plan-file subsection is the persistent source of truth — no context
variables, no in-memory state to lose.

## Verification

After the edits:

1. `git diff .claude/skills/task-workflow/SKILL.md` shows:
   - A new "Upstream defects identified" bullet inside the Final
     Implementation Notes template in Step 8's "Commit changes" branch.
   - "Proceed to Step 8c" replaced with "Proceed to Step 8b" at the end of
     Step 8's "Commit changes" branch.
   - A new `### Step 8b: Upstream Defect Follow-up` dispatcher section
     between Step 8 and Step 8c.
   - Updated Step 8c opener acknowledging Step 8b as the predecessor.
   - A new entry in the Procedures list referencing
     `upstream-followup.md`.

2. `git status` shows the new file
   `.claude/skills/task-workflow/upstream-followup.md` (untracked).

3. `cat .claude/skills/task-workflow/upstream-followup.md` shows the t660
   canonical example, the plan-file read step, the AskUserQuestion, and
   the Batch Task Creation invocation.

4. Manual reading: the Step 8 → 8b → 8c → 9 flow scans cleanly. Step 8b is
   a no-op (procedure returns immediately) when the plan file's subsection
   is `None` or absent.

## Step 9 (Post-Implementation) reminders

After this task is committed and reviewed, archival proceeds via
`./.aitask-scripts/aitask_archive.sh 667`. No worktree to clean up
(profile `fast` chose current branch). No `verify_build` is configured for
this project.

## Notes / cross-agent parity follow-up

The task description's "Cross-agent parity follow-up" section names paths
that **do not exist** in this repository:

- `.opencode/skills/task-workflow/SKILL.md` — does not exist; opencode
  pick skills do not share a task-workflow file.
- `.gemini/skills/task-workflow/SKILL.md` — does not exist.
- `.agents/skills/task-workflow/SKILL.md` — does not exist.

The other agents' aitask-pick variants (`.opencode/skills/aitask-pick/SKILL.md`,
`.gemini/commands/aitask-pick.toml`, `.agents/skills/aitask-pick/`) inline
their own workflow steps. Cross-agent follow-up tasks should target those
concrete files instead. Surface this at Step 8b/8c so the user can accept
or reject creating cross-agent follow-up tasks.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Created
  `.claude/skills/task-workflow/upstream-followup.md` (new procedure file
  mirroring `manual-verification-followup.md`) and made four edits to
  `.claude/skills/task-workflow/SKILL.md`: added the "Upstream defects
  identified" bullet to the Final Implementation Notes template; changed
  "Proceed to Step 8c" → "Proceed to Step 8b"; inserted a new Step 8b
  dispatcher between Step 8 and Step 8c; updated the Step 8c opener to
  acknowledge Step 8b as the predecessor; added an entry for the new
  procedure to the Procedures list.
- **Deviations from plan:** None. The user gave two design corrections
  during plan mode (file-as-source-of-truth instead of context variables;
  extract procedure to its own file) and both were folded into the
  approved plan before implementation began.
- **Issues encountered:** None during implementation.
- **Key decisions:**
  - Plan file (the "Upstream defects identified" subsection) is the
    persistent source of truth — no new context variables.
  - Procedure body extracted to `upstream-followup.md`; SKILL.md's Step
    8b is a short dispatcher that mirrors Step 8c's shape exactly.
  - The `None`-vs-list distinction in the subsection is the parser's
    signal: writing `None` verbatim is a positive assertion that the
    agent reflected and found nothing.
- **Upstream defects identified:** None.

