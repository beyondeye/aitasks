# Explorer Input

## Exploration Mandate
note to the current proposal:
- static go binary: the name of the framewors is "aitasks" not "aitask" so the installed binaries should go in "~/.aitasks/engine/..." 
- in thinkingapp project we have a natural subdivision of code: all code that affects "visually" a specific screen for one or more localization (please look at how this is implemented in the thinkingapp test code). do the current proposal support this kind of mapping of source changes to tests?

## Baseline Node
- Metadata: .aitask-crews/crew-brainstorm-1812/br_nodes/n003_synthesizer_001.yaml
- Proposal: .aitask-crews/crew-brainstorm-1812/br_proposals/n003_synthesizer_001.md

## Subgraph Context
subgraph context: _umbrella

## Reference Files
### Local
- /home/ddt/Work/aitasks/aiwork/t1812_selective_testing_proposal.md
- aitasks/t1812_selective_testing_source_to_tests_map_graded_selection_runne.md
- .github/workflows/release.yml
- .github/workflows/release-packaging.yml
- .github/workflows/contribution-check.yml
- .github/workflows/hugo.yml
- aidocs/packaging/packaging_strategy.md
- packaging/nfpm/nfpm.yaml
- packaging/shim/ait
- install.sh
- .aitask-scripts/aitask_setup.sh
- .aitask-scripts/aitask_upgrade.sh
- .aitask-scripts/lib/aitask_path.sh
- .aitask-scripts/lib/python_resolve.sh
- .aitask-scripts/VERSION
- ait
- website/go.mod
- /home/ddt/Work/aitasks_go/go.mod
- aidocs/framework/aitasks_extension_points.md
- aidocs/framework/python_tui_performance.md
- aidocs/framework/planning_conventions.md
- .aitask-scripts/aitask_change_surface.sh
- .aitask-scripts/lib/gate_verifier_lib.sh
- .aitask-scripts/aitask_gate_tests_pass.sh
- .aitask-scripts/aitask_gate.sh
- .aitask-scripts/gates_reference.yaml
- aitasks/metadata/gates.yaml
- .claude/skills/aitask-gate-template/SKILL.md
- .claude/skills/aitask-gate-docs-updated/SKILL.md
- .claude/skills/task-workflow/SKILL.md
- seed/project_config.yaml
- seed/code_areas.yaml
- .aitask-scripts/aitask_codemap.sh
- aidocs/framework/manual_verification_staleness.md
- .aitask-scripts/aitask_verification_stale.sh
- .aitask-scripts/aitask_sync.sh
- .aitask-scripts/lib/artifact_utils.sh
- tests/run_all_python_tests.sh
- tests/test_serial_carveout_doc_drift.sh
- tests/test_board_header_row_live.py
- tests/test_brainstorm_cli.sh
- tests/test_no_unscoped_task_commit.sh
- tests/test_gate_verifiers.sh
- tests/test_frozen_agents_acceptance.sh
- tests/test_t167_integration.sh

