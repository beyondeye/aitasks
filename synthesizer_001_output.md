--- NODE_YAML_START ---
node_id: n003_synthesizer_001
parents:
- n001_explorer_001a
- n002_explorer_001b
description: Best-of-both synthesis - the ait-testmap Go engine built from engine/ and installed
  per framework version off PATH, per-edge blob-digest stamps as the staleness key with committed
  run evidence as the healing anchor through a new evidence-join component, and broad tests
  as scoped rows in the one registry directory selected under an explicit suite budget and
  run after the unit wave.
proposal_file: br_proposals/n003_synthesizer_001.md
created_at: "2026-09-16 09:43"
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
requirements_generic_across_projects: A framework feature, generic across projects (aitasks,
  thinking_app, thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation between
  source files and test units
requirements_reason_per_selected_test: Translates a task's change set into one ranked list
  of tests that must run, with a reason on every line - including a stale mark when a selecting
  edge's digest no longer matches and no run evidence covers it, and an explicit DEFERRED
  line for every broad test the suite budget cut
requirements_standard_runner_contract: 'Runs selected tests through project-defined runners
  under a standard contract (describe/list/run verbs); reference runners are built into the
  engine as builtin:<name> with command:/cwd: overrides, and a project script of the same
  name shadows a builtin'
requirements_cost_tracking: Tracks cost per test unit, keyed by host class, using Welford's
  online update (n, mean, standard deviation, p95, last), plus a last_pass {sha, at, run_id}
  anchor and a flake rate per unit
requirements_feedback_loop: Learns from failures the map did not predict via a score/attribute
  feedback loop; attribute records an observed edge for a unit test and an observed trigger
  or area member for a broad test, merged into the registry at load
requirements_gate_enforcement: 'Enforced by gates so the map cannot rot silently: a procedure
  gate (testmap_fresh) that reviews stale annotations before the task commit, a check gate
  (testmap_check, fails rotted paths on its own) and a run gate (testmap_run), fail-closed
  with explicit waivers; only check unlocks run'
requirements_agent_skill: 'Agent skills teach agents how to keep the map current as they write
  code and tests: annotate, attribute, waive, verify after editing an annotation, and confirm
  or retarget digest stamps in the procedure gate'
requirements_go_engine_and_cli: The engine and CLI are one static Go binary (ait-testmap)
  built from engine/; bash keeps only the dispatcher arm, the shim that resolves the binary
  and pipes the change surface in, the two gate verifier shells, the ait engine developer
  verbs and any project-local runner scripts; the binary never invokes aitask_*.sh
requirements_go_engine: Scan, check, select and stale finish in well under a second on a ~720-test
  repo and the scheduler runs concurrently with real cross-process locks, so selection overhead
  stays negligible against the shortest test and check can run at every commit step
requirements_platform_binaries_in_release: Release CI builds and attaches checksummed binaries
  for linux/darwin x amd64/arm64 (ait-testmap_<V>_<os>_<arch> + ait-testmap_<V>_SHA256SUMS.txt)
  from one engine job that also runs go vet and go test; a new engine-check.yml runs the same
  on push/PR for engine/**; tarball and package-manager artifacts stay architecture-independent
requirements_engine_packaging: ait setup and ait upgrade (through install.sh's --source-only
  path) install the host's binary under ~/.aitask/engine/v<VERSION>/ with checksum verification,
  a .sha256 sidecar and a version --json self-check; fallbacks --local-engine, --engine-from-source,
  AIT_TESTMAP_BIN; opt-out --no-testmap / AIT_TESTMAP_FETCH=0
requirements_dev_rebuild_from_source: A framework developer rebuilds the engine with one command
  (ait engine build) through the same engine/build.sh that CI uses, into a dev slot the shim
  selects via AIT_ENGINE=dev (version must read <V>-dev+<sha>); ait engine cross produces
  the CI matrix locally, byte-identical
requirements_engine_dev_regeneration: The GOOS/GOARCH matrix, CGO_ENABLED=0 and ldflags live
  in one script (engine/build.sh) shared by release CI, ait engine build and ait engine cross;
  ait engine test runs go vet and go test; ait engine prune removes versions no registered
  project is on
requirements_annotation_freshness: Every unit coverage annotation carries the date and a blob
  digest of the covered source at confirmation; committed last_pass anchors let stale prove
  a test already passed against a changed source's current content (EVIDENCED) so most hot-source
  churn needs no rewrite; a procedure gate at the post-implementation step hands the report
  to an agent that fixes annotations before the task commit
requirements_annotation_staleness: A stale verb reports, for a task's change set or repo-wide,
  STALE_PATH (deleted or renamed source, fail-closed), STALE (content changed, no evidence),
  EVIDENCED, UNSTAMPED, STALE_AREA and opt-in REVIEW_DUE rows in the framework's fixed line
  protocol; digest comparison needs no git history, evidence only removes nags
requirements_high_level_tests_separate: Integration, e2e and device tests declare areas, scope
  globs or budget-exempt trigger globs instead of covers, live in registry/_scoped.yaml beside
  the unit table, join the ranked list at distance 1 as sinks, and never enter the per-file
  edge graph or its digest staleness
requirements_broad_test_handling: Scoped rows are ranked after unit tests at equal distance,
  selected under an explicit suite budget that prints every DEFERRED cut, scheduled only after
  the unit wave is green (broad_after_unit), widened by attribute on a full-run miss, and
  drift-flagged by evidence (STALE_AREA) rather than by calendar
assumption_static_granularity_v1: Static file-level facts are enough for v1 - no scanner in
  use today produces symbol-level coverage; the schema keeps an optional symbols slot on an
  edge so a hunk-level matcher can be added later
assumption_change_surface_is_intake: 'The change-surface script''s attribution (aitask_change_surface.sh)
  is the right intake; its exit codes carry no meaning, so the shim pipes its COMMITTED:/TASK:/OTHER:/UNKNOWN:
  lines into the engine''s --changes - and the engine parses lines only; selection never reads
  a raw git diff, and an UNKNOWN path refuses selection and drives the stale decision'
assumption_existing_locks_wrappable: Existing project locks and allocators (thinking_app's
  heavy-run lock, emulator allocation) can be wrapped as resources without changing them;
  the Go admission and allocator kinds exec the project's commands and honour their exit codes,
  deferring on 75 until the run deadline
assumption_batch_per_unit_timing_reportable: Runners can report per-unit timing inside a batch
  from their tool's own report format (JUnit XML, go test -json, pytest junitxml); the builtin
  runners parse these in Go
assumption_target_repos_accept_aitestmap_root: Every target repo will accept a root aitestmap/
  directory of YAML committed into its code tree; runner scripts are optional because the
  reference runners are built into the engine
assumption_testmap_token_no_collision: The annotation token 'testmap:' does not collide with
  existing prose comments in any target repo; the 38 existing '# Covers:' headers in aitasks
  are behavioural prose and are not matched
assumption_gate_exit_contract_reused: The framework verifier contract (0 pass / 1 fail / 2
  skip / 3 error) is reused through two dedicated verifier shells, not through gate_command_exit_contract,
  which maps only command exits 0/1/2; runner exit 75 (admission refused, a thinking_app code
  absent from the framework) is deferred inside the engine and a final 75 maps to verifier
  3; only an empty selection maps to 2; a missing engine maps to 3, never skip
assumption_go_toolchain_available: 'A Go toolchain >= 1.26 is available in release CI through
  an actions/setup-go step this design adds to release.yml (go-version-file: engine/go.mod)
  and on framework developers'' machines; target-project users never need Go'
assumption_go_toolchain_ci_and_dev_only: Go is a build-time dependency only - corrected premise
  - release.yml has no Go step today and the repo's only setup-go is hugo.yml's at website/go.mod's
  1.25.7, so the engine job provisions its own toolchain; users receive prebuilt binaries
  and never compile
assumption_release_asset_reachable: A host running ait setup or ait upgrade can reach github.com/beyondeye/aitasks/releases
  over HTTPS, as it already must for the framework tarball; the shim itself never downloads,
  so a gate run never performs a network fetch
assumption_release_assets_reachable: Air-gapped or off-matrix hosts supply the binary via
  --local-engine, --engine-from-source, AIT_TESTMAP_BIN or a pre-seeded ~/.aitask/engine/;
  --no-testmap / AIT_TESTMAP_FETCH=0 skip the fetch and nothing else in setup depends on it
assumption_git_history_is_freshness_clock: Git history is the evidence clock, not the staleness
  key - commit reachability (merge-base --is-ancestor) decides which last_pass anchors may
  suppress a STALE row, never whether an edge is stale; mtime is never compared; a shallow
  clone whose anchors are outside fetched history reports STALE, not EVIDENCED, and remains
  fully functional
assumption_passing_run_anchors_edges: A passing run of a test at commit C, on any host class,
  from an invocation without a cause and for a unit under the flake threshold, is evidence
  that its annotated edges held for the source content present in C's tree - so an edge whose
  current blob equals the blob at C is EVIDENCED without touching the test file
assumption_areas_express_suite_blast_radius: The blast radius of a high-level test is expressible
  as a union of area glob sets plus scope globs plus budget-exempt trigger globs; what that
  misses surfaces through score on a full run as an observed trigger or area member
assumption_engine_latency_targets: On the aitasks repo (about 720 test units, 2,500-3,000
  edges, about 270 scanned sources) the engine meets select < 200 ms warm, scan < 300 ms,
  check < 300 ms, stale --task < 300 ms, stale --all < 2 s, cold select < 1.5 s; pinned by
  committed go test -bench fixtures with a 2x regression failing engine-check.yml, validated
  before the gates are enabled here
assumption_platform_matrix_sufficient: linux/darwin x amd64/arm64 covers every target host
  (WSL reports Linux); any other platform builds from source via --engine-from-source
assumption_blob_digest_is_staleness_key: The git blob digest of the covered source's content
  is the staleness key; file mtime (reset by checkout) and the annotation date (day granularity,
  clock skew) are never compared - the date is display only; the blob id doubles as the join
  key into any commit's tree for the evidence join
assumption_broad_tests_area_scoped: Integration, e2e and device tests can be described by
  named areas or globs whose membership changes rarely, so evidence-based drift (STALE_AREA)
  plus attribute widening is adequate; a calendar cadence (REVIEW_DUE, broad_review_days)
  is opt-in and off by default because a date is the key both parents rejected for unit edges
assumption_one_engine_per_framework_version: One engine build per framework version suffices;
  a per-user versioned directory (~/.aitask/engine/v<VERSION>/) resolves per-project VERSION
  differences without a compatibility matrix, and exact-version resolution in the shim never
  falls back to newest-wins
component_registry_loader: 'Registry loader and writer (internal/registry): merges aitestmap/registry/*.yaml
  into five tables (edges, scopes, areas, rules, waivers); owns: routing by glob for edges
  and rules and by area name for hand-declared scopes; write routing (scan --apply -> _scanned.yaml
  and _scoped.yaml, attribute -> observed.yaml, declare -> the owning hand file, refusing
  when nothing owns); deterministic sorted writes only on change; check rules incl. STALE_PATH
  rows, UNSTAMPED past bootstrap under require_stamp, DEAD_SCOPE, KIND_MISMATCH|CONVERT_TO_SUITE
  above unit_covers_max (warn; fail under --strict), CONTRACT_MISMATCH; golden tests pin the
  merge rule (merged from n001 and n002)'
component_annotation_scanner: 'Annotation scanner and rewriter (internal/annot): grammar v2
  - testmap:kind, testmap:covers <path> @<date>/<blob10>, testmap:area, testmap:scope, testmap:trigger,
  testmap:reviewed, runner/needs/batch - per comment leader and Python module docstrings;
  refuses unknown keys with a line number; kind decides the association form; a line-targeted
  rewriter edits stamps by (file, line, current text) and refuses on REWRITE_CONFLICT; produces
  both generated files from every runner''s list output (merged from n001 and n002)'
component_dependency_scanners: 'Dependency scanners (internal/deps): built-in bash, python,
  go (go list -deps -json cached by go.sum digest), kotlin and Gradle module-graph scanners
  plus executable plugins under aitestmap/scanners/ speaking one JSON line per file; forward
  deps cached per source blob under ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json
  and inverted in memory (merged from n001 and n002)'
component_selector: 'Selector (internal/selectr, internal/changesurface): line-protocol intake
  via --changes - or a file, refusing on UNKNOWN:; the graded walk with select/implies/escalate
  rules; scoped join at d1; ranking by distance then kind then cost; stale marks from digest
  compare plus evidence join; --include-stale union of STALE and STALE_AREA rows at distance
  s; suite budget with DEFERRED lines and budget-exempt triggers; cut knobs; prediction record
  with per-kind estimates; explain (merged from n001 and n002)'
component_runner_contract: 'Runner contract and repository (internal/runner): describe/list/run
  verbs, manifest and results.jsonl/runner.json formats, first-match bindings and per-test
  override, the builtin: scheme with command:/cwd: overrides and shadow-by-name, batching
  by (runner, resource set, batch flag), per-unit timeouts, units_expected/units_reported
  reconciliation, exit contract 0/1/2/75 plus 64 for usage errors (merged from n001 and n002)'
component_scheduler_resources: 'Scheduler and resources (internal/sched): kinds mutex/semaphore/admission/allocator,
  scopes host/worktree/run, acquired_by planning; flock(2) slot files taken in canonical order;
  admission exec with 75 deferral and backoff to the run deadline; allocator exec with signal-safe
  release; goroutines under errgroup; batching; broad_after_unit waves; config concurrency:
  serial|parallel defaulting to serial at bootstrap (one invocation at a time, schedule printed)
  with --serial/--parallel overrides; the schedule report and its check half (inherited from
  n002, n001 default)'
component_cost_ledger: 'Cost ledger (internal/cost): Welford per (unit, host class) with P2
  p95 and last; per-repo ledger .aitask-testmap/ledger.jsonl with run_id/unit/status/duration_ms/head_sha
  per result; costs --update folds into aitestmap/costs/<hostclass>.yaml and truncates; per-invocation
  overhead rows; last_pass {sha, at, run_id} per unit and a flake rate with flake_threshold
  excluding a unit from anchoring; per-kind estimates (merged from n001 and n002)'
component_evidence_join: 'Evidence join (internal/stale + internal/gitx, reads internal/cost):
  for every edge whose stamped_blob differs from the current blob, collects the test''s last_pass
  shas from the local ledger and committed costs (any host class), drops candidates from invocations
  with a cause or units over the flake threshold, keeps shas that are ancestors of HEAD, and
  runs one git ls-tree per distinct sha; an edge whose source object id at that sha equals
  the current blob is EVIDENCED, otherwise STALE; never rewrites - stale --confirm-evidenced
  is the explicit re-stamp and the only bulk confirmation an autonomous profile may run (new:
  introduced to bridge n001 and n002)'
component_feedback_tools: 'Feedback tools (internal/feedback): score splits a full run''s
  failures into caught/missed for unit and scoped rows against a prediction record; attribute
  records missing-edge/test-wrong/source-wrong for units and missing-trigger/area-too-narrow
  for scoped rows, with task and run id, as observed edges, observed triggers and observed
  area members in registry/observed.yaml that the loader merges; stale --confirm-evidenced
  bridges to the staleness loop (merged from n001 and n002)'
component_gates: 'Gates: three entries in gates_reference.yaml synced to gates.yaml - testmap_fresh
  (kind: procedure, verifier aitask-gate-testmap-fresh, no unlocks, like docs_updated), testmap_check
  (machine, max_retries 0, timeout 120, unlocks [testmap_run]), testmap_run (machine, blocks_dependents,
  max_retries 1, timeout 1800); two bash verifiers on the tests_pass template mapping engine
  exits 0/1/2/75/64 and a missing engine to verifier 0/1/2/3/3/3, appending via aitask_gate.sh
  (merged from n001 and n002)'
component_skill: 'Skills: aitask-testmap teaches annotate (covers or area/scope/trigger),
  give a new source an edge/rule/area/waiver, attribute before the gate, verify after editing
  an annotation, classify --suggest to choose the table; aitask-gate-testmap-fresh is the
  procedure gate that runs stale --task, shows git diff <stamped_blob> <current_blob> per
  STALE row, retargets STALE_PATH rows from the culprit task''s plan, re-stamps EVIDENCED
  rows, prompts on UNSTAMPED rows past bootstrap, never guesses UNKNOWN and never confirms
  a STALE row autonomously; Claude Code first, then ported (merged from n001 and n002)'
component_reference_runners: 'Reference runners built into the binary as ait-testmap runner
  <name>: bash-file, pytest (junitxml; a unit annotated testmap:batch no gets its own invocation
  - the serial carve-out, pinned by extending tests/test_serial_carveout_doc_drift.sh), go-test
  (per-file -run regex, -json), gradle-class, suite, device (allocator handle); command:/cwd:
  overrides in runners.yaml; a project script of the same name shadows a builtin and explain
  shows which won; engine-test runs go-test over engine/ so the engine''s own tests ride the
  map (inherited from n002, n001 additions)'
component_go_engine: 'Go engine and CLI: engine/cmd/ait-testmap with internal/{registry,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform};
  Go 1.26 with pinned toolchain, CGO_ENABLED=0, -trimpath -buildvcs=false -ldflags -s -w -X
  version/commit/contract; deps gopkg.in/yaml.v3, bmatcuk/doublestar/v4, golang.org/x/sync
  only; stdlib flag verb table, syscall.Flock, os/exec git (no cobra, no go-git, no gofrs/flock);
  line-protocol stdout, --json, per-verb exit contracts; never writes aitasks/, aiplans/,
  .aitask-data/ or a gate ledger and never invokes aitask_*.sh; tests against fixture repos
  in t.TempDir() (merged from n001 and n002)'
component_binary_distribution: 'Binary distribution: engine/build.sh as the single build and
  matrix command; the engine job in release.yml (setup-go from engine/go.mod, go vet, go test,
  build.sh all) producing ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and ait-testmap_<V>_SHA256SUMS.txt
  attached by both action-gh-release steps with release needs: [plan, engine]; the unchanged
  VERSION-matches-tag guard; a new engine-check.yml on push/pull_request for engine/** (gofmt,
  vet, test, 2x bench rule); lib/platform_detect.sh; the shim''s strict handshake (AIT_TESTMAP_BIN
  with override notice > AIT_ENGINE=dev slot requiring <V>-dev+<sha> > ~/.aitask/engine/v<V>/
  requiring == VERSION > ENGINE_MISSING exit 3 with repair hint); tests test_testmap_shim.sh
  and test_platform_detect.sh; aidocs/framework/go_engine.md, a CLAUDE.md Engine block and
  a packaging_strategy.md paragraph; release-packaging.yml and nfpm arch: all untouched (merged
  from n001 and n002)'
component_engine_binary: 'Engine binary identity and budget: embeds version, commit and contract;
  version --json is the install-time self-check; fixed-prefix structured output and --json;
  CONTRACT_MISMATCH refusal on registry files from a newer contract; performance budget pinned
  by go test -bench on a golden registry with a 2x regression failing CI; scanner and dependency
  pools capped at 8 so the engine never competes with the tests it launches (inherited from
  n002, targets merged)'
component_engine_packaging: 'Engine install and developer regeneration: install_engine_binary()
  in aitask_setup.sh, reached by ait setup and by ait upgrade through install.sh''s --source-only
  path beside install_global_shim; uname mapping; .sha256 sidecar short-circuit; source order
  --local-engine > exact-version release asset > --engine-from-source > ENGINE_MISSING warning;
  sha256sum -c / shasum -a 256; atomic install to ~/.aitask/engine/v<V>/; version --json must
  echo <V>; .dev-marked binaries never overwritten without --force-engine; --no-testmap /
  AIT_TESTMAP_FETCH=0 print TESTMAP_BINARY:skipped; .aitask-testmap/ gitignored by setup;
  aitask_engine.sh with ait engine build|test|cross|prune (prune against ~/.config/aitasks/projects.yaml,
  never automatic in upgrade); tests/test_install_engine_binary.sh through a real install.sh
  --dir --local-engine (inherited from n002, n001 opt-outs added)'
component_freshness: 'Freshness: the per-edge @<date>/<blob10> stamp written only by verify,
  annotate and stale --confirm*; last_pass anchors in the ledger and committed costs; the
  verify verb and verify --all-evidenced; config bootstrap_until, require_stamp, flake_threshold;
  the testmap_fresh procedure gate dispatched by the existing procedure-gate block before
  the change summary so stamp rewrites ride the (t<id>) commit; the aitask-gate-testmap-fresh
  skill; not a git hook and not a Claude Code hook (merged from n001 and n002; the per-block
  testmap:verified stamp is replaced by the per-edge digest plus the evidence join)'
component_suite_registry: 'Scoped-row registry and areas: registry/areas.yaml plus areas:
  blocks in hand files (seedable via areas --import-codemap from code_areas.yaml as <path>/**);
  registry/_scoped.yaml rows {test, kind, runner, areas, globs, triggers, needs, reviewed_at,
  line}; owns: by area name for hand-declared rows; the d1 join, kind ranking, suite budget
  (suite_budget_s default 600, --suite-budget, --suites auto|all|none) with DEFERRED lines
  and budget-exempt triggers; check rules incl. DEAD_SCOPE and KIND_MISMATCH|CONVERT_TO_SUITE;
  ait testmap areas (--import-codemap, --list, --check) and classify --suggest (tmux new-session,
  ./ait exec, serial carve-out, covers over limit); missing-trigger / area-too-narrow in attribute;
  a rule may select: a scoped test by name (merged from n001 and n002)'
component_staleness_tool: 'Staleness tool (internal/stale): stale --task --changes - | --all
  prints SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION
  lines with %25/%7C encoding, content states exit 0, --strict exits 1 on STALE_PATH; compares
  blob digests of the working tree only, consults the evidence join, adds rename hints and
  culprit task ids from git log --name-status -M when history is reachable; mutates stamps
  via --confirm, --confirm-source, --confirm-evidenced, --retarget through the rewriter with
  a re-scan of touched files (inherited from n002, classes merged with n001)'
component_broad_test_scopes: 'Broad-test scheduling and staleness policy: kind integration|e2e|device
  selects the scoped association form; broad_after_unit: true waves run scoped rows only after
  a green unit wave; device_policy: filter_by_resource default; scoped rows are exempt from
  per-edit digest staleness, with STALE_AREA (files in scope changed since last_pass, no pass
  since) as the evidence-based drift signal feeding --include-stale and REVIEW_DUE as an opt-in
  cadence (broad_review_days, default 0); attribute widens areas by evidence; covers on a
  scoped row is allowed for digest-stamped fixture pins (inherited from n002, n001 drift signal)'
tradeoff_computed_vs_prose: 'Advantage: selection is computed, explained and scored rather
  than remembered; blast radius becomes data instead of prose, and the stale mark, the EVIDENCED
  class and the digest-anchored diff add how trustworthy an edge is, and why, to why it was
  selected'
tradeoff_fail_closed_bootstrap_cost: 'Disadvantage: fail-closed enforcement means bootstrapping
  each repo requires an explicit waiver pass before testmap_check can be enabled and a first
  green full run before require_stamp and --strict are turned on; mitigated by check --strict
  off until enabled and bulk stamping via stale --all --confirm-evidenced'
tradeoff_static_scanner_overselection: 'Disadvantage: static scanners overselect on hot files
  and cannot see runtime coupling; kind ranking, the suite budget and --budget-s trim scoped
  rows first and a project scanner plugin can narrow a hot resource file'
tradeoff_resource_declaration_completeness: 'Risk: declared resources are only as complete
  as the declarations; an undeclared interference is invisible until a full run or a probe
  finds it; serial-by-default at bootstrap means declarations are reviewed in the schedule
  report before concurrency is trusted'
tradeoff_registry_directory_complexity: 'Disadvantage: a merged registry directory needs more
  CLI logic than a single file would - now five tables and two generated files; kept to one
  directory with one merge rule in one Go package with golden tests, avoiding n001''s second
  merged directory'
tradeoff_attribution_risk: 'Risk: an agent that edits sources without attributing produces
  a map that looks current and is not; narrowed - such a source shows as STALE in the next
  task touching it and as a stale mark on every selection - but a new coupling with no edge
  at all is still only caught by score on a full run'
tradeoff_batch_misreport_risk: 'Risk: a batch runner that misreports per-unit results corrupts
  attribution, cost and now evidence (a false pass could manufacture an EVIDENCED row); mitigated
  by units_expected/units_reported reconciliation per invocation, a mismatch being a mechanism
  failure, and no line from an invocation with a cause ever anchoring; a wrongly scoped resource
  either serialises everything or protects nothing'
tradeoff_two_toolchains: 'Disadvantage: bash and Go in one framework; mitigated by the boundary
  rule (parse/walk/match/digest/schedule in Go; gate ledger, task file and shell environment
  in bash; builtins exec configured commands and never source shell state), the engine-check.yml
  job, and Go source confined to engine/ and excluded from the tarball so target projects
  never need Go'
tradeoff_setup_network_fetch: 'Disadvantage: ait setup gains the framework''s first self-downloaded
  release asset; mitigated by reusing the CDN URL family install.sh already uses, SHA256SUMS
  verification, the .sha256 sidecar, --no-testmap / AIT_TESTMAP_FETCH=0, the shim never fetching
  on its own, and setup never depending on the binary for anything else'
tradeoff_area_glob_coarseness: 'Disadvantage: area and scope globs are coarser than edges
  - a broad area over-selects its tests on every edit inside it and a scoped test depending
  on a file outside its scope is under-selected until a full run scores it; mitigated by the
  suite budget with explicit DEFERRED lines, budget-exempt triggers for known sharp edges,
  and the missing-trigger / area-too-narrow attribution path'
tradeoff_flaky_pass_anchors: 'Risk: a flaky pass anchors evidence as surely as a real one;
  mitigated by per-run status in the ledger so costs exposes a flake rate, and a unit above
  flake_threshold is excluded from the evidence join'
tradeoff_strict_version_handshake: 'Risk: the binary must match .aitask-scripts/VERSION exactly,
  so an ait upgrade on a host that cannot fetch leaves ait testmap refusing to run until a
  matching binary is supplied; intended fail-closed behaviour, and the error names the fix
  (ait setup, AIT_TESTMAP_BIN, ait engine build)'
tradeoff_engine_speed_enables_per_task_use: 'Advantage: sub-second select/check/stale on a
  720-test repo makes selection overhead negligible against the shortest test and lets check
  run at every commit step; a bash+Python engine would spend seconds in start-up and YAML
  parsing first'
tradeoff_real_scheduler: 'Advantage: goroutines plus flock(2) give correct cross-worktree
  contention and a critical-path report; the shell suite (owning the real index) and the pytest
  lane get the enforced do-not-overlap that is only a comment today, once a project flips
  concurrency from the serial bootstrap default after reviewing the schedule report'
tradeoff_noarch_packages_preserved: 'Advantage: Homebrew, AUR, .deb, .rpm and the tarball
  ship nothing compiled; the per-arch concern is contained in one release job and one setup
  function'
tradeoff_compiled_component_cost: 'Disadvantage: the framework gains a compiled component
  - contributors touching the engine need Go, a release fails if go test fails, install gains
  a fetch and checksum step; mitigated by a single build.sh matrix, ait engine build, and
  the engine being optional until a testmap gate is enabled'
tradeoff_engine_version_skew: 'Disadvantage: one user with several projects on different framework
  versions keeps several ~10 MB binaries under ~/.aitask/engine/; mitigated by exact-version
  resolution in the shim (never newest-wins) and ait engine prune against the project registry,
  never a count-based prune'
tradeoff_stamp_churn: 'Disadvantage: confirming stamps rewrites test files, so a source named
  by 72 tests could yield a 72-file diff; mitigated more than in either parent - EVIDENCED
  rows need no rewrite until someone chooses --confirm-evidenced, --confirm-source makes a
  deliberate re-stamp one commit, only confirmation rewrites, and KIND_MISMATCH nudges such
  fan-out toward a scope'
tradeoff_broad_scope_coarseness: 'Disadvantage: a test scoped to a large area is selected
  for any change inside it; mitigated by ranking last at its distance, running only after
  a green unit wave, being cut first by the suite budget with the cut printed as DEFERRED,
  and the cost visible in schedule'
tradeoff_autonomous_confirmation_weak: 'Risk: treating a green test as evidence that a coverage
  claim still holds is weaker than review; narrowed - the only autonomous confirmation is
  --confirm-evidenced, which requires a pass whose tree held the current bytes of the specific
  source, records confirmed_by: <run_id>, and is re-opened by a later score miss; a STALE
  row is never confirmed without a human'
tradeoff_engine_absent_on_host: 'Risk: an unsigned macOS binary or a blocked download leaves
  a host without an engine; mitigated by ENGINE_MISSING naming the path and repair verb, --engine-from-source
  and --local-engine fallbacks, and the testmap gates exiting 3 (error), never skip, when
  the engine is absent'
tradeoff_evidence_requires_reachable_history: 'Risk: the evidence join can only suppress a
  STALE row when the anchoring commit is reachable, so a depth-1 CI clone or a fresh shallow
  worktree sees the precise digest verdict with no self-healing; the safe direction, and the
  reason --strict fails only on STALE_PATH; a repo-wide stale --all --strict job should run
  on a full clone or accept STALE noise'
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

The goal is the baseline's: a framework feature, generic across aitasks,
thinking_app, thinking_backend, aitasks_go and aitasks_mobile, that maintains
a relation between source files and test units, translates a task's change
set into the ranked set of tests that must run with a reason on every line,
runs them through project-defined runners under a standard contract, tracks
cost per unit by host class, learns from failures the map did not predict, is
enforced by gates so the map cannot rot silently, and is taught to agents by a
skill.

Both parents agree on the three departures from the baseline — a static Go
engine shipped per platform, a staleness stamp on annotations with a `stale`
verb and a procedure gate, and a separate table for high-level tests — and
disagree on almost every mechanism underneath. This node takes the stronger
mechanism from each side and, where the two are not merely different but
complementary, bridges them:

1. **One static Go binary, `ait-testmap`, built from `engine/` and installed
   per framework version under `~/.aitask/engine/v<VERSION>/`.** The name
   is n001's (`ait-<sub>` pattern; never confusable with the `aitestmap/`
   registry root), the source directory, off-PATH versioned install slot,
   embedded `contract` number, `ait engine build|test|cross|prune` verbs and
   registry-aware prune are n002's, the strict version handshake,
   `.sha256` sidecar, `--no-testmap` / `AIT_TESTMAP_FETCH=0` opt-out and the
   `AIT_TESTMAP_BIN` override are n001's. Dependencies are n001's minimal set
   plus `golang.org/x/sync` from n002 for the scheduler.

2. **Per-edge blob-digest stamps (n002) as the staleness key, run evidence
   (n001) as the healing anchor.** `testmap:covers <path> @<date>/<blob10>`
   makes staleness precise, history-free and diffable (`git diff <blob>
   <blob>` shows the reviewer exactly what changed). The committed
   `last_pass: {sha, at, run_id}` per unit lets `stale` prove, with one
   `git ls-tree` per distinct sha, that a test already passed against the
   *current* content of a changed source — such an edge is `EVIDENCED`, not
   `STALE`, and nobody is nagged to re-stamp 72 files because
   `aitask_update.sh` moved. A new bridging component, the **evidence join**,
   is what makes the two models one; where history is unreachable (a depth-1
   CI clone) the join yields nothing and the digest comparison alone decides,
   so n002's fail-safe guarantee is preserved.

3. **Broad tests in one registry directory (n002) with n001's selection
   policy.** Integration, e2e and device tests declare `testmap:area`,
   `testmap:scope` globs, or `testmap:trigger` globs and land in
   `registry/_scoped.yaml` beside the unit table's `_scanned.yaml` — one
   directory, one merge rule, five tables. They join the single ranked list
   at distance 1 with n002's kind ranking, but n001's explicit suite budget
   with `DEFERRED:` lines and budget-exempt `trigger` hits govern how many
   actually run, and n002's `broad_after_unit` wave policy governs when.

The two factual corrections the merge surfaced are recorded, not papered
over: the Go toolchain n002 called "already provisioned in release CI" is
provisioned only in `hugo.yml`, at Go 1.25.7, so `release.yml` needs its own
`setup-go` step at 1.26 (as n001 specified); and the PR-time Go check n001
placed in `contribution-check.yml` cannot live there because that workflow is
issue-triggered — it needs its own `engine-check.yml`. n001's boundary rule
("the binary never invokes `aitask_*.sh`") is kept, and n001's own data flow
that violated it (the binary running `aitask_change_surface.sh`) is replaced by
n002's shim piping.
<!-- /section: overview -->

<!-- section: decision_matrix [dimensions: component_*, assumption_*] -->
## Decision Matrix: What Was Taken From Which Parent, and Why

Every row names the alternative that was not taken and the reason. "Bridge"
means neither was taken as-is; the Conflict Resolutions section has the detail.

| aspect | n001_explorer_001a | n002_explorer_001b | chosen | why |
|---|---|---|---|---|
| binary name | `ait-testmap` | `aitestmap` | **n001** | `aitestmap` is also the registry root every repo carries; the `ait-<sub>` form cannot be confused with it in prose or `ls` |
| source dir / module | `go/`, `…/aitasks/go` | `engine/`, `…/aitasks/engine` | **n002** | names the component, not the language; keeps `go/` free for a future second Go component; both are tarball-excluded |
| install slot | `~/.aitask/bin/ait-testmap-<V>` + `ait-testmap` symlink on PATH | `~/.aitask/engine/v<V>/` off PATH | **n002** | a bare symlink on PATH is a "newest wins" pointer that skill-direct calls could hit without the version handshake; the versioned dir mirrors `~/.aitask/python/<ver>/`, an existing precedent; nothing needs PATH |
| version check | exact match to `.aitask-scripts/VERSION`, hard error | exact match, embeds version+commit+contract | **both** | n001's fail-closed handshake with n002's three embedded values and `CONTRACT_MISMATCH` on registry files |
| checksum bookkeeping | `.sha256` sidecar, skip re-download when it matches | verify then `version --json` must echo V | **both** | sidecar makes `ait setup` idempotent; the post-install self-check catches a wrong asset |
| fetch on miss | shim lazily fetches on first `ait testmap` | shim exits 3 `ENGINE_MISSING`, `ait setup`/`ait upgrade` install | **n002** | `ait upgrade` already reaches `aitask_setup.sh --source-only` via `install.sh` (verified), so the engine lands in the same run; a gate verifier that downloads binaries mid-run is a surprise network fetch |
| fallbacks | `AIT_TESTMAP_BIN`, pre-seeded dir, `--no-testmap`, `AIT_TESTMAP_FETCH=0` | `--local-engine`, `--engine-from-source`, `--force-engine` | **both** | disjoint sets; together they cover air-gapped, off-matrix and dev hosts |
| prune | keep two most recent | `ait engine prune` against `projects.yaml` | **n002** | a count-based prune can delete the version another registered project is still on |
| dev rebuild | `cd go && make install-dev`, `AIT_TESTMAP_DEV=1` | `ait engine build`, `AIT_ENGINE=dev` | **n002** | the mandate says one command; an `ait` verb is discoverable from the dispatcher and needs no `make`; `engine/build.sh` stays the single matrix (both) |
| CLI parsing | stdlib `flag` verb table | cobra | **n001** | the primary consumers are scripts and gates reading the line protocol; per-verb `--help` is a table lookup; the exit-code discipline needs custom handling either way; fewer modules in the supply chain |
| locks | `syscall.Flock` | `gofrs/flock` | **n001** | both targets are Unix; the wrapper's value is Windows, which is not built |
| concurrency primitives | own worker pool | `x/sync` errgroup + weighted semaphore | **n002** | cancel-on-first-error and bounded fan-out are where hand-rolled pools grow bugs |
| release build | 4-job matrix, upload/download artifacts | one `engine` job, `build.sh all` cross-compiles | **n002** | Go cross-compiles in-process; one job, no artifact plumbing, byte-identical to a local `ait engine cross` |
| `go test` in release | not run | `go vet && go test` before build | **n002** | a release must fail if the engine's tests fail |
| PR-time Go check | `go-check` job in `contribution-check.yml` | none | **n001, re-sited** | the intent is right; that workflow is issue-triggered, so a new `engine-check.yml` on `push`/`pull_request` with `paths: [engine/**]` carries it |
| asset names | `ait-testmap_<V>_<os>_<arch>`, `…_checksums.txt` | `aitestmap-v<V>-<os>-<arch>`, `…-SHA256SUMS.txt` | **n001 pattern, n002 checksum name** | `ait-testmap_<V>_<os>_<arch>` + `ait-testmap_<V>_SHA256SUMS.txt`, the `sha256sum -c` convention |
| change-set intake | binary execs `aitask_change_surface.sh` | shim pipes into `select --changes -`; `--changes <file>` for tests | **n002** | n001's own boundary rule forbids the binary invoking `aitask_*.sh`; n002's shape also makes the engine testable without the framework |
| stamp | `testmap:verified <sha> <date>` per block | `testmap:covers <path> @<date>/<blob10>` per edge | **n002** | per-edge precision; no history needed; the blob id is the join key to any commit's tree (`git rev-parse <sha>:<path>`), which is what makes the evidence bridge cheap |
| staleness key | commit reachability from an anchor | blob digest of working tree | **n002 as key, n001 as evidence** | bridge — see `component_evidence_join` |
| run evidence | `last_pass {sha, at}` per unit, committed in costs | `--confirm-run <run-id>` rewrites stamps | **n001 data, computed** | evidence is *computed* (the pass's tree held the current blob) rather than asserted (the test was green in some run); n002's autonomous-confirmation risk narrows accordingly |
| stale classes | `STALE_PATH` / `STALE_RUN` / `STALE_AREA` / `UNVERIFIED` | `STALE` / `DELETED` / `UNSTAMPED` / `REVIEW_DUE` | **union, renamed** | `STALE_PATH` (deleted or renamed, fail-closed) · `STALE` (n002's, = n001's `STALE_RUN` without evidence) · `EVIDENCED` (new) · `UNSTAMPED` (= `UNVERIFIED`) · `STALE_AREA` · `REVIEW_DUE` (opt-in) |
| stale report shape | `ANCHOR:`/`DECISION:` lines, `(t<N>)` culprit parsing | `SURFACE:`/`EDGES:`/`DISPLAY:`/`DECISION:`, `%25`/`%7C` encoding, content states exit 0 | **n002 shape, n001 culprits** | matches `aitask_verification_stale.sh` exactly; culprit task ids are added to `STALE_PATH` rows when history is reachable |
| broad-test staleness | `STALE_AREA` (files in area changed, no pass since) | `REVIEW_DUE` (90-day cadence) | **n001 default, n002 opt-in** | a calendar key is the thing both parents rejected for unit edges; evidence-based drift is consistent; `broad_review_days` stays available, default 0 (off) |
| broad-test storage | `aitestmap/suites/` (second merged directory) | `registry/_scoped.yaml` in the one directory | **n002** | one directory, one merge rule; n001 itself lists the second directory as a disadvantage |
| broad vocabulary | `area`, `trigger` | `area`, `scope`, `reviewed` | **union** | `area` (named, reusable), `scope` (inline globs, budgeted), `trigger` (inline globs, budget-exempt), `reviewed` (display, optional cadence) |
| covers on broad tests | forbidden | allowed for fixture pins | **n002** | a handful of digest-stamped pins on an e2e test is precise coverage, not graph pollution; the fan-out guard applies to unit kind only |
| covers guard | 8 → fail, `CONVERT_TO_SUITE:` | 6 → `KIND_MISMATCH:` warn, fail under `--strict` | **8, warn, fail under `--strict`** | neither parent measured the covers distribution, so the guard is a nudge, not a fact: the looser threshold with the softer escalation cannot fail a bootstrap on day one; `--strict` hardens it once a repo is mapped |
| broad selection | separate lane 2, own budget, `DEFERRED:` lines, triggers always run | join at d1, kind ranking, `--budget-s` trims broad first | **one list (n002), n001 policy** | one ranked list and one prediction record keep "a reason on every line"; the suite budget applies only to broad rows and prints every cut |
| scheduler waves | `concurrency: report\|execute`, default `report` | goroutines, `broad_after_unit`, `--serial` | **n002 mechanism, n001 caution** | real scheduler with `broad_after_unit`; `concurrency: serial\|parallel` defaults to `serial` at bootstrap and is flipped per project after the schedule report is reviewed |
| reference runners | project-local bash, Go validates | built into the binary, `builtin:` scheme, project script shadows | **n002 + `command:` override** | five repos should not each carry the same JUnit/`go test -json` parsing in bash; the override keeps the boundary (a builtin execs the configured command, e.g. the framework venv's python, and never sources shell state) |
| serial carve-out | `testmap:batch no` on the test | `serial` list in `aitestmap/config.yaml` | **n001** | the list already exists in two drift-guarded places; a third copy is what `planning_conventions.md` warns about; the annotation lives in the file it describes and `test_serial_carveout_doc_drift.sh` is extended to pin it |
| gate names | `testmap_fresh` / `testmap_check` / `testmap_run` | `testmap_current` / `testmap_check` / `testmap_select` | **n001** | the procedure gate is named by the report's own decision word (`DECISION:FRESH`); `run` names the outcome the gate checks, `select` names a step |
| gate chaining | `fresh → check → run` via `unlocks:` | none | **`check → run` only** | a procedure gate is deferred by the headless engine; a machine gate unlocked by it would be blocked in every headless run — `check` fails `STALE_PATH` rows on its own, so it does not need the procedure to have run |
| run gate retries | `max_retries: 3` | `max_retries: 1` | **n002** | admission `75` is deferred and retried *inside* the engine until the run deadline; a verifier `3` after that is a real error |
| run outputs | `.aitask-gates/<task>/testmap/` | `.aitask-testmap/runs/<run-id>/`, `AIT_TESTMAP_DIR` | **n002** | run-id keyed, works for CI and `--all` runs with no task; verifiers still log under `.aitask-gates/<task>/` |
| local ledger | `$XDG_CACHE_HOME/…/ledger/<hostclass>.jsonl` | `.aitask-testmap/ledger.jsonl` | **n002** | the ledger is per repository (its units are repo paths); a user-wide cache would mix repos |
| lock fallback dir | `$XDG_CACHE_HOME` when `XDG_RUNTIME_DIR` unset | `${TMPDIR:-/tmp}/…-<uid>` | **n002** | a cache dir survives reboots; stale lock files would too |
| area seeding | `areas --import-codemap` from `code_areas.yaml` | — | **n001** | free bootstrap for repos that already have a code map |
| classify heuristics | `classify --suggest` (tmux, `./ait` exec, carve-out, covers limit) | — | **n001** | turns the "which table" question into a report during bootstrap |
| performance budget | targets table; validated before gates enabled | pool capped at 8; `-bench` regression past 2× fails CI | **both** | one table below; the 2× rule and the cap are how it is enforced |
| Python docstring scan, unknown-key refusal | yes | — | **n001** | the repo's docstring `Covers:` habit needs a home; a typo in a key must not silently drop an edge |
| line-targeted rewriter, `REWRITE_CONFLICT:` | — | yes | **n002** | required by per-edge stamps; refuses to clobber an intervening edit |
| engine's own tests on the map | `go-test` over `go/` | — | **n001** | the engine should eat its own selection |
<!-- /section: decision_matrix -->

<!-- section: architecture [dimensions: component_go_engine, component_engine_binary, component_binary_distribution, component_engine_packaging, component_registry_loader] -->
## Architecture

### Process boundary

```
ait testmap <verb> ...                          (user / skill / gate verifier)
 └─ .aitask-scripts/aitask_testmap.sh           bash shim, ~30 lines:
      │   resolve  $AIT_TESTMAP_BIN  >  AIT_ENGINE=dev → ~/.aitask/engine/dev/ait-testmap
      │            >  ~/.aitask/engine/v$(cat .aitask-scripts/VERSION)/ait-testmap
      │   verify   `<bin> version` == VERSION (dev slot: <VERSION>-dev+<sha>), else ENGINE_MISSING / ENGINE_MISMATCH, exit 3
      │   for --task verbs: aitask_change_surface.sh list <id>  |  <bin> <verb> --changes - ...
      └─ ~/.aitask/engine/v<VERSION>/ait-testmap --repo-root "$AIT_DIR" <verb> ...
           internal/registry        merge aitestmap/registry/*.yaml → edges, scopes, areas, rules, waivers; owns: routing; check rules
           internal/annot           grammar v2 scanner (per leader, Python docstrings), stamp reader, line-targeted rewriter
           internal/deps            bash/python/go/kotlin/gradle forward-dep scanners + plugin exec; blob-keyed cache; inverted in memory
           internal/changesurface   parser for BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines
           internal/selectr         graded walk, rules engine, scoped join at d1, kind ranking, suite budget, stale marks, prediction record
           internal/sched           errgroup waves, flock slot files, admission/allocator exec, broad_after_unit, schedule report
           internal/runner          manifest/results codec, bindings, builtin: runners, units_expected/units_reported, exit mapping
           internal/cost            Welford + P² p95 ledger, fold, last_pass anchors, flake rate
           internal/feedback        score, attribute (unit edges; area/trigger widening)
           internal/stale           digest compare, evidence join, classes, confirm/retarget
           internal/gitx            git via os/exec: rev-parse, ls-tree, merge-base --is-ancestor, log --name-status -M (rename hints)
           internal/platform        os/arch naming shared with engine/build.sh
             ├─ exec:  git, runner scripts or builtin runners, admission/allocator commands, scanner plugins
             └─ files: aitestmap/** (committed) · .aitask-testmap/ (runs, ledger; gitignored) ·
                       ${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/ · ${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/
.aitask-scripts/aitask_gate_testmap_check.sh    machine verifier  <task> <attempt> <run-id> → check --task
.aitask-scripts/aitask_gate_testmap_run.sh      machine verifier  → select --include-stale → schedule → run
.aitask-scripts/aitask_engine.sh                ait engine build | test | cross | prune   (framework developers)
.claude/skills/aitask-gate-testmap-fresh/       procedure gate: consumes `stale` lines, fixes annotations, `verify`
.claude/skills/aitask-testmap/                  agent skill: annotate, attribute, waive, verify, classify
engine/                                          Go source — framework repo only; excluded from the release tarball
```

**Boundary rule (n001, now honoured everywhere).** Anything that parses,
walks, matches, digests or schedules is Go. Anything that touches the gate
ledger, the task file, or the shell environment is bash and calls the binary.
The binary never writes to `aitasks/`, `aiplans/` or `.aitask-data/`, never
appends to a gate ledger, and never invokes `aitask_*.sh` — the shim pipes
the change surface in (n002), and the two verifiers own their side effects
through `aitask_gate.sh append`, exactly as `aitask_gate_tests_pass.sh` does.
Builtin runners exec the command `runners.yaml` gives them; they never source
`python_resolve.sh` or any other shell state.

### Go module (`engine/`, n002 layout)

```
engine/
  go.mod                 module github.com/beyondeye/aitasks/engine; go 1.26; toolchain directive pinned
  build.sh               the ONE place GOOS/GOARCH matrix, CGO_ENABLED=0, -trimpath, -buildvcs=false,
                         -ldflags "-s -w -X main.version=<V> -X main.commit=<sha> -X main.contract=1" live
  cmd/ait-testmap/main.go   stdlib `flag` verb table; per-verb --help; line protocol / --json
  internal/<pkg>/        as above
  testdata/              golden registries; fixture repos created with `git init` in t.TempDir(), never the framework repo
```

Dependencies: `gopkg.in/yaml.v3` (registry codec, key order preserved for
deterministic writes; already used by `aitasks_go`), `github.com/bmatcuk/doublestar/v4`
(`**` globs for bindings, `owns:`, areas, scopes, triggers),
`golang.org/x/sync` (`errgroup`, weighted semaphore). Everything else is the
standard library: `flag`, `os/exec`, `encoding/json`, `crypto/sha1` (blob
digests), `crypto/sha256` (asset checksums), `syscall.Flock`. No cobra, no
go-git, no gofrs/flock. Git is a hard framework dependency and the same `git`
the shell scripts use must see the same repository state (worktrees,
`commit --only`, task-data branches); the alternatives are named in the
decision matrix.

### Where state lives

| data | location | rationale |
|---|---|---|
| registry, runners, resources, areas, committed costs | `aitestmap/**` in the code tree | inherited: versioned with the code |
| run outputs, prediction records, local ledger | `.aitask-testmap/runs/<run-id>/`, `.aitask-testmap/ledger.jsonl` (gitignored by `ait setup`; `AIT_TESTMAP_DIR` override) | the framework's `.aitask-gates/` / `.aitask-explain/` pattern; run-id keyed so CI and `--all` runs need no task |
| gate logs | `.aitask-gates/<task>/<gate>_<run-id>.log` | the verifier template; points at the run dir |
| dependency-scan cache | `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` | regenerable, content-addressed (`artifact_utils.sh` precedent) |
| host-scope locks | `${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/aitasks-testmap-<uid>/<resource>.<slot>.lock` | `flock(2)`; does not survive a reboot, needs no cleanup |
| engine binaries | `~/.aitask/engine/v<VERSION>/ait-testmap` (+ `.sha256`), `~/.aitask/engine/dev/ait-testmap` (+ `.dev` marker) | mirrors `~/.aitask/python/<ver>/`; never on PATH |

### Registry directory (one directory, five tables)

```
aitestmap/
  config.yaml            unit_covers_max: 8 · suite_budget_s: 600 · bootstrap_until · require_stamp · broad_review_days: 0
                         concurrency: serial|parallel · broad_after_unit: true · device_policy: filter_by_resource
                         host_class · flake_threshold: 0.2
  runners.yaml           runner repository (builtin: or script), bindings, command: overrides
  resources.yaml         named resources (mutex / semaphore / admission / allocator; host / worktree / run)
  registry/
    _scanned.yaml        generated: unit edges with @date/blob10 stamps          written only by scan --apply
    _scoped.yaml         generated: broad rows (areas, globs, triggers, reviewed)  written only by scan --apply
    observed.yaml        written only by attribute: observed edges, observed area members, observed triggers
    areas.yaml           hand-written named glob sets (seedable via `areas --import-codemap`)
    <area>.yaml          hand-written: owns: [globs | area names], edges, scopes, rules, waivers, areas:
  costs/<hostclass>.yaml Welford n/mean/sd/p95/last + last_pass {sha, at, run_id} + flake per unit
  runners/*.sh           optional project runners (a script named like a builtin shadows it)
  scanners/*             optional executable scanner plugins
```

Merge rule: every file under `registry/` contributes rows to the same five
tables (edges, scopes, areas, rules, waivers). `owns:` lists globs (for edges
and rules) and area names (for hand-declared scopes); a row outside its file's
`owns:` fails `check`; `declare` routes by `owns:` and refuses when nothing
matches. The loader validates the `contract:` number per file and refuses a
newer contract with exit 3 and `CONTRACT_MISMATCH:<file>|<have>|<want>`.
<!-- /section: architecture -->

<!-- section: data_flow [dimensions: component_selector, component_staleness_tool, component_freshness, component_evidence_join, component_cost_ledger, component_engine_packaging, component_binary_distribution] -->
## Data Flow

### Authoring → registry

```
test files ──annotations──▶ ait testmap scan --apply ──▶ registry/_scanned.yaml   unit edges  {test, covers, from: annotation, line, stamped_at, stamped_blob}
                                                     └▶ registry/_scoped.yaml    broad rows  {test, kind, areas, globs, triggers, needs, reviewed_at, line}
hand files + areas.yaml + observed.yaml ────────────▶ merged registry (in memory, five tables)
```

`scan` asks every runner's `list` verb for the units it owns, reads each file
once, matches `testmap:` lines with a compiled regexp per comment leader (and
Python module docstrings), refuses unknown keys with a line number, and
rewrites each generated file only when its content changed, keys sorted, so a
hot-file confirmation diff touches only the stamped rows.

### Task → selection → run

```
aitask_change_surface.sh list t1234 ──▶ BASELINE:/PLANSCOPE:/COMMITTED:/TASK:/OTHER:/UNKNOWN: lines
        │  (the shim pipes; exit codes carry no meaning, lines do)
        ▼
ait-testmap select --task t1234 --changes - --include-stale [knobs] --run <run-id>
        ├─ UNKNOWN: present ──▶ refuse (exit 1, the lines echoed)
        ├─ exclude aitasks/ aiplans/ .aitask-data/ .aitask-gates/ before the walk (the script's own excludes)
        ├─ walk:  d0 changed tests + escalation · d1 unit edges + scoped join (area/scope/trigger glob match)
        │         d2.. reverse-dependency hops from the blob-keyed cache · rules inject select/implies/escalate
        ├─ stale: `stale` mark on a unit row when a selecting edge's stamped_blob ≠ current blob and no evidence covers it
        ├─ union: --include-stale adds every STALE-row test at distance s, reason `stale-evidence <source>`
        ├─ rank:  distance → kind (unit < integration < e2e < device) → est. cost ascending
        ├─ budget: broad rows ordered by p95, run until suite_budget_s; remainder printed DEFERRED:<test>|budget;
        │          trigger hits are never deferred
        └─ write .aitask-testmap/runs/<run-id>/{selection.json, prediction.json}   (per-kind estimates)

ait-testmap schedule --run <run-id>  ──▶ waves, holds, critical path, est. wall vs serial sum; check half flags undeclared runner-default resources
ait-testmap run --run <run-id>       ──▶ per invocation: manifest.json → builtin or script runner → results.jsonl, runner.json
        ├─ wave 1: unit kind · wave 2+: broad kinds only if wave 1 is green (broad_after_unit; --no-fail-fast disables)
        ├─ concurrency: serial (default at bootstrap; prints the schedule it would have used) | parallel (errgroup + flock)
        ├─ every result line → .aitask-testmap/ledger.jsonl with run_id, unit, status, duration_ms, head_sha
        ├─ units_expected ≠ units_reported → mechanism failure, never a pass
        └─ run.json: aggregate status; exit 0 / 1 / 2 (nothing selected) / 75 (admission refused past deadline) / 64 (usage)
```

### Results → evidence → cost

Every passing result line whose invocation's `runner.json` carries no
`cause`, for a unit under the flake threshold, advances the unit's
`last_pass: {sha: HEAD, at, run_id}` in the local ledger. `costs --update`
folds the ledger into `aitestmap/costs/<hostclass>.yaml` (Welford
`n/mean/sd/p95/last`, `last_pass`, per-run flake rate, per-invocation
overhead rows) and truncates the ledger. The anchor is therefore committed
with the code and available on a fresh clone — without which the evidence
join below would only ever see this host's runs.

### Post-implementation → staleness → fix in the same commit

```
aitask_change_surface.sh list t1234  |  ait-testmap stale --task t1234 --changes -
        ├─ for each edge whose source is in the change set:
        │     current_blob = sha1("blob <len>\0" + working-tree bytes)                 (no git needed)
        │     source missing                       → STALE_PATH:<test>|<source>|deleted|<culprits>
        │     rename hint (git log -M, if history)  → STALE_PATH:<test>|<source>|renamed|<new>|<culprits>
        │     stamped_blob == current_blob          → fresh (no line)
        │     stamped_blob ≠ current_blob:
        │         evidence join: ∃ last_pass.sha ancestor of HEAD with ls-tree(sha, source) == current_blob
        │            yes → EVIDENCED:<test>|<source>|<stamped>|<current>|<sha>|<run_id>
        │            no  → STALE:<test>|<source>|<stamped_at>|<stamped>|<current>
        │     no @stamp                            → UNSTAMPED:<test>|<source>
        ├─ broad rows: area/scope files changed since the test's last_pass and no pass since → STALE_AREA:<test>|<area>|<n_files>|<n_commits>
        │              reviewed_at older than broad_review_days (only when > 0)        → REVIEW_DUE:<test>|<area>|<reviewed_at>|<age_days>
        ├─ UNKNOWN:<path>|<reason>  from the change surface; drives the decision
        └─ DISPLAY:<summary>  DECISION:FRESH|REVIEW|SKIP           (content states exit 0; --strict exits 1 on STALE_PATH)

procedure gate testmap_fresh (attended agent; autonomous rules below)
        ├─ STALE_PATH  → edit or retarget the covers line (`--retarget <test>:<old>=<new>`; culprit task's plan names the successor)
        ├─ STALE       → show `git diff <stamped_blob> <current_blob>`; confirm / retarget / annotate --covers new / --drop; follow-up task
        ├─ EVIDENCED   → `stale --confirm-evidenced` re-stamps them in bulk (records confirmed_by: <run_id>)
        ├─ UNSTAMPED   → outside bootstrap_until: verify now or waive with an until date
        ├─ STALE_AREA  → count reported; consumed by the run gate's --include-stale
        └─ ait testmap scan --apply ; aitask_gate.sh append --only-if-running <run-id> t1234 testmap_fresh pass|skip|fail
           → the stamp rewrites ride the task's (t1234) commit
```

### Full run → score → attribute

`ait testmap run --all` is the same machinery with every unit selected.
`score --run <full-run> --prediction <run-id>` splits failures into caught /
missed. A missed unit test proposes an observed edge; a missed broad test
proposes `missing-trigger` (adds a trigger glob) or `area-too-narrow` (adds a
path to the area). `attribute` accepts a proposal with a decision, task and
run id, writing to `registry/observed.yaml`; observed area members and
triggers are merged into their area at load, so evidence widens a scope
without editing `areas.yaml` by hand.

### Release → host

```
git tag v0.36.0 ──▶ release.yml
   ├─ plan
   ├─ engine  (needs: plan)   setup-go (go-version-file: engine/go.mod) → go vet ./... → go test ./...
   │                          → engine/build.sh all 0.36.0 → dist/ait-testmap_0.36.0_{linux,darwin}_{amd64,arm64}
   │                                                        + dist/ait-testmap_0.36.0_SHA256SUMS.txt → upload-artifact
   ├─ release (needs: [plan, engine])  Verify VERSION == tag (unchanged) → tarball (noarch, engine/ excluded)
   │                                   → action-gh-release files: tarball + shim + 4 binaries + SHA256SUMS (both steps)
   └─ packaging (unchanged)            Homebrew / AUR / .deb / .rpm ship only the shim; nfpm arch: all
.github/workflows/engine-check.yml  (new)  on: push, pull_request  paths: [engine/**]  → gofmt -l, go vet, go test

ait setup   (or ait upgrade → install.sh --force → aitask_setup.sh --source-only → install_engine_binary, beside install_global_shim)
   ├─ os = uname -s → linux|darwin ; arch = uname -m → amd64|arm64 ; else ENGINE_UNSUPPORTED (skip, exit 0)
   ├─ ~/.aitask/engine/v<V>/ait-testmap exists and .sha256 sidecar matches → return
   ├─ --local-engine <path>  |  curl -fsSL --max-time 60 <asset> + SHA256SUMS from releases/download/v<V>/  |  --engine-from-source
   ├─ sha256sum -c (shasum -a 256 on macOS) → install -m 0755 to .tmp → mv -f (atomic) → write .sha256
   ├─ `<bin> version --json` must echo <V>, else remove and fail loudly
   └─ --no-testmap / AIT_TESTMAP_FETCH=0 → TESTMAP_BINARY:skipped:<reason>; the rest of setup never depends on the engine

ait engine build   → engine/build.sh host → ~/.aitask/engine/dev/ait-testmap, .dev marker {source, commit}, ENGINE_BUILT:<path>|<commit>
ait engine test    → go vet + go test ./... [-race]        ait engine cross → build.sh all into engine/dist/ (identical to CI)
ait engine prune   → remove ~/.aitask/engine/v*/ no project in ~/.config/aitasks/projects.yaml is on
AIT_ENGINE=dev ait testmap ...   → shim picks the dev slot (version must read <V>-dev+<sha>)
```
<!-- /section: data_flow -->

<!-- section: freshness [dimensions: component_freshness, component_staleness_tool, component_evidence_join, assumption_blob_digest_is_staleness_key, assumption_git_history_is_freshness_clock, assumption_passing_run_anchors_edges] -->
## Annotation Freshness: Digest Key, Evidence Anchor

### The stamp (n002)

```
# testmap:kind unit
# testmap:covers .aitask-scripts/aitask_gate_pass.sh        @2026-09-16/8f3a1c2d9e
# testmap:covers .aitask-scripts/lib/gate_verifier_lib.sh   @2026-09-16/41b0c7e2aa
```

`<blob10>` is the first ten hex digits of the git blob object id of the
covered source's content when the claim was last confirmed —
`sha1("blob <len>\0" + bytes)`, what `git hash-object` prints — computed in
Go without invoking git. Humans never type it: `annotate`, `verify` and
`stale --confirm*` write it through the line-targeted rewriter, which refuses
(`REWRITE_CONFLICT:`) if the text at that line no longer matches the registry
row. The date is for the reader; the digest is what is compared. A repository
using git's sha256 object format is detected once (`git rev-parse
--show-object-format`) and stamped with the matching function.

Why per-edge digest rather than n001's per-block `testmap:verified <sha>
<date>`: a block stamp says "all of these held at commit X" and needs history
to say anything at all; a per-edge digest says "this claim was confirmed
against exactly this content", needs no history, and gives the reviewer the
exact source diff (`git diff <stamped_blob> <current_blob>`) — which is what
the procedure gate shows. The block stamp's one advantage, low churn, is
recovered below without it.

### The anchor (n001) and the evidence join (new)

Re-flagging every edge whenever its source changes would be noise:
`aitask_update.sh` is named by 72 tests. Most of that staleness is
self-healing, because a test that ran and passed against the current content
of a source has demonstrated that its edge still holds at least as far as a
test can. So:

- Every passing result line records `last_pass: {sha: <HEAD at run>, at,
  run_id}` for its unit in the local ledger and, after `costs --update`, in
  the committed `costs/<hostclass>.yaml` (any host class counts). Lines from
  an invocation whose `runner.json` has a `cause`, and units whose flake rate
  exceeds `flake_threshold`, never anchor.
- For an edge whose `stamped_blob ≠ current_blob`, the **evidence join** asks:
  is there a `last_pass.sha` for this test, reachable from HEAD
  (`git merge-base --is-ancestor`), whose tree holds the source at exactly
  `current_blob`? Implementation: group mismatched edges by candidate sha,
  run one `git ls-tree <sha> -- <paths...>` per distinct sha under a bounded
  pool, compare object ids. A hit is `EVIDENCED`; no hit is `STALE`.
- Where the sha is not in the fetched history (a depth-1 CI clone, a shallow
  worktree) the join yields nothing and the edge is `STALE` — the fail-safe
  direction. Digest comparison itself never needs history, so n002's
  guarantee ("works in a depth-1 checkout") is intact; history only ever
  *removes* nags.

This is the bridge between the parents' two models and it is deliberately
narrower than n002's `--confirm-run <run-id>`: that flag treated "the test was
green in run R" as confirmation; the join requires that run R's tree held the
*current* bytes of the specific source. `stale --confirm-evidenced` then
re-stamps exactly the `EVIDENCED` rows (recording `confirmed_by: <run_id>`),
which is the only bulk confirmation an autonomous profile may perform.

### Classes and report (n002 shape, union of classes)

`ait testmap stale (--task <id> --changes - | --all) [--strict] [--json]`
prints, in the fixed-line shape of `aitask_verification_stale.sh` (fields
`|`-separated, `%`→`%25` then `|`→`%7C`; every content state exits 0; only
CLI misuse exits non-zero; `--strict` exits 1 on `STALE_PATH` for CI):

```
SURFACE:task|all
EDGES:<n>                                                   stamped unit edges examined
STALE_PATH:<test>|<source>|deleted|<culprit_tasks>          source gone; fail-closed in check
STALE_PATH:<test>|<source>|renamed|<new_path>|<culprit_tasks>   rename hint from git log -M when history is reachable
STALE:<test>|<source>|<stamped_at>|<stamped_blob>|<current_blob>   content changed, no pass evidence → review
EVIDENCED:<test>|<source>|<stamped_blob>|<current_blob>|<run_sha>|<run_id>   content changed, a pass held it → bulk re-stamp
UNSTAMPED:<test>|<source>                                   no @stamp; tolerated until bootstrap_until, then a check failure under require_stamp
STALE_AREA:<test>|<area-or-glob>|<n_files>|<n_commits>      broad row: files in scope changed since last_pass, no pass since → selection input
REVIEW_DUE:<test>|<area-or-glob>|<reviewed_at>|<age_days>   broad row: only when config broad_review_days > 0 (default 0)
UNKNOWN:<path>|<reason>                                     change-surface UNKNOWN: paths; drives the decision
DISPLAY:<one-line human summary>
DECISION:FRESH|REVIEW|SKIP
```

`--task` restricts sources to the task's `COMMITTED:`/`TASK:` paths, which is
what makes the in-task check precise even for same-day edits; `--all` is the
repo-wide sweep (a weekly CI job and a board action). `check` fails on any
`STALE_PATH` row and, after `bootstrap_until`, on `UNSTAMPED` rows when
`require_stamp: true`. `select --include-stale` (the run verifier's default)
adds every `STALE`-row test at distance `s` with reason
`stale-evidence <source>`, so a test whose source changed without a
subsequent pass gets run — and on passing becomes `EVIDENCED`.

Culprit task ids on `STALE_PATH` rows are parsed from `(t<N>)` commit
subjects between the test's last anchor and HEAD when history is reachable
(n001), matching the `CHANGED:<path>|<n_commits>|<task_ids>` habit of the
manual-verification report; without history the field is empty.

### Mutations

`verify <test>...` (re-stamp every edge of a test after editing its
annotations), `stale --confirm <test>:<source>`, `--confirm-source <path>`
(every annotation on one hot source at once — one commit, not 72 nags),
`--confirm-evidenced`, `--retarget <test>:<old>=<new>`, and
`annotate <test> --covers/--drop/--area/--scope/--trigger/--kind/--runner/--needs`.
Confirmation is the only thing that rewrites a stamp; a source edit alone
never touches a test file, and gate runs never dirty the tree.

### The procedure gate

`testmap_fresh` is a `kind: procedure` gate (the `docs_updated` shape),
dispatched by the existing generic procedure-gate block of the
post-implementation step — before the change summary, so the rewritten stamps
and annotation edits are part of the reviewed diff and land in the task's
`(t<id>)` commit. It is not a git hook (the framework installs none, and
`commit --only` makes a pre-commit hook unusable) and not a Claude Code hook
(those must stay silent and cannot take an editing decision). The
`aitask-gate-testmap-fresh` skill:

1. `aitask_gate.sh begin-procedure <task> testmap_fresh` → `RUN_ID:`, `ATTEMPT:`.
2. `ait testmap stale --task <task>` (the shim pipes the change surface).
3. `UNKNOWN:` paths: resolve with the user; under an autonomous profile
   exclude and log them — never guess.
4. `STALE_PATH:` rows: retarget to the renamed path, or to the successor the
   culprit task's plan names; else drop the line and note it.
5. `STALE:` rows: show `git diff <stamped_blob> <current_blob> --stat` and the
   hunks; ask confirm / retarget / `annotate --covers <new>` / `--drop` /
   follow-up task. Autonomous profiles never confirm a `STALE:` row.
6. `EVIDENCED:` rows: `stale --confirm-evidenced` (allowed autonomously).
7. `UNSTAMPED:` rows outside the bootstrap window: verify now or waive with an
   `until` date.
8. `ait testmap scan --apply`; `aitask_gate.sh append --only-if-running
   <run-id> <task> testmap_fresh pass|skip|fail` with per-class counts and the
   resolved/unresolved rows in the sidecar log. `pass` when every
   `STALE_PATH`/`STALE`/`UNSTAMPED` row for the task's sources was resolved;
   `skip` on `DECISION:FRESH` or `SKIP`; `fail` when rows remain.
<!-- /section: freshness -->

<!-- section: broad_tests [dimensions: component_suite_registry, component_broad_test_scopes, assumption_areas_express_suite_blast_radius, assumption_broad_tests_area_scoped] -->
## High-Level Tests: One Directory, Scoped Rows, Budgeted Selection

### Why they are not edges (both parents)

Measured on this repo: 4 tests are in the serial carve-out, 29 boot a real
tmux pane, 46 bash tests drive `./ait` end to end,
`tests/test_brainstorm_cli.sh` statically names 24 scripts. As `covers`
edges they would sit at distance 1 from most of the tree, every edit would
stale-flag them, and `_scanned.yaml` would carry thousands of rows meaning
"everything". So they are scoped rows in their own generated table.

### Vocabulary (union)

```
# testmap:kind e2e                        integration | e2e | device
# testmap:area brainstorm                 named glob set from areas.yaml (n001, n002); budgeted
# testmap:area agentcrew
# testmap:scope .aitask-scripts/aitask_*.sh          inline globs (n002); budgeted like an area
# testmap:trigger .aitask-scripts/lib/launch_modes*.py   inline globs (n001); a hit always selects, never deferred
# testmap:reviewed 2026-09-16              display; REVIEW_DUE only when broad_review_days > 0 (n002, opt-in)
# testmap:covers tests/fixtures/board_seed.yaml @2026-09-16/0c1d2e3f4a   optional fixture pin, digest-stamped (n002)
# testmap:runner bash-file   testmap:needs tmux-server   testmap:batch no
```

```yaml
# aitestmap/registry/areas.yaml   (hand-written; `ait testmap areas --import-codemap` seeds it from aitasks/metadata/code_areas.yaml as <path>/**)
contract: 1
areas:
  brainstorm: {paths: [".aitask-scripts/aitask_brainstorm_*.sh", ".aitask-scripts/brainstorm/**"]}
  agentcrew:  {paths: [".aitask-scripts/aitask_crew_*.sh", ".aitask-scripts/agentcrew/**", ".aitask-scripts/lib/agentcrew_utils.*"]}
  board:      {paths: [".aitask-scripts/board/**", ".aitask-scripts/aitask_board.sh"]}
  gates:      {paths: [".aitask-scripts/aitask_gate*.sh", ".aitask-scripts/lib/gate_*.sh", ".aitask-scripts/lib/gate_ledger.py", "aitasks/metadata/gates.yaml"]}
  install:    {paths: ["install.sh", ".aitask-scripts/aitask_setup.sh", "packaging/**", "seed/**"]}
```

`_scoped.yaml` rows: `{test, kind, runner, areas: [...], globs: [...],
triggers: [...], needs: [...], reviewed_at, line, from: annotation}`.
Concrete rows in this repo: `tests/test_no_unscoped_task_commit.sh`
(`integration`, `scope .aitask-scripts/aitask_*.sh`); `tests/test_gate_verifiers.sh`
(`integration`, `area gates`); `tests/test_frozen_agents_acceptance.sh` and
`tests/test_t167_integration.sh` (`e2e`, `area install`);
`tests/test_board_header_row_live.py` (`e2e`, `area board`, `needs git-index`,
`batch no`).

### Check rules (union)

- `kind` ∈ {integration, e2e, device} for scoped rows; a unit test carrying
  `area`/`scope`/`trigger` fails; a scoped row without at least one
  `area`/`scope`/`trigger` fails.
- Every named area exists; every area glob and scope glob matches at least one
  file (`DEAD_SCOPE:` — an empty glob is the rot signal for globs).
- A unit test with more than `unit_covers_max` (default 8) covers lines gets
  `KIND_MISMATCH:<test>|<n>|CONVERT_TO_SUITE` — a warning normally, a failure
  under `check --strict`.
- `ait testmap classify --suggest` lists scope candidates from heuristics —
  `tmux new-session`, an exec of `./ait`, membership in a runner's serial
  carve-out, covers above the limit — one matched heuristic per line, for
  the bootstrap pass (roughly 60–70 files here; the 107 headless
  `App.run_test` files are narrow and stay unit-mapped).

### Selection and scheduling of scoped rows

A scoped row joins the ranked list at distance 1 when the change set
intersects any glob of any of its areas, any scope glob, or any trigger
(`doublestar.Match`). Reasons read `area(brainstorm) <-
.aitask-scripts/aitask_brainstorm_init.sh`, `scope(.aitask-scripts/aitask_*.sh)
<- …`, `trigger(lib/launch_modes*.py) <- …`. Within a distance the list is
ranked unit < integration < e2e < device, then by estimated cost ascending
(n002). Scoped rows never contribute distance, never appear in `implies`,
and are sinks in the walk (n001). Then the budget (n001): trigger hits
always run; area/scope hits are taken in p95-ascending order until
`suite_budget_s` (config, default 600; `--suite-budget` overrides) is spent,
and the remainder is printed as `DEFERRED:<test>|budget` so every cut is
explicit and lands in the prediction record. `--suites auto|all|none`
selects the policy; the estimate line reports unit and broad totals
separately. A rule may `select:` a scoped test by name, which is how
thinking_app's "tooling change runs `verify-active`" becomes data.

In the scheduler, `broad_after_unit: true` (n002, default) makes wave 1
unit-kind invocations only; scoped rows run only if wave 1 is green, so a
cheap red unit test never pays for an 8-minute screenshot suite.
`device_policy: filter_by_resource` (n002, default) selects device units by
distance but runs them only when the emulator allocator can hand out a
handle.

### Feedback for scoped rows

A full-run failure in a scoped test the prediction did not select proposes a
row naming the changed paths outside its scope; `attribute` accepts it with
`missing-trigger` (an observed trigger glob) or `area-too-narrow` (an observed
area member), each with task and run id, written to `registry/observed.yaml`
and merged into the area at load. `STALE_AREA` rows — files in an area
changed since the test's `last_pass` with no pass since — are a selection
input via `--include-stale`, exactly like `STALE` rows for units.
<!-- /section: broad_tests -->

<!-- section: selection [dimensions: component_selector, assumption_change_surface_is_intake] -->
## Selection: the Graded Walk, One List

Intake is the change-surface line protocol — `BASELINE:`, `PLANSCOPE:`, then
`COMMITTED:`/`TASK:`/`OTHER:`/`UNKNOWN:` per path — piped in by the shim
(`--changes -`) or read from a file (`--changes <file>`, for engine tests
outside the framework). `COMMITTED:` and `TASK:` are the change set; `OTHER:`
is ignored; any `UNKNOWN:` refuses selection with exit 1 and the lines
echoed. The script says nothing through exit codes, so the parser trusts
lines only. Paths under `aitasks/`, `aiplans/`, `.aitask-data/`,
`.aitask-gates/` are excluded before the walk. A changed source with no edge,
no rule, no area, no scope and no waiver refuses the same way.

The graded walk is the baseline's: d0 for a changed test and for escalation,
d1 for a direct edge and for a scoped join, d2+ for reverse-dependency hops,
rules injecting at a declared distance with `select`, `implies`, `escalate`.
Reverse dependencies come from the in-process scanners (bash `source`/`.`
lines and `$SCRIPT_DIR/aitask_*.sh` sibling invocations; python
`import`/`from` resolved under configured roots with a small tokenizer;
`go list -deps -json ./...` once per run, cached by the `go.sum` digest;
Kotlin imports within a Gradle module plus the module graph from
`settings.gradle(.kts)` and `dependencies {}` blocks) and from executable
plugins under `aitestmap/scanners/` speaking one JSON line per file
(`{"file":…, "deps":[…]}`); forward deps are cached per source blob under
the XDG cache and inverted in memory, so a warm `select` rescans only what
changed.

```
tests/test_gate_pass.sh                 d=1 unit         edge(annotation, stale) .aitask-scripts/aitask_gate_pass.sh
tests/test_gate_orchestrator.sh         d=2 unit         dep lib/gate_verifier_lib.sh <- aitask_gate_pass.sh
tests/test_gate_ledger.sh               d=2 unit         rule gates-area
tests/test_update_risk.sh               d=s unit         stale-evidence .aitask-scripts/aitask_update.sh
tests/test_gate_verifiers.sh            d=1 integration  area(gates) <- .aitask-scripts/aitask_gate_pass.sh              est 12s
tests/test_no_unscoped_task_commit.sh   d=1 integration  scope(.aitask-scripts/aitask_*.sh) <- aitask_gate_pass.sh      est 9s
tests/test_board_header_row_live.py     d=1 e2e          DEFERRED budget  area(board)                                    est 48s
```

Every selected unit row carries a `stale` mark when any edge that selected it
is `STALE` (mismatched digest, no evidence) — visible in the reason column,
never a filter. `select` writes `selection.json` and `prediction.json` under
`.aitask-testmap/runs/<run-id>/` (`r-<YYYYMMDD>-<HHMMSS>-<4 hex>`; every later
artifact carries the id). The prediction record holds task, knobs, change
set, unit rows with distances, scoped rows with reasons and deferrals,
escalations fired, and the estimate per kind. Cuts are knobs applied after
ranking: `--max-distance`, `--budget-s`, `--kind`, `--resource-filter`,
`--suite-budget`, `--suites`. `explain <test|source>` prints the binding
chain, every reason path, and which runner (builtin or shadowing script) won.
<!-- /section: selection -->

<!-- section: runner_contract [dimensions: component_runner_contract, component_reference_runners, assumption_gate_exit_contract_reused, assumption_existing_locks_wrappable] -->
## Runner Contract, Builtin Runners, Exit Mapping

The three verbs (`describe`, `list`, `run --manifest <f> --out <d>`), the
manifest and `results.jsonl` / `runner.json` shapes, first-match bindings
with the per-test `testmap:runner` override, batching and `unit: suite`
wrappers are the baseline's. `runners.yaml` gains the `builtin:` scheme
(n002) and a `command:` override (new, to keep n001's boundary):

```yaml
runners:
  bash-file:    {exec: "builtin:bash-file",  unit: file,  batch: false, needs: [git-index]}
  pytest:       {exec: "builtin:pytest",     unit: file,  batch: true,  needs: [git-index],
                 command: ["$HOME/.aitask/venv/bin/python", "-m", "pytest"]}      # the framework venv; never resolved by the binary
  go-test:      {exec: "builtin:go-test",    unit: file,  batch: true}
  gradle-class: {exec: tools/verification/testmap_runner.sh, unit: class, batch: true, needs: [heavy-run]}
  verify-active:{exec: tools/verification/screenshot-tests.sh, unit: suite}
  engine-test:  {exec: "builtin:go-test",    unit: file,  batch: true,  cwd: engine/}   # the engine's own tests ride the map
bindings:
  - {glob: "tests/test_*.sh",  runner: bash-file}
  - {glob: "tests/test_*.py",  runner: pytest}
  - {glob: "engine/**/*_test.go", runner: engine-test}
  - {glob: "**/*_test.go",     runner: go-test}
```

Builtin runners (`ait-testmap runner <name> describe|list|run`): `bash-file`
(one process per file, stdout+stderr to `logs/<name>.log`), `pytest`
(one interpreter per invocation, `--junitxml` parsed for per-unit status and
duration; a unit annotated `testmap:batch no` gets its own invocation — this
repo's four serial-carve-out modules carry that annotation, and
`tests/test_serial_carveout_doc_drift.sh` is extended to pin the annotations
against the runner script's list so the two cannot diverge), `go-test`
(per-file `-run` regex from `func Test…` names, `-json` for per-test timing,
package setup attributed to every file in the package), `gradle-class`
(`--tests <fqn>` batch, JUnit XML), `suite` (any command as one unit),
`device` (takes the allocator handle from the manifest). A project script of
the same name under `aitestmap/runners/` shadows the builtin and `explain`
shows which won; `aitestmap/runners/` is therefore optional in target repos.
thinking_app keeps its own `gradle-class` and `verify-active` scripts.

Runner exit codes are unchanged (0 all passed; 1 a unit failed or the
mechanism broke, `cause` set only for the mechanism; 2 did not run for a
self-clearing reason; 75 admission refused); the engine's `run` adds 64 for a
usage or configuration error. `units_expected` vs `units_reported` is checked
per invocation and a mismatch is a mechanism failure, never a pass.

The verifier shells, not the engine, map to the framework's verifier
contract `0 pass / 1 fail / 2 skip / 3 error` (both parents' correction of
the baseline: `75` appears nowhere in the framework and
`gate_command_exit_contract` maps only command exits `0/1/2`):

| engine exit | `aitask_gate_testmap_run.sh` | `aitask_gate_testmap_check.sh` |
|---|---|---|
| 0 | 0 pass | 0 pass |
| 1 | 1 fail | 1 fail |
| 2 (nothing selected) | 2 skip | — |
| 75 (admission refused past the run deadline) | 3 error → retried within `max_retries` | — |
| 64 / other / engine absent (shim exit 3) | 3 error | 3 error |

Admission refusal and a missing engine must never become a skip, because a
skipped test gate reads as a pass. Verifier 3 appends nothing to the ledger.
These are dedicated verifiers following the `tests_pass` template, not
`run_command_gate` wrappers, because their command is fixed and their skip
semantics are richer than a config-key opt-in.
<!-- /section: runner_contract -->

<!-- section: gates [dimensions: component_gates, requirements_gate_enforcement] -->
## Gates

Registered in `.aitask-scripts/gates_reference.yaml` (canonical) and synced
to `aitasks/metadata/gates.yaml`; every field key already exists:

```yaml
  testmap_fresh:
    type: machine
    kind: procedure                              # skill aitask-gate-testmap-fresh; dispatched by the procedure-gate block
    description: "Source-to-test annotations on this task's changed sources reviewed and re-stamped"
    blocks_dependents: false
    verifier: aitask-gate-testmap-fresh
    max_retries: 0
    # unlocks ABSENT (linear-default), like docs_updated: a headless run defers procedure gates,
    # so no machine gate may depend on this one having run.
  testmap_check:
    type: machine
    description: "Test map consistent: changed sources mapped, tests registered, no drift, no rotted paths"
    blocks_dependents: false
    verifier: aitask-gate-testmap-check          # .aitask-scripts/aitask_gate_testmap_check.sh
    max_retries: 0
    timeout_seconds: 120
    unlocks: [testmap_run]
  testmap_run:
    type: machine
    description: "Selected tests (unit and scoped, stale-evidence included) pass"
    blocks_dependents: true
    verifier: aitask-gate-testmap-run            # .aitask-scripts/aitask_gate_testmap_run.sh
    max_retries: 1
    timeout_seconds: 1800
```

`testmap_check` does not depend on `testmap_fresh` having run: it fails
`STALE_PATH` rows (and, past bootstrap, `UNSTAMPED` rows under
`require_stamp`) on its own. The procedure gate exists so the fix happens
*before* the check fails, in the reviewed diff. A project enables the three
by adding them to its profile's declared gate set; `tests_pass` may stay for
a monolithic `test_command`; the manual-verification reachable-gate filter
leaves all three unreachable for `manual_verification` tasks, which is
correct. The full run is `ait testmap run --all`, the same machinery with
every unit selected, writing the same evidence under `.aitask-testmap/runs/`
or, for CI, `--out <dir>`.
<!-- /section: gates -->

<!-- section: go_engine [dimensions: component_go_engine, component_engine_binary, assumption_engine_latency_targets, assumption_go_toolchain_available, assumption_go_toolchain_ci_and_dev_only] -->
## The Go Engine: Why, and What It Must Cost

The wall time of a selected run is dominated by the tests, but the engine's
own latency is paid at every gate and every commit step (`select`, `check`,
`stale`), interactively (`explain`), and on every `scan`. The framework
already routes `ait board` through a PyPy fast path for exactly this class
of cost; a pure-Python parse of ~720 units and ~2,500–3,000 edges is in the
hundreds of milliseconds before any walk starts, and a real concurrent
scheduler with cross-process locks is something bash cannot do well and
Python does slowly. Targets on the aitasks repo, warm cache, pinned by
`go test -bench` fixtures with a golden registry in `internal/selectr`; a
regression past 2× fails `engine-check.yml`; the gates are not enabled here
until the benchmarks pass (n001 and n002 combined):

| verb | target | what dominates |
|---|---|---|
| `select` (with stale marks) | < 200 ms | YAML load + walk + digest of covered sources of selected units |
| `select` cold | < 1.5 s | ~270 files regex-scanned, blob-hashed, cached |
| `scan` | < 300 ms | ~720 file reads + comment parse over a pool |
| `check` | < 300 ms | merged-table rules + `list` per runner |
| `stale --task` | < 300 ms | digests of the task's sources + one `ls-tree` per distinct evidence sha |
| `stale --all` | < 2 s | same, whole registry |

The scanner and dependency passes fan out over a pool sized to
`runtime.NumCPU()`, capped at 8, so the engine never competes with the tests
it is about to launch.

CLI: `ait testmap <verb>` with verbs `scan | check | select | schedule | run |
stale | verify | annotate | score | attribute | declare | explain | costs |
areas | classify | runner | version`. Every verb prints fixed-prefix
`KEY:value` lines on stdout, `--json` prints one object, diagnostics go to
stderr, exit codes are per verb (`0` ok / findings-free, `1` refused or
failed, `2` nothing to do, `3` mechanism error, `64` usage). Mutating verbs
write only the files the registry's write-routing rules name and print
`WROTE:<path>` per file.

Go ≥ 1.26 is needed in release CI (added: `actions/setup-go@v5` with
`go-version-file: engine/go.mod` in the new `engine` job — `release.yml`
has no Go step today; the only `setup-go` is `hugo.yml`'s, at
`website/go.mod`'s 1.25.7, which is not this) and on framework developers'
machines; target-project users never compile.
<!-- /section: go_engine -->

<!-- section: components [dimensions: component_*] -->
## Components

Sources are annotated per component: *(inherited from nXXX)* names the parent
whose design was taken; *(merged from n001 and n002)* means both contributed
mechanisms as described; *(new: introduced to bridge n001 and n002)* is a
component neither parent had.

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(merged from n001 and n002)*

`engine/cmd/ait-testmap` (name: n001; layout: n002) plus the `internal/`
packages in the architecture; Go 1.26 with a pinned `toolchain` directive
(n002), `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w -X
main.version=<V> -X main.commit=<sha> -X main.contract=1"`. Dependencies
`gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4` (n001) and `golang.org/x/sync`
(n002); stdlib `flag` verb table (n001), `syscall.Flock` (n001). Line
protocol / `--json` / per-verb exit contracts; never writes `aitasks/`,
`aiplans/`, `.aitask-data/` or a gate ledger, never invokes `aitask_*.sh`.
Unit tests are table-driven against fixture repos built with `git init` in
`t.TempDir()`.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary: embedded identity, output contract, performance budget *(inherited from n002, targets merged)*

Embeds `version`, `commit`, `contract`; `version --json` is the install-time
self-check. Fixed-prefix structured output and `--json`. `CONTRACT_MISMATCH:`
refusal on registry files from a newer contract. Performance budget as in
the table above, pinned by `go test -bench` on the golden registry with the
2× regression rule; worker pool capped at 8.
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution: release assets and the host-side handshake *(merged from n001 and n002)*

`engine/build.sh` as the single build/matrix command (both); the `engine`
job in `release.yml` running `go vet`, `go test` and `build.sh all` into
four assets plus `ait-testmap_<V>_SHA256SUMS.txt`, uploaded by both
`action-gh-release` steps (n002 job shape, n001 asset naming); the `Verify
VERSION file matches tag` step unchanged, so a binary can never claim a
version its tarball lacks (n001); the new `engine-check.yml` on
`push`/`pull_request` with `paths: [engine/**]` (n001's intent, re-sited);
`lib/platform_detect.sh` (`ait_platform_os`, `ait_platform_arch`; WSL →
`linux`, else `unsupported`) (n001); the shim's strict version handshake —
`AIT_TESTMAP_BIN` explicit override with a `TESTMAP_BIN_OVERRIDE:` notice,
`AIT_ENGINE=dev` dev slot requiring `<V>-dev+<sha>`, versioned slot requiring
`== VERSION`, mismatch a hard error, absence `ENGINE_MISSING:<path>` exit 3
with the repair hint (n001 handshake, n002 env and messages). Bash tests:
`tests/test_testmap_shim.sh` (resolution order, mismatch, missing) and
`tests/test_platform_detect.sh`. Docs: `aidocs/framework/go_engine.md`
(layout, resolver order, handshake, build script), a `### Engine` block in
`CLAUDE.md`, and a paragraph in `aidocs/packaging/packaging_strategy.md`
stating that framework binaries are release assets fetched by `ait setup`
per host, never bundled by a package manager. `release-packaging.yml` and
`nfpm.yaml` (`arch: all`) are untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade and developer regeneration *(inherited from n002, n001 opt-outs added)*

`install_engine_binary()` in `aitask_setup.sh`, called from `ait setup` and,
because `install.sh` already sources `aitask_setup.sh --source-only` to run
`install_global_shim`, from `ait upgrade` in the same run: uname mapping,
`.sha256` sidecar short-circuit (n001), source order `--local-engine <path>`
→ release asset for the exact version → `--engine-from-source` (local `go`
≥ the module toolchain; off-matrix hosts) → `ENGINE_MISSING` warning and
continue; checksum via `sha256sum -c` / `shasum -a 256`; atomic
`install -m 0755` to `.tmp` then `mv -f`; `version --json` must echo `<V>`;
a `.dev`-marked binary is never overwritten without `--force-engine`;
`--no-testmap` / `AIT_TESTMAP_FETCH=0` print `TESTMAP_BINARY:skipped:<reason>`
and return 0 (n001). `ait setup` gitignores `.aitask-testmap/`.
`.aitask-scripts/aitask_engine.sh`: `build` (into the dev slot, `.dev`
marker, `ENGINE_BUILT:<path>|<commit>`), `test` (`go vet`, `go test`,
optional `-race`), `cross` (`build.sh all` into `engine/dist/`, identical to
CI), `prune` (versions no project in `~/.config/aitasks/projects.yaml` is on;
never automatic in `ait upgrade`). `engine/bin/`, `engine/dist/` gitignored.
Bash test: `tests/test_install_engine_binary.sh` through a real `install.sh
--dir <tmp> --local-engine`, per the rule that setup-flow changes are
exercised through a real install.
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(inherited from n002, n001 rules added)*

`internal/registry`: merges `aitestmap/registry/*.yaml` into five tables
(edges, scopes, areas, rules, waivers); `owns:` routing by glob (edges,
rules) and by area name (hand-declared scopes) (n001); write routing
(`scan --apply` → `_scanned.yaml`, `_scoped.yaml`; `attribute` →
`observed.yaml`; `declare` → the owning hand file, refusing when nothing
owns); deterministic writes (sorted keys, only when content changed); the
check rules: duplicate rule names, waiver-with-edge, annotation rows whose
annotation is gone, expired waivers, `STALE_PATH` rows, `UNSTAMPED` rows
past bootstrap under `require_stamp`, the scoped-row rules and
`DEAD_SCOPE:`, `KIND_MISMATCH:` above the covers limit, `CONTRACT_MISMATCH:`.
Golden tests pin the merge rule.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(merged from n001 and n002)*

`internal/annot`: grammar v2 — `kind`, `covers <path> @<date>/<blob10>`,
`area`, `scope`, `trigger`, `reviewed`, `runner`, `needs`, `batch` — per
comment leader (`#`, `//`, `--`) and Python module docstrings (n001);
refusal of unknown `testmap:` keys with a line number (n001); the
line-targeted rewriter keyed by (file, line, current text) with
`REWRITE_CONFLICT:` refusal, preserving line endings and every other byte
(n002); `kind` decides the association form and `check` enforces it. Produces
both generated files from the union of every runner's `list` output.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(merged from n001 and n002)*

`internal/deps`: built-in bash, python, go (`go list -deps -json`, cached by
`go.sum` digest), kotlin and Gradle module-graph scanners; executable plugins
under `aitestmap/scanners/` with the one-JSON-line-per-file contract (n001);
forward deps cached per source blob under
`${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` and
inverted in memory (n002).
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(merged from n001 and n002)*

`internal/selectr` and `internal/changesurface`: line-protocol intake via
`--changes` (n002), refusal on `UNKNOWN:`, the graded walk with rules, scoped
join at d1, kind-then-cost ranking (n002), `stale` marks from the digest
compare plus evidence join, `--include-stale` union at distance `s` (n001),
the suite budget with `DEFERRED:` lines and budget-exempt triggers (n001),
cut knobs, the prediction record with per-kind estimates, `explain`.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(merged from n001 and n002)*

`internal/runner`: `runners.yaml` loading with the `builtin:` scheme and
`command:`/`cwd:` overrides, first-match bindings and the per-test override,
manifest writing, `results.jsonl`/`runner.json` reading,
`units_expected`/`units_reported` reconciliation, batching by (runner,
resource set, batch flag), per-unit timeouts, the exit contract
`0/1/2/75/64`, and the shadowing rule (project script beats builtin by name).
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n002, n001 default)*

`internal/sched`: kinds mutex / semaphore / admission / allocator, scopes
host / worktree / run, `acquired_by: runner` planning; `flock(2)` slot files
(`<name>.<i>.lock`, `i < capacity`) taken in canonical name order; admission
execs the project's command and treats 75 as defer-and-retry with backoff
until the run deadline; allocator execs `acquire`, parses one JSON line as
the handle, injects it into the manifest, and releases in a deferred call
that also fires on `SIGINT`/`SIGTERM` via `signal.NotifyContext`;
invocations as goroutines under an `errgroup`; `broad_after_unit` waves;
`config.yaml: concurrency: serial|parallel` (default `serial` at bootstrap —
one invocation at a time while printing the schedule it would have used) with
`--serial`/`--parallel` overrides; `schedule` prints waves, holds, critical
path and estimated wall vs serial sum, and its check half flags
runner-default resources a unit does not declare.
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(merged from n001 and n002)*

`internal/cost`: Welford per (unit, host class) with M2 → sd, a P² estimate
for p95, and last (n002); `.aitask-testmap/ledger.jsonl` appended per result
line with `run_id, unit, status, duration_ms, head_sha` (n002 location, n001
fields); `costs --update` folds into `aitestmap/costs/<hostclass>.yaml` and
truncates the ledger; per-invocation overhead rows; `last_pass: {sha, at,
run_id}` per unit (n001) and a per-unit flake rate from per-run status, with
`flake_threshold` excluding a unit from anchoring; host class from
`config.yaml`, defaulting to the hostname; the estimate for a selection is
Σ unit means + Σ per-invocation overhead, reported per kind.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_freshness, component_staleness_tool, component_cost_ledger] -->
### Evidence join *(new: introduced to bridge n001 and n002)*

