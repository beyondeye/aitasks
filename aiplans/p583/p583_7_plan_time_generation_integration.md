---
Task: t583_7_plan_time_generation_integration.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_8_documentation_website_and_skill.md, aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md
Archived Sibling Plans: aiplans/archived/p583/p583_1_verification_parser_python_helper.md, aiplans/archived/p583/p583_2_verifies_frontmatter_field_three_layer.md, aiplans/archived/p583/p583_3_verification_followup_helper_script.md, aiplans/archived/p583/p583_4_manual_verification_workflow_procedure.md, aiplans/archived/p583/p583_5_archival_gate_and_carryover.md, aiplans/archived/p583/p583_6_issue_type_manual_verification_and_unit_tests.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 17:26
---

# Plan: t583_7 — Plan-time Generation Integration (verified)

## Context

This is the **planning-flow integration** side of t583 (manual-verification
module). It teaches `/aitask-pick` and `/aitask-explore` to proactively offer
to create manual-verification tasks at **plan time** rather than as ad-hoc
afterthoughts:

- **Aggregate-sibling path** (parent task with children): after child tasks
  are created during planning, prompt to add a manual-verification *sibling*
  that covers 2+ children at once (e.g. the t571_7 pattern).
- **Single-task follow-up path**: after a single-task plan is approved,
  prompt to create a standalone manual-verification follow-up that picks up
  after this task archives.
- **Explore path**: when creating a task via `/aitask-explore`, offer the
  same follow-up.

Depends on t583_2 (`verifies:` field plumbing — done) and t583_6
(`manual_verification` issue_type — done). Wraps `aitask_create.sh --batch`
plus `aitask_verification_parse.sh seed` in one helper script.

## Verification Summary (April 2026)

Plan assumptions re-checked against current codebase:

- `aitask_verification_parse.sh seed <file> --items <file>` subcommand: **exists** (from t583_1).
- `aitask_create.sh --batch` supports: `--type manual_verification`, `--priority`, `--effort`, `--labels`, `--name`, `--parent <NUM>`, `--verifies <csv>`, `--desc-file`, `--commit`, `--deps`. **No `--related` flag** — falls back to `--deps` per plan.
- `manual_verification` registered at `aitasks/metadata/task_types.txt:9`.
- `aitask_create.sh --batch --commit` outputs `Created: <filepath>`; task ID extractable from filename.
- `planning.md` child-creation loop ends at line 169; child checkpoint starts line 170 — plan's "~line 170" is still accurate.
- `planning.md` single-task ExitPlanMode at line 184; Checkpoint section begins at line 258.
- `aitask-explore/SKILL.md` create-task phase ends around line 185 before §3b (Execution Profile Selection).
- 5 whitelist touchpoints confirmed (see §4).

## 1. New script: `.aitask-scripts/aitask_create_manual_verification.sh`

Usage:

```
aitask_create_manual_verification.sh \
  --name <task_name> \
  --verifies <csv_of_ids> \
  [--parent <parent_num>] [--related <task_id>] \
  --items <items_file>
```

Behavior:

- Exactly one of `--parent` or `--related` must be set.
  - `--parent <N>`: aggregate-sibling mode — creates a child of parent N.
  - `--related <id>`: follow-up mode — creates a standalone task that
    references the source. Since `aitask_create.sh` lacks `--related`, pass
    `--deps <related_id>` and append `**Related to:** t<related_id>` in the
    description body.
- Builds a `<tmp_desc>` file containing:
  - A preamble: *"This is a manual-verification task. Run it with
    `/aitask-pick` which will dispatch to the manual-verification module.
    Each checklist item must be marked Pass/Fail/Skip/Defer."*
  - A `## Verification Checklist` H2 header (body empty; populated by the
    seed step below).
