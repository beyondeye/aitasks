# Output from agent: explorer_005b

--- NODE_YAML_START ---
# node: n012_explorer_005b — child of n010_explorer_004 (agent-closed adoption loop)
# Each dimension is tagged: [inherited] unchanged from n010; [modified] rewritten here; [new] added here.
node_id: n012_explorer_005b
parents:
- n010_explorer_004
description: 'Agent-closed adoption loop over the n010 architecture (engine, registry, ledger, run surface
  and workflow seam unchanged): the origin table gains two READING origins - agent:review (0.90, a verdict
  from an agent that read a bounded, digest-stamped packet of the test''s assertion lines and the source''s
  symbols) and agent:author (0.90, the implementing agent naming a pair for a test it wrote, through `annotate
  --author`) - and the autonomous adoption floor is rewritten from ''confidence 1.0 only'' to ''rule,
  measurement or reading'' (static:package, coverage, agent:*), so a headless profile completes level
  1 on every target repo; every adopted and rejected row records by: human|agent:<agent-string>, run,
  rationale and packet_sha; agent rejections are evidence-revocable (a scored miss re-seeds the pair and
  counts toward readiness), agent acceptances are tolerated as the over-selecting direction seeds already
  occupy; completion.mode gains `auto` - the engine flips to the selection when readiness is ADMISSIBLE,
  records approved_by engine:readiness@<run> with mode: auto in costs/policy.yaml, demotes loudly as before,
  and a per-project cadence full_run_every {tasks, selection_ratio_above, days} keeps full runs and scoring
  alive with no person; the reading happens at three sites that share one verdict intake (`onboard adopt
  --agent-verdicts -`): the testmap_fresh in-gate step, the pre-review Affected Tests procedure''s autonomous
  branch, and a new bulk skill aitask-testmap-review launched interactively (`ait skillrun`) or, only
  under an explicit --headless flag, via `ait codeagent testmap-review` (the engine never calls a model,
  no default path uses `claude -p`); kind changes and axes stay human, headless profiles propose kinds
  and apply none; calibration (`onboard review --calibrate`) against coverage facts or human-reviewed
  rows lowers agent:review''s weight where it disagrees; design decisions 2 and 10 rewritten, 14-16 added.'
proposal_file: br_proposals/n012_explorer_005b.md
created_at: 2026-09-20 09:14
created_by_group: explore_005
# reference_files: baseline list plus the headless-launch, agent-string, model-config,
# gate-ledger and coverage references the agent review pass and the auto policy rely on
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
- .aitask-scripts/aitask_skillrun.sh
- .aitask-scripts/lib/agent_string.sh
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
- aidocs/gates/aitask-gate-framework.md

# ===== REQUIREMENTS =====
# [inherited]
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
# [inherited]
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
# [modified]
requirements_agent_skill: 'Agent skills teach agents how to keep the map current as they write code and
  tests (annotate a file, a testmap:unit member or a testmap:axis coordinate, declare an axis source,
  put testmap:reads on a tree-scanning helper, axes --explain, attribute before the gate, verify after
  editing, classify --suggest, confirm or retarget stamps in the procedure gate, drive a render loop from
  select --format tokens, and NAME the pair for a test they wrote through `annotate --author`) AND how
  a repository''s EXISTING tests get onto the map without a person: aitask-testmap-onboard is the resumable,
  profile-aware migration in graded levels, and its level-1 adoption is by rule (static:package), measurement
  (coverage) and reading - the new aitask-testmap-review skill reads engine-cut packets (`onboard review
  --next 20`) and returns VERDICT lines that `onboard adopt --agent-verdicts - --by <agent-string> --run
  <id>` turns into stamped edges with by: agent provenance, rejections with revocable: true, or unsure
  marks; the same intake serves the testmap_fresh in-gate step and the pre-review procedure; the generic
  `## Running Tests` section plus `ait test --howto` remain how an agent learns the run surface once.'
# [modified]
requirements_annotation_freshness: 'Every STAMPED unit coverage annotation carries the date and blob digest
  of the covered source at confirmation, scoped to the member block where the unit is a member, with committed
  last_pass anchors per variant letting stale prove EVIDENCED so most hot-source churn needs no rewrite;
  a SEEDED edge carries no stamp and makes no freshness claim; `onboard adopt` (by class, by row, or from
  agent verdicts) and `annotate --author` are the acts that turn a seed or an author claim into a stamped
  testmap:covers line through the rewriter, with an adopted.yaml provenance row recording origin[], confidence
  and by: human:<email>|agent:<agent-string> (plus run, rationale, packet_sha for a reading) that stale
  and explain display until a human re-stamps the edge - so a stamp always records who accepted the claim,
  whether that was a person or an agent, at what level of review, and against which bytes; the procedure
  gate at the post-implementation step hands the report to an agent that fixes annotations and, reading
  the packets for the touched files'' seeds, adopts or rejects them before the task commit (attended:
  a person confirms the agent''s pre-filled verdicts; autonomous: the verdicts are the adoption).'
# [inherited]
requirements_annotation_staleness: A stale verb reports, for a task's change set or repo-wide, STALE_PATH
  (deleted or renamed source, fail-closed), STALE (content changed, no evidence on every reached variant,
  the unevidenced variants named), EVIDENCED, UNSTAMPED, STALE_AREA and opt-in REVIEW_DUE rows in the
  framework's fixed line protocol, plus one CHECK_STRUCTURAL:<n> summary line on --all; seeded edges are
  excluded from every stale class (they claim nothing), stale --all adds SEEDED:<n> and ADOPTED:<n> summary
  lines so a repo-wide sweep sees how much of the map is provisional or machine-accepted, and a row on
  an adopted edge carries adopted(...) in its DISPLAY line; structural rot on axes, members, variants
  and artifacts stays check's; digest comparison needs no git history, evidence only removes nags.
# [inherited]
requirements_axis_product_selection: 'A project whose tests form a product of named facets (thinking_app:
  49 screens x 10 matrices where a matrix is locale x direction x geometry; aitasks: skill x profile x
  agent goldens) declares the axis with its facets, values and facet-valued source globs, and lets the
  engine select exact variants - an axis-source hit selects the variants carrying the facet value, any
  other hit selects every variant, hits union - instead of choosing between thousands of hand edges and
  one all-or-nothing suite scope; a source matching no axis source reaches units only through edges and
  dependencies, which select every variant, the fail-safe direction; intersection reduces to the facet
  join on every single-file case.'
# [inherited]
requirements_broad_test_handling: 'Scoped rows are ranked after unit tests at equal distance, selected
  under an explicit suite budget that prints every DEFERRED cut, scheduled only after the unit wave is
  green (broad_after_unit), widened by attribute on a full-run miss, and drift-flagged by evidence (STALE_AREA)
  rather than by calendar; a suite row marked full: true with a children: post-processor anchors registered
  ids on every run.'
# [inherited]
requirements_cost_tracking: Tracks cost per test unit and per variant, keyed by host class, using Welford's
  online update (n, mean, standard deviation, p95, last), plus a last_pass {sha, at, run_id} anchor and
  a flake rate per id; per-invocation overhead rows are a first-class input keyed by invocation group,
  so a selection's estimate is the sum over groups of overhead.p95 + the marginal p95 of each selected
  id - a second method in a booted Robolectric class costs its per-unit mean, not another boot.
# [inherited]
requirements_dev_rebuild_from_source: A framework developer rebuilds the engine with one command (ait
  engine build) through the same engine/build.sh that CI uses, into $AITASKS_HOME/engine/dev/ which the
  shim selects via AIT_ENGINE=dev (version must read <V>-dev+<sha>); ait engine cross produces the CI
  matrix locally, byte-identical.
# [inherited]
requirements_engine_dev_regeneration: The GOOS/GOARCH matrix, CGO_ENABLED=0 and ldflags live in one script
  (engine/build.sh) shared by release CI, ait engine build and ait engine cross; ait engine test runs
  go vet and go test; ait engine prune removes versions under $AITASKS_HOME/engine/ that no registered
  project is on; ait engine home reports the root, legacy tenants and symlink state and performs the migration
  on --migrate.
# [inherited]
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
# [modified]
requirements_feedback_loop: 'Learns from failures the map did not predict via a score/attribute feedback
  loop: every task-scoped selection writes the task''s prediction record and the newest one wins; every
  full run (run --all, `ait test --gate` under a full policy or a cadence-triggered full run under auto,
  or a full: true suite runner) automatically scores that record for the same task and prints PREDICTION_FALSE_NEGATIVES:<n>
  plus one PREDICTION_MISSED:<id> line per miss, appending to a committed costs/predictions.yaml that
  readiness counts; the pre-review advisory run is the selection guaranteed to exist in every profile;
  attribute records observed edges, axis sources (widen only) and triggers; an undecided attribute proposal
  lands in registry/seeded.yaml with origin observed; AND score revokes agent rejections - for each missed
  test and each changed source in the run''s surface, a rejections[] row for the pair with by: agent:*
  is removed, the pair re-seeded with origins [observed] plus its originals and evidence.revoked_from:
  <run>, and AGENT_REJECTION_REVOKED:<test>|<source>|<run> printed, while a by: human row prints REJECTION_CONTRADICTED:
  and stays; the predictions row records revoked: [...]; readiness counts revocations (max_revoked_rejections)
  and clean full runs since the last map change (min_full_runs_since_map_change); `onboard status` reports
  the queue per origin, adopted split by agent/human, REVOKED, UNSURE and REVIEW_HUMAN so adoption is
  measurable.'
# [inherited]
requirements_framework_home_name: 'The framework is named aitasks, so every path it owns under the user''s
  home should be ~/.aitasks - the engine installs there now, and the legacy ~/.aitask tree is migrated
  by an explicit verb, ait engine home --migrate (flock, per-entry rename, rmdir, compatibility symlink;
  known set including pypy_venv), with ait setup printing a HOME_LEGACY: hint in this release and a named
  follow-up flipping the default once the verb has passed a real install.sh --dir test.'
# [modified]
requirements_gate_enforcement: 'Enforced by gates so the map cannot rot silently: testmap_fresh (procedure,
  before the task commit; reads packets for the seeds on the test files this task touched and adopts or
  rejects them - attended with a person confirming the agent''s verdicts, autonomous on the agent''s verdicts
  alone), testmap_check (machine; fails STALE_PATH on its own; reports SEEDED:<n>, ADOPTED:<n>|agent <a>|human
  <h> and UNMAPPED_SOURCE:<path> rows; fails the structural rows plus UNMAPPED_SOURCE only under --strict
  past bootstrap_until; unlocks: [tests_pass]) and ONE completion test gate - the existing tests_pass,
  whose test_command is `./ait test`, which runs the whole registry or the task''s selection according
  to the committed completion policy in aitestmap/config.yaml: full by default for attended onboarding;
  selected only after `ait testmap readiness` reports ADMISSIBLE and a human records approved_by; or auto,
  written by detect --write under a headless profile, under which the engine itself flips to the selection
  when readiness is ADMISSIBLE (recording approved_by {who: engine:readiness@<run-id>, mode: auto} in
  costs/policy.yaml), runs full whenever a cadence trigger fires (full_run_every.tasks | selection_ratio_above
  | days, printed as POLICY:auto|full|cadence:<trigger>), and demotes back to full at run time if readiness
  regresses. There is no separate selection gate: its verifier logic is `ait test --gate`, blocks_dependents
  and max_retries: 1 are tests_pass''s own, and the timeout is a per-project tests_pass.timeout_seconds
  written from the measured full-run p95. A command key opted into gate_command_exit_contract also reads
  exit 75 and exit 3 as verifier error. Gates are enabled by the onboarding skill''s enable phase, never
  by hand and never by ait setup; a project whose completion invariant is a full suite keeps tests_pass
  exactly as today.'
# [inherited]
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
# [inherited]
requirements_go_engine: Scan, check, select and stale finish in well under a second on a ~720-test repo
  - and select stays under 250 ms warm on thinking_app's 297 golden variants over 49 members plus 374
  JVM classes with axis expansion, never executing a runner - and the scheduler runs concurrently with
  real cross-process locks, so selection overhead stays negligible against the shortest test and check
  can run at every commit step.
# [inherited]
requirements_go_engine_and_cli: The engine and CLI are one static Go binary (ait-testmap) built from engine/;
  bash keeps only the dispatcher arms, the shim that resolves the binary under $AITASKS_HOME and pipes
  the change surface in, the `ait test` front, the gate verifier shells, lib/aitasks_home.sh, the ait
  engine developer verbs (incl. home [--migrate]) and any project-local runner or scanner scripts; the
  binary never invokes aitask_*.sh and never needs its own install root.
# [inherited]
requirements_high_level_tests_separate: Integration, e2e and device tests declare areas, scope globs or
  budget-exempt trigger globs instead of covers, live in registry/_scoped.yaml beside the unit table,
  join the ranked list at distance 1 as sinks, and never enter the per-file edge graph or its digest staleness;
  a helper file may declare testmap:reads <glob> so every unit whose test-file closure contains it inherits
  the glob as a trigger; variant-bearing units are unit kind and never scoped rows.
# [modified]
requirements_incremental_adoption: 'Adoption is incremental and measurable, never big-bang, and never
  waits on a person where a rule, a measurement or a reading exists: a seeded edge selects from the moment
  `onboard seed --apply` runs (fail-safe direction) but claims no freshness; adoption - the act that writes
  testmap: lines and stamps - happens per evidence class with provenance (adopted.yaml, by: human or agent),
  per area in batches, from agent verdicts over engine-cut packets (bulk through aitask-testmap-review,
  bounded by max_pairs_per_run and resumable through onboard.yaml phases.review), inside the testmap_fresh
  gate for the test files a task already touched, or at authoring time through `annotate --author`; readiness
  prints LEVEL and NEXT from what exists and `onboard status` prints ONBOARD_NEXT and the ratios (tests
  with an edge, sources with an edge, seeds pending per origin, adopted by agent and by human, unsure,
  REVIEW_HUMAN, revoked, oldest pending age) so a half-migrated repo is a known state with a next step,
  and check reports SEEDED:<n> and ADOPTED:<n> until both queues are empty.'
# [modified]
requirements_onboarding_existing_tests: 'A skill onboards a project''s existing tests into the architecture
  without the user writing a registry by hand, in four graded levels each landing as one reviewed aitask:
  level 0 detects test frameworks and writes runners.yaml bindings, config.yaml, resources.yaml and areas.yaml,
  seeds the edge queue, proposes waivers and enables the gates (the universe exists, `ait test --all`
  runs it and is the task''s own first full run, selection works through seeds and the test-file static
  closure, nothing is stamped); level 1 adopts covers edges from the seed queue in the order rule (static:package
  1.0) -> measurement (coverage 0.95) -> reading (agent verdicts over packets, agent:review 0.90 noisy-OR''d
  with the static origins beneath), with naming conventions, plans, prose and (t<id>) co-change as corroboration,
  helpers split from subjects by root and fan-in - written as stamped annotation blocks through the engine''s
  rewriter with provenance in registry/adopted.yaml carrying by: for class and agent adoptions and none
  for per-row human ones; level 2 classifies broad tests as scoped rows over codemap areas, adds testmap:reads
  to tree-scanning helpers, testmap:batch no from serial lists, and declares detected locks as resources;
  level 3 declares axes, scaffolds a project runner script and member blocks where the grid heuristic
  finds a product space. Rewriting a test means inserting comment lines only; the skill proposes and never
  performs code restructuring; headless profiles complete levels 0 and 1 in full (rule, measurement, reading
  to budget), propose kinds at level 2 without applying them, and never enter level 3.'
