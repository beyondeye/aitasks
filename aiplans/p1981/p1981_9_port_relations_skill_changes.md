---
Task: t1981_9_port_relations_skill_changes.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_9 — Port relations skill changes to the other agent trees

## Context

The Claude Code skill changes from t1981_4 (the plan-approval enqueue), t1981_5
(the related-work procedure, Step 8e, `/aitask-note` store-first) and t1981_6
(the band display) must reach the Codex / agy (`.agents/skills/`) and OpenCode
(`.opencode/`) trees. The headless relations operation stays Claude-only in v1.
The consumers only call `ait relations` CLIs, so they must work under every
agent.

## Steps

0. **Reality check.**
   - `git log --stat` for t1981_4, t1981_5 and t1981_6: list every changed
     skill, procedure or `.md.j2` file.
   - Find the counterparts in each agent tree.
   - Read `aidocs/framework/skill_authoring_conventions.md`,
     `stub-skill-pattern.md` and `adding_a_new_codeagent.md`.
   - Read `aidocs/framework/agent_runtime_guards_audit.md` before touching any
     `{% if agent %}` gate.
1. **Port each change**, adapting it to the target format. Keep the
   Claude-only parts (plan externalization and the like) out, as the existing
   ports do.
2. **Regenerate the goldens** for every affected render and run
   `./.aitask-scripts/aitask_skill_verify.sh`.

## Verification

- `aitask_skill_verify.sh` passes.
- The goldens are regenerated in the same commit.
- Each agent's rendered variant shows the related-work check, Step 8e and the
  store-first note discovery.

## Step 9

Post-implementation per task-workflow Step 9.
