---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_contribute]
children_to_implement: [t341_1, t341_2, t341_3]
created_at: 2026-03-09 12:23
updated_at: 2026-03-09 13:09
---

the aitask_contribute skill was designed with hard coded area selection and checks if we are working in a repo that only installed the ait framework or we are actually in a clone/fork of the original aitasks repo. in brief the aitask-contribute skill was designed to tightly answer the requireent of make it easy to contribute back to the aitasks repo itself. yet in the website documentation (see the docs/workflows/contribute-and-manage.md it is described as a general skill than integrate seamlessy with the issue-import and pr-import capabilities of the aitasks framework. this is actually a good idea, so we want to generalize the scope of the current aitask-contribute skill to support ALSO the git repo where the aitasks framework is installed, that is the first question in the skill should be if we want to contribute to the aitasks framework or the project itself. note that we have started to introduce some more metadata about the git repo where the aitasks framework is installed: see aitasks/metadata/project_config.yaml).  The information that is missing that is needed to generalize the contribute skill is WHAT CODE AREAAS THERE ARE IN THE REPO, to allow to drill down to the actual changes we want to contribute. the question is how to obtain this information. an option is to include the contribute skill instruction on how to generate some new metadata file with a markdown drill down true of the various area and module of a project (based on the source structure of the project) and also if the user during the drill-down select a different area that was not listed, a way to update this markdown file with new area of the code identified. in order to make the drill-down efficient this markdown file with the mapping of various areas of the source code should be well structured, with a standardized format for each "branch" and "leaf" of the map of the source code. this is complex task that must be subdivided in child tasks
