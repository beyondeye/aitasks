--- NODE_YAML_START ---
node_id: n009_synthesizer_003
parents:
- n001_explorer_001a
- n002_explorer_001b
- n007_explorer_003a
- n008_explorer_003b
description: 'n006''s engine unchanged (every n001/n002 dimension carried through n003-n006),
  plus the adoption layer synthesized from n007 and n008: a three-state adoption ledger (registry/seeded.yaml
  select-only queue -> registry/adopted.yaml class-accepted stamped edges with provenance
  -> reviewed per-row stamps) fed by one measured origin table (static:package 1.0, coverage
  0.95, static:invocation 0.90, static:import 0.85, observed 0.70, convention 0.60, plan 0.50,
  prose 0.30, cochange capped at 0.60) with autonomous adoption limited to language-rule origins;
  onboarding as levels x phases (levels 0-3 from n008, the onboard.yaml phase ledger and ONBOARD_NEXT
  re-entry from n007, one aitask per level whose Step-9 tests_pass is the first anchoring
  full run); one front verb `ait test` (n008''s aitask_test.sh resolving mode / task / intake
  / policy with test_command and fallback_command fallbacks, over n007''s engine `test` composite,
  plus an --advisory mode that folds n007''s workflow helper into the same script and degrades
  every absence to a printed skip); `ait test --howto` = the engine brief; one merged `##
  Running Tests` section in the seeded agent-instructions block; the completion gate is the
  existing tests_pass running `./ait test --gate` under a committed completion policy (testmap_run
  retired, testmap_check unlocks tests_pass, 75/3 -> verifier error for opted-in keys); the
  workflow seam is n008''s data plus n007''s one pre-review Affected Tests procedure, kept
  because it writes the prediction the full run scores; aitask-qa reads the registry; ait
  setup prints TESTMAP:<state>.'
proposal_file: br_proposals/n009_synthesizer_003.md
created_at: "2026-09-16 12:47"
created_by_group: synthesize_003
reference_files:
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
- https://go.dev/doc/install/source#environment
- https://pkg.go.dev/gopkg.in/yaml.v3
- https://github.com/bmatcuk/doublestar
- https://github.com/actions/setup-go
- https://github.com/softprops/action-gh-release
- https://git-scm.com/docs/git-log
- ait
- website/go.mod
- .aitask-scripts/lib/artifact_utils.sh
- tests/test_no_unscoped_task_commit.sh
- tests/test_gate_verifiers.sh
- tests/test_frozen_agents_acceptance.sh
- tests/test_t167_integration.sh
- https://go.dev/doc/install
- https://go.dev/ref/mod#go-mod-file-toolchain
- https://go.dev/doc/go1.21#tools
- https://pkg.go.dev/github.com/bmatcuk/doublestar/v4
- https://pkg.go.dev/golang.org/x/sync/errgroup
- https://git-scm.com/docs/git-hash-object
- .github/workflows/hugo.yml
- aidocs/framework/planning_conventions.md
- .aitask-scripts/aitask_gate.sh
- tests/test_serial_carveout_doc_drift.sh
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
- https://docs.pytest.org/en/stable/how-to/usage.html
- https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags
- https://pkg.go.dev/cmd/go#hdr-Testing_flags
- https://pkg.go.dev/cmd/go#hdr-List_packages_or_modules
- https://kotlinlang.org/docs/multiplatform-run-tests.html
- https://developer.android.com/studio/test/command-line
- https://git-scm.com/docs/git-status
- https://git-scm.com/docs/git-rev-parse
- .aitask-scripts/aitask_task_commit.sh
- .aitask-scripts/aitask_pick_own.sh
assumption_annotation_is_comment_only: 'Integrating an existing test into the architecture
  never changes what the test does: onboard adopt inserts `testmap:` comment lines with the
  file''s own comment leader - bash after the header comment block (after the shebang and
  leading # block), Python as # lines after the module docstring (the grammar reads docstring
  lines but adoption never writes into one because that changes __doc__), Go after the package
  clause, Kotlin after the import block or inside the member''s testmap:unit block for a member
  seed - the runners execute the unchanged test, and `git diff -w --ignore-blank-lines` of
  an adopted file shows comments only; a test that cannot be annotated by comment (no comment
  leader the grammar knows) is skipped with ADOPT_SKIP:no-leader and stays seeded; existing
  `# Covers:` prose headers are shown beside the seeds as reviewer context and read by the
  prose origin, never rewritten (n008''s rule, with n007''s member-block placement)'
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
  is the right intake for every --task path - the gate verifiers, `ait test` in interactive,
  completion and advisory mode, and stale --task: the front pipes its COMMITTED:/TASK:/OTHER:/UNKNOWN:
  lines into the engine''s --changes - (its exit codes carry no meaning, the engine parses
  lines only), selection never reads a raw git diff, and an UNKNOWN: row refuses selection
  in interactive and completion mode and surfaces as VERDICT:skip REASON:unknown_paths naming
  the paths in advisory mode, never as a run over another task''s work; `ait test <path>...`
  is the one explicit-list intake (TASK: rows), `--dirty` the explicit and printed no-task
  intake, and `--all` has no intake; the before content a symbol scanner needs comes from
  HEAD:<path> (TASK: rows) or the parent of the first (t<id>) commit (COMMITTED: rows) and
  is absent - so the whole file is the symbol set - when history is unreachable (merged from
  n007 and n008 over n005)'
assumption_cochange_is_corroboration: '(t<id>)-tagged commit history is a corroborating signal,
  never a primary one: in the last 400 commits touching tests/ or .aitask-scripts/ on aitasks
  there are 336 task groups averaging 1.14 commits each, and a group pairs a few tests with
  a few scripts (t1159_1: 4 tests x 4 scripts) with nothing inside the group to say which
  test covers which script, so co-change scores 0.20 + 0.20 x distinct task groups capped
  at 0.60, requires >= 2 distinct tasks (min_cochange), and cannot reach the 0.85 class-acceptance
  threshold alone or with convention (0.84 at the cap); repositories without the (t<id>) convention
  fall back to per-commit grouping with the same cap; one `git log --name-status -M --format=%H%x00%s`
  pass cached by HEAD sha, SEED_HISTORY:shallow|<n> on a shallow clone (n008''s cap replacing
  n007''s 0.5-0.8 ladder; n007''s min_cochange and cache kept)'
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
assumption_full_run_expressible_per_repo: 'Every target repository''s completion suite is
  expressible as `ait test --all` over its runners or as one full: true suite runner generated
  by onboard detect from test_command with a children: post-processor and a fallback_command:
  - thinking_app''s verify-active (already test_command; screen-matrix and gradle-class subsumed_by
  it), thinking_backend''s scripts/tests/run_script_tests.sh (22 bash + 18 python tests, wired
  today as verify_build because it also runs a shellcheck baseline - the skill asks and keeps
  it by default, adding test_command: ./ait test over the detected units), aitasks_go''s `go
  test ./...` over 85 packages, aitasks_mobile''s `./gradlew check` minus the 3 androidDeviceTest
  classes which run only under device_policy, and aitasks'' 400 bash + 320 python units which
  had no suite command at all (test_command: null) and gain one; fallback_command is derivable
  for each from detect''s output (n008, merged with n007''s detect-generated wrapper)'
assumption_gate_exit_contract_reused: 'The framework verifier contract (0 pass / 1 fail /
  2 skip / 3 error) is reached through the EXISTING tests_pass verifier running test_command:
  `./ait test --gate` speaks 0/1/2/3/75/64, and run_project_command_key() - the single canonical
  statement of the command exit contract - gains two rows for opted-in keys: 75 -> error (PROJECT_CMD_STATUS=error,
  CODE=3, REASON=command_refused) and 3 -> error (command_errored), so an admission refusal
  that survived the in-engine deferral or a missing engine is a verifier error the orchestrator
  retries within budget, never a code failure and never a skip; 2 (nothing ran: empty selection)
  stays the opt-in skip. The verifier exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID to the command,
  which is how `./ait test` knows it is in completion mode and for which task; aitask_run_project_command.sh
  --task-id exports the same, so the legacy Step-9 path, aitask-qa and the gate agree by construction.
  testmap_check keeps its own verifier shell mapping engine exits 0/1/2/64 and a missing engine
  to 0/1/2/3/3. The advisory mode of `ait test` speaks aitask_run_project_command.sh''s 0/1/2/3
  domain with 75 folded into VERDICT:skip REASON:admission_refused and usage errors into 3,
  so the Step-7 procedure and the Step-9 path cannot disagree about an exit code. n001 reused
  the contract through two dedicated shells; here it is one shell plus two rows in the shared
  lib (merged from n007 and n008)'
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
assumption_helper_degrades_when_absent: '`ait test --advisory` can always answer: engine missing
  (ENGINE_MISSING from the shim) -> VERDICT:skip REASON:testmap_absent; no aitestmap/ -> VERDICT:skip
  REASON:registry_absent; UNKNOWN: rows in the change surface -> VERDICT:skip REASON:unknown_paths
  naming them; empty selection -> VERDICT:skip REASON:no_selection with UNMAPPED_SOURCE lines;
  admission refused after the deadline -> VERDICT:skip REASON:admission_refused; only a run
  that executed maps to pass/fail, and only a front that cannot write its LOG: exits 3. This
  is what lets the pre-review Affected Tests procedure sit before Step 8 in every profile
  including remote (Claude Code Web has no engine) without a conditional per environment;
  the interactive and completion modes of the same script keep n006''s rule that a missing
  engine is an error (n007''s helper assumption, restated for the advisory mode of n008''s
  entrypoint)'