Lives in `internal/stale` with `internal/gitx` and reads `internal/cost`.
Input: the set of edges whose `stamped_blob ≠ current_blob`, and for each
test its `last_pass` shas from the local ledger and the committed costs (any
host class). Steps: drop candidates from invocations with a `cause` or from
units over the flake threshold; keep shas that are ancestors of HEAD
(`git merge-base --is-ancestor`, results memoised per sha); group the
mismatched edges by candidate sha; one `git ls-tree <sha> -- <paths…>` per
distinct sha under a pool of four; an edge whose source object id at that
sha equals `current_blob` is `EVIDENCED:<test>|<source>|…|<sha>|<run_id>`,
otherwise `STALE:`. It never rewrites anything; `stale --confirm-evidenced`
is the explicit, auditable re-stamp, and it is the only bulk confirmation an
autonomous profile may run. Tradeoffs: it needs reachable history to remove
nags (a shallow clone sees only `STALE`, which is the safe direction); it
inherits n001's assumption that a passing run is evidence for the edges it
exercised, narrowed to "against exactly this content"; and it makes
`last_pass` anchors in the committed costs load-bearing, so
`units_expected`/`units_reported` reconciliation and the `cause` rule are
what keep a batch misreport from manufacturing evidence.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(merged from n001 and n002)*