# [inherited]
requirements_platform_binaries_in_release: Release CI builds and attaches checksummed binaries for linux/darwin
  x amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt) from one engine job that
  also runs go vet and go test; a new engine-check.yml runs the same on push/PR for engine/**; tarball
  and package-manager artifacts stay architecture-independent.
# [modified]
requirements_reason_per_selected_test: Translates a task's change set into one ranked list of tests that
  must run with a reason on every line (edge(annotation|declared|observed), dep, rule, axis(...)[keys]
  <- <source>, test-dep <helper>, reads(<helper>) <- <path>, ESCALATE:<file>|<reason>, the facet value
  or @* that placed each variant row, a stale mark when a selecting edge's digest no longer matches and
  no run evidence covers that variant, an invocation group and its cost, an explicit DEFERRED line for
  every broad row or group the budget cut) plus `edge(seeded:<origins>)` for a seeded edge - the origins
  list (static:invocation, static:import, static:package, convention, cochange, plan, prose, coverage,
  observed, agent:review, agent:author) printed so a reader knows what the row rests on - and `adopted(<origins>
  <confidence> by <human|agent:<agent-string>>)` beside an annotation edge that entered by class acceptance,
  agent verdict or author claim; `ait test` prints a SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>
  summary line and UNMAPPED_SOURCE:<path> lines ahead of the rows.
# [inherited]
requirements_screen_locale_subdivision: 'A test unit may be a member of a file (<path>#<member>, opened
  by a testmap:unit block) and may carry variants on a declared axis (<unit>@<variant>); a source change
  reaches a unit on every variant, or reaches an axis facet value (matrix.locale=ru) and thereby only
  the variants carrying it plus any plain unit carrying testmap:axis matrix.locale=ru; the runner lowers
  a variant id to what it executes (thinking_app: <Class>.<method> per matrix through matrix_classes /
  preview_resolve_token) so the engine never learns Gradle, Roborazzi or the membership manifests.'
# [inherited]
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
# [inherited]
requirements_user_root: Every per-user artifact this feature installs lives under the framework's own
  root, ~/.aitasks/ (env override AITASKS_HOME, one owner file lib/aitasks_home.sh, no fallback to ~/.aitask),
  beside the existing ~/.config/aitasks/ and ~/.cache/aitasks/ roots; the engine is the root's first tenant
  at $AITASKS_HOME/engine/v<VERSION>/ and $AITASKS_HOME/engine/dev/; the legacy ~/.aitask/ tenants (venv,
  pypy_venv, python, bin, uv, dev_tier, update_check) are neither moved nor read by this feature's default
  path.
# [modified]
requirements_workflow_seam: 'The change-aware run is reached from the existing workflows without a new
  workflow: task-workflow Step 7 gains one paragraph naming `./ait test` as the implementation test loop
  and one pre-review Affected Tests procedure (affected-tests.md) before Step 8, behind an affected_tests:
  run|show|off profile key (default run), that calls `./ait test --advisory --task <id>` speaking the
  VERDICT:/REASON:/DETAIL:/LOG: line shape and set -e capture form aitask_run_project_command.sh already
  established, guarantees the prediction record the completion run scores, and - in its autonomous no_selection
  branch - has the agent name its own test for each UNMAPPED_SOURCE through `ait testmap annotate --author
  <test> <source> --task <id> --by <agent-string>` (adopted with origin agent:author; AUTHOR_REFUSED:not-in-task
  when the test is neither in the change surface nor reaches the source) before falling back to attribute
  --propose; Step 8''s procedure-gate block dispatches testmap_fresh, whose seeds step reads packets and
  adopts on verdicts; Step 9''s gate orchestrator runs testmap_check -> tests_pass and the legacy build-verification
  path is untouched except for one error branch; aitask-qa''s test discovery reads the map (explain --sources)
  when aitestmap/ exists and its execution step runs `./ait test`; aitask-pickrem and aitask-pickweb inherit
  Step 7 through the shared task-workflow; ait setup prints TESTMAP:<state>; and every seam degrades to
  a printed skip where the engine or registry is absent.'
# [inherited]
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
# [inherited]
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
# [modified]
requirements_zero_config_onboarding: 'A repository with an existing test tree is brought onto the map
  by runs of /aitask-testmap-onboard and nothing typed by hand - attended or headless: the skill detects
  the test tools with evidence per row, generates aitestmap/ (config.yaml with completion, conventions,
  helper roots and - under a headless profile - completion.mode: auto, full_run_every, agent_review and
  readiness blocks; runners.yaml; resources.yaml; registry/areas.yaml), inventories every test unit, seeds
  edges from the origin table, proposes rules and waivers, enables tests_pass / testmap_check / testmap_fresh
  and the test_command swap, and runs the existing full gate once as the level-0 task''s own completion
  gate; level 1 adopts seeds by rule, by measurement and by reading (the agent reads engine-cut packets
  and returns verdicts; a person confirms them in attended profiles and nobody does in headless ones),
  classifies broad tests with confirmation (headless: proposes only), and scaffolds axes (attended only)
  - each phase idempotent and resumable from a committed ledger (aitestmap/onboard.yaml, whose review
  phase may be partial and re-entered), each level shaped as an aitask so its writes land under (t<id>)
  commits, are reviewed at Step 8 and attributed by the change surface; no policy flip is written by anyone
  under auto - the engine flips per run.'
# [new]
requirements_autonomous_loop_closure: 'The value of a per-change-set test selection is realised only when
  the loop closes without a person: seeding, adoption, the completion-policy flip and the safety net that
  keeps scoring alive are each performed by a machine or an agent under a committed, per-project policy
  - a rule (static:package) or a measurement (coverage) adopts by class, a reading (agent:review over
  engine-cut packets, agent:author at authoring time) adopts everything the heuristics only seeded, completion.mode:
  auto flips to the selection when readiness is ADMISSIBLE and records the engine''s approval with mode:
  auto, and full_run_every {tasks, selection_ratio_above, days} guarantees full runs so a miss is caught
  within a bounded number of tasks; every place a person remains is named and printed (KIND_PROPOSALS,
  REVIEW_HUMAN, axes, disabling the loop) rather than assumed done; the engine never launches a code agent
  and no default path uses headless print mode; a project that wants a human in the loop keeps completion.mode:
  selected or sets agent_review.enabled: false and gets the baseline exactly.'

# ===== ASSUMPTIONS =====
# [inherited]
assumption_annotation_is_comment_only: 'Integrating an existing test into the architecture never changes
  what the test does: onboard adopt inserts `testmap:` comment lines with the file''s own comment leader
  - bash after the header comment block (after the shebang and leading # block), Python as # lines after
  the module docstring (the grammar reads docstring lines but adoption never writes into one because that
  changes __doc__), Go after the package clause, Kotlin after the import block or inside the member''s
  testmap:unit block for a member seed - the runners execute the unchanged test, and `git diff -w --ignore-blank-lines`
  of an adopted file shows comments only; a test that cannot be annotated by comment (no comment leader
  the grammar knows) is skipped with ADOPT_SKIP:no-leader and stays seeded; existing `# Covers:` prose
  headers are shown beside the seeds as reviewer context and read by the prose origin, never rewritten.'
# [inherited]
assumption_areas_express_suite_blast_radius: The blast radius of a high-level test is expressible as a
  union of area glob sets plus scope globs plus budget-exempt trigger globs, plus the reads globs of helpers
  in its test-file closure; what that misses surfaces through score on a full run as an observed trigger
  or area member.
# [inherited]
assumption_axis_membership_declarable: 'For a product-shaped suite, which facet value a source belongs
  to is declarable as globs by the people who own the suite, because the project already routes by exactly
  that shape - res/values-ar/** and font/cairo_*.ttf are the Arabic matrices'' inputs and matrix_classes()
  already maps a matrix to its classes; aitasks'' .claude/ vs .opencode/ vs .agents/ trees are the agent
  facet. A source that matches no axis source is not an axis hit and reaches units only through edges
  and dependencies, which select every variant - the fail-safe direction. Falsifier: a project whose membership
  is genuinely dynamic (a runtime flag choosing a locale), for which the answer is to declare no sources
  on that facet. assumption_axis_sources_declarable is the thinking_app instance of this general claim.'
# [inherited]
assumption_axis_sources_declarable: 'The sources that reach one facet value of an axis are declarable
  as globs in axes.yaml: for thinking_app''s locale facet, values-<q>/**, raw-<q>/** and the per-family
  fonts (heebo_* for he, roboto_* for en and ru, cairo_* for ar); sources every locale reads (values/**,
  TypeScale.kt, Fonts.kt, AppRoot.kt) are ordinary edges, scanned dependencies or one hand rule over values/**
  and reach every variant; the geometry and direction facets have no axis sources because they are test-side
  constants in ScreenshotTestHarness.kt, reached through the test-dep closure.'
# [inherited]
assumption_batch_per_unit_timing_reportable: Runners can report per-unit timing inside a batch from their
  tool's own report format (JUnit XML, go test -json, pytest junitxml), can invert a report row to a registered
  id (JUnit classname+name back to ScreenFixtures.kt#Welcome@pixel5Ru_ltr through the same routing table
  the runner's list verb printed), and the same JUnit XML reports each @Test method with its own duration,
  which is what makes a variant's marginal cost measurable separately from its class's boot - the number
  the invocation-group budget depends on.
# [inherited]
assumption_blob_digest_is_staleness_key: The git blob digest of the covered source's content is the staleness
  key; file mtime (reset by checkout) and the annotation date (day granularity, clock skew) are never
  compared - the date is display only; the blob id doubles as the join key into any commit's tree for
  the evidence join.
# [inherited]
assumption_broad_tests_area_scoped: Integration, e2e and device tests can be described by named areas
  or globs whose membership changes rarely, so evidence-based drift (STALE_AREA) plus attribute widening
  is adequate; a calendar cadence (REVIEW_DUE, broad_review_days) is opt-in and off by default.
# [inherited]
assumption_cells_enumerable_by_plugin: 'The variant universe a repo has is enumerable from the project''s
  existing single routing statement rather than a second hand-maintained list - and the enumerator is
  the runner''s list verb, not a separate plugin directory: thinking_app''s runner lists 297 variant ids
  from matrix_classes() crossed with the two membership manifests, aitasks'' from its rendered tests/golden/
  tree; the framework never infers a variant. Falsifier: a repo whose test methods are only knowable by
  running the build, for which list may exec the build''s own list task at the cost of a slower scan/check,
  since select never calls it.'
# [inherited]
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
# [inherited]
assumption_cochange_is_corroboration: '(t<id>)-tagged commit history is a corroborating signal, never
  a primary one: in the last 400 commits touching tests/ or .aitask-scripts/ on aitasks there are 336
  task groups averaging 1.14 commits each, and a group pairs a few tests with a few scripts (t1159_1:
  4 tests x 4 scripts) with nothing inside the group to say which test covers which script, so co-change
  scores 0.20 + 0.20 x distinct task groups capped at 0.60, requires >= 2 distinct tasks (min_cochange),
  and cannot reach the 0.85 class-acceptance threshold alone or with convention (0.84 at the cap); repositories
  without the (t<id>) convention fall back to per-commit grouping with the same cap; one `git log --name-status
  -M --format=%H%x00%s` pass cached by HEAD sha, SEED_HISTORY:shallow|<n> on a shallow clone.'
# [inherited]
assumption_engine_latency_targets: 'On the aitasks repo (about 720 test units, 2,500-3,000 edges, about
  270 scanned sources) the engine meets select < 200 ms warm, scan < 300 ms, check < 300 ms, stale --task
  < 300 ms, stale --all < 2 s, cold select < 1.5 s; on a thinking_app-shaped fixture (297 golden variants
  over 49 member units, 374 JVM test classes, about 900 Kotlin files) select with axis expansion < 250
  ms warm, reading the committed variants: lists and never executing a runner; pinned by committed go
  test -bench fixtures with a 2x regression failing engine-check.yml, validated before the gates are enabled.'
# [inherited]
assumption_existing_locks_wrappable: Existing project locks and allocators (thinking_app's heavy-run lock
  with its exit-75 admission in tools/verification/heavy-run-lock.sh, emulator allocation in emulator-allot.sh)
  can be wrapped as resources without changing them; the Go admission and allocator kinds exec the project's
  commands and honour their exit codes, deferring on 75 until the run deadline; thinking_app's runner
  script goes through screenshot-tests.sh unit-tests, which reserves the slot itself.
# [inherited]
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
# [inherited]
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
# [inherited]
assumption_git_history_is_freshness_clock: Git history is the evidence clock, not the staleness key -
  commit reachability (merge-base --is-ancestor) decides which last_pass anchors may suppress a STALE
  row, never whether an edge is stale; mtime is never compared; a shallow clone whose anchors are outside
  fetched history reports STALE, not EVIDENCED, and remains fully functional; the cochange seed origin
  reads history as a seed source only, never as a freshness or evidence source.
# [inherited]
assumption_go_toolchain_available: 'A Go toolchain >= 1.26 is available in release CI through an actions/setup-go
  step this design adds to release.yml (go-version-file: engine/go.mod) and on framework developers''
  machines; target-project users never need Go.'
# [inherited]
assumption_go_toolchain_ci_and_dev_only: Go is a build-time dependency only - release.yml has no Go step
  today and the repo's only setup-go is hugo.yml's at website/go.mod's 1.25.7, so the engine job provisions
  its own toolchain; users receive prebuilt binaries and never compile.
# [inherited]
assumption_helper_degrades_when_absent: '`ait test --advisory` can always answer: engine missing (ENGINE_MISSING
  from the shim) -> VERDICT:skip REASON:testmap_absent; no aitestmap/ -> VERDICT:skip REASON:registry_absent;
  UNKNOWN: rows in the change surface -> VERDICT:skip REASON:unknown_paths naming them; empty selection
  -> VERDICT:skip REASON:no_selection with UNMAPPED_SOURCE lines; admission refused after the deadline
  -> VERDICT:skip REASON:admission_refused; only a run that executed maps to pass/fail, and only a front
  that cannot write its LOG: exits 3. This is what lets the pre-review Affected Tests procedure sit before
  Step 8 in every profile including remote (Claude Code Web has no engine) without a conditional per environment;
  the interactive and completion modes of the same script keep the rule that a missing engine is an error.'
# [inherited]
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
# [inherited]
assumption_home_symlink_compatibility: 'Every existing consumer of the legacy ~/.aitask tree keeps resolving
  unchanged when ~/.aitask becomes a symlink to ~/.aitasks, because all of them dereference a path rather
  than compare one - verified: the 35 references across 8 framework files (21 in aitask_setup.sh, 6 in
  python_resolve.sh, 3 in aitask_path.sh), the venv''s console-script shebangs (#!/home/<u>/.aitask/venv/bin/python3),
  the ~/.aitask/bin/python3 wrappers, the ~/.aitask/python/<ver>/bin/python3 symlinks whose targets are
  absolute paths outside the home, and pyvenv.cfg''s informational command = line; no ==, !=, -ef, realpath,
  os.path.realpath or samefile on the home path anywhere under .aitask-scripts/, ait or install.sh. This
  is the precondition of ait engine home --migrate, re-checked by tests/test_aitasks_home.sh''s post-migration
  venv and PyPy-venv exercise before the default is flipped.'
# [inherited]
assumption_instruction_block_is_read: 'Code agents load CLAUDE.md / AGENTS.md at session start and follow
  a managed block that names one command: the framework already relies on this for `./ait git`, notes
  and commit format, and ait setup regenerates the >>>aitasks block on every run, so a `## Running Tests`
  section reaches every agent in every onboarded project with no per-project authoring; the hand-maintained-CLAUDE.md
  case (sentinel present, no markers) is this repository and is edited by the level-0 onboarding task.
  Falsifier: an agent whose harness does not read the file - for which `ait test --howto` is the one-call
  fallback.'
# [inherited]
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
# [inherited]
assumption_kotlin_scanner_fail_closed: A closed construct list (explicit repo import, same-package as
  fully connected, repo star import as a package edge, fully-qualified in-body reference from the comment-stripped
  body) is enough to over-approximate the Kotlin import graph, and every construct that defeats such a
  graph - inline functions, const val, Hilt/DI bindings, Class.forName / ::class.java, generated or KSP
  sources, an unreadable or untokenizable file - is detectable by pattern and marks the file opaque, so
  a change to it escalates instead of being silently narrow; measured on thinking_app, 42 main files declare
  const val or inline fun and 63 carry DI annotations, so escalation is frequent by design; each opaque
  branch is reachable and red-proved by an engine fixture test.
# [inherited]
assumption_legacy_user_root_coexists: In this release ~/.aitasks/ (engine) and ~/.aitask/ (venv, pypy_venv,
  python, bin, uv, dev_tier, update_check; 8 framework code files with 35 references name it, plus 20
  test and 18 doc files) coexist on one host without either reading the other; the migration of the legacy
  tenants exists as ait engine home --migrate but is not run by ait setup by default, and nothing in this
  feature depends on it having happened; the default flip is a named follow-up.
# [inherited]
assumption_onboarding_is_a_task: 'Onboarding writes committed files (aitestmap/**, test-file comment lines,
  project config, profile and gates edits) across several sessions, so each level runs as an aitask: /aitask-testmap-onboard
  creates and claims `testmap onboarding level <n>` (issue_type chore, labels testing,testmap) through
  aitask_create.sh --batch and aitask_pick_own.sh, attaches the seed dump with ait attach, records the
  task id and level in onboard.yaml, continues into task-workflow, and every phase at Step 7 commits its
  files through aitask_task_commit.sh under `chore: Onboard testmap - <phase> (t<id>)` so the change surface
  attributes them and a resumed session re-enters at ONBOARD_NEXT; Step 8 reviews the diff, the level-0
  task''s Step-9 tests_pass is the first full run, and the next level''s task is created with depends:
  on this one because a level may wait weeks on full-run history. Falsifier: a repo that forbids tasks
  on the code branch - for which --no-task writes without committing and prints the commit lines to run.'
# [inherited]
assumption_one_engine_per_framework_version: One engine build per framework version suffices; a per-user
  versioned directory ($AITASKS_HOME/engine/v<VERSION>/) resolves per-project VERSION differences without
  a compatibility matrix, and exact-version resolution in the shim never falls back to newest-wins.
# [inherited]
assumption_passing_run_anchors_edges: A passing run of a test variant at commit C, on any host class,
  from an invocation without a cause and for an id under the flake threshold, is evidence that its annotated
  edges held for that variant against the source content present in C's tree - so an edge whose current
  blob equals the blob at C is EVIDENCED for that variant without touching the test file; a unit with
  variants is EVIDENCED only when every variant the change reaches has such a pass; a verify-active full
  run's child rows anchor all 297 goldens at once.
# [inherited]
assumption_platform_matrix_sufficient: linux/darwin x amd64/arm64 covers every target host (WSL reports
  Linux); any other platform builds from source via --engine-from-source.
# [inherited]
assumption_release_asset_reachable: A host running ait setup or ait upgrade can reach github.com/beyondeye/aitasks/releases
  over HTTPS, as it already must for the framework tarball; the shim itself never downloads, so a gate
  run never performs a network fetch.
# [inherited]
assumption_release_assets_reachable: Air-gapped or off-matrix hosts supply the binary via --local-engine,
  --engine-from-source, AIT_TESTMAP_BIN or a pre-seeded $AITASKS_HOME/engine/; --no-testmap / AIT_TESTMAP_FETCH=0
  skip the fetch and nothing else in setup depends on it.
# [modified]
assumption_seed_sources_measured: 'One origin table seeds edges, each origin measured on 2026-09-16 and
  none below 1.0 trusted alone as a HEURISTIC; every row carries a class - rule, measurement, reading
  or heuristic - that the autonomous floor reads. Rule: static:package (a _test.go''s own package: deterministic,
  1.0). Measurement: coverage (opt-in per-unit runtime coverage: coverage.py dynamic contexts, go -coverprofile
  per -run, LCOV with a test column, JaCoCo per-test sessions, 0.95). Reading: agent:review (an agent
  read the engine-cut packet - the static anchor line +-20, the test''s assertion lines flagged, the source''s
  declared symbols, the prose header - and answered verifies; evidence {by: agent:<agent-string>, run,
  rationale, packet_sha, test_blob, source_blob}; 0.90) and agent:author (the implementing agent named
  the pair for a test it wrote or a source it introduced in the task, through annotate --author; 0.90).
  Heuristic: static:invocation (398 of 400 aitasks bash tests, 0.90), static:import (320 of 320 aitasks
  Python, 139 of 339 thinking_app, 0.85), observed (0.70; also a revoked agent rejection), convention
  (0.60), plan (0.50), prose (0.30), cochange (0.20 + 0.20 per group capped at 0.60). Confidence combines
  by noisy-OR (static:invocation + agent:review = 0.99), orders the review queue and never hides a row.
  agent:review''s 0.90 is a prior: `onboard review --calibrate <n>` compares agent verdicts against coverage
  facts where a coverage import exists, else against human-reviewed rows and human rejections, prints
  CALIBRATION:agree|disagree|<ratio>, and a ratio under 0.90 writes agent_review.measured_confidence for
  this repository; under accept_min it disables headless adoption from the reading origins. Seeding is
  partial by construction: the remainder is rules, waivers, author claims and incremental adoption.'
# [modified]
assumption_seeds_select_never_evidence: 'A seeded edge is safe to act on in exactly one direction: it
  may cause a test to run (over-selection costs time) and may never suppress a STALE row, anchor evidence,
  satisfy require_stamp or count as coverage for UNMAPPED_SOURCE under --strict (under-claiming a freshness
  fact costs correctness). So seeds live in a generated file (registry/seeded.yaml), carry no stamp, are
  excluded from stale, are counted separately by check (SEEDED:<n>), and become claims only through an
  explicit adopt that writes the line and the stamp - by class (with an adopted.yaml provenance row),
  by row (a reviewed claim), from an agent verdict (an adopted.yaml row with by: agent) or from an author
  claim. Autonomous profiles may seed everything and may adopt a class only when every member carries
  at least one RULE, MEASUREMENT or READING origin (static:package, coverage, agent:review, agent:author)
  and its noisy-OR clears agent_review.accept_min (0.85); a heuristic-only class (static:invocation alone,
  static:import alone, convention, cochange, plan, prose, observed) is never adopted headless, however
  high its measured precision, because its fact is ''executes'' or ''co-occurs'', never ''verifies''.
  Falsifier: a project whose full suite is so expensive that seeded over-selection is itself the cost
  problem - for which the suite budget and --format tokens preview are the levers, not trusting seeds.'
# [inherited]
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
# [inherited]
assumption_static_granularity_v1: 'Static file-level facts remain the default for v1, with two narrower
  granularities in use rather than reserved: a member unit (<path>#<member>, annotations scoped by testmap:unit
  blocks, no language parsing) and the edge''s symbols slot, whose first consumer is the opt-in android-res
  scanner that names the string keys a values-<q>/ diff changed; no scanner produces symbol-level coverage
  of Kotlin or Python code; a change anywhere in a member file is a change to every member until hunk-level
  attribution exists.'
# [inherited]
assumption_target_repos_accept_aitestmap_root: Every target repo will accept a root aitestmap/ directory
  of YAML committed into its code tree, including onboard.yaml, registry/seeded.yaml, registry/adopted.yaml
  and an optional axes.yaml; runner scripts and axes are both optional (a repo with no product space declares
  none and gets the plain unit-map behaviour) because the reference runners are built into the engine;
  thinking_app commits one runner script (tools/verification/testmap_runner.sh) because its lowering is
  the harness's own routing.
# [inherited]
assumption_task_resolvable_from_session: '`ait test` can find the task an agent is implementing without
  being told: task-workflow names worktree branches aitask/<task_name> where <task_name> is the task file
  stem (t<id>_<slug>), so `git rev-parse --abbrev-ref HEAD` yields the id in worktree mode; in current-branch
  mode (fast profile, create_worktree: false) the task lock this user holds on this host is unique per
  Implementing task, so a `--list-mine` listing on aitask_lock.sh yields it; two or more yield AMBIGUOUS_TASK:<ids>
  and require --task; gate context supplies AIT_GATE_TASK_ID; the pre-review advisory form always passes
  --task explicitly because the procedure knows the id. Falsifier: an agent implementing outside the workflow
  (no lock, no branch) - for whom `ait test --dirty` is the explicit, printed, never-default intake.'
# [inherited]
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
# [inherited]
assumption_testmap_token_no_collision: The annotation token 'testmap:' does not collide with existing
  prose comments in any target repo; the 38 existing '# Covers:' headers in aitasks are behavioural prose
  and are not matched; thinking_app's KDoc mentions no 'testmap:' string.
# [inherited]
assumption_variant_universe_from_runner_list: 'A runner''s list verb enumerates the complete universe
  its run filter can address, so whole-run selection is sound: for thinking_app that is every <Screen>_<matrix>.png
  of the two membership manifests (50 + 247 = 297 goldens over 10 matrices) as variant ids plus every
  other class under app/src/test/java as a file unit; a class absent from list is a check failure (UNREGISTERED),
  never a silently unfiltered one; scan --apply persists each member''s listed variants so select reads
  the committed table and only scan and check exec list.'
# [new]
assumption_agent_reads_verify_vs_drive: 'An agent given the review packet - the static anchor line +-20
  lines, every assertion line in the test flagged, the source''s declared symbols (never its body), the
  prose header and, for a member seed, the testmap:unit block - distinguishes ''verifies'' from ''only
  drives'' at least as precisely as the baseline''s ten-sample human review of a class, because the judgement
  is local to the test body: does a flagged assertion check an output, a state or an exit status the named
  source produces, or does the source appear only in setup, teardown or as a path argument whose result
  is never checked? Measured before it is trusted: `onboard review --calibrate 50` against coverage facts
  where a coverage import exists (a measurement as ground truth), else against human-reviewed rows and
  human rejections; agreement >= 0.90 keeps the 0.90 prior, lower agreement writes agent_review.measured_confidence,
  agreement below accept_min disables headless adoption from the reading origins and readiness says so;
  a repo with neither ground truth runs on the prior and prints CALIBRATION:none. Falsifier: a repository
  whose tests assert through an opaque harness (a golden-diff script that never names what it checks)
  - the packet has no flagged lines, the agent answers unsure, and the pair lands in REVIEW_HUMAN rather
  than being guessed.'
# [new]
assumption_wrong_positive_claim_only_overselects: 'A wrong `verifies` verdict produces a stamped covers
  edge to a source the test only drives; its cost is a needless run of that test when the source changes
  and a STALE nag the evidence join heals when the test next passes; it never hides a coupling, never
  suppresses a STALE row on another edge, never anchors evidence for anything the test did not run, and
  never satisfies UNMAPPED_SOURCE for a source the test does not reach (the static closure had to contain
  the source for a packet to exist, or the author had to name it from inside the task''s change surface).
  Agent acceptance therefore errs in the direction seeds were already allowed to err in, and the only
  agent verdict that can under-select is a rejection. Falsifier: a project running --strict with on_empty_selection:
  full that relies on UNMAPPED_SOURCE to force full runs - a wrong positive there turns a forced full
  run into a selection; the cadence bounds it.'
# [new]
assumption_agent_rejection_is_revocable: 'A scored full-run miss (PREDICTION_MISSED:<test>) on a run whose
  change surface contains <source> is evidence that (test, source) is a real coupling; when that pair
  sits in onboard.yaml rejections[] with by: agent:*, the rejection was the wrong verdict and is revoked
  - the row removed, the pair re-seeded with origins [observed] plus its originals and evidence.revoked_from:
  <run>, AGENT_REJECTION_REVOKED:<test>|<source>|<run> printed, and max_revoked_rejections counted by
  readiness; a by: human rejection is contradicted in print (REJECTION_CONTRADICTED:) and kept, because
  evidence removes nags and never overrules a person; a rejections[] row with no by: (the baseline''s
  rows) reads as human. Falsifier: a miss caused by a coupling through a third file (the test reaches
  the source only through a helper) - the revoked pair is re-packeted once with its revoked_from line
  visible and a second `drives` verdict on it is REVIEW_HUMAN, never a second revocable rejection.'
# [new]
assumption_headless_launch_is_explicit_opt_in: 'No engine path, gate, hook or default skill flow launches
  a code agent in headless print mode: the in-gate and authoring sites read packets inside the session
  that already holds the task and the files; bulk review runs as `ait skillrun testmap-review` (an interactive
  launch like every skill run, `claude --model <id> "/aitask-testmap-review ..."`) or inside the onboarding
  task''s own session; `ait codeagent testmap-review` is interactive by default and appends --print only
  under --headless, the same explicit opt-in batch-review requires, because Claude Code bills print mode
  at a higher per-token rate and the framework''s shell conventions forbid `claude -p` without one; the
  engine validates a --by agent-string''s grammar and never resolves a model. Falsifier: a CI lane with
  no terminal - for which --headless is the documented, explicit, billed choice, never a default.'
# [new]
assumption_cadence_bounds_exposure: 'Under completion.mode: auto, a wrong agent verdict or an unmapped
  coupling that lets a task land without an affected test running is caught by the next cadence full run,
  which is at most full_run_every.tasks selected completion runs, full_run_every.days wall-clock, or the
  next selection whose estimate reaches selection_ratio_above of the full p95 away - whichever comes first;
  every full run scores the newest prediction, so the exposure window is a project-set number printed
  on every completion run as next_full_in:<n> and in --howto; the cadence state lives in costs/policy.yaml
  and is reset by every full run whatever triggered it. Falsifier: a project whose tasks land faster than
  its full run completes - for it tasks: 1 is `full` with extra steps and the project should stay on full.'

# ===== COMPONENTS =====
# [modified]
component_adoption_ledger: 'Adoption ledger: the three-file state of a machine-proposed edge and the rules
  that move it - registry/seeded.yaml (the queue: rows {test[#member], covers, origin[], confidence, evidence{},
  proposed_at}; select-only at d1 with reason edge(seeded:<origins>), no stamp, invisible to stale, never
  --strict, SEEDED:<n> on check / stale --all / readiness), registry/adopted.yaml (provenance: rows {test,
  source, origin[], confidence, adopted_at, task, by: human:<email>|agent:<agent-string>, run?, rationale?,
  packet_sha?, test_blob?, source_blob?} for a stamped edge accepted by evidence class, by agent verdict
  or by author claim; shown as adopted(<origins> <confidence> by <who>) on stale and explain rows; counted
  as ADOPTED_UNREVIEWED:<n>|<ratio> and AGENT_ADOPTED:<n>|<ratio> by readiness and ADOPTED:<n>|agent <a>|human
  <h> by check; a row is deleted when a human verify, stale --confirm-source, annotate or a per-row adopt
  re-stamps that edge) and onboard.yaml''s rejections[] (rows {test, source, reason|rationale, by, run?,
  revocable}; an absent by: reads as human / revocable: false; a by: agent row is removed and its pair
  re-seeded when a scored full-run miss contradicts it). Transitions: onboard seed / attribute --propose
  / revocation -> seeded; onboard adopt --class <origin> [--accept-min 0.85] [--scope <glob>] -> adopted
  (by: human); onboard adopt --agent-verdicts - --by agent:<s> --run <r> with VERDICT verifies -> adopted
  (by: agent), with drives -> rejected (revocable), with unsure -> unsure count, twice -> REVIEW_HUMAN;
  annotate --author -> adopted (agent:author, by: agent); onboard adopt <test> <source> | --area <a> --batch
  <n> and the testmap_fresh in-gate step confirmed by a person -> reviewed; human re-stamp -> reviewed;
  onboard reject -> rejected (by: human, not revocable). Load rules: SEED_SHADOWED, ADOPTED_ORPHAN, absent-by:-is-human.
  The autonomous floor: a headless profile may seed everything and may adopt a class only when every member
  carries a rule, a measurement or a reading origin and clears accept_min. Costs recorded under tradeoff_two_edge_states_during_adoption,
  tradeoff_seed_precision and tradeoff_wrong_positive_invisible_to_score.'
# [modified]
component_agent_brief: 'Agent brief (internal/brief): engine verb `brief [--md]`, surfaced as `ait test
  --howto [--md]` and `ait testmap brief`, prints TESTMAP:<state>|since|LEVEL:<n>|POLICY:<mode>[|next
  full in <n> tasks]|seeds pending <n>|adopted <n> (agent <a>, human <h>)[|revoked <n>], one RUNNER: line
  per runner, FULL_GATE:<runner>|<p95 est>|<cadence: every N tasks / >= R / D d>|<tests_pass timeout>,
  GATE: (the chain and what --gate would run now under the policy), VERBS:, AXES:, RESOURCE:, AGENT_REVIEW:enabled|<confidence>|<calibration
  ratio or none>, NEW_TEST:, DOCS:, NOTES: verbatim, ONBOARD_NEXT: while a ledger is unfinished, KIND_PROPOSALS:<n>
  and REVIEW_HUMAN:<n> when non-zero; before onboarding it prints TESTMAP_ABSENT plus the test_command;
  --md renders the same as markdown; < 100 ms warm.'
# [inherited]
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
# [modified]
component_annotation_scanner: 'Annotation scanner and rewriter (internal/annot): grammar v3 - testmap:unit
  <Member> opens a member block; testmap:kind, testmap:covers <path> @<date>/<blob10>, testmap:area, testmap:scope,
  testmap:trigger, testmap:reads <glob>, testmap:axis, testmap:reviewed, runner/needs/batch - per comment
  leader and Python module docstrings (read); refuses unknown keys with a line number; the line-targeted
  rewriter edits stamps by (file, line, current text) and refuses on REWRITE_CONFLICT; annotate --from-body
  seeds covers for a member from the kotlin scanner; two callers of the rewriter beyond the baseline''s:
  `onboard adopt --agent-verdicts` (same fixed per-language position as class adoption) and `annotate
  --author <test> <source> --task <id> --by <agent-string>`, which checks that the test is in the task''s
  change surface or reaches the source through the static closure (AUTHOR_REFUSED:<test>|not-in-task otherwise),
  inserts the stamped line, and writes the adopted.yaml row with origin [agent:author]; comment lines
  only (bash after the shebang and leading # block; Python as # lines after the module docstring, never
  inside it; Go after the package clause; Kotlin after the import block, or inside the member''s testmap:unit
  block); existing `# Covers:` prose headers are shown in packets as REVIEW_PROSE lines and read by the
  prose origin, never matched by the annotation scanner and never rewritten.'
# [inherited]
component_axes: 'Axis resolver verbs (internal/axes): ait testmap axes --list prints every declared axis
  with its facets, values and the variant count each value has in list; --check runs the axis rules (DEAD_AXIS_SOURCE,
  UNKNOWN_VARIANT, UNCOVERED_VALUE); --explain <path> prints AXIS:<axis>.<facet>|<value or ->|<why> per
  facet for one file - which glob matched, or that no source is declared - so a maintainer sees where
  a file lands before anything is trusted; resolve(changeSet) -> set | ANY is the SourcesHit join read
  the other way, with ANY printed as - and meaning no axis hit.'
# [inherited]
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
# [inherited]
component_broad_test_scopes: 'Broad-test scheduling and staleness policy: kind integration|e2e|device
  selects the scoped association form; broad_after_unit: true waves run scoped rows only after a green
  unit wave; device_policy: filter_by_resource default; scoped rows are exempt from per-edit digest staleness,
  with STALE_AREA as the evidence-based drift signal and REVIEW_DUE as an opt-in cadence; attribute widens
  areas by evidence; covers on a scoped row is allowed for digest-stamped fixture pins; a suite row (thinking_app''s
  verify-active) marked full: true with a children: post-processor anchors registered ids on every run;
  variant-bearing units are unit kind, never area-scoped, and ride the unit wave with admission-holding
  invocations ordered last; completion.deferred: run means the suite budget applies to the interactive
  loop only.'
# [inherited]
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
# [modified]
component_completion_policy: 'aitestmap/config.yaml `completion:` block: mode full|selected|auto (full
  by default under attended onboarding; selected is written only by the onboarding skill''s --policy re-entry
  after READINESS_DECISION:ADMISSIBLE beside run_gate_admission.approved_by in config.yaml; auto is written
  by detect --write under a headless profile and may be set by hand), full_run_every {tasks: 5, selection_ratio_above:
  0.60, days: 7} (the cadence; any trigger makes this completion run full), deferred run|fail (default
  run), on_empty_selection skip|full (default skip), engine_absent error|fallback_command (default error).
  Under auto, `ait test --gate` runs readiness on every completion run: NOT_YET -> POLICY:auto|full|not_yet:<criterion>
  and run --all; ADMISSIBLE for the first time -> approved_by {who: engine:readiness@<run-id>, at, mode:
  auto, statement: <the readiness lines>} written to aitestmap/costs/policy.yaml (the engine''s ledger,
  so config.yaml stays a human-authored declaration); then the cadence: selected_since_full >= tasks ->
  POLICY:auto|full|cadence:tasks; the selection''s per-group estimate / newest full p95 >= selection_ratio_above
  -> POLICY:auto|full|cadence:selection_ratio; now - last_full_run.at >= days -> POLICY:auto|full|cadence:days;
  otherwise POLICY:auto|selected|next_full_in:<n> and the task selection with deferred rows run. A full
  run resets selected_since_full and updates last_full_run. If mode is selected or auto and a criterion
  is unmet (a new false negative, a revoked rejection, a regressed opaque proof), POLICY_DEMOTED:<mode>->full|<criterion>
  prints and full runs - the demotion is automatic and loud, so the policy can only fail toward running
  more; readiness prints POLICY:<mode>|<what --gate would run now>|next full in <n>; the gate-run ledger
  block carries result="MODE:<full|selected>|<n units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>]".'
# [modified]
component_cost_ledger: 'Cost ledger (internal/cost): Welford per (id, host class), P2 p95 and last; the
  per-repo ledger .aitask-testmap/ledger.jsonl; costs --update folds into aitestmap/costs/<hostclass>.yaml;
  last_pass {sha, at, run_id} per id and a flake rate; the selection estimate as the per-group sum; costs/predictions.yaml
  holds the last 200 scored full runs (rows now carry revoked: [...]); run-id prefixes test- / gate- /
  full- as before plus review- for bulk review runs, which write no cost rows; `costs --gate-timeout tests_pass`
  unchanged; NEW aitestmap/costs/policy.yaml {last_full_run: {run_id, at, task, sha}, selected_since_full:
  <n>, approved_by: {who, at, mode, statement}} written by `ait test --gate` under auto - the cadence
  state and the engine''s approval record, committed beside the other engine-written ledgers so config.yaml
  stays human-authored; selection_ratio_above compares the selection''s per-group estimate to the newest
  full run''s p95 on this host class.'
# [modified]
component_dependency_scanners: 'Dependency scanners (internal/deps): built-in bash, python, go, kotlin
  with the opaque contract, Gradle module graph, executable plugins under aitestmap/scanners/, the opt-in
  android-res symbol scanner, forward deps cached per source blob under the XDG cache and inverted in
  memory; the bash scanner''s literal-invocation facts, the python and kotlin scanners'' direct imports
  and the go scanner''s package membership are exposed to internal/seed as the static origins; two more
  read-only facts are exposed to internal/onboard review from the same cache: the anchor line (file:line)
  of each static fact, and a source''s declared symbols (bash function names and top-level verbs, Python
  def/class, Go exported identifiers, Kotlin declarations) for the REVIEW_SOURCE lines - never a source
  body; the deeper closure stays the selector''s d2 walk and is never seeded.'
# [inherited]
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
# [inherited]
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
# [inherited]
component_evidence_join: 'Evidence join (internal/stale + internal/gitx, reads internal/cost): for every
  edge whose stamped_blob differs from the current blob, collects last_pass shas per reached variant from
  the local ledger and committed costs (any host class), drops candidates from invocations with a cause
  or ids over the flake threshold, keeps shas that are ancestors of HEAD, and runs one git ls-tree per
  distinct sha; an edge is EVIDENCED when every reached variant has a sha whose source object id equals
  the current blob, otherwise STALE with the unevidenced variants listed; never rewrites - stale --confirm-evidenced
  is the explicit re-stamp and the only bulk confirmation an autonomous profile may run; seeded edges
  are not joined (no stamp to heal), adopted edges are joined like any stamped edge, and the level-0 task''s
  first full run is what first populates the anchors it reads.'
# [modified]
component_feedback_tools: 'Feedback tools (internal/feedback): score (automatic after run --all, after
  a cadence-triggered full completion run and after a full: true suite run, printing PREDICTION_SCORED
  / PREDICTION_FALSE_NEGATIVES:<n> / PREDICTION_MISSED:<id> and appending to costs/predictions.yaml) gains
  the revocation step: for each missed test and each changed source in the run''s surface, a rejections[]
  row for the pair with by: agent:* is removed, the pair re-seeded with origins [observed] plus its originals
  and evidence.revoked_from: <run>, AGENT_REJECTION_REVOKED:<test>|<source>|<run> printed; a by: human
  row prints REJECTION_CONTRADICTED:<test>|<source>|<run> and stays; the predictions row records revoked:
  [...]. attribute (missing-edge / test-wrong / source-wrong, missing-axis-source widen-only, missing-trigger
  / area-too-narrow) and its propose decision are unchanged. readiness prints LEVEL:<0-3>, NEXT:, ADOPTED_UNREVIEWED:<n>|<ratio>,
  AGENT_ADOPTED:<n>|<ratio>, SEEDED:<n>, REVOKED:<n>, REVIEW_HUMAN:<n>, KIND_PROPOSALS:<n>, CALIBRATION:<ratio>|none
  and POLICY:<mode>|<what --gate would run now>|next full in <n>; gains two criteria read from config.yaml
  readiness: - min_full_runs_since_map_change (default 3; clean scored full runs since the last bulk adoption,
  revocation or --author write) and max_revoked_rejections (default 0 over the predictions window); under
  auto the approved_by criterion is satisfied by costs/policy.yaml''s engine record; it still enables
  nothing and never launches an agent.'
# [inherited]
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
# [modified]
component_freshness: 'Freshness: per-edge @<date>/<blob10> stamp written only by verify, annotate (including
  --author), stale --confirm* and `onboard adopt` (by class, by row, or from agent verdicts), scoped to
  the member block; variants carry no stamp; last_pass per id; bootstrap_until, require_stamp, flake_threshold;
  the testmap_fresh procedure gate dispatched by the existing procedure-gate block before the change summary
  so rewrites ride the (t<id>) commit; not a git hook, not a code-agent hook; its seeds step reads engine-cut
  packets for the test files this task touched and adopts or rejects them - attended, the agent pre-fills
  verifies/drives/unsure per row and a person confirms, overrides or trusts the batch; autonomous, the
  agent''s verdicts are the adoption through `onboard adopt --agent-verdicts -` - which is the moment
  the reader has the file open and the claim is cheapest to check; an adopted stamp is a stamp like any
  other and the procedure gate handles it identically, with the adopted(... by <who>) display as context.'
# [modified]
component_gates: 'Gates: testmap_fresh (kind: procedure, verifier aitask-gate-testmap-fresh, no unlocks;
  its seeds step reads packets and adopts or rejects on verdicts) and testmap_check (machine, max_retries
  0, timeout 120, unlocks: [tests_pass]) in gates_reference.yaml synced to gates.yaml; the completion
  test gate is the EXISTING tests_pass with test_command: ./ait test and gate_command_exit_contract: [test_command];
  there is no selection-only gate and no aitask_gate_testmap_run.sh; aitask_gate_testmap_check.sh reports
  SEEDED:<n>, ADOPTED:<n>|agent <a>|human <h> (informational) and UNMAPPED_SOURCE:<path>; an unlocks:
  target absent from a task''s active set is ignored; the completion POLICY flip is gated by readiness
  - recorded by a human in config.yaml under selected, or by the engine in costs/policy.yaml under auto
  with mode: auto, so the committed declaration and the engine''s approval ledger are different files
  and a reader can tell them apart; the engine never enables a gate and never writes a profile.'
# [inherited]
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
# [modified]
component_onboarding_engine_verbs: 'internal/onboard behind `onboard detect [--write] | inventory | seed
  | review [--next N] [--class <origin>] [--scope <glob>] [--ids <csv>] [--json] [--calibrate <n>] | classify
  [--apply|--propose] | adopt [--class ...|<test> [<source>]|--area|--files-from -|--agent-verdicts -
  --by <agent-string> --run <id>] | reject | scaffold | status | finish` and the aitestmap/onboard.yaml
  phase ledger {contract, task, level, phases{detect, inventory, seed, waivers, enable, full_run, adopt,
  review: {status, at, by, counts{reviewed, adopted, rejected, unsure}, partial}, classify, scaffold,
  finish}, rejections[] {test, source, reason|rationale, by, run?, revocable}, kind_proposals[], calibration[]}.
  `detect --write` additionally writes completion.mode: auto plus the full_run_every, agent_review and
  readiness blocks when the profile is headless and agent_review is not disabled. `review` assembles digest-stamped
  packets - REVIEW_PAIR:<id>|<test>|<source>|<origins>|<confidence>|<unsure_count>, REVIEW_ANCHOR:<id>|<file:line>,
  REVIEW_TEST:<id>|<line>|<flag>|<text> (anchor +-20 lines then every assertion line flagged ''!'', ceiling
  agent_review.packet_lines), REVIEW_SOURCE:<id>|<symbol>|<kind> (declared symbols only, never the body),
  REVIEW_PROSE:, REVIEW_MEMBER:, REVIEW_END:<id>|<packet_sha> - in < 300 ms warm; --calibrate <n> samples
  pairs with a ground truth (coverage rows, reviewed edges, human rejections) and marks them so the intake
  compares instead of writing. `adopt --agent-verdicts -` reads VERDICT:<id>|verifies|drives|unsure|<rationale>
  lines: verifies -> agent:review added, noisy-OR recomputed, >= accept_min -> stamped through the rewriter
  with an adopted.yaml row {by: agent:<s>, run, rationale, packet_sha, test_blob, source_blob}; drives
  -> rejections[] {by: agent, revocable: true}, REJECTED:; unsure -> evidence.agent.unsure++, at 2 ->
  REVIEW_HUMAN and out of the agent queue; packet_sha mismatch -> VERDICT_STALE:<id> ignored; --by must
  parse as <agent>/<model> (lib/agent_string.sh grammar) else exit 64; under --calibrate prints CALIBRATION:agree
  <a>|disagree <d>|<ratio> and appends to calibration[]. `classify --propose` writes CLASSIFY rows to
  kind_proposals[] and applies nothing. `status` adds AGENT_ADOPTED, AGENT_REJECTED, UNSURE, REVIEW_HUMAN,
  REVOKED, KIND_PROPOSALS and CALIBRATION lines. `finish` additionally requires REVOKED:0 in the window
  and REVIEW_HUMAN:0 under a headless profile. The engine reads onboard.yaml''s task: and level: and writes
  phase rows; it never creates a task, edits a profile, project_config.yaml, gates.yaml or CLAUDE.md,
  commits, or launches an agent.'
# [modified]
component_onboarding_skill: 'Onboarding skill: .claude/skills/aitask-testmap-onboard/ as a profile-aware
  stub + SKILL.md.j2 (resolver key `onboard`) with one procedure file per phase (detect.md, inventory.md,
  seed.md, waivers.md, enable.md, full-run.md, adopt.md, review.md, classify.md, scaffold.md, finish.md);
  Claude Code first, Codex and OpenCode ports as follow-up tasks; rendered goldens under tests/golden/skills/aitask-testmap-onboard/.
  Flow as the baseline (preconditions -> survey -> one aitask per level -> task-workflow -> the first
  full run at Step 9 -> timeout, readiness, next level) with adopt.md ordering rule -> measurement ->
  reading: `onboard adopt --class static:package --accept-min 1.0`, `--class coverage`, then review.md
  (the aitask-testmap-review flow inlined: `onboard review --next 20` -> read -> VERDICT lines -> `onboard
  adopt --agent-verdicts - --by <agent-string> --run onboard-<run>` until the queue is empty or max_pairs_per_run,
  the phase recorded partial and re-entered at ONBOARD_NEXT:review), then `onboard review --calibrate
  50` where a ground truth exists; attended profile: the per-class confirmation shows the agent''s verdicts
  pre-filled (accept all / review a sample of ten / edit rows / skip), kind changes confirmed individually,
  level 3 with the maintainer. Headless (remote) profile: level 0 in full; level 1 in full by rule, measurement
  and reading to budget; level 2 `classify --propose` only (kind_proposals[]); level 3 not entered; no
  policy flip because detect --write set completion.mode: auto; finish requires REVOKED:0 and REVIEW_HUMAN:0.
  `--policy selected` re-entry (a human flip) and `--no-task` unchanged. Commits per phase under `chore:
  Onboard testmap - <phase> (t<id>)`.'
# [modified]
component_qa_integration: 'aitask-qa reads the registry when aitestmap/ exists: test-discovery.md 3a-3c
  map the changed sources through `ait testmap explain --sources <paths> --format table` (Covered / Covered
  (adopted by human) / Covered (adopted by agent) / Covered (seeded) / GAP), falling back to the naming-convention
  scan only when no registry exists; test-execution.md 4a runs the configured `./ait test` through aitask_run_project_command.sh
  test_command --task-id <id>, 4b runs named units through `ait test <path>`, 4c gains a REFUSED (host
  resources) row, and 4d''s coverage component uses registry edges with seeded and agent-adopted rows
  counted as coverage that exists (QA measures whether a test exists, not who accepted the claim or whether
  it is fresh); the health score''s Tests component treats REFUSED like SKIP.'
# [inherited]
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
# [modified]
component_registry_loader: 'Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  plus axes.yaml into the six core tables with unit ids <path>[#<member>][@<variant>], the check rules,
  deterministic sorted writes; two tables added: seeds from registry/seeded.yaml (rows {test[#member],
  covers, origin[], confidence, evidence{}, proposed_at}) and adopted from registry/adopted.yaml (rows
  {test, source, origin[], confidence, adopted_at, task, by: human:<email>|agent:<agent-string>, run?,
  rationale?, packet_sha?, test_blob?, source_blob?}); onboard.yaml''s rejections[] rows {test, source,
  reason|rationale, by, run?, revocable} with the load rule that an absent by: reads as human / revocable:
  false, plus kind_proposals[] and calibration[] read by status and readiness; SEED_SHADOWED and ADOPTED_ORPHAN
  as before; write routing: onboard seed -> seeded.yaml; onboard adopt --class / --agent-verdicts (verifies)
  -> seeded.yaml (row removed) + adopted.yaml + the test file through the rewriter; --agent-verdicts (drives)
  -> seeded.yaml (row removed) + onboard.yaml rejections[]; annotate --author -> the test file + adopted.yaml;
  onboard reject -> seeded.yaml (row removed) + onboard.yaml; attribute --propose -> seeded.yaml; score
  revocation -> onboard.yaml (row removed) + seeded.yaml (row re-added); a human re-stamp -> adopted.yaml
  (row removed); config.yaml gains completion.full_run_every, agent_review {enabled, accept_min, batch,
  packet_lines, max_pairs_per_run, rejections_revocable, measured_confidence}, readiness {min_scored_full_runs,
  max_false_negatives, require_opaque_proofs, min_full_runs_since_map_change, max_revoked_rejections}
  beside conventions:, helper_roots:, helper_fanin:, exclude:, docs:, notes: and broad_threshold_s; costs/policy.yaml
  {last_full_run, selected_since_full, approved_by} is read by the front and written by the engine; golden
  tests pin the by: merge, the absent-by: rule and the id grammar.'
# [inherited]
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
# [inherited]
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
# [modified]
component_seeder: 'Seeder (internal/seed): `ait testmap onboard seed [--from static,convention,cochange,plan,prose,coverage]
  [--min-cochange 2] [--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json --out <f>]`
  produces registry/seeded.yaml rows {test[#member], covers, origin[], confidence, evidence{static: file:line,
  convention: pair, cochange: [task ids], plan: path, prose: line, coverage: run id, agent: {by, run,
  rationale, packet_sha, test_blob, source_blob, unsure: n}}, proposed_at}; static:{package, invocation,
  import} read internal/deps facts for the test file only; convention applies config.yaml conventions:
  patterns; cochange parses one git log pass cached by HEAD sha; plan reads the explain cache; prose reads
  header comments; coverage imports coverage.py contexts, go -coverprofile, LCOV or a plugin''s {test,
  covers} lines. Two READING origins are written by other verbs, never by seed: agent:review (0.90) by
  `onboard adopt --agent-verdicts` and agent:author (0.90) by `annotate --author`. Confidence table static:package
  1.0 / coverage 0.95 / agent:review 0.90 (or agent_review.measured_confidence when calibration measured
  lower) / agent:author 0.90 / static:invocation 0.90 / static:import 0.85 / observed 0.70 / convention
  0.60 / plan 0.50 / prose 0.30 / cochange 0.20 + 0.20 per group capped 0.60; each origin carries class:
  rule|measurement|reading|heuristic; noisy-OR across origins, ordering only. Helpers separated first
  by helper_roots and helper_fanin; SEED_KIND:, SEED_BATCH_NO:, SEED_MEMBER:, SEED_AXIS: from onboard
  classify''s signals. A rejected pair is never re-proposed by seed (revocation is score''s act, not seed''s);
  a pair already stamped is dropped with SEED_SHADOWED; --apply writes deterministically sorted. Budget:
  static + convention < 2 s and cochange < 5 s over 600 commits. Fixtures: a synthetic repo per origin
  with a (t<id>) history, plus one per verdict branch.'
# [modified]
component_selector: 'Selector (internal/selectr, internal/changesurface): line-protocol intake refusing
  UNKNOWN:, the graded walk with select/implies/escalate rules, variant expansion and axis join, test-dep
  at d1, ESCALATE on opaque files, scoped join, kind-then-cost ranking, invocation groups, stale marks
  from digest compare plus the per-variant evidence join, --include-stale, suite budget with DEFERRED
  lines, cut knobs incl. --axis, --format lines|json|tokens, prediction record, explain; a seeded edge
  is walked exactly like an annotation edge at d1 with reason edge(seeded:<origins>) and never contributes
  a stale mark; an adopted edge is an annotation edge whose reason carries adopted(<origins> <confidence>
  by <who>) - e.g. adopted(static:invocation+agent:review 0.99 by agent:claudecode/opus5) or adopted(agent:author
  0.90 by agent:...); `explain --sources <path>... --format table` prints the reverse view with Covered
  / Covered (adopted by human) / Covered (adopted by agent) / Covered (seeded) / UNMAPPED_SOURCE as the
  table aitask-qa consumes; the `test` composite prints one SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>
  line and UNMAPPED_SOURCE:<path> lines before the ranked rows.'
# [modified]
component_skill: 'Skills: (1) aitask-testmap (maintenance: annotate a file / member / coordinate, declare
  axis sources, reads on helpers, axes --explain, attribute before the gate, verify after editing, classify
  --suggest, select --format tokens into a render loop) opens with `ait test --howto` and hands a repo
  without aitestmap/ to aitask-testmap-onboard; (2) aitask-gate-testmap-fresh (the procedure gate: stale
  --task, git diff per STALE row, retarget STALE_PATH, re-stamp EVIDENCED, resolve check''s structural
  rows, prompt on UNSTAMPED past bootstrap, never guess UNKNOWN, never confirm STALE autonomously) whose
  seeds step now runs `onboard review --ids <rows>` for each COMMITTED:/TASK: test file with seeds and
  reads the packets - attended: the agent''s verdict is pre-filled per row and the person confirms (by:
  human), overrides, or trusts the batch (by: agent); autonomous: `onboard adopt --agent-verdicts - --by
  <agent-string> --run <gate-run>`; (3) aitask-testmap-onboard (component_onboarding_skill); (4) aitask-testmap-review
  (component_agent_review_pass): profile-aware stub + SKILL.md.j2 (resolver key `testmap-review`), review-batch.md,
  the verifies-or-drives rule stated once (''a test verifies a source when a flagged assertion checks
  an output, a state or an exit status the source''s symbols produce; it only drives it when the source
  appears solely in setup, teardown or as a path argument whose result is never checked''), batches of
  agent_review.batch, resumable, attended table-confirm / autonomous no prompts; launched by review.md
  inside an onboarding task, by `ait skillrun testmap-review` interactively, or by `ait codeagent testmap-review`
  (interactive; --print only under --headless, as batch-review). Every skill''s runtime knowledge of how
  to run tests is the seeded `## Running Tests` block plus `./ait test --howto`, never prose in a SKILL.md.
  All ship Claude Code first with wrapper surfaces regenerated by aitask_audit_wrappers.sh apply-wrapper
  for Codex and OpenCode.'
# [modified]
component_staleness_tool: 'Staleness tool (internal/stale): stale --task --changes - | --all; the SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION
  line classes with %25/%7C encoding; a STALE row on a unit with variants carries a trailing |<unevidenced
  variants> field; --all adds CHECK_STRUCTURAL:<n>; content states exit 0, --strict exits 1 on STALE_PATH;
  compares blob digests of the working tree only, consults the per-variant evidence join, adds rename
  hints and culprit task ids when history is reachable; mutates stamps via --confirm, --confirm-source,
  --confirm-evidenced, --retarget through the rewriter; seeded edges excluded from every class, SEEDED:<n>
  and ADOPTED:<n>|agent <a>|human <h> summary lines on --all, and a STALE or EVIDENCED row whose edge
  has an adopted.yaml row carrying `adopted(<origins> <confidence> by <human|agent:<agent-string>>)` in
  its DISPLAY line so the procedure gate knows whether it is confirming a class-accepted, an agent-accepted
  or a per-pair reviewed claim.'
# [modified]
component_suite_registry: 'Scoped-row registry and areas: registry/areas.yaml plus areas: blocks in hand
  files, seedable via areas --import-codemap; _scoped.yaml rows; owns: by area name; the d1 join, kind
  ranking, suite budget with DEFERRED lines; check rules incl. DEAD_SCOPE and KIND_MISMATCH|CONVERT_TO_SUITE;
  ait testmap areas; classify --suggest with the reads-helper and grid heuristics plus the three onboarding
  signals (a recorded p95 above broad_threshold_s, a source-set or directory convention, a resource declaration
  or use in the file) and fanout:<n> above unit_covers_max, each printed as the reason on the CLASSIFY:<test>|<kind>|<reason>
  line; attended, the skill confirms per batch of 20 with kind changes confirmed individually and `onboard
  classify --apply` writes the confirmed rows'' source lines at level 2; headless, `onboard classify --propose`
  records the rows in onboard.yaml kind_proposals[] and applies nothing, because a wrong kind changes
  staleness semantics and no run evidence checks it.'
# [modified]
component_test_entrypoint: '`ait test` = .aitask-scripts/aitask_test.sh, a ~150-line bash front over the
  shim with flags --task <id> | --gate | --advisory | --all | --dirty | --explain | --howto [--md] | --tokens
  | --fresh-only | --budget-s <n> | --json and positional <path|id>...; resolves MODE, TASK, INTAKE and
  POLICY as the baseline, where POLICY under completion.mode: auto runs the engine''s readiness, reads
  costs/policy.yaml, applies the three cadence triggers and prints POLICY:auto|selected|next_full_in:<n>
  or POLICY:auto|full|cadence:<tasks|selection_ratio|days> or POLICY:auto|full|not_yet:<criterion>, having
  the engine write the first ADMISSIBLE as approved_by {engine:readiness@<run>, mode: auto}; calls the
  engine `test` composite; with no aitestmap/ prints TESTMAP_ABSENT:<hint> and delegates to aitask_run_project_command.sh
  test_command; with the engine absent behaves per mode as the baseline; advisory mode prints VERDICT:/REASON:/DETAIL:/LOG:
  lines and exits 0/1/2/3; prints MODE / TASK / INTAKE / POLICY / SELECTED / RUN / RESULT, UNANNOTATED_TEST:<path>|HINT
  and UNMAPPED_SOURCE:<path>; exit 0 / 1 / 2 / 3 / 75 / 64; run-id prefixes test- / gate- / full-; dispatcher
  arm `test)`; 5 permission touchpoints; tests/test_ait_test_entrypoint.sh against a fixture repo with
  AIT_TESTMAP_BIN pointing at a fake engine that replays scripted exits, in all three modes, every REASON,
  and the auto matrix (ADMISSIBLE x each cadence trigger x NOT_YET x first-flip record).'
# [inherited]
component_test_front_verb: 'Engine `test` composite (internal/selectr + sched + runner, reached by aitask_test.sh):
  `test --task <id> --changes - | --paths <p>... | --all [--explain] [--budget-s] [--format lines|json|tokens]
  [--run <id>]` runs select --include-stale -> schedule -> run in one process and prints SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>,
  one UNMAPPED_SOURCE:<path> per changed source no unit reaches, the ranked rows with their reasons (a
  seeded edge reads edge(seeded:<origins>), an adopted one edge(annotation) adopted(<origins> <confidence>)),
  the schedule''s wave lines, results per id and RESULT:pass|fail|skip|deferred|<run_id>; --all is run
  --all (anchors evidence, scores the newest prediction, honours subsumed_by); --explain stops after select;
  the run id is prefixed by the front. It never resolves a task, reads a profile, applies a completion
  policy or touches a gate ledger - those are the bash front''s.'
# [inherited]
component_user_root: 'Per-user root: .aitask-scripts/lib/aitasks_home.sh exports AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}
  and aitasks_engine_dir <version|dev>, plus $AITASKS_HOME/.home.lock; sourced by the shim, aitask_setup.sh''s
  install_engine_binary, aitask_engine.sh, the verifiers and aitask_test.sh; never falls back to ~/.aitask/;
  ait setup creates $AITASKS_HOME/engine/ with mode 0755 and prints AITASKS_HOME:<path> in its summary
  beside the venv line so both roots are visible; ait engine prune walks only $AITASKS_HOME/engine/v*/;
  test_aitasks_home.sh pins the default, the env override, and that no framework script under this feature
  names ~/.aitask/.'
