--- NODE_YAML_START ---
node_id: n008_explorer_003b
parents:
- n006_synthesizer_002
description: 'n006 plus the missing last mile: a graded onboarding path that scans a project''s existing
  tests and integrates them into the change-aware architecture (engine verbs detect / suggest / adopt
  driven by an aitask-testmap-onboard skill that runs as an ordinary aitask, seeding covers edges from
  the test-file static closure - measured 398/400 bash and 320/320 python tests on aitasks - with naming
  conventions and (t<id>) co-change as corroboration, helpers split from subjects by fan-in, kinds classified,
  provenance kept in registry/adopted.yaml); one zero-config entrypoint `ait test` that resolves mode
  (interactive vs completion), task and intake by itself, falls back to test_command where no aitestmap/
  exists and to a recorded full-suite command where the engine is absent, and prints its own project-specific
  --howto; a `## Running Tests` section in the seeded agent-instructions block so no code agent relearns
  how to run tests; and a task-workflow seam that is data rather than new steps - tests_pass runs `./ait
  test` under a committed completion policy (full until readiness is ADMISSIBLE and a human approves selected),
  testmap_check unlocks it, testmap_run is retired as a gate name, exit 75 maps to verifier error for
  opted-in command keys, profiles'' default_gates carry the two gates, and aitask-qa''s convention-based
  test discovery reads the registry instead.'
proposal_file: br_proposals/n008_explorer_003b.md
created_at: "2026-09-16 12:02"
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
- .claude/skills/task-workflow/build-verification.md
- .claude/skills/task-workflow/gate-cli.md
- .claude/skills/task-workflow/gate-recording.md
- .claude/skills/task-workflow/profiles.md
- .claude/skills/task-workflow/resource-admission.md
- .claude/skills/aitask-explore/SKILL.md.j2
- .aitask-scripts/aitask_run_project_command.sh
- .aitask-scripts/aitask_resolve_config_path.sh
- .aitask-scripts/aitask_lock.sh
- .aitask-scripts/aitask_task_worktree.sh
- .aitask-scripts/aitask_create.sh
- .aitask-scripts/aitask_attach.sh
- .aitask-scripts/aitask_skill_render.sh
- .aitask-scripts/aitask_skill_resolve_profile.sh
- .aitask-scripts/aitask_explain_extract_raw_data.sh
- .aitask-scripts/aitask_audit_wrappers.sh
- .aitask-scripts/lib/yaml_utils.sh
- .aitask-scripts/lib/gate_orchestrator.py
- seed/aitasks_agent_instructions.seed.md
- seed/codex_instructions.seed.md
- seed/opencode_instructions.seed.md
- seed/claude_settings.local.json
- seed/codex_rules.default.rules
- seed/opencode_config.seed.json
- .claude/settings.local.json
- .codex/rules/default.rules
- aitasks/metadata/profiles/default.yaml
- aitasks/metadata/profiles/fast.yaml
- aitasks/metadata/profiles/remote.yaml
- aitasks/metadata/project_config.yaml
- tests/lib/asserts.sh
- tests/lib/import_isolated.py
- tests/lib/board_fixture.py
- tests/lib/validate_session_hook_fixtures.py
- tests/test_agent_instructions.sh
- tests/test_touchpoint_count_contract.sh
- tests/test_agent_freeze.py
- aidocs/framework/code_conventions.md
- aidocs/framework/documentation_conventions.md
- /home/ddt/Work/thinking_backend/scripts/tests/run_script_tests.sh
- /home/ddt/Work/thinking_backend/aitasks/metadata/project_config.yaml
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
# new (n008)
assumption_annotation_is_comment_only: 'Integrating an existing test into the architecture never changes
  what the test does: adopt inserts `testmap:` comment lines (bash and Python after the header comment
  block or module docstring, Go after the package clause, Kotlin after the import block, with the file''s
  own comment leader), the runners execute the unchanged test, and `git diff -w --ignore-blank-lines`
  of an adopted file shows comments only; a test that cannot be annotated by comment (a file with no comment
  leader the grammar knows) is skipped with ADOPT_SKIP:no-leader and stays at level 0 (new)'
# inherited from n006 (unchanged)
assumption_areas_express_suite_blast_radius: The blast radius of a high-level test is expressible as a
  union of area glob sets plus scope globs plus budget-exempt trigger globs, plus the reads globs of helpers
  in its test-file closure; what that misses surfaces through score on a full run as an observed trigger
  or area member (inherited from n005)
