---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [agents_md, task_workflow]
file_references: [.claude/skills/task-workflown/planning.md:25-40]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-18 13:42
updated_at: 2026-05-18 14:28
completed_at: 2026-05-18 14:28
---

minijinja support block-comments. we are now rewriting skills to subsitute runtime check for current execution profile with templating based on execution profile parameters value. the proble is that this makes skill definition not very clear with conditional blocks, sometimes nested. it would be useful to define in aidocs that document writing skills and specifically skills that support execution profile variable that we should add comments for {% else %}: what conditions trigger the elee block. and for {%endif%} to what if/else condition it is associated with? Also, to make the skill defintion more parsable by a huoman and see at glance where the templated blocks are it would be useful to add a {# -------- #} or something similar before each {%if} and integrate the ----- in the explanation of the else branch and endif identification defined above so that their position is better parsable. also we should need to retroactively update all markdown file that already has been process for templating by task 777_7 and make sure that remaining t777 siblings has these formatting instruction in their context. after the retroactive fix, need to rerun tests associated with t777_7 (and any other relevant) to make sure we did not break anything