# [inherited]
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
# [modified]
component_workflow_integration: 'The procedure edits of the seam: task-workflow gains affected-tests.md
  (Affected Tests Procedure) called once from Step 7 before proceeding to Step 8, wrapped in {% if profile.affected_tests
  is not defined or profile.affected_tests != ''off'' %}; the procedure runs `./ait test --advisory --task
  <id>` in the set -e capture form, branches: pass -> continue; fail -> the build-verification fail loop;
  skip:no_selection -> display the UNMAPPED_SOURCE paths and, attended, offer annotate / attribute --propose
  / waiver with the agent''s proposed pairs pre-filled, or, autonomous, have the agent name its own test
  for each source and run `ait testmap annotate --author <test> <source> --task <id> --by <agent-string>`
  (adopted, origin agent:author; AUTHOR_REFUSED:not-in-task refused and logged) falling back to attribute
  --propose when it knows none; UNANNOTATED_TEST -> annotate --suggest then --author on the rows the agent
  confirms; skip:testmap_absent|registry_absent -> one line, continue; skip:unknown_paths -> the scope
  prompt; skip:admission_refused -> print DETAIL, continue; rc 3 -> diagnose, never fix code; the verdict
  line is recorded in the plan''s Final Implementation Notes and never in the gate ledger; it is the task-scoped
  selection guaranteed to exist in every profile; profile key affected_tests run|show|off unchanged and
  no profile key added (agent_review.enabled is project config, so provenance never depends on who ran
  the task); Step 8''s testmap_fresh dispatch plus its packet-reading seeds step; Step 9 unchanged; aitask-qa''s
  test-discovery.md and test-execution.md as the baseline with `Covered (adopted by agent|human)`; pickrem
  and pickweb inherit Step 7; ait setup prints TESTMAP:<state>; the new aitask-testmap-review skill and
  the rewritten gate skill rendered for every profile x agent; goldens regenerated; aitask_skill_verify.sh
  run.'
