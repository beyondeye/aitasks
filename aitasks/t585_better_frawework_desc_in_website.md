---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [web_site, positioning]
file_references: [website/content/_index.md:54-63]
children_to_implement: [t585_1, t585_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 10:32
updated_at: 2026-04-19 11:17
---

the aitasks framework has evolved from a few helper skill, to proper tasks handling , git integrations workflows, and lately full tmux integration and a cohesice "IDE"-like experence for agent coding in the TERMINAL. I want to redesign the website landing page to reflect the full scope of the aitasks framework better. currently we have three highlighted "features" file-based tasks, code agen integration, parallel development. these are relatively low level features that does not reflect the full scope of the frameworks here are some ideas of what are actually high level features that should be highlighted: 1) a full agentic IDE in you terminal: kanban board for tasks, codebrowser, and agent monitoring dashboard 2) structure long term memory for agents (via queriable archived tasks+plans linked to git history) 3) tight coupling with git and common git-based workflows: ai-enhanced handling of PR/issues/contributions/change logs/revert code changes 4) ai-enhanced code reviews: qa and testing, explain code changes, batched code reviews and review guides autoamtic suggestion 5) automatic task decomposition and parellelization 5) support for multiple codeagents in parallel with codeagent wrapper and agent verified scores 6) linux macos and windows. In addition to the restructuring of the main page with these new highlights, there is also a need to add a new main page for "Concepts" for concepts that spawn the whole framework, like tasks, plans etc with proper cross reference to the reset of the documentation. also after the restructuring of the highlight in the main page need to verify that the rest of web pages are adjusted so that they are now coherent with the new highlights. for example the overview page is outdated for sure. Also remove references to conductor framework, beads framework: aitasks has evolved so much that reference to such frameworks is misguiding. this is a complex documentation task taht should be split in multiple child task. By the way the new highlights in the main website page should also include a revamp of the general visual style in the main page, to make it more modern and appealing. also after updating the main webpage. should consider updating in a similar way also the main README.md in the github repo. also the reference to github page in the website should be rephrased with something like:  "start the repo on github" to support us!
