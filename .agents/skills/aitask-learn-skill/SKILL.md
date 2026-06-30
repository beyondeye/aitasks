---
name: aitask-learn-skill
description: Learn a new skill from sources — a local file, a URL, a repo file/dir, or a tmux pane (capturing the workflow an agent just ran) — and generate a complete static SKILL.md.
---

## Source of Truth

This is a wrapper for code agents that use the shared `.agents/` skills root
(Codex CLI today, and other `.agents`-standard agents such as Antigravity CLI as
support is added) — it is not Codex-specific. The authoritative skill definition
is:

**`.claude/skills/aitask-learn-skill/SKILL.md`**

Read that file and follow its complete workflow (it reads its shared
`generate.md` core itself).

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

Optional source: a tmux pane id (`%5`), a local file path, or a GitHub/GitLab/Bitbucket file-or-directory URL. Without an argument, the skill prompts for the source.
