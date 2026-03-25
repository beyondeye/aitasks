---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codebrowser, qa]
children_to_implement: [t465_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-25 12:40
updated_at: 2026-03-25 12:56
---

we have implemented a new screen in codebrowser, the history screen, but there are addiional feature I would like to add

in codebrowser main screen, when a file is open and a plan is selected, add a keyboard shortcut/ command to open the corresponding task in the history screen (this is analogous to the feature that from history screen allow to open a file in the main codebrowser screen)

another feature I want to add is in the history screen, when a task is selected and visible in the detail screen, add a context aware command/shortcut to spwwn a codeagent with aitask-qa skill for the selected task, this is analogous to the feture we already have to spawn a codeagent with aitask-explain skill from the main codebrowser screen. we need also to add in the settings tui the proper configuration for the codeagent/model to use for this (similar as what we have for the explain skill) this involve updating the settings screen but also the seed with the default code agents configured for the skills like pick/explain (and now qa).  finally we need to update the codebrowser tui docs in the website about this new feature. this is a complex task. and must be split in child tasks
