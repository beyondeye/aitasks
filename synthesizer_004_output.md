--- NODE_YAML_START ---
node_id: n013_synthesizer_004
parents:
- n011_explorer_005a
- n012_explorer_005b
description: 'Agent-closed adoption loop over the unchanged n010 architecture (static Go engine under
  $AITASKS_HOME/engine/v<VERSION>/, blob-digest stamps, evidence join, scoped rows, axes, graded walk,
  scheduler, cost ledger, scoring, the three-state adoption ledger, levels x phases onboarding, `ait test`
  in three modes, one tests_pass completion gate) merged from n011 and n012: the origin table gains a
  class column (rule static:package / measurement coverage / reading agent:review, agent:author / heuristic)
  and the autonomous floor becomes ''every member carries a rule, a measurement or a reading and clears
  accept_min''; the engine cuts bounded, digest-stamped line-protocol packets (`onboard review`: anchor
  +-20 lines, assertion lines flagged, declared symbols only, packet_sha) and one intake (`onboard adopt
  --agent-verdicts - --by <agent-string> --run <id>`) consumes VERDICT:<id>|verifies|<test path:line>|
  <rationale> / drives / unsure lines, validating the assertion-line anchor (VERDICT_INVALID) and the
  packet digest (VERDICT_STALE); a verifies verdict adopts with by: agent:<agent-string> (adopted.yaml
  rows carry by: human:<email>|agent:<agent-string>|auto plus run, rationale, assert_line, packet_sha),
  while drives and unsure PARK the seed (still selecting, out of autonomous adoption, REVIEW_PARKED; two
  unsure -> REVIEW_HUMAN) - no agent verdict ever removes a seed, so no revocation exists and a scored
  miss that contradicts a human rejection is only printed (REJECTION_CONTRADICTED); calibration is both
  passive (REVIEW_AGREEMENT vs human per-row decisions) and explicit (`onboard review --calibrate` vs
  coverage facts), writing agent_review.measured_confidence and stopping verdict adoption below accept_min;
  completion.mode auto is the value detect --write writes in both profiles (confirmed in the attended
  config table), flips on the first ADMISSIBLE run with approved_by engine:readiness@<run> recorded in
  the engine''s own ledger aitestmap/costs/policy.yaml (committed by the bash front under `ait: testmap
  policy <flip|full-run> (t<id>)`, config.yaml staying human-authored) behind a required cadence completion.full_run_every
  {tasks 5, selection_ratio_above 0.60, days 7} whose full runs score every prediction in the window;
  the pre-review procedure''s autonomous branch stamps pairs whose two files are both on the task''s change
  surface through `annotate --author --by <agent-string>` (AUTHOR_REFUSED otherwise, AUTHOR_UNCORROBORATED
  flagged, agent_review.author the switch); the reading happens at three sites sharing the intake - the
  testmap_fresh in-gate step (attended pre-fill / confirm / trust-batch, autonomous adopts), the pre-review
  procedure, and the new bulk skill aitask-testmap-review launched only through framework wrappers (`ait
  skillrun testmap-review` interactive, `ait codeagent testmap-review` with --print only under --headless,
  or crew agents `ait crew runner` starts through `ait codeagent`) - the engine never launches a code
  agent and no default path uses print mode; kinds stay human (headless `classify --propose` -> kind_proposals[]),
  axes stay human, headless profiles complete levels 0 and 1 and finish --auto with parked rows listed.'
proposal_file: br_proposals/n013_synthesizer_004.md
created_at: "2026-09-20 10:19"
created_by_group: synthesize_004
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
- .aitask-scripts/aitask_codeagent.sh
- .aitask-scripts/lib/agent_string.sh
- .aitask-scripts/aitask_skillrun.sh
- .aitask-scripts/aitask_crew_init.sh
- .aitask-scripts/aitask_crew_addwork.sh
- .aitask-scripts/aitask_crew_runner.sh
- .aitask-scripts/aitask_crew_status.sh
- aidocs/agentcrew/agentcrew_architecture.md
- aidocs/agentcrew/agentcrew_work2do_guide.md
- aidocs/gates/aitask-gate-framework.md
- aidocs/gates/ledger-driven-reentry.md
- .aitask-scripts/aitask_note.sh
- .aitask-scripts/lib/gate_ledger.py
- .aitask-scripts/aitask_gate_record.sh
- .aitask-scripts/aitask_run_gates.sh
- .aitask-scripts/lib/launch_modes.py
- .aitask-scripts/aitask_add_model.sh
- .claude/skills/aitask-add-model/SKILL.md
- .claude/skills/aitask-review/SKILL.md.j2
- seed/models_claudecode.json
- seed/models_codex.json
- seed/models_opencode.json
- .aitask-scripts/agentcrew/agentcrew_runner.py
- tests/test_codeagent.sh
requirements_agent_instructions_seeded: 'No code agent learns how to run tests from the repository at
  session start: the shared agent-instructions seed (seed/aitasks_agent_instructions.seed.md) gains a
  fourteen-line `## Running Tests` section - always `./ait test`, never the test tool directly; `./ait
  test <path>` for one unit; `./ait test --all`; `./ait test --howto` for project specifics; UNANNOTATED_TEST
  -> `./ait testmap annotate --suggest`; UNMAPPED_SOURCE -> map it before the gate; TESTMAP_ABSENT ->
  /aitask-testmap-onboard; the exit-code table - which ait setup already installs into CLAUDE.md''s >>>aitasks
  block, AGENTS.md, .codex/instructions.md and the OpenCode mirror through assemble_aitasks_instructions();
  the section is written before onboarding because `ait test` is correct in every repo state; a hand-maintained
  CLAUDE.md (this repository''s) is edited by the level-0 onboarding task instead; project specifics live
  only in --howto''s computed output.'
requirements_agent_run_surface: 'Any code agent runs the right tests in any onboarded project without
  learning the project: one front verb, `ait test`, with four agent-facing forms - `./ait test` (the tests
  the task''s attributed change reaches, a reason per row, the task resolved from the branch or lock),
  `./ait test <path>...` (the tests reaching those sources, or those test files themselves), `./ait test
  --all` (the full registered suite, what completion runs under a full policy) and `./ait test --howto`
  (this project''s runners, resources, full gate, gates, axes, policy, level, docs and notes, generated
  from the registry) - taught once by a generic Running Tests section in the seeded >>>aitasks agent-instructions
  block that ait setup writes into every supported agent''s instructions file, so the sentence an agent
  reads is the same in aitasks, thinking_app and aitasks_mobile and the project-specific facts come from
  `--howto`, never from prose the agent has to find; the same verb is correct before onboarding (it runs
  test_command and prints the onboarding hint).'
requirements_agent_skill: 'Agent skills teach agents how to keep the map current as they write code and
  tests (annotate a file, a testmap:unit member or a testmap:axis coordinate, declare an axis source,
  put testmap:reads on a tree-scanning helper, axes --explain, attribute before the gate, verify after
  editing, classify --suggest, confirm or retarget stamps in the procedure gate, drive a render loop from
  select --format tokens, and NAME the pair for a test they wrote through `annotate --author`) AND how
  a repository''s EXISTING tests get onto the map without a person: aitask-testmap-onboard is the resumable,
  profile-aware migration of an existing test tree in graded levels (detect tools -> generate aitestmap/
  -> inventory -> seed edges from the origin table -> waivers -> enable gates -> first full run -> adopt
  by rule and measurement, then by reading -> classify kinds -> scaffold axes), each level an ordinary
  aitask whose annotation diff is reviewed and committed under a (t<id>) with provenance kept in registry/adopted.yaml;
  its level-1 reading is the new aitask-testmap-review skill, which reads engine-cut packets (`onboard
  review --next 20`) and returns VERDICT lines that `onboard adopt --agent-verdicts - --by <agent-string>
  --run <id>` turns into stamped edges with by: agent provenance or parked marks, launched only through
  `ait skillrun testmap-review`, `ait codeagent testmap-review [--headless]` or `ait crew runner`; the
  same intake serves the testmap_fresh in-gate step and the pre-review procedure; and the generic `##
  Running Tests` section of the seeded agent-instructions block plus `ait test --howto` are how an agent
  learns the run surface once, identically in every project - the daily-use surface shrinks to `./ait
  test`, `./ait test --howto` and `./ait testmap annotate --suggest <new test>`.'
requirements_annotation_freshness: 'Every STAMPED unit coverage annotation carries the date and blob digest
  of the covered source at confirmation, scoped to the member block where the unit is a member, with committed
  last_pass anchors per variant letting stale prove EVIDENCED so most hot-source churn needs no rewrite;
  a SEEDED edge carries no stamp and makes no freshness claim - it lives in registry/seeded.yaml, selects
  at d1, and is invisible to stale, whether or not a verdict parked it; `onboard adopt` (by class, by
  row, or from a verifies verdict) and `annotate --author` are the acts that turn a seed or an author
  claim into a stamped testmap:covers line through the rewriter, with an adopted.yaml provenance row recording
  origin[], confidence and by: human:<email>|agent:<agent-string>| auto (plus run, rationale, assert_line
  and packet_sha for a reading) that stale and explain display until a human re-stamps the edge - so a
  stamp always records who accepted the claim, whether that was a person, an agent or a rule, at what
  level of review, and against which bytes; the procedure gate at the post-implementation step hands the
  report to an agent that fixes annotations and, reading the packets for the touched files'' seeds, adopts
  or parks them before the task commit (attended: a person confirms the agent''s pre-filled verdicts;
  autonomous: the verdicts are the adoption).'
requirements_annotation_staleness: A stale verb reports, for a task's change set or repo-wide, STALE_PATH
  (deleted or renamed source, fail-closed), STALE (content changed, no evidence on every reached variant,
  the unevidenced variants named), EVIDENCED, UNSTAMPED, STALE_AREA and opt-in REVIEW_DUE rows in the
  framework's fixed line protocol, plus one CHECK_STRUCTURAL:<n> summary line on --all; seeded edges are
  excluded from every stale class (they claim nothing), stale --all adds SEEDED:<n> and ADOPTED:<n> summary
  lines so a repo-wide sweep sees how much of the map is provisional or machine-accepted, and a row on
  an adopted edge carries adopted(...) in its DISPLAY line; structural rot on axes, members, variants
  and artifacts stays check's; digest comparison needs no git history, evidence only removes nags.
requirements_axis_product_selection: 'A project whose tests form a product of named facets (thinking_app:
  49 screens x 10 matrices where a matrix is locale x direction x geometry; aitasks: skill x profile x
  agent goldens) declares the axis with its facets, values and facet-valued source globs, and lets the
  engine select exact variants - an axis-source hit selects the variants carrying the facet value, any
  other hit selects every variant, hits union - instead of choosing between thousands of hand edges and
  one all-or-nothing suite scope; a source matching no axis source reaches units only through edges and
  dependencies, which select every variant, the fail-safe direction; intersection reduces to the facet
  join on every single-file case.'
requirements_broad_test_handling: 'Scoped rows are ranked after unit tests at equal distance, selected
  under an explicit suite budget that prints every DEFERRED cut, scheduled only after the unit wave is
  green (broad_after_unit), widened by attribute on a full-run miss, and drift-flagged by evidence (STALE_AREA)
  rather than by calendar; a suite row marked full: true with a children: post-processor anchors registered
  ids on every run.'
requirements_cost_tracking: Tracks cost per test unit and per variant, keyed by host class, using Welford's
  online update (n, mean, standard deviation, p95, last), plus a last_pass {sha, at, run_id} anchor and
  a flake rate per id; per-invocation overhead rows are a first-class input keyed by invocation group,
  so a selection's estimate is the sum over groups of overhead.p95 + the marginal p95 of each selected
  id - a second method in a booted Robolectric class costs its per-unit mean, not another boot.
requirements_dev_rebuild_from_source: A framework developer rebuilds the engine with one command (ait
  engine build) through the same engine/build.sh that CI uses, into $AITASKS_HOME/engine/dev/ which the
  shim selects via AIT_ENGINE=dev (version must read <V>-dev+<sha>); ait engine cross produces the CI
  matrix locally, byte-identical.
requirements_engine_dev_regeneration: The GOOS/GOARCH matrix, CGO_ENABLED=0 and ldflags live in one script
  (engine/build.sh) shared by release CI, ait engine build and ait engine cross; ait engine test runs
  go vet and go test; ait engine prune removes versions under $AITASKS_HOME/engine/ that no registered
  project is on; ait engine home reports the root, legacy tenants and symlink state and performs the migration
  on --migrate.
requirements_engine_packaging: ait setup and ait upgrade (through install.sh's --source-only path) install
  the host's binary under $AITASKS_HOME/engine/v<VERSION>/ with checksum verification, a .sha256 sidecar
  and a version --json self-check that also prints ENGINE:<path>; fallbacks --local-engine, --engine-from-source,
  AIT_TESTMAP_BIN; opt-out --no-testmap / AIT_TESTMAP_FETCH=0; setup prints AITASKS_HOME:<path> and, when
  legacy tenants exist, HOME_LEGACY:<path>|run 'ait engine home --migrate' and continues; setup's summary
  ends with one TESTMAP:absent|bootstrapping|<next>|onboarded[|engine-missing] line computed by report_testmap_state()
  from the presence of aitestmap/ and onboard.yaml's phase ledger, with the hint `run /aitask-testmap-onboard`
  on absent - setup reports, it never onboards; and the re-inserted >>>aitasks instructions block carries
  the generic Running Tests section, so the run surface reaches every project's agent instructions on
  the next setup or upgrade with no per-project step.
requirements_feedback_loop: 'Learns from failures the map did not predict via a score/attribute feedback
  loop: every task-scoped selection (an interactive `./ait test` or the pre-review advisory run) writes
  the task''s prediction record and the newest one wins; every full run (run --all, `ait test --gate`
  under a full policy or a cadence-triggered full run under auto, or a full: true suite runner) automatically
  scores that record and prints PREDICTION_FALSE_NEGATIVES:<n> plus one PREDICTION_MISSED:<id>|<task>
  line per miss, appending to a committed costs/predictions.yaml that readiness counts; under auto a cadence
  full run (every full_run_every.tasks-th selected completion, a selection over selection_ratio_above
  of the full p95, or days since the last full run) scores every unscored prediction since the last full
  run and attributes each miss to the earliest task in the window whose change surface reaches the failing
  unit (culprit ids from git log -M when history is reachable), so scoring never stops once the gate shrinks;
  the pre-review advisory run is the selection guaranteed to exist in every profile, so every task that
  reaches completion has something to score; attribute records an observed edge for a unit or member,
  an observed axis source for a facet value (widen only, never narrow), and an observed trigger or area
  member for a broad test, merged into the registry at load; an attribute proposal a reviewer has not
  decided lands in registry/seeded.yaml with origin `observed` so it selects immediately and is read through
  the same review and adopt queue as onboarding seeds; a miss that contradicts a human rejection prints
  REJECTION_CONTRADICTED and keeps the row; the review pass feeds the loop the other way - every human
  per-row adopt or reject labels a verdict and REVIEW_AGREEMENT, with `onboard review --calibrate` against
  coverage facts, calibrates the agent:review origin, writing measured_confidence and stopping verdict
  adoption below accept_min; `onboard status` reports the queue (seeded per origin and per verdict, adopted
  split by human/agent/auto, parked, REVIEW_HUMAN, rejected, oldest pending age) so adoption is measurable
  rather than remembered.'
requirements_framework_home_name: 'The framework is named aitasks, so every path it owns under the user''s
  home should be ~/.aitasks - the engine installs there now, and the legacy ~/.aitask tree is migrated
  by an explicit verb, ait engine home --migrate (flock, per-entry rename, rmdir, compatibility symlink;
  known set including pypy_venv), with ait setup printing a HOME_LEGACY: hint in this release and a named
  follow-up flipping the default once the verb has passed a real install.sh --dir test.'
requirements_gate_enforcement: 'Enforced by gates so the map cannot rot silently: testmap_fresh (procedure,
  before the task commit; reads packets for the seeds on the test files this task touched and adopts or
  parks them - attended with a person confirming the agent''s pre-filled verdicts, autonomous on the agent''s
  verdicts alone), testmap_check (machine; fails STALE_PATH on its own; reports SEEDED:<n>, ADOPTED:<n>|human
  <h>|agent <a>|auto <m> and UNMAPPED_SOURCE:<path> rows; fails the structural rows plus UNMAPPED_SOURCE
  only under --strict past bootstrap_until; unlocks: [tests_pass]) and ONE completion test gate - the
  existing tests_pass, whose test_command is `./ait test`, which runs the whole registry or the task''s
  selection according to the committed completion policy in aitestmap/config.yaml: auto by default (written
  by detect --write, confirmed in the attended config table) - identical to full until `ait testmap readiness`
  reports ADMISSIBLE, then the selection with approved_by engine:readiness@<run> recorded by the engine
  in costs/policy.yaml and committed by the verifier''s caller, full whenever a cadence trigger fires
  (full_run_every.tasks | selection_ratio_above | days, printed as POLICY:auto|full|cadence:<trigger>),
  demoted back to full at run time if readiness regresses, and a cadence full run never skipped by on_empty_selection
  or a demotion; selected only after readiness reports ADMISSIBLE and a human records approved_by in config.yaml;
  full as the opt-out. There is no separate selection gate: its verifier logic is `ait test --gate`, blocks_dependents
  and max_retries: 1 are tests_pass''s own, and the timeout is a per-project tests_pass.timeout_seconds
  written from the measured full-run p95 (`ait testmap costs --gate-timeout`). A command key opted into
  gate_command_exit_contract also reads exit 75 and exit 3 as verifier error, never fail and never skip.
  The selection gate a two-gate design would declare IS tests_pass under completion.mode selected or auto,
  and the ledger block''s result= field carries MODE, policy, next_full_in:<n> or cadence:<trigger> so
  a reader knows whether the whole suite ran and why. Gates are enabled by the onboarding skill''s enable
  phase (which edits the profile''s default_gates / rendered_gates with confirmation and sets bootstrap_until),
  never by hand and never by ait setup; a project whose completion invariant is a full suite keeps tests_pass
  exactly as today.'
requirements_generic_across_projects: 'A framework feature, generic across projects (aitasks, thinking_app,
  thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation between source files and test
  units - including a project''s own finer subdivision expressed through member units and variant axes,
  with the project''s runner lowering ids - never project-specific code in the engine; and whose onboarding
  is generic too: `onboard detect` recognises each repo''s test tools from the tree and from project_config.yaml
  with an evidence field per row (aitasks: tests/test_*.sh + run_all_python_tests.sh with its serial carve-out;
  thinking_app: gradlew + the screenshot harness; thinking_backend: run_script_tests.sh named under verify_build,
  bash + pytest; aitasks_go: Makefile test = go test ./... plus the tmux parity suite; aitasks_mobile:
  one gradle-class runner per source set - commonTest and androidHostTest as unit, androidDeviceTest as
  device - a kind/runner distinction, no axis) and writes runners.yaml from builtins with a full: true
  suite runner from the existing test_command, scaffolding a project runner script only where an axis
  or a full-suite post-processor needs one; every seed origin is a language- or convention-level rule,
  never a project name.'
requirements_go_engine: Scan, check, select and stale finish in well under a second on a ~720-test repo
  - and select stays under 250 ms warm on thinking_app's 297 golden variants over 49 members plus 374
  JVM classes with axis expansion, never executing a runner - and the scheduler runs concurrently with
  real cross-process locks, so selection overhead stays negligible against the shortest test and check
  can run at every commit step.
requirements_go_engine_and_cli: The engine and CLI are one static Go binary (ait-testmap) built from engine/;
  bash keeps only the dispatcher arms, the shim that resolves the binary under $AITASKS_HOME and pipes
  the change surface in, the `ait test` front, the gate verifier shells, lib/aitasks_home.sh, the ait
  engine developer verbs (incl. home [--migrate]) and any project-local runner or scanner scripts; the
  binary never invokes aitask_*.sh and never needs its own install root.
requirements_high_level_tests_separate: Integration, e2e and device tests declare areas, scope globs or
  budget-exempt trigger globs instead of covers, live in registry/_scoped.yaml beside the unit table,
  join the ranked list at distance 1 as sinks, and never enter the per-file edge graph or its digest staleness;
  a helper file may declare testmap:reads <glob> so every unit whose test-file closure contains it inherits
  the glob as a trigger; variant-bearing units are unit kind and never scoped rows.
requirements_incremental_adoption: 'Adoption is incremental, measurable and agent-driven, never big-bang
  and never waiting on a person where a rule, a measurement or a reading exists: a seeded edge selects
  from the moment `onboard seed --apply` runs (fail-safe direction) but claims no freshness; adoption
  - the act that writes testmap: lines and stamps - happens autonomously for rule and measurement classes
  (`onboard adopt --class <origin> --auto`, by: auto), from agent verdicts over engine-cut packets (`onboard
  adopt --agent-verdicts`, by: agent:<agent-string>; bulk through aitask-testmap-review, bounded by max_pairs_per_run
  and resumable through onboard.yaml phases.review), by the authoring agent for pairs on its own change
  surface (`annotate --author`), and for the rest by a person per evidence class with provenance (adopted.yaml,
  by: human:<email>), per area in batches, or inside the testmap_fresh gate for the test files a task
  already touched; a drives or unsure verdict parks a seed (still selecting, out of autonomous adoption,
  REVIEW_PARKED:<n>; two unsure -> REVIEW_HUMAN) and only a person''s `onboard reject` removes one; readiness
  prints LEVEL and NEXT from what exists, `onboard status` prints ONBOARD_NEXT and the ratios (tests with
  an edge, sources with an edge, seeds pending per origin and per verdict, adopted unreviewed split by
  human/agent/auto, parked, REVIEW_HUMAN, AUTHOR_UNCORROBORATED, KIND_PROPOSALS, REVIEW_AGREEMENT, CALIBRATION,
  oldest pending age) so a half-migrated repo is a known state with a next step, and check reports SEEDED:<n>
  and ADOPTED:<n> until both queues are empty.'
requirements_onboarding_existing_tests: 'A skill onboards a project''s existing tests into the architecture
  without the user writing a registry by hand, in four graded levels each landing as one reviewed aitask:
  level 0 detects test frameworks and writes runners.yaml bindings, config.yaml (completion.mode auto
  with its cadence, agent_review and readiness knobs, conventions, helper roots), resources.yaml and areas.yaml,
  seeds the edge queue, proposes waivers and enables the gates (the universe exists, `ait test --all`
  runs it and is the task''s own first full run, selection works through seeds and the test-file static
  closure, nothing is stamped); level 1 adopts covers edges from the seed queue in the order rule (static:package
  1.0) -> measurement (coverage 0.95) -> reading (agent verdicts over engine-cut packets, agent:review
  0.90 noisy-OR''d with the static origins beneath, adopted at intake with by: agent; drives and unsure
  parked), with naming conventions, plans, prose and (t<id>) co-change as corroboration, helpers split
  from subjects by root and fan-in, the parked remainder left to a person per class or per row - written
  as stamped annotation blocks through the engine''s rewriter with provenance in registry/adopted.yaml
  carrying by: for class, auto, agent and author adoptions and none for per-row human ones, then finish
  --auto when check is clean; level 2 classifies broad tests as scoped rows over codemap areas, adds testmap:reads
  to tree-scanning helpers, testmap:batch no from serial lists, and declares detected locks as resources
  - kind changes confirmed individually by a person, proposed only (kind_proposals[]) in headless runs;
  level 3 declares axes, scaffolds a project runner script and member blocks where the grid heuristic
  finds a product space. Rewriting a test means inserting comment lines only; the skill proposes and never
  performs code restructuring; headless profiles complete levels 0 and 1 in full (rule, measurement, reading
  to budget), propose kinds at level 2 without applying them, and never enter level 3.'
requirements_platform_binaries_in_release: Release CI builds and attaches checksummed binaries for linux/darwin
  x amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt) from one engine job that
  also runs go vet and go test; a new engine-check.yml runs the same on push/PR for engine/**; tarball
  and package-manager artifacts stay architecture-independent.
requirements_reason_per_selected_test: Translates a task's change set into one ranked list of tests that
  must run with a reason on every line (edge(annotation|declared|observed), dep, rule, axis(...)[keys]
  <- <source>, test-dep <helper>, reads(<helper>) <- <path>, ESCALATE:<file>|<reason>, the facet value
  or @* that placed each variant row, a stale mark when a selecting edge's digest no longer matches and
  no run evidence covers that variant, an invocation group and its cost, an explicit DEFERRED line for
  every broad row or group the budget cut) plus `edge(seeded:<origins>)` for a seeded edge - the origins
  list (static:invocation, static:import, static:package, convention, cochange, plan, prose, coverage,
  observed, agent:review) printed so a reader knows what the row rests on, a parked seed selecting exactly
  like an unread one - and `adopted(<origins> <confidence> by <human:<email>|agent:<agent-string>|auto>)`
  beside an annotation edge that entered by class acceptance, agent verdict or author claim; `ait test`
  prints a SELECTED:<n>|<groups>|<est_s>|<seeded_n>| <adopted_n> summary line and UNMAPPED_SOURCE:<path>
  lines ahead of the rows.
requirements_screen_locale_subdivision: 'A test unit may be a member of a file (<path>#<member>, opened
  by a testmap:unit block) and may carry variants on a declared axis (<unit>@<variant>); a source change
  reaches a unit on every variant, or reaches an axis facet value (matrix.locale=ru) and thereby only
  the variants carrying it plus any plain unit carrying testmap:axis matrix.locale=ru; the runner lowers
  a variant id to what it executes (thinking_app: <Class>.<method> per matrix through matrix_classes /
  preview_resolve_token) so the engine never learns Gradle, Roborazzi or the membership manifests.'
requirements_standard_runner_contract: 'Runs selected tests through project-defined runners under a standard
  contract (describe/list/run; fields incl. group_by, token_format, filter_scope, full, children, artifact_glob;
  TSV list; results.jsonl with child rows; runner.json overhead; builtins bash-file, pytest, go-test,
  gradle-class, suite, device with command:/cwd: overrides and shadow-by-name) plus the onboarding affordances:
  two repository keys, `subsumed_by: <suite>` (run --all executes a full: true suite once, never its subsumed
  runners beside it) and `fallback_command:` (what completion runs when the engine is absent and the policy
  allows); `onboard scaffold --runner <builtin> --as <name>` writes a project runner script skeleton whose
  describe/run delegate to the builtin and whose list is the one function the project fills (thinking_app''s
  tools/verification/testmap_runner.sh is that scaffold completed); and `onboard detect` wraps an existing
  project_config.yaml test_command as a `full: true` suite runner with a children: post-processor generated
  for pytest junitxml, bash-file names and go test -json and a fallback_command: equal to the previous
  test_command, so the project''s full gate feeds evidence from day one without anyone writing a runner.'
requirements_user_root: Every per-user artifact this feature installs lives under the framework's own
  root, ~/.aitasks/ (env override AITASKS_HOME, one owner file lib/aitasks_home.sh, no fallback to ~/.aitask),
  beside the existing ~/.config/aitasks/ and ~/.cache/aitasks/ roots; the engine is the root's first tenant
  at $AITASKS_HOME/engine/v<VERSION>/ and $AITASKS_HOME/engine/dev/; the legacy ~/.aitask/ tenants (venv,
  pypy_venv, python, bin, uv, dev_tier, update_check) are neither moved nor read by this feature's default
  path.
requirements_workflow_seam: 'The change-aware run is reached from the existing workflows without a new
  workflow: task-workflow Step 7 gains one paragraph naming `./ait test` as the implementation test loop
  and one pre-review Affected Tests procedure (affected-tests.md) before Step 8, behind an affected_tests:
  run|show|off profile key (default run), that calls `./ait test --advisory --task <id>` speaking the
  VERDICT:/REASON:/DETAIL:/LOG: line shape and set -e capture form aitask_run_project_command.sh already
  established, guarantees the prediction record the completion run scores, and - in its autonomous no_selection
  branch - has the agent name its own test for each UNMAPPED_SOURCE through `ait testmap annotate --author
  <test> <source> --task <id> --by <agent-string>` (adopted with origin agent:author; AUTHOR_REFUSED:outside-change-surface
  unless both files are on the change surface) before falling back to attribute --propose; Step 8''s procedure-gate
  block dispatches testmap_fresh, whose seeds step reads packets and adopts or parks on verdicts; Step
  9''s gate orchestrator runs testmap_check -> tests_pass and the legacy build-verification path is untouched
  except for one error branch; aitask-qa''s test discovery reads the map (explain --sources) instead of
  naming conventions when aitestmap/ exists and its execution step runs `./ait test`; aitask-pickrem and
  aitask-pickweb inherit Step 7 through the shared task-workflow; ait setup prints TESTMAP:<state>; the
  one new agent launch surface, aitask-testmap-review, is reached only through `ait skillrun` / `ait codeagent`
  / `ait crew runner`; and every seam degrades to a printed skip where the engine or registry is absent.'
requirements_workflow_seam_is_data: 'The integration with task-workflow, aitask-qa, aitask-pickrem, aitask-pickweb
  and aitask-resume adds no new gate and one procedure: the seam is project_config.yaml (test_command:
  ./ait test, gate_command_exit_contract: [test_command]), the project''s profiles (default_gates += tests_pass,
  testmap_check, testmap_fresh; the affected_tests key), gates.yaml (testmap_check unlocks tests_pass;
  tests_pass.timeout_seconds from the ledger), the completion policy in aitestmap/config.yaml, and two
  environment variables this design adds to the verifier (AIT_GATE_TASK_ID, AIT_GATE_RUN_ID); the prose
  changes are one Step-7 paragraph naming `./ait test` as the implementation test loop with the UNANNOTATED_TEST
  and UNMAPPED_SOURCE answers, one branch in build-verification.md for verdict error / command_refused
  | command_errored, aitask-qa''s discovery reading the registry instead of naming conventions when aitestmap/
  exists, and the one pre-review Affected Tests procedure kept because it guarantees the prediction record
  the completion run scores; Step 9''s verify block, the merge broker, archival and the gate orchestrator
  are untouched.'
requirements_zero_config_entrypoint: 'One user-facing verb, `ait test`, is the only way an agent or a
  person runs tests in any aitasks project, at every stage of adoption: with no aitestmap/ it runs project_config.yaml
  test_command through aitask_run_project_command.sh and prints the onboarding hint; with a registry it
  resolves mode (completion when --gate or AIT_GATE_TASK_ID is set, advisory when --advisory, interactive
  otherwise), task (--task > AIT_GATE_TASK_ID > the aitask/<task_name> branch of the current worktree
  > the single Implementing lock this user holds on this host > NO_TASK with the three ways out) and intake
  (change surface for a task, --dirty, --all, or named paths where a source path is a one-file change
  set) by itself; it prints MODE / TASK / INTAKE / POLICY / SELECTED / RUN / RESULT lines, UNANNOTATED_TEST:<path>
  for a new test in the change surface and UNMAPPED_SOURCE:<path> for a changed source no unit reaches,
  and exits 0 / 1 / 2 / 3 / 75 / 64; in advisory mode it exits 0 / 1 / 2 / 3 with VERDICT: / REASON: lines
  and every absence a skip; and `ait test --howto` prints the project''s runners, kinds, resources, gates,
  completion policy, level, docs and notes and the four commands an agent needs, computed from runners.yaml,
  config.yaml and the ledger so it cannot rot.'
requirements_zero_config_onboarding: 'A repository with an existing test tree is brought onto the map
  by runs of /aitask-testmap-onboard, attended or headless, and nothing typed by hand: the skill detects
  the test tools (pytest, go test, gradle per source set, bash tests/test_*.sh, npm test, Makefile test,
  and the project_config.yaml test_command / verify_build) with evidence per row, generates aitestmap/
  (config.yaml with completion.mode auto and its full_run_every cadence, agent_review, readiness, conventions
  and helper roots - confirmed in the attended config table; runners.yaml with bindings and the full suite
  wrapper; resources.yaml from hints; registry/areas.yaml from code_areas.yaml), inventories every test
  unit through the runners'' list, seeds edges from the origin table, proposes rules and waivers for the
  remainder, enables tests_pass / testmap_check / testmap_fresh and the test_command swap, and runs the
  existing full gate once as the level-0 task''s own completion gate; level 1 adopts seeds by rule, by
  measurement and by reading (the skill''s agent reads engine-cut packets and returns verdicts; a person
  confirms them in attended profiles and nobody does in headless ones; drives and unsure park and stay
  listed), classifies broad tests with a person''s confirmation (headless: proposes only), and scaffolds
  axes (attended only) - each phase idempotent and resumable from a committed ledger (aitestmap/onboard.yaml,
  whose review phase may be partial and re-entered and whose reviews[] memo keeps a pair from being read
  twice for the same test bytes), each level shaped as an aitask so its writes land under (t<id>) commits,
  are reviewed at Step 8 and attributed by the change surface; no policy flip is written by anyone under
  auto - the engine flips per run.'
requirements_agent_driven_adoption: 'The value of a change-aware test set is that the set is adapted automatically,
  so adoption must not wait on a person where a rule, a measurement or a reading exists: every heuristic
  seed is read by an agent over an engine-cut packet and every verifies verdict is adopted at intake with
  by: agent:<agent-string>; rule and measurement classes (static:package, coverage) adopt with no reading
  through `onboard adopt --class --auto` (by: auto); the agent that writes a change stamps the pairs whose
  two files are on its own change surface (agent:author); a headless profile reaches level 1 and finish
  --auto without a prompt. Three things stay a person''s and the design says so: kind changes (a wrong
  kind changes staleness semantics and no run gives an agent evidence to check itself against; headless
  runs propose them), axis declaration, and removing a seed from selection - an agent verdict may only
  move an edge toward more claims, never toward fewer runs, so drives and unsure park a seed (still selecting,
  REVIEW_PARKED; two unsure -> REVIEW_HUMAN) and only `onboard reject` removes one. Every autonomous act
  is printed with its provenance (by: agent:<s> | auto; adopted(... by <who>) on every stale / explain
  line; approved_by engine:readiness@<run> in costs/policy.yaml) and every residual risk has a knob in
  aitestmap/config.yaml (agent_review.confidence, agent_review.enabled, agent_review.author, full_run_every,
  mode: full) rather than a hidden default.'
requirements_autonomous_loop_closure: 'The value of a per-change-set test selection is realised only when
  the loop closes without a person: seeding, adoption, the completion-policy flip and the safety net that
  keeps scoring alive are each performed by a machine or an agent under a committed, per-project policy
  - a rule (static:package) or a measurement (coverage) adopts by class, a reading (agent:review over
  engine-cut packets, agent:author at authoring time) adopts everything the heuristics only seeded, completion.mode:
  auto flips to the selection when readiness is ADMISSIBLE and records the engine''s approval in costs/policy.yaml
  with mode: auto, and full_run_every {tasks, selection_ratio_above, days} guarantees full runs so a miss
  is caught within a bounded number of tasks; every place a person remains is named and printed (REVIEW_PARKED,
  REVIEW_HUMAN, KIND_PROPOSALS, axes, disabling the loop) rather than assumed done; the engine never launches
  a code agent, every agent launch is a framework wrapper (`ait skillrun`, `ait codeagent`, `ait crew
  runner`) and no default path uses headless print mode; a project that wants a human in the loop keeps
  completion.mode: selected or sets agent_review.enabled: false and gets the baseline exactly.'
assumption_annotation_is_comment_only: 'Integrating an existing test into the architecture never changes
  what the test does: onboard adopt inserts `testmap:` comment lines with the file''s own comment leader
  - bash after the header comment block (after the shebang and leading # block), Python as # lines after
  the module docstring (the grammar reads docstring lines but adoption never writes into one because that
  changes __doc__), Go after the package clause, Kotlin after the import block or inside the member''s
  testmap:unit block for a member seed - the runners execute the unchanged test, and `git diff -w --ignore-blank-lines`
  of an adopted file shows comments only; a test that cannot be annotated by comment (no comment leader
  the grammar knows) is skipped with ADOPT_SKIP:no-leader and stays seeded; existing `# Covers:` prose
  headers are shown beside the seeds as reviewer context and read by the prose origin, never rewritten.'
assumption_areas_express_suite_blast_radius: The blast radius of a high-level test is expressible as a
  union of area glob sets plus scope globs plus budget-exempt trigger globs, plus the reads globs of helpers
  in its test-file closure; what that misses surfaces through score on a full run as an observed trigger
  or area member.
assumption_axis_membership_declarable: 'For a product-shaped suite, which facet value a source belongs
  to is declarable as globs by the people who own the suite, because the project already routes by exactly
  that shape - res/values-ar/** and font/cairo_*.ttf are the Arabic matrices'' inputs and matrix_classes()
  already maps a matrix to its classes; aitasks'' .claude/ vs .opencode/ vs .agents/ trees are the agent
  facet. A source that matches no axis source is not an axis hit and reaches units only through edges
  and dependencies, which select every variant - the fail-safe direction. Falsifier: a project whose membership
  is genuinely dynamic (a runtime flag choosing a locale), for which the answer is to declare no sources
  on that facet. assumption_axis_sources_declarable is the thinking_app instance of this general claim.'
assumption_axis_sources_declarable: 'The sources that reach one facet value of an axis are declarable
  as globs in axes.yaml: for thinking_app''s locale facet, values-<q>/**, raw-<q>/** and the per-family
  fonts (heebo_* for he, roboto_* for en and ru, cairo_* for ar); sources every locale reads (values/**,
  TypeScale.kt, Fonts.kt, AppRoot.kt) are ordinary edges, scanned dependencies or one hand rule over values/**
  and reach every variant; the geometry and direction facets have no axis sources because they are test-side
  constants in ScreenshotTestHarness.kt, reached through the test-dep closure.'
assumption_batch_per_unit_timing_reportable: Runners can report per-unit timing inside a batch from their
  tool's own report format (JUnit XML, go test -json, pytest junitxml), can invert a report row to a registered
  id (JUnit classname+name back to ScreenFixtures.kt#Welcome@pixel5Ru_ltr through the same routing table
  the runner's list verb printed), and the same JUnit XML reports each @Test method with its own duration,
  which is what makes a variant's marginal cost measurable separately from its class's boot - the number
  the invocation-group budget depends on.
assumption_blob_digest_is_staleness_key: The git blob digest of the covered source's content is the staleness
  key; file mtime (reset by checkout) and the annotation date (day granularity, clock skew) are never
  compared - the date is display only; the blob id doubles as the join key into any commit's tree for
  the evidence join.
assumption_broad_tests_area_scoped: Integration, e2e and device tests can be described by named areas
  or globs whose membership changes rarely, so evidence-based drift (STALE_AREA) plus attribute widening
  is adequate; a calendar cadence (REVIEW_DUE, broad_review_days) is opt-in and off by default.
assumption_cells_enumerable_by_plugin: 'The variant universe a repo has is enumerable from the project''s
  existing single routing statement rather than a second hand-maintained list - and the enumerator is
  the runner''s list verb, not a separate plugin directory: thinking_app''s runner lists 297 variant ids
  from matrix_classes() crossed with the two membership manifests, aitasks'' from its rendered tests/golden/
  tree; the framework never infers a variant. Falsifier: a repo whose test methods are only knowable by
  running the build, for which list may exec the build''s own list task at the cost of a slower scan/check,
  since select never calls it.'
assumption_change_surface_is_intake: 'The change-surface script''s attribution (aitask_change_surface.sh)
  is the right intake for every --task path - the gate verifiers, `ait test` in interactive, completion
  and advisory mode, and stale --task: the front pipes its COMMITTED:/TASK:/OTHER:/UNKNOWN: lines into
  the engine''s --changes - (its exit codes carry no meaning, the engine parses lines only), selection
  never reads a raw git diff, and an UNKNOWN: row refuses selection in interactive and completion mode
  and surfaces as VERDICT:skip REASON:unknown_paths naming the paths in advisory mode, never as a run
  over another task''s work; `ait test <path>...` is the one explicit-list intake (TASK: rows), `--dirty`
  the explicit and printed no-task intake, and `--all` has no intake; the before content a symbol scanner
  needs comes from HEAD:<path> (TASK: rows) or the parent of the first (t<id>) commit (COMMITTED: rows)
  and is absent - so the whole file is the symbol set - when history is unreachable.'
assumption_cochange_is_corroboration: '(t<id>)-tagged commit history is a corroborating signal, never
  a primary one: in the last 400 commits touching tests/ or .aitask-scripts/ on aitasks there are 336
  task groups averaging 1.14 commits each, and a group pairs a few tests with a few scripts (t1159_1:
  4 tests x 4 scripts) with nothing inside the group to say which test covers which script, so co-change
  scores 0.20 + 0.20 x distinct task groups capped at 0.60, requires >= 2 distinct tasks (min_cochange),
  and cannot reach the 0.85 class-acceptance threshold alone or with convention (0.84 at the cap); repositories
  without the (t<id>) convention fall back to per-commit grouping with the same cap; one `git log --name-status
  -M --format=%H%x00%s` pass cached by HEAD sha, SEED_HISTORY:shallow|<n> on a shallow clone.'
assumption_engine_latency_targets: 'On the aitasks repo (about 720 test units, 2,500-3,000 edges, about
  270 scanned sources) the engine meets select < 200 ms warm, scan < 300 ms, check < 300 ms, stale --task
  < 300 ms, stale --all < 2 s, cold select < 1.5 s; on a thinking_app-shaped fixture (297 golden variants
  over 49 member units, 374 JVM test classes, about 900 Kotlin files) select with axis expansion < 250
  ms warm, reading the committed variants: lists and never executing a runner; pinned by committed go
  test -bench fixtures with a 2x regression failing engine-check.yml, validated before the gates are enabled.'
assumption_existing_locks_wrappable: Existing project locks and allocators (thinking_app's heavy-run lock
  with its exit-75 admission in tools/verification/heavy-run-lock.sh, emulator allocation in emulator-allot.sh)
  can be wrapped as resources without changing them; the Go admission and allocator kinds exec the project's
  commands and honour their exit codes, deferring on 75 until the run deadline; thinking_app's runner
  script goes through screenshot-tests.sh unit-tests, which reserves the slot itself.
assumption_full_run_expressible_per_repo: 'Every target repository''s completion suite is expressible
  as `ait test --all` over its runners or as one full: true suite runner generated by onboard detect from
  test_command with a children: post-processor and a fallback_command: - thinking_app''s verify-active
  (already test_command; screen-matrix and gradle-class subsumed_by it), thinking_backend''s scripts/tests/run_script_tests.sh
  (22 bash + 18 python tests, wired today as verify_build because it also runs a shellcheck baseline -
  the skill asks and keeps it by default, adding test_command: ./ait test over the detected units), aitasks_go''s
  `go test ./...` over 85 packages, aitasks_mobile''s `./gradlew check` minus the 3 androidDeviceTest
  classes which run only under device_policy, and aitasks'' 400 bash + 320 python units which had no suite
  command at all (test_command: null) and gain one; fallback_command is derivable for each from detect''s
  output.'
assumption_gate_exit_contract_reused: 'The framework verifier contract (0 pass / 1 fail / 2 skip / 3 error)
  is reached through the EXISTING tests_pass verifier running test_command: `./ait test --gate` speaks
  0/1/2/3/75/64, and run_project_command_key() - the single canonical statement of the command exit contract
  - gains two rows for opted-in keys: 75 -> error (PROJECT_CMD_STATUS=error, CODE=3, REASON=command_refused)
  and 3 -> error (command_errored), so an admission refusal that survived the in-engine deferral or a
  missing engine is a verifier error the orchestrator retries within budget, never a code failure and
  never a skip; 2 (nothing ran: empty selection) stays the opt-in skip. The verifier exports AIT_GATE_TASK_ID
  / AIT_GATE_RUN_ID to the command (both new in this design), which is how `./ait test` knows it is in
  completion mode and for which task; aitask_run_project_command.sh --task-id exports the same, so the
  legacy Step-9 path, aitask-qa and the gate agree by construction. testmap_check keeps its own verifier
  shell mapping engine exits 0/1/2/64 and a missing engine to 0/1/2/3/3. The advisory mode of `ait test`
  speaks aitask_run_project_command.sh''s 0/1/2/3 domain with 75 folded into VERDICT:skip REASON:admission_refused
  and usage errors into 3, so the pre-review procedure and the Step-9 path cannot disagree about an exit
  code. One shell plus two rows in the shared lib, not two dedicated verifier shells.'
assumption_git_history_is_freshness_clock: Git history is the evidence clock, not the staleness key -
  commit reachability (merge-base --is-ancestor) decides which last_pass anchors may suppress a STALE
  row, never whether an edge is stale; mtime is never compared; a shallow clone whose anchors are outside
  fetched history reports STALE, not EVIDENCED, and remains fully functional; the cochange seed origin
  reads history as a seed source only, never as a freshness or evidence source.
assumption_go_toolchain_available: 'A Go toolchain >= 1.26 is available in release CI through an actions/setup-go
  step this design adds to release.yml (go-version-file: engine/go.mod) and on framework developers''
  machines; target-project users never need Go.'
assumption_go_toolchain_ci_and_dev_only: Go is a build-time dependency only - release.yml has no Go step
  today and the repo's only setup-go is hugo.yml's at website/go.mod's 1.25.7, so the engine job provisions
  its own toolchain; users receive prebuilt binaries and never compile.
assumption_helper_degrades_when_absent: '`ait test --advisory` can always answer: engine missing (ENGINE_MISSING
  from the shim) -> VERDICT:skip REASON:testmap_absent; no aitestmap/ -> VERDICT:skip REASON:registry_absent;
  UNKNOWN: rows in the change surface -> VERDICT:skip REASON:unknown_paths naming them; empty selection
  -> VERDICT:skip REASON:no_selection with UNMAPPED_SOURCE lines; admission refused after the deadline
  -> VERDICT:skip REASON:admission_refused; only a run that executed maps to pass/fail, and only a front
  that cannot write its LOG: exits 3. This is what lets the pre-review Affected Tests procedure sit before
  Step 8 in every profile including remote (Claude Code Web has no engine) without a conditional per environment;
  the interactive and completion modes of the same script keep the rule that a missing engine is an error.'
assumption_helpers_separable_by_fanin: 'Within a test file''s closure, helpers (asserts, fixtures, fakes)
  are separable from subjects by two rules the skill confirms: a path under a declared helper root (tests/lib/**,
  **/testing/**, **/src/test/** for Kotlin, **/testdata/**) is a helper, and any other closure path whose
  fan-in reaches >= helper_fanin (default 5% of the runner''s units) is a helper; helpers get test-dep
  through the closure and, when they glob the tree (ls tests/*.sh, glob.glob, rglob, find, git ls-files,
  os.walk - aitasks: tests/lib/import_isolated.py, board_fixture.py, validate_session_hook_fixtures.py),
  a proposed testmap:reads (SEED_READS:) written at level 2 on class acceptance; subjects become covers
  candidates. Falsifier: a hot production module imported by most tests would be misread as a helper and
  lose its covers edges - it keeps test-dep selection, over-selecting rather than under-selecting, and
  the skill lists every fan-in reclassification for review.'
assumption_home_symlink_compatibility: 'Every existing consumer of the legacy ~/.aitask tree keeps resolving
  unchanged when ~/.aitask becomes a symlink to ~/.aitasks, because all of them dereference a path rather
  than compare one - verified: the 35 references across 8 framework files (21 in aitask_setup.sh, 6 in
  python_resolve.sh, 3 in aitask_path.sh), the venv''s console-script shebangs (#!/home/<u>/.aitask/venv/bin/python3),
  the ~/.aitask/bin/python3 wrappers, the ~/.aitask/python/<ver>/bin/python3 symlinks whose targets are
  absolute paths outside the home, and pyvenv.cfg''s informational command = line; no ==, !=, -ef, realpath,
  os.path.realpath or samefile on the home path anywhere under .aitask-scripts/, ait or install.sh. This
  is the precondition of ait engine home --migrate, re-checked by tests/test_aitasks_home.sh''s post-migration
  venv and PyPy-venv exercise before the default is flipped.'
assumption_instruction_block_is_read: 'Code agents load CLAUDE.md / AGENTS.md at session start and follow
  a managed block that names one command: the framework already relies on this for `./ait git`, notes
  and commit format, and ait setup regenerates the >>>aitasks block on every run, so a `## Running Tests`
  section reaches every agent in every onboarded project with no per-project authoring; the hand-maintained-CLAUDE.md
  case (sentinel present, no markers) is this repository and is edited by the level-0 onboarding task.
  Falsifier: an agent whose harness does not read the file - for which `ait test --howto` is the one-call
  fallback.'
assumption_instructions_block_reaches_agents: The seeded agent-instructions block (seed/aitasks_agent_instructions.seed.md,
  assembled by assemble_aitasks_instructions()) is inserted between >>>aitasks / <<<aitasks markers into
  every supported agent's instructions file (CLAUDE.md, AGENTS.md, .codex/instructions.md, the OpenCode
  mirror) by ait setup and refreshed on re-run and on upgrade (insert_aitasks_instructions replaces the
  marked block) - verified in aitask_setup.sh - so the generic Running Tests section added to the seed
  reaches every onboarded and not-yet-onboarded project on its next setup with no per-project edit, and
  is the one always-loaded place an agent learns the run surface. The section names no code agent, carries
  no project specifics (those are `ait test --howto`'s computed output) and stays at fourteen lines so
  it costs every session the same small context; the hand-maintained CLAUDE.md case (sentinel present,
  no markers) is edited by the level-0 onboarding task.
assumption_kotlin_scanner_fail_closed: A closed construct list (explicit repo import, same-package as
  fully connected, repo star import as a package edge, fully-qualified in-body reference from the comment-stripped
  body) is enough to over-approximate the Kotlin import graph, and every construct that defeats such a
  graph - inline functions, const val, Hilt/DI bindings, Class.forName / ::class.java, generated or KSP
  sources, an unreadable or untokenizable file - is detectable by pattern and marks the file opaque, so
  a change to it escalates instead of being silently narrow; measured on thinking_app, 42 main files declare
  const val or inline fun and 63 carry DI annotations, so escalation is frequent by design; each opaque
  branch is reachable and red-proved by an engine fixture test.
assumption_legacy_user_root_coexists: In this release ~/.aitasks/ (engine) and ~/.aitask/ (venv, pypy_venv,
  python, bin, uv, dev_tier, update_check; 8 framework code files with 35 references name it, plus 20
  test and 18 doc files) coexist on one host without either reading the other; the migration of the legacy
  tenants exists as ait engine home --migrate but is not run by ait setup by default, and nothing in this
  feature depends on it having happened; the default flip is a named follow-up.
assumption_onboarding_is_a_task: 'Onboarding writes committed files (aitestmap/**, test-file comment lines,
  project config, profile and gates edits) across several sessions, so each level runs as an aitask: /aitask-testmap-onboard
  creates and claims `testmap onboarding level <n>` (issue_type chore, labels testing,testmap) through
  aitask_create.sh --batch and aitask_pick_own.sh, attaches the seed dump with ait attach, records the
  task id and level in onboard.yaml, continues into task-workflow, and every phase at Step 7 commits its
  files through aitask_task_commit.sh under `chore: Onboard testmap - <phase> (t<id>)` so the change surface
  attributes them and a resumed session re-enters at ONBOARD_NEXT (a partial review phase included); Step
  8 reviews the diff, the level-0 task''s Step-9 tests_pass is the first full run, and the next level''s
  task is created with depends: on this one because a level may wait weeks on full-run history; a headless
  level-1 task has the same shape with the review loop as its longest phase and finish --auto as its last.
  Falsifier: a repo that forbids tasks on the code branch - for which --no-task writes without committing
  and prints the commit lines to run.'
assumption_one_engine_per_framework_version: One engine build per framework version suffices; a per-user
  versioned directory ($AITASKS_HOME/engine/v<VERSION>/) resolves per-project VERSION differences without
  a compatibility matrix, and exact-version resolution in the shim never falls back to newest-wins.
assumption_passing_run_anchors_edges: A passing run of a test variant at commit C, on any host class,
  from an invocation without a cause and for an id under the flake threshold, is evidence that its annotated
  edges held for that variant against the source content present in C's tree - so an edge whose current
  blob equals the blob at C is EVIDENCED for that variant without touching the test file; a unit with
  variants is EVIDENCED only when every variant the change reaches has such a pass; a verify-active full
  run's child rows anchor all 297 goldens at once.
assumption_platform_matrix_sufficient: linux/darwin x amd64/arm64 covers every target host (WSL reports
  Linux); any other platform builds from source via --engine-from-source.
assumption_release_asset_reachable: A host running ait setup or ait upgrade can reach github.com/beyondeye/aitasks/releases
  over HTTPS, as it already must for the framework tarball; the shim itself never downloads, so a gate
  run never performs a network fetch.
assumption_release_assets_reachable: Air-gapped or off-matrix hosts supply the binary via --local-engine,
  --engine-from-source, AIT_TESTMAP_BIN or a pre-seeded $AITASKS_HOME/engine/; --no-testmap / AIT_TESTMAP_FETCH=0
  skip the fetch and nothing else in setup depends on it.
assumption_seed_sources_measured: 'One origin table seeds edges, each origin measured on 2026-09-16 and
  none below 1.0 trusted alone as a HEURISTIC; every row carries a class - rule, measurement, reading
  or heuristic - that the autonomous floor reads. Rule: static:package (a _test.go''s own package: deterministic,
  1.0). Measurement: coverage (opt-in per-unit runtime coverage: coverage.py dynamic contexts, go -coverprofile
  per -run, LCOV with a test column, JaCoCo per-test sessions, 0.95). Reading: agent:review (an agent
  read the engine-cut packet - the static anchor line +-20, the test''s assertion lines flagged, the source''s
  declared symbols, the prose header - and answered verifies naming the assertion line that checks the
  source, which the engine verified exists and names the source''s stem, command form, an output path
  or an exported symbol; evidence {verdict, assert_line, rationale, by: agent:<agent-string>, run, packet_sha,
  test_blob, source_blob}; attaches only to an existing seed; 0.90) and agent:author (the implementing
  agent named a pair whose two files are both on its change surface, through annotate --author; AUTHOR_UNCORROBORATED
  when the closure holds no relation; 0.90, 0.99 with a static relation). Heuristic: static:invocation
  (398 of 400 aitasks bash tests, avg 3 paths, 0.90), static:import (320 of 320 aitasks Python, 139 of
  339 thinking_app - same-package references NOT seeded, 0.85), observed (an attribute --propose row from
  a scored miss, 0.70), convention (52-72 of 400 bash, 62 of 320 Python, 48 Kotlin, 0.60), plan (0.50),
  prose (0.30), cochange ((t<id>) co-change in >= 2 distinct task groups: 336 groups in 400 aitasks commits
  at 1.14 commits each say nothing about which covers which; thinking_app 127 of 400 at 7.2 main files
  - hence 0.20 + 0.20 per group capped at 0.60, corroboration that can never reach the 0.85 class threshold
  alone). Confidence combines by noisy-OR (static:invocation + agent:review = 0.99), orders the review
  queue and never hides a row. The reading origins'' 0.90 is a prior: REVIEW_AGREEMENT against human per-row
  decisions and `onboard review --calibrate <n>` against coverage facts (else human rows) write agent_review.measured_confidence
  when lower over calibration_min pairs, and below accept_min verdict adoption stops (REVIEW_ORIGIN_DEMOTED).
  Seeding is partial by construction: the remainder is rules, waivers, author claims and incremental adoption.'
assumption_seeds_select_never_evidence: 'A seeded edge is safe to act on in exactly one direction: it
  may cause a test to run (over-selection costs time) and may never suppress a STALE row, anchor evidence,
  satisfy require_stamp or count as coverage for UNMAPPED_SOURCE under --strict (under-claiming a freshness
  fact costs correctness). So seeds live in a generated file (registry/seeded.yaml), carry no stamp, are
  excluded from stale, are counted separately by check (SEEDED:<n>), and become claims only through an
  explicit adopt that writes the line and the stamp - by class (with an adopted.yaml provenance row),
  by row (a reviewed claim), from a verifies verdict (an adopted.yaml row with by: agent:<agent-string>)
  or from an author claim. An agent verdict on a seed changes what may adopt it and never whether it selects:
  verifies adopts it at intake, drives and unsure park it (still selecting, out of autonomous adoption,
  REVIEW_PARKED; two unsure -> REVIEW_HUMAN). Autonomous profiles may seed everything and may adopt a
  class only when every member carries at least one RULE, MEASUREMENT or READING origin (static:package,
  coverage, agent:review, agent:author) and its noisy-OR clears agent_review.accept_min (0.85); a heuristic-only
  class (static:invocation alone, static:import alone, convention, cochange, plan, prose, observed) is
  never adopted headless, however high its measured precision, because its fact is ''executes'' or ''co-occurs'',
  never ''verifies''; no agent path rejects a seed or changes a kind. Falsifier: a project whose full
  suite is so expensive that seeded over-selection is itself the cost problem - for which the suite budget
  and --format tokens preview are the levers, not trusting seeds.'
assumption_static_closure_seeds_edges: 'The test-file static closure is a sufficient primary seed for
  covers edges on the target shapes, and naming conventions are not: measured on aitasks, 398 of 400 tests/test_*.sh
  name an aitask_*.sh or lib/*.sh|py path literally (the two that do not are pure fixture tests), 320
  of 320 tests/test_*.py import a .aitask-scripts/lib module through a sys.path bootstrap, while only
  52 of 400 bash tests map to .aitask-scripts/aitask_<stem>.sh by the tests/test_<stem>.sh convention
  aitask-qa relies on today; on aitasks_go the subject is deterministic (a _test.go covers the non-test
  files of its own package, confidence 1.0); on Kotlin the import graph is the same scanner the selector''s
  Kotlin closure uses. Only the direct relation is seeded; the deeper closure stays the selector''s d2
  walk. Falsifier: a project whose tests reach subjects only through a dynamic dispatcher (a CLI tests
  drive by name) - for it seed emits no static rows and the skill offers convention rules and co-change,
  or level 0 only.'
assumption_static_granularity_v1: 'Static file-level facts remain the default for v1, with two narrower
  granularities in use rather than reserved: a member unit (<path>#<member>, annotations scoped by testmap:unit
  blocks, no language parsing) and the edge''s symbols slot, whose first consumer is the opt-in android-res
  scanner that names the string keys a values-<q>/ diff changed; no scanner produces symbol-level coverage
  of Kotlin or Python code; a change anywhere in a member file is a change to every member until hunk-level
  attribution exists.'
assumption_target_repos_accept_aitestmap_root: Every target repo will accept a root aitestmap/ directory
  of YAML committed into its code tree, including onboard.yaml, registry/seeded.yaml, registry/adopted.yaml
  and an optional axes.yaml; runner scripts and axes are both optional (a repo with no product space declares
  none and gets the plain unit-map behaviour) because the reference runners are built into the engine;
  thinking_app commits one runner script (tools/verification/testmap_runner.sh) because its lowering is
  the harness's own routing.
assumption_task_resolvable_from_session: '`ait test` can find the task an agent is implementing without
  being told: task-workflow names worktree branches aitask/<task_name> where <task_name> is the task file
  stem (t<id>_<slug>), so `git rev-parse --abbrev-ref HEAD` yields the id in worktree mode; in current-branch
  mode (fast profile, create_worktree: false) the task lock this user holds on this host is unique per
  Implementing task, so a `--list-mine` listing on aitask_lock.sh yields it; two or more yield AMBIGUOUS_TASK:<ids>
  and require --task; gate context supplies AIT_GATE_TASK_ID; the pre-review advisory form always passes
  --task explicitly because the procedure knows the id. Falsifier: an agent implementing outside the workflow
  (no lock, no branch) - for whom `ait test --dirty` is the explicit, printed, never-default intake.'
assumption_test_tools_detectable: 'The test tools of every target repo are detectable from the tree and
  the project config without executing a build: pytest.ini / pyproject [tool.pytest] / conftest.py / tests/*.py
  with a runner script; go.mod plus *_test.go with packages from go list; gradlew plus src/<sourceSet>/
  test roots (commonTest, androidHostTest, androidDeviceTest, test, androidTest); tests/test_*.sh with
  tests/lib/asserts.sh; package.json scripts.test; a Makefile test target; and project_config.yaml test_command
  / verify_build. Verified on the five repos: aitasks (bash + pytest via run_all_python_tests.sh with
  a 4-module serial carve-out), thinking_app (gradlew + the screenshot harness named by test_command),
  thinking_backend (run_script_tests.sh named under verify_build - detect reports SUITE_CANDIDATE:verify_build
  and the skill asks, keeping it by default), aitasks_go (Makefile test = go test ./... plus parity/run_parity.sh),
  aitasks_mobile (three gradle source-set roots, no test_command). Every FRAMEWORK: row carries its evidence
  so a reader can dispute it. Falsifier: a build-only test discovery (tests generated at build time),
  for which detect emits DETECT_UNKNOWN and the skill asks.'
assumption_testmap_token_no_collision: The annotation token 'testmap:' does not collide with existing
  prose comments in any target repo; the 38 existing '# Covers:' headers in aitasks are behavioural prose
  and are not matched; thinking_app's KDoc mentions no 'testmap:' string.
assumption_variant_universe_from_runner_list: 'A runner''s list verb enumerates the complete universe
  its run filter can address, so whole-run selection is sound: for thinking_app that is every <Screen>_<matrix>.png
  of the two membership manifests (50 + 247 = 297 goldens over 10 matrices) as variant ids plus every
  other class under app/src/test/java as a file unit; a class absent from list is a check failure (UNREGISTERED),
  never a silently unfiltered one; scan --apply persists each member''s listed variants so select reads
  the committed table and only scan and check exec list.'
assumption_agent_can_judge_verifies: 'An agent that reads a test''s assertion lines beside the source''s
  declared symbols can tell a test that verifies the source (asserts on its output, exit, side effect
  or a symbol it exports) from one that only drives it (runs it to build state for another assertion),
  and can name the assertion line, with agreement >= accept_min against human per-row decisions; the engine''s
  check that the named line exists in the test file and names the source''s stem, command form, an output
  path or an exported symbol turns a free-text judgement into one with a machine-checkable anchor. Measured
  nowhere yet - the first labelled set is the in-gate and per-row adoptions on aitasks. Falsifier: REVIEW_AGREEMENT
  under accept_min over calibration_min pairs -> REVIEW_ORIGIN_DEMOTED, agent_review.measured_confidence
  written and autonomous verdict adoption stops; a project may also set agent_review.confidence lower
  from day one to keep verdicts as corroboration only.'
assumption_session_agent_is_reviewer: 'The agent already running the onboarding skill (attended or headless
  - the remote profile''s agent is headless by construction), the testmap_fresh gate or the pre-review
  procedure is the default reader of review packets; no gate, verifier or engine path spawns a process
  to read, so the review pass costs the session''s ordinary tokens (aitasks: ~2 k input tokens per pair,
  ~1.5 M over 36 packets of 20) and never a gate run''s; a dedicated or parallel pass exists behind the
  framework''s wrappers - `ait skillrun testmap-review` (interactive), `ait codeagent testmap-review`
  (--print only under --headless) and the crew form (`onboard review --out --crew` registering one testmap-review
  agent per packet file through aitask_crew_addwork.sh, started by a person with `ait crew runner`, which
  launches through `ait codeagent`; --collect reading the outputs) - and is started by a person. Falsifier:
  a harness whose session cannot read 20 packets'' worth of excerpts in one turn - lower agent_review.batch
  or packet_lines.'
assumption_author_annotates_own_surface: 'The agent that wrote or edited a test within a task knows which
  source on the same change surface it checks at least as well as any static seed, and its claim is safe
  to adopt because annotate --author is limited to pairs whose two files are both COMMITTED: or TASK:
  rows of the task''s change surface (AUTHOR_REFUSED:<pair>|outside-change-surface otherwise; AUTHOR_REFUSED:<test>|unregistered
  for a test no runner lists), records the agent through --by <agent-string> (adopted.yaml {origin [agent:author],
  by: agent:<s>, task, run, evidence{static: <relation or none>}}), is shown as adopted(agent:author 0.90
  by agent:<s>) until a person re-stamps it (0.99 when a static relation corroborates), is flagged AUTHOR_UNCORROBORATED
  when the deps closure holds no relation between the pair, and rides the (t<id>) commit through the Step-8
  review. Falsifier: an agent stamping every touched pair to silence UNMAPPED_SOURCE - visible as a rising
  AUTHOR_UNCORROBORATED count in onboard status and readiness, and the project-config key agent_review.author:
  false turns the autonomous branch back to attribute --propose.'
assumption_cadence_full_run_bounds_miss: 'Under completion.mode auto a coupling the map does not know
  (no edge, seed, rule, verdict or author line) can let a task land with an affected test unrun, and the
  damage is bounded by the cadence in completion.full_run_every: the miss surfaces at the next cadence
  full run (at most tasks - 1 selected completions or days later, or immediately when the selection would
  have cost selection_ratio_above of the full p95 anyway), is scored against every prediction in the window
  and attributed to the earliest task whose change surface reaches the failing unit (culprit ids from
  git log -M when history is reachable), and one miss over max_false_negatives demotes the policy to full
  until readiness is admissible again; min_full_runs_since_map_change (default 3) keeps a fresh bulk adoption
  from flipping the policy before clean full runs have scored it. Falsifier: a project whose full suite
  is too expensive to run every N tasks - raise tasks, lower selection_ratio_above, or set mode: full;
  the window is printed by --howto and readiness, never hidden.'
assumption_agent_reads_verify_vs_drive: 'The review packet is sufficient input for the verifies-or-drives
  judgement: the static anchor line +-20 lines, every assertion line in the test flagged, the source''s
  declared symbols (never its body), the prose header and, for a member seed, the testmap:unit block let
  an agent distinguish ''verifies'' from ''only drives'' at least as precisely as the baseline''s ten-sample
  human review of a class, because the judgement is local to the test body - does a flagged assertion
  check an output, a state or an exit status the named source produces, or does the source appear only
  in setup, teardown or as a path argument whose result is never checked? Measured before it is trusted:
  `onboard review --calibrate 50` against coverage facts where a coverage import exists (a measurement
  as ground truth, available headless), else against human-reviewed rows and human rejections; agreement
  >= 0.90 keeps the prior, lower agreement writes agent_review.measured_confidence, agreement below accept_min
  stops verdict adoption and readiness says so; a repo with neither ground truth runs on the prior and
  prints CALIBRATION:none. Falsifier: a repository whose tests assert through an opaque harness (a golden-diff
  script that never names what it checks) - the packet has no flagged lines, the agent answers unsure,
  and the pair is parked and then REVIEW_HUMAN rather than being guessed.'
assumption_wrong_positive_claim_only_overselects: 'A wrong `verifies` verdict produces a stamped covers
  edge to a source the test only drives; its cost is a needless run of that test when the source changes
  and a STALE nag the evidence join heals when the test next passes; it never hides a coupling, never
  suppresses a STALE row on another edge, never anchors evidence for anything the test did not run, and
  never satisfies UNMAPPED_SOURCE for a source the test does not reach (the static closure had to contain
  the source for a packet to exist, or the author had to name it from inside the task''s change surface).
  Because drives and unsure park rather than reject, no agent verdict under-selects at all; agent adoption
  errs only in the direction seeds were already allowed to err in. Falsifier: a project running --strict
  with on_empty_selection: full that relies on UNMAPPED_SOURCE to force full runs - a wrong positive there
  turns a forced full run into a selection; the cadence bounds it.'
assumption_agent_rejection_is_revocable: 'Resolved as ''no agent rejection exists to revoke'': an agent
  verdict never removes a seed from selection - drives and unsure PARK it (the verdict recorded on the
  seeded row, still selecting at d1, out of autonomous adoption, REVIEW_PARKED:<n>; two unsure from different
  runs -> REVIEW_HUMAN) - because a test that only drives a source is still coupled to it (a breaking
  change to the driven script breaks the test''s setup) and must keep running for a change to it; the
  verdict decides only whether the pair may claim. A wrong drives therefore costs a needless run and nothing
  else, no revocation mechanism is needed, and the invariant ''the loop can only fail toward running more''
  holds at the seed level. The one rejection that exists is a person''s (`onboard reject`, or a rejections[]
  row with no by:, read as a person''s) and evidence never overrules a person: a scored full-run miss
  (PREDICTION_MISSED:<test>) on a run whose change surface contains <source> prints REJECTION_CONTRADICTED:<test>|<source>|<run>
  and keeps the row for the person to revisit. Falsifier: a repository whose parked rows grow without
  anyone reading REVIEW_PARKED - the cost is over-selection time, visible in onboard status, never a missed
  test; open question 13 records the alternative.'
assumption_headless_launch_is_explicit_opt_in: 'No engine path, gate, hook or default skill flow launches
  a code agent, and none launches one in headless print mode by default: the in-gate and authoring sites
  read packets inside the session that already holds the task and the files; every launch of this feature
  is a framework wrapper - `ait skillrun testmap-review` (an interactive launch like every skill run:
  `claude --model <id> "/aitask-testmap-review --profile <p> ..."` and the Codex / OpenCode equivalents;
  skillrun never uses print mode), `ait codeagent testmap-review` (interactive by default; --print appended
  only under --headless, the same explicit opt-in batch-review requires, because Claude Code bills print
  mode at a higher per-token rate and the framework''s shell conventions forbid `claude -p` without one),
  or `ait crew runner` (which launches every crew agent through `ait codeagent --agent-string <s> invoke
  raw`, with -p only when the crew''s launch mode is headless); the engine validates a --by agent-string''s
  grammar and never resolves a model; tests/test_codeagent.sh pins testmap-review interactive-by-default
  and a grep test asserts no script of this feature invokes `claude -p` outside aitask_codeagent.sh. Falsifier:
  a CI lane with no terminal - for which --headless is the documented, explicit, billed choice, never
  a default.'
assumption_cadence_bounds_exposure: 'Under completion.mode: auto, a wrong agent verdict or an unmapped
  coupling that lets a task land without an affected test running is caught by the next cadence full run,
  which is at most full_run_every.tasks selected completion runs, full_run_every.days wall-clock, or the
  next selection whose estimate reaches selection_ratio_above of the full p95 away - whichever comes first;
  every full run scores every prediction since the last one, so the exposure window is a project-set number
  printed on every completion run as next_full_in:<n> and in --howto; the cadence state lives in costs/policy.yaml
  and is reset by every full run whatever triggered it; min_full_runs_since_map_change keeps a fresh bulk
  adoption from flipping the policy before clean full runs have scored it. Falsifier: a project whose
  tasks land faster than its full run completes - for it tasks: 1 is `full` with extra steps and the project
  should stay on full.'
component_adoption_ledger: 'Adoption ledger: the three-file state of a machine-proposed edge and the rules
  that move it - registry/seeded.yaml (the queue: rows {test[#member], covers, origin[], confidence, evidence{},
  proposed_at, verdict?}; select-only at d1 with reason edge(seeded:<origins>), no stamp, invisible to
  stale, never --strict, SEEDED:<n> on check / stale --all / readiness; a row may carry a verdict from
  the intake - verifies until it adopts, or drives | unsure as a parked mark that keeps the row selecting
  and out of autonomous adoption, with evidence.agent_review{verdict, assert_line, rationale, by, run,
  packet_sha, test_blob, unsure, at}), registry/adopted.yaml (provenance: rows {test, source, origin[],
  confidence, adopted_at, task, by: human:<email>|agent:<agent-string>|auto, run?, rationale?, assert_line?,
  packet_sha?, test_blob?, source_blob?} for a stamped edge accepted by evidence class, by a verifies
  verdict or by an author claim; shown as adopted(<origins> <confidence> by <who>) on stale and explain
  rows; counted as ADOPTED_UNREVIEWED:<n>|<ratio> and AGENT_ADOPTED:<n>|<ratio> by readiness and ADOPTED:<n>|human
  <h>|agent <a>|auto <m> by check; a row is deleted when a human verify, stale --confirm-source, annotate
  or a per-row adopt re-stamps that edge) and onboard.yaml''s rejections[] (rows {test, source, reason,
  by: human:<email>}; an absent by: reads as a person''s; never re-proposed; a scored miss that contradicts
  one prints REJECTION_CONTRADICTED and keeps it) and reviews[] (the verdict memo {test, source, verdict,
  test_blob, packet_sha, run, by}, so a pair is read once per test blob per reader). Transitions: onboard
  seed / attribute --propose -> seeded; onboard adopt --class <origin> [--accept-min 0.85] [--scope <glob>]
  (a person) -> adopted {by: human}; onboard adopt --class <rule|measurement> --auto -> adopted {by: auto},
  ADOPT_REFUSED:<pair>|not-autonomous for any other class; onboard adopt --agent-verdicts - --by agent:<s>
  --run <r> with verifies -> adopted {by: agent}, with drives | unsure -> parked; annotate --author on
  the task''s change surface -> adopted {origin [agent:author], by: agent}; onboard adopt <test> <source>
  | --area <a> --batch <n> and an in-gate row a person confirmed -> reviewed (stamp, no provenance row);
  human re-stamp -> reviewed; onboard reject -> rejected (a person''s verb; REJECT_REFUSED:headless under
  AIT_PROFILE_HEADLESS=1). Load rules: SEED_SHADOWED, ADOPTED_ORPHAN, absent-by:-is-human. The autonomous
  floor: an autonomous path may seed everything and may adopt a class only when every member carries a
  rule, a measurement or a reading origin and clears accept_min; it may never adopt a heuristic without
  a reading, reject a seed or change a kind. Costs recorded under tradeoff_two_edge_states_during_adoption,
  tradeoff_seed_precision, tradeoff_agent_judgement_unmeasured and tradeoff_wrong_positive_invisible_to_score.'
component_agent_brief: 'Agent brief (internal/brief): engine verb `brief [--md]`, surfaced as `ait test
  --howto [--md]` and `ait testmap brief`, prints TESTMAP:<state>|since|LEVEL:<n>|POLICY:<mode>[|next
  full in <n> tasks]|seeds pending <n> (parked <p>, review_human <r>)|adopted <n> (agent <a>, human <h>,
  auto <m>), one RUNNER:<name>|<kind>| <units>|<how it is invoked>|<resources>[|subsumes ...] line per
  runner, FULL_GATE:<runner>|<p95 est>|<cadence: every N tasks / >= R / D d>|<tests_pass timeout>, GATE:
  (the chain testmap_fresh -> testmap_check -> tests_pass and what --gate would run now under the policy),
  AGENT_REVIEW:enabled|<confidence>|<calibration ratio or none>|<agreement or none>, VERBS: (the four
  forms), AXES: per declared axis with facets and value counts, RESOURCE: per declared resource with its
  kind and what a refusal looks like (exit 75 -> deferred), NEW_TEST: (the annotate --suggest hint), DOCS:<path>
  per config.yaml docs: entry, NOTES: the config.yaml notes: lines verbatim (<=10, project-declared),
  ONBOARD_NEXT: while a ledger is unfinished, KIND_PROPOSALS:<n> and REVIEW_HUMAN:<n> when non-zero; before
  onboarding it prints TESTMAP_ABSENT plus the test_command; --md renders the same as markdown for agents;
  < 100 ms warm.'
component_agent_instructions: The shared agent-instructions seed (seed/aitasks_agent_instructions.seed.md)
  gains a fourteen-line `## Running Tests` section - run tests only through the framework entrypoint,
  never pytest / go test / gradle / a test script directly; `./ait test` (selected for the task, a reason
  per line), `./ait test <path>...` (a named unit; a SOURCE path runs what covers it), `./ait test --all`
  (the whole suite - what completion runs while the policy is full), `./ait test --howto` (runners, kinds,
  resources, full gate, policy, notes); UNANNOTATED_TEST -> `./ait testmap annotate --suggest <path>`;
  UNMAPPED_SOURCE -> map it before the gate (/aitask-testmap); TESTMAP_ABSENT -> /aitask-testmap-onboard;
  the exit-code table - installed unchanged into CLAUDE.md's >>>aitasks block, AGENTS.md, .codex/instructions.md
  and the OpenCode mirror by the existing assemble_aitasks_instructions() on every ait setup and ait upgrade;
  tests/test_agent_instructions.sh gains one case asserting the heading in all four rendered surfaces
  through a real install.sh --dir; the seed carries no project specifics and names no agent - `ait test
  --howto` computes them so the current-state-only doc rule holds and nothing condensed from runners.yaml
  lives in a constant; the hand-maintained CLAUDE.md case is the level-0 onboarding task's edit.
component_annotation_scanner: 'Annotation scanner and rewriter (internal/annot): grammar v3 - testmap:unit
  <Member> opens a member block that owns every following testmap: line until the next testmap:unit or
  end of file (a file-level block precedes the first unit); testmap:kind, testmap:covers <path> @<date>/<blob10>,
  testmap:area, testmap:scope, testmap:trigger, testmap:reads <glob> (helper files only), testmap:axis
  <axis>.<facet>=<value>, testmap:reviewed, runner/needs/batch - per comment leader and Python module
  docstrings (read); refuses unknown keys with a line number; the line-targeted rewriter edits stamps
  by (file, line, current text) and refuses on REWRITE_CONFLICT; annotate --from-body seeds covers for
  a member from the kotlin scanner''s symbol resolution of the block''s own lines; produces both generated
  files from every runner''s list output. Callers of the rewriter beyond verify and stale --confirm*,
  none a new writer: `onboard adopt` (by class, by row, or from a verifies verdict through --agent-verdicts)
  and `annotate --author <test> <source> --task <id> --by <agent-string>`, which checks both files are
  COMMITTED: or TASK: rows of the task''s change surface (AUTHOR_REFUSED:<pair>|outside-change-surface
  otherwise), inserts the stamped line and writes the adopted.yaml row with origin [agent:author]. All
  insert testmap:covers lines at a fixed position per language, comment lines only (bash after the shebang
  and leading # block; Python as # lines after the module docstring, never inside it; Go after the package
  clause; Kotlin after the import block, or inside the member''s testmap:unit block for a member seed),
  each stamped @<date>/<blob10> at adopt time, one file rewritten per adopted item; existing `# Covers:`
  prose headers are shown in packets as REVIEW_PROSE lines and read by the prose origin at 0.30, never
  matched by the annotation scanner and never rewritten.'
component_axes: 'Axis resolver verbs (internal/axes): ait testmap axes --list prints every declared axis
  with its facets, values and the variant count each value has in list; --check runs the axis rules (DEAD_AXIS_SOURCE,
  UNKNOWN_VARIANT, UNCOVERED_VALUE); --explain <path> prints AXIS:<axis>.<facet>|<value or ->|<why> per
  facet for one file - which glob matched, or that no source is declared - so a maintainer sees where
  a file lands before anything is trusted; resolve(changeSet) -> set | ANY is the SourcesHit join read
  the other way, with ANY printed as - and meaning no axis hit.'
component_binary_distribution: 'Binary distribution: engine/build.sh as the single build and matrix command;
  the engine job in release.yml (setup-go from engine/go.mod, go vet, go test, build.sh all) producing
  ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and ait-testmap_<V>_SHA256SUMS.txt attached by both action-gh-release
  steps with release needs: [plan, engine]; the unchanged VERSION-matches-tag guard; a new engine-check.yml
  on push/pull_request for engine/** (gofmt, vet, test, 2x bench rule); lib/platform_detect.sh; the shim''s
  strict handshake (AIT_TESTMAP_BIN with override notice > AIT_ENGINE=dev slot at $AITASKS_HOME/engine/dev/
  requiring <V>-dev+<sha> > $AITASKS_HOME/engine/v<V>/ requiring == VERSION > ENGINE_MISSING:<path> exit
  3 with repair hint); tests test_testmap_shim.sh (extended with an AITASKS_HOME host), test_platform_detect.sh
  and test_aitasks_home.sh; aidocs/framework/go_engine.md, a CLAUDE.md Engine block and a packaging_strategy.md
  paragraph naming ~/.aitasks/engine/; release-packaging.yml and nfpm arch: all untouched.'
component_broad_test_scopes: 'Broad-test scheduling and staleness policy: kind integration|e2e|device
  selects the scoped association form; broad_after_unit: true waves run scoped rows only after a green
  unit wave; device_policy: filter_by_resource default; scoped rows are exempt from per-edit digest staleness,
  with STALE_AREA as the evidence-based drift signal and REVIEW_DUE as an opt-in cadence; attribute widens
  areas by evidence; covers on a scoped row is allowed for digest-stamped fixture pins; a suite row (thinking_app''s
  verify-active) marked full: true with a children: post-processor anchors registered ids on every run;
  variant-bearing units are unit kind, never area-scoped, and ride the unit wave with admission-holding
  invocations ordered last; completion.deferred: run means the suite budget applies to the interactive
  loop only.'
component_cell_enumeration: 'Enumeration and reconciliation: there is no aitestmap/cells/ directory and
  no _cells.yaml - the project''s runner list verb is the enumeration surface and scan --apply persists
  its output as the variants: list on each member row of _scanned.yaml (49 rows with at most ten values
  for thinking_app), so select never execs a runner and only scan and check call list; two-way reconciliation
  is kept as UNCOVERED_VALUE:<axis>|<value> (a declared value no runner lists) and UNMAPPED_ARTIFACT:<path>|<runner>
  (a file matching a runner''s declared artifact_glob: that no listed id''s artifact column claims), both
  failing check --strict after bootstrap; thinking_app''s list reads the two membership manifests and
  matrix_classes, every fact from a file the project already guards; onboard detect''s UNIVERSE: is the
  same count taken before runners exist and onboard inventory is the first consumer of UNREGISTERED: rows
  as a to-do list.'
component_completion_policy: 'aitestmap/config.yaml `completion:` block: mode full|selected|auto (auto
  is what detect --write writes and the attended config table confirms; selected is written only by the
  onboarding skill''s --policy re-entry after READINESS_DECISION:ADMISSIBLE beside a human run_gate_admission.approved_by
  in config.yaml; full is the project''s opt-out of any flip), full_run_every {tasks 5, selection_ratio_above
  0.60, days 7} (the cadence; all three required when the mode is auto - READINESS:cadence_declared: tasks
  >= 2, 0 < selection_ratio_above <= 1, days >= 1), deferred run|fail (what completion does with rows
  the interactive budget would cut; default run), on_empty_selection skip|full (default skip -> exit 2
  -> gate skip under the opt-in; ignored by a cadence full run), engine_absent error|fallback_command
  (default error). `ait test --gate` re-checks readiness on every completion run: under selected an unmet
  criterion prints POLICY_DEMOTED:selected->full|<criterion> and runs full; under auto a not-yet-admissible
  map runs full (POLICY:auto|full|not_yet:<criterion>), the first admissible run prints POLICY_FLIPPED:auto->selected|engine:readiness@<run>
  and writes approved_by {who: engine:readiness@<run-id>, at, mode: auto, statement: <the readiness lines>}
  to aitestmap/costs/policy.yaml (the engine''s ledger, so config.yaml stays a human-authored declaration;
  the engine prints POLICY_WRITE:<path> and the bash front commits it under `ait: testmap policy flip
  (t<id>)` with the path named), a due cadence trigger (selected_since_full >= tasks; the selection''s
  per-group estimate / the newest full p95 on this host class >= selection_ratio_above; now - last_full_run.at
  >= days) runs full with POLICY:auto|full|cadence:<tasks|selection_ratio|days>, records last_full_run,
  resets selected_since_full and commits under `ait: testmap policy full-run (t<id>)`, otherwise the selection
  runs with POLICY:auto|selected|next_full_in:<n> and the counter increments; a later unmet criterion
  prints POLICY_DEMOTED:auto->full|<criterion> and clears approved_by. The human flip and the engine flip
  are both bounded by the automatic demotion and the engine flip additionally by the cadence, so the policy
  can only fail toward running more; the cadence sets how long a miss can survive (tasks - 1 completions,
  days days) and --howto prints it. readiness prints POLICY:<mode>|<what --gate would run now>[|next_full_in:<n>]
  and CADENCE:<last full run>|<selected completions since>|<days since>; the gate-run ledger block carries
  result="MODE:<full|selected>|<n units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>]". The cadence
  check inside ait test --gate is < 50 ms.'
component_cost_ledger: 'Cost ledger (internal/cost): Welford per (id, host class) where id may be a variant,
  with P2 p95 and last; per-repo ledger .aitask-testmap/ledger.jsonl with run_id/id/status/duration_ms/head_sha
  per result and {run_id, group, overhead_ms, units_reported} per invocation; costs --update folds both
  into aitestmap/costs/<hostclass>.yaml and truncates; last_pass {sha, at, run_id} per id and a flake
  rate with flake_threshold; the estimate for a selection is the sum over invocation groups of overhead.p95
  + the p95 of each selected id, reported per kind; costs/predictions.yaml holds the last 200 scored full
  runs. Run-id prefixes, stated here once: test- for interactive and advisory runs, gate- for completion
  runs, full- for --all, review- for bulk review runs (which write no cost rows); the first three write
  ordinary rows and feed cost and evidence exactly like any run, and the ledger says which surface produced
  a row; the SELECTED:<n>|<est_s> line''s estimate is the same per-group sum the budget uses and the number
  selection_ratio_above compares to the newest full run''s p95 on this host class; `costs --gate-timeout
  tests_pass` prints GATE_TIMEOUT_SUGGESTED:<gate>|<seconds> = max(600, 3 x p95 of the newest full run
  on this host class), which onboarding''s full_run phase writes into the project''s gates.yaml after
  the first measured full run. aitestmap/costs/policy.yaml {last_full_run: {run_id, at, task, sha}, selected_since_full:
  <n>, approved_by: {who, at, mode, statement}} is the engine''s policy ledger under auto, written by
  `ait test --gate` and committed beside the other engine-written cost files so config.yaml stays human-authored.'
component_dependency_scanners: 'Dependency scanners (internal/deps): built-in bash, python, go (go list
  -deps -json cached by go.sum digest), kotlin with the opaque contract over main and test roots, Gradle
  module graph, executable plugins under aitestmap/scanners/ speaking one JSON line per file {file, deps,
  opaque?, reads?}, the opt-in android-res symbol scanner, forward deps cached per source blob under ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json
  and inverted in memory; the bash scanner''s literal-invocation facts (a test that runs ./.aitask-scripts/x.sh
  or sources lib/y.sh, including $SCRIPT_DIR- and $PROJECT_DIR-relative forms resolved against every source
  root), the python and kotlin scanners'' direct imports of a main-root file (Python through the file''s
  own sys.path bootstrap) and the go scanner''s package membership are exposed to internal/seed as the
  static:invocation, static:import and static:package origins - same scan, same cache, read once; two
  more read-only facts are exposed to internal/onboard review from the same cache: the anchor line (file:line)
  of each static fact, and a source''s declared symbols (bash function names, top-level verbs and the
  output tokens the scanner extracted, Python def/class, Go exported identifiers, Kotlin declarations)
  for the REVIEW_SOURCE lines - never a source body; the deeper closure stays the selector''s d2 walk
  and is never seeded as an edge.'
component_engine_binary: 'Engine binary identity and budget: version/commit/contract embedded; version
  --json prints ENGINE:<path>; fixed-prefix output; CONTRACT_MISMATCH; go test -bench budgets with the
  2x rule on the aitasks and thinking_app-shaped golden registries; pools capped at 8; verb table test,
  select, schedule, run, scan, check, stale, annotate, verify, explain, axes, areas, classify, costs (+
  --gate-timeout), score, attribute, readiness, brief, onboard {detect,inventory,seed,classify,adopt,reject,
  scaffold,status,finish}, version; budgets: select < 200 ms warm (aitasks shape) and < 250 ms with axis
  expansion (thinking_app shape), scan / check / stale --task < 300 ms, stale --all < 2 s, cold select
  < 1.5 s, brief < 100 ms warm, onboard seed static + convention < 2 s and cochange < 5 s over 600 (t<id>)
  commits (one git log pass, parsed once, cached by HEAD sha under the XDG cache), onboard status < 200
  ms; detect is excluded from the latency table (once per onboarding, execs git log and every list, not
  on any gate path); contract stays 1 (seeded.yaml, adopted.yaml and onboard.yaml carry their own contract:
  field and a newer one is refused the same way).'
component_engine_packaging: 'Engine install and developer regeneration: install_engine_binary() in aitask_setup.sh,
  reached by ait setup and by ait upgrade through install.sh''s --source-only path beside install_global_shim;
  sources lib/aitasks_home.sh; uname mapping; .sha256 sidecar short-circuit; source order --local-engine
  > exact-version release asset > --engine-from-source > ENGINE_MISSING warning; sha256sum -c / shasum
  -a 256; atomic install to $AITASKS_HOME/engine/v<V>/; version --json must echo <V>; .dev-marked binaries
  never overwritten without --force-engine; --no-testmap / AIT_TESTMAP_FETCH=0 print TESTMAP_BINARY:skipped;
  HOME_LEGACY: hint when legacy tenants exist; .aitask-testmap/ gitignored by setup; aitask_engine.sh
  with ait engine build|test|cross|prune|home [--migrate]; plus report_testmap_state() run after it: prints
  TESTMAP:engine-missing when the binary is absent, TESTMAP:absent (with `run /aitask-testmap-onboard`)
  when aitestmap/ is absent, TESTMAP:bootstrapping|<next phase> while onboard.yaml has an unfinished phase,
  and TESTMAP:onboarded otherwise; setup reports, it never onboards; the seeded agent-instructions block
  re-inserted by setup gains the Running Tests section; aitask_test.sh is a framework script shipped in
  the tarball like every aitask_*.sh, nothing to install; tests/test_install_engine_binary.sh through
  a real install.sh --dir --local-engine asserts the $AITASKS_HOME path and the TESTMAP: line in each
  state.'
component_evidence_join: 'Evidence join (internal/stale + internal/gitx, reads internal/cost): for every
  edge whose stamped_blob differs from the current blob, collects last_pass shas per reached variant from
  the local ledger and committed costs (any host class), drops candidates from invocations with a cause
  or ids over the flake threshold, keeps shas that are ancestors of HEAD, and runs one git ls-tree per
  distinct sha; an edge is EVIDENCED when every reached variant has a sha whose source object id equals
  the current blob, otherwise STALE with the unevidenced variants listed; never rewrites - stale --confirm-evidenced
  is the explicit re-stamp and the only bulk confirmation an autonomous profile may run; seeded edges
  are not joined (no stamp to heal), adopted edges are joined like any stamped edge, and the level-0 task''s
  first full run is what first populates the anchors it reads.'
component_feedback_tools: 'Feedback tools (internal/feedback): score (automatic after run --all, after
  a cadence-triggered full completion run and after a full: true suite run, printing PREDICTION_SCORED
  / PREDICTION_FALSE_NEGATIVES:<n> / PREDICTION_MISSED:<id>|<task> and appending to costs/predictions.yaml;
  after a cadence full run it scores every costs/predictions.yaml row since the last full run, attributing
  each miss to the earliest task in the window whose change surface reaches the failing unit through an
  edge, a dep or a scoped row - culprit task ids from git log --name-status -M when history is reachable;
  for each missed test and each changed source in the run''s surface whose pair sits in onboard.yaml rejections[]
  it prints REJECTION_CONTRADICTED:<test>|<source>|<run> and keeps the row - evidence removes nags and
  never overrules a person), attribute (missing-edge / test-wrong / source-wrong, missing-axis-source
  widen-only, missing-trigger / area-too-narrow; a decision may be `propose`, default in autonomous profiles,
  which writes the row to seeded.yaml with origin observed (0.70) and the run id as evidence instead of
  to observed.yaml, so autonomous runs grow the review queue and never the accepted map), readiness (prints
  LEVEL:<0-3> derived from what exists - runners.yaml -> 0, any stamped _scanned edge -> 1, any _scoped
  row or reads -> 2, axes.yaml -> 3 - NEXT:<the phase or level that raises it>, ADOPTED_UNREVIEWED:<n>|<ratio
  of covers edges>, AGENT_ADOPTED:<n>|<ratio>, SEEDED:<n>, REVIEW_PARKED:<n>, REVIEW_HUMAN:<n>, KIND_PROPOSALS:<n>,
  AUTHOR_UNCORROBORATED:<n>, REVIEW_AGREEMENT:<agree>/<labelled>|none, CALIBRATION:<ratio>|none, POLICY:<mode>|<what
  ait test --gate would run now>[|next_full_in:<n>] and CADENCE:<last full run>|<selected completions
  since>|<days since>; criteria min_scored_full_runs, max_false_negatives, require_opaque_proofs, min_full_runs_since_map_change
  (default 3: clean scored full runs since the last bulk adoption or --author write) and, under auto,
  cadence_declared (all three full_run_every rules present and sane) with approved_by read met|engine
  from costs/policy.yaml once the flip is recorded); it still enables nothing, never launches an agent,
  and ait test --gate is the only writer of the flip.'
component_framework_home: 'Framework home report and migration verb (aitask_engine.sh): ait engine home
  prints HOME_ROOT:<path>, HOME_LEGACY:<path>|<tenants found>, HOME_SYMLINK:none|<target> and HOME_NEXT:<what
  --migrate would do>; ait engine home --migrate runs under flock $AITASKS_HOME/.home.lock - refuses and
  reports no-legacy-root, already-migrated, foreign-symlink:<target>, cross-device or unknown-entry:<name>;
  moves each present entry of the known set {venv, pypy_venv, python, bin, uv, dev_tier, update_check,
  engine} with a same-device mv, rmdir''s the emptied legacy root and leaves ln -s $AITASKS_HOME ~/.aitask
  behind; prints HOME_MIGRATED:<n> or HOME_SKIPPED:<reason>. pypy_venv is in the known set because setup_pypy_venv()
  creates it, python_resolve.sh reads it, and the host this was designed on carries it - a migration without
  it would refuse here. In this release ait setup only prints HOME_LEGACY:<path>|run ''ait engine home
  --migrate''; the follow-up that flips the default (reserving --no-home-migration / AIT_HOME_MIGRATE=0)
  is admitted when tests/test_aitasks_home.sh, run through a real install.sh --dir, covers fresh install,
  migration with a working venv and PyPy venv afterwards, idempotent re-run, a hostile pre-existing symlink,
  cross-device refusal and the AITASKS_HOME override, and updates the 18 doc files naming ~/.aitask.'
component_freshness: 'Freshness: per-edge @<date>/<blob10> stamp written only by verify, annotate (including
  annotate --author, which also writes the adopted.yaml {origin [agent:author], by: agent:<s>} row), stale
  --confirm* and `onboard adopt` (by class - a person''s, or --auto over a rule or measurement class -
  by row, or from a verifies verdict through --agent-verdicts), scoped to the member block; variants carry
  no stamp; last_pass per id; bootstrap_until, require_stamp, flake_threshold; the testmap_fresh procedure
  gate dispatched by the existing procedure-gate block before the change summary so rewrites ride the
  (t<id>) commit; not a git hook, not a code-agent hook; its seeds step reads engine-cut packets (onboard
  review --ids) for the test files this task touched: attended, the agent pre-fills verifies/drives/unsure
  per row with the rationale and a person confirms (a reviewed stamp, by: human), overrides or trusts
  the batch (by: agent); autonomous, the agent''s verdicts are the adoption through `onboard adopt --agent-verdicts
  -` (verifies adopts, drives and unsure park and are left) - the stamp then rides the same (t<id>) commit
  as the test edit, which is the moment the reader has the file open and the claim is cheapest to check;
  an adopted stamp is a stamp like any other and the procedure gate handles it identically, with the adopted(...
  by <who>) display as context.'
component_gates: 'Gates: testmap_fresh (kind: procedure, verifier aitask-gate-testmap-fresh, no unlocks;
  its seeds step reads packets for the task''s touched test files and adopts or parks on verdicts) and
  testmap_check (machine, max_retries 0, timeout 120, unlocks: [tests_pass]) in gates_reference.yaml synced
  to gates.yaml; the completion test gate is the EXISTING tests_pass with test_command: ./ait test and
  gate_command_exit_contract: [test_command], so `ait gates run` needs no new verifier for running tests
  and the legacy no-gates path needs no new prose - a project reaches the selective lane by declaring
  tests_pass (onboarding''s enable phase writes it into profiles'' default_gates with testmap_check and
  testmap_fresh, with confirmation; never by hand, never by ait setup); there is no selection-only gate
  and no aitask_gate_testmap_run.sh (its logic is `ait test --gate`, blocks_dependents and max_retries:
  1 are tests_pass''s own, its timeout is a project tests_pass.timeout_seconds written from the cost ledger,
  the 75 -> error mapping lands in run_project_command_key for opted-in keys, --include-stale is applied
  by the composite, deferred rows run under completion.deferred: run); aitask_gate_testmap_check.sh reports
  SEEDED:<n> and ADOPTED:<n>|human <h>|agent <a>|auto <m> (informational, never fail) and UNMAPPED_SOURCE:<path>
  (a changed source with no edge, seed, rule or waiver - reported during bootstrap, fails under --strict
  past bootstrap_until, the strict flip being onboarding''s finish phase); an unlocks: target absent from
  a task''s active set is ignored, so testmap_check declared alone is linear as before; run_gate_admission
  and `ait testmap readiness` gate the completion POLICY flip rather than a second gate''s declaration
  - recorded by a human in config.yaml under selected, or by the engine in costs/policy.yaml under auto
  (the verifier''s `./ait test --gate` performs the flip, the bash front commits the POLICY_WRITE under
  `ait: testmap policy <flip|full-run> (t<id>)` with the path named), so the committed declaration and
  the engine''s approval ledger are different files and a reader can tell them apart; the tests_pass ledger
  block''s result= field names policy:auto with next_full_in:<n> or cadence:<trigger>, so a ledger reader
  sees whether the whole suite ran and why; the engine never enables a gate and never writes a profile.'
component_go_engine: 'Go engine and CLI: engine/cmd/ait-testmap with packages internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}
  plus internal/seed (the origins and their confidence table), internal/onboard (detect, inventory, classify,
  adopt, reject, scaffold, the phase ledger, status, finish) and internal/brief (the generated run brief);
  Go 1.26 with pinned toolchain, CGO_ENABLED=0, -trimpath -buildvcs=false -ldflags -s -w -X version/commit/contract;
  deps gopkg.in/yaml.v3, bmatcuk/doublestar/v4, golang.org/x/sync only; stdlib flag verb table, syscall.Flock,
  os/exec git; line-protocol stdout, --json, per-verb exit contracts; never writes aitasks/, aiplans/,
  .aitask-data/, a gate ledger, project_config.yaml, gates.yaml, profiles or CLAUDE.md, never invokes
  aitask_*.sh, and never needs its own install root - onboard''s task creation, profile and config edits
  are done by the skill through the framework''s own scripts, the engine only reads onboard.yaml''s task:
  and level: fields; fixture repos in t.TempDir() include synthetic git histories with (t<id>) commits
  for the cochange origin, one fixture per detect shape (bash-only, pytest, go, gradle, gradle-per-source-set)
  and one per opaque-scanner branch.'
component_onboarding_engine_verbs: 'internal/onboard behind `onboard detect [--write] | inventory | seed
  | review [--next N] [--class <origin>] [--scope <glob>] [--ids <csv>] [--json] [--out <dir>] [--calibrate
  <n>] [--crew <id>] [--collect <crew-id>] | classify [--apply|--propose] | adopt [--class <origin> [--accept-min]
  [--scope] [--auto] | --agent-verdicts - --by <agent-string> --run <id> | <test> [<source>] | --area
  <a> --batch <n> | --files-from -] | reject | scaffold | status | finish [--auto]` and the aitestmap/onboard.yaml
  phase ledger {contract, task, level, phases{detect, inventory, seed, waivers, enable, full_run, adopt,
  review: {status, at, by, counts{reviewed, adopted, parked, unsure}, partial}, classify, scaffold, finish:
  {status, at, by, counts}}, rejections[] {test, source, reason, by, run?}, reviews[], kind_proposals[],
  calibration[]} (the skill''s preflight is a precondition check, not a ledger phase). `detect` prints
  FRAMEWORK:<kind>|<glob>|<count>|<builtin>|<evidence> for a closed detector list (bash-file, pytest,
  go-test, gradle-class, kmp-sourceset, suite-from-config), UNIVERSE:<n>, UNLISTED:<n>, AGGREGATE_RUNNER:<path>
  and SERIAL_LIST:<path>|<n>, RESOURCE_HINT:<name>|<n tests>|<evidence>, SUITE_CANDIDATE:test_command|verify_build|<cmd>,
  RUNNER_SCRIPT_NEEDED:<reason>; --write emits the level-0 files (config.yaml with bootstrap_until today+90,
  require_stamp false, concurrency serial, completion.mode auto with full_run_every {tasks 5, selection_ratio_above
  0.60, days 7}, agent_review {enabled true, confidence 0.90, accept_min 0.85, calibration_min 30, batch
  20, packet_lines 120, max_pairs_per_run 400, author true}, readiness {..., min_full_runs_since_map_change
  3}, conventions:, helper_roots:; runners.yaml with builtins, bindings and the full: true suite runner
  with fallback_command:; resources.yaml from hints; areas --import-codemap) and on an existing table
  prints DETECT_DIFF: and writes nothing without --force. `inventory` runs scan + every list + check and
  prints UNREGISTERED: as the to-do list. `seed` is component_seeder. `review` and `adopt --agent-verdicts`
  are component_agent_review (packets in < 300 ms warm; verdicts validated for anchor and packet digest;
  verifies adopts with by: agent, drives and unsure park, two unsure -> REVIEW_HUMAN; --calibrate compares
  instead of writing; --crew registers one testmap-review agent per --out packet file through aitask_crew_addwork.sh
  and --collect harvests their _output.md). `classify` wraps classify --suggest with the three onboarding
  signals and on --apply writes the level-2 kind/area/scope/reads/batch lines and needs: bindings for
  confirmed rows; --propose records the CLASSIFY rows in kind_proposals[] and applies nothing; there is
  no --auto and --apply refuses under AIT_PROFILE_HEADLESS=1. `adopt` (--class <origin> [--accept-min
  0.85] [--scope <glob>] [--dry-run] for a person''s bulk adoption with an adopted.yaml row per edge,
  by: human:<email>; --class <origin> --auto for the autonomous form adopting every pair of a rule or
  measurement class with by: auto and refusing the rest with ADOPT_REFUSED:<pair>|not-autonomous; --agent-verdicts
  - for verdict lines; <test> [<source>] | --area <a> --batch <n> | --files-from - for reviewed per-row
  adoption) writes stamped testmap:covers lines through internal/annot''s line-targeted rewriter at the
  fixed per-language position, refuses ADOPT_REFUSED:<path>|dirty-foreign for a dirty file outside the
  task''s change surface, skips duplicate / unregistered / no-leader, prints WROTE: per file and ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>|<by>.
  `reject <test> <source> --reason` is a person''s verb and refuses under AIT_PROFILE_HEADLESS=1 (REJECT_REFUSED:headless).
  `scaffold --axes | --runner <builtin> --as <name> | --members` writes the level-3 axes.yaml skeleton,
  aitestmap/runners/<name>.sh whose describe/run exec the builtin and whose list prints SCAFFOLD_TODO
  until filled (check reports it), and testmap:unit member blocks. `status` prints phase rows, ONBOARD_NEXT:<phase>,
  seed queue counts per origin and per verdict (verifies / parked / unsure / unreviewed), ADOPTED_UNREVIEWED
  split by `by`, AGENT_ADOPTED, AUTHOR_UNCORROBORATED:<n>, REVIEW_PARKED:<n>, REVIEW_HUMAN:<n>, KIND_PROPOSALS:<n>,
  REVIEW_AGREEMENT, CALIBRATION, tests-with-any-edge and sources-with-any-edge ratios, the oldest pending
  seed age and the rejections count. `finish` requires status green (no pending phase, check clean, every
  remaining seed under the user-set threshold or parked with a verdict), flips require_stamp and --strict,
  records the phase; --auto is the same test printing FINISH:auto|parked <n>|review_human <m>. The engine
  reads onboard.yaml''s task: and level: and writes phase rows; it never creates a task, edits a profile,
  project_config.yaml, gates.yaml or CLAUDE.md, commits, or launches a code agent - those are the skill''s
  through the framework''s own scripts.'
component_onboarding_skill: 'Onboarding skill: .claude/skills/aitask-testmap-onboard/ as a profile-aware
  stub + SKILL.md.j2 (resolver key `onboard`) with one procedure file per phase (detect.md, inventory.md,
  seed.md, waivers.md, enable.md, full-run.md, adopt.md, review.md, classify.md, scaffold.md, finish.md
  - adopt.md orders rule -> measurement -> reading: `onboard adopt --class static:package --auto`, `--class
  coverage --auto`, then review.md, the aitask-testmap-review flow as a sub-procedure: `onboard review
  --next 20` -> read the packets -> VERDICT lines naming the assertion line for every verifies -> `onboard
  adopt --agent-verdicts - --by <agent-string> --run review-<n>` -> correct or park VERDICT_INVALID rows
  -> next batch until the queue is empty or max_pairs_per_run, the phase recorded partial and re-entered
  at ONBOARD_NEXT:review, then `onboard review --calibrate 50` where a ground truth exists; the same file
  in every profile, naming no agent); Claude Code first, Codex and OpenCode ports as follow-up tasks;
  rendered goldens under tests/golden/skills/aitask-testmap-onboard/. Flow: preconditions (`ait testmap
  version` else stop with the ait setup hint; an unfinished onboard.yaml -> re-enter at ONBOARD_NEXT;
  a finished one -> refresh mode over units newer than adopted.yaml''s last row) -> read-only survey (`onboard
  detect`, `onboard seed --json --out`) and the level proposal (frameworks and counts, edges per evidence
  class with three samples each, helpers and their globs, kind candidates with reasons, UNLISTED files,
  RUNNER_SCRIPT_NEEDED, the config writes including the completion policy and its cadence) -> one aitask
  per level created with aitask_create.sh --batch (chore, labels testing,testmap), the seed dump attached
  with ait attach, claimed with aitask_pick_own.sh, id and level written to onboard.yaml -> task-workflow
  honouring the profile: the plan is the phase list; at Step 7 each phase confirms and commits its files
  (level 0: detect --write with one AskUserQuestion per runner keep/edit/drop and the full suite wrapper;
  inventory resolving UNREGISTERED by bind or exclude:; seed with counts; waivers proposing rules for
  hot directories and expiring waivers (+90d) per UNMAPPED_SOURCE cluster; enable writing test_command:
  ./ait test with the previous value moved to the full runner (verify_build left alone unless the user
  names it as the suite - thinking_backend), gate_command_exit_contract += test_command, profiles default_gates
  += tests_pass, testmap_check, testmap_fresh (and rendered_gates when present), completion.mode auto
  with its cadence, docs: and notes: for the brief, a hand-maintained CLAUDE.md Testing paragraph, all
  confirmed once as a table; level 1: adopt --auto over the rule and measurement classes, the review loop
  read by the skill''s own agent, the intake adopting the verifies pairs, then for the parked remainder
  a person per evidence class with the agent''s verdicts and rationales pre-filled - accept all / review
  a sample of ten / edit rows / skip - or per area with --scope and --batch 50, then finish when check
  is clean; level 2: classify per batch of 20 with kind changes confirmed individually by a person; level
  3: scaffold with the maintainer) under `chore: Onboard testmap - <phase> (t<id>)` commits; Step 8 reviews
  the annotation diff; the level-0 task''s Step-9 tests_pass is the first full run (full-run.md then runs
  costs --gate-timeout -> gates.yaml tests_pass.timeout_seconds and readiness -> LEVEL / NEXT and creates
  the next level''s task with depends:). Headless (remote) profile: level 0 in full, then level 1 in full
  - adopt --auto over the rule and measurement classes, the review loop in the skill''s own session to
  the max_pairs_per_run budget, --calibrate where a ground truth exists, finish --auto - no prompts, kinds
  proposed only (`classify --propose` -> kind_proposals[]), no scaffold, and no policy re-entry because
  completion.mode auto flips itself; the skill exports AIT_PROFILE_HEADLESS=1 around the engine so reject
  and classify --apply refuse. `--policy selected` re-entry (for a project that chose completion.mode
  full): flips completion.mode only when READINESS_DECISION:ADMISSIBLE, records approved_by {who, at,
  statement} in config.yaml, one ait: commit. `--no-task` writes without committing and prints the commit
  lines.'
component_qa_integration: 'aitask-qa reads the registry when aitestmap/ exists: test-discovery.md 3a-3c
  map the changed sources through `ait testmap explain --sources <paths> --format table` (edges, test-deps,
  scoped rows; Covered / Covered (adopted by human) / Covered (adopted by agent) / Covered (adopted by
  auto) / Covered (seeded) / GAP for a source with no edge and no test-dep), falling back to the naming-convention
  scan only when no registry exists; test-execution.md 4a runs the configured `./ait test` through aitask_run_project_command.sh
  test_command --task-id <id> (which exports AIT_GATE_TASK_ID so the run is the task''s selection), 4b
  runs named units through `ait test <path>`, 4c gains a REFUSED (host resources) row for verdict error
  / command_refused, and 4d''s coverage component uses registry edges rather than file-name matches with
  seeded and agent-adopted rows counted as coverage that exists (QA measures whether a test exists, not
  who accepted the claim or whether it is fresh); the health score''s Tests component treats REFUSED like
  SKIP.'
component_reference_runners: 'Reference runners built into the binary as ait-testmap runner <name>: bash-file,
  pytest (junitxml; testmap:batch no honoured, the serial carve-out pinned by extending tests/test_serial_carveout_doc_drift.sh),
  go-test (per-file -run regex, -json), gradle-class (--tests <lowering> batch, one invocation per group_by
  group, JUnit XML inverted to ids through the list table, zero-match trap as a mechanism failure), suite
  (any command as one unit, optional child rows from a children: post-processor), device (allocator handle);
  command:/cwd: overrides; shadow-by-name with explain showing which won; engine-test over engine/; thinking_app''s
  tools/verification/testmap_runner.sh (screen-matrix: list from the two membership manifests + matrix_classes
  with an artifact column, run through screenshot-tests.sh unit-tests --tests) and verify-active as a
  full: true suite runner whose child rows come from lib/screenshot-diff-set.sh; onboard detect seeds
  the repository: bash-file for tests/**/test_*.sh, pytest for test_*.py / *_test.py (an aggregate runner
  script''s serial carve-out list becomes testmap:batch no candidates), go-test per package from `go list`,
  gradle-class for src/test/**/*.kt|java, a kmp-sourceset detector mapping commonTest / androidHostTest
  to gradle-class unit runners (:<module>:jvmTest, testDebugUnitTest) and androidDeviceTest to the device
  runner (connectedDebugAndroidTest, needs: [emulator]), and a `full: true` suite runner named `full`
  wrapping project_config.yaml test_command (or verify_build only when the user names it as the suite
  - thinking_backend keeps verify_build by default) whose children: post-processor is a builtin that inverts
  pytest junitxml, bash-file test names from the per-file exit and `go test -json` events to registered
  ids, and whose fallback_command: is the previous test_command, so the existing full gate anchors evidence
  from day one without a project script; the bash-file builtin gains a `list --invocations` mode printing
  the literal repo paths a test references (the seeder''s static:invocation origin).'
component_registry_loader: 'Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  plus axes.yaml into the six core tables (edges, scopes, areas, rules, waivers, axes) with unit ids <path>[#<member>][@<variant>],
  each member''s variants: list from _scanned.yaml, owns: routing by glob for edges and rules and by area
  name for hand-declared scopes, observed axis sources merged at load widen-only, deterministic sorted
  writes only on change, and the check rules (STALE_PATH, UNSTAMPED past bootstrap under require_stamp,
  DEAD_SCOPE, DEAD_AXIS_SOURCE, UNKNOWN_VARIANT, UNCOVERED_VALUE, UNANNOTATED_MEMBER, DEAD_MEMBER, UNREGISTERED,
  UNMAPPED_ARTIFACT, KIND_MISMATCH|CONVERT_TO_SUITE, CONTRACT_MISMATCH); two tables added: seeds from
  registry/seeded.yaml (rows {test[#member], covers, origin[], confidence, evidence{}, proposed_at, verdict?};
  a row may carry evidence.agent_review{}) and adopted from registry/adopted.yaml (rows {test, source,
  origin[], confidence, adopted_at, task, by: human:<email>|agent:<agent-string>|auto, run?, rationale?,
  assert_line?, packet_sha?, test_blob?, source_blob?}, the set of stamped covers edges accepted by class,
  by verdict or by author claim that no human has reviewed per pair); onboard.yaml''s rejections[] rows
  {test, source, reason, by, run?} with the load rule that an absent by: reads as a person''s, plus reviews[],
  kind_proposals[] and calibration[] read by status and readiness; a seed whose (test, covers) pair also
  exists as any stamped edge is dropped at load with SEED_SHADOWED reported by check; an adopted row whose
  edge no longer carries a stamp is ADOPTED_ORPHAN; write routing: onboard seed -> seeded.yaml; onboard
  adopt --agent-verdicts -> seeded.yaml (a verifies row removed; a drives / unsure verdict recorded on
  the row) + adopted.yaml + the test file through the rewriter + onboard.yaml reviews[]; onboard adopt
  --class / --auto / per row -> seeded.yaml (row removed) + adopted.yaml (class and --auto adoption only)
  + the test file; annotate --author -> the test file + adopted.yaml; onboard reject -> seeded.yaml (row
  removed) + onboard.yaml (rejection recorded so the seeder never re-proposes it); attribute --propose
  -> seeded.yaml; a human re-stamp (verify, annotate, stale --confirm-source, per-row adopt) -> adopted.yaml
  (row removed); config.yaml gains completion: (with full_run_every:), agent_review: {enabled, confidence,
  accept_min, calibration_min, batch, packet_lines, max_pairs_per_run, author, measured_confidence}, readiness:
  {min_scored_full_runs, max_false_negatives, require_opaque_proofs, min_full_runs_since_map_change},
  conventions:, helper_roots:, helper_fanin:, exclude: globs (fixtures, helpers, generated tests - never
  listed, never UNREGISTERED), docs:, notes: (<=10 lines) and broad_threshold_s; costs/policy.yaml {last_full_run,
  selected_since_full, approved_by} is read by the front and written by the engine; golden tests pin the
  two new table merges, the by: merge, the absent-by: rule, the shadow rule and the id grammar.'
component_runner_contract: 'Runner contract and repository (internal/runner): describe (unit file|class|method|variant|suite,
  axis:, batch, needs, group_by:, token_format:, filter_scope:, full:, children:, artifact_glob:), list
  as TSV <id> <kind> <lowering> [<artifact>] with member and variant ids, run --manifest with ids, lowerings
  and groups, results.jsonl per id with optional child rows under a suite parent, runner.json with per-group
  overhead rows, first-match bindings and per-test override, the builtin: scheme with command:/cwd: overrides
  and shadow-by-name, batching by (runner, group, resource set, batch flag), per-unit timeouts, units_expected/units_reported
  reconciliation per id with zero-reported-some-expected and no-registered-id as mechanism failures, exit
  contract 0/1/2/75 plus 64; repository keys added: `subsumed_by: <suite>` on a runner whose units are
  the child rows of a full: true suite runner, so `run --all` executes the suite once and never the subsumed
  runner beside it (thinking_app: screen-matrix and gradle-class subsumed by verify-active), and `fallback_command:`
  on a suite runner - the pre-onboarding test_command or an equivalent detect derived - which `ait test
  --gate` runs when the engine binary is absent and completion.engine_absent is fallback_command; `onboard
  scaffold --runner <builtin> --as <name>` emits aitestmap/runners/<name>.sh whose describe and run exec
  the builtin and whose list is a stub printing SCAFFOLD_TODO until the project fills it, which check
  reports.'
component_scheduler_resources: 'Scheduler and resources (internal/sched): kinds mutex/semaphore/admission/allocator,
  scopes host/worktree/run, acquired_by planning; flock(2) slot files taken in canonical order; admission
  exec with 75 deferral and backoff to the run deadline; allocator exec with signal-safe release; goroutines
  under errgroup; batching (variants of one runner and resource set batch into one invocation per group_by
  group, so thinking_app''s whole selection is one Gradle run holding one heavy-run slot); broad_after_unit
  waves with variant-bearing units in the unit wave and, within a wave, invocations holding an admission
  resource ordered last; config concurrency: serial|parallel defaulting to serial at bootstrap with --serial/--parallel
  overrides; the schedule report and its check half; detect''s RESOURCE_HINT rows become resources.yaml
  entries the scheduler already understands (aitasks: repo-git-index mutex, worktree scope); a refusal
  at the deadline is exit 75 (advisory: skip:admission_refused).'
component_seeder: 'Seeder (internal/seed): `ait testmap onboard seed [--from static,convention,cochange,plan,prose,coverage]
  [--min-cochange 2] [--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json --out <f>]`
  produces registry/seeded.yaml rows {test[#member], covers, origin[], confidence, evidence{static: file:line,
  convention: pair, cochange: [task ids], plan: path, prose: line, coverage: run id}, proposed_at}; the
  two READING origins are never seeded here: agent:review (0.90) is written onto an existing row by `onboard
  adopt --agent-verdicts` with evidence.agent_review {verdict, assert_line, rationale, by, run, packet_sha,
  test_blob, unsure, at}, and agent:author (0.90) by `annotate --author`; static:{package, invocation,
  import} read internal/deps facts for the test file only (direct, never the closure; same-package facts
  excluded); convention applies config.yaml conventions: patterns seeded by detect per runner (bash-file:
  test_<x>.sh -> aitask_<x>.sh | lib/<x>.sh | lib/<x>.py; pytest: test_<x>.py -> any <x>.py under the
  main roots; go-test: <x>_test.go -> <x>.go same dir; gradle-class: <Stem>[Test|*Test].kt -> <Stem>.kt
  under main); cochange parses one `git log --name-status -M --format=%H%x00%s` pass over commits whose
  subject matches (t<id>) and counts (test, source) pairs across distinct tasks (per-commit grouping fallback),
  cached by HEAD sha, SEED_HISTORY:shallow|<n>; plan reads the aitask_explain_extract_raw_data.sh cache;
  prose reads header comments and `# Covers:` lines; coverage imports coverage.py contexts JSON, go -coverprofile
  per unit, LCOV with a test-id column, or a project plugin''s {test, covers} lines. Confidence table
  static:package 1.0 (rule) / coverage 0.95 (measurement) / agent:review 0.90 or agent_review.measured_confidence
  when calibration measured lower (reading) / agent:author 0.90, 0.99 with a static relation (reading)
  / static:invocation 0.90 / static:import 0.85 / observed 0.70 / convention 0.60 / plan 0.50 / prose
  0.30 / cochange 0.20 + 0.20 per group capped 0.60 (heuristics); each origin carries class: rule|measurement|reading|heuristic;
  noisy-OR across origins, ordering only; the autonomous rule is by class first and by number second.
  Helpers separated first by helper_roots and helper_fanin with SEED_HELPER: and SEED_READS:<helper>|<glob>|<evidence>
  lines; SEED_KIND:, SEED_BATCH_NO:, SEED_MEMBER:, SEED_AXIS: from onboard classify''s signals. A rejected
  pair in onboard.yaml is never re-proposed; a pair already stamped is dropped with SEED_SHADOWED; --apply
  writes deterministically sorted, otherwise prints SEED:<test>|<source>|<origins>|<confidence> lines;
  --json --out writes the dump the skill attaches to the level task. Budget: static + convention < 2 s
  and cochange < 5 s over 600 commits on the aitasks shape. Fixtures: a synthetic repo per origin with
  a (t<id>) history, plus one per verdict branch.'
component_selector: 'Selector (internal/selectr, internal/changesurface): line-protocol intake refusing
  UNKNOWN:, the graded walk with select/implies/escalate rules, variant expansion and axis join, test-dep
  at d1, ESCALATE on opaque files, scoped join, kind-then-cost ranking, invocation groups, stale marks
  from digest compare plus the per-variant evidence join, --include-stale, suite budget with DEFERRED
  lines and budget-exempt triggers and reads, cut knobs incl. --axis, --format lines|json|tokens, prediction
  record, explain; a seeded edge - parked or not - is walked exactly like an annotation edge at d1 with
  reason edge(seeded:<origins>) and never contributes a stale mark; an adopted edge is an annotation edge
  whose reason carries adopted(<origins> <confidence> by <who>) - e.g. adopted(static:invocation+agent:review
  0.99 by agent:claudecode/opus5), adopted(agent:author 0.90 by agent:...), adopted(coverage 0.95 by auto);
  `explain --sources <path>... --format table` prints the reverse view (every unit reaching each source
  with its reason and provenance - Covered / Covered (adopted by human|agent|auto) / Covered (seeded)
  - or UNMAPPED_SOURCE) as the table aitask-qa''s test discovery consumes; the `test` composite prints
  one SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n> line and UNMAPPED_SOURCE:<path> lines before
  the ranked rows so the front can build its VERDICT without parsing the rows; `ait test <source path>`
  reaches it as a one-row TASK: change set from the front.'
component_skill: 'Skills: (1) aitask-testmap (maintenance: annotate a file / member / coordinate - including
  annotate --author for the task''s own change-surface pairs -, declare axis sources, reads on helpers,
  axes --explain, attribute before the gate, verify after editing, classify --suggest, select --format
  tokens into a render loop) opens with `ait test --howto` and hands a repo without aitestmap/ to aitask-testmap-onboard;
  (2) aitask-gate-testmap-fresh (the procedure gate: stale --task, git diff per STALE row with unevidenced
  variants, retarget STALE_PATH, re-stamp EVIDENCED, resolve check''s structural rows, prompt on UNSTAMPED
  past bootstrap, never guess UNKNOWN, never confirm STALE autonomously; an adopted(... by <who>) row
  is confirmed knowing what accepted it) whose seeds step runs `onboard review --ids <rows>` for each
  COMMITTED:/TASK: test file with seeds and reads the packets - attended: the agent''s verdict is pre-filled
  per row and the person confirms (a reviewed stamp, by: human), overrides, or trusts the batch (by: agent);
  autonomous: `onboard adopt --agent-verdicts - --by <agent-string> --run <gate-run>` (verifies adopts,
  drives and unsure park) - so a map migrates a few files per task through ordinary work; (3) aitask-testmap-onboard
  (component_onboarding_skill), profile-aware, whose review.md sub-phase is where its agent reads seeds;
  (4) aitask-testmap-review (component_agent_review_pass): profile-aware stub + SKILL.md.j2 (resolver
  key `testmap-review`), review-batch.md stating the verifies-or-drives rule once (''a test verifies a
  source when a flagged assertion line checks an output, a state or an exit status the source''s symbols
  produce; it only drives it when the source appears solely in setup, teardown or as a path argument whose
  result is never checked; answer unsure rather than guess''), batches of agent_review.batch, resumable,
  attended table-confirm / autonomous no prompts; launched by review.md inside an onboarding task, by
  `ait skillrun testmap-review` interactively, by `ait codeagent testmap-review` (interactive; --print
  only under --headless, as batch-review), or as crew agents `ait crew runner` starts through `ait codeagent`.
  Every skill''s runtime knowledge of how to run tests is the seeded `## Running Tests` block plus `./ait
  test --howto`, never prose in a SKILL.md. All ship Claude Code first with wrapper surfaces regenerated
  by aitask_audit_wrappers.sh apply-wrapper for Codex and OpenCode.'
component_staleness_tool: 'Staleness tool (internal/stale): stale --task --changes - | --all; the SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION
  line classes with %25/%7C encoding; a STALE row on a unit with variants carries a trailing |<unevidenced
  variants> field; --all adds CHECK_STRUCTURAL:<n>; content states exit 0, --strict exits 1 on STALE_PATH;
  compares blob digests of the working tree only, consults the per-variant evidence join, adds rename
  hints and culprit task ids from git log --name-status -M when history is reachable; mutates stamps via
  --confirm, --confirm-source, --confirm-evidenced, --retarget through the rewriter with a re-scan of
  touched files; seeded edges excluded from every class, SEEDED:<n> and ADOPTED:<n>|human <h>|agent <a>|auto
  <m> summary lines on --all beside CHECK_STRUCTURAL:<n>, and a STALE or EVIDENCED row whose edge has
  an adopted.yaml row carrying `adopted(<origins> <confidence> by <human:<email>|agent:<agent-string>|auto>)`
  in its DISPLAY line so the procedure gate knows whether it is confirming a class-accepted, an agent-accepted,
  an author-claimed or a per-pair reviewed claim.'
component_suite_registry: 'Scoped-row registry and areas: registry/areas.yaml plus areas: blocks in hand
  files, seedable via areas --import-codemap; _scoped.yaml rows {test, kind, runner, areas, globs, triggers,
  reads_from, needs, reviewed_at, line}; owns: by area name for hand-declared rows; the d1 join, kind
  ranking, suite budget (suite_budget_s default 600) with DEFERRED lines and budget-exempt triggers; check
  rules incl. DEAD_SCOPE and KIND_MISMATCH|CONVERT_TO_SUITE; ait testmap areas; classify --suggest with
  the reads-helper and grid heuristics; missing-trigger / area-too-narrow in attribute; a rule may select:
  a scoped test or a member by name; classify --suggest gains the three signals onboarding''s classify
  phase uses - a recorded p95 above broad_threshold_s (default 60) from the first full run, a source-set
  or directory convention (androidTest/, androidDeviceTest/, *_live.py, *_integration.sh, parity/) and
  a resource declaration or use in the file (tmux, App.run_test, install.sh --dir, real .git use, emulator,
  docker, network), plus fanout:<n> above unit_covers_max - each printed as the reason on the CLASSIFY:<test>|<kind>|<reason>
  line; attended, the skill confirms per batch of 20 with kind changes confirmed individually and `onboard
  classify --apply` writes the confirmed rows'' source lines at level 2; headless, `onboard classify --propose`
  records the rows in onboard.yaml kind_proposals[] and applies nothing (readiness prints KIND_PROPOSALS:<n>),
  because a wrong kind changes staleness semantics and no run evidence checks it.'
component_test_entrypoint: '`ait test` = .aitask-scripts/aitask_test.sh, a ~150-line bash front over the
  shim (aitask_testmap.sh): flags --task <id> | --gate | --advisory | --all | --dirty | --explain | --howto
  [--md] | --tokens | --fresh-only | --budget-s <n> | --json and positional <path|id>...; resolves MODE
  (completion iff --gate or AIT_GATE_TASK_ID; advisory iff --advisory; else interactive), TASK (--task
  > AIT_GATE_TASK_ID > aitask/<name> branch > single own lock via aitask_lock.sh --list-mine > NO_TASK),
  INTAKE (aitask_change_surface.sh list <id> piped; --dirty = every dirty path as TASK: rows, printed;
  --all; named paths: a listed test path is the unit, a source path is a one-file TASK: change set) and
  POLICY (completion: config.yaml completion.mode re-checked against readiness; under auto it also reads
  costs/policy.yaml, applies the three cadence triggers, prints POLICY:auto|selected|next_full_in:<n>
  or POLICY:auto|full|<cadence:<trigger>|not_yet:<criterion>>, has the engine write the first ADMISSIBLE
  as approved_by {engine:readiness@<run>, mode: auto} and commits every POLICY_WRITE: line under `ait:
  testmap policy <flip|full-run> (t<id>)` with the path named); calls the engine `test` composite (select
  --include-stale -> schedule -> run; interactive: budget applies, DEFERRED printed; completion: deferred
  rows run); with no aitestmap/ prints TESTMAP_ABSENT:<hint> and delegates to aitask_run_project_command.sh
  test_command; with the engine absent prints ENGINE_MISSING:<path>|<repair> and exits 3 interactively,
  runs the suite runner''s fallback_command in completion mode when completion.engine_absent is fallback_command,
  and prints VERDICT:skip REASON:testmap_absent in advisory mode; completion mode applies the policy (full
  -> run --all with subsumed_by honoured; selected -> the task selection, demoted to full with POLICY_DEMOTED:
  when readiness is NOT_YET; auto as above); advisory mode prints VERDICT:pass|fail|skip / REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
  / DETAIL: / LOG:.aitask-gates/<task>/affected_<run-id>.log / SELECTED: / UNMAPPED_SOURCE: / UNKNOWN:
  lines, exits 0/1/2/3 with aitask_run_project_command.sh''s capture contract, and appends nothing to
  any ledger; prints MODE / TASK / INTAKE / POLICY / SELECTED / RUN / RESULT, UNANNOTATED_TEST:<path>|HINT
  for a listed test in the change surface with no testmap: block, no seed and no adopted row, and UNMAPPED_SOURCE:<path>;
  exit 0 pass / 1 fail / 2 nothing ran / 3 framework error / 75 refused after deadline / 64 usage; the
  run id it passes to the composite is prefixed test- / gate- / full- by mode; dispatcher arm `test)`
  in ait; 5 permission touchpoints (no second helper script; tests/test_touchpoint_count_contract.sh re-pinned);
  tests/test_ait_test_entrypoint.sh against a fixture repo with AIT_TESTMAP_BIN pointing at a fake engine
  that replays scripted exits, in all three modes, every REASON, and the auto matrix (ADMISSIBLE x each
  cadence trigger x NOT_YET x the first-flip record and its commit).'
component_test_front_verb: 'Engine `test` composite (internal/selectr + sched + runner, reached by aitask_test.sh):
  `test --task <id> --changes - | --paths <p>... | --all [--explain] [--budget-s] [--format lines|json|tokens]
  [--run <id>]` runs select --include-stale -> schedule -> run in one process and prints SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>,
  one UNMAPPED_SOURCE:<path> per changed source no unit reaches, the ranked rows with their reasons (a
  seeded edge reads edge(seeded:<origins>), an adopted one edge(annotation) adopted(<origins> <confidence>)),
  the schedule''s wave lines, results per id and RESULT:pass|fail|skip|deferred|<run_id>; --all is run
  --all (anchors evidence, scores the newest prediction, honours subsumed_by); --explain stops after select;
  the run id is prefixed by the front. It never resolves a task, reads a profile, applies a completion
  policy or touches a gate ledger - those are the bash front''s.'
component_user_root: 'Per-user root: .aitask-scripts/lib/aitasks_home.sh exports AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}
  and aitasks_engine_dir <version|dev>, plus $AITASKS_HOME/.home.lock; sourced by the shim, aitask_setup.sh''s
  install_engine_binary, aitask_engine.sh, the verifiers and aitask_test.sh; never falls back to ~/.aitask/;
  ait setup creates $AITASKS_HOME/engine/ with mode 0755 and prints AITASKS_HOME:<path> in its summary
  beside the venv line so both roots are visible; ait engine prune walks only $AITASKS_HOME/engine/v*/;
  test_aitasks_home.sh pins the default, the env override, and that no framework script under this feature
  names ~/.aitask/.'
component_variant_axes: 'Variant axes (internal/axes, read by registry, selectr, runner, cost): aitestmap/axes.yaml
  declares axes {name, facets[], values{value: {facet: v}}, sources{facet: {v: [globs]}}}; a runner''s
  describe names the axis its variants live on and a token_format; list emits <unit>@<value> ids; the
  selector joins changed paths to facet values through sources and selects the variants carrying them
  (reason axis(<axis>.<facet>=<v>) <- <path>) plus plain units carrying testmap:axis for that value (a
  hand-declared coordinate), or every variant of a unit reached by an edge, dep, rule or test-dep; --axis
  <axis>.<facet>=<v> forces a facet; costs, last_pass, evidence and score are per variant; check enforces
  DEAD_AXIS_SOURCE, UNKNOWN_VARIANT and UNCOVERED_VALUE; observed sources widen only; the engine holds
  no project axis - the first consumer is thinking_app''s matrix axis with facets locale/direction/geometry
  over its 10 recording matrices; level-3 `onboard scaffold --axes` writes only the skeleton the maintainer
  fills - the grid heuristic proposes, a person declares.'
component_workflow_integration: 'The procedure edits of the seam: task-workflow gains affected-tests.md
  (Affected Tests Procedure) called once from Step 7 before proceeding to Step 8 - the pre-review affected
  run - wrapped in {% if profile.affected_tests is not defined or profile.affected_tests != ''off'' %};
  the procedure runs `./ait test --advisory --task <id>` (with --explain when the key is show) in the
  set -e capture form, branches: pass -> continue; fail -> the build-verification fail loop (caused by
  this task: fix and re-run; unrelated: log in Final Implementation Notes under ''Affected tests''); skip:no_selection
  -> display the UNMAPPED_SOURCE paths and, attended, offer Annotate as author (default: `ait testmap
  annotate --author <test> <source> --task <id> --by <agent-string>` for each unmapped source and the
  test on this change surface that checks it - stamped, adopted.yaml {origin agent:author, by agent:<s>,
  task, run}, riding the (t<id>) commit) / annotate by hand or a rule via aitask-testmap / attribute --propose
  / continue, with the agent''s proposed pairs pre-filled, or, autonomous, have the agent name its own
  test for each source and run annotate --author for every pair whose two files are on the change surface
  (AUTHOR_REFUSED:outside-change-surface refused and logged, AUTHOR_UNCORROBORATED printed for a pair
  with no static relation) falling back to attribute --propose when it knows none; UNANNOTATED_TEST for
  a test the task added or edited -> annotate --suggest then the same offer with --author on the rows
  the agent confirms; agent_review.author: false restores the propose branch; skip:testmap_absent|registry_absent
  -> one line, continue; skip:unknown_paths -> the scope prompt aitask-gate-docs-updated already uses;
  skip:admission_refused -> print DETAIL, continue; rc 3 -> diagnose, never fix code; the verdict line
  is recorded in the plan''s Final Implementation Notes and never in the gate ledger (advisory); it is
  the task-scoped selection guaranteed to exist in every profile, so it guarantees the prediction record
  the completion run scores and readiness counts - without it a repository may never reach ADMISSIBLE;
  profile key affected_tests run|show|off documented in profiles.md, default.yaml and fast.yaml omit it
  (run), remote.yaml sets run; no profile key is added for agent review (agent_review.enabled and agent_review.author
  are project config, so provenance never depends on who ran the task); the in-loop call is the Step-7
  paragraph, not the procedure; Step 8 (testmap_fresh dispatch plus its packet-reading seeds step - attended
  pre-fill / confirm / trust-batch, autonomous --agent-verdicts) and Step 9 (gate orchestrator, build-verification.md)
  otherwise unchanged; the onboarding skill''s adopt.md gains review.md; the new aitask-testmap-review
  skill and the rewritten gate skill rendered for every profile x agent; aitask-qa test-discovery.md 3a-3c
  use `ait testmap explain --sources <changed> --format table` when aitestmap/ exists and test-execution.md
  4a runs `./ait test` through aitask_run_project_command.sh --task-id; pickrem and pickweb inherit Step
  7 and see a printed skip on Web; ait setup prints TESTMAP:<state>; goldens under tests/golden/ regenerated
  for every profile x agent; aitask_skill_verify.sh run; profiles.md row added.'
component_workflow_seam: 'The data edits of the seam: task-workflow SKILL.md.j2 Step 7 gains one paragraph
  after `Follow the approved plan` - run ./ait test as the implementation test loop, answer UNANNOTATED_TEST
  with annotate --suggest and UNMAPPED_SOURCE by mapping the source, never call the test tool directly
  (rendered into every profile; goldens regenerated); build-verification.md gains a branch for verdict
  error / reason command_refused | command_errored (host refused resources or the framework could not
  run: do not fix code, do not record pass, re-run later - the entrypoint already deferred to its deadline);
  lib/gate_verifier_lib.sh run_project_command_key() gains the 75 -> error and 3 -> error rows for opted-in
  keys and exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command, and aitask_run_project_command.sh
  --task-id exports the former; gates_reference.yaml adds testmap_fresh and testmap_check (unlocks: [tests_pass])
  and no selection-only gate; the project''s profiles gain tests_pass, testmap_check and testmap_fresh
  in default_gates via onboarding; no profile key is added for agent review (agent_review.enabled and
  agent_review.author live in aitestmap/config.yaml); the ait dispatcher gains `test)`; aitask_codeagent.sh
  gains the `testmap-review` operation (interactive by default, --print only under --headless, mirroring
  batch-review) and `list-models` shows verified.testmap-review; seed/models_{claudecode,codex,opencode}.json
  gain the verified.testmap-review key per model (0 until measured; aitask-add-model seeds it); aidocs/framework/aitasks_extension_points.md
  gains `Adding a test-framework detector` and `Adding a seed origin` with the class column (rule / measurement
  / reading / heuristic) and the autonomous-floor rule; tests/test_gate_verifiers.sh covers 75 and the
  env export, tests/test_codeagent.sh pins testmap-review interactive-by-default, tests/test_serial_carveout_doc_drift.sh
  is extended for the pytest carve-out pin, tests/test_no_unscoped_task_commit.sh is unaffected because
  the skill commits through aitask_task_commit.sh.'
component_agent_review: 'Agent review verbs (internal/onboard/review.go). Packet writer `onboard review
  [--next N] [--class <origin>] [--scope <glob>] [--ids <csv>] [--json] [--out <dir>] [--calibrate <n>]`:
  selects seeded rows without a verdict for their current test blob from this reader (the onboard.yaml
  reviews[] memo; REVIEW_MEMO:<skipped>; a pair whose second unsure came from a different run is REVIEW_HUMAN
  and never selected), groups them by test file so one file''s pairs share a batch (REVIEW_BATCH:<n>|<pairs>),
  and prints the line-protocol packet - REVIEW_PAIR:<id>|<test>|<source>|<origins>|<confidence>|<unsure_count>,
  REVIEW_ANCHOR:<id>|<file:line>, REVIEW_TEST:<id>|<line>|<flag>|<text> (the anchor +-20 lines then every
  assertion line - assert_eq / assert_contains / assert / expect / require / t.Fatal* / assertEquals /
  shouldBe / grep -q on captured output - flagged ''!'', ceiling agent_review.packet_lines 120), REVIEW_SOURCE:<id>|<symbol>|<kind>
  (declared symbols and output tokens only, never the body), REVIEW_PROSE:, REVIEW_MEMBER:, REVIEW_END:<id>|<packet_sha>
  - from the deps cache in < 300 ms warm, no runner and no model; as JSON with --json; as one file per
  batch under .aitask-testmap/onboard/<run>/review/<n>.txt (gitignored) with --out, < 1 s per 100 pairs.
  Intake `onboard adopt --agent-verdicts - --by <agent-string> --run <run-id>` reads VERDICT:<id>|verifies|<test
  path:line>|<rationale> / VERDICT:<id>|drives|-|<rationale> / VERDICT:<id>|unsure|-|<rationale> (rationale
  <= 160 chars, | as %7C) in < 200 ms per batch; validates the pair is in a packet this run cut, the packet_sha
  is current (VERDICT_STALE:<id> otherwise, ignored and re-packeted), --by against lib/agent_string.sh''s
  <agent>/<model> grammar (exit 64 otherwise; defaults to $AIT_AGENT_STRING when exported), and for verifies
  that the named line exists in the test file and contains the source''s stem, its invocation form, an
  output path the source writes or an exported symbol (VERDICT_INVALID:<id>|<reason>, including assert_line_names_other
  for a homonym stem of another source; the row untouched). Writes: verifies -> origin[] += agent:review,
  evidence.agent_review {verdict, assert_line, rationale, by, run, packet_sha, test_blob, at}, noisy-OR
  recomputed and at or above accept_min the stamp through the rewriter, the adopted.yaml row {by: agent:<s>,
  run, rationale, assert_line, packet_sha, test_blob, source_blob} and the seed row removed; drives ->
  the verdict on the row (parked: still selects, out of autonomous adoption, not re-read for these test
  bytes); unsure -> evidence.agent_review.unsure += 1, re-packeted once for a different run, at 2 REVIEW_HUMAN;
  every verdict into reviews[]. Prints REVIEW_APPLIED:<verifies>|<drives>|<unsure>|<invalid>| <stale>,
  WROTE:, ADOPT_SUMMARY:...|agent, REVIEW_PARKED:<n>, REVIEW_HUMAN:<n>, REVIEW_AGREEMENT:<agree>/<labelled>|none
  over pairs that also carry a human per-row decision, and REVIEW_ORIGIN_DEMOTED when agreement or calibration
  falls below accept_min over calibration_min pairs (writing agent_review.measured_confidence). Calibration
  --calibrate <n> samples pairs with a ground truth (coverage rows first, else reviewed edges and human
  rejections), marks them so the intake compares instead of writing, prints CALIBRATION:agree <a>|disagree
  <d>|<ratio> into onboard.yaml calibration[]. Crew form --crew <id> registers one testmap-review reviewer
  per --out packet file through aitask_crew_addwork.sh --type testmap-review --work2do review-batch.md
  (the crew''s launch_mode decides headless or interactive; the runner launches each through `ait codeagent
  --agent-string <s> invoke raw`) and prints the `ait crew runner` line for a person to start; --collect
  <crew-id> reads each agent''s _output.md as verdict lines into the intake. Config agent_review {enabled
  true, confidence 0.90, accept_min 0.85, calibration_min 30, batch 20, packet_lines 120, max_pairs_per_run
  400, author true, measured_confidence}. Tests: fixture repos per language for packet shape and assertion
  flagging; every verdict branch; every VERDICT_INVALID reason; VERDICT_STALE; the --by refusal; the memo
  skip; the unsure escalation; agreement crossing the threshold both ways; calibration against a coverage
  fixture; --auto refusing a heuristic class; --collect over a fixture crew.'
component_auto_policy: 'Auto completion policy and cadence (internal/feedback/cadence.go + the auto arm
  of aitask_test.sh''s policy step): the declaration is config.yaml completion.full_run_every {tasks 5,
  selection_ratio_above 0.60, days 7}; the state is aitestmap/costs/policy.yaml {last_full_run {run_id,
  at, task, sha}, selected_since_full, approved_by {who: engine:readiness@<run>, at, mode: auto, statement:
  <the readiness lines>}} - the engine''s ledger, committed: the engine writes it and prints POLICY_WRITE:aitestmap/costs/policy.yaml,
  the bash front commits it under `ait: testmap policy <flip|full-run> (t<id>)` with the path named, the
  same commit path the human flip uses for config.yaml. Decision order inside ait test --gate under auto:
  readiness NOT_YET -> full (POLICY:auto|full|not_yet:<criterion>); ADMISSIBLE with no approved_by ->
  POLICY_FLIPPED:auto->selected|engine:readiness@<run>, write, selection; a cadence trigger due (selected_since_full
  >= tasks; the selection''s per-group estimate >= selection_ratio_above x the newest full p95 on this
  host class; now - last_full_run.at >= days) -> full with POLICY:auto|full|cadence:<tasks| selection_ratio|days>;
  otherwise the selection with POLICY:auto|selected|next_full_in:<n> = tasks - selected_since_full and
  the counter incremented; an unmet criterion later -> POLICY_DEMOTED:auto->full| <criterion> and approved_by
  cleared. A cadence full run ignores on_empty_selection, honours subsumed_by and deferred: run, records
  last_full_run, resets selected_since_full and triggers the window score in component_feedback_tools;
  every full run, whatever triggered it, resets the counter. readiness adds cadence_declared (all three
  triggers present and sane: tasks >= 2, 0 < selection_ratio_above <= 1, days >= 1) and the CADENCE: line;
  --howto prints the cadence on FULL_GATE: and `next full in <n>` on TESTMAP:; the ledger block result=
  carries policy:auto|next_full_in:<n> or cadence:<trigger>. Budget: the cadence check < 50 ms. Tests:
  tests/test_ait_test_entrypoint.sh with the fake engine replaying readiness states and ledger counters
  for each trigger, the flip write and commit, the demotion clearing approved_by; engine tests for the
  window score attributing a miss to the right task.'
component_author_annotation: 'Author annotation: `ait testmap annotate --author <test> <source>... [--task
  <id>] [--by <agent-string>]` in internal/annot as a caller of the line-targeted rewriter with an adopted.yaml
  write: resolves the task as ait test does, reads the change surface through aitask_change_surface.sh
  list <id> (--changes -), refuses AUTHOR_REFUSED:<pair>|outside-change-surface unless both the test and
  the source are COMMITTED: or TASK: rows, refuses an unregistered test (AUTHOR_REFUSED:<test>|unregistered),
  refuses a --by that is not an agent-string (exit 64; $AIT_AGENT_STRING is the default when exported),
  writes the stamped testmap:covers line at the fixed per-language position (or into the member''s testmap:unit
  block), and adds adopted.yaml {test, source, origin [agent:author], confidence 0.90 (0.99 with a static
  relation), adopted_at, task, by: agent:<s>, run, evidence {static: invocation|import|package|none}};
  prints WROTE:<file>, AUTHOR_STAMPED:<pair>|<static or none> and AUTHOR_UNCORROBORATED:<pair> when the
  closure holds no relation. The pre-review procedure''s autonomous no_selection and UNANNOTATED_TEST
  branches are its only automatic callers (project-config key agent_review.author true|false, default
  true; false turns them back to attribute --propose); the attended offer''s Annotate as author is the
  same verb; aitask-testmap documents it. stale and explain show adopted(agent:author 0.90 by agent:<s>);
  a later human re-stamp deletes the row like any adopted row; readiness and onboard status count AUTHOR_UNCORROBORATED.
  Tests: the refusal outside the surface, member placement, corroborated and uncorroborated confidences,
  the --by refusal, the row leaving on verify.'
component_agent_review_pass: 'Agent review pass: the reading end to end - an agent reads the packets `onboard
  review` cut and returns verdicts the intake (`onboard adopt --agent-verdicts - --by <agent-string> --run
  <run-id>`) turns into adopted rows or parked marks (component_agent_review holds the engine verbs).
  Three sites share the intake: the testmap_fresh in-gate step (the task''s touched test files through
  `onboard review --ids`; attended pre-fill / confirm per row (reviewed, by: human) / override / trust-batch
  (by: agent); autonomous adopts), the pre-review Affected Tests procedure (the task''s own pairs via
  `annotate --author`, origin agent:author; component_author_annotation) and the bulk skill aitask-testmap-review
  (profile-aware stub + SKILL.md.j2, resolver key testmap-review, review-batch.md stating the verifies-or-drives
  rule once and unsure as the answer when neither applies, batches of agent_review.batch (20), resumable
  through onboard.yaml phases.review with max_pairs_per_run (400), attended table-confirm per batch, autonomous
  no prompts, commits under `chore: Onboard testmap - review (t<id>)` inside an onboarding task, prints
  the commit lines otherwise; the onboarding skill''s review.md invokes the same flow). Launch surfaces:
  review.md inside the onboarding task''s session; `ait skillrun testmap-review [--profile <p>] [-- --class
  <origin>]` (interactive; skillrun never uses print mode); `ait codeagent testmap-review [--headless]`
  (the operation joins SUPPORTED_OPERATIONS; --print only under the flag, as batch-review); one crew agent
  per `--out` packet file registered by `onboard review --crew` and started by `ait crew runner` through
  `ait codeagent`, harvested by --collect. `verified.testmap-review` in seed/models_{claudecode,codex,opencode}.json
  (the existing per-operation score table; 0 until measured; aitask-add-model seeds the key). Semantics:
  verifies adopts with by: agent:<agent-string>; drives and unsure park (still selecting, out of autonomous
  adoption, listed); no verdict rejects; a wrong verifies over-selects and is confirmed or retargeted
  at testmap_fresh like any adopted edge; the origin''s confidence is the 0.90 prior until calibration
  measures it. Budgets: packet assembly < 300 ms warm, packets bounded by packet_lines (aitasks: 36 packets
  of <= 2,400 excerpt lines). Tests: skill goldens for every profile x agent; tests/test_codeagent.sh
  pins testmap-review interactive-by-default; a grep test asserts no script of this feature invokes `claude
  -p` outside aitask_codeagent.sh.'
tradeoff_accept_rewrites_history: 'Disadvantage: adopting seeds inserts comment lines into hundreds of
  test files, so `git blame` on any test header points at the adoption commit and a concurrent task editing
  the same file hits a textual conflict on the header; mitigated by comment-only insertions at a fixed
  position (after the header block / docstring / package clause / import block), per-class, per-area and
  per-review-batch commits named for what they are, the incremental path that adopts a file''s seeds only
  inside a task that already edits it, ADOPT_REFUSED:dirty-foreign, and the rewriter''s REWRITE_CONFLICT
  refusing a file that changed under it; author annotations add one to three lines per task inside a diff
  the task already owns; the bulk rewrite now also happens headless, split across runs by max_pairs_per_run;
  a project that wants no comment churn keeps seeds unadopted (agent_review.enabled: false) and accepts
  selection-only enforcement, which onboard status reports as the state it is.'
tradeoff_area_glob_coarseness: 'Disadvantage: area and scope globs are coarser than edges - a broad area
  over-selects its tests on every edit inside it and a scoped test depending on a file outside its scope
  is under-selected until a full run scores it; mitigated by the suite budget with explicit DEFERRED lines,
  budget-exempt triggers and reads globs for known sharp edges, and the missing-trigger / area-too-narrow
  attribution path.'
tradeoff_attribution_risk: 'Risk: an agent that edits sources without attributing produces a map that
  looks current and is not; narrowed three ways - such a source shows as STALE in the next task touching
  it and as a stale mark on every selection; the Step-7 run reports UNMAPPED_SOURCE:<path> for a changed
  source no unit reaches at the moment the agent introduced it, and the pre-review procedure offers annotate
  / attribute --propose / waiver right there, so a new coupling with no edge is surfaced during the task
  rather than only on a full run; and in a repo whose completion policy is full every miss is counted
  by the automatic score within one task. What still escapes is a coupling to a source that already has
  some edge, which only score can find.'
tradeoff_autonomous_confirmation_weak: 'Risk: autonomous acts on the map are weaker than review, and this
  design has four of them - --confirm-evidenced (a green run on every reached variant whose tree held
  the current bytes of the specific source re-stamps an edge, records confirmed_by: <run_id>, re-opened
  by a later score miss; still the only bulk RE-STAMP an autonomous profile may run), adopt --auto over
  rule and measurement classes (a language fact or a coverage run: a measurement, not a judgement; by:
  auto), agent acceptance (agent:review over an engine-cut packet anchored to an assertion line the engine
  checked, agent:author inside the task''s own diff - a fresh stamp whose adopted.yaml row carries by:
  agent:<agent-string>, the run id, the rationale and the packet digest, all displayed by stale, explain,
  check and readiness, counted as AGENT_ADOPTED, calibrated by REVIEW_AGREEMENT and --calibrate with verdict
  adoption stopping below accept_min) and the completion.mode auto flip (the engine''s, bounded by the
  required cadence full run, reversed by the automatic demotion, recorded in costs/policy.yaml rather
  than config.yaml). What no autonomous path may do: confirm a STALE row, reject a seed, change a kind,
  or make the completion gate run less without a scheduled full run behind it; agent_review.enabled: false
  restores the human-only adoption exactly. The residual risk moved from reviewer fatigue on a thousand
  seeds to a wrong verdict stamping an over-claiming edge, or a policy flip letting a miss survive until
  the next cadence run - both visible in provenance and the ledger result= field, both bounded by knobs
  config.yaml exposes (agent_review.confidence, full_run_every, mode: full).'
tradeoff_axis_declaration_burden: 'Disadvantage: axes are a third authoring surface, and a project that
  declares them wrongly gets confidently wrong selection. Concretely: thinking_app must declare ten matrix
  values with three facets, four locale source-glob sets, one values/** rule, one runner script (list/describe/run/children
  over its existing routing) and one testmap:axis line per non-capturing coordinate test. Mitigated by
  making membership declarative and checkable - DEAD_AXIS_SOURCE fails a source glob that matches nothing,
  UNKNOWN_VARIANT a listed variant outside the axis, UNCOVERED_VALUE a declared value no runner lists,
  and axes --explain <path> answers why one file landed where it did before anything is trusted; and by
  an undeclared source reaching every variant, so an incomplete axis over-selects rather than under-selects.'
tradeoff_axis_projection_coarseness: 'Disadvantage: the default axis join is file-level - a one-key edit
  to values-ru/strings.xml selects every enrolled screen on both ru matrices (about 65 variants) rather
  than the screens naming that key; sound but 2/10 of the matrices rather than 1/50 of the screens; mitigated
  by the opt-in android-res symbol scanner (keys changed -> referencing Kotlin files -> member units),
  by select --format tokens feeding the project''s own render loop so the over-selection costs a preview
  rather than a gate, and by the group-costed budget.'
tradeoff_batch_misreport_risk: 'Risk: a batch runner that misreports per-unit results corrupts attribution,
  cost and evidence (a false pass could manufacture an EVIDENCED row); the JUnit classname/name to variant-id
  inversion and the zero-match trap at method granularity (a Gradle --tests filter matching nothing exits
  0 with zero tests) are two places to misreport; mitigated by units_expected/units_reported reconciliation
  per id, a row inverting to no registered id and units_reported == 0 with units_expected > 0 both being
  mechanism failures, and no line from an invocation with a cause ever anchoring.'
tradeoff_broad_scope_coarseness: 'Disadvantage: a test scoped to a large area is selected for any change
  inside it; mitigated by ranking last at its distance, running only after a green unit wave, being cut
  first by the suite budget with the cut printed as DEFERRED, and the cost visible in schedule.'
tradeoff_bulk_confirmation_granularity: 'Risk: a person''s adoption per evidence class (398 static edges
  in one answer) trades review depth for feasibility - per-file review of 720 files is not something anyone
  does, and a class-level yes accepts every member; the review pass restores per-pair depth at feasibility''s
  price - every pair is read, but by an agent, with a rationale and an assertion line on the row, and
  a class-level human yes over pre-filled verdicts is still one answer; mitigated by the three-sample
  display, `review a sample` drawing ten random members with their signals and the agent''s verdict and
  rationale beside each, --accept-min raising the bar, --scope <glob> onboarding one area per task, the
  adopted.yaml provenance with by: so nothing pretends to be a per-pair human review and readiness reports
  ADOPTED_UNREVIEWED and AGENT_ADOPTED, the per-row path (onboard adopt <test> <source>, --batch, the
  in-gate step) for anyone who wants depth, the attended choice per batch between confirm-each / trust-batch,
  autonomous adoption limited to rule, measurement and reading origins, and kind reclassifications being
  confirmed individually by a person because a wrong kind changes staleness semantics rather than selection
  breadth.'
tradeoff_cell_table_size: 'Disadvantage, inverted: instead of about 2,500 generated cell rows that churn
  whenever a screen or matrix is added, _scanned.yaml carries 49 member rows with a variants: list of
  at most ten values; the price is that scan and check exec each runner''s list (thinking_app: a bash
  script reading two manifests, milliseconds) and that a matrix added to the manifests is invisible to
  select until the next scan --apply - which check reports as UNKNOWN_VARIANT/UNCOVERED_VALUE drift the
  same day. Enumerating at every select was rejected because it would put a build-adjacent exec on the
  hot path of every gate.'
tradeoff_compiled_component_cost: 'Disadvantage: the framework gains a compiled component - contributors
  touching the engine need Go, a release fails if go test fails, install gains a fetch and checksum step;
  mitigated by a single build.sh matrix, ait engine build, and the engine being optional until a testmap
  gate is enabled.'
tradeoff_computed_vs_prose: 'Advantage: selection is computed, explained and scored rather than remembered;
  blast radius becomes data instead of prose - thinking_app''s ''a localized screen change may use preview,
  a shared component must run the full gate'' rule becomes an axis join, an import-scanner fan-out and
  an ESCALATE: line, each printed with the path that caused it; and so is the run surface - `ait test
  --howto` prints the runners, resources, full gate, gates, axes, policy and doc pointers from the registry
  and the ledger, and the generic Running Tests section is identical in every project, so an agent never
  learns ''how do I run tests here'' from a 200-line CLAUDE.md testing section again (thinking_app''s
  is 200 lines today); the project''s judgement calls become config.yaml notes: lines and docs: pointers
  the brief prints, still prose, but reached through one verb rather than found.'
tradeoff_dispatcher_verb_added: 'Disadvantage: `ait test` is a new top-level dispatcher verb beside `ait
  testmap`, two surfaces for one engine; justified by the extension-points rule (a human plausibly types
  `ait test`, and the seed instruction needs one memorable verb), kept thin (mode / task / intake / policy
  / fallback / advisory resolution only, everything else delegated to the shim and the engine `test` composite),
  and `ait testmap` stays the maintainer surface for annotate / scan / check / stale / axes / onboard;
  removing a verb later is a breaking change, so --howto documents `ait test` as the stable one.'
tradeoff_engine_absent_on_host: 'Risk: an unsigned macOS binary or a blocked download leaves a host without
  an engine; mitigated by ENGINE_MISSING naming the $AITASKS_HOME path and repair verb, --engine-from-source
  and --local-engine fallbacks, and the testmap gates exiting 3 (error), never skip, when the engine is
  absent; two deliberate, printed exceptions: `ait test --advisory` reports VERDICT:skip REASON:testmap_absent
  so the pre-review Step-7 run in task-workflow, pickrem and pickweb - which has no ait setup at all -
  continues exactly as today, because an advisory run must never block a task the way a declared gate
  legitimately does; and a project may set completion.engine_absent: fallback_command so the Web lane''s
  tests_pass runs the pre-onboarding suite command with MODE:fallback visible, the default staying error;
  neither skip is silent.'
tradeoff_engine_speed_enables_per_task_use: 'Advantage: sub-second select/check/stale on a 720-test repo,
  and sub-250 ms select over 297 variants with axis expansion, makes selection overhead negligible against
  the shortest test and lets check run at every commit step; the facet join is one glob match per changed
  file per facet and one set test per member, select never execs a runner, and a bash+Python engine would
  spend seconds in start-up and YAML parsing first.'
tradeoff_engine_version_skew: 'Disadvantage: one user with several projects on different framework versions
  keeps several ~10 MB binaries under $AITASKS_HOME/engine/; mitigated by exact-version resolution in
  the shim (never newest-wins) and ait engine prune against the project registry, never a count-based
  prune.'
tradeoff_evidence_requires_reachable_history: 'Risk: the evidence join can only suppress a STALE row when
  the anchoring commit is reachable, so a depth-1 CI clone or a fresh shallow worktree sees the precise
  digest verdict with no self-healing; the safe direction, and the reason stale --strict fails only on
  STALE_PATH (structural rot is check''s); a repo-wide stale --all --strict job should run on a full clone
  or accept STALE noise.'
tradeoff_fail_closed_bootstrap_cost: 'Disadvantage: fail-closed enforcement means bootstrapping each repo
  requires a waiver pass before testmap_check can be enabled, a first green full run before require_stamp
  and --strict, a green runner list before structural rules can fail, and min_scored_full_runs plus min_full_runs_since_map_change
  before the completion policy may reach the selection; narrowed by making the bootstrap order one aitask
  per level that the onboarding skill creates and runs - detect and seed are read-only until --write /
  --apply, level 0 writes only registry files and seeds, the seeder replaces most of the hand waiver pass
  (measured on aitasks: 88% of bash tests and 80% of Python tests carry a literal invocation or import
  that seeds at least one edge), the level-0 task''s own tests_pass gate IS the first full run that anchors
  every unit, bootstrap_until is set to level-0 day + 90 by detect --write, adoption is incremental by
  class, by area, by review batch, in-gate or at authoring, and readiness prints LEVEL / NEXT so the remaining
  steps are a list rather than a procedure someone must remember; one cost the baseline carried is removed
  - a repo is no longer level 0 ''until a human adopts level 1'', because a headless profile adopts by
  rule, measurement and reading in the same task that ran level 0, finish --auto closes enforcement with
  the parked rows still selecting, and auto flips the policy when the scored history allows; what remains
  is real: kinds and axes are human, parked and REVIEW_HUMAN pairs wait for a person, the calibration
  prior runs unmeasured where no ground truth exists, the review loop is a long session paid in tokens,
  and the required full runs must still happen.'
tradeoff_fallback_runs_more: 'Disadvantage: when the engine binary is absent in completion mode and the
  project chose engine_absent: fallback_command (the Claude Code Web lane, where ait setup never ran),
  `ait test --gate` runs the whole pre-onboarding suite command - never less than before onboarding, but
  never selective either, and with no per-unit results, no evidence anchors and no scoring; mitigated
  by the default being error (the gate reads error, not pass), by ENGINE_MISSING naming the path and repair
  verb, and by the fallback being visible as MODE:fallback in the result.'
tradeoff_flaky_pass_anchors: 'Risk: a flaky pass anchors evidence as surely as a real one; mitigated by
  per-run status in the ledger so costs exposes a flake rate per id, and an id above flake_threshold is
  excluded from the evidence join.'
tradeoff_generated_brief_limits: 'Disadvantage: a brief computed from the registry cannot say what a project''s
  people know about when a narrow run is acceptable, which device is the real test device, or why RTL
  is the design gate - thinking_app''s testing prose carries exactly that; mitigated by config.yaml docs:
  (paths the brief prints, so the prose is one hop away and named) and notes: (<=10 verbatim lines for
  the rules that must not be one hop away), and by the seeded instructions telling agents to read `ait
  test --howto` before touching a test tool; the limit that stays is that notes: is prose an agent may
  still misread, which the gates and the full completion policy backstop.'
tradeoff_home_migration_window: 'Risk: when run, the migration has a sub-millisecond window between rmdir
  ~/.aitask and ln -s during which a concurrent process that hardcodes the legacy path (rather than using
  the resolver) sees ENOENT; narrowed by the flock, by symlinking immediately after the rmdir, and by
  refusing while another ait holds the home lock - not eliminated. Measured surface: 8 framework code
  files with 35 references (21 in aitask_setup.sh), 20 test files, 18 doc files, the venv''s absolute
  shebangs and two symlink trees - none rewritten by the migration, all resolving through the symlink.
  Its refusal cases are the ones a designer does not see on their own host: an earlier known-entry set
  lacked pypy_venv, which this host carries. Both are why the verb is explicit in this release and the
  default flip waits for the real-install test.'
tradeoff_intersection_can_underselect: 'Risk: an axis-source hit is sharper than a file edge - it selects
  only the variants carrying the facet value - and is therefore capable of missing a real coupling that
  a plain covers edge (every variant) would have caught, e.g. a font family assigned to the wrong locale''s
  glob. Narrowed structurally: under-selection needs an explicit, reviewable wrong glob, never an omission,
  because a file matching no axis source reaches every variant; score on a full run raises missing-axis-source;
  observed sources may only widen; --axis and --format tokens with preview are the reviewer''s escape;
  and every variant row prints the facet value that placed it, so what a sharp selection excluded is visible
  in the prediction record.'
tradeoff_member_annotation_drift: 'Risk: a member unit''s annotation lives in a block keyed by name (testmap:unit
  Welcome) and the runner''s list keys the same member by another artifact (the golden manifest''s Welcome_<matrix>.png);
  a rename on one side orphans the other; mitigated by check reporting a listed member with no block (UNANNOTATED_MEMBER)
  and a block with no listed member (DEAD_MEMBER), both fail-closed, by scan --apply refusing rather than
  guessing, and by thinking_app''s own manifest/@Test drift loop failing the rename on its side.'
tradeoff_noarch_packages_preserved: 'Advantage: Homebrew, AUR, .deb, .rpm and the tarball ship nothing
  compiled; the per-arch concern is contained in one release job and one setup function.'
tradeoff_onboarding_partial_coverage: 'Disadvantage: onboarding cannot map what no origin reaches - thinking_app''s
  same-package tests (imports resolve for 139 of 339 files), fixture-driven tests, and any source with
  no static, convention, plan, prose, co-change or coverage relation - so a freshly onboarded repo has
  UNMAPPED_SOURCE rows and area-only coverage for a share of its tree; mitigated by the waivers phase
  (rules for hot directories, expiring waivers for the rest) so check can be enabled non-strict, by opt-in
  per-unit coverage where the tool supports it (now auto-adoptable, so turning it on maps and claims in
  one step), by the authoring agent stamping every coupling a task creates from now on through the pre-review
  procedure''s author branch - the same-package gap on thinking_app closes incrementally through agent:author
  as tasks touch pairs, not through onboarding - and by the full gate staying the completion policy until
  admissible; the honest reading of `onboard status` after one headless session is ''selecting on most
  tests, claiming on the measured and the verified, the rest parked'', and the design treats that as a
  state, not a failure - the backlog no origin reaches is still a person''s or the next task''s.'
tradeoff_one_gate_not_two: 'Advantage: one completion test gate whose behaviour is a committed policy,
  instead of tests_pass (full) beside a second selection-only gate - an agent learns one command and one
  gate, a project keeps its existing tests_pass declaration and timeout key, the legacy no-gates Step-9
  path and aitask-qa reach the selective lane through the same test_command, and the policy flip is one
  line written after readiness by a person under selected or by the engine under auto rather than a second
  gate to declare, so a headless repository reaches the selective lane by itself. Disadvantage: the gate''s
  meaning now depends on config.yaml and, under auto, on the run''s readiness and cadence state, so a
  reader of a ledger `tests_pass: pass` must look at the run''s MODE / POLICY line to know whether the
  whole suite ran, and under auto not even a person decided that it should not; mitigated by the verifier
  result= field carrying MODE:<full|selected>|<n units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>],
  by the POLICY:auto|... line printed on every completion run, by the gate- run-id prefix in the cost
  ledger, by POLICY_FLIPPED and POLICY_DEMOTED being loud, by approved_by naming engine:readiness@<run>
  in a file of its own (costs/policy.yaml) so no one mistakes it for a person''s approval, and by readiness
  printing what --gate would run now and when the next cadence full run falls.'
tradeoff_real_scheduler: 'Advantage: goroutines plus flock(2) give correct cross-worktree contention and
  a critical-path report; the shell suite and the pytest lane get the enforced do-not-overlap that is
  only a comment today; a variant batch is one Gradle invocation holding one heavy-run slot, ordered after
  cheaper invocations in its wave; thinking_app''s heavy-run lock and emulator allocator become declared
  resources the schedule report can reason about.'
tradeoff_registry_directory_complexity: 'Disadvantage: a merged registry directory needs more CLI logic
  than a single file would - eight tables, two generated files, one ledger, an id grammar with member
  and variant fragments and an artifact column in list; kept to one directory with one merge rule in one
  Go package with golden tests, no second plugin directory or generated cell table, and the axis table
  is empty for every project that declares none.'
tradeoff_resource_declaration_completeness: 'Risk: declared resources are only as complete as the declarations;
  an undeclared interference is invisible until a full run or a probe finds it; serial-by-default at bootstrap
  means declarations are reviewed in the schedule report before concurrency is trusted.'
tradeoff_seed_noise: 'Risk: heuristic seeds are wrong in both directions - a convention pairs a test with
  a homonym, an import names a helper the test only uses, co-change ties every file of a wide task to
  every test of that task (thinking_app: 7.2 main files per co-changing commit), and a wrong seed selects
  tests that cannot fail for the change. Mitigated by seeds selecting (wasted minutes) and never claiming
  (no false EVIDENCED), by the confidence table ordering review rather than gating it, by the 0.60 co-change
  cap and min_cochange 2 across distinct tasks so corroboration cannot reach the class threshold alone,
  by imports restricted to direct main-root imports (same-package facts excluded), by helpers separated
  before scoring, by the evidence printed beside every seed in its packet, by rejection memory in onboard.yaml,
  and by the suite budget and --format tokens for a repo where over-selection is expensive; the reviewer
  fatigue that remained on a 1,000-seed queue is now the review pass''s job - a noisy seed gets a drives
  or unsure verdict and is parked, still selecting, and a person sees REVIEW_PARKED:<n> instead of a thousand
  rows; what remains is that parked rows still over-select until a person rejects them, and class adoption
  with samples, per-area batches and the in-gate incremental path spread that over time.'
tradeoff_seed_precision: 'Risk: an adopted covers edge is a machine claim wearing a human annotation''s
  clothes - the static closure says the test executes the script, not that it verifies it, and under a
  class-level yes a test that drives three scripts to set up one adopts edges to all three. This is the
  gap the review pass closes: the reader marks the two set-up scripts drives (parked, still selecting)
  and the third verifies, and the intake adopts one edge, not three; with agent adoption an adopted edge
  is a READING''s claim, and the reading answers exactly the executes-vs-verifies question the closure
  could not. Narrowed further: adopted edges are recorded in registry/adopted.yaml with by:, displayed
  as adopted(... by <who>) in stale and explain until a human re-stamps them, readiness reports ADOPTED_UNREVIEWED
  and AGENT_ADOPTED, the over-claim direction only over-selects (a setup script''s change runs the test
  needlessly), the class threshold 0.85 keeps heuristic-only edges out of a person''s class adoption,
  the packet flags assertion lines so the verdict is drawn from evidence and stores its anchor, digest
  and rationale, `unsure` is an allowed answer so the agent is never forced to guess (two -> REVIEW_HUMAN),
  calibration against coverage or human rows measures the origin before it is trusted, the skill shows
  three samples per evidence class before a person adopts a class, and a project that wants no machine
  claims at all sets agent_review.enabled: false or stops at the seeded state, which selects without claiming;
  a wrong verifies verdict reproduces the original over-claim for one pair with agent:review in its provenance;
  a coupling the closure does not contain is caught by the author''s annotation when the task that creates
  it runs the pre-review procedure, and otherwise only by a full run''s score.'
tradeoff_setup_network_fetch: 'Disadvantage: ait setup gains the framework''s first self-downloaded release
  asset; mitigated by reusing the CDN URL family install.sh already uses, SHA256SUMS verification, the
  .sha256 sidecar, --no-testmap / AIT_TESTMAP_FETCH=0, the shim never fetching on its own, and setup never
  depending on the binary for anything else.'
tradeoff_split_home_rejected: 'Disadvantage of the permanent-split alternative: installing only the engine
  at ~/.aitasks/engine/ and leaving venv, pypy_venv, python, bin and uv at ~/.aitask/ satisfies the naming
  mandate literally with zero migration risk, but leaves a user with two dot-directories one character
  apart holding halves of one install, which ait setup --repair, ait engine prune, backup advice and every
  doc page would have to explain forever. Chosen: the split as the transition, not the end state - the
  migration is designed, shipped as an explicit verb and testable now, with the symlink making it reversible
  (rm ~/.aitask && mv ~/.aitasks ~/.aitask), and becomes ait setup''s default in a named follow-up.'
tradeoff_stamp_churn: 'Disadvantage: confirming stamps rewrites test files - a source named by 72 tests
  could yield a 72-file diff (EVIDENCED needs no rewrite, --confirm-source is one commit, member blocks
  keep a screen''s stamps in one file, variants carry no stamp, KIND_MISMATCH nudges fan-out toward a
  scope or axis); onboarding adds the largest rewrite of all - adopting level 1 on aitasks touches about
  720 test files with one to eight comment lines each - mitigated by seeds selecting without any rewrite,
  by adoption being batched per evidence class or per area (--scope <glob>) into `chore: Onboard testmap
  - adopt <class|area> (t<id>)` commits that add comment lines only (git blame -w and every runner ignore
  them), by ADOPT_REFUSED:dirty-foreign refusing a file dirty outside the task''s change surface so adoption
  never mixes with concurrent work, by the onboarding task being an ordinary reviewed (t<id>) commit rather
  than a hidden write, and by the in-gate path that adopts a file''s seeds only when a task already has
  it open.'
tradeoff_static_scanner_overselection: 'Disadvantage: static scanners overselect on hot files and cannot
  see runtime coupling; a shared component (thinking_app''s ui/components/*) fans out to most screens
  on every matrix, which is the correct answer and close to a full run, and ScreenFixtures.kt reaches
  every member because the change surface is file-level; kind ranking, the suite budget and --budget-s
  trim scoped rows first, the android-res symbol scanner narrows a catalog edit to the screens naming
  the changed keys, a project scanner plugin can narrow a hot resource file, and hunk-level attribution
  inside a member file is the later narrowing tool.'
tradeoff_strict_version_handshake: 'Risk: the binary must match .aitask-scripts/VERSION exactly, so an
  ait upgrade on a host that cannot fetch leaves ait testmap refusing to run until a matching binary is
  supplied; intended fail-closed behaviour, and the error names the fix (ait setup, AIT_TESTMAP_BIN, ait
  engine build) and the $AITASKS_HOME path it looked in.'
tradeoff_two_edge_states_during_adoption: 'Disadvantage: until both queues are empty a repo has FOUR provenances
  of edge a reader must keep apart - seeded (selecting only, parked or not), adopted by human (stamped,
  class-accepted with a provenance row), adopted by agent or auto (stamped, a reading''s or a rule''s
  claim with by:, run, rationale and packet digest) and reviewed (stamped, accepted per pair by a person);
  mitigated by the seeded origin or adopted(... by <who>) printed on every row, the human/agent/auto split
  on SEEDED:/ADOPTED: in check, stale --all, readiness and --howto, `onboard status` as the one place
  the ratios live, and the rule that no seed and no agent verdict ever changes a freshness verdict on
  another edge; a verdict adds a mark on a seeded row (verifies / parked) and a by field on an adopted
  row, not a fifth state; the cost the baseline recorded - --strict waiting on adoption forever in a repo
  no one reviews - is removed for headless repositories and replaced by the bounded exposure window recorded
  under tradeoff_auto_policy_exposure_window, and ''never adopts'' is now a choice (agent_review.enabled:
  false) rather than the default outcome of nobody having time.'
tradeoff_two_toolchains: 'Disadvantage: bash and Go in one framework; mitigated by the boundary rule (parse/walk/match/digest/schedule
  in Go; gate ledger, task file and shell environment in bash; builtins exec configured commands and never
  source shell state), the engine-check.yml job, and Go source confined to engine/ and excluded from the
  tarball so target projects never need Go.'
tradeoff_two_user_roots: 'Disadvantage: until ait engine home --migrate is run, a host carries ~/.aitask/
  (venv, pypy_venv, python, bin, uv) and ~/.aitasks/ (engine) side by side, and a user who deletes one
  to reset the framework removes half of it; mitigated by one variable (AITASKS_HOME) with one library
  owner, ait setup printing both roots and the HOME_LEGACY: hint, ENGINE_MISSING naming the exact path,
  ait engine home reporting the state, a test that fails if any script of this feature names ~/.aitask/,
  and the migration verb existing now rather than as an unowned ''later change''.'
tradeoff_verify_build_wired_suites: 'Disadvantage: a project that wired its test suite as verify_build
  (thinking_backend''s run_script_tests.sh, which also enforces a shellcheck baseline) cannot be onboarded
  mechanically - moving the command to a suite runner would drop the lint half from build_verified, leaving
  it would run the suite twice at completion; detect therefore reports SUITE_CANDIDATE:verify_build and
  the skill asks (keep as verify_build and add test_command: ./ait test over the detected bash-file and
  pytest units; or split the script), defaulting to keep, and records the answer in the onboarding plan;
  headless profiles keep.'
tradeoff_whole_run_filter_soundness: 'Risk: where a runner''s filter restricts a whole test run (Gradle
  --tests on thinking_app''s single testDebugUnitTest task), every class not selected is silently not
  run, so a narrow selection is only as sound as the test-side closure, the reads globs and the opaque
  contract; mitigated by list enumerating the whole universe so an unlisted class fails check, the test-dep
  closure over abstract bases and helpers, testmap:reads on tree-scanning helpers (71 SourceFence importers
  stay selected on any Kotlin change), ESCALATE on opaque files, red-proof fixtures per branch, readiness
  gating the policy flip on scored history, and the project keeping its full suite as the completion gate
  until readiness is met.'
tradeoff_workflow_surface_growth: 'Disadvantage: the seam adds one task-workflow procedure file, one profile
  key, one dispatcher verb, one skill-invoked script with a second mode (five allowlist touchpoints -
  .claude/settings.local.json, .codex/rules/default.rules and the three seeds - pinned by tests/test_touchpoint_count_contract.sh),
  a Step-7 render change across every profile x agent golden, one build-verification branch, two aitask-qa
  procedure edits, a seed-instructions edit and a profile-aware skill with two wrapper surfaces; mitigated
  by all of it degrading to a printed skip where the engine is absent (no environment conditionals), by
  the advisory mode reusing the exact VERDICT:/REASON: contract and capture form the build-verification
  path already teaches, by there being one script rather than two, and by aitask_skill_verify.sh plus
  the goldens catching a drifted render before commit.'
tradeoff_agent_judgement_unmeasured: 'Risk: agent:review''s 0.90 is a provisional number - no measurement
  of an agent''s verifies precision exists on day one, and a confident wrong verdict stamps a claim in
  the map with a rationale that reads well; narrowed by the assertion-line anchor the engine checks (a
  verdict must point at a real line naming the source, VERDICT_INVALID otherwise), by the verdict attaching
  only to an existing seed (the agent corroborates and never invents a pair), by REVIEW_AGREEMENT against
  every human per-row adopt or reject and `onboard review --calibrate` against coverage facts, both writing
  agent_review.measured_confidence and stopping verdict adoption below accept_min 0.85 over calibration_min
  30 pairs, by by: agent:<s> in every provenance row and adopted(...+agent:review) on every stale / explain
  line, by a wrong verdict over-claiming (over-selects, then is confirmed or retargeted at testmap_fresh
  like any adopted edge) and never under-selecting - drives and unsure park rather than reject - and by
  the per-project agent_review.confidence knob; what remains is the first thirty labelled pairs, during
  which the number is trust, and a purely headless project with no coverage that never labels a pair (CALIBRATION:none
  and REVIEW_AGREEMENT:none printed, the provisional number standing).'
tradeoff_cadence_window_misses: 'Disadvantage: under completion.mode auto a coupling no edge, seed, rule,
  verdict or author line knows lets a task land with an affected test unrun until the next cadence full
  run; the miss is then scored against every prediction in the window and attributed by change surface
  and history rather than pinned to the task that happened to trigger the full run; narrowed by the three
  cadence triggers being required (READINESS:cadence_declared), by selection_ratio_above running full
  whenever the saving is small, by one miss over max_false_negatives demoting to full, by min_full_runs_since_map_change
  holding the flip until a bulk adoption has been scored, by --howto and readiness printing the window
  (next_full_in:<n>, CADENCE:), and by mode: full remaining the one-line opt-out with the human --policy
  selected flip unchanged; the cost is real and per-project - config.yaml exposes it rather than the design
  hiding it.'
tradeoff_review_token_cost: 'Disadvantage: the review pass is paid in agent tokens, not engine time -
  ~2 k input tokens per pair, ~1.5 M for aitasks'' ~720 heuristic pairs in 36 packets, more for thinking_app''s
  Kotlin excerpts, and a re-read whenever a test''s bytes change; mitigated by the reviews[] memo (a pair
  is read once per test blob per reader), batching by test file so one excerpt serves several pairs, the
  packet excluding source bodies and capping test excerpts at packet_lines, --class limiting a pass to
  the origins worth reading (static:* first, convention only when nothing else corroborates), rule and
  measurement classes needing no reading at all, max_pairs_per_run bounding one run with the phase resuming,
  and the in-gate path reviewing only touched files; no gate or verifier ever pays it.'
tradeoff_loop_closes_without_a_person: 'Advantage: the value the mandate names is realised - seeding,
  adoption, the policy flip and the safety net are each performed by a machine or an agent under a committed
  policy, so a repository onboarded by a headless profile reaches a per-change-set completion gate within
  min_scored_full_runs + min_full_runs_since_map_change tasks of level 0 with nobody typing anything,
  and what remains human is a printed list (REVIEW_PARKED, REVIEW_HUMAN, KIND_PROPOSALS, axes) rather
  than an assumed step. Disadvantage: in such a repository the map''s provenance is mostly by: agent,
  and a reader who wants human-reviewed claims must look for the human split in onboard status - never
  hidden, but no longer the default state; and disabling the loop (agent_review.enabled: false, completion.mode:
  full) is now a deliberate act a project must take, where the baseline made human acceptance the only
  path.'
tradeoff_wrong_positive_invisible_to_score: 'Risk: a wrong `verifies` verdict is never detected by the
  feedback loop, because a claimed edge that should not exist can only over-select and score measures
  under-selection; its cost - needless runs of that test when the driven source changes, STALE nags on
  a pair the evidence join heals when the test passes - is bounded but accumulates silently in the AGENT_ADOPTED
  share. Mitigated by the packet flagging assertion lines so the verdict is drawn from evidence rather
  than from the file name, by the assertion-line anchor the engine checks, by `unsure` and REVIEW_HUMAN
  so the agent is never forced to guess, by calibration against coverage facts or human rows before the
  origin is trusted and agent_review.measured_confidence lowering its weight where calibration is poor,
  by the stored packet digest and rationale letting a later reader see what the agent saw, by the human
  re-stamp path deleting the provenance row, and by onboard status reporting the agent share so a maintainer
  can sample it. What remains: a repository with neither coverage nor human-reviewed rows has no calibration
  ground truth, runs on the 0.90 prior, and readiness states CALIBRATION:none rather than pretending to
  a measurement.'
tradeoff_auto_policy_exposure_window: 'Risk: under completion.mode: auto a task may land while an affected
  test never ran, until the next cadence full run - the residual risk that replaces reviewer fatigue.
  Its size is a project choice: full_run_every.tasks (default 5) bounds it in tasks, days (7) in time,
  selection_ratio_above (0.60) makes the cheap-to-run-full case run full and score for free; every completion
  run prints next_full_in:<n>; the demotion still fires on the first scored miss; min_full_runs_since_map_change
  holds the flip after a bulk adoption; and a project that cannot accept any window keeps full or a human-flipped
  selected. What remains: up to tasks - 1 tasks may merge on a wrong selection before the miss is scored,
  and their dependents may have built on them - blocks_dependents on tests_pass does not help because
  the gate passed; the honest mitigation is the number itself, chosen with the measured saving in view
  and printed on every run.'
tradeoff_periodic_full_run_cost: 'Disadvantage: the cadence spends full runs a human flip would not -
  one in every full_run_every.tasks completion runs plus the days and ratio triggers. On aitasks (p95
  ~400 s full, typical selection ~40 s) tasks: 5 keeps about 80% of the saving; on thinking_app (1,180
  s full) the same cadence keeps about 75% and the project may raise tasks once its calibration and agreement
  counters have been steady for a while. Mitigated by the ratio trigger (a selection that would cost >=
  60% of full runs full and resets the counter for free), by every full run doing double duty (evidence
  anchors, cost fold, score), by the cadence living in config.yaml beside the policy so it is a declaration
  rather than a surprise, and by readiness printing the cadence with the measured saving.'
tradeoff_agent_review_token_cost: 'Disadvantage: where the review tokens are paid matters as much as how
  many - the in-gate and authoring sites read inside a session that already has the files open (no extra
  launch, the session''s ordinary rate); a bulk pass through `ait skillrun testmap-review` is an interactive
  launch at the same rate; only `ait codeagent testmap-review --headless` and a crew whose launch mode
  is headless pay Claude Code''s print-mode rate, and both are explicit flags a person sets rather than
  a default of any path; the engine, the gates and the verifiers launch nothing. Mitigated by the packet
  excluding source bodies and capping test excerpts at packet_lines, by max_pairs_per_run bounding one
  run and the review phase resuming, and by rule and measurement classes adopting without any reading.
  What remains is that a parallel crew pass is the fastest way through a large queue and the most expensive
  per token, which the `ait crew runner` line a person must start makes a visible choice.'
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

### What the feature is

A framework feature, generic across `aitasks`, `thinking_app`,
`thinking_backend`, `aitasks_go` and `aitasks_mobile`, that keeps a **test
map** — a relation between source files and test units — and uses it in six
ways:

1. **Select.** A task's attributed change set becomes a ranked list of tests,
   each line carrying the reason it was selected.
2. **Run.** Selected tests execute through project-defined runners under one
   standard contract, scheduled against declared host resources.
3. **Track.** Every run records cost per unit and per variant, keyed by host
   class, and anchors evidence that the map's claims held.
4. **Learn.** Every full run scores the map's predictions; misses feed a
   review queue rather than silently rotting the map.
5. **Enforce.** Gates keep the map fresh and consistent and make the
   completion test run a committed policy rather than a habit.
6. **Teach.** One verb, `ait test`, and one generic instructions section are
   how any agent learns to run tests in any onboarded project; one skill
   brings a repository's existing test tree onto the map in graded levels.

The engine is a static Go binary installed per user under
`$AITASKS_HOME/engine/v<VERSION>/`; the map lives in a committed `aitestmap/`
directory at the repository root; the adoption state of machine-proposed
edges is a three-file ledger (`seeded.yaml` → `adopted.yaml` → reviewed
stamps) whose transitions are driven by **readers of the test body**: an
agent reads an engine-cut packet for each seeded pair and answers
*verifies*, *drives* or *unsure* (`agent:review`); rule and measurement
origins adopt on their own; the agent that wrote a change stamps its own
pairs (`agent:author`); a person is kept only where a wrong answer changes
staleness semantics (kinds) or declares the product space (axes).
Onboarding is a resumable skill that runs one aitask per level and reaches
level 1 in attended and headless profiles alike; the completion policy may
flip itself (`completion.mode: auto`) behind a cadence of full runs that
keeps scoring alive; the run surface is `ait test` in three modes
(interactive, completion, advisory) over an engine `test` composite, with a
bash front that still answers correctly when no registry or no engine
exists. The engine never launches a code agent; every agent launch in this
feature goes through a framework wrapper (`ait skillrun`, `ait codeagent`,
`ait crew runner`), and headless print mode is an explicit opt-in on each.

### How this differs from the baseline

The engine, the map, selection, scheduling, cost, scoring, the run surface
and the one completion gate are unchanged. What changes is **who closes the
loop**. The baseline already selects adaptively the moment level 0 runs:
seeded edges select at distance 1 in every mode, and every full run scores
the last prediction. What it held behind a person were two things — whether
the map's claims are *enforced* (adoption, which needs a stamp) and whether
the completion gate *shrinks* from the full suite to the selection (the
policy flip). Until both happened, `tests_pass` ran everything and the
feature's value leaked. The baseline's stated reason for the person was the
gap between *executes* and *verifies*: static closure proves a test runs a
script, not that it checks it, and that is a semantic judgement. This
design keeps the judgement and changes who may make it: **a reader of the
test body**, which a person or an agent can be. Five things follow:

1. **Two reading origins.** `agent:review` (0.90) — a verdict from an agent
   that read a bounded, digest-stamped packet of the test's assertion lines
   and the source's declared symbols, anchored to the assertion line that
   checks the source, which the engine verifies exists — and `agent:author`
   (0.90) — the agent that just wrote the test or the source naming the pair
   itself. Under the existing noisy-OR a static edge plus a reading is 0.99;
   a reading alone clears the class threshold. Every reading carries who read
   (an agent-string), which run, what packet (a digest) and a one-line
   rationale, so an adopted row never pretends to be a human review.
2. **The autonomous floor is "rule, measurement or reading", not
   "confidence 1.0".** `static:package` is a rule, `coverage` is a
   measurement, `agent:*` is a reading; a headless profile may adopt any
   class whose every member carries at least one of them. Heuristic-only
   classes (`static:invocation` alone, `static:import` alone, `convention`,
   `cochange`, `plan`, `prose`, `observed`) still need a reading on top. This
   makes level 1 headless on all five target repositories.
3. **An agent verdict never removes selection.** A *verifies* verdict makes
   a seed adoptable and adopts it; a *drives* or *unsure* verdict **parks**
   the seed — it keeps selecting at distance 1, leaves the adoptable set and
   is listed for a person — because a test that only drives a source is
   still coupled to it (a breaking change to the driven script breaks the
   test's setup) and must keep running for a change to it; what the verdict
   decides is only whether the pair may *claim*. Only a person's `onboard
   reject` removes a seed.
4. **A self-approving policy behind a scheduled full run.**
   `completion.mode: auto` lets `ait test --gate` flip to the selection when
   `readiness` is `ADMISSIBLE`, recording `approved_by: engine:readiness@<run>`
   in the engine's own ledger (`costs/policy.yaml`, never in the committed
   declaration `config.yaml`), and demote loudly as before. The person is
   replaced by a cadence — `full_run_every: {tasks, selection_ratio_above,
   days}` — so scoring never stops and a miss is caught within a bounded
   number of tasks; a cadence full run scores every prediction since the
   last full run. The invariant "the policy can only fail toward running
   more" holds and is extended: a cadence full run is never skipped by a
   demotion or an empty selection.
5. **The authoring agent annotates.** The pre-review procedure's autonomous
   branch no longer only proposes: for a source and a test that are both on
   the task's own change surface, the agent writes the stamped
   `testmap:covers` line through `annotate --author`, adopted with origin
   `agent:author` and riding the `(t<id>)` commit through the Step-8 review.

Two things deliberately stay human: **kind changes** (a wrong kind silently
changes staleness semantics and no run evidence can check it; headless runs
*propose* kinds and apply none) and **axis declaration** (level 3). The
reading happens at three sites that share one verdict intake: the
`testmap_fresh` in-gate step, the pre-review Affected Tests procedure and a
bulk skill, `aitask-testmap-review`, launched interactively through `ait
skillrun testmap-review`, in print mode only under `ait codeagent
testmap-review --headless`, or in parallel as crew agents the crew runner
launches through `ait codeagent`. No engine path, gate, hook or default
skill flow launches a code agent.

The cost, stated once: the residual risk moves from reviewer fatigue on a
thousand seeds to "a coupling the map does not know, or a wrong *verifies*
verdict, lets a task land while an affected test never ran, until the next
full run". The knob for that risk is the full-run cadence, per project, in
`config.yaml`, printed by `--howto` and on every completion run.

### Reading guide

*Architecture* introduces the vocabulary, the process boundary, the registry
and the design decisions. *Data flow* walks a task, a completion run under
each policy, the onboarding levels and the policy flip. *The adoption model*
is the seed → adopted → reviewed ledger with its origin table and the
autonomous floor. *The agent review pass* is the reading mechanism in full:
packets, verdicts, the three sites, the skill and its launch surfaces.
*Onboarding* is levels × phases and the per-repository detection results.
*The run surface* is `ait test` in full: forms, resolution, output, exit
contract, `--howto` and the seeded instructions section. *The workflow seam*
is every concrete edit to task-workflow, gates and `aitask-qa`. *Components*,
*Assumptions* and *Tradeoffs* are the reference sections; *Open questions*
and *Conflict resolutions* close.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_agent_brief, component_agent_instructions, component_completion_policy, component_auto_policy, component_workflow_seam, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary, component_gates, component_adoption_ledger, component_agent_review, component_agent_review_pass, component_author_annotation] -->
## Architecture

### Concepts

**Test unit and id.** A unit is a test file, a member of a file
(`<path>#<member>`, opened by a `testmap:unit` block) or a variant of a unit
on a declared axis (`<unit>@<variant>`). Ids are what runners list and what
the cost ledger, evidence and predictions are keyed by.

**Edge.** A `testmap:covers <source>` line in a test file (or a member block)
says the unit exercises that source. A *stamped* edge carries
`@<date>/<blob10>` — the git blob digest of the source at the moment the
claim was confirmed. The digest, never the mtime or the date, is the
staleness key.

**Seeded, adopted, reviewed — and who accepted.** A machine-proposed edge
passes through up to three states. *Seeded* rows live in
`registry/seeded.yaml`, select tests and claim nothing; a seed may carry an
*agent verdict* (`verifies` / `drives` / `unsure`) from the review pass, which
changes what may adopt it and never whether it selects. *Adopted* rows are
stamped edges accepted as a whole evidence class, from an agent verdict, or
by the authoring agent for its own pairs; their `registry/adopted.yaml` row
records **`by:`** — `human:<email>`, `agent:<agent-string>` or `auto` (the
engine adopting a rule or measurement class with no reader) — beside the
origins, until a person re-stamps the pair. *Reviewed* edges are stamped
edges a named person confirmed pair by pair; they carry no provenance row.

**Rule, measurement, reading, heuristic.** The origin table is partitioned
into four classes by *what kind of fact produced the row*: a **rule**
(`static:package`: deterministic from the language), a **measurement**
(`coverage`: the test ran and the source's lines executed), a **reading**
(`agent:review`, `agent:author`: something read the test body and answered
the verify-or-drive question) and a **heuristic** (everything else). The
autonomous adoption floor is stated in these terms.

**Verdict.** The unit of an agent reading: `verifies | drives | unsure` on
one `(test, source)` pair, with a rationale, the reader's agent-string, the
run id and the digest of the packet it read; a `verifies` verdict also names
the assertion line that checks the source. Verdicts enter the engine through
one intake (`onboard adopt --agent-verdicts -`), whatever site produced them.

**Parked.** Not a fourth state but a mark on a seeded row: a `drives` or
`unsure` verdict leaves the row selecting, keeps it out of autonomous
adoption and lists it for a person (`REVIEW_PARKED`); two `unsure` verdicts
from different runs mark the pair `REVIEW_HUMAN` and drop it from every
agent packet.

**Kind and scoped row.** Unit tests are edges in the per-file graph.
Integration, e2e and device tests are *scoped rows* in
`registry/_scoped.yaml`: they declare areas, scope globs or trigger globs
instead of `covers`, join the ranked list at distance 1 as sinks, and are
never digest-stale.

**Axis and variant.** A project whose tests form a product of facets
(thinking_app: 49 screens × a matrix of locale × direction × geometry)
declares the axis in `axes.yaml`; the runner's `list` enumerates the
variants; the selector joins changed paths to facet values and selects only
the variants carrying them.

**Runner and resource.** A runner speaks `describe` / `list` / `run`; the
builtins (`bash-file`, `pytest`, `go-test`, `gradle-class`, `suite`,
`device`) cover the target repositories, and a project script may shadow one
by name. A resource (`mutex`, `semaphore`, `admission`, `allocator`) is a
declared host constraint the scheduler honours across worktrees.

**Level and phase.** A repository's *level* (0–3) is a property of its tree:
what the registry has. A *phase* is a step of the onboarding run recorded in
`aitestmap/onboard.yaml`. Levels say what exists; phases say how far a run
got.

**Mode and policy.** `ait test` runs in *interactive* mode (the developer
loop), *completion* mode (what the `tests_pass` gate executes) or *advisory*
mode (a pre-review run that can never block). The *completion policy* in
`aitestmap/config.yaml` decides whether completion runs the whole registry
or the task's selection: `full` always runs everything, `selected` runs the
selection after a person approved it, `auto` runs the selection once
`readiness` is `ADMISSIBLE` and runs the whole registry on a *cadence* — the
Nth completion since the last full run, a selection that would cost a large
fraction of the full suite anyway, or D days since the last full run.

**Cadence.** `completion.full_run_every: {tasks: N, selection_ratio_above:
R, days: D}`; any trigger fires a full completion run under `auto`, which is
what keeps scoring alive without a person scheduling anything. The cadence
state lives in `aitestmap/costs/policy.yaml` and is reset by every full run
whatever triggered it.

### The process boundary

Parse, walk, match, digest, schedule, seed, adopt, packet assembly and
verdict intake happen in Go. Reading a test body and answering
verifies-or-drives is an **agent** act, performed in a skill; the engine
never calls a model. The gate ledger, task files, profile files,
`project_config.yaml`, `gates.yaml`, agent-instructions files and the shell
environment are owned by bash scripts and skill prose. Concretely:

- The engine never writes `aitasks/`, `aiplans/`, `.aitask-data/`, a gate
  ledger, `project_config.yaml`, `gates.yaml`, a profile or `CLAUDE.md`,
  never invokes an `aitask_*.sh` script, and **never launches a code
  agent**.
- The `onboard` verbs never create a task, edit a profile or commit; the
  onboarding skill does those through `aitask_create.sh --batch`,
  `aitask_pick_own.sh`, the settings helpers and `aitask_task_commit.sh`.
  The engine reads `onboard.yaml`'s `task:` and `level:` fields and writes
  its phase rows.
- The bash front of `ait test` owns everything that must work with no
  engine: mode, task and intake resolution, the completion policy check, the
  `test_command` and `fallback_command` fallbacks, and the advisory verdict.
  Under `auto` it also commits the engine's policy ledger write.
- The reading happens in three places, all agent sessions: the
  `testmap_fresh` procedure gate (the task's touched test files), the
  pre-review Affected Tests procedure (the task's own new pairs) and the
  `aitask-testmap-review` skill (bulk, during onboarding or on demand). The
  first two read inside the session that already holds the task; the third
  is launched only through a framework wrapper — `ait skillrun
  testmap-review` (interactive), `ait codeagent testmap-review` (interactive
  by default; `--print` only under `--headless`) or, for a parallel pass, one
  crew agent per packet file that `ait crew runner` starts through `ait
  codeagent --agent-string … invoke raw` under the crew's launch mode. No
  script of this feature invokes `claude -p` or its equivalents directly.

### Process map

```
./ait test [...]                                   agent · human · tests_pass verifier (test_command) · pre-review procedure (--advisory)
 └─ .aitask-scripts/aitask_test.sh                 bash front, ~150 lines: MODE / TASK / INTAKE / POLICY / fallback / advisory
      │  no aitestmap/            → TESTMAP_ABSENT:<hint> → aitask_run_project_command.sh test_command   (advisory: VERDICT:skip REASON:registry_absent)
      │  engine absent            → interactive: ENGINE_MISSING:<path>|<repair> exit 3     (advisory: VERDICT:skip REASON:testmap_absent)
      │                             completion: per config.yaml completion.engine_absent (error | fallback_command)
      │  MODE   completion iff --gate or $AIT_GATE_TASK_ID · advisory iff --advisory · else interactive
      │  TASK   --task > $AIT_GATE_TASK_ID > aitask/<task_name> branch > single own lock (aitask_lock.sh --list-mine) > NO_TASK
      │  INTAKE aitask_change_surface.sh list <id> | --dirty (printed) | --all | <path|id>...
      │  POLICY completion: config.yaml completion.mode full|selected|auto re-checked against `readiness`;
      │         auto → costs/policy.yaml + cadence (full_run_every.tasks / selection_ratio_above / days) → full | selected, reason printed;
      │         a POLICY_WRITE: line from the engine is committed by the front under `ait: testmap policy <flip|full-run> (t<id>)`
      └─ .aitask-scripts/aitask_testmap.sh          the shim: resolves $AIT_TESTMAP_BIN > AIT_ENGINE=dev > $AITASKS_HOME/engine/v<V>/
           └─ ait-testmap test … | select | schedule | run | brief | onboard … | readiness | costs … | annotate --author
                internal/registry       six tables + seeds (registry/seeded.yaml) + adopted (registry/adopted.yaml, rows carry by: / run / rationale / packet_sha)
                internal/seed           origins static:{package,invocation,import} · coverage · agent:{review,author} · observed · convention · plan · prose · cochange; class per origin; noisy-OR
                internal/onboard        detect · inventory · seed · review (packets) · classify (--apply | --propose) · adopt (--class [--auto] | --agent-verdicts | per row) · reject · scaffold · status · finish; the onboard.yaml ledger
                internal/brief          the generated run brief (`brief`, rendered by `ait test --howto [--md]`)
                internal/selectr        graded walk + seeded edges at d1 · explain --sources · the `test` summary lines
                internal/runner         contract + subsumed_by: · fallback_command: · the `full` suite wrapper · bash-file list --invocations
                internal/annot          grammar v3 + line-targeted rewriter; adopt, --agent-verdicts and --author are callers, at the fixed per-language position
                internal/deps           scanners; direct-invocation, direct-import and package facts, anchor lines and declared symbols exposed to seed and review
                internal/cost           ledger + costs --gate-timeout; run_id prefixes test- / gate- / full- / review-; costs/policy.yaml
                internal/feedback       score (window scoring after a cadence full run; REJECTION_CONTRADICTED) · attribute (+ --propose) · readiness (+ LEVEL / NEXT / ADOPTED_UNREVIEWED / AGENT_ADOPTED / SEEDED / POLICY / CADENCE / REVIEW_* / KIND_PROPOSALS / CALIBRATION)
                internal/{axes,changesurface,sched,stale,gitx,platform}
                  ├─ exec:  git, runner scripts / builtins, admission / allocator commands, scanner plugins — never a code agent
                  └─ files: aitestmap/** · .aitask-testmap/ (runs, ledger, onboard/<run>/seed.json, onboard/<run>/review/<n>.txt) · XDG cache (deps; cochange matrix by HEAD sha)

.aitask-scripts/lib/gate_verifier_lib.sh           run_project_command_key(): + 75 → error (command_refused), 3 → error (command_errored) for opted-in keys;
                                                   exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command
.aitask-scripts/gates_reference.yaml               + testmap_fresh (procedure), testmap_check (unlocks: [tests_pass]); no separate selection gate
.aitask-scripts/aitask_gate_testmap_check.sh       machine verifier; reports SEEDED:<n>, ADOPTED:<n>|human <h>|agent <a>|auto <m>, UNMAPPED_SOURCE:<path>
.aitask-scripts/aitask_gate_tests_pass.sh          unchanged; runs test_command = ./ait test under the opt-in
.aitask-scripts/aitask_setup.sh                    install_engine_binary() + report_testmap_state() → TESTMAP:<state>
.aitask-scripts/aitask_codeagent.sh                + operation testmap-review (interactive by default; --print only under --headless, as batch-review)
.claude/skills/aitask-testmap-onboard/             profile-aware stub + SKILL.md.j2 + one procedure file per phase (review.md = the reading sub-phase of adopt)
.claude/skills/aitask-testmap-review/              NEW profile-aware bulk reader: packets in, VERDICT lines out, batches of agent_review.batch, resumable
.claude/skills/aitask-testmap/                     maintenance skill; opens with `ait test --howto`; hands an un-onboarded repo to onboard; `annotate --author`
.claude/skills/aitask-gate-testmap-fresh/          procedure gate + the seeds step: packets for touched test files; attended pre-fill / confirm / trust-batch; autonomous adopts
.claude/skills/task-workflow/SKILL.md.j2           Step 7: one paragraph (the loop) + the pre-review Affected Tests Procedure (affected-tests.md; autonomous branch = annotate --author)
.claude/skills/task-workflow/build-verification.md + one branch: verdict error / command_refused | command_errored
.claude/skills/aitask-qa/{test-discovery,test-execution}.md   registry-first branches; Covered (adopted by human|agent|auto)
seed/aitasks_agent_instructions.seed.md            + `## Running Tests` (generic; installed into every agent surface by ait setup)
seed/models_{claudecode,codex,opencode}.json        + verified.testmap-review per model (the existing per-operation score table; 0 until measured)
engine/                                             Go source — framework repo only, excluded from the tarball
```

### The registry directory

```
aitestmap/
  config.yaml            unit_covers_max, suite_budget_s, bootstrap_until, require_stamp, broad_review_days, concurrency,
                         broad_after_unit, device_policy, host_class, flake_threshold, symbol_scanners, run_gate_admission
                         + completion: {mode full|selected|auto, full_run_every: {tasks, selection_ratio_above, days}, deferred, on_empty_selection, engine_absent}
                         + agent_review: {enabled, confidence, accept_min, calibration_min, batch, packet_lines, max_pairs_per_run, author, measured_confidence}
                         + readiness: {min_scored_full_runs, max_false_negatives, require_opaque_proofs, min_full_runs_since_map_change}
                         + conventions: [{test, source}]  helper_roots: [...]  helper_fanin: 0.05
                         + exclude: [globs]  docs: [paths]  notes: | (<=10 lines)  broad_threshold_s: 60
  onboard.yaml           phase ledger: {contract, task, level, phases{...}, rejections[], reviews[], kind_proposals[], calibration[]}
  axes.yaml · runners.yaml · resources.yaml      runners.yaml written by onboard detect --write, confirmed per runner
  registry/
    _scanned.yaml · _scoped.yaml · observed.yaml · areas.yaml · <area>.yaml
    seeded.yaml          the queue; generated by onboard seed; a row gains a verdict on intake; rows leave on adopt / reject; parked rows stay
    adopted.yaml         provenance of class-, verdict- and author-adopted edges; a row leaves when a human re-stamps the edge
  costs/
    <hostclass>.yaml · predictions.yaml
    policy.yaml          {last_full_run: {run_id, at, task, sha}, selected_since_full: n, approved_by: {who, at, mode, statement}} — the engine's, under auto
  runners/ · scanners/                           runners/<name>.sh may come from onboard scaffold --runner
```

The onboarding additions to `config.yaml`:

```yaml
completion:
  mode: auto                     # full | selected | auto — auto is what detect --write writes (confirmed in the attended config table);
                                 # selected is written only by the skill's --policy re-entry after READINESS_DECISION:ADMISSIBLE with a
                                 # human approved_by; auto behaves as full until readiness is ADMISSIBLE, then runs the selection and lets
                                 # the cadence below force full runs; a project that wants a person in the flip sets full
  full_run_every:                # the cadence that replaces the human approver under auto — each trigger is a printed reason
    tasks: 5                     # at most N selected completion runs between full runs (a miss survives at most N-1 tasks)
    selection_ratio_above: 0.60  # a selection estimated at >= 60 % of the full-suite p95 runs full — the saving is not worth the window
    days: 7                      # wall-clock ceiling on the gap between full runs
  deferred: run                  # run | fail — completion never silently drops a row the interactive budget would cut
  on_empty_selection: skip       # skip (exit 2 → gate skip under the opt-in) | full; ignored by a cadence full run
  engine_absent: error           # error (exit 3) | fallback_command (the full: true suite runner's fallback_command:, MODE:fallback)
agent_review:                    # the two reading origins (see The Adoption Model and The Agent Review Pass)
  enabled: true                  # false → agent:* origins are never written; the human-only adoption of the baseline
  confidence: 0.90               # the prior for agent:review and agent:author; a project may set it lower from day one
  accept_min: 0.85               # the class threshold a row must clear (noisy-OR), and the calibration floor below which verdicts stop adopting
  calibration_min: 30            # labelled pairs before agreement is acted on
  batch: 20                      # pairs per review packet
  packet_lines: 120              # ceiling on REVIEW_TEST lines per pair
  max_pairs_per_run: 400         # a bulk review stops here and records the phase as partial
  author: true                   # false → the pre-review procedure's autonomous branch proposes instead of stamping
  # measured_confidence: 0.91    # written by calibration; replaces the prior for this repository when lower
readiness:
  min_scored_full_runs: 20
  max_false_negatives: 0
  require_opaque_proofs: true
  min_full_runs_since_map_change: 3   # clean scored full runs since the last bulk adoption or author write
conventions:                     # seeded by onboard detect per framework; the `convention` origin (0.60)
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/aitask_{stem}.sh"}
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/lib/{stem}.sh"}
  - {test: "tests/test_{stem}.py", source: ".aitask-scripts/lib/{stem}.py"}
helper_roots: ["tests/lib/**", "**/testing/**", "**/testdata/**"]
helper_fanin: 0.05               # a closure path reached by ≥5 % of a runner's units is a helper, not a subject
exclude: ["tests/golden/**", "tests/data/**"]                          # never listed, never UNREGISTERED
docs: [aidocs/testing/change-aware-verification.md]                    # printed by --howto
notes: |                                                               # printed by --howto verbatim, <=10 lines
  A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
broad_threshold_s: 60            # classify signal — a recorded p95 above this proposes a broad kind
```

### Where state lives

| data | location | written by |
|---|---|---|
| seed queue | `aitestmap/registry/seeded.yaml` rows `{test[#member], covers, origin[], confidence, evidence{}, proposed_at, verdict?}` — `evidence.agent_review {verdict, assert_line, rationale, by, run, packet_sha, test_blob, unsure: n, at}` once reviewed | `onboard seed --apply`; `attribute --propose`; `onboard adopt --agent-verdicts` (adds the origin and the verdict; parks; removes a row only when it adopts it); rows removed by `onboard adopt` / `onboard reject` |
| adopted-edge provenance | `aitestmap/registry/adopted.yaml` rows `{test, source, origin[], confidence, adopted_at, task, by, run?, rationale?, assert_line?, packet_sha?, test_blob?, source_blob?}` — `by` is `human:<email>`, `agent:<agent-string>` or `auto` | `onboard adopt --class` (a person, or `--auto` over a rule or measurement class); `onboard adopt --agent-verdicts` (a `verifies` verdict); `annotate --author`; rows deleted when `verify`, `annotate`, `stale --confirm-source` or a per-row `adopt` re-stamps that edge |
| phase ledger | `aitestmap/onboard.yaml` `{contract, task, level, phases{detect, inventory, seed, waivers, enable, full_run, adopt, review: {status, at, by, counts{reviewed, adopted, parked, unsure}, partial}, classify, scaffold, finish}, rejections[], reviews[], kind_proposals[], calibration[]}` — `reviews[]` is the verdict memory `{test, source, verdict, test_blob, packet_sha, run, by}` so a pair is read once per test blob per reader; `kind_proposals[]` holds a headless run's `CLASSIFY:` rows; `calibration[]` the `--calibrate` results | the engine's `onboard` verbs; read by `onboard status`, `readiness`, `report_testmap_state()`, the skill's re-entry |
| seed dump for review | `.aitask-testmap/onboard/<run-id>/seed.json` (gitignored), attached to the level task with `ait attach` | `onboard seed --json --out` |
| review packets as files | `.aitask-testmap/onboard/<run-id>/review/<n>.txt` (gitignored): the same line-protocol packet `onboard review` prints, ≤ `agent_review.batch` pairs each, grouped by test file, one file per crew agent | `onboard review --out <dir>`; read by crew agents; their `_output.md` fed back by `onboard review --collect <crew-id>` |
| completion policy, cadence, review knobs, readiness thresholds, conventions, helper roots, docs, notes, excludes | `aitestmap/config.yaml` — the committed, human-authored declaration | `onboard detect --write` (level 0: `completion.mode auto`, `full_run_every`, `agent_review`, `readiness`); the skill's `enable` phase (`docs:`, `notes:`); the `--policy selected` re-entry (`completion.mode`, `run_gate_admission.approved_by {who, at, statement}`); calibration (`agent_review.measured_confidence`) |
| the engine's policy ledger | `aitestmap/costs/policy.yaml` `{last_full_run {run_id, at, task, sha}, selected_since_full, approved_by {who: engine:readiness@<run>, at, mode: auto, statement}}` — committed | `ait test --gate` under `auto`: the engine writes it and prints `POLICY_WRITE:<path>`; the bash front commits it under `ait: testmap policy <flip\|full-run> (t<id>)` with the path named |
| test entry and exit-contract opt-in | `aitasks/metadata/project_config.yaml`: `test_command: ./ait test`, `gate_command_exit_contract: [test_command]` | the skill's `enable` phase, confirmed once as a table |
| gate declarations | profiles' `default_gates` (`tests_pass`, `testmap_check`, `testmap_fresh`; `rendered_gates` where present); `gates.yaml` `tests_pass.timeout_seconds` | the skill's `enable` phase; the timeout from `costs --gate-timeout` after the first full run |
| agent instructions | `CLAUDE.md` `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md`, the OpenCode mirror | `ait setup` from the seed; a hand-maintained `CLAUDE.md` by the level-0 task |
| model score table | `aitasks/metadata/models_<agent>.json` `verified.testmap-review` per model | the seeds; `aitask-add-model` |
| runs, ledger, predictions | `.aitask-testmap/runs/<run-id>/`, `.aitask-testmap/ledger.jsonl` (gitignored); `aitestmap/costs/<hostclass>.yaml`, `aitestmap/costs/predictions.yaml` (committed) | every run; `costs --update`; `score` |
<!-- /section: architecture -->

<!-- section: design_decisions [dimensions: component_adoption_ledger, component_seeder, component_onboarding_skill, component_test_entrypoint, component_test_front_verb, component_gates, component_completion_policy, component_auto_policy, component_workflow_integration, component_annotation_scanner, component_agent_review_pass, component_author_annotation, assumption_seeds_select_never_evidence, assumption_cochange_is_corroboration, assumption_onboarding_is_a_task, assumption_helper_degrades_when_absent, assumption_gate_exit_contract_reused, assumption_annotation_is_comment_only, assumption_task_resolvable_from_session, assumption_headless_launch_is_explicit_opt_in, assumption_session_agent_is_reviewer, assumption_agent_rejection_is_revocable] -->
## Design decisions

Each decision names the alternative it rejects, because the alternative is
the shortest way to say what the choice protects.

1. **Three adoption states, not two.** A queue that *selects but never
   claims* is the right state before anyone has accepted an edge; a stamped
   edge with a provenance row is the right state after a whole evidence
   class, a reading or an author claim was accepted; a per-pair human
   acceptance is a reviewed claim and needs no provenance. Collapsing to
   "queue or stamped" would either force per-row review of ~720 files or let
   a class-level yes masquerade as review.

2. **Autonomous adoption needs a rule, a measurement or a reading — never a
   heuristic alone.** Acceptance is the one act that turns evidence into a
   claim the freshness machinery enforces, and the judgement it needs — does
   this test *verify* this source or only *drive* it — is a reading of the
   test body, which a person or an agent can do; a static closure cannot.
   So a headless profile may adopt a class only when every member carries a
   rule (`static:package`), a measurement (`coverage`) or a reading
   (`agent:review` over an engine-cut packet, `agent:author` at authoring
   time) and its noisy-OR clears `accept_min`; `static:invocation`,
   `static:import`, `convention`, `plan`, `prose`, `cochange` and `observed`
   remain heuristics — they select, order the queue and raise a verdict's
   combined confidence, and none of them adopts by itself, however high its
   measured precision, because its fact is "executes" or "co-occurs", never
   "verifies". The rejected alternative — "only a person" — was a proxy for
   "only something that read the test", and it left every headless
   repository at level 0 forever. Every reading is recorded with `by:`,
   run, rationale and packet digest and displayed as `adopted(… by
   agent:<string>)`, so it can never be mistaken for a human class
   acceptance.

3. **One origin table, co-change capped.** The evidence sources that seed
   edges are one measured table with one confidence vocabulary and a class
   per row. Co-change is capped at 0.60 and needs two distinct task groups
   because the measured group shape (336 groups in 400 aitasks commits, 1.14
   commits per group, a few tests paired with a few scripts) never says which
   test covers which script — it corroborates a static edge and cannot
   manufacture one.

4. **Levels × phases, one aitask per level.** Levels describe the registry
   (what exists); phases describe a run (how far it got). Both are needed
   for a half-migrated repository to be a known state with a next step. A
   level is one aitask because it may wait weeks on full-run history; a
   phase commits on its own because it may span sessions.

5. **The first full run is the level-0 task's own `tests_pass`.** A separate
   "full run" phase would be the same run outside the gate ledger. Landing it
   as the task's Step-9 gate puts every unit's `last_pass` anchor, the cost
   fold and the (empty) prediction score under one `(t<id>)`.

6. **`bootstrap_until` is level-0 day + 90.** Level 0 is unstamped by
   design and a thousand-row seed queue is not adopted in 30 days; `finish`
   may shorten it.

7. **One verb, two layers.** The parts that must run with no engine
   (fallbacks, task resolution, the advisory verdict, the policy commit) are
   bash; the pipeline (select → schedule → run) is one Go composite. A
   single Go verb would leave a repository with no engine unable to run its
   own `test_command`.

8. **Advisory is a mode, not a second script.** The pre-review helper's
   `VERDICT:/REASON:` contract and its degrade-to-skip rule are
   `ait test --advisory`. One script, one exit-contract statement, one set
   of permission touchpoints.

9. **The loop is a paragraph; the pre-review run is a procedure.** The
   in-loop call needs no procedure: "run `./ait test` after each meaningful
   change". The pre-review run needs one because it has a branch table and
   because it is the run guaranteed to write a prediction record in every
   profile.

10. **One completion gate under a committed policy that may approve
    itself, behind a cadence full run; the engine's approval is a ledger,
    not the declaration.** The existing `tests_pass` runs `./ait test
    --gate`; whether that is the whole registry or the task's selection is
    `completion.mode` in `config.yaml`. Under `selected` a person flipped it
    after `ADMISSIBLE` and recorded `approved_by` in `config.yaml`; under
    `auto` the engine flips it on the first admissible completion run,
    records `approved_by {who: engine:readiness@<run>, mode: auto}` in
    `costs/policy.yaml` beside the other engine-written ledgers — so the
    committed declaration stays human-authored and a reader can tell the two
    apart — and is demoted automatically and loudly exactly as before. What
    replaces the person's judgement is not trust in the map but a
    **cadence**: the Nth completion since the last full run, a selection
    estimated at more than a fraction of the full suite, or D days without a
    full run each force `run --all`, and that run scores every prediction
    since the last full run. The invariant holds and is extended: the policy
    can only fail toward running more, and a cadence full run is never
    skipped by `on_empty_selection` or by a demotion. The rejected
    alternatives: a second selection-only gate would give an agent two
    commands to learn and a project two declarations to keep consistent, and
    the legacy Step-9 path and `aitask-qa` would never reach the selective
    lane; trusting the demotion criteria alone was rejected because scoring
    only happens on full runs, and a policy that never runs full can never
    demote itself.

11. **Adoption writes comment lines only.** A Python module docstring is
    read by the grammar but never written into, because that changes
    `__doc__`; a member seed lands inside its `testmap:unit` block; a file
    with no comment leader the grammar knows is skipped, not restructured.
    `--agent-verdicts` and `--author` write at the same fixed positions.

12. **A suite wired as `verify_build` is asked about, not moved.**
    thinking_backend's `run_script_tests.sh` also enforces a shellcheck
    baseline; moving it would drop the lint half, leaving it would run the
    suite twice. The skill asks and defaults to keeping it, adding
    `test_command: ./ait test` over the detected units.

13. **Task resolution is implicit with an explicit override.** The worktree
    branch (`aitask/<task_name>`) or the single Implementing lock this user
    holds identifies the task; `--task` overrides; two candidates are
    `AMBIGUOUS_TASK`; the advisory form always passes `--task` because the
    procedure knows the id.

14. **An agent verdict moves an edge only toward more claims, never toward
    less selection.** A `verifies` verdict adopts a seed; a `drives` or
    `unsure` verdict *parks* it — the row stays in `seeded.yaml`, keeps
    selecting at distance 1, leaves the adoptable set, is never re-read for
    the same test bytes by the same reader, and is listed for a person as
    `REVIEW_PARKED:<n>`; two `unsure` verdicts from different runs mark the
    pair `REVIEW_HUMAN`. Only a person's `onboard reject` removes a seed, and
    a scored miss that contradicts a human rejection is printed
    (`REJECTION_CONTRADICTED:`) and never overrules it. The alternative —
    letting a `drives` verdict land as a rejection — was rejected on the
    merits of the verdict itself: a test that only drives a source is still
    coupled to it (a breaking change to a driven script breaks the test's
    setup), so it must keep running for a change to that source; what
    `drives` decides is only that the pair may not *claim*. A rejection
    would make one wrong reading stop a test running for a change, which is
    the one direction the whole design refuses to fail in, and it would need
    a revocation mechanism to undo what parking never does.

15. **The reading is a skill act; the engine never calls a model, and every
    agent launch is a framework wrapper.** The engine writes packets and
    consumes verdict lines; the reading between them is done by the agent
    already in session — the onboarding skill's agent (attended or headless;
    the `remote` profile's agent is headless already), the `testmap_fresh`
    gate's agent, the pre-review procedure's agent — or by the bulk skill
    `aitask-testmap-review` launched through `ait skillrun testmap-review`
    (interactive) or `ait codeagent testmap-review` (interactive by default,
    `--print` only under `--headless`), or by crew agents that `ait crew
    runner` launches through `ait codeagent --agent-string … invoke raw`
    under the crew's launch mode. Print mode is where Claude Code's higher
    per-token rate is accepted knowingly, so it is an explicit flag on the
    wrapper and never a default of any path. A verifier that shelled out to
    `claude -p` would put that cost on every gate run and would violate the
    rule every other script of the framework follows.

16. **The authoring agent stamps only what it touched.** `annotate
    --author <test> <source>` refuses a pair unless both the test and the
    source are `COMMITTED:` or `TASK:` rows of the current task's change
    surface (`AUTHOR_REFUSED:<pair>|outside-change-surface`); a pair with no
    static relation between them is accepted but flagged
    `AUTHOR_UNCORROBORATED` so a person can see a claim the closure does not
    support. Letting the agent annotate anything would turn
    `UNMAPPED_SOURCE` silencing into a habit; limiting it to the change
    surface keeps the claim inside the diff a reviewer already reads at
    Step 8.

17. **Kinds and axes stay human; headless proposes kinds.** A wrong
    `covers` edge over-selects and shows its provenance; a wrong kind moves
    a test between the digest-stale and the area-stale regimes and no run
    gives an agent evidence to check its answer against; an axis is a
    declaration of the project's product space. `onboard classify` keeps
    printing proposals with reasons in every profile; a headless run
    records them as `kind_proposals[]` in `onboard.yaml` (`KIND_PROPOSALS:<n>`
    in `readiness`) and writes no kind line; level 3 is not entered
    headless.
<!-- /section: design_decisions -->
<!-- section: data_flow [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_completion_policy, component_auto_policy, component_workflow_integration, component_workflow_seam, component_selector, component_annotation_scanner, component_author_annotation, component_freshness, component_feedback_tools, component_cost_ledger, component_registry_loader, component_staleness_tool, component_engine_packaging, component_agent_review, component_agent_review_pass] -->
## Data Flow

### A task in steady state

```
Step 7  edit source ──▶ ./ait test                      MODE:interactive TASK:<id> (branch | lock) INTAKE:change-surface
                        change surface ──▶ test composite ──▶ select (edges ∪ adopted ∪ seeds ∪ deps ∪ rules ∪ axes ∪ test-dep) --include-stale
                        ──▶ schedule ──▶ run ──▶ ledger rows (run_id test-…) ──▶ SELECTED: / UNMAPPED_SOURCE: / UNANNOTATED_TEST: / RESULT:
                        ──▶ prediction record for this task (newest wins)
        before Step 8 ──▶ ./ait test --advisory --task <id> ──▶ VERDICT:/REASON:/LOG: ──▶ prediction record ──▶ plan Final Implementation Notes
                        UNMAPPED_SOURCE / UNANNOTATED_TEST ──attended offer──▶ annotate --author (default, pairs pre-filled) | by hand | attribute --propose | continue
                                                           ──autonomous──▶ annotate --author <test> <source> --task <id> --by <agent-string>
                                                                           for pairs whose two files are on the change surface
                                                                           (→ stamped line + adopted.yaml {origin agent:author, by agent:<s>, task, run}) else continue
Step 8  procedure gates ──▶ testmap_fresh ──▶ stale --task (STALE / EVIDENCED / UNSTAMPED, adopted(... by <who>) shown)
                                          ──▶ seeds step: onboard review --ids <rows on touched test files> ──▶ the agent reads the packets
                                              attended  → verdicts pre-filled per row; a person confirms (reviewed, by: human) · overrides · trusts the batch (by: agent)
                                              autonomous → onboard adopt --agent-verdicts - --by <agent-string> --run <gate-run>  (verifies adopts; drives/unsure park)
Step 9  ait gates run ──▶ testmap_check (SEEDED:, ADOPTED:, UNMAPPED_SOURCE:, strict past bootstrap) ──▶ tests_pass = ./ait test --gate (policy)
        POLICY:full     ──▶ run --all ──▶ score the newest prediction
        POLICY:auto     ──▶ readiness ADMISSIBLE? no → full · yes → cadence due? yes → full (window score) · no → selection (MODE:selected|policy:auto|next_full_in:<n>)
        full run ──▶ automatic score against every unscored prediction since the last full run ──▶ PREDICTION_MISSED:<id>|<task> ──▶ attribute (decide | --propose → seeded.yaml)
                 ──▶ a miss on a pair a person rejected ──▶ REJECTION_CONTRADICTED:<test>|<source>|<run> (advisory; the row stays)
```

Every task-scoped selection writes the task's prediction record; the newest
one is what the next full run scores. The interactive loop may run many
times or never; the pre-review advisory run happens once in every profile,
which is why a scored prediction exists for every task that reaches
completion.

### A completion run under policy

```
ait gates run 1234 → testmap_check → pass → unlocks tests_pass
   → aitask_gate_tests_pass.sh → run_command_gate → export AIT_GATE_TASK_ID=1234 AIT_GATE_RUN_ID=<run> → `./ait test`
      MODE:completion  POLICY:full                       → run --all (subsumed_by honoured) → exit 0/1/2/3/75
      MODE:completion  POLICY:selected                   → readiness: all met → task selection, deferred rows RUN
      MODE:completion  POLICY:selected → POLICY_DEMOTED:selected->full|max_false_negatives → run --all
      MODE:completion  POLICY:auto                       → readiness NOT_YET → POLICY:auto|full|not_yet:<criterion> → run --all (identical to full)
      MODE:completion  POLICY:auto, first ADMISSIBLE run  → POLICY_FLIPPED:auto->selected|engine:readiness@<run>
                                                           → costs/policy.yaml approved_by {who: engine:readiness@<run>, at, mode: auto, statement}
                                                           → POLICY_WRITE:aitestmap/costs/policy.yaml → the front commits `ait: testmap policy flip (t1234)` → selection
      MODE:completion  POLICY:auto, cadence due           → POLICY:auto|full|cadence:tasks (5/5) | cadence:selection_ratio (0.63) | cadence:days (8)
                                                           → run --all → window score → last_full_run, selected_since_full := 0 → POLICY_WRITE: → `ait: testmap policy full-run (t1234)`
      MODE:completion  POLICY:auto, otherwise             → POLICY:auto|selected|next_full_in:<n> → task selection, deferred rows RUN, selected_since_full += 1
   → run_project_command_key: 0 pass · 1 fail · 2 skip · 3 error(command_errored) · 75 error(command_refused)   [opted-in key]
   → ledger block result="MODE:full|720 units|policy:full" or result="MODE:selected|14|policy:auto|next_full_in:3" → orchestrator: pass / fail / skip / error (retry within max_retries)
   → after any full run: PREDICTION_SCORED:<r1..rk>|<run> PREDICTION_FALSE_NEGATIVES:<n> → costs/predictions.yaml (every prediction since the last full run scored,
     each miss attributed to the earliest task in the window whose change surface reaches the failing unit, culprit ids from `git log -M` when history is reachable) → readiness input
```

### Onboarding level 0: existing tests → registry → first anchored run

```
repository (tests, scripts, build files, project_config.yaml, code_areas.yaml, git history)
   ▼  onboard detect [--write]        FRAMEWORK: / AGGREGATE_RUNNER: / SERIAL_LIST: / RESOURCE_HINT: / SUITE_CANDIDATE: / UNIVERSE: / UNLISTED: / RUNNER_SCRIPT_NEEDED:
   │                                  --write → aitestmap/{config,runners,resources}.yaml · registry/areas.yaml   (runner table confirmed per runner;
   │                                  config.yaml carries completion.mode auto + full_run_every, agent_review, readiness — confirmed in the config table)
   ▼  onboard inventory               scan + every runner list + check → _scanned.yaml · UNREGISTERED: resolved (bind | exclude:)
   ▼  onboard seed [--apply] [--json --out]   deps facts (invocation, imports, package) + conventions + git log (t<id>) + plans + prose [+ coverage]
   │                                  → SEED:<test>|<source>|<origins>|<confidence> · SEED_HELPER: · SEED_READS: · SEED_KIND: · SEED_BATCH_NO: · SEED_MEMBER: · SEED_AXIS:
   │                                  --apply → registry/seeded.yaml ;  --json --out → .aitask-testmap/onboard/<run>/seed.json (attached to the task)
   ▼  check / explain --sources       UNMAPPED_SOURCE clusters → rules for hot directories · expiring waivers (+90d) · leave unmapped   (waivers phase)
   ▼  enable (skill)                  test_command: ./ait test (previous value → full: true suite runner with fallback_command:) · gate_command_exit_contract += test_command
   │                                  profiles default_gates += tests_pass, testmap_check, testmap_fresh · docs: · notes: · hand-maintained CLAUDE.md paragraph
   ▼  task-workflow Step 8            annotation diff reviewed (none at level 0); testmap_fresh: nothing STALE
   ▼  task-workflow Step 9            ./ait gates run → testmap_check (non-strict) → tests_pass → ./ait test --gate
   │                                  MODE:completion POLICY:auto → readiness NOT_YET → run --all → ledger rows → last_pass per unit · costs --update · PREDICTION_SCORED:none
   ▼  after the run (full_run phase)  costs --gate-timeout tests_pass → gates.yaml tests_pass.timeout_seconds (ait: commit) · readiness → LEVEL:0 NEXT:adopt
   ▼  every phase                     onboard.yaml row · chore: Onboard testmap — <phase> (t<id>) commit, paths named
```

### Level 1: seeds → verdicts → stamped edges

```
onboard adopt --class static:package --auto          rule: no reading needed → stamp + adopted.yaml {by: auto}
onboard adopt --class coverage --auto                measurement: the same, where per-unit coverage was imported
review phase (review.md — the aitask-testmap-review flow):
   loop  onboard review --next 20 [--class static:invocation]      → REVIEW_BATCH:<n>|<pairs> · REVIEW_MEMO:<skipped> (pairs already read for this test blob)
         the agent reads each packet: REVIEW_PAIR / REVIEW_ANCHOR / REVIEW_TEST (assertion lines flagged !) / REVIEW_SOURCE (declared symbols) / REVIEW_PROSE / REVIEW_MEMBER / REVIEW_END:<packet_sha>
         and answers one line per pair:
            VERDICT:<id>|verifies|<test path:line of the assertion that checks the source>|<rationale ≤ 160 chars>
            VERDICT:<id>|drives|-|<rationale>            VERDICT:<id>|unsure|-|<rationale>
         onboard adopt --agent-verdicts - --by claudecode/opus5 --run review-<n>
            validates: pair in the packet · packet_sha current (else VERDICT_STALE:<id>, re-packeted) · for verifies the named line exists in the test
                       and names the source's stem, its command form, an output path it writes or an exported symbol (else VERDICT_INVALID:<id>|<reason>, row untouched)
            verifies → origin[] += agent:review, evidence.agent_review{...}, confidence = noisy-OR (0.90 + 0.90 = 0.99) ≥ accept_min
                       → stamp through the rewriter + adopted.yaml {by: agent:claudecode/opus5, run, rationale, assert_line, packet_sha, test_blob, source_blob} · row leaves seeded.yaml
            drives   → parked: verdict on the row, still selects, out of --auto, never re-read for these test bytes → REVIEW_PARKED
            unsure   → parked with unsure: 1, re-packeted once for a different run; at 2 → REVIEW_HUMAN, out of every packet
            → onboard.yaml reviews[] memo · REVIEW_APPLIED:<verifies>|<drives>|<unsure>|<invalid>|<stale> · WROTE:<file> · ADOPT_SUMMARY:1|<edges>|<files>|<skipped>|agent
            → REVIEW_AGREEMENT:<agree>/<labelled> over pairs that also carry a human per-row decision · REVIEW_ORIGIN_DEMOTED below accept_min over calibration_min
   until  the queue is empty, max_pairs_per_run is reached (phases.review partial → re-entered at ONBOARD_NEXT:review), or (attended) the user stops
onboard review --calibrate 50                       against coverage facts where present, else human-reviewed rows → CALIBRATION:agree <a>|disagree <d>|<ratio> → calibration[]
onboard adopt --class static:invocation --accept-min 0.85 [--scope <glob>]   (attended: accept all | review a sample of ten, verdicts and rationales beside each | edit rows | skip)
   → rewriter: testmap:covers <src> @<date>/<blob10> at the fixed position → WROTE:<file> · registry/adopted.yaml rows {by: human:<email>} · rows leave seeded.yaml
   → ADOPT_REFUSED:dirty-foreign · ADOPT_SKIP:duplicate|unregistered|no-leader · ADOPT_SUMMARY:1|<edges>|<files>|<skipped>|human
onboard adopt --area <a> --batch 50        (per row, evidence beside each: file pair, file:line, task ids, coverage run, the verdict and its rationale) → stamp, no provenance row
onboard reject <test> <source> --reason    → onboard.yaml rejections[] {by: human:<email>}; never re-proposed — a person's verb; REJECT_REFUSED:headless under AIT_PROFILE_HEADLESS=1
Step 8 testmap_fresh, any later task       → packets for seeds on this task's touched test files → attended confirm / override / trust-batch · autonomous --agent-verdicts → rides the (t<id>) commit
human re-stamp (verify · stale --confirm-source · annotate · per-row adopt) → adopted.yaml row deleted → REVIEWED
```

### The policy flip

```
completion.mode: auto  (written by detect --write; confirmed in the attended config table)
   every ./ait test --gate → readiness → READINESS:min_scored_full_runs|met|34  READINESS:max_false_negatives|met|0  READINESS:require_opaque_proofs|met
                                        READINESS:min_full_runs_since_map_change|met|4  READINESS:cadence_declared|met  READINESS:approved_by|met|engine  READINESS_DECISION:ADMISSIBLE
   first admissible run → POLICY_FLIPPED:auto->selected|engine:readiness@gate-…  → costs/policy.yaml approved_by {who: engine:readiness@gate-…, at, mode: auto, statement: <the readiness lines>}
                          → POLICY_WRITE:aitestmap/costs/policy.yaml → the front commits it (`ait: testmap policy flip (t<id>)`, path named) → this run and the next ones run the selection
   cadence               → POLICY:auto|full|cadence:tasks  → run --all → PREDICTION_SCORED over the 5-task window → last_full_run, selected_since_full := 0 → `ait: testmap policy full-run (t<id>)`
   regression            → POLICY_DEMOTED:auto->full|max_false_negatives → full until readiness is ADMISSIBLE again; approved_by cleared (the same commit path)

completion.mode: full + /aitask-testmap-onboard --policy selected   (the attended alternative, unchanged)
   → readiness → … READINESS:approved_by|unmet|-  → LEVEL:2 NEXT:scaffold  ADOPTED_UNREVIEWED:618|0.61  SEEDED:412  POLICY:full|would run selected: 14 units
   → AskUserQuestion: record approval {who, statement} → config.yaml completion.mode: selected, run_gate_admission.approved_by → ait: commit
   → the next tests_pass runs the selection; any later unmet criterion demotes it loudly; no cadence unless full_run_every is also declared
```

### Reading the map without running anything

```
ait test --howto ──▶ registry + ledger + config.yaml docs:/notes: + onboard.yaml + costs/policy.yaml ──▶ TESTMAP:/RUNNER:/FULL_GATE:/GATE:/AGENT_REVIEW:/VERBS:/AXES:/RESOURCE:/NEW_TEST:/DOCS:/NOTES:
aitask-qa 3a ──▶ ait testmap explain --sources <changed> --format table ──▶ Covered | Covered (adopted by human|agent|auto) | Covered (seeded) | GAP
ait setup ──▶ report_testmap_state() ──▶ TESTMAP:<state>
onboard status ──▶ phases · ONBOARD_NEXT: · seed queue per origin and per verdict (verifies / parked / unsure / unreviewed) · adopted unreviewed split by `by`
               · AUTHOR_UNCORROBORATED · REVIEW_PARKED · REVIEW_HUMAN · KIND_PROPOSALS · REVIEW_AGREEMENT · CALIBRATION · ratios · oldest pending
readiness ──▶ … POLICY:auto|selected|next_full_in:3 · CADENCE:last_full <run>|<n> tasks ago|<d> days · REVIEW_AGREEMENT:41/44 · AGENT_ADOPTED:540|0.75 · KIND_PROPOSALS:12
```
<!-- /section: data_flow -->

<!-- section: adoption_model [dimensions: component_adoption_ledger, component_seeder, component_onboarding_engine_verbs, component_registry_loader, component_annotation_scanner, component_dependency_scanners, component_agent_review_pass, component_author_annotation, assumption_seed_sources_measured, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_seeds_select_never_evidence, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only, assumption_agent_can_judge_verifies, assumption_agent_reads_verify_vs_drive, assumption_wrong_positive_claim_only_overselects, assumption_agent_rejection_is_revocable, assumption_author_annotates_own_surface] -->
## The Adoption Model

### The idea

A machine can find evidence that a test exercises a source; a *reader of
the test body* — a person, or an agent given the test's assertion lines
beside the source's symbols — can turn that evidence into a claim the
freshness machinery will enforce; and a *rule* or a *measurement* (a
language fact, a coverage run) may do so without a reader. The adoption
model keeps finding and claiming apart with three states, makes every
transition an explicit, printed verb, records who took it, and lets an
agent take every transition except the one that removes a seed.

### The three states, with `by:`

```
                onboard seed --apply · attribute --propose                onboard adopt --class <origin> [--accept-min 0.85] [--scope <glob>]   (a person → by: human:<email>)
   (none) ─────────────────────────────▶ SEEDED ──────────────────────────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row {by})
                                            │  (selects at d1, no stamp,     onboard adopt --class <rule|measurement> --auto                     (by: auto)
                                            │   invisible to stale,          onboard adopt --agent-verdicts - --by agent:<s> --run <r>, verifies (by: agent:<s>)
                                            │   never --strict)                                                                                │
                                            │ ◀── VERDICT drives | unsure: PARKED (verdict on the row, still selects, out of --auto; unsure ×2 → REVIEW_HUMAN)
                                            │                                                                                                  │ human re-stamp: verify · stale --confirm* · annotate
                                            │ onboard adopt <test> <source> | --area <a> --batch <n> | an in-gate row a person confirmed          ▼
                                            ├────────────────────────────────────────────────────────────────▶ REVIEWED (stamp, no provenance row)
                                            │ onboard reject <test> <source> --reason   (a person; never an agent verdict; REJECT_REFUSED:headless)
                                            ▼
                                        REJECTED (onboard.yaml rejections[] {test, source, reason, by: human:<email>}; never re-proposed; a scored miss contradicts it in print)
   annotate --author <test> <source> --task <id> --by <s>  (both files on the task's change surface) ─────────▶ ADOPTED (stamp + adopted.yaml row {origin [agent:author], by: agent:<s>})
```

- **Seeded** rows select — a seeded edge is walked like an annotation edge at
  distance 1 with reason `edge(seeded:<origins>)` — and claim nothing: no
  stamp, no freshness verdict, never counted under `--strict`, never
  satisfying `require_stamp`.
- **Adopted** edges are stamped and therefore evidenced, stale-checked and
  enforced like any annotation, but their `adopted.yaml` row keeps the
  machine origin and the adopter visible: `stale` and `explain` print
  `adopted(<origins> <confidence> by <who>)` on the row —
  `adopted(static:invocation+agent:review 0.99 by agent:claudecode/opus5)`,
  `adopted(coverage 0.95 by auto)`, `adopted(agent:author 0.90 by
  agent:…)`, `adopted(static:import 0.85 by human:…)` — `readiness` counts
  them as `ADOPTED_UNREVIEWED:<n>|<ratio>` and `AGENT_ADOPTED:<n>|<ratio>`,
  and `onboard status` splits the count by `by`.
- **Parked** is a mark on a seeded row: a `drives` or `unsure` verdict
  leaves the row selecting, keeps it out of autonomous adoption, and lists
  it as `REVIEW_PARKED:<n>` for a person, who may adopt it per row or reject
  it; a pair two different runs found `unsure` is `REVIEW_HUMAN:<n>` and
  leaves every agent packet.
- **Reviewed** edges are stamped edges a named person confirmed for that
  pair; a per-row `adopt`, an in-gate row a person confirmed, a `verify`, an
  `annotate` or a `stale --confirm-source` produces one and deletes any
  provenance row.
- **Rejected** pairs are remembered in `onboard.yaml` with `by:
  human:<email>` and never re-proposed; a rejection row without `by:` reads
  as a person's.

Surfaces that show the state: `check` prints `SEEDED:<n>` and
`ADOPTED:<n>|human <h>|agent <a>|auto <m>` (informational); `stale --all`
prints the same two summary lines; `readiness` prints `ADOPTED_UNREVIEWED`,
`AGENT_ADOPTED`, `SEEDED`, `REVIEW_PARKED` and `REVIEW_HUMAN`; `onboard
status` is the one place every ratio lives. Two load rules keep the states
disjoint: a seed with the same `(test, covers)` as any stamped edge is
dropped at load with `SEED_SHADOWED`; an adopted row whose edge no longer
carries a stamp is `ADOPTED_ORPHAN`.

### The autonomous floor

> An autonomous profile, an autonomous branch of a procedure, or `--auto` in
> any profile may seed everything and may adopt a class only when every
> member of the class carries at least one **rule**, **measurement** or
> **reading** origin and its noisy-OR confidence clears
> `agent_review.accept_min` (0.85). A heuristic origin never qualifies
> alone, however high its measured precision. No autonomous path rejects a
> seed, changes a kind or declares an axis. The rule is stated once here
> and enforced in `internal/onboard` (`ADOPT_REFUSED:<pair>|not-autonomous`
> names the missing origin).

| class | origin | headless-adoptable | why |
|---|---|---|---|
| rule | `static:package` | yes | deterministic from the language |
| measurement | `coverage` | yes | the source's lines executed under the test |
| reading | `agent:review`, `agent:author` | yes | something read the test body and answered verifies-or-drives |
| heuristic | `static:invocation`, `static:import`, `observed`, `convention`, `plan`, `prose`, `cochange` | **no** — needs a reading on top | the fact is "executes" or "co-occurs", never "verifies" |

`static:invocation` at 0.90 alone therefore stays seeded in a headless
profile — the 398/400 precision measured on aitasks says the test *runs*
the script, which is exactly the gap the baseline named — and is adopted at
0.99 the moment a `verifies` verdict lands on it. The attended profile keeps
every baseline path (class acceptance with a ten-sample review, per-row
adoption, the in-gate step); in it the agent pre-fills verdicts and a
person confirms.

### The origin table

| origin | class | rule | evidence recorded | measured | confidence |
|---|---|---|---|---|---|
| `static:package` | rule | a `_test.go` file's subject is the non-test files of its own package | — | aitasks_go: deterministic over 85 packages | **1.00** |
| `coverage` | measurement | per-unit runtime coverage, opt-in: coverage.py dynamic contexts, `go test -run <unit> -coverprofile`, LCOV with a test column, a project plugin's `{test, covers}` lines (JaCoCo per-test sessions) | run id | opt-in | 0.95 |
| `agent:review` | reading | an agent read the review packet for the pair and answered `verifies`, naming the assertion line that checks the source; the engine verified that line exists and names the source's stem, its command form, an output path it writes or an exported symbol; attaches only to an existing seed, never creates one | `{verdict, assert_line, rationale, by: agent:<agent-string>, run, packet_sha, test_blob, source_blob, at}` | a prior until calibration measures it (see *The Agent Review Pass*); replaced by `agent_review.measured_confidence` when lower | **0.90** |
| `agent:author` | reading | the agent implementing a task stamps a `(test, source)` pair with both files on its own change surface — the author's claim about the test it just wrote or edited; `AUTHOR_UNCORROBORATED` when the closure holds no relation | `{task, run, by, static: <the closure relation or none>}` | — | **0.90** (0.99 with a static relation) |
| `static:invocation` | heuristic | a literal repo path the test executes or sources (bash: `./.aitask-scripts/x.sh`, `source lib/y.sh`, `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms resolved against every source root) | file:line | aitasks bash: 398 of 400 tests, avg 3 paths | 0.90 |
| `static:import` | heuristic | a direct import of a main-root file (Python through the file's own `sys.path` bootstrap; Kotlin imports; same-package facts excluded) | file:line | aitasks Python: 320 of 320, avg 1; thinking_app: 139 of 339, avg 3 | 0.85 |
| `observed` | heuristic | an `attribute --propose` row from a scored full-run miss | run id | — | 0.70 |
| `convention` | heuristic | `config.yaml conventions:` patterns seeded by `detect` per framework (`test_<x>.sh → aitask_<x>.sh \| lib/<x>.{sh,py}`, `test_<x>.py → <x>.py`, `<Stem>Test.kt → <Stem>.kt`) | pair | aitasks: 52–72 of 400 bash, 62 of 320 Python; thinking_app: 48 Kotlin | 0.60 |
| `plan` | heuristic | an `aiplans/` file naming both paths, through the `aitask_explain_extract_raw_data.sh` cache when present | path | — | 0.50 |
| `prose` | heuristic | a literal path in the unit's header comment or a `# Covers:` line (38 in aitasks) — shown in the packet as `REVIEW_PROSE`, never matched by the annotation scanner | line | — | 0.30 |
| `cochange` | heuristic | `(test, source)` co-occurring in ≥ 2 distinct `(t<id>)` task groups over one `git log --name-status -M --format=%H%x00%s` pass, cached by HEAD sha; per-commit grouping where the convention is absent; `SEED_HISTORY:shallow\|<n>` on a shallow clone | task ids | aitasks: 439 of 600 task commits touch tests and scripts together (2.8 × 2.6, tight), but 336 groups in 400 commits at 1.14 commits each with nothing inside a group saying which covers which; thinking_app: 127 of 400 at 7.2 main files (noisy) | 0.20 + 0.20 × groups, **cap 0.60** |

**Combination.** Noisy-OR, `1 − Π(1 − cᵢ)`. The class-acceptance threshold
`accept_min` is 0.85: `static:invocation` or `static:import` alone qualifies
for a *person's* class adoption, `convention` alone (0.60) does not,
`cochange` (≤ 0.60) never does, and `convention + cochange` (0.84 at the
cap) does not either — corroboration raises a static edge's rank and cannot
manufacture one. A reading composes the same way: `static:invocation +
agent:review` is 0.99, `static:import + agent:review` 0.985, `convention +
agent:review` 0.96, `agent:review` alone 0.90 — and because a verdict only
ever attaches to an existing seed, "alone" means a seed whose other origins
are below the threshold, which the reading lifts on the strength of a read
assertion. Confidence orders the queue and never hides a row; the threshold
governs a person's `--accept-min` and the autonomous floor above is stated
in kinds of evidence first and in the number second.

**Why 0.90 and not 1.0.** A reading is a judgement, not a rule; 0.90 keeps a
lone verdict below `static:package`, above every heuristic, and exactly
where a single static fact plus a reading reaches the top of the queue. The
number is a prior that calibration replaces per repository (below).

**Where the static facts come from.** The static origins read the same
`internal/deps` facts the selector's test-side closure uses — once, from the
blob-keyed cache — and the review packet reads two more facts from the same
cache: the anchor line of each static fact and a source's declared symbols.
Only the *direct* relation is seeded; the deeper closure stays the
selector's distance-2 walk and is never written as an edge.

### Where the reading happens

| site | who reads | what | verdict path | provenance |
|---|---|---|---|---|
| `testmap_fresh` in-gate step (Step 8) | the task's agent; a person confirms in attended profiles | seeds on the test files this task touched — the file is open, the diff is in front of the reader | attended: the agent pre-fills, the person confirms per row (reviewed, `by: human`), overrides, or answers "trust this batch" once (`by: agent`); autonomous: `onboard adopt --agent-verdicts -` | `adopted(<origins>+agent:review <c> by agent:<s>)` |
| pre-review Affected Tests procedure (Step 7) | the task's agent | `UNMAPPED_SOURCE` / `UNANNOTATED_TEST` for the task's own change | `ait testmap annotate --author <test> <source> --task <id> --by <agent-string>`; no known test → `attribute --propose` | `adopted(agent:author 0.90 by agent:<s>)` |
| `aitask-testmap-review` skill (bulk) | the onboarding task's session, a dedicated `ait skillrun` / `ait codeagent` session, or crew agents the crew runner launched | `onboard review --next 20` packets over the seed queue, by class or scope | `onboard adopt --agent-verdicts -` per batch; resumable; the `review` phase in `onboard.yaml` | as above, run id `review-<n>` |

### Helpers before subjects

A closure path is a helper, not a subject, when it is under `helper_roots`
(`tests/lib/**`, `**/testing/**`, `**/src/test/**` for Kotlin,
`**/testdata/**`) or when its fan-in reaches `helper_fanin` (5 % of the
runner's units). A helper gets `test-dep` selection through the closure for
free and, when it globs the tree (`ls tests/*.sh`, `glob.glob`, `rglob`,
`find`, `git ls-files`, `os.walk` — aitasks: `tests/lib/import_isolated.py`,
`board_fixture.py`, `validate_session_hook_fixtures.py`), a proposed
`testmap:reads` line (`SEED_READS:<helper>|<glob>|<evidence>`) written at
level 2 on class acceptance. A hot production module misread as a helper
keeps `test-dep` selection (it over-selects), and every fan-in
reclassification is listed for review. A helper is never a review pair.

### Kinds, members and axes as seeds

`onboard classify` wraps `classify --suggest` with three onboarding signals
— a recorded p95 above `broad_threshold_s` from the first full run, a
source-set or directory convention (`androidTest/`, `androidDeviceTest/`,
`*_live.py`, `*_integration.sh`, `parity/`), a resource named in the file
(tmux, `App.run_test`, `install.sh --dir`, real `.git` use, emulator, docker,
network) — plus `fanout:<n>` above `unit_covers_max`, each printed as the
reason on `CLASSIFY:<test>|<kind>|<reason>`, with areas from the closure's
directories intersected with `code_areas.yaml`. `SEED_BATCH_NO` comes from an
aggregate runner's serial list; `SEED_MEMBER` and `SEED_AXIS` from the grid
heuristic. Kind changes are confirmed individually, never per class and
never by an agent, because a wrong kind changes staleness semantics rather
than selection breadth; a headless run records the rows as `kind_proposals[]`
through `onboard classify --propose` and writes nothing.

### Placement: comment lines only

`onboard adopt` — by class, by row or from a verdict — and `annotate
--author` write through the line-targeted rewriter at a fixed position per
language: bash after the header comment block (after the shebang and the
leading `#` block); Python as `#` lines after the module docstring — the
grammar reads docstring lines, but adoption never writes into one because
that changes `__doc__`; Go after the package clause; Kotlin after the import
block, or inside the member's `testmap:unit` block for a member seed. `git
diff -w --ignore-blank-lines` of an adopted file shows comments only.

Refusals and skips are explicit: `ADOPT_REFUSED:<path>|dirty-foreign` for a
file dirty outside the current task's change surface;
`ADOPT_SKIP:<path>|duplicate` (already annotated — `SEED_SHADOWED` at load);
`ADOPT_SKIP:<path>|unregistered` (no runner lists it);
`ADOPT_SKIP:<path>|no-leader`; `WROTE:<path>` per file and one
`ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>|<by>`. Each written stamp is
`@<date>/<blob10>` at adopt time; a class-, verdict- or author-adopted edge
also gets its `adopted.yaml` row.

### What seeding cannot do

thinking_app's tests resolve imports for 139 of 339 files because
same-package references need no import and "same package is fully connected"
is too coarse to seed. Fixture-driven tests and screen members seed through
`annotate --from-body` and level 3. Sources reached by no origin stay
`UNMAPPED_SOURCE:` until a rule, a waiver, a coverage import or the
authoring agent maps them — the pre-review procedure's `annotate --author`
is the one origin that reaches a coupling no scanner sees, because the
agent that wrote the test knows what it checks; it is limited to the task's
change surface so it maps couplings as they are created, never the backlog.
`onboard status` reports the state ("selecting on 84 % of tests, claiming
on 61 %, of which 75 % by agent") rather than hiding it.
<!-- /section: adoption_model -->
<!-- section: agent_review_pass [dimensions: component_agent_review, component_agent_review_pass, component_onboarding_engine_verbs, component_skill, component_freshness, component_workflow_integration, component_author_annotation, assumption_agent_can_judge_verifies, assumption_agent_reads_verify_vs_drive, assumption_session_agent_is_reviewer, assumption_headless_launch_is_explicit_opt_in, assumption_wrong_positive_claim_only_overselects, assumption_author_annotates_own_surface] -->
## The Agent Review Pass

### The idea

The engine assembles a bounded, digest-stamped **packet** per seeded pair;
an agent reads packets and returns **verdicts**; the engine turns verdicts
into adopted rows or parked marks through the same rewriter and ledger every
other adoption uses. The engine never calls a model; the skill never writes
a test file. A packet is what the agent saw, and its digest is stored beside
the verdict so a later reader can reproduce the judgement's inputs; a
`verifies` verdict also points at the assertion line it rests on, and the
engine checks that the line exists and names the source, so a free-text
judgement always has a machine-checkable anchor.

### The packet

`ait testmap onboard review [--next N] [--class <origin>] [--scope <glob>]
[--ids <csv>] [--json] [--out <dir>] [--calibrate <n>]` selects seeded rows
that carry no verdict for their current test blob from this reader (the
`reviews[]` memo; `REVIEW_MEMO:<skipped>`), groups them by test file so one
file's pairs share a batch (`REVIEW_BATCH:<n>|<pairs>`), and prints:

```
REVIEW_PAIR:<id>|<test>[#member]|<source>|<origins>|<confidence>|<unsure_count>
REVIEW_ANCHOR:<id>|<file:line>                 the static fact's line (invocation / import), when one exists
REVIEW_TEST:<id>|<line>|<flag>|<text>          the anchor ±20 lines, then every line containing an assertion call
                                               (assert_eq / assert_contains / assert / expect / require / t.Fatal* /
                                               assertEquals / shouldBe / grep -q on captured output) flagged `!`;
                                               ceiling agent_review.packet_lines per pair
REVIEW_SOURCE:<id>|<symbol>|<kind>             the source's declared symbols (bash: function names + top-level verbs and the
                                               output tokens the deps scanner extracted; Python: def/class; Go: exported idents;
                                               Kotlin: declarations) — never the body
REVIEW_PROSE:<id>|<line>                       the test's header comment / `# Covers:` lines
REVIEW_MEMBER:<id>|<block>                     for a member seed, the testmap:unit block's own lines
REVIEW_END:<id>|<packet_sha>
```

The packet deliberately excludes the source body: the question is whether
the *test* checks something the source does, and the source's symbol list is
enough to see whether the flagged assertion lines name its behaviour. The
`--json` form is one object per pair with the same fields; `--out <dir>`
writes the same lines to `.aitask-testmap/onboard/<run>/review/<n>.txt`, one
file per batch, for the crew form. `--calibrate <n>` samples `n` pairs with
a ground truth (coverage rows, reviewed edges, human rejections) and marks
them so the intake compares instead of adopting.

### The verdict

Fed to `ait testmap onboard adopt --agent-verdicts - --by <agent-string>
--run <run-id>`, one line per pair (rationale ≤ 160 chars, `|` encoded as
`%7C`):

```
VERDICT:<id>|verifies|<test path:line>|<rationale>     the line is the assertion that checks the source's effect
VERDICT:<id>|drives|-|<rationale>
VERDICT:<id>|unsure|-|<rationale>
```

| verdict | effect | printed |
|---|---|---|
| `verifies` with a valid anchor | `agent:review` added to the row's origins; noisy-OR recomputed; ≥ `accept_min` → adopted through the rewriter with an `adopted.yaml` row `{…, by: agent:<s>, run, rationale, assert_line, packet_sha, test_blob, source_blob}` and the row leaves `seeded.yaml`; below (only when calibration lowered the origin) → stays seeded with the origin recorded | `WROTE:<file>` / `ADOPT_SUMMARY:…\|agent` |
| `verifies` whose anchor fails | the named line is absent, is not `<test path>:<n>`, or names nothing of the source — a homonym stem of another source is `assert_line_names_other` | `VERDICT_INVALID:<id>\|<reason>`; the row is untouched |
| `drives` | the row stays in `seeded.yaml` with the verdict recorded — parked: still selects, out of autonomous adoption, not re-read for these test bytes | `REVIEW_PARKED:<n>` |
| `unsure` | `evidence.agent_review.unsure += 1`; parked; re-packeted once for a different run; at 2 the pair is `REVIEW_HUMAN` and leaves every agent packet | `UNSURE:<test>\|<source>\|<n>` / `REVIEW_HUMAN:<n>` |
| any, `packet_sha` ≠ current | the pair's files changed since the packet was cut | `VERDICT_STALE:<id>` — ignored, re-packeted next batch |
| `--by` not an agent-string | refused: `parse_agent_string` (`lib/agent_string.sh`, `<agent>/<model>`, agents `claudecode\|codex\|opencode`) must accept it; humans use the per-row verbs | exit 64 |
| `--calibrate` run | no writes; `CALIBRATION:agree <a>\|disagree <d>\|<ratio>` appended to `onboard.yaml calibration[]` | as printed |

Every intake also prints `REVIEW_APPLIED:<verifies>|<drives>|<unsure>|<invalid>|<stale>`
and appends each verdict to the `reviews[]` memo `{test, source, verdict,
test_blob, packet_sha, run, by}`; a test whose bytes change is read again.
`--by` defaults to `$AIT_AGENT_STRING` when the launcher exported it. Because
a `by:` value is always resolvable to a model row in `models_<agent>.json`,
the operation `testmap-review` is added to each model's `verified:` table —
the existing per-operation score the framework keeps for `batch-review`,
`pick`, `explain`, `work-report` and `trail` — 0 until measured.

### Calibration

Two measurements feed one number. Passively, every pair a person adopts per
row or rejects is a labelled example, and the intake prints
`REVIEW_AGREEMENT:<agree>/<labelled>` over pairs that carry both a verdict
and a human decision (`readiness` and `onboard status` repeat it, or
`none`). Explicitly, `onboard review --calibrate <n>` samples pairs with a
ground truth — coverage facts where a coverage import exists (a measurement
as ground truth, available headless), else human-reviewed rows and human
rejections — and prints `CALIBRATION:agree <a>|disagree <d>|<ratio>`. When
either measurement covers at least `calibration_min` (30) pairs and its
ratio is below the 0.90 prior, the engine writes
`agent_review.measured_confidence: <ratio>` for this repository; below
`accept_min` (0.85) a lone `agent:review` no longer clears the class
threshold, so verdict adoption stops (`REVIEW_ORIGIN_DEMOTED` printed,
`readiness` says so) and verdicts stay corroboration until agreement
recovers. A repository with neither coverage nor human rows runs on the
prior and prints `CALIBRATION:none`; a project may set
`agent_review.confidence` lower from day one to keep verdicts as
corroboration only.

### The skill `aitask-testmap-review`

`.claude/skills/aitask-testmap-review/` as a profile-aware stub +
`SKILL.md.j2` (resolver key `testmap-review`), one procedure file
`review-batch.md`. Flow: preconditions (`ait testmap version`; `aitestmap/`
present; `agent_review.enabled`) → `onboard review --next <batch> [--class]
[--scope]` → for each pair, read the packet and decide by the rule stated
once in `review-batch.md` — *a test verifies a source when a flagged
assertion line checks an output, a state or an exit status that the source's
symbols produce; it only drives it when the source appears solely in setup,
teardown or as a path argument whose result is never checked; answer
`unsure` rather than guess* — → emit the `VERDICT:` lines, naming the
assertion line for every `verifies` → `onboard adopt --agent-verdicts -
--by <agent-string> --run review-<n>` → read `VERDICT_INVALID` lines and
correct or park them → repeat until the queue is empty, `max_pairs_per_run`
is reached, or (attended) the user stops → commit the rewritten files under
`chore: Onboard testmap — review (t<id>)` when running inside an onboarding
task, else print the commit lines. Attended profile: the agent shows each
batch's verdicts as a table and the user confirms, edits or trusts the
batch; autonomous profile: no prompts. The same procedure is the `review.md`
sub-phase of the onboarding skill's `adopt` phase, so the rule lives in one
file. The skill ships Claude Code first; Codex and OpenCode ports are
follow-up tasks; goldens under `tests/golden/skills/aitask-testmap-review/`.

### Launch surfaces

Every place the reading happens is either the session that already holds
the task or a framework wrapper; the engine launches nothing.

| surface | launch | print mode |
|---|---|---|
| in-gate (`testmap_fresh`) and authoring (pre-review) sites | the task's own session | never — no launch |
| inside an onboarding task | the onboarding skill's session runs `review.md` | never — no launch |
| on demand, one session | `ait skillrun testmap-review [--profile <p>] [--agent-string <a>/<m>] [-- --class <origin>]` — `claude --model <id> "/aitask-testmap-review --profile <p> …"` and the Codex / OpenCode equivalents | never (`ait skillrun` does not use `claude -p`) |
| on demand, scripted | `ait codeagent testmap-review [--headless] [<args>]` — the operation joins `SUPPORTED_OPERATIONS`; interactive by default, `--print` appended only under `--headless`, exactly as `batch-review` | only under `--headless` |
| in parallel | `onboard review --out <dir> --crew <id>` registers one `testmap-review` agent per packet file through `ait crew addwork --type testmap-review --work2do review-batch.md` and prints the `ait crew runner --crew <id>` line for a person to start; the runner launches each agent through `ait codeagent --agent-string <s> invoke raw` under the crew's launch mode; `onboard review --collect <crew-id>` feeds each agent's `_output.md` `VERDICT:` lines to the intake | only when the crew's launch mode is `headless` |

`tests/test_codeagent.sh` pins `testmap-review` interactive-by-default and
`--print` under `--headless`; a grep test asserts no script of this feature
invokes `claude -p` or its equivalents outside `aitask_codeagent.sh`.

### The in-gate site (Step 8)

`aitask-gate-testmap-fresh`'s seeds step becomes: for each `COMMITTED:` /
`TASK:` test file with rows in `seeded.yaml`, run `onboard review --ids
<those rows>` and read the packets — the agent already has the diff open.
Attended: the agent's verdict is pre-filled on each row with its rationale;
the user confirms (a reviewed stamp, `by: human`), overrides, or answers
"trust this batch" once (`by: agent`). Autonomous: `onboard adopt
--agent-verdicts - --by <agent-string> --run <gate-run-id>` — `verifies` rows
are adopted, the rest are parked and left. Either way the stamps ride the
`(t<id>)` commit as before.

### The authoring site (Step 7)

The pre-review Affected Tests procedure's `skip · no_selection` branch in an
autonomous profile: for each `UNMAPPED_SOURCE:<src>`, the agent names the
test unit it wrote or edited for that source in this task and runs `ait
testmap annotate --author <test> <src> --task <id> --by <agent-string>`; the
engine refuses `AUTHOR_REFUSED:<pair>|outside-change-surface` unless both
the test and the source are `COMMITTED:` or `TASK:` rows of the change
surface, refuses an unregistered test (`AUTHOR_REFUSED:<test>|unregistered`),
writes the stamped line through the rewriter and an `adopted.yaml` row with
origin `[agent:author]`, and prints `AUTHOR_STAMPED:<pair>|<static or
none>` or `AUTHOR_UNCORROBORATED:<pair>` when the closure holds no relation
between the two. No known test → `attribute --propose` as in the baseline.
`UNANNOTATED_TEST:<t>` → `annotate --suggest <t>` then `--author` on the
rows the agent confirms from its own knowledge of what it wrote. Attended
profiles keep the baseline's *Annotate now / Propose / Continue* prompt with
the agent's proposed pairs pre-filled; `agent_review.author: false` makes
the autonomous branch propose instead of stamp.

### Budgets

Packet assembly is static (no runner, no model): `onboard review --next 20`
< 300 ms warm on the aitasks shape, `--out` < 1 s per 100 pairs; `--agent-verdicts`
validation < 200 ms per batch. A bulk pass over aitasks' ~720 static seeds
is 36 packets; at `packet_lines: 120` a packet is ≤ 2,400 lines of test
excerpt plus symbol lists — bounded, and the reason the source body is
excluded. `annotate --author` is one rewriter call.
<!-- /section: agent_review_pass -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_onboarding_engine_verbs, component_seeder, component_agent_review_pass, requirements_zero_config_onboarding, requirements_onboarding_existing_tests, requirements_incremental_adoption, requirements_autonomous_loop_closure, requirements_agent_driven_adoption, assumption_test_tools_detectable, assumption_onboarding_is_a_task, assumption_full_run_expressible_per_repo] -->
## Onboarding: Levels × Phases

### The idea

A repository with an existing test tree is brought onto the map by runs of
`/aitask-testmap-onboard`, attended or headless, with nothing typed by
hand. The skill detects the test tools, generates `aitestmap/`, inventories
every unit, seeds edges from the origin table, proposes waivers for the
remainder, enables the gates, and runs the existing full suite once as the
level-0 task's own completion gate. Level 1 adopts the rule and measurement
classes, then reads the heuristic seeds — the skill's own agent reads each
packet — and adopts the `verifies` verdicts; a person adopts what was
parked, or nothing. Later levels classify broad tests (a person confirms
kinds; a headless run proposes them) and scaffold axes. Every phase is
idempotent and resumable from the committed ledger; every level is an
aitask whose writes land under `(t<id>)` commits, are reviewed at Step 8
and are attributed by the change surface.

### Levels and phases

| level | phases in the level's task | what `onboard` writes | what the repository gains | who accepts (attended) | who accepts (headless) |
|---|---|---|---|---|---|
| **0 — runners and universe** | **detect** (`--write`) → **inventory** → **seed** → **waivers** → **enable** → **full_run** (= the task's `tests_pass` at Step 9) | `config.yaml` (`bootstrap_until` today + 90, `require_stamp false`, `concurrency serial`, `completion.mode auto` with `full_run_every`, `agent_review`, `readiness`, `conventions:`, `helper_roots:`), `runners.yaml` (builtins + bindings by glob; a `full: true` suite runner from `test_command` with `fallback_command:`), `resources.yaml` from hints, `registry/areas.yaml` via `areas --import-codemap`, `_scanned.yaml`, `registry/seeded.yaml`, rules and expiring waivers in `registry/<area>.yaml` | the universe (`list`), `ait test --all`, per-unit cost and `last_pass` from the first full run, selection through seeds and the test-file closure, scoring of every later full run; nothing stamped | the runner table (keep / edit command / drop, per runner), `UNREGISTERED` files (bind / `exclude:` / not a test), the config table once — the policy and its cadence shown | nothing to ask — the level proposal is printed |
| **1 — edges** | **adopt** — `--auto` over rule and measurement classes → **review** (`onboard review --next 20`, read and answered by the skill's agent; the crew form optional) → `--calibrate` where a ground truth exists → for the parked remainder, per evidence class (`--class static:invocation`, …) or per area (`--scope <glob> --batch 50`) for a person → then incrementally inside `testmap_fresh` | verdicts on `seeded.yaml` rows and `onboard.yaml reviews[]`; stamped `testmap:covers` blocks; `registry/adopted.yaml` rows `{by: auto \| agent:<s> \| human:<email>}`; rows leave `seeded.yaml`; parked rows stay; `phases.review` counts; `calibration[]` | freshness and the evidence join apply; `stale` reports; `testmap_check` is meaningful; `UNMAPPED_SOURCE` shrinks; `REVIEW_AGREEMENT` starts accumulating | per class with the agent's verdicts pre-filled (accept all / review a sample of ten / edit rows / skip), or per row | **the agent**: rule and measurement classes by `--auto`; every other class through the review loop until the queue is empty or `max_pairs_per_run`; parked rows listed |
| **2 — kinds** | **classify** (per batch of 20, kind changes individually) → `scan --apply` | `testmap:kind integration\|e2e\|device` + `testmap:area` / `testmap:scope` on broad tests, `testmap:reads` on tree-scanning helpers, `testmap:batch no` from serial lists, `needs:` bindings from resource hints, `resources.yaml` entries | scoped rows, the suite budget, `broad_after_unit`, enforced do-not-overlap (aitasks: `repo-git-index` mutex, worktree scope) | per kind, individually, by a person | **proposes only**: `onboard classify --propose` records the rows in `kind_proposals[]`; nothing applied; `readiness` prints `KIND_PROPOSALS:<n>` |
| **3 — product** | **scaffold** (`--axes`, `--runner <builtin> --as <name>`, `--members`) → `annotate --from-body` per member | `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` with `describe`/`run` delegating to the builtin and `list` printing `SCAFFOLD_TODO` until filled (check reports it), `testmap:unit` member blocks | variant selection | the maintainer, with the skill | not entered |
| **finish** | a phase of whichever level task the maintainer names last, or `finish --auto` at the end of a headless level-1 task | `require_stamp: true`; `check --strict`; `bootstrap_until` shortened | enforcement | `onboard status` green: no pending phase, `check` clean, every remaining seed under the user-set threshold (default 0) or parked with a verdict | the same test; `FINISH:auto\|parked <n>\|review_human <m>` says how many pairs a person still owns |

The skill's preflight (engine present, ledger state) precedes the level-0
phases and is not itself a ledger phase.

### Two views that agree by construction

`readiness` derives `LEVEL:<0-3>` from what exists — `runners.yaml` → 0, any
stamped `_scanned` edge → 1, any `_scoped` row or `reads` → 2, `axes.yaml` →
3 — and prints `NEXT:<the phase or level that raises it>`. `onboard status`
prints the ledger's `ONBOARD_NEXT:<phase>`, the seed queue per origin and
per verdict, the adopted-unreviewed count split by `by`, tests-with-any-edge
and sources-with-any-edge ratios, the oldest pending seed's age, the
rejections count, `REVIEW_PARKED`, `REVIEW_HUMAN`, `KIND_PROPOSALS`,
`AUTHOR_UNCORROBORATED`, `REVIEW_AGREEMENT` and `CALIBRATION`. `LEVEL` is a
property of the tree, `ONBOARD_NEXT` a property of the run.

### Invocation and task shape

`/aitask-testmap-onboard [--level <n>] [--policy selected] [--no-task]`.

**Preconditions.** `ait testmap version` (absent → stop with the `ait setup`
hint). An `aitestmap/` with a finished ledger → *refresh mode* (seed limited
to units newer than `adopted.yaml`'s last row, same flow). An unfinished
ledger → re-enter at `ONBOARD_NEXT:` (a partial `review` phase re-enters the
loop where it stopped).

**Survey.** Read-only: `onboard detect` and `onboard seed --json --out
.aitask-testmap/onboard/<run>/seed.json`, then the level proposal —
frameworks and counts, edges per evidence class with three samples each,
helpers found and which glob, kind candidates with reasons, `UNLISTED`
files, `RUNNER_SCRIPT_NEEDED` if any, the config writes including the
completion policy and its cadence.

**The level task.** The skill creates the level's aitask
(`aitask_create.sh --batch --name "testmap onboarding level <n>" --type chore
--labels testing,testmap`), attaches the seed dump with `ait attach`, claims
it with `aitask_pick_own.sh`, writes the id and level into `onboard.yaml`,
and continues into task-workflow honouring the profile (the
`explore_auto_continue` shape). The plan is the phase list. At Step 7 each
phase ends with `chore: Onboard testmap — <phase> (t<id>)` through
`aitask_task_commit.sh` with paths named, so `aitask_change_surface.sh`
attributes the files and a resumed session re-enters at `ONBOARD_NEXT:`.
Step 8 reviews the annotation diff and dispatches `testmap_fresh` (nothing
`STALE` yet — every stamp is today's). Step 9's `tests_pass` runs `./ait test
--gate` — under `auto` and a not-yet-admissible map that is the whole suite
— which for the level-0 task is the **first full run**: every unit's
`last_pass` anchored, `PREDICTION_SCORED:none` because nothing was predicted
yet, `costs --update` folded. The archive commits registry, annotations and
config under one `(t<id>)`.

**After the level-0 run** (the `full_run` phase's procedure): `costs
--gate-timeout tests_pass` → `GATE_TIMEOUT_SUGGESTED:tests_pass|<s>` =
`max(600, 3 × p95)` written into the project's `gates.yaml`; `readiness` →
`LEVEL` / `NEXT`; the next level's task created with `depends:` on this one.

**Variants.** `--no-task` writes without committing and prints the commit
lines, for a repository that forbids tasks on the code branch. The
`--policy selected` re-entry — for a project that chose `completion.mode:
full` and wants a person in the flip — runs `readiness` and only on
`READINESS_DECISION:ADMISSIBLE` writes `completion.mode: selected` and
`run_gate_admission.approved_by {who, at, statement}` in one `ait:` commit;
`NOT_YET` prints the unmet criteria and stops.

**Headless (`remote`) profile.** Level 0 in full (every write is a registry
file or a seed; `completion.mode: auto` and the cadence are `detect
--write`'s values). Level 1 in full: `onboard adopt --auto` over the rule
and measurement classes, then the review loop — the skill's agent reads
every packet in its own session and answers, the intake adopts the
`verifies` pairs with `by: agent:<s>` — to the `max_pairs_per_run` budget
(a partial phase is re-entered on the next run), `--calibrate` where a
ground truth exists, then `finish --auto` when `check` is clean, leaving
parked rows selecting and listed. Level 2 records `kind_proposals[]` and
writes no kind; level 3 does not run. The policy flip needs no re-entry:
`auto` flips itself on the first admissible completion run of any later
task. No prompts — the level proposal, the verdict counts and the parked
rows are printed, not asked; the level-1 task's Step-8 diff is where a
person sees the stamps if they look. The skill exports
`AIT_PROFILE_HEADLESS=1` around the engine so `reject` and `classify
--apply` refuse.

### Detection, per target repository

| repository | `onboard detect` | level 0 runners and resources | full run (`completion.mode: auto`, not yet admissible) | levels 1–3 |
|---|---|---|---|---|
| **aitasks** | `FRAMEWORK:bash-file\|tests/**/test_*.sh\|400`, `FRAMEWORK:pytest\|tests/test_*.py\|320`, `AGGREGATE_RUNNER:tests/run_all_python_tests.sh`, `SERIAL_LIST:…\|4`, `RESOURCE_HINT:repo-git-index\|~40 tests`, `SUITE_CANDIDATE:test_command\|null`, `UNIVERSE:720 UNLISTED:0` | `bash-file`, `pytest` (`testmap:batch no` on the four carve-out modules, pinned by extending `test_serial_carveout_doc_drift.sh`); `resources.yaml`: `repo-git-index {kind: mutex, scope: worktree}` — the "invocation policy, not a guarantee" comment in `run_all_python_tests.sh` becomes enforced | `ait test --all` (no suite command existed; `tests_pass` gates for the first time); `fallback_command` derived: `for f in tests/test_*.sh; do bash "$f"; done && bash tests/run_all_python_tests.sh` | 1: 398 + 320 static edges, 52–72 corroborated by convention; helpers `tests/lib/` (27; 3 `reads`); the review loop over ~718 pairs in 36 packets, headless-safe — a bash test that runs `aitask_x.sh` and asserts on its stdout token is `verifies`, a test that sources `asserts.sh` is a helper and never a pair, a test that runs `aitask_create.sh` only to build a fixture for `aitask_archive.sh` is `drives` on the first (parked, still selecting) and `verifies` on the second; ~718 adopted at 0.99 / 0.985, the 2 fixture-only tests stay seeded; 2: ~40 tmux / live-TUI / real-install tests → `integration` over codemap areas (a person; proposed headless); 3: `tests/golden/` as a skill × profile × agent axis |
| **thinking_app** | gradle-class 374 classes, `RUNNER_SCRIPT_NEEDED:grid` (screen × matrix), `SUITE_CANDIDATE:test_command\|verify-active`, `RESOURCE_HINT:heavy-run` (exit-75 lock script) | `gradle-class` builtin until the project runner exists; `verify-active {unit: suite, full: true, children: …, fallback_command: tools/verification/screenshot-tests.sh verify-active}`; `heavy-run {kind: admission, exec: heavy-run-lock.sh}` | `verify-active` once (`screen-matrix` and `gradle-class` `subsumed_by: verify-active`) — identical to today's `test_command`, and what `auto` keeps running until `ADMISSIBLE` | 1: 139 `static:import` files through review; JaCoCo per-test sessions when enabled (0.95, adoptable by class); same-package pairs reach the map through `agent:author` as tasks touch them — level 1 partial by construction, stated by `onboard status`; 3: `onboard scaffold --runner gradle-class --as screen-matrix` → `tools/verification/testmap_runner.sh` whose `list` the project fills from the manifests; `axes.yaml`; `testmap:unit` blocks in `ScreenFixtures.kt` |
| **thinking_backend** | bash-file 22 + pytest 18 under `scripts/tests/`, `SUITE_CANDIDATE:verify_build\|scripts/tests/run_script_tests.sh` | `bash-file`, `pytest` with `cwd:`; the skill asks: keep `verify_build` (it also enforces a shellcheck baseline) and add `test_command: ./ait test` — the default | `ait test --all` over the 40 units; `build_verified` still runs the script | 1: static edges into `scripts/server/**` and `db_target.py`, 40 units through review (2 packets); 2: `golden/` fixtures as `reads` |
| **aitasks_go** | go-test: 85 packages, 55 `_test.go` files, `Makefile test`, `parity/run_parity.sh` (tmux + venv) | `go-test` (per package, `-run`, `-json`); `parity` as `suite`, kind e2e, resource `tmux` | `go test ./...` = `ait test --all` | 1 fully automatic and headless-safe with no reading: `static:package` is a rule; `go test -coverprofile` per unit adds `coverage` rows for cross-package edges, a measurement |
| **aitasks_mobile** | kmp-sourceset: `commonTest` 36 (dbaccess 2, domain 25, shared 9), `androidHostTest` 1, `androidDeviceTest` 3 | `gradle-class` × modules on `:<module>:jvmTest` / `testDebugUnitTest`; `device` on `connectedDebugAndroidTest` with `emulator {kind: allocator}` | unit kinds only; device kind under `device_policy: filter_by_resource` — the source set is a runner/kind distinction, not an axis | 1: Kotlin import closure (`domain/src/commonMain/**`), 36 + 1 unit classes through review; the 3 device classes stay `device` kind (a kind, not adopted); JaCoCo where the Gradle modules enable it |

In every row the user typed nothing; the skill showed the table and asked
for one confirmation per runner, one per kind change and one per config
write; evidence classes were adopted by rule, by measurement or by verdict,
with a person asked only about the parked remainder — and in the headless
profile not even that.
<!-- /section: onboarding -->
<!-- section: run_surface [dimensions: component_test_entrypoint, component_test_front_verb, component_agent_brief, component_agent_instructions, component_auto_policy, requirements_zero_config_entrypoint, requirements_agent_run_surface, requirements_agent_instructions_seeded, assumption_task_resolvable_from_session, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_instruction_block_is_read, assumption_change_surface_is_intake] -->
## The Run Surface

### The idea

An agent learns one verb once. `ait test` is correct at every stage of a
repository's adoption: before onboarding it runs the project's
`test_command` and prints the onboarding hint; with a registry it selects,
schedules and runs by itself, resolving the task from the session; in
completion mode it is what the `tests_pass` gate executes; in advisory mode
it can never block. Project specifics are never prose an agent has to find —
they are `ait test --howto`'s computed output.

### Forms

```
ait test                       selected tests for the task you are implementing, each with a reason
ait test <path|id>...          named units: a listed test file, file#member, file#member@variant, a directory of tests,
                               or a SOURCE path — treated as a one-file TASK: change set, so `ait test lib/foo.py` runs what covers it
ait test --all                 the whole registry: every runner's list, full: true suites once, subsumed_by runners skipped
ait test --task <id>           override task resolution
ait test --gate                completion mode — what tests_pass runs; implied by $AIT_GATE_TASK_ID
ait test --advisory --task <id> [--explain]
                               the pre-review form: VERDICT:/REASON:/DETAIL:/LOG: lines, exit 0/1/2/3, every absence a printed skip
ait test --explain             the selection with reasons, groups and estimated cost; runs nothing
ait test --howto [--md]        this project's runners, kinds, resources, full gate, axes, completion policy and cadence, LEVEL, docs, notes
ait test --tokens              select --format tokens (thinking_app: `| xargs tools/verification/screenshot-tests.sh preview`)
ait test --dirty               no task: every dirty path as a TASK: row; explicit, printed as INTAKE:dirty, never the default
ait test --fresh-only          exclude stale-marked units (interactive only)
ait test --budget-s <n>        interactive suite budget override
ait test --json                one object instead of lines
```

### Resolution, in order

1. **Registry present?** No `aitestmap/config.yaml` → `TESTMAP_ABSENT:run
   /aitask-testmap-onboard to enable change-aware selection`, then delegate
   to `aitask_run_project_command.sh test_command` (with `--task-id` when a
   task resolved), exiting with its verdict; `--howto` prints the same line
   plus the `test_command`. This is what makes "always `./ait test`" true on
   day one. Advisory mode: `VERDICT:skip REASON:registry_absent`.
2. **Engine present?** Through the shim's strict handshake. Absent:
   interactive → `ENGINE_MISSING:<path>|run 'ait setup' or set
   AIT_TESTMAP_BIN`, exit 3; completion → `completion.engine_absent`:
   `error` (default, exit 3 → verifier `error`) or `fallback_command` (run
   the `full: true` suite runner's `fallback_command:`, print
   `MODE:fallback`, exit per the command); advisory → `VERDICT:skip
   REASON:testmap_absent`.
3. **Mode.** `--gate` or `$AIT_GATE_TASK_ID` → `completion`; `--advisory` →
   `advisory`; else `interactive`. Printed as `MODE:`.
4. **Task.** `--task` > `$AIT_GATE_TASK_ID` > the current worktree's branch
   if it matches `aitask/t<id>_*` (task-workflow's naming) > the locks this
   user holds on this host (`aitask_lock.sh --list-mine`, a listing verb
   added to the lock script): exactly one → that task; several →
   `AMBIGUOUS_TASK:<ids>`, exit 64 unless `--task`; none → `TASK:none`.
5. **Intake.** Named paths → units by registry lookup, or a source path → a
   synthetic `TASK:<path>` change set; `--all` → every runner's `list`; a
   resolved task → `aitask_change_surface.sh list <id>` piped to `--changes
   -` (`UNKNOWN:` refuses — advisory: `VERDICT:skip REASON:unknown_paths`
   naming them; `aitasks/`, `aiplans/`, `.aitask-data/` excluded); `--dirty`
   → `git status --porcelain` paths as `TASK:` rows; nothing → `NO_TASK:`
   with the three ways out, exit 64 (advisory: 3).
6. **Policy (completion only).** `completion.mode`. `full` → `run --all`
   with `subsumed_by` honoured. `selected` → run `readiness` first: every
   criterion met → the task selection with `deferred: run`; any unmet →
   `POLICY_DEMOTED:selected->full|<criterion>` and run full. `auto` → run
   `readiness` and read `costs/policy.yaml`: not `ADMISSIBLE` → full with
   `POLICY:auto|full|not_yet:<criterion>`; admissible for the first time →
   `POLICY_FLIPPED:auto->selected|engine:readiness@<run>`, `approved_by`
   written to `costs/policy.yaml` and committed by the front; a cadence
   trigger due (`selected_since_full ≥ full_run_every.tasks`, the selection
   estimate ≥ `selection_ratio_above × full p95`, or `last_full_run.at`
   older than `days`) → full with `POLICY:auto|full|cadence:<trigger>`;
   otherwise the selection with `POLICY:auto|selected|next_full_in:<n>`; a
   later unmet criterion → `POLICY_DEMOTED:auto->full|<criterion>` and
   `approved_by` cleared. `on_empty_selection: skip` → exit 2 → the opted-in
   `tests_pass` records `skip`, never `pass` — except that a cadence full
   run ignores `on_empty_selection` and runs.
7. **Run.** The engine `test` composite: `select --include-stale
   [--budget-s] [--format …] --run <run-id>` → `schedule` → `run`; prints
   `SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`, one
   `UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked
   rows with their reasons (a seeded edge reads
   `edge(seeded:static:invocation,cochange)`, an adopted one `edge(annotation)
   adopted(static:invocation+agent:review 0.99 by agent:claudecode/opus5)`),
   `DEFERRED:` in interactive mode only, the waves, results per id,
   `RESULT:`. The front prefixes the run id (`test-`, `gate-`, `full-`; see
   *Cost ledger*).
8. **New-test and new-source notices.** `UNANNOTATED_TEST:<path>` +
   `HINT:./ait testmap annotate --suggest <path>` for a listed test in the
   change surface with no `testmap:` block, no seed and no adopted row;
   `UNMAPPED_SOURCE:<path>` for a changed source with no edge, seed, rule or
   waiver. Informational in interactive mode; the pre-review procedure
   offers the fix (and takes it autonomously through `annotate --author`);
   in completion mode `testmap_check` owns enforcement.

### Output and exit contract

```
MODE:interactive|completion|advisory|fallback   TASK:<id>|none   INTAKE:change-surface|dirty|all|named
POLICY:full|selected|auto|<sub-state…>   SELECTED:<units>|<groups>|<est_s>|<seeded>|<adopted>   RUN:<run-id>
ESCALATE:… DEFERRED:… UNMAPPED_SOURCE:… UNANNOTATED_TEST:… HINT:…       (engine line classes pass through)
POLICY_FLIPPED:… POLICY_DEMOTED:… POLICY_WRITE:…                          (completion under auto)
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
pre-review procedure cannot disagree with the Step-9 path about an exit
code. It writes the engine's full output to the log, appends nothing to any
gate ledger, and is the one deliberate exception to "a missing engine is an
error": an *advisory* run must never block a task the way a declared gate
legitimately does; the skip is printed, never silent.

### The two environment variables

`run_command_gate` exports `AIT_GATE_TASK_ID=<task-id>` and
`AIT_GATE_RUN_ID=<run-id>` around the command; `aitask_run_project_command.sh
--task-id <id>` exports the first. That is how `./ait test` knows it is a
completion run and for which task in all three call sites (the `tests_pass`
verifier, the legacy Step-9 helper, `aitask-qa`) with no argument in
`test_command`; the run id names the gate run in
`.aitask-testmap/runs/<run-id>/` so a ledger row and a gate log share an
identifier, and it is the run the policy ledger's `approved_by` names.

### `ait test --howto` (engine verb `brief`)

For thinking_app after level 3, on this host class:

```
TESTMAP:onboarded|since 2026-09-16|LEVEL:3|POLICY:auto|next full in 3 tasks|seeds pending 412 (parked 96, review_human 4)|adopted 618 (agent 540, human 47, auto 31)
RUNNER:gradle-class|unit|374 classes|screenshot-tests.sh unit-tests --tests <class>|heavy-run
RUNNER:screen-matrix|unit (variant, axis matrix)|49 members, 297 variants over 10 matrices|screenshot-tests.sh unit-tests --tests <class>.<method>|heavy-run
RUNNER:verify-active|suite (full)|1|screenshot-tests.sh verify-active|heavy-run|subsumes screen-matrix,gradle-class
FULL_GATE:verify-active|p95 1180s|every 5 tasks / >= 60 % / 7 d|tests_pass timeout 3540s
GATE:testmap_fresh (procedure, before commit) -> testmap_check -> tests_pass = ./ait test --gate (auto: selected now, 14 units)
AGENT_REVIEW:enabled|0.90|calibration 47/50 (coverage)|agreement 41/44
VERBS:./ait test | ./ait test <path>... | ./ait test --all | ./ait test --howto
AXES:matrix|facets locale,direction,geometry|10 values
RESOURCE:heavy-run|admission (tools/verification/heavy-run-lock.sh)|refusal = exit 75 -> deferred to run deadline
NEW_TEST:./ait testmap annotate --suggest <path>
DOCS:aidocs/testing/rendering-verification.md
DOCS:aidocs/testing/change-aware-verification.md
NOTES:A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
NOTES:Never run ./gradlew test directly - the harness owns the heavy-run slot and the run id.
```

Everything above `DOCS:` is computed from the registry, the ledger,
`config.yaml` and `costs/policy.yaml`; `KIND_PROPOSALS:<n>` and
`REVIEW_HUMAN:<n>` appear when non-zero; `DOCS:` and `NOTES:` are what the
`enable` phase asked the maintainer for — the judgement calls a registry
cannot hold, kept to ten lines and reached through one verb. `--md` renders
the same as markdown; `ONBOARD_NEXT:` appears while a ledger is unfinished;
< 100 ms warm.

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
`test_command`). The author path is taught by the procedure that uses it,
not by the seed, because it is a workflow act rather than a run form.
`tests/test_agent_instructions.sh` gains one case asserting the heading in
all four rendered surfaces through a real `install.sh --dir`. This
repository's own hand-maintained `CLAUDE.md` (sentinel present, no markers)
is edited by its level-0 onboarding task to point at `./ait test` and keep
the runner-specific notes (`run_all_python_tests.sh` lanes, the `PIPESTATUS`
caveat) as background.
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_workflow_integration, component_gates, component_completion_policy, component_auto_policy, component_qa_integration, component_agent_review_pass, component_author_annotation, requirements_workflow_seam, requirements_workflow_seam_is_data, requirements_gate_enforcement, assumption_gate_exit_contract_reused] -->
## The Workflow Seam and the One Completion Gate

### The idea

The change-aware run is reached from the existing workflows without a new
workflow and without a new gate. The seam is data — project config,
profiles, gate declarations, the completion policy, two environment
variables, one `codeagent` operation and three model-table keys — plus one
paragraph for the implementation loop, one procedure for the pre-review run,
and one new skill for bulk review. The two autonomous branches that
previously only *proposed* now *act* through engine verbs. Every seam
degrades to a printed skip where the engine or the registry is absent.

### The concrete edits

| where | change | kind |
|---|---|---|
| `task-workflow/SKILL.md.j2` Step 7, after *Follow the approved plan* | one paragraph: "**Test loop.** Run `./ait test` after each meaningful change — it selects from this task's change surface and prints a reason per unit. `UNANNOTATED_TEST:<path>` → `./ait testmap annotate --suggest <path>`; `UNMAPPED_SOURCE:<path>` → map it (`/aitask-testmap`). Do not invoke the project's test tool directly; `./ait test <path>` runs one unit." | prose, every profile; goldens regenerated |
| `task-workflow/SKILL.md.j2` Step 7, once before Step 8 | the **pre-review affected run**: the Affected Tests Procedure (`affected-tests.md`) under `{% if profile.affected_tests is not defined or profile.affected_tests != 'off' %}` | procedure |
| `task-workflow/affected-tests.md` | `./ait test --advisory --task <id> [--explain]` with the `set -e` capture form; the branch table below; the autonomous branch of `no_selection` / `UNANNOTATED_TEST` runs `ait testmap annotate --author … --by <agent-string>`; the verdict line recorded in the plan's Final Implementation Notes, never in the gate ledger | procedure file |
| `task-workflow/profiles.md`, `remote.yaml` | profile key `affected_tests: run\|show\|off` (default `run`; `default.yaml` and `fast.yaml` omit it; `remote.yaml` sets `run`); no key for agent review — `agent_review.enabled` and `agent_review.author` are project config, because the map's provenance must not depend on who ran the task | data + one doc row |
| Step 8 | the `testmap_fresh` procedure-gate dispatch before the change summary; inside the gate, the seeds step reads packets (`onboard review --ids`) for each `COMMITTED:`/`TASK:` test file with rows in `seeded.yaml`: attended pre-fill / confirm / override / trust-batch; autonomous `onboard adopt --agent-verdicts -` — accepted rows ride the same `(t<id>)` commit | one step |
| Step 9 verify block (`./ait gates run`) | none — the orchestrator runs `testmap_check` → `tests_pass` (= `./ait test --gate`) | none |
| Step 9 no-gates branch (`build-verification.md`, `verify_build`) | none in prose; a project reaches the test lane by declaring `tests_pass`, which onboarding writes into `default_gates` | data |
| `build-verification.md` | one branch: verdict `error` with reason `command_refused` / `command_errored` → host refused resources or the framework could not run; do not fix code, do not record a pass, report and re-run later | prose |
| `lib/gate_verifier_lib.sh` `run_project_command_key()` | opted-in keys: 75 → `error`/3/`command_refused`, 3 → `error`/3/`command_errored`; exports `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` around the command; docblock table updated — the single canonical statement | code; `tests/test_gate_verifiers.sh` extended |
| `aitask_run_project_command.sh` | `--task-id` also exports `AIT_GATE_TASK_ID`; inherits the new rows | code |
| `gates_reference.yaml` → `gates.yaml` sync | + `testmap_fresh` (procedure, verifier `aitask-gate-testmap-fresh`), + `testmap_check` (`unlocks: [tests_pass]`, `max_retries: 0`, `timeout_seconds: 120`); `tests_pass` unchanged in the reference, `timeout_seconds` tuned per project from the ledger | data |
| project profiles | `default_gates` += `tests_pass`, `testmap_check`, `testmap_fresh` (the onboarding `enable` phase, confirmed; `rendered_gates` when present) | data |
| `aitask_gate_testmap_check.sh` | the machine verifier; rows `SEEDED:<n>`, `ADOPTED:<n>\|human <h>\|agent <a>\|auto <m>` (informational), `UNMAPPED_SOURCE:<path>` (reported during bootstrap, fails under `--strict` past `bootstrap_until`) | code |
| `ait test --gate` (`aitask_test.sh` + `test` composite) | the `auto` resolution: `readiness` + `costs/policy.yaml` + the three cadence triggers → the `POLICY:` line; the engine's `POLICY_WRITE:` committed under `ait: testmap policy <flip\|full-run> (t<id>)` | code |
| `aitask_codeagent.sh` | operation `testmap-review` (`/aitask-testmap-review`), interactive by default, `--print` only under `--headless`; `list-models` shows `verified.testmap-review` | code |
| `seed/models_{claudecode,codex,opencode}.json` | `verified.testmap-review` key per model (0 until measured); `aitask-add-model` seeds it | data |
| `aitask-testmap-review/` | **new** profile-aware skill; `review-batch.md`; goldens; Codex / OpenCode ports as follow-ups | skill |
| `aitask-testmap-onboard/adopt.md`, `review.md`, `finish.md` | rule → measurement → reading order; `review.md` as the reading sub-phase; the headless row; `finish --auto` printing parked and `review_human` counts | procedure |
| `aitestmap/config.yaml` (written by `detect --write`) | `completion.mode: auto`, `full_run_every`, `agent_review`, `readiness` blocks; confirmed in the attended config table | data |
| `aitask-qa/test-discovery.md` 3a–3c | with `aitestmap/`: `ait testmap explain --sources <changed files> --format table` → Source / Test / Reason / Status with `Covered`, `Covered (adopted by human\|agent\|auto)`, `Covered (seeded)`, `GAP` (= `UNMAPPED_SOURCE`); else the legacy convention scan | prose |
| `aitask-qa/test-execution.md` 4a–4d | 4a: the configured `./ait test` through `aitask_run_project_command.sh test_command --task-id <id>`; 4b: named units via `ait test <path>`; 4c: `REFUSED (host resources)` row, treated as `SKIP` in the health score; 4d: coverage from registry edges (seeded and agent-adopted rows counted as coverage that exists) | prose |
| `aitask-pickrem`, `aitask-pickweb`, `aitask-resume` | inherit through task-workflow and `build-verification.md`; pickweb (no `ait setup`) sees `VERDICT:skip REASON:testmap_absent` at Step 7 and the `engine_absent` policy at completion | none |
| `aitask_setup.sh` | `report_testmap_state()` after `install_engine_binary()`: `TESTMAP:engine-missing\|absent\|bootstrapping\|<next>\|onboarded`, hint `run /aitask-testmap-onboard` on `absent`; setup never onboards | code; `test_install_engine_binary.sh` asserts each state |
| `ait` dispatcher | `test)` → `aitask_test.sh`; help line | code |
| permission touchpoints (5) | `aitask_test.sh` (its `--advisory` form is the only helper); `tests/test_touchpoint_count_contract.sh` re-pinned | config |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a test-framework detector" (closed list, evidence line, fixture repo, `UNLISTED` behaviour) and "Adding a seed origin" (confidence row, class column rule / measurement / reading / heuristic, evidence field, the autonomous-floor rule, fixture) | doc |
| `aitask_skill_verify.sh` + goldens | task-workflow, aitask-qa, the onboarding and review stubs, the rewritten gate skill, every profile × agent | test |

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
| `skip` · `no_selection` | display the `UNMAPPED_SOURCE:` paths; **offer** (`AskUserQuestion`, non-skippable in attended profiles), with the agent's proposed pairs pre-filled: *Annotate as author* (default — `ait testmap annotate --author <test> <source> --task <id> --by <agent-string>` for each unmapped source and the test on this change surface that checks it; stamped, `adopted.yaml {origin agent:author, by agent:<s>, task, run}`, rides the `(t<id>)` commit) · *Annotate by hand* (`/aitask-testmap` → `annotate` / a rule) · *Propose for review* (`attribute --propose`, lands in `seeded.yaml` with origin `observed`) · *Continue unmapped*. Autonomous profiles take *Annotate as author* for every unmapped source that a test on the change surface checks (`AUTHOR_REFUSED:outside-change-surface` for anything else) and *Continue unmapped* for the rest, printing `AUTHOR_UNCORROBORATED` pairs; `agent_review.author: false` restores the propose branch |
| `UNANNOTATED_TEST` on any verdict | a test this task added or edited with no `testmap:` block, seed or adopted row: `annotate --suggest <test>`, then the same offer with `annotate --author <test> <sources>` naming the sources on the change surface the test checks; autonomous profiles annotate |
| `skip` · `unknown_paths` | the scope prompt `aitask-gate-docs-updated` already uses: include / subset / exclude; autonomous profiles exclude and log |
| `skip` · `admission_refused` | print `at_detail` (the host refused the heavy slot until the deadline); continue — nothing failed |
| `skip` · `testmap_absent` / `registry_absent` | one line; continue — not onboarded, or this host has no engine |

Why a procedure exists when the loop is a paragraph and the gate is
`tests_pass`: the advisory run is the one task-scoped selection guaranteed
to happen in every profile, so it guarantees a prediction record exists for
the completion run to score (`PREDICTION_SCORED` /
`PREDICTION_FALSE_NEGATIVES` into `costs/predictions.yaml`); `readiness`
counts those rows toward `min_scored_full_runs`. A repository whose tasks
never run the advisory form may never accumulate scored predictions and
could never flip its policy. The verdict line (`- **Affected tests:** pass
(14 units, est 41 s) — log …`) goes into the plan's Final Implementation
Notes and never into the gate ledger: no double record, no `record_gates`
guard needed.

### Gates

```yaml
  testmap_fresh:
    type: machine
    kind: procedure
    description: "Coverage annotations on this task's changed sources reviewed, re-stamped, and touched test files' seeds read and adopted or parked"
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
  # tests_pass: unchanged in the reference (blocks_dependents: true, max_retries: 1, timeout_seconds: 600).
  # In an onboarded project test_command is `./ait test`, gate_command_exit_contract lists test_command,
  # and the project's gates.yaml carries timeout_seconds from `costs --gate-timeout`.
```

There is no separate selection gate. Everything such a gate would own has a
home: its verifier logic is `ait test --gate`; `blocks_dependents` and
`max_retries: 1` are `tests_pass`'s own; its timeout is the per-project
`tests_pass.timeout_seconds` from the ledger; its exit mapping (0/1/2/75/64
→ 0/1/2/3/3) is the shared lib's new rows; `testmap_check` unlocks
`tests_pass`; `--include-stale` is applied by the composite; deferred rows
run under `completion.deferred: run`. An `unlocks:` target absent from a
task's active set is ignored, so `testmap_check` declared alone is linear as
before, and a project whose completion invariant is a full suite keeps
`tests_pass` exactly as today with `completion.mode: full`.
`run_gate_admission` and `readiness` gate the **policy flip** rather than a
second gate's declaration: recorded by a human in `config.yaml` under
`selected`, or by the engine in `costs/policy.yaml` under `auto`, so the
committed declaration and the engine's approval ledger are different files
and a reader can tell them apart; the engine never enables a gate and never
writes a profile.

### Completion policy

Two flips exist. The human one (`completion.mode: full` plus
`/aitask-testmap-onboard --policy selected` after `ADMISSIBLE`,
`approved_by {who, at, statement}` recorded in `config.yaml`) is unchanged.
The engine's one (`completion.mode: auto`, the value `detect --write`
writes) flips on the first admissible completion run, records `approved_by
{who: engine:readiness@<run>, at, mode: auto, statement}` in
`costs/policy.yaml`, and is bounded by the cadence in
`completion.full_run_every`: every `tasks`-th selected completion since the
last full run, any selection whose estimate reaches `selection_ratio_above`
of the full-suite p95, and any completion `days` after the last full run is
a full run that scores the window of predictions behind it. The demotion is
automatic and loud in both; the policy can only fail toward running more; a
cadence full run is never skipped by `on_empty_selection` or a demotion.
thinking_app's rule — full `verify-active` as the completion gate until
admissible — is preserved exactly by `auto` until `ADMISSIBLE` and by `full`
forever; the project chooses in `config.yaml`, and `--howto` prints which
(a 1,180 s full run every 5 tasks is the price of the selection on the
other 4). The completion flow itself is drawn under *Data Flow*.

### Verification of the seam

`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine replaying scripted exits, in all
three modes and every `REASON:`, plus the `auto` matrix (`ADMISSIBLE` × each
cadence trigger × `NOT_YET` × the first-flip record, the `POLICY_WRITE:`
commit, the demotion clearing `approved_by`); `tests/test_gate_verifiers.sh`
covers 75 and the env export; engine tests for `onboard review` and the
intake: packet shape and assertion flagging per language, every verdict
branch, every `VERDICT_INVALID` reason (pair not in the packet, anchor line
absent, anchor naming nothing of the source, `assert_line_names_other`),
`VERDICT_STALE`, the `--by` grammar refusal, the memo skip, the `unsure`
escalation, agreement and demotion at the threshold both ways, calibration
against a coverage fixture, `--auto` refusing a heuristic class,
`annotate --author` refusing outside the change surface, and window scoring
attributing a miss to the right task; `tests/test_codeagent.sh` pins
`testmap-review` interactive-by-default; `tests/test_agent_instructions.sh`
gains the Running-Tests case; `tests/test_testmap_onboard_ledger.sh` (resume
from each phase including a partial `review`, idempotent re-run, `--no-task`,
one task per level with `depends:`); engine tests per detector, per seed
origin on fixture repos with synthetic `(t<id>)` histories, the fan-in
reclassification, golden files for block placement per language, every
`ADOPT_*` refusal branch; the task-workflow, onboarding, review and gate
skill goldens; `tests/test_touchpoint_count_contract.sh`;
`tests/test_install_engine_binary.sh` for each `TESTMAP:` state.
<!-- /section: workflow_seam -->
<!-- section: components [dimensions: component_*] -->
## Components

Components are grouped by layer. *Core* components are the engine, map,
selection and scheduling machinery; *adoption layer* components are the
onboarding, run-surface and workflow additions. Every component names its
package or file, its verbs or keys, and how it is tested. Each heading
carries its source: *(inherited from n011)*, *(inherited from n012)*,
*(inherited from n011 and n012)* where both parents state it identically or
their statements were joined, or *(new: introduced to bridge n011 and
n012)*; these tags are the only place provenance appears outside *Conflict
Resolutions*.

**Engine and packaging**

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(core; inherited from n011 and n012)*

`engine/cmd/ait-testmap` with packages
`internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}`
plus `internal/seed`, `internal/onboard` and `internal/brief`. Go 1.26 with a
pinned toolchain, `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w
-X version/commit/contract"`; dependencies `gopkg.in/yaml.v3`,
`bmatcuk/doublestar/v4`, `golang.org/x/sync` only; stdlib `flag` verb table,
`syscall.Flock`, `os/exec` git; line-protocol stdout, `--json`, per-verb exit
contracts. It never writes `aitasks/`, `aiplans/`, `.aitask-data/`, a gate
ledger, `project_config.yaml`, `gates.yaml`, profiles or `CLAUDE.md`; never
invokes `aitask_*.sh`; never needs its own install root; never launches a
code agent, never reads `models_<agent>.json` beyond validating an
agent-string's grammar, and never decides a verdict — `onboard review`
assembles packets and `onboard adopt --agent-verdicts` consumes lines.
Fixture repositories in `t.TempDir()` carry synthetic `(t<id>)` histories
for the co-change origin, one fixture per detect shape (bash-only, pytest,
go, gradle, gradle-per-source-set), one per opaque-scanner branch, one per
verdict branch and one per packet language.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(core; inherited from n011 and n012)*

Version, commit and contract are embedded; `version --json` prints
`ENGINE:<path>`; a newer contract in any registry file is refused with
`CONTRACT_MISMATCH` (`seeded.yaml`, `adopted.yaml`, `onboard.yaml` and
`costs/policy.yaml` carry their own `contract:` field and are refused the
same way; the contract stays 1 — `by:`, `verdict:` and the review fields are
additive fields an older engine ignores). Pools are capped at 8. The verb
table is `test`, `select`, `schedule`, `run`, `scan`, `check`, `stale`,
`annotate` (+ `--author`), `verify`, `explain`, `axes`, `areas`, `classify`,
`costs` (+ `--gate-timeout`), `score`, `attribute`, `readiness`, `brief`,
`onboard {detect, inventory, seed, review, classify, adopt, reject, scaffold,
status, finish}`, `version`. Budgets pinned by `go test -bench` fixtures
with a 2× regression rule: `select` < 200 ms warm on the aitasks shape and
< 250 ms with axis expansion on the thinking_app shape, `scan` / `check` /
`stale --task` < 300 ms, `stale --all` < 2 s, cold `select` < 1.5 s, `brief`
< 100 ms warm, `onboard seed` static + convention < 2 s and co-change < 5 s
over 600 commits, `onboard status` < 200 ms, `onboard review --next 20` <
300 ms warm and `--out` < 1 s per 100 pairs, `--agent-verdicts` validation
< 200 ms per batch (the reading between them is the agent's time, not the
engine's), the cadence check inside `ait test --gate` < 50 ms. `detect` is
excluded from the latency table: it runs once per onboarding, executes `git
log` and every runner's `list`, and is on no gate path.
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(core; inherited from n011 and n012)*

`engine/build.sh` is the single build and matrix command. The release
`engine` job (`actions/setup-go` from `engine/go.mod`, `go vet`, `go test`,
`build.sh all`) produces `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
`ait-testmap_<V>_SHA256SUMS.txt`, attached by both `action-gh-release` steps
with `release needs: [plan, engine]`; the VERSION-matches-tag guard is
unchanged. `engine-check.yml` runs gofmt, vet, test and the 2× bench rule on
push / PR for `engine/**`. `lib/platform_detect.sh` maps `uname`. The shim's
strict handshake: `AIT_TESTMAP_BIN` (with an override notice) > `AIT_ENGINE=dev`
slot at `$AITASKS_HOME/engine/dev/` requiring `<V>-dev+<sha>` >
`$AITASKS_HOME/engine/v<V>/` requiring `== VERSION` > `ENGINE_MISSING:<path>`
exit 3 with the repair hint. Tests: `test_testmap_shim.sh` (with an
`AITASKS_HOME` host), `test_platform_detect.sh`, `test_aitasks_home.sh`.
Docs: `aidocs/framework/go_engine.md`, a `CLAUDE.md` Engine block, a
`packaging_strategy.md` paragraph naming `~/.aitasks/engine/`.
`release-packaging.yml` and nfpm `arch: all` are untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade and state report *(core + adoption layer; inherited from n011 and n012)*

`install_engine_binary()` in `aitask_setup.sh`, reached by `ait setup` and by
`ait upgrade` through `install.sh`'s `--source-only` path: source order
`--local-engine` > exact-version release asset > `--engine-from-source` >
`ENGINE_MISSING` warning; `sha256sum -c` / `shasum -a 256` with a `.sha256`
sidecar short-circuit; atomic install to `$AITASKS_HOME/engine/v<V>/`;
`version --json` must echo `<V>`; `.dev`-marked binaries are never
overwritten without `--force-engine`; `--no-testmap` / `AIT_TESTMAP_FETCH=0`
print `TESTMAP_BINARY:skipped`; `HOME_LEGACY:` hint when legacy tenants
exist; `.aitask-testmap/` gitignored by setup; `aitask_engine.sh` with `ait
engine build|test|cross|prune|home [--migrate]`. After it,
`report_testmap_state()` prints `TESTMAP:engine-missing` (binary absent),
`TESTMAP:absent` with `run /aitask-testmap-onboard` (no `aitestmap/`),
`TESTMAP:bootstrapping|<next phase>` (an unfinished ledger) or
`TESTMAP:onboarded`; setup reports and never onboards. The re-inserted
instructions block carries the Running Tests section. `aitask_test.sh` is a
framework script shipped in the tarball like every `aitask_*.sh` — nothing
to install. `tests/test_install_engine_binary.sh`, through a real
`install.sh --dir --local-engine`, asserts the `$AITASKS_HOME` path and each
`TESTMAP:` state.
<!-- /section: component_engine_packaging -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(core; inherited from n011 and n012)*

`.aitask-scripts/lib/aitasks_home.sh` exports
`AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`, `aitasks_engine_dir
<version|dev>` and `$AITASKS_HOME/.home.lock`; sourced by the shim,
`install_engine_binary`, `aitask_engine.sh`, the verifiers and
`aitask_test.sh`; never falls back to `~/.aitask/`. `ait setup` creates
`$AITASKS_HOME/engine/` (0755) and prints `AITASKS_HOME:<path>` beside the
venv line so both roots are visible; `ait engine prune` walks only
`$AITASKS_HOME/engine/v*/`. `test_aitasks_home.sh` pins the default, the env
override, and that no framework script of this feature names `~/.aitask/`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(core; inherited from n011 and n012)*

`ait engine home` prints `HOME_ROOT:<path>`, `HOME_LEGACY:<path>|<tenants>`,
`HOME_SYMLINK:none|<target>` and `HOME_NEXT:<what --migrate would do>`. `ait
engine home --migrate` runs under `flock $AITASKS_HOME/.home.lock`; refuses
and reports `no-legacy-root`, `already-migrated`, `foreign-symlink:<target>`,
`cross-device` or `unknown-entry:<name>`; moves each present entry of the
known set `{venv, pypy_venv, python, bin, uv, dev_tier, update_check,
engine}` with a same-device `mv`, `rmdir`s the emptied legacy root and leaves
`ln -s $AITASKS_HOME ~/.aitask` behind; prints `HOME_MIGRATED:<n>` or
`HOME_SKIPPED:<reason>`. In this release `ait setup` only prints the
`HOME_LEGACY:` hint; flipping the default (reserving `--no-home-migration` /
`AIT_HOME_MIGRATE=0`) is a named follow-up admitted when
`tests/test_aitasks_home.sh`, through a real `install.sh --dir`, covers fresh
install, migration with a working venv and PyPy venv afterwards, idempotent
re-run, a hostile pre-existing symlink, cross-device refusal and the
`AITASKS_HOME` override, and the 18 doc files naming `~/.aitask` are updated.
<!-- /section: component_framework_home -->

**The map: registry, annotations, scanners, axes**

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(core + adoption layer; inherited from n011 and n012)*

`internal/registry` merges `aitestmap/registry/*.yaml` plus `axes.yaml` into
eight tables: the six core tables (edges, scopes, areas, rules, waivers,
axes) with unit ids `<path>[#<member>][@<variant>]`, each member's
`variants:` list from `_scanned.yaml`, `owns:` routing by glob for edges and
rules and by area name for hand-declared scopes, observed axis sources merged
widen-only, deterministic sorted writes only on change, and the check rules
(`STALE_PATH`, `UNSTAMPED` past bootstrap under `require_stamp`,
`DEAD_SCOPE`, `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`,
`UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED`, `UNMAPPED_ARTIFACT`,
`KIND_MISMATCH|CONVERT_TO_SUITE`, `CONTRACT_MISMATCH`); plus **seeds** from
`registry/seeded.yaml` (rows `{test[#member], covers, origin[], confidence,
evidence{}, proposed_at, verdict?}` — a row may carry
`evidence.agent_review{}`) and **adopted** from `registry/adopted.yaml`
(rows `{test, source, origin[], confidence, adopted_at, task, by:
human:<email>|agent:<agent-string>|auto, run?, rationale?, assert_line?,
packet_sha?, test_blob?, source_blob?}`). `onboard.yaml`'s `rejections[]`
rows are `{test, source, reason, by, run?}` with the load rule that an absent
`by:` reads as a person's; `reviews[]`, `kind_proposals[]` and
`calibration[]` are read for `status` and `readiness`. Load rules: a seed
whose `(test, covers)` also exists as any stamped edge is dropped with
`SEED_SHADOWED` (reported by `check`); an adopted row whose edge no longer
carries a stamp is `ADOPTED_ORPHAN`. Write routing: `onboard seed` →
`seeded.yaml`; `onboard adopt --agent-verdicts` → `seeded.yaml` (a `verifies`
row removed; a `drives` / `unsure` verdict recorded on the row) +
`adopted.yaml` + the test file through the rewriter + `onboard.yaml
reviews[]`; `onboard adopt --class` / `--auto` / per row → `seeded.yaml` (row
removed) + `adopted.yaml` (class and `--auto` adoption only) + the test
file; `annotate --author` → the test file + `adopted.yaml`; `onboard reject`
→ `seeded.yaml` (row removed) + `onboard.yaml` (rejection recorded so the
seeder never re-proposes it); `attribute --propose` → `seeded.yaml`; a human
re-stamp (`verify`, `annotate`, `stale --confirm-source`, per-row `adopt`) →
`adopted.yaml` (row removed). `config.yaml` gains `completion:` (with
`full_run_every:`), `agent_review:`, `readiness:`, `conventions:`,
`helper_roots:`, `helper_fanin:`, `exclude:` (never listed, never
`UNREGISTERED`), `docs:`, `notes:` (≤ 10 lines) and `broad_threshold_s`;
`costs/policy.yaml` is read by the front and written by the engine. Golden
tests pin the two new table merges, the `by:` merge, the absent-`by:` rule,
the shadow rule and the id grammar.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(core; inherited from n011 and n012)*

`internal/annot`, grammar v3: `testmap:unit <Member>` opens a member block
that owns every following `testmap:` line until the next `testmap:unit` or
end of file (a file-level block precedes the first unit); `testmap:kind`,
`testmap:covers <path> @<date>/<blob10>`, `testmap:area`, `testmap:scope`,
`testmap:trigger`, `testmap:reads <glob>` (helper files only), `testmap:axis
<axis>.<facet>=<value>`, `testmap:reviewed`, `runner` / `needs` / `batch` —
per comment leader, with Python module docstrings read; unknown keys are
refused with a line number. The line-targeted rewriter edits stamps by
`(file, line, current text)` and refuses on `REWRITE_CONFLICT`; `annotate
--from-body` seeds covers for a member from the Kotlin scanner's symbol
resolution of the block's own lines; both generated files are produced from
every runner's `list` output. Three callers of the rewriter beyond
`verify` / `stale --confirm*`, none a new writer: `onboard adopt` (by class,
by row, or from a `verifies` verdict), and `annotate --author <test>
<source> --task <id> --by <agent-string>`, which checks both files are on
the task's change surface (`AUTHOR_REFUSED:<pair>|outside-change-surface`
otherwise), inserts the stamped line and writes the `adopted.yaml` row with
origin `[agent:author]`. All insert `testmap:covers` lines at the fixed
per-language position (bash after the shebang and leading `#` block; Python
as `#` lines after the module docstring, never inside it; Go after the
package clause; Kotlin after the import block, or inside the member's
`testmap:unit` block for a member seed), each stamped `@<date>/<blob10>` at
adopt time, one file rewritten per adopted item. Existing `# Covers:` prose
headers are shown in packets as `REVIEW_PROSE` lines and read by the
`prose` origin at 0.30, never matched by the annotation scanner and never
rewritten.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(core; inherited from n011 and n012)*

`internal/deps`: built-in bash, python, go (`go list -deps -json` cached by
`go.sum` digest), kotlin with the opaque contract over main and test roots,
Gradle module graph; executable plugins under `aitestmap/scanners/` speaking
one JSON line per file `{file, deps, opaque?, reads?}`; the opt-in
`android-res` symbol scanner; forward deps cached per source blob under
`${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` and
inverted in memory. The bash scanner's literal-invocation facts (a test that
runs `./.aitask-scripts/x.sh` or sources `lib/y.sh`, including `$SCRIPT_DIR`-
and `$PROJECT_DIR`-relative forms resolved against every source root), the
python and kotlin scanners' direct imports of a main-root file (Python through
the file's own `sys.path` bootstrap) and the go scanner's package membership
are exposed to `internal/seed` as the `static:invocation`, `static:import`
and `static:package` origins — same scan, same cache, read once. Two more
read-only facts are exposed to `internal/onboard review` from the same
cache: the anchor line (file:line) of each static fact, and a source's
declared symbols (bash function names, top-level verbs and the output
tokens the scanner extracted; Python `def`/`class`; Go exported
identifiers; Kotlin declarations) for the `REVIEW_SOURCE` lines — never a
source body. The deeper closure stays the selector's distance-2 walk and is
never seeded as an edge.
<!-- /section: component_dependency_scanners -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(core; inherited from n011 and n012)*

`internal/axes`, read by registry, selector, runner and cost.
`aitestmap/axes.yaml` declares axes `{name, facets[], values{value: {facet:
v}}, sources{facet: {v: [globs]}}}`; a runner's `describe` names the axis its
variants live on and a `token_format`; `list` emits `<unit>@<value>` ids. The
selector joins changed paths to facet values through `sources` and selects
the variants carrying them (reason `axis(<axis>.<facet>=<v>) <- <path>`) plus
plain units carrying `testmap:axis` for that value, or every variant of a
unit reached by an edge, dep, rule or test-dep; `--axis <axis>.<facet>=<v>`
forces a facet. Costs, `last_pass`, evidence and score are per variant;
`check` enforces `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT` and `UNCOVERED_VALUE`;
observed sources widen only. The engine holds no project axis — the first
consumer is thinking_app's `matrix` axis with facets locale / direction /
geometry over its 10 recording matrices. Level-3 `onboard scaffold --axes`
writes only the skeleton the maintainer fills; the grid heuristic proposes, a
person declares (design decision 17).
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(core; inherited from n011 and n012)*

`ait testmap axes --list` prints every declared axis with its facets, values
and the variant count each value has in `list`; `--check` runs the axis
rules (`DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`); `--explain
<path>` prints `AXIS:<axis>.<facet>|<value or ->|<why>` per facet for one file
— which glob matched, or that no source is declared — so a maintainer sees
where a file lands before anything is trusted. `-` means no axis hit, which
selects every variant.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(core; inherited from n011 and n012)*

There is no generated cell table: the runner's `list` verb is the
enumeration surface, and `scan --apply` persists its output as the
`variants:` list on each member row of `_scanned.yaml` (49 rows with at most
ten values for thinking_app), so `select` never executes a runner and only
`scan` and `check` call `list`. Two-way reconciliation is `UNCOVERED_VALUE:<axis>|<value>`
(a declared value no runner lists) and `UNMAPPED_ARTIFACT:<path>|<runner>` (a
file matching a runner's declared `artifact_glob:` that no listed id's
artifact column claims), both failing `check --strict` after bootstrap.
`onboard detect`'s `UNIVERSE:` is the same count taken before runners exist;
`onboard inventory` is the first consumer of `UNREGISTERED:` rows as a to-do
list.
<!-- /section: component_cell_enumeration -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(core; inherited from n011 and n012)*

`registry/areas.yaml` plus `areas:` blocks in hand files, seedable via `areas
--import-codemap`; `_scoped.yaml` rows `{test, kind, runner, areas, globs,
triggers, reads_from, needs, reviewed_at, line}`; `owns:` by area name for
hand-declared rows; the distance-1 join, kind ranking, the suite budget
(`suite_budget_s` default 600) with `DEFERRED` lines and budget-exempt
triggers; check rules including `DEAD_SCOPE` and
`KIND_MISMATCH|CONVERT_TO_SUITE`; `ait testmap areas`; missing-trigger /
area-too-narrow in `attribute`; a rule may `select:` a scoped test or a
member by name. `classify --suggest` gains the three onboarding signals (a
recorded p95 above `broad_threshold_s`, a source-set or directory convention,
a resource declaration or use in the file) plus `fanout:<n>` above
`unit_covers_max`, each printed as the reason on the
`CLASSIFY:<test>|<kind>|<reason>` line; attended, the skill confirms per
batch of 20 with kind changes confirmed individually and `onboard classify
--apply` writes the confirmed rows' source lines at level 2; headless,
`onboard classify --propose` records the rows in `onboard.yaml
kind_proposals[]` and applies nothing, because a wrong kind changes
staleness semantics and no run evidence checks it.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling and staleness policy *(core; inherited from n011 and n012)*

Kind `integration|e2e|device` selects the scoped association form;
`broad_after_unit: true` waves run scoped rows only after a green unit wave;
`device_policy: filter_by_resource` by default; scoped rows are exempt from
per-edit digest staleness, with `STALE_AREA` as the evidence-based drift
signal and `REVIEW_DUE` as an opt-in cadence; `attribute` widens areas by
evidence; `covers` on a scoped row is allowed for digest-stamped fixture
pins; a suite row marked `full: true` with a `children:` post-processor
anchors registered ids on every run; variant-bearing units are unit kind,
never area-scoped, and ride the unit wave with admission-holding invocations
ordered last. `completion.deferred: run` means the suite budget applies to
the interactive loop only.
<!-- /section: component_broad_test_scopes -->

**Freshness and evidence**

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(core; inherited from n011 and n012)*

Per-edge `@<date>/<blob10>` stamps, scoped to the member block, written only
by `verify`, `annotate` (including `--author`, which also writes the
`adopted.yaml` row), `stale --confirm*` and `onboard adopt` (by class — a
person's or `--auto` over a rule or measurement class — by row, or from a
`verifies` verdict); variants carry no stamp; `last_pass` per id;
`bootstrap_until`, `require_stamp`, `flake_threshold`. The `testmap_fresh`
procedure gate is dispatched by the existing procedure-gate block before the
change summary so rewrites ride the `(t<id>)` commit; it is not a git hook
and not a code-agent hook. Its seeds step reads engine-cut packets for the
test files this task touched: attended, the agent pre-fills `verifies` /
`drives` / `unsure` per row with the rationale and a person confirms,
overrides or trusts the batch; autonomous, the agent's verdicts are the
adoption through `onboard adopt --agent-verdicts -` — the stamp then rides
the same commit as the test edit, which is the moment the reader has the
file open and the claim is cheapest to check. An adopted stamp is a stamp
like any other; the gate handles it identically, with the `adopted(... by
<who>)` display as context.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(core; inherited from n011 and n012)*

`internal/stale`: `stale --task --changes - | --all` with the
`SURFACE` / `EDGES` / `STALE_PATH` / `STALE` / `EVIDENCED` / `UNSTAMPED` /
`STALE_AREA` / `REVIEW_DUE` / `UNKNOWN` / `DISPLAY` / `DECISION` line classes
and `%25` / `%7C` encoding; a `STALE` row on a unit with variants carries a
trailing `|<unevidenced variants>` field; `--all` adds `CHECK_STRUCTURAL:<n>`;
content states exit 0, `--strict` exits 1 on `STALE_PATH`; compares blob
digests of the working tree only, consults the per-variant evidence join,
adds rename hints and culprit task ids from `git log --name-status -M` when
history is reachable; mutates stamps via `--confirm`, `--confirm-source`,
`--confirm-evidenced`, `--retarget` through the rewriter with a re-scan of
touched files. Seeded edges are excluded from every class; `stale --all`
adds `SEEDED:<n>` and `ADOPTED:<n>|human <h>|agent <a>|auto <m>` summary
lines beside `CHECK_STRUCTURAL`; a `STALE` or `EVIDENCED` row whose edge has
an `adopted.yaml` row carries `adopted(<origins> <confidence> by <who>)` in
its `DISPLAY` line so the procedure gate knows whether it is confirming a
class-accepted, an agent-accepted, an author-claimed or a per-pair reviewed
claim.
<!-- /section: component_staleness_tool -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(core; inherited from n011 and n012)*

`internal/stale` + `internal/gitx`, reading `internal/cost`: for every edge
whose stamped blob differs from the current blob, collect `last_pass` shas
per reached variant from the local ledger and committed costs (any host
class), drop candidates from invocations with a cause or ids over the flake
threshold, keep shas that are ancestors of `HEAD`, and run one `git ls-tree`
per distinct sha; an edge is `EVIDENCED` when every reached variant has a sha
whose source object id equals the current blob, otherwise `STALE` with the
unevidenced variants listed. It never rewrites — `stale --confirm-evidenced`
is the explicit re-stamp and the only bulk confirmation an autonomous profile
may run; evidence removes nags and never reviews a claim. Seeded edges are
not joined (no stamp to heal); adopted edges — human, agent or auto — are
joined like any stamped edge; the level-0 task's first full run is what
first populates the anchors it reads.
<!-- /section: component_evidence_join -->

**Selection, scheduling, running, cost**

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(core; inherited from n011 and n012)*

`internal/selectr` + `internal/changesurface`: line-protocol intake refusing
`UNKNOWN:`, the graded walk with select / implies / escalate rules, variant
expansion and axis join, test-dep at distance 1, `ESCALATE` on opaque files,
scoped join, kind-then-cost ranking, invocation groups, stale marks from
digest compare plus the per-variant evidence join, `--include-stale`, the
suite budget with `DEFERRED` lines and budget-exempt triggers and reads, cut
knobs including `--axis`, `--format lines|json|tokens`, the prediction
record, `explain`. A seeded edge — parked or not — is walked exactly like an
annotation edge at distance 1 with reason `edge(seeded:<origins>)` and never
contributes a stale mark; an adopted edge is an annotation edge whose reason
carries `adopted(<origins> <confidence> by <who>)` —
`adopted(static:invocation+agent:review 0.99 by agent:claudecode/opus5)`,
`adopted(agent:author 0.90 by agent:…)`, `adopted(coverage 0.95 by auto)`.
`explain --sources <path>... --format table` prints the reverse view (every
unit reaching each source with its reason and provenance — `Covered`,
`Covered (adopted by human|agent|auto)`, `Covered (seeded)` — or
`UNMAPPED_SOURCE`) as the table `aitask-qa`'s test discovery consumes. The
`test` composite prints one `SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`
line and `UNMAPPED_SOURCE:<path>` lines before the ranked rows so the front
can build its verdict without parsing the rows; `ait test <source path>`
reaches it as a one-row `TASK:` change set.
<!-- /section: component_selector -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(core; inherited from n011 and n012)*

`internal/sched`: resource kinds `mutex` / `semaphore` / `admission` /
`allocator`, scopes `host` / `worktree` / `run`, `acquired_by` planning;
`flock(2)` slot files taken in canonical order; admission exec with 75
deferral and backoff to the run deadline; allocator exec with signal-safe
release; goroutines under `errgroup`; batching (variants of one runner and
resource set batch into one invocation per `group_by` group, so
thinking_app's whole selection is one Gradle run holding one heavy-run
slot); `broad_after_unit` waves with variant-bearing units in the unit wave
and, within a wave, invocations holding an admission resource ordered last;
`concurrency: serial|parallel` defaulting to serial at bootstrap with
`--serial` / `--parallel` overrides; the schedule report and its check half.
`detect`'s `RESOURCE_HINT` rows become `resources.yaml` entries the
scheduler already understands (aitasks: `repo-git-index` mutex, worktree
scope); a refusal at the deadline is exit 75 (advisory:
`skip:admission_refused`).
<!-- /section: component_scheduler_resources -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(core; inherited from n011 and n012)*

`internal/runner`: `describe` (`unit file|class|method|variant|suite`,
`axis:`, `batch`, `needs`, `group_by:`, `token_format:`, `filter_scope:`,
`full:`, `children:`, `artifact_glob:`), `list` as TSV `<id> <kind>
<lowering> [<artifact>]` with member and variant ids, `run --manifest` with
ids, lowerings and groups, `results.jsonl` per id with optional child rows
under a suite parent, `runner.json` with per-group overhead rows,
first-match bindings and per-test override, the `builtin:` scheme with
`command:` / `cwd:` overrides and shadow-by-name, batching by `(runner, group,
resource set, batch flag)`, per-unit timeouts, `units_expected` /
`units_reported` reconciliation with zero-reported-some-expected and
no-registered-id as mechanism failures, exit contract `0/1/2/75` plus `64`.
Repository keys added: `subsumed_by: <suite>` on a runner whose units are
the child rows of a `full: true` suite runner, so `run --all` executes the
suite once and never the subsumed runner beside it (thinking_app:
`screen-matrix` and `gradle-class` subsumed by `verify-active`); and
`fallback_command:` on a suite runner — the pre-onboarding `test_command` or
a detect-derived equivalent — which `ait test --gate` runs when the engine is
absent and `completion.engine_absent` is `fallback_command`. `onboard
scaffold --runner <builtin> --as <name>` emits `aitestmap/runners/<name>.sh`
whose `describe` and `run` exec the builtin and whose `list` prints
`SCAFFOLD_TODO` until the project fills it, which `check` reports.
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(core; inherited from n011 and n012)*

Built into the binary as `ait-testmap runner <name>`: `bash-file`; `pytest`
(junitxml; `testmap:batch no` honoured, the serial carve-out pinned by
extending `tests/test_serial_carveout_doc_drift.sh`); `go-test` (per-file
`-run` regex, `-json`); `gradle-class` (`--tests <lowering>` batch, one
invocation per `group_by` group, JUnit XML inverted to ids through the list
table, zero-match trap as a mechanism failure); `suite` (any command as one
unit, optional child rows from a `children:` post-processor); `device`
(allocator handle); `command:` / `cwd:` overrides; shadow-by-name with
`explain` showing which won; `engine-test` over `engine/`. thinking_app's
`tools/verification/testmap_runner.sh` (`screen-matrix`: `list` from the
two membership manifests plus `matrix_classes` with an artifact column, `run`
through `screenshot-tests.sh unit-tests --tests`) and `verify-active` as a
`full: true` suite runner whose child rows come from
`lib/screenshot-diff-set.sh`. `onboard detect` seeds the repository:
`bash-file` for `tests/**/test_*.sh`; `pytest` for `test_*.py` / `*_test.py`
(an aggregate runner script's serial carve-out list becomes `testmap:batch
no` candidates); `go-test` per package from `go list`; `gradle-class` for
`src/test/**/*.kt|java`; a `kmp-sourceset` detector mapping `commonTest` /
`androidHostTest` to gradle-class unit runners (`:<module>:jvmTest`,
`testDebugUnitTest`) and `androidDeviceTest` to the device runner
(`connectedDebugAndroidTest`, `needs: [emulator]`); and a `full: true` suite
runner named `full` wrapping `project_config.yaml test_command` (or
`verify_build` only when the user names it as the suite) whose `children:`
post-processor is a builtin inverting pytest junitxml, bash-file names from
the per-file exit and `go test -json` events to registered ids, and whose
`fallback_command:` is the previous `test_command` — so the existing full
gate anchors evidence from day one without a project script. The
`bash-file` builtin gains `list --invocations`, printing the literal repo
paths a test references, for the seeder's `static:invocation` origin.
<!-- /section: component_reference_runners -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(core; inherited from n011 and n012)*

`internal/cost`: Welford per `(id, host class)` where id may be a variant,
with P² p95 and last; the per-repo ledger `.aitask-testmap/ledger.jsonl` with
`run_id` / `id` / `status` / `duration_ms` / `head_sha` per result and
`{run_id, group, overhead_ms, units_reported}` per invocation; `costs
--update` folds both into `aitestmap/costs/<hostclass>.yaml` and truncates;
`last_pass {sha, at, run_id}` per id and a flake rate against
`flake_threshold`; the estimate for a selection is the sum over invocation
groups of `overhead.p95` plus the p95 of each selected id, reported per kind;
`costs/predictions.yaml` holds the last 200 scored full runs. **Run-id
prefixes**, stated here once: `test-` for interactive and advisory runs,
`gate-` for completion runs, `full-` for `--all`, `review-` for bulk review
runs (which write no cost rows); the first three write ordinary rows and
feed cost and evidence exactly like any run, and the ledger says which
surface produced a row. The `SELECTED:` estimate is the same per-group sum
the budget uses and the number `selection_ratio_above` compares to the
newest full run's p95 on this host class. `costs --gate-timeout tests_pass`
prints `GATE_TIMEOUT_SUGGESTED:<gate>|<seconds>` = `max(600, 3 × p95 of the
newest full run on this host class)`, which the onboarding `full_run` phase
writes into the project's `gates.yaml` after the first measured full run.
`aitestmap/costs/policy.yaml` `{last_full_run: {run_id, at, task, sha},
selected_since_full: <n>, approved_by: {who, at, mode, statement}}` is the
engine's policy ledger under `auto`, written by `ait test --gate` and
committed beside the other engine-written cost files so `config.yaml` stays
human-authored.
<!-- /section: component_cost_ledger -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(core; inherited from n011 and n012)*

`internal/feedback`: `score` runs automatically after `run --all`, after a
cadence-triggered full completion run and after a `full: true` suite run,
printing `PREDICTION_SCORED` / `PREDICTION_FALSE_NEGATIVES:<n>` /
`PREDICTION_MISSED:<id>|<task>` and appending to `costs/predictions.yaml`;
after a cadence full run it scores every `costs/predictions.yaml` row since
the last full run, attributing each miss to the earliest task in the window
whose change surface reaches the failing unit through an edge, a dep or a
scoped row (culprit task ids from `git log --name-status -M` when history is
reachable). For each missed test and each changed source in the run's
surface whose pair sits in `onboard.yaml rejections[]`, it prints
`REJECTION_CONTRADICTED:<test>|<source>|<run>` and keeps the row — evidence
removes nags and never overrules a person. `attribute` records missing-edge
/ test-wrong / source-wrong, missing-axis-source (widen only), missing-trigger
/ area-too-narrow; a decision may be `propose` (default in autonomous
profiles), which writes the row to `seeded.yaml` with origin `observed`
(0.70) and the run id as evidence instead of to `observed.yaml`, so
autonomous runs grow the review queue and never the accepted map.
`readiness` prints `LEVEL:<0-3>`, `NEXT:<the phase or level that raises
it>`, `ADOPTED_UNREVIEWED:<n>|<ratio of covers edges>`,
`AGENT_ADOPTED:<n>|<ratio>`, `SEEDED:<n>`, `REVIEW_PARKED:<n>`,
`REVIEW_HUMAN:<n>`, `KIND_PROPOSALS:<n>`, `AUTHOR_UNCORROBORATED:<n>`,
`REVIEW_AGREEMENT:<agree>/<labelled>|none`, `CALIBRATION:<ratio>|none`,
`POLICY:<mode>|<what ait test --gate would run now>[|next_full_in:<n>]` and
`CADENCE:<last full run>|<selected completions since>|<days since>`; its
criteria are `min_scored_full_runs`, `max_false_negatives`,
`require_opaque_proofs`, `min_full_runs_since_map_change` (default 3: clean
scored full runs since the last bulk adoption or `--author` write) and, under
`auto`, `cadence_declared` (all three `full_run_every` rules present and
sane: `tasks ≥ 2`, `0 < selection_ratio_above ≤ 1`, `days ≥ 1`) with
`approved_by` read `met|engine` from `costs/policy.yaml` once the flip is
recorded. `readiness` still enables nothing, never launches an agent, and
`ait test --gate` is the only writer of the flip.
<!-- /section: component_feedback_tools -->
**Adoption and onboarding**

<!-- section: component_adoption_ledger [dimensions: component_adoption_ledger, component_registry_loader, component_seeder, component_onboarding_engine_verbs, component_agent_review_pass] -->
### Adoption ledger: seeded → adopted → reviewed *(adoption layer; inherited from n011 and n012)*

The three-file state of a machine-proposed edge and the rules that move it —
`registry/seeded.yaml` (select-only, no stamp, invisible to `stale`, never
`--strict`, `SEEDED:<n>` on `check` / `stale --all` / `readiness`; a row may
carry a verdict — `verifies` until it adopts, `drives` or `unsure` as a
parked mark that keeps the row selecting and out of autonomous adoption),
`registry/adopted.yaml` (provenance of a stamped edge accepted by evidence
class, by a `verifies` verdict or by an author claim, with `by:
human:<email>|agent:<agent-string>|auto`; `adopted(<origins> <confidence> by
<who>)` on `stale` and `explain` rows; `ADOPTED_UNREVIEWED:<n>|<ratio>` and
`AGENT_ADOPTED:<n>|<ratio>` on `readiness`, `ADOPTED:<n>|human <h>|agent
<a>|auto <m>` on `check`; a row is deleted when a human `verify`, `stale
--confirm-source`, `annotate` or a per-row `adopt` re-stamps that edge) and
`onboard.yaml`'s `rejections[]` (a person's, never re-proposed; an absent
`by:` reads as a person's) and `reviews[]` (the verdict memo). Transitions:
`onboard seed` / `attribute --propose` → seeded; `onboard adopt --class
<origin> [--accept-min 0.85] [--scope <glob>]` (a person) → adopted `{by:
human}`; `onboard adopt --class <rule|measurement> --auto` → adopted `{by:
auto}`, `ADOPT_REFUSED:<pair>|not-autonomous` for any other class; `onboard
adopt --agent-verdicts - --by agent:<s> --run <r>` with `verifies` → adopted
`{by: agent}`, with `drives` / `unsure` → parked (twice `unsure` →
`REVIEW_HUMAN`); `annotate --author` on the task's change surface → adopted
`{origin [agent:author], by: agent}`; `onboard adopt <test> <source>` /
`--area <a> --batch <n>` / an in-gate row a person confirmed → reviewed
(stamp, no provenance row); a human re-stamp → reviewed; `onboard reject` →
rejected (`REJECT_REFUSED:headless` under `AIT_PROFILE_HEADLESS=1`). Load
rules: `SEED_SHADOWED`, `ADOPTED_ORPHAN`, absent-`by:`-is-human. The
autonomous floor: an autonomous path may seed everything and may adopt a
class only when every member carries a rule, a measurement or a reading
origin and clears `accept_min`; it may never adopt a heuristic without a
reading, reject a seed or change a kind. The full model is drawn under *The
Adoption Model*; its costs are recorded under
`tradeoff_two_edge_states_during_adoption`, `tradeoff_seed_precision`,
`tradeoff_agent_judgement_unmeasured` and
`tradeoff_wrong_positive_invisible_to_score`.
<!-- /section: component_adoption_ledger -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(adoption layer; inherited from n011 and n012)*

`internal/seed`, verb `ait testmap onboard seed [--from
static,convention,cochange,plan,prose,coverage] [--min-cochange 2]
[--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json
--out <f>]`, produces `registry/seeded.yaml` rows `{test[#member], covers,
origin[], confidence, evidence{static: file:line, convention: pair, cochange:
[task ids], plan: path, prose: line, coverage: run id}, proposed_at}`. The
two reading origins are never seeded here: `agent:review` is written onto
an existing row by `onboard adopt --agent-verdicts` (with
`evidence.agent_review {verdict, assert_line, rationale, by, run,
packet_sha, test_blob, unsure, at}`) and `agent:author` by `annotate
--author`. `static:{package, invocation, import}` read `internal/deps` facts
for the test file only (direct, never the closure; same-package facts
excluded). `convention` applies `config.yaml conventions:` patterns seeded
by `detect` per runner (bash-file: `test_<x>.sh → aitask_<x>.sh | lib/<x>.sh
| lib/<x>.py`; pytest: `test_<x>.py → <x>.py` under the main roots; go-test:
`<x>_test.go → <x>.go` same dir; gradle-class: `<Stem>[Test|*Test].kt →
<Stem>.kt` under main). `cochange` parses one `git log --name-status -M
--format=%H%x00%s` pass over commits whose subject matches `(t<id>)` and
counts `(test, source)` pairs across distinct tasks (per-commit grouping
fallback), cached by HEAD sha, `SEED_HISTORY:shallow|<n>`. `plan` reads the
`aitask_explain_extract_raw_data.sh` cache; `prose` reads header comments and
`# Covers:` lines; `coverage` imports coverage.py contexts JSON, `go
-coverprofile` per unit, LCOV with a test-id column, or a project plugin's
`{test, covers}` lines. The confidence table is the one under *The Adoption
Model*, each origin carrying its `class:` (rule / measurement / reading /
heuristic); `agent:review`'s row reads `agent_review.measured_confidence`
when calibration wrote one; combination is noisy-OR, ordering only, and the
autonomous rule is by class first and by number second. Helpers are
separated first by `helper_roots` and `helper_fanin` with `SEED_HELPER:` and
`SEED_READS:<helper>|<glob>|<evidence>` lines; `SEED_KIND:`, `SEED_BATCH_NO:`,
`SEED_MEMBER:`, `SEED_AXIS:` come from `onboard classify`'s signals. A
rejected pair is never re-proposed; a pair already stamped is dropped with
`SEED_SHADOWED`; `--apply` writes deterministically sorted, otherwise prints
`SEED:<test>|<source>|<origins>|<confidence>` lines; `--json --out` writes the
dump the skill attaches to the level task. Budget: static + convention < 2 s
and co-change < 5 s over 600 commits on the aitasks shape. Fixtures: a
synthetic repo per origin with a `(t<id>)` history, plus one per verdict
branch.
<!-- /section: component_seeder -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs *(adoption layer; inherited from n011 and n012)*

`internal/onboard` behind `onboard detect [--write] | inventory | seed |
review | classify [--apply|--propose] | adopt | reject | scaffold | status |
finish` and the `aitestmap/onboard.yaml` phase ledger `{contract, task,
level, phases{detect, inventory, seed, waivers, enable, full_run, adopt,
review: {status, at, by, counts{reviewed, adopted, parked, unsure},
partial}, classify, scaffold, finish: {status, at, by, counts}},
rejections[], reviews[], kind_proposals[], calibration[]}` (the skill's
preflight is a precondition check, not a ledger phase).

- `detect` prints `FRAMEWORK:<kind>|<glob>|<count>|<builtin>|<evidence>` for a
  closed detector list (`bash-file`, `pytest`, `go-test`, `gradle-class`,
  `kmp-sourceset`, `suite-from-config`), `UNIVERSE:<n>`, `UNLISTED:<n>`
  (test-looking files no detector claims), `AGGREGATE_RUNNER:<path>` and
  `SERIAL_LIST:<path>|<n>` for a runner script with a carve-out list,
  `RESOURCE_HINT:<name>|<n tests>|<evidence>` (real-repo git use, flock, a
  lock script), `SUITE_CANDIDATE:test_command|verify_build|<cmd>`,
  `RUNNER_SCRIPT_NEEDED:<reason>` from the grid heuristic. `--write` emits
  the level-0 files (`config.yaml` with `bootstrap_until` today + 90,
  `require_stamp false`, `concurrency serial`, `completion.mode auto` with
  `full_run_every {tasks 5, selection_ratio_above 0.60, days 7}`,
  `agent_review {enabled true, confidence 0.90, accept_min 0.85,
  calibration_min 30, batch 20, packet_lines 120, max_pairs_per_run 400,
  author true}`, `readiness {…, min_full_runs_since_map_change 3}`,
  `conventions:`, `helper_roots:`; `runners.yaml` with builtins, bindings and
  the `full: true` suite runner with `fallback_command:`; `resources.yaml`
  from hints; `areas --import-codemap`) and on an existing table prints
  `DETECT_DIFF:` and writes nothing without `--force`.
- `inventory` runs `scan` + every `list` + `check` and prints `UNREGISTERED:`
  as the to-do list.
- `seed` is the seeder.
- `review [--next N] [--class <origin>] [--scope <glob>] [--ids <csv>]
  [--json] [--out <dir>] [--calibrate <n>] [--crew <id>] [--collect
  <crew-id>]` assembles packets and, with `--crew` / `--collect`, registers
  and harvests crew reviewers; `adopt --agent-verdicts - --by <agent-string>
  --run <id>` is the intake. Both are *component_agent_review*.
- `classify` wraps `classify --suggest` with the three onboarding signals and
  on `--apply` writes the level-2 kind / area / scope / reads / batch lines
  and `needs:` bindings for confirmed rows; `--propose` records the
  `CLASSIFY:` rows in `kind_proposals[]` and applies nothing; there is no
  `--auto`, and `--apply` refuses under `AIT_PROFILE_HEADLESS=1`.
- `adopt`: `--class <origin> [--accept-min 0.85] [--scope <glob>]
  [--dry-run]` for a person's bulk adoption with an `adopted.yaml` row per
  edge (`by: human:<email>`); `--class <origin> --auto` for the autonomous
  form, which adopts every pair of a rule or measurement class (`by: auto`)
  and refuses anything else with `ADOPT_REFUSED:<pair>|not-autonomous`;
  `--agent-verdicts -` for verdict lines; `<test> [<source>]` / `--area <a>
  --batch <n>` / `--files-from -` for reviewed per-row adoption; writes
  stamped `testmap:covers` lines through the rewriter at the fixed
  per-language position; refuses `ADOPT_REFUSED:<path>|dirty-foreign`; skips
  duplicate / unregistered / no-leader; prints `WROTE:` per file and
  `ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>|<by>`.
- `reject <test> <source> --reason` — a person's verb; the engine refuses it
  when `AIT_PROFILE_HEADLESS=1` is exported by the skill's headless
  invocation (`REJECT_REFUSED:headless`), so no autonomous path can remove
  a seed.
- `scaffold --axes | --runner <builtin> --as <name> | --members` writes the
  level-3 `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` with a
  `SCAFFOLD_TODO` list, and `testmap:unit` member blocks.
- `status` prints phase rows, `ONBOARD_NEXT:<phase>`, seed queue counts per
  origin and per verdict (`verifies` / parked / unsure / unreviewed),
  `ADOPTED_UNREVIEWED` split by `by`, `AGENT_ADOPTED`,
  `AUTHOR_UNCORROBORATED:<n>`, `REVIEW_PARKED:<n>`, `REVIEW_HUMAN:<n>`,
  `KIND_PROPOSALS:<n>`, `REVIEW_AGREEMENT`, `CALIBRATION`,
  tests-with-any-edge and sources-with-any-edge ratios, the oldest pending
  seed age and the rejections count.
- `finish` requires status green (no pending phase, `check` clean, every
  remaining seed either under the user-set threshold or parked with a
  verdict), flips `require_stamp` and `--strict`, records the phase;
  `--auto` is the same test with `FINISH:auto|parked <n>|review_human <m>`
  printed, so a headless level-1 task can close enforcement.

The engine reads `onboard.yaml`'s `task:` and `level:` and writes phase
rows; it never creates a task, edits a profile, `project_config.yaml`,
`gates.yaml` or `CLAUDE.md`, commits, or launches a code agent — those are
the skill's through the framework's own scripts. Go tests on fixture
repositories: one per detector and per detect shape, the fan-in
reclassification, golden files for block placement per language, every
refusal branch, resume from each phase including a partial `review`.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(adoption layer; inherited from n011 and n012)*

`.claude/skills/aitask-testmap-onboard/` as a profile-aware stub +
`SKILL.md.j2` (resolver key `onboard`) with one procedure file per phase
(`detect.md`, `inventory.md`, `seed.md`, `waivers.md`, `enable.md`,
`full-run.md`, `adopt.md`, `review.md`, `classify.md`, `scaffold.md`,
`finish.md`); Claude Code first, Codex and OpenCode ports as follow-up
tasks; rendered goldens under `tests/golden/skills/aitask-testmap-onboard/`.
`adopt.md` orders rule → measurement → reading: `onboard adopt --class
static:package --auto`, `--class coverage --auto`, then `review.md` — the
`aitask-testmap-review` flow as a sub-procedure (`onboard review --next 20`
→ read → `VERDICT:` lines naming the assertion line for every `verifies` →
`onboard adopt --agent-verdicts - --by <agent-string> --run review-<n>` →
correct or park `VERDICT_INVALID` rows → next batch, until the queue is
empty or `max_pairs_per_run`, the phase recorded partial and re-entered at
`ONBOARD_NEXT:review`), then `onboard review --calibrate 50` where a ground
truth exists; the same file in every profile, naming no agent. Flow:
preconditions → read-only survey and level proposal → one aitask per level
created with the seed dump attached and claimed → task-workflow (phases at
Step 7 with per-phase commits, the diff at Step 8, the first full run at
Step 9) → the timeout from the ledger, `readiness`, the next level's task
with `depends:`. Confirmations: per runner (keep / edit command / drop); per
evidence class for the parked remainder with the agent's verdicts and
rationales pre-filled (accept all / review a sample of ten / edit rows /
skip); per kind change individually; `UNLISTED` files (bind / not a test /
later); the config table once (`test_command` → `./ait test` with the
previous value moved to a `full: true` suite runner; `verify_build` left
alone unless the user names it as the suite; `gate_command_exit_contract` +=
`test_command`; profiles `default_gates` += `tests_pass`, `testmap_check`,
`testmap_fresh`; `bootstrap_until`; `completion.mode auto` with its cadence;
`docs:` and `notes:`; a hand-maintained `CLAUDE.md` Testing paragraph).
Re-entry at `ONBOARD_NEXT:`; every phase idempotent; `--no-task`; the
`--policy selected` re-entry writes the flip only on `ADMISSIBLE` with
`approved_by`, for a project that chose `completion.mode: full`. Headless:
level 0, then level 1 in full — `adopt --auto` over the rule and measurement
classes, the review loop in the skill's own session to budget, the intake
adopting the `verifies` pairs, `finish --auto` — no prompts, kinds proposed
only (`classify --propose`), no scaffold, and no policy re-entry because
`auto` flips itself. The skill exports `AIT_PROFILE_HEADLESS=1` around the
engine in the headless profile so `reject` and `classify --apply` refuse.
The full flow is under *Onboarding*.
<!-- /section: component_onboarding_skill -->

**The run surface**

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(adoption layer; inherited from n011 and n012)*

`.aitask-scripts/aitask_test.sh`, a ~150-line bash front over the shim, with
flags `--task <id> | --gate | --advisory | --all | --dirty | --explain |
--howto [--md] | --tokens | --fresh-only | --budget-s <n> | --json` and
positional `<path|id>...`. It resolves `MODE` (completion iff `--gate` or
`$AIT_GATE_TASK_ID`; advisory iff `--advisory`; else interactive), `TASK`
(`--task` > `$AIT_GATE_TASK_ID` > `aitask/<task_name>` branch > single own
lock via `aitask_lock.sh --list-mine` > `NO_TASK`), `INTAKE` (change surface
piped; `--dirty`; `--all`; named paths, a source path as a one-file `TASK:`
set) and `POLICY` (completion: `config.yaml completion.mode` re-checked
against `readiness`; under `auto` it also reads `costs/policy.yaml`, applies
the three cadence triggers, prints `POLICY:auto|selected|next_full_in:<n>`
or `POLICY:auto|full|<cadence:…|not_yet:…>`, has the engine write the first
`ADMISSIBLE` as `approved_by`, and commits every `POLICY_WRITE:` line under
`ait: testmap policy <flip|full-run> (t<id>)` with the path named); calls
the engine `test` composite (interactive: the budget applies and `DEFERRED`
is printed; completion: deferred rows run); with no `aitestmap/` prints
`TESTMAP_ABSENT:<hint>` and delegates to `aitask_run_project_command.sh
test_command`; with the engine absent prints `ENGINE_MISSING:<path>|<repair>`
and exits 3 interactively, runs the suite runner's `fallback_command` in
completion mode when `completion.engine_absent` is `fallback_command`, and
prints `VERDICT:skip REASON:testmap_absent` in advisory mode. Advisory mode
prints `VERDICT:pass|fail|skip` /
`REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused`
/ `DETAIL:` / `LOG:.aitask-gates/<task>/affected_<run-id>.log` / `SELECTED:`
/ `UNMAPPED_SOURCE:` / `UNKNOWN:` lines, exits `0/1/2/3` with
`aitask_run_project_command.sh`'s capture contract, and appends nothing to
any ledger. Every mode prints `MODE / TASK / INTAKE / POLICY / SELECTED /
RUN / RESULT`, `UNANNOTATED_TEST:<path>` + `HINT` (a listed test in the
change surface with no `testmap:` block, no seed and no adopted row) and
`UNMAPPED_SOURCE:<path>`; exits `0 / 1 / 2 / 3 / 75 / 64`; the run id it
passes to the composite is prefixed `test-` / `gate-` / `full-` by mode.
Dispatcher arm `test)` in `ait`; five permission touchpoints (no second
helper script; `tests/test_touchpoint_count_contract.sh` re-pinned).
`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine that replays scripted exits, in
all three modes, every `REASON` and the `auto` matrix (`ADMISSIBLE` × each
cadence trigger × `NOT_YET` × the first-flip record and its commit).
<!-- /section: component_test_entrypoint -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Engine `test` composite *(adoption layer; inherited from n011 and n012)*

`internal/selectr` + `sched` + `runner`, reached by `aitask_test.sh`: `test
--task <id> --changes - | --paths <p>... | --all [--explain] [--budget-s]
[--format lines|json|tokens] [--run <id>]` runs `select --include-stale` →
`schedule` → `run` in one process and prints
`SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`, one
`UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked rows
with their reasons (a seeded edge reads `edge(seeded:<origins>)`, an adopted
one `edge(annotation) adopted(<origins> <confidence> by <who>)`), the
schedule's wave lines, results per id and
`RESULT:pass|fail|skip|deferred|<run_id>`. `--all` is `run --all` (anchors
evidence, scores the predictions behind it, honours `subsumed_by`);
`--explain` stops after `select`; the run id is prefixed by the front. It
never resolves a task, reads a profile, applies a completion policy or
touches a gate ledger — those are the bash front's.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief *(adoption layer; inherited from n011 and n012)*

`internal/brief`, verb `brief [--md]`, surfaced as `ait test --howto [--md]`
and `ait testmap brief`: `TESTMAP:<state>|since|LEVEL:<n>|POLICY:<mode>[|next
full in <n> tasks]|seeds pending <n> (parked <p>, review_human <r>)|adopted
<n> (agent <a>, human <h>, auto <m>)`; one `RUNNER:<name>|<kind>|<units>|<how
it is invoked>|<resources>[|subsumes ...]` line per runner;
`FULL_GATE:<runner>|<p95 est>|<cadence: every N tasks / >= R / D d>|<tests_pass
timeout>`; `GATE:` (the chain `testmap_fresh` → `testmap_check` →
`tests_pass` and what `--gate` would run now under the policy);
`AGENT_REVIEW:enabled|<confidence>|<calibration ratio or none>|<agreement or
none>`; `VERBS:` (the four forms); `AXES:` per declared axis with facets and
value counts; `RESOURCE:` per declared resource with its kind and what a
refusal looks like; `NEW_TEST:` (the `annotate --suggest` hint);
`DOCS:<path>` per `config.yaml docs:` entry; `NOTES:` the `config.yaml
notes:` lines verbatim (≤ 10); `ONBOARD_NEXT:` while a ledger is unfinished;
`KIND_PROPOSALS:<n>` and `REVIEW_HUMAN:<n>` when non-zero. Before onboarding
it prints `TESTMAP_ABSENT` plus the `test_command`. `--md` renders the same
as markdown. < 100 ms warm. The worked example is under *The Run Surface*.
<!-- /section: component_agent_brief -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(adoption layer; inherited from n011 and n012)*

The fourteen-line `## Running Tests` section (text under *The Run Surface*)
in `seed/aitasks_agent_instructions.seed.md`, installed unchanged into
`CLAUDE.md`'s `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md` and
the OpenCode mirror by the existing `assemble_aitasks_instructions()` /
`insert_aitasks_instructions()` on every `ait setup` and `ait upgrade`. The
seed carries no project specifics and names no agent — `ait test --howto`
computes them, so the current-state-only documentation rule holds and
nothing condensed from `runners.yaml` lives in a constant; the author path
is a procedure act, not a run form, and is taught by the procedure.
`tests/test_agent_instructions.sh` gains one case asserting the heading in
all four rendered surfaces through a real `install.sh --dir`. The
hand-maintained `CLAUDE.md` case (sentinel present, no markers) is the
level-0 onboarding task's edit.
<!-- /section: component_agent_instructions -->

**Workflow and gates**

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(adoption layer; inherited from n011 and n012)*

`aitestmap/config.yaml completion:`: `mode full|selected|auto` (`auto` is
what `detect --write` writes and the attended config table confirms;
`selected` is written only by the onboarding skill's `--policy` re-entry
after `READINESS_DECISION:ADMISSIBLE`, beside a human
`run_gate_admission.approved_by` in `config.yaml`; `full` is the project's
opt-out of any flip), `full_run_every {tasks 5, selection_ratio_above 0.60,
days 7}` (the cadence; all three required when the mode is `auto` —
`READINESS:cadence_declared`: `tasks ≥ 2`, `0 < selection_ratio_above ≤ 1`,
`days ≥ 1`), `deferred run|fail` (what completion does with rows the
interactive budget would cut; default run), `on_empty_selection skip|full`
(default skip → exit 2 → gate skip under the opt-in; ignored by a cadence
full run), `engine_absent error|fallback_command` (default error). `ait
test --gate` re-checks `readiness` on every completion run: under `selected`
an unmet criterion prints `POLICY_DEMOTED:selected->full|<criterion>` and
runs full; under `auto` a not-yet-admissible map runs full
(`POLICY:auto|full|not_yet:<criterion>`), the first admissible run prints
`POLICY_FLIPPED:auto->selected|engine:readiness@<run>` and writes
`approved_by {who: engine:readiness@<run-id>, at, mode: auto, statement:
<the readiness lines>}` to `costs/policy.yaml`, a due cadence trigger
(`selected_since_full ≥ tasks`; the selection's per-group estimate ≥
`selection_ratio_above` × the newest full p95 on this host class; `now −
last_full_run.at ≥ days`) runs full with `POLICY:auto|full|cadence:<trigger>`
and resets the counter, otherwise the selection runs with
`POLICY:auto|selected|next_full_in:<n>` and the counter increments, and a
later unmet criterion prints `POLICY_DEMOTED:auto->full|<criterion>` and
clears `approved_by`. The human flip and the engine flip are both bounded
by the same automatic demotion, and the engine flip additionally by the
cadence, so the policy can only fail toward running more. The cadence is
the knob that sets how long a miss can survive (`tasks − 1` completions,
`days` days) and is printed by `--howto` and on every completion run.
`readiness` prints `POLICY:<mode>|<what --gate would run now>[|next_full_in:<n>]`;
the gate-run ledger block carries `result="MODE:<full|selected>|<n
units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>]"`.
<!-- /section: component_completion_policy -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(adoption layer; inherited from n011 and n012)*

`testmap_fresh` (kind procedure, verifier `aitask-gate-testmap-fresh`, no
unlocks; its seeds step reads packets for the task's touched test files and
adopts or parks on verdicts) and `testmap_check` (machine, `max_retries 0`,
`timeout 120`, `unlocks: [tests_pass]`) in `gates_reference.yaml` synced to
`gates.yaml`. The completion test gate is the existing `tests_pass` with
`test_command: ./ait test` and `gate_command_exit_contract: [test_command]`,
so `ait gates run` needs no new verifier for running tests and the legacy
no-gates path needs no new prose — a project reaches the selective lane by
declaring `tests_pass`, which onboarding's `enable` phase writes into the
profiles' `default_gates` with `testmap_check` and `testmap_fresh`, with
confirmation; never by hand, never by `ait setup`. There is no selection-only
gate and no `aitask_gate_testmap_run.sh`. `aitask_gate_testmap_check.sh`
reports `SEEDED:<n>` and `ADOPTED:<n>|human <h>|agent <a>|auto <m>`
(informational, never fail) and `UNMAPPED_SOURCE:<path>` (a changed source
with no edge, seed, rule or waiver — reported during bootstrap, failing under
`--strict` past `bootstrap_until`; the strict flip is onboarding's `finish`
phase). An `unlocks:` target absent from a task's active set is ignored, so
`testmap_check` declared alone is linear as before. `run_gate_admission` and
`ait testmap readiness` gate the completion policy flip rather than a second
gate's declaration: under `selected` the approval is a human's in
`config.yaml`; under `auto` the verifier's `./ait test --gate` performs the
flip, the engine records it in `costs/policy.yaml`, the bash front commits
the write under `ait: testmap policy <flip|full-run> (t<id>)`, and the
`tests_pass` ledger block's `result=` field names `policy:auto` with
`next_full_in:<n>` or `cadence:<trigger>`, so a ledger reader sees whether
the whole suite ran and why. The engine never enables a gate and never
writes a profile.
<!-- /section: component_gates -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam — the data edits *(adoption layer; inherited from n011 and n012)*

`task-workflow/SKILL.md.j2` Step 7 gains one paragraph after *Follow the
approved plan* — run `./ait test` as the implementation test loop, answer
`UNANNOTATED_TEST` with `annotate --suggest` and `UNMAPPED_SOURCE` by mapping
the source, never call the test tool directly (rendered into every profile;
goldens regenerated). `build-verification.md` gains a branch for verdict
`error` / reason `command_refused | command_errored` (host refused resources
or the framework could not run: do not fix code, do not record pass, re-run
later — the entrypoint already deferred to its deadline).
`lib/gate_verifier_lib.sh run_project_command_key()` gains the 75 → error and
3 → error rows for opted-in keys and exports `AIT_GATE_TASK_ID` /
`AIT_GATE_RUN_ID` around the command; `aitask_run_project_command.sh
--task-id` exports the former. `gates_reference.yaml` adds `testmap_fresh`
and `testmap_check` (`unlocks: [tests_pass]`) and no selection-only gate. The
project's profiles gain `tests_pass`, `testmap_check` and `testmap_fresh` in
`default_gates` via onboarding; no profile key is added for agent review
(`agent_review.enabled` and `agent_review.author` live in
`aitestmap/config.yaml`). The `ait` dispatcher gains `test)`.
`aitask_codeagent.sh` gains the `testmap-review` operation (interactive by
default, `--print` only under `--headless`, mirroring `batch-review`) and
`list-models` shows `verified.testmap-review`;
`seed/models_{claudecode,codex,opencode}.json` gain the
`verified.testmap-review` key per model (0 until measured; `aitask-add-model`
seeds it). `aidocs/framework/aitasks_extension_points.md` gains *Adding a
test-framework detector* and *Adding a seed origin* with the class column
(rule / measurement / reading / heuristic) and the autonomous-floor rule.
`tests/test_gate_verifiers.sh` covers 75 and the env export;
`tests/test_codeagent.sh` pins `testmap-review` interactive-by-default;
`tests/test_serial_carveout_doc_drift.sh` is extended for the pytest
carve-out pin; `tests/test_no_unscoped_task_commit.sh` is unaffected because
the skill commits through `aitask_task_commit.sh`.
<!-- /section: component_workflow_seam -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration — the procedure edits *(adoption layer; inherited from n011 and n012)*

task-workflow gains `affected-tests.md` (the Affected Tests Procedure),
called once from Step 7 before proceeding to Step 8, wrapped in `{% if
profile.affected_tests is not defined or profile.affected_tests != 'off' %}`;
the procedure runs `./ait test --advisory --task <id>` (with `--explain` when
the key is `show`) in the `set -e` capture form and branches per the table
under *The Workflow Seam*; its autonomous `no_selection` and
`UNANNOTATED_TEST` branches run `ait testmap annotate --author <test>
<source> --task <id> --by <agent-string>` for pairs on the change surface
(*component_author_annotation*) before falling back to `attribute
--propose`, so a headless task stamps the couplings it created; attended
profiles keep the offer with the agent's pairs pre-filled; the verdict line
is recorded in the plan's Final Implementation Notes and never in the gate
ledger. Profile key `affected_tests: run|show|off` is documented in
`profiles.md`; `default.yaml` and `fast.yaml` omit it (run); `remote.yaml`
sets `run`; no profile key is added for agent review. The in-loop call is
the Step-7 paragraph, not the procedure. Step 8's `testmap_fresh` dispatch
gains the packet-reading seeds step (attended pre-fill / confirm /
trust-batch; autonomous `--agent-verdicts`); Step 9 (gate orchestrator,
`build-verification.md`) is otherwise unchanged. The onboarding skill's
`adopt.md` gains `review.md`; the new `aitask-testmap-review` skill and the
rewritten gate skill are rendered for every profile × agent. `aitask-qa`'s
`test-discovery.md` uses `ait testmap explain --sources <changed> --format
table` when `aitestmap/` exists and `test-execution.md` runs `./ait test`
through `aitask_run_project_command.sh --task-id`. pickrem and pickweb
inherit Step 7 and see a printed skip on Web. `ait setup` prints
`TESTMAP:<state>`. Goldens under `tests/golden/` are regenerated for every
profile × agent; `aitask_skill_verify.sh` is run.
<!-- /section: component_workflow_integration -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(adoption layer; inherited from n011 and n012)*

`aitask-qa` reads the registry when `aitestmap/` exists: `test-discovery.md`
3a–3c map the changed sources through `ait testmap explain --sources <paths>
--format table` (edges, test-deps, scoped rows; `Covered` / `Covered
(adopted by human|agent|auto)` / `Covered (seeded)` / `GAP` for a source with
no edge and no test-dep), falling back to the naming-convention scan only
when no registry exists; `test-execution.md` 4a runs the configured `./ait
test` through `aitask_run_project_command.sh test_command --task-id <id>`
(which exports `AIT_GATE_TASK_ID` so the run is the task's selection), 4b
runs named units through `ait test <path>`, 4c gains a `REFUSED (host
resources)` row for verdict error / `command_refused`, and 4d's coverage
component uses registry edges rather than file-name matches, with seeded and
agent-adopted rows counted as coverage that exists (QA measures whether a
test exists, not who accepted the claim or whether it is fresh); the health
score's Tests component treats `REFUSED` like `SKIP`.
<!-- /section: component_qa_integration -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(core + adoption layer; inherited from n011 and n012)*

Four skills. **`aitask-testmap`** (maintenance: annotate a file / member /
coordinate — including `annotate --author` for the task's own pairs —
declare axis sources, `reads` on helpers, `axes --explain`, `attribute`
before the gate, `verify` after editing, `classify --suggest`, `select
--format tokens` into a render loop) opens with `ait test --howto` and hands
a repository without `aitestmap/` to `aitask-testmap-onboard`.
**`aitask-gate-testmap-fresh`** (the procedure gate: `stale --task`, `git
diff` per `STALE` row with unevidenced variants, retarget `STALE_PATH`,
re-stamp `EVIDENCED`, resolve `check`'s structural rows, prompt on
`UNSTAMPED` past bootstrap, never guess `UNKNOWN`, never confirm `STALE`
autonomously; an `adopted(... by <who>)` row is confirmed knowing what
accepted it) whose seeds step runs `onboard review --ids <rows>` for each
`COMMITTED:` / `TASK:` test file with seeds and reads the packets —
attended: the agent's verdict is pre-filled per row and the person confirms
(`by: human`), overrides, or trusts the batch (`by: agent`); autonomous:
`onboard adopt --agent-verdicts - --by <agent-string> --run <gate-run>` — so
a map migrates a few files per task through ordinary work.
**`aitask-testmap-onboard`** is the profile-aware onboarding skill, whose
`review.md` sub-phase is where its agent reads seeds.
**`aitask-testmap-review`** (*component_agent_review_pass*) is the bulk
reader: profile-aware stub + `SKILL.md.j2` (resolver key `testmap-review`),
`review-batch.md` stating the verifies-or-drives rule once, batches of
`agent_review.batch`, resumable, attended table-confirm / autonomous no
prompts; launched by `review.md` inside an onboarding task, by `ait skillrun
testmap-review` interactively, by `ait codeagent testmap-review`
(interactive; `--print` only under `--headless`, as `batch-review`), or as
crew agents through `ait crew runner`. Every skill's runtime knowledge of
how to run tests is the seeded `## Running Tests` block plus `./ait test
--howto`, never prose in a `SKILL.md`. All ship Claude Code first, with
wrapper surfaces regenerated by `aitask_audit_wrappers.sh apply-wrapper`;
Codex and OpenCode ports are separate tasks.
<!-- /section: component_skill -->

**Agent-driven adoption**

<!-- section: component_agent_review [dimensions: component_agent_review] -->
### Agent review verbs *(adoption layer; new: introduced to bridge n011 and n012)*

The engine side of the review pass, `internal/onboard/review.go`. **Packet
writer** `onboard review [--next N] [--class <origin>] [--scope <glob>]
[--ids <csv>] [--json] [--out <dir>] [--calibrate <n>]`: selects seeded rows
without a verdict for their current test blob from this reader (the
`onboard.yaml reviews[]` memo; `REVIEW_MEMO:<skipped>`; a pair whose second
`unsure` came from a different run is `REVIEW_HUMAN` and never selected),
groups them by test file so one file's pairs share a batch
(`REVIEW_BATCH:<n>|<pairs>`), and prints the line-protocol packet
(`REVIEW_PAIR` / `REVIEW_ANCHOR` / `REVIEW_TEST` with the anchor ±20 lines
and every assertion line flagged `!`, ceiling `agent_review.packet_lines` /
`REVIEW_SOURCE` declared symbols only / `REVIEW_PROSE` / `REVIEW_MEMBER` /
`REVIEW_END:<id>|<packet_sha>`), as JSON with `--json`, or as one file per
batch under `.aitask-testmap/onboard/<run>/review/<n>.txt` with `--out`.
**Intake** `onboard adopt --agent-verdicts - --by <agent-string> --run
<run-id>`: reads `VERDICT:<id>|verifies|<test path:line>|<rationale>` /
`…|drives|-|<rationale>` / `…|unsure|-|<rationale>` (rationale ≤ 160
chars, `|` as `%7C`); validates the pair is in a packet this run cut, the
`packet_sha` is current (`VERDICT_STALE:<id>` otherwise, ignored and
re-packeted), the `--by` value against `lib/agent_string.sh`'s grammar (exit
64 otherwise), and for `verifies` that the named line exists in the test
file and contains the source's stem, its invocation form, an output path
the source writes or an exported symbol (`VERDICT_INVALID:<id>|<reason>`,
including `assert_line_names_other` for a homonym stem of another source;
the row untouched). Writes: for `verifies`, `origin[] += agent:review`,
`evidence.agent_review {verdict, assert_line, rationale, by, run,
packet_sha, test_blob, at}`, the noisy-OR recomputed and, at or above
`accept_min`, the stamp through the rewriter plus the `adopted.yaml` row
and the seed row removed; for `drives`, the verdict on the row (parked);
for `unsure`, `evidence.agent_review.unsure += 1` and at 2 `REVIEW_HUMAN`;
every verdict into `reviews[]`. Prints `REVIEW_APPLIED:<verifies>|<drives>|<unsure>|<invalid>|<stale>`,
`WROTE:`, `ADOPT_SUMMARY:…|agent`, `REVIEW_PARKED:<n>`, `REVIEW_HUMAN:<n>`,
`REVIEW_AGREEMENT:<agree>/<labelled>|none` over pairs that also carry a
human per-row decision, and `REVIEW_ORIGIN_DEMOTED` when agreement or
calibration falls below `accept_min` over `calibration_min` pairs (writing
`agent_review.measured_confidence`). **Calibration** `--calibrate <n>`
samples pairs with a ground truth (coverage rows first, else reviewed edges
and human rejections), marks them so the intake compares instead of
writing, and prints `CALIBRATION:agree <a>|disagree <d>|<ratio>` into
`onboard.yaml calibration[]`. **Crew form** `--crew <id>` registers one
`testmap-review` reviewer per `--out` packet file through `aitask_crew_addwork.sh
--type testmap-review --work2do review-batch.md` (the crew's `launch_mode`
decides headless or interactive; the runner launches each through `ait
codeagent --agent-string <s> invoke raw`) and prints the `ait crew runner`
line for a person to start; `--collect <crew-id>` reads each agent's
`_output.md` as verdict lines into the intake. Config: `agent_review
{enabled, confidence 0.90, accept_min 0.85, calibration_min 30, batch 20,
packet_lines 120, max_pairs_per_run 400, author true,
measured_confidence}`. Budgets: `--next 20` < 300 ms warm, `--out` < 1 s
per 100 pairs, the intake < 200 ms per batch. Tests: fixture repos per
language for packet shape and assertion flagging; every verdict branch;
every `VERDICT_INVALID` reason; `VERDICT_STALE`; the `--by` refusal; the
memo skip; the `unsure` escalation; agreement crossing the threshold both
ways; calibration against a coverage fixture; `--auto` refusing a heuristic
class; `--collect` over a fixture crew.
<!-- /section: component_agent_review -->

<!-- section: component_agent_review_pass [dimensions: component_agent_review_pass] -->
### Agent review pass *(adoption layer; new: introduced to bridge n011 and n012)*

The reading end to end, drawn under *The Agent Review Pass*: an agent reads
the packets `onboard review` cut and returns verdicts the intake turns into
adopted rows or parked marks. Three sites share the intake — the
`testmap_fresh` in-gate step (the task's touched test files; attended
pre-fill / confirm / trust-batch, autonomous adopts), the pre-review
Affected Tests procedure (the task's own pairs through `annotate --author`,
*component_author_annotation*) and the bulk skill
**`aitask-testmap-review`** (profile-aware stub + `SKILL.md.j2`, resolver key
`testmap-review`, `review-batch.md` stating the verifies-or-drives rule once
and `unsure` as the answer when neither applies, batches of
`agent_review.batch`, resumable through `onboard.yaml phases.review` with
`max_pairs_per_run`, attended table-confirm per batch, autonomous no
prompts, commits under `chore: Onboard testmap — review (t<id>)` inside an
onboarding task, prints the commit lines otherwise). Launch surfaces:
`review.md` inside the onboarding task's session; `ait skillrun
testmap-review [--profile <p>] [-- --class <origin>]` (interactive; `ait
skillrun` never uses print mode); `ait codeagent testmap-review
[--headless]` (`--print` only under the flag, as `batch-review`); one crew
agent per packet file started by `ait crew runner` through `ait codeagent`.
`verified.testmap-review` in `seed/models_{claudecode,codex,opencode}.json`
(0 until measured; `aitask-add-model` seeds the key). Semantics: a
`verifies` verdict adopts with `by: agent:<agent-string>`; `drives` and
`unsure` park (still selecting, out of autonomous adoption, listed); no
verdict rejects; a wrong `verifies` over-selects and is confirmed or
retargeted at `testmap_fresh` like any adopted edge; the origin's
confidence is the 0.90 prior until calibration measures it. Tests: skill
goldens for every profile × agent; `tests/test_codeagent.sh` pins
`testmap-review` interactive-by-default; a grep test asserts no script of
this feature invokes `claude -p` outside `aitask_codeagent.sh`.
<!-- /section: component_agent_review_pass -->

<!-- section: component_auto_policy [dimensions: component_auto_policy] -->
### Auto completion policy and cadence *(adoption layer; new: introduced to bridge n011 and n012)*

`internal/feedback/cadence.go` and the `auto` arm of `aitask_test.sh`'s
policy step. State: `config.yaml completion.full_run_every {tasks,
selection_ratio_above, days}` (the declaration) and `aitestmap/costs/policy.yaml
{last_full_run {run_id, at, task, sha}, selected_since_full, approved_by
{who: engine:readiness@<run>, at, mode: auto, statement}}` (the engine's
ledger, committed) — the engine writes the ledger and prints
`POLICY_WRITE:aitestmap/costs/policy.yaml`; the bash front commits it under
`ait: testmap policy <flip|full-run> (t<id>)` with the path named, the same
commit path the human flip uses for `config.yaml`. Decision order inside
`ait test --gate` under `auto`: `readiness` → `NOT_YET` → full
(`POLICY:auto|full|not_yet:<criterion>`); `ADMISSIBLE` and no `approved_by`
→ `POLICY_FLIPPED:auto->selected|engine:readiness@<run>`, write, selection;
a cadence trigger due → full with `POLICY:auto|full|cadence:<trigger>`;
otherwise the selection with `POLICY:auto|selected|next_full_in:<n>` =
`tasks − selected_since_full`; a later unmet criterion →
`POLICY_DEMOTED:auto->full|<criterion>` and `approved_by` cleared. A cadence
full run ignores `on_empty_selection`, honours `subsumed_by` and `deferred:
run`, records `last_full_run`, resets `selected_since_full` and triggers
the window score (*component_feedback_tools*); every full run, whatever
triggered it, resets the counter. `readiness` adds `cadence_declared` and
the `CADENCE:` line; `--howto` prints the cadence on `FULL_GATE:` and
`next full in <n>` on `TESTMAP:`; the ledger block `result=` carries
`policy:auto|next_full_in:<n>` or `cadence:<trigger>`. Budget: the cadence
check < 50 ms. Tests: `tests/test_ait_test_entrypoint.sh` with the fake
engine replaying `readiness` states and ledger counters for each trigger,
the flip write and commit, the demotion clearing `approved_by`; engine tests
for the window score attributing a miss to the right task.
<!-- /section: component_auto_policy -->

<!-- section: component_author_annotation [dimensions: component_author_annotation] -->
### Author annotation *(adoption layer; new: introduced to bridge n011 and n012)*

`ait testmap annotate --author <test> <source>... [--task <id>] [--by
<agent-string>]` in `internal/annot` as a caller of the line-targeted
rewriter with an `adopted.yaml` write: resolves the task as `ait test` does,
reads the change surface through `aitask_change_surface.sh list <id>`
(`--changes -`), refuses `AUTHOR_REFUSED:<pair>|outside-change-surface`
unless both the test and the source are `COMMITTED:` or `TASK:` rows,
refuses an unregistered test (`AUTHOR_REFUSED:<test>|unregistered`), refuses
a `--by` that is not an agent-string (exit 64; `$AIT_AGENT_STRING` is the
default when exported), writes the stamped `testmap:covers` line at the
fixed per-language position (or into the member's `testmap:unit` block), and
adds `adopted.yaml {test, source, origin: [agent:author], confidence: 0.90
(0.99 with a static relation), adopted_at, task, by: agent:<s>, run,
evidence {static: <invocation|import|package|none>}}`; prints `WROTE:<file>`,
`AUTHOR_STAMPED:<pair>|<static or none>` and `AUTHOR_UNCORROBORATED:<pair>`
when the closure holds no relation. The pre-review procedure's autonomous
`no_selection` and `UNANNOTATED_TEST` branches are its only automatic
callers (`agent_review.author: false` turns them back to `attribute
--propose`); the attended offer's *Annotate as author* is the same verb;
`aitask-testmap` documents it. `stale` and `explain` show
`adopted(agent:author 0.90 by agent:<s>)`; a later human re-stamp deletes
the row like any adopted row; `readiness` and `onboard status` count
`AUTHOR_UNCORROBORATED`. Tests: the refusal outside the surface, member
placement, the corroborated and uncorroborated confidences, the `--by`
refusal, the row leaving on `verify`.
<!-- /section: component_author_annotation -->
<!-- /section: components -->
<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Every assumption of the baseline is inherited; two are rewritten
(`assumption_seeds_select_never_evidence`, `assumption_seed_sources_measured`)
and nine are new. Each is stated with its falsifier where one is known.
Full text is in the node metadata.

### Engine, distribution and install

- **`assumption_go_toolchain_available`** — Go ≥ 1.26 is available in release
  CI through an `actions/setup-go` step this design adds to `release.yml`
  (`go-version-file: engine/go.mod`) and on framework developers' machines;
  target-project users never need Go.
- **`assumption_go_toolchain_ci_and_dev_only`** — Go is a build-time
  dependency only: `release.yml` has no Go step today and the repository's
  only `setup-go` is `hugo.yml`'s for the website, so the engine job
  provisions its own toolchain; users receive prebuilt binaries.
- **`assumption_platform_matrix_sufficient`** — linux/darwin × amd64/arm64
  covers every target host (WSL reports Linux); any other platform builds
  from source via `--engine-from-source`.
- **`assumption_release_asset_reachable`** — a host running `ait setup` or
  `ait upgrade` can reach the GitHub release over HTTPS, as it already must
  for the framework tarball; the shim never downloads, so a gate run never
  performs a network fetch.
- **`assumption_release_assets_reachable`** — air-gapped or off-matrix hosts
  supply the binary via `--local-engine`, `--engine-from-source`,
  `AIT_TESTMAP_BIN` or a pre-seeded `$AITASKS_HOME/engine/`; `--no-testmap` /
  `AIT_TESTMAP_FETCH=0` skip the fetch and nothing else in setup depends on it.
- **`assumption_one_engine_per_framework_version`** — one engine build per
  framework version suffices; the per-user versioned directory resolves
  per-project VERSION differences without a compatibility matrix, and the
  shim never falls back to newest-wins.
- **`assumption_engine_latency_targets`** — on the aitasks shape (~720 units,
  2,500–3,000 edges, ~270 scanned sources) `select` < 200 ms warm, `scan` /
  `check` / `stale --task` < 300 ms, `stale --all` < 2 s, cold `select` <
  1.5 s, `onboard review --next 20` < 300 ms warm; on the thinking_app shape
  (297 variants over 49 members, 374 JVM classes, ~900 Kotlin files) `select`
  with axis expansion < 250 ms warm, reading the committed variants list and
  never executing a runner; pinned by committed `go test -bench` fixtures
  with a 2× regression failing `engine-check.yml`, validated before the
  gates are enabled.
- **`assumption_home_symlink_compatibility`** — every existing consumer of
  the legacy `~/.aitask` tree keeps resolving when it becomes a symlink to
  `~/.aitasks`, because all of them dereference a path rather than compare
  one: verified across the 35 references in 8 framework files, the venv's
  console-script shebangs, the `~/.aitask/bin/python3` wrappers, the
  `python/<ver>/bin/python3` symlinks and `pyvenv.cfg`; no `==`, `-ef`,
  `realpath` or `samefile` on the home path anywhere. This is the
  precondition of `ait engine home --migrate`, re-checked by
  `tests/test_aitasks_home.sh` before the default is flipped.
- **`assumption_legacy_user_root_coexists`** — in this release `~/.aitasks/`
  (engine) and `~/.aitask/` (venv, pypy_venv, python, bin, uv, dev_tier,
  update_check) coexist without either reading the other; the migration
  exists as an explicit verb and nothing in this feature depends on it having
  run.
- **`assumption_target_repos_accept_aitestmap_root`** — every target repo
  accepts a root `aitestmap/` directory of committed YAML (`onboard.yaml`,
  `seeded.yaml`, `adopted.yaml` and `costs/policy.yaml` included) and an
  optional `axes.yaml`; runner scripts and axes are optional because the
  reference runners are built in; thinking_app commits one runner script
  because its lowering is the harness's own routing.
- **`assumption_testmap_token_no_collision`** — the token `testmap:` collides
  with no existing prose comment in any target repo; the 38 `# Covers:`
  headers in aitasks are behavioural prose and are not matched.

### The map and freshness

- **`assumption_blob_digest_is_staleness_key`** — the git blob digest of the
  covered source is the staleness key; mtime and the annotation date are
  never compared; the blob id doubles as the join key into any commit's tree.
- **`assumption_git_history_is_freshness_clock`** — git history is the
  evidence clock, not the staleness key: commit reachability decides which
  `last_pass` anchors may suppress a `STALE` row, never whether an edge is
  stale; a shallow clone reports `STALE`, not `EVIDENCED`, and stays
  functional. Co-change reads history as a *seed* source, never as a
  freshness or evidence source.
- **`assumption_passing_run_anchors_edges`** — a passing run of a variant at
  commit C, on any host class, from an invocation without a cause and for an
  id under the flake threshold, is evidence that its annotated edges held
  against C's tree; a unit with variants is `EVIDENCED` only when every
  reached variant has such a pass; a `verify-active` full run's child rows
  anchor all 297 goldens at once.
- **`assumption_static_granularity_v1`** — file-level facts are the default,
  with two narrower granularities in use: member units and the edge's
  symbols slot (first consumer: the opt-in `android-res` scanner); no
  scanner produces symbol-level coverage of Kotlin or Python code; a change
  anywhere in a member file is a change to every member until hunk-level
  attribution exists.
- **`assumption_kotlin_scanner_fail_closed`** — a closed construct list
  over-approximates the Kotlin import graph, and every construct that defeats
  it (inline functions, `const val`, DI bindings, reflection, generated
  sources, an unreadable file) is detectable by pattern and marks the file
  opaque so a change escalates; measured on thinking_app, 42 main files
  declare `const val` or `inline fun` and 63 carry DI annotations, so
  escalation is frequent by design; each opaque branch is red-proved by a
  fixture test.
- **`assumption_annotation_is_comment_only`** — integrating an existing test
  never changes what it does: `onboard adopt` — by class, by row or from a
  verdict — and `annotate --author` insert `testmap:` comment lines at the
  fixed per-language position (never into a Python docstring, because that
  changes `__doc__`; inside the member's `testmap:unit` block for a member
  seed); `git diff -w --ignore-blank-lines` shows comments only; a file with
  no known comment leader is skipped with `ADOPT_SKIP:no-leader` and stays
  seeded; `# Covers:` prose headers are shown as `REVIEW_PROSE` context and
  read by the `prose` origin, never rewritten.

### Variants, broad tests and runners

- **`assumption_variant_universe_from_runner_list`** — a runner's `list`
  enumerates the complete universe its run filter can address, so whole-run
  selection is sound; a class absent from `list` is `UNREGISTERED`, never
  silently unfiltered; `scan --apply` persists each member's listed variants
  so `select` reads the committed table.
- **`assumption_cells_enumerable_by_plugin`** — the variant universe is
  enumerable from the project's existing routing statement through the
  runner's `list` verb (thinking_app: `matrix_classes()` crossed with the two
  membership manifests; aitasks: the rendered `tests/golden/` tree); the
  framework never infers a variant. Falsifier: tests knowable only by running
  the build — `list` may exec the build's own list task at the cost of a
  slower `scan` / `check`, since `select` never calls it.
- **`assumption_axis_sources_declarable`** — the sources that reach one
  facet value are declarable as globs (thinking_app's locale facet:
  `values-<q>/**`, `raw-<q>/**`, the per-family fonts); sources every locale
  reads are ordinary edges or one hand rule and reach every variant; the
  geometry and direction facets have no axis sources because they are
  test-side constants reached through the test-dep closure.
- **`assumption_axis_membership_declarable`** — which facet value a source
  belongs to is declarable by the people who own the suite because the
  project already routes by that shape; a source matching no axis source
  reaches units only through edges and dependencies, which select every
  variant. Falsifier: genuinely dynamic membership — declare no sources on
  that facet.
- **`assumption_batch_per_unit_timing_reportable`** — runners report
  per-unit timing inside a batch from their tool's own report (JUnit XML, `go
  test -json`, pytest junitxml), invert a report row to a registered id
  through the runner's own routing table, and JUnit XML reports each method
  with its own duration, which is what makes a variant's marginal cost
  measurable apart from its class's boot.
- **`assumption_areas_express_suite_blast_radius`** — a broad test's blast
  radius is expressible as area glob sets plus scope globs plus
  budget-exempt trigger globs plus the `reads` globs of helpers in its
  closure; what that misses surfaces through `score` as an observed trigger
  or area member.
- **`assumption_broad_tests_area_scoped`** — integration, e2e and device
  tests can be described by areas or globs whose membership changes rarely,
  so evidence-based drift (`STALE_AREA`) plus `attribute` widening is
  adequate; the calendar cadence is opt-in.
- **`assumption_existing_locks_wrappable`** — existing project locks and
  allocators (thinking_app's heavy-run lock with exit-75 admission, the
  emulator allocator) can be wrapped as resources without changing them; the
  admission and allocator kinds exec the project's commands and honour their
  exit codes, deferring on 75 until the run deadline.

### Seeding and adoption

- **`assumption_seed_sources_measured`** *(rewritten)* — one origin table
  seeds edges, each origin measured on 2026-09-16 and none below 1.0 trusted
  alone as a *heuristic*; every row carries a class — rule, measurement,
  reading or heuristic — that the autonomous floor reads. Rule:
  `static:package` (1.0). Measurement: `coverage` (0.95). Reading:
  `agent:review` (0.90 — an agent read the engine-cut packet and answered
  `verifies`, naming an assertion line the engine verified) and
  `agent:author` (0.90 — the implementing agent named a pair with both files
  on its change surface). Heuristic: `static:invocation` 0.90,
  `static:import` 0.85, `observed` 0.70, `convention` 0.60, `plan` 0.50,
  `prose` 0.30, `cochange` capped at 0.60. Confidence combines by noisy-OR
  (`static:invocation + agent:review` = 0.99), orders the queue and never
  hides a row. The reading origins' 0.90 is a prior: passive agreement with
  human per-row decisions and `onboard review --calibrate` against coverage
  facts or human rows write `agent_review.measured_confidence` when lower,
  and below `accept_min` verdict adoption stops. Seeding is partial by
  construction: the remainder is rules, waivers, author claims and
  incremental adoption.
- **`assumption_static_closure_seeds_edges`** — the test-file static closure
  is a sufficient primary seed on the target shapes and naming conventions
  are not: 398 of 400 aitasks bash tests name their subject path literally
  (the two that do not are pure fixture tests), 320 of 320 Python tests
  import a lib module, only 52 of 400 bash tests match the `test_<stem>.sh →
  aitask_<stem>.sh` convention; Go's subject is deterministic; Kotlin's is
  the same import scanner the selector uses. Only the direct relation is
  seeded, and it also supplies the review packet's anchor line. Falsifier:
  tests reaching subjects only through a dynamic dispatcher — no static
  rows; conventions plus co-change, or level 0 only.
- **`assumption_cochange_is_corroboration`** — `(t<id>)` history
  corroborates and never decides: 336 task groups in 400 aitasks commits at
  1.14 commits each, pairing a few tests with a few scripts with nothing in
  the group saying which covers which; hence 0.20 + 0.20 × groups, capped at
  0.60, ≥ 2 distinct tasks, unreachable to the 0.85 class threshold alone or
  with convention (0.84); per-commit grouping where the convention is absent;
  one `git log` pass cached by HEAD sha; `SEED_HISTORY:shallow|<n>` on a
  shallow clone.
- **`assumption_helpers_separable_by_fanin`** — within a closure, helpers are
  separable from subjects by declared helper roots and by fan-in ≥ 5 % of the
  runner's units; helpers get `test-dep` through the closure and, when they
  glob the tree, a proposed `testmap:reads`; a helper is never a review
  pair. Falsifier: a hot production module imported by most tests is
  misread as a helper — it keeps `test-dep` selection (over-selects) and
  every reclassification is listed for review.
- **`assumption_seeds_select_never_evidence`** *(rewritten)* — a seed may
  cause a test to run and may never suppress `STALE`, anchor evidence,
  satisfy `require_stamp` or count under `--strict`; a verdict on a seed
  changes what may adopt it and never whether it selects; it becomes a claim
  only through an explicit adopt — by class (with provenance), by row, from
  a `verifies` verdict or from an author claim. Autonomous profiles may seed
  everything and may adopt a class only when every member carries a rule, a
  measurement or a reading origin and clears `accept_min`; a heuristic-only
  class is never adopted headless, however high its measured precision; no
  agent path removes a seed. Falsifier: a suite so expensive that seeded
  over-selection is itself the problem — the suite budget and `--format
  tokens` are the levers, not trusting seeds.
- **`assumption_agent_can_judge_verifies`** *(new)* — an agent that reads a
  test's assertion lines beside the source's declared symbols can tell a
  test that *verifies* the source (asserts on its output, exit, side effect
  or a symbol it exports) from one that only *drives* it (runs it to build
  state for another assertion), and can name the assertion line, with
  agreement ≥ `accept_min` against human per-row decisions; the engine's
  check that the named line exists and names the source turns a free-text
  judgement into one with a machine-checkable anchor. Measured nowhere yet —
  the first labelled set is the in-gate and per-row adoptions on aitasks.
  Falsifier: `REVIEW_AGREEMENT` under `accept_min` over `calibration_min`
  pairs → `REVIEW_ORIGIN_DEMOTED`, `measured_confidence` written and verdict
  adoption stops; a project may also set `agent_review.confidence` lower
  from day one to keep verdicts as corroboration only.
- **`assumption_agent_reads_verify_vs_drive`** *(new)* — the packet is
  sufficient input for that judgement: the anchor line ±20, every assertion
  line flagged, the source's declared symbols (never its body), the prose
  header and, for a member seed, the `testmap:unit` block let an agent
  answer at least as precisely as the baseline's ten-sample human review of
  a class, because the judgement is local to the test body — does a flagged
  assertion check an output, a state or an exit status the named source
  produces? `onboard review --calibrate` measures it before it is trusted,
  against coverage facts where a coverage import exists (a measurement as
  ground truth, available headless) else against human rows; a repository
  with neither runs on the prior and prints `CALIBRATION:none`. Falsifier: a
  repository whose tests assert through an opaque harness (a golden-diff
  script that never names what it checks) — the packet has no flagged
  lines, the agent answers `unsure`, and the pair is parked and then
  `REVIEW_HUMAN` rather than guessed.
- **`assumption_wrong_positive_claim_only_overselects`** *(new)* — a wrong
  `verifies` verdict produces a stamped `covers` edge to a source the test
  only drives; its cost is a needless run of that test when the source
  changes and a `STALE` nag the evidence join heals when the test next
  passes; it never hides a coupling, never suppresses a `STALE` row on
  another edge, never anchors evidence for anything the test did not run,
  and never satisfies `UNMAPPED_SOURCE` for a source the test does not reach
  (the static closure had to contain the source for a packet to exist, or
  the author had to name it from inside the task's change surface). Because
  `drives` and `unsure` park rather than reject, no agent verdict
  under-selects at all; agent adoption errs only in the direction seeds were
  already allowed to err in. Falsifier: a project running `--strict` with
  `on_empty_selection: full` that relies on `UNMAPPED_SOURCE` to force full
  runs — a wrong positive there turns a forced full run into a selection;
  the cadence bounds it.
- **`assumption_agent_rejection_is_revocable`** *(new; resolved as "no
  agent rejection exists to revoke")* — an agent verdict never removes a
  seed: `drives` and `unsure` park it, still selecting, so a wrong `drives`
  costs a needless run and nothing else, and no revocation mechanism is
  needed. The one rejection that exists is a person's (`onboard reject`, or
  a `rejections[]` row with no `by:`), and evidence never overrules a
  person: a scored full-run miss (`PREDICTION_MISSED:<test>`) on a run whose
  change surface contains `<source>` prints
  `REJECTION_CONTRADICTED:<test>|<source>|<run>` and keeps the row for the
  person to revisit. Falsifier: a repository whose parked rows grow without
  anyone reading `REVIEW_PARKED` — the cost is over-selection time, visible
  in `onboard status`, never a missed test.
- **`assumption_session_agent_is_reviewer`** *(new)* — the agent already
  running the onboarding skill (attended or headless — the `remote` profile's
  agent is headless by construction), the `testmap_fresh` gate or the
  pre-review procedure is the default reader; no gate, verifier or engine
  path spawns a process to read, so the review pass costs the session's
  ordinary tokens (aitasks: ~2 k input tokens per pair, ~1.5 M over 36
  packets) and never a gate run's; the bulk skill and the crew form exist
  for a dedicated or parallel pass and are started by a person through a
  wrapper. Falsifier: a harness whose session cannot read 20 packets' worth
  of excerpts in one turn — lower `agent_review.batch` or `packet_lines`.
- **`assumption_headless_launch_is_explicit_opt_in`** *(new)* — no engine
  path, gate, hook or default skill flow launches a code agent, and none
  launches one in headless print mode by default: every launch of this
  feature is a framework wrapper — `ait skillrun testmap-review` (an
  interactive launch like every skill run), `ait codeagent testmap-review`
  (interactive by default; `--print` only under `--headless`, the same
  explicit opt-in `batch-review` requires, because Claude Code bills print
  mode at a higher per-token rate and the framework's shell conventions
  forbid `claude -p` without one) or `ait crew runner` (which launches every
  crew agent through `ait codeagent --agent-string … invoke raw`, `-p` only
  under the crew's `headless` launch mode); the engine validates a `--by`
  agent-string's grammar and never resolves a model. Falsifier: a CI lane
  with no terminal — for which `--headless` is the documented, explicit,
  billed choice, never a default.
- **`assumption_author_annotates_own_surface`** *(new)* — the agent that
  wrote or edited a test within a task knows which source on the same
  change surface it checks at least as well as any static seed, and its
  claim is safe to adopt because `annotate --author` is limited to pairs
  whose two files are both `COMMITTED:` or `TASK:` rows of the task's change
  surface (`AUTHOR_REFUSED:outside-change-surface` otherwise), is shown as
  `adopted(agent:author 0.90 by agent:<s>)` until a person re-stamps it, is
  flagged `AUTHOR_UNCORROBORATED` when the deps closure holds no relation
  between the pair, and rides the `(t<id>)` commit through the Step-8
  review. Falsifier: an agent stamping every touched pair to silence
  `UNMAPPED_SOURCE` — visible as a rising `AUTHOR_UNCORROBORATED` count in
  `onboard status` and `readiness`, and `agent_review.author: false` turns
  the branch off.

### Onboarding

- **`assumption_test_tools_detectable`** — every target repo's test tools
  are detectable from the tree and the project config without executing a
  build (pytest markers, `go.mod` + `_test.go`, `gradlew` + source-set
  roots, `tests/test_*.sh` + `asserts.sh`, `package.json`, a `Makefile`
  target, `test_command` / `verify_build`); verified on the five
  repositories; every `FRAMEWORK:` row carries its evidence. Falsifier:
  build-time test generation — `DETECT_UNKNOWN`, the skill asks.
- **`assumption_full_run_expressible_per_repo`** — every target's completion
  suite is `ait test --all` over its runners or one `full: true` suite
  runner generated from `test_command` with a `children:` post-processor and
  a `fallback_command:` (thinking_app's `verify-active`; thinking_backend's
  `run_script_tests.sh`, kept as `verify_build` by default; aitasks_go's `go
  test ./...`; aitasks_mobile's `./gradlew check` minus the device classes;
  aitasks' 720 units which had no suite command and gain one).
- **`assumption_onboarding_is_a_task`** — onboarding writes committed files
  across several sessions, so each level runs as an aitask the skill creates
  and claims, committing per phase under `(t<id>)`, re-entering at
  `ONBOARD_NEXT:` (a partial `review` phase included), with the level-0
  task's `tests_pass` as the first full run and the next level's task
  depending on it; a headless level-1 task is the same shape with the review
  loop as its longest phase and `finish --auto` as its last. Falsifier: a
  repo that forbids tasks on the code branch — `--no-task`.
- **`assumption_cadence_full_run_bounds_miss`** *(new)* — under
  `completion.mode: auto` a coupling the map does not know (no edge, seed,
  rule, verdict or author line) can let a task land with an affected test
  unrun, and the damage is bounded by the cadence: the miss surfaces at the
  next cadence full run, is scored against every prediction in the window
  and attributed to the earliest task whose change surface reaches the
  failing unit (culprit ids from `git log -M` when history is reachable), and
  one miss over `max_false_negatives` demotes the policy to full until
  readiness is admissible again. Falsifier: a project whose full suite is
  too expensive to run every N tasks — raise `tasks`, lower
  `selection_ratio_above`, or set `mode: full`; the window is printed by
  `--howto` and readiness, never hidden.
- **`assumption_cadence_bounds_exposure`** *(new)* — the window is a
  project-set number: at most `full_run_every.tasks` selected completion
  runs, `days` wall-clock, or the next selection whose estimate reaches
  `selection_ratio_above` of the full p95 — whichever comes first; every
  completion run prints `next_full_in:<n>`; the cadence state lives in
  `costs/policy.yaml` and is reset by every full run whatever triggered it,
  and `min_full_runs_since_map_change` keeps a fresh bulk adoption from
  flipping the policy before clean full runs have scored it. Falsifier: a
  project whose tasks land faster than its full run completes — for it
  `tasks: 1` is `full` with extra steps and the project should stay on
  `full`.

### Run surface and workflow

- **`assumption_change_surface_is_intake`** — `aitask_change_surface.sh`'s
  attribution is the intake for every `--task` path (the gate verifiers, all
  three `ait test` modes, `stale --task`, `annotate --author`'s refusal
  check): its `COMMITTED:` / `TASK:` / `OTHER:` / `UNKNOWN:` lines are piped
  to `--changes -`, selection never reads a raw git diff, an `UNKNOWN:` row
  refuses selection (advisory: `VERDICT:skip REASON:unknown_paths`);
  `<path>...` is the one explicit-list intake, `--dirty` the explicit and
  printed no-task intake, `--all` has none; before-content for a symbol
  scanner comes from `HEAD:<path>` or the parent of the first `(t<id>)`
  commit.
- **`assumption_task_resolvable_from_session`** — the worktree branch
  `aitask/<task_name>` yields the id in worktree mode; the single
  Implementing lock this user holds yields it in current-branch mode; two or
  more are `AMBIGUOUS_TASK`; gate context supplies `AIT_GATE_TASK_ID`; the
  advisory form always passes `--task`. Falsifier: an agent outside the
  workflow — `ait test --dirty`.
- **`assumption_helper_degrades_when_absent`** — `ait test --advisory` can
  always answer: engine missing → `skip:testmap_absent`; no `aitestmap/` →
  `skip:registry_absent`; `UNKNOWN:` rows → `skip:unknown_paths`; empty
  selection → `skip:no_selection`; admission refused after the deadline →
  `skip:admission_refused`; only an executed run is pass / fail; only an
  unwritable log is 3. This is what admits the pre-review procedure into
  every profile including `remote` with no per-environment conditional; the
  interactive and completion modes keep the rule that a missing engine is an
  error.
- **`assumption_gate_exit_contract_reused`** — the verifier contract
  `0/1/2/3` is reached through the existing `tests_pass` verifier running
  `test_command`; `run_project_command_key()` — the single canonical
  statement of the command exit contract — gains 75 → error
  (`command_refused`) and 3 → error (`command_errored`) for opted-in keys, so
  a post-deferral refusal or a missing engine is a verifier error the
  orchestrator retries, never a code failure and never a skip; 2 stays the
  opt-in skip; the verifier exports `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`
  and `aitask_run_project_command.sh --task-id` exports the former, so the
  legacy Step-9 path, `aitask-qa` and the gate agree by construction;
  `testmap_check` keeps its own verifier shell; advisory mode speaks the
  `0/1/2/3` domain with 75 folded into a skip reason.
- **`assumption_instructions_block_reaches_agents`** — the seeded
  agent-instructions block is inserted between `>>>aitasks` / `<<<aitasks`
  markers into every supported agent's instructions file by `ait setup` and
  refreshed on re-run and on upgrade (verified in `aitask_setup.sh`), so a
  section added to the seed reaches every project on its next setup; the
  section names no agent, carries no project specifics and stays at fourteen
  lines; the hand-maintained `CLAUDE.md` case is the level-0 task's edit.
- **`assumption_instruction_block_is_read`** — code agents load
  `CLAUDE.md` / `AGENTS.md` at session start and follow a managed block that
  names one command, as the framework already relies on for `./ait git`,
  notes and the commit format. Falsifier: a harness that ignores the file —
  `ait test --howto` is the one-call fallback.
<!-- /section: assumptions -->
<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Every tradeoff of the baseline is inherited; the ones the agent-driven loop
touches are rewritten in place (`tradeoff_autonomous_confirmation_weak`,
`tradeoff_bulk_confirmation_granularity`, `tradeoff_seed_precision`,
`tradeoff_seed_noise`, `tradeoff_fail_closed_bootstrap_cost`,
`tradeoff_one_gate_not_two`, `tradeoff_onboarding_partial_coverage`,
`tradeoff_two_edge_states_during_adoption`, `tradeoff_attribution_risk`,
`tradeoff_stamp_churn`, `tradeoff_accept_rewrites_history`,
`tradeoff_workflow_surface_growth`) and nine are new. Advantages first, then
costs and risks by area, each with its mitigation.

### Advantages

- **`tradeoff_computed_vs_prose`** — selection is computed, explained and
  scored rather than remembered, and so are the run surface and, now,
  acceptance: `--howto` is generated, the instructions section is identical
  everywhere, every adopted row carries who accepted it and what they read,
  and a 200-line testing chapter becomes ten declared `notes:` lines plus
  `docs:` pointers reached through one verb; thinking_app's "shared
  component → full gate" rule is an axis join, a fan-out and an `ESCALATE:`
  line.
- **`tradeoff_engine_speed_enables_per_task_use`** — sub-second select /
  check / stale on a 720-test repo, sub-250 ms select over 297 variants
  with axis expansion, and sub-300 ms packet assembly make selection and
  review overhead negligible against the shortest test and let `check` run
  at every commit step.
- **`tradeoff_real_scheduler`** — goroutines plus `flock(2)` give correct
  cross-worktree contention and a critical-path report; the shell suite and
  the pytest lane get the enforced do-not-overlap that is only a comment
  today; a variant batch is one Gradle invocation holding one heavy-run slot.
- **`tradeoff_noarch_packages_preserved`** — Homebrew, AUR, .deb, .rpm and
  the tarball ship nothing compiled; the per-arch concern is one release job
  and one setup function.
- **`tradeoff_one_gate_not_two`** *(rewritten)* — *advantage:* one
  completion gate whose behaviour is a committed policy; an agent learns one
  command and one gate; the legacy Step-9 path and `aitask-qa` reach the
  selective lane through `test_command`; the flip is one line after
  readiness, written by a person under `selected` or by the engine under
  `auto`, so a headless repository reaches the selective lane by itself.
  *Disadvantage:* the gate's meaning now depends on `config.yaml` and, under
  `auto`, on the run's readiness and cadence state, so a ledger `tests_pass:
  pass` says even less by itself about what ran, and under `auto` not even a
  person decided that it should not — mitigated by
  `result="MODE:<full|selected>|<n>|policy:<mode>|next_full_in:<n>|cadence:<trigger>"`
  on the gate-run block, the `POLICY:auto|…` line on every completion run,
  the `gate-` run-id prefix, `POLICY_FLIPPED` and `POLICY_DEMOTED` being
  loud, `approved_by` naming `engine:readiness@<run>` in a file of its own
  so no one mistakes it for a person's approval, and `readiness` printing
  what `--gate` would run and when the next full run is due.
- **`tradeoff_loop_closes_without_a_person`** *(new)* — *advantage:* the
  value the mandate names is realised — seeding, adoption, the policy flip
  and the safety net are each performed by a machine or an agent under a
  committed policy, so a repository onboarded by a headless profile reaches
  a per-change-set completion gate within `min_scored_full_runs +
  min_full_runs_since_map_change` tasks of level 0 with nobody typing
  anything, and what remains human is a printed list (`REVIEW_PARKED`,
  `REVIEW_HUMAN`, `KIND_PROPOSALS`, axes) rather than an assumed step.
  *Disadvantage:* in such a repository the map's provenance is mostly `by:
  agent`, and a reader who wants human-reviewed claims must look for the
  `human` split in `onboard status` — never hidden, but no longer the
  default state; and disabling the loop (`agent_review.enabled: false`,
  `completion.mode: full`) is now a deliberate act a project must take,
  where the baseline made human acceptance the only path.

### Engine and distribution

- **`tradeoff_compiled_component_cost`** — the framework gains a compiled
  component: engine contributors need Go, a release fails if `go test` fails,
  install gains a fetch and checksum step; mitigated by one `build.sh`
  matrix, `ait engine build`, and the engine being optional until a testmap
  gate is enabled.
- **`tradeoff_two_toolchains`** — bash and Go in one framework; mitigated by
  the boundary rule, `engine-check.yml`, and Go source confined to `engine/`
  and excluded from the tarball.
- **`tradeoff_setup_network_fetch`** — `ait setup` gains its first
  self-downloaded release asset; mitigated by reusing the URL family
  `install.sh` already uses, SHA256SUMS verification, the `.sha256` sidecar,
  `--no-testmap` / `AIT_TESTMAP_FETCH=0`, the shim never fetching, and setup
  never depending on the binary for anything else.
- **`tradeoff_engine_version_skew`** — several ~10 MB binaries under
  `$AITASKS_HOME/engine/` for a user on several framework versions; mitigated
  by exact-version resolution and `ait engine prune` against the project
  registry, never count-based.
- **`tradeoff_strict_version_handshake`** — the binary must match `VERSION`
  exactly, so an upgrade on a host that cannot fetch leaves `ait testmap`
  refusing until a matching binary is supplied; intended fail-closed
  behaviour; the error names the fix and the path.
- **`tradeoff_engine_absent_on_host`** — an unsigned macOS binary or a
  blocked download leaves a host without an engine; mitigated by
  `ENGINE_MISSING` naming the path and repair verb, the source fallbacks, and
  declared gates exiting 3 (never skip). Two deliberate, printed exceptions:
  `ait test --advisory` reports `VERDICT:skip REASON:testmap_absent` so the
  pre-review run in task-workflow, pickrem and pickweb (which has no `ait
  setup`) continues, and a project may set `completion.engine_absent:
  fallback_command` for the Web lane with `MODE:fallback` visible.
- **`tradeoff_fallback_runs_more`** — with the engine absent and
  `engine_absent: fallback_command`, completion runs the pre-onboarding suite
  command — never less than before, never selective, no per-unit results, no
  anchors, no scoring; mitigated by the default being `error`, by
  `ENGINE_MISSING` naming the repair, and by `MODE:fallback` in the result.

### The per-user root

- **`tradeoff_two_user_roots`** — until `ait engine home --migrate` runs, a
  host carries `~/.aitask/` and `~/.aitasks/` side by side and a user who
  deletes one removes half the install; mitigated by one variable with one
  library owner, setup printing both roots and the `HOME_LEGACY:` hint,
  `ENGINE_MISSING` naming the exact path, `ait engine home` reporting the
  state, a test that fails if any script of this feature names `~/.aitask/`,
  and the migration verb existing now.
- **`tradeoff_split_home_rejected`** — installing only the engine at
  `~/.aitasks/engine/` and leaving the rest at `~/.aitask/` forever would be
  zero-risk but would leave two dot-directories one character apart holding
  halves of one install, explained forever by every doc page; chosen: the
  split as the transition, the migration designed, shipped as an explicit
  verb and reversible through the symlink, becoming the default in a named
  follow-up.
- **`tradeoff_home_migration_window`** — the migration has a sub-millisecond
  window between `rmdir ~/.aitask` and `ln -s` during which a process that
  hardcodes the legacy path sees ENOENT; narrowed by the flock, symlinking
  immediately after the rmdir, and refusing while another `ait` holds the
  home lock — not eliminated. Measured surface: 8 framework files with 35
  references, 20 test files, 18 doc files, the venv's absolute shebangs and
  two symlink trees — none rewritten, all resolving through the symlink. The
  refusal cases are the ones a designer does not see on their own host (the
  known-entry set once lacked `pypy_venv`), which is why the verb is explicit
  in this release.

### Map and registry structure

- **`tradeoff_registry_directory_complexity`** — a merged registry directory
  needs more CLI logic than a single file: eight tables, two generated files,
  two ledgers (`onboard.yaml`, `costs/policy.yaml`), an id grammar with
  member and variant fragments and a handful of provenance fields; kept to
  one directory with one merge rule in one Go package with golden tests, no
  second plugin directory or generated cell table, and the axis table empty
  for every project that declares none.
- **`tradeoff_cell_table_size`** — instead of ~2,500 generated cell rows,
  `_scanned.yaml` carries 49 member rows with a `variants:` list of at most
  ten values; the price is that `scan` and `check` exec each runner's `list`
  and a matrix added to the manifests is invisible to `select` until the next
  `scan --apply`, which `check` reports as drift the same day. Enumerating
  at every `select` was rejected because it would put a build-adjacent exec
  on the hot path of every gate.
- **`tradeoff_member_annotation_drift`** — a member's annotation is keyed by
  name and the runner's `list` keys the same member by another artifact; a
  rename on one side orphans the other; mitigated by `UNANNOTATED_MEMBER` and
  `DEAD_MEMBER`, both fail-closed, by `scan --apply` refusing rather than
  guessing, and by thinking_app's own manifest / `@Test` drift loop.
- **`tradeoff_static_scanner_overselection`** — static scanners overselect on
  hot files and cannot see runtime coupling; a shared component fans out to
  most screens on every matrix, which is the correct answer and close to a
  full run; kind ranking, the suite budget and `--budget-s` trim scoped rows
  first, the `android-res` scanner narrows a catalog edit, a project scanner
  plugin can narrow a hot resource file, and hunk-level attribution is the
  later tool.
- **`tradeoff_area_glob_coarseness`** — area and scope globs are coarser
  than edges: a broad area over-selects on every edit inside it and a scoped
  test depending on a file outside its scope is under-selected until a full
  run scores it; mitigated by the suite budget with explicit `DEFERRED`
  lines, budget-exempt triggers and `reads` globs, and the missing-trigger /
  area-too-narrow attribution path.
- **`tradeoff_broad_scope_coarseness`** — a test scoped to a large area is
  selected for any change inside it; mitigated by ranking last at its
  distance, running only after a green unit wave, being cut first by the
  budget with the cut printed, and the cost visible in `schedule`.
- **`tradeoff_axis_declaration_burden`** — axes are a third authoring
  surface and a wrong declaration gives confidently wrong selection;
  thinking_app must declare ten matrix values with three facets, four locale
  source-glob sets, one `values/**` rule, one runner script and one
  `testmap:axis` line per non-capturing coordinate test; mitigated by
  membership being declarative and checkable (`DEAD_AXIS_SOURCE`,
  `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`, `axes --explain`) and by an
  undeclared source reaching every variant.
- **`tradeoff_axis_projection_coarseness`** — the default axis join is
  file-level: a one-key edit to `values-ru/strings.xml` selects every
  enrolled screen on both ru matrices (~65 variants) rather than the screens
  naming that key; mitigated by the opt-in `android-res` symbol scanner,
  `select --format tokens` feeding the project's own preview loop, and the
  group-costed budget.
- **`tradeoff_intersection_can_underselect`** — an axis-source hit is
  sharper than a file edge and can miss a coupling a plain `covers` edge
  would have caught (a font family assigned to the wrong locale's glob);
  narrowed structurally: under-selection needs an explicit, reviewable wrong
  glob, never an omission; `score` raises missing-axis-source; observed
  sources only widen; every variant row prints the facet value that placed
  it.
- **`tradeoff_whole_run_filter_soundness`** — where a runner's filter
  restricts a whole run (Gradle `--tests`), every class not selected is
  silently not run, so a narrow selection is only as sound as the test-side
  closure, the `reads` globs and the opaque contract; mitigated by `list`
  enumerating the whole universe, the test-dep closure over abstract bases
  and helpers, `testmap:reads` on tree-scanning helpers, `ESCALATE` on opaque
  files, red-proof fixtures per branch, `readiness` gating the policy flip on
  scored history, and the full suite staying the completion gate until then.
- **`tradeoff_resource_declaration_completeness`** — declared resources are
  only as complete as the declarations; an undeclared interference is
  invisible until a full run or a probe finds it; serial-by-default at
  bootstrap means declarations are reviewed in the schedule report before
  concurrency is trusted.

### Freshness and evidence

- **`tradeoff_stamp_churn`** *(rewritten)* — confirming stamps rewrites test
  files (a source named by 72 tests could yield a 72-file diff; `EVIDENCED`
  needs no rewrite, `--confirm-source` is one commit, member blocks keep a
  screen's stamps in one file, variants carry no stamp); onboarding adds the
  largest rewrite of all — level 1 on aitasks touches ~720 test files with
  one to eight comment lines each, and a headless level 1 now performs it
  without a person — mitigated by seeds selecting without any rewrite,
  adoption batched per class, per area or per review batch into `chore:
  Onboard testmap — adopt <class|area> | review (t<id>)` commits that add
  comment lines only (`git blame -w` and every runner ignore them),
  `max_pairs_per_run` splitting the rewrite across runs,
  `ADOPT_REFUSED:dirty-foreign`, the reviewed `(t<id>)` commit, and the
  in-gate path that adopts a file's seeds only when a task already has it
  open.
- **`tradeoff_flaky_pass_anchors`** — a flaky pass anchors evidence as surely
  as a real one; mitigated by per-run status in the ledger exposing a flake
  rate per id, and an id above `flake_threshold` being excluded from the
  evidence join.
- **`tradeoff_evidence_requires_reachable_history`** — the evidence join can
  only suppress a `STALE` row when the anchoring commit is reachable, so a
  depth-1 clone sees the precise digest verdict with no self-healing; the
  safe direction, and why `stale --strict` fails only on `STALE_PATH`; a
  repo-wide `stale --all --strict` job should run on a full clone.
- **`tradeoff_autonomous_confirmation_weak`** *(rewritten)* — autonomous
  acts on the map are weaker than review, and this design has four of them:
  `--confirm-evidenced` (a green run on every reached variant whose tree
  held the current bytes re-stamps an edge, `confirmed_by: <run_id>`,
  re-opened by a later miss — still the only bulk *re-stamp* an autonomous
  profile may run), `adopt --auto` over rule and measurement classes (a
  language fact or a coverage run — a measurement, not a judgement), agent
  acceptance (`agent:review` over an engine-cut packet anchored to an
  assertion line the engine checked, `agent:author` inside the task's own
  diff — a fresh stamp whose `adopted.yaml` row carries `by: agent`, the run
  id, the rationale and the packet digest, all displayed by `stale`,
  `explain`, `check` and `readiness`, counted as `AGENT_ADOPTED`, and
  calibrated with demotion below `accept_min`) and the `auto` policy flip
  (the engine's, bounded by the cadence and reversed by the demotion,
  recorded in `costs/policy.yaml` rather than `config.yaml`). What no
  autonomous path may do: confirm a `STALE` row, reject a seed, change a
  kind, or make the completion gate run less without a scheduled full run
  behind it; `agent_review.enabled: false` restores the human-only adoption
  exactly. The residual risk moved from reviewer fatigue on a thousand seeds
  to a wrong verdict stamping an over-claiming edge, or a policy flip
  letting a miss survive until the next cadence run — both visible in
  provenance and the ledger `result=` field, both bounded by knobs
  `config.yaml` exposes (`agent_review.confidence`, `full_run_every`, `mode:
  full`).
- **`tradeoff_attribution_risk`** *(rewritten)* — an agent that edits
  sources without attributing produces a map that looks current and is not;
  narrowed four ways: such a source shows as `STALE` in the next task and as
  a stale mark on every selection; the Step-7 run reports
  `UNMAPPED_SOURCE:<path>` at the moment the source is introduced and the
  pre-review procedure offers annotate / propose / waiver right there; the
  authoring agent maps its own new sources at that step through `annotate
  --author`, so the "looks current and is not" window closes during the task
  in autonomous profiles too; and under a full completion policy every miss
  is counted by the automatic score within one task. What still escapes is a
  coupling to a source that already has some edge, which only `score` can
  find.
- **`tradeoff_batch_misreport_risk`** — a batch runner that misreports
  per-unit results corrupts attribution, cost and evidence (a false pass
  could manufacture an `EVIDENCED` row); the JUnit inversion and the
  method-granularity zero-match trap are two places to misreport; mitigated
  by `units_expected` / `units_reported` reconciliation per id, a row
  inverting to no registered id and zero-reported-some-expected both being
  mechanism failures, and no line from an invocation with a cause anchoring.

### Seeding, adoption and onboarding

- **`tradeoff_seed_noise`** *(rewritten)* — heuristic seeds are wrong in
  both directions (a convention pairs a homonym, an import names a helper,
  co-change ties every file of a wide task to every test of it —
  thinking_app: 7.2 main files per co-changing commit); mitigated by seeds
  selecting and never claiming, confidence ordering review rather than
  gating it, the 0.60 co-change cap and `min_cochange 2`, direct imports
  only, helpers separated before scoring, evidence beside every row,
  rejection memory, and the suite budget and `--format tokens` where
  over-selection is expensive; the reviewer fatigue that remained on a
  1,000-seed queue is now the review pass's job — a noisy seed gets a
  `drives` or `unsure` verdict and is parked, still selecting, and a person
  sees `REVIEW_PARKED:<n>` instead of a thousand rows; what remains is that
  parked rows still over-select until a person rejects them, and class
  adoption with samples, per-area batches and the in-gate incremental path
  spread that over time.
- **`tradeoff_seed_precision`** *(rewritten)* — an adopted `covers` edge is
  a machine claim in a human annotation's clothes: the closure says the test
  *executes* the script, not that it *verifies* it, and under a class-level
  yes a test that drives three scripts to set up one adopts edges to all
  three. This is exactly the gap the review pass closes — the reader marks
  the two set-up scripts `drives` (parked, still selecting) and only the
  third `verifies`, and the intake adopts one edge, not three; with agent
  adoption an adopted edge is a *reading's* claim, and the reading answers
  the executes-vs-verifies question the closure could not. Narrowed further
  by the `adopted.yaml` provenance and `by` shown in `stale` / `explain`,
  `ADOPTED_UNREVIEWED` and `AGENT_ADOPTED` in `readiness`, the over-claim
  direction only over-selecting, the 0.85 threshold keeping heuristic-only
  edges out of a person's class adoption, the packet flagging assertion
  lines so the verdict is drawn from evidence and stores its anchor, digest
  and rationale, `unsure` as an allowed answer so the agent is never forced
  to guess, calibration against coverage or human rows before the origin is
  trusted, three samples per class, and the seeded state existing at all for
  a project that wants no machine claims (`agent_review.enabled: false`); a
  wrong `verifies` reproduces the original over-claim for one pair with
  `agent:review` in its provenance; a coupling the closure does not contain
  is caught by the author's annotation when the task that creates it runs
  the pre-review procedure, and otherwise only by a full run's score.
- **`tradeoff_two_edge_states_during_adoption`** *(rewritten)* — until both
  queues are empty a repo has four provenances of edge a reader must keep
  apart — seeded (selecting only, parked or not), adopted by human
  (stamped, class-accepted with a provenance row), adopted by agent or auto
  (stamped, a reading's or a rule's claim with `by:`, run, rationale and
  packet digest) and reviewed (stamped, accepted per pair by a person);
  mitigated by the seeded origin or `adopted(... by <who>)` printed on every
  row, the `human / agent / auto` split on `SEEDED:` / `ADOPTED:` in `check`,
  `stale --all`, `readiness` and `--howto`, `onboard status` as the one place
  the ratios live, and the rule that no seed and no agent verdict ever
  changes a freshness verdict on another edge; the cost the baseline
  recorded — `--strict` waiting on adoption forever in a repo no one reviews
  — is removed for headless repositories and replaced by the bounded
  exposure window recorded under `tradeoff_auto_policy_exposure_window`;
  "never adopts" is now a choice (`agent_review.enabled: false`) rather than
  the default outcome of nobody having time.
- **`tradeoff_agent_judgement_unmeasured`** *(new)* — `agent:review`'s 0.90
  is a provisional number: no measurement of an agent's *verifies* precision
  exists on day one, and a confident wrong verdict stamps a claim in the map
  with a rationale that reads well; narrowed by the assertion-line anchor the
  engine checks (a verdict must point at a real line naming the source,
  `VERDICT_INVALID` otherwise), by the verdict attaching only to an existing
  seed (the agent corroborates and never invents a pair), by
  `REVIEW_AGREEMENT` against every human per-row decision and `--calibrate`
  against coverage facts, both writing `measured_confidence` and stopping
  verdict adoption below `accept_min` over `calibration_min` pairs, by `by:
  agent:<s>` in every provenance row and `adopted(...+agent:review)` on
  every `stale` / `explain` line, by a wrong verdict over-claiming (over-selects,
  then is confirmed or retargeted at `testmap_fresh` like any adopted edge)
  and never under-selecting, and by the per-project `agent_review.confidence`
  knob; what remains is the first thirty labelled pairs, during which the
  number is trust, and a purely headless project with no coverage that never
  labels a pair (`CALIBRATION:none` printed, the provisional number
  standing).
- **`tradeoff_wrong_positive_invisible_to_score`** *(new)* — risk: a wrong
  `verifies` verdict is never detected by the feedback loop, because a
  claimed edge that should not exist can only over-select and score measures
  under-selection; its cost — needless runs of that test when the driven
  source changes, `STALE` nags on a pair the evidence join heals when the
  test passes — is bounded but accumulates silently in the `AGENT_ADOPTED`
  share. Mitigated by the packet flagging assertion lines so the verdict is
  drawn from evidence rather than from the file name, by the anchor check,
  by `unsure` and `REVIEW_HUMAN` so the agent is never forced to guess, by
  calibration before the origin is trusted and `measured_confidence`
  lowering its weight where calibration is poor, by the stored packet digest
  and rationale letting a later reader see what the agent saw, by the human
  re-stamp path deleting the provenance row, and by `onboard status`
  reporting the agent share so a maintainer can sample it. What remains: a
  repository with neither coverage nor human-reviewed rows has no
  calibration ground truth, runs on the 0.90 prior, and `readiness` states
  `CALIBRATION:none` rather than pretending to a measurement.
- **`tradeoff_cadence_window_misses`** *(new)* — under `auto` a coupling no
  edge, seed, rule, verdict or author line knows lets a task land with an
  affected test unrun until the next cadence full run; the miss is then
  scored against every prediction in the window and attributed by change
  surface and history rather than pinned to the task that happened to
  trigger the full run; narrowed by the three cadence triggers being
  required (`cadence_declared`), by `selection_ratio_above` running full
  whenever the saving is small, by one miss over `max_false_negatives`
  demoting to full, by `min_full_runs_since_map_change` holding the flip
  until a bulk adoption has been scored, by `--howto` and `readiness`
  printing the window, and by `mode: full` remaining the one-line opt-out
  with the human `--policy selected` flip unchanged; the cost is real and
  per-project — `config.yaml` exposes it rather than the design hiding it.
- **`tradeoff_auto_policy_exposure_window`** *(new)* — the size of that
  window is a project choice, and it replaces reviewer fatigue as the
  residual risk: `full_run_every.tasks` (default 5) bounds it in tasks,
  `days` (7) in time, `selection_ratio_above` (0.60) makes the
  cheap-to-run-full case run full and score for free; every completion run
  prints `next_full_in:<n>`; the demotion still fires on the first scored
  miss; and a project that cannot accept any window keeps `full` or a
  human-flipped `selected`. What remains: up to `tasks − 1` tasks may merge
  on a wrong selection before the miss is scored, and their dependents may
  have built on them — `blocks_dependents` on `tests_pass` does not help
  because the gate passed; the honest mitigation is the number itself,
  chosen with the measured saving in view and printed on every run.
- **`tradeoff_periodic_full_run_cost`** *(new)* — the cadence spends full
  runs a human flip would not — one in every `tasks` completion runs plus
  the `days` and ratio triggers. On aitasks (p95 ≈ 400 s full, typical
  selection ≈ 40 s) `tasks: 5` keeps about 80 % of the saving; on
  thinking_app (1,180 s full) the same cadence keeps about 75 % and the
  project may raise `tasks` once its calibration and agreement counters
  have been steady for a while. Mitigated by the ratio trigger (a selection
  that would cost ≥ 60 % of full runs full and resets the counter for free),
  by every full run doing double duty (evidence anchors, cost fold, score),
  by the cadence living in `config.yaml` beside the policy so it is a
  declaration rather than a surprise, and by `readiness` printing the
  cadence with the measured saving.
- **`tradeoff_review_token_cost`** *(new)* — the review pass is paid in
  agent tokens, not engine time: ~2 k input tokens per pair, ~1.5 M for
  aitasks' ~720 heuristic pairs in 36 packets, more for thinking_app's
  Kotlin excerpts, and a re-read whenever a test's bytes change; mitigated
  by the `reviews[]` memo (a pair is read once per test blob per reader),
  batching by test file so one excerpt serves several pairs, the packet
  excluding source bodies and capping test excerpts at `packet_lines`,
  `--class` limiting a pass to the origins worth reading (`static:*` first,
  `convention` only when nothing else corroborates), rule and measurement
  classes needing no reading at all, `max_pairs_per_run` bounding one run
  with the phase resuming, and the in-gate path reviewing only touched
  files; no gate or verifier ever pays it.
- **`tradeoff_agent_review_token_cost`** *(new)* — where the tokens are
  paid matters as much as how many: the in-gate and authoring sites read
  inside a session that already has the files open (no extra launch, the
  session's ordinary rate); a bulk pass through `ait skillrun testmap-review`
  is an interactive launch at the same rate; only `ait codeagent
  testmap-review --headless` and a crew whose launch mode is `headless` pay
  Claude Code's print-mode rate, and both are explicit flags a person sets
  rather than a default of any path; the engine, the gates and the
  verifiers launch nothing. What remains is that a parallel crew pass is the
  fastest way through a large queue and the most expensive per token, which
  the `ait crew runner` line a person must start makes a visible choice.
- **`tradeoff_bulk_confirmation_granularity`** *(rewritten)* — a person's
  class adoption (398 static edges in one answer) trades review depth for
  feasibility; the review pass restores per-pair depth at feasibility's
  price — every pair is read, but by an agent, and a class-level human yes
  over pre-filled verdicts is still one answer; mitigated by the
  three-sample display, `review a sample` drawing ten random members with
  their signals and the agent's verdict and rationale beside each,
  `--accept-min`, `--scope` onboarding one area per task, the `adopted.yaml`
  provenance with `by:` so nothing pretends to be a per-pair human review,
  `readiness` reporting `ADOPTED_UNREVIEWED` and `AGENT_ADOPTED`, the per-row
  path for anyone who wants depth, the attended choice per batch between
  confirm-each / trust-batch, autonomous adoption limited to rule,
  measurement and reading origins, and kind changes confirmed individually
  by a person because a wrong kind changes staleness semantics.
- **`tradeoff_accept_rewrites_history`** *(rewritten)* — adoption inserts
  comment lines into hundreds of test files, so `git blame` on any test
  header points at the adoption commit and a concurrent task editing the
  same file hits a header conflict; mitigated by fixed insertion positions,
  batch commits named for what they are, the in-task incremental path,
  `ADOPT_REFUSED:dirty-foreign` and `REWRITE_CONFLICT`; author annotations
  add one to three lines per task inside a diff the task already owns; the
  bulk rewrite now also happens headless; a project that wants no comment
  churn keeps seeds unadopted (`agent_review.enabled: false`) and accepts
  selection-only enforcement, reported as such.
- **`tradeoff_onboarding_partial_coverage`** *(rewritten)* — onboarding
  cannot map what no origin reaches (thinking_app's same-package tests,
  fixture-driven tests, any source with no static, convention, plan, prose,
  co-change or coverage relation), so a freshly onboarded repo has
  `UNMAPPED_SOURCE` rows and area-only coverage for a share of its tree;
  mitigated by the waivers phase (rules for hot directories, expiring
  waivers for the rest) so `check` can be enabled non-strict, opt-in
  per-unit coverage (now auto-adoptable, so turning it on maps and claims
  in one step), the authoring agent stamping every coupling a task creates
  from now on — the same-package gap on thinking_app closes incrementally
  through `agent:author` as tasks touch pairs, not through onboarding — and
  the full gate staying the completion policy until admissible; the honest
  reading of `onboard status` after one headless session is "selecting on
  most tests, claiming on the measured and the verified, the rest parked",
  treated as a state, not a failure — and the backlog no origin reaches is
  still a person's or the next task's.
- **`tradeoff_fail_closed_bootstrap_cost`** *(rewritten)* — fail-closed
  enforcement means each repo needs a waiver pass before `testmap_check` can
  be enabled, a first green full run before `require_stamp` and `--strict`,
  a green runner list before structural rules can fail, and
  `min_scored_full_runs` plus `min_full_runs_since_map_change` before the
  policy may reach the selection; narrowed by making the bootstrap one
  aitask per level that the skill creates and runs — `detect` and `seed`
  read-only until `--write` / `--apply`, level 0 writing only registry files
  and seeds, the seeder replacing most of the hand waiver pass (88 % of bash
  and 80 % of Python tests on aitasks seed at least one edge), the level-0
  task's own `tests_pass` being the first anchoring full run,
  `bootstrap_until` set to +90 days, adoption incremental by class, area,
  review batch, in-gate or at authoring, and `readiness` printing `LEVEL` /
  `NEXT`; one cost the baseline carried is removed — a repo is no longer
  level 0 "until a human adopts level 1", because a headless profile adopts
  by rule, measurement and reading and `auto` flips the policy when the
  scored history allows; what remains is real: kinds and axes are human,
  parked and `REVIEW_HUMAN` pairs wait for a person, the calibration prior
  runs unmeasured where no ground truth exists, the review loop is a long
  session paid in tokens, and the required full runs must still happen.
- **`tradeoff_verify_build_wired_suites`** — a suite wired as `verify_build`
  (thinking_backend's `run_script_tests.sh`, which also enforces a shellcheck
  baseline) cannot be onboarded mechanically: moving it would drop the lint
  half from `build_verified`, leaving it would run the suite twice at
  completion; `detect` reports `SUITE_CANDIDATE:verify_build` and the skill
  asks (keep and add `test_command: ./ait test`; or split the script),
  defaulting to keep and recording the answer; headless keeps.

### Run surface and workflow

- **`tradeoff_dispatcher_verb_added`** — `ait test` is a new top-level verb
  beside `ait testmap`, two surfaces for one engine; justified by the
  extension-points rule (a human plausibly types `ait test`, and the seed
  instruction needs one memorable verb), kept thin (mode / task / intake /
  policy / fallback / advisory only), with `ait testmap` staying the
  maintainer surface (`annotate --author` is a `testmap` subverb, not a new
  dispatcher verb); removing a verb later is a breaking change, so
  `--howto` documents `ait test` as the stable one.
- **`tradeoff_generated_brief_limits`** — a brief computed from the registry
  cannot say what a project's people know about when a narrow run is
  acceptable or why RTL is the design gate; mitigated by `config.yaml docs:`
  (named paths one hop away) and `notes:` (≤ 10 verbatim lines for the rules
  that must not be one hop away), and by the seeded instructions telling
  agents to read `--howto` before touching a test tool; `notes:` is still
  prose an agent may misread, which the gates and the full completion policy
  backstop.
- **`tradeoff_workflow_surface_growth`** *(rewritten)* — the seam adds one
  task-workflow procedure file, one profile key, one dispatcher verb, one
  skill-invoked script with a second mode (five allowlist touchpoints pinned
  by `tests/test_touchpoint_count_contract.sh`), a Step-7 render change
  across every profile × agent golden, one build-verification branch, two
  `aitask-qa` edits, a seed-instructions edit, two profile-aware skills with
  wrapper surfaces (onboard, review), one rewritten gate skill, one
  `codeagent` operation and three `models_*.json` keys; mitigated by all of
  it degrading to a printed skip where the engine is absent (no environment
  conditionals), by the advisory mode reusing the exact `VERDICT:` /
  `REASON:` contract and capture form the build-verification path already
  teaches, by there being one script rather than two, by every agent launch
  reusing the wrappers the framework already has rather than adding a
  launcher, and by `aitask_skill_verify.sh` plus the goldens catching a
  drifted render before commit.
<!-- /section: tradeoffs -->
<!-- section: open_questions -->
## Open Questions

1. Should `affected_tests` default to `run` or `show` when a repository's
   affected run is expensive (thinking_app: one Gradle boot under the
   heavy-run lock, ~40 s minimum)? Proposed: `run`, because the scheduler
   defers on a refused slot and the estimate is printed first; a project may
   set `show` in its profile.
2. Should a person's `onboard adopt --class static:invocation` skip the
   ten-sample review once the review pass has run over the class — the
   verdicts are per pair and the sample would re-read what the agent read?
   Proposed: yes when every pair of the class carries a verdict and
   `REVIEW_AGREEMENT` or `CALIBRATION` is at or above `accept_min`;
   otherwise the sample stays.
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
   statement, and `approved_by.statement` points at it; under `auto` the
   statement is the readiness lines themselves, stored in
   `costs/policy.yaml`.
6. `aitask_lock.sh --list-mine` is a new verb on an existing script; is an
   `ait ls`-based query (`status Implementing`, `assigned_to` = me) preferable
   so no lock-format knowledge leaves the lock script? Either satisfies the
   resolution rule; the lock is proposed because it is host-scoped.
7. Should `onboard finish` refuse while any unparked pending seeds remain,
   or accept a user-set threshold? Proposed: threshold, default 0, printed
   in `status`; parked and `REVIEW_HUMAN` rows never block `finish`.
8. Should the `full` suite wrapper's `children:` post-processor for bash-file
   tests infer per-file results from the runner's own per-file exit or require
   junit-style output? Proposed: the per-file exit; a monolithic script gets
   suite-level evidence only.
9. Should `readiness` count only scored predictions whose selection was
   non-trivial (at least one unit) toward `min_scored_full_runs`? A
   `no_selection` advisory run scored against a green full run says nothing.
   Proposed: yes.
10. Should an `adopted.yaml` row age out — an edge that has been `EVIDENCED`
    by N scored full runs without a miss becoming reviewed automatically?
    Proposed: no in v1; evidence removes nags, it does not review claims, and
    `ADOPTED_UNREVIEWED` is meant to be read — the same answer for `by:
    agent` and `by: auto` rows, where "reviewed" would otherwise come to mean
    "old".
11. The engine-level questions recorded before the adoption layer existed
    (scanner plugin contracts, symbol-level attribution, the default-flip of
    the home migration) remain open and are not restated here; the one about
    aitasks_mobile's source sets is answered: they are runner / kind
    distinctions, not an axis.
12. Should `detect --write` default `completion.mode` to `auto` in attended
    onboarding, or to `full` with `auto` opt-in? Proposed: `auto`, shown and
    confirmed in the config table with its cadence, because until
    `ADMISSIBLE` it is `full` byte for byte and the counter-argument — a
    project should choose to let its gate shrink, not discover that it did —
    is met by the confirmation rather than by a different default.
13. Should a `drives` verdict ever remove selection — say after N cadence
    full runs in which the parked test never failed for a change to that
    source? Proposed: no; a person rejects, and `REVIEW_PARKED` is the list
    they read; a test that only drives a source is still coupled to it.
14. What are the right cadence defaults per repository shape? `5 / 0.60 / 7`
    is a guess for aitasks (full ≈ 111 s); thinking_app's `verify-active`
    (p95 1180 s) may want `10 / 0.50 / 14`. Proposed: `detect --write` scales
    `tasks` from the first full run's p95 after `full_run`, printed; a
    project with dependents building on every task may want `2`.
15. Where does calibration come from in a purely headless project with no
    coverage import that never adopts per row? Proposed: nowhere —
    `CALIBRATION:none` and `REVIEW_AGREEMENT:none` are printed, the
    provisional 0.90 stands, and `agent_review.confidence` is the project's
    knob; a second, cheaper cross-check (a different model re-reading a
    random 5 % through `ait codeagent testmap-review --agent-string
    <other>`) is a follow-up, not v1.
16. Should the review packet include the source *body* for small sources
    (< 40 lines)? Proposed: no in v1 — the symbol list keeps the packet
    bounded and the question is about the test, not the source;
    `--source-lines <n>` is reserved for a project whose sources are small.
17. Should `agent:author` also accept a test outside the change surface
    whose static closure reaches the source? Proposed: no in v1 — a claim
    about a test the agent did not touch is a review verdict, not an author
    claim, and the in-gate step reads it the next time that test file is
    touched.
18. Should `verified.testmap-review` in `models_<agent>.json` gate which
    models may write `--by`? Proposed: no — `verified` is informational
    across every operation today; a project that wants a floor sets
    `agent_review.min_verified: <n>` (reserved, not implemented).
<!-- /section: open_questions -->

<!-- section: conflict_resolutions [dimensions: component_agent_review, component_agent_review_pass, component_auto_policy, component_author_annotation, component_adoption_ledger, component_completion_policy, component_onboarding_skill, component_skill, assumption_agent_rejection_is_revocable, assumption_seeds_select_never_evidence, assumption_headless_launch_is_explicit_opt_in, tradeoff_*] -->
## Conflict Resolutions

The two parents, n011 and n012, are siblings of the same baseline (n010)
and answer the same mandate; 106 of their shared dimensions are identical
and were carried verbatim. The conflicts below are the design-level ones;
every other difference was additive and was joined. Provenance appears
here and in the *Components* headings only; the body of the proposal
states the merged design on its own terms.

1. **What a `drives` verdict does.** n011 parks the seed (still selecting,
   out of autonomous adoption, listed for a person); n012 turns it into a
   rejection with `revocable: true`, revoked by a later scored miss, with
   `max_revoked_rejections` and a revocation step in `score`. *Resolution
   (assumption update, in n011's favour):* a test that only drives a source
   is still coupled to it — a breaking change to the driven script breaks
   the test's setup — so the pair must keep selecting; the verdict decides
   only whether the pair may claim. Parking is therefore the semantically
   correct outcome, keeps the invariant both parents rely on ("the loop can
   only fail toward running more"), and needs no revocation machinery. Kept
   from n012: `unsure` as a verdict (two, from different runs, →
   `REVIEW_HUMAN`), `REJECTION_CONTRADICTED:` for a human rejection a scored
   miss contradicts (advisory), and the `min_full_runs_since_map_change`
   readiness criterion. Dropped: revocation, `max_revoked_rejections`,
   `rejections_revocable`. `assumption_agent_rejection_is_revocable` is
   rewritten to record that no agent rejection exists to revoke; design
   decision 14 states the rule. Open question 13 keeps the door.

2. **Packet transport and verdict grammar.** n011 writes batch files on
   disk with ±40-line excerpts and reads answer files through `review
   --answer`; n012 prints bounded, digest-stamped line-protocol packets and
   reads verdicts on stdin through `adopt --agent-verdicts`. *Resolution
   (bridge):* n012's packet (assertion lines flagged, declared symbols only,
   `packet_lines` ceiling, `packet_sha`) and n012's single stdin intake, with
   n011's assertion-line anchor added to the `verifies` grammar and validated
   the same way (`VERDICT_INVALID:<id>|<reason>`, including
   `assert_line_names_other`), n011's `reviews[]` memo (a pair is read once
   per test blob per reader), n011's grouping by test file, and n011's
   file form as `--out <dir>` for the crew. The line names are unified:
   `VERDICT:` / `VERDICT_INVALID:` / `VERDICT_STALE:` / `REVIEW_BATCH:` /
   `REVIEW_MEMO:` / `REVIEW_APPLIED:`; the verdict vocabulary is `verifies |
   drives | unsure`.

3. **Autonomous floor vocabulary and how a verdict adopts.** n011 says
   "measured or reader"; n012 partitions the origin table into rule /
   measurement / reading / heuristic with a `class:` per row and a floor
   stated in those terms, and adopts a `verifies` verdict at intake. n011
   adopts verdicts in a second `adopt --class --auto` pass. *Resolution:*
   n012's four classes and floor rule (every member carries a rule,
   measurement or reading and clears `accept_min`); n012's adopt-at-intake
   for verdicts; n011's explicit `--auto` flag kept as the engine-enforced
   autonomous form for rule and measurement classes
   (`ADOPT_REFUSED:not-autonomous`).

4. **`by:` vocabulary.** n011 records *how* (`human | auto:measured |
   auto:review | author`); n012 records *who* (`human:<email> |
   agent:<agent-string>`) plus run, rationale and packet digest.
   *Resolution:* `by:` records who — `human:<email> | agent:<agent-string> |
   auto` (the engine adopting a rule or measurement class with no reader) —
   because how is already `origin[]`; every display splits `human / agent /
   auto`.

5. **Calibration of `agent:review`.** n011 accumulates `REVIEW_AGREEMENT`
   passively from human per-row decisions and demotes to a fixed 0.60 under
   `min_agreement`; n012 adds an explicit `--calibrate` against coverage
   facts (a measurement, available headless) and writes the measured ratio
   as `measured_confidence`, disabling headless adoption below `accept_min`.
   *Resolution (both):* passive agreement and explicit calibration feed one
   number, `agent_review.measured_confidence`; one threshold, `accept_min`
   (0.85), is both the class threshold and the calibration floor; the 0.90
   prior stays a project knob; `calibration_min` (30) gates when either
   measurement is acted on.

6. **The `auto` policy — default, state and names.** n011 writes `auto`
   unconditionally and keeps its state in `config.yaml`, committed by the
   bash front under `ait: testmap policy … (t<id>)`; n012 writes `auto` only
   under a headless profile and keeps the engine's approval in
   `costs/policy.yaml` so `config.yaml` stays human-authored, and names the
   cadence `full_run_every {tasks, selection_ratio_above, days}`.
   *Resolution (bridge):* `auto` is the written value in both profiles, with
   the attended config table showing and confirming it beside its cadence
   (open question 12 records the counter-argument); n012's file and names,
   n011's explicit commit path (the engine prints `POLICY_WRITE:<path>`, the
   front commits it with the path named); n012's `POLICY:auto|…` line shapes
   plus n011's `POLICY_FLIPPED`, `cadence_declared`, window scoring with
   per-task attribution, and "a cadence full run ignores
   `on_empty_selection`".

7. **Author annotation — refusal rule and its switch.** n011 requires both
   files on the change surface, flags `AUTHOR_UNCORROBORATED`, and adds a
   profile key `unmapped_source_autonomous: author|propose`; n012 also
   accepts a test outside the surface whose closure reaches the source,
   adds `--by <agent-string>`, and adds no profile key because provenance
   must not depend on who ran the task. *Resolution:* n011's stricter rule
   (the claim stays inside the diff Step 8 reviews; open question 17 keeps
   the alternative) and its flag, n012's `--by`, one refusal name
   (`AUTHOR_REFUSED:<pair>|outside-change-surface`), and the switch moved
   from the profile to project config as `agent_review.author: true|false`
   per n012's principle.

8. **Kinds in a headless run.** n011 prints `CLASSIFY_PENDING` and writes
   nothing; n012 records `kind_proposals[]` and prints `KIND_PROPOSALS:<n>`.
   *Resolution:* n012 — a durable proposal a later attended session finds.

9. **Who reads, and every launch surface.** n011's reader is the session
   agent, with a crew form (`onboard review --crew` over
   `aitask_crew_addwork.sh`, `--collect`) as the parallel option; n012 adds
   the bulk skill `aitask-testmap-review` with `ait skillrun testmap-review`
   and `ait codeagent testmap-review [--headless]`, the
   `verified.testmap-review` model-table key and the interactive-by-default
   test. *Resolution (both):* the session agent reads at the in-gate and
   authoring sites; the bulk skill is n012's, launched through n012's two
   wrappers; n011's crew form is kept as the parallel option and made
   explicit about its wrapper — the crew runner launches every crew agent
   through `ait codeagent --agent-string … invoke raw`, in print mode only
   when the crew's launch mode is `headless`. The rule the merge enforces is
   stated once (design decision 15) and pinned by a test: the engine never
   launches an agent; every launch is `ait skillrun`, `ait codeagent` or
   `ait crew runner`; print mode is an explicit flag on each.

10. **The in-gate seeds step.** n011 shows seeds with their earlier verdict
    rationales and adopts `verifies` rows autonomously; n012 has the gate's
    agent read packets in-gate, with attended pre-fill / confirm /
    trust-batch. *Resolution:* n012 — the file is open and the diff is in
    front of the reader; a person's per-row confirmation stays a reviewed
    stamp (no provenance row), "trust this batch" is `by: agent`.

11. **Skills, `finish` and `reject`.** Three skills (n011) versus four
    (n012): four, with the onboarding skill's `review.md` invoking the same
    `review-batch.md` flow so the verifies-or-drives rule lives in one file.
    `finish --auto`: n011 accepts parked rows; n012 requires `REVOKED:0` and
    `REVIEW_HUMAN:0`. n011's — parked and `REVIEW_HUMAN` rows still select,
    and a strict-gate hit on a source only they cover is what the author
    branch resolves per task — with both counts printed
    (`FINISH:auto|parked <n>|review_human <m>`). `reject` refusing under
    `AIT_PROFILE_HEADLESS=1` (n011) is kept: no autonomous path removes a
    seed.

12. **Config knobs unified.** n011's `agent_review {confidence, batch 25,
    min_agreement, calibration_min}` and `completion.auto {full_every_n,
    full_when_selection_over, full_after_days}`; n012's `agent_review
    {enabled, accept_min, batch 20, packet_lines, max_pairs_per_run,
    rejections_revocable, measured_confidence}`, `completion.full_run_every`
    and a `readiness:` block. *Resolution:* `agent_review {enabled,
    confidence 0.90, accept_min 0.85, calibration_min 30, batch 20,
    packet_lines 120, max_pairs_per_run 400, author true,
    measured_confidence}`, `completion.full_run_every {tasks 5,
    selection_ratio_above 0.60, days 7}`, `readiness {min_scored_full_runs,
    max_false_negatives, require_opaque_proofs,
    min_full_runs_since_map_change 3}`; `min_agreement` folded into
    `accept_min`; `rejections_revocable` and `max_revoked_rejections`
    dropped with resolution 1.

13. **Dimension pairs that name the same topic.** Both parents' keys are
    kept and scoped so they do not repeat: `component_agent_review` (the
    engine verbs: packet writer, memo, validator, calibration, crew form)
    beside `component_agent_review_pass` (the pass end to end: sites, skill,
    launch surfaces, verdict semantics); `assumption_agent_can_judge_verifies`
    (the capability, the anchor, passive agreement) beside
    `assumption_agent_reads_verify_vs_drive` (the packet as sufficient
    input, explicit calibration, the `unsure` escape);
    `assumption_session_agent_is_reviewer` (the default reader, in-session)
    beside `assumption_headless_launch_is_explicit_opt_in` (every launch
    wrapped, headless a flag); `assumption_cadence_full_run_bounds_miss` (the
    miss's scoring and attribution) beside `assumption_cadence_bounds_exposure`
    (the window's bounds and reset); `tradeoff_review_token_cost` (how many
    tokens) beside `tradeoff_agent_review_token_cost` (where they are paid);
    `tradeoff_cadence_window_misses` (the miss mechanics) beside
    `tradeoff_auto_policy_exposure_window` (the window's size and
    dependents); `tradeoff_agent_judgement_unmeasured` (the provisional
    number) beside `tradeoff_wrong_positive_invisible_to_score` (what the
    loop cannot see); `requirements_agent_driven_adoption` (who may adopt
    what) beside `requirements_autonomous_loop_closure` (how the loop
    closes). `component_auto_policy` and `component_author_annotation` exist
    only in n011 and are carried with the merged mechanics.

14. **Reference files.** The union of both parents' lists (219 entries),
    deduplicated; the crew scripts and agentcrew docs (n011) and the
    `codeagent` / `skillrun` / `agent_string` / `launch_modes` / model-seed
    files (n012) are all retained because the merged launch-surface rule
    reaches each of them; `.aitask-scripts/agentcrew/agentcrew_runner.py`
    and `tests/test_codeagent.sh` are added for the crew-runner launch path
    and the interactive-by-default pin. No component was dropped whole, so
    no reference was removed.
<!-- /section: conflict_resolutions -->
--- PROPOSAL_END ---
