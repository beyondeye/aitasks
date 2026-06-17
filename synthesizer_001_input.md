# Synthesizer Input

## Merge Rules
here there are 3 proposal on how to improve steerability pf the aitask-shadow skill, try to merge the best points from each proposal in a COHERENT new proposal

## Source Nodes
### n001_explorer_001a
- Metadata: .aitask-crews/crew-brainstorm-1017/br_nodes/n001_explorer_001a.yaml
- Proposal: .aitask-crews/crew-brainstorm-1017/br_proposals/n001_explorer_001a.md

### n002_explorer_001b
- Metadata: .aitask-crews/crew-brainstorm-1017/br_nodes/n002_explorer_001b.yaml
- Proposal: .aitask-crews/crew-brainstorm-1017/br_proposals/n002_explorer_001b.md

### n003_explorer_001c
- Metadata: .aitask-crews/crew-brainstorm-1017/br_nodes/n003_explorer_001c.yaml
- Proposal: .aitask-crews/crew-brainstorm-1017/br_proposals/n003_explorer_001c.md


## Subgraph Context
subgraph context: _umbrella
## Reference Files (merged from all source nodes, deduplicated)
### Local
- .claude/skills/aitask-shadow/SKILL.md
- .claude/skills/aitask-shadow/plan-challenge.md
- .claude/skills/aitask-shadow/plan-assumptions.md
- .claude/skills/aitask-shadow/plan-socratic.md
- .claude/skills/aitask-shadow/plan-explain.md
- .claude/skills/aitask-shadow/plan-triage.md
- .aitask-scripts/aitask_shadow_capture.sh
- .aitask-scripts/aitask_shadow_context.sh
- .aitask-scripts/aitask_shadow_spinoff.sh
- .aitask-scripts/aitask_create.sh
- tests/test_aitask_shadow_spinoff.sh
- aidocs/framework/shadow_agent.md
- aidocs/framework/planning_conventions.md
- .aitask-scripts/aitask_shadow_spillover.sh
- aidocs/framework/skill_authoring_conventions.md
- .aitask-scripts/aitask_shadow_defer.sh
- .aitask-scripts/aitask_explain_context.sh
- tests/test_shadow_defer.sh

## Dimension Keys
Use these dimension keys in section markers:
- assumption_advisory_contract
- assumption_batch_create_available
- assumption_concern_volume
- assumption_context_fetch_has_ac
- assumption_create_batch_available
- assumption_developer_owns_decisions
- assumption_ephemeral_session
- assumption_followed_agent_pane
- assumption_intent_anchor_available
- assumption_intent_capturable
- assumption_loss_aversion_is_the_driver
- assumption_no_auto_apply
- assumption_single_active_task
- component_capture
- component_concern_ledger
- component_concern_triage
- component_context_fetch
- component_decision_withholding_guardrail
- component_defer_to_task_bridge
- component_deferral_helper
- component_intent_anchor
- component_scope_drift_guard
- component_scope_drift_meter
- component_skill_flow
- component_spillover_ledger
- component_spinoff_helper
- component_steer_draft
- component_steerability_guardrail
- component_triage_router
- component_triage_subprocedure
- requirements_fixed
- requirements_mutable
- tradeoff_advisory_purity_preserved
- tradeoff_create_stub_accuracy
- tradeoff_decision_withholding_friction
- tradeoff_deferral_proliferation
- tradeoff_draft_review_backlog
- tradeoff_extra_friction
- tradeoff_friction_vs_discipline
- tradeoff_intent_anchor_overhead
- tradeoff_intent_anchor_staleness
- tradeoff_ledger_overhead
- tradeoff_ledger_persistence
- tradeoff_scope_creep_reduction
- tradeoff_scope_meter_false_drift

## Assigned Node ID
n004_synthesizer_001

Use this exact value as the `node_id` field of your output YAML.
Do not invent a different id or modify it in any way.