- Calls:
  ```
  aitask_create.sh --batch \
    --type manual_verification \
    --priority medium --effort medium \
    --labels verification,manual \
    --name <name> \
    [--parent <parent_num> | --deps <related_id>] \
    --verifies <csv> \
    --desc-file <tmp_desc> \
    --commit
  ```
- Parses the `Created: <filepath>` output, extracts `<task_id>` from the
  filename (e.g. `t583_10_manual_verification_...` → `583_10`).
- Runs `aitask_verification_parse.sh seed <new_file> --items <items_file>`
  to populate the checklist section created above.
- Outputs: `MANUAL_VERIFICATION_CREATED:<task_id>:<path>`.

Follows shell conventions from CLAUDE.md: `#!/usr/bin/env bash`, `set -euo
pipefail`, sources `terminal_compat.sh` for `die`/`warn`/`info`.

## 2. `planning.md` edits

### Edit 1 — Aggregate Manual Verification Sibling

**Location:** `.claude/skills/task-workflow/planning.md` — insert between
line 169 (end of child plan commit) and line 170 (child task checkpoint).

Insert a new `### Manual Verification Sibling (post-child-creation)` section:

- `AskUserQuestion` with three options:
  - "No, not needed"
  - "Yes, add aggregate sibling covering all children (Recommended for TUI/UX-heavy work)"
  - "Yes, but let me choose which children it verifies"
- On "let me choose" → multiSelect `AskUserQuestion` with one option per
  child to narrow the `verifies:` list.
- Build `<tmp_checklist>`: for each selected child, read its plan file's
  `## Verification` section bullets if present; otherwise emit a single
  stub `TODO: define verification for t<parent>_<child>`.
- Shell out:
  ```
  ./.aitask-scripts/aitask_create_manual_verification.sh \
    --parent <parent_num> \
    --name manual_verification_<parent_slug> \
    --verifies <selected_child_ids_csv> \
    --items <tmp_checklist>
  ```
- The new sibling becomes the last child of the parent.
- Then continue to the existing child task checkpoint (line 170).

### Edit 2 — Single-task Manual Verification Follow-up

**Location:** `.claude/skills/task-workflow/planning.md` — insert inside
the **Checkpoint** section (line 258+), in the "Start implementation"
branch. Specifically: after the profile check resolves
`post_plan_action = "start_implementation"` or the user selects "Start
implementation", and **before** control returns to Step 7.

Rationale for placement: the manual-verification follow-up should only be
offered once the plan is actually approved and the user is proceeding with
implementation — not between `ExitPlanMode` and the Checkpoint where the
plan may still be revised or aborted.

Insert `### Manual Verification Follow-up (post-approval, single-task path)`:

- Skip the prompt entirely if the current task is a child task
  (`is_child == true`) — aggregate siblings cover child verification.
- `AskUserQuestion`:
  - "No" / "Yes, create follow-up task (picked after this task archives)"
- On "Yes":
  - Extract the plan's `## Verification` bullets into `<tmp_checklist>`;
    else a single `TODO: define verification` stub.
  - Shell out:
    ```
    ./.aitask-scripts/aitask_create_manual_verification.sh \
      --related <this_task_id> \
      --name manual_verification_<this_task_slug>_followup \
      --verifies <this_task_id> \
      --items <tmp_checklist>
    ```
  - Display the `MANUAL_VERIFICATION_CREATED:` line to the user.

## 3. `aitask-explore/SKILL.md` edit

**Location:** `.claude/skills/aitask-explore/SKILL.md` — end of §3 "Task
Creation", after line 184 (folded-task marking), before §3b at line 186.

Add the same follow-up question from Edit 2 (variant):

- `AskUserQuestion`: "No" / "Yes, create manual-verification follow-up".
- On "Yes":
  - Exploration-created tasks have no plan yet, so `<tmp_checklist>` is a
    single `TODO: define verification` stub item. The user fills it in when
    they later pick the follow-up.
  - Shell out to `aitask_create_manual_verification.sh --related
    <new_task_id> --verifies <new_task_id>` with the stub items file.

