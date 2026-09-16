# Explorer Input

## Exploration Mandate
-additional requirement: write the the engine and cli in go. update the framework packaging for release CI to generate all needed binaries for each platform and install the correct one. make it easy to regenerate binaries from sources for development work of the aitasks framework itself.
- the go choice will allow for better speed processing the test registry. since all the point of the new system is make tests run faster not slower
-there is a concern about the source file annotations about tests<->source association getting stale when we edit source code. perhaps we can add a field to the annotation with the time and date of the last update and create a skill/agent procedure that on file commit check the annotations and update them if needed. perhaps this can be decomposed with a cli cmnd (or subcommand of already planned cli commands) that can be used to scan for all stale annotations( update time different from last modified time) and this input can be sent to the agent procedure (to be integrated with task workfloow post impl phase or something similar)
- I have a concern about high level tests (not unit tests) that can be affected by large sets of source changes, if the planned encoding format for the registry or the source file annotations can become polluted becasue of this high level tests perhaps we should handle this kind of tests differently( different registry? different registry/annotation format?)

## Baseline Node
- Metadata: .aitask-crews/crew-brainstorm-1812/br_nodes/n000_init.yaml
- Proposal: .aitask-crews/crew-brainstorm-1812/br_proposals/n000_init.md

## Subgraph Context
subgraph context: _umbrella

## Reference Files
### Local
- /home/ddt/Work/aitasks/aiwork/t1812_selective_testing_proposal.md
- aitasks/t1812_selective_testing_source_to_tests_map_graded_selection_runne.md

## Active Dimensions
(none)

## Dimension Keys
Use these dimension keys in section markers:
- assumption_batch_per_unit_timing_reportable
- assumption_change_surface_is_intake
- assumption_existing_locks_wrappable
- assumption_gate_exit_contract_reused
- assumption_static_granularity_v1
- assumption_target_repos_accept_aitestmap_root
- assumption_testmap_token_no_collision
- component_annotation_scanner
- component_cost_ledger
- component_dependency_scanners
- component_feedback_tools
- component_gates
- component_reference_runners
- component_registry_loader
- component_runner_contract
- component_scheduler_resources
- component_selector
- component_skill
- requirements_agent_skill
- requirements_cost_tracking
- requirements_feedback_loop
- requirements_gate_enforcement
- requirements_generic_across_projects
- requirements_reason_per_selected_test
- requirements_standard_runner_contract
- tradeoff_attribution_risk
- tradeoff_batch_misreport_risk
- tradeoff_computed_vs_prose
- tradeoff_fail_closed_bootstrap_cost
- tradeoff_registry_directory_complexity
- tradeoff_resource_declaration_completeness
- tradeoff_static_scanner_overselection

## Assigned Node ID
n001_explorer_001a

Use this exact value as the `node_id` field of your output YAML.
Do not invent a different id or modify it in any way.
