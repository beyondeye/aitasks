---
priority: low
effort: medium
depends: []
issue_type: feature
status: Postponed
labels: [cross_repo, aitask-create]
created_at: 2026-05-29 18:33
updated_at: 2026-06-01 11:56
boardcol: now
boardidx: 60
---

## Context

Follow-up to t832_10. That task added `xdeprepo` declaration and cross-repo task/file references to the **`ait create` interactive bash flow** (fzf-driven). This task mirrors the same UX into the AI-driven **`aitask-create` skill** (`.claude/skills/aitask-create/SKILL.md` and its Codex / OpenCode equivalents).

## Goal

When an AI agent runs `/aitask-create` (or the equivalent skill in another agent), the skill should:

1. Ask early whether the task involves a second (cross-repo) project.
2. Present a project picker sourced from `aitask_project_resolve.sh list`.
3. When in cross-repo mode, integrate cross-repo deps into Step 3c (dependency selection — unified multiSelect across local + cross-repo).
4. When in cross-repo mode, add labels-union support (Step 3e new) reading local + cross-repo `labels.txt`.
5. Recognise and resolve the `<project>#<id>` task notation and `<project>:<relative/path>` file notation during description authoring.
6. Pass `--xdeprepo` (and `--xdeps` when applicable) on the final `aitask_create.sh --batch` invocation.

## Key Files to Modify

- `.claude/skills/aitask-create/SKILL.md` — currently non-templated `SKILL.md`. Add Step 1b (cross-repo question + project picker) between Step 1 (parent selection) and Step 2 (draft creation); thread cross-repo through Steps 3c (deps), and add a new labels step.
- `.agents/skills/aitask-create/SKILL.md` (Codex equivalent — apply same changes).
- `.opencode/commands/aitask-create.md` (OpenCode equivalent — apply same changes).
- `.aitask-scripts/aitask_query_files.sh` — add a `labels` subcommand emitting `LABEL:<name>` per non-blank, non-comment line of `aitasks/metadata/labels.txt`. Reuses the existing `--project` re-exec path for cross-repo.

## Reference Files for Patterns

- `aiplans/archived/p832/p832_10_aitask_create_interactive_cross_repo.md` — the t832_10 plan, which describes the equivalent interactive bash implementation including helper additions, validator semantics, and notation conventions. The skill follow-up should mirror those decisions.
- `aidocs/cross_repo_references.md` — documented `<project>#<id>` and `<project>:<relative/path>` notations consumed here.
- `.aitask-scripts/aitask_project_resolve.sh list` — already exists (added by t832_10). Returns `PROJECT:<name>:<path>:<status>` per line; reuse for the skill's project picker.

## Implementation Plan (sketch — refine during planning)

1. **Step 1b (between parent selection and Step 2 draft creation):**
   - `AskUserQuestion`: "Does this task involve a second (cross-repo) project?" → No / Yes.
   - Project picker: enumerate via `aitask_project_resolve.sh list`; skip STALE / NOT_FOUND with a warn. `AskUserQuestion` to select.
   - Store `<xdeprepo_name>` for the rest of the flow.

2. **Step 3c (Dependencies) — cross-repo aware:**
   - Existing: list local active tasks.
   - When in cross-repo mode: additionally `aitask_ls.sh --project <xdeprepo_name> -v 99`.
   - Unified `AskUserQuestion multiSelect: true` with the two sources visually grouped; partition on submission into `--deps` and `--xdeps`/`--xdeprepo`.

3. **Step 3e (Labels) — union list:**
   - Read local `aitasks/metadata/labels.txt`.
   - When in cross-repo mode: also read cross-repo labels via the new `aitask_query_files.sh --project <xdeprepo_name> labels` subcommand.
   - Deduplicate; present as a single multiSelect. Selected labels go into the local task's `labels:`. (Mirror-to-counterpart happens via the planning procedure landed by t832_5.)

4. **Notation resolution in description authoring:**
   - When the user pastes `<project>#<id>`: offer to resolve into a link by re-reading the referenced task's title via `aitask_query_files.sh --project <name> task-file <id>`.
   - When the user picks a file via the file picker while in cross-repo mode: extend `user-file-select` to support `--project <name>` and produce `<project>:<relative/path>` references.

5. **Final batch call:** append `--xdeprepo "<name>"` (always when set) and `--xdeps "<csv>"` (when concrete cross-repo deps were selected) to the `aitask_create.sh --batch` invocation. Validator (`validate_xdeps_pair`) already allows `xdeprepo` alone since t832_10.

## Helper additions

- `aitask_query_files.sh labels` subcommand — emit `LABEL:<name>` per non-blank, non-comment line of `aitasks/metadata/labels.txt`. Works with `--project` re-exec.
- Whitelist `aitask_project_resolve.sh` for skill use (5 touchpoints via `aitask_audit_wrappers.sh apply-helper-whitelist`). t832_10 did NOT whitelist because no skill called the helper at that time; this task changes that.

## Tests

- `tests/test_query_files_labels.sh` (new): assert `labels` subcommand output for local and `--project <name>` cases.
- Existing `tests/test_aitask_create_xdeprepo_alone.sh` and `tests/test_xdeps_validation.sh` already cover the batch surface and validator semantics from t832_10 — no changes needed.

## Verification

- `bash tests/test_query_files_labels.sh` passes.
- `./.aitask-scripts/aitask_skill_verify.sh` passes (skill changes).
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_project_resolve.sh` returns no MISSING lines after the apply step.
- Manual smoke: AI-driven `/aitask-create` interactively walks through the cross-repo question, picks a project, gathers cross-repo deps, and produces a draft with the expected frontmatter.

## Out of scope

- aitask-explore cross-repo integration → t832_11 (separate task).
- TUI surfacing of `xdeprepo` in `ait board` → t832_8.
- The deferred trigger consumer (parallel-cross-repo-planning procedure) → t832_5.

## Notes

This task is **not** a child of t832 — it is intentionally top-level per the user's direction during t832_10 planning. The skill-side work mirrors the bash-side work but lives at the AI-agent interaction surface; it is decoupled enough that it should sit at the top of the backlog independently rather than as a t832 child.

See `aiplans/archived/p832/p832_10_aitask_create_interactive_cross_repo.md` (after t832_10 archives) for the full implementation rationale of the symmetric bash-side work.