## 4. Whitelist updates (5 files)

Add an entry for `aitask_create_manual_verification.sh` in each of:

1. `.claude/settings.local.json` — runtime Claude Code, JSON:
   `"Bash(./.aitask-scripts/aitask_create_manual_verification.sh:*)"`
2. `.gemini/policies/aitasks-whitelist.toml` — runtime Gemini CLI, TOML
   `[[rule]]` block with `commandPrefix =
   "./.aitask-scripts/aitask_create_manual_verification.sh"`
3. `seed/claude_settings.local.json` — seed for `ait setup`, same JSON
   format as (1)
4. `seed/geminicli_policies/aitasks-whitelist.toml` — seed for Gemini,
   same TOML format as (2)
5. `seed/opencode_config.seed.json` — seed for OpenCode, JSON:
   `"./.aitask-scripts/aitask_create_manual_verification.sh *": "allow"`

Codex: skip (no per-script allowlist, only forbidden/prompt rules for
dangerous commands).

No runtime OpenCode whitelist exists in the repo — the seed is sufficient.

## 5. Key Files

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_create_manual_verification.sh` | New |
| `.claude/skills/task-workflow/planning.md` | Edit 1 + Edit 2 |
| `.claude/skills/aitask-explore/SKILL.md` | Explore path prompt |
| `.claude/settings.local.json` | Whitelist |
| `.gemini/policies/aitasks-whitelist.toml` | Whitelist |
| `seed/claude_settings.local.json` | Whitelist |
| `seed/geminicli_policies/aitasks-whitelist.toml` | Whitelist |
| `seed/opencode_config.seed.json` | Whitelist |

## 6. Reference patterns

- `.aitask-scripts/aitask_create.sh --batch` — backend; see lines 1618–1623 for output format.
- `.aitask-scripts/aitask_verification_parse.sh seed` — from t583_1.
- `.claude/skills/task-workflow/planning.md` §6.1 Complexity Assessment (lines 140–184) — where Edit 1 inserts.
- `.claude/skills/task-workflow/planning.md` Checkpoint (lines 258–303) — where Edit 2 inserts.
- `.claude/skills/aitask-explore/SKILL.md` §3 Task Creation — where Explore prompt inserts.

## 7. Verification

Behavior checks (run after implementation):

- **Aggregate-sibling path:** pick a parent task that is about to spawn
  children during planning; in plan mode create 2 children; answer "Yes,
  aggregate sibling" at the new prompt; confirm a new sibling is created
  with `issue_type: manual_verification`, `verifies: [child1, child2]`,
  `## Verification Checklist` populated with stubs.
- **Single-task follow-up:** pick a task that results in a single-task
  plan; at the Checkpoint select "Start implementation"; answer "Yes" at
  the new follow-up prompt; confirm a standalone task with
  `verifies: [this_task]` and `depends: [this_task]`.
- **Explore path:** `/aitask-explore` → create a new task → answer "Yes"
  at the new prompt; confirm a follow-up task is created.
- **Opt-out:** answer "No" in each of the three paths → no extra task
  created; workflow continues normally.
- **Whitelist:** after installing updates, each runtime (Claude, Gemini,
  OpenCode) can invoke `./.aitask-scripts/aitask_create_manual_verification.sh`
  without a permission prompt.

## 8. Out of scope for this task

- Gemini / Codex / OpenCode skill mirrors of the `planning.md` +
  `aitask-explore/SKILL.md` edits. Per CLAUDE.md, Claude Code is the
  source of truth; mirror tasks should be created as follow-ups after this
  task archives.
- Website docs for the new plan-time prompts — covered by t583_8
  (documentation sibling).
- Meta dogfood / aggregate manual verification for t583 itself — covered
  by t583_9 (aggregate-verification sibling).

## 9. Step 9 reminder

Commit message: `feature: Add plan-time manual-verification task generation (t583_7)`.
