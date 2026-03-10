---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [geminicli]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-10 09:17
updated_at: 2026-03-10 12:12
---

need to update known issue subpage in installation page in website (docs/installation/known-issues/) about current limitiations in geminicli 1)white-lists of bashscripts for aitasks scripts not working (also create a follow up tasks to fix this by installing a global white list (that seems to work) 2) llm model detection not working (geminicli cannot autodetect what llm is using, unless we use cli_help tool that is very slow) 3) detection of current llm model in use also is unreliable in codex cli 4) codex cli sometimes still misses to follow instruction for task locking before starting implementation and cannot lock tasks before task planning phase, and also need to be explicitly prompted to finish workflow, after implementation (because once in normal exection mode, not suggest/plan mode, ask user question stop working in codex.  rewrite all this in better english and using appropriate terminology per geminicli docs and codex cli docs. ask me questions if you need clarifications
