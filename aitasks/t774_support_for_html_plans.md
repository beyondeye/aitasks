---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_pick, html_plans]
created_at: 2026-05-14 15:46
updated_at: 2026-05-14 15:46
boardidx: 30
---

currently the aitasks framework only support markdown plan files, associated to tasks. there is a growing trend to better integrate html as a format for implementation plans or exploration of the implementation space. see https://x.com/trq212/status/2052809885763747935 I want to gradually add full support for html plans files in the aitasks framework. the first step would be that a 3rd file associated to aitasks tasks. that is curently we have a task file and a markdown file associated to the task. I would like to also add an option html "plan" file. with full support for archiving/querying/ zipping old files like we currently have for markdonw plan files associated to tasks. Once this is supported we can start thinking how to integrate html plan files in exisitng workflows supported by aitasks. I think we are not going to "substitute" markdown plans with html plans. I think we are going to have them in parallel, with different and varying roles as described in the linked page on x. like the html plan containing prototypes and the markdown the authorative actual implementation plan, that translate all the information in the the html "plan" file (like multiple mockups, etc) into a single actionable plan, or referencing info contained in the html plan (again like mockups, or configurations selected by the user). One issue for all this to work, is that in "planning" mode claude and other code agent cannot write files they can only update the internal markdown plan file, so unless this changes we need to find a way to allow writing the html plan during "planning" I think that the upcoming implementation of the gates franework (task 635) that will allow multi-stage processing will be perfect to integrate this kind of workflow, with plan -> html plan with mocks/ multiple choices -> user choices and refinemeent of impl plan, etc. naturally able to integrate html plans in the task implementation workflow. this a very complex tasks, and that need be first probably explored in brainstorming mode before implementation
see also https://thariqs.github.io/html-effectiveness/