assumption_helpers_separable_by_fanin: 'Within a test file''s closure, helpers (asserts, fixtures,
  fakes) are separable from subjects by two rules the skill confirms: a path under a declared
  helper root (tests/lib/**, **/testing/**, **/src/test/** for Kotlin, **/testdata/**) is
  a helper, and any other closure path whose fan-in reaches >= helper_fanin (default 5% of
  the runner''s units) is a helper; helpers get test-dep through the closure and, when they
  glob the tree (ls tests/*.sh, glob.glob, rglob, find, git ls-files, os.walk - aitasks: tests/lib/import_isolated.py,
  board_fixture.py, validate_session_hook_fixtures.py), a proposed testmap:reads (SEED_READS:)
  written at level 2 on class acceptance; subjects become covers candidates. Falsifier: a
  hot production module imported by most tests would be misread as a helper and lose its covers
  edges - it keeps test-dep selection, over-selecting rather than under-selecting, and the
  skill lists every fan-in reclassification for review (n008)'
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
assumption_instruction_block_is_read: 'Code agents load CLAUDE.md / AGENTS.md at session start
  and follow a managed block that names one command: the framework already relies on this
  for `./ait git`, notes and commit format, and ait setup regenerates the >>>aitasks block
  on every run (t1612), so a `## Running Tests` section reaches every agent in every onboarded
  project with no per-project authoring; the hand-maintained-CLAUDE.md case (sentinel present,
  no markers) is this repository and is edited by the level-0 onboarding task. Falsifier:
  an agent whose harness does not read the file - for which `ait test --howto` is the one-call
  fallback (n008; complementary to n007''s mechanism assumption)'
assumption_instructions_block_reaches_agents: The seeded agent-instructions block (seed/aitasks_agent_instructions.seed.md,
  installed to aitasks/metadata/ and assembled by assemble_aitasks_instructions()) is inserted
  between >>>aitasks / <<<aitasks markers into every supported agent's instructions file (CLAUDE.md,
  AGENTS.md, .codex/instructions.md, the OpenCode mirror) by ait setup and refreshed on re-run
  and on upgrade (insert_aitasks_instructions replaces the marked block) - verified in aitask_setup.sh
  - so the generic Running Tests section added to the seed reaches every onboarded and not-yet-onboarded
  project on its next setup with no per-project edit, and is the one always-loaded place an
  agent learns the run surface. The section names no code agent (documentation convention),
  carries no project specifics (those are `ait test --howto`'s computed output) and stays
  at fourteen lines so it costs every session the same small context; the hand-maintained
  CLAUDE.md case (sentinel present, no markers) is edited by the level-0 onboarding task (n007,
  merged with n008's no-project-specifics rule)
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
  comment lines, project config, profile and gates edits) across several sessions, so each
  level runs as an aitask: /aitask-testmap-onboard creates and claims `testmap onboarding
  level <n>` (issue_type chore, labels testing,testmap) through aitask_create.sh --batch and
  aitask_pick_own.sh, attaches the seed dump with ait attach, records the task id and level
  in onboard.yaml, continues into task-workflow, and every phase at Step 7 commits its files
  through aitask_task_commit.sh under `chore: Onboard testmap - <phase> (t<id>)` so the change
  surface attributes them and a resumed session re-enters at ONBOARD_NEXT; Step 8 reviews
  the diff, the level-0 task''s Step-9 tests_pass is the first full run, and the next level''s
  task is created with depends: on this one because a level may wait weeks on full-run history.
  Falsifier: a repo that forbids tasks on the code branch - for which --no-task writes without
  committing and prints the commit lines to run (n007''s task shape merged with n008''s one-task-per-level)'
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
assumption_seed_sources_measured: 'One origin table seeds edges, each origin measured on 2026-09-16
  by one or both explorers and none below 1.0 trusted alone: static:package (a _test.go''s
  own package: deterministic, 1.0), coverage (opt-in per-unit runtime coverage where the tool
  supports it: coverage.py dynamic contexts, go -coverprofile per -run, LCOV with a test column,
  a project plugin such as JaCoCo per-test sessions, 0.95), static:invocation (a bash test
  naming a repo path literally: 350-398/400 aitasks bash tests, avg 3 paths, 0.90), static:import
  (a direct import of a main-root file: 255-320/320 aitasks Python tests avg 1, 139/339 thinking_app
  tests avg 3 - same-package references are invisible to imports and are NOT seeded because
  the package-connected fact is too coarse, 0.85), observed (an attribute --propose row from
  a scored miss, 0.70), convention (config.yaml conventions: patterns seeded by detect: 52-72/400
  bash, 62/320 Python, 48/307 Kotlin, 0.60), plan (an aiplans/ file naming both paths through
  the explain cache, 0.50), prose (a literal path in the header comment or a `# Covers:` line,
  0.30) and cochange ((t<id>) co-change in >= 2 distinct task groups: aitasks 439 of 600 task
  commits touch tests and scripts together at 2.8 x 2.6 but 336 groups in 400 commits average
  1.14 commits with nothing inside a group saying which covers which; thinking_app 127 of
  400 at 7.2 main files - hence 0.20 + 0.20 per group capped at 0.60, corroboration that can
  never reach the 0.85 class-acceptance threshold alone). Confidence combines by noisy-OR,
  orders the review queue and never hides a row. Seeding is partial by construction: the remainder
  is rules, waivers and incremental adoption (n007''s measurements merged with n008''s table
  and cap)'
assumption_seeds_select_never_evidence: 'A seeded edge is safe to act on in exactly one direction:
  it may cause a test to run (over-selection costs time) and may never suppress a STALE row,
  anchor evidence, satisfy require_stamp or count as coverage for UNMAPPED_SOURCE under --strict
  (under-claiming a freshness fact costs correctness). So seeds live in a generated file (registry/seeded.yaml),
  carry no stamp, are excluded from stale, are counted separately by check (SEEDED:<n>), and
  become claims only through an explicit adopt that writes the line and the stamp - by class
  (with an adopted.yaml provenance row, ADOPTED:<n>) or by row (a reviewed claim). Autonomous
  profiles may seed and may adopt only origins whose confidence is a language rule (1.0),
  never a heuristic. Falsifier: a project whose full suite is so expensive that seeded over-selection
  is itself the cost problem - for which the suite budget and --format tokens preview are
  the levers, not trusting seeds (n007; the adopted state from n008 sits above it)'
assumption_static_closure_seeds_edges: 'The test-file static closure is a sufficient primary
  seed for covers edges on the target shapes, and naming conventions are not: measured on
  aitasks, 398 of 400 tests/test_*.sh name an aitask_*.sh or lib/*.sh|py path literally (the
  two that do not are pure fixture tests), 320 of 320 tests/test_*.py import a .aitask-scripts/lib
  module through a sys.path bootstrap, while only 52 of 400 bash tests map to .aitask-scripts/aitask_<stem>.sh
  by the tests/test_<stem>.sh convention aitask-qa relies on today; on aitasks_go the subject
  is deterministic (a _test.go covers the non-test files of its own package, confidence 1.0);
  on Kotlin the import graph is the same scanner n006''s Kotlin closure uses. Only the direct
  relation is seeded; the deeper closure stays the selector''s d2 walk. Falsifier: a project
  whose tests reach subjects only through a dynamic dispatcher (a CLI tests drive by name)
  - for it seed emits no static rows and the skill offers convention rules and co-change,
  or level 0 only (n008, measured; the static origin split into invocation / import / package
  here)'
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
assumption_task_resolvable_from_session: '`ait test` can find the task an agent is implementing
  without being told: task-workflow names worktree branches aitask/<task_name> where <task_name>
  is the task file stem (t<id>_<slug>), so `git rev-parse --abbrev-ref HEAD` yields the id
  in worktree mode; in current-branch mode (fast profile, create_worktree: false) the task
  lock this user holds on this host is unique per Implementing task, so a `--list-mine` listing
  on aitask_lock.sh yields it; two or more yield AMBIGUOUS_TASK:<ids> and require --task;
  gate context supplies AIT_GATE_TASK_ID; the Step-7 advisory form always passes --task explicitly
  because the procedure knows the id. Falsifier: an agent implementing outside the workflow
  (no lock, no branch) - for whom `ait test --dirty` is the explicit, printed, never-default
  intake (n008; n007''s explicit --task kept as the override)'
assumption_test_tools_detectable: 'The test tools of every target repo are detectable from
  the tree and the project config without executing a build: pytest.ini / pyproject [tool.pytest]
  / conftest.py / tests/*.py with a runner script; go.mod plus *_test.go with packages from
  go list; gradlew plus src/<sourceSet>/ test roots (commonTest, androidHostTest, androidDeviceTest,
  test, androidTest); tests/test_*.sh with tests/lib/asserts.sh; package.json scripts.test;
  a Makefile test target; and project_config.yaml test_command / verify_build. Verified on
  the five repos: aitasks (bash + pytest via run_all_python_tests.sh with a 4-module serial
  carve-out), thinking_app (gradlew + the screenshot harness named by test_command), thinking_backend
  (run_script_tests.sh named under verify_build - detect reports SUITE_CANDIDATE:verify_build
  and the skill asks, keeping it by default), aitasks_go (Makefile test = go test ./... plus
  parity/run_parity.sh), aitasks_mobile (three gradle source-set roots, no test_command).
  Every FRAMEWORK: row carries its evidence so a reader can dispute it. Falsifier: a build-only
  test discovery (tests generated at build time), for which detect emits DETECT_UNKNOWN and
  the skill asks (n007 merged with n008''s evidence rows)'
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
component_adoption_ledger: 'Adoption ledger (new: introduced to bridge n007 and n008): the
  three-file state of a machine-proposed edge and the rules that move it - registry/seeded.yaml
  (n007''s queue: rows {test[#member], covers, origin[], confidence, evidence{}, proposed_at};
  select-only at d1 with reason edge(seeded:<origins>), no stamp, invisible to stale, never
  --strict, SEEDED:<n> on check / stale --all / readiness), registry/adopted.yaml (n008''s
  provenance: rows {test, source, origin[], confidence, adopted_at, task} for a stamped edge
  accepted by evidence class; shown as adopted(<origins> <confidence>) on stale and explain
  rows; counted as ADOPTED_UNREVIEWED:<n>|<ratio> by readiness and ADOPTED:<n> by check; a
  row is deleted when a human verify, stale --confirm-source, annotate or a per-row adopt
  re-stamps that edge) and onboard.yaml''s rejections[] (never re-proposed). Transitions:
  onboard seed / attribute --propose -> seeded; onboard adopt --class <origin> [--accept-min
  0.85] [--scope <glob>] -> adopted (stamp + provenance row); onboard adopt <test> <source>
  | --area <a> --batch <n> and the testmap_fresh in-gate step -> reviewed (stamp, no provenance
  row); human re-stamp -> reviewed; onboard reject -> rejected. Load rules: a seed whose (test,
  covers) exists as any stamped edge is dropped with SEED_SHADOWED; an adopted row whose edge
  no longer carries a stamp is ADOPTED_ORPHAN. Autonomous profiles may seed and may adopt
  only origins at confidence 1.0 (static:package). Tradeoffs recorded under tradeoff_two_edge_states_during_adoption
  and tradeoff_seed_precision'
component_agent_brief: 'Agent brief (internal/brief): engine verb `brief [--md]`, surfaced
  as `ait test --howto [--md]` and `ait testmap brief`, prints TESTMAP:<state>|since|LEVEL:<n>|POLICY:<mode>|seeds
  pending <n>|adopted unreviewed <n>, one RUNNER:<name>|<kind>|<units>|<how it is invoked>|<resources>[|subsumes
  ...] line per runner, FULL_GATE:<runner>|<p95 est>|<= project_config test_command>|<tests_pass
  timeout>, GATE: (the chain testmap_fresh -> testmap_check -> tests_pass and what --gate
  would run now), VERBS: (the four forms), AXES: per declared axis with facets and value counts,
  RESOURCE: per declared resource with its kind and what a refusal looks like (exit 75 ->
  deferred), NEW_TEST: (the annotate --suggest hint), DOCS:<path> per config.yaml docs: entry,
  NOTES: the config.yaml notes: lines verbatim (<=10, project-declared), and, while a ledger
  is unfinished, ONBOARD_NEXT:; before onboarding it prints TESTMAP_ABSENT plus the test_command;
  --md renders the same as markdown for agents; < 100 ms warm (n007''s brief merged with n008''s
  --howto content)'
component_agent_instructions: The shared agent-instructions seed (seed/aitasks_agent_instructions.seed.md)
  gains a fourteen-line `## Running Tests` section - run tests only through the framework
  entrypoint, never pytest / go test / gradle / a test script directly; `./ait test` (selected
  for the task, a reason per line), `./ait test <path>...` (a named unit; a SOURCE path runs
  what covers it), `./ait test --all` (the whole suite - what completion runs while the policy
  is full), `./ait test --howto` (runners, kinds, resources, full gate, policy, notes); UNANNOTATED_TEST
  -> `./ait testmap annotate --suggest <path>`; UNMAPPED_SOURCE -> map it before the gate
  (/aitask-testmap); TESTMAP_ABSENT -> /aitask-testmap-onboard; the exit-code table - installed
  unchanged into CLAUDE.md's >>>aitasks block, AGENTS.md, .codex/instructions.md and the OpenCode
  mirror by the existing assemble_aitasks_instructions() on every ait setup and ait upgrade;
  tests/test_agent_instructions.sh gains T40 asserting the heading in all four rendered surfaces
  through a real install.sh --dir; the seed carries no project specifics and names no agent
  - `ait test --howto` computes them so the current-state-only doc rule holds and nothing
  condensed from runners.yaml lives in a constant; the hand-maintained CLAUDE.md case is the
  level-0 onboarding task's edit (merged from n007 and n008)
component_annotation_scanner: 'Annotation scanner and rewriter (internal/annot): grammar v3
  - testmap:unit <Member> opens a member block that owns every following testmap: line until
  the next testmap:unit or end of file (a file-level block precedes the first unit); testmap:kind,
  testmap:covers <path> @<date>/<blob10>, testmap:area, testmap:scope, testmap:trigger, testmap:reads
  <glob> (helper files only), testmap:axis <axis>.<facet>=<value>, testmap:reviewed, runner/needs/batch
  - per comment leader and Python module docstrings (read); refuses unknown keys with a line
  number; the line-targeted rewriter edits stamps by (file, line, current text) and refuses
  on REWRITE_CONFLICT; annotate --from-body seeds covers for a member from the kotlin scanner''s
  symbol resolution of the block''s own lines; produces both generated files from every runner''s
  list output - n006 unchanged; `onboard adopt` is a new caller of the rewriter, not a new
  writer: it inserts testmap:covers lines at a fixed position per language, comment lines
  only (bash after the shebang and leading # block; Python as # lines after the module docstring,
  never inside it; Go after the package clause; Kotlin after the import block, or inside the
  member''s testmap:unit block for a member seed), each stamped @<date>/<blob10> at adopt
  time, one file rewritten per adopted item; existing `# Covers:` prose headers in aitasks
  are shown beside the seeds as reviewer context and read by the prose origin at 0.30, never
  matched by the annotation scanner and never rewritten (merged from n007 and n008)'
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
component_completion_policy: 'aitestmap/config.yaml `completion:` block: mode full|selected
  (full by default; selected is written only by the onboarding skill''s --policy re-entry
  after READINESS_DECISION:ADMISSIBLE, beside run_gate_admission.approved_by), deferred run|fail
  (what completion does with rows the interactive budget would cut; default run), on_empty_selection
  skip|full (default skip -> exit 2 -> gate skip under the opt-in), engine_absent error|fallback_command
  (default error). `ait test --gate` re-checks readiness on every completion run and, if mode
  is selected but a criterion is unmet (a new false negative, a regressed opaque proof), prints
  POLICY_DEMOTED:selected->full|<criterion> and runs full - the flip is a human decision and
  the demotion is automatic, so the policy can only fail toward running more; readiness prints
  POLICY:<mode>|<what --gate would run now>; the gate-run ledger block carries result="MODE:<full|selected>|<n
  units>|policy:<mode>" (n008)'
component_cost_ledger: Cost ledger (internal/cost) as n006 (Welford per (id, host class) where
  id may be a variant, with P2 p95 and last; per-repo ledger .aitask-testmap/ledger.jsonl
  with run_id/id/status/duration_ms/head_sha per result and {run_id, group, overhead_ms, units_reported}
  per invocation; costs --update folds both into aitestmap/costs/<hostclass>.yaml and truncates;
  last_pass {sha, at, run_id} per id and a flake rate with flake_threshold; the estimate for
  a selection is the sum over invocation groups of overhead.p95 + the p95 of each selected
  id, reported per kind; costs/predictions.yaml holds the last 200 scored full runs); an `ait
  test` run writes ordinary rows with run_id prefixed test- (interactive and advisory), gate-
  (completion) or full- (--all) so Step-7 runs and completion runs feed cost and evidence
  exactly like any run and the ledger says which surface produced a row; the SELECTED:<n>|<est_s>
  line's estimate is the same per-group sum the budget uses; `costs --gate-timeout tests_pass`
  prints GATE_TIMEOUT_SUGGESTED:<gate>|<seconds> = max(600, 3 x p95 of the newest full run
  on this host class), which onboarding's full-run phase writes into the project's gates.yaml
  after the first measured full run (merged from n007 and n008)
component_dependency_scanners: Dependency scanners (internal/deps) as n006 (built-in bash,
  python, go (go list -deps -json cached by go.sum digest), kotlin with the opaque contract
  over main and test roots, Gradle module graph, executable plugins under aitestmap/scanners/
  speaking one JSON line per file {file, deps, opaque?, reads?}, the opt-in android-res symbol
  scanner, forward deps cached per source blob under ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json
  and inverted in memory); the bash scanner's literal-invocation facts (a test that runs ./.aitask-scripts/x.sh
  or sources lib/y.sh, including $SCRIPT_DIR- and $PROJECT_DIR-relative forms resolved against
  every source root), the python and kotlin scanners' direct imports of a main-root file (Python
  through the file's own sys.path bootstrap) and the go scanner's package membership are exposed
  to internal/seed as the static:invocation, static:import and static:package origins - same
  scan, same cache, read once; the deeper closure stays the selector's d2 walk and is never
  seeded as an edge (merged from n007 and n008)
component_engine_binary: 'Engine binary identity and budget as n006 (version/commit/contract
  embedded; version --json prints ENGINE:<path>; fixed-prefix output; CONTRACT_MISMATCH; go
  test -bench budgets with the 2x rule on the aitasks and thinking_app-shaped golden registries;
  pools capped at 8) with the verb table extended by test, brief, onboard {detect,inventory,seed,classify,adopt,reject,scaffold,status,finish}
  and costs --gate-timeout; budgets added: brief < 100 ms warm, onboard seed static + convention
  < 2 s and cochange < 5 s over 600 (t<id>) commits (one git log pass, parsed once, cached
  by HEAD sha under the XDG cache) on the aitasks shape, onboard status < 200 ms; detect is
  excluded from the latency table (once per onboarding, execs git log and every list, not
  on any gate path); contract stays 1 (seeded.yaml, adopted.yaml and onboard.yaml carry their
  own contract: field and a newer one is refused the same way) (merged from n007 and n008)'
component_engine_packaging: 'Engine install and developer regeneration as n006 (install_engine_binary()
  in aitask_setup.sh, reached by ait setup and by ait upgrade through install.sh''s --source-only
  path beside install_global_shim; sources lib/aitasks_home.sh; uname mapping; .sha256 sidecar
  short-circuit; source order --local-engine > exact-version release asset > --engine-from-source
  > ENGINE_MISSING warning; sha256sum -c / shasum -a 256; atomic install to $AITASKS_HOME/engine/v<V>/;
  version --json must echo <V>; .dev-marked binaries never overwritten without --force-engine;
  --no-testmap / AIT_TESTMAP_FETCH=0 print TESTMAP_BINARY:skipped; HOME_LEGACY: hint when
  legacy tenants exist; .aitask-testmap/ gitignored by setup; aitask_engine.sh with ait engine
  build|test|cross|prune|home [--migrate]) plus report_testmap_state() run after it: prints
  TESTMAP:engine-missing when the binary is absent, TESTMAP:absent (with `run /aitask-testmap-onboard`)
  when aitestmap/ is absent, TESTMAP:bootstrapping|<next phase> while onboard.yaml has an
  unfinished phase, and TESTMAP:onboarded otherwise; setup reports, it never onboards; the
  seeded agent-instructions block re-inserted by setup gains the Running Tests section; aitask_test.sh
  is a framework script shipped in the tarball like every aitask_*.sh, nothing to install;
  tests/test_install_engine_binary.sh through a real install.sh --dir --local-engine asserts
  the $AITASKS_HOME path and the TESTMAP: line in each state (merged from n007 and n008)'
component_evidence_join: 'Evidence join (internal/stale + internal/gitx, reads internal/cost):
  for every edge whose stamped_blob differs from the current blob, collects last_pass shas
  per reached variant from the local ledger and committed costs (any host class), drops candidates
  from invocations with a cause or ids over the flake threshold, keeps shas that are ancestors
  of HEAD, and runs one git ls-tree per distinct sha; an edge is EVIDENCED when every reached
  variant has a sha whose source object id equals the current blob, otherwise STALE with the
  unevidenced variants listed; never rewrites - stale --confirm-evidenced is the explicit
  re-stamp and the only bulk confirmation an autonomous profile may run (inherited from n005)'
component_feedback_tools: 'Feedback tools (internal/feedback): score (automatic after run
  --all and after a full: true suite run, printing PREDICTION_SCORED / PREDICTION_FALSE_NEGATIVES:<n>
  / PREDICTION_MISSED:<id> and appending to costs/predictions.yaml), attribute (missing-edge
  / test-wrong / source-wrong, missing-axis-source widen-only, missing-trigger / area-too-narrow),
  readiness (n006); new: an attribute decision may be `propose` (default in autonomous profiles)
  which writes the row to seeded.yaml with origin observed (0.70) and the run id as evidence
  instead of to observed.yaml, so autonomous runs grow the review queue and never the accepted
  map; readiness additionally prints LEVEL:<0-3> (derived from what exists: runners.yaml ->
  0, any stamped _scanned edge -> 1, any _scoped row or reads -> 2, axes.yaml -> 3), NEXT:<the
  phase or level that raises it>, ADOPTED_UNREVIEWED:<n>|<ratio of covers edges> and SEEDED:<n>
  as informational criteria, and POLICY:<completion.mode>|<what ait test --gate would run
  now>; it still enables nothing (merged from n007 and n008)'
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
  dispatched by the existing procedure-gate block before the change summary so rewrites ride
  the (t<id>) commit; not a git hook, not a code-agent hook) with one more stamp writer, `onboard
  adopt` (by class with an adopted.yaml provenance row, or by row), and one more gate step:
  testmap_fresh offers to adopt or reject the seeds of the test files this task touched -
  the stamp then rides the same (t<id>) commit as the test edit, which is the moment the reviewer
  has the file open and the claim is cheapest to check; an adopted stamp is a stamp like any
  other and the procedure gate handles it identically, with the adopted(...) display as context
  (merged from n007 and n008)'
component_gates: 'Gates: testmap_fresh (kind: procedure, verifier aitask-gate-testmap-fresh,
  no unlocks; gains the adopt / reject / leave step for seeds on the task''s touched test
  files) and testmap_check (machine, max_retries 0, timeout 120, unlocks: [tests_pass]) in
  gates_reference.yaml synced to gates.yaml; the completion test gate is the EXISTING tests_pass
  with test_command: ./ait test and gate_command_exit_contract: [test_command], so `ait gates
  run` needs no new verifier for running tests and the legacy no-gates path needs no new prose
  - a project reaches the selective lane by declaring tests_pass (onboarding''s enable phase
  writes it into profiles'' default_gates with testmap_check and testmap_fresh, with confirmation;
  never by hand, never by ait setup); testmap_run is retired as a name (its logic is `ait
  test --gate`, its blocks_dependents and max_retries: 1 are tests_pass''s own, its timeout
  becomes a project tests_pass.timeout_seconds written from the cost ledger, its 75 -> error
  mapping lands in run_project_command_key for opted-in keys, --include-stale is applied by
  the composite, deferred rows run under completion.deferred: run); aitask_gate_testmap_run.sh
  is not written; aitask_gate_testmap_check.sh stays and reports SEEDED:<n> and ADOPTED:<n>
  (informational, never fail) and UNMAPPED_SOURCE:<path> (a changed source with no edge, seed,
  rule or waiver - reported during bootstrap, fails under --strict past bootstrap_until, the
  strict flip being onboarding''s finish phase); an unlocks: target absent from a task''s
  active set is ignored, so testmap_check declared alone is linear as before; run_gate_admission
  and `ait testmap readiness` gate the completion POLICY flip rather than a second gate''s
  declaration (n008''s one completion gate; n007''s SEEDED / UNMAPPED_SOURCE rows and enable-phase
  siting; n001/n002''s three-gate shape replaced)'
component_go_engine: 'Go engine and CLI: engine/cmd/ait-testmap with the n006 packages internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}
  plus internal/seed (the origins and their confidence table), internal/onboard (detect, inventory,
  classify, adopt, reject, scaffold, the phase ledger, status, finish) and internal/brief
  (the generated run brief); Go 1.26 with pinned toolchain, CGO_ENABLED=0, -trimpath -buildvcs=false
  -ldflags -s -w -X version/commit/contract; deps gopkg.in/yaml.v3, bmatcuk/doublestar/v4,
  golang.org/x/sync only; stdlib flag verb table, syscall.Flock, os/exec git; line-protocol
  stdout, --json, per-verb exit contracts; never writes aitasks/, aiplans/, .aitask-data/,
  a gate ledger, project_config.yaml, gates.yaml, profiles or CLAUDE.md, never invokes aitask_*.sh,
  and never needs its own install root - onboard''s task creation, profile and config edits
  are done by the skill through the framework''s own scripts, the engine only reads onboard.yaml''s
  task: and level: fields; fixture repos in t.TempDir() include synthetic git histories with
  (t<id>) commits for the cochange origin, one fixture per detect shape (bash-only, pytest,
  go, gradle, gradle-per-source-set) and one per opaque-scanner branch (merged from n007 and
  n008)'
component_onboarding_engine_verbs: 'internal/onboard behind `onboard detect [--write] | inventory
  | seed | classify [--apply] | adopt | reject | scaffold | status | finish` and the aitestmap/onboard.yaml
  phase ledger {contract, task, level, phases{detect, inventory, seed, waivers, enable, full_run,
  adopt, classify, scaffold, finish: {status, at, by, counts}}, rejections[]}. `detect` prints
  FRAMEWORK:<kind>|<glob>|<count>|<builtin>|<evidence> for a closed detector list (bash-file,
  pytest, go-test, gradle-class, kmp-sourceset, suite-from-config), UNIVERSE:<n>, UNLISTED:<n>
  test-looking files no detector claims, AGGREGATE_RUNNER:<path> and SERIAL_LIST:<path>|<n>
  for a runner script with a carve-out list, RESOURCE_HINT:<name>|<n tests>|<evidence> (real-repo
  git use, flock, a lock script), SUITE_CANDIDATE:test_command|verify_build|<cmd>, RUNNER_SCRIPT_NEEDED:<reason>
  from the grid heuristic; --write emits the level-0 files (config.yaml with bootstrap_until
  today+90, require_stamp false, concurrency serial, completion.mode full, conventions:, helper_roots:;
  runners.yaml with builtins, bindings and the full: true suite runner with fallback_command:;
  resources.yaml from hints; areas --import-codemap) and on an existing table prints DETECT_DIFF:
  and writes nothing without --force. `inventory` runs scan + every list + check and prints
  UNREGISTERED: as the to-do list. `seed` is component_seeder. `classify` wraps classify --suggest
  with the three onboarding signals and on --apply writes the level-2 kind/area/scope/reads/batch
  lines and needs: bindings for confirmed rows. `adopt` (--class <origin> [--accept-min 0.85]
  [--scope <glob>] [--dry-run] for bulk adoption with an adopted.yaml row per edge; <test>
  [<source>] | --area <a> --batch <n> | --files-from - for reviewed per-row adoption) writes
  stamped testmap:covers lines through internal/annot''s line-targeted rewriter at the fixed
  per-language position, refuses ADOPT_REFUSED:<path>|dirty-foreign for a dirty file outside
  the task''s change surface, skips duplicate / unregistered / no-leader, prints WROTE: per
  file and ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>. `reject <test> <source> --reason`.
  `scaffold --axes | --runner <builtin> --as <name> | --members` writes the level-3 axes.yaml
  skeleton, aitestmap/runners/<name>.sh whose describe/run exec the builtin and whose list
  prints SCAFFOLD_TODO until filled (check reports it), and testmap:unit member blocks. `status`
  prints phase rows, ONBOARD_NEXT:<phase>, seed queue counts per origin, ADOPTED_UNREVIEWED,
  tests-with-any-edge and sources-with-any-edge ratios, the oldest pending seed age and the
  rejections count. `finish` requires status green (no pending phase, seed queue <= a user-set
  threshold, check clean), flips require_stamp and --strict, records the phase. The engine
  reads onboard.yaml''s task: and level: and writes phase rows; it never creates a task, edits
  a profile, project_config.yaml, gates.yaml or CLAUDE.md, or commits - those are the skill''s
  through the framework''s own scripts (merged from n007 and n008)'
component_onboarding_skill: 'Onboarding skill: .claude/skills/aitask-testmap-onboard/ as a
  profile-aware stub + SKILL.md.j2 (resolver key `onboard`) with one procedure file per phase
  (detect.md, inventory.md, seed.md, waivers.md, enable.md, full-run.md, adopt.md, classify.md,
  scaffold.md, finish.md); Claude Code first, Codex and OpenCode ports as follow-up tasks;
  rendered goldens under tests/golden/skills/aitask-testmap-onboard/. Flow: preconditions
  (`ait testmap version` else stop with the ait setup hint; an unfinished onboard.yaml ->
  re-enter at ONBOARD_NEXT; a finished one -> refresh mode over units newer than adopted.yaml''s
  last row) -> read-only survey (`onboard detect`, `onboard seed --json --out`) and the level
  proposal (frameworks and counts, edges per evidence class with three samples each, helpers
  and their globs, kind candidates with reasons, UNLISTED files, RUNNER_SCRIPT_NEEDED, the
  config writes) -> one aitask per level created with aitask_create.sh --batch (chore, labels
  testing,testmap), the seed dump attached with ait attach, claimed with aitask_pick_own.sh,
  id and level written to onboard.yaml -> task-workflow honouring the profile: the plan is
  the phase list; at Step 7 each phase confirms and commits its files (level 0: detect --write
  with one AskUserQuestion per runner keep/edit/drop and the full suite wrapper; inventory
  resolving UNREGISTERED by bind or exclude:; seed with counts; waivers proposing rules for
  hot directories and expiring waivers (+90d) per UNMAPPED_SOURCE cluster; enable writing
  test_command: ./ait test with the previous value moved to the full runner (verify_build
  left alone unless the user names it as the suite - thinking_backend), gate_command_exit_contract
  += test_command, profiles default_gates += tests_pass, testmap_check, testmap_fresh (and
  rendered_gates when present), docs: and notes: for the brief, a hand-maintained CLAUDE.md
  Testing paragraph, all confirmed once as a table; level 1: adopt per evidence class - accept
  all / review a sample of ten / skip - or per area with --scope and --batch 50; level 2:
  classify per batch of 20 with kind changes confirmed individually; level 3: scaffold with
  the maintainer) under `chore: Onboard testmap - <phase> (t<id>)` commits; Step 8 reviews
  the annotation diff; the level-0 task''s Step-9 tests_pass is the first full run (full-run.md
  then runs costs --gate-timeout -> gates.yaml tests_pass.timeout_seconds and readiness ->
  LEVEL / NEXT and creates the next level''s task with depends:). `finish` when status is
  green. Headless (remote) profile: level 0 in full plus adoption of static:package origins
  only (--accept-min 1.0), no prompts, no kinds, no scaffold, no policy flip. `--policy selected`
  re-entry: flips completion.mode only when READINESS_DECISION:ADMISSIBLE, records approved_by
  {who, at, statement} in config.yaml, one ait: commit. `--no-task` writes without committing
  and prints the commit lines (merged from n007 and n008)'
component_qa_integration: 'aitask-qa reads the registry when aitestmap/ exists: test-discovery.md
  3a-3c map the changed sources through `ait testmap explain --sources <paths> --format table`
  (edges, test-deps, scoped rows; Covered / Covered (adopted) / Covered (seeded) / GAP for
  a source with no edge and no test-dep), falling back to the naming-convention scan only
  when no registry exists; test-execution.md 4a runs the configured `./ait test` through aitask_run_project_command.sh
  test_command --task-id <id> (which exports AIT_GATE_TASK_ID so the run is the task''s selection),
  4b runs named units through `ait test <path>`, 4c gains a REFUSED (host resources) row for
  verdict error / command_refused, and 4d''s coverage component uses registry edges rather
  than file-name matches with seeded rows counted as coverage that exists; the health score''s
  Tests component treats REFUSED like SKIP (merged from n007 and n008)'
component_reference_runners: 'Reference runners built into the binary as ait-testmap runner
  <name>: bash-file, pytest (junitxml; testmap:batch no honoured, the serial carve-out pinned
  by extending tests/test_serial_carveout_doc_drift.sh), go-test (per-file -run regex, -json),
  gradle-class (--tests <lowering> batch, one invocation per group_by group, JUnit XML inverted
  to ids through the list table, zero-match trap as a mechanism failure), suite (any command
  as one unit, optional child rows from a children: post-processor), device (allocator handle);
  command:/cwd: overrides; shadow-by-name with explain showing which won; engine-test over
  engine/; thinking_app''s tools/verification/testmap_runner.sh (screen-matrix: list from
  the two membership manifests + matrix_classes with an artifact column, run through screenshot-tests.sh
  unit-tests --tests) and verify-active as a full: true suite runner whose child rows come
  from lib/screenshot-diff-set.sh - n006 unchanged; onboard detect seeds the repository: bash-file
  for tests/**/test_*.sh, pytest for test_*.py / *_test.py (an aggregate runner script''s
  serial carve-out list becomes testmap:batch no candidates), go-test per package from `go
  list`, gradle-class for src/test/**/*.kt|java, a kmp-sourceset detector mapping commonTest
  / androidHostTest to gradle-class unit runners (:<module>:jvmTest, testDebugUnitTest) and
  androidDeviceTest to the device runner (connectedDebugAndroidTest, needs: [emulator]), and
  a `full: true` suite runner named `full` wrapping project_config.yaml test_command (or verify_build
  only when the user names it as the suite - thinking_backend keeps verify_build by default)
  whose children: post-processor is a builtin that inverts pytest junitxml, bash-file test
  names from the per-file exit and `go test -json` events to registered ids, and whose fallback_command:
  is the previous test_command, so the existing full gate anchors evidence from day one without
  a project script; the bash-file builtin gains a `list --invocations` mode printing the literal
  repo paths a test references (the seeder''s static:invocation origin) (merged from n007
  and n008)'
component_registry_loader: 'Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  plus axes.yaml into the six n006 tables (edges, scopes, areas, rules, waivers, axes) with
  unit ids <path>[#<member>][@<variant>], each member''s variants: list from _scanned.yaml,
  owns: routing by glob for edges and rules and by area name for hand-declared scopes, observed
  axis sources merged at load widen-only, deterministic sorted writes only on change, and
  the n006 check rules (STALE_PATH, UNSTAMPED past bootstrap under require_stamp, DEAD_SCOPE,
  DEAD_AXIS_SOURCE, UNKNOWN_VARIANT, UNCOVERED_VALUE, UNANNOTATED_MEMBER, DEAD_MEMBER, UNREGISTERED,
  UNMAPPED_ARTIFACT, KIND_MISMATCH|CONVERT_TO_SUITE, CONTRACT_MISMATCH) - unchanged; two tables
  added: seeds from registry/seeded.yaml (rows {test[#member], covers, origin[], confidence,
  evidence{}, proposed_at}) and adopted from registry/adopted.yaml (rows {test, source, origin[],
  confidence, adopted_at, task}, the set of stamped covers edges accepted by class that no
  human has reviewed per pair); a seed whose (test, covers) pair also exists as any stamped
  edge is dropped at load with SEED_SHADOWED reported by check; an adopted row whose edge
  no longer carries a stamp is ADOPTED_ORPHAN; write routing gains onboard seed -> seeded.yaml,
  onboard adopt -> seeded.yaml (row removed) + adopted.yaml (class adoption only) + the test
  file through the rewriter, onboard reject -> seeded.yaml (row removed) + onboard.yaml (rejection
  recorded so the seeder never re-proposes it), attribute --propose -> seeded.yaml, and a
  human re-stamp (verify, annotate, stale --confirm-source, per-row adopt) -> adopted.yaml
  (row removed); config.yaml gains completion:, conventions:, helper_roots:, helper_fanin:
  (n008) and exclude: globs (fixtures, helpers, generated tests - never listed, never UNREGISTERED),
  docs:, notes: (<=10 lines) and broad_threshold_s (n007); golden tests pin the two new table
  merges, the shadow rule and the id grammar (merged from n007 and n008)'
component_runner_contract: 'Runner contract and repository (internal/runner): describe (unit
  file|class|method|variant|suite, axis:, batch, needs, group_by:, token_format:, filter_scope:,
  full:, children:, artifact_glob:), list as TSV <id> <kind> <lowering> [<artifact>] with
  member and variant ids, run --manifest with ids, lowerings and groups, results.jsonl per
  id with optional child rows under a suite parent, runner.json with per-group overhead rows,
  first-match bindings and per-test override, the builtin: scheme with command:/cwd: overrides
  and shadow-by-name, batching by (runner, group, resource set, batch flag), per-unit timeouts,
  units_expected/units_reported reconciliation per id with zero-reported-some-expected and
  no-registered-id as mechanism failures, exit contract 0/1/2/75 plus 64 - n006 unchanged;
  repository keys added: `subsumed_by: <suite>` on a runner whose units are the child rows
  of a full: true suite runner, so `run --all` executes the suite once and never the subsumed
  runner beside it (thinking_app: screen-matrix and gradle-class subsumed by verify-active),
  and `fallback_command:` on a suite runner - the pre-onboarding test_command or an equivalent
  detect derived - which `ait test --gate` runs when the engine binary is absent and completion.engine_absent
  is fallback_command (n008); `onboard scaffold --runner <builtin> --as <name>` emits aitestmap/runners/<name>.sh
  whose describe and run exec the builtin and whose list is a stub printing SCAFFOLD_TODO
  until the project fills it, which check reports (n007''s runner scaffold re-sited) (merged
  from n007 and n008)'
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
component_seeder: 'Seeder (internal/seed): `ait testmap onboard seed [--from static,convention,cochange,plan,prose,coverage]
  [--min-cochange 2] [--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json
  --out <f>]` produces registry/seeded.yaml rows {test[#member], covers, origin[], confidence,
  evidence{static: file:line, convention: pair, cochange: [task ids], plan: path, prose: line,
  coverage: run id}, proposed_at}; static:{package, invocation, import} read internal/deps
  facts for the test file only (direct, never the closure; same-package facts excluded); convention
  applies config.yaml conventions: patterns seeded by detect per runner (bash-file: test_<x>.sh
  -> aitask_<x>.sh | lib/<x>.sh | lib/<x>.py; pytest: test_<x>.py -> any <x>.py under the
  main roots; go-test: <x>_test.go -> <x>.go same dir; gradle-class: <Stem>[Test|*Test].kt
  -> <Stem>.kt under main); cochange parses one `git log --name-status -M --format=%H%x00%s`
  pass over commits whose subject matches (t<id>) and counts (test, source) pairs across distinct
  tasks (per-commit grouping fallback), cached by HEAD sha, SEED_HISTORY:shallow|<n>; plan
  reads the aitask_explain_extract_raw_data.sh cache; prose reads header comments and `# Covers:`
  lines; coverage imports coverage.py contexts JSON, go -coverprofile per unit, LCOV with
  a test-id column, or a project plugin''s {test, covers} lines. Confidence table static:package
  1.0 / coverage 0.95 / static:invocation 0.90 / static:import 0.85 / observed 0.70 / convention
  0.60 / plan 0.50 / prose 0.30 / cochange 0.20 + 0.20 per group capped 0.60, noisy-OR across
  origins, ordering only. Helpers separated first by helper_roots and helper_fanin with SEED_HELPER:
  and SEED_READS:<helper>|<glob>|<evidence> lines; SEED_KIND:, SEED_BATCH_NO:, SEED_MEMBER:,
  SEED_AXIS: from onboard classify''s signals. A rejected pair in onboard.yaml is never re-proposed;
  a pair already stamped is dropped with SEED_SHADOWED; --apply writes, otherwise prints SEED:<test>|<source>|<origins>|<confidence>
  lines; --json --out writes the dump the skill attaches to the level task. Budget: static
  + convention < 2 s and cochange < 5 s over 600 commits on the aitasks shape. Fixtures: a
  synthetic repo per origin with a (t<id>) history (merged from n007 and n008)'
component_selector: 'Selector (internal/selectr, internal/changesurface): n006 unchanged -
  line-protocol intake refusing UNKNOWN:, the graded walk with select/implies/escalate rules,
  variant expansion and axis join, test-dep at d1, ESCALATE on opaque files, scoped join,
  kind-then-cost ranking, invocation groups, stale marks from digest compare plus the per-variant
  evidence join, --include-stale, suite budget with DEFERRED lines and budget-exempt triggers
  and reads, cut knobs incl. --axis, --format lines|json|tokens, prediction record, explain
  - plus: a seeded edge is walked exactly like an annotation edge at d1 with reason edge(seeded:<origins>)
  and never contributes a stale mark; an adopted edge is an annotation edge whose reason carries
  adopted(<origins> <confidence>); `explain --sources <path>... --format table` prints the
  reverse view (every unit reaching each source with its reason and provenance, or UNMAPPED_SOURCE)
  as the table aitask-qa''s test discovery consumes; the `test` composite prints one SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>
  line and UNMAPPED_SOURCE:<path> lines before the ranked rows so the front can build its
  VERDICT without parsing the rows; `ait test <source path>` reaches it as a one-row TASK:
  change set from the front (merged from n007 and n008)'
component_skill: 'Skills: (1) aitask-testmap (n006: annotate a file / member / coordinate,
  declare axis sources, reads on helpers, axes --explain, attribute before the gate, verify
  after editing, classify --suggest, select --format tokens into a render loop) now opens
  with `ait test --howto` and hands a repo without aitestmap/ to aitask-testmap-onboard; (2)
  aitask-gate-testmap-fresh (the procedure gate: stale --task, git diff per STALE row with
  unevidenced variants, retarget STALE_PATH, re-stamp EVIDENCED, resolve check''s structural
  rows, prompt on UNSTAMPED past bootstrap, never guess UNKNOWN, never confirm STALE autonomously;
  an adopted(...) row is confirmed knowing it is a class-accepted claim) gains one step: for
  each COMMITTED:/TASK: test file with rows in seeded.yaml it shows the seeds with their evidence
  and offers adopt / reject / leave per row, so a map migrates a few files per task through
  ordinary work; (3) the new aitask-testmap-onboard (component_onboarding_skill), profile-aware.
  Every skill''s runtime knowledge of how to run tests is the seeded `## Running Tests` block
  plus `./ait test --howto`, never prose in a SKILL.md. All ship Claude Code first with wrapper
  surfaces regenerated by aitask_audit_wrappers.sh apply-wrapper for Codex and OpenCode (merged
  from n007 and n008)'
component_staleness_tool: Staleness tool (internal/stale) as n006 (stale --task --changes
  - | --all; the SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION
  line classes with %25/%7C encoding; a STALE row on a unit with variants carries a trailing
  |<unevidenced variants> field; --all adds CHECK_STRUCTURAL:<n>; content states exit 0, --strict
  exits 1 on STALE_PATH; compares blob digests of the working tree only, consults the per-variant
  evidence join, adds rename hints and culprit task ids from git log --name-status -M when
  history is reachable; mutates stamps via --confirm, --confirm-source, --confirm-evidenced,
  --retarget through the rewriter with a re-scan of touched files) with seeded edges excluded
  from every class, SEEDED:<n> and ADOPTED:<n> summary lines on --all beside CHECK_STRUCTURAL:<n>,
  and a STALE or EVIDENCED row whose edge has an adopted.yaml row carrying `adopted(<origins>
  <confidence>)` in its DISPLAY line so the procedure gate knows it is confirming a class-accepted
  claim, not a per-pair reviewed one (merged from n007 and n008)
component_suite_registry: 'Scoped-row registry and areas as n006 (registry/areas.yaml plus
  areas: blocks in hand files, seedable via areas --import-codemap; _scoped.yaml rows {test,
  kind, runner, areas, globs, triggers, reads_from, needs, reviewed_at, line}; owns: by area
  name for hand-declared rows; the d1 join, kind ranking, suite budget (suite_budget_s default
  600) with DEFERRED lines and budget-exempt triggers; check rules incl. DEAD_SCOPE and KIND_MISMATCH|CONVERT_TO_SUITE;
  ait testmap areas; classify --suggest with the reads-helper and grid heuristics; missing-trigger
  / area-too-narrow in attribute; a rule may select: a scoped test or a member by name); classify
  --suggest gains the three signals onboarding''s classify phase uses - a recorded p95 above
  broad_threshold_s (default 60) from the first full run, a source-set or directory convention
  (androidTest/, androidDeviceTest/, *_live.py, *_integration.sh, parity/) and a resource
  declaration or use in the file (tmux, App.run_test, install.sh --dir, real .git use, emulator,
  docker, network), plus fanout:<n> above unit_covers_max - each printed as the reason on
  the CLASSIFY:<test>|<kind>|<reason> line the skill confirms per batch of 20 with kind changes
  confirmed individually, and `onboard classify --apply` writes the confirmed rows'' source
  lines at level 2 (merged from n007 and n008)'
