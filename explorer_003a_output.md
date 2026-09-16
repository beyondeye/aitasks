--- NODE_YAML_START ---
# n007_explorer_003a - node metadata
# Dimension provenance (every n006 dimension is carried; none dropped):
#   inherited unchanged from n006 (73):
#     assumption_areas_express_suite_blast_radius
#     assumption_axis_membership_declarable
#     assumption_axis_sources_declarable
#     assumption_batch_per_unit_timing_reportable
#     assumption_blob_digest_is_staleness_key
#     assumption_broad_tests_area_scoped
#     assumption_cells_enumerable_by_plugin
#     assumption_engine_latency_targets
#     assumption_existing_locks_wrappable
#     assumption_gate_exit_contract_reused
#     assumption_git_history_is_freshness_clock
#     assumption_go_toolchain_available
#     assumption_go_toolchain_ci_and_dev_only
#     assumption_home_symlink_compatibility
#     assumption_kotlin_scanner_fail_closed
#     assumption_legacy_user_root_coexists
#     assumption_one_engine_per_framework_version
#     assumption_passing_run_anchors_edges
#     assumption_platform_matrix_sufficient
#     assumption_release_asset_reachable
#     assumption_release_assets_reachable
#     assumption_static_granularity_v1
#     assumption_target_repos_accept_aitestmap_root
#     assumption_testmap_token_no_collision
#     assumption_variant_universe_from_runner_list
#     component_axes
#     component_binary_distribution
#     component_broad_test_scopes
#     component_cell_enumeration
#     component_evidence_join
#     component_framework_home
#     component_runner_contract
#     component_scheduler_resources
#     component_user_root
#     component_variant_axes
#     requirements_axis_product_selection
#     requirements_broad_test_handling
#     requirements_cost_tracking
#     requirements_dev_rebuild_from_source
#     requirements_engine_dev_regeneration
#     requirements_framework_home_name
#     requirements_go_engine
#     requirements_go_engine_and_cli
#     requirements_high_level_tests_separate
#     requirements_platform_binaries_in_release
#     requirements_screen_locale_subdivision
#     requirements_user_root
#     tradeoff_area_glob_coarseness
#     tradeoff_autonomous_confirmation_weak
#     tradeoff_axis_declaration_burden
#     tradeoff_axis_projection_coarseness
#     tradeoff_batch_misreport_risk
#     tradeoff_broad_scope_coarseness
#     tradeoff_cell_table_size
#     tradeoff_compiled_component_cost
#     tradeoff_engine_speed_enables_per_task_use
#     tradeoff_engine_version_skew
#     tradeoff_evidence_requires_reachable_history
#     tradeoff_flaky_pass_anchors
#     tradeoff_home_migration_window
#     tradeoff_intersection_can_underselect
#     tradeoff_member_annotation_drift
#     tradeoff_noarch_packages_preserved
#     tradeoff_real_scheduler
#     tradeoff_registry_directory_complexity
#     tradeoff_resource_declaration_completeness
#     tradeoff_setup_network_fetch
#     tradeoff_split_home_rejected
#     tradeoff_static_scanner_overselection
#     tradeoff_strict_version_handshake
#     tradeoff_two_toolchains
#     tradeoff_two_user_roots
#     tradeoff_whole_run_filter_soundness
#   modified from n006 (30):
#     assumption_change_surface_is_intake
#     component_annotation_scanner
#     component_cost_ledger
#     component_dependency_scanners
#     component_engine_binary
#     component_engine_packaging
#     component_feedback_tools
#     component_freshness
#     component_gates
#     component_go_engine
#     component_reference_runners
#     component_registry_loader
#     component_selector
#     component_skill
#     component_staleness_tool
#     component_suite_registry
#     requirements_agent_skill
#     requirements_annotation_freshness
#     requirements_annotation_staleness
#     requirements_engine_packaging
#     requirements_feedback_loop
#     requirements_gate_enforcement
#     requirements_generic_across_projects
#     requirements_reason_per_selected_test
#     requirements_standard_runner_contract
#     tradeoff_attribution_risk
#     tradeoff_computed_vs_prose
#     tradeoff_engine_absent_on_host
#     tradeoff_fail_closed_bootstrap_cost
#     tradeoff_stamp_churn
#   new in this node (21):
#     assumption_helper_degrades_when_absent
#     assumption_instructions_block_reaches_agents
#     assumption_onboarding_is_a_task
#     assumption_seed_sources_measured
#     assumption_seeds_select_never_evidence
#     assumption_test_tools_detectable
#     component_agent_brief
#     component_onboarding_skill
#     component_seeder
#     component_test_front_verb
#     component_workflow_integration
#     requirements_agent_run_surface
#     requirements_incremental_adoption
#     requirements_workflow_seam
#     requirements_zero_config_onboarding
#     tradeoff_accept_rewrites_history
#     tradeoff_generated_brief_limits
#     tradeoff_onboarding_partial_coverage
#     tradeoff_seed_noise
#     tradeoff_two_edge_states_during_adoption
#     tradeoff_workflow_surface_growth
node_id: n007_explorer_003a
parents:
- n006_synthesizer_002
description: 'n006 plus the missing adoption layer: an attended, resumable, task-shaped onboarding
  skill (aitask-testmap-onboard) that detects a repo''s test tools, generates aitestmap/ (runners,
  bindings, areas, config) and seeds edges from four measured sources (naming, literal invocation
  / imports, (t<id>) co-change history, opt-in per-unit coverage) into a generated seeded.yaml
  that selects immediately but never evidences; acceptance promotes seeds into testmap: lines
  in batches or incrementally inside the testmap_fresh gate; one agent-facing front verb (ait
  test --task|--all|<paths>|brief) plus a generic ''Running Tests'' section in the seeded
  agent-instructions block so every agent learns the run surface once; and a single workflow
  helper (aitask_affected_tests.sh) wired into task-workflow Step 7 behind an affected_tests
  profile key, aitask-qa''s test discovery/execution, and ait setup''s TESTMAP: state line
  - degrading to a reported skip wherever the engine or registry is absent.'
proposal_file: br_proposals/n007_explorer_003a.md
created_at: 2026-09-16 12:10
created_by_group: explore_003
reference_files:
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
- https://go.dev/doc/install
- https://go.dev/doc/install/source#environment
- https://go.dev/ref/mod#go-mod-file-toolchain
- https://go.dev/doc/go1.21#tools
- https://pkg.go.dev/gopkg.in/yaml.v3
- https://github.com/bmatcuk/doublestar
- https://pkg.go.dev/github.com/bmatcuk/doublestar/v4
- https://pkg.go.dev/golang.org/x/sync/errgroup
- https://github.com/actions/setup-go
- https://github.com/softprops/action-gh-release
- https://git-scm.com/docs/git-log
- https://git-scm.com/docs/git-hash-object
- https://git-scm.com/docs/git-ls-tree
- https://git-scm.com/docs/git-merge-base
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
- https://docs.gradle.org/current/userguide/java_testing.html#test_filtering
- https://github.com/takahirom/roborazzi
- https://robolectric.org/device-configuration/
- https://developer.android.com/guide/topics/resources/providing-resources
- https://specifications.freedesktop.org/basedir-spec/latest/
- https://pkg.go.dev/os#Rename
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
- https://developer.android.com/guide/topics/resources/providing-resources#AlternativeResources
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
- https://coverage.readthedocs.io/en/latest/contexts.html
- https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files
- https://go.dev/blog/cover
- https://www.jacoco.org/jacoco/trunk/doc/
- https://git-scm.com/docs/git-log#Documentation/git-log.txt---name-status
assumption_areas_express_suite_blast_radius: The blast radius of a high-level test is expressible
  as a union of area glob sets plus scope globs plus budget-exempt trigger globs, plus the
  reads globs of helpers in its test-file closure; what that misses surfaces through score
  on a full run as an observed trigger or area member (inherited from n005)
