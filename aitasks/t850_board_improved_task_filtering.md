---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-27 23:27
updated_at: 2026-05-28 09:28
---

in ait board, currently we have the following task filters: a all, i impl, g git, t type. We want to add  a new filter: f free, that is only tasks that currently are not locked or in implementing status. also, we are currently in the process of adding customizable shortcuts. also currently we cannot have at the same time t type filter active together with g git or i impl filter. We should: t type filter should always be applied in addition to any of a all, g git, i impl, f free, type filters. while a all, i impl, f free are mutually exclusive filters, also g git filter should be a filter that can be applied in addition to a all, i impl, f free type filter. and of course, filtering by task name is always applied in addition to other task filter. we need to change the ui to reflect this modified behavior, that is that g git, t type, are filter add can be active in parallel to a,i,f filters. ask me questions if you need clarifications