`internal/feedback`: `score --run <full-run> --prediction <run-id>` splitting
failures into caught / missed for unit and scoped rows; `attribute`
recording `missing-edge` / `test-wrong` / `source-wrong` for units and
`missing-trigger` / `area-too-narrow` for scoped rows (n001 vocabulary), each
with task and run id, written to `registry/observed.yaml` as observed edges,
observed triggers and observed area members that the loader merges (n002's
"evidence widens the scope", with provenance kept in one file);
`stale --confirm-evidenced` is the bridge to the staleness loop.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(merged from n001 and n002)*

`testmap_fresh` (procedure, no `unlocks`), `testmap_check` (`unlocks:
[testmap_run]`), `testmap_run` (`blocks_dependents`, `max_retries: 1`) in
`gates_reference.yaml`, synced down so the drift guard stays green; the two
bash verifiers following the `tests_pass` template (log to
`.aitask-gates/<task>/<gate>_<run-id>.log`, append via `aitask_gate.sh
append`, exit the appended status), registered in the helper-script
whitelist, with the exit mapping table above; engine absent → 3, never skip.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(merged from n001 and n002)*

`aitask-testmap`: annotate what a new test covers or which areas / scopes /
triggers a new high-level test binds to, and let the tool write the stamp;
give a new source an edge, rule, area or waiver; `attribute` before the gate
when a failing test is fixed by editing a source it had no edge to; run
`verify` after editing an annotation; use `classify --suggest` when unsure
which table a test belongs to. `aitask-gate-testmap-fresh`: the procedure
gate above (n002's per-row digest-diff review and autonomous rules, n001's
`STALE_PATH` handling and `UNSTAMPED` prompt), with the `pass`/`skip`/`fail`
contract. Claude Code first, then ported to `.agents/skills/` and
`.opencode/skills/` as separate tasks per the framework's porting rule; the
shim is allowlisted at the skill-permission touchpoints because the skill
calls it directly.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(inherited from n002, n001 additions)*

