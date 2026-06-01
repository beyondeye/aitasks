---
priority: high
effort: high
depends: [873]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstom_modules]
file_references: [aidocs/brainstorming/module_decomposition_design.md]
children_to_implement: [t756_1, t756_2]
created_at: 2026-05-06 18:53
updated_at: 2026-06-01 17:29
boardidx: 10
---

in ait brainstrom we want to implement a few new node operations and data model extension to support "modules" se the attached design document. this is very complex task that require child decomposition
aidocs/brainstorming/module_decomposition_design.md

## Plan-layer machinery is the reference model for the module ops (see t891)

The existing plan-layer machinery — the `detail`/`patch` operations, the
detailer/patcher agents, their plan wizard flows, and the bottom-up
impact-analysis escalation — is the **working reference model** for the new
module operations to be built here (`module_decompose`, `module_sync`, their
wizards, the syncer's bottom-up reconciliation). Build the module ops from that
model first.

The plan layer is then retired (making `ait brainstorm` proposal-only) by
**t891**, whose children are explicitly gated on this task (`depends: 756`) and
execute only after it lands. When decomposing this task into children, carry the
same reference so each child knows the plan machinery is the template — not
something to remove early. See t891 and `aiplans/p756_brainstorm_modules.md`.
