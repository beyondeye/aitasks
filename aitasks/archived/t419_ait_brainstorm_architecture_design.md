---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [brainstorming, agentcrew]
created_at: 2026-03-18 12:56
updated_at: 2026-03-19 23:07
completed_at: 2026-03-19 23:07
boardidx: 30
---

we want to create a new tui for brainstorming tasks plans, that is more general and flexible that the normal planning features avaiable in code agents. we have recently built (or we are building) infrastructure to support this new feature (see agentcrew, see ait diffviewer (task t417)). we also we have a design document (aidocs/brainstorming/building_an_iterative_ai_design_system) where we started the design of the brainstorming process. the process need a ai agent orchestator engine, and we have one already (see aidocs/agentcrew). the purpose of this task is finalize the architecture of this brainstorming engine, using agencrew as orchestrator. the actual UI (TUI) for managing the brainstorming process will be designed later: this task is for designing the orchestration layer, finalizing data formats, where brainstorming data is stored and how. and supporting the general design flow as described in building_an_iterative_ai_design.md. by the way the design level still probably need refinement, so if you see places where an alternative approach could be beneficial ask me to finalize decisions. this is complex task that require child decomposition
