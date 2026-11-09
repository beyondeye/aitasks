---
priority: medium
effort: low
depends: [t1981_4, t1981_5, t1981_6]
issue_type: chore
status: Ready
labels: [task_relations, skills]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. Skill changes land in the Claude Code tree first (`.claude/skills/`).
This child ports them to the other supported agent trees: Codex CLI / agy
(`.agents/skills/`) and OpenCode (`.opencode/skills/`, `.opencode/commands/`).
Design anchor: `aidocs/framework/task_relations.md`.

Changes to port, from what actually landed:
- **t1981_4:** the plan-approval enqueue in task-workflow Step 7 and
  `plan-approved-stop.md`.
- **t1981_5:** the related-work procedure (Step 3 check and Step 8 re-check),
  the Step 8e notify flow, and `/aitask-note` store-first.
- **t1981_6:** the obsolescence band display in the related-work check.

## Scope

1. **Inventory first.** Diff every skill or procedure file that t1981_4, t1981_5
   and t1981_6 changed. List the corresponding files in each agent tree.
2. **Port each change**, adapting to the target agent's skill format. The
   headless relations operation itself is Claude-only in v1 (D5). The
   *consumers* (pick-time check, Step 8e, `/aitask-note`) must work under every
   agent: they only call `ait relations` CLIs.
3. **Regenerate goldens** and run `./.aitask-scripts/aitask_skill_verify.sh`.

## Reference patterns

- `aidocs/framework/skill_authoring_conventions.md`
- `aidocs/framework/stub-skill-pattern.md`
- `aidocs/framework/adding_a_new_codeagent.md` (shared-root semantics of
  `.agents/`)
- `aidocs/framework/agent_runtime_guards_audit.md`, before adding or moving any
  `{% if agent %}` gate.

## Implementation plan

See `aiplans/p1981/p1981_9_port_relations_skill_changes.md`.

## Verification

- `aitask_skill_verify.sh` passes.
- The goldens are regenerated in the same commit.
- A rendered variant per agent shows the new steps.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981_5** id=2026-11-08T13:39:20Z.1abaa6d2deef57b41b951c0a from=t1981_5 from_verified=yes at=2026-11-08T13:39:20Z base=85b688f06300e7fcdab1ada992343b7036e4aeb8 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1981_5 (relations consumption), code commit f87d4ef27. These skill changes need porting to the other agent trees:
> | - .claude/skills/task-workflow/SKILL.md:
> |   - Step 3 Check 8 (related work);
> |   - the Step 8 "related work during this implementation" re-check;
> |   - Step 8e "Relations-derived offers" (the A→B→C→D flow, with profile/headless Jinja branches);
> |   - three Context Requirements rows;
> |   - a Procedures-index entry.
> | - .claude/skills/task-workflow/related-work-check.md (new, no Jinja).
> | - .claude/skills/task-workflow/planning.md: one "Related work" bullet in "While in plan mode".
> | - .claude/skills/task-workflow/profiles.md: the `relations_incomplete_action` row.
> | - .claude/skills/aitask-note/SKILL.md: Step 1 "No target given" now reads `related-work <sender> --point note` first.
> | - Agents must call /aitask-note with the `NOTE_TARGET:` value, never the qualified `<project>#<id>` ref.
> | The committed remote prerenders (.agents/, .opencode/, .claude/ task-workflow-remote*) were already regenerated at f87d4ef27.

> **✉ note:t1981_6** id=2026-11-09T09:16:51Z.5f2479480e9da1480150894e from=t1981_6 from_verified=yes at=2026-11-09T09:16:50Z base=a5763bd4eaaf17b0afa044e1f1864ddfc2836923 base_branch=main dirty=yes host=omg16
>
> | From t1981_6 (obsolescence layer), committed in e9f3d85a8. Advisory context for the porting work.
> | 
> | - `.claude/skills/task-workflow/related-work-check.md` changed in two places:
> |   - "Reading the output" now documents the `OBSOLESCENCE:<band>|<disposition>[:<target>]|<inputs>` and `OBSOLESCENCE_REASON:` lines. `related-work --point pick` emits them for the task's own medium+ obsolescence band.
> |   - "## Pick-time check" step 1 now says to show them as "Possibly obsolete (advisory)".
> | - Only the remote-profile prerenders were regenerated, mechanically, by `aitask_skill_rerender.sh remote`: `.agents/skills/task-workflow-remote-codex-/` and `.opencode/skills/task-workflow-remote-/`. The other agent trees' source surfaces still need the port, if they carry their own copy.
> | - The new user-facing CLI `ait obsolete` (`aitask_obsolete.sh`) is not invoked from any skill, so it has no permission-whitelist touchpoints.
