---
priority: medium
effort: medium
depends: [t832_9]
issue_type: feature
status: Done
labels: [cross_repo, aitask_create]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-28 12:03
updated_at: 2026-05-29 18:34
completed_at: 2026-05-29 18:34
---

## Context

Sibling of t832_5. After the cross-planning procedure lands in
`task-workflow` (via t832_5, wired at `aitask-pick`'s planning
phase), the `aitask-create` interactive flow itself needs cross-repo
awareness so cross-repo intent can be captured at create time —
rather than relying on the user to remember to add `xdeprepo:`
manually after creation.

This is the second piece of the cross-repo planning rollout. Once
this lands, the trigger in `parallel-cross-repo-planning.md` (which
is metadata-only — fires iff `xdeprepo` is non-empty) will see a
freshly-created task with `xdeprepo:` set and run paired planning
automatically on pick.

## Architectural decisions (per user direction during t832_5 planning)

- **Trigger source remains metadata-only.** This task's job is to
  populate that metadata via UI; do NOT add body-text scanning,
  registered-project-name matching, or `aitasks#N_M` notation
  parsing anywhere in the trigger path. The intent is recorded as
  `xdeprepo:` (and optional `xdeps:`); incidental project-name
  mentions never trigger cross-repo planning.

- **Scope rollout order:** t832_5 (planning-phase wire-in,
  metadata-only trigger) → t832_10 (this task, `aitask-create`
  interactive cross-repo UI) → t832_11 (aitask-explore cross-repo
  follow-up, separate sibling, opened after this stabilises).

## Key Files to Modify

- `.claude/skills/aitask-create/SKILL.md` — currently a
  non-templated `SKILL.md`. The interactive workflow lives here.
  Add a new "Step 1b" cross-repo question, then thread
  `xdeprepo`-mode through Steps 1 (parent selection), 3c
  (dependencies), 3d (labels), and the description-authoring
  prompts.

- `.aitask-scripts/aitask_create.sh` — already supports `--xdeps`
  / `--xdeprepo` batch flags (from t832_3). No new flags needed
  for batch — only interactive plumbing through the existing
  batch surface.

- (Possibly) `.claude/skills/user-file-select/SKILL.md` — when
  the user wants to reference files in the cross-repo as part of
  the description / plan, the file-select skill needs a
  `--project <name>` option that lists files from the cross-repo.
  Confirm whether this is in scope for this task or a separate
  follow-up.

## Reference Files for Patterns

- `aidocs/cross_repo_references.md` — registry schema, resolver
  protocol.
- `.aitask-scripts/aitask_project_resolve.sh` — name → root
  resolution. Use this to validate the user's pick.
- `.aitask-scripts/aitask_query_files.sh --project <name>` (from
  t832_1) — cross-repo task lookup. Use to populate cross-repo
  dependency candidates.
- `aiplans/archived/p832/p832_3_xdeps_parser_and_validation.md` —
  confirms `--xdeps` / `--xdeprepo` batch interface and
  validation semantics.
- `aiplans/archived/p832/p832_7_cross_repo_task_update.md` —
  symmetric-edge back-fill via `aitask_update.sh --project`.

## Procedure (sketch — refine during planning)

1. **Step 1b (between parent selection and Step 2 draft creation):**
   - `AskUserQuestion`: "Does this task involve a second
     (cross-repo) project?"
     - "No, single-repo task (default)" — proceed normally.
     - "Yes, cross-repo task" — proceed to project picker.
   - Project picker: list registered projects from
     `~/.config/aitasks/projects.yaml`. Resolve each via
     `aitask_project_resolve.sh` (skip STALE / NOT_FOUND with a
     warning). Use `AskUserQuestion`.
   - Store `<xdeprepo_name>` for the rest of the flow.

2. **Step 3c (Dependencies) — cross-repo aware:**
   - List local active tasks (existing behaviour).
   - Additionally, when in cross-repo mode, list active tasks in
     `<xdeprepo_name>` via `aitask_query_files.sh --project
     <xdeprepo_name>` and present them as additional candidates.
   - The user can select any mix; on submission, partition into
     `--deps <local_ids>` and `--xdeps <cross_repo_ids>
     --xdeprepo <xdeprepo_name>` for the batch call.

3. **Step 3d (Labels) — union list:**
   - Present union of local `labels.txt` and cross-repo
     `labels.txt`. Deduplicate.
   - Selected labels go into the local task's `labels:`. The
     planning procedure (t832_5) will mirror them onto the
     counterpart cross-repo task at spawn time.

4. **Task references in description / metadata authoring:**
   - When the user is composing the task description or paste-in
     context, recognise `aitasks#N_M` notation (regex from
     `aidocs/cross_repo_references.md`) and offer to resolve
     them. (Optional polish — gate behind a follow-up if this
     adds too much scope.)

5. **File references during description authoring:**
   - When the user pastes a cross-repo file path (or invokes the
     file picker), allow selecting files from the cross-repo
     project. Requires `user-file-select` to support `--project`
     — confirm in planning whether to include here or split.

6. **Final batch call:**
   - Append `--xdeps "<csv>" --xdeprepo "<name>"` to the
     `aitask_create.sh --batch` invocation. The validator
     (`validate_xdeps_pair`) already enforces both-or-neither,
     `xdeprepo` registry resolution, and `xdeps` ID existence
     cross-repo (per t832_3).

## Tests

- `tests/test_aitask_create_interactive_cross_repo.sh`:
  - Scaffold two fake projects + registry.
  - Drive `aitask-create` interactive in cross-repo mode (mock
    AskUserQuestion answers).
  - Assert resulting task file frontmatter carries
    `xdeprepo: <name>` and (if deps were selected) the right
    `xdeps:` list.
  - Negative: pick a STALE / NOT_FOUND project name → assert the
    UI warns and re-prompts (does not fail silently).
- Regression: confirm non-cross-repo flow (the default "No") still
  produces a task with no `xdeprepo` / no `xdeps`.

## Verification

- `bash tests/test_aitask_create_interactive_cross_repo.sh` →
  passes.
- Manual smoke: create a task interactively in cross-repo mode,
  then `/aitask-pick` it and confirm the trigger in
  `parallel-cross-repo-planning.md` fires (t832_5 must be live).

## Out of scope

- aitask-explore cross-repo integration → opened as t832_11 after
  this lands.
- Templating `aitask-create` to .j2 — orthogonal cleanup task,
  unrelated to cross-repo.
- TUI surfacing of `xdeprepo` in `ait board` (t832_8).

See parent plan §t832 and the cross-planning procedure landed in
t832_5 for context.