# inherited from n006 (unchanged)
assumption_axis_membership_declarable: 'For a product-shaped suite, which facet value a source belongs
  to is declarable as globs by the people who own the suite, because the project already routes by exactly
  that shape - res/values-ar/** and font/cairo_*.ttf are the Arabic matrices'' inputs and matrix_classes()
  already maps a matrix to its classes; aitasks'' .claude/ vs .opencode/ vs .agents/ trees are the agent
  facet. A source that matches no axis source is not an axis hit and reaches units only through edges
  and dependencies, which select every variant - the fail-safe direction n004 called ANY. Falsifier: a
  project whose membership is genuinely dynamic (a runtime flag choosing a locale), for which the answer
  is to declare no sources on that facet (n004''s general claim, of which assumption_axis_sources_declarable
  is the thinking_app instance)'
# inherited from n006 (unchanged)
assumption_axis_sources_declarable: 'The sources that reach one facet value of an axis are declarable
  as globs in axes.yaml: for thinking_app''s locale facet, values-<q>/**, raw-<q>/** and the per-family
  fonts (heebo_* for he, roboto_* for en and ru, cairo_* for ar); sources every locale reads (values/**,
  TypeScale.kt, Fonts.kt, AppRoot.kt) are ordinary edges, scanned dependencies or one hand rule over values/**
  and reach every variant; the geometry and direction facets have no axis sources because they are test-side
  constants in ScreenshotTestHarness.kt, reached through the test-dep closure (inherited from n005)'
# inherited from n006 (unchanged)
assumption_batch_per_unit_timing_reportable: Runners can report per-unit timing inside a batch from their
  tool's own report format (JUnit XML, go test -json, pytest junitxml), can invert a report row to a registered
  id (JUnit classname+name back to ScreenFixtures.kt#Welcome@pixel5Ru_ltr through the same routing table
  the runner's list verb printed), and the same JUnit XML reports each @Test method with its own duration,
  which is what makes a variant's marginal cost measurable separately from its class's boot - the number
  the invocation-group budget depends on (n005 inversion, n004 per-method timing)
# inherited from n006 (unchanged)
assumption_blob_digest_is_staleness_key: The git blob digest of the covered source's content is the staleness
  key; file mtime (reset by checkout) and the annotation date (day granularity, clock skew) are never
  compared - the date is display only; the blob id doubles as the join key into any commit's tree for
  the evidence join (inherited)
# inherited from n006 (unchanged)
assumption_broad_tests_area_scoped: Integration, e2e and device tests can be described by named areas
  or globs whose membership changes rarely, so evidence-based drift (STALE_AREA) plus attribute widening
  is adequate; a calendar cadence (REVIEW_DUE, broad_review_days) is opt-in and off by default (inherited)
# inherited from n006 (unchanged)
assumption_cells_enumerable_by_plugin: 'The variant universe a repo has is enumerable from the project''s
  existing single routing statement rather than a second hand-maintained list - and the enumerator is
  the runner''s list verb, not a separate plugin directory: thinking_app''s runner lists ~300 variant
  ids from matrix_classes() crossed with the two membership manifests, aitasks'' from its rendered tests/golden/
  tree; the framework never infers a variant. Falsifier: a repo whose test methods are only knowable by
  running the build, for which list may exec the build''s own list task at the cost of a slower scan/check,
  since select never calls it (n004''s assumption, re-sited onto n005''s runner list)'
# inherited from n006 (unchanged)
assumption_change_surface_is_intake: 'The change-surface script''s attribution (aitask_change_surface.sh)
  is the right intake; its exit codes carry no meaning, so the shim pipes its COMMITTED:/TASK:/OTHER:/UNKNOWN:
  lines into the engine''s --changes - and the engine parses lines only; selection never reads a raw git
  diff, and an UNKNOWN path refuses selection and drives the stale decision; the before content a symbol
  scanner needs comes from HEAD:<path> (TASK: rows) or the parent of the first (t<id>) commit (COMMITTED:
  rows) and is absent - so the whole file is the symbol set - when history is unreachable (inherited from
  n005)'
# new (n008)
assumption_cochange_is_corroboration: '(t<id>)-tagged commit history is a corroborating signal, never
  a primary one: in the last 400 commits touching tests/ or .aitask-scripts/ on aitasks there are 336
  task groups averaging 1.14 commits each, and a group pairs a few tests with a few scripts (t1159_1:
  4 tests x 4 scripts) with nothing inside the group to say which test covers which script, so co-change
  scores 0.2 + 0.2 x shared groups capped at 0.6 and cannot reach the 0.85 acceptance threshold alone;
  repositories without the (t<id>) convention fall back to per-commit grouping with the same cap (new,
  measured)'
# inherited from n006 (unchanged)
assumption_engine_latency_targets: 'On the aitasks repo (about 720 test units, 2,500-3,000 edges, about
  270 scanned sources) the engine meets select < 200 ms warm, scan < 300 ms, check < 300 ms, stale --task
  < 300 ms, stale --all < 2 s, cold select < 1.5 s; on a thinking_app-shaped fixture (about 300 golden
  variants over 49 member units, about 370 JVM classes, about 900 Kotlin files) select with axis expansion
  < 250 ms warm, reading the committed variants: lists and never executing a runner; pinned by committed
  go test -bench fixtures with a 2x regression failing engine-check.yml, validated before the gates are
  enabled (n005; n004''s 2,500-row cell target dropped with the cell table)'
# inherited from n006 (unchanged)
assumption_existing_locks_wrappable: Existing project locks and allocators (thinking_app's heavy-run lock
  with its exit-75 admission in tools/verification/heavy-run-lock.sh, emulator allocation in emulator-allot.sh)
  can be wrapped as resources without changing them; the Go admission and allocator kinds exec the project's
  commands and honour their exit codes, deferring on 75 until the run deadline; thinking_app's runner
  script goes through screenshot-tests.sh unit-tests, which reserves the slot itself (inherited)
# new (n008)
assumption_full_run_expressible_per_repo: 'Every target repository''s completion suite is expressible
  as `ait test --all` over its runners or as one full: true suite runner: thinking_app''s verify-active
  (already test_command; screen-matrix and gradle-class subsumed_by it), thinking_backend''s scripts/tests/run_script_tests.sh
  (22 bash + 18 python tests, wired today as verify_build because it also runs a shellcheck baseline),
  aitasks_go''s `go test ./...` over 85 packages, aitasks_mobile''s `./gradlew check` minus the 3 androidDeviceTest
  classes which run only under device_policy, and aitasks'' 400 bash + 320 python units which had no suite
  command at all (test_command: null) and gain one; fallback_command is derivable for each from detect''s
  output (new)'
# modified from n006
assumption_gate_exit_contract_reused: 'The framework verifier contract (0 pass / 1 fail / 2 skip / 3 error)
  is reached through the EXISTING tests_pass verifier running test_command: `./ait test --gate` speaks
  0/1/2/3/75/64, and run_project_command_key() - the single canonical statement of the command exit contract
  - gains one row for opted-in keys: 75 -> error (PROJECT_CMD_STATUS=error, CODE=3, REASON=command_refused),
  so an admission refusal that survived the in-engine deferral is a verifier error the orchestrator retries
  within budget, never a code failure and never a skip; 2 (nothing ran: empty selection) stays the opt-in
  skip; a missing engine is 3 through `ait test` itself. The verifier exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID
  to the command, which is how `./ait test` knows it is in completion mode and for which task; aitask_run_project_command.sh
  --task-id exports the same, so the legacy Step-9 path, aitask-qa and the gate agree by construction.
  testmap_check keeps its own verifier shell (n006 reused two shells; here one shell plus one row in the
  shared lib)'
# inherited from n006 (unchanged)
assumption_git_history_is_freshness_clock: Git history is the evidence clock, not the staleness key -
  commit reachability (merge-base --is-ancestor) decides which last_pass anchors may suppress a STALE
  row, never whether an edge is stale; mtime is never compared; a shallow clone whose anchors are outside
  fetched history reports STALE, not EVIDENCED, and remains fully functional (inherited)
# inherited from n006 (unchanged)
assumption_go_toolchain_available: 'A Go toolchain >= 1.26 is available in release CI through an actions/setup-go
  step this design adds to release.yml (go-version-file: engine/go.mod) and on framework developers''
  machines; target-project users never need Go (inherited)'
# inherited from n006 (unchanged)
assumption_go_toolchain_ci_and_dev_only: Go is a build-time dependency only - release.yml has no Go step
  today and the repo's only setup-go is hugo.yml's at website/go.mod's 1.25.7, so the engine job provisions
  its own toolchain; users receive prebuilt binaries and never compile (inherited)
# new (n008)
assumption_helpers_separable_by_fanin: 'Within a test file''s closure, helpers (asserts, fixtures, fakes)
  are separable from subjects by two rules the skill confirms: a path under a declared helper root (tests/lib/**,
  **/testing/**, **/src/test/** for Kotlin, **/testdata/**) is a helper, and any other closure path whose
  fan-in reaches >= helper_fanin (default 5% of the runner''s units) is a helper; helpers get test-dep
  through the closure and, when they glob the tree (ls tests/*.sh, glob.glob, rglob, find, git ls-files,
  os.walk - aitasks: tests/lib/import_isolated.py, board_fixture.py, validate_session_hook_fixtures.py),
  a proposed testmap:reads; subjects become covers candidates. Falsifier: a hot production module imported
  by most tests would be misread as a helper and lose its covers edges - it keeps test-dep selection,
  over-selecting rather than under-selecting, and the skill lists every fan-in reclassification for review
  (new)'
# inherited from n006 (unchanged)
assumption_home_symlink_compatibility: 'Every existing consumer of the legacy ~/.aitask tree keeps resolving
  unchanged when ~/.aitask becomes a symlink to ~/.aitasks, because all of them dereference a path rather
  than compare one - verified: the 35 references across 8 framework files (21 in aitask_setup.sh, 6 in
  python_resolve.sh, 3 in aitask_path.sh), the venv''s console-script shebangs (#!/home/<u>/.aitask/venv/bin/python3),
  the ~/.aitask/bin/python3 wrappers, the ~/.aitask/python/<ver>/bin/python3 symlinks whose targets are
  absolute paths outside the home, and pyvenv.cfg''s informational command = line; no ==, !=, -ef, realpath,
  os.path.realpath or samefile on the home path anywhere under .aitask-scripts/, ait or install.sh. This
  is the precondition of ait engine home --migrate, re-checked by tests/test_aitasks_home.sh''s post-migration
  venv and PyPy-venv exercise before the default is flipped (n004''s assumption, verified and scoped to
  the verb)'
# new (n008)
assumption_instruction_block_is_read: 'Code agents load CLAUDE.md / AGENTS.md at session start and follow
  a managed block that names one command: the framework already relies on this for `./ait git`, notes
  and commit format, and ait setup regenerates the >>>aitasks block on every run (t1612), so a `## Running
  Tests` section reaches every agent in every onboarded project with no per-project authoring; the hand-maintained-CLAUDE.md
  case (sentinel present, no markers) is this repository and is edited by the onboarding task. Falsifier:
  an agent whose harness does not read the file - for which `ait test --howto` is the one-call fallback
  (new)'
# inherited from n006 (unchanged)
assumption_kotlin_scanner_fail_closed: A closed construct list (explicit repo import, same-package as
  fully connected, repo star import as a package edge, fully-qualified in-body reference from the comment-stripped
  body) is enough to over-approximate the Kotlin import graph, and every construct that defeats such a
  graph - inline functions, const val, Hilt/DI bindings, Class.forName / ::class.java, generated or KSP
  sources, an unreadable or untokenizable file - is detectable by pattern and marks the file opaque, so
  a change to it escalates instead of being silently narrow; measured on thinking_app, 42 main files declare
  const val or inline fun and 63 carry DI annotations, so escalation is frequent by design; each opaque
  branch is reachable and red-proved by an engine fixture test (inherited from n005, cost measured)
# inherited from n006 (unchanged)
assumption_legacy_user_root_coexists: In this release ~/.aitasks/ (engine) and ~/.aitask/ (venv, pypy_venv,
  python, bin, uv, dev_tier, update_check; 8 framework code files with 35 references name it, plus 20
  test and 18 doc files) coexist on one host without either reading the other; the migration of the legacy
  tenants exists as ait engine home --migrate but is not run by ait setup by default, and nothing in this
  feature depends on it having happened (n005; the default flip is a named follow-up)
# inherited from n006 (unchanged)
assumption_one_engine_per_framework_version: One engine build per framework version suffices; a per-user
  versioned directory ($AITASKS_HOME/engine/v<VERSION>/) resolves per-project VERSION differences without
  a compatibility matrix, and exact-version resolution in the shim never falls back to newest-wins (inherited,
  root corrected)
# inherited from n006 (unchanged)
assumption_passing_run_anchors_edges: A passing run of a test variant at commit C, on any host class,
  from an invocation without a cause and for an id under the flake threshold, is evidence that its annotated
  edges held for that variant against the source content present in C's tree - so an edge whose current
  blob equals the blob at C is EVIDENCED for that variant without touching the test file; a unit with
  variants is EVIDENCED only when every variant the change reaches has such a pass; a verify-active full
  run's child rows anchor all 297 goldens at once (inherited from n005)
# inherited from n006 (unchanged)
assumption_platform_matrix_sufficient: linux/darwin x amd64/arm64 covers every target host (WSL reports
  Linux); any other platform builds from source via --engine-from-source (inherited)
# inherited from n006 (unchanged)
assumption_release_asset_reachable: A host running ait setup or ait upgrade can reach github.com/beyondeye/aitasks/releases
  over HTTPS, as it already must for the framework tarball; the shim itself never downloads, so a gate
  run never performs a network fetch (inherited)
# inherited from n006 (unchanged)
assumption_release_assets_reachable: Air-gapped or off-matrix hosts supply the binary via --local-engine,
  --engine-from-source, AIT_TESTMAP_BIN or a pre-seeded $AITASKS_HOME/engine/; --no-testmap / AIT_TESTMAP_FETCH=0
  skip the fetch and nothing else in setup depends on it (inherited, root corrected)
# new (n008)
assumption_static_closure_seeds_edges: 'The test-file static closure is a sufficient primary seed for
  covers edges on the target shapes, and naming conventions are not: measured on aitasks, 398 of 400 tests/test_*.sh
  name an aitask_*.sh or lib/*.sh|py path literally (the two that do not are pure fixture tests), 320
  of 320 tests/test_*.py import a .aitask-scripts/lib module through a sys.path bootstrap, while only
  52 of 400 bash tests map to .aitask-scripts/aitask_<stem>.sh by the tests/test_<stem>.sh convention
  aitask-qa relies on today; on aitasks_go the subject is deterministic (a _test.go covers the non-test
  files of its own package); on Kotlin the import graph is the same scanner n006''s Kotlin closure uses.
  Falsifier: a project whose tests reach subjects only through a dynamic dispatcher (a CLI tests drive
  by name) - for it suggest emits no static rows and the skill offers convention rules and co-change,
  or level 0 only (new, measured)'
# inherited from n006 (unchanged)
assumption_static_granularity_v1: 'Static file-level facts remain the default for v1, with two narrower
  granularities in use rather than reserved: a member unit (<path>#<member>, annotations scoped by testmap:unit
  blocks, no language parsing) and the edge''s symbols slot, whose first consumer is the opt-in android-res
  scanner that names the string keys a values-<q>/ diff changed; no scanner produces symbol-level coverage
  of Kotlin or Python code; a change anywhere in a member file is a change to every member until hunk-level
  attribution exists (n005; n004''s plugin exception subsumed by the runner list)'
# inherited from n006 (unchanged)
assumption_target_repos_accept_aitestmap_root: Every target repo will accept a root aitestmap/ directory
  of YAML committed into its code tree, including an optional axes.yaml; runner scripts and axes are both
  optional (a repo with no product space declares none and gets exactly n003's behaviour) because the
  reference runners are built into the engine; thinking_app commits one runner script (tools/verification/testmap_runner.sh)
  because its lowering is the harness's own routing (merged)
# new (n008)
assumption_task_resolvable_from_session: '`ait test` can find the task an agent is implementing without
  being told: task-workflow names worktree branches aitask/<task_name> where <task_name> is the task file
  stem (t<id>_<slug>), so `git rev-parse --abbrev-ref HEAD` yields the id in worktree mode; in current-branch
  mode (fast profile, create_worktree: false) the task lock this user holds on this host is unique per
  Implementing task, so a `--list-mine` listing on aitask_lock.sh yields it; two or more yield AMBIGUOUS_TASK:<ids>
  and require --task; gate context supplies AIT_GATE_TASK_ID. Falsifier: an agent implementing outside
  the workflow (no lock, no branch) - for whom `ait test --dirty` is the explicit, printed, never-default
  intake (new)'
# inherited from n006 (unchanged)
assumption_testmap_token_no_collision: The annotation token 'testmap:' does not collide with existing
  prose comments in any target repo; the 38 existing '# Covers:' headers in aitasks are behavioural prose
  and are not matched; thinking_app's KDoc mentions no 'testmap:' string (inherited)
# inherited from n006 (unchanged)
assumption_variant_universe_from_runner_list: 'A runner''s list verb enumerates the complete universe
  its run filter can address, so whole-run selection is sound: for thinking_app that is every <Screen>_<matrix>.png
  of the two membership manifests (50 + 247 goldens over 10 matrices) as variant ids plus every other
  class under app/src/test/java as a file unit; a class absent from list is a check failure (UNREGISTERED),
  never a silently unfiltered one; scan --apply persists each member''s listed variants so select reads
  the committed table and only scan and check exec list (inherited from n005; persistence from n004''s
  committed-table property)'
# new (n008)
component_agent_instructions: The shared agent-instructions seed gains `## Running Tests` (always ./ait
  test; ./ait test <path>; ./ait test --all; ./ait test --howto; UNANNOTATED_TEST -> ./ait testmap annotate
  --suggest <path>; never invoke pytest / go test / gradle / a test script directly; the exit-code table),
  installed unchanged into CLAUDE.md's >>>aitasks block, AGENTS.md, .codex/instructions.md and the OpenCode
  mirror by the existing assemble_aitasks_instructions() on every ait setup; tests/test_agent_instructions.sh
  gains T40 asserting the heading in all four rendered surfaces; the seed carries no project specifics
  - `ait test --howto` computes them (runners, kinds, resources, completion policy, full-run command,
  the current LEVEL) so the current-state-only doc rule holds and nothing condensed from runners.yaml
  lives in a constant (new)
# inherited from n006 (unchanged)
component_annotation_scanner: 'Annotation scanner and rewriter (internal/annot): grammar v3 - testmap:unit
  <Member> opens a member block that owns every following testmap: line until the next testmap:unit or
  end of file (a file-level block precedes the first unit); testmap:kind, testmap:covers <path> @<date>/<blob10>,
  testmap:area, testmap:scope, testmap:trigger, testmap:reads <glob> (helper files only), testmap:axis
  <axis>.<facet>=<value> (a plain unit''s coordinate, from n004), testmap:reviewed, runner/needs/batch
  - per comment leader and Python module docstrings; refuses unknown keys with a line number; the line-targeted
  rewriter edits stamps by (file, line, current text) and refuses on REWRITE_CONFLICT; annotate --from-body
  seeds covers for a member from the kotlin scanner''s symbol resolution of the block''s own lines; produces
  both generated files from every runner''s list output (merged from n004 and n005)'
# inherited from n006 (unchanged)
component_axes: 'Axis resolver verbs (internal/axes): ait testmap axes --list prints every declared axis
  with its facets, values and the variant count each value has in list; --check runs the axis rules (DEAD_AXIS_SOURCE,
  UNKNOWN_VARIANT, UNCOVERED_VALUE); --explain <path> prints AXIS:<axis>.<facet>|<value or ->|<why> per
  facet for one file - which glob matched, or that no source is declared - so a maintainer sees where
  a file lands before anything is trusted; n004''s resolve(changeSet) -> set | ANY is the SourcesHit join
  read the other way, with ANY printed as - and meaning no axis hit (n004''s verbs re-sited onto the variant-axes
  table)'
# inherited from n006 (unchanged)
component_binary_distribution: 'Binary distribution: engine/build.sh as the single build and matrix command;
  the engine job in release.yml (setup-go from engine/go.mod, go vet, go test, build.sh all) producing
  ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and ait-testmap_<V>_SHA256SUMS.txt attached by both action-gh-release
  steps with release needs: [plan, engine]; the unchanged VERSION-matches-tag guard; a new engine-check.yml
  on push/pull_request for engine/** (gofmt, vet, test, 2x bench rule); lib/platform_detect.sh; the shim''s
  strict handshake (AIT_TESTMAP_BIN with override notice > AIT_ENGINE=dev slot at $AITASKS_HOME/engine/dev/
  requiring <V>-dev+<sha> > $AITASKS_HOME/engine/v<V>/ requiring == VERSION > ENGINE_MISSING:<path> exit
  3 with repair hint); tests test_testmap_shim.sh (extended with an AITASKS_HOME host), test_platform_detect.sh
  and test_aitasks_home.sh; aidocs/framework/go_engine.md, a CLAUDE.md Engine block and a packaging_strategy.md
  paragraph naming ~/.aitasks/engine/; release-packaging.yml and nfpm arch: all untouched (inherited from
  n005)'
# inherited from n006 (unchanged)
component_broad_test_scopes: 'Broad-test scheduling and staleness policy: kind integration|e2e|device
  selects the scoped association form; broad_after_unit: true waves run scoped rows only after a green
  unit wave; device_policy: filter_by_resource default; scoped rows are exempt from per-edit digest staleness,
  with STALE_AREA as the evidence-based drift signal and REVIEW_DUE as an opt-in cadence; attribute widens
  areas by evidence; covers on a scoped row is allowed for digest-stamped fixture pins; a suite row (thinking_app''s
  verify-active) marked full: true with a children: post-processor anchors registered ids on every run;
  variant-bearing units are unit kind, never area-scoped, and ride the unit wave with admission-holding
  invocations ordered last (merged from n004 and n005)'
# inherited from n006 (unchanged)
component_cell_enumeration: 'Enumeration and reconciliation: there is no aitestmap/cells/ directory and
  no _cells.yaml - the project''s runner list verb is the enumeration surface and scan --apply persists
  its output as the variants: list on each member row of _scanned.yaml (49 rows with at most ten values
  for thinking_app), so select never execs a runner and only scan and check call list; what n004''s enumeration
  bought - two-way reconciliation - is kept as UNCOVERED_VALUE:<axis>|<value> (a declared value no runner
  lists) and UNMAPPED_ARTIFACT:<path>|<runner> (a file matching a runner''s declared artifact_glob: that
  no listed id''s artifact column claims), both failing check --strict after bootstrap; thinking_app''s
  list reads the two membership manifests and matrix_classes, every fact from a file the project already
  guards (n004''s component, re-sited onto n005''s runner list)'
# new (n008)
component_completion_policy: 'aitestmap/config.yaml `completion:` block: mode full|selected (full by default;
  selected is written only by the onboarding skill''s --policy re-entry after READINESS_DECISION:ADMISSIBLE,
  beside run_gate_admission.approved_by), deferred run|fail (what completion does with rows the interactive
  budget would cut; default run), on_empty_selection skip|full (default skip -> exit 2 -> gate skip under
  the opt-in), engine_absent error|fallback_command (default error). `ait test --gate` re-checks readiness
  on every completion run and, if mode is selected but a criterion is unmet (a new false negative, a regressed
  opaque proof), prints POLICY_DEMOTED:selected->full|<criterion> and runs full - the flip is a human
  decision and the demotion is automatic, so the policy can only fail toward running more (new)'
# modified from n006
component_cost_ledger: 'Cost ledger (internal/cost): Welford per (id, host class) where id may be a variant,
  with P2 p95 and last; per-repo ledger .aitask-testmap/ledger.jsonl with run_id/id/status/duration_ms/head_sha
  per result and {run_id, group, overhead_ms, units_reported} per invocation; costs --update folds both
  into aitestmap/costs/<hostclass>.yaml and truncates; last_pass {sha, at, run_id} per id and a flake
  rate with flake_threshold; the estimate for a selection is the sum over invocation groups of overhead.p95
  + the p95 of each selected id, reported per kind (n004 group costing); costs/predictions.yaml holds
  the last 200 scored full runs {run_id, prediction_run_id, task, predicted, false_negatives, missed[]}
  (merged from n004 and n005; `costs --gate-timeout tests_pass` prints GATE_TIMEOUT_SUGGESTED:<gate>|<seconds>
  = max(600, 3 x p95 of the newest full run on this host class), which onboarding writes into the project''s
  gates.yaml after the first measured full run (n006 ledger; timeout derivation new)'
# inherited from n006 (unchanged)
component_dependency_scanners: 'Dependency scanners (internal/deps): built-in bash, python, go (go list
  -deps -json cached by go.sum digest), kotlin and Gradle module-graph scanners plus executable plugins
  under aitestmap/scanners/ speaking one JSON line per file {file, deps, opaque?, reads?}; the kotlin
  scanner runs over main and test roots, handles a closed construct list and marks every other file opaque:<reason>;
  the opt-in android-res symbol scanner indexes R.string.<key>, stringResource(R.string.<key>) and "<key>".localized()
  sites per Kotlin file and, given a before blob, the keys a values-<q>/ diff changed; forward deps cached
  per source blob under ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json and inverted
  in memory; n004''s reach: consumer is not carried (inherited from n005)'
# inherited from n006 (unchanged)
component_engine_binary: 'Engine binary identity and budget: embeds version, commit and contract; version
  --json is the install-time self-check and prints the resolved ENGINE:<path> from the executable path;
  fixed-prefix structured output and --json; CONTRACT_MISMATCH refusal on registry files from a newer
  contract (contract 1 covers axes.yaml, member ids and the artifact column); performance budget pinned
  by go test -bench on golden registries for aitasks and a thinking_app-shaped fixture with a 2x regression
  failing CI; scanner and dependency pools capped at 8 (inherited from n005)'
# inherited from n006 (unchanged)
component_engine_packaging: 'Engine install and developer regeneration: install_engine_binary() in aitask_setup.sh,
  reached by ait setup and by ait upgrade through install.sh''s --source-only path beside install_global_shim;
  sources lib/aitasks_home.sh; uname mapping; .sha256 sidecar short-circuit; source order --local-engine
  > exact-version release asset > --engine-from-source > ENGINE_MISSING warning; sha256sum -c / shasum
  -a 256; atomic install to $AITASKS_HOME/engine/v<V>/; version --json must echo <V>; .dev-marked binaries
  never overwritten without --force-engine; --no-testmap / AIT_TESTMAP_FETCH=0 print TESTMAP_BINARY:skipped;
  HOME_LEGACY: hint when legacy tenants exist; .aitask-testmap/ gitignored by setup (the per-repo .aitask-*
  family is unchanged); aitask_engine.sh with ait engine build|test|cross|prune|home [--migrate]; tests/test_install_engine_binary.sh
  through a real install.sh --dir --local-engine asserting the $AITASKS_HOME path (merged from n004 and
  n005)'
# inherited from n006 (unchanged)
component_evidence_join: 'Evidence join (internal/stale + internal/gitx, reads internal/cost): for every
  edge whose stamped_blob differs from the current blob, collects last_pass shas per reached variant from
  the local ledger and committed costs (any host class), drops candidates from invocations with a cause
  or ids over the flake threshold, keeps shas that are ancestors of HEAD, and runs one git ls-tree per
  distinct sha; an edge is EVIDENCED when every reached variant has a sha whose source object id equals
  the current blob, otherwise STALE with the unevidenced variants listed; never rewrites - stale --confirm-evidenced
  is the explicit re-stamp and the only bulk confirmation an autonomous profile may run (inherited from
  n005)'
# modified from n006
component_feedback_tools: 'Feedback tools (internal/feedback): score splits a full run''s failures into
  caught/missed for unit, variant and scoped rows against a prediction record; run --all and any full:
  true suite runner run auto-invoke score against the newest prediction for the same task and print PREDICTION_SCORED
  / PREDICTION_FALSE_NEGATIVES:<n> / PREDICTION_MISSED:<id> lines, appending to costs/predictions.yaml;
  attribute records missing-edge/test-wrong/source-wrong for units and members, missing-axis-source for
  a facet value (an observed source glob in observed.yaml, merged at load, widen only - n004''s rule),
  missing-trigger/area-too-narrow for scoped rows, with task and run id; readiness prints the run-gate
  admission facts (merged from n004 and n005; readiness additionally prints LEVEL:<0-3> (onboarding level
  reached, derived from what exists: runners.yaml -> 0, any _scanned edge -> 1, any _scoped row or reads
  -> 2, axes.yaml -> 3), NEXT:<the adopt or skill step that raises it>, ADOPTED_UNREVIEWED:<n>|<ratio
  of covers edges> as an informational criterion, and POLICY:<completion.mode>|<what ait test --gate would
  run now>; it still enables nothing (n006 feedback; level report new)'
# inherited from n006 (unchanged)
component_framework_home: 'Framework home report and migration verb (aitask_engine.sh): ait engine home
  prints HOME_ROOT:<path>, HOME_LEGACY:<path>|<tenants found>, HOME_SYMLINK:none|<target> and HOME_NEXT:<what
  --migrate would do>; ait engine home --migrate runs n004''s algorithm under flock $AITASKS_HOME/.home.lock
  - refuses and reports no-legacy-root, already-migrated, foreign-symlink:<target>, cross-device or unknown-entry:<name>;
  moves each present entry of the known set {venv, pypy_venv, python, bin, uv, dev_tier, update_check,
  engine} with a same-device mv, rmdir''s the emptied legacy root and leaves ln -s $AITASKS_HOME ~/.aitask
  behind; prints HOME_MIGRATED:<n> or HOME_SKIPPED:<reason>. pypy_venv is the correction to n004''s set:
  setup_pypy_venv() creates it, python_resolve.sh reads it, and the host this was designed on carries
  it, so n004''s migration would have refused here. In this release ait setup only prints HOME_LEGACY:<path>|run
  ''ait engine home --migrate''; the follow-up that flips the default (reserving --no-home-migration /
  AIT_HOME_MIGRATE=0) is admitted when tests/test_aitasks_home.sh, run through a real install.sh --dir,
  covers fresh install, migration with a working venv and PyPy venv afterwards, idempotent re-run, a hostile
  pre-existing symlink, cross-device refusal and the AITASKS_HOME override, and updates the 18 doc files
  naming ~/.aitask (inherited from n004, made explicit and deferred; known set corrected)'
# inherited from n006 (unchanged)
component_freshness: 'Freshness: the per-edge @<date>/<blob10> stamp written only by verify, annotate
  and stale --confirm*, scoped to a member block where the unit is a member; variants carry no stamp of
  their own (the member''s edges are the claim, the variant''s last_pass is the evidence); last_pass anchors
  per id in the ledger and committed costs; the verify verb and verify --all-evidenced; config bootstrap_until,
  require_stamp, flake_threshold; the testmap_fresh procedure gate dispatched by the existing procedure-gate
  block before the change summary so stamp rewrites ride the (t<id>) commit; the aitask-gate-testmap-fresh
  skill; not a git hook and not a Claude Code hook (inherited from n005)'
# modified from n006
component_gates: 'Gates: testmap_fresh (kind: procedure, verifier aitask-gate-testmap-fresh, no unlocks)
  and testmap_check (machine, max_retries 0, timeout 120, unlocks: [tests_pass]) in gates_reference.yaml
  synced to gates.yaml; the completion test gate is the EXISTING tests_pass with test_command: ./ait test
  and gate_command_exit_contract: [test_command], so `ait gates run` needs no new verifier for running
  tests and the legacy no-gates path needs no new prose - a project reaches the selective lane by declaring
  tests_pass (onboarding writes it into profiles'' default_gates); testmap_run is retired as a name (its
  logic is `ait test --gate`, its timeout becomes a project tests_pass.timeout_seconds written from the
  cost ledger, its 75 -> error mapping lands in run_project_command_key for opted-in keys); aitask_gate_testmap_run.sh
  is not written; aitask_gate_testmap_check.sh stays; an `unlocks:` target absent from a task''s active
  set is ignored, so testmap_check declared alone is linear as before; run_gate_admission and `ait testmap
  readiness` (n006) now gate the completion POLICY flip rather than a second gate''s declaration (n006
  gates re-cut; one completion gate)'
# modified from n006
component_go_engine: 'Go engine and CLI: engine/cmd/ait-testmap with internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform};
  Go 1.26 with pinned toolchain, CGO_ENABLED=0, -trimpath -buildvcs=false -ldflags -s -w -X version/commit/contract;
  deps gopkg.in/yaml.v3, bmatcuk/doublestar/v4, golang.org/x/sync only; stdlib flag verb table, syscall.Flock,
  os/exec git; line-protocol stdout, --json, per-verb exit contracts; never writes aitasks/, aiplans/,
  .aitask-data/ or a gate ledger, never invokes aitask_*.sh, and never needs its own install root (n004''s
  internal/home dropped); tests against fixture repos in t.TempDir() including one fixture per opaque-scanner
  branch (inherited from n005; plus internal/onboard (framework detectors, the suggest signal join, the
  adopt writer over internal/annot''s rewriter, the howto renderer) behind the verbs detect | suggest
  | adopt | howto, and `costs --gate-timeout`; the engine still never writes project_config.yaml, gates.yaml,
  profiles or CLAUDE.md - those writes are the skill''s, through the existing bash helpers (n006 engine;
  onboard package new)'
# new (n008)
component_onboarding_engine_verbs: 'internal/onboard behind four verbs. `detect` prints FRAMEWORK:<kind>|<glob>|<count>|<builtin>|<evidence>
  for a closed detector list (bash-file, pytest, go-test, gradle-class, kmp-sourceset, suite-from-config),
  UNIVERSE:<n>, UNLISTED:<n> test-looking files no detector claims, AGGREGATE_RUNNER:<path> and SERIAL_LIST:<path>|<n>
  for a runner script with a carve-out list, RESOURCE_HINT:<name>|<n tests>|<evidence> (real-repo git
  use, flock, a lock script), SUITE_CANDIDATE:test_command|verify_build|<cmd>, RUNNER_SCRIPT_NEEDED:<reason>
  from the grid heuristic. `suggest [--test <p>...|--all] [--json --out <f>]` prints per unit SUGGEST:<test>|<source>|<signals>|<confidence>
  where signals are static 0.9 (go package 1.0), convention 0.7 (patterns from config.yaml conventions:,
  seeded by detect), cochange 0.2+0.2n capped 0.6, plan 0.5 (aiplans naming both paths via the explain
  cache when present), prose 0.3 (a literal path in the header comment or `# Covers:` line), combined
  1-prod(1-c); plus SUGGEST_HELPER, SUGGEST_READS:<helper>|<glob>|<evidence>, SUGGEST_KIND:<test>|unit|integration|e2e|device|<reason>
  (tmux / App.run_test / install.sh --dir / real .git use / fanout:<n> above unit_covers_max -> integration
  with areas from the closure''s directories x codemap; androidDeviceTest -> device), SUGGEST_BATCH_NO
  from serial lists, SUGGEST_MEMBER / SUGGEST_AXIS from classify --suggest. `adopt --from <json> [--accept-min
  0.85] [--scope <glob>] [--level 0..3] [--dry-run]` writes level-0 files (config.yaml with bootstrap_until
  today+90, require_stamp false, concurrency serial, completion.mode full, conventions:, helper_roots:;
  runners.yaml; resources.yaml; areas --import-codemap), level-1 stamped covers blocks through the line-targeted
  rewriter plus registry/adopted.yaml rows, level-2 kind/area/reads/batch lines and needs: bindings, level-3
  axes.yaml skeleton and aitestmap/runners/<name>.sh scaffold with describe/list/run stubs; refuses ADOPT_REFUSED:<path>|dirty-foreign
  for a dirty file outside the task''s change surface, skips duplicate / unregistered / no-leader; prints
  WROTE: per file and ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>. `howto` renders the --howto text
  from runners.yaml, resources.yaml and config.yaml (new)'
# new (n008)
component_onboarding_skill: 'aitask-testmap-onboard: profile-aware (stub + SKILL.md.j2, resolver key `onboard`),
  Claude Code first with Codex and OpenCode ports as follow-up tasks. Steps: (1) preconditions - `ait
  testmap version` else stop with the ait setup hint; existing aitestmap/ -> refresh mode limited to units
  newer than adopted.yaml''s last row; (2) run detect and suggest --all --json read-only and show the
  level proposal: counts per framework, per evidence class and per kind, three sample edges per class,
  the UNLISTED files, RUNNER_SCRIPT_NEEDED if any; (3) AskUserQuestion per evidence class - accept all
  / review a sample / skip - and per kind reclassification (non-skippable); (4) the config table, confirmed
  once: test_command -> ./ait test with the previous value moved to a full: true suite runner (verify_build
  left alone unless the user says it is the suite, as in thinking_backend), gate_command_exit_contract
  += test_command, profiles default_gates += tests_pass and testmap_check, CLAUDE.md Testing paragraph
  when hand-maintained; (5) create the onboarding aitask (aitask_create.sh --batch, issue_type chore,
  labels testing testmap, the suggest JSON attached with ait attach) whose plan is the adopt commands
  and config writes, and continue into task-workflow (explore-style auto-continue honouring the profile)
  so the diff is reviewed at Step 8 and the first full run happens at Step 9; (6) after that run: costs
  --gate-timeout -> gates.yaml tests_pass.timeout_seconds, readiness -> LEVEL / NEXT, follow-up tasks
  for the next level with depends: on this one. Headless (remote) profile: level 0 + static-only level
  1 at --accept-min 0.95, no prompts, no policy flip. `--policy selected` re-entry: flips completion.mode
  only when READINESS_DECISION:ADMISSIBLE, records approved_by {who, at, statement} in config.yaml, one
  ait: commit (new)'
# new (n008)
component_qa_integration: 'aitask-qa reads the registry when aitestmap/ exists: test-discovery.md 3a-3c
  map each changed source through `ait testmap explain --source <path>` (edges, test-deps, scoped rows)
  and report GAP for a source with no edge and no test-dep, falling back to the naming-convention scan
  only when no registry exists; test-execution.md 4a runs the configured `./ait test` through aitask_run_project_command.sh
  test_command --task-id <id> (which exports AIT_GATE_TASK_ID so the run is the task''s selection), 4b
  runs named units through `ait test <path>`, 4c gains a REFUSED (host resources) row for verdict error
  / command_refused, and 4d''s coverage component uses registry edges rather than file-name matches; the
  health score''s Tests component treats REFUSED like SKIP (new)'
# modified from n006
component_reference_runners: 'Reference runners built into the binary as ait-testmap runner <name>: bash-file,
  pytest (junitxml; testmap:batch no honoured, the serial carve-out pinned by extending tests/test_serial_carveout_doc_drift.sh),
  go-test (per-file -run regex, -json), gradle-class (--tests <lowering> batch, one invocation per group_by
  group, JUnit XML inverted to ids through the list table, zero-match trap treated as a mechanism failure
  - n004''s method mode), suite (any command as one unit, optional child rows from a project children:
  post-processor), device (allocator handle); command:/cwd: overrides in runners.yaml; a project script
  of the same name shadows a builtin and explain shows which won; engine-test runs go-test over engine/;
  thinking_app ships tools/verification/testmap_runner.sh (screen-matrix: list from the two membership
  manifests + matrix_classes with an artifact column, run through screenshot-tests.sh unit-tests --tests)
  and wraps verify-active as a full: true suite runner whose child rows come from lib/screenshot-diff-set.sh
  (merged from n004 and n005; detect seeds the repository: bash-file for tests/**/test_*.sh, pytest for
  test_*.py / *_test.py (an aggregate runner script''s serial carve-out list becomes testmap:batch no
  lines), go-test per package from `go list`, gradle-class for src/test/**/*.kt|java, a kmp-sourceset
  detector mapping commonTest / androidHostTest to gradle-class unit runners (:<module>:jvmTest, testDebugUnitTest)
  and androidDeviceTest to the device runner (connectedDebugAndroidTest, needs: [emulator]), and a suite
  runner with full: true from project_config test_command or verify_build when the value looks like a
  test runner (n006 builtins; detector seeding new)'
