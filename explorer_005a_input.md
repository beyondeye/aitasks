# Explorer Input

## Exploration Mandate
❯ one of the main value of an framework that allow to adaptively define a test set per change set is that is is done AUTOMATICALLY. if we leave this outside the proposal, then it loses a lot of its value. is possible to adapt
  the proposal (perhaps expanding it where the test sets is fully seeded by an ai agent?

● Yes, and the adaptation is smaller than it looks, because the proposal is already automatic in the place that matters most. It is worth separating what is automatic today from what the human gates actually hold back.

  What is already automatic. Seeded edges select. The moment level 0 runs, ait test in interactive and advisory mode walks seeded edges at distance 1, so every in-loop run and every pre-review run already gets an adaptive,
  per-change-set test list with no human having adopted anything. The scoring loop is automatic too. What the human gates hold back is only two things: whether the map's claims are enforced by freshness checks, and whether the
  completion gate shrinks from the full suite to the selection. Until the policy flip, tests_pass still runs everything, and that is where the value leaks.

  Why the proposal put a person there. Its stated reason is the gap between executes and verifies: static closure proves a test runs a script, not that it checks it. That is a semantic judgement, and the proposal assumes only a
  human can make it. That assumption is the thing to replace. An agent that reads the test body and the source can make exactly that judgement, and the design already has the slot for it.

  Four additions that make the loop fully agent-driven

  1. An agent-review origin. Add agent:review to the origin table at about 0.90, produced by a headless pass that reads each seeded pair and answers "does this test verify this source, or only drive it?" with a stored rationale,
     model and run id as evidence. Under the existing noisy-OR, a static edge plus agent review clears the 0.85 class threshold, so onboard adopt --class becomes headless-safe. The provenance row would read
     adopted(static:invocation+agent:review 0.99), keeping it distinct from a human reviewed stamp. Rejections land in onboard.yaml exactly as human rejections do. This rewrites design decision 2 from "only a person" to "only a
     reader of the test body", which a human or an agent can be.
  2. Treat measured origins as auto-adoptable. coverage sits at 0.95 but is barred from autonomous adoption because the rule is "confidence 1.0 only". Coverage is a measurement, not a heuristic, so the autonomous floor could be
     "measured origins" rather than "1.0". That alone makes level 1 headless for Python, Go and Kotlin projects that turn coverage on.
  3. A self-approving policy with a periodic full run. Add completion.mode: auto. The engine flips to selection when readiness reports ADMISSIBLE, records approved_by: engine:readiness@<run>, and keeps the existing automatic,
     loud demotion. The safety net that replaces the human is a scheduled full run, for example every Nth task or when the selection is under some fraction of full cost, so scoring never stops and a miss is caught within N tasks.
     The proposal's invariant "the policy can only fail toward running more" still holds.
  4. Let the authoring agent annotate. In the pre-review procedure the autonomous branch currently only proposes. The agent that just wrote the change knows which test covers the new source better than any heuristic. Let it write
     the testmap:covers line directly with origin agent:author, adopted, not merely seeded.

  What this costs, honestly. The residual risk moves from "reviewer fatigue" to "a wrong agent judgement lets a task land while an affected test never ran, until the next full run". The knob for that is the full-run cadence in
  item 3, and it is a per-project policy choice the config should expose rather than hide. Kind changes (integration, e2e, device) are the one place I would keep human confirmation, because a wrong kind silently changes staleness
  semantics and the agent has no run evidence to check itself against.

  I cannot edit the proposal, but these four points are a clean brief for a child node of n010_explorer_004, and the passages to rewrite are design decisions 2 and 10, the "Autonomous profiles may seed and may adopt only origins
  at confidence 1.0" rule in the Adoption Model, and the headless row of the onboarding section.

## Baseline Node
- Metadata: .aitask-crews/crew-brainstorm-1812/br_nodes/n010_explorer_004.yaml
- Proposal: .aitask-crews/crew-brainstorm-1812/br_proposals/n010_explorer_004.md

## Subgraph Context
subgraph context: _umbrella

## Reference Files
### Local
- /home/ddt/Work/aitasks/aiwork/t1812_selective_testing_proposal.md
- aitasks/t1812_selective_testing_source_to_tests_map_graded_selection_runne.md
- .github/workflows/release.yml
- .github/workflows/release-packaging.yml
- .github/workflows/contribution-check.yml
- aidocs/packaging/packaging_strategy.md
- packaging/nfpm/nfpm.yaml
- packaging/shim/ait
- install.sh
- .aitask-scripts/aitask_setup.sh
- .aitask-scripts/aitask_upgrade.sh
- .aitask-scripts/lib/aitask_path.sh
- .aitask-scripts/lib/python_resolve.sh
- .aitask-scripts/VERSION
- aidocs/framework/aitasks_extension_points.md
- aidocs/framework/python_tui_performance.md
- /home/ddt/Work/aitasks_go/go.mod
- .aitask-scripts/aitask_change_surface.sh
- .aitask-scripts/lib/gate_verifier_lib.sh
- .aitask-scripts/aitask_gate_tests_pass.sh
- .aitask-scripts/gates_reference.yaml
- aitasks/metadata/gates.yaml
- .claude/skills/aitask-gate-template/SKILL.md
- .claude/skills/aitask-gate-docs-updated/SKILL.md
- .claude/skills/task-workflow/SKILL.md
- seed/project_config.yaml
- aidocs/framework/manual_verification_staleness.md
- .aitask-scripts/aitask_verification_stale.sh
- .aitask-scripts/aitask_sync.sh
- tests/run_all_python_tests.sh
- tests/test_board_header_row_live.py
- tests/test_brainstorm_cli.sh
- seed/code_areas.yaml
- .aitask-scripts/aitask_codemap.sh
- ait
- website/go.mod
- .aitask-scripts/lib/artifact_utils.sh
- tests/test_no_unscoped_task_commit.sh
- tests/test_gate_verifiers.sh
- tests/test_frozen_agents_acceptance.sh
- tests/test_t167_integration.sh
- .github/workflows/hugo.yml
- aidocs/framework/planning_conventions.md
- .aitask-scripts/aitask_gate.sh
- tests/test_serial_carveout_doc_drift.sh
- .aitask-scripts/lib/launch_modes_sh.sh
- .aitask-scripts/lib/followup_kinds_sh.sh
- aidocs/framework/shell_conventions.md
- .aitask-scripts/aitask_skill_verify.sh
- tests/golden/skills/aitask-pick/SKILL-default-claude.md
- tests/golden/skills/aitask-pick/SKILL-fast-claude.md
- tests/golden/procs/task-workflow/manual-verification-default.md
- aidocs/framework/skill_authoring_conventions.md
- aidocs/framework/stub-skill-pattern.md
- aidocs/framework/adding_a_new_codeagent.md
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ScreenshotTestHarness.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/MatrixAuditRegistry.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/MatrixClassificationTest.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/CurrentHeadScreenshotsTest.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ExtendedCatalogScreenshotsTest.kt
- /home/ddt/Work/thinking_app/app/src/test/resources/screenshot-baseline-map.properties
- /home/ddt/Work/thinking_app/tools/verification/lib/screenshot-review.sh
- /home/ddt/Work/thinking_app/tools/verification/screenshot-tests.sh
- /home/ddt/Work/thinking_app/tools/verification/secondary-matrices-expected.txt
- /home/ddt/Work/thinking_app/tools/verification/primary-catalog-expected.txt
- /home/ddt/Work/thinking_app/tools/verification/matrix-audit-evidence-check.py
- /home/ddt/Work/thinking_app/tools/verification/lib/budget-constants.sh
- /home/ddt/Work/thinking_app/tools/verification/lib/gradle-invocation.sh
- /home/ddt/Work/thinking_app/tools/verification/heavy-run-lock.sh
- /home/ddt/Work/thinking_app/tools/verification/emulator-allot.sh
- /home/ddt/Work/thinking_app/tools/verification/measurements/suite-split-7943100.tsv
- /home/ddt/Work/thinking_app/tools/verification/measurements/profile-verify-active-7943100.tsv
- /home/ddt/Work/thinking_app/app/src/main/res/values-ar
- /home/ddt/Work/thinking_app/app/src/main/res/values-ru
- /home/ddt/Work/thinking_app/app/src/main/res/values-iw
- /home/ddt/Work/thinking_app/app/src/main/res/font
- .aitask-scripts/aitask_projects.sh
- .aitask-scripts/aitask_project_resolve.sh
- /home/ddt/Work/thinking_app/aidocs/testing/change-aware-verification.md
- /home/ddt/Work/thinking_app/aidocs/testing/rendering-verification.md
- /home/ddt/Work/thinking_app/aidocs/testing/localized-strings.md
- /home/ddt/Work/thinking_app/CLAUDE.md
- /home/ddt/Work/thinking_app/aitasks/metadata/project_config.yaml
- /home/ddt/Work/thinking_app/tools/verification/lib/screenshot-diff-set.sh
- /home/ddt/Work/thinking_app/tools/verification/suite-outcome-check.py
- /home/ddt/Work/thinking_app/app/src/main/java/com/softman/thinking/utils/TypeScale.kt
- /home/ddt/Work/thinking_app/app/src/main/java/com/softman/thinking/ui/components/AppRoot.kt
- /home/ddt/Work/thinking_app/aitasks/t384_advisory_affected_surface_for_change_aware_verify.md
- /home/ddt/Work/thinking_app/aitasks/t386_prediction_accuracy_ledger_for_affected_surface.md
- /home/ddt/Work/thinking_app/aitasks/t387_test_side_dependency_model_for_change_aware_verify.md
- /home/ddt/Work/thinking_app/aitasks/t388_conditional_gating_verify_affected_tier.md
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ArMatrixArabicOnlyTest.kt
- /home/ddt/Work/thinking_app/app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeScreen.kt
- .claude/skills/aitask-qa/SKILL.md.j2
- .claude/skills/aitask-qa/test-discovery.md
- .claude/skills/aitask-qa/test-execution.md
- .claude/skills/aitask-qa/change-analysis.md
- .claude/skills/task-workflow/build-verification.md
- .claude/skills/task-workflow/profiles.md
- .claude/skills/task-workflow/gate-cli.md
- .claude/skills/task-workflow/gate-recording.md
- .claude/skills/aitask-learn-skill/SKILL.md
- .claude/skills/aitask-pickrem/SKILL.md.j2
- .claude/skills/aitask-pickweb/SKILL.md.j2
- .aitask-scripts/aitask_run_project_command.sh
- .aitask-scripts/aitask_resolve_config_path.sh
- .aitask-scripts/aitask_skill_render.sh
- .aitask-scripts/aitask_skill_resolve_profile.sh
- .aitask-scripts/aitask_audit_wrappers.sh
- .aitask-scripts/aitask_explain_context.sh
- .aitask-scripts/aitask_explain_extract_raw_data.sh
- .aitask-scripts/aitask_create.sh
- .aitask-scripts/lib/followup_kinds.py
- .aitask-scripts/lib/config_utils.py
- seed/aitasks_agent_instructions.seed.md
- seed/claude_settings.local.json
- seed/codex_rules.default.rules
- seed/opencode_config.seed.json
- .claude/settings.local.json
- .codex/rules/default.rules
- aitasks/metadata/profiles/default.yaml
- aitasks/metadata/profiles/fast.yaml
- aitasks/metadata/profiles/remote.yaml
- tests/test_touchpoint_count_contract.sh
- tests/test_seed_manifest_drift.sh
- tests/test_gates_reference_drift.sh
- /home/ddt/Work/thinking_backend/scripts/tests/run_script_tests.sh
- /home/ddt/Work/thinking_backend/aitasks/metadata/project_config.yaml
- /home/ddt/Work/aitasks_go/Makefile
- /home/ddt/Work/aitasks_go/parity/run_parity.sh
- /home/ddt/Work/aitasks_mobile/shared/src/commonTest
- /home/ddt/Work/aitasks_mobile/shared/src/androidHostTest
- /home/ddt/Work/aitasks_mobile/domain/src/androidDeviceTest
- .claude/skills/task-workflow/resource-admission.md
- .claude/skills/aitask-explore/SKILL.md.j2
- .aitask-scripts/aitask_lock.sh
- .aitask-scripts/aitask_task_worktree.sh
- .aitask-scripts/aitask_attach.sh
- .aitask-scripts/lib/yaml_utils.sh
- .aitask-scripts/lib/gate_orchestrator.py
- seed/codex_instructions.seed.md
- seed/opencode_instructions.seed.md
- aitasks/metadata/project_config.yaml
- tests/lib/asserts.sh
- tests/lib/import_isolated.py
- tests/lib/board_fixture.py
- tests/lib/validate_session_hook_fixtures.py
- tests/test_agent_instructions.sh
- tests/test_agent_freeze.py
- aidocs/framework/code_conventions.md
- aidocs/framework/documentation_conventions.md
- /home/ddt/Work/thinking_backend/CLAUDE.md
- /home/ddt/Work/aitasks_go/aitasks/metadata/project_config.yaml
- /home/ddt/Work/aitasks_go/app/root_test.go
- /home/ddt/Work/aitasks_go/CLAUDE.md
- /home/ddt/Work/aitasks_mobile/aitasks/metadata/project_config.yaml
- /home/ddt/Work/aitasks_mobile/build.gradle.kts
- /home/ddt/Work/aitasks_mobile/domain/src/commonTest/kotlin/com/beyondeye/aitmobile/applink/PairFramesTest.kt
- /home/ddt/Work/aitasks_mobile/domain/src/androidDeviceTest/kotlin/com/beyondeye/aitmobile/applink/HttpClientTrustDeviceTest.kt
- /home/ddt/Work/aitasks_mobile/CLAUDE.md
- .aitask-scripts/aitask_task_commit.sh
- .aitask-scripts/aitask_pick_own.sh

### Remote (cached)
- br_url_cache/84304bbb.md (source: https://go.dev/doc/install/source#environment)
- br_url_cache/f991a74a.md (source: https://pkg.go.dev/gopkg.in/yaml.v3)
- br_url_cache/b5a9b7af.md (source: https://github.com/bmatcuk/doublestar)
- br_url_cache/013532e5.md (source: https://github.com/actions/setup-go)
- br_url_cache/1f6d4ab5.md (source: https://github.com/softprops/action-gh-release)
- br_url_cache/bbc6139b.md (source: https://git-scm.com/docs/git-log)
- br_url_cache/00475296.md (source: https://go.dev/doc/install)
- br_url_cache/ce7aab58.md (source: https://go.dev/ref/mod#go-mod-file-toolchain)
- br_url_cache/4569986c.md (source: https://go.dev/doc/go1.21#tools)
- br_url_cache/74c0088c.md (source: https://pkg.go.dev/github.com/bmatcuk/doublestar/v4)
- br_url_cache/38fbcc8e.md (source: https://pkg.go.dev/golang.org/x/sync/errgroup)
- br_url_cache/0b15f3e7.md (source: https://git-scm.com/docs/git-hash-object)
- br_url_cache/c1edd7e4.md (source: https://git-scm.com/docs/git-ls-tree)
- br_url_cache/a555ec8c.md (source: https://git-scm.com/docs/git-merge-base)
- br_url_cache/ac3736c0.md (source: https://docs.gradle.org/current/userguide/java_testing.html#test_filtering)
- br_url_cache/e2769b8d.md (source: https://github.com/takahirom/roborazzi)
- br_url_cache/b8dcb4f8.md (source: https://robolectric.org/device-configuration/)
- br_url_cache/73cc8de1.md (source: https://developer.android.com/guide/topics/resources/providing-resources)
- br_url_cache/1d107a50.md (source: https://specifications.freedesktop.org/basedir-spec/latest/)
- br_url_cache/ab8d14b1.md (source: https://pkg.go.dev/os#Rename)
- br_url_cache/7de5f43e.md (source: https://developer.android.com/guide/topics/resources/providing-resources#AlternativeResources)
- br_url_cache/4c1fe5b5.md (source: https://coverage.readthedocs.io/en/latest/contexts.html)
- br_url_cache/f9779964.md (source: https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files)
- br_url_cache/fad102f0.md (source: https://go.dev/blog/cover)
- br_url_cache/8dd9623d.md (source: https://www.jacoco.org/jacoco/trunk/doc/)
- br_url_cache/f52255ac.md (source: https://git-scm.com/docs/git-log#Documentation/git-log.txt---name-status)
- br_url_cache/2bd24e9b.md (source: https://docs.pytest.org/en/stable/how-to/usage.html)
- br_url_cache/e393aa3d.md (source: https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags)
- br_url_cache/461f3c34.md (source: https://pkg.go.dev/cmd/go#hdr-Testing_flags)
- br_url_cache/510b5603.md (source: https://pkg.go.dev/cmd/go#hdr-List_packages_or_modules)
- br_url_cache/9182300a.md (source: https://kotlinlang.org/docs/multiplatform-run-tests.html)
- br_url_cache/c2a3e986.md (source: https://developer.android.com/studio/test/command-line)
- br_url_cache/8edb86ab.md (source: https://git-scm.com/docs/git-status)
- br_url_cache/9d9768b3.md (source: https://git-scm.com/docs/git-rev-parse)

## Active Dimensions
requirements_go_engine_and_cli, requirements_platform_binaries_in_release, requirements_dev_rebuild_from_source, requirements_annotation_freshness, requirements_high_level_tests_separate, assumption_go_toolchain_available, assumption_release_asset_reachable, assumption_git_history_is_freshness_clock, assumption_passing_run_anchors_edges, assumption_areas_express_suite_blast_radius, assumption_engine_latency_targets, component_go_engine, component_binary_distribution, component_freshness, component_suite_registry, tradeoff_two_toolchains, tradeoff_setup_network_fetch, tradeoff_area_glob_coarseness, tradeoff_flaky_pass_anchors, tradeoff_strict_version_handshake, requirements_go_engine, requirements_engine_packaging, requirements_engine_dev_regeneration, requirements_annotation_staleness, requirements_broad_test_handling, assumption_go_toolchain_ci_and_dev_only, assumption_release_assets_reachable, assumption_platform_matrix_sufficient, assumption_blob_digest_is_staleness_key, assumption_broad_tests_area_scoped, assumption_one_engine_per_framework_version, component_engine_binary, component_engine_packaging, component_staleness_tool, component_broad_test_scopes, tradeoff_engine_speed_enables_per_task_use, tradeoff_real_scheduler, tradeoff_noarch_packages_preserved, tradeoff_compiled_component_cost, tradeoff_engine_version_skew, tradeoff_stamp_churn, tradeoff_broad_scope_coarseness, tradeoff_autonomous_confirmation_weak, tradeoff_engine_absent_on_host, component_evidence_join, tradeoff_evidence_requires_reachable_history, requirements_screen_locale_subdivision, requirements_user_root, assumption_variant_universe_from_runner_list, assumption_axis_sources_declarable, assumption_kotlin_scanner_fail_closed, assumption_legacy_user_root_coexists, component_variant_axes, component_user_root, tradeoff_two_user_roots, tradeoff_axis_projection_coarseness, tradeoff_whole_run_filter_soundness, tradeoff_member_annotation_drift, requirements_framework_home_name, requirements_axis_product_selection, component_framework_home, component_axes, component_cell_enumeration, assumption_home_symlink_compatibility, assumption_axis_membership_declarable, assumption_cells_enumerable_by_plugin, tradeoff_home_migration_window, tradeoff_split_home_rejected, tradeoff_axis_declaration_burden, tradeoff_cell_table_size, tradeoff_intersection_can_underselect, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_onboarding_is_a_task, assumption_seed_sources_measured, assumption_seeds_select_never_evidence, assumption_test_tools_detectable, component_agent_brief, component_onboarding_skill, component_seeder, component_test_front_verb, component_workflow_integration, requirements_agent_run_surface, requirements_incremental_adoption, requirements_workflow_seam, requirements_zero_config_onboarding, tradeoff_accept_rewrites_history, tradeoff_generated_brief_limits, tradeoff_onboarding_partial_coverage, tradeoff_seed_noise, tradeoff_two_edge_states_during_adoption, tradeoff_workflow_surface_growth, assumption_annotation_is_comment_only, assumption_cochange_is_corroboration, assumption_full_run_expressible_per_repo, assumption_helpers_separable_by_fanin, assumption_instruction_block_is_read, assumption_static_closure_seeds_edges, assumption_task_resolvable_from_session, component_agent_instructions, component_completion_policy, component_onboarding_engine_verbs, component_qa_integration, component_test_entrypoint, component_workflow_seam, requirements_agent_instructions_seeded, requirements_onboarding_existing_tests, requirements_workflow_seam_is_data, requirements_zero_config_entrypoint, tradeoff_bulk_confirmation_granularity, tradeoff_dispatcher_verb_added, tradeoff_fallback_runs_more, tradeoff_one_gate_not_two, tradeoff_seed_precision, tradeoff_verify_build_wired_suites

## Dimension Keys
Use these dimension keys in section markers:
- assumption_annotation_is_comment_only
- assumption_areas_express_suite_blast_radius
- assumption_axis_membership_declarable
- assumption_axis_sources_declarable
- assumption_batch_per_unit_timing_reportable
- assumption_blob_digest_is_staleness_key
- assumption_broad_tests_area_scoped
- assumption_cells_enumerable_by_plugin
- assumption_change_surface_is_intake
- assumption_cochange_is_corroboration
- assumption_engine_latency_targets
- assumption_existing_locks_wrappable
- assumption_full_run_expressible_per_repo
- assumption_gate_exit_contract_reused
- assumption_git_history_is_freshness_clock
- assumption_go_toolchain_available
- assumption_go_toolchain_ci_and_dev_only
- assumption_helper_degrades_when_absent
- assumption_helpers_separable_by_fanin
- assumption_home_symlink_compatibility
- assumption_instruction_block_is_read
- assumption_instructions_block_reaches_agents
- assumption_kotlin_scanner_fail_closed
- assumption_legacy_user_root_coexists
- assumption_onboarding_is_a_task
- assumption_one_engine_per_framework_version
- assumption_passing_run_anchors_edges
- assumption_platform_matrix_sufficient
- assumption_release_asset_reachable
- assumption_release_assets_reachable
- assumption_seed_sources_measured
- assumption_seeds_select_never_evidence
- assumption_static_closure_seeds_edges
- assumption_static_granularity_v1
- assumption_target_repos_accept_aitestmap_root
- assumption_task_resolvable_from_session
- assumption_test_tools_detectable
- assumption_testmap_token_no_collision
- assumption_variant_universe_from_runner_list
- component_adoption_ledger
- component_agent_brief
- component_agent_instructions
- component_annotation_scanner
- component_axes
- component_binary_distribution
- component_broad_test_scopes
- component_cell_enumeration
- component_completion_policy
- component_cost_ledger
- component_dependency_scanners
- component_engine_binary
- component_engine_packaging
- component_evidence_join
- component_feedback_tools
- component_framework_home
- component_freshness
- component_gates
- component_go_engine
- component_onboarding_engine_verbs
- component_onboarding_skill
- component_qa_integration
- component_reference_runners
- component_registry_loader
- component_runner_contract
- component_scheduler_resources
- component_seeder
- component_selector
- component_skill
- component_staleness_tool
- component_suite_registry
- component_test_entrypoint
- component_test_front_verb
- component_user_root
- component_variant_axes
- component_workflow_integration
- component_workflow_seam
- requirements_agent_instructions_seeded
- requirements_agent_run_surface
- requirements_agent_skill
- requirements_annotation_freshness
- requirements_annotation_staleness
- requirements_axis_product_selection
- requirements_broad_test_handling
- requirements_cost_tracking
- requirements_dev_rebuild_from_source
- requirements_engine_dev_regeneration
- requirements_engine_packaging
- requirements_feedback_loop
- requirements_framework_home_name
- requirements_gate_enforcement
- requirements_generic_across_projects
- requirements_go_engine
- requirements_go_engine_and_cli
- requirements_high_level_tests_separate
- requirements_incremental_adoption
- requirements_onboarding_existing_tests
- requirements_platform_binaries_in_release
- requirements_reason_per_selected_test
- requirements_screen_locale_subdivision
- requirements_standard_runner_contract
- requirements_user_root
- requirements_workflow_seam
- requirements_workflow_seam_is_data
- requirements_zero_config_entrypoint
- requirements_zero_config_onboarding
- tradeoff_accept_rewrites_history
- tradeoff_area_glob_coarseness
- tradeoff_attribution_risk
- tradeoff_autonomous_confirmation_weak
- tradeoff_axis_declaration_burden
- tradeoff_axis_projection_coarseness
- tradeoff_batch_misreport_risk
- tradeoff_broad_scope_coarseness
- tradeoff_bulk_confirmation_granularity
- tradeoff_cell_table_size
- tradeoff_compiled_component_cost
- tradeoff_computed_vs_prose
- tradeoff_dispatcher_verb_added
- tradeoff_engine_absent_on_host
- tradeoff_engine_speed_enables_per_task_use
- tradeoff_engine_version_skew
- tradeoff_evidence_requires_reachable_history
- tradeoff_fail_closed_bootstrap_cost
- tradeoff_fallback_runs_more
- tradeoff_flaky_pass_anchors
- tradeoff_generated_brief_limits
- tradeoff_home_migration_window
- tradeoff_intersection_can_underselect
- tradeoff_member_annotation_drift
- tradeoff_noarch_packages_preserved
- tradeoff_onboarding_partial_coverage
- tradeoff_one_gate_not_two
- tradeoff_real_scheduler
- tradeoff_registry_directory_complexity
- tradeoff_resource_declaration_completeness
- tradeoff_seed_noise
- tradeoff_seed_precision
- tradeoff_setup_network_fetch
- tradeoff_split_home_rejected
- tradeoff_stamp_churn
- tradeoff_static_scanner_overselection
- tradeoff_strict_version_handshake
- tradeoff_two_edge_states_during_adoption
- tradeoff_two_toolchains
- tradeoff_two_user_roots
- tradeoff_verify_build_wired_suites
- tradeoff_whole_run_filter_soundness
- tradeoff_workflow_surface_growth

## Assigned Node ID
n011_explorer_005a

Use this exact value as the `node_id` field of your output YAML.
Do not invent a different id or modify it in any way.
