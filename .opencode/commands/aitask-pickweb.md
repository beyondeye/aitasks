---
description: Pick and implement a task on Claude Code Web. Zero interactive prompts. No cross-branch operations — stores task data locally in .aitask-data-updated/.
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Pre-rendered variants for headless
profiles (currently `remote`) are committed to the repo so the skill works
in environments where the rendering toolchain (minijinja) is unavailable.
Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh pickweb`
   and use the single-line stdout as `<profile>`.

2. **Render only if needed.** If the committed pre-rendered file at
   `.opencode/skills/aitask-pickweb-<profile>-/SKILL.md` already exists, skip
   this step. Otherwise run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-pickweb --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/aitask-pickweb-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