assumption_axis_membership_declarable: 'For a product-shaped suite, which facet value a source
  belongs to is declarable as globs by the people who own the suite, because the project already
  routes by exactly that shape - res/values-ar/** and font/cairo_*.ttf are the Arabic matrices''
  inputs and matrix_classes() already maps a matrix to its classes; aitasks'' .claude/ vs
  .opencode/ vs .agents/ trees are the agent facet. A source that matches no axis source is
  not an axis hit and reaches units only through edges and dependencies, which select every
  variant - the fail-safe direction n004 called ANY. Falsifier: a project whose membership
  is genuinely dynamic (a runtime flag choosing a locale), for which the answer is to declare
  no sources on that facet (n004''s general claim, of which assumption_axis_sources_declarable
  is the thinking_app instance)'
assumption_axis_sources_declarable: 'The sources that reach one facet value of an axis are
  declarable as globs in axes.yaml: for thinking_app''s locale facet, values-<q>/**, raw-<q>/**
  and the per-family fonts (heebo_* for he, roboto_* for en and ru, cairo_* for ar); sources
  every locale reads (values/**, TypeScale.kt, Fonts.kt, AppRoot.kt) are ordinary edges, scanned
  dependencies or one hand rule over values/** and reach every variant; the geometry and direction
  facets have no axis sources because they are test-side constants in ScreenshotTestHarness.kt,
  reached through the test-dep closure (inherited from n005)'
assumption_batch_per_unit_timing_reportable: Runners can report per-unit timing inside a batch
  from their tool's own report format (JUnit XML, go test -json, pytest junitxml), can invert
  a report row to a registered id (JUnit classname+name back to ScreenFixtures.kt#Welcome@pixel5Ru_ltr
  through the same routing table the runner's list verb printed), and the same JUnit XML reports
  each @Test method with its own duration, which is what makes a variant's marginal cost measurable
  separately from its class's boot - the number the invocation-group budget depends on (n005
  inversion, n004 per-method timing)
assumption_blob_digest_is_staleness_key: The git blob digest of the covered source's content
  is the staleness key; file mtime (reset by checkout) and the annotation date (day granularity,
  clock skew) are never compared - the date is display only; the blob id doubles as the join
  key into any commit's tree for the evidence join (inherited)
assumption_broad_tests_area_scoped: Integration, e2e and device tests can be described by
  named areas or globs whose membership changes rarely, so evidence-based drift (STALE_AREA)
  plus attribute widening is adequate; a calendar cadence (REVIEW_DUE, broad_review_days)
  is opt-in and off by default (inherited)
assumption_cells_enumerable_by_plugin: 'The variant universe a repo has is enumerable from
  the project''s existing single routing statement rather than a second hand-maintained list
  - and the enumerator is the runner''s list verb, not a separate plugin directory: thinking_app''s
  runner lists ~300 variant ids from matrix_classes() crossed with the two membership manifests,
  aitasks'' from its rendered tests/golden/ tree; the framework never infers a variant. Falsifier:
  a repo whose test methods are only knowable by running the build, for which list may exec
  the build''s own list task at the cost of a slower scan/check, since select never calls
  it (n004''s assumption, re-sited onto n005''s runner list)'
assumption_change_surface_is_intake: 'The change-surface script''s attribution (aitask_change_surface.sh)
  is the right intake for every --task path: the shim pipes COMMITTED:/TASK:/OTHER:/UNKNOWN:
  lines into --changes -, selection never reads a raw git diff, and an UNKNOWN: path refuses
  selection (n006); `ait test --task` and aitask_affected_tests.sh go through the same pipe,
  so the workflow''s affected run is attributed exactly as the gates are, and an UNKNOWN:
  row surfaces as VERDICT:skip REASON:unknown_paths naming the paths rather than a run over
  another task''s work; `ait test <path>...` is the one path-list intake (an explicit source
  or test list from the user or agent, treated as TASK: rows) and `ait test --all` has no
  intake'
assumption_engine_latency_targets: 'On the aitasks repo (about 720 test units, 2,500-3,000
  edges, about 270 scanned sources) the engine meets select < 200 ms warm, scan < 300 ms,
  check < 300 ms, stale --task < 300 ms, stale --all < 2 s, cold select < 1.5 s; on a thinking_app-shaped
  fixture (about 300 golden variants over 49 member units, about 370 JVM classes, about 900
  Kotlin files) select with axis expansion < 250 ms warm, reading the committed variants:
  lists and never executing a runner; pinned by committed go test -bench fixtures with a 2x
  regression failing engine-check.yml, validated before the gates are enabled (n005; n004''s
  2,500-row cell target dropped with the cell table)'
assumption_existing_locks_wrappable: Existing project locks and allocators (thinking_app's
  heavy-run lock with its exit-75 admission in tools/verification/heavy-run-lock.sh, emulator
  allocation in emulator-allot.sh) can be wrapped as resources without changing them; the
  Go admission and allocator kinds exec the project's commands and honour their exit codes,
  deferring on 75 until the run deadline; thinking_app's runner script goes through screenshot-tests.sh
  unit-tests, which reserves the slot itself (inherited)
assumption_gate_exit_contract_reused: The framework verifier contract (0 pass / 1 fail / 2
  skip / 3 error) is reused through two dedicated verifier shells, not through gate_command_exit_contract,
  which maps only command exits 0/1/2; runner exit 75 (admission refused, a thinking_app code
  absent from the framework) is deferred inside the engine and a final 75 maps to verifier
  3; only an empty selection maps to 2; a missing engine maps to 3, never skip (inherited)
assumption_git_history_is_freshness_clock: Git history is the evidence clock, not the staleness
  key - commit reachability (merge-base --is-ancestor) decides which last_pass anchors may
  suppress a STALE row, never whether an edge is stale; mtime is never compared; a shallow
  clone whose anchors are outside fetched history reports STALE, not EVIDENCED, and remains
  fully functional (inherited)
assumption_go_toolchain_available: 'A Go toolchain >= 1.26 is available in release CI through
  an actions/setup-go step this design adds to release.yml (go-version-file: engine/go.mod)
  and on framework developers'' machines; target-project users never need Go (inherited)'
assumption_go_toolchain_ci_and_dev_only: Go is a build-time dependency only - release.yml
  has no Go step today and the repo's only setup-go is hugo.yml's at website/go.mod's 1.25.7,
  so the engine job provisions its own toolchain; users receive prebuilt binaries and never
  compile (inherited)
assumption_helper_degrades_when_absent: 'aitask_affected_tests.sh can always answer: engine
  missing (ENGINE_MISSING from the shim) -> VERDICT:skip REASON:testmap_absent; no aitestmap/
  -> VERDICT:skip REASON:registry_absent; UNKNOWN: rows in the change surface -> VERDICT:skip
  REASON:unknown_paths naming them; empty selection -> VERDICT:skip REASON:no_selection with
  UNMAPPED_SOURCE lines; admission refused after the deadline -> VERDICT:skip REASON:admission_refused;
  only a run that executed maps to pass/fail, and only a helper that cannot write its LOG:
  exits 3. This is what lets the procedure sit in Step 7 of every profile including remote
  (Claude Code Web has no engine) without a conditional per environment'
assumption_home_symlink_compatibility: 'Every existing consumer of the legacy ~/.aitask tree
  keeps resolving unchanged when ~/.aitask becomes a symlink to ~/.aitasks, because all of
  them dereference a path rather than compare one - verified: the 35 references across 8 framework
  files (21 in aitask_setup.sh, 6 in python_resolve.sh, 3 in aitask_path.sh), the venv''s
  console-script shebangs (#!/home/<u>/.aitask/venv/bin/python3), the ~/.aitask/bin/python3
  wrappers, the ~/.aitask/python/<ver>/bin/python3 symlinks whose targets are absolute paths
  outside the home, and pyvenv.cfg''s informational command = line; no ==, !=, -ef, realpath,
  os.path.realpath or samefile on the home path anywhere under .aitask-scripts/, ait or install.sh.
  This is the precondition of ait engine home --migrate, re-checked by tests/test_aitasks_home.sh''s
  post-migration venv and PyPy-venv exercise before the default is flipped (n004''s assumption,
  verified and scoped to the verb)'
assumption_instructions_block_reaches_agents: The seeded agent-instructions block (seed/aitasks_agent_instructions.seed.md,
  installed to aitasks/metadata/ and assembled by assemble_aitasks_instructions()) is inserted
  between >>>aitasks / <<<aitasks markers into every supported agent's instructions file by
  ait setup and refreshed on re-run and on upgrade (insert_aitasks_instructions replaces the
  marked block) - verified in aitask_setup.sh - so a generic Running Tests section added to
  the seed reaches every onboarded and not-yet-onboarded project on its next setup with no
  per-project edit, and is the one always-loaded place an agent learns the run surface. The
  section names no code agent (documentation convention) and stays under 12 lines so it costs
  every session the same small context
assumption_kotlin_scanner_fail_closed: A closed construct list (explicit repo import, same-package
  as fully connected, repo star import as a package edge, fully-qualified in-body reference
  from the comment-stripped body) is enough to over-approximate the Kotlin import graph, and
  every construct that defeats such a graph - inline functions, const val, Hilt/DI bindings,
  Class.forName / ::class.java, generated or KSP sources, an unreadable or untokenizable file
  - is detectable by pattern and marks the file opaque, so a change to it escalates instead
  of being silently narrow; measured on thinking_app, 42 main files declare const val or inline
  fun and 63 carry DI annotations, so escalation is frequent by design; each opaque branch
  is reachable and red-proved by an engine fixture test (inherited from n005, cost measured)
assumption_legacy_user_root_coexists: In this release ~/.aitasks/ (engine) and ~/.aitask/
  (venv, pypy_venv, python, bin, uv, dev_tier, update_check; 8 framework code files with 35
  references name it, plus 20 test and 18 doc files) coexist on one host without either reading
  the other; the migration of the legacy tenants exists as ait engine home --migrate but is
  not run by ait setup by default, and nothing in this feature depends on it having happened
  (n005; the default flip is a named follow-up)
assumption_onboarding_is_a_task: 'Onboarding writes committed files (aitestmap/**, test-file
  comment lines, a profile edit) across several sessions, so it runs as an aitask: /aitask-testmap-onboard
  with no argument creates and claims `testmap_onboarding` (issue_type chore, label testmap)
  through aitask_create.sh --batch and aitask_pick_own.sh, records the task id in onboard.yaml,
  and every phase commits its files under `chore: Onboard testmap - <phase> (t<id>)` so the
  change surface attributes them and a resumed session re-enters at ONBOARD_NEXT; the task
  is archived by `onboard finish`. Falsifier: a repo that forbids tasks on the code branch
  - for which --no-task writes without committing and prints the commit lines to run'
assumption_one_engine_per_framework_version: One engine build per framework version suffices;
  a per-user versioned directory ($AITASKS_HOME/engine/v<VERSION>/) resolves per-project VERSION
  differences without a compatibility matrix, and exact-version resolution in the shim never
  falls back to newest-wins (inherited, root corrected)
assumption_passing_run_anchors_edges: A passing run of a test variant at commit C, on any
  host class, from an invocation without a cause and for an id under the flake threshold,
  is evidence that its annotated edges held for that variant against the source content present
  in C's tree - so an edge whose current blob equals the blob at C is EVIDENCED for that variant
  without touching the test file; a unit with variants is EVIDENCED only when every variant
  the change reaches has such a pass; a verify-active full run's child rows anchor all 297
  goldens at once (inherited from n005)
assumption_platform_matrix_sufficient: linux/darwin x amd64/arm64 covers every target host
  (WSL reports Linux); any other platform builds from source via --engine-from-source (inherited)
assumption_release_asset_reachable: A host running ait setup or ait upgrade can reach github.com/beyondeye/aitasks/releases
  over HTTPS, as it already must for the framework tarball; the shim itself never downloads,
  so a gate run never performs a network fetch (inherited)
assumption_release_assets_reachable: Air-gapped or off-matrix hosts supply the binary via
  --local-engine, --engine-from-source, AIT_TESTMAP_BIN or a pre-seeded $AITASKS_HOME/engine/;
  --no-testmap / AIT_TESTMAP_FETCH=0 skip the fetch and nothing else in setup depends on it
  (inherited, root corrected)
assumption_seed_sources_measured: 'Four heuristic origins seed edges, each measured on 2026-09-16
  and none trusted alone: naming (test_<x>.sh -> aitask_<x>.sh / lib/<x>.{sh,py}: 72/400 aitasks
  bash tests; test_<x>.py -> <x>.py: 62/320 aitasks Python tests; <Stem>Test.kt -> <Stem>.kt:
  48/307 thinking_app tests), literal invocation (a bash test naming an .aitask-scripts path:
  350/400, avg 3 distinct paths), imports (255/320 aitasks Python tests import a resolvable
  module, avg 1; 139/339 thinking_app tests import a resolvable main file, avg 3 - same-package
  references are invisible to imports and are NOT seeded because the package-connected fact
  is too coarse), and (t<id>) co-change (aitasks: 439 of 600 task commits touch tests and
  scripts together, avg 2.8 scripts x 2.6 tests, tight; thinking_app: 127 of 400, avg 7.2
  main files, noisy - hence min_cochange 2 and the lowest base confidence). Per-unit runtime
  coverage (coverage.py dynamic contexts, go -coverprofile per -run) is the fifth, opt-in,
  highest-confidence origin where the tool supports it; JaCoCo per-test sessions are a project
  plugin. Confidence is a fixed table combined by noisy-OR and orders the review queue; it
  never hides a row. Seeding is partial by construction: the remainder is rules, waivers and
  incremental accept'
assumption_seeds_select_never_evidence: 'A seeded edge is safe to act on in exactly one direction:
  it may cause a test to run (over-selection costs time) and may never suppress a STALE row,
  anchor evidence, satisfy require_stamp or count as coverage for UNMAPPED_SOURCE under --strict
  (under-claiming a freshness fact costs correctness). So seeds live in a generated file,
  carry no stamp, are excluded from stale, are counted separately by check, and become claims
  only through an explicit accept that writes the line and the stamp. Falsifier: a project
  whose full suite is so expensive that seeded over-selection is itself the cost problem -
  for which the suite budget and --format tokens preview are the levers, not trusting seeds'
assumption_static_granularity_v1: 'Static file-level facts remain the default for v1, with
  two narrower granularities in use rather than reserved: a member unit (<path>#<member>,
  annotations scoped by testmap:unit blocks, no language parsing) and the edge''s symbols
  slot, whose first consumer is the opt-in android-res scanner that names the string keys
  a values-<q>/ diff changed; no scanner produces symbol-level coverage of Kotlin or Python
  code; a change anywhere in a member file is a change to every member until hunk-level attribution
  exists (n005; n004''s plugin exception subsumed by the runner list)'
assumption_target_repos_accept_aitestmap_root: Every target repo will accept a root aitestmap/
  directory of YAML committed into its code tree, including an optional axes.yaml; runner
  scripts and axes are both optional (a repo with no product space declares none and gets
  exactly n003's behaviour) because the reference runners are built into the engine; thinking_app
  commits one runner script (tools/verification/testmap_runner.sh) because its lowering is
  the harness's own routing (merged)
assumption_test_tools_detectable: 'The test tools of every target repo are detectable from
  the tree and the project config without executing a build: pytest.ini / pyproject [tool.pytest]
  / tests/*.py with a runner script; go.mod plus *_test.go; gradlew plus src/<sourceSet>/
  test roots (commonTest, androidHostTest, androidDeviceTest, test, androidTest); tests/test_*.sh
  with tests/lib/asserts.sh; package.json scripts.test; a Makefile test target; and project_config.yaml
  test_command / verify_build. Verified on the five repos: aitasks (bash + pytest via run_all_python_tests.sh),
  thinking_app (gradlew + the screenshot harness named by test_command), thinking_backend
  (run_script_tests.sh named under verify_build - detect proposes moving it to test_command
  with confirmation), aitasks_go (Makefile test = go test ./... plus parity/run_parity.sh),
  aitasks_mobile (three gradle source-set roots, no test_command). Falsifier: a build-only
  test discovery (tests generated at build time), for which detect emits DETECT_UNKNOWN and
  the skill asks'
assumption_testmap_token_no_collision: The annotation token 'testmap:' does not collide with
  existing prose comments in any target repo; the 38 existing '# Covers:' headers in aitasks
  are behavioural prose and are not matched; thinking_app's KDoc mentions no 'testmap:' string
  (inherited)
assumption_variant_universe_from_runner_list: 'A runner''s list verb enumerates the complete
  universe its run filter can address, so whole-run selection is sound: for thinking_app that
  is every <Screen>_<matrix>.png of the two membership manifests (50 + 247 goldens over 10
  matrices) as variant ids plus every other class under app/src/test/java as a file unit;
  a class absent from list is a check failure (UNREGISTERED), never a silently unfiltered
  one; scan --apply persists each member''s listed variants so select reads the committed
  table and only scan and check exec list (inherited from n005; persistence from n004''s committed-table
  property)'
component_agent_brief: 'Agent brief and instructions: `ait testmap brief [--md]` (alias `ait
  test brief`) prints TESTMAP:<state>, one RUNNER:<name>|<kind>|<units>|<how it is invoked>|<resources>
  line per runner, FULL_GATE:<runner>|<p95 est>|<= project_config test_command>, VERBS: (the
  four forms), AXES: per declared axis with facets and value counts, RESOURCE: per declared
  resource with its kind and what a refusal looks like (exit 75 -> deferred), DOCS:<path>
  per config.yaml docs: entry, NOTES: the config.yaml notes: lines verbatim (<=10, project-declared,
  e.g. thinking_app''s ''a shared component change must run the full gate; preview is a render
  loop with no verdict''), and, while bootstrapping, ONBOARD_NEXT:; --md renders the same
  as markdown for agents; the seeded agent-instructions block gains a generic `## Running
  Tests` section (the four verbs, ''run `ait test brief` before invoking a test tool directly;
  prefer the registered runner'', ''a new test file needs testmap: annotations - /aitask-testmap'',
  ''TESTMAP:absent means not onboarded - /aitask-testmap-onboard''), identical in every project;
  tests/test_agent_instructions_running_tests.sh pins the section through a real install.sh
  --dir (new)'
component_annotation_scanner: 'Annotation scanner and rewriter (internal/annot): grammar v3
  with testmap:unit blocks, kind/covers/area/scope/trigger/reads/axis/reviewed/runner/needs/batch,
  per comment leader and Python docstrings, unknown keys refused with a line number, the line-targeted
  rewriter with REWRITE_CONFLICT, annotate --from-body (n006); new: `onboard accept` writes
  the accepted seeds of a file as testmap:covers lines through the rewriter - inserted after
  the file''s existing header comment block (bash: after the shebang and leading # block;
  Python: appended to the module docstring; Kotlin: a // block before the class KDoc, or inside
  the member''s testmap:unit block for a member seed), each stamped @<date>/<blob10> at accept
  time, one file rewritten per accepted batch item; existing ''# Covers:'' prose headers in
  aitasks are shown beside the seeds as reviewer context and are never parsed or rewritten'
component_axes: 'Axis resolver verbs (internal/axes): ait testmap axes --list prints every
  declared axis with its facets, values and the variant count each value has in list; --check
  runs the axis rules (DEAD_AXIS_SOURCE, UNKNOWN_VARIANT, UNCOVERED_VALUE); --explain <path>
  prints AXIS:<axis>.<facet>|<value or ->|<why> per facet for one file - which glob matched,
  or that no source is declared - so a maintainer sees where a file lands before anything
  is trusted; n004''s resolve(changeSet) -> set | ANY is the SourcesHit join read the other
  way, with ANY printed as - and meaning no axis hit (n004''s verbs re-sited onto the variant-axes
  table)'
component_binary_distribution: 'Binary distribution: engine/build.sh as the single build and
  matrix command; the engine job in release.yml (setup-go from engine/go.mod, go vet, go test,
  build.sh all) producing ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and ait-testmap_<V>_SHA256SUMS.txt
  attached by both action-gh-release steps with release needs: [plan, engine]; the unchanged
  VERSION-matches-tag guard; a new engine-check.yml on push/pull_request for engine/** (gofmt,
  vet, test, 2x bench rule); lib/platform_detect.sh; the shim''s strict handshake (AIT_TESTMAP_BIN
  with override notice > AIT_ENGINE=dev slot at $AITASKS_HOME/engine/dev/ requiring <V>-dev+<sha>
  > $AITASKS_HOME/engine/v<V>/ requiring == VERSION > ENGINE_MISSING:<path> exit 3 with repair
  hint); tests test_testmap_shim.sh (extended with an AITASKS_HOME host), test_platform_detect.sh
  and test_aitasks_home.sh; aidocs/framework/go_engine.md, a CLAUDE.md Engine block and a
  packaging_strategy.md paragraph naming ~/.aitasks/engine/; release-packaging.yml and nfpm
  arch: all untouched (inherited from n005)'
component_broad_test_scopes: 'Broad-test scheduling and staleness policy: kind integration|e2e|device
  selects the scoped association form; broad_after_unit: true waves run scoped rows only after
  a green unit wave; device_policy: filter_by_resource default; scoped rows are exempt from
  per-edit digest staleness, with STALE_AREA as the evidence-based drift signal and REVIEW_DUE
  as an opt-in cadence; attribute widens areas by evidence; covers on a scoped row is allowed
  for digest-stamped fixture pins; a suite row (thinking_app''s verify-active) marked full:
  true with a children: post-processor anchors registered ids on every run; variant-bearing
  units are unit kind, never area-scoped, and ride the unit wave with admission-holding invocations
  ordered last (merged from n004 and n005)'
component_cell_enumeration: 'Enumeration and reconciliation: there is no aitestmap/cells/
  directory and no _cells.yaml - the project''s runner list verb is the enumeration surface
  and scan --apply persists its output as the variants: list on each member row of _scanned.yaml
  (49 rows with at most ten values for thinking_app), so select never execs a runner and only
  scan and check call list; what n004''s enumeration bought - two-way reconciliation - is
  kept as UNCOVERED_VALUE:<axis>|<value> (a declared value no runner lists) and UNMAPPED_ARTIFACT:<path>|<runner>
  (a file matching a runner''s declared artifact_glob: that no listed id''s artifact column
  claims), both failing check --strict after bootstrap; thinking_app''s list reads the two
  membership manifests and matrix_classes, every fact from a file the project already guards
  (n004''s component, re-sited onto n005''s runner list)'
component_cost_ledger: Cost ledger as n006 (Welford per (id, host class) with P2 p95 and last;
  .aitask-testmap/ledger.jsonl per result and per invocation; costs --update; last_pass and
  flake per id; group costing; costs/predictions.yaml); an `ait test` run writes ordinary
  rows (run_id prefixed test- for the workflow's affected runs, full- for --all) so Step-7
  runs feed cost and evidence exactly like gate runs, and the SELECTED:<n>|<est_s> line's
  estimate is the same per-group sum the budget uses
component_dependency_scanners: Dependency scanners (internal/deps) as n006 (bash, python,
  go, kotlin with the opaque contract, Gradle module graph, plugins, the opt-in android-res
  symbol scanner, XDG blob-keyed cache); the bash scanner's literal-invocation facts (a test
  that runs ./.aitask-scripts/x.sh or sources lib/y.sh) and the python/kotlin/go scanners'
  direct imports of a main-root file are exposed to internal/seed as the invocation and imports
  origins - same scan, same cache, read once; the deeper closure stays the selector's d2 walk
  and is never seeded as an edge
component_engine_binary: 'Engine binary identity and budget as n006 (version/commit/contract
  embedded; version --json prints ENGINE:<path>; fixed-prefix output; CONTRACT_MISMATCH; go
  test -bench budgets with the 2x rule; pools capped at 8) with the verb table extended by
  test, brief, seed, onboard {detect,inventory,status,accept,reject,finish} and runner scaffold;
  budgets added: brief < 100 ms warm, seed --from naming,invocation,imports < 2 s on the aitasks
  shape, seed --from cochange < 5 s over 600 (t<id>) commits (one git log --name-status -M
  --grep pass, parsed once, cached by HEAD sha under the XDG cache), onboard status < 200
  ms; contract stays 1 (seeded.yaml and onboard.yaml carry their own contract: field and a
  newer one is refused the same way)'
component_engine_packaging: 'Engine install and developer regeneration as n006 (install_engine_binary()
  reached by ait setup and ait upgrade; source order; checksum; atomic install; version self-check;
  --no-testmap; HOME_LEGACY: hint; aitask_engine.sh build|test|cross|prune|home; tests/test_install_engine_binary.sh
  through a real install.sh --dir) plus report_testmap_state() run after it: prints TESTMAP:engine-missing
  when the binary is absent, TESTMAP:absent (with `run /aitask-testmap-onboard`) when aitestmap/
  is absent, TESTMAP:bootstrapping|<next phase> while onboard.yaml has an unfinished phase,
  and TESTMAP:onboarded otherwise; the seeded agent-instructions block re-inserted by setup
  gains the Running Tests section; tests/test_install_engine_binary.sh asserts the TESTMAP:
  line in each state and a new tests/test_agent_instructions_running_tests.sh asserts the
  section lands in CLAUDE.md / AGENTS.md through a real install.sh --dir'
component_evidence_join: 'Evidence join (internal/stale + internal/gitx, reads internal/cost):
  for every edge whose stamped_blob differs from the current blob, collects last_pass shas
  per reached variant from the local ledger and committed costs (any host class), drops candidates
  from invocations with a cause or ids over the flake threshold, keeps shas that are ancestors
  of HEAD, and runs one git ls-tree per distinct sha; an edge is EVIDENCED when every reached
  variant has a sha whose source object id equals the current blob, otherwise STALE with the
  unevidenced variants listed; never rewrites - stale --confirm-evidenced is the explicit
  re-stamp and the only bulk confirmation an autonomous profile may run (inherited from n005)'
component_feedback_tools: 'Feedback tools (internal/feedback): score (automatic after run
  --all and after a full: true suite run), attribute (missing-edge / test-wrong / source-wrong,
  missing-axis-source widen-only, missing-trigger / area-too-narrow), readiness (n006); new:
  an attribute decision may be `propose` (default in autonomous profiles) which writes the
  row to seeded.yaml with origin observed and the run id as evidence instead of to observed.yaml,
  so autonomous runs grow the review queue and never the accepted map; `onboard status` reports
  phase states, seed queue counts per origin, tests-with-any-edge and sources-with-any-edge
  ratios, oldest pending seed age, and ONBOARD_NEXT:<phase>'
component_framework_home: 'Framework home report and migration verb (aitask_engine.sh): ait
  engine home prints HOME_ROOT:<path>, HOME_LEGACY:<path>|<tenants found>, HOME_SYMLINK:none|<target>
  and HOME_NEXT:<what --migrate would do>; ait engine home --migrate runs n004''s algorithm
  under flock $AITASKS_HOME/.home.lock - refuses and reports no-legacy-root, already-migrated,
  foreign-symlink:<target>, cross-device or unknown-entry:<name>; moves each present entry
  of the known set {venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine} with
  a same-device mv, rmdir''s the emptied legacy root and leaves ln -s $AITASKS_HOME ~/.aitask
  behind; prints HOME_MIGRATED:<n> or HOME_SKIPPED:<reason>. pypy_venv is the correction to
  n004''s set: setup_pypy_venv() creates it, python_resolve.sh reads it, and the host this
  was designed on carries it, so n004''s migration would have refused here. In this release
  ait setup only prints HOME_LEGACY:<path>|run ''ait engine home --migrate''; the follow-up
  that flips the default (reserving --no-home-migration / AIT_HOME_MIGRATE=0) is admitted
  when tests/test_aitasks_home.sh, run through a real install.sh --dir, covers fresh install,
  migration with a working venv and PyPy venv afterwards, idempotent re-run, a hostile pre-existing
  symlink, cross-device refusal and the AITASKS_HOME override, and updates the 18 doc files
  naming ~/.aitask (inherited from n004, made explicit and deferred; known set corrected)'
component_freshness: 'Freshness as n006 (per-edge @<date>/<blob10> stamp written only by verify,
  annotate and stale --confirm*, scoped to the member block; variants carry no stamp; last_pass
  per id; bootstrap_until, require_stamp, flake_threshold; the testmap_fresh procedure gate
  dispatched before the change summary so rewrites ride the (t<id>) commit; not a git hook,
  not a code-agent hook) with one more stamp writer, `onboard accept`, and one more gate step:
  testmap_fresh offers to accept the seeds of the test files this task touched - the stamp
  then rides the same (t<id>) commit as the test edit, which is the moment the accepter has
  the file open and the claim is cheapest to check'
component_gates: 'Gates: testmap_fresh (procedure), testmap_check (machine, max_retries 0,
  timeout 120, unlocks [testmap_run]) and testmap_run (machine, blocks_dependents, max_retries
  1, timeout 1800) in gates_reference.yaml synced to gates.yaml; two bash verifiers on the
  tests_pass template mapping engine exits 0/1/2/75/64 and a missing engine to verifier 0/1/2/3/3/3;
  run_gate_admission + readiness (n006). New rows in testmap_check: SEEDED:<n> (informational,
  never fails), UNMAPPED_SOURCE:<path> (a changed source with no edge, seed, rule or waiver
  - reported during bootstrap, fails under --strict past bootstrap_until), and the strict
  flip is the onboarding `finish` phase''s act, not a hand edit; the verifiers are unchanged
  - the onboarding skill''s `enable` phase is what adds testmap_check/testmap_fresh to the
  chosen profile''s default_gates (and rendered_gates when present) with confirmation, and
  testmap_run only when readiness is ADMISSIBLE (merged from n006; SEEDED / UNMAPPED_SOURCE
  rows and gate enabling sited in onboarding)'
component_go_engine: 'Go engine and CLI: engine/cmd/ait-testmap with the n006 packages internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}
  plus internal/seed (the four seed origins and their confidence table), internal/onboard
  (detect, inventory, the phase ledger, accept/reject, status, finish) and internal/brief
  (the generated run brief); Go 1.26, CGO_ENABLED=0, yaml.v3 + doublestar + x/sync only, line-protocol
  stdout, --json, per-verb exit contracts; never writes aitasks/, aiplans/, .aitask-data/
  or a gate ledger, never invokes aitask_*.sh - onboard''s task creation and profile edit
  are done by the skill through the framework''s own scripts, the engine only reads onboard.yaml''s
  task: field; fixture repos in t.TempDir() include synthetic git histories with (t<id>) commits
  for the cochange origin and one fixture per detect shape (bash-only, pytest, go, gradle,
  gradle-per-source-set)'
component_onboarding_skill: 'Onboarding skill and verbs: .claude/skills/aitask-testmap-onboard/
  (static, attended-only; SKILL.md + one procedure file per phase) driving `ait testmap onboard
  detect [--write] | inventory | status | accept | reject | finish` and `seed`; phases recorded
  in aitestmap/onboard.yaml {contract, task, phases{detect,inventory,classify,seed,waivers,full_run,accept,enable,finish:
  {status, at, by, counts}}, rejections[]}: detect writes the aitestmap/ skeleton and a runner
  table the user confirms per runner (keep / edit command / drop) with the existing test_command
  wrapped as the `full` suite runner; inventory runs scan + every list, resolves UNREGISTERED
  files by binding or exclude: glob, classifies broad candidates per batch of 20 with the
  reason line; seed runs the origins and reports counts; waivers proposes rules for hot directories
  and expiring waivers for unmapped sources; full_run executes `ait test --all` (child rows
  anchor, costs --update, no prediction to score); accept reviews seeds per area with evidence,
  `--batch 50` at a time, writing lines through the rewriter and one commit per batch; enable
  adds testmap_check and testmap_fresh to the chosen profile''s default_gates / rendered_gates
  with confirmation, sets bootstrap_until (+30 days), records docs: and notes: for the brief;
  finish requires status green, flips require_stamp and --strict, archives the task. Re-entry
  is ONBOARD_NEXT; every phase is idempotent on re-run; wrappers regenerated for Codex and
  OpenCode (new)'
component_reference_runners: 'Reference runners built into the binary (bash-file, pytest with
  junitxml and the serial carve-out pinned, go-test, gradle-class with JUnit inversion and
  the zero-match trap, suite with children: post-processor, device with allocator handle;
  command:/cwd: overrides; shadow-by-name; engine-test) and thinking_app''s project runner
  (n006); new: `ait testmap runner scaffold <builtin> --as <name>` emits aitestmap/runners/<name>.sh
  whose describe and run exec the builtin and whose list is a stub printing SCAFFOLD_TODO
  until the project fills it (check reports it), and `onboard detect` generates a `full: true`
  suite runner named `full` wrapping project_config.yaml test_command (or verify_build when
  it is the only test-running key, thinking_backend''s case, with confirmation) whose children:
  post-processor is a builtin that inverts pytest junitxml, bash-file test names from the
  per-file exit and `go test -json` events to registered ids, so the existing full gate anchors
  evidence without a project script; the bash-file builtin gains a `list --invocations` mode
  printing the literal .aitask-scripts/ paths a test references (the seeder''s invocation
  origin)'
component_registry_loader: 'Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  plus axes.yaml into the six n006 tables (edges, scopes, areas, rules, waivers, axes) and
  a seventh, seeds, loaded from registry/seeded.yaml (rows {test, covers, origin[], confidence,
  evidence{}, proposed_at}); a seed whose (test, covers) pair also exists as an accepted edge
  is dropped at load with SEED_SHADOWED reported by check; write routing gains seed -> seeded.yaml
  and onboard accept/reject -> seeded.yaml (row removed) + onboard.yaml (rejection recorded
  so the seeder never re-proposes it); config.yaml gains exclude: globs (fixtures, helpers,
  generated tests - never listed, never UNREGISTERED), docs: (paths the brief prints) and
  notes: (<=10 lines of project-declared test guidance the brief prints verbatim); unit ids,
  owns: routing, deterministic writes and the n006 check rules are unchanged; golden tests
  pin the seed table merge and the shadow rule (n006 + seeds table)'
component_runner_contract: 'Runner contract and repository (internal/runner): describe (unit
  file|class|method|variant|suite, axis:, batch, needs, group_by: (n004), token_format:, filter_scope:,
  full:, children:, artifact_glob: (n004)), list as TSV <id> <kind> <lowering> [<artifact>]
  with member and variant ids, run --manifest with ids, lowerings and groups, results.jsonl
  per id with optional child rows under a suite parent, runner.json with per-group overhead
  rows, first-match bindings and per-test override, the builtin: scheme with command:/cwd:
  overrides and shadow-by-name, batching by (runner, group, resource set, batch flag), per-unit
  timeouts, units_expected/units_reported reconciliation per id with zero-reported-some-expected
  and no-registered-id as mechanism failures, exit contract 0/1/2/75 plus 64 (merged from
  n004 and n005)'
component_scheduler_resources: 'Scheduler and resources (internal/sched): kinds mutex/semaphore/admission/allocator,
  scopes host/worktree/run, acquired_by planning; flock(2) slot files taken in canonical order;
  admission exec with 75 deferral and backoff to the run deadline; allocator exec with signal-safe
  release; goroutines under errgroup; batching (variants of one runner and resource set batch
  into one invocation per group_by group, so thinking_app''s whole selection is one Gradle
  run holding one heavy-run slot); broad_after_unit waves with variant-bearing units in the
  unit wave and, within a wave, invocations holding an admission resource ordered last (the
  ordering half of n004''s placement rule); config concurrency: serial|parallel defaulting
  to serial at bootstrap with --serial/--parallel overrides; the schedule report and its check
  half (inherited from n003; ordering refinement)'
component_seeder: 'Seeder (internal/seed): `ait testmap seed [--from naming,invocation,imports,cochange,coverage]
  [--min-cochange 2] [--coverage-report <f>|--per-unit] [--apply]` produces registry/seeded.yaml
  rows {test[#member], covers, origin[], confidence, evidence{naming: pair, invocation: file:line,
  imports: file:line, cochange: [task ids], coverage: run id}, proposed_at}; naming applies
  per-runner stem rules (bash-file: test_<x>.sh -> aitask_<x>.sh|lib/<x>.sh|lib/<x>.py; pytest:
  test_<x>.py -> any <x>.py under the main roots; go-test: <x>_test.go -> <x>.go same dir;
  gradle-class: <Stem>[Test|*Test].kt -> <Stem>.kt under main); invocation and imports read
  internal/deps facts for the test file only (direct, never the closure); cochange parses
  one `git log --name-status -M --format=%H%x00%s` pass over commits whose subject matches
  (t<id>) and counts (test, source) pairs across distinct tasks, cached by HEAD sha; coverage
  imports coverage.py contexts JSON, go -coverprofile per unit and LCOV with a test-id column,
  or a project plugin''s {test, covers} lines; confidence table naming 0.6 / invocation 0.9
  / imports 0.85 / cochange 0.5 + 0.1 per extra task to 0.8 / coverage 0.95 / observed 0.7,
  noisy-OR across origins; a rejected pair in onboard.yaml is never re-proposed; a pair already
  accepted is dropped with SEED_SHADOWED; --apply writes, otherwise prints SEED:<test>|<source>|<origins>|<confidence>
  lines (new)'
component_selector: 'Selector (internal/selectr, internal/changesurface): n006 unchanged -
  line-protocol intake refusing UNKNOWN:, the graded walk with select/implies/escalate rules,
  variant expansion and axis join, test-dep at d1, ESCALATE on opaque files, scoped join,
  kind-then-cost ranking, invocation groups, stale marks, --include-stale, suite budget with
  DEFERRED lines, cut knobs incl. --axis, --format lines|json|tokens, prediction record, explain
  - plus: a seeded edge is walked exactly like an annotation edge at d1 with reason edge(seeded:<origins>)
  and never contributes a stale mark; `explain --sources <path>...` prints the reverse view
  (every unit reaching each source with its reason, or UNMAPPED_SOURCE) as the table aitask-qa''s
  test discovery consumes; and the `test` composite verb prints one SELECTED:<n>|<est_s>|<seeded_n>
  line and UNMAPPED_SOURCE:<path> lines before the ranked rows so the workflow helper can
  build its VERDICT without parsing the rows'
component_skill: 'Skills: aitask-testmap (n006: annotate a file / member / coordinate, declare
  axis sources, reads on helpers, axes --explain, attribute before the gate, verify after
  editing, classify --suggest, select --format tokens into a render loop) now opens with `ait
  test brief` and hands a repo without aitestmap/ to aitask-testmap-onboard; aitask-gate-testmap-fresh
  (the procedure gate: stale --task, git diff per STALE row with unevidenced variants, retarget
  STALE_PATH, re-stamp EVIDENCED, resolve check''s structural rows by editing axes.yaml /
  the runner''s list / the member block, prompt on UNSTAMPED past bootstrap, never guess UNKNOWN,
  never confirm STALE autonomously) gains one step: for each COMMITTED:/TASK: test file with
  rows in seeded.yaml it shows the seeds with their evidence and offers accept / reject /
  leave per row, so a map migrates a few files per task through ordinary work; the new aitask-testmap-onboard
  is a static, attended-only skill (no profile stub: its every phase is a judgement call)
  documented in component_onboarding_skill; all three ship Claude Code first with wrapper
  surfaces regenerated by aitask_audit_wrappers.sh apply-wrapper for Codex and OpenCode (merged
  from n006; onboarding and accept-in-gate added)'
component_staleness_tool: Staleness tool (internal/stale) as n006 (stale --task --changes
  - | --all; the line classes with %25/%7C encoding; unevidenced variants on STALE rows; CHECK_STRUCTURAL:<n>
  on --all; --strict exits 1 on STALE_PATH; rename hints and culprits from git log -M; --confirm,
  --confirm-source, --confirm-evidenced, --retarget) with seeded edges excluded from every
  class and one SEEDED:<n> summary line on --all
component_suite_registry: 'Scoped-row registry and areas as n006 (areas.yaml seedable via
  areas --import-codemap; _scoped.yaml rows with reads_from; owns: by area; the d1 join; suite
  budget with DEFERRED; DEAD_SCOPE and KIND_MISMATCH|CONVERT_TO_SUITE; classify --suggest
  with the reads-helper and grid heuristics; missing-trigger / area-too-narrow); classify
  --suggest gains the three signals onboarding''s classify phase uses - a recorded p95 above
  broad_threshold_s (default 60) from the first full run, a source-set or directory convention
  (androidTest/, androidDeviceTest/, *_live.py, *_integration.sh, parity/) and a resource
  declaration in the file (tmux, emulator, docker, network) - each printed as the reason on
  the CLASSIFY:<test>|<kind>|<reason> line the skill confirms per batch'
component_test_front_verb: 'Front verb and workflow helper: `ait test` in the dispatcher ->
  aitask_testmap.sh test -> engine `test` composite: --task <id> pipes the change surface,
  refuses UNKNOWN:, select --include-stale -> schedule -> run, prints SELECTED:<n>|<est_s>|<seeded_n>,
  UNMAPPED_SOURCE:<path>, the ranked rows, then RESULT:pass|fail|skip|deferred with the run
  id; <path>... treats explicit paths as TASK: rows (a test path runs that unit and its variants);
  --all runs every registered unit through the runners (the same machinery as run --all, anchoring
  evidence and scoring the newest prediction); brief prints the run brief; --mode show stops
  after select; --json. .aitask-scripts/aitask_affected_tests.sh <task_id> [--mode run|show]
  is the workflow seam: sources lib/aitasks_home.sh and the shim, runs `ait test --task`,
  writes the log to .aitask-gates/<task>/affected_<run-id>.log, prints VERDICT:pass|fail|skip
  / REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
  / DETAIL: / LOG: / SELECTED:<n>|<est_s> / UNMAPPED_SOURCE: lines, exits 0/1/2/3 with the
  aitask_run_project_command.sh capture contract, appends nothing to any ledger; allowlisted
  on the five touchpoints; tests/test_affected_tests_helper.sh covers every REASON against
  fixture registries and an absent engine (new)'
component_user_root: 'Per-user root: .aitask-scripts/lib/aitasks_home.sh exports AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}
  and aitasks_engine_dir <version|dev>, plus $AITASKS_HOME/.home.lock; sourced by the shim,
  aitask_setup.sh''s install_engine_binary, aitask_engine.sh and the verifiers; never falls
  back to ~/.aitask/; ait setup creates $AITASKS_HOME/engine/ with mode 0755 and prints AITASKS_HOME:<path>
  in its summary beside the venv line so both roots are visible; ait engine prune walks only
  $AITASKS_HOME/engine/v*/; test_aitasks_home.sh pins the default, the env override, and that
  no framework script under this feature names ~/.aitask/ (inherited from n005)'
