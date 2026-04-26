---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [brainstorming, ait_brainstorm]
children_to_implement: [t571_7]
created_at: 2026-04-16 09:50
updated_at: 2026-04-20 12:03
boardidx: 150
---

the ait brainstorming tui and infrastructure (see also aidocs/brainstorming design documents) support "design" dimensions that are explored in in DAG where each node can split according to alternative design decision for some design dimension. a fundamental problem in the current IMPLEMENTATION is that the plan markdown file that basically define each node of the dag is UNSTRUCTURED, there is no clear link between design dimensions and section of the plan. of course not always this link exists: sometime a design dimension affect multiple components or even the whole design. but wehn possible we should be able to connect design dimensions and specific section in the plan, but we have no standard/ convention to define such section in a parsable way. note that this "section" concept is useful also when we want to define child decompostion or if we want to concentrate avaiable design operations to a specific section of the plan. in addition to a format for defining this plan "sections" and how to parse them (from python: this is all integrated in the ait codebrowser) there should be a plan "viewer" integrated in the ait codebrowser that support a minimap of all plan section with associated dimension tags to jump directly. and again there should be support in braisntorm operation to refer to these sections (for example the detail operation) so basically some parameter that specificy one ore more sections on which the brainstorm operation should work on. this a complex refactor task that need to be sp[it into child tasks: ask me questions if you need clarifications
