---
description: Sitrep steward for this repository — keeps its one persisted todo list (what is going on, what is pending), turns finished agents' wrap-ups into action and watch items, and answers questions from the sources. Advisory-only. Opened with `ait sitrep` in its own window; not a task-implementation command.
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh sitrep`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-sitrep --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/aitask-sitrep-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