# modified from n006
component_registry_loader: 'Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  plus axes.yaml into six tables (edges, scopes, areas, rules, waivers, axes); unit ids follow <path>[#<member>][@<variant>],
  with each member''s variants: list read from _scanned.yaml as written by scan --apply from runner list
  output and validated against the axis''s value set; owns: routing by glob for edges and rules and by
  area name for hand-declared scopes; write routing (scan --apply -> _scanned.yaml and _scoped.yaml, attribute
  -> observed.yaml, declare -> the owning hand file); observed axis sources merged at load may only widen;
  deterministic sorted writes only on change; check rules incl. STALE_PATH, UNSTAMPED past bootstrap under
  require_stamp, DEAD_SCOPE, DEAD_AXIS_SOURCE, UNKNOWN_VARIANT, UNCOVERED_VALUE, UNANNOTATED_MEMBER, DEAD_MEMBER,
  UNREGISTERED, UNMAPPED_ARTIFACT, KIND_MISMATCH|CONVERT_TO_SUITE above unit_covers_max, CONTRACT_MISMATCH;
  golden tests pin the merge rule and the id grammar (merged from n004 and n005; a seventh table, registry/adopted.yaml,
  written only by adopt: rows {test, source, signals, confidence, adopted_at, task} for every covers edge
  that entered the map through onboarding rather than a human annotation; a row is deleted when verify,
  stale --confirm-source or annotate re-stamps that edge, so the table is the set of edges no human has
  reviewed yet (n006 loader; adopted table new)'
# modified from n006
component_runner_contract: 'Runner contract and repository (internal/runner): describe (unit file|class|method|variant|suite,
  axis:, batch, needs, group_by: (n004), token_format:, filter_scope:, full:, children:, artifact_glob:
  (n004)), list as TSV <id> <kind> <lowering> [<artifact>] with member and variant ids, run --manifest
  with ids, lowerings and groups, results.jsonl per id with optional child rows under a suite parent,
  runner.json with per-group overhead rows, first-match bindings and per-test override, the builtin: scheme
  with command:/cwd: overrides and shadow-by-name, batching by (runner, group, resource set, batch flag),
  per-unit timeouts, units_expected/units_reported reconciliation per id with zero-reported-some-expected
  and no-registered-id as mechanism failures, exit contract 0/1/2/75 plus 64 (merged from n004 and n005;
  two repository keys added here: `subsumed_by: <suite>` on a runner whose units are the child rows of
  a full: true suite runner, so `run --all` executes the suite once and never the subsumed runner beside
  it (thinking_app: screen-matrix and gradle-class subsumed by verify-active), and `fallback_command:`
  on a suite runner - the pre-onboarding test_command or an equivalent detect derived - which `ait test
  --gate` runs when the engine binary is absent and config.yaml completion.engine_absent is fallback_command
  (n006 contract; two keys new)'
# inherited from n006 (unchanged)
component_scheduler_resources: 'Scheduler and resources (internal/sched): kinds mutex/semaphore/admission/allocator,
  scopes host/worktree/run, acquired_by planning; flock(2) slot files taken in canonical order; admission
  exec with 75 deferral and backoff to the run deadline; allocator exec with signal-safe release; goroutines
  under errgroup; batching (variants of one runner and resource set batch into one invocation per group_by
  group, so thinking_app''s whole selection is one Gradle run holding one heavy-run slot); broad_after_unit
  waves with variant-bearing units in the unit wave and, within a wave, invocations holding an admission
  resource ordered last (the ordering half of n004''s placement rule); config concurrency: serial|parallel
  defaulting to serial at bootstrap with --serial/--parallel overrides; the schedule report and its check
  half (inherited from n003; ordering refinement)'
# inherited from n006 (unchanged)
component_selector: 'Selector (internal/selectr, internal/changesurface): line-protocol intake via --changes
  - or a file, refusing on UNKNOWN:; the graded walk with select/implies/escalate rules; variant expansion
  (an edge to a unit selects every variant; an axis hit selects the variants carrying the facet value
  plus plain units carrying that testmap:axis coordinate; a symbol-narrowed axis hit selects only the
  member units whose closure names a changed key; hits union); test-dep at d1 when a changed file is in
  a unit''s own test-file closure, including reads globs; ESCALATE:<file>|<reason>|<runner-set> for a
  changed opaque file; scoped join at d1; ranking by distance then kind then cost per variant; invocation
  groups by the runner''s group_by with group cost overhead.p95 + sum of unit p95 (n004); stale marks
  from digest compare plus the per-variant evidence join; --include-stale; suite budget over broad rows
  and groups with DEFERRED lines and budget-exempt triggers and reads; cut knobs incl. --axis <axis>.<facet>=<v>
  (n004); --format lines|json|tokens; a prediction record with per-variant rows, facet reasons and groups;
  explain (merged from n004 and n005)'
# modified from n006
component_skill: 'Skills: (1) aitask-testmap (n006, unchanged: annotate a file / member / coordinate,
  axes, reads, attribute, verify, classify --suggest, tokens loop); (2) aitask-gate-testmap-fresh (n006,
  unchanged procedure gate); (3) NEW aitask-testmap-onboard - profile-aware stub + SKILL.md.j2, Claude
  Code first then Codex/OpenCode as separate tasks: preconditions (engine present, else the ait setup
  hint; aitestmap/ present -> refresh mode over tests added since the adopt ledger''s last row), `ait
  testmap detect` and `ait testmap suggest --all --json` read-only, a level proposal (0 runners+config,
  1 static-closure covers edges, 2 kinds/areas/reads/batch/resources, 3 axes + runner script scaffold)
  with counts and a sample per evidence class, then creates the onboarding aitask via aitask_create.sh
  --batch with the suggest JSON attached and continues into task-workflow whose plan is the adopt commands
  - so Step 8 reviews the annotation diff, Step 9''s tests_pass performs the FIRST FULL RUN that anchors
  every unit''s last_pass, and the archive commits it all under one (t<id>); batch confirmation is per
  evidence class (AskUserQuestion: accept all / review sample / skip), non-skippable for kind changes
  because a kind changes staleness semantics; config writes are confirmed once as a table (test_command
  -> ./ait test with the previous value moved to a full: true suite runner, gate_command_exit_contract
  += test_command, profiles default_gates += tests_pass and testmap_check, a hand-maintained CLAUDE.md
  Testing paragraph); headless profiles do level 0 plus static-only level 1 at --accept-min 0.95 with
  no prompts; a `--policy selected` re-entry flips the completion mode only on READINESS_DECISION:ADMISSIBLE
  and records approved_by. Every skill''s runtime knowledge of how to run tests is the seeded `## Running
  Tests` block plus `./ait test --howto`, never prose in a SKILL.md (n006 skills kept; onboarding skill
  new)'