Built into the binary as `ait-testmap runner <name>`: `bash-file`, `pytest`
(honouring `testmap:batch no`, n001), `go-test`, `gradle-class`, `suite`,
`device`; `command:` and `cwd:` overrides from `runners.yaml`; a project
script of the same name shadows a builtin; `engine-test` — `go-test` over
`engine/` — lets the engine's own tests ride the map (n001).
<!-- /section: component_reference_runners -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness: stamps, anchors, `verify`, the procedure gate *(merged from n001 and n002)*

The per-edge `@<date>/<blob10>` stamp (n002) written only by `verify` /
`annotate` / `stale --confirm*`; `last_pass` anchors in the ledger and
committed costs (n001); the `verify` verb; `config.yaml: bootstrap_until,
require_stamp, flake_threshold`; the `testmap_fresh` gate entry; the
`aitask-gate-testmap-fresh` procedure skill; `verify --all-evidenced` for a
maintainer who wants file stamps to reflect run evidence repo-wide (n001's
`--all-fresh`, renamed).
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(inherited from n002, classes merged)*

`internal/stale`: `stale --task --changes - | --all` printing
`SURFACE/EDGES/STALE_PATH/STALE/EVIDENCED/UNSTAMPED/STALE_AREA/REVIEW_DUE/UNKNOWN/DISPLAY/DECISION`
with the `%25`/`%7C` encoding and content states exiting 0; digest-only
comparison of the working tree; the evidence join; rename hints and culprit
task ids via `git log --name-status -M` when history is reachable (n001);
`--strict` for CI; mutations `--confirm`, `--confirm-source`,
`--confirm-evidenced`, `--retarget` through the rewriter with a re-scan of
touched files.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(merged from n001 and n002)*