# [modified]
component_workflow_seam: 'The data edits of the seam: task-workflow SKILL.md.j2 Step 7 gains one paragraph
  after `Follow the approved plan` (run ./ait test as the implementation test loop, answer UNANNOTATED_TEST
  and UNMAPPED_SOURCE, never call the test tool directly); build-verification.md gains a branch for verdict
  error / reason command_refused | command_errored; lib/gate_verifier_lib.sh run_project_command_key()
  gains the 75 -> error and 3 -> error rows for opted-in keys and exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID;
  aitask_run_project_command.sh --task-id exports the former; gates_reference.yaml adds testmap_fresh
  and testmap_check (unlocks: [tests_pass]) and no selection-only gate; the project''s profiles gain tests_pass,
  testmap_check and testmap_fresh in default_gates via onboarding; no profile key is added for agent review
  (agent_review.enabled lives in aitestmap/config.yaml); the ait dispatcher gains `test)`; aitask_codeagent.sh
  gains the `testmap-review` operation (interactive by default, --print only under --headless, mirroring
  batch-review) and `list-models` shows verified.testmap-review; seed/models_{claudecode,codex,opencode}.json
  gain the verified.testmap-review key per model (0 until measured; aitask-add-model seeds it); aidocs/framework/aitasks_extension_points.md
  gains `Adding a test-framework detector` and `Adding a seed origin` with the class column (rule / measurement
  / reading / heuristic) and the autonomous-floor rule; tests/test_gate_verifiers.sh covers 75 and the
  env export, tests/test_codeagent.sh pins testmap-review interactive-by-default, tests/test_serial_carveout_doc_drift.sh
  is extended, tests/test_no_unscoped_task_commit.sh is unaffected.'
