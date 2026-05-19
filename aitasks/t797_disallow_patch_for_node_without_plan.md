---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [ait_brainstorm]
created_at: 2026-05-19 11:18
updated_at: 2026-05-19 11:18
---

in ait brainstorm we various operations that can be executed on a parent node. the patch operation work specifically on an node existing plan. if no plan exists, then the patch op do nothing: we should not allow the patch operation for parent node that have no plans, need to update the wizard in the actions tab to return an error of stop with some meaningful message if the selected node for patching does not have a plan. also: a general question about every place where we render a brainstorm node in ait brainstorm: be it in the dashboard tab (with the node list), or in graph tab or in the actions tab when we show a list of node from where to selecte the source node: do we show any indicator for nodes that have a plan? ask me questions if you need clarificaitons
