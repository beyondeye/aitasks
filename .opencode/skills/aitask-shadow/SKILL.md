---
name: aitask-shadow
description: Shadow companion for a followed coding agent — reads its captured terminal output and, in one instruction-driven flow, explains it, helps answer an AskUserQuestion, or critically interrogates a plan. Advisory-only. Spawned by minimonitor; not a task-implementation command.
user-invocable: true
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh shadow`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/aitask-shadow-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
