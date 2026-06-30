---
name: aitask-learn-skill
description: Learn a new skill from sources — a local file, a URL, a repo file/dir, or a tmux pane (capturing the workflow an agent just ran) — and generate a complete static SKILL.md.
---

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-learn-skill/SKILL.md`**

Read that file and follow its complete workflow (it reads its shared
`generate.md` core itself). For tool mapping and OpenCode adaptations, read
**`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

Optional source: a tmux pane id (`%5`), a local file path, or a GitHub/GitLab/Bitbucket file-or-directory URL. Without an argument, the skill prompts for the source.
