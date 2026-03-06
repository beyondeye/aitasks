# aitasks Framework — OpenCode Instructions

For shared aitasks conventions (task file format, task hierarchy,
git operations, commit message format), see `seed/aitasks_agent_instructions.seed.md`.
During `ait setup`, those conventions are installed directly into this file.

The sections below are OpenCode-specific additions.

## Skills

aitasks skills are available in `.opencode/skills/`. Each skill is a wrapper
that references the authoritative Claude Code skill in `.claude/skills/`.
Read the wrapper for tool mapping guidance.

Invoke skills with `/skill-name` syntax (e.g., `/aitask-pick 16`).

## Agent Identification

When recording `implemented_with` in task metadata, identify as
`opencode/<model_name>`. Read `aitasks/metadata/models_opencode.json` to find the
matching `name` for your model ID. Construct as `opencode/<name>`.