# modified from n006
component_staleness_tool: 'Staleness tool (internal/stale): stale --task --changes - | --all prints SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION
  lines with %25/%7C encoding; a STALE row on a unit with variants carries a trailing |<unevidenced variants>
  field; --all adds one CHECK_STRUCTURAL:<n> summary line for the axis, member, variant and artifact rot
  that check owns; content states exit 0, --strict exits 1 on STALE_PATH; compares blob digests of the
  working tree only, consults the per-variant evidence join, adds rename hints and culprit task ids from
  git log --name-status -M when history is reachable; mutates stamps via --confirm, --confirm-source,
  --confirm-evidenced, --retarget through the rewriter with a re-scan of touched files (n005; n004''s
  structural classes re-sited to check; a STALE or EVIDENCED row whose edge has an adopted.yaml row carries
  `adopted(<signals> <confidence>)` in its DISPLAY line so the procedure gate knows it is confirming a
  machine-seeded claim, not a reviewed one (n006 tool; provenance display new)'
# inherited from n006 (unchanged)
component_suite_registry: 'Scoped-row registry and areas: registry/areas.yaml plus areas: blocks in hand
  files (seedable via areas --import-codemap); registry/_scoped.yaml rows {test, kind, runner, areas,
  globs, triggers, reads_from, needs, reviewed_at, line} where reads_from lists the helper files whose
  testmap:reads globs the row inherited; owns: by area name for hand-declared rows; the d1 join, kind
  ranking, suite budget (suite_budget_s default 600) with DEFERRED lines and budget-exempt triggers; check
  rules incl. DEAD_SCOPE and KIND_MISMATCH|CONVERT_TO_SUITE; ait testmap areas and classify --suggest,
  which flags a test file importing a reads-bearing helper (n005) and proposes a variant axis for an area-scoped
  suite whose classes share a stem and differ by a token that also names a directory or resource qualifier
  (n004); missing-trigger / area-too-narrow in attribute; a rule may select: a scoped test or a member
  (#*) by name (merged from n004 and n005)'
# new (n008)
component_test_entrypoint: '`ait test` = .aitask-scripts/aitask_test.sh, a ~120-line bash front over the
  n006 shim (aitask_testmap.sh): flags --task <id> | --gate | --all | --dirty | --explain | --howto |
  --tokens | --fresh-only | --budget-s <n> and positional <path|id>...; resolves MODE (completion iff
  --gate or AIT_GATE_TASK_ID), TASK (--task > AIT_GATE_TASK_ID > aitask/<name> branch > single own lock
  > NO_TASK), INTAKE (aitask_change_surface.sh list <id> piped; --dirty = every dirty path as TASK: rows,
  printed; --all; named paths: a listed test path is the unit, a source path is a one-file TASK: change
  set); runs select --include-stale (interactive: budget applies, DEFERRED printed; completion: deferred
  rows run) -> schedule -> run; with no aitestmap/ prints TESTMAP_ABSENT:<hint> and delegates to aitask_run_project_command.sh
  test_command; with the engine absent prints ENGINE_MISSING:<path>|<repair> and exits 3 interactively,
  or runs the suite runner''s fallback_command in completion mode when completion.engine_absent is fallback_command;
  completion mode applies the policy (full -> run --all with subsumed_by honoured; selected -> the task
  selection, demoted to full with POLICY_DEMOTED: when readiness is NOT_YET); prints UNANNOTATED_TEST:<path>|HINT
  for a listed test in the change surface with no testmap: block and no adopted row; exit 0 pass / 1 fail
  / 2 nothing ran / 3 framework error / 75 refused after deadline / 64 usage; dispatcher arm `test)` in
  ait, 5 permission touchpoints, tests/test_ait_test_entrypoint.sh against a fixture repo with AIT_TESTMAP_BIN
  pointing at a fake engine (new)'
# inherited from n006 (unchanged)
component_user_root: 'Per-user root: .aitask-scripts/lib/aitasks_home.sh exports AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}
  and aitasks_engine_dir <version|dev>, plus $AITASKS_HOME/.home.lock; sourced by the shim, aitask_setup.sh''s
  install_engine_binary, aitask_engine.sh and the verifiers; never falls back to ~/.aitask/; ait setup
  creates $AITASKS_HOME/engine/ with mode 0755 and prints AITASKS_HOME:<path> in its summary beside the
  venv line so both roots are visible; ait engine prune walks only $AITASKS_HOME/engine/v*/; test_aitasks_home.sh
  pins the default, the env override, and that no framework script under this feature names ~/.aitask/
  (inherited from n005)'
# inherited from n006 (unchanged)
component_variant_axes: 'Variant axes (internal/axes, read by registry, selectr, runner, cost): aitestmap/axes.yaml
  declares axes {name, facets[], values{value: {facet: v}}, sources{facet: {v: [globs]}}}; a runner''s
  describe names the axis its variants live on and a token_format; list emits <unit>@<value> ids; the
  selector joins changed paths to facet values through sources and selects the variants carrying them
  (reason axis(<axis>.<facet>=<v>) <- <path>) plus plain units carrying testmap:axis for that value (n004''s
  hand-declared coordinate), or every variant of a unit reached by an edge, dep, rule or test-dep; --axis
  <axis>.<facet>=<v> forces a facet (n004); costs, last_pass, evidence and score are per variant; check
  enforces DEAD_AXIS_SOURCE, UNKNOWN_VARIANT and UNCOVERED_VALUE (n004); observed sources widen only;
  the engine holds no project axis - the first consumer is thinking_app''s matrix axis with facets locale/direction/geometry
  over its 10 recording matrices (inherited from n005; n004 bridges)'
# new (n008)
component_workflow_seam: 'The concrete edits: task-workflow SKILL.md.j2 Step 7 gains one paragraph after
  `Follow the approved plan` - run ./ait test as the implementation test loop, answer UNANNOTATED_TEST
  with annotate --suggest, never call the test tool directly (rendered into every profile; goldens regenerated);
  build-verification.md gains a branch for verdict error / reason command_refused (host refused resources:
  do not fix code, do not record pass, re-run later - the entrypoint already deferred to its deadline);
  lib/gate_verifier_lib.sh run_project_command_key() gains the 75 -> error row for opted-in keys and exports
  AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command, and aitask_run_project_command.sh --task-id exports
  the former; gates_reference.yaml adds testmap_fresh and testmap_check (unlocks: [tests_pass]) and no
  testmap_run; the project''s profiles gain the two gates in default_gates via onboarding; the ait dispatcher
  gains `test)`; aidocs/framework/aitasks_extension_points.md gains `Adding a test-framework detector`;
  tests/test_gate_verifiers.sh covers 75 and the env export, tests/test_serial_carveout_doc_drift.sh is
  extended per n006, tests/test_no_unscoped_task_commit.sh is unaffected because the skill commits through
  aitask_task_commit.sh (new)'
# new (n008)
requirements_agent_instructions_seeded: 'No code agent learns how to run tests from the repository at
  session start: the shared agent-instructions seed (seed/aitasks_agent_instructions.seed.md) gains a
  `## Running Tests` section - always `./ait test`, never the test tool directly; `./ait test <path>`
  for one unit; `./ait test --all`; `./ait test --howto` for project specifics; answer UNANNOTATED_TEST
  with `./ait testmap annotate --suggest`; the exit-code table - which ait setup already installs into
  CLAUDE.md''s >>>aitasks block, AGENTS.md, .codex/instructions.md and the OpenCode mirror through assemble_aitasks_instructions();
  the section is written before onboarding because `ait test` is correct in every repo state; a hand-maintained
  CLAUDE.md (this repository''s) is edited by the onboarding task instead; project specifics live only
  in --howto''s computed output (new)'
# modified from n006
requirements_agent_skill: 'Agent skills teach agents how to keep the map current as they write code and
  tests - annotate a file, a testmap:unit member (--from-body) or a coordinate (testmap:axis), declare
  an axis source, put testmap:reads on a tree-scanning helper, axes --explain, attribute, verify, classify
  --suggest, confirm or retarget stamps in the procedure gate, drive a render loop from --format tokens
  (n006) - AND, new here, one skill onboards a project''s EXISTING tests into the architecture without
  the user configuring anything: aitask-testmap-onboard runs detect / suggest / adopt as an ordinary aitask
  so the annotation diff is reviewed and committed under a (t<id>), confirms edges in batches grouped
  by evidence class rather than per file, and leaves the project with runners.yaml, config.yaml, a completion
  policy, test_command: ./ait test, default_gates and an agent-instructions block; the daily-use surface
  an agent must know shrinks to `./ait test`, `./ait test --howto` and `./ait testmap annotate --suggest
  <new test>` (n006 skills kept; onboarding and the instruction seed are new)'
# inherited from n006 (unchanged)
requirements_annotation_freshness: Every unit coverage annotation carries the date and a blob digest of
  the covered source at confirmation, scoped to the member block where the unit is a member; committed
  last_pass anchors, per variant where a unit has variants, let stale prove a test already passed against
  a changed source's current content (EVIDENCED only when every reached variant is anchored) so most hot-source
  churn needs no rewrite; a procedure gate at the post-implementation step hands the report to an agent
  that fixes annotations before the task commit (inherited from n005)
# inherited from n006 (unchanged)
requirements_annotation_staleness: A stale verb reports, for a task's change set or repo-wide, STALE_PATH
  (deleted or renamed source, fail-closed), STALE (content changed, no evidence on every reached variant,
  the unevidenced variants named), EVIDENCED, UNSTAMPED, STALE_AREA and opt-in REVIEW_DUE rows in the
  framework's fixed line protocol, plus one CHECK_STRUCTURAL:<n> summary line on --all; structural rot
  on axes, members, variants and artifacts is check's, not stale's; digest comparison needs no git history,
  evidence only removes nags (n005; n004's axis classes re-sited to check)
# inherited from n006 (unchanged)
requirements_axis_product_selection: 'A project whose tests form a product of named facets (thinking_app:
  49 screens x 10 matrices where a matrix is locale x direction x geometry; aitasks: skill x profile x
  agent goldens) declares the axis with its facets, values and facet-valued source globs, and lets the
  engine select exact variants - an axis-source hit selects the variants carrying the facet value, any
  other hit selects every variant, hits union - instead of choosing between thousands of hand edges and
  one all-or-nothing suite scope; a source matching no axis source reaches units only through edges and
  dependencies, which select every variant, the fail-safe direction (n004''s requirement, realised by
  n005''s mechanism; intersection reduces to the facet join on every single-file case)'
# inherited from n006 (unchanged)
requirements_broad_test_handling: 'Scoped rows are ranked after unit tests at equal distance, selected
  under an explicit suite budget that prints every DEFERRED cut, scheduled only after the unit wave is
  green (broad_after_unit), widened by attribute on a full-run miss, and drift-flagged by evidence (STALE_AREA)
  rather than by calendar; a suite row marked full: true with a children: post-processor anchors registered
  ids on every run (inherited)'
# inherited from n006 (unchanged)
requirements_cost_tracking: Tracks cost per test unit and per variant, keyed by host class, using Welford's
  online update (n, mean, standard deviation, p95, last), plus a last_pass {sha, at, run_id} anchor and
  a flake rate per id; per-invocation overhead rows are a first-class input keyed by invocation group,
  so a selection's estimate is the sum over groups of overhead.p95 + the marginal p95 of each selected
  id - a second method in a booted Robolectric class costs its per-unit mean, not another boot (n005 rows,
  n004 group costing)
# inherited from n006 (unchanged)
requirements_dev_rebuild_from_source: A framework developer rebuilds the engine with one command (ait
  engine build) through the same engine/build.sh that CI uses, into $AITASKS_HOME/engine/dev/ which the
  shim selects via AIT_ENGINE=dev (version must read <V>-dev+<sha>); ait engine cross produces the CI
  matrix locally, byte-identical (inherited, root corrected)
# inherited from n006 (unchanged)
requirements_engine_dev_regeneration: The GOOS/GOARCH matrix, CGO_ENABLED=0 and ldflags live in one script
  (engine/build.sh) shared by release CI, ait engine build and ait engine cross; ait engine test runs
  go vet and go test; ait engine prune removes versions under $AITASKS_HOME/engine/ that no registered
  project is on; ait engine home reports the root, legacy tenants and symlink state and performs the migration
  on --migrate (merged)
# inherited from n006 (unchanged)
requirements_engine_packaging: ait setup and ait upgrade (through install.sh's --source-only path) install
  the host's binary under $AITASKS_HOME/engine/v<VERSION>/ with checksum verification, a .sha256 sidecar
  and a version --json self-check that also prints ENGINE:<path>; fallbacks --local-engine, --engine-from-source,
  AIT_TESTMAP_BIN; opt-out --no-testmap / AIT_TESTMAP_FETCH=0; setup prints AITASKS_HOME:<path> and, when
  legacy tenants exist, HOME_LEGACY:<path>|run 'ait engine home --migrate' and continues (merged)
# inherited from n006 (unchanged)
requirements_feedback_loop: 'Learns from failures the map did not predict via a score/attribute feedback
  loop; every full run (run --all or a full: true suite runner) automatically scores the newest prediction
  record for the same task and prints PREDICTION_FALSE_NEGATIVES:<n> plus one PREDICTION_MISSED:<id> line
  per miss, appending to a committed costs/predictions.yaml; attribute records an observed edge for a
  unit or member, an observed axis source for a facet value (widen only, never narrow), and an observed
  trigger or area member for a broad test, merged into the registry at load (n005 automatic score, n004
  widen-only rule)'
# inherited from n006 (unchanged)
requirements_framework_home_name: 'The framework is named aitasks, so every path it owns under the user''s
  home should be ~/.aitasks - the engine installs there now, and the legacy ~/.aitask tree is migrated
  by an explicit verb, ait engine home --migrate (flock, per-entry rename, rmdir, compatibility symlink;
  known set corrected to include pypy_venv), with ait setup printing a HOME_LEGACY: hint in this release
  and a named follow-up flipping the default once the verb has passed a real install.sh --dir test (n004''s
  principle and mechanism, n005''s default)'
# modified from n006
requirements_gate_enforcement: 'Enforced by gates so the map cannot rot silently: testmap_fresh (procedure,
  before the task commit), testmap_check (machine, fails STALE_PATH on its own and the structural rows
  under --strict past bootstrap; unlocks: [tests_pass]) and ONE completion test gate - the existing tests_pass,
  whose test_command is `./ait test`, which runs the whole registry or the task''s selection according
  to the committed completion policy in aitestmap/config.yaml (full by default; selected only after `ait
  testmap readiness` reports ADMISSIBLE and a human records approved_by; demoted back to full at run time
  if readiness regresses). testmap_run is retired as a gate name: its verifier logic is `ait test --gate`,
  its blocks_dependents and max_retries: 1 are tests_pass''s own, and its 1800 s timeout becomes a per-project
  tests_pass.timeout_seconds written from the measured full-run p95 (`ait testmap costs --gate-timeout`).
  A command key opted into gate_command_exit_contract now also reads exit 75 as verifier error (3), never
  fail and never skip (n006 gates, re-cut to one completion gate; 75 mapping new)'
# inherited from n006 (unchanged)
requirements_generic_across_projects: 'A framework feature, generic across projects (aitasks, thinking_app,
  thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation between source files and test
  units - including a project''s own finer subdivision of a test file (thinking_app''s screen fixtures
  crossed with its recording matrices) expressed through member units and declared variant axes, with
  the project''s runner lowering ids to what it executes, never project-specific code in the engine (merged:
  n005 model, n004 fail-safe wording)'
# inherited from n006 (unchanged)
requirements_go_engine: Scan, check, select and stale finish in well under a second on a ~720-test repo
  - and select stays under 250 ms warm on thinking_app's ~300 golden variants over 49 members plus ~370
  JVM classes with axis expansion, never executing a runner - and the scheduler runs concurrently with
  real cross-process locks, so selection overhead stays negligible against the shortest test and check
  can run at every commit step (n005 target; n004's 2,500-row cell target has no referent in the merged
  design)
# inherited from n006 (unchanged)
requirements_go_engine_and_cli: The engine and CLI are one static Go binary (ait-testmap) built from engine/;
  bash keeps only the dispatcher arm, the shim that resolves the binary under $AITASKS_HOME and pipes
  the change surface in, the two gate verifier shells, lib/aitasks_home.sh, the ait engine developer verbs
  (incl. home [--migrate]) and any project-local runner or scanner scripts; the binary never invokes aitask_*.sh
  and never needs its own install root (n005; n004's ait engine home verb added, its internal/home dropped)
# inherited from n006 (unchanged)
requirements_high_level_tests_separate: Integration, e2e and device tests declare areas, scope globs or
  budget-exempt trigger globs instead of covers, live in registry/_scoped.yaml beside the unit table,
  join the ranked list at distance 1 as sinks, and never enter the per-file edge graph or its digest staleness;
  a helper file may declare testmap:reads <glob> so every unit whose test-file closure contains it inherits
  the glob as a trigger; variant-bearing units are unit kind and never scoped rows (inherited from n005)
# new (n008)
requirements_onboarding_existing_tests: 'A skill onboards a project''s existing tests into the architecture
  without the user writing a registry by hand, in four graded levels each landing as one reviewed aitask:
  level 0 detects test frameworks and writes runners.yaml bindings, config.yaml, resources.yaml and areas.yaml
  (the universe exists, `ait test --all` runs it, selection works through the test-file static closure,
  nothing is stamped); level 1 adopts covers edges from the suggest join - static closure as primary evidence,
  naming conventions and (t<id>) co-change as corroboration, helpers split from subjects by root and fan-in
  - written as stamped annotation blocks through the engine''s rewriter with provenance in registry/adopted.yaml;
  level 2 classifies broad tests as scoped rows over codemap areas, adds testmap:reads to tree-scanning
  helpers, testmap:batch no from serial lists, and declares detected locks as resources; level 3 declares
  axes and scaffolds a project runner script where the grid heuristic finds a product space. Rewriting
  a test means inserting comment lines only; the skill proposes and never performs code restructuring
  (new)'
# inherited from n006 (unchanged)
requirements_platform_binaries_in_release: Release CI builds and attaches checksummed binaries for linux/darwin
  x amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt) from one engine job that
  also runs go vet and go test; a new engine-check.yml runs the same on push/PR for engine/**; tarball
  and package-manager artifacts stay architecture-independent (inherited)
# inherited from n006 (unchanged)
requirements_reason_per_selected_test: Translates a task's change set into one ranked list of tests that
  must run, with a reason on every line - edge, dep, rule, axis(matrix.locale=ru)[keys] <- <source>, test-dep
  <helper>, reads(<helper>) <- <path>, ESCALATE:<file>|<reason> for an opaque source, the facet value
  or @* that placed each variant row (n004), a stale mark when a selecting edge's digest no longer matches
  and no run evidence covers that variant, an invocation group and its cost, and an explicit DEFERRED
  line for every broad row or group the budget cut (merged)
# inherited from n006 (unchanged)
requirements_screen_locale_subdivision: 'A test unit may be a member of a file (<path>#<member>, opened
  by a testmap:unit block) and may carry variants on a declared axis (<unit>@<variant>); a source change
  reaches a unit on every variant, or reaches an axis facet value (matrix.locale=ru) and thereby only
  the variants carrying it plus any plain unit carrying testmap:axis matrix.locale=ru; the runner lowers
  a variant id to what it executes (thinking_app: <Class>.<method> per matrix through matrix_classes /
  preview_resolve_token) so the engine never learns Gradle, Roborazzi or the membership manifests (inherited
  from n005; testmap:axis from n004)'
# inherited from n006 (unchanged)
requirements_standard_runner_contract: 'Runs selected tests through project-defined runners under a standard
  contract (describe/list/run verbs); describe declares unit (file|class|method|variant|suite), axis,
  group_by, token_format, filter_scope, full, children and artifact_glob; list emits TSV rows <id> <kind>
  <lowering> [<artifact>] and may emit member and variant ids; run receives ids with lowerings and groups,
  results.jsonl reports per id (a batch runner inverts JUnit classname/name back to ids through its own
  list table), runner.json carries per-group overhead, and a unit: suite runner may emit child rows keyed
  to registered ids; reference runners are built into the engine as builtin:<name> with command:/cwd:
  overrides, and a project script of the same name shadows a builtin (merged from n004 and n005)'
# inherited from n006 (unchanged)
requirements_user_root: Every per-user artifact this feature installs lives under the framework's own
  root, ~/.aitasks/ (env override AITASKS_HOME, one owner file lib/aitasks_home.sh, no fallback to ~/.aitask),
  beside the existing ~/.config/aitasks/ and ~/.cache/aitasks/ roots; the engine is the root's first tenant
  at $AITASKS_HOME/engine/v<VERSION>/ and $AITASKS_HOME/engine/dev/; the legacy ~/.aitask/ tenants (venv,
  pypy_venv, python, bin, uv, dev_tier, update_check) are neither moved nor read by this feature's default
  path (inherited from n005)
# new (n008)
requirements_workflow_seam_is_data: 'The integration with task-workflow, aitask-qa, aitask-pickrem, aitask-pickweb
  and aitask-resume adds no workflow step: the seam is project_config.yaml (test_command: ./ait test,
  gate_command_exit_contract: [test_command]), the project''s profiles (default_gates += tests_pass, testmap_check),
  gates.yaml (testmap_check unlocks tests_pass; tests_pass.timeout_seconds from the ledger), the completion
  policy in aitestmap/config.yaml, and two environment variables the verifier already knows (AIT_GATE_TASK_ID,
  AIT_GATE_RUN_ID); the prose changes are one Step-7 paragraph naming `./ait test` as the implementation
  test loop and the UNANNOTATED_TEST answer, one branch in build-verification.md for verdict error / command_refused,
  and aitask-qa''s discovery reading the registry instead of naming conventions when aitestmap/ exists;
  Step 9''s verify block, the merge broker, archival and the gate orchestrator are untouched (new)'
# new (n008)
requirements_zero_config_entrypoint: 'One user-facing verb, `ait test`, is the only way an agent or a
  person runs tests in any aitasks project, at every stage of adoption: with no aitestmap/ it runs project_config.yaml
  test_command through aitask_run_project_command.sh and prints the onboarding hint; with a registry it
  resolves mode (completion when --gate or AIT_GATE_TASK_ID is set, interactive otherwise), task (--task
  > AIT_GATE_TASK_ID > the aitask/<task_name> branch of the current worktree > the single Implementing
  lock this user holds on this host > NO_TASK with the three ways out) and intake (change surface for
  a task, --dirty, --all, or named paths where a source path is a one-file change set) by itself; it prints
  MODE / TASK / INTAKE / SELECTED / RUN / RESULT lines, UNANNOTATED_TEST:<path> for a new test in the
  change surface, and exits 0 / 1 / 2 / 3 / 75 / 64; and `ait test --howto` prints the project''s runners,
  kinds, resources, completion policy and the three commands an agent needs, computed from runners.yaml
  and config.yaml so it cannot rot (new)'
# inherited from n006 (unchanged)
tradeoff_area_glob_coarseness: 'Disadvantage: area and scope globs are coarser than edges - a broad area
  over-selects its tests on every edit inside it and a scoped test depending on a file outside its scope
  is under-selected until a full run scores it; mitigated by the suite budget with explicit DEFERRED lines,
  budget-exempt triggers and reads globs for known sharp edges, and the missing-trigger / area-too-narrow
  attribution path (inherited)'
# inherited from n006 (unchanged)
tradeoff_attribution_risk: 'Risk: an agent that edits sources without attributing produces a map that
  looks current and is not; narrowed - such a source shows as STALE in the next task touching it and as
  a stale mark on every selection, and in a repo that runs a full suite at completion every miss is counted
  by the automatic score within one task - but a new coupling with no edge at all is still only caught
  on a full run (inherited)'
# inherited from n006 (unchanged)
tradeoff_autonomous_confirmation_weak: 'Risk: treating a green test as evidence that a coverage claim
  still holds is weaker than review; narrowed - the only autonomous confirmation is --confirm-evidenced,
  which requires a pass on every reached variant whose tree held the current bytes of the specific source,
  records confirmed_by: <run_id>, and is re-opened by a later score miss; a STALE row is never confirmed
  without a human (inherited from n005)'
# inherited from n006 (unchanged)
tradeoff_axis_declaration_burden: 'Disadvantage: axes are a third authoring surface, and a project that
  declares them wrongly gets confidently wrong selection. Concretely: thinking_app must declare ten matrix
  values with three facets, four locale source-glob sets, one values/** rule, one runner script (list/describe/run/children
  over its existing routing) and one testmap:axis line per non-capturing coordinate test. Mitigated by
  making membership declarative and checkable - DEAD_AXIS_SOURCE fails a source glob that matches nothing,
  UNKNOWN_VARIANT a listed variant outside the axis, UNCOVERED_VALUE a declared value no runner lists,
  and axes --explain <path> answers why one file landed where it did before anything is trusted; and by
  an undeclared source reaching every variant, so an incomplete axis over-selects rather than under-selects
  (n004''s burden, restated for the merged mechanism)'
# inherited from n006 (unchanged)
tradeoff_axis_projection_coarseness: 'Disadvantage: the default axis join is file-level - a one-key edit
  to values-ru/strings.xml selects every enrolled screen on both ru matrices (about 65 variants) rather
  than the screens naming that key; sound but 2/10 of the matrices rather than 1/50 of the screens; mitigated
  by the opt-in android-res symbol scanner (keys changed -> referencing Kotlin files -> member units),
  by select --format tokens feeding the project''s own render loop so the over-selection costs a preview
  rather than a gate, and by the group-costed budget (inherited from n005)'
# inherited from n006 (unchanged)
tradeoff_batch_misreport_risk: 'Risk: a batch runner that misreports per-unit results corrupts attribution,
  cost and evidence (a false pass could manufacture an EVIDENCED row); two more places to misreport than
  n003 - the JUnit classname/name to variant-id inversion, and the zero-match trap at method granularity
  where a Gradle --tests filter matching nothing exits 0 with zero tests; mitigated by units_expected/units_reported
  reconciliation per id, a row inverting to no registered id and units_reported == 0 with units_expected
  > 0 both being mechanism failures, and no line from an invocation with a cause ever anchoring (merged
  from n004 and n005)'
# inherited from n006 (unchanged)
tradeoff_broad_scope_coarseness: 'Disadvantage: a test scoped to a large area is selected for any change
  inside it; mitigated by ranking last at its distance, running only after a green unit wave, being cut
  first by the suite budget with the cut printed as DEFERRED, and the cost visible in schedule (inherited)'
# new (n008)
tradeoff_bulk_confirmation_granularity: 'Risk: confirming edges per evidence class (398 static edges in
  one answer) trades review depth for feasibility - per-file review of 720 files is not something anyone
  does, and a class-level yes accepts every member; mitigated by the three-sample display, `review a sample`
  drawing ten random members with their signals, --accept-min raising the bar, --scope <glob> onboarding
  one area per task, the adopted.yaml provenance so nothing pretends to be reviewed, and kind reclassifications
  being confirmed individually because a wrong kind changes staleness semantics rather than selection
  breadth (new)'
# inherited from n006 (unchanged)
tradeoff_cell_table_size: 'Disadvantage, inverted: instead of n004''s ~2,500 generated cell rows that
  churn whenever a screen or matrix is added, _scanned.yaml carries 49 member rows with a variants: list
  of at most ten values; the price is that scan and check exec each runner''s list (thinking_app: a bash
  script reading two manifests, milliseconds) and that a matrix added to the manifests is invisible to
  select until the next scan --apply - which check reports as UNKNOWN_VARIANT/UNCOVERED_VALUE drift the
  same day. Enumerating at every select was rejected for the reason n004 gave: it would put a build-adjacent
  exec on the hot path of every gate (n004''s tradeoff, re-cut for the runner-list universe)'
# inherited from n006 (unchanged)
tradeoff_compiled_component_cost: 'Disadvantage: the framework gains a compiled component - contributors
  touching the engine need Go, a release fails if go test fails, install gains a fetch and checksum step;
  mitigated by a single build.sh matrix, ait engine build, and the engine being optional until a testmap
  gate is enabled (inherited)'
# inherited from n006 (unchanged)
tradeoff_computed_vs_prose: 'Advantage: selection is computed, explained and scored rather than remembered;
  blast radius becomes data instead of prose - thinking_app''s ''a localized screen change may use preview,
  a shared component must run the full gate'' rule becomes an axis join, an import-scanner fan-out and
  an ESCALATE: line, each printed with the path that caused it and the facet value that placed each variant
  (merged)'
# new (n008)
tradeoff_dispatcher_verb_added: 'Disadvantage: `ait test` is a new top-level dispatcher verb beside `ait
  testmap`, two surfaces for one engine; justified by the extension-points rule (a human plausibly types
  `ait test`, and the seed instruction needs one memorable verb), kept thin (mode / task / intake / policy
  / fallback resolution only, everything else delegated to the n006 shim), and `ait testmap` stays the
  maintainer surface for annotate / scan / check / stale / axes; removing a verb later is a breaking change,
  so --howto documents `ait test` as the stable one (new)'
# inherited from n006 (unchanged)
tradeoff_engine_absent_on_host: 'Risk: an unsigned macOS binary or a blocked download leaves a host without
  an engine; mitigated by ENGINE_MISSING naming the $AITASKS_HOME path and repair verb, --engine-from-source
  and --local-engine fallbacks, and the testmap gates exiting 3 (error), never skip, when the engine is
  absent (inherited)'
# inherited from n006 (unchanged)
tradeoff_engine_speed_enables_per_task_use: 'Advantage: sub-second select/check/stale on a 720-test repo,
  and sub-250 ms select over 300 variants with axis expansion, makes selection overhead negligible against
  the shortest test and lets check run at every commit step; the facet join is one glob match per changed
  file per facet and one set test per member, select never execs a runner, and a bash+Python engine would
  spend seconds in start-up and YAML parsing first (merged)'
# inherited from n006 (unchanged)
tradeoff_engine_version_skew: 'Disadvantage: one user with several projects on different framework versions
  keeps several ~10 MB binaries under $AITASKS_HOME/engine/; mitigated by exact-version resolution in
  the shim (never newest-wins) and ait engine prune against the project registry, never a count-based
  prune (inherited, root corrected)'
# inherited from n006 (unchanged)
tradeoff_evidence_requires_reachable_history: 'Risk: the evidence join can only suppress a STALE row when
  the anchoring commit is reachable, so a depth-1 CI clone or a fresh shallow worktree sees the precise
  digest verdict with no self-healing; the safe direction, and the reason stale --strict fails only on
  STALE_PATH (structural rot is check''s); a repo-wide stale --all --strict job should run on a full clone
  or accept STALE noise (inherited)'
# modified from n006
tradeoff_fail_closed_bootstrap_cost: 'Disadvantage: fail-closed enforcement means bootstrapping each repo
  requires a waiver pass before testmap_check can be enabled, a first green full run before require_stamp
  and --strict, a green runner list before structural rules can fail, and min_scored_full_runs before
  the completion policy may flip to selected (n006); narrowed here by making the bootstrap order a single
  aitask that the onboarding skill creates and runs - detect and suggest are read-only, adopt at level
  0 writes only registry files, the onboarding task''s own tests_pass gate IS the first full run that
  anchors every unit, bootstrap_until is set to adoption day + 90 by adopt, and readiness prints LEVEL
  / NEXT so the remaining steps are a list rather than a procedure someone must remember; the cost that
  remains is real - a repo is at level 0 (runner-bound, closure-selected, unstamped) until a human accepts
  level 1 - and headless profiles stop there plus static-only edges (n006 tradeoff, narrowed by onboarding)'
# new (n008)
tradeoff_fallback_runs_more: 'Disadvantage: when the engine binary is absent in completion mode and the
  project chose engine_absent: fallback_command (the Claude Code Web lane, where ait setup never ran),
  `ait test --gate` runs the whole pre-onboarding suite command - never less than before onboarding, but
  never selective either, and with no per-unit results, no evidence anchors and no scoring; mitigated
  by the default being error (the gate reads error, not pass), by ENGINE_MISSING naming the path and repair
  verb, and by the fallback being visible as MODE:fallback in the result (new)'
# inherited from n006 (unchanged)
tradeoff_flaky_pass_anchors: 'Risk: a flaky pass anchors evidence as surely as a real one; mitigated by
  per-run status in the ledger so costs exposes a flake rate per id, and an id above flake_threshold is
  excluded from the evidence join (inherited)'
# inherited from n006 (unchanged)
tradeoff_home_migration_window: 'Risk: when run, the migration has a sub-millisecond window between rmdir
  ~/.aitask and ln -s during which a concurrent process that hardcodes the legacy path (rather than using
  the resolver) sees ENOENT; narrowed by the flock, by symlinking immediately after the rmdir, and by
  refusing while another ait holds the home lock - not eliminated. Measured surface: 8 framework code
  files with 35 references (21 in aitask_setup.sh), 20 test files, 18 doc files, the venv''s absolute
  shebangs and two symlink trees - none rewritten by the migration, all resolving through the symlink.
  And its refusal cases are the ones a designer does not see on their own host: n004''s known-entry set
  lacked pypy_venv, which this host carries. Both are why the verb is explicit in this release and the
  default flip waits for the real-install test (n004''s risk, re-measured and scoped to the verb)'
# inherited from n006 (unchanged)
tradeoff_intersection_can_underselect: 'Risk: an axis-source hit is sharper than a file edge - it selects
  only the variants carrying the facet value - and is therefore capable of missing a real coupling that
  a plain covers edge (every variant) would have caught, e.g. a font family assigned to the wrong locale''s
  glob. Narrowed structurally: under-selection needs an explicit, reviewable wrong glob, never an omission,
  because a file matching no axis source reaches every variant; score on a full run raises missing-axis-source;
  observed sources may only widen; --axis and --format tokens with preview are the reviewer''s escape;
  and every variant row prints the facet value that placed it, so what a sharp selection excluded is visible
  in the prediction record (n004''s risk, restated for the facet join)'
# inherited from n006 (unchanged)
tradeoff_member_annotation_drift: 'Risk: a member unit''s annotation lives in a block keyed by name (testmap:unit
  Welcome) and the runner''s list keys the same member by another artifact (the golden manifest''s Welcome_<matrix>.png);
  a rename on one side orphans the other; mitigated by check reporting a listed member with no block (UNANNOTATED_MEMBER)
  and a block with no listed member (DEAD_MEMBER), both fail-closed, by scan --apply refusing rather than
  guessing, and by thinking_app''s own manifest/@Test drift loop failing the rename on its side (inherited
  from n005)'
# inherited from n006 (unchanged)
tradeoff_noarch_packages_preserved: 'Advantage: Homebrew, AUR, .deb, .rpm and the tarball ship nothing
  compiled; the per-arch concern is contained in one release job and one setup function (inherited)'
# new (n008)
tradeoff_one_gate_not_two: 'Advantage: one completion test gate whose behaviour is a committed policy,
  instead of n006''s tests_pass (full) beside testmap_run (selected) - an agent learns one command and
  one gate, a project keeps its existing tests_pass declaration and timeout key, the legacy no-gates Step-9
  path and aitask-qa reach the selective lane through the same test_command, and the policy flip is one
  line a human writes after readiness rather than a second gate to declare. Disadvantage: the gate''s
  meaning now depends on config.yaml, so a reader of a ledger `tests_pass: pass` must look at the run''s
  MODE line to know whether the whole suite ran; mitigated by the verifier result= field carrying MODE:<full|selected>|<n
  units>|<policy>, by POLICY_DEMOTED being loud, and by readiness printing what --gate would run now (new)'
# inherited from n006 (unchanged)
tradeoff_real_scheduler: 'Advantage: goroutines plus flock(2) give correct cross-worktree contention and
  a critical-path report; the shell suite and the pytest lane get the enforced do-not-overlap that is
  only a comment today; a variant batch is one Gradle invocation holding one heavy-run slot, ordered after
  cheaper invocations in its wave; thinking_app''s heavy-run lock and emulator allocator become declared
  resources the schedule report can reason about (merged)'
# inherited from n006 (unchanged)
tradeoff_registry_directory_complexity: 'Disadvantage: a merged registry directory needs more CLI logic
  than a single file would - now six tables, two generated files, an id grammar with member and variant
  fragments and an artifact column in list; kept to one directory with one merge rule in one Go package
  with golden tests, no second plugin directory or generated cell table, and the axis table is empty for
  every project that declares none (merged)'
# inherited from n006 (unchanged)
tradeoff_resource_declaration_completeness: 'Risk: declared resources are only as complete as the declarations;
  an undeclared interference is invisible until a full run or a probe finds it; serial-by-default at bootstrap
  means declarations are reviewed in the schedule report before concurrency is trusted (inherited)'
# new (n008)
tradeoff_seed_precision: 'Risk: an adopted covers edge is a machine claim wearing a human annotation''s
  clothes - the static closure says the test executes the script, not that it verifies it, and a test
  that drives three scripts to set up one adopts edges to all three. Narrowed: adopted edges are recorded
  in registry/adopted.yaml and displayed as adopted(...) in stale and explain until a human re-stamps
  them, readiness reports ADOPTED_UNREVIEWED, the over-claim direction only over-selects (a setup script''s
  change runs the test needlessly), the acceptance threshold 0.85 keeps convention-only and co-change-only
  edges out, and the skill shows three samples per evidence class before accepting a class; what it cannot
  do is invent a subject the closure does not contain - such a coupling is caught only by a full run''s
  score, as in n006 (new)'
# inherited from n006 (unchanged)
tradeoff_setup_network_fetch: 'Disadvantage: ait setup gains the framework''s first self-downloaded release
  asset; mitigated by reusing the CDN URL family install.sh already uses, SHA256SUMS verification, the
  .sha256 sidecar, --no-testmap / AIT_TESTMAP_FETCH=0, the shim never fetching on its own, and setup never
  depending on the binary for anything else (inherited)'
# inherited from n006 (unchanged)
tradeoff_split_home_rejected: 'Disadvantage of the alternative n005 took as permanent and n004 rejected:
  installing only the engine at ~/.aitasks/engine/ and leaving venv, pypy_venv, python, bin and uv at
  ~/.aitask/ satisfies the mandate literally with zero migration risk, but leaves a user with two dot-directories
  one character apart holding halves of one install, which ait setup --repair, ait engine prune, backup
  advice and every doc page would have to explain forever. Chosen: the split as the transition, not the
  end state - the migration is designed, shipped as an explicit verb and testable now, with the symlink
  making it reversible (rm ~/.aitask && mv ~/.aitasks ~/.aitask), and becomes ait setup''s default in
  a named follow-up (n004''s argument, n005''s timing)'
# modified from n006
tradeoff_stamp_churn: 'Disadvantage: confirming stamps rewrites test files, so a source named by 72 tests
  could yield a 72-file diff; mitigated - EVIDENCED rows need no rewrite until someone chooses --confirm-evidenced,
  --confirm-source makes a deliberate re-stamp one commit, only confirmation rewrites, member blocks keep
  a screen''s stamps in one file (ScreenFixtures.kt) so thinking_app''s fan-out is a one-file diff, variants
  carry no stamp at all, and KIND_MISMATCH nudges fan-out toward a scope or an axis (merged; onboarding
  adds one bulk diff per level - level 1 on aitasks touches ~720 test files with one to eight comment
  lines each - mitigated by --scope <glob> to adopt per area across several tasks, by the diff being comments
  only (git blame -w and every test runner ignore it), by adopt refusing files dirty outside the task''s
  change surface so it never mixes with concurrent work, and by the onboarding task being an ordinary
  reviewed (t<id>) commit rather than a hidden write (merged; bulk-adoption clause new)'
# inherited from n006 (unchanged)
tradeoff_static_scanner_overselection: 'Disadvantage: static scanners overselect on hot files and cannot
  see runtime coupling; a shared component (thinking_app''s ui/components/*) fans out to most screens
  on every matrix, which is the correct answer and close to a full run, and ScreenFixtures.kt reaches
  every member because the change surface is file-level; kind ranking, the suite budget and --budget-s
  trim scoped rows first, the android-res symbol scanner narrows a catalog edit to the screens naming
  the changed keys, a project scanner plugin can narrow a hot resource file, and hunk-level attribution
  inside a member file is the later narrowing tool (merged)'
# inherited from n006 (unchanged)
tradeoff_strict_version_handshake: 'Risk: the binary must match .aitask-scripts/VERSION exactly, so an
  ait upgrade on a host that cannot fetch leaves ait testmap refusing to run until a matching binary is
  supplied; intended fail-closed behaviour, and the error names the fix (ait setup, AIT_TESTMAP_BIN, ait
  engine build) and the $AITASKS_HOME path it looked in (inherited)'
# inherited from n006 (unchanged)
tradeoff_two_toolchains: 'Disadvantage: bash and Go in one framework; mitigated by the boundary rule (parse/walk/match/digest/schedule
  in Go; gate ledger, task file and shell environment in bash; builtins exec configured commands and never
  source shell state), the engine-check.yml job, and Go source confined to engine/ and excluded from the
  tarball so target projects never need Go (inherited)'
# inherited from n006 (unchanged)
tradeoff_two_user_roots: 'Disadvantage: until ait engine home --migrate is run, a host carries ~/.aitask/
  (venv, pypy_venv, python, bin, uv) and ~/.aitasks/ (engine) side by side, and a user who deletes one
  to reset the framework removes half of it; mitigated by one variable (AITASKS_HOME) with one library
  owner, ait setup printing both roots and the HOME_LEGACY: hint, ENGINE_MISSING naming the exact path,
  ait engine home reporting the state, a test that fails if any script of this feature names ~/.aitask/,
  and the migration verb existing now rather than as an unowned ''later change'' (n005, narrowed by n004''s
  verb)'
# new (n008)
tradeoff_verify_build_wired_suites: 'Disadvantage: a project that wired its test suite as verify_build
  (thinking_backend''s run_script_tests.sh, which also enforces a shellcheck baseline) cannot be onboarded
  mechanically - moving the command to a suite runner would drop the lint half from build_verified, leaving
  it would run the suite twice at completion; the skill therefore asks (keep as verify_build and add test_command:
  ./ait test over the detected bash-file and pytest units; or split the script), defaulting to keep, and
  records the answer in the onboarding plan; headless profiles keep (new)'
# inherited from n006 (unchanged)
tradeoff_whole_run_filter_soundness: 'Risk: where a runner''s filter restricts a whole test run (Gradle
  --tests on thinking_app''s single testDebugUnitTest task), every class not selected is silently not
  run, so a narrow selection is only as sound as the test-side closure, the reads globs and the opaque
  contract; mitigated by list enumerating the whole universe so an unlisted class fails check, the test-dep
  closure over abstract bases and helpers, testmap:reads on tree-scanning helpers (71 SourceFence importers
  stay selected on any Kotlin change), ESCALATE on opaque files, red-proof fixtures per branch, readiness
  gating the run gate on scored history, and the project keeping its full suite as the completion gate
  until readiness is met - the risk n004''s cell selection would have carried unmitigated (inherited from
  n005)'
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

The baseline (n006) is complete as an *engine*: a static Go binary under
`$AITASKS_HOME/engine/v<VERSION>/`, a merged `aitestmap/` registry with member
units and variant axes, blob-digest stamps healed by a per-variant evidence
join, scoped rows under a suite budget, the graded walk, a real scheduler, the
cost ledger, automatic prediction scoring, three gates and two skills. Every one
of those pieces is kept unchanged here. What n006 leaves as a *procedure a
maintainer remembers* — the "Per-Repository Bootstrap Order" (`scan → classify
--suggest → areas --import-codemap → … → readiness`) and "how a project's tests
are run through the runners" — is exactly what this node turns into product:

1. **Onboarding existing tests is a skill that runs as an aitask.** Three new
   engine verbs (`detect`, `suggest`, `adopt`) do the deterministic work — find
   the test frameworks a repository already has, propose `covers` edges for
   every existing test from evidence, and write the registry files and
   annotation blocks through the engine's own line-targeted rewriter — and one
   new skill, `aitask-testmap-onboard`, supplies the judgement: it groups the
   proposals by evidence class, asks once per class rather than once per file,
   creates the onboarding task, and hands it to `task-workflow`, so the
   annotation diff is reviewed at Step 8 and the task's own `tests_pass` gate at
   Step 9 performs the **first full run that anchors every unit's `last_pass`**.
   The bootstrap order stops being a list in a document and becomes the plan
   of one task. Onboarding is graded in four levels so a repository is useful
   after level 0 (runners bound, `ait test --all` works, selection through the
   static closure) and gets sharper as each level lands as its own reviewed
   commit.

2. **Running tests is one verb, `ait test`, correct in every repository
   state.** With no `aitestmap/` it runs `test_command` and prints the
   onboarding hint; with a registry it resolves by itself whether it is the
   implementation loop or a completion gate, which task it is running for,
   and what the change set is — nothing is passed on the command line in the
   common case. It prints its own project-specific instructions
   (`ait test --howto`), computed from `runners.yaml` and `config.yaml`, so
   they cannot rot.

3. **No code agent relearns how to run tests.** The shared agent-instructions
   seed that `ait setup` already installs into `CLAUDE.md`'s managed block,
   `AGENTS.md`, `.codex/instructions.md` and the OpenCode mirror gains a
   `## Running Tests` section naming `./ait test` and forbidding direct tool
   invocation. It is agent-agnostic, project-agnostic and installed before
   onboarding, because the verb is right before onboarding too.

4. **The seam with `task-workflow` is data, not new steps.** The existing
   `tests_pass` gate runs `test_command`; onboarding sets `test_command:
   ./ait test`, and `ait test --gate` decides between the whole suite and the
   task's selection from a **committed completion policy** in
   `aitestmap/config.yaml` — `full` until `ait testmap readiness` reports
   `ADMISSIBLE` and a human writes `approved_by`, demoted back to `full`
   automatically if readiness regresses. n006's `testmap_run` gate is retired
   as a name; its verifier logic is `ait test --gate`, its `blocks_dependents`
   and `max_retries: 1` are `tests_pass`'s own, and its 1800 s timeout becomes
   a per-project `tests_pass.timeout_seconds` derived from the cost ledger.
   `testmap_check` now unlocks `tests_pass`. The command exit contract gains one
   row — 75 → verifier `error` for opted-in keys — in the one function that
   owns it. Profiles' `default_gates` carry the two gates. The workflow prose
   changes are one Step-7 paragraph, one `build-verification.md` branch, and
   `aitask-qa` reading the registry instead of naming conventions.

**Why the seed signal is the static closure and not the naming convention.**
Measured on this repository: 398 of 400 `tests/test_*.sh` name an
`aitask_*.sh` or `lib/*.sh|py` path literally (the two that do not are pure
fixture tests), 320 of 320 `tests/test_*.py` import a `.aitask-scripts/lib`
module through a `sys.path` bootstrap, and only **52 of 400** bash tests map to
`.aitask-scripts/aitask_<stem>.sh` by the `tests/test_<stem>.sh` convention
`aitask-qa`'s discovery step relies on today. On `aitasks_go` the subject is
deterministic (a `_test.go` covers the non-test files of its own package). The
`(t<id>)` commit convention gives a co-change signal for free — 336 task groups
in the last 400 commits touching tests or scripts — but a group averages 1.14
commits and pairs a few tests with a few scripts (t1159_1: 4 × 4) with nothing
inside the group to say which covers which, so co-change corroborates and never
decides. Every number here is reproduced by `ait testmap suggest --all --json`
on the day it runs; the skill shows them before anything is written.

**Scope of "rewrite".** Integrating an existing test means inserting
`testmap:` comment lines with the file's own comment leader — bash and Python
after the header comment block or module docstring, Go after the package
clause, Kotlin after the import block — plus, at level 2, `testmap:kind`,
`testmap:area`, `testmap:reads`, `testmap:batch no`, and at level 3
`testmap:unit` member blocks and a scaffolded runner script. The test's code is
never restructured: `git diff -w --ignore-blank-lines` of an adopted file shows
comments only. Where a test *should* be split or made runnable in isolation the
skill says so and proposes a follow-up task; it does not do it.
<!-- /section: overview -->

<!-- section: what_the_mandate_adds [dimensions: requirements_zero_config_entrypoint, requirements_onboarding_existing_tests, requirements_agent_instructions_seeded, requirements_workflow_seam_is_data, component_gates] -->
## What the Mandate Adds, and What It Changes in the Baseline

| mandate clause | n006 answer | this node | why |
|---|---|---|---|
| scan existing tests and integrate them | `scan` reads annotations that do not exist yet; `classify --suggest` and `areas --import-codemap` help; the bootstrap order is a list | `detect` / `suggest` / `adopt` verbs + `aitask-testmap-onboard` skill; four levels, each an aitask | the registry cannot be scanned into existence from files that carry no `testmap:` lines; evidence has to be joined and a human has to accept it in bulk |
| rewrite tests to use the architecture | `annotate --from-body` for one Kotlin member | `adopt` writes stamped blocks for every accepted edge through the same rewriter; comments only; provenance in `registry/adopted.yaml` | a machine-seeded claim must be distinguishable from a reviewed one until a human re-stamps it |
| how to actually run the tests | `ait testmap select … \| schedule \| run`, two gate verifiers, `tests_pass` beside `testmap_run` | `ait test` (interactive / completion / named / all / dirty / explain / howto), one completion gate under a committed policy | an agent should know one verb; which tests run at completion is a project decision that belongs in data, not in which of two gates a task declared |
| no configuration by the final user | `ait setup` installs the engine; the registry is hand-written | onboarding writes `config.yaml`, `runners.yaml`, `resources.yaml`, `areas.yaml`, `test_command`, `gate_command_exit_contract`, profiles' `default_gates`; `ait test` falls back to `test_command` and to `fallback_command` | every key the user would have typed is derived from what the repository already has, and confirmed once as a table |
| no re-learning per session | `aitask-testmap` skill teaches the verbs | `## Running Tests` in the seeded instructions block, `ait test --howto` computed | CLAUDE.md is where agents already learn `./ait git`; project specifics that would rot in prose are computed instead |
| seamless with task-workflow | `testmap_fresh` before the change summary; `testmap_check` → `testmap_run` | same procedure gate; `testmap_check` → `tests_pass`; `AIT_GATE_TASK_ID` export; 75 → error; one Step-7 paragraph; `aitask-qa` registry discovery | Step 9's verify block, the merge broker, archival and the orchestrator are untouched; the legacy no-gates path and `aitask-qa` inherit the selective lane through `test_command` |

Two baseline decisions are changed, both recorded in *Changes to the
Baseline* at the end: `testmap_run` is retired as a gate name, and the
command exit contract gains a 75 row for opted-in keys. Everything else in
n006 — engine, registry, axes, freshness, evidence, gates `testmap_fresh` and
`testmap_check`, the skills `aitask-testmap` and `aitask-gate-testmap-fresh`,
the per-user root and its migration verb — is inherited unchanged.
<!-- /section: what_the_mandate_adds -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_onboarding_engine_verbs, component_onboarding_skill, component_agent_instructions, component_completion_policy, component_workflow_seam, component_qa_integration, component_go_engine] -->
## Architecture

### Process boundary, extended

```
./ait test [...]                                   (agent · human · tests_pass verifier via test_command)
 └─ .aitask-scripts/aitask_test.sh                 bash, ~120 lines: MODE / TASK / INTAKE / POLICY / fallback resolution only
      │  no aitestmap/            → TESTMAP_ABSENT:<hint>  → aitask_run_project_command.sh test_command  (exit per its verdict)
      │  engine absent            → interactive: ENGINE_MISSING:<path>|<repair> exit 3
      │                             completion:  per config.yaml completion.engine_absent (error | fallback_command)
      │  MODE   completion iff --gate or $AIT_GATE_TASK_ID, else interactive
      │  TASK   --task > $AIT_GATE_TASK_ID > aitask/<task_name> branch > single own lock (aitask_lock.sh --list-mine) > NO_TASK
      │  INTAKE aitask_change_surface.sh list <id> | --dirty (every dirty path as TASK:, printed) | --all | <path|id>...
      │  POLICY completion: config.yaml completion.mode (full | selected) re-checked against `readiness`
      └─ .aitask-scripts/aitask_testmap.sh          the n006 shim, unchanged
           └─ ait-testmap select --include-stale … → schedule → run        (n006 pipeline, unchanged)
                internal/onboard                    NEW: detect · suggest · adopt · howto
                internal/registry                   + registry/adopted.yaml (seventh table, written only by adopt)
                internal/cost                       + costs --gate-timeout
                internal/feedback                   + readiness LEVEL / NEXT / ADOPTED_UNREVIEWED / POLICY lines

.claude/skills/aitask-testmap-onboard/             NEW skill: detect → suggest → level proposal → per-class confirmation
                                                   → config table → create onboarding aitask → task-workflow
.claude/skills/aitask-testmap/                     n006, unchanged
.claude/skills/aitask-gate-testmap-fresh/          n006, unchanged
seed/aitasks_agent_instructions.seed.md            + ## Running Tests   (installed by ait setup into all four agent surfaces)
.aitask-scripts/lib/gate_verifier_lib.sh           run_project_command_key(): + 75 → error (opted-in keys); exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID
.aitask-scripts/gates_reference.yaml               + testmap_fresh, testmap_check (unlocks: [tests_pass]);  no testmap_run
.aitask-scripts/aitask_gate_testmap_check.sh       n006, unchanged;  aitask_gate_testmap_run.sh is NOT written
```

The boundary rule is n006's: parse, walk, match, digest, schedule *and now
detect / suggest / adopt* in Go; gate ledger, task file, shell environment
*and every write to `project_config.yaml`, `gates.yaml`, profiles or
`CLAUDE.md`* in bash and the skill. The engine never edits a framework
configuration file; it writes `aitestmap/**` and the annotation blocks it is
asked to write, and prints `WROTE:` for each.

### Where the new state lives

| data | location | written by |
|---|---|---|
| completion policy, onboarding conventions, helper roots | `aitestmap/config.yaml` (`completion:`, `conventions:`, `helper_roots:`, `helper_fanin:`) | `adopt` (level 0); the skill's `--policy` re-entry (`completion.mode`, `run_gate_admission.approved_by`) |
| adopted-edge provenance | `aitestmap/registry/adopted.yaml` rows `{test, source, signals, confidence, adopted_at, task}` | `adopt`; rows deleted by `verify`, `annotate`, `stale --confirm-source` on that edge |
| suggest output for review and attachment | `.aitask-testmap/onboard/<run-id>/suggest.json` (gitignored), attached to the onboarding task with `ait attach` | `suggest --json --out` |
| the test entry in project config | `aitasks/metadata/project_config.yaml`: `test_command: ./ait test`, `gate_command_exit_contract: [test_command]` | the skill, through `aitask_settings`-compatible YAML edits, confirmed |
| gate declarations | `aitasks/metadata/profiles/*.yaml` `default_gates`; `aitasks/metadata/gates.yaml` `tests_pass.timeout_seconds` | the skill, confirmed; timeout from `costs --gate-timeout` after the first full run |
| agent instructions | `CLAUDE.md` `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md`, OpenCode mirror | `ait setup` from the seed; hand-maintained `CLAUDE.md` by the onboarding task |

Everything else — registry, runners, resources, axes, costs, predictions,
runs, ledger, deps cache, locks, engine binaries — is where n006 put it.

### `aitestmap/config.yaml`, the additions

```yaml
# n006 keys unchanged: unit_covers_max, suite_budget_s, bootstrap_until, require_stamp, broad_review_days,
# concurrency, broad_after_unit, device_policy, host_class, flake_threshold, symbol_scanners, run_gate_admission
completion:
  mode: full                 # full | selected — selected written only by the onboarding skill after READINESS_DECISION:ADMISSIBLE
  deferred: run              # run | fail — completion never silently drops a row the interactive budget would cut
  on_empty_selection: skip   # skip (exit 2 → gate skip under the opt-in) | full
  engine_absent: error       # error (exit 3) | fallback_command (the suite runner's fallback_command:, MODE:fallback)
conventions:                 # seeded by detect; used by suggest's `convention` signal (0.7)
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/aitask_{stem}.sh"}
  - {test: "tests/test_{stem}.py", source: ".aitask-scripts/lib/{stem}.py"}
helper_roots: ["tests/lib/**", "**/testing/**", "**/testdata/**"]
helper_fanin: 0.05           # a closure path reached by ≥5% of a runner's units is a helper, not a subject
```
<!-- /section: architecture -->

<!-- section: entrypoint [dimensions: component_test_entrypoint, component_completion_policy, assumption_task_resolvable_from_session, assumption_gate_exit_contract_reused] -->
## `ait test`: One Verb, Every Repository State

### Surface

```
ait test                       selected tests for the task you are implementing, each with a reason
ait test <path|id>...          named units: a listed test file, file#member, file#member@variant, a directory of tests,
                               or a SOURCE path — treated as a one-file change set, so `ait test lib/foo.py` runs what covers it
ait test --all                 the whole registry: every runner's list, full: true suites once, subsumed runners skipped
ait test --explain             the selection with reasons, groups and estimated cost; runs nothing
ait test --howto               this project's runners, kinds, resources, completion policy, LEVEL, and the three commands an agent needs
ait test --tokens              select --format tokens (thinking_app: `| xargs tools/verification/screenshot-tests.sh preview`)
ait test --gate                completion mode — what tests_pass runs; implied by $AIT_GATE_TASK_ID
ait test --dirty               no task: every dirty path is a TASK: row; explicit, printed as INTAKE:dirty, never the default
ait test --task <id>           override task resolution
ait test --fresh-only          exclude stale-marked units (interactive only)
ait test --budget-s <n>        interactive suite budget override
```

### Resolution, in order

1. **Registry present?** No `aitestmap/config.yaml` → print
   `TESTMAP_ABSENT:run /aitask-testmap-onboard to enable change-aware selection`
   and delegate to `aitask_run_project_command.sh test_command` (with
   `--task-id` when a task resolved), exiting with its verdict. This is what
   makes the seed instruction "always `./ait test`" true on day one in a
   repository that has never heard of the engine.
2. **Engine present?** Through the n006 shim's strict handshake. Absent:
   interactive → `ENGINE_MISSING:<path>|run 'ait setup' or set AIT_TESTMAP_BIN`,
   exit 3; completion → `completion.engine_absent`: `error` (default, exit 3 →
   verifier `error`) or `fallback_command` (run the `full: true` suite runner's
   `fallback_command:`, print `MODE:fallback`, exit per the command).
3. **Mode.** `--gate` or `$AIT_GATE_TASK_ID` set → `completion`; else
   `interactive`. Printed as `MODE:`.
4. **Task.** `--task` > `$AIT_GATE_TASK_ID` > the current worktree's branch if
   it matches `aitask/t<id>_*` (task-workflow's own naming) > the locks this
   user holds on this host (`aitask_lock.sh --list-mine`, a listing verb added
   to the lock script): exactly one → that task; several →
   `AMBIGUOUS_TASK:<ids>`, exit 64 unless `--task`; none → `TASK:none`.
5. **Intake.** Named paths → units by registry lookup, or a source path → a
   synthetic `TASK:<path>` change set; `--all` → every runner's `list`; a
   resolved task → `aitask_change_surface.sh list <id>` piped to `--changes -`
   (the n006 intake: `UNKNOWN:` refuses, `aitasks/` `aiplans/` `.aitask-data/`
   excluded); `--dirty` → `git status --porcelain` paths as `TASK:` rows with
   `INTAKE:dirty (no task attribution)`; nothing resolved → `NO_TASK:` with the
   three ways out (`--task`, `--dirty`, `--all`), exit 64.
6. **Policy (completion only).** Read `completion.mode`; if `selected`, run
   `ait testmap readiness` first: every criterion met → selected; any unmet →
   `POLICY_DEMOTED:selected->full|<criterion>` and run `full`. `full` →
   `run --all` with `subsumed_by` honoured (thinking_app: `verify-active`
   once, never `screen-matrix` beside it). `deferred: run` means the budget is
   not applied in completion mode; `on_empty_selection: skip` means a selected
   run with zero units exits 2, which the opted-in `tests_pass` records as
   `skip`, not `pass`.
7. **Run.** `select --include-stale [--budget-s] [--format …] --run <run-id>`
   → `schedule` → `run`, exactly the n006 pipeline. Interactive mode prints
   `DEFERRED:` rows; completion mode runs them.
8. **New-test notice.** For every `TASK:` / `COMMITTED:` path a runner lists
   that has no `testmap:` block and no `adopted.yaml` row:
   `UNANNOTATED_TEST:<path>` + `HINT:./ait testmap annotate --suggest <path>`.
   Informational in interactive mode; in completion mode `testmap_check` owns
   the enforcement (`UNSTAMPED` past bootstrap under `require_stamp`).

### Output and exit contract

```
MODE:interactive|completion|fallback   TASK:<id>|none   INTAKE:change-surface|dirty|all|named
POLICY:full|selected|<demoted…>        SELECTED:<units>|<groups>|<est_s>   RUN:<run-id>
ESCALATE:… DEFERRED:… UNANNOTATED_TEST:… HINT:…          (n006 line classes pass through)
RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>
```

| exit | meaning | as `test_command` under `gate_command_exit_contract: [test_command]` |
|---|---|---|
| 0 | every selected unit passed | pass |
| 1 | a unit failed, or a mechanism failure (`units_reported == 0`, unregistered row) | fail |
| 2 | nothing ran: empty selection, or `TESTMAP_ABSENT` + no `test_command` | skip |
| 3 | framework error: engine missing / mismatched, registry `CONTRACT_MISMATCH`, `UNKNOWN:` intake | **error** (new row) |
| 75 | admission refused after the in-engine deferral to the run deadline | **error** (new row) |
| 64 | usage: `NO_TASK`, `AMBIGUOUS_TASK`, bad flag | fail (a verifier cannot skip on a usage error) |

The 3 and 75 rows are the one change to `run_project_command_key()`'s table:
for a key listed in `gate_command_exit_contract`, exit 75 → `PROJECT_CMD_STATUS=error`,
`CODE=3`, `REASON=command_refused`, and exit 3 → `error` / `command_errored`.
For a key not opted in, both stay `fail` as today. The verifier appends
`error`, exits 3, and the orchestrator treats it as a verifier infrastructure
failure — retried within `max_retries`, never "fix the code", never a skip
that releases dependents. `build-verification.md` gains the matching branch.

### The two environment variables

`run_command_gate` exports `AIT_GATE_TASK_ID=<task-id>` and
`AIT_GATE_RUN_ID=<run-id>` around the command; `aitask_run_project_command.sh
--task-id <id>` exports the first. That is the whole mechanism by which
`./ait test` knows it is a completion run and for which task, in all three
existing call sites (the `tests_pass` verifier, the legacy Step-9 helper,
`aitask-qa`), with no argument in `test_command`. The run id lets the engine
name the gate run in `.aitask-testmap/runs/<run-id>/` so a ledger row and a
gate log share an identifier.
<!-- /section: entrypoint -->

<!-- section: onboarding [dimensions: component_onboarding_engine_verbs, component_onboarding_skill, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only, component_annotation_scanner, component_dependency_scanners] -->
## Onboarding Existing Tests

### Four levels, each one reviewed aitask

| level | what `adopt` writes | what the repository gains | who accepts |
|---|---|---|---|
| **0 — runners** | `config.yaml`, `runners.yaml` (builtins + bindings by glob, a `full: true` suite runner from `test_command` / `verify_build` with `fallback_command:`), `resources.yaml` from hints, `registry/areas.yaml` via `areas --import-codemap` | the universe (`list`), `ait test --all`, per-unit cost and `last_pass`, selection through the test-file static closure (`test-dep`), scoring on full runs; nothing stamped, nothing to go stale | nobody per edge — headless-safe |
| **1 — edges** | stamped `testmap:covers` blocks for accepted subject edges; `registry/adopted.yaml` rows | freshness and the evidence join apply; `stale` reports; `testmap_check` meaningful | per evidence class |
| **2 — kinds** | `testmap:kind integration\|e2e\|device` + `testmap:area` on broad tests, `testmap:reads` on tree-scanning helpers, `testmap:batch no` from serial lists, `needs:` on runners from resource hints | scoped rows, budget, `broad_after_unit`, enforced do-not-overlap | per kind reclassification, individually |
| **3 — product** | `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` scaffold (`describe` / `list` / `run` stubs), `testmap:unit` member blocks | variant selection (n006's thinking_app mapping) | the maintainer, with the skill |

`readiness` derives the level from what exists (`runners.yaml` → 0, any
`_scanned` edge → 1, any `_scoped` row or `reads` → 2, `axes.yaml` → 3) and
prints `LEVEL:<n>` and `NEXT:<the adopt or skill step that raises it>`.

### `detect`

A closed detector list; each row carries its evidence so a reader can dispute it:

```
FRAMEWORK:bash-file|tests/**/test_*.sh|400|bash-file|bash shebang; sources tests/lib/asserts.sh
FRAMEWORK:pytest|tests/test_*.py|320|pytest|unittest/pytest imports; tests/run_all_python_tests.sh
AGGREGATE_RUNNER:tests/run_all_python_tests.sh|serial carve-out list found
SERIAL_LIST:tests/run_all_python_tests.sh|4                       → testmap:batch no candidates
RESOURCE_HINT:repo-git-index|~40 tests|git status/add against the real repo; .git/index.lock in comments
UNIVERSE:720   UNLISTED:0
SUITE_CANDIDATE:test_command|null
```

Detectors: `bash-file` (`tests/**/test_*.sh`, `scripts/tests/test_*.sh`, bash
shebang), `pytest` (`test_*.py` / `*_test.py`, `pytest.ini` / `pyproject
[tool.pytest]` / `conftest.py` / unittest imports), `go-test` (`go.mod` +
`*_test.go`, packages from `go list ./...`), `gradle-class` (`build.gradle(.kts)` +
`src/test/**/*.kt|java`; task `testDebugUnitTest` for Android modules, `test`
for JVM), `kmp-sourceset` (a `kotlin { }` multiplatform block; `commonTest` →
`gradle-class` on `:<module>:jvmTest` or `allTests`, `androidHostTest` →
`testDebugUnitTest`, `androidDeviceTest` → the `device` runner on
`connectedDebugAndroidTest` with `needs: [emulator]`), `suite-from-config`
(`test_command` / `verify_build` values that look like a test runner).
`RUNNER_SCRIPT_NEEDED:<reason>` when the grid heuristic (n006's `classify
--suggest`) finds a product space or when listed files are not lowerable by a
builtin. `UNLISTED:<n>` is the set that would fail `UNREGISTERED` after
adoption, printed so the skill can ask whether they are tests at all.

### `suggest`: the evidence join

For every unit a runner lists, one row per candidate source:

```
SUGGEST:tests/test_gate_verifiers.sh|.aitask-scripts/lib/gate_verifier_lib.sh|static,cochange:3|0.94
SUGGEST:tests/test_gate_verifiers.sh|.aitask-scripts/aitask_gate_tests_pass.sh|static|0.90
SUGGEST:tests/test_gate_pass.sh|.aitask-scripts/aitask_gate_pass.sh|static,convention|0.97
SUGGEST_HELPER:tests/test_gate_verifiers.sh|tests/lib/asserts.sh|helper_root
SUGGEST_READS:tests/lib/import_isolated.py|.aitask-scripts/lib/**/*.py|glob.glob
SUGGEST_KIND:tests/test_board_header_row_live.py|integration|tmux;real-git;areas:board,scripts
SUGGEST_BATCH_NO:tests/test_board_header_row_live.py|SERIAL_LIST
```

| signal | how | confidence |
|---|---|---|
| `static` | the unit's forward closure from the n006 dependency scanners — bash `source` / `.` / exec of a repo path including `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms resolved against every source root; Python imports resolved through the file's own `sys.path` bootstrap; a `_test.go`'s own package; Kotlin imports — minus helpers | 0.9; Go package 1.0 |
| `convention` | `config.yaml conventions:` patterns, seeded by `detect` per framework | 0.7 |
| `cochange` | `git log --name-only` on the unit's last 50 commits, grouped by `(t<id>)` tag when present else by commit; a source-root path present in ≥ 2 groups | 0.2 + 0.2 × groups, cap 0.6 |
| `plan` | an `aiplans/` file naming both paths, through the `aitask_explain_extract_raw_data.sh` cache when present | 0.5 |
| `prose` | a literal path in the unit's header comment or a `# Covers:` line — a hint, never matched by the scanner | 0.3 |

Combined confidence is `1 − Π(1 − cᵢ)`; the default acceptance threshold is
0.85, so `static` alone qualifies, `convention` alone (0.7) does not, and
`cochange` can never qualify alone. **Helpers are separated from subjects
before scoring**: a closure path under `helper_roots` or with fan-in ≥
`helper_fanin` (5 % of the runner's units) is a helper — it gets `test-dep`
through the closure for free and, when it globs the tree (`ls tests/*.sh`,
`glob.glob`, `rglob`, `find`, `git ls-files`, `os.walk`), a proposed
`testmap:reads`. On this repository that is `tests/lib/` (27 files, 3 of which
glob). Kind classification: `integration` when the unit spawns tmux or a TUI
(`App.run_test`), boots a real install (`install.sh --dir`), touches the real
repository's git, or has more subjects than `unit_covers_max` (reason
`fanout:<n>`), with areas from the closure's directories intersected with
`code_areas.yaml`; `device` for `androidDeviceTest`; else `unit`. Members and
axes come from n006's grid heuristic.

### `adopt`: writing through the engine

`adopt --from suggest.json [--accept-min 0.85] [--scope <glob>] [--level 0..3]
[--dry-run]` writes level-0 files first, then for every accepted edge a
stamped block through `internal/annot`'s line-targeted rewriter:

```bash
# tests/test_gate_verifiers.sh - Tests for the project-command machine-gate verifiers …
# Run: bash tests/test_gate_verifiers.sh
# testmap:covers .aitask-scripts/lib/gate_verifier_lib.sh      @2026-09-16/3f9a1c07be
# testmap:covers .aitask-scripts/aitask_gate_tests_pass.sh     @2026-09-16/91be0d2a4c
# testmap:covers .aitask-scripts/aitask_gate_build.sh          @2026-09-16/c02d7e5f18
```

Placement per language: bash and Python after the header comment block (Python
after the module docstring, as `#` lines — the grammar also accepts docstring
lines, but rewriting a docstring changes `__doc__`, so adoption does not); Go
after the package clause; Kotlin after the import block. Every edge written
gets a row in `registry/adopted.yaml` (`test, source, signals, confidence,
adopted_at, task`), deleted when a human `verify` / `annotate` /
`--confirm-source` re-stamps that edge. Refusals and skips are explicit:
`ADOPT_REFUSED:<path>|dirty-foreign` for a file dirty outside the current
task's change surface (adoption never mixes with concurrent work),
`ADOPT_SKIP:<path>|duplicate` for an edge already annotated,
`ADOPT_SKIP:<path>|unregistered` for a file no runner lists (fix `runners.yaml`
first), `ADOPT_SKIP:<path>|no-leader` for a file whose comment leader the
grammar does not know. `WROTE:<path>` per file and one
`ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>`.

### The skill, step by step

1. **Preconditions.** `ait testmap version` — absent → stop with the `ait
   setup` hint. `aitestmap/` present → *refresh mode*: `suggest` limited to
   units newer than the last `adopted.yaml` row, same flow.
2. **Read-only survey.** `detect`; `suggest --all --json --out
   .aitask-testmap/onboard/<run>/suggest.json`. Display the level proposal:
   frameworks and counts, edges per evidence class with three samples each,
   helpers found and which glob, kind candidates with reasons, `UNLISTED`
   files, `RUNNER_SCRIPT_NEEDED` if any, and the four config writes.
3. **Confirm per class.** `AskUserQuestion` per evidence class — *accept all /
   review a sample (ten random members with their signals) / skip* — and per
   kind reclassification individually (non-skippable: a kind changes staleness
   semantics). `UNLISTED` files: *test — bind to runner X / not a test /
   decide later*. Headless (`remote`) profile: level 0 plus static-only level 1
   at `--accept-min 0.95`, no prompts, no kinds.
4. **Confirm the config table once.** `test_command` → `./ait test`, with a
   previous value moved to a `full: true` suite runner (`verify_build` is left
   alone unless the user names it as the suite — thinking_backend);
   `gate_command_exit_contract` += `test_command`; project profiles'
   `default_gates` += `tests_pass`, `testmap_check`; the `### Testing`
   paragraph when `CLAUDE.md` is hand-maintained (the sentinel guard in
   `update_claudemd_git_section` is exactly how the skill knows).
5. **Create the onboarding aitask and continue into task-workflow.**
   `aitask_create.sh --batch --name "testmap onboarding level <n>" --type chore
   --labels testing,testmap`, `ait attach` the `suggest.json`; the plan is the
   `adopt` command lines and the config writes; continue as `aitask-explore`
   does (`explore_auto_continue`-style, honouring the profile). Step 7 runs
   `adopt`; Step 8 reviews the diff — the user sees every inserted line; Step
   9's `tests_pass` runs `./ait test --gate` under `completion.mode: full`,
   which is the **first full run**: every unit's `last_pass` is anchored,
   `PREDICTION_SCORED:none` is printed because nothing was predicted yet, and
   the archive commits registry, annotations and config under one `(t<id>)`.
6. **After the first run.** `ait testmap costs --gate-timeout tests_pass` →
   `GATE_TIMEOUT_SUGGESTED:tests_pass|<s>` = `max(600, 3 × p95)` → written into
   the project's `gates.yaml`; `readiness` → `LEVEL` / `NEXT`; the next level's
   task is created with `depends:` on this one.
7. **`--policy selected` re-entry**, later: run `readiness`; only on
   `READINESS_DECISION:ADMISSIBLE` write `completion.mode: selected` and
   `run_gate_admission.approved_by {who, at, statement}`; one `ait:` commit.
   `NOT_YET` → print the unmet criteria and stop.
<!-- /section: onboarding -->

<!-- section: worked_onboarding [dimensions: assumption_full_run_expressible_per_repo, component_reference_runners, component_runner_contract, component_scheduler_resources, assumption_existing_locks_wrappable] -->
## Worked Onboarding: the Five Target Repositories

| repository | `detect` | level 0 runners and resources | full run (`completion.mode: full`) | levels 1–3 |
|---|---|---|---|---|
| **aitasks** | bash-file 400, pytest 320, `AGGREGATE_RUNNER` with a 4-module `SERIAL_LIST`, `RESOURCE_HINT:repo-git-index`, `test_command: null` | `bash-file`, `pytest` (`testmap:batch no` on the carve-out); `resources.yaml`: `repo-git-index {kind: mutex, scope: worktree}` needed by both runners — the "invocation policy, not a guarantee" comment in `run_all_python_tests.sh` becomes enforced | `ait test --all` (no suite existed; `tests_pass` gates for the first time); `fallback_command` derived: `for f in tests/test_*.sh; do bash "$f"; done && bash tests/run_all_python_tests.sh` | 1: 398 + 320 static edges, 52 corroborated by convention; helpers `tests/lib/` (27; 3 `reads`); 2: ~40 tmux / live-TUI / real-install tests → `integration` over codemap areas; 3: the goldens tree `tests/golden/` as a skill × profile × agent axis (n006's example) |
| **thinking_app** | gradle-class 374 classes, `RUNNER_SCRIPT_NEEDED:grid` (screen × matrix), `SUITE_CANDIDATE:test_command\|verify-active`, `RESOURCE_HINT:heavy-run` (exit 75 lock script) | `gradle-class` builtin until the project runner exists; `verify-active {unit: suite, full: true, children: …, fallback_command: tools/verification/screenshot-tests.sh verify-active}`; `heavy-run {kind: admission, exec: heavy-run-lock.sh}` | `verify-active` once (`screen-matrix`, `gradle-class` `subsumed_by: verify-active`) — identical to today's `test_command` | 3 = n006's worked mapping: `axes.yaml`, `tools/verification/testmap_runner.sh`, `testmap:unit` blocks in `ScreenFixtures.kt`; `completion.mode` stays `full` until readiness, exactly t388's rule |
| **thinking_backend** | bash-file 22 + pytest 18 under `scripts/tests/`, `SUITE_CANDIDATE:verify_build\|scripts/tests/run_script_tests.sh` | `bash-file`, `pytest` with `cwd:`; the skill asks: keep `verify_build` (it also enforces a shellcheck baseline — half lint) and add `test_command: ./ait test` — default | `ait test --all` over the 40 units; `build_verified` still runs the script | 1: static edges into `scripts/server/**` and `db_target.py`; 2: `golden/` fixtures as `reads` |
| **aitasks_go** | go-test: 85 packages, 55 `_test.go` files | `go-test` (per-package `-run`, `-json`) | `go test ./...` = `ait test --all` | 1 fully automatic: a test's package is its subject at confidence 1.0 — level 1 is headless-safe here |
| **aitasks_mobile** | kmp-sourceset: `commonTest` 36 (dbaccess 2, domain 25, shared 9), `androidHostTest` 1, `androidDeviceTest` 3 | `gradle-class` × modules on `:<module>:jvmTest` / `testDebugUnitTest`; `device` runner on `connectedDebugAndroidTest` with `emulator {kind: allocator}` | unit kinds only; device kind under `device_policy: filter_by_resource` — n006's open question 9 is answered: the source set is a runner/kind distinction, no axis | 1: Kotlin import closure (`domain/src/commonMain/**`) |

In every row the user typed nothing; the skill showed the table and asked for
one confirmation per class and one per config write.
<!-- /section: worked_onboarding -->

<!-- section: agent_instructions [dimensions: component_agent_instructions, assumption_instruction_block_is_read, requirements_agent_instructions_seeded] -->
## Agent Instructions: Installed, Not Learned

`seed/aitasks_agent_instructions.seed.md` gains one section, installed by the
existing `assemble_aitasks_instructions()` into every agent surface on every
`ait setup` (the `>>>aitasks` block is regenerated each run since t1612):

```markdown
## Running Tests

Run tests only through the framework entrypoint — never call pytest, go test,
gradle, or a test script directly.

    ./ait test              # tests selected for the task you are implementing, each line with its reason
    ./ait test <path>...    # a named test file or unit; a SOURCE path runs what covers it
    ./ait test --all        # the whole suite — what completion runs while the project's policy is `full`
    ./ait test --howto      # this project's runners, kinds, resources, completion policy and level

`./ait test` chooses tests from your task's change surface. When it prints
`UNANNOTATED_TEST:<path>` for a test you added, run
`./ait testmap annotate --suggest <path>` and accept or edit the proposal.
Exit codes: 0 pass · 1 fail · 2 nothing ran · 3 framework error (run `ait setup`) · 75 host refused
(resources; the run already waited — try later).
```

Three properties make this safe to install everywhere at once: the verb is
correct before onboarding (it runs `test_command`), the section carries no
project specifics (those are `--howto`'s computed output, so the
current-state-only documentation rule holds and no constant condenses
`runners.yaml`), and it is agent-agnostic (the shared Layer-1 seed, not the
per-agent Layer-2 files). `tests/test_agent_instructions.sh` gains T40: the
heading present in all four rendered surfaces. This repository's own
`CLAUDE.md` is hand-maintained (sentinel present, no markers), so its
`### Testing` block is edited by the onboarding task to point at `./ait test`
and keep the runner-specific notes (`run_all_python_tests.sh` lanes, the
`PIPESTATUS` caveat) as background.

`ait test --howto` prints, for aitasks after level 2:

```
HOWTO:aitasks LEVEL:2 POLICY:full
RUN   ./ait test                     selected for your task     ./ait test --all    720 units, ~4 min p95 on this host class
RUNNER bash-file   400 units  tests/**/test_*.sh          needs: repo-git-index
RUNNER pytest      320 units  tests/test_*.py             needs: repo-git-index   batch:no ×4 (serial carve-out)
KIND   unit 679 · integration 41 (areas: board, monitor, setup)
GATE   tests_pass runs `./ait test --gate` → full; testmap_check unlocks it; testmap_fresh before commit
NEW TEST  ./ait testmap annotate --suggest <path>
```
<!-- /section: agent_instructions -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_gates, component_qa_integration, assumption_gate_exit_contract_reused, requirements_workflow_seam_is_data, requirements_gate_enforcement] -->
## The task-workflow Seam

| where | change | kind |
|---|---|---|
| `task-workflow/SKILL.md.j2` Step 7, after *Follow the approved plan* | one paragraph: "**Test loop.** Run `./ait test` after each meaningful change — it selects from this task's change surface and prints a reason per unit. When it prints `UNANNOTATED_TEST:<path>` for a test you added, run `./ait testmap annotate --suggest <path>` and accept or edit. Do not invoke the project's test tool directly; `./ait test <path>` runs one unit." | prose, rendered into every profile; goldens regenerated |
| Step 8 | n006's `testmap_fresh` procedure-gate dispatch before the change summary | inherited |
| Step 9 verify block (`./ait gates run`) | none — the orchestrator runs `testmap_check` → `tests_pass` (= `./ait test --gate`) | none |
| Step 9 no-gates branch (`build-verification.md`, `verify_build`) | none in prose; a project reaches the test lane by declaring `tests_pass`, which onboarding writes into `default_gates` | data |
| `build-verification.md` | one branch: verdict `error` with reason `command_refused` / `command_errored` → host refused resources or the framework could not run; do not fix code, do not record a pass, report and re-run later | prose |
| `lib/gate_verifier_lib.sh` `run_project_command_key()` | opted-in keys: 75 → `error`/3/`command_refused`, 3 → `error`/3/`command_errored`; export `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` around the command; docblock table updated (the single statement) | code; `tests/test_gate_verifiers.sh` extended |
| `aitask_run_project_command.sh` | `--task-id` also exports `AIT_GATE_TASK_ID`; inherits the new rows | code |
| `gates_reference.yaml` → `gates.yaml` sync | + `testmap_fresh` (procedure), + `testmap_check` (`unlocks: [tests_pass]`, `max_retries: 0`, `timeout_seconds: 120`); **no `testmap_run`**; `tests_pass` unchanged in the reference, `timeout_seconds` tuned per project from the ledger | data |
| project profiles (`aitasks/metadata/profiles/*.yaml`) | `default_gates` += `tests_pass`, `testmap_check` (onboarding, confirmed) | data |
| `aitask-qa/test-discovery.md` 3a–3c | with `aitestmap/`: per changed source `ait testmap explain --source <path>` → edges, test-deps, scoped rows; `GAP` = no edge and no test-dep; else the legacy convention scan | prose |
| `aitask-qa/test-execution.md` 4a–4d | 4a: the configured `./ait test` through `aitask_run_project_command.sh test_command --task-id <id>`; 4b: named units via `ait test <path>`; 4c: `REFUSED (host resources)` row; 4d coverage from registry edges | prose |
| `aitask-pickrem`, `aitask-pickweb`, `aitask-resume` | inherit through task-workflow and `build-verification.md`; pickweb (no `ait setup`) is the `engine_absent` case | none |
| `ait` dispatcher | `test)` → `aitask_test.sh`; help line | code |
| permission touchpoints (5) | `aitask_test.sh`, `aitask_testmap.sh` | config |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a test-framework detector" (closed list, evidence line, fixture repo, `UNLISTED` behaviour) | doc |
| `aitask_skill_verify.sh` + goldens | task-workflow, aitask-qa, the new stub | test |

Three things the seam deliberately does **not** do: it does not add a Step-9
test step for tasks without gates (declaring `tests_pass` is the framework's
existing way to say "run tests at completion", and onboarding writes the
declaration); it does not make the engine write any framework file; and it
does not touch the merge broker, archival or the gate orchestrator.
<!-- /section: workflow_seam -->

<!-- section: data_flow [dimensions: component_test_entrypoint, component_onboarding_engine_verbs, component_onboarding_skill, component_completion_policy, component_workflow_seam, component_selector, component_cost_ledger, component_feedback_tools, component_registry_loader, component_staleness_tool] -->
## Data Flow

### Onboarding: existing tests → registry → first anchored run

```
repository (tests, scripts, build files, project_config.yaml, code_areas.yaml, git history)
   │
   ▼  ait testmap detect                        FRAMEWORK: / AGGREGATE_RUNNER: / SERIAL_LIST: / RESOURCE_HINT: / SUITE_CANDIDATE: / UNLISTED:
   ▼  ait testmap suggest --all --json           SUGGEST: (static·convention·cochange·plan·prose → confidence) / SUGGEST_HELPER: / SUGGEST_READS: / SUGGEST_KIND: / SUGGEST_BATCH_NO: / SUGGEST_MEMBER:
   │                                             → .aitask-testmap/onboard/<run>/suggest.json
   ▼  skill: level proposal → per-class AskUserQuestion → config table → aitask_create.sh --batch (+ ait attach suggest.json)
   ▼  task-workflow Step 7:  ait testmap adopt --from suggest.json --level 0 [--level 1 --accept-min 0.85] [--scope <glob>]
   │      writes aitestmap/config.yaml runners.yaml resources.yaml registry/areas.yaml           (level 0)
   │             testmap: blocks via the line-targeted rewriter + registry/adopted.yaml         (level 1)
   │      skill writes project_config.yaml test_command / gate_command_exit_contract, profiles default_gates, CLAUDE.md paragraph
   ▼  task-workflow Step 8:  the annotation diff reviewed; testmap_fresh (n006) — nothing STALE yet, every stamp is today's
   ▼  task-workflow Step 9:  ./ait gates run → testmap_check (non-strict during bootstrap) → tests_pass → ./ait test --gate
   │      MODE:completion POLICY:full → run --all → ledger.jsonl rows → last_pass per unit → PREDICTION_SCORED:none
   ▼  archive: one (t<id>) commit with registry, annotations, config;  ait: commit for gates.yaml timeout after costs --gate-timeout
   ▼  readiness → LEVEL:<n> NEXT:<step>;  the next level's task created with depends:
```

### Implementing a task: the interactive loop

```
agent edits code → ./ait test
   MODE:interactive  TASK:1234 (aitask/t1234_… branch)  INTAKE:change-surface
   aitask_change_surface.sh list 1234 | ait-testmap select --task 1234 --changes - --include-stale --budget-s <suite_budget_s> --run r1
   ├─ SELECTED:14|3|41s   …/test_gate_verifiers.sh d=1 unit edge(annotation) lib/gate_verifier_lib.sh  adopted(static 0.90)
   ├─ DEFERRED:tests/test_t167_integration.sh|budget                              (interactive only)
   ├─ UNANNOTATED_TEST:tests/test_ait_test_entrypoint.sh  HINT:./ait testmap annotate --suggest tests/test_ait_test_entrypoint.sh
   └─ schedule → run → RESULT:pass|14|0|0   prediction.json written for task 1234 (scored by the next full run)
agent: ./ait testmap annotate --suggest tests/test_ait_test_entrypoint.sh   → SUGGEST: rows → accept → block written, stamp today
```

### Completion: `tests_pass` → `./ait test --gate`

```
ait gates run 1234 → testmap_check (aitask_gate_testmap_check.sh) → pass → unlocks tests_pass
   → aitask_gate_tests_pass.sh → run_command_gate → export AIT_GATE_TASK_ID=1234 AIT_GATE_RUN_ID=<run> → `./ait test`
      MODE:completion  POLICY:full                       → run --all (subsumed_by honoured) → exit 0/1/2/3/75
      MODE:completion  POLICY:selected                   → readiness: all met → task selection, deferred rows RUN → exit …
      MODE:completion  POLICY:selected → POLICY_DEMOTED:selected->full|max_false_negatives  → run --all
   → run_project_command_key: 0 pass · 1 fail · 2 skip · 3 error(command_errored) · 75 error(command_refused)   [opted-in key]
   → ledger block result="MODE:full|720 units|policy:full" → orchestrator: pass / fail / skip / error(retry within max_retries: 1)
   → after any full run: PREDICTION_SCORED:<r1>|<run> PREDICTION_FALSE_NEGATIVES:<n> → costs/predictions.yaml → readiness input
```

### Policy flip

```
/aitask-testmap-onboard --policy selected
   → ait testmap readiness → READINESS:min_scored_full_runs|met|34  READINESS:max_false_negatives|met|0
                              READINESS:require_opaque_proofs|met  READINESS:approved_by|unmet|-
   → AskUserQuestion: record approval {who, statement}  → config.yaml completion.mode: selected, run_gate_admission.approved_by
   → ait: commit → the next tests_pass runs the selection; any later unmet criterion demotes it loudly
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n006)* means unchanged in substance; *(modified)* names the
clause added here; *(new)* is a component n006 did not have.

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(new)*

`.aitask-scripts/aitask_test.sh`, a ~120-line bash front over the n006 shim:
resolves `MODE` (completion iff `--gate` or `$AIT_GATE_TASK_ID`), `TASK`
(`--task` > `$AIT_GATE_TASK_ID` > `aitask/<task_name>` branch > single own lock
via `aitask_lock.sh --list-mine` > `NO_TASK`), `INTAKE` (change surface piped;
`--dirty`; `--all`; named paths, a source path as a one-file `TASK:` set) and
`POLICY` (completion: `config.yaml completion.mode` re-checked against
`readiness`); runs `select --include-stale → schedule → run`; falls back to
`aitask_run_project_command.sh test_command` when `aitestmap/` is absent and
to the suite runner's `fallback_command` when the engine is absent and the
policy allows; prints `MODE / TASK / INTAKE / POLICY / SELECTED / RUN /
RESULT` and `UNANNOTATED_TEST` + `HINT`; exits 0 / 1 / 2 / 3 / 75 / 64;
dispatcher arm `test)`; five permission touchpoints;
`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine that replays scripted exits.
<!-- /section: component_test_entrypoint -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs `detect` / `suggest` / `adopt` / `howto` *(new)*

`internal/onboard`. `detect`: the closed detector list with an evidence field
per row, `UNIVERSE`, `UNLISTED`, `AGGREGATE_RUNNER`, `SERIAL_LIST`,
`RESOURCE_HINT`, `SUITE_CANDIDATE`, `RUNNER_SCRIPT_NEEDED`. `suggest`: the
five-signal join over the n006 dependency scanners with helper/subject
separation by root and fan-in, `SUGGEST_*` line classes, `--json`. `adopt`:
level-0 registry files, stamped blocks through `internal/annot`'s rewriter,
`registry/adopted.yaml`, level-2 lines and `needs:` bindings, level-3
`axes.yaml` skeleton and runner scaffold; `ADOPT_REFUSED` / `ADOPT_SKIP` /
`WROTE` / `ADOPT_SUMMARY`. `howto`: the `--howto` renderer over
`runners.yaml`, `resources.yaml`, `config.yaml` and the cost ledger. Go tests
on fixture repositories in `t.TempDir()`: one per detector, the fan-in
reclassification, a synthetic `(t<id>)` history for co-change, golden files
for block placement per language, every refusal branch.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(new)*

Profile-aware stub + `SKILL.md.j2` (resolver key `onboard`), Claude Code first,
Codex and OpenCode ports as follow-up tasks. Preconditions → read-only survey
→ level proposal → per-class and per-kind confirmation → config table →
onboarding aitask created with the suggest JSON attached → task-workflow
(adopt at Step 7, diff at Step 8, first full run at Step 9) → timeout from
the ledger, `readiness`, next-level task with `depends:`. Headless: level 0 +
static-only level 1 at 0.95. `--policy selected` re-entry writes the flip only
on `ADMISSIBLE`. Rendered goldens under `tests/golden/skills/aitask-testmap-onboard/`.
<!-- /section: component_onboarding_skill -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(new)*

`## Running Tests` in `seed/aitasks_agent_instructions.seed.md`, installed by
`assemble_aitasks_instructions()` into `CLAUDE.md`'s `>>>aitasks` block,
`AGENTS.md`, `.codex/instructions.md` and the OpenCode mirror on every `ait
setup`; no project specifics (computed by `--howto`); `tests/test_agent_instructions.sh`
T40 pins the heading in all four surfaces; the hand-maintained `CLAUDE.md`
case is the onboarding task's edit.
<!-- /section: component_agent_instructions -->

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(new)*

`aitestmap/config.yaml completion: {mode, deferred, on_empty_selection,
engine_absent}`; `mode: selected` written only by the skill after
`ADMISSIBLE` with `approved_by`; `ait test --gate` re-checks readiness on
every completion run and demotes loudly (`POLICY_DEMOTED:`) — the flip is
human, the demotion automatic, so the policy fails only toward running more.
<!-- /section: component_completion_policy -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(new)*

`test-discovery.md` 3a–3c read the registry (`explain --source`) when
`aitestmap/` exists and fall back to the naming-convention scan otherwise;
`test-execution.md` 4a runs the configured `./ait test` through
`aitask_run_project_command.sh test_command --task-id <id>`, 4b runs named
units through `ait test <path>`, 4c gains the `REFUSED` row, 4d scores
coverage from edges; `REFUSED` is treated as `SKIP` in the health score.
<!-- /section: component_qa_integration -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam *(new)*

The concrete edit list of the previous section: the Step-7 paragraph, the
`build-verification.md` branch, the two rows and two exports in
`run_project_command_key()`, `--task-id` export in
`aitask_run_project_command.sh`, `gates_reference.yaml` entries (no
`testmap_run`), profiles' `default_gates`, the `test)` dispatcher arm, the
extension-points section, the extended `tests/test_gate_verifiers.sh` and
regenerated goldens.
<!-- /section: component_workflow_seam -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(modified)*

`testmap_fresh` (procedure) and `testmap_check` (machine, `unlocks:
[tests_pass]`) in the reference registry; the completion test gate is the
existing `tests_pass` with `test_command: ./ait test` and the opt-in;
`testmap_run` retired as a name, its logic `ait test --gate`, its timeout a
project `tests_pass.timeout_seconds` from `costs --gate-timeout`, its 75 →
error mapping in the shared lib; `aitask_gate_testmap_run.sh` not written;
`run_gate_admission` and `readiness` gate the policy flip instead of a second
gate's declaration.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(modified)*

`aitask-testmap` and `aitask-gate-testmap-fresh` as in n006, plus
`aitask-testmap-onboard`; the runtime knowledge an agent needs is the seeded
block plus `--howto`, never prose in a SKILL.md.
<!-- /section: component_skill -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(modified)*

n006's `describe` / `list` / `run` contract unchanged; two repository keys
added: `subsumed_by: <suite>` (so `run --all` executes a `full: true` suite
once and never its subsumed runners beside it) and `fallback_command:` on a
suite runner (what completion runs when the engine is absent and the policy
allows).
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(modified)*

n006's builtins; `detect` seeds the repository — bash-file, pytest (serial
carve-out → `testmap:batch no`), go-test per package, gradle-class, the
`kmp-sourceset` mapping (`commonTest` / `androidHostTest` → gradle-class unit
runners, `androidDeviceTest` → `device` with `needs: [emulator]`), and a
`full: true` suite runner from `test_command` / `verify_build`.
<!-- /section: component_reference_runners -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(modified)*