`registry/areas.yaml` and `areas:` blocks in hand files; `registry/_scoped.yaml`
(n002 location); the `area`/`scope`/`trigger`/`reviewed` annotations; scoped
rows in `internal/registry` with `owns:` by area name for hand-declared rows
(n001); the d1 join, kind ranking, suite budget with `DEFERRED:` and
budget-exempt triggers in `internal/selectr`; the check rules incl.
`DEAD_SCOPE:` and `KIND_MISMATCH:|CONVERT_TO_SUITE`; `ait testmap areas`
(`--import-codemap`, `--list`, `--check`) (n001); `classify --suggest`
(n001); `missing-trigger` / `area-too-narrow` in `attribute`.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n002)*

`broad_after_unit: true` waves; `device_policy: filter_by_resource` default;
scoped rows exempt from per-edit digest staleness, with `STALE_AREA` as their
evidence-based drift signal (n001) and `REVIEW_DUE` as an opt-in cadence
(`broad_review_days`, default 0); `attribute` widens areas by evidence rather
than per-edit review.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited unchanged (both parents):

- **Static file-level facts are enough for v1**; the edge schema keeps the
  optional `symbols` slot for a later hunk-level matcher.
- **Existing project locks and allocators can be wrapped as resources** —
  the Go admission and allocator kinds exec the project's commands and honour
  their exit codes; nothing in thinking_app changes.
