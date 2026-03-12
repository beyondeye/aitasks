---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_settings, task_workflow]
created_at: 2026-03-12 10:47
updated_at: 2026-03-12 10:47
---

currently in ait settings tui we have in the Project Config tab, the option to set the verify_build settings. drr /docs/skills/aitask-pick/build-verification/ in website documentation. there are several issue with it

First, when editing it, it still continue to show it as not set. second, in the editing dialog, we should have a multine edit, third, we should have a button the modal dialog where we edit it, to choose it from some predefined defaults from common project types, make the list of this pre-configurations dynamic, storing it in a aitask-scripts/settings/ directory in some format (like yaml) that is easily parsable end editor, with a list of entries there with common project configuration. when pressing the button to select from predefined configurations, allow to fuzzy search for the configuration name, and use top down arrows to move between currenly fuzzy selected configs, when a config is selected, show also a preview of its content in side box.

also in the project config tab, in addition toe explanation of what the verify_build option is for, add a link with the link to the build verification page in the aitasks documentation: https://aitasks.io/docs/skills/aitask-pick/build-verification/

also in the project config tab, when some verify_build value is set, show, when used, which preset build config was selected
