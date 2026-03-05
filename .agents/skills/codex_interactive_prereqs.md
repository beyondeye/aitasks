# Codex CLI Interactive Skill Prerequisites

These prerequisites apply to all interactive Codex CLI skills. Check them
BEFORE reading or executing the source Claude Code skill.

## Plan Mode Required

This skill uses `request_user_input` for interactive prompts. This function
**only works in plan mode** (Suggest mode). In other modes, all user prompts
are silently skipped, causing the skill to make wrong decisions or skip
critical steps.

**Check:** If you are NOT running in plan mode, STOP immediately and
display this message to the user:

> This skill requires **plan mode** to work correctly.
> Please switch to plan mode and re-run the skill.
> Without plan mode, interactive prompts are silently skipped.

Do NOT proceed with the skill workflow until plan mode is confirmed.