- **Runners can report per-unit timing inside a batch** from JUnit XML,
  `go test -json` or pytest junitxml.
- **`testmap:` does not collide with prose** in any target repo; this repo's
  38 `# Covers:` headers are behavioural prose and are not matched.

Inherited and made precise (n002's wording, both agree):

- **The change-surface script is the intake**: its exit codes carry no
  meaning, so the engine parses only its `COMMITTED:`/`TASK:`/`OTHER:`/`UNKNOWN:`
  lines, delivered by the shim on stdin; an `UNKNOWN:` refuses selection and
  drives `stale`'s decision; selection never reads a raw `git diff`.
- **The gate exit contract is reused** as the framework's verifier contract
  `0 pass / 1 fail / 2 skip / 3 error` (there is no `75` in the framework),
  through two dedicated verifier shells; the runner contract keeps `75`
  internally, the engine defers on it until the run deadline, and the
  verifier maps a final `75` to `3`; only an empty selection maps to `2`.
- **Target repos accept an `aitestmap/` root** — weakened to YAML only:
  with builtin reference runners no scripts need committing unless a project
  writes a custom runner (n002).

From n001, kept:

- **A Go toolchain ≥ 1.26 is available in release CI via `actions/setup-go`
  (`go-version-file: engine/go.mod`)** — as a step this design *adds* to
  `release.yml`, which has no Go step today — and on framework developers'
  machines; target-project users never need Go.
- **Hosts running `ait setup` or `ait upgrade` can reach
  `github.com/beyondeye/aitasks/releases`** over HTTPS, as they already must
  for the tarball; air-gapped hosts use `AIT_TESTMAP_BIN`, `--local-engine`,
  `--engine-from-source` or a pre-seeded `~/.aitask/engine/`.
- **A passing run of a test is evidence that the edges it exercised held** —
  narrowed: evidence for an edge is a pass whose tree held the covered
  source at exactly its current content; a shallow clone whose anchors are
  outside fetched history reports `STALE`, never `EVIDENCED`.
- **The blast radius of a high-level test is expressible as areas plus scope
  and trigger globs**; what that misses surfaces through `score` on a full
  run as an observed trigger or area member.
- **The engine latency targets** in the table are achievable on the aitasks
  repo with a warm cache and are validated by committed benchmarks before
  the gates are enabled here.

From n001, revised:

- **Git history is the *evidence* clock, not the staleness key.** n001 made
  commit reachability the definition of staleness; here the definition is the
  blob digest (below) and history is consulted only to suppress nags via the
  evidence join. mtime is never compared. A repository with no reachable
  anchors is fully functional, just noisier.

From n002, kept:

- **The blob digest of the covered source's content is the staleness key.**
  Neither mtime (reset by checkout) nor the annotation date (day granularity,
  clock skew) is compared; the date is display only.
- **linux/darwin × amd64/arm64 covers every target host** (WSL reports
  Linux); anything else builds from source.
- **One engine build per framework version suffices**; a per-user versioned
  directory resolves per-project `VERSION` differences without a
  compatibility matrix.

From n002, revised:

- **Go is a build-time dependency only** — but it is *not* "already
  provisioned in release CI": the only `setup-go` in this repo is
  `hugo.yml`'s at Go 1.25.7 against `website/go.mod`. The `engine` job
  provisions its own toolchain from `engine/go.mod`.
- **Broad tests can be described by areas or globs whose membership changes
  rarely** — so their drift signal is evidence-based (`STALE_AREA`: files in
  scope changed since the last pass) plus `attribute` widening; the calendar
  cadence (`REVIEW_DUE`) is available but off by default, because a date is
  the key both parents rejected for unit edges.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Advantages:

- **Computed, explained, scored selection** (inherited) — blast radius is
  data; the `stale` mark, the `EVIDENCED` class and the digest-anchored diff
  add "how trustworthy is this edge, and why" to "why was it selected".
- **Speed makes the machinery usable per task** (n002) — sub-second
  `select`/`check`/`stale` on a 720-test repo, so selection overhead is
  negligible against the shortest test and `check` can run on every commit
  step; no venv, no interpreter start.
- **A real scheduler** (n002) — goroutines plus `flock(2)` give correct
  cross-worktree contention and a critical-path report; the shell suite
  (owning the real index) and the pytest lane get the enforced
  do-not-overlap that is a comment today. Serial-by-default at bootstrap
  (n001) means the declarations are reviewed before they are trusted.
- **Architecture-independent packages stay that way** (n002) — Homebrew,
  AUR, `.deb`, `.rpm` and the tarball ship nothing compiled; the per-arch
  concern is one release job and one setup function.
- **Freshness heals itself where it can and fails safe where it cannot**
  (bridge) — most staleness on hot sources is cleared by run evidence with
  no file rewrite; a shallow clone or a never-run test simply gets the
  precise digest verdict.

Disadvantages:

- **Registry directory complexity** (inherited) — five tables and two
  generated files, in one directory with one merge rule in one Go package
  with golden tests; n001's second directory was avoided.
- **Fail-closed bootstrap cost** (inherited) — an explicit waiver pass before
  `testmap_check` can be enabled; a first green full run before
  `require_stamp` and `--strict` are turned on (`stale --all
  --confirm-evidenced` stamps the bulk of `UNSTAMPED` rows from it).
- **Static scanners overselect on hot files** (inherited) — kind ranking,
  the suite budget and `--budget-s` trim broad rows first; a project scanner
  plugin can narrow a hot resource file.
- **Two toolchains in one framework** (n001) — mitigated by the boundary
  rule (parse/walk/match/digest/schedule in Go; ledger, task file and shell
  environment in bash), `engine-check.yml`, and Go source confined to
  `engine/` and excluded from the tarball.
- **The framework gains a compiled component** (n002) — contributors
  touching the engine need Go; a release fails if `go test` fails; install
  grows a fetch and a checksum step. Mitigated by one `build.sh`, `ait engine
  build`, and the engine being optional until a testmap gate is enabled.
- **`ait setup` gains a self-downloaded release asset** (n001) — the CDN URL
  family `install.sh` already uses, `SHA256SUMS` verification, the `.sha256`
  sidecar, `--no-testmap` / `AIT_TESTMAP_FETCH=0`, and setup never depending
  on the binary for anything else.
- **Engine version skew on multi-project hosts** (n002) — several ~10 MB
  binaries under `~/.aitask/engine/`; exact-version resolution in the shim
  (never newest-wins) and `ait engine prune` against the project registry.
- **Stamp churn on hot sources** (n002) — confirmation rewrites test files;
  a source named by 72 tests could yield a 72-file diff. Mitigated more than
  in either parent: `EVIDENCED` rows need no rewrite at all until someone
  chooses `--confirm-evidenced`; `--confirm-source` makes a deliberate
  re-stamp one commit; only confirmation rewrites; `KIND_MISMATCH` nudges
  such fan-out toward a scope.
- **Area globs and scopes are coarser than edges** (n001, n002) — a broad
  area over-selects on every edit inside it and a scoped test depending on a
  file outside its scope is under-selected until a full run scores it.
  Mitigated by the budget with explicit `DEFERRED:` lines, budget-exempt
  triggers for known sharp edges, `broad_after_unit`, cost visible in
  `schedule`, and the `missing-trigger` / `area-too-narrow` attribution path.

Risks:

- **Unattributed source edits** (inherited) — narrowed, not removed: a source
  edited without review of its annotations shows as `STALE:` in the next task
  touching it and as a `stale` mark on every selection; a new coupling with
  no edge at all is still only caught by `score` on a full run.
- **Batch misreport and wrongly scoped resources** (inherited) — now also
  corrupts anchors: a false `pass` line could manufacture evidence.
  `units_expected`/`units_reported` is enforced per invocation, a mismatch is
  a mechanism failure, and no line from an invocation with a `cause` anchors.
- **Resource declarations are only as complete as declared** (inherited) —
  `schedule`'s check half and the heuristic for shell tests running git in
  the repo root remain the only detection short of a probe.
- **A flaky pass anchors as surely as a real one** (n001) — the ledger keeps
  per-run status, `costs` exposes a flake rate, and a unit above
  `flake_threshold` is excluded from evidence.
- **Autonomous confirmation is weaker than review** (n002) — narrowed: the
  only autonomous confirmation is `--confirm-evidenced`, which requires that a
  pass's tree held the current bytes of the specific source, records
  `confirmed_by: <run_id>`, and is re-opened by a later `score` miss; a
  `STALE:` row is never confirmed without a human.
- **The version handshake is strict by design** (n001) — an `ait upgrade` on
  a host that cannot fetch leaves `ait testmap` refusing to run until a
  matching binary is supplied; the error names the fix (`ait setup`,
  `AIT_TESTMAP_BIN`, `ait engine build`).
- **An unsigned macOS binary or a blocked download leaves a host without an
  engine** (n002) — `ENGINE_MISSING` names the path and the repair verb;
  `--engine-from-source` and `--local-engine` are documented fallbacks; the
  testmap gates exit 3 (error), never skip, when the engine is absent.
- **The evidence join needs reachable history to remove nags** (new) — a
  depth-1 CI clone or a fresh shallow worktree sees only `STALE`, so a CI
  `stale --all --strict` job should run on a full clone or accept `STALE`
  noise; `STALE_PATH` is the only class `--strict` fails on for this reason.
<!-- /section: tradeoffs -->

<!-- section: conflict_resolutions [dimensions: component_*, assumption_*, tradeoff_*] -->
## Conflict Resolutions

Each entry names the conflict, the strategy applied in the mandated priority
order (Adapter/Bridge > Assumption update > Component replacement), the
resolution, and the dimensions it changed.

### 1. Staleness model: history anchor (n001) vs content digest (n002)

- **Conflict.** n001's `component_freshness` depends on git history
  (`git log <anchor>..HEAD`) and on `last_pass` anchors in `component_cost_ledger`;
  n002's `component_staleness_tool` depends on per-edge digests in
  `component_annotation_scanner` and explicitly on *not* needing history.
  Taking either whole drops the other's real advantage (low churn vs
  precision and shallow-clone safety).