component_variant_axes: 'Variant axes (internal/axes, read by registry, selectr, runner, cost):
  aitestmap/axes.yaml declares axes {name, facets[], values{value: {facet: v}}, sources{facet:
  {v: [globs]}}}; a runner''s describe names the axis its variants live on and a token_format;
  list emits <unit>@<value> ids; the selector joins changed paths to facet values through
  sources and selects the variants carrying them (reason axis(<axis>.<facet>=<v>) <- <path>)
  plus plain units carrying testmap:axis for that value (n004''s hand-declared coordinate),
  or every variant of a unit reached by an edge, dep, rule or test-dep; --axis <axis>.<facet>=<v>
  forces a facet (n004); costs, last_pass, evidence and score are per variant; check enforces
  DEAD_AXIS_SOURCE, UNKNOWN_VARIANT and UNCOVERED_VALUE (n004); observed sources widen only;
  the engine holds no project axis - the first consumer is thinking_app''s matrix axis with
  facets locale/direction/geometry over its 10 recording matrices (inherited from n005; n004
  bridges)'
component_workflow_integration: 'Workflow integration: task-workflow gains affected-tests.md
  (Affected Tests Procedure) called from Step 7 at two points - on demand while implementing
  (''after editing a source, run the procedure instead of the full suite'') and once before
  proceeding to Step 8 (the pre-review affected run) - wrapped in {% if profile.affected_tests
  is not defined or profile.affected_tests != ''off'' %}; the procedure runs the helper with
  the set -e capture form, branches: pass -> continue; fail -> the build-verification fail
  loop (caused by this task: fix and re-run; unrelated: log in Final Implementation Notes
  under ''Affected tests''); skip:no_selection -> display the UNMAPPED_SOURCE paths and offer
  annotate / attribute --propose / waiver via the aitask-testmap skill; skip:testmap_absent|registry_absent
  -> one line, continue; skip:unknown_paths -> the Step-2b-style scope prompt; skip:admission_refused
  -> print DETAIL, continue; rc 3 -> diagnose, never fix code; the verdict line is recorded
  in the plan''s Final Implementation Notes and never in the gate ledger (advisory); profile
  key affected_tests documented in profiles.md, default.yaml and fast.yaml omit it (run),
  remote.yaml sets run; Step 8 (testmap_fresh dispatch) and Step 9 (gate orchestrator, build-verification.md)
  unchanged; aitask-qa test-discovery.md 3a-3c use `ait testmap explain --sources <changed>
  --format table` when aitestmap/ exists (gaps = UNMAPPED_SOURCE rows, naming scan otherwise)
  and test-execution.md 4a prefers `ait test --task <id>` with test_command kept for the exhaustive
  tier''s fresh full run; pickrem and pickweb inherit Step 7 and see a printed skip on Web;
  goldens under tests/golden/ regenerated for every profile x agent; aitask_skill_verify.sh
  run; profiles.md row added (new)'
requirements_agent_run_surface: 'Any code agent runs the right tests in any onboarded project
  without learning the project: one front verb, `ait test`, with four forms - --task <id>
  (the tests the task''s attributed change reaches, a reason per row), <path>... (the tests
  reaching those sources, or those test files themselves), --all (the full registered suite,
  the completion gate) and brief (this project''s runners, resources, full gate, axes, docs
  and notes, generated from the registry) - taught once by a generic Running Tests section
  in the seeded >>>aitasks agent-instructions block that ait setup writes into every supported
  agent''s instructions file, so the sentence an agent reads is the same in aitasks, thinking_app
  and aitasks_mobile and the project-specific facts come from `ait test brief`, never from
  prose the agent has to find'
requirements_agent_skill: 'Agent skills teach agents how to keep the map current as they write
  code and tests (annotate a file, a testmap:unit member or a testmap:axis coordinate, declare
  an axis source, put testmap:reads on a tree-scanning helper, axes --explain, attribute before
  the gate, verify after editing, classify --suggest, confirm/retarget stamps in the procedure
  gate, drive a render loop from select --format tokens - n006) AND, new here, how a repository
  gets onto the map in the first place and how any agent runs tests without learning the project:
  aitask-testmap-onboard is the attended, resumable migration of an existing test tree (detect
  tools -> generate aitestmap/ -> inventory and classify -> seed edges from measured sources
  -> waivers -> first full run -> accept seeds in batches -> enable gates), and the generic
  ''Running Tests'' section of the seeded agent-instructions block plus `ait test brief` are
  how an agent learns the run surface once, identically in every project (n006 + onboarding
  and run surface)'