### Remote (cached)
- br_url_cache/00475296.md (source: https://go.dev/doc/install)
- br_url_cache/84304bbb.md (source: https://go.dev/doc/install/source#environment)
- br_url_cache/ce7aab58.md (source: https://go.dev/ref/mod#go-mod-file-toolchain)
- br_url_cache/4569986c.md (source: https://go.dev/doc/go1.21#tools)
- br_url_cache/f991a74a.md (source: https://pkg.go.dev/gopkg.in/yaml.v3)
- br_url_cache/b5a9b7af.md (source: https://github.com/bmatcuk/doublestar)
- br_url_cache/74c0088c.md (source: https://pkg.go.dev/github.com/bmatcuk/doublestar/v4)
- br_url_cache/38fbcc8e.md (source: https://pkg.go.dev/golang.org/x/sync/errgroup)
- br_url_cache/013532e5.md (source: https://github.com/actions/setup-go)
- br_url_cache/1f6d4ab5.md (source: https://github.com/softprops/action-gh-release)
- br_url_cache/bbc6139b.md (source: https://git-scm.com/docs/git-log)
- br_url_cache/0b15f3e7.md (source: https://git-scm.com/docs/git-hash-object)
- br_url_cache/c1edd7e4.md (source: https://git-scm.com/docs/git-ls-tree)
- br_url_cache/a555ec8c.md (source: https://git-scm.com/docs/git-merge-base)

## Active Dimensions
requirements_go_engine_and_cli, requirements_platform_binaries_in_release, requirements_dev_rebuild_from_source, requirements_annotation_freshness, requirements_high_level_tests_separate, assumption_go_toolchain_available, assumption_release_asset_reachable, assumption_git_history_is_freshness_clock, assumption_passing_run_anchors_edges, assumption_areas_express_suite_blast_radius, assumption_engine_latency_targets, component_go_engine, component_binary_distribution, component_freshness, component_suite_registry, tradeoff_two_toolchains, tradeoff_setup_network_fetch, tradeoff_area_glob_coarseness, tradeoff_flaky_pass_anchors, tradeoff_strict_version_handshake, requirements_go_engine, requirements_engine_packaging, requirements_engine_dev_regeneration, requirements_annotation_staleness, requirements_broad_test_handling, assumption_go_toolchain_ci_and_dev_only, assumption_release_assets_reachable, assumption_platform_matrix_sufficient, assumption_blob_digest_is_staleness_key, assumption_broad_tests_area_scoped, assumption_one_engine_per_framework_version, component_engine_binary, component_engine_packaging, component_staleness_tool, component_broad_test_scopes, tradeoff_engine_speed_enables_per_task_use, tradeoff_real_scheduler, tradeoff_noarch_packages_preserved, tradeoff_compiled_component_cost, tradeoff_engine_version_skew, tradeoff_stamp_churn, tradeoff_broad_scope_coarseness, tradeoff_autonomous_confirmation_weak, tradeoff_engine_absent_on_host, component_evidence_join, tradeoff_evidence_requires_reachable_history

## Dimension Keys
Use these dimension keys in section markers:
- assumption_areas_express_suite_blast_radius
- assumption_batch_per_unit_timing_reportable
- assumption_blob_digest_is_staleness_key
- assumption_broad_tests_area_scoped
- assumption_change_surface_is_intake
- assumption_engine_latency_targets
- assumption_existing_locks_wrappable
- assumption_gate_exit_contract_reused
- assumption_git_history_is_freshness_clock
- assumption_go_toolchain_available
- assumption_go_toolchain_ci_and_dev_only
- assumption_one_engine_per_framework_version
- assumption_passing_run_anchors_edges
- assumption_platform_matrix_sufficient
- assumption_release_asset_reachable
- assumption_release_assets_reachable
- assumption_static_granularity_v1
- assumption_target_repos_accept_aitestmap_root
- assumption_testmap_token_no_collision
- component_annotation_scanner
- component_binary_distribution
- component_broad_test_scopes
- component_cost_ledger
- component_dependency_scanners
- component_engine_binary
- component_engine_packaging
- component_evidence_join
- component_feedback_tools
- component_freshness
- component_gates
- component_go_engine
- component_reference_runners
- component_registry_loader
- component_runner_contract
- component_scheduler_resources
- component_selector
- component_skill
- component_staleness_tool
- component_suite_registry
- requirements_agent_skill
- requirements_annotation_freshness
- requirements_annotation_staleness
- requirements_broad_test_handling
- requirements_cost_tracking
- requirements_dev_rebuild_from_source
- requirements_engine_dev_regeneration
- requirements_engine_packaging
- requirements_feedback_loop
- requirements_gate_enforcement
- requirements_generic_across_projects
- requirements_go_engine
- requirements_go_engine_and_cli
- requirements_high_level_tests_separate
- requirements_platform_binaries_in_release
- requirements_reason_per_selected_test
- requirements_standard_runner_contract
- tradeoff_area_glob_coarseness
- tradeoff_attribution_risk
- tradeoff_autonomous_confirmation_weak
- tradeoff_batch_misreport_risk
- tradeoff_broad_scope_coarseness
- tradeoff_compiled_component_cost
- tradeoff_computed_vs_prose
- tradeoff_engine_absent_on_host
- tradeoff_engine_speed_enables_per_task_use
- tradeoff_engine_version_skew
- tradeoff_evidence_requires_reachable_history
- tradeoff_fail_closed_bootstrap_cost
- tradeoff_flaky_pass_anchors
- tradeoff_noarch_packages_preserved
- tradeoff_real_scheduler
- tradeoff_registry_directory_complexity
- tradeoff_resource_declaration_completeness
- tradeoff_setup_network_fetch
- tradeoff_stamp_churn
- tradeoff_static_scanner_overselection
- tradeoff_strict_version_handshake
- tradeoff_two_toolchains

## Assigned Node ID
n004_explorer_002a

Use this exact value as the `node_id` field of your output YAML.
Do not invent a different id or modify it in any way.