- **Strategy.** Adapter/Bridge.
- **Resolution.** New `component_evidence_join`: the digest is the key
  (n002), `last_pass` shas are candidates (n001), and `git ls-tree <sha> --
  <paths>` joins them — an edge whose current blob appears in a reachable
  passing run's tree is `EVIDENCED`, otherwise `STALE`. The per-block
  `testmap:verified` stamp is dropped (component replacement inside
  `component_freshness`, since the per-edge stamp subsumes it). n002's
  `--confirm-run` is replaced by the computed `--confirm-evidenced`.
- **Dimensions changed.** `component_freshness`, `component_staleness_tool`,
  `component_annotation_scanner`, `component_cost_ledger` (anchors are now
  load-bearing), `assumption_git_history_is_freshness_clock` (revised: evidence
  clock, not key), `assumption_passing_run_anchors_edges` (narrowed),
  `assumption_blob_digest_is_staleness_key` (kept), `tradeoff_stamp_churn`,
  `tradeoff_autonomous_confirmation_weak`, `tradeoff_batch_misreport_risk`,
  new `tradeoff_evidence_requires_reachable_history`.

### 2. Stale report vocabulary

- **Conflict.** `STALE_PATH/STALE_RUN/STALE_AREA/UNVERIFIED` vs
  `STALE/DELETED/UNSTAMPED/REVIEW_DUE`, and `ANCHOR:` lines vs
  `SURFACE:/EDGES:/DISPLAY:` with the manual-verification encoding.