requirements_annotation_freshness: Every ACCEPTED unit coverage annotation carries the date
  and blob digest of the covered source at confirmation, scoped to the member block (n006),
  with committed last_pass anchors per variant letting stale prove EVIDENCED; a SEEDED edge
  carries no stamp and makes no freshness claim - it lives in registry/seeded.yaml, selects
  at d1, and is invisible to stale; `onboard accept` is the act that turns a seed into a stamped
  testmap:covers line through the rewriter, so a stamp always records who accepted the claim
  and against which bytes
requirements_annotation_staleness: A stale verb reports STALE_PATH / STALE / EVIDENCED / UNSTAMPED
  / STALE_AREA / REVIEW_DUE rows in the fixed line protocol plus CHECK_STRUCTURAL:<n> on --all
  (n006); seeded edges are excluded from every stale class (they claim nothing), and stale
  --all adds one SEEDED:<n> summary line so a repo-wide sweep sees how much of the map is
  still provisional; structural rot stays check's
requirements_axis_product_selection: 'A project whose tests form a product of named facets
  (thinking_app: 49 screens x 10 matrices where a matrix is locale x direction x geometry;
  aitasks: skill x profile x agent goldens) declares the axis with its facets, values and
  facet-valued source globs, and lets the engine select exact variants - an axis-source hit
  selects the variants carrying the facet value, any other hit selects every variant, hits
  union - instead of choosing between thousands of hand edges and one all-or-nothing suite
  scope; a source matching no axis source reaches units only through edges and dependencies,
  which select every variant, the fail-safe direction (n004''s requirement, realised by n005''s
  mechanism; intersection reduces to the facet join on every single-file case)'
requirements_broad_test_handling: 'Scoped rows are ranked after unit tests at equal distance,
  selected under an explicit suite budget that prints every DEFERRED cut, scheduled only after
  the unit wave is green (broad_after_unit), widened by attribute on a full-run miss, and
  drift-flagged by evidence (STALE_AREA) rather than by calendar; a suite row marked full:
  true with a children: post-processor anchors registered ids on every run (inherited)'
requirements_cost_tracking: Tracks cost per test unit and per variant, keyed by host class,
  using Welford's online update (n, mean, standard deviation, p95, last), plus a last_pass
  {sha, at, run_id} anchor and a flake rate per id; per-invocation overhead rows are a first-class
  input keyed by invocation group, so a selection's estimate is the sum over groups of overhead.p95
  + the marginal p95 of each selected id - a second method in a booted Robolectric class costs
  its per-unit mean, not another boot (n005 rows, n004 group costing)
requirements_dev_rebuild_from_source: A framework developer rebuilds the engine with one command
  (ait engine build) through the same engine/build.sh that CI uses, into $AITASKS_HOME/engine/dev/
  which the shim selects via AIT_ENGINE=dev (version must read <V>-dev+<sha>); ait engine
  cross produces the CI matrix locally, byte-identical (inherited, root corrected)
requirements_engine_dev_regeneration: The GOOS/GOARCH matrix, CGO_ENABLED=0 and ldflags live
  in one script (engine/build.sh) shared by release CI, ait engine build and ait engine cross;
  ait engine test runs go vet and go test; ait engine prune removes versions under $AITASKS_HOME/engine/
  that no registered project is on; ait engine home reports the root, legacy tenants and symlink
  state and performs the migration on --migrate (merged)
requirements_engine_packaging: 'ait setup and ait upgrade install the host''s binary under
  $AITASKS_HOME/engine/v<VERSION>/ with checksum verification and a version --json self-check;
  fallbacks --local-engine, --engine-from-source, AIT_TESTMAP_BIN; opt-out --no-testmap /
  AIT_TESTMAP_FETCH=0; AITASKS_HOME: and HOME_LEGACY: lines (n006); new: setup''s summary
  ends with one TESTMAP:absent|bootstrapping|onboarded[|engine-missing] line computed by report_testmap_state()
  from the presence of aitestmap/ and onboard.yaml''s phase ledger, with the hint `run /aitask-testmap-onboard`
  on absent - setup reports, it never onboards; and the re-inserted >>>aitasks instructions
  block now carries the generic Running Tests section, so the run surface reaches every project''s
  agent instructions on the next setup or upgrade with no per-project step'
requirements_feedback_loop: 'Learns from failures the map did not predict via score/attribute
  (n006: automatic score after every full run, PREDICTION_FALSE_NEGATIVES / PREDICTION_MISSED
  lines, costs/predictions.yaml; attribute records observed edges, axis sources (widen only),
  triggers and area members merged at load); new here, an attribute proposal a reviewer has
  not decided lands in registry/seeded.yaml with origin `observed` so it selects immediately
  and is reviewed through the same accept/reject queue as onboarding seeds, and `onboard status`
  reports the queue (accepted / rejected / pending, oldest pending age) so adoption is measurable
  rather than remembered'
requirements_framework_home_name: 'The framework is named aitasks, so every path it owns under
  the user''s home should be ~/.aitasks - the engine installs there now, and the legacy ~/.aitask
  tree is migrated by an explicit verb, ait engine home --migrate (flock, per-entry rename,
  rmdir, compatibility symlink; known set corrected to include pypy_venv), with ait setup
  printing a HOME_LEGACY: hint in this release and a named follow-up flipping the default
  once the verb has passed a real install.sh --dir test (n004''s principle and mechanism,
  n005''s default)'
requirements_gate_enforcement: 'Enforced by gates so the map cannot rot silently: testmap_fresh
  (procedure, before the task commit; now also offers to accept seeded edges on the test files
  this task touched), testmap_check (fails STALE_PATH on its own; reports SEEDED:<n> and UNMAPPED_SOURCE:<path>
  rows and fails the structural rows plus UNMAPPED_SOURCE only under --strict past bootstrap_until)
  and testmap_run (fail-closed with explicit waivers, admitted by readiness); only check unlocks
  run; a project whose completion invariant is a full suite keeps tests_pass. Gates are enabled
  by the onboarding skill''s `enable` phase (which edits the profile''s default_gates / rendered_gates
  with confirmation and sets bootstrap_until), never by hand and never by ait setup (n006
  rules; enabling moved into onboarding)'
requirements_generic_across_projects: 'A framework feature, generic across projects (aitasks,
  thinking_app, thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation between
  source files and test units - including a project''s own finer subdivision expressed through
  member units and variant axes, with the project''s runner lowering ids - never project-specific
  code in the engine (n006); and whose onboarding is generic too: `onboard detect` recognises
  each repo''s test tools from the tree and from project_config.yaml (aitasks: tests/test_*.sh
  + run_all_python_tests.sh with its serial carve-out; thinking_app: gradlew + the screenshot
  harness; thinking_backend: run_script_tests.sh named under verify_build, bash + pytest;
  aitasks_go: Makefile test = go test ./... plus the tmux parity suite; aitasks_mobile: one
  gradle-class runner per source set - commonTest and androidHostTest as unit, androidDeviceTest
  as device - which is the answer to n006''s open question 9: a kind/runner distinction, no
  axis) and writes runners.yaml from builtins, scaffolding a project runner script only where
  an axis or a full-suite post-processor needs one'
requirements_go_engine: Scan, check, select and stale finish in well under a second on a ~720-test
  repo - and select stays under 250 ms warm on thinking_app's ~300 golden variants over 49
  members plus ~370 JVM classes with axis expansion, never executing a runner - and the scheduler
  runs concurrently with real cross-process locks, so selection overhead stays negligible
  against the shortest test and check can run at every commit step (n005 target; n004's 2,500-row
  cell target has no referent in the merged design)
