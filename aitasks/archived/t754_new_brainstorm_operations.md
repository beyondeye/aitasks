---
priority: high
effort: low
depends: []
issue_type: feature
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-05 12:15
updated_at: 2026-05-06 12:16
completed_at: 2026-05-06 12:16
boardidx: 10
---

in ait brainstorm, the current supported brainstorm operations do not cover all use cases, in this task I want to preset the use cases and design new operations that will help to cover them, by themselves of by the combination of multiple operation (best single operation for most common use cases).

1) we have a wide ranging proposal that add a feature but it is also a bit "abstract", and we have some specific use case that exercise the feature of only a part of the proposal feature. It would be good if it could be possible to "decompose" the proposal in multiple module and evolve/implement each module using the brainstorm machinery independently, so we could extract and evolve the modules first that are most relevant to some use case, refine their plans but keep a reference to the wider proposal, that we will refine later onces specific modules are refined/or even already implemented. this new angle conflicts with the current one to one connection of a proposal to a task file, need to rethink if can change the brainstorming to link (two way links) to multiple tasks associated with each of the modules identified in the proposal that evolve/implement independently although still correlated

2) a second use case that is related to 1) is when we have a wide ranging proposal and we identify a specific module/part in it that we currently want to refine/implement connect to specific use cases, while other parts of the proposal we need to get back to later and decide later if and how to implement. we want ait brainstorm data to support keeping this fluid status of the proposal with parts progressing faster other parts left for later

3) connect part/modules of the proposal to specific use cases and have an operation that help use extract the modules from the proposal to fast track so that we can support the specific use cases we want to support while keeping the general structure of the proposal and more genral scope for later (i.e. we dont want to loose the general framework of the prposal, we want in parallel to evolve part of the proposal that directly connect to specific use cases