- **Strategy.** Assumption update (one report shape) plus union.
- **Resolution.** n002's shape and encoding (it matches
  `aitask_verification_stale.sh` exactly); classes `STALE_PATH` (n001's name
  for n002's `DELETED`, extended with `renamed` hints), `STALE` (n002; equals
  n001's `STALE_RUN` when no evidence exists), `EVIDENCED` (new), `UNSTAMPED`
  (n002's name for n001's `UNVERIFIED`), `STALE_AREA` (n001), `REVIEW_DUE`
  (n002, opt-in), `UNKNOWN`, `DISPLAY`, `DECISION`. `--include-stale`
  consumes `STALE` and `STALE_AREA`.
- **Dimensions changed.** `component_staleness_tool`, `component_freshness`,
  `component_selector`.

### 3. Broad-test staleness: evidence (n001) vs calendar (n002)

- **Conflict.** `STALE_AREA` needs anchors; `REVIEW_DUE` needs a cadence
  that contradicts `assumption_blob_digest_is_staleness_key`'s reasoning.
- **Strategy.** Assumption update.
- **Resolution.** `assumption_broad_tests_area_scoped` revised: drift is
  evidence-based by default; `broad_review_days` defaults to 0 and
  `REVIEW_DUE` appears only when a project sets it. `testmap:reviewed` stays
  as display metadata.
- **Dimensions changed.** `assumption_broad_tests_area_scoped`,
  `component_broad_test_scopes`, `component_staleness_tool`.

### 4. Broad-test storage and selection

- **Conflict.** Second merged directory `suites/` with lane 2 (n001) vs
  `_scoped.yaml` in `registry/` joining the one list at d1 (n002).
- **Strategy.** Component replacement of n001's directory by n002's table;
  bridge of the selection policies.
- **Resolution.** One directory, five tables (n002); n001's `trigger`
  keyword, suite budget, `DEFERRED:` lines, `areas --import-codemap`,
  `classify --suggest` and `owns:` by area name are layered on n002's d1 join,
  kind ranking and `broad_after_unit`. n001's "never contribute distance,
  sinks in the walk" holds in n002's structure. `covers` on scoped rows is
  allowed (n002) for digest-stamped fixture pins.
- **Dimensions changed.** `component_suite_registry`,
  `component_broad_test_scopes`, `component_registry_loader`,
  `component_selector`, `component_scheduler_resources`,
  `tradeoff_registry_directory_complexity`, `tradeoff_area_glob_coarseness`,
  `tradeoff_broad_scope_coarseness`.

### 5. Covers-fan-out guard

- **Conflict.** 8/fail/`CONVERT_TO_SUITE` vs 6/warn/`KIND_MISMATCH`.
- **Strategy.** Assumption update.
- **Resolution.** `unit_covers_max: 8`, `KIND_MISMATCH:<test>|<n>|CONVERT_TO_SUITE`
  as a warning, a failure under `check --strict`. Neither parent measured
  the distribution; the guard is a nudge and must not fail a bootstrap.
- **Dimensions changed.** `component_registry_loader`,
  `component_suite_registry`.

### 6. Reference runners: project bash (n001) vs builtins (n002), and the boundary rule

- **Conflict.** n001's boundary rule keeps shell state out of the binary;
  n002's builtin `pytest` must run under this repo's framework venv, which
  `python_resolve.sh` resolves in bash.
- **Strategy.** Adapter (a `command:` override) rather than picking.
- **Resolution.** Builtins with `command:`/`cwd:` overrides in `runners.yaml`
  and n002's shadow-by-name rule. The binary execs what it is told and never
  sources shell state; a project needing more commits a script. n001's
  `testmap:batch no` for the serial carve-out replaces n002's `serial` list
  in `config.yaml` (which would be a third copy of a list already
  drift-guarded in two places); `tests/test_serial_carveout_doc_drift.sh` is
  extended to pin the annotations. n001's `go-test` over the engine is kept.
- **Dimensions changed.** `component_reference_runners`,
  `component_runner_contract`, `assumption_target_repos_accept_aitestmap_root`
  (n002's weakening stands).

### 7. Change-set intake

- **Conflict.** n001's data flow has the binary exec `aitask_change_surface.sh`,
  which n001's own boundary rule forbids; n002 pipes via the shim.
- **Strategy.** Component replacement (n001's intake by n002's).
- **Resolution.** The shim runs the script for every `--task` verb and pipes
  into `--changes -`; `--changes <file>` makes the engine testable outside
  the framework. `assumption_change_surface_is_intake` takes n002's precise
  wording.
- **Dimensions changed.** `component_selector`, `component_staleness_tool`,
  `assumption_change_surface_is_intake`.

### 8. Binary identity, layout and developer surface

- **Conflict.** `ait-testmap` in `go/` installed to `~/.aitask/bin` with a
  symlink, `make install-dev`, `AIT_TESTMAP_DEV` (n001) vs `aitestmap` in
  `engine/` installed to `~/.aitask/engine/v<V>/` off PATH, `ait engine`,
  `AIT_ENGINE=dev` (n002).
- **Strategy.** Per-aspect selection with motivation (decision matrix).
- **Resolution.** Name from n001; directory, slot, verbs and env from n002;
  n001's `.sha256` sidecar, strict handshake, `AIT_TESTMAP_BIN` and
  `--no-testmap` / `AIT_TESTMAP_FETCH=0` retained; n001's lazy fetch in the
  shim dropped in favour of install at `ait setup` / `ait upgrade` (verified
  to share `install.sh`'s `--source-only` path); n001's two-version prune
  replaced by n002's registry-aware `ait engine prune`.
- **Dimensions changed.** `component_go_engine`, `component_engine_binary`,
  `component_binary_distribution`, `component_engine_packaging`,
  `requirements_go_engine_and_cli`, `requirements_platform_binaries_in_release`,
  `requirements_dev_rebuild_from_source`, `requirements_engine_dev_regeneration`,
  `tradeoff_strict_version_handshake`, `tradeoff_engine_version_skew`.

### 9. Dependencies and CLI framework

- **Conflict.** yaml.v3 + doublestar + stdlib (n001) vs + cobra + gofrs/flock
  + x/sync (n002).
- **Strategy.** Per-dependency selection.
- **Resolution.** yaml.v3, doublestar/v4, x/sync; no cobra (scripts are the
  primary consumer; exit-code discipline is custom either way), no
  gofrs/flock (Unix-only targets), no go-git (both agree). References to
  cobra and gofrs/flock are removed from `reference_files`.
- **Dimensions changed.** `component_go_engine`, `component_engine_binary`.

### 10. Release CI and PR-time checks

- **Conflict.** Four-job matrix without tests + `go-check` in
  `contribution-check.yml` (n001) vs one `engine` job with `go test`, no PR
  check (n002). Factual: `contribution-check.yml` is issue-triggered;
  `release.yml` has no Go step, `hugo.yml` has one at 1.25.7.
- **Strategy.** Assumption update with correction.
- **Resolution.** One `engine` job (n002) with `setup-go` from
  `engine/go.mod`, `go vet`, `go test`, `build.sh all`; `release` gains
  `needs: [plan, engine]`; a new `engine-check.yml` on `push`/`pull_request`
  with `paths: [engine/**]` carries n001's PR-time intent and the 2× bench
  regression rule. Asset names `ait-testmap_<V>_<os>_<arch>` and
  `ait-testmap_<V>_SHA256SUMS.txt`.
- **Dimensions changed.** `component_binary_distribution`,
  `assumption_go_toolchain_available`, `assumption_go_toolchain_ci_and_dev_only`
  (premise corrected), `requirements_platform_binaries_in_release`,
  `requirements_engine_packaging`.

### 11. Gates: names, chaining, retries

- **Conflict.** `testmap_fresh → testmap_check → testmap_run` via `unlocks:`,
  `max_retries: 3` (n001) vs `testmap_current`, `testmap_check`,
  `testmap_select`, unchained, `max_retries: 1` (n002). A procedure gate that
  `unlocks` a machine gate would block that gate in every headless run, where
  procedure gates are deferred.
- **Strategy.** Assumption update.
- **Resolution.** n001's names; `unlocks:` only on `testmap_check →
  testmap_run`; `testmap_fresh` linear-default like `docs_updated`; `check`
  fails `STALE_PATH` on its own so it needs no procedure to precede it;
  `max_retries: 1` because admission `75` is deferred inside the engine.
- **Dimensions changed.** `component_gates`, `requirements_gate_enforcement`,
  `assumption_gate_exit_contract_reused`.

### 12. Scheduler default

- **Conflict.** `concurrency: report` default (n001) vs concurrent with
  `--serial` (n002).
- **Strategy.** Assumption update.
- **Resolution.** n002's real scheduler and `broad_after_unit`;
  `config.yaml: concurrency: serial|parallel` defaults to `serial`
  (one invocation at a time, schedule printed) until the project's bootstrap
  flips it after reviewing the schedule report; `--serial`/`--parallel`
  override per run. `report` as a mode that runs nothing is dropped.
- **Dimensions changed.** `component_scheduler_resources`,
  `tradeoff_real_scheduler`, `tradeoff_resource_declaration_completeness`.

### 13. State locations

- **Conflict.** `.aitask-gates/<task>/testmap/` evidence, XDG ledger per
  host class, XDG-cache lock fallback (n001) vs `.aitask-testmap/runs/<run-id>/`,
  per-repo ledger, `${TMPDIR:-/tmp}` lock fallback (n002).
- **Strategy.** Per-item selection.
- **Resolution.** n002 for all three (run-id keyed outputs work without a
  task; a ledger is per repository; a lock fallback must not survive
  reboot); verifier logs stay under `.aitask-gates/<task>/` per the template;
  the deps cache keeps n001's `aitasks/` namespace under XDG.
- **Dimensions changed.** `component_cost_ledger`, `component_scheduler_resources`,
  `component_gates`.

### 14. Near-duplicate dimensions across parents

- **Conflict.** Rule 1 forbids dropping any parent dimension, yet the parents
  named the same concern twice (`requirements_go_engine_and_cli` /
  `requirements_go_engine`, `component_freshness` / `component_staleness_tool`,
  `assumption_release_asset_reachable` / `assumption_release_assets_reachable`,
  `tradeoff_two_toolchains` / `tradeoff_compiled_component_cost`, and so on).
- **Strategy.** Keep every key; make each pair complementary rather than
  redundant.
- **Resolution.** Each paired key in the metadata carries the facet its
  parent emphasised (mechanism vs packaging, release side vs host side,
  boundary cost vs release/install cost), stated against the merged design,
  so no key is a copy of another and none is dropped.
- **Dimensions changed.** All paired keys listed in the metadata.
<!-- /section: conflict_resolutions -->

<!-- section: open_questions -->
## Open Questions

1. Should `--confirm-evidenced` be allowed under autonomous profiles at all
   (as proposed), or should autonomous runs only report and leave every
   re-stamp to an attended session? The evidence is computed, but it is
   still "the test passed", not "the test exercised this source".
2. Should the evidence join also accept a `last_pass` from another host class
   when its tree holds the current blob (proposed: yes, any host class), or
   only from the class that will run the gate?
3. Is `unit_covers_max: 8` right, and should `check --strict` refuse rather
   than warn once a repo has finished bootstrapping (proposed: yes)?
4. Should `ait upgrade` prune `~/.aitask/engine/` automatically when the old
   version is on no registered project, or only `ait engine prune`
   (proposed: only explicit)?
5. Should `broad_review_days` stay off by default, or is a long cadence
   (180 days) worth the noise for e2e tests that never fail?
6. Does a scoped row need a distance-like grade — an area hit through a
   scanned dependency counting weaker than a direct file — or are
   trigger/area/scope plus the budget enough?
7. Should the Go module later absorb `aitask_change_surface.sh` in a new
   contract, or does keeping the intake in bash preserve a useful seam?
8. Should the deb/rpm postinstall message mention the binary fetch that
   `ait setup` performs, given the packages themselves stay `noarch`?
9. Baseline questions still open: routing of a new declared edge when no
   `owns:` matches (proposed: refuse); CI evidence export format (JUnit
   alongside the results directory); how the thinking_app screenshot gate is
   wrapped (`verify-active` as a suite runner plus `gradle-class` over
   `unit-tests --tests`); the per-repo bootstrap order (proposed: `scan` →
   `classify --suggest` → `areas --import-codemap` → waivers → `testmap_check`
   → first full run → `stale --all --confirm-evidenced` → `require_stamp` →
   review `schedule` → `concurrency: parallel` → `testmap_run`). Baseline
   question 3 becomes the `concurrency` knob and 5 becomes `device_policy`.
<!-- /section: open_questions -->
--- PROPOSAL_END ---
--- NEW_DIMENSIONS ---
component_evidence_join, tradeoff_evidence_requires_reachable_history