n006's six tables plus `registry/adopted.yaml`, written only by `adopt`, rows
removed when a human re-stamps the edge — the set of covers edges nobody has
reviewed yet.
<!-- /section: component_registry_loader -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(modified)*

n006's line classes; a row whose edge has an `adopted.yaml` entry carries
`adopted(<signals> <confidence>)` in its `DISPLAY` line so the procedure gate
knows it is confirming a machine-seeded claim.
<!-- /section: component_staleness_tool -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(modified)*

n006's `score` / `attribute` / `readiness`; `readiness` additionally prints
`LEVEL`, `NEXT`, `ADOPTED_UNREVIEWED:<n>|<ratio>` and `POLICY:<mode>|<what
--gate would run now>`; still enables nothing.
<!-- /section: component_feedback_tools -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(modified)*

n006's Welford / P² / invocation-group ledger; `costs --gate-timeout <gate>`
prints `GATE_TIMEOUT_SUGGESTED:<gate>|max(600, 3 × p95 of the newest full run)`.
<!-- /section: component_cost_ledger -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(modified)*

n006's packages plus `internal/onboard`; verbs gain `detect | suggest | adopt |
howto`; the engine still never writes `project_config.yaml`, `gates.yaml`,
profiles or `CLAUDE.md`.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(inherited from n006)*

Version / commit / contract embedding, `version --json`, `CONTRACT_MISMATCH`,
the bench budget. `detect` and `suggest` are excluded from the latency table
(they run once per onboarding, exec `git log`, and are not on any gate path).
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n006)*

Unchanged: `engine/build.sh`, the release `engine` job, `engine-check.yml`,
the shim's strict handshake, `platform_detect.sh`.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install and developer regeneration *(inherited from n006)*

Unchanged: `install_engine_binary()`, `ait engine build|test|cross|prune|home`.
`aitask_test.sh` is a framework script shipped in the tarball like every
`aitask_*.sh`; nothing to install.
<!-- /section: component_engine_packaging -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n006)*

`lib/aitasks_home.sh`, `$AITASKS_HOME/engine/`; unchanged.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(inherited from n006)*

`ait engine home [--migrate]`; unchanged, default flip still a named follow-up.
<!-- /section: component_framework_home -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n006)*

`axes.yaml`, `<unit>@<variant>`, the facet join; unchanged. Level-3 adoption
writes only the skeleton the maintainer fills.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n006)*

`axes --list | --check | --explain`; unchanged.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n006)*

The runner's `list` as the universe, `UNCOVERED_VALUE`, `UNMAPPED_ARTIFACT`;
unchanged. `detect`'s `UNIVERSE:` is the same count taken before runners exist.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(inherited from n006)*

Grammar v3 and the line-targeted rewriter; unchanged — `adopt` is a new
*caller* of the rewriter, not a new writer.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(inherited from n006)*

bash / python / go / kotlin / gradle scanners and plugins; unchanged —
`suggest`'s `static` signal is their forward closure read from the same
blob-keyed cache.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(inherited from n006)*

Intake, graded walk, variant expansion, budget, formats; unchanged. `ait test
<source path>` reaches it as a one-row `TASK:` change set from the shim.
<!-- /section: component_selector -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n006)*

Unchanged; `detect`'s `RESOURCE_HINT` rows become `resources.yaml` entries the
scheduler already understands (aitasks: `repo-git-index` mutex, worktree scope).
<!-- /section: component_scheduler_resources -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n006)*

Unchanged; the onboarding task's first full run is what first populates the
anchors it reads.
<!-- /section: component_evidence_join -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(inherited from n006)*

Unchanged; an adopted stamp is a stamp like any other and the procedure gate
handles it identically, with the `adopted(...)` display as context.
<!-- /section: component_freshness -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(inherited from n006)*

Unchanged; level-0 adoption calls `areas --import-codemap`, level 2 writes the
scoped rows' source lines.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n006)*

Unchanged; `completion.deferred: run` means the suite budget applies to the
interactive loop only.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

**Inherited unchanged from n006** (the full text is in the node metadata):
`assumption_areas_express_suite_blast_radius`, `assumption_axis_membership_declarable`,
`assumption_axis_sources_declarable`, `assumption_batch_per_unit_timing_reportable`,
`assumption_blob_digest_is_staleness_key`, `assumption_broad_tests_area_scoped`,
`assumption_cells_enumerable_by_plugin`, `assumption_change_surface_is_intake`,
`assumption_engine_latency_targets`, `assumption_existing_locks_wrappable`,
`assumption_git_history_is_freshness_clock`, `assumption_go_toolchain_available`,
`assumption_go_toolchain_ci_and_dev_only`, `assumption_home_symlink_compatibility`,
`assumption_kotlin_scanner_fail_closed`, `assumption_legacy_user_root_coexists`,
`assumption_one_engine_per_framework_version`, `assumption_passing_run_anchors_edges`,
`assumption_platform_matrix_sufficient`, `assumption_release_asset_reachable`,
`assumption_release_assets_reachable`, `assumption_static_granularity_v1`,
`assumption_target_repos_accept_aitestmap_root`, `assumption_testmap_token_no_collision`,
`assumption_variant_universe_from_runner_list`.

**Modified:**

- **`assumption_gate_exit_contract_reused`** — the verifier contract is reached
  through the *existing* `tests_pass` verifier running `test_command: ./ait
  test`; `run_project_command_key()` gains the 75 → error and 3 → error rows for
  opted-in keys; the verifier exports `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`;
  `testmap_check` keeps its own shell. n006 reused the contract through two
  dedicated shells; here it is one shell plus one row in the shared lib, which
  is what lets the legacy Step-9 helper and `aitask-qa` agree by construction.

**New:**

- **`assumption_static_closure_seeds_edges`** — measured: 398/400 bash tests
  name their subject path literally, 320/320 Python tests import a lib module,
  52/400 match the naming convention; Go's subject is deterministic; Kotlin's
  is the n006 import closure. *Falsifier:* tests reaching subjects only through
  a dynamic dispatcher — `suggest` emits no static rows, and the answer is
  conventions plus co-change, or level 0.
- **`assumption_cochange_is_corroboration`** — 336 task groups in 400 commits,
  1.14 commits per group, few-to-few pairing inside a group; capped at 0.6 so
  it never decides alone; per-commit grouping where the `(t<id>)` convention is
  absent.
- **`assumption_helpers_separable_by_fanin`** — helper roots plus fan-in ≥ 5 %
  of a runner's units; a misread hot production module keeps `test-dep`
  selection (over-selects) and every reclassification is listed for review.
- **`assumption_task_resolvable_from_session`** — the `aitask/<task_name>`
  branch in worktree mode, the single own lock in current-branch mode,
  `AIT_GATE_TASK_ID` in gate context; `AMBIGUOUS_TASK` and `--dirty` cover the
  rest. *Falsifier:* work outside the workflow — explicit intake only.
- **`assumption_full_run_expressible_per_repo`** — each of the five targets'
  completion suite is `ait test --all` or one `full: true` suite runner, with a
  derivable `fallback_command`; thinking_backend's suite is wired as
  `verify_build` and is the case the skill asks about.
- **`assumption_annotation_is_comment_only`** — adoption inserts comment lines
  only; `git diff -w --ignore-blank-lines` of an adopted file shows comments;
  `ADOPT_SKIP:no-leader` otherwise.
- **`assumption_instruction_block_is_read`** — agents follow the managed
  `CLAUDE.md` / `AGENTS.md` block, as the framework already relies on for `./ait
  git`; `ait setup` regenerates it on every run. *Falsifier:* a harness that
  ignores the file — `--howto` is the one-call fallback.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

**Inherited unchanged from n006** (full text in the node metadata):
`tradeoff_area_glob_coarseness`, `tradeoff_attribution_risk`,
`tradeoff_autonomous_confirmation_weak`, `tradeoff_axis_declaration_burden`,
`tradeoff_axis_projection_coarseness`, `tradeoff_batch_misreport_risk`,
`tradeoff_broad_scope_coarseness`, `tradeoff_cell_table_size`,
`tradeoff_compiled_component_cost`, `tradeoff_computed_vs_prose`,
`tradeoff_engine_absent_on_host`, `tradeoff_engine_speed_enables_per_task_use`,
`tradeoff_engine_version_skew`, `tradeoff_evidence_requires_reachable_history`,
`tradeoff_flaky_pass_anchors`, `tradeoff_home_migration_window`,
`tradeoff_intersection_can_underselect`, `tradeoff_member_annotation_drift`,
`tradeoff_noarch_packages_preserved`, `tradeoff_real_scheduler`,
`tradeoff_registry_directory_complexity`, `tradeoff_resource_declaration_completeness`,
`tradeoff_setup_network_fetch`, `tradeoff_split_home_rejected`,
`tradeoff_static_scanner_overselection`, `tradeoff_strict_version_handshake`,
`tradeoff_two_toolchains`, `tradeoff_two_user_roots`, `tradeoff_whole_run_filter_soundness`.

**Modified:**

- **`tradeoff_fail_closed_bootstrap_cost`** — *narrowed.* The bootstrap order
  becomes one aitask the skill creates and runs; `detect` and `suggest` are
  read-only; level 0 writes only registry files; the onboarding task's own
  `tests_pass` is the first anchoring full run; `bootstrap_until` is set by
  `adopt`; `readiness` prints `LEVEL` / `NEXT`. What remains: a repository is
  level 0 (bound, closure-selected, unstamped) until a human accepts level 1,
  and headless profiles stop at level 0 plus static-only edges.
- **`tradeoff_stamp_churn`** — *one clause added.* Level 1 on aitasks touches
  ~720 files with one to eight comment lines each; mitigated by `--scope
  <glob>` per area across tasks, the diff being comments only, `ADOPT_REFUSED`
  on dirty-foreign files, and the reviewed `(t<id>)` commit.

**New:**

- **`tradeoff_one_gate_not_two`** — *Advantage:* one completion gate whose
  behaviour is a committed policy; one command for agents; the legacy Step-9
  path and `aitask-qa` reach the selective lane through `test_command`; the
  flip is one line after readiness. *Disadvantage:* a ledger `tests_pass: pass`
  no longer says by itself whether the whole suite ran — mitigated by
  `result="MODE:<full|selected>|<n>|policy:<mode>"` on the gate-run block,
  `POLICY_DEMOTED` being loud, and `readiness` printing what `--gate` would run.
- **`tradeoff_seed_precision`** — *Risk:* an adopted `covers` edge says the
  test *executes* the source, not that it *verifies* it; a test that drives
  three scripts to set up one adopts three edges. Narrowed by `adopted.yaml`
  provenance shown in `stale` / `explain`, `ADOPTED_UNREVIEWED` in readiness,
  the over-claim direction only over-selecting, the 0.85 threshold, and
  three-sample display per class; a coupling the closure does not contain is
  still caught only by a full run's score, as in n006.
- **`tradeoff_fallback_runs_more`** — *Disadvantage:* with the engine absent and
  `engine_absent: fallback_command`, completion runs the pre-onboarding suite
  command — never less than before, never selective, no per-unit results or
  anchors; the default is `error`, and `MODE:fallback` is visible.
- **`tradeoff_verify_build_wired_suites`** — *Disadvantage:* a suite wired as
  `verify_build` (thinking_backend, half lint) cannot be moved mechanically
  without either dropping the lint half or double-running; the skill asks,
  defaults to keeping it, records the answer in the plan; headless keeps.
- **`tradeoff_dispatcher_verb_added`** — *Disadvantage:* `ait test` beside `ait
  testmap`, two surfaces for one engine; justified by the human-would-type-it
  rule and the seed's need for one verb; kept thin; `ait testmap` remains the
  maintainer surface; `--howto` names `ait test` as the stable one.
- **`tradeoff_bulk_confirmation_granularity`** — *Risk:* per-class acceptance
  trades review depth for feasibility; mitigated by samples, `review a sample`,
  `--accept-min`, `--scope`, `adopted.yaml`, and individual confirmation of
  kind changes because a wrong kind changes staleness semantics.
<!-- /section: tradeoffs -->

<!-- section: changes_to_baseline [dimensions: component_gates, assumption_gate_exit_contract_reused, requirements_gate_enforcement] -->
## Changes to the Baseline, Stated

1. **`testmap_run` is retired as a gate name.** n006 had `tests_pass` (full,
   the completion gate) beside `testmap_run` (selected, `blocks_dependents`,
   `max_retries: 1`, `timeout_seconds: 1800`, unlocked by `testmap_check`,
   declared only when `readiness` is admissible). Here `tests_pass` runs
   `./ait test --gate` and the *policy* is what readiness admits. Every
   property of `testmap_run` has a home: its verifier logic is `ait test
   --gate`; `blocks_dependents` and `max_retries: 1` are `tests_pass`'s own;
   its timeout is a per-project `tests_pass.timeout_seconds` from the ledger;
   its exit mapping (0/1/2/75/64 → 0/1/2/3/3) is the shared lib's new rows;
   `testmap_check` unlocks `tests_pass`. Reason: an agent should know one gate
   and one command, and "which tests run at completion" is a project decision
   that belongs in committed data with an automatic demotion, not in which of
   two gates a task happened to declare. n006's thinking_app rule — full
   suite as the completion gate until admissible — is preserved exactly by
   `completion.mode: full`.
2. **The command exit contract gains two rows for opted-in keys.** 75 →
   `error` (`command_refused`), 3 → `error` (`command_errored`), in
   `run_project_command_key()`'s docblock and body — the single canonical
   statement — inherited by the three verifiers, the legacy helper and
   `aitask-qa`. Non-opted-in keys are unchanged. This is the smallest change
   that keeps n006's "75 → verifier 3, never skip" once the verifier is the
   command-driven `tests_pass`.
3. **`aitask_gate_testmap_run.sh` is not written**; `aitask_gate_testmap_check.sh`
   is. Everything else in n006's component list is unchanged or extended by a
   clause named in *Components*.
<!-- /section: changes_to_baseline -->

<!-- section: open_questions -->
## Open Questions

1. Should level 1 be accepted automatically for `go-test` projects (confidence
   1.0, deterministic subject) even under attended profiles? Proposed: yes, with
   the summary still shown.
2. Should `adopt` write `testmap:reads` into a helper under `tests/lib/` without
   asking, given a missing `reads` under-selects? Proposed: propose always,
   write on class acceptance, because the fallback (`test-dep`) still selects
   every importer on the helper's own change — only the *glob* is the addition.
3. `AIT_GATE_TASK_ID` is also visible to any other `test_command` — should the
   export be limited to commands matching `./ait test*`? Proposed: no; an
   environment variable a command ignores is harmless, and a project's own
   wrapper may want it.
4. Should `completion.on_empty_selection` default to `full` rather than `skip`
   for a `selected` policy? An empty selection with a non-empty change surface
   is a strong "the map does not know this file" signal. Proposed: `skip`
   during bootstrap, `full` once `require_stamp: true` — `readiness` prints the
   recommendation.
5. Where does the onboarding skill's `--policy selected` approval statement
   live for a project without a design record like thinking_app's
   `change-aware-verification.md#what-this-cannot-do`? Proposed: the skill
   writes `aitestmap/ADMISSION.md` from the readiness output and the user's
   statement, and `approved_by.statement` points at it.
