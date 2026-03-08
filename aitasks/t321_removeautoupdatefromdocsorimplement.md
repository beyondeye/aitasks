---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [auto-update]
children_to_implement: [t321_1, t321_2, t321_3, t321_4]
created_at: 2026-03-06 07:53
updated_at: 2026-03-08 09:37
---

currently in the docs we reference in the docs/overview/ that the framework has an autoupdate feature for make it easy to contribute features to the framework. we should implement it, we already have now infrastructure for import pull request that can be used for this purpose call this skill aitask-contribute. in the skill we should ask the user where the changes they want to contribute are and gather information about that and automatically open an issue with the associated changes and ai described changes, base the new aitask-contribute skill on a modified version of pr-import that work instead comparing pr branch with main, by comparing the user local code with main branch that output a structured output with code samples, motivation scope of the change proposed merge approach in a new issue to the aitasks repo on github, for this special issue, we should in the issue-import generate contributor field like now this is done in pr-import so that when the aitask generated from this special issue in implemented proper attribution to the the commits as contributors is given to the contributing user. need to update documentation for this new aitask-contribute skill and proper wrapper for all supported coding agents and specifically reference to this skill in docs/overview where this feature is referenced. this is a very complex task that need to be decomposed to child tasks
