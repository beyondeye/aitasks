---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [geminicli]
created_at: 2026-03-08 09:57
updated_at: 2026-03-08 09:57
---

geminicli read skills both from .gemini and from .agents

here are the warnings I get: ⚠  Skill conflict detected: "aitask-wrap" from "/home/ddt/Work/aitasks/.agents/skills/aitask-wrap/SKILL.md" is overriding the same skill from "/home/ddt/Work/aitasks/.gemini/skills/aitask-wrap/SKILL.md".

so we must adapt the skill wrappers in .agents to handle both the cases for geminicli and codexcli, making sure that the codex specific adaptation are read only if we are in codexcli, and specific adaptation for geminicli only if we are on geminicli. to detect this wrap the specific doc reference read with If you are codexcli, then ....,   If you are geminicli then ....

this task, in addiion to consolidating geminicli skill wrappers and codexcli skill wrappers, need also to update tarball generation and ait setup script to unify packaging and installing for the gemini/codex skills. gemini custom commands packaging/wrappers remain AS IS for now.
