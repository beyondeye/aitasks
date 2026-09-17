---
name: aitask-brainstorm-discuss
description: Discuss brainstorm proposals interactively — compare them in simple words or in depth, explain one plainly but fully, answer questions, and check a design for structural flaws and risks. Advisory-only. Launched from the brainstorm TUI; not a task-implementation command.
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh brainstorm-discuss`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-brainstorm-discuss --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/aitask-brainstorm-discuss-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