component_test_entrypoint: '`ait test` = .aitask-scripts/aitask_test.sh, a ~150-line bash
  front over the n006 shim (aitask_testmap.sh): flags --task <id> | --gate | --advisory |
  --all | --dirty | --explain | --howto [--md] | --tokens | --fresh-only | --budget-s <n>
  | --json and positional <path|id>...; resolves MODE (completion iff --gate or AIT_GATE_TASK_ID;
  advisory iff --advisory; else interactive), TASK (--task > AIT_GATE_TASK_ID > aitask/<name>
  branch > single own lock via aitask_lock.sh --list-mine > NO_TASK), INTAKE (aitask_change_surface.sh
  list <id> piped; --dirty = every dirty path as TASK: rows, printed; --all; named paths:
  a listed test path is the unit, a source path is a one-file TASK: change set) and POLICY
  (completion: config.yaml completion.mode re-checked against readiness); calls the engine
  `test` composite (select --include-stale -> schedule -> run; interactive: budget applies,
  DEFERRED printed; completion: deferred rows run); with no aitestmap/ prints TESTMAP_ABSENT:<hint>
  and delegates to aitask_run_project_command.sh test_command; with the engine absent prints
  ENGINE_MISSING:<path>|<repair> and exits 3 interactively, runs the suite runner''s fallback_command
  in completion mode when completion.engine_absent is fallback_command, and prints VERDICT:skip
  REASON:testmap_absent in advisory mode; completion mode applies the policy (full -> run
  --all with subsumed_by honoured; selected -> the task selection, demoted to full with POLICY_DEMOTED:
  when readiness is NOT_YET); advisory mode (n007''s aitask_affected_tests.sh folded in) prints
  VERDICT:pass|fail|skip / REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
  / DETAIL: / LOG:.aitask-gates/<task>/affected_<run-id>.log / SELECTED: / UNMAPPED_SOURCE:
  / UNKNOWN: lines, exits 0/1/2/3 with aitask_run_project_command.sh''s capture contract,
  and appends nothing to any ledger; prints MODE / TASK / INTAKE / POLICY / SELECTED / RUN
  / RESULT, UNANNOTATED_TEST:<path>|HINT for a listed test in the change surface with no testmap:
  block, no seed and no adopted row, and UNMAPPED_SOURCE:<path>; exit 0 pass / 1 fail / 2
  nothing ran / 3 framework error / 75 refused after deadline / 64 usage; dispatcher arm `test)`
  in ait; 5 permission touchpoints (a second helper is not written; tests/test_touchpoint_count_contract.sh
  re-pinned); tests/test_ait_test_entrypoint.sh against a fixture repo with AIT_TESTMAP_BIN
  pointing at a fake engine that replays scripted exits, in all three modes and every REASON
  (merged from n007 and n008)'
component_test_front_verb: 'Engine `test` composite (internal/selectr + sched + runner, reached
  by aitask_test.sh): `test --task <id> --changes - | --paths <p>... | --all [--explain] [--budget-s]
  [--format lines|json|tokens] [--run <id>]` runs select --include-stale -> schedule -> run
  in one process and prints SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>, one UNMAPPED_SOURCE:<path>
  per changed source no unit reaches, the ranked rows with n006''s reasons (a seeded edge
  reads edge(seeded:<origins>), an adopted one edge(annotation) adopted(<origins> <confidence>)),
  the schedule''s wave lines, results per id and RESULT:pass|fail|skip|deferred|<run_id>;
  --all is run --all (anchors evidence, scores the newest prediction, honours subsumed_by);
  --explain stops after select; the run id is prefixed test- / gate- / full- by the front.
  It never resolves a task, reads a profile, applies a completion policy or touches a gate
  ledger - those are the bash front''s (n007''s composite; brief split into component_agent_brief,
  the helper into component_test_entrypoint)'
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
component_workflow_integration: 'The procedure edits of the seam: task-workflow gains affected-tests.md
  (Affected Tests Procedure) called once from Step 7 before proceeding to Step 8 - the pre-review
  affected run - wrapped in {% if profile.affected_tests is not defined or profile.affected_tests
  != ''off'' %}; the procedure runs `./ait test --advisory --task <id>` (with --explain when
  the key is show) in the set -e capture form, branches: pass -> continue; fail -> the build-verification
  fail loop (caused by this task: fix and re-run; unrelated: log in Final Implementation Notes
  under ''Affected tests''); skip:no_selection -> display the UNMAPPED_SOURCE paths and offer
  annotate / attribute --propose / waiver via the aitask-testmap skill (autonomous profiles
  propose); skip:testmap_absent|registry_absent -> one line, continue; skip:unknown_paths
  -> the Step-2b-style scope prompt; skip:admission_refused -> print DETAIL, continue; rc
  3 -> diagnose, never fix code; the verdict line is recorded in the plan''s Final Implementation
  Notes and never in the gate ledger (advisory); it is the run that writes the task''s prediction
  record, which the completion run scores and readiness counts, so without it a repository
  can never reach ADMISSIBLE; profile key affected_tests run|show|off documented in profiles.md,
  default.yaml and fast.yaml omit it (run), remote.yaml sets run; the in-loop call is the
  Step-7 paragraph, not the procedure; Step 8 (testmap_fresh dispatch, plus its adopt-on-touched-files
  step) and Step 9 (gate orchestrator, build-verification.md) unchanged; aitask-qa test-discovery.md
  3a-3c use `ait testmap explain --sources <changed> --format table` when aitestmap/ exists
  and test-execution.md 4a runs `./ait test` through aitask_run_project_command.sh --task-id;
  pickrem and pickweb inherit Step 7 and see a printed skip on Web; ait setup prints TESTMAP:<state>;
  goldens under tests/golden/ regenerated for every profile x agent; aitask_skill_verify.sh
  run; profiles.md row added (n007; the helper folded into the entrypoint, the in-loop call
  replaced by n008''s paragraph)'
component_workflow_seam: 'The data edits of the seam: task-workflow SKILL.md.j2 Step 7 gains
  one paragraph after `Follow the approved plan` - run ./ait test as the implementation test
  loop, answer UNANNOTATED_TEST with annotate --suggest and UNMAPPED_SOURCE by mapping the
  source, never call the test tool directly (rendered into every profile; goldens regenerated);
  build-verification.md gains a branch for verdict error / reason command_refused | command_errored
  (host refused resources or the framework could not run: do not fix code, do not record pass,
  re-run later - the entrypoint already deferred to its deadline); lib/gate_verifier_lib.sh
  run_project_command_key() gains the 75 -> error and 3 -> error rows for opted-in keys and
  exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command, and aitask_run_project_command.sh
  --task-id exports the former; gates_reference.yaml adds testmap_fresh and testmap_check
  (unlocks: [tests_pass]) and no testmap_run; the project''s profiles gain tests_pass, testmap_check
  and testmap_fresh in default_gates via onboarding; the ait dispatcher gains `test)`; aidocs/framework/aitasks_extension_points.md
  gains `Adding a test-framework detector` and `Adding a seed origin`; tests/test_gate_verifiers.sh
  covers 75 and the env export, tests/test_serial_carveout_doc_drift.sh is extended per n006,
  tests/test_no_unscoped_task_commit.sh is unaffected because the skill commits through aitask_task_commit.sh
  (n008; profiles row and extension section extended)'
requirements_agent_instructions_seeded: 'No code agent learns how to run tests from the repository
  at session start: the shared agent-instructions seed (seed/aitasks_agent_instructions.seed.md)
  gains a fourteen-line `## Running Tests` section - always `./ait test`, never the test tool
  directly; `./ait test <path>` for one unit; `./ait test --all`; `./ait test --howto` for
  project specifics; UNANNOTATED_TEST -> `./ait testmap annotate --suggest`; UNMAPPED_SOURCE
  -> map it before the gate; TESTMAP_ABSENT -> /aitask-testmap-onboard; the exit-code table
  - which ait setup already installs into CLAUDE.md''s >>>aitasks block, AGENTS.md, .codex/instructions.md
  and the OpenCode mirror through assemble_aitasks_instructions(); the section is written
  before onboarding because `ait test` is correct in every repo state; a hand-maintained CLAUDE.md
  (this repository''s) is edited by the level-0 onboarding task instead; project specifics
  live only in --howto''s computed output (merged from n007 and n008)'
requirements_agent_run_surface: 'Any code agent runs the right tests in any onboarded project
  without learning the project: one front verb, `ait test`, with four agent-facing forms -
  `./ait test` (the tests the task''s attributed change reaches, a reason per row, the task
  resolved from the branch or lock), `./ait test <path>...` (the tests reaching those sources,
  or those test files themselves), `./ait test --all` (the full registered suite, what completion
  runs under a full policy) and `./ait test --howto` (this project''s runners, resources,
  full gate, gates, axes, policy, level, docs and notes, generated from the registry) - taught
  once by a generic Running Tests section in the seeded >>>aitasks agent-instructions block
  that ait setup writes into every supported agent''s instructions file, so the sentence an
  agent reads is the same in aitasks, thinking_app and aitasks_mobile and the project-specific
  facts come from `--howto`, never from prose the agent has to find; the same verb is correct
  before onboarding (it runs test_command and prints the onboarding hint) (merged from n007
  and n008)'
requirements_agent_skill: 'Agent skills teach agents how to keep the map current as they write
  code and tests (annotate a file, a testmap:unit member or a testmap:axis coordinate, declare
  an axis source, put testmap:reads on a tree-scanning helper, axes --explain, attribute before
  the gate, verify after editing, classify --suggest, confirm or retarget stamps in the procedure
  gate, drive a render loop from select --format tokens - n006) AND, new here, how a repository''s
  EXISTING tests get onto the map and how any agent runs tests without learning the project:
  aitask-testmap-onboard is the attended, resumable, profile-aware migration of an existing
  test tree in graded levels (detect tools -> generate aitestmap/ -> inventory -> seed edges
  from measured origins -> waivers -> enable gates -> first full run -> adopt seeds by class
  or by row -> classify kinds -> scaffold axes), each level an ordinary aitask whose annotation
  diff is reviewed and committed under a (t<id>) with provenance kept in registry/adopted.yaml;
  and the generic `## Running Tests` section of the seeded agent-instructions block plus `ait
  test --howto` are how an agent learns the run surface once, identically in every project
  - the daily-use surface shrinks to `./ait test`, `./ait test --howto` and `./ait testmap
  annotate --suggest <new test>` (merged from n007 and n008)'
requirements_annotation_freshness: Every STAMPED unit coverage annotation carries the date
  and blob digest of the covered source at confirmation, scoped to the member block where
  the unit is a member (n006), with committed last_pass anchors per variant letting stale
  prove EVIDENCED so most hot-source churn needs no rewrite; a SEEDED edge carries no stamp
  and makes no freshness claim - it lives in registry/seeded.yaml, selects at d1, and is invisible
  to stale; `onboard adopt` is the act that turns a seed into a stamped testmap:covers line
  through the rewriter - by evidence class with an adopted.yaml provenance row that stale
  and explain display until a human re-stamps the edge, or by row as a reviewed claim - so
  a stamp always records who accepted the claim, at what level of review, and against which
  bytes; a procedure gate at the post-implementation step hands the report to an agent that
  fixes annotations and adopts or rejects the touched files' seeds before the task commit
  (merged from n007 and n008)
requirements_annotation_staleness: A stale verb reports, for a task's change set or repo-wide,
  STALE_PATH (deleted or renamed source, fail-closed), STALE (content changed, no evidence
  on every reached variant, the unevidenced variants named), EVIDENCED, UNSTAMPED, STALE_AREA
  and opt-in REVIEW_DUE rows in the framework's fixed line protocol, plus one CHECK_STRUCTURAL:<n>
  summary line on --all (n006); seeded edges are excluded from every stale class (they claim
  nothing), stale --all adds SEEDED:<n> and ADOPTED:<n> summary lines so a repo-wide sweep
  sees how much of the map is provisional or machine-accepted, and a row on an adopted edge
  carries adopted(...) in its DISPLAY line; structural rot on axes, members, variants and
  artifacts stays check's; digest comparison needs no git history, evidence only removes nags
  (merged from n007 and n008)
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
requirements_engine_packaging: 'ait setup and ait upgrade (through install.sh''s --source-only
  path) install the host''s binary under $AITASKS_HOME/engine/v<VERSION>/ with checksum verification,
  a .sha256 sidecar and a version --json self-check that also prints ENGINE:<path>; fallbacks
  --local-engine, --engine-from-source, AIT_TESTMAP_BIN; opt-out --no-testmap / AIT_TESTMAP_FETCH=0;
  setup prints AITASKS_HOME:<path> and, when legacy tenants exist, HOME_LEGACY:<path>|run
  ''ait engine home --migrate'' and continues (n006); new: setup''s summary ends with one
  TESTMAP:absent|bootstrapping|<next>|onboarded[|engine-missing] line computed by report_testmap_state()
  from the presence of aitestmap/ and onboard.yaml''s phase ledger, with the hint `run /aitask-testmap-onboard`
  on absent - setup reports, it never onboards; and the re-inserted >>>aitasks instructions
  block carries the generic Running Tests section, so the run surface reaches every project''s
  agent instructions on the next setup or upgrade with no per-project step (merged from n007
  and n008)'
requirements_feedback_loop: 'Learns from failures the map did not predict via a score/attribute
  feedback loop; every full run (run --all, `ait test --gate` under a full policy, or a full:
  true suite runner) automatically scores the newest prediction record for the same task -
  written by the task''s interactive and pre-review advisory runs - and prints PREDICTION_FALSE_NEGATIVES:<n>
  plus one PREDICTION_MISSED:<id> line per miss, appending to a committed costs/predictions.yaml
  that readiness counts; attribute records an observed edge for a unit or member, an observed
  axis source for a facet value (widen only, never narrow), and an observed trigger or area
  member for a broad test, merged into the registry at load (n006); new here, an attribute
  proposal a reviewer has not decided lands in registry/seeded.yaml with origin `observed`
  so it selects immediately and is reviewed through the same adopt / reject queue as onboarding
  seeds, and `onboard status` reports the queue (seeded per origin, adopted unreviewed, rejected,
  oldest pending age) so adoption is measurable rather than remembered (merged from n007 and
  n008)'
requirements_framework_home_name: 'The framework is named aitasks, so every path it owns under
  the user''s home should be ~/.aitasks - the engine installs there now, and the legacy ~/.aitask
  tree is migrated by an explicit verb, ait engine home --migrate (flock, per-entry rename,
  rmdir, compatibility symlink; known set corrected to include pypy_venv), with ait setup
  printing a HOME_LEGACY: hint in this release and a named follow-up flipping the default
  once the verb has passed a real install.sh --dir test (n004''s principle and mechanism,
  n005''s default)'
requirements_gate_enforcement: 'Enforced by gates so the map cannot rot silently: testmap_fresh
  (procedure, before the task commit; now also offers to adopt or reject the seeds on the
  test files this task touched), testmap_check (machine; fails STALE_PATH on its own; reports
  SEEDED:<n>, ADOPTED:<n> and UNMAPPED_SOURCE:<path> rows; fails the structural rows plus
  UNMAPPED_SOURCE only under --strict past bootstrap_until; unlocks: [tests_pass]) and ONE
  completion test gate - the existing tests_pass, whose test_command is `./ait test`, which
  runs the whole registry or the task''s selection according to the committed completion policy
  in aitestmap/config.yaml (full by default; selected only after `ait testmap readiness` reports
  ADMISSIBLE and a human records approved_by; demoted back to full at run time if readiness
  regresses). testmap_run is retired as a gate name: its verifier logic is `ait test --gate`,
  its blocks_dependents and max_retries: 1 are tests_pass''s own, and its 1800 s timeout becomes
  a per-project tests_pass.timeout_seconds written from the measured full-run p95 (`ait testmap
  costs --gate-timeout`). A command key opted into gate_command_exit_contract now also reads
  exit 75 and exit 3 as verifier error, never fail and never skip. n001''s "a selection gate
  and a check gate" is satisfied: the selection gate is tests_pass under completion.mode:
  selected. Gates are enabled by the onboarding skill''s enable phase (which edits the profile''s
  default_gates / rendered_gates with confirmation and sets bootstrap_until), never by hand
  and never by ait setup; a project whose completion invariant is a full suite keeps tests_pass
  exactly as today (merged: n008''s one completion gate, n007''s rows and enable siting)'
requirements_generic_across_projects: 'A framework feature, generic across projects (aitasks,
  thinking_app, thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation between
  source files and test units - including a project''s own finer subdivision expressed through
  member units and variant axes, with the project''s runner lowering ids - never project-specific
  code in the engine (n006); and whose onboarding is generic too: `onboard detect` recognises
  each repo''s test tools from the tree and from project_config.yaml with an evidence field
  per row (aitasks: tests/test_*.sh + run_all_python_tests.sh with its serial carve-out; thinking_app:
  gradlew + the screenshot harness; thinking_backend: run_script_tests.sh named under verify_build,
  bash + pytest; aitasks_go: Makefile test = go test ./... plus the tmux parity suite; aitasks_mobile:
  one gradle-class runner per source set - commonTest and androidHostTest as unit, androidDeviceTest
  as device - which is the answer to n006''s open question 9: a kind/runner distinction, no
  axis) and writes runners.yaml from builtins with a full: true suite runner from the existing
  test_command, scaffolding a project runner script only where an axis or a full-suite post-processor
  needs one; every seed origin is a language- or convention-level rule, never a project name
  (merged from n007 and n008)'
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
  a seeded edge selects from the moment `onboard seed --apply` runs (fail-safe direction)
  but claims no freshness; adoption - the act that writes testmap: lines and stamps - happens
  per evidence class with provenance (adopted.yaml), per area in batches, or inside the testmap_fresh
  gate for the test files a task already touched; readiness prints LEVEL and NEXT from what
  exists and `onboard status` prints ONBOARD_NEXT and the ratios (tests with an edge, sources
  with an edge, seeds pending per origin, adopted unreviewed, oldest pending age) so a half-migrated
  repo is a known state with a next step, and check reports SEEDED:<n> and ADOPTED:<n> until
  both queues are empty (n007, with n008''s levels and provenance)'
requirements_onboarding_existing_tests: 'A skill onboards a project''s existing tests into
  the architecture without the user writing a registry by hand, in four graded levels each
  landing as one reviewed aitask: level 0 detects test frameworks and writes runners.yaml
  bindings, config.yaml, resources.yaml and areas.yaml, seeds the edge queue, proposes waivers
  and enables the gates (the universe exists, `ait test --all` runs it and is the task''s
  own first full run, selection works through seeds and the test-file static closure, nothing
  is stamped); level 1 adopts covers edges from the seed queue - static closure as primary
  evidence at 0.85+, naming conventions, plans, prose and (t<id>) co-change as corroboration,
  helpers split from subjects by root and fan-in - written as stamped annotation blocks through
  the engine''s rewriter with provenance in registry/adopted.yaml for class adoptions and
  none for per-row ones; level 2 classifies broad tests as scoped rows over codemap areas,
  adds testmap:reads to tree-scanning helpers, testmap:batch no from serial lists, and declares
  detected locks as resources; level 3 declares axes, scaffolds a project runner script and
  member blocks where the grid heuristic finds a product space. Rewriting a test means inserting
  comment lines only; the skill proposes and never performs code restructuring; headless profiles
  stop at level 0 plus language-rule adoption (n008, with n007''s seed queue and phases inside
  each level)'