6. `aitask_lock.sh --list-mine` is a new verb on an existing script; is a
   `ait ls`-based query (`status Implementing`, `assigned_to` = me) preferable
   so no lock-format knowledge leaves the lock script? Either satisfies the
   resolution rule; the proposal names the lock because it is host-scoped.
7. Should the onboarding task be *one* task per level or one parent with a
   child per level? Proposed: one task per level with `depends:`, because a
   level may wait weeks on the full-run history and a parent would sit
   Implementing the whole time.
8. Baseline questions still open (n006 §Open Questions 1–11) are unchanged;
   n006's question 9 (aitasks_mobile axis) is answered here: no axis, source
   sets are runner/kind distinctions.
<!-- /section: open_questions -->
--- PROPOSAL_END ---
--- NEW_DIMENSIONS ---
assumption_annotation_is_comment_only,assumption_cochange_is_corroboration,assumption_full_run_expressible_per_repo,assumption_helpers_separable_by_fanin,assumption_instruction_block_is_read,assumption_static_closure_seeds_edges,assumption_task_resolvable_from_session,component_agent_instructions,component_completion_policy,component_onboarding_engine_verbs,component_onboarding_skill,component_qa_integration,component_test_entrypoint,component_workflow_seam,requirements_agent_instructions_seeded,requirements_onboarding_existing_tests,requirements_workflow_seam_is_data,requirements_zero_config_entrypoint,tradeoff_bulk_confirmation_granularity,tradeoff_dispatcher_verb_added,tradeoff_fallback_runs_more,tradeoff_one_gate_not_two,tradeoff_seed_precision,tradeoff_verify_build_wired_suites
