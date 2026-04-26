---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [brainstorming, ait_brainstorm]
created_at: 2026-04-16 09:15
updated_at: 2026-04-16 09:15
boardidx: 70
---

I would like to add a new brainstrom operation in ait brainstorm tui: child split and high level implementation plan (that is order and dependency for children implementation) child split operation should be designed to maximize testability, that is order of child implementation should reflect the priority of making the implemented code testable as soon as possible, without deferring tests to later stages when more sibling are implemented. anyway this operation should be configurable: there user should be able to choose the high level options for the operation, like prioritize parallel implementation vs prioritize testability etc. just make sure to create the the skeleton ui (wizard like when operation is issued). the plan subdivision in child should be defined as a separate section of the brainstormed plan, at the end of the brainstormed plan,