requirements_platform_binaries_in_release: Release CI builds and attaches checksummed binaries
  for linux/darwin x amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt)
  from one engine job that also runs go vet and go test; a new engine-check.yml runs the same
  on push/PR for engine/**; tarball and package-manager artifacts stay architecture-independent
  (inherited)
requirements_reason_per_selected_test: 'Translates a task''s change set into one ranked list
  of tests that must run with a reason on every line (n006''s reasons: edge(annotation|declared|observed),
  dep, rule, axis(...)[keys] <- <source>, test-dep <helper>, reads(<helper>) <- <path>, ESCALATE:<file>|<reason>,
  the facet value or @* that placed each variant row, a stale mark when a selecting edge''s
  digest no longer matches and no run evidence covers that variant, an invocation group and
  its cost, an explicit DEFERRED line for every broad row or group the budget cut) plus `edge(seeded:<origins>)`
  for a seeded edge - the origins list (static:invocation, static:import, static:package,
  convention, cochange, plan, prose, coverage, observed) printed so a reader knows the row
  rests on a heuristic - and `adopted(<origins> <confidence>)` beside an annotation edge that
  entered by class acceptance; `ait test` prints a SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>
  summary line and UNMAPPED_SOURCE:<path> lines ahead of the rows (merged from n007 and n008)'
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
  overrides and shadow-by-name) plus the onboarding affordances: two repository keys, `subsumed_by:
  <suite>` (run --all executes a full: true suite once, never its subsumed runners beside
  it) and `fallback_command:` (what completion runs when the engine is absent and the policy
  allows); `onboard scaffold --runner <builtin> --as <name>` writes a project runner script
  skeleton whose describe/run delegate to the builtin and whose list is the one function the
  project fills (thinking_app''s tools/verification/testmap_runner.sh is that scaffold completed);
  and `onboard detect` wraps an existing project_config.yaml test_command as a `full: true`
  suite runner with a children: post-processor generated for pytest junitxml, bash-file names
  and go test -json and a fallback_command: equal to the previous test_command, so the project''s
  full gate feeds evidence from day one without anyone writing a runner (merged from n007
  and n008)'
requirements_user_root: Every per-user artifact this feature installs lives under the framework's
  own root, ~/.aitasks/ (env override AITASKS_HOME, one owner file lib/aitasks_home.sh, no
  fallback to ~/.aitask), beside the existing ~/.config/aitasks/ and ~/.cache/aitasks/ roots;
  the engine is the root's first tenant at $AITASKS_HOME/engine/v<VERSION>/ and $AITASKS_HOME/engine/dev/;
  the legacy ~/.aitask/ tenants (venv, pypy_venv, python, bin, uv, dev_tier, update_check)
  are neither moved nor read by this feature's default path (inherited from n005)
requirements_workflow_seam: 'The change-aware run is reached from the existing workflows without
  a new workflow: task-workflow Step 7 gains one paragraph naming `./ait test` as the implementation
  test loop and one pre-review Affected Tests procedure (affected-tests.md) before Step 8,
  behind an affected_tests: run|show|off profile key (default run), that calls `./ait test
  --advisory --task <id>` speaking the VERDICT:/REASON:/DETAIL:/LOG: line shape and set -e
  capture form aitask_run_project_command.sh already established and writes the prediction
  the completion run scores; Step 8''s procedure-gate block dispatches testmap_fresh unchanged;
  Step 9''s gate orchestrator runs testmap_check -> tests_pass and the legacy build-verification
  path is untouched except for one error branch; aitask-qa''s test discovery reads the map
  (explain --sources) instead of naming conventions when aitestmap/ exists and its execution
  step runs `./ait test`; aitask-pickrem and aitask-pickweb inherit Step 7 through the shared
  task-workflow; ait setup prints TESTMAP:<state>; and every seam degrades to a printed skip
  where the engine or registry is absent (n007, with the helper folded into the entrypoint
  and the in-loop call replaced by n008''s paragraph)'
requirements_workflow_seam_is_data: 'The integration with task-workflow, aitask-qa, aitask-pickrem,
  aitask-pickweb and aitask-resume adds no new gate and one procedure: the seam is project_config.yaml
  (test_command: ./ait test, gate_command_exit_contract: [test_command]), the project''s profiles
  (default_gates += tests_pass, testmap_check, testmap_fresh; the affected_tests key), gates.yaml
  (testmap_check unlocks tests_pass; tests_pass.timeout_seconds from the ledger), the completion
  policy in aitestmap/config.yaml, and two environment variables the verifier already knows
  (AIT_GATE_TASK_ID, AIT_GATE_RUN_ID); the prose changes are one Step-7 paragraph naming `./ait
  test` as the implementation test loop with the UNANNOTATED_TEST and UNMAPPED_SOURCE answers,
  one branch in build-verification.md for verdict error / command_refused | command_errored,
  aitask-qa''s discovery reading the registry instead of naming conventions when aitestmap/
  exists, and the one pre-review Affected Tests procedure kept because it is the run that
  writes the prediction the completion run scores; Step 9''s verify block, the merge broker,
  archival and the gate orchestrator are untouched (n008, with n007''s one procedure admitted)'
requirements_zero_config_entrypoint: 'One user-facing verb, `ait test`, is the only way an
  agent or a person runs tests in any aitasks project, at every stage of adoption: with no
  aitestmap/ it runs project_config.yaml test_command through aitask_run_project_command.sh
  and prints the onboarding hint; with a registry it resolves mode (completion when --gate
  or AIT_GATE_TASK_ID is set, advisory when --advisory, interactive otherwise), task (--task
  > AIT_GATE_TASK_ID > the aitask/<task_name> branch of the current worktree > the single
  Implementing lock this user holds on this host > NO_TASK with the three ways out) and intake
  (change surface for a task, --dirty, --all, or named paths where a source path is a one-file
  change set) by itself; it prints MODE / TASK / INTAKE / POLICY / SELECTED / RUN / RESULT
  lines, UNANNOTATED_TEST:<path> for a new test in the change surface and UNMAPPED_SOURCE:<path>
  for a changed source no unit reaches, and exits 0 / 1 / 2 / 3 / 75 / 64; in advisory mode
  it exits 0 / 1 / 2 / 3 with VERDICT: / REASON: lines and every absence a skip; and `ait
  test --howto` prints the project''s runners, kinds, resources, gates, completion policy,
  level, docs and notes and the four commands an agent needs, computed from runners.yaml,
  config.yaml and the ledger so it cannot rot (n008, with n007''s advisory contract and UNMAPPED_SOURCE)'
requirements_zero_config_onboarding: 'A repository with an existing test tree is brought onto
  the map by attended runs of /aitask-testmap-onboard and nothing typed by hand: the skill
  detects the test tools (pytest, go test, gradle per source set, bash tests/test_*.sh, npm
  test, Makefile test, and the project_config.yaml test_command / verify_build) with evidence
  per row, generates aitestmap/ (config.yaml with completion, conventions and helper roots,
  runners.yaml with bindings and the full suite wrapper, resources.yaml from hints, registry/areas.yaml
  from code_areas.yaml), inventories every test unit through the runners'' list, seeds edges
  from the origin table, proposes rules and waivers for the remainder, enables tests_pass
  / testmap_check / testmap_fresh and the test_command swap, and runs the existing full gate
  once as the level-0 task''s own completion gate; later levels adopt seeds by class or by
  row, classify broad tests with confirmation, and scaffold axes - each phase idempotent and
  resumable from a committed ledger (aitestmap/onboard.yaml), each level shaped as an aitask
  so its writes land under (t<id>) commits, are reviewed at Step 8 and attributed by the change
  surface (merged from n007 and n008)'
tradeoff_accept_rewrites_history: 'Disadvantage: adopting seeds inserts comment lines into
  hundreds of test files, so `git blame` on any test header points at the adoption commit
  and a concurrent task editing the same file hits a textual conflict on the header; mitigated
  by comment-only insertions at a fixed position (after the header block / docstring / package
  clause / import block), per-class and per-area batch commits named for what they are, the
  incremental path that adopts a file''s seeds only inside a task that already edits it, ADOPT_REFUSED:dirty-foreign,
  and the rewriter''s REWRITE_CONFLICT refusing a file that changed under it; a project that
  wants no comment churn keeps seeds unadopted and accepts selection-only enforcement, which
  onboard status reports as the state it is (n007)'
tradeoff_area_glob_coarseness: 'Disadvantage: area and scope globs are coarser than edges
  - a broad area over-selects its tests on every edit inside it and a scoped test depending
  on a file outside its scope is under-selected until a full run scores it; mitigated by the
  suite budget with explicit DEFERRED lines, budget-exempt triggers and reads globs for known
  sharp edges, and the missing-trigger / area-too-narrow attribution path (inherited)'
tradeoff_attribution_risk: 'Risk: an agent that edits sources without attributing produces
  a map that looks current and is not; narrowed three ways - such a source shows as STALE
  in the next task touching it and as a stale mark on every selection (n006); the Step-7 run
  reports UNMAPPED_SOURCE:<path> for a changed source no unit reaches at the moment the agent
  introduced it, and the pre-review procedure offers annotate / attribute --propose / waiver
  right there, so a new coupling with no edge is surfaced during the task rather than only
  on a full run (n007); and in a repo whose completion policy is full every miss is counted
  by the automatic score within one task (n008). What still escapes is a coupling to a source
  that already has some edge, which only score can find (merged)'
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
tradeoff_bulk_confirmation_granularity: 'Risk: adopting edges per evidence class (398 static
  edges in one answer) trades review depth for feasibility - per-file review of 720 files
  is not something anyone does, and a class-level yes accepts every member; mitigated by the
  three-sample display, `review a sample` drawing ten random members with their signals, --accept-min
  raising the bar, --scope <glob> onboarding one area per task, the adopted.yaml provenance
  so nothing pretends to be reviewed and readiness reports ADOPTED_UNREVIEWED, the per-row
  path (onboard adopt <test> <source>, --batch, the in-gate step) for anyone who wants depth,
  autonomous profiles being limited to confidence-1.0 origins, and kind reclassifications
  being confirmed individually because a wrong kind changes staleness semantics rather than
  selection breadth (n008, with the per-row path from n007)'
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
  than remembered; blast radius becomes data instead of prose - thinking_app''s ''a localized
  screen change may use preview, a shared component must run the full gate'' rule becomes
  an axis join, an import-scanner fan-out and an ESCALATE: line, each printed with the path
  that caused it (n006); and so is the run surface - `ait test --howto` prints the runners,
  resources, full gate, gates, axes, policy and doc pointers from the registry and the ledger,
  and the generic Running Tests section is identical in every project, so an agent never learns
  ''how do I run tests here'' from a 200-line CLAUDE.md testing section again (thinking_app''s
  is 200 lines today); the project''s judgement calls become config.yaml notes: lines and
  docs: pointers the brief prints, still prose, but reached through one verb rather than found
  (merged from n007 and n008)'
tradeoff_dispatcher_verb_added: 'Disadvantage: `ait test` is a new top-level dispatcher verb
  beside `ait testmap`, two surfaces for one engine; justified by the extension-points rule
  (a human plausibly types `ait test`, and the seed instruction needs one memorable verb),
  kept thin (mode / task / intake / policy / fallback / advisory resolution only, everything
  else delegated to the n006 shim and the engine `test` composite), and `ait testmap` stays
  the maintainer surface for annotate / scan / check / stale / axes / onboard; removing a
  verb later is a breaking change, so --howto documents `ait test` as the stable one (n008)'
tradeoff_engine_absent_on_host: 'Risk: an unsigned macOS binary or a blocked download leaves
  a host without an engine; mitigated by ENGINE_MISSING naming the $AITASKS_HOME path and
  repair verb, --engine-from-source and --local-engine fallbacks, and the testmap gates exiting
  3 (error), never skip, when the engine is absent (n006); two deliberate, printed exceptions:
  `ait test --advisory` reports VERDICT:skip REASON:testmap_absent so the pre-review Step-7
  run in task-workflow, pickrem and pickweb - which has no ait setup at all - continues exactly
  as today, because an advisory run must never block a task the way a declared gate legitimately
  does (n007); and a project may set completion.engine_absent: fallback_command so the Web
  lane''s tests_pass runs the pre-onboarding suite command with MODE:fallback visible, the
  default staying error (n008); neither skip is silent (merged)'
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
tradeoff_fail_closed_bootstrap_cost: 'Disadvantage: fail-closed enforcement means bootstrapping
  each repo requires a waiver pass before testmap_check can be enabled, a first green full
  run before require_stamp and --strict, a green runner list before structural rules can fail,
  and min_scored_full_runs before the completion policy may flip to selected (n006); narrowed
  here by making the bootstrap order one aitask per level that the onboarding skill creates
  and runs - detect and seed are read-only until --write / --apply, level 0 writes only registry
  files and seeds, the seeder replaces most of the hand waiver pass (measured on aitasks:
  88% of bash tests and 80% of Python tests carry a literal invocation or import that seeds
  at least one edge), the level-0 task''s own tests_pass gate IS the first full run that anchors
  every unit, bootstrap_until is set to level-0 day + 90 by detect --write, adoption is incremental
  by class, by area or in-gate, and readiness prints LEVEL / NEXT so the remaining steps are
  a list rather than a procedure someone must remember; the cost that remains is real - a
  repo is at level 0 (runner-bound, seed- and closure-selected, unstamped) until a human adopts
  level 1, headless profiles stop there plus language-rule origins, and the judgement in classify
  and adopt is one no seeder can take (merged from n007 and n008)'
tradeoff_fallback_runs_more: 'Disadvantage: when the engine binary is absent in completion
  mode and the project chose engine_absent: fallback_command (the Claude Code Web lane, where
  ait setup never ran), `ait test --gate` runs the whole pre-onboarding suite command - never
  less than before onboarding, but never selective either, and with no per-unit results, no
  evidence anchors and no scoring; mitigated by the default being error (the gate reads error,
  not pass), by ENGINE_MISSING naming the path and repair verb, and by the fallback being
  visible as MODE:fallback in the result (n008)'
tradeoff_flaky_pass_anchors: 'Risk: a flaky pass anchors evidence as surely as a real one;
  mitigated by per-run status in the ledger so costs exposes a flake rate per id, and an id
  above flake_threshold is excluded from the evidence join (inherited)'
tradeoff_generated_brief_limits: 'Disadvantage: a brief computed from the registry cannot
  say what a project''s people know about when a narrow run is acceptable, which device is
  the real test device, or why RTL is the design gate - thinking_app''s testing prose carries
  exactly that; mitigated by config.yaml docs: (paths the brief prints, so the prose is one
  hop away and named) and notes: (<=10 verbatim lines for the rules that must not be one hop
  away), and by the seeded instructions telling agents to read `ait test --howto` before touching
  a test tool; the limit that stays is that notes: is prose an agent may still misread, which
  the gates and the full completion policy backstop (n007)'
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
  tests, and any source with no static, convention, plan, prose, co-change or coverage relation
  - so a freshly onboarded repo has UNMAPPED_SOURCE rows and area-only coverage for a share
  of its tree; mitigated by the waivers phase (rules for hot directories, expiring waivers
  for the rest) so check can be enabled non-strict, by the Step-7 UNMAPPED_SOURCE prompt that
  maps a source the first time a task touches it, by opt-in per-unit coverage where the tool
  supports it, and by the full gate staying the completion policy; the honest reading of `onboard
  status` after one session is ''selecting on most tests, claiming on few'', and the design
  treats that as a state, not a failure (n007)'
tradeoff_one_gate_not_two: 'Advantage: one completion test gate whose behaviour is a committed
  policy, instead of n006''s tests_pass (full) beside testmap_run (selected) - an agent learns
  one command and one gate, a project keeps its existing tests_pass declaration and timeout
  key, the legacy no-gates Step-9 path and aitask-qa reach the selective lane through the
  same test_command, and the policy flip is one line a human writes after readiness rather
  than a second gate to declare. Disadvantage: the gate''s meaning now depends on config.yaml,
  so a reader of a ledger `tests_pass: pass` must look at the run''s MODE line to know whether
  the whole suite ran; mitigated by the verifier result= field carrying MODE:<full|selected>|<n
  units>|<policy>, by the gate- run-id prefix in the cost ledger, by POLICY_DEMOTED being
  loud, and by readiness printing what --gate would run now (n008)'
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
tradeoff_seed_noise: 'Risk: heuristic seeds are wrong in both directions - a convention pairs
  a test with a homonym, an import names a helper the test only uses, co-change ties every
  file of a wide task to every test of that task (thinking_app: 7.2 main files per co-changing
  commit), and a wrong seed selects tests that cannot fail for the change. Mitigated by seeds
  selecting (wasted minutes) and never claiming (no false EVIDENCED), by the confidence table
  ordering review rather than gating it, by the 0.60 co-change cap and min_cochange 2 across
  distinct tasks so corroboration cannot reach the class threshold alone, by imports restricted
  to direct main-root imports (same-package facts excluded), by helpers separated before scoring,
  by the evidence printed beside every seed at review, by rejection memory in onboard.yaml,
  and by the suite budget and --format tokens for a repo where over-selection is expensive;
  what remains is reviewer fatigue on a 1,000-seed queue, which class adoption with samples,
  per-area batches and the in-gate incremental path spread over time (n007, with n008''s cap
  and helper split)'
tradeoff_seed_precision: 'Risk: an adopted covers edge is a machine claim wearing a human
  annotation''s clothes - the static closure says the test executes the script, not that it
  verifies it, and a test that drives three scripts to set up one adopts edges to all three.
  Narrowed: adopted edges are recorded in registry/adopted.yaml and displayed as adopted(...)
  in stale and explain until a human re-stamps them, readiness reports ADOPTED_UNREVIEWED,
  the over-claim direction only over-selects (a setup script''s change runs the test needlessly),
  the class threshold 0.85 keeps convention-only, prose-only and co-change-only edges out,
  the skill shows three samples per evidence class before adopting a class, and a project
  that wants no machine claims at all stops at the seeded state, which selects without claiming;
  what it cannot do is invent a subject the closure does not contain - such a coupling is
  caught only by a full run''s score, as in n006 (n008, with the seeded state below it from
  n007)'
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
  of all - adopting level 1 on aitasks touches ~720 test files with one to eight comment lines
  each - mitigated by seeds selecting without any rewrite, by adoption being batched per evidence
  class or per area (--scope <glob>) into `chore: Onboard testmap - adopt <class|area> (t<id>)`
  commits that add comment lines only (git blame -w and every runner ignore them), by ADOPT_REFUSED:dirty-foreign
  refusing a file dirty outside the task''s change surface so adoption never mixes with concurrent
  work, by the onboarding task being an ordinary reviewed (t<id>) commit rather than a hidden
  write, and by the in-gate path that adopts a file''s seeds only when a task already has
  it open (merged from n007 and n008)'
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
tradeoff_two_edge_states_during_adoption: 'Disadvantage: until both queues are empty a repo
  has three provenances of edge - seeded (selecting only), adopted (stamped, evidenced, stale-checked,
  accepted by class with a provenance row) and reviewed (stamped, accepted per pair) - and
  a reader of a selection, a check report or a stale row must keep them apart; mitigated by
  the seeded origin or adopted(...) printed on every row, SEEDED:<n> and ADOPTED:<n> on check
  and stale --all, ADOPTED_UNREVIEWED in readiness, `onboard status` as the one place the
  ratios live, and the rule that no seed ever changes a freshness verdict; the cost is real:
  --strict cannot be enabled while UNMAPPED_SOURCE rows are only seed-covered, so a repo that
  never adopts stays at bootstrap enforcement indefinitely, which `onboard status` makes visible
  rather than silent; this is the recorded cost of the adoption ledger bridging component
  (n007, extended to three states by the n008 bridge)'
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
tradeoff_verify_build_wired_suites: 'Disadvantage: a project that wired its test suite as
  verify_build (thinking_backend''s run_script_tests.sh, which also enforces a shellcheck
  baseline) cannot be onboarded mechanically - moving the command to a suite runner would
  drop the lint half from build_verified, leaving it would run the suite twice at completion;
  detect therefore reports SUITE_CANDIDATE:verify_build and the skill asks (keep as verify_build
  and add test_command: ./ait test over the detected bash-file and pytest units; or split
  the script), defaulting to keep, and records the answer in the onboarding plan; headless
  profiles keep (n008, replacing n007''s detect proposal to move it)'
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
  file, one profile key, one dispatcher verb, one skill-invoked script with a second mode
  (five allowlist touchpoints - .claude/settings.local.json, .codex/rules/default.rules and
  the three seeds - pinned by tests/test_touchpoint_count_contract.sh), a Step-7 render change
  across every profile x agent golden, one build-verification branch, two aitask-qa procedure
  edits, a seed-instructions edit and a profile-aware skill with two wrapper surfaces; mitigated
  by all of it degrading to a printed skip where the engine is absent (no environment conditionals),
  by the advisory mode reusing the exact VERDICT:/REASON: contract and capture form the build-verification
  path already teaches, by there being one script rather than n007''s two, and by aitask_skill_verify.sh
  plus the goldens catching a drifted render before commit (n007, narrowed by folding the
  helper into the entrypoint)'
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

The goal is unchanged: a framework feature, generic across `aitasks`,
`thinking_app`, `thinking_backend`, `aitasks_go` and `aitasks_mobile`, that
maintains a relation between source files and test units, translates a task's
change set into a ranked list of tests with a reason on every line, runs them
through project-defined runners under a standard contract, tracks cost per
unit by host class, learns from failures the map did not predict, is enforced
by gates, and is taught to agents by a skill. The engine — a static Go binary
under `$AITASKS_HOME/engine/v<VERSION>/`, per-edge blob-digest stamps healed by
a per-variant evidence join, scoped rows under a suite budget, member units
and variant axes, the graded walk, the real scheduler, the cost ledger,
automatic prediction scoring — is the n006 baseline that both n007 and n008
kept unchanged, and it is kept unchanged here. n001 and n002, the two
first-round parents, are the origin of that engine: every one of their
dimensions survives in n006 and therefore here, with the resolutions n003 made
between them (blob digest over commit-sha stamps, `_scoped.yaml` over a second
`suites/` directory, `engine/` over `go/`, built-in runners over bash scripts,
`$AITASKS_HOME/engine/` over `~/.aitask/bin/`) carried and recorded in
*Conflict Resolutions* rather than re-argued.

The two third-round parents answered the same mandate — *how does a repository
with an existing test tree get onto the map, how does any agent run tests
without learning the project, and how does that sit inside task-workflow* —
with designs that agree on most of the machinery and disagree on four things.
This node takes the stronger answer for each and bridges what the other side
got right:

**1. Machine-seeded edges have three provenances, not two.** n007 keeps every
heuristic edge in a `registry/seeded.yaml` queue that *selects but never
claims* until a person accepts it row by row; n008 lets a class-level "accept
all static edges" write stamped `testmap:covers` lines at once and records
their machine origin in `registry/adopted.yaml` until a human re-stamps them.
Both are right about different moments. The merged model is
**seeded → adopted → reviewed**: `onboard seed` fills the queue (select-only,
no stamp, invisible to `stale`, excluded from `--strict`, `SEEDED:<n>`
everywhere it matters); `onboard adopt --class <origin>` promotes a whole
evidence class to stamped edges with an `adopted.yaml` provenance row shown as
`adopted(...)` in `stale` and `explain` and counted as `ADOPTED_UNREVIEWED` by
`readiness`; `onboard adopt <test> <source>` (or the accept step inside the
`testmap_fresh` gate) promotes one reviewed pair with no provenance row. A seed
never satisfies `require_stamp`; an adopted edge does, because a person
accepted its class. Autonomous profiles may seed and may adopt only origins
whose confidence is a *language rule* (a `_test.go` file's own package, 1.0) —
never a heuristic — which is n007's "acceptance is the one act that turns a
heuristic into a claim" and n008's headless level 1 reconciled by the number
that distinguishes them.

**2. One seed table, one confidence vocabulary, measured on both sides.**
n007's five origins (naming, literal invocation, direct imports, `(t<id>)`
co-change, opt-in per-unit coverage) and n008's five signals (static closure,
convention, co-change, plan, prose) are the same facts named twice. The merged
table: `static:package` 1.0, `coverage` 0.95, `static:invocation` 0.90,
`static:import` 0.85, `observed` 0.70, `convention` 0.60, `plan` 0.50,
`prose` 0.30, `cochange` 0.20 + 0.20 per distinct task group, capped at 0.60
and requiring two distinct tasks — n008's cap because the measurement that
matters is that a `(t<id>)` group pairs a few tests with a few scripts and
nothing inside it says which covers which, so co-change corroborates and can
never reach the 0.85 class-acceptance threshold alone. Noisy-OR combination;
the queue is ordered by confidence and never hides a row.

**3. Onboarding is levels × phases, one aitask per level.** n008's four
graded levels (0 runners and universe, 1 stamped edges, 2 kinds / areas /
reads / batch / resources, 3 axes / members / runner scaffold) say *what* a
repository has; n007's phase ledger (`aitestmap/onboard.yaml`, every phase
idempotent and committed under `(t<id>)`, `ONBOARD_NEXT:` on re-entry) says
*how far a level's run got*. Each level is one aitask (a level may wait weeks
on full-run history); within it the skill's phase procedures run at
task-workflow Step 7 and commit per phase, Step 8 reviews the annotation diff,
and the level-0 task's own `tests_pass` at Step 9 is the **first full run that
anchors every unit's `last_pass`**. `readiness` prints `LEVEL:` from what
exists; `onboard status` prints `ONBOARD_NEXT:` from the ledger.

**4. One verb, one gate, one thin procedure.** `ait test` is n008's bash front
(`aitask_test.sh`: resolves mode, task, intake and completion policy by itself;
falls back to `test_command` where no registry exists and to a recorded
`fallback_command` where the engine is absent at completion) over n007's engine
`test` composite (select → schedule → run with `SELECTED:` /
`UNMAPPED_SOURCE:` / `RESULT:` summary lines). It gains one mode from n007's
workflow helper, `--advisory`, which always answers with `VERDICT:/REASON:`
lines and treats every absence as a printed skip — that is what lets a Step-7
affected run sit in every profile including the one Claude Code Web runs with
no engine. The completion gate is n008's: the existing `tests_pass` runs
`./ait test --gate` under a committed `completion:` policy in
`aitestmap/config.yaml` (`full` until `readiness` is `ADMISSIBLE` and a human
records `approved_by`; demoted back to `full` automatically), `testmap_check`
unlocks it, `testmap_run` is retired as a gate name, and the command exit
contract gains the 75 → error and 3 → error rows for opted-in keys in the one
function that owns it. The workflow seam is n008's data (project config,
profiles, gates, two environment variables, one Step-7 paragraph) plus n007's
one procedure — the **pre-review affected run** before Step 8 — kept because it
is the run that writes the prediction record the next full run scores: without
it no prediction is ever scored and `readiness` can never be reached. The
`## Running Tests` section of the seeded agent-instructions block is one
merged text: never call the tool directly; `./ait test`, `./ait test
<path>...`, `./ait test --all`, `./ait test --howto`; `UNANNOTATED_TEST` →
`annotate --suggest`; `UNMAPPED_SOURCE` → map it before the gate;
`TESTMAP_ABSENT` → `/aitask-testmap-onboard`; the exit-code table.

What this does not change: the engine's process boundary, the registry's six
n006 tables and check rules, the id grammar, axes, the runner contract, the
scheduler, the ledger, the evidence join, the per-user root and its migration
verb, the `testmap_fresh` and `testmap_check` verifiers, and the
`aitask-testmap` skill's maintenance obligations. The additions are one engine
package family (`internal/{seed,onboard,brief}`), three registry-adjacent
files (`seeded.yaml`, `adopted.yaml`, `onboard.yaml`), one bash front, one
completion-policy block, one skill, one instructions section, one Step-7
procedure and one profile key.
<!-- /section: overview -->

<!-- section: decision_matrix [dimensions: component_*, assumption_*] -->
## Decision Matrix: What Was Taken From Which Parent, and Why

| aspect | n007_explorer_003a | n008_explorer_003b | chosen | why |
|---|---|---|---|---|
| machine-seeded edge state | `seeded.yaml`: selects, never claims; per-row accept writes the stamp | `adopt` writes stamped blocks per accepted class; `adopted.yaml` provenance until re-stamped | **both, as three states** | a queue that cannot claim is right *before* anyone accepted; a stamped edge with provenance is right *after* a class was accepted; per-row acceptance is a reviewed claim and needs no provenance row |
| autonomous acceptance | never (OQ2: acceptance turns a heuristic into a claim) | headless: level 0 + static-only level 1 at 0.95 | **n007's rule, n008's mechanism at 1.0** | a language-rule origin (Go package) is not a heuristic; everything below 1.0 is |
| seed origins and weights | naming 0.6 / invocation 0.9 / imports 0.85 / cochange 0.5–0.8 / coverage 0.95 / observed 0.7 | static 0.9 (go 1.0) / convention 0.7 / cochange 0.2+0.2n ≤ 0.6 / plan 0.5 / prose 0.3 | **one table** | same facts; n008's co-change cap is the measured one (groups do not disambiguate); n007's coverage and observed origins have no n008 counterpart and are kept |
| class-acceptance threshold | none (per row) | 0.85 | **0.85 for `--class`**; per-row has none | static alone qualifies, convention alone does not, co-change never |
| onboarding structure | 9 phases in `onboard.yaml`, one task, resumable at `ONBOARD_NEXT:` | 4 levels, one task each, `readiness` derives `LEVEL` | **levels × phases** | levels are the grade of the registry; phases are the ledger of a run; both are needed to make a half-migrated repo a known state |
| first full run | phase 6 `full_run` = `ait test --all` | the level-0 task's own `tests_pass` at Step 9 | **n008** | it is the same run and it lands under the task's gate ledger; n007's `costs --update` and anchoring happen inside it |
| `bootstrap_until` | enable + 30 d | adopt (level 0) + 90 d | **+90 d at level 0** | level 0 is unstamped by design and a 1,000-seed queue is not accepted in 30 days; `finish` may shorten it |
| skill shape | static, attended-only, no stub | profile-aware stub + `.j2`, headless behaviour defined | **n008** | the merged design has a defined headless behaviour (seed; adopt 1.0 origins only; no kinds; no policy flip) |
| task shape | one `testmap_onboarding` task, per-phase commits, `--no-task` | one task per level through task-workflow, adopt at Step 7 | **n008's task per level, n007's per-phase commits and re-entry** | a level may wait weeks; a phase may span sessions |
| front verb | engine `test` composite via the shim: `--task`, `<path>...`, `--all`, `brief`, `--mode show` | `aitask_test.sh`: MODE / TASK / INTAKE / POLICY resolution, `test_command` and `fallback_command` fallbacks, `--howto`, `--dirty`, `--explain`, `--tokens` | **both layers** | the fallbacks must be bash (they run with no engine); the composite must be Go (it is the pipeline) |
| workflow helper | `aitask_affected_tests.sh` → `VERDICT:/REASON:`, 0/1/2/3, absence = skip | none; Step-7 paragraph names `./ait test` | **n007's contract as `ait test --advisory`** | one script, two modes; the advisory mode is what Web needs |
| Step 7 | `affected-tests.md` at two points behind `affected_tests: run\|show\|off` | one paragraph | **paragraph for the loop, procedure for the pre-review run** | the pre-review run writes the prediction the full run scores; the loop needs no procedure |
| gates | `testmap_fresh` → `testmap_check` → `testmap_run` (kept from n006); enabled by `enable` phase | `testmap_check` → `tests_pass` = `./ait test --gate` under `completion:`; `testmap_run` retired; 75 → error row | **n008** | one gate an agent learns; the legacy Step-9 path and `aitask-qa` reach the lane through `test_command`; demotion fails toward running more |
| `UNMAPPED_SOURCE` / `UNANNOTATED_TEST` | `UNMAPPED_SOURCE:` on `test` and `check`; Step-7 offer | `UNANNOTATED_TEST:` + `HINT:` | **both** | one is the source side, the other the test side |
| instructions section | 12 lines: four verbs incl. `brief`, `UNMAPPED_SOURCE`, `TESTMAP:absent` | rule + four forms incl. `--howto`, `UNANNOTATED_TEST`, exit table | **one merged section** | `--howto` is the flag family; `brief` is the engine verb behind it |
| task resolution | `--task <id>` explicit | `--task` > `AIT_GATE_TASK_ID` > `aitask/<name>` branch > single own lock > `NO_TASK` | **n008** | the advisory mode still passes the id explicitly |
| `ait setup` state line | `TESTMAP:absent\|bootstrapping\|onboarded\|engine-missing` | — | **n007** | |
| `aitask-qa` | `explain --sources <paths> --format table`; 4a prefers `ait test --task` | `explain --source` per path; 4a via `aitask_run_project_command.sh --task-id`; 4c `REFUSED`; 4d edges | **n007's verb form, n008's four edits** | |
| annotation placement | bash after header; Python appended to docstring; Kotlin block before KDoc / inside member block | comment lines only; Python `#` after docstring (never inside — `__doc__`); Go after package; Kotlin after imports | **n008, plus n007's member-block placement** | rewriting a docstring changes behaviour; a member seed belongs in its `testmap:unit` block |
| `attribute --propose` | → `seeded.yaml` origin `observed` | — | **n007** | the autonomous-safe half of feedback |
| `costs --gate-timeout` / run-id prefixes | `test-` / `full-` prefixes | `GATE_TIMEOUT_SUGGESTED = max(600, 3 × p95)` | **both** | |
| runner keys | `runner scaffold`, `full` wrapper from `test_command`, `bash-file list --invocations` | `subsumed_by:`, `fallback_command:` | **both** | |
| `verify_build`-wired suite | detect proposes moving it to `test_command` | ask, default keep, add `test_command: ./ait test` | **n008** | the lint half |
| config additions | `exclude:`, `docs:`, `notes:`, `broad_threshold_s` | `completion:`, `conventions:`, `helper_roots:`, `helper_fanin:` | **all** | |

Lineage rows for the first-round parents — resolved in n003 and n006, carried
here unchanged: n001's `testmap:verified <sha>` and `git log` anchor walk
versus n002's `@<date>/<blob10>` digest → **digest plus the evidence join**;
n001's `suites/` directory versus n002's `_scoped.yaml` → **`_scoped.yaml`**;
n001's `go/` + `make install-dev` + `AIT_TESTMAP_DEV=1` versus n002's
`engine/` + `ait engine build` + `AIT_ENGINE=dev` → **n002's**; n001's bash
reference runners versus n002's builtins → **builtins with shadow-by-name**;
n001's `~/.aitask/bin/ait-testmap-<V>` versus n002's `~/.aitask/engine/v<V>/`
→ n002's shape under **`$AITASKS_HOME`** (n005); n001's `testmap_run` /
n002's `testmap_select` → n003's `testmap_run` → **retired here in favour of
`tests_pass` under policy**; n002's cobra and gofrs/flock → **stdlib `flag` and
`syscall.Flock`** (n006).
<!-- /section: decision_matrix -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_agent_brief, component_agent_instructions, component_completion_policy, component_workflow_seam, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary, component_gates] -->
## Architecture

### Process boundary (n006's, with the additions marked)

```
./ait test [...]                                   agent · human · tests_pass verifier (test_command) · Step-7 procedure (--advisory)
 └─ .aitask-scripts/aitask_test.sh                 ← NEW  bash front, ~150 lines: MODE / TASK / INTAKE / POLICY / fallback / advisory
      │  no aitestmap/            → TESTMAP_ABSENT:<hint> → aitask_run_project_command.sh test_command   (advisory: VERDICT:skip REASON:registry_absent)
      │  engine absent            → interactive: ENGINE_MISSING:<path>|<repair> exit 3     (advisory: VERDICT:skip REASON:testmap_absent)
      │                             completion: per config.yaml completion.engine_absent (error | fallback_command)
      │  MODE   completion iff --gate or $AIT_GATE_TASK_ID · advisory iff --advisory · else interactive
      │  TASK   --task > $AIT_GATE_TASK_ID > aitask/<task_name> branch > single own lock (aitask_lock.sh --list-mine) > NO_TASK
      │  INTAKE aitask_change_surface.sh list <id> | --dirty (printed) | --all | <path|id>...
      │  POLICY completion: config.yaml completion.mode re-checked against `readiness`
      └─ .aitask-scripts/aitask_testmap.sh          the n006 shim, unchanged: resolves $AIT_TESTMAP_BIN > AIT_ENGINE=dev > $AITASKS_HOME/engine/v<V>/
           └─ ait-testmap test … | select | schedule | run | brief | onboard … | readiness | costs …
                internal/registry       six tables (n006) + seeds (registry/seeded.yaml) + adopted (registry/adopted.yaml)
                internal/seed           ← NEW  origins static:{package,invocation,import} · convention · cochange · plan · prose · coverage · observed; noisy-OR
                internal/onboard        ← NEW  detect · inventory · seed · classify · adopt · reject · scaffold · status · finish; the onboard.yaml phase ledger
                internal/brief          ← NEW  the generated run brief (`brief`, rendered by `ait test --howto [--md]`)
                internal/selectr        graded walk (n006) + seeded edges at d1 · explain --sources · the `test` summary lines
                internal/runner         contract (n006) + subsumed_by: · fallback_command: · the `full` suite wrapper · bash-file list --invocations
                internal/annot          grammar v3 + rewriter (n006); adopt is a caller, at the fixed per-language position
                internal/deps           scanners (n006); direct-invocation and direct-import facts exposed to internal/seed
                internal/cost           ledger (n006) + costs --gate-timeout; run_id prefixes test- / full- / gate-
                internal/feedback       score · attribute (+ --propose) · readiness (+ LEVEL / NEXT / ADOPTED_UNREVIEWED / SEEDED / POLICY)
                internal/{axes,changesurface,sched,stale,gitx,platform}   unchanged
                  ├─ exec:  git, runner scripts / builtins, admission / allocator commands, scanner plugins
                  └─ files: aitestmap/** · .aitask-testmap/ (runs, ledger, onboard/<run>/seed.json) · XDG cache (deps; cochange matrix by HEAD sha)

.aitask-scripts/lib/gate_verifier_lib.sh           run_project_command_key(): + 75 → error (command_refused), 3 → error (command_errored) for opted-in keys;
                                                   exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command
.aitask-scripts/gates_reference.yaml               + testmap_fresh (procedure), testmap_check (unlocks: [tests_pass]);  NO testmap_run
.aitask-scripts/aitask_gate_testmap_check.sh       machine verifier (n006); reports SEEDED:<n>, ADOPTED:<n>, UNMAPPED_SOURCE:<path>
.aitask-scripts/aitask_gate_tests_pass.sh          unchanged; runs test_command = ./ait test under the opt-in
.aitask-scripts/aitask_setup.sh                    install_engine_binary (n006) + report_testmap_state() → TESTMAP:<state>
.claude/skills/aitask-testmap-onboard/             ← NEW  profile-aware stub + SKILL.md.j2 + one procedure file per phase
.claude/skills/aitask-testmap/                     n006; opens with `ait test --howto`; hands an un-onboarded repo to onboard
.claude/skills/aitask-gate-testmap-fresh/          n006 procedure gate + "adopt seeds on touched test files" step
.claude/skills/task-workflow/SKILL.md.j2           Step 7: one paragraph (the loop) + the pre-review Affected Tests Procedure (affected-tests.md)
.claude/skills/task-workflow/build-verification.md + one branch: verdict error / command_refused | command_errored
.claude/skills/aitask-qa/{test-discovery,test-execution}.md   registry-first branches
seed/aitasks_agent_instructions.seed.md            + `## Running Tests` (generic; installed into every agent surface by ait setup)
engine/                                             Go source — framework repo only, excluded from the tarball
```

The boundary rule is n001's, made precise by n006 and not bent: parse, walk,
match, digest, schedule, seed and adopt in Go; gate ledger, task file,
profile file, `project_config.yaml`, `gates.yaml`, `CLAUDE.md` and the shell
environment in bash and skill prose. `onboard` never creates a task, never
edits a profile and never commits — the skill does those through
`aitask_create.sh --batch`, `aitask_pick_own.sh`, the settings helpers and
`aitask_task_commit.sh`; the engine reads `onboard.yaml`'s `task:` and writes
its phase rows. The engine still never writes `aitasks/`, `aiplans/`,
`.aitask-data/` or a gate ledger and never invokes `aitask_*.sh`.

### Registry directory (n006's, with the additions marked)

```
aitestmap/
  config.yaml            n006 keys (unit_covers_max, suite_budget_s, bootstrap_until, require_stamp, broad_review_days,
                         concurrency, broad_after_unit, device_policy, host_class, flake_threshold, symbol_scanners, run_gate_admission)
                         + completion: {mode, deferred, on_empty_selection, engine_absent}        ← n008
                         + conventions: [{test, source}]  helper_roots: [...]  helper_fanin: 0.05   ← n008 (seeded by detect)
                         + exclude: [globs]  docs: [paths]  notes: | (<=10 lines)  broad_threshold_s: 60   ← n007
  onboard.yaml           ← n007  phase ledger: {contract, task, level, phases{...}, rejections[]}
  axes.yaml · runners.yaml · resources.yaml      n006; runners.yaml written by onboard detect --write, confirmed per runner
  registry/
    _scanned.yaml · _scoped.yaml · observed.yaml · areas.yaml · <area>.yaml    n006
    seeded.yaml          ← n007  the queue; generated by onboard seed; rows leave on adopt / reject
    adopted.yaml         ← n008  provenance of class-adopted edges; a row leaves when a human re-stamps the edge
  costs/ · runners/ · scanners/                  n006; runners/<name>.sh may come from onboard scaffold --runner
```

### `aitestmap/config.yaml`, the additions

```yaml
completion:                  # n008
  mode: full                 # full | selected — selected written only by the onboarding skill's --policy re-entry after READINESS_DECISION:ADMISSIBLE
  deferred: run              # run | fail — completion never silently drops a row the interactive budget would cut
  on_empty_selection: skip   # skip (exit 2 → gate skip under the opt-in) | full
  engine_absent: error       # error (exit 3) | fallback_command (the full: true suite runner's fallback_command:, MODE:fallback)
conventions:                 # n008; seeded by onboard detect per framework; the `convention` origin (0.60)
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/aitask_{stem}.sh"}
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/lib/{stem}.sh"}
  - {test: "tests/test_{stem}.py", source: ".aitask-scripts/lib/{stem}.py"}
helper_roots: ["tests/lib/**", "**/testing/**", "**/testdata/**"]     # n008
helper_fanin: 0.05           # n008: a closure path reached by ≥5 % of a runner's units is a helper, not a subject
exclude: ["tests/golden/**", "tests/data/**"]                          # n007: never listed, never UNREGISTERED
docs: [aidocs/testing/change-aware-verification.md]                    # n007: printed by --howto
notes: |                                                               # n007: printed by --howto verbatim, <=10 lines
  A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
broad_threshold_s: 60        # n007: classify signal — a recorded p95 above this proposes a broad kind
```

### Where the new state lives

| data | location | written by |
|---|---|---|
| seed queue | `aitestmap/registry/seeded.yaml` rows `{test[#member], covers, origin[], confidence, evidence{}, proposed_at}` | `onboard seed --apply`; `attribute --propose`; rows removed by `onboard adopt` / `reject` |
| adopted-edge provenance | `aitestmap/registry/adopted.yaml` rows `{test, source, origin[], confidence, adopted_at, task}` | `onboard adopt --class`; rows deleted when `verify`, `annotate`, `stale --confirm-source` or a per-row `adopt` re-stamps that edge |
| phase ledger | `aitestmap/onboard.yaml` `{contract, task, level, phases{detect,inventory,seed,waivers,enable,full_run,adopt,classify,scaffold,finish: {status, at, by, counts}}, rejections[]}` | the engine's `onboard` verbs; read by `onboard status`, `report_testmap_state()`, the skill's re-entry |
| the seed dump for review and attachment | `.aitask-testmap/onboard/<run-id>/seed.json` (gitignored), attached to the level task with `ait attach` | `onboard seed --json --out` |
| completion policy, conventions, helper roots, docs, notes, excludes | `aitestmap/config.yaml` | `onboard detect --write` (level 0); the skill's `enable` phase (`docs:`, `notes:`); the `--policy` re-entry (`completion.mode`, `run_gate_admission.approved_by`) |
| test entry and exit-contract opt-in | `aitasks/metadata/project_config.yaml`: `test_command: ./ait test`, `gate_command_exit_contract: [test_command]` | the skill's `enable` phase, confirmed once as a table |
| gate declarations | profiles' `default_gates` (`tests_pass`, `testmap_check`, `testmap_fresh`); `gates.yaml` `tests_pass.timeout_seconds` | the skill's `enable` phase; the timeout from `costs --gate-timeout` after the first full run |
| agent instructions | `CLAUDE.md` `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md`, OpenCode mirror | `ait setup` from the seed; a hand-maintained `CLAUDE.md` by the level-0 task |

### The three-state adoption model

```
                onboard seed --apply                          onboard adopt --class <origin> [--accept-min 0.85] [--scope <glob>]
   (none) ─────────────────────────────▶ SEEDED ────────────────────────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row)
   attribute --propose ──────────────────▶  │  (selects at d1, no stamp,                                            │
                                            │   invisible to stale, never --strict)                                  │ human re-stamp: verify · stale --confirm* · annotate
                                            │ onboard adopt <test> <source> | --area <a> --batch <n> | in-gate row   ▼
                                            ├──────────────────────────────────────────────────────────────▶ REVIEWED (stamp, no provenance row)
                                            │ onboard reject <test> <source> --reason
                                            ▼
                                        REJECTED (onboard.yaml; never re-proposed)
```

`SEEDED` selects; `ADOPTED` and `REVIEWED` claim; only `REVIEWED` is a claim a
named person made about that pair. `check` prints `SEEDED:<n>` and
`ADOPTED:<n>` (informational); `readiness` prints `ADOPTED_UNREVIEWED:<n>|<ratio>`
and `SEEDED:<n>`; `stale` and `explain` show `adopted(<origins> <confidence>)`
on an adopted edge's `DISPLAY` line so the procedure gate knows it is
confirming a class-accepted claim. A seed with the same `(test, covers)` as any
stamped edge is dropped at load with `SEED_SHADOWED`.
<!-- /section: architecture -->

<!-- section: adoption_model [dimensions: component_seeder, component_onboarding_engine_verbs, component_registry_loader, component_annotation_scanner, component_dependency_scanners, assumption_seed_sources_measured, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_seeds_select_never_evidence, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only] -->
## Seeds: Origins, Confidence, Helpers, Placement

### One origin table

| origin | rule | measured (n007 / n008, 2026-09-16) | confidence |
|---|---|---|---|
| `static:package` | a `_test.go`'s subject is the non-test files of its own package | aitasks_go: deterministic, 85 packages | **1.00** |
| `coverage` | per-unit runtime coverage, opt-in: coverage.py dynamic contexts, `go test -run <unit> -coverprofile`, LCOV with a test column, a project plugin's `{test, covers}` lines (JaCoCo per-test sessions) | opt-in | 0.95 |
| `static:invocation` | a literal repo path the test executes or sources (bash: `./.aitask-scripts/x.sh`, `source lib/y.sh`, `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms resolved against every source root) | aitasks bash: 350/400 (n007) … 398/400 (n008 counting `lib/` too), avg 3 paths | 0.90 |
| `static:import` | a direct import of a main-root file (Python through the file's own `sys.path` bootstrap; Kotlin imports; same-package facts excluded) | aitasks Python 255–320/320, avg 1; thinking_app 139/339, avg 3 | 0.85 |
| `observed` | an `attribute --propose` row from a scored full-run miss | — | 0.70 |
| `convention` | `config.yaml conventions:` patterns seeded by `detect` per framework (`test_<x>.sh → aitask_<x>.sh \| lib/<x>.{sh,py}`, `test_<x>.py → <x>.py`, `<Stem>Test.kt → <Stem>.kt`) | 52–72/400 bash, 62/320 Python, 48/307 Kotlin | 0.60 |
| `plan` | an `aiplans/` file naming both paths, through the `aitask_explain_extract_raw_data.sh` cache when present | — | 0.50 |
| `prose` | a literal path in the unit's header comment or a `# Covers:` line (38 in aitasks) — displayed beside the seed as reviewer context, never matched by the annotation scanner | — | 0.30 |
| `cochange` | `(test, source)` co-occurring in ≥ 2 distinct `(t<id>)` task groups over one `git log --name-status -M --format=%H%x00%s` pass, cached by HEAD sha; per-commit grouping where the convention is absent; `SEED_HISTORY:shallow\|<n>` on a shallow clone | aitasks: 439/600 task commits, 2.8 × 2.6 (tight); 336 groups in 400 commits at 1.14 commits each with nothing inside a group saying which covers which; thinking_app: 127/400 at 7.2 main files (noisy) | 0.20 + 0.20 × groups, **cap 0.60** |

Combination is noisy-OR, `1 − Π(1 − cᵢ)`. The default class-acceptance
threshold is 0.85: `static:invocation` or `static:import` alone qualifies,
`convention` alone (0.60) does not, `cochange` (≤ 0.60) never does, and
`convention + cochange` (0.84 at the cap) does not either — corroboration
raises a static edge's rank and cannot manufacture one. Confidence orders the
queue and never hides a row. The static origins read the same `internal/deps`
facts the selector's test-side closure uses — once, from the blob-keyed
cache; only the *direct* relation is seeded, the deeper closure stays the d2
walk.

### Helpers before subjects

A closure path is a helper, not a subject, when it is under `helper_roots`
(`tests/lib/**`, `**/testing/**`, `**/src/test/**` for Kotlin, `**/testdata/**`)
or when its fan-in reaches ≥ `helper_fanin` (5 % of the runner's units). A
helper gets `test-dep` selection through the closure for free and, when it
globs the tree (`ls tests/*.sh`, `glob.glob`, `rglob`, `find`, `git
ls-files`, `os.walk` — aitasks: `tests/lib/import_isolated.py`,
`board_fixture.py`, `validate_session_hook_fixtures.py`), a proposed
`testmap:reads` line (`SEED_READS:<helper>|<glob>|<evidence>`) written at
level 2 on class acceptance. A hot production module misread as a helper keeps
`test-dep` selection (over-selects), and every fan-in reclassification is
listed for review.

### Kinds, members, axes as seeds

`onboard classify` wraps n006's `classify --suggest` with the three
onboarding signals — a recorded p95 above `broad_threshold_s` from the first
full run, a source-set or directory convention (`androidTest/`,
`androidDeviceTest/`, `*_live.py`, `*_integration.sh`, `parity/`), a resource
named in the file (tmux, `App.run_test`, `install.sh --dir`, real `.git` use,
emulator, docker, network) and `fanout:<n>` above `unit_covers_max` — each
printed as the reason on `CLASSIFY:<test>|<kind>|<reason>`, with areas from
the closure's directories intersected with `code_areas.yaml`; `SEED_BATCH_NO`
from an aggregate runner's serial list; `SEED_MEMBER` / `SEED_AXIS` from the
grid heuristic. Kind changes are confirmed individually, never per class,
because a wrong kind changes staleness semantics rather than selection breadth.

### Placement: comments only

`onboard adopt` writes through `internal/annot`'s line-targeted rewriter at a
fixed position per language, comment lines only: bash after the header
comment block (after the shebang and leading `#` block); Python as `#` lines
after the module docstring — the grammar reads docstring lines (n001/n002)
but adoption never writes into one because that changes `__doc__`; Go after
the package clause; Kotlin after the import block, or inside the member's
`testmap:unit` block for a member seed. `git diff -w --ignore-blank-lines` of
an adopted file shows comments only. Refusals and skips are explicit:
`ADOPT_REFUSED:<path>|dirty-foreign` for a file dirty outside the current
task's change surface, `ADOPT_SKIP:<path>|duplicate` (already annotated —
`SEED_SHADOWED` at load), `ADOPT_SKIP:<path>|unregistered` (no runner lists
it), `ADOPT_SKIP:<path>|no-leader`; `WROTE:<path>` per file and one
`ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>`. Each written stamp is
`@<date>/<blob10>` at adopt time; a class-adopted edge also gets its
`adopted.yaml` row.

### What seeding cannot do, stated

thinking_app's tests resolve imports for 139 of 339 files because same-package
references need no import and "same package is fully connected" is too coarse
to seed; fixture-driven tests and screen members seed through `annotate
--from-body` (n006) and level 3; sources reached by no origin stay
`UNMAPPED_SOURCE:` until a rule, a waiver, a Step-7 prompt or a coverage import
maps them. `onboard status` reports that state ("selecting on 84 % of tests,
claiming on 18 %") rather than hiding it.
<!-- /section: adoption_model -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_onboarding_engine_verbs, component_seeder, requirements_zero_config_onboarding, requirements_onboarding_existing_tests, requirements_incremental_adoption, assumption_test_tools_detectable, assumption_onboarding_is_a_task, assumption_full_run_expressible_per_repo] -->
## Onboarding: Levels × Phases, One Aitask per Level

### Levels (what the registry has) and phases (how a level's task gets there)

| level | phases in the level's task | what `onboard` writes | what the repository gains | who accepts |
|---|---|---|---|---|
| **0 — runners and universe** | preflight → **detect** (`--write`) → **inventory** → **seed** → **waivers** → **enable** → **full_run** (= the task's `tests_pass` at Step 9) | `config.yaml` (`bootstrap_until` today + 90, `require_stamp false`, `concurrency serial`, `completion.mode full`, `conventions:`, `helper_roots:`), `runners.yaml` (builtins + bindings by glob; a `full: true` suite runner from `test_command` with `fallback_command:`), `resources.yaml` from hints, `registry/areas.yaml` via `areas --import-codemap`, `_scanned.yaml`, `registry/seeded.yaml`, rules and expiring waivers in `registry/<area>.yaml` | the universe (`list`), `ait test --all`, per-unit cost and `last_pass` from the first full run, selection through seeds and the test-file closure, scoring of every later full run; nothing stamped | the runner table (keep / edit command / drop, per runner), `UNREGISTERED` files (bind / `exclude:` / not a test), the config table once — headless-safe |
| **1 — edges** | **adopt** per evidence class (`--class static:invocation`, …) or per area (`--scope <glob> --batch 50`), then incrementally inside `testmap_fresh` | stamped `testmap:covers` blocks; `registry/adopted.yaml` rows for class adoptions; rows leave `seeded.yaml` | freshness and the evidence join apply; `stale` reports; `testmap_check` is meaningful; `UNMAPPED_SOURCE` shrinks | per class (accept all / review a sample of ten / skip) or per row; headless: `static:package` only |
| **2 — kinds** | **classify** (per batch of 20, kind changes individually) → `scan --apply` | `testmap:kind integration\|e2e\|device` + `testmap:area` / `testmap:scope` on broad tests, `testmap:reads` on tree-scanning helpers, `testmap:batch no` from serial lists, `needs:` bindings from resource hints, `resources.yaml` entries | scoped rows, the suite budget, `broad_after_unit`, enforced do-not-overlap (aitasks: `repo-git-index` mutex, worktree scope) | per kind, individually |
| **3 — product** | **scaffold** (`--axes`, `--runner <builtin> --as <name>`, `--members`) → `annotate --from-body` per member | `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` with `describe`/`run` delegating to the builtin and `list` printing `SCAFFOLD_TODO` until filled (check reports it), `testmap:unit` member blocks | variant selection (n006's thinking_app mapping) | the maintainer, with the skill |
| **finish** | a phase of whichever level task the maintainer names last | `require_stamp: true`; `check --strict`; `bootstrap_until` shortened | enforcement | `onboard status` green: no pending phase, seed queue ≤ a user-set threshold (default 0), `check` clean |

`readiness` derives `LEVEL:<0-3>` from what exists (`runners.yaml` → 0, any
stamped `_scanned` edge → 1, any `_scoped` row or `reads` → 2, `axes.yaml` →
3) and prints `NEXT:<the phase or level that raises it>`; `onboard status`
prints the ledger's `ONBOARD_NEXT:<phase>`, the seed queue per origin, the
adopted-unreviewed count, tests-with-any-edge and sources-with-any-edge
ratios, the oldest pending seed's age, and the rejections count. The two
agree by construction: `LEVEL` is a property of the tree, `ONBOARD_NEXT` a
property of the run.

### Invocation and task shape

`/aitask-testmap-onboard [--level <n>] [--policy selected] [--no-task]`.
Preconditions: `ait testmap version` (absent → stop with the `ait setup`
hint); `aitestmap/` present with a finished ledger → *refresh mode* (seed
limited to units newer than `adopted.yaml`'s last row, same flow); an
unfinished ledger → re-enter at `ONBOARD_NEXT:`. The read-only survey runs
`onboard detect` and `onboard seed --json --out .aitask-testmap/onboard/<run>/seed.json`
and shows the level proposal: frameworks and counts, edges per evidence class
with three samples each, helpers found and which glob, kind candidates with
reasons, `UNLISTED` files, `RUNNER_SCRIPT_NEEDED` if any, and the config
writes. The skill then creates the level's aitask (`aitask_create.sh --batch
--name "testmap onboarding level <n>" --type chore --labels testing,testmap`,
`ait attach` the seed dump), claims it (`aitask_pick_own.sh`), writes the id
and level into `onboard.yaml`, and continues into task-workflow honouring the
profile (the `explore_auto_continue` shape). The plan is the phase list; at
Step 7 each phase ends with `chore: Onboard testmap — <phase> (t<id>)`
through `aitask_task_commit.sh` with paths named, so `aitask_change_surface.sh`
attributes the files and a resumed session re-enters at `ONBOARD_NEXT:`; Step
8 reviews the annotation diff and dispatches `testmap_fresh` (nothing `STALE`
yet — every stamp is today's); Step 9's `tests_pass` runs `./ait test --gate`
under `completion.mode: full`, which for the level-0 task is the **first full
run**: every unit's `last_pass` anchored, `PREDICTION_SCORED:none` because
nothing was predicted yet, `costs --update` folded; the archive commits
registry, annotations and config under one `(t<id>)`. After it: `costs
--gate-timeout tests_pass` → `GATE_TIMEOUT_SUGGESTED:tests_pass|<s>` =
`max(600, 3 × p95)` written into the project's `gates.yaml`; `readiness` →
`LEVEL` / `NEXT`; the next level's task created with `depends:` on this one.
`--no-task` writes without committing and prints the commit lines, for a repo
that forbids tasks on the code branch. The `--policy selected` re-entry runs
`readiness` and only on `READINESS_DECISION:ADMISSIBLE` writes
`completion.mode: selected` and `run_gate_admission.approved_by {who, at,
statement}` in one `ait:` commit; `NOT_YET` prints the unmet criteria and
stops.

Headless (`remote`) profile: level 0 in full (every write is a registry file
or a seed), adoption of `static:package` origins only (`--accept-min 1.0`), no
kinds, no scaffold, no policy flip, no prompts — the level proposal is
printed, not asked.

### Detection, per target repository

| repository | `onboard detect` | level 0 runners and resources | full run (`completion.mode: full`) | levels 1–3 |
|---|---|---|---|---|
| **aitasks** | `FRAMEWORK:bash-file\|tests/**/test_*.sh\|400`, `FRAMEWORK:pytest\|tests/test_*.py\|320`, `AGGREGATE_RUNNER:tests/run_all_python_tests.sh`, `SERIAL_LIST:…\|4`, `RESOURCE_HINT:repo-git-index\|~40 tests`, `SUITE_CANDIDATE:test_command\|null`, `UNIVERSE:720 UNLISTED:0` | `bash-file`, `pytest` (`testmap:batch no` on the four carve-out modules, pinned by extending `test_serial_carveout_doc_drift.sh`); `resources.yaml`: `repo-git-index {kind: mutex, scope: worktree}` — the "invocation policy, not a guarantee" comment in `run_all_python_tests.sh` becomes enforced | `ait test --all` (no suite command existed; `tests_pass` gates for the first time); `fallback_command` derived: `for f in tests/test_*.sh; do bash "$f"; done && bash tests/run_all_python_tests.sh` | 1: 398 + 320 static edges, 52–72 corroborated by convention; helpers `tests/lib/` (27; 3 `reads`); 2: ~40 tmux / live-TUI / real-install tests → `integration` over codemap areas; 3: `tests/golden/` as a skill × profile × agent axis |
| **thinking_app** | gradle-class 374 classes, `RUNNER_SCRIPT_NEEDED:grid` (screen × matrix), `SUITE_CANDIDATE:test_command\|verify-active`, `RESOURCE_HINT:heavy-run` (exit-75 lock script) | `gradle-class` builtin until the project runner exists; `verify-active {unit: suite, full: true, children: …, fallback_command: tools/verification/screenshot-tests.sh verify-active}`; `heavy-run {kind: admission, exec: heavy-run-lock.sh}` | `verify-active` once (`screen-matrix` and `gradle-class` `subsumed_by: verify-active`) — identical to today's `test_command` | 3 = n006's worked mapping: `onboard scaffold --runner gradle-class --as screen-matrix` → `tools/verification/testmap_runner.sh` whose `list` the project fills from the manifests; `axes.yaml`; `testmap:unit` blocks in `ScreenFixtures.kt`; `completion.mode` stays `full` until readiness — t388's rule |
| **thinking_backend** | bash-file 22 + pytest 18 under `scripts/tests/`, `SUITE_CANDIDATE:verify_build\|scripts/tests/run_script_tests.sh` | `bash-file`, `pytest` with `cwd:`; the skill asks: keep `verify_build` (it also enforces a shellcheck baseline) and add `test_command: ./ait test` — the default | `ait test --all` over the 40 units; `build_verified` still runs the script | 1: static edges into `scripts/server/**` and `db_target.py`; 2: `golden/` fixtures as `reads` |
| **aitasks_go** | go-test: 85 packages, 55 `_test.go` files, `Makefile test`, `parity/run_parity.sh` (tmux + venv) | `go-test` (per package, `-run`, `-json`); `parity` as `suite`, kind e2e, resource `tmux` | `go test ./...` = `ait test --all` | 1 fully automatic and headless-safe: `static:package` at 1.0 |
| **aitasks_mobile** | kmp-sourceset: `commonTest` 36 (dbaccess 2, domain 25, shared 9), `androidHostTest` 1, `androidDeviceTest` 3 | `gradle-class` × modules on `:<module>:jvmTest` / `testDebugUnitTest`; `device` on `connectedDebugAndroidTest` with `emulator {kind: allocator}` | unit kinds only; device kind under `device_policy: filter_by_resource` — n006's open question 9 answered: the source set is a runner/kind distinction, no axis | 1: Kotlin import closure (`domain/src/commonMain/**`) |

In every row the user typed nothing; the skill showed the table and asked for
one confirmation per runner, one per evidence class, one per kind change and
one per config write.
<!-- /section: onboarding -->

<!-- section: run_surface [dimensions: component_test_entrypoint, component_test_front_verb, component_agent_brief, component_agent_instructions, requirements_zero_config_entrypoint, requirements_agent_run_surface, requirements_agent_instructions_seeded, assumption_task_resolvable_from_session, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_instruction_block_is_read, assumption_change_surface_is_intake] -->
## The Run Surface an Agent Learns Once

### `ait test`

```
ait test                       selected tests for the task you are implementing, each with a reason
ait test <path|id>...          named units: a listed test file, file#member, file#member@variant, a directory of tests,
                               or a SOURCE path — treated as a one-file TASK: change set, so `ait test lib/foo.py` runs what covers it
ait test --all                 the whole registry: every runner's list, full: true suites once, subsumed_by runners skipped
ait test --task <id>           override task resolution
ait test --gate                completion mode — what tests_pass runs; implied by $AIT_GATE_TASK_ID
ait test --advisory --task <id> [--explain]
                               the Step-7 form: VERDICT:/REASON:/DETAIL:/LOG: lines, exit 0/1/2/3, every absence a printed skip
ait test --explain             the selection with reasons, groups and estimated cost; runs nothing (n007's --mode show)
ait test --howto [--md]        this project's runners, kinds, resources, full gate, axes, completion policy, LEVEL, docs, notes
ait test --tokens              select --format tokens (thinking_app: `| xargs tools/verification/screenshot-tests.sh preview`)
ait test --dirty               no task: every dirty path as a TASK: row; explicit, printed as INTAKE:dirty, never the default
ait test --fresh-only          exclude stale-marked units (interactive only)
ait test --budget-s <n>        interactive suite budget override
ait test --json                one object instead of lines
```

### Resolution, in order

1. **Registry present?** No `aitestmap/config.yaml` → `TESTMAP_ABSENT:run
   /aitask-testmap-onboard to enable change-aware selection`, then delegate to
   `aitask_run_project_command.sh test_command` (with `--task-id` when a task
   resolved), exiting with its verdict; `--howto` prints the same line plus the
   `test_command`. This is what makes "always `./ait test`" true on day one.
   Advisory mode: `VERDICT:skip REASON:registry_absent`.
2. **Engine present?** Through the n006 shim's strict handshake. Absent:
   interactive → `ENGINE_MISSING:<path>|run 'ait setup' or set AIT_TESTMAP_BIN`,
   exit 3; completion → `completion.engine_absent`: `error` (default, exit 3 →
   verifier `error`) or `fallback_command` (run the `full: true` suite runner's
   `fallback_command:`, print `MODE:fallback`, exit per the command); advisory
   → `VERDICT:skip REASON:testmap_absent`.
3. **Mode.** `--gate` or `$AIT_GATE_TASK_ID` → `completion`; `--advisory` →
   `advisory`; else `interactive`. Printed as `MODE:`.
4. **Task.** `--task` > `$AIT_GATE_TASK_ID` > the current worktree's branch if
   it matches `aitask/t<id>_*` (task-workflow's naming) > the locks this user
   holds on this host (`aitask_lock.sh --list-mine`, a listing verb added to
   the lock script): exactly one → that task; several → `AMBIGUOUS_TASK:<ids>`,
   exit 64 unless `--task`; none → `TASK:none`.
5. **Intake.** Named paths → units by registry lookup, or a source path → a
   synthetic `TASK:<path>` change set; `--all` → every runner's `list`; a
   resolved task → `aitask_change_surface.sh list <id>` piped to `--changes -`
   (`UNKNOWN:` refuses — advisory: `VERDICT:skip REASON:unknown_paths` naming
   them; `aitasks/`, `aiplans/`, `.aitask-data/` excluded); `--dirty` → `git
   status --porcelain` paths as `TASK:` rows; nothing → `NO_TASK:` with the
   three ways out, exit 64 (advisory: 3).
6. **Policy (completion only).** `completion.mode`; if `selected`, run
   `readiness` first: every criterion met → the task selection with `deferred:
   run`; any unmet → `POLICY_DEMOTED:selected->full|<criterion>` and run
   `full`. `full` → `run --all` with `subsumed_by` honoured. `on_empty_selection:
   skip` → exit 2 → the opted-in `tests_pass` records `skip`, never `pass`.
7. **Run.** The engine `test` composite: `select --include-stale [--budget-s]
   [--format …] --run <run-id>` → `schedule` → `run`; prints `SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`,
   one `UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked
   rows with n006's reasons (a seeded edge reads `edge(seeded:static:invocation,cochange)`,
   an adopted one `edge(annotation) adopted(static:invocation 0.90)`), `DEFERRED:`
   in interactive mode only, the waves, results per id, `RESULT:`. The run id is
   prefixed `test-` (interactive), `gate-` (completion) or `full-` (`--all`), so
   the ledger says which surface produced a row; all three anchor evidence.
8. **New-test and new-source notices.** `UNANNOTATED_TEST:<path>` + `HINT:./ait
   testmap annotate --suggest <path>` for a listed test in the change surface
   with no `testmap:` block, no seed and no adopted row; `UNMAPPED_SOURCE:<path>`
   for a changed source with no edge, seed, rule or waiver. Informational in
   interactive mode; the Step-7 procedure offers the fix; in completion mode
   `testmap_check` owns enforcement.

### Output and exit contract

```
MODE:interactive|completion|advisory|fallback   TASK:<id>|none   INTAKE:change-surface|dirty|all|named
POLICY:full|selected|<demoted…>   SELECTED:<units>|<groups>|<est_s>|<seeded>|<adopted>   RUN:<run-id>
ESCALATE:… DEFERRED:… UNMAPPED_SOURCE:… UNANNOTATED_TEST:… HINT:…       (n006/n007/n008 line classes pass through)
RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>
advisory only:  VERDICT:pass|fail|skip   REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
                DETAIL:<one line>   LOG:.aitask-gates/<task>/affected_<run-id>.log
```

| exit | meaning | as `test_command` under the opt-in | advisory mode |
|---|---|---|---|
| 0 | every selected unit passed | pass | `VERDICT:pass` |
| 1 | a unit failed, or a mechanism failure | fail | `VERDICT:fail REASON:command_failed` |
| 2 | nothing ran: empty selection, or `TESTMAP_ABSENT` + no `test_command` | skip | `VERDICT:skip REASON:no_selection` (+ `UNMAPPED_SOURCE:` lines) |
| 3 | framework error: engine missing / mismatched, `CONTRACT_MISMATCH`, `UNKNOWN:` intake | **error** (`command_errored`) | `VERDICT:skip` with the reason (`testmap_absent`, `registry_absent`, `unknown_paths`); exit 3 only when the log cannot be written |
| 75 | admission refused after the in-engine deferral to the run deadline | **error** (`command_refused`) | `VERDICT:skip REASON:admission_refused` |
| 64 | usage: `NO_TASK`, `AMBIGUOUS_TASK`, bad flag | fail | 3 |

Advisory mode speaks `aitask_run_project_command.sh`'s `0/1/2/3` domain and
the `set -e` capture form `build-verification.md` already teaches, so the
Step-7 procedure cannot disagree with the Step-9 path about an exit code. It
writes the engine's full output to the log, appends nothing to any gate
ledger, and is the one deliberate exception to "a missing engine is an error":
an *advisory* run must never block a task the way a declared gate legitimately
does; the skip is printed, never silent.

### The two environment variables

`run_command_gate` exports `AIT_GATE_TASK_ID=<task-id>` and
`AIT_GATE_RUN_ID=<run-id>` around the command; `aitask_run_project_command.sh
--task-id <id>` exports the first. That is how `./ait test` knows it is a
completion run and for which task in all three call sites (the `tests_pass`
verifier, the legacy Step-9 helper, `aitask-qa`) with no argument in
`test_command`; the run id names the gate run in `.aitask-testmap/runs/<run-id>/`
so a ledger row and a gate log share an identifier.

### `ait test --howto` (engine verb `brief`)

For thinking_app after level 3, on this host class:

```
TESTMAP:onboarded|since 2026-09-16|LEVEL:3|POLICY:full|seeds pending 412|adopted unreviewed 618
RUNNER:gradle-class|unit|371 classes|screenshot-tests.sh unit-tests --tests <class>|heavy-run
RUNNER:screen-matrix|unit (variant, axis matrix)|49 members x 10 matrices = 297|screenshot-tests.sh unit-tests --tests <class>.<method>|heavy-run
RUNNER:verify-active|suite (full)|1|screenshot-tests.sh verify-active|heavy-run|subsumes screen-matrix,gradle-class
FULL_GATE:verify-active|p95 1180s|= project_config test_command|tests_pass timeout 3540s
GATE:testmap_fresh (procedure, before commit) -> testmap_check -> tests_pass = ./ait test --gate (full)
VERBS:./ait test | ./ait test <path>... | ./ait test --all | ./ait test --howto
AXES:matrix|facets locale,direction,geometry|10 values
RESOURCE:heavy-run|admission (tools/verification/heavy-run-lock.sh)|refusal = exit 75 -> deferred to run deadline
NEW_TEST:./ait testmap annotate --suggest <path>
DOCS:aidocs/testing/rendering-verification.md
DOCS:aidocs/testing/change-aware-verification.md
NOTES:A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
NOTES:Never run ./gradlew test directly - the harness owns the heavy-run slot and the run id.
```

Everything above `DOCS:` is computed from the registry, the ledger and
`config.yaml`; `DOCS:` and `NOTES:` are what the `enable` phase asked the
maintainer for — the judgement calls a registry cannot hold, kept to ten
lines and reached through one verb. `--md` renders the same as markdown;
`ONBOARD_NEXT:` appears while a ledger is unfinished; < 100 ms warm.

### The generic instructions section

Added to `seed/aitasks_agent_instructions.seed.md`, therefore inserted
between the `>>>aitasks` / `<<<aitasks` markers of every supported agent's
instructions file (`CLAUDE.md`, `AGENTS.md`, `.codex/instructions.md`, the
OpenCode mirror) on the next `ait setup` or `ait upgrade` by
`assemble_aitasks_instructions()` / `insert_aitasks_instructions()`, with no
per-project edit:

```markdown
## Running Tests

Run tests only through the framework entrypoint — never call pytest, go test, gradle
or a test script directly.

    ./ait test              # tests selected for the task you are implementing, a reason per line
    ./ait test <path>...    # a named test file or unit; a SOURCE path runs what covers it
    ./ait test --all        # the whole suite — what completion runs while the project's policy is `full`
    ./ait test --howto      # this project's runners, kinds, resources, full gate, policy and notes

`UNANNOTATED_TEST:<path>` for a test you added → `./ait testmap annotate --suggest <path>`.
`UNMAPPED_SOURCE:<path>` for a source no test reaches → map it before the gate (`/aitask-testmap`).
`TESTMAP_ABSENT` means the project is not onboarded → `/aitask-testmap-onboard`.
Exit codes: 0 pass · 1 fail · 2 nothing ran · 3 framework error (run `ait setup`) · 75 host refused (already waited; retry later).
```

Fourteen lines, no agent named, no project specifics (those are `--howto`'s
computed output, so the current-state-only documentation rule holds and no
constant condenses `runners.yaml`), correct before onboarding (the verb runs
`test_command`). `tests/test_agent_instructions.sh` gains T40 asserting the
heading in all four rendered surfaces through a real `install.sh --dir`. This
repository's own hand-maintained `CLAUDE.md` (sentinel present, no markers) is
edited by its level-0 onboarding task to point at `./ait test` and keep the
runner-specific notes (`run_all_python_tests.sh` lanes, the `PIPESTATUS`
caveat) as background.
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_workflow_integration, component_gates, component_completion_policy, component_qa_integration, requirements_workflow_seam, requirements_workflow_seam_is_data, requirements_gate_enforcement, assumption_gate_exit_contract_reused] -->
## The Workflow Seam and the One Completion Gate

### The concrete edits

| where | change | kind | from |
|---|---|---|---|
| `task-workflow/SKILL.md.j2` Step 7, after *Follow the approved plan* | one paragraph: "**Test loop.** Run `./ait test` after each meaningful change — it selects from this task's change surface and prints a reason per unit. `UNANNOTATED_TEST:<path>` → `./ait testmap annotate --suggest <path>`; `UNMAPPED_SOURCE:<path>` → map it (`/aitask-testmap`). Do not invoke the project's test tool directly; `./ait test <path>` runs one unit." | prose, every profile; goldens regenerated | n008 |
| `task-workflow/SKILL.md.j2` Step 7, once before Step 8 | the **pre-review affected run**: the Affected Tests Procedure (`affected-tests.md`) under `{% if profile.affected_tests is not defined or profile.affected_tests != 'off' %}` | procedure | n007 |
| `task-workflow/affected-tests.md` | `./ait test --advisory --task <id> [--explain]` with the `set -e` capture form; the branch table below; the verdict line recorded in the plan's Final Implementation Notes, never in the gate ledger | procedure file | n007 |
| `task-workflow/profiles.md`, `remote.yaml` | profile key `affected_tests: run\|show\|off` (default `run`; `default.yaml` and `fast.yaml` omit it; `remote.yaml` sets `run`) | data + one doc row | n007 |
| Step 8 | n006's `testmap_fresh` procedure-gate dispatch before the change summary; inside the gate, one new step: for each `COMMITTED:`/`TASK:` test file with rows in `seeded.yaml`, show the seeds with evidence and offer adopt / reject / leave per row — accepted rows ride the same `(t<id>)` commit | inherited + one step | n007 |
| Step 9 verify block (`./ait gates run`) | none — the orchestrator runs `testmap_check` → `tests_pass` (= `./ait test --gate`) | none | n008 |
| Step 9 no-gates branch (`build-verification.md`, `verify_build`) | none in prose; a project reaches the test lane by declaring `tests_pass`, which onboarding writes into `default_gates` | data | n008 |
| `build-verification.md` | one branch: verdict `error` with reason `command_refused` / `command_errored` → host refused resources or the framework could not run; do not fix code, do not record a pass, report and re-run later | prose | n008 |
| `lib/gate_verifier_lib.sh` `run_project_command_key()` | opted-in keys: 75 → `error`/3/`command_refused`, 3 → `error`/3/`command_errored`; exports `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` around the command; docblock table updated — the single canonical statement | code; `tests/test_gate_verifiers.sh` extended | n008 |
| `aitask_run_project_command.sh` | `--task-id` also exports `AIT_GATE_TASK_ID`; inherits the new rows | code | n008 |
| `gates_reference.yaml` → `gates.yaml` sync | + `testmap_fresh` (procedure, verifier `aitask-gate-testmap-fresh`), + `testmap_check` (`unlocks: [tests_pass]`, `max_retries: 0`, `timeout_seconds: 120`); **no `testmap_run`**; `tests_pass` unchanged in the reference, `timeout_seconds` tuned per project from the ledger | data | n008 |
| project profiles | `default_gates` += `tests_pass`, `testmap_check`, `testmap_fresh` (the onboarding `enable` phase, confirmed; `rendered_gates` when present) | data | n007 + n008 |
| `aitask_gate_testmap_check.sh` | n006's verifier; rows `SEEDED:<n>`, `ADOPTED:<n>` (informational), `UNMAPPED_SOURCE:<path>` (reported during bootstrap, fails under `--strict` past `bootstrap_until`) | code | n007 |
| `aitask-qa/test-discovery.md` 3a–3c | with `aitestmap/`: `ait testmap explain --sources <changed files> --format table` → Source / Test / Reason / Status with `Covered`, `Covered (adopted)`, `Covered (seeded)`, `GAP` (= `UNMAPPED_SOURCE`); else the legacy convention scan | prose | n007 verb, n008 edits |
| `aitask-qa/test-execution.md` 4a–4d | 4a: the configured `./ait test` through `aitask_run_project_command.sh test_command --task-id <id>`; 4b: named units via `ait test <path>`; 4c: `REFUSED (host resources)` row, treated as `SKIP` in the health score; 4d: coverage from registry edges (seeded counted as `Covered (seeded)`) | prose | n008 |
| `aitask-pickrem`, `aitask-pickweb`, `aitask-resume` | inherit through task-workflow and `build-verification.md`; pickweb (no `ait setup`) sees `VERDICT:skip REASON:testmap_absent` at Step 7 and the `engine_absent` policy at completion | none | both |
| `aitask_setup.sh` | `report_testmap_state()` after `install_engine_binary()`: `TESTMAP:engine-missing\|absent\|bootstrapping\|<next>\|onboarded`, hint `run /aitask-testmap-onboard` on `absent`; setup never onboards | code; `test_install_engine_binary.sh` asserts each state | n007 |
| `ait` dispatcher | `test)` → `aitask_test.sh`; help line | code | both |
| permission touchpoints (5) | `aitask_test.sh` (its `--advisory` form replaces a second helper); `tests/test_touchpoint_count_contract.sh` re-pinned | config | both |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a test-framework detector" (closed list, evidence line, fixture repo, `UNLISTED` behaviour) and "Adding a seed origin" (confidence row, evidence field, fixture) | doc | n008 + new |
| `aitask_skill_verify.sh` + goldens | task-workflow, aitask-qa, the new onboarding stub, every profile × agent | test | both |

### The pre-review Affected Tests Procedure

```bash
if at_out="$(./ait test --advisory --task <task_id> {{ '--explain' if profile.affected_tests == 'show' else '' }})"; then
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
| `at_rc` 3 or empty verdict | infrastructure — diagnose the entrypoint / engine; never "fix the code"; never a pass |
| `pass` | display `SELECTED:` and continue |
| `fail` | read `at_log`; caused by this task → fix and re-run; unrelated → log under **Affected tests** in the plan's Final Implementation Notes and proceed (the `build-verification.md` loop, verbatim) |
| `skip` · `no_selection` | display the `UNMAPPED_SOURCE:` paths; **offer** (`AskUserQuestion`, non-skippable in attended profiles): *Annotate now* (`/aitask-testmap` → `annotate` / a rule) · *Propose for review* (`attribute --propose`, lands in `seeded.yaml` with origin `observed`) · *Continue unmapped*. Autonomous profiles take *Propose for review* |
| `skip` · `unknown_paths` | the Step-2b-style scope prompt from `aitask-gate-docs-updated`: include / subset / exclude; autonomous profiles exclude and log |
| `skip` · `admission_refused` | print `at_detail` (the host refused the heavy slot until the deadline); continue — nothing failed |
| `skip` · `testmap_absent` / `registry_absent` | one line; continue — not onboarded, or this host has no engine |

Why the procedure exists when the loop is a paragraph and the gate is
`tests_pass`: the advisory run is the one that writes the task's
`prediction.json`; the completion run (`full` policy) scores it
(`PREDICTION_SCORED` / `PREDICTION_FALSE_NEGATIVES`) into
`costs/predictions.yaml`; `readiness` counts those rows toward
`min_scored_full_runs`. A repository whose tasks never run the advisory form
never accumulates scored predictions and can never flip its policy. The
verdict line (`- **Affected tests:** pass (14 units, est 41 s) — log …`) goes
into the plan's Final Implementation Notes and never into the gate ledger: no
double record, no `record_gates` guard needed.

### Gates

```yaml
  testmap_fresh:
    type: machine
    kind: procedure
    description: "Coverage annotations on this task's changed sources reviewed, re-stamped, and touched test files' seeds adopted or rejected"
    blocks_dependents: false
    verifier: aitask-gate-testmap-fresh
  testmap_check:
    type: machine
    description: "Test map consistent: rotted paths fail; structural rot and unmapped sources fail under --strict past bootstrap"
    blocks_dependents: false
    verifier: aitask-gate-testmap-check
    max_retries: 0
    timeout_seconds: 120
    unlocks: [tests_pass]
  # tests_pass: unchanged in the reference. In an onboarded project test_command is `./ait test`,
  # gate_command_exit_contract lists test_command, and gates.yaml carries timeout_seconds from `costs --gate-timeout`.
```

`testmap_run` is retired as a gate name. Every property it had has a home:
its verifier logic is `ait test --gate`; `blocks_dependents` and
`max_retries: 1` are `tests_pass`'s own; its 1800 s timeout becomes a
per-project `tests_pass.timeout_seconds` from the ledger; its exit mapping
(0/1/2/75/64 → 0/1/2/3/3) is the shared lib's new rows; `testmap_check`
unlocks `tests_pass`; `--include-stale` is applied by the composite; deferred
rows run under `completion.deferred: run`. An `unlocks:` target absent from a
task's active set is ignored, so `testmap_check` declared alone is linear as
before, and a project whose completion invariant is a full suite keeps
`tests_pass` exactly as today with `completion.mode: full`. `run_gate_admission`
and `readiness` (n006) gate the **policy flip** rather than a second gate's
declaration; the engine never enables a gate and never writes a profile.

### Completion policy

```
ait gates run 1234 → testmap_check → pass → unlocks tests_pass
   → aitask_gate_tests_pass.sh → run_command_gate → export AIT_GATE_TASK_ID=1234 AIT_GATE_RUN_ID=<run> → `./ait test`
      MODE:completion  POLICY:full                       → run --all (subsumed_by honoured) → exit 0/1/2/3/75
      MODE:completion  POLICY:selected                   → readiness: all met → task selection, deferred rows RUN
      MODE:completion  POLICY:selected → POLICY_DEMOTED:selected->full|max_false_negatives → run --all
   → run_project_command_key: 0 pass · 1 fail · 2 skip · 3 error(command_errored) · 75 error(command_refused)   [opted-in key]
   → ledger block result="MODE:full|720 units|policy:full" → orchestrator: pass / fail / skip / error (retry within max_retries)
   → after any full run: PREDICTION_SCORED:<r1>|<run> PREDICTION_FALSE_NEGATIVES:<n> → costs/predictions.yaml → readiness input
```

The flip is human (`/aitask-testmap-onboard --policy selected` after
`ADMISSIBLE`, `approved_by` recorded); the demotion is automatic and loud; the
policy can only fail toward running more. thinking_app's rule — full
`verify-active` as the completion gate until admissible (t388) — is preserved
exactly by `completion.mode: full`.

### Verification of the seam itself

`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine replaying scripted exits, in all
three modes and every `REASON:` (n007's helper cases folded in);
`tests/test_gate_verifiers.sh` covers 75 and the env export;
`tests/test_agent_instructions.sh` T40; `tests/test_testmap_onboard_ledger.sh`
(resume from each phase, idempotent re-run, `--no-task`, one task per level
with `depends:`); engine tests per detector, per seed origin on fixture repos
with synthetic `(t<id>)` histories, the fan-in reclassification, golden files
for block placement per language, every `ADOPT_*` refusal branch; the
task-workflow and onboarding goldens; `tests/test_touchpoint_count_contract.sh`;
`tests/test_install_engine_binary.sh` for each `TESTMAP:` state.
<!-- /section: workflow_seam -->

<!-- section: data_flow [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_completion_policy, component_workflow_integration, component_workflow_seam, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_registry_loader, component_staleness_tool, component_engine_packaging] -->
## Data Flow

### Onboarding level 0: existing tests → registry → first anchored run

```
repository (tests, scripts, build files, project_config.yaml, code_areas.yaml, git history)
   ▼  onboard detect [--write]        FRAMEWORK: / AGGREGATE_RUNNER: / SERIAL_LIST: / RESOURCE_HINT: / SUITE_CANDIDATE: / UNIVERSE: / UNLISTED: / RUNNER_SCRIPT_NEEDED:
   │                                  --write → aitestmap/{config,runners,resources}.yaml · registry/areas.yaml   (runner table confirmed per runner)
   ▼  onboard inventory               scan + every runner list + check → _scanned.yaml · UNREGISTERED: resolved (bind | exclude:)
   ▼  onboard seed [--apply] [--json --out]   deps facts (invocation, imports, package) + conventions + git log (t<id>) + plans + prose [+ coverage]
   │                                  → SEED:<test>|<source>|<origins>|<confidence> · SEED_HELPER: · SEED_READS: · SEED_KIND: · SEED_BATCH_NO: · SEED_MEMBER: · SEED_AXIS:
   │                                  --apply → registry/seeded.yaml ;  --json --out → .aitask-testmap/onboard/<run>/seed.json (attached to the task)
   ▼  check / explain --sources       UNMAPPED_SOURCE clusters → rules for hot directories · expiring waivers (+90d) · leave unmapped   (waivers phase)
   ▼  enable (skill)                  test_command: ./ait test (previous value → full: true suite runner with fallback_command:) · gate_command_exit_contract += test_command
   │                                  profiles default_gates += tests_pass, testmap_check, testmap_fresh · docs: · notes: · hand-maintained CLAUDE.md paragraph
   ▼  task-workflow Step 8            annotation diff reviewed (none at level 0); testmap_fresh: nothing STALE
   ▼  task-workflow Step 9            ./ait gates run → testmap_check (non-strict) → tests_pass → ./ait test --gate
   │                                  MODE:completion POLICY:full → run --all → ledger rows → last_pass per unit · costs --update · PREDICTION_SCORED:none
   ▼  after the run                   costs --gate-timeout tests_pass → gates.yaml tests_pass.timeout_seconds (ait: commit) · readiness → LEVEL:0 NEXT:adopt
   ▼  every phase                     onboard.yaml row · chore: Onboard testmap — <phase> (t<id>) commit, paths named
```

### Level 1: seeds → stamped edges

```
onboard adopt --class static:invocation --accept-min 0.85 [--scope <glob>]   (attended: accept all | review a sample of ten | skip)
   → rewriter: testmap:covers <src> @<date>/<blob10> at the fixed position → WROTE:<file> · registry/adopted.yaml rows · rows leave seeded.yaml
   → ADOPT_REFUSED:dirty-foreign · ADOPT_SKIP:duplicate|unregistered|no-leader · ADOPT_SUMMARY:1|<edges>|<files>|<skipped>
onboard adopt --area <a> --batch 50        (per row, evidence beside each: file pair, file:line, task ids, coverage run) → stamp, no provenance row
onboard reject <test> <source> --reason    → onboard.yaml rejections[]; never re-proposed
Step 8 testmap_fresh, any later task       → seeds on this task's touched test files: adopt / reject / leave per row → rides the (t<id>) commit
human re-stamp (verify · stale --confirm-source · annotate) → adopted.yaml row deleted → REVIEWED
```

### A task, steady state

```
Step 7  edit source ──▶ ./ait test                      MODE:interactive TASK:<id> (branch | lock) INTAKE:change-surface
                        change surface ──▶ test composite ──▶ select (edges ∪ adopted ∪ seeds ∪ deps ∪ rules ∪ axes ∪ test-dep) --include-stale
                        ──▶ schedule ──▶ run ──▶ ledger rows (run_id test-…) ──▶ SELECTED: / UNMAPPED_SOURCE: / UNANNOTATED_TEST: / RESULT:
        before Step 8 ──▶ ./ait test --advisory --task <id> ──▶ VERDICT:/REASON:/LOG: ──▶ prediction.json for this task ──▶ plan Final Implementation Notes
                        UNMAPPED_SOURCE ──offer──▶ annotate | attribute --propose (→ seeded.yaml, origin observed) | continue
Step 8  procedure gates ──▶ testmap_fresh ──▶ stale --task (n006: STALE / EVIDENCED / UNSTAMPED, adopted(...) shown) + adopt seeds on touched test files
Step 9  ait gates run ──▶ testmap_check (SEEDED:, ADOPTED:, UNMAPPED_SOURCE:, strict past bootstrap) ──▶ tests_pass = ./ait test --gate (policy)
        full run ──▶ automatic score against the newest prediction ──▶ PREDICTION_MISSED:<id> ──▶ attribute (decide | --propose → seeded.yaml)
```

### Policy flip

```
/aitask-testmap-onboard --policy selected
   → readiness → READINESS:min_scored_full_runs|met|34  READINESS:max_false_negatives|met|0  READINESS:require_opaque_proofs|met  READINESS:approved_by|unmet|-
               → LEVEL:2 NEXT:scaffold  ADOPTED_UNREVIEWED:618|0.61  SEEDED:412  POLICY:full|would run selected: 14 units
   → AskUserQuestion: record approval {who, statement} → config.yaml completion.mode: selected, run_gate_admission.approved_by → ait: commit
   → the next tests_pass runs the selection; any later unmet criterion demotes it loudly
```

### Reading the map without running anything

```
ait test --howto ──▶ registry + ledger + config.yaml docs:/notes: + onboard.yaml ──▶ TESTMAP:/RUNNER:/FULL_GATE:/GATE:/VERBS:/AXES:/RESOURCE:/NEW_TEST:/DOCS:/NOTES:
aitask-qa 3a ──▶ ait testmap explain --sources <changed> --format table ──▶ Covered | Covered (adopted) | Covered (seeded) | GAP
ait setup ──▶ report_testmap_state() ──▶ TESTMAP:<state>
onboard status ──▶ phases · ONBOARD_NEXT: · seed queue per origin · adopted unreviewed · ratios · oldest pending
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n006)* means carried as n006 specified it, which is itself
the resolution of n001 and n002; *(merged from n007 and n008)* names what
each contributed; *(new: introduced to bridge n007 and n008)* is a component
neither parent had in that form.

<!-- section: component_adoption_ledger [dimensions: component_registry_loader, component_seeder, component_onboarding_engine_verbs] -->
### Adoption ledger: seeded → adopted → reviewed *(new: introduced to bridge n007 and n008)*

The three-file state of a machine-proposed edge and the rules that move it:
`registry/seeded.yaml` (n007's queue: select-only, no stamp, invisible to
`stale`, never `--strict`), `registry/adopted.yaml` (n008's provenance: a
stamped edge accepted by class, shown as `adopted(...)`, counted as
`ADOPTED_UNREVIEWED`, cleared by a human re-stamp) and `onboard.yaml`'s
`rejections[]`. Transitions: `onboard seed` / `attribute --propose` → seeded;
`onboard adopt --class` → adopted; `onboard adopt <row>` / the `testmap_fresh`
in-gate step → reviewed; `verify` / `stale --confirm*` / `annotate` → reviewed;
`onboard reject` → rejected. Load rule: a seed shadowed by any stamped edge is
dropped with `SEED_SHADOWED`. Autonomous profiles may seed, and may adopt only
origins at confidence 1.0. Its tradeoffs are recorded under
`tradeoff_two_edge_states_during_adoption` (three provenances a reader must
keep apart) and `tradeoff_seed_precision` (an adopted edge is still a machine
claim in a human annotation's clothes).
<!-- /section: component_adoption_ledger -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(merged from n007 and n008)*

`internal/seed`, verb `onboard seed [--from static,convention,cochange,plan,prose,coverage]
[--min-cochange 2] [--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json --out <f>]`:
the origin table above — `static:{package,invocation,import}` from
`internal/deps` facts for the test file only (direct, never the closure),
`convention` from `config.yaml conventions:` (seeded by `detect` per runner),
`cochange` from one `git log --name-status -M --format=%H%x00%s` pass over
`(t<id>)` commits (pairs counted per distinct task, `--min-cochange 2`,
per-commit grouping fallback, cached by HEAD sha, `SEED_HISTORY:shallow|<n>`),
`plan` through the explain cache, `prose` from header comments and `# Covers:`
lines, `coverage` opt-in (coverage.py contexts, `go -coverprofile` per unit,
LCOV with a test column, plugin `{test, covers}` lines). Confidence table
1.0 / 0.95 / 0.90 / 0.85 / 0.70 / 0.60 / 0.50 / 0.30 / 0.20+0.20n ≤ 0.60,
noisy-OR, ordering only. Helpers separated first (roots + fan-in) with
`SEED_HELPER:` and `SEED_READS:` lines; `SEED_KIND:`, `SEED_BATCH_NO:`,
`SEED_MEMBER:`, `SEED_AXIS:` from `onboard classify`'s signals. Output
`SEED:<test>|<source>|<origins>|<confidence>`; `--apply` writes
`registry/seeded.yaml` deterministically sorted; rejected pairs never
re-proposed; shadowed pairs dropped. Budget: static + convention < 2 s,
cochange < 5 s over 600 commits on the aitasks shape. Fixtures: a synthetic
repo per origin with a `(t<id>)` history.
<!-- /section: component_seeder -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs *(merged from n007 and n008)*

`internal/onboard` behind `onboard detect [--write] | inventory | seed |
classify [--apply] | adopt | reject | scaffold | status | finish` and the
`onboard.yaml` phase ledger. `detect`: the closed detector list with an
evidence field per row (`bash-file`, `pytest`, `go-test`, `gradle-class`,
`kmp-sourceset`, `suite-from-config`), `UNIVERSE:`, `UNLISTED:`,
`AGGREGATE_RUNNER:`, `SERIAL_LIST:`, `RESOURCE_HINT:`, `SUITE_CANDIDATE:`,
`RUNNER_SCRIPT_NEEDED:`; `--write` emits the level-0 files and `conventions:`;
re-running on an existing table prints `DETECT_DIFF:` and writes nothing
without `--force`. `inventory`: `scan` + every `list` + `check`, `UNREGISTERED:`
as the to-do list. `classify`: n006's `classify --suggest` plus the three
onboarding signals; `--apply` writes the level-2 lines and `needs:` bindings
for confirmed rows. `adopt`: `--class <origin> [--accept-min] [--scope <glob>]
[--dry-run]` (bulk, provenance row) or `<test> [<source>]` / `--area <a>
--batch <n>` / `--files-from -` (per row, reviewed); writes through the
rewriter; `ADOPT_REFUSED` / `ADOPT_SKIP` / `WROTE` / `ADOPT_SUMMARY`.
`reject <test> <source> --reason`. `scaffold --axes | --runner <builtin> --as
<name> | --members` (level 3). `status`: phase rows, `ONBOARD_NEXT:`, seed
queue per origin, `ADOPTED_UNREVIEWED`, ratios, oldest pending seed. `finish`:
requires status green; flips `require_stamp` and `--strict`; records the
phase. The engine reads `onboard.yaml`'s `task:` and `level:` and writes
phase rows; task creation, profile edits, `project_config.yaml`, `gates.yaml`,
`CLAUDE.md` and commits are the skill's, through the framework's own scripts.
Go tests on fixture repositories in `t.TempDir()`: one per detector and per
detect shape (bash-only, pytest, go, gradle, gradle-per-source-set), the
fan-in reclassification, golden files for block placement per language,
every refusal branch, resume from each phase.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(merged from n007 and n008)*

Profile-aware stub + `SKILL.md.j2` (resolver key `onboard`) with one
procedure file per phase (`detect.md`, `inventory.md`, `seed.md`,
`waivers.md`, `enable.md`, `full-run.md`, `adopt.md`, `classify.md`,
`scaffold.md`, `finish.md`), Claude Code first, Codex and OpenCode ports as
follow-up tasks; rendered goldens under
`tests/golden/skills/aitask-testmap-onboard/`. Flow: preconditions → read-only
survey and level proposal → one aitask per level created with the seed dump
attached and claimed → task-workflow (phases at Step 7 with per-phase
commits, the diff at Step 8, the first full run at Step 9) → timeout from the
ledger, `readiness`, the next level's task with `depends:`. Confirmations:
per runner, per evidence class (accept all / review a sample of ten / skip),
per kind change individually, `UNLISTED` files (bind / not a test / later),
the config table once (`test_command` → `./ait test` with the previous value
moved to a `full: true` suite runner; `verify_build` left alone unless the
user names it as the suite — thinking_backend; `gate_command_exit_contract`
+= `test_command`; profiles `default_gates` += `tests_pass`, `testmap_check`,
`testmap_fresh`; `bootstrap_until`; `docs:` and `notes:`; a hand-maintained
`CLAUDE.md` Testing paragraph). Re-entry at `ONBOARD_NEXT:`; every phase
idempotent; `--no-task`; `--policy selected` re-entry writes the flip only on
`ADMISSIBLE` with `approved_by`. Headless: level 0 + `static:package`
adoption only, no prompts, no kinds, no policy flip.
<!-- /section: component_onboarding_skill -->

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(merged from n007 and n008)*

`.aitask-scripts/aitask_test.sh`, a ~150-line bash front over the n006 shim:
resolves `MODE` (completion iff `--gate` or `$AIT_GATE_TASK_ID`; advisory iff
`--advisory`; else interactive), `TASK` (`--task` > `$AIT_GATE_TASK_ID` >
`aitask/<task_name>` branch > single own lock via `aitask_lock.sh --list-mine`
> `NO_TASK`), `INTAKE` (change surface piped; `--dirty`; `--all`; named
paths, a source path as a one-file `TASK:` set) and `POLICY` (completion:
`config.yaml completion.mode` re-checked against `readiness`); calls the
engine `test` composite; falls back to `aitask_run_project_command.sh
test_command` when `aitestmap/` is absent and to the suite runner's
`fallback_command` when the engine is absent and the policy allows; in
`--advisory` mode (n007's `aitask_affected_tests.sh` folded in) prints
`VERDICT:/REASON:/DETAIL:/LOG:/SELECTED:/UNMAPPED_SOURCE:/UNKNOWN:`, exits
`0/1/2/3` on `aitask_run_project_command.sh`'s contract, maps every absence
and a post-deadline refusal to a skip reason, writes the log under
`.aitask-gates/<task>/affected_<run-id>.log` and appends nothing to any
ledger; prints `MODE / TASK / INTAKE / POLICY / SELECTED / RUN / RESULT`,
`UNANNOTATED_TEST` + `HINT`, `UNMAPPED_SOURCE`; exits `0 / 1 / 2 / 3 / 75 /
64`; dispatcher arm `test)`; five permission touchpoints;
`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine in all three modes.
<!-- /section: component_test_entrypoint -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Engine `test` composite *(inherited from n007; brief split out)*

The engine side of the front: `test --task <id> --changes - | --paths <p>... |
--all [--explain] [--budget-s] [--format lines|json|tokens] [--run <id>]`
runs `select --include-stale` → `schedule` → `run` in one process and prints
`SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`, `UNMAPPED_SOURCE:<path>`
lines, the ranked rows, waves, results per id and `RESULT:pass|fail|skip|deferred|<run_id>`
before the front adds its own lines; `--all` is `run --all` (anchors evidence,
scores the newest prediction, honours `subsumed_by`); `--explain` stops after
`select`. It never resolves a task, reads a profile or touches a gate ledger —
those are the bash front's.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief *(merged from n007 and n008)*

`internal/brief`, verb `brief [--md]`, surfaced as `ait test --howto [--md]`
and `ait testmap brief`: `TESTMAP:<state>|LEVEL:|POLICY:|seeds pending|adopted
unreviewed`, `RUNNER:` per runner (name, kind, unit count from `list`,
invocation shape, resources, `subsumes`), `FULL_GATE:` (the `full` runner, its
p95, `= test_command`, the `tests_pass` timeout), `GATE:` (the gate chain and
what `--gate` would run now), `VERBS:`, `AXES:`, `RESOURCE:` with refusal
semantics, `NEW_TEST:`, `DOCS:` per `config.yaml docs:`, `NOTES:` verbatim,
`ONBOARD_NEXT:` while a ledger is unfinished; before onboarding
`TESTMAP_ABSENT` plus the `test_command`; < 100 ms warm.
<!-- /section: component_agent_brief -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(merged from n007 and n008)*

The `## Running Tests` section above in `seed/aitasks_agent_instructions.seed.md`,
installed by `assemble_aitasks_instructions()` into `CLAUDE.md`'s `>>>aitasks`
block, `AGENTS.md`, `.codex/instructions.md` and the OpenCode mirror on every
`ait setup` and `ait upgrade`; fourteen lines, no agent named, no project
specifics; `tests/test_agent_instructions.sh` T40 pins the heading in all four
surfaces through a real `install.sh --dir`; the hand-maintained `CLAUDE.md`
case is the level-0 task's edit.
<!-- /section: component_agent_instructions -->

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(inherited from n008)*

`aitestmap/config.yaml completion: {mode, deferred, on_empty_selection,
engine_absent}`; `mode: selected` written only by the skill's `--policy`
re-entry after `ADMISSIBLE` with `approved_by`; `ait test --gate` re-checks
`readiness` on every completion run and demotes loudly (`POLICY_DEMOTED:`);
the flip is human, the demotion automatic, so the policy fails only toward
running more; `readiness` prints `POLICY:<mode>|<what --gate would run now>`.
<!-- /section: component_completion_policy -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam — the data edits *(inherited from n008)*

The Step-7 test-loop paragraph, the `build-verification.md` branch, the two
rows and two exports in `run_project_command_key()`, `--task-id`'s export in
`aitask_run_project_command.sh`, `gates_reference.yaml` entries (no
`testmap_run`), profiles' `default_gates`, the `test)` dispatcher arm, the
extension-points sections, the extended `tests/test_gate_verifiers.sh`,
`tests/test_serial_carveout_doc_drift.sh` per n006, regenerated goldens;
`tests/test_no_unscoped_task_commit.sh` unaffected because the skill commits
through `aitask_task_commit.sh`.
<!-- /section: component_workflow_seam -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration — the procedure edits *(inherited from n007; helper folded into the entrypoint)*

`task-workflow/affected-tests.md` called once before Step 8 behind
`affected_tests: run|show|off` (`run` default; `show` → `--explain`; `off`
renders it away); the branch table; the verdict in the plan's Final
Implementation Notes, never in the gate ledger. `aitask-gate-testmap-fresh`
gains the adopt-on-touched-files step. `aitask-qa` `test-discovery.md`
registry-first with `explain --sources … --format table`, `test-execution.md`
4a–4d. `profiles.md` row; `remote.yaml: affected_tests: run`. `ait setup`
prints `TESTMAP:`. pickrem / pickweb inherit and see a printed skip on Web.
Goldens regenerated for every profile × agent; `aitask_skill_verify.sh` run.
<!-- /section: component_workflow_integration -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(merged from n007 and n008)*

`test-discovery.md` 3a–3c map the changed sources through `ait testmap
explain --sources <paths> --format table` when `aitestmap/` exists (`Covered`,
`Covered (adopted)`, `Covered (seeded)`, `GAP` = no edge and no test-dep),
falling back to the naming-convention scan otherwise; `test-execution.md` 4a
runs the configured `./ait test` through `aitask_run_project_command.sh
test_command --task-id <id>`, 4b runs named units through `ait test <path>`,
4c gains the `REFUSED (host resources)` row treated as `SKIP` in the health
score, 4d scores coverage from registry edges with seeded rows counted as
coverage that exists (QA measures whether a test exists, not whether its
claim is fresh).
<!-- /section: component_qa_integration -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(merged from n007 and n008; n001/n002's three-gate shape replaced)*

`testmap_fresh` (procedure; the in-gate adopt step added) and `testmap_check`
(machine, `max_retries 0`, `timeout 120`, `unlocks: [tests_pass]`) in
`gates_reference.yaml` synced to `gates.yaml`; the completion test gate is the
existing `tests_pass` with `test_command: ./ait test` and
`gate_command_exit_contract: [test_command]`; `testmap_run` retired as a name;
`aitask_gate_testmap_run.sh` not written; `aitask_gate_testmap_check.sh` stays
and reports `SEEDED:<n>`, `ADOPTED:<n>` (informational) and
`UNMAPPED_SOURCE:<path>` (fails under `--strict` past `bootstrap_until`);
`run_gate_admission` and `readiness` gate the policy flip; gates are enabled by
the onboarding `enable` phase with confirmation, never by hand and never by
`ait setup`.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(merged from n007 and n008)*

`aitask-testmap` (n006's obligations; opens with `ait test --howto`; hands an
un-onboarded repo to `aitask-testmap-onboard`); `aitask-gate-testmap-fresh`
(n006's procedure gate plus the adopt / reject / leave step for seeds on the
task's touched test files; an `adopted(...)` row is confirmed knowing it is a
class-accepted claim); `aitask-testmap-onboard` (new, above). Every skill's
runtime knowledge of how to run tests is the seeded block plus `--howto`,
never prose in a `SKILL.md`. Claude Code first; wrapper surfaces regenerated
by `aitask_audit_wrappers.sh apply-wrapper`; Codex and OpenCode ports as
separate tasks.
<!-- /section: component_skill -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(inherited from n006; three packages added)*

`engine/cmd/ait-testmap` with n006's `internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}`
plus `internal/seed`, `internal/onboard`, `internal/brief`; Go 1.26 with a
pinned toolchain, `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w
-X version/commit/contract"`; deps `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
`golang.org/x/sync` only; stdlib `flag` verb table, `syscall.Flock`, `os/exec`
git; line-protocol stdout, `--json`, per-verb exit contracts; never writes
`aitasks/`, `aiplans/`, `.aitask-data/`, a gate ledger, `project_config.yaml`,
`gates.yaml`, profiles or `CLAUDE.md`; never invokes `aitask_*.sh`; never
needs its own install root. Fixture repos in `t.TempDir()` gain synthetic
`(t<id>)` histories and one fixture per detect shape.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(inherited from n006; verbs and budgets added)*

Version / commit / contract embedding, `version --json` printing `ENGINE:<path>`,
`CONTRACT_MISMATCH`, the `go test -bench` budgets with the 2× rule, pools
capped at 8; verb table extended by `test`, `brief`, `onboard {detect,
inventory, seed, classify, adopt, reject, scaffold, status, finish}` and
`costs --gate-timeout`; budgets added: `brief` < 100 ms warm, `onboard seed`
static + convention < 2 s and cochange < 5 s over 600 commits on the aitasks
shape, `onboard status` < 200 ms; `detect` is excluded from the latency table
(once per onboarding, not on any gate path). Contract stays 1; `seeded.yaml`,
`adopted.yaml` and `onboard.yaml` carry `contract:` and a newer one is refused
the same way.
<!-- /section: component_engine_binary -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade, regeneration *(inherited from n006; `report_testmap_state()` added)*

`install_engine_binary()` reached by `ait setup` and `ait upgrade` (through
`install.sh`'s `--source-only` path); source order `--local-engine` >
exact-version release asset > `--engine-from-source` > `ENGINE_MISSING`
warning; checksum; atomic install to `$AITASKS_HOME/engine/v<V>/`; `version
--json` self-check; `.dev` marker; `--no-testmap` / `AIT_TESTMAP_FETCH=0`;
`HOME_LEGACY:` hint; `.aitask-testmap/` gitignored by setup;
`aitask_engine.sh build|test|cross|prune|home [--migrate]`. After it,
`report_testmap_state()` prints `TESTMAP:engine-missing|absent|bootstrapping|<next>|onboarded`
with the onboarding hint on `absent`; the re-inserted instructions block
carries the Running Tests section. `aitask_test.sh` is a framework script
shipped in the tarball like every `aitask_*.sh`; nothing to install.
`tests/test_install_engine_binary.sh` through a real `install.sh --dir`
asserts the path and each `TESTMAP:` state.
<!-- /section: component_engine_packaging -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n006)*

`engine/build.sh` as the single build and matrix command; the release
`engine` job (`setup-go` from `engine/go.mod`, `go vet`, `go test`, `build.sh
all`) producing `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
`ait-testmap_<V>_SHA256SUMS.txt`, attached by both `action-gh-release` steps
with `release needs: [plan, engine]`; the unchanged VERSION-matches-tag guard;
`engine-check.yml` on push / PR for `engine/**`; `lib/platform_detect.sh`; the
shim's strict handshake; `test_testmap_shim.sh`, `test_platform_detect.sh`,
`test_aitasks_home.sh`; `aidocs/framework/go_engine.md`; `release-packaging.yml`
and nfpm `arch: all` untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n006)*

`lib/aitasks_home.sh` exporting `AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`
and `aitasks_engine_dir`; no fallback to `~/.aitask/`; sourced by the shim,
`install_engine_binary`, `aitask_engine.sh`, the verifiers and now
`aitask_test.sh`; `ait setup` prints `AITASKS_HOME:<path>`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(inherited from n006)*

`ait engine home [--migrate]` with the known set including `pypy_venv`; `ait
setup` hints, does not migrate; the default flip is a named follow-up
admitted after `tests/test_aitasks_home.sh` through a real `install.sh --dir`.
<!-- /section: component_framework_home -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(merged from n007 and n008)*

n006's six tables (edges, scopes, areas, rules, waivers, axes), id grammar
`<path>[#<member>][@<variant>]`, `owns:` routing, deterministic writes and
check rules unchanged; two tables added: `seeds` from `registry/seeded.yaml`
(rows `{test[#member], covers, origin[], confidence, evidence{}, proposed_at}`)
and `adopted` from `registry/adopted.yaml` (rows `{test, source, origin[],
confidence, adopted_at, task}`); a seed whose `(test, covers)` also exists as a
stamped edge is dropped at load with `SEED_SHADOWED`; an adopted row whose
edge no longer carries a stamp is `ADOPTED_ORPHAN` (check); write routing
gains `onboard seed → seeded.yaml`, `onboard adopt → seeded.yaml (row removed)
+ adopted.yaml (class only) + the test file`, `onboard reject → seeded.yaml +
onboard.yaml`, `attribute --propose → seeded.yaml`; `config.yaml` gains
`completion:`, `conventions:`, `helper_roots:`, `helper_fanin:`, `exclude:`,
`docs:`, `notes:`, `broad_threshold_s`; golden tests pin the two new merges and
the shadow rule.
<!-- /section: component_registry_loader -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n006)*

`axes.yaml`, `<unit>@<variant>`, the facet join, `testmap:axis`, `--axis`;
unchanged. Level-3 `onboard scaffold --axes` writes only the skeleton the
maintainer fills; the grid heuristic proposes, a person declares.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n006)*

`axes --list | --check | --explain <path>`; unchanged.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n006)*

The runner's `list` is the universe; `variants:` persisted by `scan --apply`;
`UNCOVERED_VALUE`, `UNMAPPED_ARTIFACT`. `onboard detect`'s `UNIVERSE:` is the
same count taken before runners exist; `onboard inventory` is the first
consumer of `UNREGISTERED:` rows as a to-do list.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(inherited from n006; adopt as a caller)*

Grammar v3 (`testmap:unit` blocks; kind / covers / area / scope / trigger /
reads / axis / reviewed / runner / needs / batch; per comment leader and
Python module docstrings read; unknown keys refused with a line number), the
line-targeted rewriter with `REWRITE_CONFLICT`, `annotate --from-body`
unchanged. `onboard adopt` is a new caller writing `testmap:covers` lines at
the fixed per-language position (comments only, never into a docstring, inside
the member's `testmap:unit` block for a member seed), each stamped
`@<date>/<blob10>` at adopt time. `# Covers:` prose headers are shown beside
seeds as reviewer context and read by the `prose` origin at 0.30, never
matched by the annotation scanner.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(inherited from n006; facts shared with the seeder)*

bash / python / go / kotlin (opaque contract) / Gradle scanners, plugins, the
opt-in `android-res` symbol scanner, the XDG blob-keyed cache — unchanged.
The bash scanner's literal-invocation facts, the python / kotlin scanners'
direct main-root imports and the go scanner's package membership are exposed
to `internal/seed` as `static:{invocation,import,package}` — same scan, same
cache, read once; the deeper closure stays the selector's d2 walk and is never
seeded as an edge.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(inherited from n006; seeded edges, `explain --sources`, summary lines)*

Intake, the graded walk, variant expansion and axis join, test-dep, `ESCALATE`,
scoped join, ranking, invocation groups, stale marks, `--include-stale`, the
suite budget, cut knobs, formats, prediction record, explain — unchanged. A
seeded edge is walked like an annotation edge at d1 with reason
`edge(seeded:<origins>)` and never contributes a stale mark; an adopted edge
is an annotation edge whose reason carries `adopted(<origins> <confidence>)`;
`explain --sources <path>... --format table` prints the reverse view for
`aitask-qa`; the `test` composite prints `SELECTED:` and `UNMAPPED_SOURCE:`
ahead of the rows; `ait test <source path>` reaches it as a one-row `TASK:`
change set.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(merged from n007 and n008)*

n006's `describe` / `list` / `run` contract, TSV list with member and variant
ids, `results.jsonl` with child rows, `runner.json` overhead, bindings,
`builtin:` with `command:`/`cwd:` and shadow-by-name, batching, timeouts,
reconciliation, exit contract `0/1/2/75/64` — unchanged. Repository keys
added: `subsumed_by: <suite>` (so `run --all` executes a `full: true` suite
once and never its subsumed runners beside it) and `fallback_command:` on a
suite runner (what completion runs when the engine is absent and
`completion.engine_absent` is `fallback_command`); `onboard scaffold --runner
<builtin> --as <name>` writes a project script whose `describe` / `run`
delegate to the builtin and whose `list` prints `SCAFFOLD_TODO` until filled.
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(merged from n007 and n008)*

n006's builtins (bash-file, pytest with junitxml and the serial carve-out
pinned, go-test, gradle-class with JUnit inversion and the zero-match trap,
suite with `children:` post-processor, device with the allocator handle;
`engine-test` over `engine/`) and thinking_app's project runner unchanged;
`onboard detect` seeds the repository — bash-file for `tests/**/test_*.sh`,
pytest for `test_*.py` / `*_test.py` with an aggregate runner's serial list
becoming `testmap:batch no` candidates, go-test per package from `go list`,
gradle-class for `src/test/**/*.kt|java`, the `kmp-sourceset` mapping
(`commonTest` / `androidHostTest` → gradle-class unit runners on
`:<module>:jvmTest` / `testDebugUnitTest`, `androidDeviceTest` → `device` on
`connectedDebugAndroidTest` with `needs: [emulator]`), and a `full: true`
suite runner named `full` wrapping `test_command` (or `verify_build` only when
the user names it as the suite) whose `children:` post-processor is a builtin
inverting pytest junitxml, bash-file names from the per-file exit and `go test
-json` events to registered ids, and whose `fallback_command:` is the previous
`test_command`; `bash-file list --invocations` prints the literal paths a test
references for the seeder.
<!-- /section: component_reference_runners -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n006)*

Kinds, scopes, `flock(2)` slots, admission deferral, allocators, waves,
`broad_after_unit`, admission-holding invocations ordered last, `concurrency:
serial|parallel` — unchanged. `detect`'s `RESOURCE_HINT` rows become
`resources.yaml` entries the scheduler already understands (aitasks:
`repo-git-index` mutex, worktree scope); an `ait test` run on thinking_app is
one Gradle invocation under the heavy-run slot, and a refusal at the deadline
is exit 75 (advisory: `skip:admission_refused`).
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(merged from n007 and n008)*

n006's Welford / P² / invocation-group ledger, `costs --update`, `last_pass`
and flake per id, group costing, `costs/predictions.yaml` — unchanged. Run ids
are prefixed `test-` (interactive and advisory), `gate-` (completion) and
`full-` (`--all`) so ordinary rows say which surface produced them; all three
feed cost and evidence exactly like gate runs; the `SELECTED:` estimate is the
same per-group sum the budget uses; `costs --gate-timeout tests_pass` prints
`GATE_TIMEOUT_SUGGESTED:<gate>|max(600, 3 × p95 of the newest full run on this
host class)`, which onboarding writes into the project's `gates.yaml` after the
first measured full run.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n006)*

Per reached variant; `EVIDENCED` only when every variant is anchored; never
rewrites; `--confirm-evidenced` the only bulk autonomous confirmation. Seeded
edges are not joined (no stamp to heal); adopted edges are joined like any
stamped edge; the level-0 task's first full run is what first populates the
anchors it reads.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(merged from n007 and n008)*

`score` automatic after `run --all` and after a `full: true` suite run;
`attribute` (missing-edge / test-wrong / source-wrong, missing-axis-source
widen-only, missing-trigger / area-too-narrow) gains `--propose` (default in
autonomous profiles) writing the row to `seeded.yaml` with origin `observed`
and the run id as evidence instead of to `observed.yaml`, so autonomous runs
grow the review queue and never the accepted map; `readiness` additionally
prints `LEVEL:<0-3>`, `NEXT:`, `ADOPTED_UNREVIEWED:<n>|<ratio>`, `SEEDED:<n>`
and `POLICY:<completion.mode>|<what ait test --gate would run now>`; it still
enables nothing.
<!-- /section: component_feedback_tools -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(inherited from n006; one stamp writer, one gate step)*

Per-edge `@<date>/<blob10>` stamps written only by `verify`, `annotate`,
`stale --confirm*` and now `onboard adopt`; member-block scoping; variants
carry no stamp; `last_pass` per id; `bootstrap_until`, `require_stamp`,
`flake_threshold`; the `testmap_fresh` procedure gate dispatched before the
change summary so rewrites ride the `(t<id>)` commit, gaining the step that
offers to adopt the seeds of the test files this task touched; not a git hook
and not a code-agent hook. An adopted stamp is a stamp like any other and the
procedure gate handles it identically, with the `adopted(...)` display as
context.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(merged from n007 and n008)*

n006's `stale --task --changes - | --all` line classes, `%25`/`%7C` encoding,
unevidenced variants on `STALE` rows, `CHECK_STRUCTURAL:<n>`, `--strict` on
`STALE_PATH`, rename hints, `--confirm`, `--confirm-source`,
`--confirm-evidenced`, `--retarget` — unchanged. Seeded edges are excluded
from every class; `stale --all` adds `SEEDED:<n>` and `ADOPTED:<n>` summary
lines; a `STALE` or `EVIDENCED` row whose edge has an `adopted.yaml` row
carries `adopted(<origins> <confidence>)` in its `DISPLAY` line so the
procedure gate knows it is confirming a class-accepted claim.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(inherited from n006; classify signals added)*

`areas.yaml` seedable via `areas --import-codemap`, `_scoped.yaml` rows with
`reads_from`, `owns:` by area, the d1 join, the suite budget with `DEFERRED`,
`DEAD_SCOPE` and `KIND_MISMATCH|CONVERT_TO_SUITE`, missing-trigger /
area-too-narrow — unchanged; `classify --suggest` gains the three onboarding
signals (recorded p95 above `broad_threshold_s`, a source-set or directory
convention, a resource named in the file) printed as the reason on each
`CLASSIFY:` line, and `onboard classify --apply` writes the confirmed rows'
source lines at level 2.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n006)*

`broad_after_unit`, `device_policy`, `STALE_AREA`, opt-in `REVIEW_DUE`,
attribute widening, fixture pins, `full: true` suite rows with child rows —
unchanged; `completion.deferred: run` means the suite budget applies to the
interactive loop only.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

**Inherited unchanged from n006** (full text in the node metadata; each
originates in n001 or n002 and was made precise in n003–n006):
`assumption_areas_express_suite_blast_radius`, `assumption_axis_membership_declarable`,
`assumption_axis_sources_declarable`, `assumption_batch_per_unit_timing_reportable`,
`assumption_blob_digest_is_staleness_key`, `assumption_broad_tests_area_scoped`,
`assumption_cells_enumerable_by_plugin`, `assumption_engine_latency_targets`,
`assumption_existing_locks_wrappable`, `assumption_git_history_is_freshness_clock`
(co-change reads history as a *seed* source, never as a freshness or evidence
source), `assumption_go_toolchain_available`, `assumption_go_toolchain_ci_and_dev_only`,
`assumption_home_symlink_compatibility`, `assumption_kotlin_scanner_fail_closed`,
`assumption_legacy_user_root_coexists`, `assumption_one_engine_per_framework_version`,
`assumption_passing_run_anchors_edges`, `assumption_platform_matrix_sufficient`,
`assumption_release_asset_reachable`, `assumption_release_assets_reachable`,
`assumption_static_granularity_v1`, `assumption_target_repos_accept_aitestmap_root`
(now also `onboard.yaml`, `seeded.yaml` and `adopted.yaml` under that root),
`assumption_testmap_token_no_collision`, `assumption_variant_universe_from_runner_list`.

**Merged (both parents modified them):**

- **`assumption_change_surface_is_intake`** — the change surface is the intake
  for every `--task` path: the gate verifiers, `ait test` in all three modes,
  `stale --task`. `<path>...` is the one explicit-list intake (`TASK:` rows),
  `--dirty` the explicit and printed no-task intake, `--all` has none. An
  `UNKNOWN:` row refuses selection in interactive and completion mode and is
  `VERDICT:skip REASON:unknown_paths` naming the paths in advisory mode. The
  before content a symbol scanner needs comes from `HEAD:<path>` or the parent
  of the first `(t<id>)` commit (n005).
- **`assumption_gate_exit_contract_reused`** — the verifier contract `0/1/2/3`
  is reached through the *existing* `tests_pass` verifier running
  `test_command: ./ait test`; `run_project_command_key()` gains the 75 → error
  and 3 → error rows for opted-in keys and exports `AIT_GATE_TASK_ID` /
  `AIT_GATE_RUN_ID`; `testmap_check` keeps its own shell; advisory mode speaks
  `aitask_run_project_command.sh`'s `0/1/2/3` with 75 folded into a skip
  reason. n001 reused the contract through two dedicated shells; here it is
  one shell plus one row in the shared lib, which is what lets the legacy
  Step-9 helper and `aitask-qa` agree by construction.

**From n007, carried (with the resolution edits):**

- **`assumption_test_tools_detectable`** — verified on all five repositories;
  falsifier: build-time test generation → `DETECT_UNKNOWN`, the skill asks.
- **`assumption_seed_sources_measured`** — the merged origin table, with
  n008's co-change cap replacing n007's 0.5–0.8 ladder because the measured
  group shape does not disambiguate pairs.
- **`assumption_seeds_select_never_evidence`** — a *seed* may cause a test to
  run and may never suppress `STALE`, anchor evidence, satisfy `require_stamp`
  or count under `--strict`; promotion is an explicit adopt, by class (with
  provenance) or by row. Falsifier unchanged.
- **`assumption_instructions_block_reaches_agents`** — the mechanism: the
  `>>>aitasks` block is written and refreshed into every supported agent's
  file by `ait setup` / `ait upgrade`; fourteen lines, no agent named.
- **`assumption_helper_degrades_when_absent`** — restated for the advisory
  mode of `ait test`: absent engine / registry / `UNKNOWN:` rows / empty
  selection / admission refusal after the deadline are `skip` reasons; only an
  executed run is pass / fail; only an unwritable log is 3. This is what
  admits the pre-review procedure into every profile including `remote`.
- **`assumption_onboarding_is_a_task`** — onboarding writes committed files
  over several sessions, so each level runs as an aitask created and claimed
  by the skill, committing per phase under `(t<id>)`, re-entering at
  `ONBOARD_NEXT:`, archived by task-workflow with `finish` recorded in the
  ledger; `--no-task` for a repo that forbids tasks on the code branch.

**From n008, carried (with the resolution edits):**

- **`assumption_static_closure_seeds_edges`** — measured: 398/400 bash tests
  name their subject path literally, 320/320 Python tests import a lib module,
  52–72/400 match a naming convention; Go's subject is deterministic; Kotlin's
  is the n006 import closure. Falsifier: tests reaching subjects only through
  a dynamic dispatcher — no static rows; conventions plus co-change, or level 0.
- **`assumption_cochange_is_corroboration`** — 336 task groups in 400 commits
  at 1.14 commits each, few-to-few pairing; capped at 0.60 so it never decides
  alone; per-commit grouping where `(t<id>)` is absent; `min_cochange 2`.
- **`assumption_helpers_separable_by_fanin`** — helper roots plus fan-in ≥ 5 %;
  a misread hot module keeps `test-dep` selection; every reclassification
  listed.
- **`assumption_task_resolvable_from_session`** — the `aitask/<task_name>`
  branch in worktree mode, the single own lock in current-branch mode,
  `AIT_GATE_TASK_ID` in gate context; `AMBIGUOUS_TASK` and `--dirty` cover the
  rest; the advisory form always passes `--task` explicitly.
- **`assumption_full_run_expressible_per_repo`** — each target's completion
  suite is `ait test --all` or one `full: true` suite runner with a derivable
  `fallback_command`; thinking_backend's `verify_build` suite is the case the
  skill asks about.
- **`assumption_annotation_is_comment_only`** — adoption inserts comment lines
  only, never into a docstring; `ADOPT_SKIP:no-leader` otherwise; a member
  seed lands inside its `testmap:unit` block.
- **`assumption_instruction_block_is_read`** — agents follow the managed
  block, as the framework already relies on for `./ait git`; falsifier: a
  harness that ignores the file — `--howto` is the one-call fallback.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

**Inherited unchanged from n006** (full text in the node metadata):
`tradeoff_area_glob_coarseness`, `tradeoff_autonomous_confirmation_weak`,
`tradeoff_axis_declaration_burden`, `tradeoff_axis_projection_coarseness`,
`tradeoff_batch_misreport_risk`, `tradeoff_broad_scope_coarseness`,
`tradeoff_cell_table_size`, `tradeoff_compiled_component_cost`,
`tradeoff_engine_speed_enables_per_task_use`, `tradeoff_engine_version_skew`,
`tradeoff_evidence_requires_reachable_history`, `tradeoff_flaky_pass_anchors`,
`tradeoff_home_migration_window`, `tradeoff_intersection_can_underselect`,
`tradeoff_member_annotation_drift`, `tradeoff_noarch_packages_preserved`,
`tradeoff_real_scheduler`, `tradeoff_registry_directory_complexity` (two more
generated files and one ledger, under the same root and merge rule),
`tradeoff_resource_declaration_completeness`, `tradeoff_setup_network_fetch`,
`tradeoff_split_home_rejected`, `tradeoff_static_scanner_overselection`,
`tradeoff_strict_version_handshake`, `tradeoff_two_toolchains`,
`tradeoff_two_user_roots`, `tradeoff_whole_run_filter_soundness`.

**Merged (both parents modified them):**

- **`tradeoff_computed_vs_prose`** — *Advantage.* Selection is computed,
  explained and scored (n006); so is the run surface: `--howto` is generated,
  the instructions section is identical everywhere, and a 200-line testing
  chapter becomes ten declared `notes:` lines plus `docs:` pointers reached
  through one verb; thinking_app's "shared component → full gate" rule is an
  axis join, a fan-out and an `ESCALATE:` line.
- **`tradeoff_fail_closed_bootstrap_cost`** — *Disadvantage, narrowed.* The
  bootstrap order becomes one aitask per level that the skill creates and
  runs; `detect` and `seed` are read-only until `--write` / `--apply`; level 0
  writes only registry files and seeds; the level-0 task's own `tests_pass` is
  the first anchoring full run; `bootstrap_until` is set to +90 days by level
  0; the seeder replaces most of the hand waiver pass (88 % / 80 % of aitasks
  tests seed at least one edge); `readiness` prints `LEVEL` / `NEXT`. What
  remains: a repository is level 0 (bound, closure- and seed-selected,
  unstamped) until a human adopts level 1; headless profiles stop there plus
  language-rule origins; and the judgement in classify and adopt, which no
  seeder can take.
- **`tradeoff_attribution_risk`** — *Risk, narrowed twice.* `STALE` on the
  next task and the stale mark on every selection (n006); the Step-7
  `UNMAPPED_SOURCE:` report at the moment a source is introduced, with
  annotate / propose / waiver offered right there (n007); the automatic score
  within one task wherever completion runs the full suite (n008). What still
  escapes is a coupling to a source that already has some edge, which only
  `score` can find.
- **`tradeoff_stamp_churn`** — *Disadvantage.* `EVIDENCED` needs no rewrite,
  `--confirm-source` is one commit, member blocks keep a screen's stamps in one
  file, variants carry no stamp (n006); onboarding adds the largest rewrite of
  all — level 1 on aitasks touches ~720 test files with one to eight comment
  lines each — mitigated by seeds selecting without any rewrite, `--scope
  <glob>` per area across tasks, per-class and per-area batch commits that add
  comment lines only (`git blame -w` and every runner ignore them),
  `ADOPT_REFUSED:dirty-foreign`, the reviewed `(t<id>)` commit, and the
  in-gate path that adopts a file's seeds only when a task already has it open.
- **`tradeoff_engine_absent_on_host`** — *Risk.* `ENGINE_MISSING` names the
  path and repair verb; the fallbacks; declared gates exit 3, never skip
  (n006). Two deliberate exceptions: the advisory Step-7 run prints
  `VERDICT:skip REASON:testmap_absent` so task-workflow, pickrem and pickweb
  continue (n007), and a project may choose `completion.engine_absent:
  fallback_command` for the Web lane (n008) — both printed, never silent.

**From n007, carried (with the resolution edits):**

- **`tradeoff_seed_noise`** — heuristic seeds are wrong in both directions;
  mitigated by seeds selecting and never claiming, confidence ordering review
  rather than gating it, the 0.60 co-change cap and `min_cochange 2`, direct
  imports only, evidence beside every row, rejection memory, and the suite
  budget for a repo where over-selection is expensive; reviewer fatigue on a
  1,000-row queue is spread by class acceptance, per-area batches and the
  in-gate path.
- **`tradeoff_two_edge_states_during_adoption`** — now *three* provenances
  (seeded, adopted, reviewed) a reader must keep apart; mitigated by the origin
  or `adopted(...)` on every row, `SEEDED:` / `ADOPTED:` on `check` and `stale
  --all`, `onboard status` as the one place the ratios live, and the rule that
  no seed ever changes a freshness verdict; `--strict` cannot be enabled while
  `UNMAPPED_SOURCE` rows are only seed-covered, which is visible rather than
  silent.
- **`tradeoff_generated_brief_limits`** — a computed brief cannot hold a
  project's judgement calls; `docs:` and `notes:` carry them one hop away; the
  full completion gate backstops a misread note.
- **`tradeoff_workflow_surface_growth`** — one procedure file, one profile key,
  one dispatcher verb, one skill-invoked script with a second mode (five
  allowlist touchpoints), a Step-7 render across every profile × agent golden,
  two QA edits, a seed edit and a profile-aware skill with two wrappers;
  mitigated by uniform degradation to a printed skip, the reused `VERDICT:`
  contract, and `aitask_skill_verify.sh` plus the goldens; smaller than n007's
  by one script.
- **`tradeoff_accept_rewrites_history`** — adoption inserts comment lines into
  hundreds of test files (blame noise, header conflicts); mitigated by fixed
  insertion positions, batch commits named for what they are, the in-task
  incremental path and `REWRITE_CONFLICT`; a project may keep seeds unadopted
  and live with selection-only enforcement, reported as such.
- **`tradeoff_onboarding_partial_coverage`** — what no origin reaches stays
  `UNMAPPED_SOURCE` or area-only; mitigated by rules and expiring waivers, the
  Step-7 prompt, opt-in coverage, and the full gate as the completion criterion.

**From n008, carried (with the resolution edits):**

- **`tradeoff_one_gate_not_two`** — *Advantage:* one completion gate whose
  behaviour is a committed policy; one command; the legacy Step-9 path and
  `aitask-qa` reach the selective lane through `test_command`; the flip is one
  line after readiness. *Disadvantage:* a ledger `tests_pass: pass` no longer
  says by itself whether the whole suite ran — mitigated by
  `result="MODE:<full|selected>|<n>|policy:<mode>"` on the gate-run block,
  `POLICY_DEMOTED` being loud, `readiness` printing what `--gate` would run, and
  the `gate-` run-id prefix in the ledger.
- **`tradeoff_seed_precision`** — *Risk:* an adopted `covers` edge says the
  test *executes* the source, not that it *verifies* it; narrowed by the
  `adopted.yaml` provenance shown in `stale` / `explain`, `ADOPTED_UNREVIEWED`
  in `readiness`, the over-claim direction only over-selecting, the 0.85
  threshold with co-change unable to reach it, three-sample display per class,
  and the seeded state existing at all — a project that wants no machine
  claims stops at seeds; a coupling the closure does not contain is still
  caught only by a full run's score.
- **`tradeoff_fallback_runs_more`** — with the engine absent and
  `engine_absent: fallback_command`, completion runs the pre-onboarding suite
  command — never less than before, never selective; default `error`;
  `MODE:fallback` visible.
- **`tradeoff_verify_build_wired_suites`** — a suite wired as `verify_build`
  (thinking_backend, half lint) cannot be moved mechanically; the skill asks,
  defaults to keeping it, records the answer; headless keeps.
- **`tradeoff_dispatcher_verb_added`** — `ait test` beside `ait testmap`;
  justified by the human-would-type-it rule and the seed's need for one verb;
  kept thin; `ait testmap` remains the maintainer surface; `--howto` documents
  `ait test` as the stable one.
- **`tradeoff_bulk_confirmation_granularity`** — per-class acceptance trades
  review depth for feasibility; mitigated by samples, `review a sample`,
  `--accept-min`, `--scope`, the `adopted.yaml` provenance so nothing pretends
  to be reviewed, the per-row path for anyone who wants depth, and individual
  confirmation of kind changes.
<!-- /section: tradeoffs -->

<!-- section: conflict_resolutions [dimensions: component_*, assumption_*, tradeoff_*] -->
## Conflict Resolutions

Strategy labels follow the synthesizer's priority order: **bridge** (a
component or mode that lets both sides stand), **assumption update** (one
side's premise changed, stated), **replacement** (one side's component
dropped for another's), **carried** (resolved in n003/n006 between n001 and
n002; recorded so no first-round dimension is silently dropped).

1. **Seeded queue (n007) vs. stamped adopted edges (n008) — bridge.** Both
   states exist: `seeded.yaml` is the select-only queue, `adopted.yaml` the
   provenance of class-accepted stamped edges, a per-row acceptance is a
   reviewed claim with no provenance row. Introduced as the *adoption ledger*
   bridging component; `check` / `stale --all` / `readiness` report all three
   counts. n007's `assumption_seeds_select_never_evidence` now speaks of
   *seeds*; n008's `tradeoff_seed_precision` now has a state below it.
2. **Autonomous acceptance — assumption update.** n008 let headless profiles
   adopt static-only edges at 0.95; n007 allowed no autonomous acceptance.
   Resolved by the number that separates a language rule from a heuristic:
   headless profiles seed everything and adopt only origins at confidence
   1.0 (`static:package`). The `adopted.yaml` provenance keeps even that
   distinguishable. This also answers n007 OQ2 and n008 OQ1.
3. **Two confidence tables — bridge.** One origin vocabulary
   (`static:{package,invocation,import}`, `coverage`, `observed`,
   `convention`, `plan`, `prose`, `cochange`); n008's co-change cap (0.60,
   corroboration only) replaces n007's 0.5–0.8 ladder because the measured
   group shape (1.14 commits per group, few-to-few pairing) cannot say which
   test covers which script; n007's `coverage` and `observed` origins have no
   n008 counterpart and are kept; convention takes n007's 0.60 (the weakest
   positive signal, 16–19 % coverage, homonym risk); n008's 0.85 class
   threshold applies to `--class` only. `assumption_seed_sources_measured` and
   `assumption_cochange_is_corroboration` both hold under the merged table.
4. **Phase ledger (n007) vs. graded levels (n008) — bridge.** Levels describe
   the registry, phases describe a run; `onboard.yaml` records both (`level:`
   plus phase rows); `readiness` derives `LEVEL` from the tree, `onboard
   status` prints `ONBOARD_NEXT` from the ledger. One aitask per level (n008
   OQ7) with n007's per-phase commits and re-entry inside each.
5. **First full run: `full_run` phase (n007) vs. the task's `tests_pass`
   (n008) — replacement.** They are the same run; it lands as the level-0
   task's Step-9 gate so it is in the gate ledger, and n007's `costs --update`
   and anchoring happen inside it. `full-run.md` remains as the phase
   procedure that reads its results and writes the timeout.
6. **`bootstrap_until` +30 at enable (n007) vs. +90 at level 0 (n008) —
   assumption update.** +90 at level 0: level 0 is unstamped by design and a
   1,000-seed queue is not adopted in 30 days; `finish` may shorten it.
7. **Skill static/attended-only (n007) vs. profile-aware (n008) —
   replacement.** Profile-aware, because the merged design has a defined
   headless behaviour (resolution 2); the phase procedure files (n007) live
   under the profile-aware skill.
8. **Engine `test` composite (n007) vs. `aitask_test.sh` front (n008) —
   bridge.** Both layers, split by what must run without an engine: the front
   resolves mode / task / intake / policy and owns the `test_command` and
   `fallback_command` fallbacks; the composite is the pipeline. n007's `--mode
   show` becomes `--explain`; n007's `ait test brief` becomes `--howto`
   backed by the engine `brief` verb; n007's `ait test explain <path>` is
   dropped in favour of `ait testmap explain`.
9. **`aitask_affected_tests.sh` (n007) vs. no helper (n008) — bridge.** The
   helper's `VERDICT:/REASON:` contract and its degrade-to-skip rule become
   `ait test --advisory`, a mode of the one front; the second script is not
   written; `tests/test_affected_tests_helper.sh`'s cases fold into
   `tests/test_ait_test_entrypoint.sh`. `assumption_helper_degrades_when_absent`
   is restated for the mode.
10. **Step 7: procedure file + profile key (n007) vs. one paragraph (n008) —
    bridge.** The loop is n008's paragraph; the pre-review run before Step 8
    is n007's procedure, kept because it writes the prediction record the
    completion run scores — without it `readiness` cannot accumulate
    `min_scored_full_runs`. The profile key governs only that run.
    `requirements_workflow_seam_is_data` (n008) now reads "data plus one
    procedure"; `requirements_workflow_seam` (n007) drops the in-loop call.
11. **Three gates with `testmap_run` (n001 → n006 → n007) vs. one completion
    gate under policy (n008) — replacement.** `testmap_run` is retired; every
    property it had is placed (verifier logic → `ait test --gate`;
    `blocks_dependents` and `max_retries: 1` → `tests_pass`; timeout → the
    ledger-derived `tests_pass.timeout_seconds`; exit mapping → the shared
    lib's rows; `--include-stale` → the composite; unlock → `testmap_check`
    unlocks `tests_pass`). n001's `requirements_gate_enforcement` ("a
    selection gate and a check gate") is satisfied: the selection gate *is*
    `tests_pass` under `completion.mode: selected`. n007's enable phase keeps
    its role — it writes `tests_pass`, `testmap_check` and `testmap_fresh`
    into the profile.
12. **`UNMAPPED_SOURCE` (n007) and `UNANNOTATED_TEST` (n008) — bridge.** Both
    printed by `ait test`; both answered by the Step-7 paragraph and the
    pre-review procedure.
13. **Two `## Running Tests` texts — bridge.** One fourteen-line section
    carrying n008's rule and exit table and n007's `UNMAPPED_SOURCE` and
    not-onboarded lines; `--howto` is the flag, `brief` the engine verb.
    Pinned by extending `tests/test_agent_instructions.sh` (n008's T40)
    rather than a new test file, through a real `install.sh --dir` (n007).
14. **Task resolution — replacement.** n008's resolution order replaces n007's
    explicit-only `--task`; the advisory form still passes the id.
15. **`aitask-qa` verb form — bridge.** n007's `explain --sources <paths>
    --format table` (one call for the whole change set) with n008's 4a–4d
    edits; seeded rows are `Covered (seeded)` (n007 OQ5, taken as yes).
16. **Annotation placement — assumption update.** n008's comment-only rule
    (never into a docstring, because it changes `__doc__`) replaces n007's
    "appended to the module docstring"; n007's member-block placement and
    Go's package-clause position are added. `assumption_annotation_is_comment_only`
    holds.
17. **`verify_build`-wired suites — replacement.** n008's ask-and-keep replaces
    n007's detect proposal to move the command; the lint half decides it.
18. **Verb naming — bridge.** n007's `seed` and `onboard {detect, inventory,
    status, accept, reject, finish}` and n008's `detect | suggest | adopt |
    howto` become one family: `onboard detect | inventory | seed | classify |
    adopt | reject | scaffold | status | finish` plus `brief`; `suggest` is
    `onboard seed` (its `--json --out` dump kept), `accept` is `onboard adopt`
    (with `--class` for n008's bulk form), `runner scaffold` is `onboard
    scaffold --runner`.
19. **First-round positions resolved upstream — carried.** n001's `testmap:verified
    <sha>` stamp, `git log` anchor walk and `STALE_RUN` / `UNVERIFIED` classes
    → n002's `@<date>/<blob10>` digest with n003's evidence join and `STALE` /
    `EVIDENCED` / `UNSTAMPED`; n001's `suites/` directory → n002's
    `_scoped.yaml`; n001's `go/` + `make install-dev` + `AIT_TESTMAP_DEV=1` →
    n002's `engine/` + `ait engine build` + `AIT_ENGINE=dev`; n001's bash
    reference runners → n002's builtins with shadow-by-name; n001's
    `~/.aitask/bin/` → n002's versioned engine directory under n005's
    `$AITASKS_HOME`; n001's `concurrency: report|execute` → n002's `--serial`
    knob → n006's `serial|parallel`; n001's `max_covers_per_test` /
    `require_anchor` → n002's `unit_covers_max` / `require_stamp`; n002's
    cobra and gofrs/flock → n006's stdlib `flag` and `syscall.Flock`; n001's
    `go-check` PR job → n006's `engine-check.yml`; n002's `testmap_select` /
    `testmap_current` names → n003's `testmap_check` / `testmap_fresh`. Every
    dimension of n001 and n002 is present in the metadata with the n006 text;
    the two references specific to dropped n002 choices (cobra, gofrs/flock)
    are removed from `reference_files`.
<!-- /section: conflict_resolutions -->

<!-- section: open_questions -->
## Open Questions

1. Should `affected_tests` default to `run` or `show` when a repository's
   affected run is expensive (thinking_app: one Gradle boot under the
   heavy-run lock, ~40 s minimum)? Proposed: `run`, because the scheduler
   defers on a refused slot and the estimate is printed first; a project may
   set `show` in its profile.
2. Should `onboard adopt --class` be permitted for `static:invocation` (0.90)
   under an attended profile without the ten-sample review, given the measured
   398/400 precision on aitasks? Proposed: no — the sample costs a minute and
   is what makes the class-level yes defensible.
3. Should `completion.on_empty_selection` default to `full` rather than `skip`
   once `require_stamp: true`? An empty selection with a non-empty change
   surface is a strong "the map does not know this file" signal. Proposed:
   `skip` during bootstrap, `full` after `finish`; `readiness` prints the
   recommendation.
4. `AIT_GATE_TASK_ID` is visible to any other `test_command` — should the
   export be limited to commands matching `./ait test*`? Proposed: no; a
   variable a command ignores is harmless and a project wrapper may want it.
5. Where does the `--policy selected` approval statement live for a project
   without a design record like thinking_app's
   `change-aware-verification.md#what-this-cannot-do`? Proposed: the skill
   writes `aitestmap/ADMISSION.md` from the readiness output and the user's
   statement, and `approved_by.statement` points at it.
6. `aitask_lock.sh --list-mine` is a new verb on an existing script; is an
   `ait ls`-based query (`status Implementing`, `assigned_to` = me) preferable
   so no lock-format knowledge leaves the lock script? Either satisfies the
   resolution rule; the lock is proposed because it is host-scoped.
7. Should `onboard finish` refuse while any `pending` seeds remain, or accept
   a user-set threshold? Proposed: threshold, default 0, printed in `status`.
8. Should the `full` suite wrapper's `children:` post-processor for bash-file
   tests infer per-file results from the runner's own per-file exit or require
   junit-style output? Proposed: the per-file exit; a monolithic script gets
   suite-level evidence only.
9. Should `readiness` count only scored predictions whose selection was
   non-trivial (at least one unit) toward `min_scored_full_runs`? A
   `no_selection` advisory run scored against a green full run says nothing.
   Proposed: yes.
10. Should an `adopted.yaml` row age out — a class-adopted edge that has been
    `EVIDENCED` by N scored full runs without a miss becoming reviewed
    automatically? Proposed: no in v1; evidence removes nags, it does not
    review claims (the n005 rule), and `ADOPTED_UNREVIEWED` is meant to be
    read.
11. Baseline questions still open (n006 §Open Questions 1–8, 10–11)
    unchanged; n006's question 9 (aitasks_mobile axis) is answered by both
    parents identically: no axis, source sets are runner/kind distinctions.
<!-- /section: open_questions -->
--- PROPOSAL_END ---
