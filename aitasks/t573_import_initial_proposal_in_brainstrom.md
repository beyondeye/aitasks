---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [ait_brainstorm]
children_to_implement: [t573_1, t573_2, t573_3, t573_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-16 11:50
updated_at: 2026-04-23 11:01
boardidx: 10
---

currently in ait brainstorm tui, when initialize a brainstorm we start from a blank slate ( a root node with no proposal and no plan) I would like to add support for importing an existing markdown file to be used as the initial prpposoal. the proposal need to be analyzied by a codeagent to properly reformat it (don't touch original file: i mean generate a proposal/plan) adding sections metadata, extract dimensions (see also task 571 and aidocs/brainstorming), so we end up we a proper initialized initial node for further exploration. ask me questions if you need clarifications