requirements_go_engine_and_cli: The engine and CLI are one static Go binary (ait-testmap)
  built from engine/; bash keeps only the dispatcher arm, the shim that resolves the binary
  under $AITASKS_HOME and pipes the change surface in, the two gate verifier shells, lib/aitasks_home.sh,
  the ait engine developer verbs (incl. home [--migrate]) and any project-local runner or
  scanner scripts; the binary never invokes aitask_*.sh and never needs its own install root
  (n005; n004's ait engine home verb added, its internal/home dropped)
requirements_high_level_tests_separate: Integration, e2e and device tests declare areas, scope
  globs or budget-exempt trigger globs instead of covers, live in registry/_scoped.yaml beside
  the unit table, join the ranked list at distance 1 as sinks, and never enter the per-file
  edge graph or its digest staleness; a helper file may declare testmap:reads <glob> so every
  unit whose test-file closure contains it inherits the glob as a trigger; variant-bearing
  units are unit kind and never scoped rows (inherited from n005)
requirements_incremental_adoption: 'Adoption is incremental and measurable, never big-bang:
  a seeded edge selects from the moment seed runs (fail-safe direction) but claims no freshness;
  acceptance - the act that writes testmap: lines and stamps - happens in onboarding batches
  by area or, inside the testmap_fresh gate, for the test files a task already touched; `onboard
  status` prints the ratios (tests with an edge, sources with an edge, seeds pending per origin,
  oldest pending age) and ONBOARD_NEXT so a half-migrated repo is a known state with a next
  step, and check reports SEEDED:<n> until the queue is empty'
requirements_platform_binaries_in_release: Release CI builds and attaches checksummed binaries
  for linux/darwin x amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt)
  from one engine job that also runs go vet and go test; a new engine-check.yml runs the same
  on push/PR for engine/**; tarball and package-manager artifacts stay architecture-independent
  (inherited)
requirements_reason_per_selected_test: 'Translates a task''s change set into one ranked list
  of tests that must run with a reason on every line (n006''s reasons: edge(annotation|declared|observed),
  dep, rule, axis(...)[keys], test-dep, reads(...), area/scope/trigger, stale-evidence, ESCALATE:,
  facet value or @*, invocation group and cost, DEFERRED:) plus `edge(seeded:<origins>)` for
  a seeded edge - the origins list (naming, invocation, imports, cochange, coverage, observed)
  is printed so a reader knows the row rests on a heuristic, and `ait test` prints a SELECTED:<n>|<est_s>|<seeded_n>
  summary line ahead of the rows'
requirements_screen_locale_subdivision: 'A test unit may be a member of a file (<path>#<member>,
  opened by a testmap:unit block) and may carry variants on a declared axis (<unit>@<variant>);
  a source change reaches a unit on every variant, or reaches an axis facet value (matrix.locale=ru)
  and thereby only the variants carrying it plus any plain unit carrying testmap:axis matrix.locale=ru;
  the runner lowers a variant id to what it executes (thinking_app: <Class>.<method> per matrix
  through matrix_classes / preview_resolve_token) so the engine never learns Gradle, Roborazzi
  or the membership manifests (inherited from n005; testmap:axis from n004)'
requirements_standard_runner_contract: 'Runs selected tests through project-defined runners
  under a standard contract (describe/list/run; n006 fields incl. group_by, token_format,
  filter_scope, full, children, artifact_glob; TSV list; results.jsonl with child rows; runner.json
  overhead; builtins bash-file, pytest, go-test, gradle-class, suite, device with command:/cwd:
  overrides and shadow-by-name) plus two onboarding affordances: `ait testmap runner scaffold
  <builtin> --as <name>` writes a project runner script skeleton whose describe/run delegate
  to the builtin and whose list is the one function the project fills (thinking_app''s tools/verification/testmap_runner.sh
  is that scaffold completed), and `onboard detect` wraps an existing project_config.yaml
  test_command as a `full: true` suite runner with a children: post-processor generated for
  pytest junitxml, bash-file names and go test -json, so the project''s full gate feeds evidence
  from day one without anyone writing a runner'
requirements_user_root: Every per-user artifact this feature installs lives under the framework's
  own root, ~/.aitasks/ (env override AITASKS_HOME, one owner file lib/aitasks_home.sh, no
  fallback to ~/.aitask), beside the existing ~/.config/aitasks/ and ~/.cache/aitasks/ roots;
  the engine is the root's first tenant at $AITASKS_HOME/engine/v<VERSION>/ and $AITASKS_HOME/engine/dev/;
  the legacy ~/.aitask/ tenants (venv, pypy_venv, python, bin, uv, dev_tier, update_check)
  are neither moved nor read by this feature's default path (inherited from n005)
requirements_workflow_seam: 'The change-aware run is reached from the existing workflows without
  a new workflow: task-workflow Step 7 gains an Affected Tests procedure (affected-tests.md)
  behind an affected_tests: run|show|off profile key (default run) that calls one helper,
  aitask_affected_tests.sh <task_id>, speaking the VERDICT:/REASON:/DETAIL:/LOG: line shape
  and set -e capture form aitask_run_project_command.sh already established; Step 8''s procedure-gate
  block dispatches testmap_fresh unchanged; Step 9''s gate orchestrator and legacy build-verification
  path are untouched; aitask-qa''s test discovery reads the map (explain --sources) instead
  of naming conventions when aitestmap/ exists and its execution step prefers `ait test --task`;
  aitask-pickrem and aitask-pickweb inherit Step 7 through the shared task-workflow; ait setup
  prints TESTMAP:<state>; and every seam degrades to a printed skip where the engine or registry
  is absent'
requirements_zero_config_onboarding: 'A repository with an existing test tree is brought onto
  the map by one attended run of /aitask-testmap-onboard and nothing typed by hand: the skill
  detects the test tools (pytest, go test, gradle per source set, bash tests/test_*.sh, npm
  test, Makefile test, and the project_config.yaml test_command / verify_build), generates
  aitestmap/ (config.yaml, runners.yaml with bindings, resources.yaml stub, registry/areas.yaml
  from code_areas.yaml), inventories every test unit through the runners'' list, classifies
  broad tests with confirmation, seeds edges from the four origins, proposes rules and waivers
  for the remainder, wraps the existing full gate as a suite runner and runs it once, accepts
  seeds in batches, and enables the gates - each phase idempotent and resumable from a committed
  ledger (aitestmap/onboard.yaml), the whole run shaped as an aitask so its writes land under
  (t<id>) commits and the change surface attributes them'
tradeoff_accept_rewrites_history: 'Disadvantage: accepting seeds inserts comment lines into
  hundreds of test files, so `git blame` on any test header points at the acceptance commit
  and a concurrent task editing the same file hits a textual conflict on the header; mitigated
  by comment-only insertions at a fixed position (after the header block / docstring), per-area
  batch commits named for what they are, the incremental path that accepts a file''s seeds
  only inside a task that already edits it, and the rewriter''s REWRITE_CONFLICT refusing
  a file that changed under it; a project that wants no comment churn keeps seeds unaccepted
  and accepts selection-only enforcement, which onboard status reports as the state it is'
tradeoff_area_glob_coarseness: 'Disadvantage: area and scope globs are coarser than edges
  - a broad area over-selects its tests on every edit inside it and a scoped test depending
  on a file outside its scope is under-selected until a full run scores it; mitigated by the
  suite budget with explicit DEFERRED lines, budget-exempt triggers and reads globs for known
  sharp edges, and the missing-trigger / area-too-narrow attribution path (inherited)'
tradeoff_attribution_risk: 'Risk: an agent that edits sources without attributing produces
  a map that looks current and is not; narrowed (n006) by STALE on the next task, stale marks
  on every selection, and the automatic score within one task where a full suite runs at completion.
  Narrowed further here: the Step-7 affected run reports UNMAPPED_SOURCE:<path> for a changed
  source no unit reaches, at the moment the agent introduced it, and the procedure offers
  annotate / attribute / waiver right there - so a new coupling with no edge is surfaced during
  the task rather than only on a full run; what still escapes is a coupling to a source that
  already has some edge, which only score can find'
tradeoff_autonomous_confirmation_weak: 'Risk: treating a green test as evidence that a coverage
  claim still holds is weaker than review; narrowed - the only autonomous confirmation is
  --confirm-evidenced, which requires a pass on every reached variant whose tree held the
  current bytes of the specific source, records confirmed_by: <run_id>, and is re-opened by
  a later score miss; a STALE row is never confirmed without a human (inherited from n005)'
tradeoff_axis_declaration_burden: 'Disadvantage: axes are a third authoring surface, and a
  project that declares them wrongly gets confidently wrong selection. Concretely: thinking_app
  must declare ten matrix values with three facets, four locale source-glob sets, one values/**
  rule, one runner script (list/describe/run/children over its existing routing) and one testmap:axis
  line per non-capturing coordinate test. Mitigated by making membership declarative and checkable
  - DEAD_AXIS_SOURCE fails a source glob that matches nothing, UNKNOWN_VARIANT a listed variant
  outside the axis, UNCOVERED_VALUE a declared value no runner lists, and axes --explain <path>
  answers why one file landed where it did before anything is trusted; and by an undeclared
  source reaching every variant, so an incomplete axis over-selects rather than under-selects
  (n004''s burden, restated for the merged mechanism)'
tradeoff_axis_projection_coarseness: 'Disadvantage: the default axis join is file-level -
  a one-key edit to values-ru/strings.xml selects every enrolled screen on both ru matrices
  (about 65 variants) rather than the screens naming that key; sound but 2/10 of the matrices
  rather than 1/50 of the screens; mitigated by the opt-in android-res symbol scanner (keys
  changed -> referencing Kotlin files -> member units), by select --format tokens feeding
  the project''s own render loop so the over-selection costs a preview rather than a gate,
  and by the group-costed budget (inherited from n005)'
tradeoff_batch_misreport_risk: 'Risk: a batch runner that misreports per-unit results corrupts
  attribution, cost and evidence (a false pass could manufacture an EVIDENCED row); two more
  places to misreport than n003 - the JUnit classname/name to variant-id inversion, and the
  zero-match trap at method granularity where a Gradle --tests filter matching nothing exits
  0 with zero tests; mitigated by units_expected/units_reported reconciliation per id, a row
  inverting to no registered id and units_reported == 0 with units_expected > 0 both being
  mechanism failures, and no line from an invocation with a cause ever anchoring (merged from
  n004 and n005)'
tradeoff_broad_scope_coarseness: 'Disadvantage: a test scoped to a large area is selected
  for any change inside it; mitigated by ranking last at its distance, running only after
  a green unit wave, being cut first by the suite budget with the cut printed as DEFERRED,
  and the cost visible in schedule (inherited)'
tradeoff_cell_table_size: 'Disadvantage, inverted: instead of n004''s ~2,500 generated cell
  rows that churn whenever a screen or matrix is added, _scanned.yaml carries 49 member rows
  with a variants: list of at most ten values; the price is that scan and check exec each
  runner''s list (thinking_app: a bash script reading two manifests, milliseconds) and that
  a matrix added to the manifests is invisible to select until the next scan --apply - which
  check reports as UNKNOWN_VARIANT/UNCOVERED_VALUE drift the same day. Enumerating at every
  select was rejected for the reason n004 gave: it would put a build-adjacent exec on the
  hot path of every gate (n004''s tradeoff, re-cut for the runner-list universe)'
tradeoff_compiled_component_cost: 'Disadvantage: the framework gains a compiled component
  - contributors touching the engine need Go, a release fails if go test fails, install gains
  a fetch and checksum step; mitigated by a single build.sh matrix, ait engine build, and
  the engine being optional until a testmap gate is enabled (inherited)'
tradeoff_computed_vs_prose: 'Advantage: selection is computed, explained and scored rather
  than remembered (n006); and so is the run surface - `ait test brief` prints the runners,
  resources, full gate, axes and doc pointers from the registry, and the generic Running Tests
  section is identical in every project, so an agent never learns ''how do I run tests here''
  from a 200-line CLAUDE.md testing section again (thinking_app''s is 200 lines today); the
  project''s judgement calls (when a preview loop is acceptable) become config.yaml notes:
  lines and docs: pointers the brief prints, still prose, but reached through one verb rather
  than found'
tradeoff_engine_absent_on_host: 'Risk: an unsigned macOS binary or a blocked download leaves
  a host without an engine; mitigated by ENGINE_MISSING naming the path and repair verb, the
  fallbacks, and the testmap gates exiting 3, never skip (n006); the workflow helper is the
  one deliberate exception: aitask_affected_tests.sh reports VERDICT:skip REASON:testmap_absent
  (engine or registry missing) so task-workflow, pickrem and pickweb - which has no ait setup
  at all - continue exactly as today, because an advisory Step-7 run must never block a task
  the way a declared gate legitimately does; the skip is printed, never silent'
tradeoff_engine_speed_enables_per_task_use: 'Advantage: sub-second select/check/stale on a
  720-test repo, and sub-250 ms select over 300 variants with axis expansion, makes selection
  overhead negligible against the shortest test and lets check run at every commit step; the
  facet join is one glob match per changed file per facet and one set test per member, select
  never execs a runner, and a bash+Python engine would spend seconds in start-up and YAML
  parsing first (merged)'
tradeoff_engine_version_skew: 'Disadvantage: one user with several projects on different framework
  versions keeps several ~10 MB binaries under $AITASKS_HOME/engine/; mitigated by exact-version
  resolution in the shim (never newest-wins) and ait engine prune against the project registry,
  never a count-based prune (inherited, root corrected)'
tradeoff_evidence_requires_reachable_history: 'Risk: the evidence join can only suppress a
  STALE row when the anchoring commit is reachable, so a depth-1 CI clone or a fresh shallow
  worktree sees the precise digest verdict with no self-healing; the safe direction, and the
  reason stale --strict fails only on STALE_PATH (structural rot is check''s); a repo-wide
  stale --all --strict job should run on a full clone or accept STALE noise (inherited)'
tradeoff_fail_closed_bootstrap_cost: 'Disadvantage: fail-closed enforcement means each repo
  pays a bootstrap - a waiver pass before testmap_check, a green full run before require_stamp
  and --strict, a green runner list before the structural rules fail, min_scored_full_runs
  before testmap_run (n006). Now owned rather than described: the onboarding skill''s phase
  ledger sequences it, the seeder replaces most of the hand waiver pass (measured on aitasks:
  88% of bash tests and 80% of Python tests carry a literal invocation or import that seeds
  at least one edge), the first full run is the project''s existing test_command wrapped as
  a suite runner, and acceptance is incremental, so the attended cost is one onboarding session
  of a few hours per repo plus a few rows per later task rather than a big-bang rewrite; the
  cost that remains is the judgement in classify and accept, which no seeder can take (n006,
  cost re-cut by onboarding)'
tradeoff_flaky_pass_anchors: 'Risk: a flaky pass anchors evidence as surely as a real one;
  mitigated by per-run status in the ledger so costs exposes a flake rate per id, and an id
  above flake_threshold is excluded from the evidence join (inherited)'
tradeoff_generated_brief_limits: 'Disadvantage: a brief computed from the registry cannot
  say what a project''s people know about when a narrow run is acceptable, which device is
  the real test device, or why RTL is the design gate - thinking_app''s testing prose carries
  exactly that; mitigated by config.yaml docs: (paths the brief prints, so the prose is one
  hop away and named) and notes: (<=10 verbatim lines for the rules that must not be one hop
  away), and by the seeded instructions telling agents to read the brief before touching a
  test tool; the limit that stays is that notes: is prose an agent may still misread, which
  the gates and the full completion gate backstop'
tradeoff_home_migration_window: 'Risk: when run, the migration has a sub-millisecond window
  between rmdir ~/.aitask and ln -s during which a concurrent process that hardcodes the legacy
  path (rather than using the resolver) sees ENOENT; narrowed by the flock, by symlinking
  immediately after the rmdir, and by refusing while another ait holds the home lock - not
  eliminated. Measured surface: 8 framework code files with 35 references (21 in aitask_setup.sh),
  20 test files, 18 doc files, the venv''s absolute shebangs and two symlink trees - none
  rewritten by the migration, all resolving through the symlink. And its refusal cases are
  the ones a designer does not see on their own host: n004''s known-entry set lacked pypy_venv,
  which this host carries. Both are why the verb is explicit in this release and the default
  flip waits for the real-install test (n004''s risk, re-measured and scoped to the verb)'
tradeoff_intersection_can_underselect: 'Risk: an axis-source hit is sharper than a file edge
  - it selects only the variants carrying the facet value - and is therefore capable of missing
  a real coupling that a plain covers edge (every variant) would have caught, e.g. a font
  family assigned to the wrong locale''s glob. Narrowed structurally: under-selection needs
  an explicit, reviewable wrong glob, never an omission, because a file matching no axis source
  reaches every variant; score on a full run raises missing-axis-source; observed sources
  may only widen; --axis and --format tokens with preview are the reviewer''s escape; and
  every variant row prints the facet value that placed it, so what a sharp selection excluded
  is visible in the prediction record (n004''s risk, restated for the facet join)'
tradeoff_member_annotation_drift: 'Risk: a member unit''s annotation lives in a block keyed
  by name (testmap:unit Welcome) and the runner''s list keys the same member by another artifact
  (the golden manifest''s Welcome_<matrix>.png); a rename on one side orphans the other; mitigated
  by check reporting a listed member with no block (UNANNOTATED_MEMBER) and a block with no
  listed member (DEAD_MEMBER), both fail-closed, by scan --apply refusing rather than guessing,
  and by thinking_app''s own manifest/@Test drift loop failing the rename on its side (inherited
  from n005)'
tradeoff_noarch_packages_preserved: 'Advantage: Homebrew, AUR, .deb, .rpm and the tarball
  ship nothing compiled; the per-arch concern is contained in one release job and one setup
  function (inherited)'
tradeoff_onboarding_partial_coverage: 'Disadvantage: onboarding cannot map what no origin
  reaches - thinking_app''s same-package tests (imports resolve for 139 of 339 files), fixture-driven
  tests, and any source with no naming, invocation, import, co-change or coverage relation
  - so a freshly onboarded repo has UNMAPPED_SOURCE rows and area-only coverage for a share
  of its tree; mitigated by the waivers phase (rules for hot directories, expiring waivers
  for the rest) so check can be enabled non-strict, by the Step-7 UNMAPPED_SOURCE prompt that
  maps a source the first time a task touches it, by opt-in per-unit coverage where the tool
  supports it, and by the full gate staying the completion criterion; the honest reading of
  `onboard status` after one session is ''selecting on most tests, claiming on few'', and
  the design treats that as a state, not a failure'
tradeoff_real_scheduler: 'Advantage: goroutines plus flock(2) give correct cross-worktree
  contention and a critical-path report; the shell suite and the pytest lane get the enforced
  do-not-overlap that is only a comment today; a variant batch is one Gradle invocation holding
  one heavy-run slot, ordered after cheaper invocations in its wave; thinking_app''s heavy-run
  lock and emulator allocator become declared resources the schedule report can reason about
  (merged)'
tradeoff_registry_directory_complexity: 'Disadvantage: a merged registry directory needs more
  CLI logic than a single file would - now six tables, two generated files, an id grammar
  with member and variant fragments and an artifact column in list; kept to one directory
  with one merge rule in one Go package with golden tests, no second plugin directory or generated
  cell table, and the axis table is empty for every project that declares none (merged)'
tradeoff_resource_declaration_completeness: 'Risk: declared resources are only as complete
  as the declarations; an undeclared interference is invisible until a full run or a probe
  finds it; serial-by-default at bootstrap means declarations are reviewed in the schedule
  report before concurrency is trusted (inherited)'
tradeoff_seed_noise: 'Risk: heuristic seeds are wrong in both directions - naming pairs a
  test with a homonym, an import names a helper the test only uses, co-change ties every file
  of a wide task to every test of that task (thinking_app: 7.2 main files per co-changing
  commit), and a wrong seed selects tests that cannot fail for the change. Mitigated by seeds
  selecting (wasted minutes) and never claiming (no false EVIDENCED), by the confidence table
  ordering review rather than gating it, min_cochange 2 across distinct tasks, imports restricted
  to direct main-root imports (same-package facts excluded), the evidence printed beside every
  seed at review, rejection memory in onboard.yaml, and the suite budget and --format tokens
  for a repo where over-selection is expensive; what remains is reviewer fatigue on a 1,000-seed
  queue, which the per-area batches and the in-gate incremental path spread over time'
tradeoff_setup_network_fetch: 'Disadvantage: ait setup gains the framework''s first self-downloaded
  release asset; mitigated by reusing the CDN URL family install.sh already uses, SHA256SUMS
  verification, the .sha256 sidecar, --no-testmap / AIT_TESTMAP_FETCH=0, the shim never fetching
  on its own, and setup never depending on the binary for anything else (inherited)'
tradeoff_split_home_rejected: 'Disadvantage of the alternative n005 took as permanent and
  n004 rejected: installing only the engine at ~/.aitasks/engine/ and leaving venv, pypy_venv,
  python, bin and uv at ~/.aitask/ satisfies the mandate literally with zero migration risk,
  but leaves a user with two dot-directories one character apart holding halves of one install,
  which ait setup --repair, ait engine prune, backup advice and every doc page would have
  to explain forever. Chosen: the split as the transition, not the end state - the migration
  is designed, shipped as an explicit verb and testable now, with the symlink making it reversible
  (rm ~/.aitask && mv ~/.aitasks ~/.aitask), and becomes ait setup''s default in a named follow-up
  (n004''s argument, n005''s timing)'
tradeoff_stamp_churn: 'Disadvantage: confirming stamps rewrites test files - a source named
  by 72 tests could yield a 72-file diff (n006: EVIDENCED needs no rewrite, --confirm-source
  is one commit, member blocks keep a screen''s stamps in one file, variants carry no stamp,
  KIND_MISMATCH nudges fan-out toward a scope or axis); onboarding adds the largest rewrite
  of all - accepting seeds touches most test files once (aitasks: up to ~700 files) - mitigated
  by seeds selecting without any rewrite, by accept being batched per area into `chore: Accept
  testmap seeds for <area> (t<id>)` commits that add comment lines only, and by the incremental
  path that accepts a file''s seeds only when a task already has it open'
tradeoff_static_scanner_overselection: 'Disadvantage: static scanners overselect on hot files
  and cannot see runtime coupling; a shared component (thinking_app''s ui/components/*) fans
  out to most screens on every matrix, which is the correct answer and close to a full run,
  and ScreenFixtures.kt reaches every member because the change surface is file-level; kind
  ranking, the suite budget and --budget-s trim scoped rows first, the android-res symbol
  scanner narrows a catalog edit to the screens naming the changed keys, a project scanner
  plugin can narrow a hot resource file, and hunk-level attribution inside a member file is
  the later narrowing tool (merged)'
tradeoff_strict_version_handshake: 'Risk: the binary must match .aitask-scripts/VERSION exactly,
  so an ait upgrade on a host that cannot fetch leaves ait testmap refusing to run until a
  matching binary is supplied; intended fail-closed behaviour, and the error names the fix
  (ait setup, AIT_TESTMAP_BIN, ait engine build) and the $AITASKS_HOME path it looked in (inherited)'
tradeoff_two_edge_states_during_adoption: 'Disadvantage: until the seed queue is empty a repo
  has two kinds of edge - accepted (stamped, evidenced, stale-checked) and seeded (selecting
  only) - and a reader of a selection or a check report must keep them apart; mitigated by
  the seeded origin printed on every row, SEEDED:<n> on check and stale --all, `onboard status`
  as the one place the ratio lives, and the rule that no seed ever changes a freshness verdict;
  the cost is real: --strict cannot be enabled while UNMAPPED_SOURCE rows are only seed-covered,
  so a repo that never finishes accepting stays at bootstrap enforcement indefinitely, which
  `onboard status` makes visible rather than silent'
tradeoff_two_toolchains: 'Disadvantage: bash and Go in one framework; mitigated by the boundary
  rule (parse/walk/match/digest/schedule in Go; gate ledger, task file and shell environment
  in bash; builtins exec configured commands and never source shell state), the engine-check.yml
  job, and Go source confined to engine/ and excluded from the tarball so target projects
  never need Go (inherited)'
tradeoff_two_user_roots: 'Disadvantage: until ait engine home --migrate is run, a host carries
  ~/.aitask/ (venv, pypy_venv, python, bin, uv) and ~/.aitasks/ (engine) side by side, and
  a user who deletes one to reset the framework removes half of it; mitigated by one variable
  (AITASKS_HOME) with one library owner, ait setup printing both roots and the HOME_LEGACY:
  hint, ENGINE_MISSING naming the exact path, ait engine home reporting the state, a test
  that fails if any script of this feature names ~/.aitask/, and the migration verb existing
  now rather than as an unowned ''later change'' (n005, narrowed by n004''s verb)'
tradeoff_whole_run_filter_soundness: 'Risk: where a runner''s filter restricts a whole test
  run (Gradle --tests on thinking_app''s single testDebugUnitTest task), every class not selected
  is silently not run, so a narrow selection is only as sound as the test-side closure, the
  reads globs and the opaque contract; mitigated by list enumerating the whole universe so
  an unlisted class fails check, the test-dep closure over abstract bases and helpers, testmap:reads
  on tree-scanning helpers (71 SourceFence importers stay selected on any Kotlin change),
  ESCALATE on opaque files, red-proof fixtures per branch, readiness gating the run gate on
  scored history, and the project keeping its full suite as the completion gate until readiness
  is met - the risk n004''s cell selection would have carried unmitigated (inherited from
  n005)'
tradeoff_workflow_surface_growth: 'Disadvantage: the seam adds one task-workflow procedure
  file, one profile key, one dispatcher verb, one skill-invoked helper (five allowlist touchpoints
  - .claude/settings.local.json, .codex/rules/default.rules and the three seeds - pinned by
  tests/test_touchpoint_count_contract.sh), a Step-7 render change across every profile x
  agent golden, two aitask-qa procedure edits, a seed-instructions edit and a static skill
  with two wrapper surfaces; mitigated by all of it degrading to a printed skip where the
  engine is absent (no environment conditionals), by the helper reusing the exact VERDICT:/REASON:
  contract and capture form the build-verification path already teaches, and by aitask_skill_verify.sh
  plus the goldens catching a drifted render before commit'
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

The baseline (n006) is a complete change-aware testing engine — a static Go
binary under `~/.aitasks/engine/`, a committed `aitestmap/` registry of
source→test edges with blob-digest stamps healed by run evidence, member units
and variant axes for product-shaped suites, a runner contract, a real
scheduler, a cost ledger, a feedback loop, three gates and a maintenance skill.
What it does not say is how a repository that already has 300–700 test files
**gets onto** that map, and how an agent that opens the repository tomorrow
**runs tests** without first reading a 200-line testing section of `CLAUDE.md`.
Its "Per-Repository Bootstrap Order" is one paragraph of prose; its
`component_skill` teaches an agent to *maintain* a map that someone else has
already built by hand.

This node keeps every mechanism of n006 unchanged and adds the adoption layer
the mandate asks for, in three parts, each shaped by a measurement taken on the
target repositories rather than by preference:

**1. Onboarding as a resumable, task-shaped skill, not a runbook.**
`/aitask-testmap-onboard` detects the repository's test tools from the tree and
`project_config.yaml`, generates `aitestmap/` (config, runner table with
bindings, resources stub, areas imported from `code_areas.yaml`), inventories
every test unit through the runners' own `list`, classifies broad tests with the
reasons printed, **seeds** edges, proposes rules and waivers for what no seed
reaches, wraps the project's existing `test_command` as a `full: true` suite
runner and runs it once so evidence exists from day one, then accepts seeds in
batches and enables the gates. Every phase is idempotent and recorded in a
committed ledger (`aitestmap/onboard.yaml`); the run is an aitask so its writes
land under `(t<id>)` commits and a resumed session re-enters at
`ONBOARD_NEXT:`. The user types no YAML.

**2. Seeds that select but never claim.** The one genuinely new registry
object is `registry/seeded.yaml`: edges proposed by four measured heuristic
origins — naming (`test_gate_pass.sh` ↔ `aitask_gate_pass.sh`; 16–19 % of tests
in the target repos), **literal invocation and direct imports** (a bash test
that runs `./.aitask-scripts/x.sh`, a Python or Kotlin test that imports a main
file; 88 % / 80 % of aitasks tests, 41 % of thinking_app's), **`(t<id>)`
co-change history** (439 of the last 600 aitasks task commits touch tests and
scripts together, 2.8 scripts × 2.6 tests each — tight; thinking_app's 127 of
400 average 7.2 main files — noisy, hence a minimum of two distinct tasks), and
opt-in per-unit runtime coverage where the tool supports it. A seeded edge is
walked like an annotation edge at distance 1 (over-selection is the safe
direction) but carries no stamp, is invisible to `stale`, anchors nothing and
cannot satisfy `--strict`. **Acceptance** — a review act with the evidence
printed beside every row — is what writes the `testmap:covers` line and the
stamp, in per-area batches during onboarding or, inside the `testmap_fresh`
gate, for the test files a task already has open. Adoption is therefore
incremental and measurable (`onboard status`), never a big-bang rewrite, and a
half-migrated repository is a known state with a next step.

**3. One run surface, learned once.** `ait test` is the only verb an agent
needs: `--task <id>` (the tests the task's *attributed* change reaches, a reason
per row), `<path>...`, `--all` (the full registered suite — the completion
gate), and `brief` (this project's runners, resources, full gate, axes, doc
pointers and declared notes, generated from the registry). The seeded
`>>>aitasks` agent-instructions block that `ait setup` already writes into every
supported agent's instructions file gains a generic **Running Tests** section
— the same twelve lines in aitasks, thinking_app and aitasks_mobile — so the
project-specific facts come from `ait test brief`, never from prose an agent
has to find. The workflow seam is one helper, `aitask_affected_tests.sh`,
speaking the `VERDICT:/REASON:/LOG:` contract `aitask_run_project_command.sh`
already established, called from a new task-workflow Step-7 procedure behind
an `affected_tests` profile key; `aitask-qa`'s test discovery reads the map
instead of naming conventions; Step 8's procedure-gate dispatch and Step 9's
gate orchestrator are untouched; and every seam degrades to a **printed skip**
where the engine or registry is absent, which is what lets it sit in every
profile including the one Claude Code Web runs with no engine at all.

What this does not change: the engine's process boundary, the registry's six
tables and check rules, the id grammar, axes, the runner contract, the
scheduler, the ledger, the evidence join, the three gates' verifiers and the
per-user root. The seeds table is a seventh table with one rule (a seed that
duplicates an accepted edge is dropped with `SEED_SHADOWED`); the `test`,
`brief`, `seed` and `onboard` verbs are additions to the same binary; and the
freshness model gains exactly one new stamp writer (`onboard accept`), which is
also the only place a seed becomes a claim.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_onboarding_skill, component_seeder, component_test_front_verb, component_agent_brief, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary] -->
## Architecture

### Process boundary (additions in bold-face comments)

```
ait test <form> ...                              (agent / user)            ← NEW alias
ait testmap <verb> ...                           (user / skill / gate verifier)
 └─ .aitask-scripts/aitask_testmap.sh            bash shim (n006), gains `test` passthrough
      │   resolve $AIT_TESTMAP_BIN > AIT_ENGINE=dev > $AITASKS_HOME/engine/v<VERSION>/ait-testmap
      │   for --task forms: aitask_change_surface.sh list <id> | <bin> <verb> --changes - ...
      └─ $AITASKS_HOME/engine/v<VERSION>/ait-testmap --repo-root "$AIT_DIR" <verb> ...
           internal/registry        six tables (n006) + seeds table from registry/seeded.yaml; SEED_SHADOWED
           internal/seed            ← NEW  naming / invocation / imports / cochange / coverage origins; confidence table
           internal/onboard         ← NEW  detect, inventory, phase ledger (onboard.yaml), accept / reject, status, finish
           internal/brief           ← NEW  the generated run brief (lines and --md)
           internal/selectr         graded walk (n006) + seeded edges at d1 with reason edge(seeded:<origins>); explain --sources
           internal/runner          contract (n006) + `runner scaffold`, the `full` suite wrapper, bash-file `list --invocations`
           internal/annot           grammar v3 + rewriter (n006); accept writes lines at the fixed header position
           internal/deps            scanners (n006); invocation + direct-import facts exposed to internal/seed
           internal/{axes,changesurface,sched,cost,feedback,stale,gitx,platform}   unchanged
             ├─ exec:  git, runner scripts / builtins, admission / allocator commands, scanner plugins
             └─ files: aitestmap/** · .aitask-testmap/ (runs, ledger) · XDG cache (deps, cochange matrix by HEAD sha)
.aitask-scripts/aitask_affected_tests.sh         ← NEW  workflow seam: `ait test --task` → VERDICT:/REASON:/DETAIL:/LOG:/SELECTED:/UNMAPPED_SOURCE:
.aitask-scripts/aitask_gate_testmap_check.sh     machine verifier (n006); reports SEEDED:<n>, UNMAPPED_SOURCE:<path>
.aitask-scripts/aitask_gate_testmap_run.sh       machine verifier (n006)
.aitask-scripts/aitask_setup.sh                  install_engine_binary (n006) + report_testmap_state() → TESTMAP:<state>   ← NEW line
.claude/skills/aitask-testmap-onboard/           ← NEW  static attended skill: SKILL.md + detect.md inventory.md classify.md seed.md
                                                        waivers.md full-run.md accept.md enable.md finish.md
.claude/skills/aitask-testmap/                   n006 skill; opens with `ait test brief`; hands an un-onboarded repo to onboard
.claude/skills/aitask-gate-testmap-fresh/        n006 procedure gate + "accept seeds for touched test files" step
.claude/skills/task-workflow/affected-tests.md   ← NEW  Affected Tests Procedure (Step 7)
.claude/skills/aitask-qa/{test-discovery,test-execution}.md   registry-first branches
seed/aitasks_agent_instructions.seed.md          + `## Running Tests` (generic; reaches CLAUDE.md / AGENTS.md via ait setup)
engine/                                           Go source — framework repo only
```

The boundary rule is n006's and is not bent: parse, walk, match, digest,
schedule and now *seed* in Go; gate ledger, task file, profile file and shell
environment in bash and skill prose. `onboard` never creates a task, never
edits a profile and never commits — the skill does those through
`aitask_create.sh --batch`, `aitask_pick_own.sh`, the settings helpers and
`git commit -- <paths>`; the engine reads `onboard.yaml`'s `task:` field and
writes `onboard.yaml`'s phase rows. The engine still never writes `aitasks/`,
`aiplans/`, `.aitask-data/` or a gate ledger and never invokes `aitask_*.sh`.

### Registry directory (n006's, with the additions marked)

```
aitestmap/
  config.yaml            n006 keys · exclude: [globs]            ← never listed, never UNREGISTERED (fixtures, helpers, generated)
                         · docs: [paths]                          ← printed by brief
                         · notes: |  (<=10 lines)                 ← printed by brief verbatim
                         · broad_threshold_s: 60                  ← classify signal
                         · bootstrap_until  (set by onboard enable, +30d)
  onboard.yaml           ← NEW  phase ledger: {contract: 1, task: t<id>, phases{...}, rejections[]}
  axes.yaml · runners.yaml · resources.yaml     (n006; runners.yaml written by onboard detect, confirmed per runner)
  registry/
    _scanned.yaml · _scoped.yaml · observed.yaml · areas.yaml · <area>.yaml    (n006)
    seeded.yaml          ← NEW  generated by `seed`; edited only by `onboard accept` (row removed) / `reject` (row removed)
  costs/ · runners/ · scanners/                  (n006; runners/<name>.sh may come from `runner scaffold`)
```

`seeded.yaml` rows:

```yaml
contract: 1
seeded:
  - test: tests/test_gate_pass.sh
    covers: .aitask-scripts/aitask_gate_pass.sh
    origin: [naming, invocation, cochange]
    confidence: 0.99          # noisy-OR of 0.6, 0.9, 0.6 — ordering only
    evidence:
      naming: "test_gate_pass.sh ~ aitask_gate_pass.sh"
      invocation: "tests/test_gate_pass.sh:41"
      cochange: [t635_15, t1147]
    proposed_at: 2026-09-16
  - test: app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt#Welcome
    covers: app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeScreen.kt
    origin: [imports]
    confidence: 0.85
    evidence: {imports: "ScreenFixtures.kt:212"}
    proposed_at: 2026-09-16
```

`onboard.yaml`:

```yaml
contract: 1
task: t1830
started_at: 2026-09-16 12:30
phases:
  detect:    {status: done,    at: 2026-09-16 12:41, by: daelyasy@hotmail.com, runners: 3}
  inventory: {status: done,    at: 2026-09-16 13:02, units: 721, unregistered_resolved: 12, excluded: 4}
  classify:  {status: partial, reviewed: 41, pending: 7}
  seed:      {status: done,    at: 2026-09-16 13:20, rows: 1184, tests_with_seed: 605, sources_with_seed: 233}
  waivers:   {status: done,    rules: 4, waivers: 9}
  full_run:  {status: done,    run_id: full-2026-09-16T13.40-3f1c, anchored: 721}
  accept:    {status: partial, accepted: 210, rejected: 14, pending: 960}
  enable:    {status: pending}
  finish:    {status: pending}
rejections:
  - {test: tests/test_board_header_row_live.py, source: .aitask-scripts/lib/tmux_exec.py,
     reason: "gateway used, not covered", at: 2026-09-16 13:55}
```

### The seed → accept state machine

```
                seed --apply                    onboard accept <test> | --area | --batch N
   (none) ───────────────────▶ SEEDED ──────────────────────────────────────────▶ ACCEPTED (testmap:covers line + stamp)
                                  │                                                  ▲
                                  │ onboard reject <test> <source>                    │ annotate / attribute (n006 paths, unchanged)
                                  ▼                                                  │
                              REJECTED (onboard.yaml; never re-proposed)              (none) ───────────────────────────────┘
   attribute --propose (autonomous) ───▶ SEEDED with origin observed
```

`SEEDED` selects; only `ACCEPTED` claims. Nothing moves a row right without a
person or an attended agent naming the row.
<!-- /section: architecture -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_seeder, requirements_zero_config_onboarding, requirements_incremental_adoption, assumption_test_tools_detectable, assumption_seed_sources_measured, assumption_seeds_select_never_evidence, assumption_onboarding_is_a_task] -->
## Onboarding a Repository: Phases, Ledger, Seeds

### Invocation and shape

`/aitask-testmap-onboard [<task-id>]`. Without an argument the skill creates and
claims `testmap_onboarding` (`aitask_create.sh --batch --name testmap_onboarding
--type chore --labels testmap --priority medium`, then `aitask_pick_own.sh`),
writes the id into `onboard.yaml`, and from then on every phase ends with one
commit of the files it produced — `chore: Onboard testmap — <phase> (t<id>)`,
paths named — so `aitask_change_surface.sh` attributes them and the framework's
own re-entry (`/aitask-pick <id>`, which finds `onboard.yaml` and dispatches
back to this skill) resumes at `ONBOARD_NEXT:`. The skill is **static and
attended-only** (no profile stub, no `.j2`): every phase is a judgement call, and
a repository is onboarded once. It refuses on Claude Code Web (`TESTMAP:engine-missing`).

### Phases

| # | phase | engine verb | what the skill confirms | commit |
|---|---|---|---|---|
| 0 | preflight | `version --json`, `onboard status` | engine present, repo root, no `aitestmap/` or an unfinished ledger to resume | — |
| 1 | **detect** | `onboard detect [--write]` | the runner table, one `AskUserQuestion` per detected runner: keep / edit command / drop; the `full` suite wrapper of `test_command` (or `verify_build` when that is the only test-running key — thinking_backend — with the proposal to move it) | `aitestmap/{config,runners,resources}.yaml`, `registry/areas.yaml` |
| 2 | **inventory** | `scan`, every runner `list`, `check` | `UNREGISTERED:` files → bind to a runner or add an `exclude:` glob (fixtures, `tests/lib/`, `tests/golden/`); `areas --import-codemap` when `code_areas.yaml` has areas | `registry/_scanned.yaml`, `config.yaml` |
| 3 | **classify** | `classify --suggest` | each `CLASSIFY:<test>\|<kind>\|<reason>` candidate in batches of 20: accept kind, set areas / scope / trigger; unit stays the default | `registry/_scoped.yaml` via `scan --apply` |
| 4 | **seed** | `seed --from naming,invocation,imports,cochange [--apply]` | the counts: rows, tests with ≥1 seed, sources with ≥1 seed, per-origin share; opt-in `--from coverage` when the tool supports per-unit contexts | `registry/seeded.yaml` |
| 5 | **waivers** | `check`, `explain --sources` | for each `UNMAPPED_SOURCE:` directory cluster: a `rules:` entry (glob → runner set) for hot directories, an expiring waiver (`expires: +90d`) for the rest, or "leave unmapped" | `registry/<area>.yaml` |
| 6 | **full_run** | `ait test --all`, `costs --update` | the full gate ran through the suite wrapper; child rows anchored `last_pass` on every registered id; `PREDICTION_SCORED:none` | `costs/<hostclass>.yaml` |
| 7 | **accept** | `onboard accept --area <a> --batch 50` | every seed with its evidence — the file pair, the `file:line`, the task ids, the coverage run — accept / reject / leave; a file's `# Covers:` prose header (38 in aitasks) is shown beside its seeds as context | one commit per batch: the rewritten test files |
| 8 | **enable** | `readiness` | which profile(s) get `testmap_check` and `testmap_fresh` in `default_gates` (and `rendered_gates` when present); `bootstrap_until` = today + 30; `docs:` paths and `notes:` lines for the brief; `testmap_run` only if `READINESS_DECISION:ADMISSIBLE` | `aitasks/metadata/profiles/<p>.yaml` (via `./ait git`), `config.yaml` |
| 9 | **finish** | `onboard finish` | `onboard status` green (no `pending` phase, seed queue ≤ a threshold the user sets, `check` clean); flips `require_stamp: true` and `--strict`; archives the task | `config.yaml` |

Phase 7 may be left `partial`: the remainder migrates through the
`testmap_fresh` gate a few files per task. `enable` and `finish` do not wait
for it. A repository that finishes onboarding with 960 pending seeds is
"selecting on 84 % of tests, claiming on 18 %", and `onboard status` says so.

### Detection, per target repository

| repo | detected | runner table written | scaffold needed |
|---|---|---|---|
| aitasks | `tests/test_*.sh` + `tests/lib/asserts.sh`; `tests/run_all_python_tests.sh` (pytest lane with the serial carve-out); `test_command` unset | `bash-file` over `tests/test_*.sh`; `pytest` (`testmap:batch no` on the four carve-out modules, pinned by extending `test_serial_carveout_doc_drift.sh`); `full` = `bash tests/run_all_python_tests.sh` + every bash test, children from junitxml and per-file exit | none |
| thinking_app | `gradlew`, `app/src/test/java` (334 files), `test_command: screenshot-tests.sh verify-active`, the two membership manifests, `matrix_classes` | `gradle-class`; `screen-matrix` (axis detected by the grid heuristic: 297 goldens over 10 matrices); `verify-active` as `full: true` with `children:` | `runner scaffold gradle-class --as screen-matrix` → `tools/verification/testmap_runner.sh`, whose `list` the project fills from the manifests (n006's runner, arrived at by scaffold) |
| thinking_backend | `scripts/tests/run_script_tests.sh` under `verify_build`; `test_*.sh` and `test_*.py` under `scripts/tests/` | `bash-file`, `pytest`; `full` = `run_script_tests.sh`; detect proposes `test_command:` = the same script with confirmation | none |
| aitasks_go | `go.mod`, 55 `_test.go`, `Makefile test`, `parity/run_parity.sh` (tmux + venv) | `go-test`; `parity` as `suite`, kind e2e, areas from `widget/`, `style/`, resource `tmux` | none |
| aitasks_mobile | `gradlew`; `shared/src/{commonTest,androidHostTest}`, `domain/src/{commonTest,androidDeviceTest}`, `dbaccess/src/{commonTest,androidDeviceTest}` | one `gradle-class` per source set: `commonTest` and `androidHostTest` unit, `androidDeviceTest` kind device with an `emulator` allocator resource — a kind/runner distinction, no axis (n006 open question 9) | none |

### Seed origins, measured

| origin | rule | aitasks bash (400) | aitasks Python (320) | thinking_app (307–339) | base confidence |
|---|---|---|---|---|---|
| naming | `test_<x>.sh → aitask_<x>.sh \| lib/<x>.{sh,py}`; `test_<x>.py → <x>.py`; `<Stem>Test.kt → <Stem>.kt` | 72 (18 %) | 62 (19 %) | 48 (16 %) | 0.60 |
| invocation | a literal `.aitask-scripts/…` path in the test body | 350 (88 %), 3 paths avg | — | — | 0.90 |
| imports | direct `import` / `from` of a main-root file (same-package facts excluded) | — | 255 (80 %), 1 avg | 139 (41 %), 3 avg | 0.85 |
| cochange | (test, source) in ≥ `min_cochange` distinct `(t<id>)` commits | 439/600 commits, 2.8 × 2.6 | same pass | 127/400 commits, 7.2 main files avg | 0.50 + 0.10/extra task ≤ 0.80 |
| coverage | per-unit runtime coverage (coverage.py dynamic contexts; `go test -run <unit> -coverprofile`; LCOV with a test column; project plugin) | opt-in | opt-in | JaCoCo per-test sessions = project plugin | 0.95 |

The invocation and imports origins are the same facts `internal/deps` already
scans for the test-side closure — read once, cached by blob. Only the **direct**
relation is seeded; the deeper closure is the selector's d2 walk and would be
noise as an edge. Co-change is one `git log --name-status -M
--format=%H%x00%s` pass over commits whose subject matches `(t<id>)`, counted
per distinct task id, cached by HEAD sha under the XDG cache; a shallow clone
seeds fewer rows and says so (`SEED_HISTORY:shallow|<n commits>`). Confidence
is a fixed table combined by noisy-OR; it orders the review queue and never
hides a row.

### What seeding cannot do, stated

thinking_app's tests resolve imports for 139 of 339 files because same-package
references need no import and the Kotlin scanner's "same package is fully
connected" fact is too coarse to seed; fixture-driven tests and screen members
seed through `annotate --from-body` (n006) rather than through this table;
sources reached by no origin stay `UNMAPPED_SOURCE:` until a rule, a waiver, a
Step-7 prompt or a coverage import maps them. The design treats that as a state
the ledger reports, not a failure it hides.
<!-- /section: onboarding -->

<!-- section: run_surface [dimensions: component_test_front_verb, component_agent_brief, requirements_agent_run_surface, assumption_instructions_block_reaches_agents, assumption_helper_degrades_when_absent, assumption_change_surface_is_intake] -->
## The Run Surface an Agent Learns Once

### `ait test`

```
ait test --task <id> [--mode run|show] [--json]     the tests the task's attributed change reaches
ait test <path>... [--mode run|show]                the tests reaching those sources; a test path runs that unit (and its variants)
ait test --all                                      every registered unit through the runners — the completion gate
ait test brief [--md]                               this project's run brief
ait test explain <path>                             = ait testmap explain (why a unit is or is not selected)
```

Output of a `--task` run, in order: `SELECTED:<n>|<est_s>|<seeded_n>`, one
`UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked rows
with n006's reasons (a seeded edge reads `edge(seeded:invocation,cochange)`),
the schedule's wave lines, results per id, and `RESULT:pass|fail|skip|deferred|<run_id>`.
`--task` goes through the change surface exactly as the gates do — `UNKNOWN:`
refuses with the paths named; `OTHER:` is never selected on. `<path>...` is the
one explicit-list intake (treated as `TASK:` rows). `--all` has no intake and
is `run --all`: it anchors evidence and scores the newest prediction.

### `ait test brief` on thinking_app (after onboarding)

```
TESTMAP:onboarded|since 2026-09-16|seeds pending 412
RUNNER:gradle-class|unit|371 classes|screenshot-tests.sh unit-tests --tests <class>|heavy-run
RUNNER:screen-matrix|unit (variant, axis matrix)|49 members x 10 matrices = 297|screenshot-tests.sh unit-tests --tests <class>.<method>|heavy-run
RUNNER:verify-active|suite (full)|1|screenshot-tests.sh verify-active|heavy-run
FULL_GATE:verify-active|p95 1180s|= project_config test_command
VERBS:ait test --task <id> | ait test <path>... | ait test --all | ait test brief
AXES:matrix|facets locale,direction,geometry|10 values
RESOURCE:heavy-run|admission (tools/verification/heavy-run-lock.sh)|refusal = exit 75 -> deferred to run deadline
DOCS:aidocs/testing/rendering-verification.md
DOCS:aidocs/testing/change-aware-verification.md
NOTES:A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
NOTES:Never run ./gradlew test directly - the harness owns the heavy-run slot and the run id.
```

`--md` renders the same facts as markdown. Everything above `DOCS:` is computed
from the registry; `DOCS:` and `NOTES:` are what the onboarding `enable` phase
asked the maintainer for — the judgement calls the registry cannot hold, kept
to ten lines and reached through one verb.

### The generic instructions block

Added to `seed/aitasks_agent_instructions.seed.md`, therefore inserted between
the `>>>aitasks` / `<<<aitasks` markers of every supported agent's instructions
file on the next `ait setup` or `ait upgrade` — the mechanism
`assemble_aitasks_instructions()` / `insert_aitasks_instructions()` already
implements — with no per-project edit:

```markdown
## Running Tests

This project's tests may be registered with the change-aware test map (`aitestmap/`).

- `ait test brief` — this project's runners, resources, full gate, and notes. Run it
  before invoking any test tool directly; prefer the registered runner it names.
- `ait test --task <id>` — the tests the task's change reaches, with a reason per row.
- `ait test <path>...` — the tests reaching those sources, or those test files.
- `ait test --all` — the full registered suite; this is the completion gate.
- A new test file needs `testmap:` annotations (`/aitask-testmap`); a changed source
  no test reaches is reported as `UNMAPPED_SOURCE` — map it before the gate.
- `TESTMAP:absent` means the project is not onboarded — `/aitask-testmap-onboard`.
```

Twelve lines, no agent named, identical everywhere. What varies per project
comes out of `brief`.

### The workflow helper

```
./.aitask-scripts/aitask_affected_tests.sh <task_id> [--mode run|show]
  stdout (data channel, KEY:value only):
    VERDICT:pass|fail|skip
    REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
    DETAIL:<one line>
    LOG:.aitask-gates/<task>/affected_<run-id>.log
    SELECTED:<n>|<est_s>|<seeded_n>
    UNMAPPED_SOURCE:<path>          (0..n lines)
    UNKNOWN:<path>                  (0..n lines, with REASON:unknown_paths)
  exit: 0 pass · 1 fail · 2 skip · 3 usage / log unwritable   (aitask_run_project_command.sh's contract)
```

It sources `lib/aitasks_home.sh` and the shim, writes the engine's full output
to the log, appends nothing to any ledger, and is allowlisted on the five
touchpoints (`tests/test_touchpoint_count_contract.sh` re-pinned). Every
absence is a *reason*, never an error: this is what lets the procedure below
run in `remote` on Claude Code Web, where there is no engine, and print one
line.
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_integration, requirements_workflow_seam, assumption_gate_exit_contract_reused, assumption_helper_degrades_when_absent] -->
## The Workflow Seam

### task-workflow Step 7 — the Affected Tests Procedure (`affected-tests.md`)

Rendered into Step 7 under `{% if profile.affected_tests is not defined or
profile.affected_tests != 'off' %}`, at two points:

- **While implementing.** One sentence after "Follow the approved plan": *"After
  editing a source, run the Affected Tests Procedure (`affected-tests.md`) rather
  than the full suite; the full gate remains the completion criterion."* This is
  the iteration loop the mandate asks for — an agent runs the right tests
  without deciding which those are.
- **Before Step 8.** Once, the pre-review affected run, so the reviewer sees a
  verdict for the tests the change reaches before approving the commit.

The procedure body, mirroring `build-verification.md` so the two cannot
disagree about an exit code:

```bash
if at_out="$(./.aitask-scripts/aitask_affected_tests.sh <task_id> --mode {{ 'show' if profile.affected_tests == 'show' else 'run' }})"; then
  at_rc=0
else
  at_rc=$?
fi
at_verdict="$(printf '%s\n' "$at_out" | sed -n 's/^VERDICT://p')"
at_reason="$(printf '%s\n' "$at_out"  | sed -n 's/^REASON://p')"
at_detail="$(printf '%s\n' "$at_out"  | sed -n 's/^DETAIL://p')"
at_log="$(printf '%s\n' "$at_out"     | sed -n 's/^LOG://p')"
at_selected="$(printf '%s\n' "$at_out" | sed -n 's/^SELECTED://p')"
```

| branch | action |
|---|---|
| `at_rc` 3 or empty verdict | infrastructure — diagnose the helper / engine; never "fix the code"; never a pass |
| `pass` | display `SELECTED:` and continue |
| `fail` | read `at_log`; caused by this task → fix and re-run; unrelated → log under **Affected tests** in the plan's Final Implementation Notes and proceed (the `build-verification.md` loop, verbatim) |
| `skip` · `no_selection` | display the `UNMAPPED_SOURCE:` paths; **offer** (`AskUserQuestion`, non-skippable in attended profiles): *Annotate now* (`/aitask-testmap` → `annotate` / a rule) · *Propose for review* (`attribute --propose`, lands in `seeded.yaml`) · *Continue unmapped*. Autonomous profiles take *Propose for review*. This is the moment a new coupling is cheapest to record |
| `skip` · `unknown_paths` | the Step-2b-style scope prompt from `aitask-gate-docs-updated`: include / subset / exclude; autonomous profiles exclude and log |
| `skip` · `admission_refused` | print `at_detail` (the host refused the heavy slot until the deadline); continue — nothing failed |
| `skip` · `testmap_absent` / `registry_absent` | one line; continue — the repository is not onboarded or this host has no engine |

The verdict line (`- **Affected tests:** pass (14 units, est 41 s) — log …`)
is written into the plan's Final Implementation Notes and **never** into the
gate ledger: Step 7's run is advisory, and a task that declares `testmap_run`
has the Step-9 orchestrator record the real gate. No double record, no
`record_gates` guard needed.

Profile key `affected_tests: run|show|off` — `run` when omitted (the whole
point is that an agent runs the right tests without being told); `show` prints
the selection and runs nothing; `off` renders the procedure away. `default.yaml`
and `fast.yaml` omit it; `remote.yaml` sets `run` (on Web the helper prints
`skip:testmap_absent`, so the key costs nothing there). Documented as one row in
`profiles.md`; goldens regenerated for every profile × agent;
`aitask_skill_verify.sh` run before commit.

### Step 8 — unchanged dispatch, one new step inside the gate

The procedure-gate block already dispatches `testmap_fresh` before the change
summary (n006). Inside `aitask-gate-testmap-fresh`, after the `STALE` /
`STALE_PATH` / `UNSTAMPED` handling, one new step: for every `COMMITTED:` /
`TASK:` path that is a test file with rows in `seeded.yaml`, show the seeds
with their evidence and offer *accept / reject / leave* per row. Accepted rows
are written through the rewriter and ride the same `(t<id>)` commit as the
test edit. This is the incremental half of adoption — and the reason
onboarding's `accept` phase may stop early.

### Step 9 — untouched

The gate orchestrator runs `testmap_check` / `testmap_run` when declared; the
legacy path runs `build-verification.md` (`verify_build`). Neither changes. A
project whose completion gate is a full suite keeps `tests_pass` (n006).

### aitask-qa

- `test-discovery.md` 3a–3c: when `aitestmap/` exists, `ait testmap explain
  --sources <changed files> --format table` gives the Source / Test / Reason /
  Status map directly — `Covered` for an accepted edge, `Covered (seeded)` for a
  seed, `GAP` for `UNMAPPED_SOURCE`; the naming-convention scan stays as the
  fallback for a repository without a map. The health score's coverage
  component reads the same rows.
- `test-execution.md` 4a: prefer `ait test --task <id>` and keep its
  `SELECTED:`; `test_command` remains what the exhaustive tier's verification
  gate (4e) re-runs fresh, because that step is defined as the full run.

### aitask-pickrem / aitask-pickweb / ait setup

Both inherit Step 7 through the shared task-workflow; pickweb sees a printed
`skip:testmap_absent`. `ait setup` prints `TESTMAP:absent|bootstrapping|<next>|onboarded|engine-missing`
after the engine line and, on `absent`, the hint `run /aitask-testmap-onboard`.
Setup never onboards.

### Verification of the seam itself

`tests/test_affected_tests_helper.sh` (every `REASON:` against fixture
registries in scratch git repos; an absent engine; exit-code ↔ verdict
agreement with `aitask_run_project_command.sh`'s table);
`tests/test_agent_instructions_running_tests.sh` (the section lands in
`CLAUDE.md` / `AGENTS.md` through a real `install.sh --dir`);
`tests/test_testmap_onboard_ledger.sh` (resume from each phase; idempotent
re-run; `--no-task`); engine tests for each seed origin on fixture repos with
synthetic `(t<id>)` histories and one fixture per detect shape; the
task-workflow goldens; `tests/test_touchpoint_count_contract.sh`.
<!-- /section: workflow_seam -->

<!-- section: data_flow [dimensions: component_onboarding_skill, component_seeder, component_test_front_verb, component_workflow_integration, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_engine_packaging] -->
## Data Flow

### Onboarding (once per repository)

```
tree + project_config.yaml ──▶ onboard detect --write ──▶ aitestmap/{config,runners,resources}.yaml · registry/areas.yaml
                                                          (runner table confirmed per runner by the skill)
runners' list + scan ─────────▶ onboard inventory ───────▶ _scanned.yaml · UNREGISTERED: resolved (bind | exclude:)
classify --suggest ───────────▶ CLASSIFY:<test>|<kind>|<reason> ──confirm──▶ _scoped.yaml (scan --apply)
deps facts (invocation, imports) + naming rules + git log (t<id>) co-change [+ coverage] ──▶ seed --apply ──▶ registry/seeded.yaml
check / explain --sources ────▶ UNMAPPED_SOURCE clusters ──confirm──▶ rules / waivers in registry/<area>.yaml
ait test --all ───────────────▶ runs · child rows · ledger.jsonl ──costs --update──▶ costs/<hostclass>.yaml (last_pass on every id)
onboard accept --area <a> --batch 50 ──▶ rewriter ──▶ testmap:covers lines + stamps in test files; rows leave seeded.yaml
readiness + profile edit ─────▶ default_gates += [testmap_check, testmap_fresh] · bootstrap_until · docs: · notes:
onboard finish ───────────────▶ require_stamp: true · strict · task archived
every phase ──▶ onboard.yaml row ──▶ chore: Onboard testmap — <phase> (t<id>) commit (paths named)
```

### A task, steady state

```
Step 7  edit source ──▶ aitask_affected_tests.sh <id> ──▶ change surface ──▶ test --task ──▶ select (edges ∪ seeds ∪ deps ∪ rules ∪ axes)
                                                             ──▶ schedule ──▶ run ──▶ ledger rows (run_id test-…) ──▶ VERDICT:/SELECTED:/UNMAPPED_SOURCE:
        UNMAPPED_SOURCE ──offer──▶ annotate | attribute --propose (→ seeded.yaml, origin observed) | continue
Step 8  procedure gates ──▶ testmap_fresh ──▶ stale --task … (n006) + accept seeds on touched test files ──▶ rewrites ride the (t<id>) commit
Step 9  ait gates run ──▶ testmap_check (SEEDED:<n>, UNMAPPED_SOURCE:, strict past bootstrap) ──▶ testmap_run | tests_pass (n006)
full run (any) ──▶ automatic score ──▶ PREDICTION_MISSED:<id> ──▶ attribute (decide | --propose → seeded.yaml)
```

### Reading the map without running anything

```
ait test brief ──▶ registry + config.yaml docs:/notes: + onboard.yaml ──▶ TESTMAP:/RUNNER:/FULL_GATE:/VERBS:/AXES:/RESOURCE:/DOCS:/NOTES:
aitask-qa 3a ──▶ ait testmap explain --sources <changed> --format table ──▶ Covered | Covered (seeded) | GAP
ait setup ──▶ report_testmap_state() ──▶ TESTMAP:<state>
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n006, unchanged)* means the component is carried as n006
specified it; *(n006 + …)* names the addition; *(new)* is introduced here.

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill and verbs *(new)*

`.claude/skills/aitask-testmap-onboard/` — a static, attended-only skill:
`SKILL.md` (invocation, task creation, `onboard status` → `ONBOARD_NEXT:`
dispatch) plus one procedure file per phase (`detect.md`, `inventory.md`,
`classify.md`, `seed.md`, `waivers.md`, `full-run.md`, `accept.md`,
`enable.md`, `finish.md`), each ending with the phase's commit and ledger row.
Engine verbs: `onboard detect [--write]` (prints `DETECT:<tool>|<root>|<evidence>`
and `RUNNER_PROPOSED:<name>|<builtin>|<glob>|<command>`; `--write` emits the
skeleton), `onboard inventory`, `onboard status` (phase rows, seed queue per
origin, tests-with-edge and sources-with-edge ratios, oldest pending seed,
`ONBOARD_NEXT:`), `onboard accept (<test>[#member] | --area <a> | --batch <n> |
--files-from -) [--min-confidence]`, `onboard reject <test> <source> --reason`,
`onboard finish`. All phases idempotent; re-running `detect --write` on an
existing table prints `DETECT_DIFF:` and writes nothing without `--force`.
Wrapper surfaces for Codex and OpenCode regenerated with
`aitask_audit_wrappers.sh apply-wrapper`. Tests: `test_testmap_onboard_ledger.sh`
and one engine fixture per detect shape.
<!-- /section: component_onboarding_skill -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(new)*

`internal/seed`: origins **naming** (per-runner stem rules), **invocation**
(bash literal paths), **imports** (direct main-root imports from the python /
kotlin / go scanners; same-package facts excluded), **cochange** (one
`git log --name-status -M --format=%H%x00%s` pass over `(t<id>)` commits,
pairs counted per distinct task, `--min-cochange 2`, cached by HEAD sha,
`SEED_HISTORY:shallow|<n>` on a shallow clone) and **coverage** (opt-in:
coverage.py contexts JSON, `go test -run <unit> -coverprofile`, LCOV with a
test column, or a plugin printing `{test, covers}` lines). Confidence table
naming 0.60 / invocation 0.90 / imports 0.85 / cochange 0.50 + 0.10 per extra
task ≤ 0.80 / coverage 0.95 / observed 0.70, combined by noisy-OR; ordering
only. Output `SEED:<test>|<source>|<origins>|<confidence>` lines, `--apply`
writes `registry/seeded.yaml` deterministically sorted. Rejected pairs
(`onboard.yaml`) are never re-proposed; accepted pairs are dropped with
`SEED_SHADOWED`. Budget: naming+invocation+imports < 2 s, cochange < 5 s over
600 commits on the aitasks shape. Fixtures: a synthetic repo per origin.
<!-- /section: component_seeder -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Front verb and workflow helper *(new)*

`ait test` in the dispatcher → `aitask_testmap.sh test` → engine `test`
composite (`--task`, `<path>...`, `--all`, `brief`, `--mode run|show`,
`--json`) printing `SELECTED:`, `UNMAPPED_SOURCE:`, the rows, waves, results
and `RESULT:`. `aitask_affected_tests.sh <task_id> [--mode]` is the workflow
seam: the `VERDICT:/REASON:/DETAIL:/LOG:/SELECTED:/UNMAPPED_SOURCE:/UNKNOWN:`
lines, exit `0/1/2/3` on `aitask_run_project_command.sh`'s contract, stderr for
humans only, log under `.aitask-gates/<task>/affected_<run-id>.log`, no ledger
append. Five allowlist touchpoints. `tests/test_affected_tests_helper.sh`.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief and instructions *(new)*

`internal/brief`: `brief [--md]` → `TESTMAP:`, `RUNNER:` per runner (name, kind,
unit count from `list`, invocation shape from `runners.yaml` / the builtin,
resources), `FULL_GATE:` (the `full` runner, its p95 from costs, `= test_command`
when it wraps it), `VERBS:`, `AXES:`, `RESOURCE:` per declared resource with
its refusal semantics, `DOCS:` per `config.yaml docs:`, `NOTES:` verbatim,
`ONBOARD_NEXT:` while bootstrapping; < 100 ms warm. The generic `## Running
Tests` section in `seed/aitasks_agent_instructions.seed.md` (twelve lines, no
agent named). `tests/test_agent_instructions_running_tests.sh`.
<!-- /section: component_agent_brief -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration *(new)*

`task-workflow/affected-tests.md` at two Step-7 points behind `affected_tests`
(`run` default; `show`; `off`); the branch table above; the plan-notes record;
no ledger write. `aitask-gate-testmap-fresh` gains the accept-on-touched-files
step. `aitask-qa/test-discovery.md` registry-first, `test-execution.md` 4a
prefers `ait test --task`. `profiles.md` row; `remote.yaml: affected_tests:
run`. Goldens regenerated; `aitask_skill_verify.sh`. pickrem / pickweb inherit;
`ait setup` prints `TESTMAP:`.
<!-- /section: component_workflow_integration -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(n006 + three packages)*

n006's `engine/cmd/ait-testmap` and `internal/*` unchanged; adds
`internal/seed`, `internal/onboard`, `internal/brief`. Same toolchain, deps
and boundary: the engine reads `onboard.yaml`'s `task:` and writes its phase
rows; task creation, profile edits and commits are the skill's, through the
framework's scripts. Fixture repos gain synthetic `(t<id>)` histories.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary *(n006 + verbs and budgets)*

Verb table + `test`, `brief`, `seed`, `onboard {detect,inventory,status,accept,reject,finish}`,
`runner scaffold`. Budgets added (brief < 100 ms, seed < 2 s / cochange < 5 s,
onboard status < 200 ms) under the same `go test -bench` 2× rule. Contract
stays 1; `seeded.yaml` and `onboard.yaml` carry `contract:` and a newer one is
refused with `CONTRACT_MISMATCH`.
<!-- /section: component_engine_binary -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n006, unchanged)*

`lib/aitasks_home.sh`, `AITASKS_HOME` defaulting to `~/.aitasks`, no fallback;
sourced additionally by `aitask_affected_tests.sh`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home: report and migration verb *(inherited from n006, unchanged)*

`ait engine home [--migrate]` as n006 specified, known set including
`pypy_venv`, default flip a named follow-up.
<!-- /section: component_framework_home -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n006, unchanged)*

`engine/build.sh`, the `engine` job, `engine-check.yml`, the shim's handshake,
`test_testmap_shim.sh` / `test_platform_detect.sh` / `test_aitasks_home.sh`.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade, regeneration *(n006 + `report_testmap_state()`)*

`install_engine_binary()` as n006; after it, `report_testmap_state()` prints
`TESTMAP:engine-missing|absent|bootstrapping|<next>|onboarded` with the
onboarding hint on `absent`. The re-inserted instructions block carries the
Running Tests section. `test_install_engine_binary.sh` asserts each state.
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(n006 + the seeds table)*

Six tables plus `seeds` from `registry/seeded.yaml`; `SEED_SHADOWED` at load;
write routing `seed → seeded.yaml`, `onboard accept/reject → seeded.yaml +
onboard.yaml`; `config.yaml` `exclude:`, `docs:`, `notes:`, `broad_threshold_s`.
n006's id grammar, `owns:` routing, deterministic writes and check rules
unchanged; golden tests pin the seed merge and the shadow rule.
<!-- /section: component_registry_loader -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n006, unchanged)*

`axes.yaml`, facets / values / sources, `<unit>@<variant>`, the facet join,
`testmap:axis`, `--axis`. The onboarding grid heuristic proposes an axis; a
person declares it.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n006, unchanged)*

`axes --list | --check | --explain <path>`.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n006, unchanged)*

The runner's `list` is the universe; `variants:` persisted by `scan --apply`;
`UNCOVERED_VALUE` / `UNMAPPED_ARTIFACT`. Onboarding's inventory phase is the
first consumer of `UNREGISTERED:` rows as a to-do list.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(n006 + accept as a writer)*

Grammar v3 and the rewriter unchanged; `onboard accept` inserts
`testmap:covers` lines at a fixed position per language (after the bash header
block; appended to the Python module docstring; a `//` block before the class
KDoc, or inside the member's `testmap:unit` block), stamped at accept time;
`# Covers:` prose headers shown as context, never parsed.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(n006; facts shared with the seeder)*

bash / python / go / kotlin / gradle scanners, the opaque contract, plugins,
`android-res`, the XDG cache — unchanged. Invocation and direct-import facts
for a test file are exposed to `internal/seed`; the closure is never seeded.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(n006 + seeded edges, `explain --sources`, the `test` summary lines)*

Seeded edges walked at d1 with `edge(seeded:<origins>)`, no stale mark;
`explain --sources <path>... --format table` for QA; `SELECTED:` and
`UNMAPPED_SOURCE:` lines ahead of the rows in `test`. Everything else as n006.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(inherited from n006, unchanged)*

`describe` / `list` / `run`, manifests, `results.jsonl`, `runner.json`,
bindings, `builtin:` with `command:` / `cwd:`, shadow-by-name, batching,
timeouts, reconciliation, exit contract `0/1/2/75/64`.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n006, unchanged)*

Kinds, scopes, `flock(2)` slots, admission deferral, allocators, waves,
`broad_after_unit`, ordering of admission-holding invocations last. An `ait
test --task` run on thinking_app is one Gradle invocation under the heavy-run
slot, and a refusal at the deadline is `VERDICT:skip REASON:admission_refused`.
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(n006; Step-7 runs are ordinary rows)*

Welford per (id, host class), invocation overhead rows, `costs --update`,
`last_pass`, flake rate, group costing, `predictions.yaml`. Affected runs use
`run_id` prefix `test-`, full runs `full-`; the `SELECTED:` estimate is the
budget's per-group sum.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n006, unchanged)*

Per reached variant; `EVIDENCED` only when every variant is anchored; never
rewrites. Seeded edges are not joined — they have no stamp to heal.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(n006 + `attribute --propose`, `onboard status` metrics)*

`score` automatic after full runs; `attribute` gains `--propose` (default in
autonomous profiles) writing to `seeded.yaml` with origin `observed`;
`readiness` unchanged; `onboard status` reports the queue and ratios.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(n006 + `SEEDED:` / `UNMAPPED_SOURCE:` rows; enabling sited in onboarding)*

`testmap_fresh`, `testmap_check`, `testmap_run` and their verifiers unchanged;
`testmap_check` reports `SEEDED:<n>` (never fails) and `UNMAPPED_SOURCE:<path>`
(fails under `--strict` past `bootstrap_until`); the onboarding `enable` phase
is what adds the gates to a profile, with confirmation; `testmap_run` only on
`READINESS_DECISION:ADMISSIBLE`.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(n006 + onboarding hand-off and accept-in-gate)*

`aitask-testmap` opens with `ait test brief` and hands an un-onboarded repo to
`aitask-testmap-onboard`; `aitask-gate-testmap-fresh` gains the accept step for
touched test files; the onboarding skill is new (above). Claude Code first,
wrappers regenerated.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(n006 + scaffold, the `full` wrapper, `list --invocations`)*

Builtins unchanged; `runner scaffold <builtin> --as <name>` emits a project
script whose `list` prints `SCAFFOLD_TODO` until filled (check reports it);
`onboard detect` writes the `full` suite runner wrapping `test_command` with a
builtin `children:` post-processor for pytest junitxml, bash-file names and
`go test -json`; `bash-file list --invocations` for the seeder.
<!-- /section: component_reference_runners -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(n006 + one stamp writer, one gate step)*

Stamps written by `verify`, `annotate`, `stale --confirm*` and now `onboard
accept`; the `testmap_fresh` gate offers acceptance for the test files the
task touched, so the stamp rides the same commit as the edit.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(n006; seeds excluded, `SEEDED:` summary)*

`stale` classes unchanged; seeded edges excluded from every class; `stale
--all` adds `SEEDED:<n>` beside `CHECK_STRUCTURAL:<n>`.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(n006 + classify signals)*

`classify --suggest` adds the three onboarding signals — recorded p95 above
`broad_threshold_s`, a directory / source-set convention, a resource named in
the file — each printed as the reason on the `CLASSIFY:` line. Everything else
as n006.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n006, unchanged)*

`broad_after_unit`, `device_policy`, `STALE_AREA`, opt-in `REVIEW_DUE`,
attribute widening, fixture pins, `full: true` suite rows with child rows.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

**New in this node**

- **assumption_test_tools_detectable** — the test tools of every target repo
  are recognisable from the tree and `project_config.yaml` without a build:
  verified on all five (aitasks bash + pytest lane; thinking_app gradlew +
  harness; thinking_backend `run_script_tests.sh` under `verify_build`;
  aitasks_go `Makefile test` + parity; aitasks_mobile three source-set roots).
  Falsifier: build-time test generation → `DETECT_UNKNOWN`, the skill asks.
- **assumption_seed_sources_measured** — the four origins seed what the table
  above says (naming 16–19 %, invocation 88 %, imports 80 % / 41 %, co-change
  439/600 tight vs 127/400 noisy), measured 2026-09-16; coverage is the fifth,
  opt-in; confidence orders, never hides; seeding is partial by construction.
- **assumption_seeds_select_never_evidence** — a seed may cause a test to run
  and may never suppress `STALE`, anchor evidence, satisfy `require_stamp` or
  count under `--strict`; the only promotion is an explicit accept. Falsifier:
  a suite so expensive that over-selection is the cost problem — the budget and
  tokens preview are the levers, not trusting seeds.
- **assumption_instructions_block_reaches_agents** — the `>>>aitasks` marker
  block is written and refreshed by `ait setup` / `ait upgrade` into every
  supported agent's instructions file (verified in `assemble_aitasks_instructions`
  / `insert_aitasks_instructions`), so one seed edit reaches every project; the
  section names no agent and stays under twelve lines.
- **assumption_helper_degrades_when_absent** — `aitask_affected_tests.sh`
  always answers: absent engine / registry / `UNKNOWN:` rows / empty selection /
  admission refusal are `skip` reasons; only an executed run is pass / fail;
  only an unwritable log is 3. This is what admits the procedure into every
  profile including `remote`.
- **assumption_onboarding_is_a_task** — onboarding writes committed files over
  several sessions, so it runs as an aitask created and claimed by the skill,
  commits per phase under `(t<id>)`, resumes at `ONBOARD_NEXT:`, archives on
  `finish`; `--no-task` prints the commits to run for a repo that forbids tasks
  on the code branch.

**Modified from n006**

- **assumption_change_surface_is_intake** — also the intake for `ait test
  --task` and the helper, so the Step-7 run is attributed exactly as the gates
  are; `<path>...` is the one explicit-list intake; `--all` has none.

**Inherited from n006 unchanged** — carried verbatim in the node metadata:
assumption_areas_express_suite_blast_radius, assumption_axis_membership_declarable,
assumption_axis_sources_declarable, assumption_batch_per_unit_timing_reportable,
assumption_blob_digest_is_staleness_key, assumption_broad_tests_area_scoped,
assumption_cells_enumerable_by_plugin, assumption_engine_latency_targets,
assumption_existing_locks_wrappable, assumption_gate_exit_contract_reused (the
helper's `0/1/2/3` is `aitask_run_project_command.sh`'s table, not a third
mapping), assumption_git_history_is_freshness_clock (co-change reads history
as a *seed* source, never as a freshness or evidence source),
assumption_go_toolchain_available, assumption_go_toolchain_ci_and_dev_only,
assumption_home_symlink_compatibility, assumption_kotlin_scanner_fail_closed,
assumption_legacy_user_root_coexists, assumption_one_engine_per_framework_version,
assumption_passing_run_anchors_edges, assumption_platform_matrix_sufficient,
assumption_release_asset_reachable, assumption_release_assets_reachable,
assumption_static_granularity_v1, assumption_target_repos_accept_aitestmap_root
(now also `onboard.yaml` and `registry/seeded.yaml` under that root),
assumption_testmap_token_no_collision, assumption_variant_universe_from_runner_list.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

**Advantages**

- **tradeoff_computed_vs_prose** *(n006, extended)* — selection is computed,
  explained and scored; so now is the run surface: the brief is generated, the
  instructions section is identical everywhere, and a 200-line testing chapter
  becomes ten declared `notes:` lines plus `docs:` pointers reached through one
  verb.
- **tradeoff_engine_speed_enables_per_task_use**, **tradeoff_real_scheduler**,
  **tradeoff_noarch_packages_preserved** *(inherited from n006, unchanged)*.

**Disadvantages and risks — new**

- **tradeoff_seed_noise** — heuristic seeds are wrong in both directions
  (homonyms, helper imports, wide co-changing tasks at 7.2 files); mitigated by
  seeds selecting and never claiming, confidence ordering review not gating it,
  `min_cochange 2` across distinct tasks, direct imports only, evidence beside
  every row, rejection memory, and the suite budget for a repo where
  over-selection is expensive; reviewer fatigue on a 1,000-row queue is spread
  by per-area batches and the in-gate path.
- **tradeoff_two_edge_states_during_adoption** — until the queue empties a
  repo has accepted and seeded edges side by side; mitigated by the origin on
  every row, `SEEDED:<n>` on check and stale, `onboard status` as the one ratio;
  the real cost is that `--strict` cannot be enabled while `UNMAPPED_SOURCE`
  rows are only seed-covered, which is visible rather than silent.
- **tradeoff_generated_brief_limits** — a computed brief cannot hold a
  project's judgement calls; `docs:` and `notes:` carry them one hop away, and
  the full gate backstops a misread note.
- **tradeoff_workflow_surface_growth** — one procedure file, one profile key,
  one dispatcher verb, one skill-invoked helper (five allowlist touchpoints), a
  Step-7 render across every profile × agent golden, two QA edits, a seed edit
  and a static skill with two wrappers; mitigated by uniform degradation to a
  printed skip, the reused `VERDICT:` contract, and `aitask_skill_verify.sh`
  plus the goldens.
- **tradeoff_accept_rewrites_history** — acceptance inserts comment lines into
  hundreds of test files (blame noise, header conflicts); mitigated by fixed
  insertion positions, per-area batch commits, the in-task incremental path and
  `REWRITE_CONFLICT`; a project may keep seeds unaccepted and live with
  selection-only enforcement, reported as such.
- **tradeoff_onboarding_partial_coverage** — what no origin reaches stays
  `UNMAPPED_SOURCE` or area-only (thinking_app's same-package tests, fixture
  tests); mitigated by rules and expiring waivers, the Step-7 prompt that maps a
  source the first time a task touches it, opt-in coverage, and the full gate as
  the completion criterion.

**Disadvantages and risks — modified from n006**

- **tradeoff_fail_closed_bootstrap_cost** — now owned by the onboarding ledger
  rather than described: the seeder replaces most of the hand waiver pass, the
  first full run is the existing `test_command` wrapped, acceptance is
  incremental; what remains is the judgement in classify and accept.
- **tradeoff_attribution_risk** — narrowed further by the Step-7
  `UNMAPPED_SOURCE` prompt at the moment a source is introduced; a coupling to
  an already-edged source is still only caught by score.
- **tradeoff_stamp_churn** — onboarding's acceptance is the largest rewrite of
  all; mitigated by seeds selecting without any rewrite, batch commits that add
  comment lines only, and the incremental path.
- **tradeoff_engine_absent_on_host** — the workflow helper is the one
  deliberate exception to "never skip": an advisory Step-7 run prints
  `skip:testmap_absent` and the task continues; declared gates still exit 3.

**Inherited from n006 unchanged** — carried verbatim in the node metadata:
tradeoff_area_glob_coarseness, tradeoff_autonomous_confirmation_weak,
tradeoff_axis_declaration_burden, tradeoff_axis_projection_coarseness,
tradeoff_batch_misreport_risk, tradeoff_broad_scope_coarseness,
tradeoff_cell_table_size, tradeoff_compiled_component_cost,
tradeoff_engine_version_skew, tradeoff_evidence_requires_reachable_history,
tradeoff_flaky_pass_anchors, tradeoff_home_migration_window,
tradeoff_intersection_can_underselect, tradeoff_member_annotation_drift,
tradeoff_registry_directory_complexity (one more generated file and one
ledger, both under the same root and merge rule),
tradeoff_resource_declaration_completeness, tradeoff_setup_network_fetch,
tradeoff_split_home_rejected, tradeoff_static_scanner_overselection,
tradeoff_strict_version_handshake, tradeoff_two_toolchains,
tradeoff_two_user_roots, tradeoff_whole_run_filter_soundness.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should `affected_tests` default to `run` or `show` when a repository's
   affected run is expensive (thinking_app: one Gradle boot under the heavy-run
   lock, ~40 s minimum)? Proposed: `run`, because the scheduler already defers
   on a refused slot and the estimate is printed first; a project may set
   `show` in its profile.
2. Should `onboard accept --batch` be allowed to auto-accept rows above a
   confidence threshold (e.g. invocation + naming ≥ 0.95) in an autonomous
   profile? Proposed: no — acceptance is the one act that turns a heuristic
   into a claim; `attribute --propose` and seeds already give autonomy the
   safe half.
3. Where does the co-change origin stop being useful — should it be off by
   default for repositories whose task commits average more than N files
   (thinking_app's 7.2)? Proposed: keep it on with `min_cochange 2` and print
   the noise figure in the seed report so the maintainer decides.
4. Should the Running Tests section be a Layer-2 (per-agent) addition instead
   of Layer 1, so a project that has not installed the engine sees nothing?
   Proposed: Layer 1 — the section's last line is the not-onboarded case, and a
   uniform block is the point.
5. Should `aitask-qa`'s health score treat a seeded edge as coverage (proposed:
   yes, shown as `Covered (seeded)` and weighted the same — QA measures whether
   a test exists, not whether its claim is fresh) or discount it?
6. Should the `full` suite wrapper's `children:` post-processor for bash-file
   tests infer per-file results from the runner's own per-file exit (available
   when `full` iterates the files) or require junit-style output? Proposed: the
   per-file exit; a project with a monolithic script gets suite-level evidence
   only.
7. Should `onboard finish` refuse while any `pending` seeds remain, or accept a
   user-set threshold? Proposed: threshold, default 0, printed in `status`.
8. Baseline questions still open (n006 §Open Questions 1–11), unchanged, with
   9 (aitasks_mobile's axis) answered here as a kind/runner distinction.
<!-- /section: open_questions -->
--- PROPOSAL_END ---
--- NEW_DIMENSIONS ---
assumption_helper_degrades_when_absent,assumption_instructions_block_reaches_agents,assumption_onboarding_is_a_task,assumption_seed_sources_measured,assumption_seeds_select_never_evidence,assumption_test_tools_detectable,component_agent_brief,component_onboarding_skill,component_seeder,component_test_front_verb,component_workflow_integration,requirements_agent_run_surface,requirements_incremental_adoption,requirements_workflow_seam,requirements_zero_config_onboarding,tradeoff_accept_rewrites_history,tradeoff_generated_brief_limits,tradeoff_onboarding_partial_coverage,tradeoff_seed_noise,tradeoff_two_edge_states_during_adoption,tradeoff_workflow_surface_growth
