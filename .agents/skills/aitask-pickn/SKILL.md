---
name: aitask-pickn
description: Select the next AI task for implementation from the `aitasks/` directory.
---

This is a profile-aware skill stub. Execute these steps in order, then stop:

Experimental staging skill: this is a parallel copy of `aitask-pick` used to
test `task-workflown` hardening before any production workflow merge.

1. **Resolve active profile.** Parse ARGUMENTS for `--profile <name>`. If
   found, use that as `<profile>` and remove the `--profile <name>` pair
   from ARGUMENTS. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh pickn`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-pickn --profile <profile> --agent codex`
   No-op if the per-profile SKILL.md is already up to date.

3. **Dispatch via Read-and-follow.** Read the file at
   `.agents/skills/aitask-pickn-<profile>-codex-/SKILL.md` and execute its
   instructions as if they were this skill, forwarding the (possibly
   stripped) ARGUMENTS unchanged.