# [new]
component_agent_review_pass: 'Agent review pass: the reader-of-the-test-body mechanism - `onboard review
  [--next N] [--class <origin>] [--scope <glob>] [--ids <csv>] [--json] [--calibrate <n>]` assembles bounded,
  digest-stamped packets per seeded pair (REVIEW_PAIR:<id>|<test>|<source>|<origins>|<confidence>|<unsure_count>;
  REVIEW_ANCHOR:<id>|<file:line>; REVIEW_TEST:<id>|<line>|<flag>|<text> = the anchor +-20 lines then every
  assertion line flagged ''!'' - assert_eq / assert_contains / assert / expect / require / t.Fatal* /
  assertEquals / shouldBe / grep -q on captured output - ceiling agent_review.packet_lines (120); REVIEW_SOURCE:<id>|<symbol>|<kind>
  = declared symbols only, never the body; REVIEW_PROSE:; REVIEW_MEMBER:; REVIEW_END:<id>|<packet_sha>)
  from the deps cache in < 300 ms warm, no runner and no model; `onboard adopt --agent-verdicts - --by
  <agent-string> --run <run-id>` consumes VERDICT:<id>|verifies|drives|unsure|<rationale <= 160 chars>
  lines with six outcomes: verifies -> agent:review added, noisy-OR >= accept_min -> adopted through the
  rewriter with an adopted.yaml row {by: agent:<s>, run, rationale, packet_sha, test_blob, source_blob}
  (WROTE:, ADOPT_SUMMARY:); drives -> rejections[] {by: agent, revocable: true} (REJECTED:<test>|<source>|agent);
  unsure -> evidence.agent.unsure++, at 2 REVIEW_HUMAN and out of the agent queue (UNSURE:); packet_sha
  mismatch -> VERDICT_STALE:<id> ignored and re-packeted; --by failing lib/agent_string.sh''s <agent>/<model>
  grammar -> exit 64 (humans use the per-row verbs); --calibrate -> no writes, CALIBRATION:agree <a>|disagree
  <d>|<ratio> appended to onboard.yaml calibration[]. Three sites share the intake: the testmap_fresh
  in-gate step (the task''s touched test files; attended pre-fill / confirm / trust-batch, autonomous
  adopts), the pre-review Affected Tests procedure (the task''s own pairs via `annotate --author`, origin
  agent:author, AUTHOR_REFUSED:not-in-task otherwise) and the bulk skill aitask-testmap-review (profile-aware
  stub + SKILL.md.j2, resolver key testmap-review, review-batch.md stating the verifies-or-drives rule
  once, batches of agent_review.batch (20), resumable through onboard.yaml phases.review with max_pairs_per_run
  (400), attended table-confirm per batch, autonomous no prompts, commits under `chore: Onboard testmap
  - review (t<id>)` inside an onboarding task, prints the commit lines otherwise). Launch surfaces: review.md
  inside the onboarding task; `ait skillrun testmap-review [--profile <p>] [-- --class <origin>]` (interactive);
  `ait codeagent testmap-review [--headless]` (--print only under the flag, as batch-review). `verified.testmap-review`
  in seed/models_{claudecode,codex,opencode}.json (the existing per-operation score table; 0 until measured;
  aitask-add-model seeds the key). config.yaml agent_review: {enabled: true, accept_min: 0.85, batch:
  20, packet_lines: 120, max_pairs_per_run: 400, rejections_revocable: true, measured_confidence: <written
  by calibration>}. Tests: engine fixtures per language for packet shape and assertion flagging, every
  verdict branch, VERDICT_STALE, the --by grammar refusal, calibration against a coverage fixture, revocation
  on a synthetic miss, AUTHOR_REFUSED; skill goldens for every profile x agent; tests/test_codeagent.sh
  pins testmap-review interactive-by-default.'

# ===== TRADEOFFS =====
# [inherited]
tradeoff_accept_rewrites_history: 'Disadvantage: adopting seeds inserts comment lines into hundreds of
  test files, so `git blame` on any test header points at the adoption commit and a concurrent task editing
  the same file hits a textual conflict on the header; mitigated by comment-only insertions at a fixed
  position (after the header block / docstring / package clause / import block), per-class and per-area
  batch commits named for what they are, the incremental path that adopts a file''s seeds only inside
  a task that already edits it, ADOPT_REFUSED:dirty-foreign, and the rewriter''s REWRITE_CONFLICT refusing
  a file that changed under it; a project that wants no comment churn keeps seeds unadopted and accepts
  selection-only enforcement, which onboard status reports as the state it is.'
# [inherited]
tradeoff_area_glob_coarseness: 'Disadvantage: area and scope globs are coarser than edges - a broad area
  over-selects its tests on every edit inside it and a scoped test depending on a file outside its scope
  is under-selected until a full run scores it; mitigated by the suite budget with explicit DEFERRED lines,
  budget-exempt triggers and reads globs for known sharp edges, and the missing-trigger / area-too-narrow
  attribution path.'
# [inherited]
tradeoff_attribution_risk: 'Risk: an agent that edits sources without attributing produces a map that
  looks current and is not; narrowed three ways - such a source shows as STALE in the next task touching
  it and as a stale mark on every selection; the Step-7 run reports UNMAPPED_SOURCE:<path> for a changed
  source no unit reaches at the moment the agent introduced it, and the pre-review procedure offers annotate
  / attribute --propose / waiver right there, so a new coupling with no edge is surfaced during the task
  rather than only on a full run; and in a repo whose completion policy is full every miss is counted
  by the automatic score within one task. What still escapes is a coupling to a source that already has
  some edge, which only score can find.'
# [modified]
tradeoff_autonomous_confirmation_weak: 'Risk: an autonomous run now does more than confirm evidence -
  it accepts claims (agent:review, agent:author), rejects seeds, and flips the completion policy (auto).
  Narrowed: --confirm-evidenced remains the only bulk RE-STAMP an autonomous profile may run; an agent
  acceptance is a fresh stamp whose adopted.yaml row carries by: agent, the run id, the rationale and
  the packet digest, all displayed by stale, explain, check and readiness and counted as AGENT_ADOPTED;
  a STALE row is still never confirmed without a person; an agent rejection is revocable by the next scored
  miss; the policy flip is bounded by the cadence, reversed by the automatic demotion, and recorded with
  mode: auto in costs/policy.yaml rather than in config.yaml; and agent_review.enabled: false restores
  the baseline''s human-only adoption exactly.'
# [inherited]
tradeoff_axis_declaration_burden: 'Disadvantage: axes are a third authoring surface, and a project that
  declares them wrongly gets confidently wrong selection. Concretely: thinking_app must declare ten matrix
  values with three facets, four locale source-glob sets, one values/** rule, one runner script (list/describe/run/children
  over its existing routing) and one testmap:axis line per non-capturing coordinate test. Mitigated by
  making membership declarative and checkable - DEAD_AXIS_SOURCE fails a source glob that matches nothing,
  UNKNOWN_VARIANT a listed variant outside the axis, UNCOVERED_VALUE a declared value no runner lists,
  and axes --explain <path> answers why one file landed where it did before anything is trusted; and by
  an undeclared source reaching every variant, so an incomplete axis over-selects rather than under-selects.'
# [inherited]
tradeoff_axis_projection_coarseness: 'Disadvantage: the default axis join is file-level - a one-key edit
  to values-ru/strings.xml selects every enrolled screen on both ru matrices (about 65 variants) rather
  than the screens naming that key; sound but 2/10 of the matrices rather than 1/50 of the screens; mitigated
  by the opt-in android-res symbol scanner (keys changed -> referencing Kotlin files -> member units),
  by select --format tokens feeding the project''s own render loop so the over-selection costs a preview
  rather than a gate, and by the group-costed budget.'
# [inherited]
tradeoff_batch_misreport_risk: 'Risk: a batch runner that misreports per-unit results corrupts attribution,
  cost and evidence (a false pass could manufacture an EVIDENCED row); the JUnit classname/name to variant-id
  inversion and the zero-match trap at method granularity (a Gradle --tests filter matching nothing exits
  0 with zero tests) are two places to misreport; mitigated by units_expected/units_reported reconciliation
  per id, a row inverting to no registered id and units_reported == 0 with units_expected > 0 both being
  mechanism failures, and no line from an invocation with a cause ever anchoring.'
# [inherited]
tradeoff_broad_scope_coarseness: 'Disadvantage: a test scoped to a large area is selected for any change
  inside it; mitigated by ranking last at its distance, running only after a green unit wave, being cut
  first by the suite budget with the cut printed as DEFERRED, and the cost visible in schedule.'
# [modified]
tradeoff_bulk_confirmation_granularity: 'Risk: adopting edges per evidence class (398 static edges in
  one answer) traded review depth for feasibility; agent review restores depth at feasibility''s price
  - every pair is read, but by an agent, and a class-level human yes over pre-filled verdicts is still
  one answer. Mitigated by the three-sample display, `review a sample` drawing ten random members with
  their signals AND the agent''s verdict and rationale beside each, --accept-min raising the bar, --scope
  <glob> onboarding one area per task, the adopted.yaml provenance with by: so nothing pretends to be
  a per-pair human review, readiness reporting ADOPTED_UNREVIEWED and AGENT_ADOPTED, the per-row path
  for anyone who wants depth, the attended choice per batch between confirm-each / trust-batch, autonomous
  profiles being limited to rule, measurement and reading origins, and kind reclassifications being confirmed
  individually by a person because a wrong kind changes staleness semantics rather than selection breadth.'
# [inherited]
tradeoff_cell_table_size: 'Disadvantage, inverted: instead of about 2,500 generated cell rows that churn
  whenever a screen or matrix is added, _scanned.yaml carries 49 member rows with a variants: list of
  at most ten values; the price is that scan and check exec each runner''s list (thinking_app: a bash
  script reading two manifests, milliseconds) and that a matrix added to the manifests is invisible to
  select until the next scan --apply - which check reports as UNKNOWN_VARIANT/UNCOVERED_VALUE drift the
  same day. Enumerating at every select was rejected because it would put a build-adjacent exec on the
  hot path of every gate.'
# [inherited]
tradeoff_compiled_component_cost: 'Disadvantage: the framework gains a compiled component - contributors
  touching the engine need Go, a release fails if go test fails, install gains a fetch and checksum step;
  mitigated by a single build.sh matrix, ait engine build, and the engine being optional until a testmap
  gate is enabled.'
# [inherited]
tradeoff_computed_vs_prose: 'Advantage: selection is computed, explained and scored rather than remembered;
  blast radius becomes data instead of prose - thinking_app''s ''a localized screen change may use preview,
  a shared component must run the full gate'' rule becomes an axis join, an import-scanner fan-out and
  an ESCALATE: line, each printed with the path that caused it; and so is the run surface - `ait test
  --howto` prints the runners, resources, full gate, gates, axes, policy and doc pointers from the registry
  and the ledger, and the generic Running Tests section is identical in every project, so an agent never
  learns ''how do I run tests here'' from a 200-line CLAUDE.md testing section again (thinking_app''s
  is 200 lines today); the project''s judgement calls become config.yaml notes: lines and docs: pointers
  the brief prints, still prose, but reached through one verb rather than found.'
# [inherited]
tradeoff_dispatcher_verb_added: 'Disadvantage: `ait test` is a new top-level dispatcher verb beside `ait
  testmap`, two surfaces for one engine; justified by the extension-points rule (a human plausibly types
  `ait test`, and the seed instruction needs one memorable verb), kept thin (mode / task / intake / policy
  / fallback / advisory resolution only, everything else delegated to the shim and the engine `test` composite),
  and `ait testmap` stays the maintainer surface for annotate / scan / check / stale / axes / onboard;
  removing a verb later is a breaking change, so --howto documents `ait test` as the stable one.'
# [inherited]
tradeoff_engine_absent_on_host: 'Risk: an unsigned macOS binary or a blocked download leaves a host without
  an engine; mitigated by ENGINE_MISSING naming the $AITASKS_HOME path and repair verb, --engine-from-source
  and --local-engine fallbacks, and the testmap gates exiting 3 (error), never skip, when the engine is
  absent; two deliberate, printed exceptions: `ait test --advisory` reports VERDICT:skip REASON:testmap_absent
  so the pre-review Step-7 run in task-workflow, pickrem and pickweb - which has no ait setup at all -
  continues exactly as today, because an advisory run must never block a task the way a declared gate
  legitimately does; and a project may set completion.engine_absent: fallback_command so the Web lane''s
  tests_pass runs the pre-onboarding suite command with MODE:fallback visible, the default staying error;
  neither skip is silent.'
# [inherited]
tradeoff_engine_speed_enables_per_task_use: 'Advantage: sub-second select/check/stale on a 720-test repo,
  and sub-250 ms select over 297 variants with axis expansion, makes selection overhead negligible against
  the shortest test and lets check run at every commit step; the facet join is one glob match per changed
  file per facet and one set test per member, select never execs a runner, and a bash+Python engine would
  spend seconds in start-up and YAML parsing first.'
# [inherited]
tradeoff_engine_version_skew: 'Disadvantage: one user with several projects on different framework versions
  keeps several ~10 MB binaries under $AITASKS_HOME/engine/; mitigated by exact-version resolution in
  the shim (never newest-wins) and ait engine prune against the project registry, never a count-based
  prune.'
# [inherited]
tradeoff_evidence_requires_reachable_history: 'Risk: the evidence join can only suppress a STALE row when
  the anchoring commit is reachable, so a depth-1 CI clone or a fresh shallow worktree sees the precise
  digest verdict with no self-healing; the safe direction, and the reason stale --strict fails only on
  STALE_PATH (structural rot is check''s); a repo-wide stale --all --strict job should run on a full clone
  or accept STALE noise.'
# [modified]
tradeoff_fail_closed_bootstrap_cost: 'Disadvantage: fail-closed enforcement means bootstrapping each repo
  requires a waiver pass before testmap_check can be enabled, a first green full run before require_stamp
  and --strict, a green runner list before structural rules can fail, and min_scored_full_runs (plus min_full_runs_since_map_change)
  before the completion policy may reach the selection; narrowed by making the bootstrap order one aitask
  per level that the onboarding skill creates and runs, the seeder replacing most of the hand waiver pass
  (88% of bash and 80% of Python tests on aitasks seed at least one edge), the level-0 task''s own tests_pass
  gate being the first anchoring full run, bootstrap_until at +90 days, adoption incremental by class,
  by area, by agent batch, in-gate or at authoring, and readiness printing LEVEL / NEXT; one cost the
  baseline carried is removed - a repo is no longer level 0 ''until a human adopts level 1'', because
  a headless profile adopts by rule, measurement and reading and auto flips the policy when the scored
  history allows; what remains is real: kinds and axes are human, REVIEW_HUMAN pairs wait for a person,
  the calibration prior runs unmeasured where no ground truth exists, and the required full runs must
  still happen.'
# [inherited]
tradeoff_fallback_runs_more: 'Disadvantage: when the engine binary is absent in completion mode and the
  project chose engine_absent: fallback_command (the Claude Code Web lane, where ait setup never ran),
  `ait test --gate` runs the whole pre-onboarding suite command - never less than before onboarding, but
  never selective either, and with no per-unit results, no evidence anchors and no scoring; mitigated
  by the default being error (the gate reads error, not pass), by ENGINE_MISSING naming the path and repair
  verb, and by the fallback being visible as MODE:fallback in the result.'
# [inherited]
tradeoff_flaky_pass_anchors: 'Risk: a flaky pass anchors evidence as surely as a real one; mitigated by
  per-run status in the ledger so costs exposes a flake rate per id, and an id above flake_threshold is
  excluded from the evidence join.'
# [inherited]
tradeoff_generated_brief_limits: 'Disadvantage: a brief computed from the registry cannot say what a project''s
  people know about when a narrow run is acceptable, which device is the real test device, or why RTL
  is the design gate - thinking_app''s testing prose carries exactly that; mitigated by config.yaml docs:
  (paths the brief prints, so the prose is one hop away and named) and notes: (<=10 verbatim lines for
  the rules that must not be one hop away), and by the seeded instructions telling agents to read `ait
  test --howto` before touching a test tool; the limit that stays is that notes: is prose an agent may
  still misread, which the gates and the full completion policy backstop.'
# [inherited]
tradeoff_home_migration_window: 'Risk: when run, the migration has a sub-millisecond window between rmdir
  ~/.aitask and ln -s during which a concurrent process that hardcodes the legacy path (rather than using
  the resolver) sees ENOENT; narrowed by the flock, by symlinking immediately after the rmdir, and by
  refusing while another ait holds the home lock - not eliminated. Measured surface: 8 framework code
  files with 35 references (21 in aitask_setup.sh), 20 test files, 18 doc files, the venv''s absolute
  shebangs and two symlink trees - none rewritten by the migration, all resolving through the symlink.
  Its refusal cases are the ones a designer does not see on their own host: an earlier known-entry set
  lacked pypy_venv, which this host carries. Both are why the verb is explicit in this release and the
  default flip waits for the real-install test.'
# [inherited]
tradeoff_intersection_can_underselect: 'Risk: an axis-source hit is sharper than a file edge - it selects
  only the variants carrying the facet value - and is therefore capable of missing a real coupling that
  a plain covers edge (every variant) would have caught, e.g. a font family assigned to the wrong locale''s
  glob. Narrowed structurally: under-selection needs an explicit, reviewable wrong glob, never an omission,
  because a file matching no axis source reaches every variant; score on a full run raises missing-axis-source;
  observed sources may only widen; --axis and --format tokens with preview are the reviewer''s escape;
  and every variant row prints the facet value that placed it, so what a sharp selection excluded is visible
  in the prediction record.'
# [inherited]
tradeoff_member_annotation_drift: 'Risk: a member unit''s annotation lives in a block keyed by name (testmap:unit
  Welcome) and the runner''s list keys the same member by another artifact (the golden manifest''s Welcome_<matrix>.png);
  a rename on one side orphans the other; mitigated by check reporting a listed member with no block (UNANNOTATED_MEMBER)
  and a block with no listed member (DEAD_MEMBER), both fail-closed, by scan --apply refusing rather than
  guessing, and by thinking_app''s own manifest/@Test drift loop failing the rename on its side.'
# [inherited]
tradeoff_noarch_packages_preserved: 'Advantage: Homebrew, AUR, .deb, .rpm and the tarball ship nothing
  compiled; the per-arch concern is contained in one release job and one setup function.'
# [inherited]
tradeoff_onboarding_partial_coverage: 'Disadvantage: onboarding cannot map what no origin reaches - thinking_app''s
  same-package tests (imports resolve for 139 of 339 files), fixture-driven tests, and any source with
  no static, convention, plan, prose, co-change or coverage relation - so a freshly onboarded repo has
  UNMAPPED_SOURCE rows and area-only coverage for a share of its tree; mitigated by the waivers phase
  (rules for hot directories, expiring waivers for the rest) so check can be enabled non-strict, by the
  Step-7 UNMAPPED_SOURCE prompt that maps a source the first time a task touches it, by opt-in per-unit
  coverage where the tool supports it, and by the full gate staying the completion policy; the honest
  reading of `onboard status` after one session is ''selecting on most tests, claiming on few'', and the
  design treats that as a state, not a failure.'
# [modified]
tradeoff_one_gate_not_two: 'Advantage: one completion test gate whose behaviour is a committed policy,
  instead of tests_pass (full) beside a second selection-only gate - an agent learns one command and one
  gate, a project keeps its existing tests_pass declaration and timeout key, the legacy Step-9 path and
  aitask-qa reach the selective lane through the same test_command, and under auto the policy needs no
  one to flip it, so a headless repository reaches the selective lane by itself. Disadvantage: the gate''s
  meaning now depends on config.yaml AND, under auto, on the run''s readiness and cadence state, so a
  reader of a ledger `tests_pass: pass` must look at the run''s MODE / POLICY line to know whether the
  whole suite ran; mitigated by the verifier result= field carrying MODE:<full|selected>|<n units>|policy:<mode>[|next_full_in:<n>|cadence:<trigger>],
  by the POLICY:auto|... line printed on every completion run, by the gate- run-id prefix in the cost
  ledger, by POLICY_DEMOTED being loud, and by readiness printing what --gate would run now and when the
  next cadence full run falls.'
# [inherited]
tradeoff_real_scheduler: 'Advantage: goroutines plus flock(2) give correct cross-worktree contention and
  a critical-path report; the shell suite and the pytest lane get the enforced do-not-overlap that is
  only a comment today; a variant batch is one Gradle invocation holding one heavy-run slot, ordered after
  cheaper invocations in its wave; thinking_app''s heavy-run lock and emulator allocator become declared
  resources the schedule report can reason about.'
# [inherited]
tradeoff_registry_directory_complexity: 'Disadvantage: a merged registry directory needs more CLI logic
  than a single file would - eight tables, two generated files, one ledger, an id grammar with member
  and variant fragments and an artifact column in list; kept to one directory with one merge rule in one
  Go package with golden tests, no second plugin directory or generated cell table, and the axis table
  is empty for every project that declares none.'
# [inherited]
tradeoff_resource_declaration_completeness: 'Risk: declared resources are only as complete as the declarations;
  an undeclared interference is invisible until a full run or a probe finds it; serial-by-default at bootstrap
  means declarations are reviewed in the schedule report before concurrency is trusted.'
# [inherited]
tradeoff_seed_noise: 'Risk: heuristic seeds are wrong in both directions - a convention pairs a test with
  a homonym, an import names a helper the test only uses, co-change ties every file of a wide task to
  every test of that task (thinking_app: 7.2 main files per co-changing commit), and a wrong seed selects
  tests that cannot fail for the change. Mitigated by seeds selecting (wasted minutes) and never claiming
  (no false EVIDENCED), by the confidence table ordering review rather than gating it, by the 0.60 co-change
  cap and min_cochange 2 across distinct tasks so corroboration cannot reach the class threshold alone,
  by imports restricted to direct main-root imports (same-package facts excluded), by helpers separated
  before scoring, by the evidence printed beside every seed at review, by rejection memory in onboard.yaml,
  and by the suite budget and --format tokens for a repo where over-selection is expensive; what remains
  is reviewer fatigue on a 1,000-seed queue, which class adoption with samples, per-area batches and the
  in-gate incremental path spread over time.'
# [modified]
tradeoff_seed_precision: 'Risk: an adopted covers edge is a machine claim wearing a human annotation''s
  clothes - the static closure says the test executes the script, not that it verifies it. With agent
  adoption it is a READING''s claim, and the reading answers exactly the executes-vs-verifies question
  the closure could not. Narrowed: adopted edges are recorded in registry/adopted.yaml with by:, displayed
  as adopted(... by <who>) in stale and explain until a human re-stamps them, readiness reports ADOPTED_UNREVIEWED
  and AGENT_ADOPTED, the over-claim direction only over-selects, the class threshold 0.85 keeps heuristic-only
  edges out, the packet flags assertion lines so the verdict is drawn from evidence and stores its digest
  and rationale, `unsure` is an allowed answer so the agent is never forced to guess (two -> REVIEW_HUMAN),
  calibration against coverage or human rows measures the origin before it is trusted, and a project that
  wants no machine claims at all sets agent_review.enabled: false or stops at the seeded state; what it
  cannot do is invent a subject the closure does not contain - such a coupling is caught only by a full
  run''s score, or named by the authoring agent at the moment it is created.'
# [inherited]
tradeoff_setup_network_fetch: 'Disadvantage: ait setup gains the framework''s first self-downloaded release
  asset; mitigated by reusing the CDN URL family install.sh already uses, SHA256SUMS verification, the
  .sha256 sidecar, --no-testmap / AIT_TESTMAP_FETCH=0, the shim never fetching on its own, and setup never
  depending on the binary for anything else.'
# [inherited]
tradeoff_split_home_rejected: 'Disadvantage of the permanent-split alternative: installing only the engine
  at ~/.aitasks/engine/ and leaving venv, pypy_venv, python, bin and uv at ~/.aitask/ satisfies the naming
  mandate literally with zero migration risk, but leaves a user with two dot-directories one character
  apart holding halves of one install, which ait setup --repair, ait engine prune, backup advice and every
  doc page would have to explain forever. Chosen: the split as the transition, not the end state - the
  migration is designed, shipped as an explicit verb and testable now, with the symlink making it reversible
  (rm ~/.aitask && mv ~/.aitasks ~/.aitask), and becomes ait setup''s default in a named follow-up.'
# [inherited]
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
# [inherited]
tradeoff_static_scanner_overselection: 'Disadvantage: static scanners overselect on hot files and cannot
  see runtime coupling; a shared component (thinking_app''s ui/components/*) fans out to most screens
  on every matrix, which is the correct answer and close to a full run, and ScreenFixtures.kt reaches
  every member because the change surface is file-level; kind ranking, the suite budget and --budget-s
  trim scoped rows first, the android-res symbol scanner narrows a catalog edit to the screens naming
  the changed keys, a project scanner plugin can narrow a hot resource file, and hunk-level attribution
  inside a member file is the later narrowing tool.'
# [inherited]
tradeoff_strict_version_handshake: 'Risk: the binary must match .aitask-scripts/VERSION exactly, so an
  ait upgrade on a host that cannot fetch leaves ait testmap refusing to run until a matching binary is
  supplied; intended fail-closed behaviour, and the error names the fix (ait setup, AIT_TESTMAP_BIN, ait
  engine build) and the $AITASKS_HOME path it looked in.'
# [modified]
tradeoff_two_edge_states_during_adoption: 'Disadvantage: until both queues are empty a repo has FOUR provenances
  of edge a reader must keep apart - seeded (selecting only), adopted by human (stamped, class-accepted
  with a provenance row), adopted by agent (stamped, a reading''s claim with by:, run, rationale and packet
  digest) and reviewed (stamped, accepted per pair by a person); mitigated by the seeded origin or adopted(...
  by <who>) printed on every row, the agent/human split on SEEDED:/ADOPTED: in check, stale --all, readiness
  and --howto, `onboard status` as the one place the ratios live, and the rule that no seed and no agent
  verdict ever changes a freshness verdict on another edge; the cost the baseline recorded - --strict
  waiting on adoption forever in a repo no one reviews - is removed for headless repositories and replaced
  by the bounded exposure window recorded under tradeoff_auto_policy_exposure_window.'
# [inherited]
tradeoff_two_toolchains: 'Disadvantage: bash and Go in one framework; mitigated by the boundary rule (parse/walk/match/digest/schedule
  in Go; gate ledger, task file and shell environment in bash; builtins exec configured commands and never
  source shell state), the engine-check.yml job, and Go source confined to engine/ and excluded from the
  tarball so target projects never need Go.'
# [inherited]
tradeoff_two_user_roots: 'Disadvantage: until ait engine home --migrate is run, a host carries ~/.aitask/
  (venv, pypy_venv, python, bin, uv) and ~/.aitasks/ (engine) side by side, and a user who deletes one
  to reset the framework removes half of it; mitigated by one variable (AITASKS_HOME) with one library
  owner, ait setup printing both roots and the HOME_LEGACY: hint, ENGINE_MISSING naming the exact path,
  ait engine home reporting the state, a test that fails if any script of this feature names ~/.aitask/,
  and the migration verb existing now rather than as an unowned ''later change''.'
# [inherited]
tradeoff_verify_build_wired_suites: 'Disadvantage: a project that wired its test suite as verify_build
  (thinking_backend''s run_script_tests.sh, which also enforces a shellcheck baseline) cannot be onboarded
  mechanically - moving the command to a suite runner would drop the lint half from build_verified, leaving
  it would run the suite twice at completion; detect therefore reports SUITE_CANDIDATE:verify_build and
  the skill asks (keep as verify_build and add test_command: ./ait test over the detected bash-file and
  pytest units; or split the script), defaulting to keep, and records the answer in the onboarding plan;
  headless profiles keep.'
# [inherited]
tradeoff_whole_run_filter_soundness: 'Risk: where a runner''s filter restricts a whole test run (Gradle
  --tests on thinking_app''s single testDebugUnitTest task), every class not selected is silently not
  run, so a narrow selection is only as sound as the test-side closure, the reads globs and the opaque
  contract; mitigated by list enumerating the whole universe so an unlisted class fails check, the test-dep
  closure over abstract bases and helpers, testmap:reads on tree-scanning helpers (71 SourceFence importers
  stay selected on any Kotlin change), ESCALATE on opaque files, red-proof fixtures per branch, readiness
  gating the policy flip on scored history, and the project keeping its full suite as the completion gate
  until readiness is met.'
# [inherited]
tradeoff_workflow_surface_growth: 'Disadvantage: the seam adds one task-workflow procedure file, one profile
  key, one dispatcher verb, one skill-invoked script with a second mode (five allowlist touchpoints -
  .claude/settings.local.json, .codex/rules/default.rules and the three seeds - pinned by tests/test_touchpoint_count_contract.sh),
  a Step-7 render change across every profile x agent golden, one build-verification branch, two aitask-qa
  procedure edits, a seed-instructions edit and a profile-aware skill with two wrapper surfaces; mitigated
  by all of it degrading to a printed skip where the engine is absent (no environment conditionals), by
  the advisory mode reusing the exact VERDICT:/REASON: contract and capture form the build-verification
  path already teaches, by there being one script rather than two, and by aitask_skill_verify.sh plus
  the goldens catching a drifted render before commit.'
# [new]
tradeoff_loop_closes_without_a_person: 'Advantage: the value the mandate names is realised - seeding,
  adoption, the policy flip and the safety net are each performed by a machine or an agent under a committed
  policy, so a repository onboarded by a headless profile reaches a per-change-set completion gate within
  min_scored_full_runs + min_full_runs_since_map_change tasks of level 0 with nobody typing anything,
  and what remains human is a printed list (KIND_PROPOSALS, REVIEW_HUMAN, axes) rather than an assumed
  step. Disadvantage: in such a repository the map''s provenance is mostly by: agent, and a reader who
  wants human-reviewed claims must look for the human split in onboard status - never hidden, but no longer
  the default state; and disabling the loop (agent_review.enabled: false, completion.mode: full) is now
  a deliberate act a project must take, where the baseline made human acceptance the only path.'
# [new]
tradeoff_wrong_positive_invisible_to_score: 'Risk: a wrong `verifies` verdict is never detected by the
  feedback loop, because a claimed edge that should not exist can only over-select and score measures
  under-selection; its cost - needless runs of that test when the driven source changes, STALE nags on
  a pair the evidence join heals when the test passes - is bounded but accumulates silently in the AGENT_ADOPTED
  share. Mitigated by the packet flagging assertion lines so the verdict is drawn from evidence rather
  than from the file name, by `unsure` and REVIEW_HUMAN so the agent is never forced to guess, by calibration
  against coverage facts or human rows before the origin is trusted and agent_review.measured_confidence
  lowering its weight where calibration is poor, by the stored packet digest and rationale letting a later
  reader see what the agent saw, by the human re-stamp path deleting the provenance row, and by onboard
  status reporting the agent share so a maintainer can sample it. What remains: a repository with neither
  coverage nor human-reviewed rows has no calibration ground truth, runs on the 0.90 prior, and readiness
  states CALIBRATION:none rather than pretending to a measurement.'
# [new]
tradeoff_auto_policy_exposure_window: 'Risk: under completion.mode: auto a task may land while an affected
  test never ran, until the next cadence full run - the residual risk that replaces reviewer fatigue.
  Its size is a project choice: full_run_every.tasks (default 5) bounds it in tasks, days (7) in time,
  selection_ratio_above (0.60) makes the cheap-to-run-full case run full and score for free; every completion
  run prints next_full_in:<n>; the demotion still fires on the first scored miss and on any revoked rejection;
  and a project that cannot accept any window keeps full or a human-flipped selected. What remains: up
  to tasks - 1 tasks may merge on a wrong selection before the miss is scored, and their dependents may
  have built on them - blocks_dependents on tests_pass does not help because the gate passed; the honest
  mitigation is the number itself, chosen with the measured saving in view and printed on every run.'
# [new]
tradeoff_periodic_full_run_cost: 'Disadvantage: the cadence spends full runs a human flip would not -
  one in every full_run_every.tasks completion runs plus the days and ratio triggers. On aitasks (p95
  ~400 s full, typical selection ~40 s) tasks: 5 keeps about 80% of the saving; on thinking_app (1,180
  s full) the same cadence keeps about 75% and the project may raise tasks once its calibration and revocation
  counters have been zero for a while. Mitigated by the ratio trigger (a selection that would cost >=
  60% of full runs full and resets the counter for free), by every full run doing double duty (evidence
  anchors, cost fold, score), by the cadence living in config.yaml beside the policy so it is a declaration
  rather than a surprise, and by readiness printing the cadence with the measured saving.'
# [new]
tradeoff_agent_review_token_cost: 'Disadvantage: bulk review costs model tokens - about 36 packets of
  <= 2,400 excerpt lines plus symbol lists on aitasks - and a headless launch costs more per token than
  an interactive one. Mitigated by the packet excluding source bodies and capping test excerpts at packet_lines,
  by the in-gate and authoring sites reading inside a session that already has the files open (no extra
  launch), by max_pairs_per_run bounding one run and the review phase resuming, by rule and measurement
  classes adopting without any reading, and by the headless launch being an explicit --headless flag on
  `ait codeagent testmap-review` rather than a default of any path.'
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

### What the feature is

A framework feature, generic across `aitasks`, `thinking_app`,
`thinking_backend`, `aitasks_go` and `aitasks_mobile`, that keeps a **test
map** — a relation between source files and test units — and uses it to
select, run, track, learn, enforce and teach. The engine is a static Go binary
under `$AITASKS_HOME/engine/v<VERSION>/`; the map is a committed `aitestmap/`
directory; machine-proposed edges pass through a three-file adoption ledger
(`seeded.yaml` → `adopted.yaml` → reviewed stamps); onboarding is a resumable
skill that runs one aitask per level; the run surface is one verb, `ait test`,
in interactive, completion and advisory modes.

### How this approach differs from the baseline

The baseline's loop is automatic everywhere except at two points, and both
sit on the path from "the map exists" to "the completion gate shrinks":

1. **Acceptance.** A seeded edge becomes a claim only when a person accepts
   it, because the closure proves a test *executes* a script, not that it
   *verifies* it, and the baseline assumes only a person can tell the two
   apart. Until acceptance happens, `--strict` cannot be enabled and
   `readiness` cannot count stamped coverage.
2. **The policy flip.** `completion.mode: selected` is written only by a
   human after `readiness` reports `ADMISSIBLE`. Until then `tests_pass` runs
   the whole suite, and the per-change-set selection that every interactive
   run already computes never reaches the gate.

This proposal replaces the assumption behind (1) and the human behind (2),
and names precisely what stays human. The statement it rests on is: *the
judgement "does this test verify this source, or only drive it?" needs a
reader of the test body, and an agent is a reader.* Four changes follow:

- **Two reading origins.** `agent:review` (0.90) — a headless-safe verdict
  from an agent that read a bounded packet of the test and the source —
  and `agent:author` (0.90) — the agent that just wrote the test or the
  source naming the pair itself. Under the existing noisy-OR a static edge
  plus a reading clears the 0.85 class threshold
  (`static:invocation + agent:review` = 0.99), and a reading alone clears it
  too. Every reading carries who read (an agent-string), which run, what
  packet (a digest), and a one-line rationale, so an adopted row never
  pretends to be a human review.
- **The autonomous floor is "rule, measurement or reading", not "1.0".**
  `static:package` is a rule, `coverage` is a measurement, `agent:*` is a
  reading; a headless profile may adopt any class whose every member
  carries at least one of them. Heuristic-only classes (`static:invocation`
  alone, `convention`, `cochange`, `plan`, `prose`) still need a reading on
  top. This makes level 1 headless on all five target repositories.
- **A self-approving policy with a scheduled full run.**
  `completion.mode: auto` lets `ait test --gate` flip to the selection when
  `readiness` is `ADMISSIBLE`, recording `approved_by: engine:readiness@<run>`
  with `mode: auto` (the same `explicit | auto` vocabulary `ait note read`
  already uses), and demote loudly as before. The person is replaced by a
  cadence — `full_run_every: {tasks, selection_ratio_above, days}` — so
  scoring never stops and a miss is caught within a bounded number of
  tasks. The invariant "the policy can only fail toward running more" holds.
- **The authoring agent annotates.** The pre-review procedure's autonomous
  branch no longer only proposes: for a source it introduced or a test it
  wrote, the agent writes the `testmap:covers` line through `annotate
  --author`, adopted with origin `agent:author`.

Two things are deliberately kept human: **kind changes** (a wrong kind
silently changes staleness semantics and no run evidence can check it) and
**axis declaration** (level 3). One thing is made *safer* than the baseline:
an **agent rejection is evidence-revocable** — a scored full-run miss whose
`(test, source)` pair sits in `rejections[]` with `by: agent:*` re-seeds the
pair and counts against `readiness`, because a wrong "only drives" verdict is
the one agent judgement that can under-select, and it is the one that a full
run *can* catch. A wrong "verifies" only over-selects, which is the
direction seeds were already allowed to err in.

The cost, stated once: the residual risk moves from reviewer fatigue to "a
wrong agent verdict lets a task land while an affected test never ran,
until the next full run". The knob for that risk is the full-run cadence,
per project, in `config.yaml`, printed by `--howto`.

### Reading guide

*Architecture* introduces the vocabulary, the process boundary and the
rewritten design decisions. *Data flow* walks a task, a completion run under
`auto`, headless onboarding through level 1, and the revocation path. *The
adoption model* holds the extended origin table and the new autonomous floor.
*Onboarding* has the headless row rewritten. *The agent review pass* is the
new mechanism in full. *Components*, *Assumptions* and *Tradeoffs* are the
reference sections, marking what is inherited, modified or new.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_agent_brief, component_agent_instructions, component_completion_policy, component_workflow_seam, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary, component_gates, component_adoption_ledger, component_agent_review_pass] -->
## Architecture

### Concepts

**Test unit and id.** A unit is a test file, a member of a file
(`<path>#<member>`) or a variant on a declared axis (`<unit>@<variant>`).
Unchanged.

**Edge.** A `testmap:covers <source>` line, stamped `@<date>/<blob10>` with
the source's git blob digest at confirmation. The digest is the staleness
key. Unchanged.

**Seeded, adopted, reviewed — and who accepted.** A machine-proposed edge
passes through up to three states. *Seeded* rows select and claim nothing.
*Adopted* rows are stamped edges accepted as a whole evidence class; their
`adopted.yaml` row now records **`by:`** — `human:<email>` or
`agent:<agent-string>` — beside the origins. *Reviewed* edges are stamped
edges a named person confirmed pair by pair. **New:** a row adopted from a
reading origin is an adopted row like any other; the `by:` field and the
`agent:*` origin are what keep it distinct from a human class acceptance.

