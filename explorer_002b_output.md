--- NODE_YAML_START ---
node_id: n005_explorer_002b
parents:
- n003_synthesizer_001
description: >-
  The n003 synthesis with two corrections - the engine installs under the
  framework's own per-user root ~/.aitasks/engine/v<VERSION>/ (a new
  AITASKS_HOME, legacy ~/.aitask/ tenants left in place), and the registry gains
  member-scoped units and declared variant axes so a project's own test
  subdivision - thinking_app's screen x matrix, where a matrix is locale x
  direction x geometry - is a first-class unit: a screen's composable selects
  that screen on every matrix, values-ru/ selects every screen on the ru
  matrices only, a fail-closed Kotlin scanner escalates on constructs it cannot
  see through, and every full run scores the last prediction as a golden
  false-negative count.
proposal_file: br_proposals/n005_explorer_002b.md
created_at: "2026-09-16 10:20"
reference_files:
# --- carried from the baseline ---
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
# --- added: the per-user root precedent (~/.config/aitasks) ---
- .aitask-scripts/aitask_projects.sh
- .aitask-scripts/aitask_project_resolve.sh
# --- added: thinking_app's screen x matrix test subdivision (resolved via the project registry) ---
- /home/ddt/Work/thinking_app/aidocs/testing/change-aware-verification.md
- /home/ddt/Work/thinking_app/aidocs/testing/rendering-verification.md
- /home/ddt/Work/thinking_app/aidocs/testing/localized-strings.md
- /home/ddt/Work/thinking_app/CLAUDE.md
- /home/ddt/Work/thinking_app/aitasks/metadata/project_config.yaml
- /home/ddt/Work/thinking_app/tools/verification/screenshot-tests.sh
- /home/ddt/Work/thinking_app/tools/verification/lib/screenshot-review.sh
- /home/ddt/Work/thinking_app/tools/verification/lib/screenshot-diff-set.sh
- /home/ddt/Work/thinking_app/tools/verification/suite-outcome-check.py
- /home/ddt/Work/thinking_app/tools/verification/primary-catalog-expected.txt
- /home/ddt/Work/thinking_app/tools/verification/secondary-matrices-expected.txt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ScreenshotTestHarness.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/CurrentHeadScreenshotsTest.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/ExtendedCatalogScreenshotsTest.kt
- /home/ddt/Work/thinking_app/app/src/test/java/com/softman/thinking/testing/MatrixAuditRegistry.kt
- /home/ddt/Work/thinking_app/app/src/test/resources/screenshot-baseline-map.properties
- /home/ddt/Work/thinking_app/app/src/main/java/com/softman/thinking/utils/TypeScale.kt
- /home/ddt/Work/thinking_app/app/src/main/java/com/softman/thinking/ui/components/AppRoot.kt
- /home/ddt/Work/thinking_app/aitasks/t384_advisory_affected_surface_for_change_aware_verify.md
- /home/ddt/Work/thinking_app/aitasks/t386_prediction_accuracy_ledger_for_affected_surface.md
- /home/ddt/Work/thinking_app/aitasks/t387_test_side_dependency_model_for_change_aware_verify.md
- /home/ddt/Work/thinking_app/aitasks/t388_conditional_gating_verify_affected_tier.md
# --- carried remote references ---
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
# --- added remote references for the variant-axis lowering ---
- https://docs.gradle.org/current/userguide/java_testing.html#test_filtering
- https://github.com/takahirom/roborazzi
- https://robolectric.org/device-configuration/
- https://developer.android.com/guide/topics/resources/providing-resources#AlternativeResources
# ---------------------------------------------------------------------------
# requirements_* (inherited unless marked; paths and unit grammar revised)
# ---------------------------------------------------------------------------
requirements_generic_across_projects: >-
  A framework feature, generic across projects (aitasks, thinking_app,
  thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation
  between source files and test units - including a project's own finer
  subdivision of a test file, such as thinking_app's screen fixtures crossed with
  its recording matrices, expressed through member units and declared axes
  rather than through project-specific code in the engine (revised)
requirements_screen_locale_subdivision: >-
  NEW - a test unit may be a member of a file (<path>#<member>) and may carry
  variants on a declared axis (<unit>@<variant>); a source change reaches a unit
  on every variant, or reaches an axis facet value (matrix.locale=ru) and thereby
  only the variants carrying it; the runner lowers a variant id to what it
  executes (for thinking_app, <Class>.<method> per matrix through the existing
  matrix_classes / preview_resolve_token routing) so the engine never learns
  Gradle, Roborazzi or the membership manifests
requirements_reason_per_selected_test: >-
  Translates a task's change set into one ranked list of tests that must run,
  with a reason on every line - edge, dep, rule, axis(matrix.locale=ru) <-
  <source>, test-dep <helper>, ESCALATE:<file>|<reason> for an opaque source,
  a stale mark when a selecting edge's digest no longer matches and no run
  evidence covers that variant, and an explicit DEFERRED line for every broad
  test the suite budget cut (revised: axis, test-dep and ESCALATE reasons)
requirements_standard_runner_contract: >-
  Runs selected tests through project-defined runners under a standard contract
  (describe/list/run verbs); list emits TSV rows <id> <kind> <lowering> and may
  emit member and variant ids, run receives ids and lowers them, results.jsonl
  reports per id (a batch runner inverts its tool's report - JUnit
  classname/name - back to ids through its own list table), and a unit: suite
  runner may emit child rows keyed to registered ids beside its verdict row;
  reference runners are built into the engine as builtin:<name> with
  command:/cwd: overrides, and a project script of the same name shadows a
  builtin (revised)
requirements_cost_tracking: >-
  Tracks cost per test unit and per variant, keyed by host class, using
  Welford's online update (n, mean, standard deviation, p95, last), plus a
  last_pass {sha, at, run_id} anchor and a flake rate per unit or variant
  (revised: variant rows)
requirements_feedback_loop: >-
  Learns from failures the map did not predict via a score/attribute feedback
  loop; every full run automatically scores the newest prediction record for
  the same task and prints PREDICTION_FALSE_NEGATIVES:<n> plus one
  PREDICTION_MISSED:<id> line per miss, appending to a committed
  costs/predictions.yaml so a repo can cite its own miss history; attribute
  records an observed edge for a unit or member unit, an observed axis source
  for a facet value, and an observed trigger or area member for a broad test,
  merged into the registry at load (revised)
requirements_gate_enforcement: >-
  Enforced by gates so the map cannot rot silently: a procedure gate
  (testmap_fresh) that reviews stale annotations before the task commit, a
  check gate (testmap_check, fails rotted paths on its own) and a run gate
  (testmap_run), fail-closed with explicit waivers; only check unlocks run;
  a project whose completion invariant is a full suite (thinking_app's
  verify-active as test_command) keeps tests_pass as the completion gate and
  enables testmap_run only after ait testmap readiness reports the declared
  admission criteria met (revised)
requirements_agent_skill: >-
  Agent skills teach agents how to keep the map current as they write code and
  tests: annotate (file, member or axis), attribute, waive, verify after editing
  an annotation, confirm or retarget digest stamps in the procedure gate, and
  drive a project's own render loop from select --format tokens (revised)
requirements_go_engine_and_cli: >-
  The engine and CLI are one static Go binary (ait-testmap) built from engine/;
  bash keeps only the dispatcher arm, the shim that resolves the binary under
  $AITASKS_HOME and pipes the change surface in, the two gate verifier shells,
  the ait engine developer verbs and any project-local runner scripts; the
  binary never invokes aitask_*.sh (revised: root variable)
requirements_go_engine: >-
  Scan, check, select and stale finish in well under a second on a ~720-test
  repo - and select stays under 250 ms on thinking_app's ~300 golden variants
  plus ~370 JVM classes with axis expansion - and the scheduler runs
  concurrently with real cross-process locks, so selection overhead stays
  negligible against the shortest test and check can run at every commit step
  (revised: variant target added)
requirements_platform_binaries_in_release: >-
  Release CI builds and attaches checksummed binaries for linux/darwin x
  amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt)
  from one engine job that also runs go vet and go test; a new engine-check.yml
  runs the same on push/PR for engine/**; tarball and package-manager artifacts
  stay architecture-independent
requirements_user_root: >-
  NEW - every per-user artifact this feature installs lives under the
  framework's own root, ~/.aitasks/ (env override AITASKS_HOME), beside the
  existing ~/.config/aitasks/ and ~/.cache/aitasks/ roots; the engine is the
  root's first tenant at $AITASKS_HOME/engine/v<VERSION>/ and
  $AITASKS_HOME/engine/dev/; the legacy ~/.aitask/ tenants (venv, python, bin,
  uv, dev_tier, update_check) are neither moved nor read by this feature
requirements_engine_packaging: >-
  ait setup and ait upgrade (through install.sh's --source-only path) install
  the host's binary under $AITASKS_HOME/engine/v<VERSION>/ with checksum
  verification, a .sha256 sidecar and a version --json self-check; fallbacks
  --local-engine, --engine-from-source, AIT_TESTMAP_BIN; opt-out --no-testmap /
  AIT_TESTMAP_FETCH=0 (revised: root)
requirements_dev_rebuild_from_source: >-
  A framework developer rebuilds the engine with one command (ait engine build)
  through the same engine/build.sh that CI uses, into $AITASKS_HOME/engine/dev/
  which the shim selects via AIT_ENGINE=dev (version must read <V>-dev+<sha>);
  ait engine cross produces the CI matrix locally, byte-identical (revised: root)
requirements_engine_dev_regeneration: >-
  The GOOS/GOARCH matrix, CGO_ENABLED=0 and ldflags live in one script
  (engine/build.sh) shared by release CI, ait engine build and ait engine cross;
  ait engine test runs go vet and go test; ait engine prune removes versions
  under $AITASKS_HOME/engine/ that no registered project is on (revised: root)
requirements_annotation_freshness: >-
  Every unit coverage annotation carries the date and a blob digest of the
  covered source at confirmation; committed last_pass anchors, per variant where
  a unit has variants, let stale prove a test already passed against a changed
  source's current content (EVIDENCED) so most hot-source churn needs no
  rewrite; a procedure gate at the post-implementation step hands the report to
  an agent that fixes annotations before the task commit (revised: per-variant
  evidence)
requirements_annotation_staleness: >-
  A stale verb reports, for a task's change set or repo-wide, STALE_PATH
  (deleted or renamed source, fail-closed), STALE (content changed, no
  evidence on every reached variant), EVIDENCED, UNSTAMPED, STALE_AREA and
  opt-in REVIEW_DUE rows in the framework's fixed line protocol; digest
  comparison needs no git history, evidence only removes nags
requirements_high_level_tests_separate: >-
  Integration, e2e and device tests declare areas, scope globs or budget-exempt
  trigger globs instead of covers, live in registry/_scoped.yaml beside the
  unit table, join the ranked list at distance 1 as sinks, and never enter the
  per-file edge graph or its digest staleness; a helper file may declare
  testmap:reads <glob> so every unit whose test-file closure contains it
  inherits the glob as a trigger (revised: reads)
requirements_broad_test_handling: >-
  Scoped rows are ranked after unit tests at equal distance, selected under an
  explicit suite budget that prints every DEFERRED cut, scheduled only after
  the unit wave is green (broad_after_unit), widened by attribute on a full-run
  miss, and drift-flagged by evidence (STALE_AREA) rather than by calendar
# ---------------------------------------------------------------------------
# assumption_* (inherited unless marked)
# ---------------------------------------------------------------------------
assumption_static_granularity_v1: >-
  Static file-level facts remain the default for v1, with two narrower
  granularities now in use rather than reserved: a member unit (<path>#<member>,
  annotations scoped by testmap:unit blocks, no language parsing) and the
  edge's symbols slot, whose first consumer is the opt-in android-res scanner
  that names the string keys a values-<q>/ diff changed; no scanner produces
  symbol-level coverage of Kotlin or Python code (revised)
assumption_change_surface_is_intake: >-
  The change-surface script's attribution (aitask_change_surface.sh) is the
  right intake; its exit codes carry no meaning, so the shim pipes its
  COMMITTED:/TASK:/OTHER:/UNKNOWN: lines into the engine's --changes - and the
  engine parses lines only; selection never reads a raw git diff, and an
  UNKNOWN path refuses selection and drives the stale decision; the before
  content a symbol scanner needs comes from HEAD:<path> (TASK: rows) or the
  parent of the first (t<id>) commit (COMMITTED: rows) and is absent - so the
  whole file is the symbol set - when history is unreachable
assumption_existing_locks_wrappable: >-
  Existing project locks and allocators (thinking_app's heavy-run lock, emulator
  allocation) can be wrapped as resources without changing them; the Go
  admission and allocator kinds exec the project's commands and honour their
  exit codes, deferring on 75 until the run deadline
assumption_batch_per_unit_timing_reportable: >-
  Runners can report per-unit timing inside a batch from their tool's own
  report format (JUnit XML, go test -json, pytest junitxml) and can invert a
  report row to a registered id - JUnit classname+name back to
  ScreenFixtures.kt#Welcome@pixel5Ru_ltr through the same routing table the
  runner's list verb printed; the builtin runners parse these in Go (revised)
assumption_target_repos_accept_aitestmap_root: >-
  Every target repo will accept a root aitestmap/ directory of YAML committed
  into its code tree, including an optional axes.yaml; runner scripts are
  optional because the reference runners are built into the engine, and
  thinking_app commits one (tools/verification/testmap_runner.sh) because its
  lowering is the harness's own routing
assumption_testmap_token_no_collision: >-
  The annotation token 'testmap:' does not collide with existing prose comments
  in any target repo; the 38 existing '# Covers:' headers in aitasks are
  behavioural prose and are not matched; thinking_app's KDoc mentions no
  'testmap:' string
assumption_gate_exit_contract_reused: >-
  The framework verifier contract (0 pass / 1 fail / 2 skip / 3 error) is
  reused through two dedicated verifier shells, not through
  gate_command_exit_contract, which maps only command exits 0/1/2; runner exit
  75 (admission refused, a thinking_app code absent from the framework) is
  deferred inside the engine and a final 75 maps to verifier 3; only an empty
  selection maps to 2; a missing engine maps to 3, never skip
assumption_go_toolchain_available: >-
  A Go toolchain >= 1.26 is available in release CI through an actions/setup-go
  step this design adds to release.yml (go-version-file: engine/go.mod) and on
  framework developers' machines; target-project users never need Go
assumption_go_toolchain_ci_and_dev_only: >-
  Go is a build-time dependency only - release.yml has no Go step today and the
  repo's only setup-go is hugo.yml's at website/go.mod's 1.25.7, so the engine
  job provisions its own toolchain; users receive prebuilt binaries and never
  compile
assumption_release_asset_reachable: >-
  A host running ait setup or ait upgrade can reach
  github.com/beyondeye/aitasks/releases over HTTPS, as it already must for the
  framework tarball; the shim itself never downloads, so a gate run never
  performs a network fetch
assumption_release_assets_reachable: >-
  Air-gapped or off-matrix hosts supply the binary via --local-engine,
  --engine-from-source, AIT_TESTMAP_BIN or a pre-seeded $AITASKS_HOME/engine/;
  --no-testmap / AIT_TESTMAP_FETCH=0 skip the fetch and nothing else in setup
  depends on it (revised: root)
assumption_git_history_is_freshness_clock: >-
  Git history is the evidence clock, not the staleness key - commit
  reachability (merge-base --is-ancestor) decides which last_pass anchors may
  suppress a STALE row, never whether an edge is stale; mtime is never
  compared; a shallow clone whose anchors are outside fetched history reports
  STALE, not EVIDENCED, and remains fully functional
assumption_passing_run_anchors_edges: >-
  A passing run of a test variant at commit C, on any host class, from an
  invocation without a cause and for a unit under the flake threshold, is
  evidence that its annotated edges held for that variant against the source
  content present in C's tree - so an edge whose current blob equals the blob
  at C is EVIDENCED for that variant without touching the test file; a unit
  with variants is EVIDENCED only when every variant the change reaches has such
  a pass (revised: per variant)
assumption_areas_express_suite_blast_radius: >-
  The blast radius of a high-level test is expressible as a union of area glob
  sets plus scope globs plus budget-exempt trigger globs, plus the reads globs
  of helpers in its test-file closure; what that misses surfaces through score
  on a full run as an observed trigger or area member (revised: reads)
assumption_engine_latency_targets: >-
  On the aitasks repo (about 720 test units, 2,500-3,000 edges, about 270
  scanned sources) the engine meets select < 200 ms warm, scan < 300 ms, check
  < 300 ms, stale --task < 300 ms, stale --all < 2 s, cold select < 1.5 s; on
  thinking_app (about 300 golden variants over 49 member units, about 370 JVM
  classes, about 900 Kotlin files) select with axis expansion < 250 ms warm;
  pinned by committed go test -bench fixtures with a 2x regression failing
  engine-check.yml, validated before the gates are enabled (revised)
assumption_platform_matrix_sufficient: >-
  linux/darwin x amd64/arm64 covers every target host (WSL reports Linux); any
  other platform builds from source via --engine-from-source
assumption_blob_digest_is_staleness_key: >-
  The git blob digest of the covered source's content is the staleness key;
  file mtime (reset by checkout) and the annotation date (day granularity,
  clock skew) are never compared - the date is display only; the blob id
  doubles as the join key into any commit's tree for the evidence join
assumption_broad_tests_area_scoped: >-
  Integration, e2e and device tests can be described by named areas or globs
  whose membership changes rarely, so evidence-based drift (STALE_AREA) plus
  attribute widening is adequate; a calendar cadence (REVIEW_DUE,
  broad_review_days) is opt-in and off by default
assumption_one_engine_per_framework_version: >-
  One engine build per framework version suffices; a per-user versioned
  directory ($AITASKS_HOME/engine/v<VERSION>/) resolves per-project VERSION
  differences without a compatibility matrix, and exact-version resolution in
  the shim never falls back to newest-wins (revised: root)
assumption_variant_universe_from_runner_list: >-
  NEW - a runner's list verb enumerates the complete universe its run filter
  can address, so whole-run selection is sound: for thinking_app that is every
  <Screen>_<matrix>.png of the two membership manifests
  (primary-catalog-expected.txt, secondary-matrices-expected.txt: 50 + 247
  goldens over 10 matrices) as variant ids plus every other class under
  app/src/test/java as a file unit; a class absent from list is a check failure
  (unregistered test), never a silently unfiltered one
assumption_axis_sources_declarable: >-
  NEW - the sources that reach one facet value of an axis are declarable as
  globs in axes.yaml: for thinking_app's locale facet, values-<q>/**, raw-<q>/**
  and the per-family fonts (heebo_* for he, roboto_* for en and ru, cairo_* for
  ar); sources every locale reads (values/**, TypeScale.kt, Fonts.kt,
  AppRoot.kt) are ordinary edges or scanned dependencies and reach every
  variant; the geometry and direction facets have no axis sources because they
  are test-side constants in ScreenshotTestHarness.kt, reached through the
  test-dep closure
assumption_kotlin_scanner_fail_closed: >-
  NEW - a closed construct list (explicit repo import, same-package as fully
  connected, repo star import as a package edge, fully-qualified in-body
  reference from the comment-stripped body) is enough to over-approximate the
  Kotlin import graph, and every construct that defeats such a graph - inline
  functions, const val, Hilt/DI bindings, Class.forName / ::class.java,
  generated or KSP sources, an unreadable or untokenizable file - is detectable
  by pattern and marks the file opaque, so a change to it escalates instead of
  being silently narrow; each opaque branch is reachable and red-proved by an
  engine fixture test
assumption_legacy_user_root_coexists: >-
  NEW - ~/.aitasks/ (this feature) and ~/.aitask/ (venv, python, bin, uv,
  dev_tier, update_check; 49 framework files name it) can coexist on one host
  without either reading the other; migrating the legacy tenants under
  AITASKS_HOME is a separate, later change, and nothing in this feature depends
  on it happening
# ---------------------------------------------------------------------------
# component_* (inherited unless marked)
# ---------------------------------------------------------------------------
component_registry_loader: >-
  Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  plus axes.yaml into six tables (edges, scopes, areas, rules, waivers, axes);
  unit ids follow <path>[#<member>][@<variant>], with variants materialised at
  load from each runner's list output and validated against the axis's value
  set; owns: routing by glob for edges and rules and by area name for
  hand-declared scopes; write routing (scan --apply -> _scanned.yaml and
  _scoped.yaml, attribute -> observed.yaml, declare -> the owning hand file);
  deterministic sorted writes only on change; check rules incl. STALE_PATH,
  UNSTAMPED past bootstrap under require_stamp, DEAD_SCOPE, DEAD_AXIS_SOURCE
  (an axis glob matching nothing), UNKNOWN_VARIANT (a listed variant outside
  the axis), KIND_MISMATCH|CONVERT_TO_SUITE above unit_covers_max,
  CONTRACT_MISMATCH; golden tests pin the merge rule (revised)
component_annotation_scanner: >-
  Annotation scanner and rewriter (internal/annot): grammar v3 - testmap:unit
  <Member> opens a member block that owns every following testmap: line until
  the next testmap:unit or end of file (a file-level block precedes the first
  unit); testmap:kind, testmap:covers <path> @<date>/<blob10>, testmap:area,
  testmap:scope, testmap:trigger, testmap:reads <glob> (helper files only),
  testmap:reviewed, runner/needs/batch - per comment leader and Python module
  docstrings; refuses unknown keys with a line number; the line-targeted
  rewriter edits stamps by (file, line, current text) and refuses on
  REWRITE_CONFLICT; produces both generated files from every runner's list
  output (revised: unit blocks, reads)
component_dependency_scanners: >-
  Dependency scanners (internal/deps): built-in bash, python, go (go list -deps
  -json cached by go.sum digest), kotlin and Gradle module-graph scanners plus
  executable plugins under aitestmap/scanners/ speaking one JSON line per file
  {file, deps, opaque?, reads?}; the kotlin scanner runs over main and test
  roots, handles a closed construct list and marks every other file
  opaque:<reason>; the opt-in android-res symbol scanner indexes R.string.<key>,
  stringResource(R.string.<key>) and "<key>".localized() sites per Kotlin file
  and, given a before blob, the keys a values-<q>/ diff changed; forward deps
  cached per source blob under ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json
  and inverted in memory (revised)
component_selector: >-
  Selector (internal/selectr, internal/changesurface): line-protocol intake via
  --changes - or a file, refusing on UNKNOWN:; the graded walk with
  select/implies/escalate rules; variant expansion (an edge to a unit selects
  every variant; an axis hit selects the variants carrying the facet value; a
  symbol-narrowed axis hit selects only the member units whose closure names a
  changed key); test-dep at d1 when a changed file is in a unit's own test-file
  closure, including reads globs; ESCALATE:<file>|<reason>|<runner-set> for a
  changed opaque file; scoped join at d1; ranking by distance then kind then
  cost; stale marks from digest compare plus per-variant evidence join;
  --include-stale; suite budget with DEFERRED lines and budget-exempt triggers;
  --format lines|json|tokens (tokens = the runner's declared token_format, e.g.
  <matrix>:<Screen>); prediction record; explain (revised)
component_runner_contract: >-
  Runner contract and repository (internal/runner): describe (adds axis:,
  token_format:), list as TSV <id> <kind> <lowering> with member and variant
  ids, run --manifest with ids and their lowerings, results.jsonl per id with
  optional child rows under a suite parent, runner.json, first-match bindings
  and per-test override, the builtin: scheme with command:/cwd: overrides and
  shadow-by-name, batching by (runner, resource set, batch flag), per-unit
  timeouts, units_expected/units_reported reconciliation per id, exit contract
  0/1/2/75 plus 64 (revised)
component_scheduler_resources: >-
  Scheduler and resources (internal/sched): kinds mutex/semaphore/admission/allocator,
  scopes host/worktree/run, acquired_by planning; flock(2) slot files taken in
  canonical order; admission exec with 75 deferral and backoff to the run
  deadline; allocator exec with signal-safe release; goroutines under
  errgroup; batching (variants of one runner batch into one invocation, so
  thinking_app's whole selection is one Gradle run); broad_after_unit waves;
  config concurrency: serial|parallel defaulting to serial at bootstrap with
  --serial/--parallel overrides; the schedule report and its check half
component_cost_ledger: >-
  Cost ledger (internal/cost): Welford per (id, host class) where id may be a
  variant, with P2 p95 and last; per-repo ledger .aitask-testmap/ledger.jsonl
  with run_id/id/status/duration_ms/head_sha per result; costs --update folds
  into aitestmap/costs/<hostclass>.yaml and truncates; per-invocation overhead
  rows; last_pass {sha, at, run_id} per id and a flake rate with
  flake_threshold; per-kind estimates; costs/predictions.yaml holds the last
  200 scored full runs {run_id, prediction_run_id, task, predicted,
  false_negatives, missed[]} (revised)
component_evidence_join: >-
  Evidence join (internal/stale + internal/gitx, reads internal/cost): for every
  edge whose stamped_blob differs from the current blob, collects last_pass shas
  per reached variant from the local ledger and committed costs (any host
  class), drops candidates from invocations with a cause or ids over the flake
  threshold, keeps shas that are ancestors of HEAD, and runs one git ls-tree per
  distinct sha; an edge is EVIDENCED when every reached variant has a sha whose
  source object id equals the current blob, otherwise STALE with the
  unevidenced variants listed; never rewrites - stale --confirm-evidenced is the
  explicit re-stamp and the only bulk confirmation an autonomous profile may
  run (revised: per variant)
component_feedback_tools: >-
  Feedback tools (internal/feedback): score splits a full run's failures into
  caught/missed for unit, variant and scoped rows against a prediction record;
  run --all and any unit: suite runner run auto-invoke score against the newest
  prediction for the same task and print PREDICTION_FALSE_NEGATIVES:<n> plus
  PREDICTION_MISSED:<id> lines, appending to costs/predictions.yaml; attribute
  records missing-edge/test-wrong/source-wrong for units and members,
  missing-axis-source for a facet value, missing-trigger/area-too-narrow for
  scoped rows, with task and run id, in registry/observed.yaml; readiness
  prints the run-gate admission facts (revised)
component_gates: >-
  Gates: three entries in gates_reference.yaml synced to gates.yaml -
  testmap_fresh (kind: procedure, verifier aitask-gate-testmap-fresh, no
  unlocks), testmap_check (machine, max_retries 0, timeout 120, unlocks
  [testmap_run]), testmap_run (machine, blocks_dependents, max_retries 1,
  timeout 1800); two bash verifiers on the tests_pass template mapping engine
  exits 0/1/2/75/64 and a missing engine to verifier 0/1/2/3/3/3; a project
  declares run_gate_admission in config.yaml and ait testmap readiness reports
  it, so a repo whose completion gate is a full suite keeps tests_pass and adds
  testmap_run only once admissible (revised)
component_skill: >-
  Skills: aitask-testmap teaches annotate (covers on a file or a testmap:unit
  member, or area/scope/trigger/reads), declaring an axis value's sources in
  axes.yaml, attribute before the gate, verify after editing an annotation,
  classify --suggest, and driving a project render loop from select --format
  tokens (thinking_app: piped into screenshot-tests.sh preview);
  aitask-gate-testmap-fresh is the procedure gate that runs stale --task, shows
  git diff <stamped_blob> <current_blob> per STALE row with the unevidenced
  variants, retargets STALE_PATH rows, re-stamps EVIDENCED rows, prompts on
  UNSTAMPED rows past bootstrap, never guesses UNKNOWN and never confirms a
  STALE row autonomously; Claude Code first, then ported (revised)
component_reference_runners: >-
  Reference runners built into the binary as ait-testmap runner <name>:
  bash-file, pytest (junitxml; testmap:batch no honoured), go-test (per-file
  -run regex, -json), gradle-class (--tests <lowering> batch, JUnit XML
  inverted to ids through the list table), suite (any command as one unit,
  optional child rows from a project post-processor), device (allocator
  handle); command:/cwd: overrides in runners.yaml; a project script of the
  same name shadows a builtin and explain shows which won; thinking_app ships
  tools/verification/testmap_runner.sh (screen-matrix: list from the two
  membership manifests + matrix_classes, run through screenshot-tests.sh
  unit-tests --tests) and wraps verify-active as a suite runner whose child
  rows come from lib/screenshot-diff-set.sh (revised)
component_variant_axes: >-
  NEW - Variant axes (internal/axes, read by registry, selectr, runner, cost):
  aitestmap/axes.yaml declares axes {name, facets[], values{value: {facet:
  v}}, sources{facet: {v: [globs]}}}; a runner's describe names the axis its
  variants live on and a token_format; list emits <unit>@<value> ids; the
  selector joins changed paths to facet values through sources and selects
  the variants carrying them (reason axis(<axis>.<facet>=<v>) <- <path>), or
  every variant of a unit reached by an edge, dep, rule or test-dep; costs,
  last_pass, evidence and score are per variant; check enforces
  DEAD_AXIS_SOURCE and UNKNOWN_VARIANT; the engine holds no project axis - the
  first consumer is thinking_app's matrix axis with facets locale/direction/geometry
  over its 10 recording matrices
component_go_engine: >-
  Go engine and CLI: engine/cmd/ait-testmap with internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform};
  Go 1.26 with pinned toolchain, CGO_ENABLED=0, -trimpath -buildvcs=false
  -ldflags -s -w -X version/commit/contract; deps gopkg.in/yaml.v3,
  bmatcuk/doublestar/v4, golang.org/x/sync only; stdlib flag verb table,
  syscall.Flock, os/exec git; line-protocol stdout, --json, per-verb exit
  contracts; never writes aitasks/, aiplans/, .aitask-data/ or a gate ledger
  and never invokes aitask_*.sh; tests against fixture repos in t.TempDir()
  including one fixture per opaque-scanner branch (revised: axes package,
  opaque fixtures)
component_binary_distribution: >-
  Binary distribution: engine/build.sh as the single build and matrix command;
  the engine job in release.yml (setup-go from engine/go.mod, go vet, go test,
  build.sh all) producing ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and
  ait-testmap_<V>_SHA256SUMS.txt attached by both action-gh-release steps with
  release needs: [plan, engine]; the unchanged VERSION-matches-tag guard; a new
  engine-check.yml on push/pull_request for engine/**; lib/platform_detect.sh;
  the shim's strict handshake (AIT_TESTMAP_BIN with override notice >
  AIT_ENGINE=dev slot at $AITASKS_HOME/engine/dev/ requiring <V>-dev+<sha> >
  $AITASKS_HOME/engine/v<V>/ requiring == VERSION > ENGINE_MISSING exit 3 with
  repair hint); tests test_testmap_shim.sh, test_platform_detect.sh and
  test_aitasks_home.sh; aidocs/framework/go_engine.md, a CLAUDE.md Engine
  block and a packaging_strategy.md paragraph; release-packaging.yml and nfpm
  arch: all untouched (revised: root)
component_engine_binary: >-
  Engine binary identity and budget: embeds version, commit and contract;
  version --json is the install-time self-check and also prints the resolved
  ENGINE:<path>; fixed-prefix structured output and --json; CONTRACT_MISMATCH
  refusal on registry files from a newer contract (contract 1 covers axes.yaml
  and member ids); performance budget pinned by go test -bench on golden
  registries for aitasks and a thinking_app-shaped fixture with a 2x regression
  failing CI; scanner and dependency pools capped at 8 (revised)
component_user_root: >-
  NEW - Per-user root: .aitask-scripts/lib/aitasks_home.sh exports
  AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks} and aitasks_engine_dir
  <version|dev>; sourced by the shim, aitask_setup.sh's install_engine_binary,
  aitask_engine.sh and the verifiers; never falls back to ~/.aitask/; ait setup
  creates $AITASKS_HOME/engine/ with mode 0755 and prints AITASKS_HOME:<path>
  in its summary beside the venv line so both roots are visible; ait engine
  prune walks only $AITASKS_HOME/engine/v*/; test_aitasks_home.sh pins the
  default, the env override, and that no framework script under this feature
  names ~/.aitask/
component_engine_packaging: >-
  Engine install and developer regeneration: install_engine_binary() in
  aitask_setup.sh, reached by ait setup and by ait upgrade through install.sh's
  --source-only path beside install_global_shim; uname mapping; .sha256 sidecar
  short-circuit; source order --local-engine > exact-version release asset >
  --engine-from-source > ENGINE_MISSING warning; sha256sum -c / shasum -a 256;
  atomic install to $AITASKS_HOME/engine/v<V>/; version --json must echo <V>;
  .dev-marked binaries never overwritten without --force-engine; --no-testmap /
  AIT_TESTMAP_FETCH=0 print TESTMAP_BINARY:skipped; .aitask-testmap/ gitignored
  by setup (the per-repo .aitask-* family is unchanged); aitask_engine.sh with
  ait engine build|test|cross|prune; tests/test_install_engine_binary.sh
  through a real install.sh --dir --local-engine asserting the $AITASKS_HOME
  path (revised: root)
component_freshness: >-
  Freshness: the per-edge @<date>/<blob10> stamp written only by verify,
  annotate and stale --confirm*, scoped to a member block where the unit is a
  member; last_pass anchors per id in the ledger and committed costs; the
  verify verb and verify --all-evidenced; config bootstrap_until, require_stamp,
  flake_threshold; the testmap_fresh procedure gate dispatched by the existing
  procedure-gate block before the change summary; the aitask-gate-testmap-fresh
  skill; not a git hook and not a Claude Code hook (revised: member scope)
component_suite_registry: >-
  Scoped-row registry and areas: registry/areas.yaml plus areas: blocks in hand
  files (seedable via areas --import-codemap); registry/_scoped.yaml rows
  {test, kind, runner, areas, globs, triggers, reads_from, needs, reviewed_at,
  line} where reads_from lists the helper files whose testmap:reads globs the
  row inherited; owns: by area name for hand-declared rows; the d1 join, kind
  ranking, suite budget (suite_budget_s default 600) with DEFERRED lines and
  budget-exempt triggers; check rules incl. DEAD_SCOPE and
  KIND_MISMATCH|CONVERT_TO_SUITE; ait testmap areas and classify --suggest;
  missing-trigger / area-too-narrow in attribute; a rule may select: a scoped
  test by name (revised: reads_from)
component_staleness_tool: >-
  Staleness tool (internal/stale): stale --task --changes - | --all prints
  SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION
  lines with %25/%7C encoding; a STALE row on a unit with variants carries a
  trailing |<unevidenced variants> field; content states exit 0, --strict exits
  1 on STALE_PATH; compares blob digests of the working tree only, consults the
  per-variant evidence join, adds rename hints and culprit task ids from git
  log --name-status -M when history is reachable; mutates stamps via --confirm,
  --confirm-source, --confirm-evidenced, --retarget through the rewriter with
  a re-scan of touched files (revised)
component_broad_test_scopes: >-
  Broad-test scheduling and staleness policy: kind integration|e2e|device
  selects the scoped association form; broad_after_unit: true waves run scoped
  rows only after a green unit wave; device_policy: filter_by_resource default;
  scoped rows are exempt from per-edit digest staleness, with STALE_AREA as the
  evidence-based drift signal and REVIEW_DUE as an opt-in cadence; attribute
  widens areas by evidence; covers on a scoped row is allowed for digest-stamped
  fixture pins; a suite row (thinking_app's verify-active) may report child rows
  so its goldens feed evidence and the prediction ledger without being selected
  individually
# ---------------------------------------------------------------------------
# tradeoff_* (inherited unless marked)
# ---------------------------------------------------------------------------
tradeoff_computed_vs_prose: >-
  Advantage: selection is computed, explained and scored rather than
  remembered; blast radius becomes data instead of prose - including the
  "localized screen change may use preview, shared component must run the full
  gate" rule, which becomes an axis join plus an import-scanner fan-out that
  select prints with a reason per variant
tradeoff_fail_closed_bootstrap_cost: >-
  Disadvantage: fail-closed enforcement means bootstrapping each repo requires
  an explicit waiver pass before testmap_check can be enabled and a first green
  full run before require_stamp and --strict are turned on; a repo with a
  whole-suite completion gate additionally needs the readiness criteria met
  before testmap_run gates anything; mitigated by check --strict off until
  enabled, bulk stamping via stale --all --confirm-evidenced, and the ledger
  filling itself from the full runs the repo already performs
tradeoff_static_scanner_overselection: >-
  Disadvantage: static scanners overselect on hot files and cannot see runtime
  coupling; a shared component (thinking_app's ui/components/*) fans out to
  most screens on every matrix, which is the correct answer and close to a
  full run; kind ranking, the suite budget and --budget-s trim scoped rows
  first, the android-res symbol scanner narrows a catalog edit to the screens
  naming the changed keys, and a project scanner plugin can narrow a hot
  resource file
tradeoff_resource_declaration_completeness: >-
  Risk: declared resources are only as complete as the declarations; an
  undeclared interference is invisible until a full run or a probe finds it;
  serial-by-default at bootstrap means declarations are reviewed in the
  schedule report before concurrency is trusted
tradeoff_registry_directory_complexity: >-
  Disadvantage: a merged registry directory needs more CLI logic than a single
  file would - now six tables, two generated files and an id grammar with
  member and variant fragments; kept to one directory with one merge rule in
  one Go package with golden tests, and the axis table is empty for every
  project that declares none
tradeoff_attribution_risk: >-
  Risk: an agent that edits sources without attributing produces a map that
  looks current and is not; narrowed - such a source shows as STALE in the
  next task touching it and as a stale mark on every selection, and in a repo
  that runs a full suite at completion every miss is counted by the automatic
  score - but a new coupling with no edge at all is still only caught on a
  full run
tradeoff_batch_misreport_risk: >-
  Risk: a batch runner that misreports per-unit results corrupts attribution,
  cost and evidence (a false pass could manufacture an EVIDENCED row); the
  inversion from JUnit classname/name to variant ids is a second place a
  runner can misreport; mitigated by units_expected/units_reported
  reconciliation per id, a row that inverts to no registered id being a
  mechanism failure, and no line from an invocation with a cause ever anchoring
tradeoff_two_toolchains: >-
  Disadvantage: bash and Go in one framework; mitigated by the boundary rule
  (parse/walk/match/digest/schedule in Go; gate ledger, task file and shell
  environment in bash; builtins exec configured commands and never source
  shell state), the engine-check.yml job, and Go source confined to engine/
  and excluded from the tarball so target projects never need Go
tradeoff_setup_network_fetch: >-
  Disadvantage: ait setup gains the framework's first self-downloaded release
  asset; mitigated by reusing the CDN URL family install.sh already uses,
  SHA256SUMS verification, the .sha256 sidecar, --no-testmap /
  AIT_TESTMAP_FETCH=0, the shim never fetching on its own, and setup never
  depending on the binary for anything else
tradeoff_area_glob_coarseness: >-
  Disadvantage: area and scope globs are coarser than edges - a broad area
  over-selects its tests on every edit inside it and a scoped test depending
  on a file outside its scope is under-selected until a full run scores it;
  mitigated by the suite budget with explicit DEFERRED lines, budget-exempt
  triggers and reads globs for known sharp edges, and the missing-trigger /
  area-too-narrow attribution path
tradeoff_flaky_pass_anchors: >-
  Risk: a flaky pass anchors evidence as surely as a real one; mitigated by
  per-run status in the ledger so costs exposes a flake rate per id, and an id
  above flake_threshold is excluded from the evidence join
tradeoff_strict_version_handshake: >-
  Risk: the binary must match .aitask-scripts/VERSION exactly, so an ait
  upgrade on a host that cannot fetch leaves ait testmap refusing to run until
  a matching binary is supplied; intended fail-closed behaviour, and the error
  names the fix (ait setup, AIT_TESTMAP_BIN, ait engine build) and the
  $AITASKS_HOME path it looked in
tradeoff_engine_speed_enables_per_task_use: >-
  Advantage: sub-second select/check/stale on a 720-test repo, and sub-250 ms
  select over 300 variants, makes selection overhead negligible against the
  shortest test and lets check run at every commit step; a bash+Python engine
  would spend seconds in start-up and YAML parsing first
tradeoff_real_scheduler: >-
  Advantage: goroutines plus flock(2) give correct cross-worktree contention
  and a critical-path report; the shell suite and the pytest lane get the
  enforced do-not-overlap that is only a comment today, once a project flips
  concurrency from the serial bootstrap default after reviewing the schedule
  report
tradeoff_noarch_packages_preserved: >-
  Advantage: Homebrew, AUR, .deb, .rpm and the tarball ship nothing compiled;
  the per-arch concern is contained in one release job and one setup function
tradeoff_compiled_component_cost: >-
  Disadvantage: the framework gains a compiled component - contributors
  touching the engine need Go, a release fails if go test fails, install gains
  a fetch and checksum step; mitigated by a single build.sh matrix, ait engine
  build, and the engine being optional until a testmap gate is enabled
tradeoff_engine_version_skew: >-
  Disadvantage: one user with several projects on different framework versions
  keeps several ~10 MB binaries under $AITASKS_HOME/engine/; mitigated by
  exact-version resolution in the shim (never newest-wins) and ait engine prune
  against the project registry, never a count-based prune
tradeoff_stamp_churn: >-
  Disadvantage: confirming stamps rewrites test files, so a source named by 72
  tests could yield a 72-file diff; mitigated - EVIDENCED rows need no rewrite
  until someone chooses --confirm-evidenced, --confirm-source makes a
  deliberate re-stamp one commit, only confirmation rewrites, member blocks
  keep a screen's stamps in one file (ScreenFixtures.kt) so thinking_app's
  fan-out is a one-file diff, and KIND_MISMATCH nudges fan-out toward a scope
tradeoff_broad_scope_coarseness: >-
  Disadvantage: a test scoped to a large area is selected for any change
  inside it; mitigated by ranking last at its distance, running only after a
  green unit wave, being cut first by the suite budget with the cut printed as
  DEFERRED, and the cost visible in schedule
tradeoff_autonomous_confirmation_weak: >-
  Risk: treating a green test as evidence that a coverage claim still holds is
  weaker than review; narrowed - the only autonomous confirmation is
  --confirm-evidenced, which requires a pass on every reached variant whose
  tree held the current bytes of the specific source, records confirmed_by:
  <run_id>, and is re-opened by a later score miss; a STALE row is never
  confirmed without a human
tradeoff_engine_absent_on_host: >-
  Risk: an unsigned macOS binary or a blocked download leaves a host without
  an engine; mitigated by ENGINE_MISSING naming the $AITASKS_HOME path and
  repair verb, --engine-from-source and --local-engine fallbacks, and the
  testmap gates exiting 3 (error), never skip, when the engine is absent
tradeoff_evidence_requires_reachable_history: >-
  Risk: the evidence join can only suppress a STALE row when the anchoring
  commit is reachable, so a depth-1 CI clone or a fresh shallow worktree sees
  the precise digest verdict with no self-healing; the safe direction, and the
  reason --strict fails only on STALE_PATH; a repo-wide stale --all --strict
  job should run on a full clone or accept STALE noise
tradeoff_two_user_roots: >-
  NEW - Disadvantage: until the legacy tenants move, a host carries ~/.aitask/
  (venv, python, bin, uv) and ~/.aitasks/ (engine) side by side, and a user
  who deletes one to "reset" the framework removes half of it; mitigated by
  one variable (AITASKS_HOME) with one library owner, ait setup printing both
  roots in its summary, ENGINE_MISSING naming the exact path, and a
  test that fails if any script of this feature names ~/.aitask/
tradeoff_axis_projection_coarseness: >-
  NEW - Disadvantage: the default axis join is file-level - a one-key edit to
  values-ru/strings.xml selects every screen on both ru matrices (about 65
  variants) rather than the screens naming that key; sound but 2/10 of the
  matrices rather than 1/50 of the screens; mitigated by the opt-in android-res
  symbol scanner (keys changed -> referencing Kotlin files -> member units), by
  select --format tokens feeding the project's own render loop so the
  over-selection costs a preview rather than a gate, and by the budget knobs
tradeoff_whole_run_filter_soundness: >-
  NEW - Risk: where a runner's filter restricts a whole test run (Gradle
  --tests on thinking_app's single testDebugUnitTest task), every class not
  selected is silently not run, so a narrow selection is only as sound as the
  test-side closure, the reads globs and the opaque contract; mitigated by list
  enumerating the whole universe so an unlisted class fails check, the
  test-dep closure over abstract bases and helpers, testmap:reads on tree-scanning
  helpers (57 SourceFence classes stay selected on any Kotlin change), ESCALATE
  on opaque files, red-proof fixtures per branch, and the project keeping its
  full suite as the completion gate until readiness is met
tradeoff_member_annotation_drift: >-
  NEW - Risk: a member unit's annotation lives in a block keyed by name
  (testmap:unit Welcome) and the runner's list keys the same member by another
  artifact (the golden manifest's Welcome_<matrix>.png); a rename on one side
  orphans the other; mitigated by check reporting a listed member with no
  block (UNANNOTATED_MEMBER) and a block with no listed member (DEAD_MEMBER),
  both fail-closed, and by scan --apply refusing rather than guessing
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

This proposal keeps the baseline's architecture — one static Go binary
`ait-testmap` built from `engine/`, per-edge blob-digest stamps healed by a
committed run-evidence join, and broad tests as scoped rows in one registry
directory under an explicit suite budget — and corrects it on two points.

**1. The per-user install root is the framework's own name.** The framework is
`aitasks`; its per-user roots that already exist are `~/.config/aitasks/`
(the project registry) and `${XDG_CACHE_HOME:-~/.cache}/aitasks/` (caches).
The baseline placed the engine under `~/.aitask/engine/v<VERSION>/`, copying
the directory the Python venv lives in. Here the engine installs under
**`~/.aitasks/engine/v<VERSION>/`** (dev slot `~/.aitasks/engine/dev/`),
resolved through one variable, `AITASKS_HOME`, owned by one library file. The
legacy `~/.aitask/` tenants (`venv/`, `python/`, `bin/`, `uv/`, `dev_tier`,
`update_check` — 49 framework files name that path) are neither moved nor read
by this feature; the two roots coexist and a later change may migrate the rest.
The per-repository `.aitask-testmap/` directory keeps the `.aitask-*` family
every per-repo directory already uses (`.aitask-data`, `.aitask-gates`,
`.aitask-explain`, `.aitask-history`, `.aitask-shadow`, …); only the per-user
root changes.

**2. A project's own test subdivision becomes a first-class unit.**
thinking_app's verification is organised around *screens rendered on
matrices*. Each of 49 `ScreenFixture("Name") { … }` bodies in
`ScreenFixtures.kt` composes one production screen; each of ten recording
matrices (`pixel5_rtl`, `pixel5_ltr`, `shortPhone_rtl`, `shortPhone_ltr`,
`imeProxy_rtl`, `bidiSampler_rtl`, `pixel5Ru_ltr`, `shortPhoneRu_ltr`,
`pixel5Ar_rtl`, `shortPhoneAr_rtl`) is a `@Config(qualifiers = …)` subclass of
an abstract base whose `@Test fun welcome() = capture(ScreenFixtures.welcome())`
is dispatched once per matrix; the identity of a test is the golden
`<Screen>_<matrix>.png`, and a matrix token encodes **locale × direction ×
geometry** (`he-rIL-ldrtl-w393dp…`, `ru-rRU-ldltr-w360dp…`). The catalog is
297 goldens: 50 primary plus 247 secondary (47 `pixel5_ltr`, 47
`shortPhone_ltr`, 17 `shortPhone_rtl`, 6 `imeProxy_rtl`, 1 `bidiSampler_rtl`,
48 `pixel5Ru_ltr`, 17 `shortPhoneRu_ltr`, 47 `pixel5Ar_rtl`, 17
`shortPhoneAr_rtl`). The routing *token → (matrix, class, method, png)* is a
solved lookup in `tools/verification/lib/screenshot-review.sh`
(`known_matrices`, `matrix_classes`, `preview_resolve_token`) and the harness
already narrows along it: `screenshot-tests.sh preview [<matrix>:]<Screen>…`
renders named screens with no verdict, `verify-active-rtl` gates on a matrix
subset through `verify_active_tiered`, and `unit-tests --tests <fqn>` runs
named classes. What does not exist anywhere in that repository, in its own
words (`aidocs/testing/change-aware-verification.md`, t381), is the edge
*production composable → screen token*; and what constrains any selector is
that Gradle's `--tests` filters the **whole** `testDebugUnitTest` run, so a
narrow selection takes responsibility for every class in the suite.

**Does the baseline support this mapping?** Partially, and the gaps are
structural rather than configurational:

| the subdivision needs | the baseline has | gap |
|---|---|---|
| a unit that is *a screen*, finer than a test file and dispatched through ten classes | units keyed by path; `gradle-class` runner with `unit: class` | no id for `Welcome`; annotating the abstract base's method covers all matrices and cannot be lowered to one |
| a change to `values-ru/**` selecting *every screen on the ru matrices only* | edges, areas, scopes, triggers, rules | nothing expresses "the ru facet of the matrix axis"; the nearest fit is a scope over every class, i.e. a full run |
| a change to `WelcomeScreen.kt` selecting *Welcome on all ten matrices* | `covers` edges + Kotlin import scanner | expressible only as ten class-level edges, and the runner cannot select one method of a class |
| whole-run soundness: the 57 `SourceFence` classes that scan the Kotlin tree, and `ComposeScreenTest` reached by 84 test files | scoped rows with triggers; d2+ reverse deps | expressible with 57 annotations; the test-side closure (abstract bases, helpers, `app/src/test/resources/`) is implied by "d2 through the dependency graph" but never stated for test files |
| a *fail-closed* Kotlin graph — `inline`, `const val`, DI, reflection, star imports defeat an import parser | a Kotlin import scanner, `escalate` rules, `UNKNOWN:` refusal | the scanner never says "I cannot see through this file", so a NARROW answer is not trustworthy on those constructs |
| a prediction ledger fed by *every* full run (`PREDICTION_FALSE_NEGATIVES:<n>`) | `score --run --prediction` on demand | not automatic, and a suite-wrapped `verify-active` reports one unit, so its per-golden diff set is invisible to `score` |

The additions that close them, all generic and all empty for a project that
declares none: **member units** (`<path>#<member>`, annotation blocks opened by
`testmap:unit`), **variant axes** (`aitestmap/axes.yaml`, `<unit>@<variant>`,
facet-valued sources), a **runner `list` that emits ids with their lowering**
and a `run` that inverts its tool's report back to ids, a **test-side
dependency closure** with `testmap:reads` on tree-scanning helpers, an
**opaque contract** on the Kotlin scanner that escalates instead of narrowing,
**suite child rows** so a wrapped full suite still feeds evidence, and
**automatic scoring** of the newest prediction on every full run with a
committed `costs/predictions.yaml`. The optional `android-res` symbol scanner
is the reserved `symbols` slot's first consumer: it turns "`values-ru/strings.xml`
changed" into "these three keys changed, referenced by these Kotlin files,
composed by these screens", so the answer becomes *those screens × the ru
matrices* rather than *every screen × the ru matrices*.

Everything else — the Go module, the release and install flow, the stamp and
evidence model, scoped rows, the scheduler, the gates and skills — is the
baseline's, restated where a path or an id grammar changed and otherwise
carried unchanged.
<!-- /section: overview -->

<!-- section: mandate_answers [dimensions: requirements_engine_packaging, requirements_dev_rebuild_from_source, component_engine_packaging, component_binary_distribution, assumption_one_engine_per_framework_version, component_selector, component_runner_contract] -->
## The Two Corrections, Stated Precisely

### Install root: `~/.aitasks/engine/`

```
$AITASKS_HOME                      default $HOME/.aitasks   (env override; never falls back to ~/.aitask)
  engine/
    v<VERSION>/ait-testmap         exact-version slot the shim requires == .aitask-scripts/VERSION
    v<VERSION>/ait-testmap.sha256  sidecar; ait setup short-circuits when it matches the release SHA256SUMS
    dev/ait-testmap                ait engine build output; version must read <V>-dev+<sha>
    dev/.dev                       {source, commit} marker; never overwritten without --force-engine
```

Owner: `.aitask-scripts/lib/aitasks_home.sh` — `AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`,
`aitasks_engine_dir() { printf '%s/engine/%s' "$AITASKS_HOME" "$1"; }` — sourced
by `aitask_testmap.sh` (the shim), `install_engine_binary()` in
`aitask_setup.sh`, `aitask_engine.sh`, and both gate verifiers. Every message
that names the slot (`ENGINE_MISSING:<path>`, `ENGINE_BUILT:<path>|<commit>`,
`TESTMAP_BINARY:installed:<path>`) prints the resolved path, and `ait setup`'s
summary prints `AITASKS_HOME:<path>` on the line after the venv line so a host
with both roots sees both. `ait engine prune` walks `$AITASKS_HOME/engine/v*/`
only. Tests: `tests/test_aitasks_home.sh` (default, env override, and a grep
that fails if any file this feature adds names `~/.aitask/`),
`tests/test_testmap_shim.sh` and `tests/test_install_engine_binary.sh` assert
the new path. Docs (`aidocs/framework/go_engine.md`, the `CLAUDE.md` Engine
block, `packaging_strategy.md`) name `~/.aitasks/engine/` and state in one
sentence that `~/.aitask/` holds the Python tenants and is unrelated.

Not changed: `.aitask-testmap/` (per-repo runs and ledger), `.aitask-gates/`
(verifier logs), `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/` (already
`aitasks`), `${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/` (locks),
`~/.config/aitasks/projects.yaml` (prune's source of truth).

### Screen × localization as a unit

The unit id grammar becomes `<path>[#<member>][@<variant>]`:

- `<path>` — a test file, the baseline's unit (`tests/test_gate_pass.sh`).
- `#<member>` — a named block inside the file, opened by a `testmap:unit
  <Member>` annotation (`app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt#Welcome`).
  A member has its own `covers` edges, stamps, costs and evidence; the file
  itself is not a unit when it has members.
- `@<variant>` — a value of the axis the unit's runner declares
  (`…ScreenFixtures.kt#Welcome@pixel5Ru_ltr`). Variants are enumerated by the
  runner's `list`, never written by hand; they share the member's annotations
  and have their own cost, `last_pass` and evidence rows.

```yaml
# aitestmap/axes.yaml  (thinking_app; the engine ships no axis of its own)
contract: 1
axes:
  matrix:
    facets: [locale, direction, geometry]
    values:
      pixel5_rtl:       {locale: he, direction: rtl, geometry: pixel5}
      pixel5_ltr:       {locale: en, direction: ltr, geometry: pixel5}
      shortPhone_rtl:   {locale: he, direction: rtl, geometry: shortPhone}
      shortPhone_ltr:   {locale: en, direction: ltr, geometry: shortPhone}
      imeProxy_rtl:     {locale: he, direction: rtl, geometry: imeProxy}
      bidiSampler_rtl:  {locale: he, direction: rtl, geometry: pixel5}
      pixel5Ru_ltr:     {locale: ru, direction: ltr, geometry: pixel5}
      shortPhoneRu_ltr: {locale: ru, direction: ltr, geometry: shortPhone}
      pixel5Ar_rtl:     {locale: ar, direction: rtl, geometry: pixel5}
      shortPhoneAr_rtl: {locale: ar, direction: rtl, geometry: shortPhone}
    sources:                                   # facet value <- source globs: the axis edges
      locale:
        he: ["app/src/main/res/values-iw/**", "app/src/main/res/raw-iw/**", "app/src/main/res/font/heebo_*.ttf"]
        en: ["app/src/main/res/values-en/**", "app/src/main/res/raw-en/**", "app/src/main/res/font/roboto_*.ttf"]
        ru: ["app/src/main/res/values-ru/**", "app/src/main/res/raw-ru/**", "app/src/main/res/font/roboto_*.ttf"]
        ar: ["app/src/main/res/values-ar/**", "app/src/main/res/raw-ar/**", "app/src/main/res/font/cairo_*.ttf"]
      # direction and geometry have no sources: they are test-side constants in
      # ScreenshotTestHarness.kt, reached through the test-dep closure (every screen class
      # imports them), which selects every variant — the right answer for a geometry edit.
```

Sources every locale reads — `app/src/main/res/values/**` (the generated
Hebrew mirror plus `system_strings.xml` and `donottranslate.xml`),
`utils/TypeScale.kt` (`RussianTypeScale`, `EnglishTypeScale`, `typeScaleFor`),
`utils/Fonts.kt`, `ui/components/AppRoot.kt` (`AppLocalePolicy`) — are not axis
sources. They reach screens through ordinary edges or the import scanner and
therefore select every variant, which is correct: a `typeScaleFor` edit can
change any locale's render.

The selection rule with axes (formal, so the runner and `explain` agree):

1. An **edge, rule, dependency hop or test-dep** that reaches a unit selects
   **all** of its variants (`#Welcome@*`), reason as today.
2. A changed path matching an **axis source** selects, for every unit whose
   runner lives on that axis, the variants whose facet carries the value
   (`*@pixel5Ru_ltr`, `*@shortPhoneRu_ltr`), reason
   `axis(matrix.locale=ru) <- app/src/main/res/values-ru/strings.xml`, at
   distance 1.
3. When the `android-res` symbol scanner is enabled and the before content is
   reachable, rule 2 is narrowed to the members whose forward closure names a
   changed key: `axis(matrix.locale=ru)[timer_ring_label,daily_summary] <-
   values-ru/strings.xml`.
4. Several hits union; there is no intersection semantics, because each hit is
   a real blast radius.
5. Cost, ranking, budget, `last_pass`, evidence and `score` operate on the
   selected variant ids; stamps and annotations operate on the member.

thinking_app's runner lowers each variant to Gradle exactly as `preview` does
today — every class enrolled for the matrix gets `--tests <class>.<method>`
(the non-owning filters are inert because Gradle fails only when the whole
include set matches nothing) — and inverts JUnit `classname`/`name` back to the
variant id through the same table after the run.
<!-- /section: mandate_answers -->

<!-- section: architecture [dimensions: component_go_engine, component_engine_binary, component_binary_distribution, component_engine_packaging, component_registry_loader] -->
## Architecture

### Process boundary

```
ait testmap <verb> ...                          (user / skill / gate verifier)
 └─ .aitask-scripts/aitask_testmap.sh           bash shim, ~35 lines; sources lib/aitasks_home.sh
      │   resolve  $AIT_TESTMAP_BIN  >  AIT_ENGINE=dev → $AITASKS_HOME/engine/dev/ait-testmap
      │            >  $AITASKS_HOME/engine/v$(cat .aitask-scripts/VERSION)/ait-testmap
      │   verify   `<bin> version` == VERSION (dev: <VERSION>-dev+<sha>), else ENGINE_MISSING:<path> / ENGINE_MISMATCH, exit 3
      │   for --task verbs: aitask_change_surface.sh list <id>  |  <bin> <verb> --changes - ...
      └─ $AITASKS_HOME/engine/v<VERSION>/ait-testmap --repo-root "$AIT_DIR" <verb> ...
           internal/registry        merge aitestmap/registry/*.yaml + axes.yaml → six tables; id grammar; owns: routing; check rules
           internal/axes            axis table, facet lookup, source-glob join, variant materialisation from runner list
           internal/annot           grammar v3 scanner (unit blocks, reads), stamp reader, line-targeted rewriter
           internal/deps            bash/python/go/kotlin/gradle scanners (kotlin: opaque contract, test roots) + android-res symbols + plugins
           internal/changesurface   parser for BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines; before-blob resolution
           internal/selectr         graded walk, rules, variant expansion, axis join, test-dep, ESCALATE, scoped join, budget, formats
           internal/sched           errgroup waves, flock slot files, admission/allocator exec, broad_after_unit, schedule report
           internal/runner          list TSV codec, manifest/results codec (child rows), bindings, builtin: runners, id inversion, exit mapping
           internal/cost            Welford + P² per id, ledger, fold, last_pass, flake, predictions.yaml
           internal/feedback        score (auto on full runs), attribute, readiness
           internal/stale           digest compare, per-variant evidence join, classes, confirm/retarget
           internal/gitx            git via os/exec: rev-parse, ls-tree, merge-base --is-ancestor, log --name-status -M, show <sha>:<path>
           internal/platform        os/arch naming shared with engine/build.sh
             ├─ exec:  git, runner scripts or builtin runners, admission/allocator commands, scanner plugins
             └─ files: aitestmap/** (committed) · .aitask-testmap/ (runs, ledger; gitignored) ·
                       ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/ · ${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/
.aitask-scripts/lib/aitasks_home.sh             AITASKS_HOME, aitasks_engine_dir  (new; the only owner of the per-user root)
.aitask-scripts/aitask_gate_testmap_check.sh    machine verifier  <task> <attempt> <run-id> → check --task
.aitask-scripts/aitask_gate_testmap_run.sh      machine verifier  → select --include-stale → schedule → run
.aitask-scripts/aitask_engine.sh                ait engine build | test | cross | prune   (framework developers)
.claude/skills/aitask-gate-testmap-fresh/       procedure gate: consumes `stale` lines, fixes annotations, `verify`
.claude/skills/aitask-testmap/                  agent skill: annotate, attribute, waive, verify, classify, axes, tokens
engine/                                          Go source — framework repo only; excluded from the release tarball
```

The boundary rule is unchanged: parse, walk, match, digest and schedule in Go;
gate ledger, task file and shell environment in bash; the binary never writes
`aitasks/`, `aiplans/`, `.aitask-data/` or a gate ledger and never invokes
`aitask_*.sh`; builtin runners exec what `runners.yaml` gives them. The
thinking_app lowering (`matrix_classes`, `preview_resolve_token`) stays in
that repository's bash, behind its own runner script — the engine sees ids and
lowerings as opaque strings.

### Go module (`engine/`)

Unchanged from the baseline (`go 1.26`, pinned toolchain, `CGO_ENABLED=0`,
`-trimpath -buildvcs=false -ldflags "-s -w -X main.version -X main.commit -X
main.contract=1"`, `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
`golang.org/x/sync`, stdlib `flag`, `syscall.Flock`, `os/exec` git) plus one
package, `internal/axes`, and one fixture family under `testdata/opaque/` —
one Kotlin file per opaque branch, each with a test that disables that branch
and asserts the verdict flips from `ESCALATE` to a narrow selection (the
red-proof shape the thinking_app design record demands).

### Where state lives

| data | location |
|---|---|
| registry, runners, resources, areas, **axes**, committed costs and **predictions** | `aitestmap/**` in the code tree |
| run outputs, prediction records, local ledger | `.aitask-testmap/runs/<run-id>/`, `.aitask-testmap/ledger.jsonl` (gitignored; `AIT_TESTMAP_DIR` override) |
| gate logs | `.aitask-gates/<task>/<gate>_<run-id>.log` |
| dependency-scan cache | `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` |
| host-scope locks | `${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/<resource>.<slot>.lock` |
| engine binaries | **`$AITASKS_HOME/engine/v<VERSION>/ait-testmap` (+ `.sha256`), `$AITASKS_HOME/engine/dev/ait-testmap` (+ `.dev`)** — never on PATH |

### Registry directory (one directory, six tables)

```
aitestmap/
  config.yaml            unit_covers_max: 8 · suite_budget_s: 600 · bootstrap_until · require_stamp · broad_review_days: 0
                         concurrency: serial|parallel · broad_after_unit: true · device_policy: filter_by_resource
                         host_class · flake_threshold: 0.2 · symbol_scanners: [] (thinking_app: [android-res])
                         run_gate_admission: {min_scored_full_runs: 0, max_false_negatives: 0, approved_by: null}
  axes.yaml              optional; declared axes with facets, values and facet-valued sources
  runners.yaml           runner repository (builtin: or script), bindings, command:/cwd: overrides
  resources.yaml         named resources (mutex / semaphore / admission / allocator; host / worktree / run)
  registry/
    _scanned.yaml        generated: unit and member edges with @date/blob10 stamps; variants: {axis, values[]} per member
    _scoped.yaml         generated: broad rows (areas, globs, triggers, reads_from, reviewed)
    observed.yaml        written only by attribute: observed edges, axis sources, area members, triggers
    areas.yaml           hand-written named glob sets
    <area>.yaml          hand-written: owns:, edges, scopes, rules, waivers, areas:
  costs/<hostclass>.yaml Welford n/mean/sd/p95/last + last_pass {sha, at, run_id} + flake per id (variants included)
  costs/predictions.yaml last 200 scored full runs: {run_id, prediction_run_id, task, predicted, false_negatives, missed[]}
  runners/*.sh           optional project runners
  scanners/*             optional executable scanner plugins
```

Merge rule as in the baseline (every `registry/` file contributes rows to the
same tables; `owns:` routing; `contract:` per file with `CONTRACT_MISMATCH`
refusal). The axis table is loaded from `axes.yaml` only; `check` adds
`DEAD_AXIS_SOURCE:<axis>.<facet>=<v>|<glob>` (a source glob matching no file),
`UNKNOWN_VARIANT:<id>` (a listed variant outside the axis's values),
`UNANNOTATED_MEMBER:<id>` (listed by a runner, no `testmap:unit` block) and
`DEAD_MEMBER:<file>#<member>` (a block no runner lists).
<!-- /section: architecture -->

<!-- section: data_flow [dimensions: component_selector, component_staleness_tool, component_freshness, component_evidence_join, component_cost_ledger, component_engine_packaging, component_binary_distribution, component_runner_contract, component_feedback_tools] -->
## Data Flow

### Authoring → registry

```
test files ──annotations──▶ ait testmap scan --apply ──▶ registry/_scanned.yaml   unit/member edges {test, covers, from, line, stamped_at, stamped_blob, variants}
                                                     └▶ registry/_scoped.yaml    broad rows {test, kind, areas, globs, triggers, reads_from, needs, reviewed_at, line}
runner list (TSV) ─────────────────────────────────▶ the unit universe: file ids, member ids, member@variant ids, each with its lowering
hand files + areas.yaml + axes.yaml + observed.yaml ▶ merged registry (in memory, six tables)
```

`scan` asks every runner's `list` for the ids it owns, reads each annotated
file once, splits it into blocks at `testmap:unit` lines, matches `testmap:`
lines per comment leader (and Python module docstrings), refuses unknown keys
with a line number, joins member blocks to listed member ids by name, and
rewrites each generated file only when content changed. A `testmap:reads
<glob>` line is legal only in a file no runner lists (a helper) and lands in
an in-memory helper table.

### Task → selection → run

```
aitask_change_surface.sh list t1234 ──▶ BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines  (the shim pipes)
        ▼
ait-testmap select --task t1234 --changes - --include-stale [--format lines|json|tokens] --run <run-id>
        ├─ UNKNOWN: present ──▶ refuse (exit 1, lines echoed);  exclude aitasks/ aiplans/ .aitask-data/ .aitask-gates/
        ├─ opaque: a changed file the kotlin scanner marked opaque ──▶ ESCALATE:<file>|<reason>|<runners>  → every id of those runners at d0
        ├─ walk:  d0 changed tests + escalation
        │         d1 unit/member edges · axis sources (facet value → matching variants; symbol-narrowed when enabled)
        │            · test-dep (changed file in a unit's own test-file forward closure, incl. helpers' reads globs) · scoped join
        │         d2.. reverse-dependency hops from the blob-keyed cache · rules inject select/implies/escalate
        ├─ expand: a hit on a member → all its variants; an axis hit → the carrying variants only; union across hits
        ├─ stale: `stale` mark when a selecting edge's stamped_blob ≠ current blob and any reached variant lacks evidence
        ├─ rank:  distance → kind (unit < integration < e2e < device) → est. cost ascending (per variant)
        ├─ budget: broad rows in p95 order until suite_budget_s; remainder DEFERRED:<test>|budget; trigger and reads hits never deferred
        └─ write .aitask-testmap/runs/<run-id>/{selection.json, prediction.json}
           --format tokens: one line per selected variant in the runner's token_format (thinking_app: <matrix>:<Screen>)

ait-testmap schedule --run <run-id>  ──▶ waves, holds, critical path; variants of one runner batch into one invocation
ait-testmap run --run <run-id>       ──▶ manifest.json {units: [{id, lowering, timeout_s}]} → runner → results.jsonl (per id) + runner.json
        ├─ wave 1: unit kind · wave 2+: broad kinds only if wave 1 is green (broad_after_unit)
        ├─ a suite runner may add child rows {id, status, parent: <suite id>} for registered ids it can attribute
        ├─ every result row → ledger.jsonl {run_id, id, status, duration_ms, head_sha}
        ├─ units_expected ≠ units_reported, or a report row inverting to no registered id → mechanism failure, never a pass
        └─ run.json: aggregate status; exit 0 / 1 / 2 / 75 / 64
```

### Results → evidence → cost → prediction ledger

Every passing row whose invocation has no `cause`, for an id under the flake
threshold, advances that id's `last_pass {sha, at, run_id}`. `costs --update`
folds the ledger into `costs/<hostclass>.yaml`. **After any full run** —
`run --all`, or a `unit: suite` runner run that the project marks `full: true`
in `runners.yaml` (thinking_app's `verify-active`) — the engine looks up the
newest `prediction.json` for the same task (or, with no task, the newest on
this host for this HEAD's first-parent chain), scores it, and prints:

```
PREDICTION_SCORED:<prediction_run_id>|<full_run_id>
PREDICTION_FALSE_NEGATIVES:<n>
PREDICTION_MISSED:<id>            one per failed id the prediction did not select (a changed golden is a failure here)
```

appending `{run_id, prediction_run_id, task, predicted, false_negatives,
missed[]}` to `costs/predictions.yaml` (capped at 200 rows, oldest dropped).
No prediction → `PREDICTION_SCORED:none` and nothing appended. The count is a
plain non-negative integer and never a verdict; it is what a project cites
when deciding whether the selective gate is admissible.

### Post-implementation → staleness → fix in the same commit

As in the baseline (`stale --task --changes -` → `STALE_PATH` /
`STALE` / `EVIDENCED` / `UNSTAMPED` / `STALE_AREA` / `REVIEW_DUE` /
`UNKNOWN` / `DISPLAY` / `DECISION`), with one change: for a member with
variants the evidence join runs per reached variant, and the row reads

```
STALE:<test>|<source>|<stamped_at>|<stamped_blob>|<current_blob>|<unevidenced variants>
EVIDENCED:<test>|<source>|<stamped_blob>|<current_blob>|<run_sha>|<run_id>       every reached variant evidenced
```

where `<unevidenced variants>` is a comma list (`pixel5Ar_rtl,shortPhoneAr_rtl`)
or `-` for a unit without variants. The procedure gate shows the same
`git diff <stamped_blob> <current_blob>` and, for a variant-bearing row, names
the matrices that have not been rendered against the current bytes — which is
exactly the `preview <matrix>:<Screen>` invocation the agent should run before
confirming.

### Release → host

Unchanged in CI (one `engine` job; `engine-check.yml`; `ait-testmap_<V>_<os>_<arch>`
+ `SHA256SUMS`). Host side:

```
ait setup   (or ait upgrade → install.sh --force → aitask_setup.sh --source-only → install_engine_binary)
   ├─ source lib/aitasks_home.sh; mkdir -p "$AITASKS_HOME/engine"
   ├─ os/arch via lib/platform_detect.sh; else ENGINE_UNSUPPORTED (skip, exit 0)
   ├─ $AITASKS_HOME/engine/v<V>/ait-testmap exists and .sha256 sidecar matches → return
   ├─ --local-engine <path>  |  curl -fsSL --max-time 60 <asset> + SHA256SUMS  |  --engine-from-source
   ├─ sha256sum -c / shasum -a 256 → install -m 0755 to .tmp → mv -f → write .sha256
   ├─ `<bin> version --json` must echo <V> (and prints ENGINE:<path>), else remove and fail loudly
   ├─ --no-testmap / AIT_TESTMAP_FETCH=0 → TESTMAP_BINARY:skipped:<reason>
   └─ summary: VENV:~/.aitask/venv … AITASKS_HOME:~/.aitasks  ENGINE:~/.aitasks/engine/v<V>/ait-testmap

ait engine build   → $AITASKS_HOME/engine/dev/ait-testmap + .dev marker; ENGINE_BUILT:<path>|<commit>
ait engine prune   → remove $AITASKS_HOME/engine/v*/ no project in ~/.config/aitasks/projects.yaml is on
AIT_ENGINE=dev ait testmap ...   → the dev slot
```
<!-- /section: data_flow -->

<!-- section: thinking_app_mapping [dimensions: component_selector, component_runner_contract, component_reference_runners, component_dependency_scanners, component_annotation_scanner, assumption_areas_express_suite_blast_radius] -->
## Worked Mapping: thinking_app

### Annotations

In `ScreenFixtures.kt`, one block per fixture; the member name is the golden
token, which is also the `@Test` method name with its first letter lowercased
and the `ScreenFixture("…")` literal:

```kotlin
    // testmap:unit Welcome
    // testmap:covers app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeScreen.kt   @2026-09-16/7c1e0b9a3d
    // testmap:covers app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeViewModel.kt @2026-09-16/2a9f47d0c1
    fun welcome(coordinator: MainCoordinator = coordinator()) = ScreenFixture("Welcome") {
        val viewModel = WelcomeViewModel(coordinator).apply { registerResult.value = "" }
        WelcomeScreen(viewModel).body()
    }
```

`ait testmap annotate` writes these from the fixture body's own symbols when
asked (`annotate ScreenFixtures.kt#Welcome --from-body`, using the kotlin
scanner's resolution of `WelcomeScreen` / `WelcomeViewModel` through the
file's imports); the agent confirms; the stamp is the tool's. A file-level
block before the first `testmap:unit` may carry `testmap:kind unit` and
`testmap:runner screen-matrix` so no block repeats them.

Tree-scanning helpers declare what they read, once, in the helper:

```kotlin
// app/src/test/java/com/softman/thinking/testing/SourceFence.kt
// testmap:reads app/src/main/java/**/*.kt
```

Every unit whose test-file closure imports `SourceFence` (57 classes today)
inherits that glob as a trigger: any Kotlin change selects them, never
deferred, which is the "constant floor" the design record says a selector
cannot trade away — now data, and printed with reason
`reads(SourceFence.kt) <- app/src/main/java/.../HeroBand.kt`.

### Runners

```yaml
# aitestmap/runners.yaml  (thinking_app)
runners:
  screen-matrix: {exec: tools/verification/testmap_runner.sh, unit: variant, axis: matrix, batch: true,
                  needs: [heavy-run], token_format: "{variant}:{member}"}
  gradle-class:  {exec: tools/verification/testmap_runner.sh, unit: class, batch: true, needs: [heavy-run]}
  verify-active: {exec: tools/verification/screenshot-tests.sh, unit: suite, full: true,
                  children: tools/verification/testmap_runner.sh}     # post-processor: results-summary.json → child rows
bindings:
  - {glob: "app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt", runner: screen-matrix}
  - {glob: "app/src/test/java/**/*.kt",                                        runner: gradle-class}
```

`tools/verification/testmap_runner.sh` (project-owned, ~150 lines, sources
`lib/screenshot-review.sh`):

- `describe` → `contract:1 unit:variant axis:matrix batch:true needs:heavy-run token_format:{variant}:{member}`.
- `list` → for every non-comment line of `primary-catalog-expected.txt` and
  `secondary-matrices-expected.txt` (`<Screen>_<matrix>.png`): one row
  `app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt#<Screen>@<matrix>\tunit\t<lowering>`
  where `<lowering>` is the comma-joined `<class>.<method>` for every class in
  `matrix_classes <matrix>` (the base class owns the method; the others are
  inert); plus, for `gradle-class`, one row per other class under
  `app/src/test/java` with lowering `<fqn>`. The two runners share the script
  and split the universe by binding, so every JVM class is listed exactly once.
- `run --manifest <f> --out <d>` → collects lowerings →
  `screenshot-tests.sh unit-tests --tests <l1> --tests <l2> …` (which reserves
  the heavy-run slot through `jvm_gradle`, sets `-Pthinking.runId`, and
  classifies the no-verdict states) → on return, runs
  `suite-outcome-check.py --expect-run-id <id> --require-ran <every class in
  the manifest>` and parses `app/build/test-results/testDebugUnitTest/*.xml`:
  each `<testcase classname name>` inverts through the `list` table to an id;
  a `pixel5Ru_ltr` `welcome` failure with a Roborazzi diff carries
  `{"status":"fail","evidence":{"golden":"Welcome_pixel5Ru_ltr.png","compare":"<abs path>"}}`
  so the agent gets the `DIFF_SET:`/`IMAGE:` paths the repository's rule
  requires. Exit contract `0/1/2/75/64` as `unit-tests` already defines it.
- `children` (for the `verify-active` suite runner) → after a full run,
  `lib/screenshot-diff-set.sh` rows keyed on `result_id` (= golden basename)
  become child rows `{id: …#<Screen>@<matrix>, status: fail|pass, parent: verify-active}`
  for every catalog golden, so the full gate feeds per-variant evidence and
  the prediction ledger without ever being *selected* per variant.

### Three changes, three selections

```
$ ait testmap select --task t9001 --changes -          # t9001 edits ui/mvvm/auth/welcome/WelcomeScreen.kt
…ScreenFixtures.kt#Welcome@pixel5_rtl        d=1 unit  edge(annotation) WelcomeScreen.kt                      est 6s
…ScreenFixtures.kt#Welcome@pixel5_ltr        d=1 unit  edge(annotation) WelcomeScreen.kt                      est 6s
…  (all ten matrices Welcome is enrolled in; 8 here — Welcome is absent from imeProxy_rtl and bidiSampler_rtl)
…testing/SourceFenceTest.kt                  d=1 unit  reads(SourceFence.kt) <- WelcomeScreen.kt                est 2s
…  (the other 56 SourceFence classes)
…testing/PrimaryCtaReachabilityTest.kt       d=2 unit  dep ui/mvvm/auth/welcome/WelcomeScreen.kt <- Welcome fixture (test-dep)
tokens: pixel5_rtl:Welcome pixel5_ltr:Welcome shortPhone_rtl:Welcome shortPhone_ltr:Welcome pixel5Ru_ltr:Welcome …

$ ait testmap select --task t9002 --changes -          # t9002 edits res/values-ru/strings.xml (2 keys), symbol_scanners: [android-res]
…ScreenFixtures.kt#Questions@pixel5Ru_ltr      d=1 unit  axis(matrix.locale=ru)[timer_ring_label,accumulated_time] <- values-ru/strings.xml
…ScreenFixtures.kt#Questions@shortPhoneRu_ltr  d=1 unit  axis(matrix.locale=ru)[timer_ring_label,accumulated_time] <- values-ru/strings.xml
…ScreenFixtures.kt#QuestionNumber@pixel5Ru_ltr d=1 unit  axis(matrix.locale=ru)[accumulated_time] <- values-ru/strings.xml
…localization/CatalogParityGateTest.kt         d=1 unit  reads(CatalogManifest.kt) <- values-ru/strings.xml
…localization/MixedDirectionCatalogOracleTest.kt d=1 unit reads(CatalogManifest.kt) <- values-ru/strings.xml
tokens: pixel5Ru_ltr:Questions shortPhoneRu_ltr:Questions pixel5Ru_ltr:QuestionNumber
        (without android-res: every enrolled screen on both ru matrices — 65 variants — same reason minus the key list)

$ ait testmap select --task t9003 --changes -          # t9003 edits ui/components/HeroBand.kt
…ScreenFixtures.kt#Welcome@pixel5_rtl        d=2 unit  dep ui/components/HeroBand.kt <- WelcomeScreen.kt
…  (every screen whose closure imports HeroBand — the t86 case: 14 goldens moved across 4 screens and 3 matrices; here every
     matrix of every such screen is listed, so the selection is a superset of what t86 needed)
…testing/SourceFenceTest.kt (+56)            d=1 unit  reads(SourceFence.kt) <- HeroBand.kt
$ ait testmap select --task t9004 --changes -          # t9004 edits utils/TypeScale.kt, which declares `const val`
ESCALATE:app/src/main/java/com/softman/thinking/utils/TypeScale.kt|const-val|screen-matrix,gradle-class
…  every id of both runners at d=0 — the whole JVM suite, which is what verify-active runs
```

`select --format tokens | xargs tools/verification/screenshot-tests.sh preview`
is the advisory surface the repository's design record calls Stage 1: it
runs no verdict and gates nothing. The full `verify-active` stays the
completion gate (`test_command`), and its child rows score every prediction
made during the task.

### What stays in bash in that repository

`known_matrices`, `matrix_classes`, `matrix_manifest`, `preview_resolve_token`,
the membership manifests, `suite-outcome-check.py`, `screenshot-diff-set.sh`,
`heavy-run-lock.sh` and `emulator-allot.sh` are untouched. The runner script is
the only addition; `axes.yaml` and the annotations are the only committed data.
<!-- /section: thinking_app_mapping -->

<!-- section: freshness [dimensions: component_freshness, component_staleness_tool, component_evidence_join, assumption_blob_digest_is_staleness_key, assumption_git_history_is_freshness_clock, assumption_passing_run_anchors_edges] -->
## Annotation Freshness with Variants

The stamp, the anchor and the join are the baseline's. The one refinement is
where evidence lives: `last_pass` is recorded **per id**, so a member with
variants has one anchor per matrix. For an edge whose `stamped_blob ≠
current_blob`, the join asks, for every variant the change reaches, whether a
`last_pass.sha` of *that variant* is an ancestor of HEAD and holds the source
at `current_blob`. All reached variants evidenced → `EVIDENCED`; otherwise
`STALE` with the unevidenced variants named. The reasoning: a Hebrew render
that passed against the current `WelcomeScreen.kt` says nothing about the
Arabic render, whose line boxes run 27–30 % taller; the procedure gate must
not re-stamp on the strength of the wrong matrix.

The full-run child rows make this cheap in thinking_app: every
`verify-active` at task completion anchors all 297 goldens at once, so the
next task's `stale` finds evidence for most hot sources without anyone
running anything extra.

`stale --confirm-evidenced` remains the only autonomous re-stamp and now
requires all reached variants evidenced. `--confirm-source <path>` and
`--retarget` are unchanged. `verify <file>#<member>` re-stamps one member.
<!-- /section: freshness -->

<!-- section: selection [dimensions: component_selector, component_dependency_scanners, assumption_change_surface_is_intake] -->
## Selection: Fail-Closed Scanners and the Test-Side Closure

Intake, refusal on `UNKNOWN:`, the graded walk, rules and cut knobs are the
baseline's. Three additions:

**Opaque contract (kotlin scanner).** Handled constructs: an explicit
`import <repo package>…` → edge; a same-package reference → the package is
fully connected; a repo-package star import → an edge to every file in the
package; a fully-qualified in-body reference found in the comment-stripped
body → edge. Everything else marks the *file* `opaque:<reason>`: `inline fun`,
`const val`, `@Module` / `@Provides` / `@Inject`, `Class.forName` /
`::class.java`, a file under a generated or KSP root, a file that fails to
tokenize or read. An opaque file participates in the graph normally as a
*dependency* (its imports are still edges), but a *change to it* emits
`ESCALATE:<file>|<reason>|<runner set>` and selects every id of the runners
bound to its module at d0. The scanner runs over `app/src/main` and
`app/src/test` alike. Each opaque reason has a fixture in
`engine/testdata/opaque/` and a test that disables the branch and observes a
narrow selection — the red proof that the fallback is reachable.

**Test-side closure.** A unit is selected at d1 with reason `test-dep
<file>` when a changed file is in the forward closure of the unit's own test
file: imports, abstract-base inheritance (an import or same-package
reference), test resources read by literal path, and the `reads` globs of any
helper in the closure. This is what makes a change to `ComposeScreenTest.kt`
select its 84 dependants and a change to `robolectric.properties` select every
Robolectric class — the fan-out the design record measured — without a second
model: it is the same scanner over the test root.

**Symbol narrowing (opt-in).** `config.yaml: symbol_scanners: [android-res]`
enables the built-in scanner that indexes `R.string.<key>`,
`stringResource(R.string.<key>)` and `"<key>".localized()` sites per Kotlin
file (652 + 419 + 18 sites under `ui/` today) and, for a changed
`res/values*/{strings,plurals}.xml`, diffs the before blob (`HEAD:<path>` for a
`TASK:` row, the parent of the first `(t<id>)` commit for a `COMMITTED:` row,
resolved by `internal/gitx`) against the working tree to list changed keys.
An axis hit is then narrowed to members whose closure names a changed key;
with no before blob (shallow history) the whole file's key set is used, which
degrades to the file-level projection. `explain` prints the key list.

Reasons, in full: `edge(annotation|declared|observed)`, `dep <a> <- <b>`,
`rule <name>`, `axis(<axis>.<facet>=<v>)[keys] <- <path>`, `test-dep <file>`,
`reads(<helper>) <- <path>`, `area(<name>) <- <path>`, `scope(<glob>) <-
<path>`, `trigger(<glob>) <- <path>`, `stale-evidence <source>`, and the
`ESCALATE:` line.
<!-- /section: selection -->

<!-- section: runner_contract [dimensions: component_runner_contract, component_reference_runners, assumption_gate_exit_contract_reused, assumption_existing_locks_wrappable, assumption_batch_per_unit_timing_reportable] -->
## Runner Contract

```
describe   → contract:1 unit:file|class|method|variant|suite axis:<name>? batch:true|false needs:[…] overhead_ms:<n>? token_format:<fmt>?
list       → TSV rows: <id>\t<kind>\t<lowering>       ids may carry #<member> and @<variant>; lowering is opaque to the engine
run        → --manifest <f> --out <d>; manifest units: [{id, lowering, timeout_s}]; results.jsonl rows keyed by id;
             optional child rows {id, status, duration_ms, parent, evidence?} for a unit: suite runner;
             runner.json {status, exit, cause, units_expected, units_reported, overhead_ms}
```

`list` is the universe: `check` fails `UNREGISTERED:<path>` for a test file no
runner lists and, for a runner whose filter restricts a whole run (declared
`filter_scope: run` in `describe`), the selector treats "listed and not
selected" as a deliberate omission it must be able to justify — which is why
the test-side closure and `reads` exist. Builtin runners: `bash-file`,
`pytest`, `go-test`, `gradle-class` (now consuming `<lowering>` verbatim as
`--tests` and inverting JUnit `classname`+`name` through the list table),
`suite`, `device`. Exit mapping to the verifier contract is the baseline's
table (0→0, 1→1, 2→2 skip, 75→3 after in-engine deferral, 64/absent→3).
<!-- /section: runner_contract -->

<!-- section: gates [dimensions: component_gates, requirements_gate_enforcement] -->
## Gates and Admission

The three gate entries are the baseline's (`testmap_fresh` procedure;
`testmap_check` machine, `unlocks: [testmap_run]`; `testmap_run` machine,
`blocks_dependents`, `max_retries: 1`). One addition governs *when a project
turns `testmap_run` on*:

```yaml
# aitestmap/config.yaml
run_gate_admission:
  min_scored_full_runs: 30          # rows in costs/predictions.yaml
  max_false_negatives: 0            # over those rows
  require_opaque_proofs: true       # engine self-check: every opaque branch has a red-proof fixture
  approved_by: {who: <email>, at: 2026-10-01, statement: aidocs/testing/change-aware-verification.md#what-this-cannot-do}
```

`ait testmap readiness` prints `READINESS:<criterion>|<met|unmet>|<value>` per
line and `READINESS_DECISION:ADMISSIBLE|NOT_YET`, never a pass/fail exit. It is
a report for the human who edits the profile's gate set; the engine never
enables a gate. For thinking_app the intended state is: `testmap_check` and
`testmap_fresh` from bootstrap; `tests_pass` (full `verify-active`) unchanged
as the completion gate; `testmap_run` added only when readiness is admissible,
and even then beside `tests_pass`, not instead of it, because the design
record's t86 case is about what a human looks at, not what runs.
<!-- /section: gates -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited)* means unchanged from the baseline; *(revised)* names the change;
*(new)* is introduced here.

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(revised: `internal/axes`, opaque fixtures)*

`engine/cmd/ait-testmap` with `internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}`;
Go 1.26, pinned toolchain, `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w -X …"`;
`gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`, `golang.org/x/sync`; stdlib
`flag`, `syscall.Flock`, `os/exec` git. Verbs: `scan | check | select |
schedule | run | stale | verify | annotate | score | attribute | declare |
explain | costs | areas | classify | readiness | runner | version`. Line
protocol, `--json`, per-verb exits `0/1/2/3/64`. Never writes `aitasks/`,
`aiplans/`, `.aitask-data/` or a gate ledger; never invokes `aitask_*.sh`.
Tests against fixture repos in `t.TempDir()`, including `testdata/opaque/`.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary: identity, output contract, budget *(revised: `ENGINE:` line, second bench fixture)*

Embeds `version`, `commit`, `contract`; `version --json` prints them plus
`ENGINE:<resolved path>`; `CONTRACT_MISMATCH:` on registry files from a newer
contract (contract 1 includes `axes.yaml` and the id grammar). Budget pinned
by `go test -bench` on two golden registries — the aitasks shape (~720 units)
and a thinking_app shape (49 members × 10 matrices, ~370 classes, ~900 Kotlin
files) — with the 2× regression rule; pools capped at 8.
<!-- /section: component_engine_binary -->

<!-- section: component_user_root [dimensions: component_engine_packaging, component_binary_distribution] -->
### Per-user root *(new)*

`.aitask-scripts/lib/aitasks_home.sh`: `AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`,
`aitasks_engine_dir <version|dev>`. Sourced by the shim, `install_engine_binary`,
`aitask_engine.sh` and the verifiers; no fallback to `~/.aitask/`. `ait setup`
creates `$AITASKS_HOME/engine/` (0755) and prints `AITASKS_HOME:<path>`.
`tests/test_aitasks_home.sh`: default, override, and a grep over the files
this feature adds that fails on `~/.aitask/`. Precedents: `~/.config/aitasks/`
(`aitask_projects.sh`), `${XDG_CACHE_HOME:-~/.cache}/aitasks/`.
<!-- /section: component_user_root -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(revised: slot paths)*

`engine/build.sh`; the `engine` job in `release.yml`; `engine-check.yml`;
`lib/platform_detect.sh`; the shim's handshake (`AIT_TESTMAP_BIN` >
`AIT_ENGINE=dev` at `$AITASKS_HOME/engine/dev/` requiring `<V>-dev+<sha>` >
`$AITASKS_HOME/engine/v<V>/` requiring `== VERSION` > `ENGINE_MISSING:<path>`
exit 3). Tests `test_testmap_shim.sh`, `test_platform_detect.sh`,
`test_aitasks_home.sh`. Docs name `~/.aitasks/engine/`. `release-packaging.yml`
and `nfpm.yaml` untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade, developer regeneration *(revised: slot paths)*

`install_engine_binary()` in `aitask_setup.sh` (reached by `ait setup` and by
`ait upgrade` through `install.sh --source-only`): uname mapping; `.sha256`
short-circuit; `--local-engine` > exact-version asset > `--engine-from-source`
> `ENGINE_MISSING` warning; checksum; atomic install to
`$AITASKS_HOME/engine/v<V>/`; `version --json` must echo `<V>`; `.dev` never
overwritten without `--force-engine`; `--no-testmap` / `AIT_TESTMAP_FETCH=0`.
`.aitask-testmap/` gitignored. `aitask_engine.sh`: `build` (dev slot), `test`,
`cross`, `prune` (`$AITASKS_HOME/engine/v*/` against `projects.yaml`).
`tests/test_install_engine_binary.sh` through a real `install.sh --dir
--local-engine`.
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(revised: six tables, id grammar)*

`internal/registry`: merges `registry/*.yaml` and `axes.yaml`; parses
`<path>[#<member>][@<variant>]`; materialises variants from runner `list`;
`owns:` routing; write routing; deterministic writes; check rules incl.
`STALE_PATH`, `UNSTAMPED`, `DEAD_SCOPE`, `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`,
`UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED`, `KIND_MISMATCH`,
`CONTRACT_MISMATCH`. Golden tests pin the merge rule and the id grammar.
<!-- /section: component_registry_loader -->

<!-- section: component_variant_axes [dimensions: component_registry_loader, component_selector, component_runner_contract, component_cost_ledger] -->
### Variant axes *(new)*

`internal/axes`: loads `axes.yaml` `{axes: {<name>: {facets[], values{v: {facet: fv}}, sources{facet: {fv: [globs]}}}}}`;
`FacetOf(axis, value, facet)`, `VariantsWith(axis, facet, fv)`,
`SourcesHit(changedPaths) → [(axis, facet, fv, path)]` via `doublestar.Match`;
validates runner `describe` `axis:` against declared axes and `list` variants
against value sets. Used by the selector (rules 1–4 above), the runner codec
(`token_format` expansion: `{variant}`, `{member}`, `{path}`, plus
`{facet.<name>}`), cost and evidence (per-variant ids) and `check`. A project
with no `axes.yaml` has an empty table and every code path is a no-op.
<!-- /section: component_variant_axes -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(revised: grammar v3)*

`internal/annot`: `testmap:unit <Member>` opens a block; keys `kind`, `covers
<path> @<date>/<blob10>`, `area`, `scope`, `trigger`, `reads <glob>` (helper
files only; refused in a listed file), `reviewed`, `runner`, `needs`, `batch`;
per comment leader (`#`, `//`, `--`) and Python docstrings; unknown keys
refused with a line number; block ownership by position only (no language
parsing); the line-targeted rewriter keyed by (file, line, current text) with
`REWRITE_CONFLICT:`; `annotate --from-body` seeds `covers` for a member from
the kotlin scanner's symbol resolution of the block's own lines.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(revised: opaque contract, test roots, android-res)*

`internal/deps`: bash, python, go (`go list -deps -json`), kotlin (closed
construct list; `opaque:<reason>` otherwise; main and test roots; Gradle
module graph), plus plugins under `aitestmap/scanners/` speaking
`{"file", "deps", "opaque"?, "reads"?}` per line; the opt-in `android-res`
symbol scanner (key sites per Kotlin file; changed keys from a before blob);
forward deps cached per source blob under the XDG cache and inverted in
memory.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(revised: expansion, axis join, test-dep, ESCALATE, formats)*

`internal/selectr` + `internal/changesurface`: intake; refusal on `UNKNOWN:`;
the graded walk with rules; variant expansion and axis join (symbol-narrowed
when enabled); test-dep at d1 through the test-side closure and helper
`reads`; `ESCALATE:` on a changed opaque file; scoped join; kind-then-cost
ranking per variant; stale marks from the per-variant evidence join;
`--include-stale`; suite budget with `DEFERRED:`; cut knobs; `--format
lines|json|tokens`; the prediction record; `explain` with key lists and
closure paths.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(revised: list TSV, child rows, inversion)*

`internal/runner`: `describe` fields (`unit`, `axis`, `batch`, `needs`,
`token_format`, `filter_scope`, `full`, `children`); `list` TSV codec; manifest
with lowerings; `results.jsonl` with child rows; inversion of batch reports to
ids with "no registered id" as a mechanism failure; bindings and per-test
override; `builtin:` with `command:`/`cwd:`; shadow-by-name; batching;
per-unit timeouts; `units_expected`/`units_reported` per id; exit contract
`0/1/2/75/64`.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited)*

`internal/sched` as in the baseline: mutex / semaphore / admission /
allocator; host / worktree / run scopes; `flock(2)` slots in canonical order;
admission 75 deferral to the run deadline; allocator handle injection with
signal-safe release; errgroup waves; `broad_after_unit`; `concurrency:
serial|parallel` (serial at bootstrap); the schedule report. Variants of one
runner and one resource set batch into one invocation, so a thinking_app
selection is one Gradle run holding one heavy-run slot.
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(revised: per-id rows, predictions.yaml)*

`internal/cost`: Welford per (id, host class) with P² p95 and last;
`.aitask-testmap/ledger.jsonl` `{run_id, id, status, duration_ms, head_sha}`;
`costs --update` folds into `costs/<hostclass>.yaml` and truncates;
per-invocation overhead rows; `last_pass` and flake rate per id;
`costs/predictions.yaml` (200-row cap) written by the automatic score.
Estimates per kind, with a member's estimate the sum of its selected variants.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(revised: per variant)*

`internal/stale` + `internal/gitx`: for each mismatched edge, candidate shas
per reached variant from ledger and committed costs (any host class); drop
`cause` invocations and ids over `flake_threshold`; keep ancestors of HEAD
(memoised); one `git ls-tree <sha> -- <paths…>` per distinct sha under a pool
of four; `EVIDENCED` only when every reached variant is covered; never
rewrites; `stale --confirm-evidenced` is the explicit re-stamp.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(revised: automatic score, readiness, axis attribution)*

`internal/feedback`: `score --run --prediction`; automatic invocation after
`run --all` and after a `full: true` suite run, printing `PREDICTION_SCORED`,
`PREDICTION_FALSE_NEGATIVES`, `PREDICTION_MISSED` and appending to
`costs/predictions.yaml`; `attribute` with `missing-edge` / `test-wrong` /
`source-wrong` (units and members), `missing-axis-source` (a facet value gains
a source glob in `observed.yaml`, merged at load), `missing-trigger` /
`area-too-narrow`; `readiness` against `run_gate_admission`.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(revised: admission report)*

`testmap_fresh`, `testmap_check`, `testmap_run` in `gates_reference.yaml`
synced to `gates.yaml`; the two verifiers on the `tests_pass` template with the
exit mapping table; engine absent → 3. `run_gate_admission` in `config.yaml`
and `ait testmap readiness`; the engine never edits a gate set.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(revised: members, axes, tokens)*

`aitask-testmap`: annotate a file or a `testmap:unit` member (`--from-body` to
seed), declare an axis source in `axes.yaml` when a new locale or matrix
arrives (the repo's "adding a language" procedure gains one line), `reads` on a
new tree-scanning helper, attribute before the gate, verify after editing an
annotation, `classify --suggest`, and `select --format tokens` piped into the
project's render loop. `aitask-gate-testmap-fresh`: the procedure gate,
naming unevidenced matrices per `STALE` row. Claude Code first, then ported.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(revised: gradle-class lowering, suite children)*

`bash-file`, `pytest` (`testmap:batch no` honoured), `go-test`, `gradle-class`
(`--tests <lowering>` batch; JUnit inversion), `suite` (any command; child rows
from a `children:` post-processor), `device`; `command:`/`cwd:` overrides;
shadow-by-name; `engine-test` over `engine/`. thinking_app's
`tools/verification/testmap_runner.sh` is a project runner, not a builtin.
<!-- /section: component_reference_runners -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(revised: member scope)*

The per-edge stamp written only by `verify`, `annotate`, `stale --confirm*`,
scoped to the member block; `last_pass` per id; `verify` and `verify
--all-evidenced`; `bootstrap_until`, `require_stamp`, `flake_threshold`; the
`testmap_fresh` procedure gate before the change summary; not a git hook, not
a Claude Code hook.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(revised: unevidenced-variants field)*

`stale --task --changes - | --all` with the baseline's line classes and
encoding; `STALE` rows carry `|<unevidenced variants>`; `--strict` on
`STALE_PATH`; rename hints and culprits from `git log -M`; `--confirm`,
`--confirm-source`, `--confirm-evidenced`, `--retarget`.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(revised: reads_from)*

`areas.yaml`; `_scoped.yaml` rows gain `reads_from`; `owns:` by area name;
the d1 join; suite budget with `DEFERRED:`; `DEAD_SCOPE`, `KIND_MISMATCH`;
`ait testmap areas` (`--import-codemap`, `--list`, `--check`); `classify
--suggest` (now also flags a test file importing a `reads`-bearing helper);
`missing-trigger` / `area-too-narrow`.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited; suite children noted)*

`broad_after_unit`, `device_policy: filter_by_resource`, evidence-based
`STALE_AREA`, opt-in `REVIEW_DUE`, `attribute` widening, fixture pins. A suite
row marked `full: true` with a `children:` post-processor anchors registered
ids on every run.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited unchanged from the baseline:

- **Existing project locks and allocators can be wrapped as resources**
  (`assumption_existing_locks_wrappable`) — thinking_app's heavy-run lock and
  emulator allocator are exec'd, never reimplemented; the runner script goes
  through `screenshot-tests.sh unit-tests`, which reserves the slot itself.
- **The change-surface script is the intake** (`assumption_change_surface_is_intake`)
  — lines only, `UNKNOWN:` refuses; the before blob a symbol scanner needs is
  resolved from the same rows and is simply absent without history.
- **`testmap:` does not collide with prose** (`assumption_testmap_token_no_collision`)
  — thinking_app's KDoc, which is unusually long, contains no `testmap:`.
- **The gate exit contract is reused** through two verifier shells
  (`assumption_gate_exit_contract_reused`); `75` stays inside the engine.
- **Go ≥ 1.26 in release CI via a new `setup-go` step and on developer
  machines** (`assumption_go_toolchain_available`), **build-time only**
  (`assumption_go_toolchain_ci_and_dev_only`).
- **Release assets are reachable from `ait setup` / `ait upgrade`**
  (`assumption_release_asset_reachable`) and **air-gapped hosts have
  documented fallbacks** (`assumption_release_assets_reachable`) — the
  pre-seeded directory is now `$AITASKS_HOME/engine/`.
- **Git history is the evidence clock, not the staleness key**
  (`assumption_git_history_is_freshness_clock`); **the blob digest is the key**
  (`assumption_blob_digest_is_staleness_key`).
- **Areas, scopes and triggers express a broad test's blast radius**
  (`assumption_areas_express_suite_blast_radius`) — extended by helper `reads`
  globs, which are triggers inherited through the test-file closure.
- **Broad tests are area-scoped with evidence-based drift**
  (`assumption_broad_tests_area_scoped`).
- **linux/darwin × amd64/arm64 suffices** (`assumption_platform_matrix_sufficient`).
- **One engine per framework version** (`assumption_one_engine_per_framework_version`)
  — the versioned directory is `$AITASKS_HOME/engine/v<VERSION>/`.
- **Target repos accept an `aitestmap/` root** (`assumption_target_repos_accept_aitestmap_root`)
  — plus an optional `axes.yaml`; thinking_app commits one runner script
  because its lowering is its harness's own routing.

Inherited and revised:

- **Static file-level facts are enough for v1** (`assumption_static_granularity_v1`)
  — revised: file-level remains the default, but two narrower granularities
  are in use rather than reserved: member units (position-scoped blocks, no
  language parsing) and the edge `symbols` slot through the `android-res`
  scanner. No scanner produces symbol-level coverage of *code*.
- **Runners can report per-unit timing inside a batch**
  (`assumption_batch_per_unit_timing_reportable`) — revised: and can invert a
  report row to a registered id; for JUnit that is `classname`+`name` through
  the `list` table the runner itself printed.
- **A passing run anchors edges** (`assumption_passing_run_anchors_edges`) —
  revised: per variant; a unit with variants is `EVIDENCED` only when every
  reached variant has a qualifying pass.
- **The engine latency targets** (`assumption_engine_latency_targets`) —
  revised: a second target, select < 250 ms warm on a thinking_app-shaped
  registry (49 members × 10 matrices, ~370 classes, ~900 Kotlin files), pinned
  by a second bench fixture.

New:

- **A runner's `list` is the complete universe its filter can address**
  (`assumption_variant_universe_from_runner_list`) — for thinking_app, the two
  membership manifests (297 goldens over 10 matrices) plus every other class
  under `app/src/test/java`; an unlisted class is `UNREGISTERED` in `check`,
  never silently unfiltered. This is what makes a whole-run `--tests` filter
  sound: nothing can be omitted by accident, only by a selection the engine
  printed.
- **Axis sources are declarable as globs** (`assumption_axis_sources_declarable`)
  — the locale facet's sources are `values-<q>/**`, `raw-<q>/**` and the
  per-family fonts; sources every locale reads are ordinary edges; direction
  and geometry are test-side constants reached through the test-dep closure.
  If a locale ever gains a production-side source the globs cannot name (a
  per-locale Kotlin file), it becomes an ordinary edge to the screens it
  serves, which over-selects across locales rather than under-selecting.
- **The kotlin scanner's opaque list is sufficient** (`assumption_kotlin_scanner_fail_closed`)
  — every construct known to defeat a static import graph is pattern-detectable
  and escalates; the residual risk is a construct not on the list, which is
  why the list is written down, why each branch has a red-proof fixture, and
  why the prediction ledger counts what the list missed.
- **The two per-user roots coexist** (`assumption_legacy_user_root_coexists`)
  — `~/.aitasks/` and `~/.aitask/` share nothing; migrating the Python tenants
  is a later, separate change that this feature neither needs nor blocks.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Advantages:

- **Computed, explained, scored selection** (`tradeoff_computed_vs_prose`) —
  thinking_app's prose rule ("a localized screen change may use `preview` or
  the RTL tier; a shared component or tooling change must run the full gate")
  becomes an axis join, an import fan-out and an `ESCALATE:` line, each printed
  with the path that caused it and the matrices it reaches.
- **Speed makes the machinery usable per task** (`tradeoff_engine_speed_enables_per_task_use`)
  — sub-second on aitasks, sub-250 ms with axis expansion on thinking_app.
- **A real scheduler** (`tradeoff_real_scheduler`) — unchanged; a variant
  batch is one Gradle invocation holding one heavy-run slot.
- **Architecture-independent packages stay that way** (`tradeoff_noarch_packages_preserved`).

Disadvantages:

- **Two per-user roots during the transition** (`tradeoff_two_user_roots`, new)
  — `~/.aitask/` (venv, python, bin, uv) and `~/.aitasks/` (engine) side by
  side; a user who deletes one to reset the framework removes half of it.
  Actionable mitigations: one variable with one owner (`lib/aitasks_home.sh`),
  `ait setup` printing both roots, `ENGINE_MISSING` naming the exact path, and
  `test_aitasks_home.sh` failing if any file of this feature names
  `~/.aitask/`. The residual cost is documentation until the Python tenants
  move.
- **Axis projection is coarse by default** (`tradeoff_axis_projection_coarseness`, new)
  — a one-key edit to `values-ru/strings.xml` selects every enrolled screen on
  both ru matrices (about 65 variants, a few minutes of Robolectric) rather
  than the two screens naming the key. Sound, and still 2 of 10 matrices
  rather than all; narrowed to the screens by enabling `symbol_scanners:
  [android-res]`, and cheap in practice because `--format tokens` drives
  `preview` (no verdict, no promotion) during iteration.
- **Registry directory complexity** (`tradeoff_registry_directory_complexity`)
  — six tables, two generated files, and an id grammar with `#` and `@`
  fragments; the axis table is empty for four of the five target repos and
  every axis code path is a no-op then.
- **Fail-closed bootstrap cost** (`tradeoff_fail_closed_bootstrap_cost`) — a
  repo whose completion gate is a full suite additionally waits for
  `min_scored_full_runs` before `testmap_run` is admissible; the ledger fills
  itself from the full runs the repo already performs at every task's end.
- **Static scanners overselect on hot files** (`tradeoff_static_scanner_overselection`)
  — a `ui/components/*` edit selects most screens on every matrix, which is
  the right answer and close to a full run; the symbol scanner and a project
  plugin are the narrowing tools.
- **Two toolchains** (`tradeoff_two_toolchains`), **a compiled component**
  (`tradeoff_compiled_component_cost`), **a self-downloaded asset in setup**
  (`tradeoff_setup_network_fetch`), **version skew on multi-project hosts**
  (`tradeoff_engine_version_skew`) — as in the baseline, with the slot under
  `$AITASKS_HOME/engine/`.
- **Stamp churn** (`tradeoff_stamp_churn`) — better than the baseline for
  thinking_app: all 49 members' stamps live in `ScreenFixtures.kt`, so a
  hot-source confirmation is a one-file diff.
- **Area and scope coarseness** (`tradeoff_area_glob_coarseness`,
  `tradeoff_broad_scope_coarseness`) — unchanged; `reads` globs are a third
  budget-exempt sharp edge beside triggers.

Risks:

- **Whole-run filter soundness** (`tradeoff_whole_run_filter_soundness`, new)
  — when a runner's filter restricts a whole run, every unselected class is
  silently not run, so a narrow selection is exactly as sound as the test-side
  closure, the `reads` globs and the opaque contract. Mitigations, each
  checkable: `list` enumerates the universe (unlisted → `UNREGISTERED`), the
  scanner runs over the test root (abstract bases, helpers, resources), `reads`
  keeps the 57 fence classes selected on any Kotlin change, opaque files
  escalate, every opaque branch has a red-proof fixture, `readiness` gates the
  run gate on scored history, and the project keeps its full suite as the
  completion gate regardless.
- **Member annotation drift** (`tradeoff_member_annotation_drift`, new) — a
  `testmap:unit` block is keyed by name and the runner's `list` keys the same
  member by the manifest's `<Screen>_<matrix>.png`; a rename on one side
  orphans the other. `check` fails both directions (`UNANNOTATED_MEMBER`,
  `DEAD_MEMBER`) and `scan --apply` refuses rather than guesses; thinking_app's
  own manifest/@Test drift loop already fails the rename on its side.
- **Unattributed source edits** (`tradeoff_attribution_risk`) — narrowed
  further in a repo with a full completion gate: every miss is counted by the
  automatic score, so a map that "looks current and is not" shows up as
  `PREDICTION_FALSE_NEGATIVES:<n>` within one task.
- **Batch misreport** (`tradeoff_batch_misreport_risk`) — one more place to
  misreport (the JUnit → id inversion); a row inverting to no registered id is
  a mechanism failure, and `units_expected`/`units_reported` is per id.
- **Resource declarations are only as complete as declared**
  (`tradeoff_resource_declaration_completeness`), **flaky passes anchor**
  (`tradeoff_flaky_pass_anchors`, per id), **autonomous confirmation is weak**
  (`tradeoff_autonomous_confirmation_weak`, now requiring every reached
  variant), **the handshake is strict** (`tradeoff_strict_version_handshake`),
  **an engine can be absent** (`tradeoff_engine_absent_on_host`), **evidence
  needs reachable history** (`tradeoff_evidence_requires_reachable_history`)
  — as in the baseline.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should the Python tenants (`venv`, `python`, `bin`, `uv`, `dev_tier`,
   `update_check`) move under `AITASKS_HOME` in the same release, with a
   one-time migration in `ait setup`, or stay put until a separate change? This
   proposal assumes the latter.
2. Should an axis hit on a member with **no** `covers` edges at all (a screen
   nobody annotated yet) still select its carrying variants (proposed: yes —
   an axis edge is an edge), or be an `UNSTAMPED`-style bootstrap warning?
3. Is `EVIDENCED` requiring *every* reached variant too strict for the
   `imeProxy_rtl` / `bidiSampler_rtl` matrices, which enrol a handful of
   screens and render rarely? Alternative: an axis value may be marked
   `evidence: optional` in `axes.yaml`.
4. Should `run_gate_admission.min_scored_full_runs` count only runs whose
   prediction was non-trivial (at least one selected variant), so a run with
   nothing predicted does not pad the sample?
5. Should the `android-res` symbol scanner also index Compose `@StringRes`
   parameters passed through helpers, or is a helper file's own edge (which
   reaches every caller) the acceptable over-approximation for v1?
6. For aitasks_mobile, is the natural axis the source-set target
   (`commonTest` / `androidHostTest` / `androidDeviceTest`), or is that a
   runner/kind distinction with no axis needed? Undecided; no axis is declared
   there in this proposal.
7. Baseline questions still open: `--confirm-evidenced` under autonomous
   profiles; cross-host-class evidence; `unit_covers_max: 8`; automatic prune
   on upgrade; `broad_review_days` default; a distance-like grade for scoped
   rows; absorbing `aitask_change_surface.sh` into the engine; the deb/rpm
   postinstall message; routing of a new declared edge with no `owns:` match;
   CI evidence export format; the per-repo bootstrap order (now ending with
   `readiness` before `testmap_run`).
<!-- /section: open_questions -->
--- PROPOSAL_END ---
--- NEW_DIMENSIONS ---
requirements_screen_locale_subdivision, requirements_user_root, assumption_variant_universe_from_runner_list, assumption_axis_sources_declarable, assumption_kotlin_scanner_fail_closed, assumption_legacy_user_root_coexists, component_variant_axes, component_user_root, tradeoff_two_user_roots, tradeoff_axis_projection_coarseness, tradeoff_whole_run_filter_soundness, tradeoff_member_annotation_drift
