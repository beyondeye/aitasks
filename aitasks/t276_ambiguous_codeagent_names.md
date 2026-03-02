---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codeagent]
children_to_implement: [t276_1]
implemented_with: claudecode/claude-opus-4-6
created_at: 2026-03-02 11:26
updated_at: 2026-03-02 19:52
---

throught the bash scripts, aitasks/metadata/modesl_<code agent>.json, and tuis with refer to the claude code code agent as simply "claude" and to geminicli as "gemini" and codex cli as code. although the actual command name for running them is actually as currently used (calude for claude code, gemini for geminicli, the actual correct names are claudecode and geminicli (in order not to confuse them to the associated llm models) need to update all reference to claude (when referring to claude code) and gemini (when referring to geminicli) with claudecode and geminicli. this is a tasks that require scanning a lot of project files so for avoiding context bloat it is better split this task in a couple of child tasks