**Rule, measurement, reading, heuristic.** The origin table is partitioned
into four classes by *what kind of fact produced the row*: a **rule**
(`static:package`: deterministic from the language), a **measurement**
(`coverage`: the test ran and the source's lines executed), a **reading**
(`agent:review`, `agent:author`: something read the test body and answered
the verify-or-drive question) and a **heuristic** (everything else). The
autonomous adoption floor is stated in these terms.

**Verdict.** The unit of an agent reading: `verifies | drives | unsure` on
one `(test, source)` pair, with a rationale, the reader's agent-string, the
run id and the digest of the packet it read. Verdicts enter the engine
through one intake (`onboard adopt --agent-verdicts -`), whatever site
produced them.

**Mode and policy.** `ait test` runs in interactive, completion or advisory
mode. The completion policy is `full`, `selected` or **`auto`**. Under
`auto` the engine decides per run: the selection when `readiness` is
`ADMISSIBLE` and no cadence trigger fires; the whole registry otherwise, with
the reason printed.

**Cadence.** `completion.full_run_every` — `{tasks: N, selection_ratio_above:
R, days: D}`; any trigger fires a full completion run under `auto`, which is
what keeps scoring alive without a person scheduling anything.

### The process boundary

Parse, walk, match, digest, schedule, seed, adopt, review-packet assembly
and verdict intake happen in Go. Reading a test body and answering
verifies-or-drives is an **agent** act, performed in a skill; the engine
never calls a model. The gate ledger, task files, profile files,
`project_config.yaml`, `gates.yaml`, agent-instructions files and the shell
environment stay bash and skill prose. Concretely:

- The engine never writes `aitasks/`, `aiplans/`, `.aitask-data/`, a gate
  ledger, `project_config.yaml`, `gates.yaml`, a profile or `CLAUDE.md`,
  never invokes an `aitask_*.sh` script, and **never launches a code agent**.
- The reading happens in three places, all agent sessions: the
  `testmap_fresh` procedure gate (the task's touched test files), the
  pre-review Affected Tests procedure (the task's own new pairs) and the
  `aitask-testmap-review` skill (bulk, during onboarding or on demand).
- No site uses headless print mode by default. Bulk review runs as an
  interactive skill launch (`ait skillrun testmap-review`) or inside the
  onboarding task's session; `ait codeagent testmap-review --headless` is
  the explicit opt-in, mirroring `batch-review`, because the framework's
  shell conventions forbid `claude -p` without one.

### Process map (additions in bold)

```
./ait test [...]                                   agent · human · tests_pass verifier · pre-review procedure (--advisory)
 └─ .aitask-scripts/aitask_test.sh                 bash front: MODE / TASK / INTAKE / POLICY / fallback / advisory
      │  POLICY completion: config.yaml completion.mode ∈ {full, selected, **auto**}; auto → readiness + **cadence** → full | selected, reason printed
      └─ .aitask-scripts/aitask_testmap.sh          the shim
           └─ ait-testmap test … | select | run | brief | onboard … | readiness | costs … | **annotate --author**
                internal/registry       six tables + seeds + adopted (rows now carry **by:** / run / rationale / packet_sha)
                internal/seed           origins static:{package,invocation,import} · coverage · **agent:review · agent:author** · observed · convention · plan · prose · cochange
                internal/onboard        detect · inventory · seed · **review** · classify · adopt (**--agent-verdicts**) · reject · scaffold · status · finish
                internal/feedback       score (**+ rejection revocation**) · attribute · readiness (**+ agent criteria**)
                internal/cost           ledger · **costs/policy.yaml** (last full run, tasks since, cadence state)
                internal/brief          --howto (**POLICY:auto|next full in <n> tasks**)

.claude/skills/aitask-gate-testmap-fresh/          in-gate seeds step: **autonomous → the agent's verdicts are the adoption**
.claude/skills/task-workflow/affected-tests.md     autonomous branch: **annotate --author** for the task's own pairs
.claude/skills/aitask-testmap-review/              **NEW** profile-aware skill: packets in, verdicts out, batch of 20, resumable
.claude/skills/aitask-testmap-onboard/             adopt phase gains the **review** sub-phase; headless completes level 1
.aitask-scripts/aitask_codeagent.sh                **testmap-review** operation (interactive; --headless opt-in as batch-review)
seed/models_<agent>.json                           **verified.testmap-review** score per model (the existing per-operation table)
```

### The registry directory (additions)

```
aitestmap/
  config.yaml            + completion: {mode: full|selected|auto, full_run_every: {tasks, selection_ratio_above, days}, …}
                         + agent_review: {enabled, accept_min, batch, packet_lines, max_pairs_per_run, rejections_revocable}
                         + readiness: {…, min_full_runs_since_map_change, max_revoked_rejections}
  onboard.yaml           phases gain `review: {status, at, by, counts{reviewed, adopted, rejected, unsure}}`;
                         rejections[] rows gain `by:` and `revocable:`; calibration[] rows
  registry/adopted.yaml  rows {test, source, origin[], confidence, adopted_at, task, by, run?, rationale?, packet_sha?}
  costs/policy.yaml      {last_full_run: {run_id, at, task, sha}, selected_since_full: n, approved_by: {who, at, mode, statement}}
```

```yaml
completion:
  mode: auto                     # full | selected | auto — auto: the engine flips when readiness is ADMISSIBLE
  full_run_every:                # any trigger → this completion run is full (POLICY:auto|full|cadence:<trigger>)
    tasks: 5                     # at most N selected completion runs between full runs
    selection_ratio_above: 0.60  # a selection costing ≥ 60 % of the full p95 saves little — run full and score
    days: 7                      # wall-clock ceiling on the gap between full runs
  deferred: run
  on_empty_selection: skip
  engine_absent: error
agent_review:
  enabled: true                  # false → agent:* origins are never written; the baseline's human-only adoption
  accept_min: 0.85               # the class threshold agent-backed rows must clear (noisy-OR)
  batch: 20                      # pairs per review packet
  packet_lines: 120              # ceiling on REVIEW_TEST lines per pair
  max_pairs_per_run: 400         # a bulk review stops here and records the phase as partial
  rejections_revocable: true     # a scored miss re-seeds an agent-rejected pair
readiness:
  min_scored_full_runs: 20
  max_false_negatives: 0
  require_opaque_proofs: true
  min_full_runs_since_map_change: 3   # bulk adoption / revocation resets the counter
  max_revoked_rejections: 0           # over the predictions window
```

### Design decisions (rewritten where the mandate touches them)

1. **Three adoption states, not two.** Unchanged.

2. **Autonomous adoption needs a rule, a measurement or a reading — never a
   heuristic alone.** The act that turns evidence into a claim needs a
   *reader of the test body*, and a reader may be a person or an agent. The
   rejected alternative — "only a person" — was a proxy for "only something
   that read the test", and it left every headless repository at level 0
   forever. A headless profile may therefore adopt `static:package` (rule),
   `coverage` (measurement), and any pair carrying `agent:review` or
   `agent:author` (reading) whose noisy-OR clears `accept_min`; it may never
   adopt `static:invocation`, `static:import`, `convention`, `cochange`,
   `plan` or `prose` without a reading on top. The reading is recorded with
   `by:`, run, rationale and packet digest, and is displayed as
   `adopted(… by agent:<string>)` so it can never be mistaken for a human
   class acceptance.

3. **One origin table, co-change capped.** Unchanged; two rows added.

4–9. Unchanged (levels × phases; the first full run is the level-0 gate;
`bootstrap_until`; one verb, two layers; advisory is a mode; the loop is a
paragraph).

10. **One completion gate under a committed policy, and the policy may
    self-approve.** `tests_pass` runs `./ait test --gate`; `completion.mode`
    decides what that is. `full` and `selected` keep their baseline
    meaning. `auto` lets the engine flip per run — the selection when
    `readiness` is `ADMISSIBLE` and no cadence trigger fires, the whole
    registry otherwise — and records `approved_by: {who:
    engine:readiness@<run-id>, mode: auto}`. The rejected alternative, a
    human flip, is kept as `selected` for a project that wants it; the
    rejected alternative to the cadence — trusting the demotion criteria
    alone — was rejected because scoring only happens on full runs, and a
    policy that never runs full can never demote itself.

11–13. Unchanged (comment lines only; `verify_build` asked about; task
resolution implicit).

14. **A wrong "verifies" over-selects; a wrong "drives" under-selects; only
    the second is revocable by evidence.** Agent rejections carry
    `revocable: true`; a scored miss on a rejected pair re-seeds it and
    counts toward `max_revoked_rejections`. Human rejections are never
    revoked, only contradicted with a printed `REJECTION_CONTRADICTED:` line.
    The rejected alternative — treating all rejections alike — would either
    let evidence overrule a person or let an agent's error persist silently.

15. **Kind changes and axes stay human.** A kind changes staleness
    semantics, not selection breadth, and no run evidence checks it; an axis
    is a declaration of the project's product space. Headless profiles
    *propose* kinds (`kind_proposals[]` in `onboard.yaml`) and never apply
    them.

16. **The engine never calls a model.** The reading is a skill act. Bulk
    review is an interactive skill launch by default; headless print mode
    is an explicit opt-in flag on `ait codeagent`, as the framework already
    requires for `batch-review`.
<!-- /section: architecture -->

<!-- section: data_flow [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_completion_policy, component_workflow_integration, component_workflow_seam, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_registry_loader, component_staleness_tool, component_agent_review_pass] -->
## Data Flow

### A task in steady state (autonomous profile)

```
Step 7  edit source ──▶ ./ait test                      MODE:interactive TASK:<id> INTAKE:change-surface
                        ──▶ select (edges ∪ adopted ∪ seeds ∪ deps ∪ rules ∪ axes ∪ test-dep) ──▶ run ──▶ prediction record
        before Step 8 ──▶ ./ait test --advisory --task <id> ──▶ VERDICT:/REASON:/LOG:
                        UNMAPPED_SOURCE:<src>  ──▶ the agent names the test it wrote for it
                                               ──▶ ait testmap annotate --author <test> <src> --task <id> --by <agent-string>
                                               ──▶ stamped covers line + adopted.yaml {origin:[agent:author], by, run}
                                               ──▶ no test known → attribute --propose (seeded, observed) as before
                        UNANNOTATED_TEST:<t>   ──▶ annotate --suggest <t> ──▶ the agent confirms rows → --author
Step 8  testmap_fresh ──▶ stale --task; then seeds on touched test files:
                        attended  → agent pre-fills verifies/drives/unsure per row; human confirms (by: human) or "trust batch" (by: agent)
                        autonomous → the agent's verdicts ARE the adoption: onboard adopt --agent-verdicts - --by <agent-string> --run <run>
Step 9  ait gates run ──▶ testmap_check ──▶ tests_pass = ./ait test --gate
                        POLICY:auto → readiness ADMISSIBLE? cadence fired? → selected | full (reason printed)
        full run ──▶ score ──▶ PREDICTION_MISSED:<id> ──▶ attribute --propose
                             ──▶ pair in rejections[] by agent:* ──▶ AGENT_REJECTION_REVOKED:<test>|<source> ──▶ re-seeded
```

### A completion run under `auto`

```
tests_pass → export AIT_GATE_TASK_ID / AIT_GATE_RUN_ID → ./ait test --gate
   POLICY:auto
     readiness → NOT_YET|<criterion>            → POLICY:auto|full|not_yet:<criterion>       → run --all
     readiness → ADMISSIBLE, first time          → costs/policy.yaml approved_by {engine:readiness@<run>, mode: auto}
     cadence: selected_since_full ≥ tasks        → POLICY:auto|full|cadence:tasks             → run --all, selected_since_full := 0
     cadence: est_s / full_p95 ≥ ratio           → POLICY:auto|full|cadence:selection_ratio  → run --all
     cadence: now − last_full_run ≥ days         → POLICY:auto|full|cadence:days             → run --all
     otherwise                                   → POLICY:auto|selected|next_full_in:<n>     → the task selection, deferred rows run
   → every full run scores the newest prediction; a miss demotes exactly as before (POLICY_DEMOTED:auto->full|max_false_negatives)
   → ledger block result="MODE:selected|14 units|policy:auto|next_full_in:3"
```

### Headless onboarding, level 0 → level 1 with no person

```
/aitask-testmap-onboard (remote profile)
   level 0   detect --write · inventory · seed --apply · waivers (rules + expiring) · enable · Step-9 tests_pass = first full run   (as baseline)
   level 1   adopt --class static:package --accept-min 1.0              rule        → aitasks_go: 55 files, done
             adopt --class coverage                                      measurement → any repo with a coverage import
             review phase:                                               reading
               loop  onboard review --next 20 --json > packet
                     the skill reads the packet, answers per pair
                     onboard adopt --agent-verdicts - --by claudecode/opus5 --run onboard-<run>
                     ADOPT_SUMMARY:1|<edges>|<files>|<skipped>  REJECTED:<n>  UNSURE:<n>
               until the queue is empty, max_pairs_per_run is reached, or the class is exhausted
             onboard.yaml phases.review {reviewed, adopted, rejected, unsure}; chore: Onboard testmap — review (t<id>)
             calibrate: onboard review --calibrate 50 (against coverage facts where present, else skipped and printed)
   level 2   classify → CLASSIFY: rows recorded as kind_proposals[]; nothing applied          (human)
   level 3   not entered                                                                        (human)
   policy    completion.mode: auto written by detect --write when the profile is headless and agent_review.enabled
```

### Revocation

```
full run (gate- or full- prefixed) → score → PREDICTION_MISSED:tests/test_x.sh
   for each changed source S in the run's change surface:
     (tests/test_x.sh, S) ∈ onboard.yaml rejections[] ?
        by: agent:*  → row removed · re-seeded {origin: [observed, <original origins>], evidence.revoked_from: <run>} · AGENT_REJECTION_REVOKED:<test>|<S>|<run>
        by: human:*  → REJECTION_CONTRADICTED:<test>|<S>|<run> (advisory; the row stays)
   costs/predictions.yaml row gains revoked: [<pairs>]
   readiness: max_revoked_rejections counts rows in the window → NOT_YET until min_full_runs_since_map_change clean runs pass
```

### Reading the map without running anything

```
ait test --howto   → TESTMAP:…|POLICY:auto|next full in 3 tasks|seeds pending 412|adopted 618 (agent 540, human 78)|revoked 0
onboard status     → … AGENT_ADOPTED:<n>  AGENT_REJECTED:<n>  UNSURE:<n>  REVOKED:<n>  CALIBRATION:<agree>/<n>|none
readiness          → READINESS:min_full_runs_since_map_change|met|4   READINESS:max_revoked_rejections|met|0   READINESS:approved_by|met|engine:readiness@gate-…
```
<!-- /section: data_flow -->

<!-- section: adoption_model [dimensions: component_adoption_ledger, component_seeder, component_onboarding_engine_verbs, component_registry_loader, component_annotation_scanner, component_dependency_scanners, component_agent_review_pass, assumption_seed_sources_measured, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_seeds_select_never_evidence, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only, assumption_agent_reads_verify_vs_drive, assumption_wrong_positive_claim_only_overselects, assumption_agent_rejection_is_revocable] -->
## The Adoption Model

### The idea

A machine can find evidence that a test exercises a source; a *reader of
the test body* can turn that evidence into a claim; the freshness machinery
enforces claims. The baseline made "reader" mean "person". This model makes
it mean "person or agent", records which, and treats the two kinds of agent
error asymmetrically: a wrong claim over-selects and is tolerated the way
seeds are; a wrong rejection under-selects and is revocable by the next full
run.

### The three states, with `by:`

```
                onboard seed --apply · attribute --propose · revocation
   (none) ─────────────────────────────────────────────▶ SEEDED ──────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row, by: human|agent)
                                                            │   onboard adopt --class <origin> [--accept-min]              │
                                                            │   onboard adopt --agent-verdicts - --by agent:<s> --run <r>   │ human re-stamp
                                                            │   annotate --author (agent:author, adopted on write)          ▼
                                                            ├──────────────────────────────────────────────────────▶ REVIEWED (stamp, no provenance row)
                                                            │ onboard reject <test> <source> --reason        (by: human, revocable: false)
                                                            │ VERDICT:<id>|drives                             (by: agent,  revocable: true)
                                                            ▼
                                                        REJECTED (onboard.yaml rejections[] {test, source, by, run, rationale, revocable})
                                                            │ scored miss on the pair, by: agent → AGENT_REJECTION_REVOKED → back to SEEDED
```

Surfaces: `check` prints `SEEDED:<n>` and `ADOPTED:<n>|agent <a>|human <h>`;
`stale --all` the same; `readiness` prints `ADOPTED_UNREVIEWED`, `SEEDED`,
`REVOKED:<n>`; `onboard status` is the one place every ratio lives. The two
load rules (`SEED_SHADOWED`, `ADOPTED_ORPHAN`) are unchanged; a third is
added: a rejection row without `by:` is read as `by: human, revocable:
false` (the baseline's rows, never revoked).

### The autonomous floor

> An autonomous profile may seed everything and may adopt a class only when
> every member of the class carries at least one **rule**, **measurement**
> or **reading** origin and its noisy-OR confidence clears
> `agent_review.accept_min` (default 0.85). A heuristic origin never
> qualifies alone, however high its measured precision.

| class | origin | headless-adoptable | why |
|---|---|---|---|
| rule | `static:package` | yes | deterministic from the language |
| measurement | `coverage` | yes | the source's lines executed under the test |
| reading | `agent:review`, `agent:author` | yes | something read the test body and answered verifies-or-drives |
| heuristic | `static:invocation`, `static:import`, `observed`, `convention`, `plan`, `prose`, `cochange` | **no** — needs a reading on top | the fact is "executes" or "co-occurs", never "verifies" |

`static:invocation` at 0.90 alone therefore stays seeded in a headless
profile — the 398/400 precision measured on aitasks says the test *runs* the
script, which is exactly the gap the baseline named — and becomes adoptable
at 0.99 the moment an agent verdict of `verifies` lands on it. The attended
profile keeps every baseline path (class acceptance with a ten-sample
review, per-row adoption, the in-gate step); in it the agent pre-fills
verdicts and a person confirms.

### The origin table

| origin | class | rule | evidence recorded | confidence |
|---|---|---|---|---|
| `static:package` | rule | a `_test.go` file's subject is its own package | — | **1.00** |
| `coverage` | measurement | per-unit runtime coverage (coverage.py contexts, `go -coverprofile` per `-run`, LCOV with a test column, JaCoCo per-test sessions) | run id | 0.95 |
| **`agent:review`** | reading | an agent read the review packet for the pair and answered `verifies` | `{by: agent:<agent-string>, run, rationale (≤ 2 lines), packet_sha, test_blob, source_blob}` | **0.90** |
| **`agent:author`** | reading | the agent implementing a task named the pair for a test it wrote or a source it introduced, through `annotate --author` | `{by, task, run, rationale}` | **0.90** |
| `static:invocation` | heuristic | a literal repo path the test executes or sources | file:line | 0.90 |
| `static:import` | heuristic | a direct import of a main-root file | file:line | 0.85 |
| `observed` | heuristic | an `attribute --propose` row from a scored miss, or a **revoked agent rejection** | run id | 0.70 |
| `convention` | heuristic | `config.yaml conventions:` patterns | pair | 0.60 |
| `plan` | heuristic | an `aiplans/` file naming both paths | path | 0.50 |
| `prose` | heuristic | a literal path in the header comment | line | 0.30 |
| `cochange` | heuristic | `(test, source)` in ≥ 2 distinct `(t<id>)` groups | task ids | 0.20 + 0.20/group, cap 0.60 |

**Combination.** Noisy-OR as before. `static:invocation + agent:review` =
0.99; `static:import + agent:review` = 0.985; `agent:review` alone = 0.90;
`convention + agent:review` = 0.96; `cochange(cap) + agent:review` = 0.96.
A reading alone clears the threshold because a reading *is* the
verify-or-drive judgement; the static origins beneath it raise the rank and
supply the packet's anchor line. Two `unsure` verdicts on one pair mark it
`REVIEW_HUMAN` and drop it from further agent packets.

**Why 0.90 and not 1.0.** A reading is a judgement, not a rule; 0.90 keeps a
lone agent verdict below `static:package`, above every heuristic, and
exactly where a single static fact plus a reading reaches the top of the
queue. The number is calibratable: `onboard review --calibrate <n>` compares
agent verdicts against the project's coverage facts where a coverage import
exists (measurement as ground truth), else against the human-reviewed rows
and human rejections where those exist, and prints `CALIBRATION:agree
<a>|disagree <d>|<ratio>`. A ratio under 0.90 lowers `agent:review`'s
effective confidence to the measured ratio for that repository (written to
`config.yaml agent_review.measured_confidence`), and under `accept_min` it
disables headless adoption from that origin and says so in `readiness`.

### Where the reading happens

| site | who reads | what | verdict path | provenance |
|---|---|---|---|---|
| `testmap_fresh` in-gate step (Step 8) | the task's agent; a person in attended profiles | seeds on the test files this task touched — the file is open, the diff is in front of the reader | attended: agent pre-fills, human confirms per row (`by: human`) or "trust this batch" (`by: agent`); autonomous: `onboard adopt --agent-verdicts -` | `adopted(<origins>+agent:review <c> by agent:<s>)` |
| pre-review Affected Tests procedure (Step 7) | the task's agent | `UNMAPPED_SOURCE` / `UNANNOTATED_TEST` for the task's own change | `ait testmap annotate --author <test> <source> --task <id>`; no known test → `attribute --propose` | `adopted(agent:author 0.90 by agent:<s>)` |
| `aitask-testmap-review` skill (bulk) | a dedicated skill session | `onboard review --next 20` packets over the seed queue, by class or scope | `onboard adopt --agent-verdicts -` per batch; resumable; `review` phase in `onboard.yaml` | as above, run id `review-<n>` |

### Helpers, kinds, placement, what seeding cannot do

Unchanged from the baseline: helpers are separated by roots and fan-in
before any origin scores; kinds, members and axes are proposed by
`classify` and `scaffold`; adoption writes comment lines only at the fixed
per-language position; a source reached by no origin stays
`UNMAPPED_SOURCE` until a rule, a waiver, a pre-review prompt, a coverage
import — **or an author annotation** — maps it. The agent:author path is
the new thing that closes the same-package gap on thinking_app: the agent
that edits a screen and its test knows the pair even when no import says so.
<!-- /section: adoption_model -->

<!-- section: agent_review_pass [dimensions: component_agent_review_pass, component_onboarding_engine_verbs, component_skill, component_freshness, component_workflow_integration, assumption_agent_reads_verify_vs_drive, assumption_headless_launch_is_explicit_opt_in, assumption_wrong_positive_claim_only_overselects] -->
## The Agent Review Pass

### The idea

The engine assembles a bounded, digest-stamped **packet** per seeded pair;
an agent reads packets and returns **verdicts**; the engine turns verdicts
into adopted rows, rejections or `unsure` marks through the same rewriter
and ledger every other adoption uses. The engine never calls a model; the
skill never writes a test file. A packet is what the agent saw, and its
digest is stored beside the verdict so a later reader can reproduce the
judgement's inputs.

### The packet

`ait testmap onboard review [--next N] [--class <origin>] [--scope <glob>]
[--ids <csv>] [--json] [--calibrate <n>]`:

```
REVIEW_PAIR:<id>|<test>[#member]|<source>|<origins>|<confidence>|<unsure_count>
REVIEW_ANCHOR:<id>|<file:line>                 the static fact's line (invocation / import), when one exists
REVIEW_TEST:<id>|<line>|<flag>|<text>          the anchor ±20 lines, then every line containing an assertion call
                                               (assert_eq / assert_contains / assert / expect / require / t.Fatal* /
                                               assertEquals / shouldBe / grep -q on captured output) flagged `!`;
                                               ceiling agent_review.packet_lines per pair
REVIEW_SOURCE:<id>|<symbol>|<kind>             the source's declared symbols (bash: function names + top-level verbs;
                                               Python: def/class; Go: exported idents; Kotlin: declarations) — never the body
REVIEW_PROSE:<id>|<line>                       the test's header comment / `# Covers:` lines
REVIEW_MEMBER:<id>|<block>                     for a member seed, the testmap:unit block's own lines
REVIEW_END:<id>|<packet_sha>
```

The packet deliberately excludes the source body: the question is whether
the *test* checks something the source does, and the source's symbol list is
enough to see whether the flagged assertion lines name its behaviour. The
`--json` form is one object per pair with the same fields. `--calibrate <n>`
samples `n` pairs with a ground truth (coverage rows, reviewed edges, human
rejections) and marks them so the intake compares instead of adopting.

### The verdict

Fed to `ait testmap onboard adopt --agent-verdicts - --by <agent-string>
--run <run-id>`, one line per pair:

```
VERDICT:<id>|verifies|<rationale ≤ 160 chars>
VERDICT:<id>|drives|<rationale>
VERDICT:<id>|unsure|<rationale>
```

| verdict | effect | printed |
|---|---|---|
| `verifies` | `agent:review` added to the row's origins; noisy-OR recomputed; ≥ `accept_min` → adopted through the rewriter with an `adopted.yaml` row `{…, by: agent:<s>, run, rationale, packet_sha, test_blob, source_blob}`; below → stays seeded with the origin recorded | `WROTE:<file>` / `ADOPT_SUMMARY:` |
| `drives` | row leaves `seeded.yaml`; `onboard.yaml rejections[] += {test, source, by: agent:<s>, run, rationale, revocable: true}` | `REJECTED:<test>|<source>|agent` |
| `unsure` | `evidence.agent.unsure += 1`; at 2 the pair is `REVIEW_HUMAN` and leaves the agent queue | `UNSURE:<test>|<source>|<n>` |
| any, packet_sha ≠ current | the pair's files changed since the packet was cut | `VERDICT_STALE:<id>` — ignored, re-packeted next batch |
| `--by` not an agent-string | refused: `parse_agent_string` must accept it; humans use the per-row verbs | exit 64 |
| `--calibrate` run | no writes; `CALIBRATION:agree <a>|disagree <d>|<ratio>` appended to `onboard.yaml calibration[]` | as printed |

`--by` is validated against `lib/agent_string.sh`'s grammar
(`<agent>/<model>`, agents `claudecode|codex|opencode`), so a `by:` value is
always resolvable to a model row in `models_<agent>.json`; the operation
`testmap-review` is added to each model's `verified:` table, the existing
per-operation score the framework keeps for `batch-review`, `pick`,
`explain`, `work-report` and `trail`.

### The skill `aitask-testmap-review`

`.claude/skills/aitask-testmap-review/` as a profile-aware stub +
`SKILL.md.j2` (resolver key `testmap-review`), one procedure file
`review-batch.md`. Flow: preconditions (`ait testmap version`; `aitestmap/`
present; `agent_review.enabled`) → `onboard review --next <batch> [--class]
[--scope]` → for each pair, read the packet and decide by the rule *"a test
verifies a source when a flagged assertion line checks an output, a state or
an exit status that the source's symbols produce; it only drives it when the
source appears solely in setup, teardown or as a path argument whose result
is never checked"* → emit the `VERDICT:` lines → `onboard adopt
--agent-verdicts - --by <agent-string> --run review-<n>` → repeat until the
queue is empty, `max_pairs_per_run` is reached, or (attended) the user stops
→ commit the rewritten files under `chore: Onboard testmap — review
(t<id>)` when running inside an onboarding task, else print the commit
lines. Attended profile: the agent shows each batch's verdicts as a table
and the user confirms, edits or trusts the batch; autonomous profile: no
prompts. The skill ships Claude Code first; Codex and OpenCode ports are
follow-up tasks; goldens under `tests/golden/skills/aitask-testmap-review/`.

**Launch surfaces.** Inside an onboarding task the skill is a sub-procedure
of the `adopt` phase (`review.md`). On demand: `ait skillrun testmap-review
[--profile <p>] [-- --class static:invocation]`, an interactive launch as
every skill run is. `ait codeagent testmap-review` mirrors `batch-review`:
interactive by default, `--print` only under `--headless`, because the
framework bills headless print mode at a higher rate and its shell
conventions forbid `claude -p` without an explicit opt-in. No engine code
path, gate or hook launches an agent.

### The in-gate site (Step 8)

`aitask-gate-testmap-fresh`'s seeds step becomes: for each `COMMITTED:` /
`TASK:` test file with rows in `seeded.yaml`, run `onboard review --ids
<those rows>` and read the packets — the agent already has the diff open.
Attended: the agent's verdict is pre-filled on each row; the user confirms
(`by: human`), overrides, or answers "trust this batch" once (`by: agent`).
Autonomous: `onboard adopt --agent-verdicts - --by <agent-string> --run
<gate-run-id>`. Either way the stamps ride the `(t<id>)` commit as before.

### The authoring site (Step 7)

The pre-review Affected Tests procedure's `skip · no_selection` branch in an
autonomous profile: for each `UNMAPPED_SOURCE:<src>`, the agent names the
test unit it wrote or edited for that source in this task (it must be in the
change surface or reach `<src>` through the static closure — `annotate
--author` refuses `AUTHOR_REFUSED:<test>|not-in-task` otherwise, keeping a
bulk-claim from riding the author path) and runs `ait testmap annotate
--author <test> <src> --task <id> --by <agent-string>`; the engine writes the
stamped line through the rewriter and an `adopted.yaml` row with origin
`[agent:author]`. No known test → `attribute --propose` as in the baseline.
`UNANNOTATED_TEST:<t>` → `annotate --suggest <t>` then `--author` on the
rows the agent confirms from its own knowledge of what it wrote. Attended
profiles keep the baseline's *Annotate now / Propose / Continue* prompt with
the agent's proposed pairs pre-filled.

### Budgets

Packet assembly is static (no runner, no model): `onboard review --next 20`
< 300 ms warm on the aitasks shape. A bulk pass over aitasks' ~720 static
seeds is 36 packets; at `packet_lines: 120` a packet is ≤ 2,400 lines of test
excerpt plus symbol lists — bounded, and the reason the source body is
excluded. `annotate --author` is one rewriter call.
<!-- /section: agent_review_pass -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_onboarding_engine_verbs, component_seeder, component_agent_review_pass, requirements_zero_config_onboarding, requirements_onboarding_existing_tests, requirements_incremental_adoption, requirements_autonomous_loop_closure, assumption_test_tools_detectable, assumption_onboarding_is_a_task, assumption_full_run_expressible_per_repo] -->
## Onboarding: Levels × Phases

### Levels and phases

| level | phases | what `onboard` writes | who accepts (attended) | who accepts (headless) |
|---|---|---|---|---|
| **0 — runners and universe** | detect → inventory → seed → waivers → enable → full_run | as baseline; `detect --write` sets `completion.mode: auto` when the profile is headless and `agent_review.enabled` | the runner table, `UNREGISTERED`, the config table | nothing to ask — as baseline |
| **1 — edges** | adopt (rule → measurement → **review**) then incrementally in `testmap_fresh` | stamped `testmap:covers` blocks; `adopted.yaml` rows with `by:`; `rejections[]` with `by:`; `phases.review` counts; `calibration[]` | per class with the agent's verdicts pre-filled, or per row | **the agent**: `static:package` and `coverage` by class; every other class through the review loop until the queue is empty or `max_pairs_per_run` |
| **2 — kinds** | classify → `scan --apply` | as baseline | per kind, individually | **proposes only**: `CLASSIFY:` rows land in `onboard.yaml kind_proposals[]`; nothing applied; `readiness` prints `KIND_PROPOSALS:<n>` |
| **3 — product** | scaffold → `annotate --from-body` | as baseline | the maintainer | not entered |
| **finish** | a phase of the last level task | `require_stamp: true`; `check --strict`; `bootstrap_until` shortened | `onboard status` green | `onboard status` green **and** `REVOKED:0` in the window **and** `REVIEW_HUMAN:0` — the finish is headless-safe when the map has no pair the agent could not judge |

### The headless (`remote`) profile — rewritten

Level 0 in full; level 1 in full by rule, measurement and reading (no
prompts; the level proposal is printed; the review loop runs to the
`max_pairs_per_run` budget and records a partial phase it re-enters on the
next run); level 2 proposes kinds and applies none; level 3 not entered;
the policy is `auto`, so no flip is written by anyone — the engine flips per
run when `readiness` is `ADMISSIBLE`. A headless repository therefore
reaches "the completion gate runs the selection" with no person having
typed anything, and the things that remain human — kinds, axes, the
`REVIEW_HUMAN` pairs — are listed by `onboard status` rather than assumed
done.

### Detection, per target repository — level 1 headless outcome

| repository | rule | measurement | reading | level 1 headless result |
|---|---|---|---|---|
| **aitasks** | — | opt-in (`coverage.py` contexts for the 320 Python tests) | 398 bash `static:invocation` + 320 Python `static:import` seeds through the review loop (36 packets) | ~718 adopted at 0.99 / 0.985; the 2 fixture-only tests stay seeded; conventions corroborate |
| **thinking_app** | — | JaCoCo per-test sessions when enabled (0.95, adoptable by class) | 139 `static:import` files through review; same-package pairs reach the map through `agent:author` as tasks touch them | level 1 partial by construction (the same-package gap), stated by `onboard status`; `verify-active` stays the completion gate until `auto` finds `ADMISSIBLE` |
| **thinking_backend** | — | opt-in | 40 units through review (2 packets) | full |
| **aitasks_go** | `static:package` 1.0 over 55 `_test.go` files | `go -coverprofile` per `-run` | none needed | full, as in the baseline |
| **aitasks_mobile** | — | JaCoCo where the Gradle modules enable it | 36 + 1 unit classes through review; the 3 device classes stay `device` kind (a kind, not adopted) | full for unit kinds |

Everything else in this section — invocation and task shape, preconditions,
survey, the level task, the after-level-0 procedure, `--no-task`, the
`--policy selected` re-entry (still available for a project that wants a
human flip) — is unchanged from the baseline.
<!-- /section: onboarding -->

<!-- section: run_surface [dimensions: component_test_entrypoint, component_test_front_verb, component_agent_brief, component_agent_instructions, requirements_zero_config_entrypoint, requirements_agent_run_surface, requirements_agent_instructions_seeded, assumption_task_resolvable_from_session, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_instruction_block_is_read, assumption_change_surface_is_intake] -->
## The Run Surface

Unchanged from the baseline in forms, resolution order, output and exit
contract, the two environment variables and the generic instructions
section, with these additions:

- **`POLICY:` line under `auto`.** `POLICY:auto|selected|next_full_in:<n>` or
  `POLICY:auto|full|cadence:<tasks|selection_ratio|days>` or
  `POLICY:auto|full|not_yet:<criterion>`; the gate-run ledger block carries
  the same in `result=`.
- **`--howto`** gains `next full in <n> tasks` on the `TESTMAP:` line, an
  `agent <a>, human <h>` split on the adopted count, `REVOKED:<n>` when
  non-zero, and one `AGENT_REVIEW:enabled|<measured_confidence>|<calibration>`
  line; `FULL_GATE:` names the cadence (`every 5 tasks / ≥ 60 % / 7 d`).
- **`ait testmap annotate --author <test> <source> --task <id> --by
  <agent-string>`** — the one new maintainer-surface form, used by the
  pre-review procedure; refuses `AUTHOR_REFUSED:not-in-task` when the test
  is neither in the task's change surface nor reaches the source through the
  static closure.
- The `## Running Tests` section is **unchanged** (fourteen lines, no agent
  named); the author path is taught by the procedure that uses it, not by
  the seed, because it is a workflow act rather than a run form.

`ait test --howto` for aitasks after headless level 1, on this host class:

```
TESTMAP:onboarded|since 2026-09-20|LEVEL:1|POLICY:auto|next full in 3 tasks|seeds pending 14|adopted 718 (agent 718, human 0)
RUNNER:bash-file|unit|400|bash <file>|repo-git-index
RUNNER:pytest|unit|320|run_all_python_tests.sh lanes; 4 serial|repo-git-index
FULL_GATE:ait test --all|p95 412s|every 5 tasks / ≥ 60 % / 7 d|tests_pass timeout 1236s
GATE:testmap_fresh (procedure, before commit) -> testmap_check -> tests_pass = ./ait test --gate (auto: selected, 14 units now)
AGENT_REVIEW:enabled|0.90|calibration 47/50 (coverage)
VERBS:./ait test | ./ait test <path>... | ./ait test --all | ./ait test --howto
NEW_TEST:./ait testmap annotate --suggest <path>
```
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_workflow_integration, component_gates, component_completion_policy, component_qa_integration, component_agent_review_pass, requirements_workflow_seam, requirements_workflow_seam_is_data, requirements_gate_enforcement, assumption_gate_exit_contract_reused] -->
## The Workflow Seam and the One Completion Gate

### The idea

Still no new workflow and no new gate. The seam is the baseline's data plus
one procedure, with the two autonomous branches that previously only
*proposed* now *acting* through engine verbs, and one new skill for bulk
review. Every seam degrades to a printed skip where the engine or the
registry is absent.

### The concrete edits (delta from the baseline)

| where | change | kind |
|---|---|---|
| `task-workflow/affected-tests.md` | `skip · no_selection`, autonomous branch: for each `UNMAPPED_SOURCE` the agent names its own test → `ait testmap annotate --author …`; none known → `attribute --propose` (baseline). `UNANNOTATED_TEST` → `--suggest` then `--author` on confirmed rows. Attended: the baseline prompt with the agent's pairs pre-filled | procedure |
| `aitask-gate-testmap-fresh` | the seeds step reads packets (`onboard review --ids`); attended: pre-filled verdicts, confirm / override / trust-batch; autonomous: `onboard adopt --agent-verdicts -` | procedure gate |
| `aitask-testmap-review/` | **new** profile-aware skill; `review-batch.md`; goldens; Codex / OpenCode ports as follow-ups | skill |
| `aitask-testmap-onboard/adopt.md` | rule → measurement → review sub-phase (`review.md`); headless row rewritten; `finish.md` adds the `REVOKED:0` / `REVIEW_HUMAN:0` conditions | procedure |
| `aitask_codeagent.sh` | operation `testmap-review` (`/aitask-testmap-review`), interactive by default, `--print` under `--headless`; `list-models` shows `verified.testmap-review` | code |
| `seed/models_{claudecode,codex,opencode}.json` | `verified.testmap-review` key per model (0 until measured); `aitask-add-model` seeds it | data |
| `aitestmap/config.yaml` (written by `detect --write`) | `completion.mode: auto` in headless profiles; `full_run_every`; `agent_review`; `readiness` block | data |
| `ait test --gate` (`aitask_test.sh` + `test` composite) | `auto` resolution: readiness + cadence → `POLICY:` line; writes `costs/policy.yaml` | code |
| `internal/feedback score` | revocation of `by: agent` rejections on a miss; `REJECTION_CONTRADICTED:` for human ones; `revoked:` in the predictions row | code |
| `internal/feedback readiness` | criteria `min_full_runs_since_map_change`, `max_revoked_rejections`; `approved_by` satisfied by `engine:readiness@<run>` under `auto`; `KIND_PROPOSALS:`, `REVIEW_HUMAN:` lines | code |
| `internal/onboard` | `review` verb; `adopt --agent-verdicts`; `review` phase; `rejections[].by/revocable`; `kind_proposals[]`; `calibration[]` | code |
| `internal/annot` | `annotate --author` (a rewriter caller with the not-in-task refusal) | code |
| `internal/registry` | `adopted.yaml` rows `by, run, rationale, packet_sha, test_blob, source_blob`; rejection load rule (absent `by:` = human) | code |
| `internal/brief` | the `--howto` additions | code |
| `profiles.md` | no new profile key — `agent_review.enabled` is project config, not a profile choice, because the map's provenance must not depend on who ran the task | doc |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a seed origin" gains the class column (rule / measurement / reading / heuristic) and the autonomous-floor rule | doc |
| tests | `test_ait_test_entrypoint.sh` gains the `auto` matrix (ADMISSIBLE × cadence triggers × NOT_YET); engine tests for packet assembly per language, every verdict branch, `VERDICT_STALE`, `--by` refusal, calibration, revocation on a synthetic miss, the not-in-task refusal; `test_testmap_onboard_ledger.sh` covers the partial `review` phase re-entry; goldens for the two skills and the rewritten gate skill; `test_codeagent.sh` pins `testmap-review` interactive-by-default | test |

Everything else in the baseline table stands: Step 7's paragraph, the
pre-review procedure's other branches, the `affected_tests` key, Step 9's
verify block, `run_project_command_key()`'s new rows, `gates_reference.yaml`
(`testmap_fresh`, `testmap_check → tests_pass`; no selection gate),
`aitask-qa`'s registry-first branches (which now show `Covered (adopted by
agent)` where the row says so), `report_testmap_state()`, the dispatcher
arm, the five touchpoints.

### Gates

Unchanged in `gates_reference.yaml`. `run_gate_admission` under `auto` is
`{who: engine:readiness@<run-id>, at, mode: auto, statement: <the readiness
lines at the flip>}` written to `costs/policy.yaml`, not `config.yaml`, so
the committed policy file stays a human-authored declaration and the
engine's approvals live beside the other engine-written ledgers.

### Completion policy

`full` and `selected` as the baseline. `auto`: the flip is the engine's,
per run, loud (`POLICY:auto|…` on every completion run); the demotion is
automatic as before; the cadence guarantees full runs keep happening; the
policy can only fail toward running more. thinking_app's rule — full
`verify-active` until admissible — is preserved by `auto` exactly as by
`full` until `readiness` says otherwise, and its cadence would be the
project's to set (a 1,180 s full run every 5 tasks is the price of the
selection on the other 4).
<!-- /section: workflow_seam -->

<!-- section: components [dimensions: component_*] -->
## Components

Grouped by layer; each marked *(inherited)*, *(modified)* or *(new)*. An
inherited component is summarised; its full text is in the node metadata
and is unchanged from the baseline.

**Engine and packaging**

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(modified: never launches an agent)*

`engine/cmd/ait-testmap` with the baseline's packages plus `internal/seed`,
`internal/onboard`, `internal/brief`; Go 1.26, `CGO_ENABLED=0`, the three
dependencies, line-protocol stdout. Boundary additions: the engine never
launches a code agent, never reads `models_<agent>.json` beyond validating
an agent-string's grammar, and never decides a verdict — `onboard review`
assembles packets and `onboard adopt --agent-verdicts` consumes lines. One
fixture per verdict branch and one per packet language join the fixture
set.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(modified: two verbs, two budgets)*

Verb table gains `onboard review` and `annotate --author`; budgets: `onboard
review --next 20` < 300 ms warm (static packet assembly, no exec); `annotate
--author` is one rewriter call. Contract stays 1; `adopted.yaml` rows with
`by:` and `rejections[]` with `by:` are additive fields an older engine
ignores.
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited)*

`engine/build.sh`, the release `engine` job, `engine-check.yml`, the shim's
strict handshake and the platform matrix are unchanged.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade and state report *(inherited)*

`install_engine_binary()`, `report_testmap_state()` and the `TESTMAP:` line
are unchanged.
<!-- /section: component_engine_packaging -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited)*

`lib/aitasks_home.sh`, `$AITASKS_HOME`, unchanged.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(inherited)*

`ait engine home [--migrate]`, unchanged.
<!-- /section: component_framework_home -->

**The map: registry, annotations, scanners, axes**

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(modified: provenance fields)*

As the baseline, plus: `adopted.yaml` rows are `{test, source, origin[],
confidence, adopted_at, task, by: human:<email>|agent:<agent-string>, run?,
rationale?, packet_sha?, test_blob?, source_blob?}`; `onboard.yaml
rejections[]` rows are `{test, source, reason|rationale, by, run?, revocable}`
with the load rule that an absent `by:` reads as `human, revocable: false`;
`kind_proposals[]` and `calibration[]` are read for `status` and
`readiness`. Write routing adds: `adopt --agent-verdicts` → `seeded.yaml`
(rows removed) + `adopted.yaml` + test files, or `onboard.yaml rejections[]`;
`annotate --author` → the test file + `adopted.yaml`; `score` revocation →
`onboard.yaml` (row removed) + `seeded.yaml` (row re-added). `config.yaml`
gains `completion.full_run_every`, `agent_review`, `readiness`. Golden tests
pin the `by:` merge and the absent-`by:` rule.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(modified: one more caller)*

Grammar v3 and the line-targeted rewriter are unchanged. `annotate --author
<test> <source> --task <id> --by <agent-string>` is a new caller: it checks
the test is in the task's change surface or reaches the source through the
static closure (`AUTHOR_REFUSED:<test>|not-in-task` otherwise), inserts the
stamped `testmap:covers` line at the fixed per-language position, and writes
the `adopted.yaml` row with origin `[agent:author]`. A member seed lands in
the `testmap:unit` block as before.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(modified: packet facts)*

The scanners expose two more read-only facts to `internal/onboard review`:
the anchor line of a static fact (file:line of the invocation or import)
and a source's declared symbols (bash function names and top-level verbs,
Python `def`/`class`, Go exported identifiers, Kotlin declarations) from the
same blob-keyed cache — no new scan, no source bodies in packets.
<!-- /section: component_dependency_scanners -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited)*

`axes.yaml`, the facet join, `--axis`, unchanged; axis declaration stays a
human act (design decision 15).
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited)*

`ait testmap axes --list|--check|--explain`, unchanged.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited)*

The runner's `list` as the enumeration surface, `UNCOVERED_VALUE`,
`UNMAPPED_ARTIFACT`, unchanged.
<!-- /section: component_cell_enumeration -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(modified: headless proposes kinds)*

As the baseline; `classify --suggest`'s `CLASSIFY:` rows in a headless
profile are written to `onboard.yaml kind_proposals[]` by `onboard classify
--propose` and never applied; `readiness` prints `KIND_PROPOSALS:<n>` so a
later attended session finds them.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling and staleness policy *(inherited)*

Kinds, `broad_after_unit`, `STALE_AREA`, `device_policy`, unchanged.
<!-- /section: component_broad_test_scopes -->

**Freshness and evidence**

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(modified: the in-gate step acts)*

Stamps are written by `verify`, `annotate` (including `--author`), `stale
--confirm*` and `onboard adopt` (including `--agent-verdicts`). The
`testmap_fresh` procedure gate's seeds step now reads packets for the
touched test files: attended, the agent pre-fills verdicts and the person
confirms per row or trusts the batch; autonomous, the agent's verdicts are
the adoption through `onboard adopt --agent-verdicts -`. The stamps ride the
`(t<id>)` commit as before; an agent-adopted stamp is a stamp like any
other, displayed with `by agent:<s>`.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(modified: display)*

As the baseline; a row whose edge has an `adopted.yaml` row carries
`adopted(<origins> <confidence> by <human|agent:<s>>)` in its `DISPLAY` line,
and `stale --all` prints `ADOPTED:<n>|agent <a>|human <h>`.
<!-- /section: component_staleness_tool -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited)*

Per-variant `last_pass` anchors, `git ls-tree` per sha, `--confirm-evidenced`
as the only bulk confirmation; unchanged, and unchanged in that evidence
removes nags and never reviews a claim — an agent-adopted edge is joined like
any stamped edge.
<!-- /section: component_evidence_join -->

**Selection, scheduling, running, cost**

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(modified: reason text)*

As the baseline; an adopted edge's reason reads
`edge(annotation) adopted(static:invocation+agent:review 0.99 by agent:claudecode/opus5)`
or `adopted(agent:author 0.90 by agent:…)`; `explain --sources` prints
`Covered (adopted by agent)` / `Covered (adopted by human)` for `aitask-qa`.
<!-- /section: component_selector -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited)*

Unchanged.
<!-- /section: component_scheduler_resources -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(inherited)*

`describe / list / run`, `subsumed_by`, `fallback_command`, scaffold;
unchanged.
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(inherited)*

The builtins and `detect`'s repository seeding; unchanged.
<!-- /section: component_reference_runners -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(modified: policy state)*

As the baseline, plus `aitestmap/costs/policy.yaml` `{last_full_run:
{run_id, at, task, sha}, selected_since_full: <n>, approved_by: {who, at,
mode, statement}}`, written by `ait test --gate` under `auto`; the cadence's
`selection_ratio_above` compares the selection's per-group estimate to the
newest full run's p95 on this host class; run-id prefixes unchanged
(`review-` is added for bulk review runs, which write no cost rows).
<!-- /section: component_cost_ledger -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(modified: revocation and criteria)*

`score` gains the revocation step: for each `PREDICTION_MISSED:<id>` and each
changed source in the run's surface, a `rejections[]` row for the pair with
`by: agent:*` is removed, the pair re-seeded with origins `[observed] ∪
<original>` and `evidence.revoked_from: <run>`, and
`AGENT_REJECTION_REVOKED:<test>|<source>|<run>` printed; a `by: human` row
prints `REJECTION_CONTRADICTED:` and stays. The predictions row records
`revoked: [...]`. `readiness` gains `min_full_runs_since_map_change` (reset
by any bulk adoption, revocation or `--author` write; counted in clean scored
full runs) and `max_revoked_rejections` (over the predictions window),
satisfies `approved_by` from `costs/policy.yaml` under `auto`, and prints
`AGENT_ADOPTED:<n>|<ratio>`, `REVOKED:<n>`, `REVIEW_HUMAN:<n>`,
`KIND_PROPOSALS:<n>`. `attribute --propose` is unchanged.
<!-- /section: component_feedback_tools -->

**Adoption and onboarding**

<!-- section: component_adoption_ledger [dimensions: component_adoption_ledger, component_registry_loader, component_seeder, component_onboarding_engine_verbs, component_agent_review_pass] -->
### Adoption ledger *(modified: `by:`, revocation, the autonomous floor)*

The three-file state as the baseline, with `by:` on adopted and rejected
rows, `revocable:` on rejections, and one more transition: a scored miss on
an agent-rejected pair → seeded. The autonomous rule is rewritten: a
headless profile may seed everything and may adopt a class only when every
member carries a rule, a measurement or a reading origin and clears
`accept_min`; heuristic-only classes need a reading on top. Costs are
recorded under `tradeoff_two_edge_states_during_adoption`,
`tradeoff_seed_precision`, `tradeoff_wrong_positive_invisible_to_score`.
<!-- /section: component_adoption_ledger -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(modified: two reading origins)*

As the baseline, plus origins `agent:review` (0.90; written by `onboard adopt
--agent-verdicts`, never by `onboard seed`) and `agent:author` (0.90; written
by `annotate --author`), with `evidence.agent: {by, run, rationale,
packet_sha, test_blob, source_blob, unsure: <n>}`; each origin row carries a
`class:` (rule / measurement / reading / heuristic) that the autonomous floor
reads; `--calibrate` mode; `config.yaml agent_review.measured_confidence`
overrides 0.90 for this repository when calibration measured lower.
<!-- /section: component_seeder -->

<!-- section: component_agent_review_pass [dimensions: component_agent_review_pass] -->
### Agent review pass *(new)*

The mechanism drawn under *The Agent Review Pass*: `onboard review` assembles
bounded, digest-stamped packets (`REVIEW_PAIR` / `REVIEW_ANCHOR` /
`REVIEW_TEST` with assertion lines flagged / `REVIEW_SOURCE` symbols /
`REVIEW_PROSE` / `REVIEW_MEMBER` / `REVIEW_END:<packet_sha>`), `--json`,
`--class`, `--scope`, `--ids`, `--next`, `--calibrate`; `onboard adopt
--agent-verdicts - --by <agent-string> --run <id>` consumes `VERDICT:<id>|
verifies|drives|unsure|<rationale>` lines with the six outcomes (adopt,
reject-revocable, unsure-count, `VERDICT_STALE`, `--by` refusal,
calibration); three sites (in-gate, authoring, bulk) share the intake; the
`aitask-testmap-review` skill is the bulk reader (`review-batch.md`,
profile-aware, resumable through `onboard.yaml phases.review`,
`max_pairs_per_run`); launch surfaces `ait skillrun testmap-review`
(interactive) and `ait codeagent testmap-review [--headless]`
(print mode only under the flag); `verified.testmap-review` in
`models_<agent>.json`; `config.yaml agent_review:` block; budgets: packet
assembly < 300 ms warm, packets bounded by `packet_lines`. Tests: engine
fixtures per language for packet shape and anchor/assertion flagging, every
verdict branch, `VERDICT_STALE`, `--by` grammar refusal, calibration against
a coverage fixture, revocation on a synthetic miss; skill goldens;
`test_codeagent.sh` pins interactive-by-default.
<!-- /section: component_agent_review_pass -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs *(modified)*

As the baseline, plus `review` (packets), `adopt --agent-verdicts` (intake),
`classify --propose` (headless: `kind_proposals[]`, nothing applied), the
`review` phase in the ledger `{status, at, by, counts{reviewed, adopted,
rejected, unsure}, partial: bool}` re-entered at `ONBOARD_NEXT:review` while
partial, `rejections[].by/revocable`, `calibration[]`, and `finish`'s two new
green conditions (`REVOKED:0` in the window, `REVIEW_HUMAN:0`). `detect
--write` writes `completion.mode: auto` and the `agent_review` / `readiness`
blocks when the profile is headless. The engine still never creates a task,
edits a profile or commits.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(modified: headless row)*

As the baseline, plus `adopt.md` ordering rule → measurement → reading with
`review.md` as the reading sub-procedure (batches of 20, the
`aitask-testmap-review` flow inlined), the attended confirmation per class
showing the agent's verdicts pre-filled, and the rewritten headless row:
level 0 and level 1 in full (rule, measurement, review to budget), level 2
proposes kinds, level 3 not entered, no policy flip because `auto` needs
none. `finish` under a headless profile requires `REVOKED:0` and
`REVIEW_HUMAN:0`.
<!-- /section: component_onboarding_skill -->

**The run surface**

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(modified: `auto` resolution)*

As the baseline; under `completion.mode: auto` the POLICY step runs
`readiness`, reads `costs/policy.yaml`, applies the three cadence triggers
and prints `POLICY:auto|selected|next_full_in:<n>` or
`POLICY:auto|full|<cadence:…|not_yet:…>`, writing the first `ADMISSIBLE` as
`approved_by {engine:readiness@<run>, mode: auto}`; the `result=` field
carries the same. `tests/test_ait_test_entrypoint.sh` gains the `auto`
matrix against the fake engine.
<!-- /section: component_test_entrypoint -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Engine `test` composite *(inherited)*

`select → schedule → run` in one process; the policy is the front's;
unchanged.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief *(modified)*

As the baseline, plus `next full in <n> tasks` and the `agent <a>, human
<h>` split on the `TESTMAP:` line, `REVOKED:<n>` when non-zero, the cadence
on `FULL_GATE:`, and one `AGENT_REVIEW:enabled|<confidence>|<calibration>`
line.
<!-- /section: component_agent_brief -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(inherited)*

The fourteen-line `## Running Tests` section, unchanged; the author path is
a procedure act, not a run form.
<!-- /section: component_agent_instructions -->

**Workflow and gates**

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(modified: `auto` and the cadence)*

`completion.mode: full|selected|auto`. `auto`: `ait test --gate` runs
`readiness` on every completion run; `NOT_YET` → full with the criterion
printed; `ADMISSIBLE` → the selection unless a cadence trigger fires
(`full_run_every.tasks` counted in `costs/policy.yaml selected_since_full`;
`selection_ratio_above` against the newest full p95; `days` against
`last_full_run.at`), each printed as `POLICY:auto|full|cadence:<trigger>`;
the first `ADMISSIBLE` writes `approved_by {who: engine:readiness@<run-id>,
at, mode: auto, statement: <readiness lines>}` to `costs/policy.yaml`; a
human-written `selected` still needs `approved_by` in `config.yaml` as
before; demotion (`POLICY_DEMOTED:auto->full|<criterion>`) is automatic and
loud; the policy can only fail toward running more; `readiness` prints what
`--gate` would run now and when the next cadence full run falls.
<!-- /section: component_completion_policy -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(modified: where the engine's approval lives)*

`testmap_fresh`, `testmap_check → tests_pass` as the baseline; no selection
gate. Under `auto` the approval record lives in `costs/policy.yaml`, written
by the engine, so `config.yaml` stays a human-authored declaration. The
verifier contract and the exit rows are unchanged.
<!-- /section: component_gates -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam — the data edits *(modified: two config keys, one operation)*

As the baseline, plus `aitask_codeagent.sh`'s `testmap-review` operation,
`verified.testmap-review` in the three `models_*.json` seeds, and the
`agent_review` / `readiness` / `completion.full_run_every` blocks in
`config.yaml`. No profile key is added.
<!-- /section: component_workflow_seam -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration — the procedure edits *(modified: the autonomous branches act)*

As the baseline, plus: `affected-tests.md`'s autonomous `no_selection`
branch runs `annotate --author` for the task's own pairs before falling back
to `attribute --propose`; `aitask-gate-testmap-fresh`'s seeds step reads
packets and, autonomous, adopts through `--agent-verdicts`; the onboarding
skill's `adopt.md` gains `review.md`; the new `aitask-testmap-review` skill;
goldens regenerated for every profile × agent; `aitask_skill_verify.sh`
run.
<!-- /section: component_workflow_integration -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(modified: display)*

As the baseline; the discovery table shows `Covered (adopted by agent)` /
`Covered (adopted by human)`; QA still measures whether a test exists, not
who accepted the claim.
<!-- /section: component_qa_integration -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(modified: one skill added, one gate skill changed)*

Four skills: `aitask-testmap` (maintenance; unchanged), `aitask-gate-testmap-fresh`
(the seeds step reads packets; attended pre-fill / confirm / trust-batch;
autonomous adopts), `aitask-testmap-onboard` (the headless row),
**`aitask-testmap-review`** (bulk reader). Every skill's runtime knowledge of
how to run tests is still the seeded block plus `--howto`. All ship Claude
Code first; Codex and OpenCode ports are separate tasks.
<!-- /section: component_skill -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited assumptions are listed by key with a one-line restatement; their
full text is in the node metadata and unchanged. Modified and new ones are
stated in full.

### Engine, distribution and install *(all inherited)*

- **`assumption_go_toolchain_available`** — Go ≥ 1.26 in release CI and on
  framework developers' machines; users never need Go.
- **`assumption_go_toolchain_ci_and_dev_only`** — Go is build-time only.
- **`assumption_platform_matrix_sufficient`** — linux/darwin × amd64/arm64.
- **`assumption_release_asset_reachable`** — setup can reach the release
  over HTTPS; the shim never downloads.
- **`assumption_release_assets_reachable`** — air-gapped hosts have the
  fallbacks.
- **`assumption_one_engine_per_framework_version`** — versioned per-user
  directory, exact-version resolution.
- **`assumption_engine_latency_targets`** — the pinned budgets; `onboard
  review` joins the table at < 300 ms warm.
- **`assumption_home_symlink_compatibility`** — every legacy consumer
  dereferences the path.
- **`assumption_legacy_user_root_coexists`** — the two roots coexist this
  release.
- **`assumption_target_repos_accept_aitestmap_root`** — a root `aitestmap/`
  of committed YAML, now also `costs/policy.yaml`.
- **`assumption_testmap_token_no_collision`** — `testmap:` collides with no
  prose.

### The map and freshness *(all inherited)*

- **`assumption_blob_digest_is_staleness_key`**,
  **`assumption_git_history_is_freshness_clock`**,
  **`assumption_passing_run_anchors_edges`**,
  **`assumption_static_granularity_v1`**,
  **`assumption_kotlin_scanner_fail_closed`**,
  **`assumption_annotation_is_comment_only`** — unchanged; `annotate
  --author` and `--agent-verdicts` write comment lines at the same fixed
  positions.

### Variants, broad tests and runners *(all inherited)*

- **`assumption_variant_universe_from_runner_list`**,
  **`assumption_cells_enumerable_by_plugin`**,
  **`assumption_axis_sources_declarable`**,
  **`assumption_axis_membership_declarable`**,
  **`assumption_batch_per_unit_timing_reportable`**,
  **`assumption_areas_express_suite_blast_radius`**,
  **`assumption_broad_tests_area_scoped`**,
  **`assumption_existing_locks_wrappable`** — unchanged.

### Seeding and adoption

- **`assumption_seed_sources_measured`** *(modified)* — one origin table,
  each origin measured and none below 1.0 trusted alone as a *heuristic*;
  the table gains two **reading** origins, `agent:review` and `agent:author`
  at 0.90, whose confidence is calibratable per repository (`onboard review
  --calibrate`, ground truth = coverage facts, else human-reviewed rows) and
  is lowered to the measured agreement ratio when that is below 0.90; every
  origin row carries a class (rule / measurement / reading / heuristic) that
  the autonomous floor reads.
- **`assumption_static_closure_seeds_edges`** *(inherited)* — the static
  closure is the primary seed; it now also supplies the packet's anchor line.
- **`assumption_cochange_is_corroboration`** *(inherited)* — capped at 0.60.
- **`assumption_helpers_separable_by_fanin`** *(inherited)*.
- **`assumption_seeds_select_never_evidence`** *(modified)* — a seed may
  cause a test to run and may never suppress `STALE`, anchor evidence,
  satisfy `require_stamp` or count under `--strict`; it becomes a claim only
  through an explicit adopt. **Autonomous profiles may seed everything and
  may adopt a class only when every member carries a rule, a measurement or
  a reading origin** (`static:package`, `coverage`, `agent:review`,
  `agent:author`) and clears `accept_min`; a heuristic-only class is never
  adopted headless. Falsifier unchanged.
- **`assumption_agent_reads_verify_vs_drive`** *(new)* — an agent given the
  review packet (the anchor line ±20, the test's assertion lines flagged, the
  source's declared symbols, the prose header) distinguishes "verifies" from
  "only drives" at least as precisely as the baseline's ten-sample human
  review of a class, because the judgement is local to the test body: does a
  flagged assertion check something the named source produces? Measured on
  a calibration sample before it is trusted: `onboard review --calibrate 50`
  against coverage facts where a coverage import exists, else against
  human-reviewed rows; agreement ≥ 0.90 keeps the 0.90 confidence, lower
  agreement lowers it, agreement below `accept_min` disables headless
  adoption from this origin and `readiness` says so. Falsifier: a repository
  whose tests assert through an opaque harness (a golden-diff script that
  never names what it checks) — for it the packet has no flagged lines, the
  agent answers `unsure`, and the pair lands in `REVIEW_HUMAN` rather than
  being guessed.
- **`assumption_wrong_positive_claim_only_overselects`** *(new)* — a wrong
  `verifies` verdict produces a stamped edge to a source the test only
  drives; the cost is a needless run when that source changes and a `STALE`
  nag the evidence join usually heals; it never hides a coupling, never
  suppresses a `STALE` row on another edge, and never satisfies
  `UNMAPPED_SOURCE` for a source the test truly does not reach (the closure
  had to contain the source for the packet to exist, or the author had to
  name it inside the task). So agent adoption errs in the direction seeds
  were already allowed to err in, and the only agent verdict that can
  under-select is a rejection. Falsifier: a project that runs `--strict`
  with `on_empty_selection: full` and relies on `UNMAPPED_SOURCE` to force
  full runs — a wrong positive there converts a forced full run into a
  selection; mitigated by the cadence.
- **`assumption_agent_rejection_is_revocable`** *(new)* — a scored full-run
  miss (`PREDICTION_MISSED:<test>`) on a run whose change surface contains
  `<source>` is evidence that `(test, source)` is a real coupling; when that
  pair sits in `rejections[]` with `by: agent:*`, the rejection was wrong
  and is revoked (row removed, pair re-seeded, `AGENT_REJECTION_REVOKED:`
  printed, `max_revoked_rejections` counted); a `by: human` rejection is
  contradicted in print and kept, because evidence removes nags and never
  overrules a person. Falsifier: a miss caused by a coupling through a
  *third* file (the test reaches the source only via a helper) — the
  revocation re-seeds a pair that is then adopted on re-review as `drives`
  again; the second rejection of a revoked pair is marked `REVIEW_HUMAN`.
- **`assumption_headless_launch_is_explicit_opt_in`** *(new)* — no engine
  path, gate, hook or default skill flow launches a code agent in headless
  print mode: the in-gate and authoring sites run inside the session that
  already holds the task; bulk review is `ait skillrun testmap-review`
  (interactive) or, only under `--headless`, `ait codeagent testmap-review`
  — the same opt-in `batch-review` requires, because Claude Code bills print
  mode higher and the framework's shell conventions forbid `claude -p`
  without it. Falsifier: a CI lane with no terminal — for which `--headless`
  is the documented, explicit choice.
- **`assumption_cadence_bounds_exposure`** *(new)* — under `auto`, a wrong
  agent verdict or an unmapped coupling that lets a task land without an
  affected test running is caught by the next cadence full run, which is at
  most `tasks` selected completion runs, `days` wall-clock, or the next
  selection costing ≥ `selection_ratio_above` of full away — whichever comes
  first; every full run scores, so the exposure window is a project-set
  number, printed on every completion run as `next_full_in:<n>`. Falsifier:
  a project whose tasks arrive faster than its full run completes — for it
  `tasks: 1` is `full` with extra steps and the project should stay `full`.

### Onboarding *(inherited)*

- **`assumption_test_tools_detectable`**,
  **`assumption_full_run_expressible_per_repo`**,
  **`assumption_onboarding_is_a_task`** — unchanged; the `review` phase is
  one more phase committed under the level-1 task.

### Run surface and workflow *(all inherited)*

- **`assumption_change_surface_is_intake`** — also the intake for
  `annotate --author`'s not-in-task check.
- **`assumption_task_resolvable_from_session`**,
  **`assumption_helper_degrades_when_absent`**,
  **`assumption_gate_exit_contract_reused`**,
  **`assumption_instructions_block_reaches_agents`**,
  **`assumption_instruction_block_is_read`** — unchanged.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Inherited tradeoffs are listed by key with a one-line restatement; modified
and new ones are stated in full.

### Advantages

- **`tradeoff_computed_vs_prose`** *(inherited)* — selection, the run
  surface and now acceptance are computed, explained and recorded rather
  than remembered.
- **`tradeoff_engine_speed_enables_per_task_use`** *(inherited)*.
- **`tradeoff_real_scheduler`** *(inherited)*.
- **`tradeoff_noarch_packages_preserved`** *(inherited)*.
- **`tradeoff_one_gate_not_two`** *(modified)* — *advantage:* one completion
  gate whose behaviour is a committed policy, and under `auto` the policy
  needs no one to flip it — a headless repository reaches the selective lane
  by itself. *Disadvantage:* a ledger `tests_pass: pass` says even less by
  itself about what ran; mitigated by `result="MODE:…|policy:auto|
  next_full_in:<n>"`, the `POLICY:auto|…` line on every run, the `gate-` run
  id, `POLICY_DEMOTED` being loud and `readiness` printing what `--gate`
  would run now.
- **`tradeoff_loop_closes_without_a_person`** *(new)* — *advantage:* the
  value the mandate names is realised: seeding, adoption, the policy flip and
  the safety net are each performed by a machine or an agent under a
  committed policy, so a repository onboarded by a headless profile gets a
  per-change-set completion gate within `min_scored_full_runs + 3` tasks of
  level 0 with nobody typing anything; what remains human is a printed list
  (`KIND_PROPOSALS`, `REVIEW_HUMAN`, axes), not an assumed step.
  *Disadvantage:* the map's provenance is now mostly `by: agent` in such a
  repository, and a reader who wants human-reviewed claims must look for the
  `human` split in `onboard status` — it is never hidden, but it is no longer
  the default state.

### Engine and distribution *(all inherited)*

- **`tradeoff_compiled_component_cost`**, **`tradeoff_two_toolchains`**,
  **`tradeoff_setup_network_fetch`**, **`tradeoff_engine_version_skew`**,
  **`tradeoff_strict_version_handshake`**,
  **`tradeoff_engine_absent_on_host`**, **`tradeoff_fallback_runs_more`** —
  unchanged.

### The per-user root *(all inherited)*

- **`tradeoff_two_user_roots`**, **`tradeoff_split_home_rejected`**,
  **`tradeoff_home_migration_window`** — unchanged.

### Map and registry structure *(all inherited)*

- **`tradeoff_registry_directory_complexity`** — one more committed ledger
  file (`costs/policy.yaml`) and three more row fields; still one merge rule.
- **`tradeoff_cell_table_size`**, **`tradeoff_member_annotation_drift`**,
  **`tradeoff_static_scanner_overselection`**,
  **`tradeoff_area_glob_coarseness`**, **`tradeoff_broad_scope_coarseness`**,
  **`tradeoff_axis_declaration_burden`**,
  **`tradeoff_axis_projection_coarseness`**,
  **`tradeoff_intersection_can_underselect`**,
  **`tradeoff_whole_run_filter_soundness`**,
  **`tradeoff_resource_declaration_completeness`** — unchanged.

### Freshness and evidence

- **`tradeoff_stamp_churn`** *(inherited)* — headless level 1 on aitasks now
  performs the ~720-file rewrite the baseline reserved for an attended
  session; the same mitigations apply (comment lines only, batched commits
  named `chore: Onboard testmap — review (t<id>)`, `ADOPT_REFUSED:
  dirty-foreign`), and `max_pairs_per_run` splits the rewrite across runs.
- **`tradeoff_flaky_pass_anchors`**,
  **`tradeoff_evidence_requires_reachable_history`**,
  **`tradeoff_batch_misreport_risk`** *(inherited)* — unchanged.
- **`tradeoff_autonomous_confirmation_weak`** *(modified)* — risk: an
  autonomous run now does more than confirm evidence — it accepts claims
  (`agent:review`, `agent:author`) and flips the policy (`auto`). Narrowed:
  `--confirm-evidenced` remains the only bulk *re-stamp*; an agent
  acceptance is a fresh stamp with `by: agent` provenance that `stale`,
  `explain`, `check` and `readiness` all display and count; the acceptance
  needs a packet the engine cut and a rationale the agent wrote, both
  stored; a `STALE` row is still never confirmed without a person; the
  policy flip is bounded by the cadence and reversed by the demotion; and
  `agent_review.enabled: false` restores the baseline exactly.
- **`tradeoff_attribution_risk`** *(inherited)* — narrowed one more way: the
  authoring agent maps its own new sources at the pre-review step through
  `annotate --author`, so the "looks current and is not" window closes
  during the task in autonomous profiles too.

### Seeding, adoption and onboarding

- **`tradeoff_seed_noise`** *(inherited)* — reviewer fatigue on a
  1,000-seed queue is now spread over agent batches as well as class
  adoption; the noise itself is unchanged.
- **`tradeoff_seed_precision`** *(modified)* — an adopted `covers` edge is a
  machine claim in a human annotation's clothes; with agent adoption it is a
  *reading's* claim, and the reading answers exactly the executes-vs-verifies
  question the closure could not. Narrowed as before (provenance shown,
  `ADOPTED_UNREVIEWED`, over-claim only over-selects, the 0.85 threshold)
  plus: `by: agent` on the row, the stored packet digest and rationale, the
  calibration sample, and `unsure` as an allowed answer so the agent is never
  forced to guess. A coupling the closure does not contain is still caught
  only by a full run's score — or named by the author at the moment it is
  created.
- **`tradeoff_wrong_positive_invisible_to_score`** *(new)* — risk: a wrong
  `verifies` verdict is never detected by the feedback loop, because a
  claimed edge that should not exist can only over-select, and score
  measures under-selection. Its cost is bounded — needless runs of that test
  when the driven source changes, and `STALE` nags on a pair the evidence
  join heals when the test passes — but it accumulates silently in the
  `agent <a>` share of the adopted count. Mitigated by the packet flagging
  assertion lines so the agent answers from evidence, by `unsure` and
  `REVIEW_HUMAN`, by calibration against coverage or human rows before the
  origin is trusted, by `agent_review.measured_confidence` lowering the
  weight where calibration is poor, by the human re-stamp path deleting the
  provenance row, and by `onboard status` reporting the agent share so a
  maintainer can sample it. What remains: a repository with neither coverage
  nor any human-reviewed rows has no calibration ground truth and runs on
  the 0.90 prior, which `readiness` states as `CALIBRATION:none`.
- **`tradeoff_auto_policy_exposure_window`** *(new)* — risk: under `auto` a
  task may land while an affected test never ran, until the next cadence
  full run — the residual risk the mandate names. Its size is a project
  choice: `full_run_every.tasks` (default 5) bounds it in tasks, `days` in
  time, `selection_ratio_above` makes the cheap-to-run-full case run full;
  every completion run prints `next_full_in:<n>`; the demotion still fires on
  the first scored miss; and a project that cannot accept any window keeps
  `full` or `selected`. What remains: `tasks − 1` tasks may merge on a wrong
  selection before the miss is scored, and their dependents may have built
  on them; `blocks_dependents` on `tests_pass` does not help here because the
  gate passed. The mitigation that is honest is the number itself, printed.
- **`tradeoff_periodic_full_run_cost`** *(new)* — disadvantage: the cadence
  spends full runs a human flip would not — one in every `tasks` completion
  runs plus the `days` and ratio triggers. On aitasks (p95 ≈ 400 s full,
  typical selection ≈ 40 s) `tasks: 5` keeps ≈ 80 % of the saving; on
  thinking_app (1,180 s full) the same cadence keeps ≈ 75 % and the project
  may raise `tasks` once its calibration and revocation counters have been
  zero for a while. Mitigated by the ratio trigger (a selection that would
  cost ≥ 60 % of full runs full and scores, so the cadence counter resets
  for free), by every full run doing double duty (evidence anchors, cost
  fold, score), and by `readiness` printing the cadence so it is a decision,
  not a surprise.
- **`tradeoff_agent_review_token_cost`** *(new)* — disadvantage: bulk review
  costs model tokens — 36 packets of ≤ 2,400 excerpt lines on aitasks — and
  a headless launch costs more per token. Mitigated by the packet excluding
  source bodies and capping test excerpts, by the in-gate and authoring
  sites reading in a session that already has the files open (no extra
  launch), by `max_pairs_per_run` bounding one run, by rule and measurement
  classes adopting without any reading, and by the headless launch being an
  explicit flag rather than a default.
- **`tradeoff_two_edge_states_during_adoption`** *(modified)* — until both
  queues are empty a repository has *four* provenances a reader must keep
  apart: seeded, adopted by human, adopted by agent, reviewed; mitigated by
  `by:` printed on every adopted row, the `agent <a>|human <h>` split on
  `check`, `stale --all`, `readiness` and `--howto`, `onboard status` as the
  one place the ratios live, and the rule that no seed and no agent verdict
  ever changes a freshness verdict on another edge. The cost that was real —
  `--strict` waiting on adoption forever in a repo no one reviews — is
  removed for headless repositories and replaced by the exposure window
  above.
- **`tradeoff_bulk_confirmation_granularity`** *(modified)* — adopting per
  evidence class traded depth for feasibility; agent review restores depth
  at feasibility's price: every pair is read, but by an agent. Mitigated as
  before (samples, `--accept-min`, `--scope`, provenance, the per-row path)
  plus the attended pre-fill / confirm / trust-batch choice, and kind changes
  still confirmed individually by a person.
- **`tradeoff_accept_rewrites_history`** *(inherited)* — unchanged; the
  bulk rewrite now also happens headless.
- **`tradeoff_onboarding_partial_coverage`** *(inherited)* — the
  same-package gap on thinking_app is now closed incrementally by
  `agent:author` as tasks touch pairs, not by onboarding; `onboard status`
  still reports the honest ratio.
- **`tradeoff_fail_closed_bootstrap_cost`** *(modified)* — the bootstrap
  order is unchanged and one cost is removed: a repository is no longer
  level 0 "until a human adopts level 1" — a headless profile adopts by
  rule, measurement and reading, and `auto` flips the policy when the scored
  history allows. What remains: kinds and axes are human, `REVIEW_HUMAN`
  pairs wait for a person, and `min_scored_full_runs` full runs must still
  happen before any selection reaches the gate.
- **`tradeoff_verify_build_wired_suites`** *(inherited)* — unchanged;
  headless keeps `verify_build`.

### Run surface and workflow *(all inherited)*

- **`tradeoff_dispatcher_verb_added`** — unchanged; `annotate --author` is a
  `testmap` subverb, not a new dispatcher verb.
- **`tradeoff_generated_brief_limits`** — unchanged.
- **`tradeoff_workflow_surface_growth`** — one more skill
  (`aitask-testmap-review`) with two wrapper surfaces, one `codeagent`
  operation, three `models_*.json` keys, and no new profile key; the same
  mitigations (printed skips, one contract, goldens).
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should `agent:author` require a static fact (the test reaches the source
   through the closure) to be adopted, or is "in this task's change
   surface" enough? Proposed: either suffices, because both bind the claim
   to the task; a claim satisfying neither is refused, never seeded.
2. Should the review packet include the source *body* for small sources
   (< 40 lines)? Proposed: no in v1 — the symbol list keeps the packet bounded
   and the question is about the test, not the source.
3. What is the right default for `full_run_every.tasks`? 5 keeps most of the
   saving and bounds exposure to four tasks; a project with dependents
   building on every task may want 2. Proposed: 5, printed by `readiness`
   with the measured saving so the number is chosen with a cost in view.
4. Should a revoked agent rejection re-enter the agent queue or go straight
   to `REVIEW_HUMAN`? Proposed: re-enter once with `evidence.revoked_from`
   in the packet's `REVIEW_PROSE` line; a second `drives` on a revoked pair is
   `REVIEW_HUMAN`.
5. Should calibration be a `readiness` criterion (`agent_review_calibrated`)
   or advisory? Proposed: advisory in v1, printed as `CALIBRATION:none` when
   no ground truth exists, because a repository with neither coverage nor
   human rows would otherwise never reach `ADMISSIBLE` — which is the
   baseline's failure mode restated.
6. Should `verified.testmap-review` in `models_<agent>.json` gate which
   models may write `--by`? Proposed: no — `verified` is informational
   across every operation today; a project that wants a floor sets
   `agent_review.min_verified: <n>` (reserved, not implemented).
7. The baseline's open questions 1–11 stand; question 10 (should adopted
   rows age out into reviewed) is sharpened by agent adoption: with most
   rows `by: agent`, "reviewed" would come to mean "old". Proposed: still
   no; `ADOPTED_UNREVIEWED` and the `agent` share are meant to be read.
<!-- /section: open_questions -->
--- PROPOSAL_END ---
--- NEW_DIMENSIONS ---
requirements_autonomous_loop_closure, assumption_agent_reads_verify_vs_drive, assumption_wrong_positive_claim_only_overselects, assumption_agent_rejection_is_revocable, assumption_headless_launch_is_explicit_opt_in, assumption_cadence_bounds_exposure, component_agent_review_pass, tradeoff_loop_closes_without_a_person, tradeoff_wrong_positive_invisible_to_score, tradeoff_auto_policy_exposure_window, tradeoff_periodic_full_run_cost, tradeoff_agent_review_token_cost
