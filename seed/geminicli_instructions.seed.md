# aitasks Framework — Gemini CLI Instructions

For shared aitasks conventions (task file format, task hierarchy,
git operations, commit message format), see `seed/aitasks_agent_instructions.seed.md`.
During `ait setup`, those conventions are installed directly into this file.

The sections below are Gemini CLI-specific additions.

## Skills

aitasks skills are available in `.gemini/skills/`. Each skill is a wrapper
that references the authoritative Claude Code skill in `.claude/skills/`.
Read the wrapper for tool mapping guidance.

Custom commands are also available in `.gemini/commands/`.

## Agent Identification

When recording `implemented_with` in task metadata, identify as
`geminicli/<model_name>`. Read `aitasks/metadata/models_geminicli.json` to find the
matching `name` for your model ID. Construct as `geminicli/<name>`.
