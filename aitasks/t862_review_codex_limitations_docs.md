---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [codexcli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 08:16
updated_at: 2026-05-31 10:16
---

we have just added codex configuration to ait setup to allow workflow user questions also outside plan mode. see
aitasks/archived/t861_add_codex_request_user_input_feature_flag.md

this basically eliminates most of the caveats documented in the website for codex. so we should update the website accordingly. Also we currently have special handling for starting codex from agentcommand dialogs in TUIs to send to codex the skill to run preceded by a command to enter /plan mode and we have enforcement in codex skills that require user input to enter them only if codex is currently in plan mode. we need also a follow up task, to the website codex caveats docs update, to check if this special treatment when running codex is still needed. Is it possible to remove the forced entering into plan mode with free text instruction in the skill to enter plan node? is it needed at all now? probably yes for skills that do actual planning like aitask-pick and aitask-explore. need to investigate this both with smoke test (try to call codex and try make it enter plan mode with free text request, and check codex docs and github issues about this.
