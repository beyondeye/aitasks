# Changelog

## v0.26.0

### Features

- **Gate orchestrator engine** (t635_11): Added a gate orchestrator that runs a task's declared verification gates — handling retries, parallelism, and stuck-detection — plus `ait gates run` and gate-authoring scaffolding.
- **Resume in-flight tasks** (t635_6): Added an `aitask-resume` command that re-enters an interrupted task at its last checkpoint, driven by the recorded gate ledger.
- **Gate-aware task picking** (t635_7): `aitask-pick` now surfaces in-flight tasks as resume candidates and routes a picked task straight back to where it left off.
- **Shared gate-ledger parser** (t635_8): Added a shared parser for gate-run state so TUIs and tools read task progress from one consistent source.
- **Board In-Flight view** (t635_9): The board gained an In-Flight view listing actively implementing tasks with their gate state and a one-key resume launch.
- **Monitor gate status** (t635_10): The monitor now shows a compact gate summary (passed/pending/failed) for each running agent.
- **Mobile live terminal streaming** (t822_8): Applink can stream live terminal snapshots to the mobile companion as compact binary keyframes.
- **Mobile delta streaming** (t822_9): Terminal updates stream as row-level deltas, sending only changed lines to the mobile app.
- **Mobile append fast path** (t822_10): Scrolling output uses an append fast path that sends just the new bottom rows, cutting bandwidth for log-like panes.
- **Mobile task-action handshakes** (t822_11): Added confirm/suggest handshakes for restarting a task or picking the next sibling from the mobile app.
- **Headless applink bridge** (t822_13): `ait monitor --headless-for-applink` runs the mobile bridge without the terminal UI, printing an ASCII-QR pairing block — ideal for servers.
- **Device name in pairing QR** (t822_5): The mobile pairing QR now carries the host's name so the companion app can label the connection.
- **Applink firewall doctor** (t1043): Applink diagnoses LAN firewall issues at launch and offers a guided, consent-based fix so pairing isn't silently blocked.
- **Project groups** (t1025_1): Projects can be organized into named groups via `ait projects group`, with an explicit ungrouped bucket and slug validation.
- **Two-axis project navigation** (t1025_2): The TUI switcher and stats view added group-aware navigation, letting you cycle by project group as well as by session.
- **Project Groups settings tab** (t1025_3): The settings TUI gained a Project Groups tab to assign, clear, rename, and sync groups, with create-on-type support.
- **Topic anchor field** (t1016_1): Tasks can carry an `anchor` field grouping them under a root topic, with `--anchor`/`--followup-of` flags on create and update.
- **Board By-Topic view** (t1016_4): The board gained a By-Topic view (`y`) that groups tasks into topic lanes by their anchor, with an editable anchor field in task detail.
- **Shadow concern format** (t1037_1): Defined a structured concern-block format and parser so a shadow agent's plan critiques can be machine-read.
- **Shadow emits concerns** (t1037_2): The shadow agent now emits its plan challenges and assumption checks as a structured, prioritized concern block.
- **Concern picker** (t1037_3): Added a picker modal to select among a shadow agent's surfaced concerns and copy them for the followed agent.
- **Forward shadow concerns** (t1037_4): minimonitor can capture a shadow agent's concerns (`c`), offer them automatically, and copy the selected ones to the clipboard.

### Enhancements

- **Restart operations from Running tab** (t1018_2): The brainstorm Running tab can re-run a whole operation group fresh (`n`) or retry-apply it (`i`), with one-call group cleanup.
- **Double-click to open group detail** (t1018_3): Double-clicking a group row in the brainstorm Running tab opens its detail, and a focused+hovered row keeps the accent color.
- **Cross-group project browsing** (t1036): Session cycling in the switcher and stats walks a cross-group ring, re-pointing the group axis as you move.
- **Auto-refresh In-Flight board** (t1024): Switching to the board's In-Flight view reloads task and gate state automatically.
- **DAG node marks** (t1004): Marked nodes in the brainstorm graph show a ☑/☐ checkbox glyph, matching the list view.
- **Follow-up anchor provenance** (t1016_3): Auto-created follow-up tasks inherit their origin via `--followup-of`, keeping them grouped with the originating topic.
- **Richer concern framing** (t1037_6): Shadow concern bodies carry full framing (problem, why it bites, how to confirm) rather than a bare one-liner.

### Improvements

- **Unified Browse tab** (t983_3): Merged the brainstorm list and graph tabs into a single Browse tab with a toggle and one shared node-detail panel.
- **Operations dialog** (t983_4): The node-action dialog became a unified Operations dialog with selection-aware ops, a target summary, and in-modal help.
- **Node Hub overlay** (t983_5): Pressing Enter on a node opens a Node Hub overlay combining detail view with an Operations entry point.
- **Pre-seeded operation wizard** (t983_6): Launching an operation from a node or marked set pre-seeds the wizard, skipping the redundant node-selection step.
- **Compare overlay** (t983_7): The brainstorm Compare tab became an on-demand overlay reachable from the Node Hub and Browse.
- **Session tab** (t983_8): Split session-lifecycle actions into their own Session tab, keeping the operations picker focused on design ops.
- **Running tab + status strip** (t983_9): Renamed the Status tab to Running, added an always-on runtime strip, and added agent cleanup/retry actions.
- **Operation wizard as overlay** (t983_11): Moved the multi-step operation wizard out of a tab into a dedicated modal screen.
- **Footer keybinding hygiene** (t1018_1): Scoped brainstorm retry actions to their owning tab and replaced undeliverable chord shortcuts with working ones.
- **Single Browse cursor state** (t1003): Consolidated the brainstorm Browse cursor onto a single selection model.
- **Modularized brainstorm code** (t1048): Split the large brainstorm TUI module into focused submodules, shrinking the main file by ~39% with no behavior change.
- **Named project registry records** (t1029): Project registry rows are parsed into named records for clearer, safer field access.
- **Shared group-cycle logic** (t1033): Centralized the project-group cycling logic shared by the switcher and stats views.

### Bug Fixes

- **Cross-repo & archived board relations** (t1021): The board resolves archived tasks in cross-repo, child, and folded relations.
- **Board detail actions from dependencies** (t1062): Fixed board detail actions being dropped when a task was opened from a dependency.
- **Parent/child task resolution** (t1026): A parent id no longer wrongly matches an active child.
- **Primary-branch detection in sync** (t1027): Sync/desync detects the repo's primary branch instead of assuming `main`.
- **Primary-branch in contribute/externalize** (t1031): Fixed hardcoded `main` assumptions in the contribute and plan-externalize flows.
- **Brainstorm comparator lifecycle** (t1020): Gave the comparator a proper completion lifecycle so results apply reliably.
- **Brainstorm crew status** (t1041): Fixed stale crew status by deriving the rollup on read.
- **Brainstorm tab-switch keys** (t1060): Tab-switch keys fire from any tab, not just Browse.
- **Brainstorm wizard/preview UX** (t1047): Fixed several node-operation wizard and preview-checkbox UX bugs.
- **Brainstorm config mount timing** (t1050): Hardened config mounting so the proposal preview populates reliably.
- **Root node delete guard** (t1010): Guarded against deleting the root node in a brainstorm graph.
- **Brainstorm footer scoping** (t1039): The footer no longer shows actions that don't apply to the current tab.
- **Brainstorm cycle-field contrast** (t1019): Fixed low-contrast text on a focused cycle field.
- **Focused-row hover color** (t1038): Fixed focused brainstorm rows losing their accent color on hover.
- **Applink empty subscribe** (t1044): An empty applink subscribe expands to all panes instead of subscribing to none.
- **Monitor pane resize** (t981): Fixed monitor pane resize to use the subprocess path, restoring correct geometry.
- **Narrow agent-command dialog** (t1012): Fixed the minimonitor agent-command dialog to render correctly in narrow panes.
- **Codex plan helper readiness** (t1006): The Codex plan helper waits for the composer to be ready before sending the prompt.
- **Codex/OpenCode mirror markers** (t1028): Fixed duplicated instruction markers in the Codex and OpenCode mirrors.
- **Helper-script permission drift** (t1001): Restored a missing helper-script permission entry that caused approval drift.
- **Pre-existing test failures** (t1014): Fixed pre-existing board and workflow test failures.
- **Multi-session monitor test** (t987): Fixed a multi-session monitor test by isolating its tmux environment.

### Documentation

- **Brainstorm TUI docs** (t929_3): Added a code-verified brainstorm TUI documentation set (overview, how-to, reference).
- **Brainstorm agent defaults** (t968): Documented brainstorm per-agent model defaults and stopped the settings UI from rendering orphaned agent rows.
- **Project group docs** (t1025_4): Added code-verified documentation for project groups and the new navigation behaviors.
- **Anchor docs** (t1016_2): Documented the new task `anchor` field across all schema, skill, and website surfaces.
- **Shadow agent docs** (t986_6): Documented the shadow companion agent across the framework docs and website.
- **Shadow concern picker docs** (t1049): Documented the shadow concern-forwarding flow and the minimonitor `c` picker.
- **Applink permissions docs** (t822_12): Synced the applink permission/verb gating table with the canonical command inventory.
- **Monitor design doc refresh** (t1013): Refreshed the applink monitor-port design doc to drift-proof symbol references.

### Maintenance

- **Applink security hardening** (t985): Hardened applink security — TLS 1.2+ floor, connection/rate caps, input validation on all verbs, secure file permissions, and audit logging.
- **Applink push scheduler resilience** (t822_14): Hardened the push scheduler against send failures and added resilience tests.
- **Brainstorm stale-ref cleanup** (t1008): Removed stale references to retired brainstorm detail/patch operations.

## v0.25.0

### Features

- **Gate ledger substrate** (t635_1): Tasks can now carry named approval checkpoints ("gates") recorded in a durable ledger — the foundation for gate-aware dependency, archival, and resume behavior.
- **Task-workflow checkpoint recording** (t635_2): With the new `record_gates` profile option, the task workflow records its approval checkpoints (plan approved, risk evaluated, build verified, review approved, merge approved) as gate runs. Enabled by default on the `fast` profile.
- **Dependency-unblock semantics** (t635_3): A task's dependents are now released as soon as its integration gates pass, rather than waiting for the task to fully complete.
- **Gate-guarded archival** (t635_4): A task that declares gates won't archive until all of them pass, with an in-session "resolve now & archive" offer and an `--ignore-gates` escape hatch.
- **Ledger-driven re-entry** (t635_5): The task workflow is now re-entrant — picking up an in-flight task resumes it at the right point (planning, implementation, or post-implementation) based on its recorded checkpoints.
- **Applink WebSocket listener** (t822_7): Added the applink control plane — a paired, TLS-secured `wss://` listener that lets the mobile companion app connect, plus a Devices screen for viewing and revoking paired devices.
- **Shadow context fetch** (t986_3): Added a helper that resolves a task's file and most-recent plan (and optionally sibling context) to feed the shadow companion.
- **Shadow companion command** (t986_4): Added `/aitask-shadow`, an advisory companion that reads a followed agent's terminal output to explain it, help answer a prompt, or critically challenge its plan.
- **Minimonitor shadow trigger** (t986_5): The minimonitor can now launch a shadow companion for the followed agent (the `e` key), with a configurable agent/model and same-window-vs-separate-window placement.

### Bug Fixes

- **Preserve local models on upgrade** (t982): Upgrading now merges new seed models into your model configuration instead of overwriting it — local entries are kept and new ones appended.
- **Monitor refresh benchmark** (t984): Fixed the monitor-refresh benchmark to patch the current monitor internals instead of a removed symbol.
- **Cross-repo deps in board detail** (t990): The board detail view now shows cross-repo dependencies, and opening a linked cross-repo task renders its metadata and body correctly instead of raw YAML.
- **Project resolver whitelist** (t991): Whitelisted the project-resolver helper so code agents can resolve cross-repo project names without a permission prompt.
- **Archived tasks in board dialogs** (t992): Board relation dialogs (Depends / Verifies) now resolve and open archived tasks read-only instead of failing to find them.
- **Narrow-pane sibling dialogs** (t998): Fixed cramped rendering of the minimonitor's next-sibling dialogs in narrow panes — they now widen and stack their buttons vertically.

### Enhancements

- **Minimonitor shadow layout** (t994): Improved the minimonitor shadow pane (placement and configurable width), reorganized the footer, added an `r` refresh binding, and wrapped the task description onto two lines.
- **Trim kill-confirm dialog** (t995): Trimmed the minimonitor's kill-confirmation dialog so it fits in narrow panes.
- **Shadow startup greeting** (t997): The shadow companion now greets you with its capabilities at startup and proactively surfaces relevant observations after each capture.

### Improvements

- **Extract monitor core** (t822_6): Extracted a Textual-free headless monitor core module — the shared substrate for the monitor TUIs and the new applink listener (no user-visible behavior change).
- **Brainstorm node detail panel** (t983_1): Refactored the brainstorm node-detail view into a reusable panel widget.
- **Brainstorm node-selection model** (t983_2): Added a headless node-selection model (primary cursor + marked set) for the brainstorm TUI.
- **Pane-keyed monitor state** (t986_1): Re-keyed monitor state by pane so multiple agents per window — and shadow panes — are tracked and excluded correctly.

### Tests

- **Multi-session monitor test update** (t999): Aligned the multi-session monitor test suite with the monitor_core package and the new shadow-target pane field.

### Maintenance

- **Stale test comment fix** (t915): Fixed a stale comment in the skill-render test suite.
- **Port shadow to Codex** (t988): Ported the `/aitask-shadow` command to Codex CLI.
- **Port shadow to OpenCode** (t989): Ported the `/aitask-shadow` command to OpenCode.

## v0.24.0

### Features

- **Gates framework roadmap** (t635): Locked the design decisions and roadmap for an upcoming task-gates framework, including a documentation track and a `docs_updated` gate.
- **Kill & next commands in minimonitor** (t944): The minimonitor can now kill the followed agent (`k`) or launch its next sibling task (`n`) directly, and shows the followed agent in its own dedicated panel separate from the general list.
- **Reusable proposal preview pane** (t945_1): Added a side-by-side proposal preview to the brainstorm TUI, with a section minimap and adjustable split ratios.
- **Proposal preview in the explore wizard** (t945_2): The brainstorm explore wizard now shows the source node's proposal side-by-side as you configure the next step.
- **Source-node choice & preview in decompose** (t945_3): The module-decompose wizard now lets you pick the source node and previews its proposal side-by-side, with full Tab navigation across inputs, minimap, and proposal.
- **Fable 5 model for Claude Code** (t966): Registered the Fable 5 (`claude-fable-5`) model so it can be selected for Claude Code agents.

### Enhancements

- **Review module decomposition before applying** (t929_1): module_decompose now offers a "Review before apply" gate where you can preview the proposed breakdown and re-run it with steering notes before it lands.
- **Agent-proposed module sets** (t929_2): module_decompose gained an "Agent-proposed" mode that infers the module breakdown from the plan instead of requiring you to name modules up front.
- **Tmux sessions survive compositor restarts** (t943): Agent tmux sessions now launch in a persistent systemd user slice, so they survive a session/compositor teardown (e.g., a Wayland compositor restart).
- **Dedicated tmux server** (t953): `ait` now runs its tmux sessions on a dedicated, persistent socket isolated from your default tmux server, with a configurable opt-out and a legacy-attach offer.
- **Line-numbered proposal view** (t954): Added a `Ctrl+Shift+L` toggle that switches the brainstorm proposal preview to a syntax-highlighted, line-numbered source view.
- **Hardened tmux server creation** (t956): New tmux servers spawned by agent launches now land in a persistent slice (with setsid/plain fallbacks), making detached agent sessions more robust.
- **Fuzzy search for shortcuts** (t958): The shortcut editor and the Settings Shortcuts tab now have a fuzzy filter box for quickly finding keybindings.

### Bug Fixes

- **Codebrowser ANSI-file hang** (t940): Fixed the codebrowser hanging on files containing raw ANSI/control characters; those bytes now render as visible control-picture glyphs.
- **Monitor window rename** (t941): The monitor now renames only its own tmux window on startup instead of an untargeted rename that could hit the wrong window.
- **TUI switcher default project from minimonitor** (t947): Opening the TUI switcher from the minimonitor now defaults to the followed agent's project, regardless of list focus.
- **Dead minimap Tab binding** (t949): Removed a dead minimap class carrying a misleading, latent Tab binding.
- **tmux test bitrot** (t951): Fixed two broken tmux tests (a relative-import failure and a stale field assertion).
- **stats-tui missing from help** (t963): `ait help` now lists the `stats-tui` command.
- **App-scope shortcut remapping** (t964): Custom App- and modal-scope keybinding overrides now take effect on the live keymap immediately, instead of silently requiring a restart.
- **Settings shortcuts test isolation** (t972): Fixed a test-ordering failure in the Settings Shortcuts tab caused by shared label-case cache state.
- **Detached TUI-spawned agents** (t974): Agents launched from a TUI (board, codebrowser, sync) now run in their own session and survive quitting the TUI that spawned them.
- **History progressive-load fixes** (t975): Fixed the codebrowser History view dropping child tasks during progressive loading and serving stale data; it now reconciles the window and auto-refreshes on open.
- **Minimonitor pane width on resize** (t978): The minimonitor companion pane now stays pinned to its target width when the terminal is resized.

### Improvements

- **Brainstorm: drop detail/patch ops** (t891_2): Removed the brainstorm `detail`/`patch` operations and the detailer/patcher agents as part of the move to a proposal-only model.
- **Brainstorm: remove plan data model** (t891_3): Removed the brainstorm plan data model and the plan-tab TUI surfaces.
- **Brainstorm: finalize exports a proposal** (t891_4): Brainstorm "finalize" now exports the node's proposal to `aiplans/` and blocks if a decomposed module still needs syncing.
- **Brainstorm initializer cleanup** (t672): Simplified the brainstorm initializer's error handling, removing a stale slow-watcher path.
- **Editable Settings tab-switch keys** (t896): The Settings tab-switch keys are now driven by the keybinding registry — editable, reflected in footer hints, and shown in each tab title.
- **NodeDetailModal minimap pane** (t946): Moved the NodeDetailModal section minimap into a fixed sibling pane with exact-heading scrolling.
- **Tmux command gateway** (t952_1, t952_2, t952_3, t952_4, t952_5): Centralized all tmux invocations (Python and shell) behind a single gateway that owns socket policy and exact-match targeting, re-pointed the monitor's control mode through it, and added a lint guard preventing new raw tmux calls.
- **Shared numbered source view** (t959): Extracted a shared line-numbered source-view widget used by both the codebrowser and the brainstorm proposal preview.
- **Single projects.yaml registry reader** (t970): Collapsed the projects.yaml registry reader to a single authoritative implementation shared by the read and write paths.
- **Dead-code cleanup** (t976): Removed a dead `find_terminal` helper from the codebrowser.

### Documentation

- **Monitor-to-applink port design** (t822_3): Added a design doc mapping the monitor's headless core and protocol verbs for the mobile companion port.
- **Brainstorm architecture v2** (t891_1): Authored a proposal-only brainstorm engine architecture doc and archived the v1 (two-level plan) design.
- **AgentCrew docs** (t917): Documented `ait crew` and the AgentCrew concept on the website, including all subcommands and the dashboard/logview TUIs.
- **tmux pane-switching shortcuts** (t948): Documented native tmux pane-switching shortcuts and how to focus the minimonitor from the agent pane.
- **Wish/SSH transport evaluation** (t950): Added an evaluation of SSH-based serving (charmbracelet/wish) as a complementary access path alongside the native mobile transport.
- **Persistent tmux workspace docs** (t957): Documented how to keep a self-launched tmux server alive across a compositor restart on Linux/Wayland.
- **Module design doc reconciliation** (t971): Updated the module-decomposition design doc to reflect the as-implemented (post-t756) proposal-only reality.
- **tmux gateway architecture** (t980): Documented the tmux gateway chokepoint, its centralized policies, and the raw-tmux freeze/allowlist.

### Tests

- **Run tmux tests alongside a live session** (t936): tmux tests now run against an isolated socket so they no longer refuse to run when a live tmux session is present.
- **CodeViewer render regression tests** (t960): Added render-contract regression tests for the CodeViewer after the shared numbered-source-view refactor.

### Maintenance

- **Hide migrate-archives from help** (t918): The one-time, upgrade-only `migrate-archives` command is now hidden from `ait help` (the command itself remains available).

## v0.23.1

### Bug Fixes

- **Cleaner installs and repeatable setup** (t938): Re-running the installer no longer aborts when the global `ait` shim is already present, and an untracked `packaging/` directory left behind by the installer is now removed automatically (a git-tracked `packaging/` is preserved).
- **Reliable test Python resolution** (t935): The test suite now invokes the project's resolved virtual-environment Python instead of a bare `python3`, preventing spurious `ModuleNotFoundError` failures when the system Python is missing `yaml`/`textual`.

### Enhancements

- **Rendered skill-closure ignore rules installed by setup** (t939): `ait setup` now writes gitignore rules that hide locally rendered skill-closure directories under `.claude`, `.agents`, and `.opencode` while still tracking the committed headless prerenders — so generated skill variants no longer show up as untracked clutter.

## v0.23.0

### Features

- **Brainstorm module decomposition** (t756): Break a brainstorm design into independent module subgraphs. Decompose, merge, and sync modules as first-class brainstorm operations, view per-module fluid status, and use the "Fast-track this module" preset to extract a module into a linked aitask in a single pass.
- **Risk evaluation in task planning** (t884): Planning now assesses two risk dimensions separately — code-health risk and goal-achievement risk — records them on the task, auto-creates before/after mitigation follow-up tasks, and force re-verifies a plan when a mitigation lands.
- **Cross-repo paired planning in explore** (t832_11): `aitask-explore` auto-detects cross-repo scope from your description and can create a cross-repo paired task that inherits the cross-repo planning flow.
- **Brainstorm node action dialog** (t925): The node picker surfaces all node operations — including cascade delete with a casualty preview — each with relevance hints.

### Bug Fixes

- **Explicit agent args beat the env var** (t703): `--agent`/`--cli-id` now take precedence over `AITASK_AGENT_STRING`, which acts only as a default.
- **macOS/BSD setup crashes fixed** (t931): `ait setup` no longer silently crashes on BSD; added seed fallbacks and POSIX-portable parsing.
- **Remaining macOS sed portability** (t932): Replaced GNU-only sed quantifiers with portable `-E` forms.
- **Board fast-path fallback** (t933): venv Python dependencies are validated at install time, with the PyPy fast-path falling back to CPython when deps are missing.
- **Risk evaluation reaches the verify path** (t909): the risk step now runs on the plan verify path, not just fresh planning.
- **Config-aware op-help hint** (t921): the brainstorm op-help hint shows the live keybinding instead of a hardcoded key.
- **Headless prerender freshness** (t894, t907): generalized the skill-verify headless prerender check and repaired git-equalized prerender drift via content diffing.
- **Drop minijinja from PyPy venv** (t930): removed an unneeded dependency from the PyPy install line.
- **Harden test assert helpers** (t920): guarded assert-grep calls against dash-prefixed needles.

### Improvements

- **Opt-in headless mode** (t778): `claude` headless `--print` is now gated behind an explicit `--headless` flag to reduce billing surprises.
- **Redesigned Settings → Execution Profiles tab** (t900): fixed selector, name filter, dirty-state-aware Save/Revert, and keyboard navigation.
- **Larger board task-detail dialog** (t904): taller dialog with collapsible metadata sections.
- **Board auto-refresh off by default** (t927): the board no longer auto-refreshes unless you set an interval (existing configured values are preserved).
- **Single-source level enum** (t911): priority/effort/risk levels now come from one canonical definition shared across bash and Python.
- **Internal refactors** (t898, t923, t937): declarative brainstorm wizard step machine; consolidated the test assert helpers into one shared library; switched fragile test `sed -i` calls to the `sed_inplace` helper.

### Documentation

- **`ait` command reference completed** (t914): added missing TUI, cross-repo, and maintenance command docs.
- **aidocs reorganized** (t901): loose docs moved into `framework/`, `packaging/`, and `codeagents/` subjects.
- **Codex workflow-compliance caveats** (t916): documented reasoning-effort guidance for workflow step compliance.
- **macOS awk/sed portability class** (t934): documented the BSD/macOS portability bug class for contributors.

### Performance

- **Slimmer CLAUDE.md** (t924): moved on-demand sections into `aidocs/`, cutting always-loaded context by ~30%.

### Tests

- **Brainstorm module-ops coverage** (t906, t913, t922): added apply-hardening, module-sync contract, and module-status compute contract tests.

### Maintenance

- **macOS compatibility audit** (t926): clean periodic audit; filed follow-ups.
- **pickn/workflown hardening sandbox** (t928): staging copies with stricter fail-closed gates.
- **Regenerate stale planning renders** (t903): refreshed drifted prerenders and goldens.

## v0.22.1

### Enhancements

- **Task risk fields** (t884_1): Tasks now support a `risk` field (high/medium/low) and a `risk_mitigation_tasks` list. Set them with `ait update --risk <level>` / `--risk-mitigation-tasks "a,b,c"`; risk is shown in `ait ls` and is viewable/editable in the board TUI.
- **`risk_evaluation` profile key** (t884_2): Added an opt-in `risk_evaluation` execution-profile key (in the Planning group) that gates risk evaluation during the planning step. Configure it per profile or from the settings TUI; it's off unless enabled.

### Bug Fixes

- **Board detail dialog arrow navigation** (t893): Restored up/down arrow-key field navigation in the board's task-detail dialog, while keeping arrow-key support in the shortcut editor's table.

### Documentation

- **AI-enhanced workflows homepage highlight** (t892): Added a fourth homepage feature highlight linking to the workflows docs, with the highlights reflowed into a 2×2 grid.

## v0.22.0

### Features

- **Cross-repo task dependencies** (t832): Tasks can now depend on tasks in *other* aitasks projects via new `xdeps`/`xdeprepo` frontmatter, with cross-repo blocking logic, a parallel cross-repo planning procedure, `ait board` picker support, interactive cross-repo task creation, cross-repo `explain-context`, and cross-project `aitasks#835_3` notation. Linked projects are referenced by logical name, not directory path.
- **Customizable keyboard shortcuts** (t848): Per-user keyboard-shortcut overrides now work across all TUIs, with an in-TUI shortcut editor modal, a Shortcuts tab in the settings TUI, and case-aware mnemonic label rendering.
- **Autonomous manual-verification mode** (t843, t845): Manual-verification tasks can run their checks autonomously — choose an impromptu or pre-built strategy, configurable per profile and from the settings TUI.
- **Claude Opus 4.8** (t853): Added Opus 4.8 to the model registry and promoted it to the default agent model.
- **Codex request-user-input flag** (t861): Added a Codex feature flag that enables request-for-user-input behavior.

### Bug Fixes

- **Compare-wizard improvements** (t873): Fixed glob dimension link expansion and badge counts, section scroll-to-position accuracy, added expandable dimension descriptions in the detail pane, and scoped/grouped/labeled the wizard's dimensions.
- **TUI task-directory handling** (t877, t881): The keybinding registry, user-config path, and TUI module/metadata loading now honor a non-default task directory.
- **YAML config guards** (t863, t864, t865): Hardened YAML loading/writing in the keybinding registry, user-config writer, and shortcut persistence against parse failures and style collisions.
- **Brainstorm nested sections** (t878): Fixed nested-section parsing and navigation in the brainstorm TUI.
- **TUI switcher overlay shortcuts** (t876): The TUI switcher overlay's shortcuts are now properly registered.
- **Board cross-repo picker navigation** (t886): Fixed keyboard navigation in the board's cross-repo reference picker.
- **add-model default target** (t852): Fixed the target of the default-agent-string update in `aitask-add-model`.
- **Stale Gemini note in CLAUDE.md** (t839): Removed an outdated Gemini reference from the Codex root note.
- **Test-fixture fixes** (t883, t890): Repaired the desync test fixture's Python resolution and the PR-contributor fixture's cross-repo re-exec scaffold.

### Improvements

- **Board task filtering** (t850): Reworked board filtering into an independent base-filter plus git and type toggles, with broader locked/free visibility rules.
- **Re-verification prompt** (t885): When a task plan is already verified, you're now asked whether to re-verify.
- **Eager subscope registration & mnemonic labels** (t848_9, t848_10): Shortcut subscopes register eagerly and labels render case-aware mnemonics.
- **Terminology cleanups** (t849, t859): Renamed "impromptu" → "autonomous" and the `manual_verification_auto_mode` profile key to clearer names across skills and docs.

### Documentation

- **Multi-project & cross-repo workflow docs** (t826_3, t832_12): New website pages covering the multi-project registry workflow and cross-project dependencies/planning.
- **Manual-verification & shortcuts docs** (t846, t848_6): Documented autonomous manual-verification mode and the customizable-shortcuts layer.
- **Codex limitations & model-default refs** (t862, t854): Refreshed Codex limitations docs and updated stale model-default references.
- **Memory-to-aidocs audit** (t869): Promoted durable authoring conventions from Claude memories into `aidocs/`.

### Tests

- **AGENTS.md idempotency** (t875): Added tests for `AGENTS.md` creation and marker idempotency.

### Maintenance

- **Codex profile/prompt cleanups** (t860, t866, t870): Removed redundant default-profile prompt-suppression keys, relaxed forced Codex plan mode for analysis skills, and deleted orphaned Codex interactive prerequisites.

### Removals

- **Remove Gemini CLI Support** (t812): Removed `geminicli` from the framework: agent identity layer, skill rendering and templating, setup/install/release pipeline, and all current-state documentation. Google is sunsetting Gemini CLI in favor of Antigravity CLI (agy); see t813 and t814 for the agy migration path. Existing CHANGELOG / blog references to Gemini CLI are preserved as historical record. `aidocs/adding_a_new_codeagent.md` was expanded into a reusable add-an-agent checklist along the way.

## v0.21.1

### Bug Fixes

- **Fix Brainstorm Retry Apply Drained Set** (t841): The `ctrl+shift+x/y/d` retry-apply bindings in brainstorm now rescan the worktree for completed explorer/synthesizer/patcher/detailer agents instead of consuming a one-shot in-memory set, so retries no longer silently no-op after the original apply ran. Surfaces a "No completed agents to retry" notify when the worktree is empty.
- **Fix v0.21.0 Blog YAML and Release Post Quoting** (t844): Repaired the v0.21.0 blog frontmatter (unescaped inner quotes broke the YAML parse) and hardened `website/new_release_post.sh` to escape title/description fields plus run a Python YAML smoke check after generation, preventing future release posts from shipping broken frontmatter.

### Enhancements

- **Improve Dialog for Next in Monitor** (t840): The monitor TUI's next-task dialog now offers a "Choose sibling" picker listing every ready sibling of the current task with blocked-by-sibling annotations, so you can pivot mid-family without backing out to the board.
- **Textual 8.2.7 Floor**: Bumped the minimum `textual` version to 8.2.7 across `ait setup` and the applink reference docs to pick up upstream text-selection improvements in TUI screens.

## v0.21.0

### Features

- **Brainstorm Apply Explorer Output** (t739): Brainstorm now auto-applies explorer agent outputs into DAG nodes when they complete, with a `ctrl+shift+x` retry binding and an `apply-explorer` CLI fallback for failure recovery.
- **Brainstorm Apply Synthesizer Output** (t740): Brainstorm auto-applies synthesizer agent outputs to create hybrid nodes linked to multiple parents, with a `ctrl+shift+y` retry binding and an `apply-synthesizer` CLI fallback.
- **Brainstorm Apply Detailer Output** (t741): Brainstorm auto-applies detailer agent outputs, writing the detailed plan into the node and updating its `plan_file` reference, with a `ctrl+shift+d` retry binding.
- **Operation Detail Screen** (t749_5): Added an `OperationDetailScreen` modal to the brainstorm TUI showing an operation Overview plus per-agent Input / Output / log tail tabs.
- **Aitask Skill Render Subcommand** (t777_2): Added the renderer that produces per-profile skill variants from `.md.j2` templates, with skip-if-fresh caching and cross-skill include resolution.
- **Stub Skill Design and Gitignore** (t777_3): Established the canonical "stub + per-profile render" model so each agent's skill surface dispatches to a profile-specific rendered variant, with a `*-/` gitignore convention for the generated dirs.
- **Aitask Skill Verify and Precommit** (t777_4): Added `aitask_skill_verify.sh` to validate that `.md.j2` templates render cleanly across all profiles and agents and that per-agent stubs carry the canonical dispatch markers.
- **Aitask Skillrun Wrapper Dispatcher** (t777_5): Added `ait skillrun` for launching any code agent with a profile-aware aitask skill, including `--profile-override` for ad-hoc YAML merges and `--dry-run` previews.
- **Per Run Profile Edit in AgentCommandScreen** (t777_17): The launch dialog now has an `(E)dit` button to tweak the active execution profile for either a one-shot run or persistent save, propagated through to the rendered prompt.
- **Profile Modification Invalidation** (t777_20): Saving a profile from the settings or launch TUIs now eagerly re-renders all affected per-profile skill variants so running agents see the new values on next invocation.
- **Extend Renderer for Uniform Recursive Rendering** (t777_22): The skill renderer now walks the full reference closure of a template, rewriting cross-skill `.md` references per agent root and tracking staleness across the entire dependency graph.
- **Support Open in Editor in Codebrowser** (t781): Added an `E` keybinding to the codebrowser TUI that suspends to `$EDITOR` on the currently-viewed file, then refreshes annotations on return.
- **Clickable Nodes in DAG** (t793): Brainstorm Graph-tab DAG nodes are now click-focusable, mirroring arrow-key focus behavior; actions still require keyboard confirmation.
- **Detailed Operation Description in Wizard** (t796): The brainstorm Actions wizard now shows the operation label plus a brief description on every step beyond Step 1, with `?` reachable from any wizard step.
- **Allow Archived Tasks in Task Dependencies in Create** (t798): `ait create` now offers a fzf-based picker for adding archived task references inline into a task description.
- **Context Aware Operations in Brainstorm** (t819): Added an `A` keybinding on the brainstorm Graph/Dashboard tabs that pops a picker for Explore / Detail / Patch on the focused node and pre-seeds the Actions wizard with the choice.
- **Applink TUI QR** (t822_2): Added the `ait applink` TUI which generates a QR code carrying a LAN pairing URI for the mobile companion app, including hostname and TLS-fingerprint fields.
- **Applink QR Add Hostname Field** (t822_5): The applink QR pairing URL now includes an optional `name=` field carrying the local hostname for friendly device identification on the mobile side.
- **Registry Resolver Projects Cmd and Create Flag** (t826_1): Added the cross-repo project registry at `~/.config/aitasks/projects.yaml` plus the `ait projects` command (list/add/resolve/exec) and `ait create --project <name>` flag for cross-repo task creation.
- **TUI Switcher Show Inactive Projects** (t826_2): The TUI switcher's Session row now surfaces registered-but-inactive projects; selecting one transparently spawns a tmux session for it on demand.
- **Ait Projects Remove Update Verbs** (t826_7): Added `ait projects remove` (with `--force`) and `ait projects update` verbs to manage entries in the cross-repo registry.
- **Ait Projects Prune Verb** (t826_8): Added `ait projects prune` to bulk-remove stale registry entries whose marker file is gone, with `--dry-run` and `--yes` modes.
- **Ait Projects Doctor Verb** (t826_9): Added `ait projects doctor` for interactive triage of stale registry entries with options to prune, repoint, or clone the missing project back.
- **Switcher Stale Inline Render and Race** (t826_10): The TUI switcher dims stale registry entries with a `(stale)` suffix and pops an inline Prune / Repoint modal when one is selected, including the race-condition path when an entry goes stale mid-session.

### Bug Fixes

- **Template Completeness and Resolver Key** (t777_26): Dropped the runtime profile-resolution fallback in templated skills and fixed the resolver-key mismatch between stubs and bodies so per-profile dispatch lands on the correct variant.
- **Graph Tab Breaks Tab Navigation** (t788): Pressing Up on the brainstorm Graph tab's top layer now escalates focus back to the tab row instead of trapping the user inside the DAG view.
- **Missing Shortcuts from TUI Switcher Footer** (t789): The TUI switcher footer is now pinned to the bottom of the dialog and stays visible regardless of list size, so keyboard shortcuts remain discoverable.
- **Status Update Error in Explorer Agent** (t791): Crew agents can now use `-m` as a short alias for `--message` on the heartbeat command, and the generated instructions show the message syntax explicitly.
- **Brainstorm Explore Progress** (t792): Brainstorm now force-canonicalizes each agent's `created_by_group` on apply, defends graph-tab consumers against historical drift, and shows a group-level aggregate progress bar in the Status tab.
- **Brainstorm Explorer Input Missing Node ID** (t795): Brainstorm now assigns the node ID to each explorer/synthesizer/patcher agent at registration time, so parallel siblings cannot collide on the same generated node.
- **Disallow Patch for Node Without Plan** (t797): The brainstorm UI now shows a `has plan` / `no plan` indicator on each node and disables the patch operation for nodes without a plan, preventing silent failures.
- **Aitask Explore With Codex** (t801): `ait setup` now installs `pexpect` so the `aitask explore` workflow launches Codex without import errors on fresh installs.
- **Add Codex Rules Allowlist Support** (t802): Added runtime and seed Codex allow-rules so the `codex` agent can be launched through aitasks without hand-editing rules files.
- **Keybinding in Wizard for Node Selection** (t806): The brainstorm Hybridize / Compare wizards now offer a fuzzy filter plus Tab group cycling and arrow-key checkbox navigation, with checked rows always visible.
- **Synthetize or Hybridize** (t807): Renamed the brainstorm DAG merge operation from `hybridize` to `synthesize` across code, tests, and docs, with a backward-compat alias so in-flight sessions still render correctly.
- **Fix Patcher CLI Next Node ID Assertion** (t810): Fixed a brainstorm patcher CLI test that wrongly asserted `next_node_id` would advance on apply — the apply path is correct, the assertion was off-by-one.
- **Fix Aitask Update Multiline YAML List Parsing** (t813): YAML frontmatter parsers now correctly join multi-line flow-list values (e.g. wrapped `folded_tasks`, `verifies`) so `ait update`, archive, and crew tools no longer truncate them.
- **TUI Switch Multiproject Hide Brainstorms** (t814): The TUI switcher's brainstorm session discovery is now scoped to the selected project's `.aitask-crews/`, so multi-project switches don't surface cross-project brainstorms.
- **Dedup Read YAML Field Definition** (t815): Consolidated two competing `read_yaml_field` definitions into a single shared `yaml_utils.sh` lib, eliminating a silent function-collision risk at archive time.
- **Fix Skill Dep Walker SKILL.md Collision** (t817): The skill dep-walker now skips self-referencing `SKILL.md` prose mentions and raises a loud collision error if two distinct sources ever map to the same target path.
- **Brainstorm Ops Fail to Write Output** (t820): Crew `_instructions.md` now tells the agent to read the pre-existing `<agent>_output.md` placeholder before writing, preventing accidental overwrites that produced empty operation results.
- **Detailer Final Output Parsing Seems Not Work** (t821): Brainstorm's auto-apply scan now tracks in-flight agents (not just Completed ones) and prunes terminally-failed ones from polling, so detailer/patcher output is reliably picked up.
- **Fix TUI Switcher Desync Line Stale Across Sessions** (t823): The desync helper now resolves the repo root from cwd rather than the script's install location, so the switcher's desync line reflects the active project in multi-project setups.
- **Fix Test Desync State Copy Changelog Missing YAML Utils** (t824): Added the missing `yaml_utils.sh` to the changelog-test scaffold's file list so the test no longer crashes on missing-source errors.
- **Idle State Not Detected** (t825): The monitor TUI now distinguishes "agent awaiting user input" from "idle" via per-agent prompt regex patterns, surfaces a separate `awaiting` count, and prefers awaiting panes when auto-switching.
- **Fix Test Codeagent Scaffold Missing Agent String** (t827): Added `agent_string.sh` to the codeagent test scaffold so the test suite no longer fails on a missing source library.
- **Obsolete AgentCommand Dialog in Monitor** (t830): The per-run profile edit now propagates through to launch dialogs in monitor, codebrowser, and history-screen TUIs, not just the board.
- **Add Back Support for PyPy for Ait Board** (t831): Restored the optional PyPy fast path scoped to `ait board` only (the four other TUIs stay on CPython), with `AIT_PYTHON=` documented as the ad-hoc override for A/B testing.
- **Fix Tmux Monitor Relative Import** (t833): Aligned a stray `tmux_monitor` test with the canonical `monitor.tmux_monitor` import path used by all peer tests, fixing three test errors.
- **Fix Failed Verification t787 Item3** (t837): The `ctrl+shift+x` retry binding in brainstorm now rescans the worktree for completed explorer agents instead of consuming an in-memory set, with a clear notify when no candidates exist.

### Enhancements

- **2D Arrow Navigation** (t748_1): The brainstorm Graph tab DAG now navigates with all four arrow keys (prev/next layer plus prev/next column with nearest-center snap), replacing the prior `j`/`k`-only flow.
- **Inline Detail Pane** (t748_2): The brainstorm Graph tab now has a right-side inline detail pane that updates as you navigate the DAG, plus Tab/Shift+Tab to toggle focus between the DAG and the detail.
- **View Proposal Plan Keys** (t748_3): Added `p` and `l` bindings on the brainstorm Graph tab to view the focused node's proposal or plan in the section viewer.
- **Compare With Picker** (t748_4): The brainstorm Graph tab now has an `x` binding to pick a compare-with anchor (highlighted in Dracula orange), `enter` to confirm, and `escape` to cancel, opening the Compare tab with the diff matrix.
- **O Keybinding Open Screen** (t749_6): Added the `o` binding on brainstorm DAG and NodeRow widgets to open the `OperationDetailScreen` for the focused node's generating group.
- **Minijinja Comments** (t786): Wrapped Jinja conditionals in templated skills with a documented same-line comment ruler convention, making profile-aware blocks easier to scan without disturbing rendered output.
- **Brainstorm Op Modal Loading Indicator** (t794): The brainstorm `OperationDetailScreen` now shows a loading indicator while it gathers content, eliminating the previous blank-modal pause when opening.
- **Defer Explore Sync to Step 2b** (t800): The `aitask-explore` skill defers its remote sync to Step 2b so the first user prompt fires faster, with sync still happening before any task creation.
- **Extend Profile Rendering with Agent Suffix** (t834): Rendered skill dirs in shared roots (currently codex) now carry an extra `-<agent>-` suffix so multiple agents sharing one root cannot collide on the same target path.
- **Auto Select Session in TUI Switcher** (t836): Opening the TUI switcher from a focused agent pane in monitor/minimonitor now pre-selects that pane's session instead of always starting on the attached session.
- **Codebrowser Show Tasks Without Code Commits** (t838): The codebrowser history now surfaces archived tasks that have no `(tNN)` code commits, anchored on their archival commit or file mtime, with a dim `[no-code]` marker.

### Improvements

- **Test Scaffold Helper for Fake Aitask Repo** (t734): Consolidated the per-test "copy these libs into a fake aitask repo" boilerplate into a shared `setup_fake_aitask_repo()` helper, reducing per-test duplication across 43 tests.
- **Convert Aitask Pick Template and Stubs** (t777_6): Piloted converting `aitask-pick` to the stub + `.md.j2` template model, producing the rename + golden-file playbook reused by sibling skill conversions.
- **Convert Task Workflow Shared Procs** (t777_7): Staged a templated copy of the shared `task-workflow` procedure files with Jinja-wrapped profile checks, in a parallel `task-workflown/` dir to avoid disturbing live skill execution.
- **Convert Aitask Explore** (t777_8): Converted `aitask-explore` to the templated stub + per-profile `.md.j2` model with the canonical `explore_auto_continue` profile wrap.
- **Convert Aitask Review** (t777_9): Converted `aitask-review` to the templated stub + per-profile `.md.j2` model, wrapping `review_default_modes` and `review_auto_continue` profile checks.
- **Convert Aitask Fold** (t777_10): Converted `aitask-fold` to the templated stub + per-profile `.md.j2` model with its `explore_auto_continue` profile wrap.
- **Convert Aitask QA** (t777_11): Converted `aitask-qa` to the templated stub model (including its own procedure-file closure) with wraps for `qa_tier`, `qa_mode`, `qa_run_tests`, and `skip_task_confirmation`.
- **Convert Aitask PR Import** (t777_12): Converted `aitask-pr-import` to the templated stub + per-profile `.md.j2` model with its `explore_auto_continue` wrap.
- **Convert Aitask Revert** (t777_13): Converted `aitask-revert` to the templated stub + per-profile `.md.j2` model, preserving its `user-file-select` closure references.
- **Convert Aitask Pickrem** (t777_14): Converted the remote/headless `aitask-pickrem` skill to a templated model with pre-committed remote-profile renders so headless agents pick up the right variant without a runtime render step.
- **Convert Aitask Pickweb** (t777_15): Converted `aitask-pickweb` to the templated model with pre-committed remote-profile renders and fixed the OpenCode skill-registry leftover that misrouted pickweb to the wrong agent root.
- **Extract Profile Editor Widget** (t777_16): Extracted the profile-editor widgets, schema, and `ProfileEditScreen` modal from `settings_app.py` into a shared `lib/profile_editor.py` so other TUIs can mount the same modal.
- **Refactor Stubs Direct Helper Paths** (t777_25): Removed the `ait skill` subcommands; profile-aware skill stubs now invoke the helper scripts (`aitask_skill_render.sh`, `aitask_skill_verify.sh`) directly.
- **Dedup Template Branches Common Proc and Macros** (t777_28): Deduplicated the Continue / Save-for-later decision-point block across 4 skill templates via a shared Jinja macro, plus inlined the parent/child confirmation prompt as a macro inside `aitask-pick`.
- **Fix OpenCode Skill Legacy Pointers** (t777_29): Rewrote 8 OpenCode `.opencode/skills/<skill>/SKILL.md` files as proper dispatch stubs so OpenCode skill auto-discovery routes through the correct agent root for templated skills.
- **Retire PyPy Fast Path Consolidate on CPython** (t785): Removed the PyPy fast path from the framework (launchers, resolver, installer, env vars, tests, docs) after empirical evidence showed PyPy was slower than CPython for most TUI workloads. (Note: t831 later restored a board-only PyPy path.)
- **Gate Agent Specific Blocks in Skills Via Jinja** (t803): Converted `aitask-wrap` to the templated stub model, gating its "Recent Claude Plans" check on `{% if agent == "claude" %}` so other agents see a cleaner skill body.
- **Brainstorm Reconcile Patcher Into Apply Node Output** (t808): Reconciled the brainstorm patcher apply path into the shared `_apply_node_output` core with a parser-strategy hook, so explorer/synthesizer/patcher all share one error-handling and validation site.
- **Prune Redundant Skill Render Goldens** (t809): Pruned 51 byte-identical agent-variant goldens from the skill-render test suite and added byte-equality cross-checks, so divergence is caught loudly rather than carried as redundant fixtures.
- **Align Detailer Planning Plan Contract** (t818): Added a shared `skill_templates/` fragments dir bridging minijinja-rendered skill templates and bash-resolved brainstorm templates, exercised by both pipelines.
- **Status Aware Read Registry Index** (t826_6): The project-registry reader now classifies each entry as OK or STALE up front, surfacing stale registry rows to the TUI switcher and CLI doctor flows.

### Documentation

- **Docs Update CLAUDEmd and Website** (t777_18): Added a "Skill templating and per-profile dispatch" section to CLAUDE.md plus a new `concepts/skill-templating` website page covering the stub + render flow, per-agent surfaces, and Jinja patterns.
- **Audit Claude Memory Promote to Claude MD** (t779): Promoted 19 durable rules from per-user Claude memory into CLAUDE.md, organized into Skill / Shell / TUI / Planning / Testing / Code Conventions plus a Reusable Helpers section.
- **Task Workflow AskUserQuestion Non Optional** (t782): Added explicit `⚠️ NON-SKIPPABLE` banners at the Step 8b/8c/9/9b workflow gates documenting which (and only which) profile keys may legitimately opt out.
- **Document Golden Regen on Template Edit** (t805): Added a "regenerate goldens after any `.md.j2` or closure edit" rule to the skill-authoring docs and fixed 12 stale goldens that the audit surfaced.
- **Applink Protocol Design** (t822_1): Added `aidocs/applink/` design docs covering the WebSocket protocol, message envelope, pairing flow, connection state machine, permission profiles, and verb gating table for the mobile companion.

### Performance

- **Verify PyPy for Monitor Minimonitor** (t718_5): Benchmarked PyPy vs CPython for the monitor/minimonitor hot path; PyPy was slower at every realistic pane count so both TUIs stay on CPython.
- **Verify PyPy for Board and Codebrowser** (t718_6): Benchmarked PyPy vs CPython for board and codebrowser; kept board on PyPy (13.6% faster) and reverted codebrowser to CPython (PyPy was 16.6% slower for its render-heavy hot path).
- **Compact CLAUDE MD** (t783): Compacted CLAUDE.md from 397 lines to 286 (-76% bytes) by extracting six specialist topics into `aidocs/` files referenced via "read when…" pointers, reducing always-loaded context size.

### Maintenance

- **Minijinja Dep Renderer Paths Resolver** (t777_1): Added the foundation for profile-aware skill rendering: `minijinja` dependency, the `lib/skill_template.py` renderer, agent-skill path helpers, and the profile resolver helper.
- **Swap Task Workflown to Task Workflow** (t777_23): Promoted the staged `task-workflown/` template skill back to the live `task-workflow/` skill name, completing the conversion started in t777_7.

### Tests

- **Recover Runtime Skills and Parity Tests** (t777_27): Added a parity test suite that renders the converted skills against frozen pre-rewrite fixtures and asserts each profile produces the expected per-profile user-visible text, guarding against silent rewrite drift.
- **Fix Test OpenCode Setup Glob Mismatch** (t828): Pinned the OpenCode setup test's install set to the `git ls-files` tracked skills so it no longer fails when locally-rendered profile-variant dirs are present.

## v0.20.3

### Improvements

- **Regroup installation pages and unify Linux** (t766): Consolidated the separate Arch / Debian / Fedora install pages into a single Linux page with per-distro sections, and reorganized the Installation index into clear "Operating systems" and "Setup topics" groups for easier navigation.

### Documentation

- **About page redesign** (t763): Refreshed the About page with a slim header, updated project stats (37 releases, 26 skills, 80+ CLI scripts), and centered author and license blocks for a cleaner look.
- **Only main TUIs on the home page** (t764): Trimmed the home page tour from five tiles to three (Board, Code Browser, Monitor) so the spotlight stays on the most-used TUIs.
- **Render overview "See also" refs as links** (t765): The cross-references on the Overview page now render as clickable links instead of bare shortcodes.
- **Getting Started: simpler install pointer** (t767): Replaced the inline per-platform install command table with a single pointer to the Installation guide so the page stays focused on first-run steps.
- **Codebrowser task-creation mention on TUIs page** (t768): The TUIs index now highlights that the Code Browser can create tasks tied to specific line ranges (press `n`), with optional auto-merge of existing tasks referencing the same file.
- **Updated maturity labels across TUI and skill docs** (t769): Added or refreshed the maturity tag on 37 doc pages and introduced a new `stable` maturity value, so the sidebar maturity cloud accurately reflects each TUI and skill.
- **Full mouse support documented across TUI docs** (t771): Every TUI doc page (and the home page tour) now calls out full mouse support — click to select, scroll to navigate — as an alternative to keyboard.
- **Installation subpage for updating model lists** (t772): New "Updating Model Lists" page under Installation explains how to refresh the supported-models list for OpenCode and friends, and how to register a single known model.
- **Lead with curl install; point upgrades to `ait upgrade`** (t773): Install pages now lead with the curl one-liner and present native packages as an alternative; per-platform "Upgrade" sections point to `ait upgrade latest` instead of suggesting (misleading) package-manager upgrades.

### Maintenance

- **Bump deprecated Node 20 actions** (t758): Updated `actions/checkout` to v6 and `softprops/action-gh-release` to v3 in release workflows to drop the deprecated Node 20 runtime.
- **Refresh OpenCode supported-models list** (t770): Refreshed `models_opencode.json` (and the seed copy) with the current set of active models — 50 active plus 11 retained as unavailable for score history — so new projects ship with an up-to-date model list.

## v0.20.2

### Bug Fixes

- **Code browser History screen crash** (t761): Fixed a crash when opening the History screen from a cold start; the screen now properly waits for its panes to mount before populating them.
- **Release packaging tests on Rocky Linux 9** (t759): Fixed the `test-rpm` CI job, which was failing on Rocky Linux 9 due to a `curl` / `curl-minimal` package conflict.

### Documentation

- **Per-platform install instructions** (t623_6): The README and website now document native install methods for each OS — Homebrew on macOS, AUR on Arch, `.deb` for Debian/Ubuntu, `.rpm` for Fedora/Rocky/Alma — alongside the curl fallback. Each platform has its own install page, and a new packaging-status reference doc tracks limitations and roadmap.
- **Redesigned home page** (t760): The website home page now opens with a split hero (text and screenshot side-by-side) and a "Take the tour" mosaic of TUI screenshots (Board, Code Browser, Monitor, Settings, Stats). Several feature sections gained inline screenshots.
- **Linked home page feature cards** (t762): The three top feature cards on the home page are now clickable, linking to the tour mosaic, agent memory docs, and the git workflows section.

## v0.20.1

### Bug Fixes

- **Release packaging workflow restored** (t757): The .deb and .rpm build jobs now invoke `nfpm` directly via its official Docker image, replacing the deleted `goreleaser/nfpm-action` GitHub Action so release packaging runs again.

## v0.20.0

### Features

- **Homebrew tap with CI auto-bump** (t623_2): A Homebrew formula template and reusable `release-packaging.yml` workflow auto-bump the tap on every tag, so macOS users can `brew tap beyondeye/aitasks && brew install aitasks`.
- **Arch AUR package with CI auto-bump** (t623_3): A PKGBUILD template and AUR publishing job auto-bump the AUR package on every tag, so Arch users can install via `yay -S aitasks` once the maintainer secrets are configured.
- **Debian/Ubuntu .deb packaging** (t623_4): `.deb` packages are now built and tested across Ubuntu 22.04/24.04 and Debian 12 in CI, attached to each release for `apt install ./aitasks_*.deb`.
- **Fedora/RHEL .rpm packaging** (t623_5): `.rpm` packages are now built and tested across Fedora 41/42 and Rocky Linux 9 in CI, attached to each release. Rocky/RHEL/AlmaLinux users need EPEL enabled first.
- **Syncer TUI** (t713_1, t713_2, t713_3, t713_5): A new `ait syncer` TUI surfaces ahead/behind state for `main` and `aitask-data` with one-key sync, pull, and push actions. Failures open an in-TUI escape hatch to dispatch a code agent for resolution.
- **Syncer integrated into switcher and monitors** (t713_4): The TUI switcher gains a `y` shortcut for the syncer and shows a desync line; monitor and minimonitor session bars surface a compact desync indicator. Optional `tmux.syncer.autostart` auto-launches it via `ait ide`.
- **Improved agent chooser dialog** (t716): The agent/model picker now cycles between Top, All, and per-agent modes via Shift+Left/Right, with a "use previous agent" shortcut that only remembers non-default picks.
- **Live usage statistics** (t717_2): Each task completion now records a usage entry independently of satisfaction feedback, building per-skill, per-agent run counts that survive month rollovers via a new `prev_month` bucket.
- **Recent-window modes in agent picker** (t717_3): The agent/model picker now ranks Top by a rolling recent window (this month + last month) and adds a new "Top by usage" mode, so old high-score incumbents stop dominating.
- **Stats TUI usage pane and time-window cycling** (t717_4): A new "Usage rankings" pane joins the Agents preset, and `[`/`]` cycle between recent / all-time / month / prev_month / week windows on both rankings panes.
- **Brainstorm patcher output applies automatically** (t743): When a patcher agent finishes, brainstorm now auto-creates the new node and shows an impact banner. A CLI fallback (`ait brainstorm apply-patcher`) handles cases where auto-apply fails.
- **Persisted brainstorm operation history** (t749_1, t749_2): Every brainstorm design op is now recorded in `br_groups.yaml` with agents, nodes created, and timestamps, with an `OpDataRef` reader for inputs/outputs/logs.
- **Module-decomposition design for brainstorm** (t754): A design doc lays out new `decompose`, `sync`, and `merge` operations for splitting umbrella plans into module subgraphs, syncing implementation status back, and re-merging — implementation in follow-up phases.
- **Brainstorm dashboard redesign** (t721): The dashboard detail pane now groups dimensions by category with proposal-section badges and Tab/Shift+Tab navigation between panes; node detail gains a `home`/`m` shortcut to jump to the inline minimap.
- **Crash recovery in `ait pick`** (t723): When a task lock is held by a dead process on the same host, `ait pick` now detects the crash via PID liveness, surveys in-progress work, and offers a guided reclaim or decline.
- **Syncer footer scopes bindings to selected row** (t736): The syncer footer now only shows `s` for `aitask-data` rows and `u`/`p` for `main` rows, with a loading indicator on long operations.
- **Brainstorm patch wizard step 3 instructions** (t737): The patch-request step now shows an instructional label and disables Next until the user types a request.
- **Context-aware brainstorm footer + tab key shortcuts** (t745_1, t745_2, t745_4): Tab keys (`d`/`g`/`c`/`a`/`s`) are embedded in tab labels rather than the footer; tab-scoped actions (`r` regenerate compare, `D` open diff) only show in the relevant tab. Compare select modal gains a `c` confirm shortcut and disables the button until 2–4 nodes are picked. The Compare tab's "Diff" action now opens the diffviewer screen in-app instead of a backgrounded subprocess.
- **Compact compare matrix with inline word-diff** (t745_3): 2-node compare rows now collapse equal values to `← same` and render differing values as inline word-diffs, making diffs much easier to scan.
- **Operation badges in brainstorm DAG** (t749_3): Each DAG node box now shows a colored op badge (e.g. `INITIALIZER`, `EXPLORER`, `PATCHER`) so you can see at a glance how each node was generated.
- **"Generated by" block in brainstorm dashboard** (t749_4): The dashboard detail pane now shows the operation, agents, and timestamp that produced each node, with a hint to drill into operation details.
- **Brainstorm node-detail dialog: full-screen view, export, navigation** (t753): The node-detail dialog now surfaces `v` (full-screen view) and `e` (export) shortcuts in the footer, with a sub-modal for exporting Proposal/Plan to user-chosen directories. Tab focuses the inline minimap.

### Bug Fixes

- **Codex auto-launches in plan mode** (t714): Codex-spawned skill agents (pick, explain, qa, explore) now start in `/plan` mode automatically; `raw` and `batch-review` continue to bypass it.
- **Detect idle Codex CLI agents in monitor** (t715): Monitor and minimonitor now strip ANSI escapes for idle comparison, so Codex agents are no longer reported as running while idle. A `d` shortcut cycles per-pane comparison mode and an `≈`/`=` glyph shows the active mode.
- **Test setups missing `lib/aitask_path.sh` + `lib/python_resolve.sh`** (t724, t732_5): Restored these libs to four test fixtures so verification, manual-verification, brainstorm-CLI, explain-context, migrate-archives and task-push tests run green.
- **Keep selected agent visible in monitor** (t726): When the preview pane is focused, the previously-selected pane card now stays highlighted, so you don't lose track of which agent you were inspecting.
- **`ait setup --with-pypy` works on Linux** (t727, t728, t731): Fixed the uv binary path discovery, made the `pypy*` candidate list honor `AIT_PYPY_PREFERRED`, and validated `sys.implementation.name == 'pypy'` on every PATH candidate so a misnamed CPython on PATH can't be falsely accepted.
- **Agent command screen "blank" pick crash** (t730): The agent/model dialog no longer crashes on empty-selection ticks under newer Textual versions.
- **Cluster A: Textual TUI test API drift** (t732_1): Fixed multi-session minimonitor and TUI switcher tests against current Textual; the switcher's desync label is now resilient to query-before-mount.
- **Cluster B: Python resolver test wrapper** (t732_2): The `python_resolve` test now resolves through `sys.executable`, surviving `HOME` overrides that broke the framework Python wrapper indirection.
- **Cluster C: branch-mode and upgrade test scaffolds** (t732_3): Test scaffolds now copy `lib/python_resolve.sh` and include `packaging/` in synthetic upgrade tarballs, restoring 30/30 init-data, 16/16 branch-mode-upgrade, and 17/17 t167-integration tests.
- **Cluster D: codex model registry drift + gemini venv path** (t732_4): The codex model registry refresh dropped 3 deprecated entries and added 2 new ones, with the test now sourced from `models_codex.json` and gating on calibration semantics; the gemini setup test strips `~/.aitask/bin` from PATH under HOME overrides.
- **Cluster F: codemap help text** (t732_6): The `aitask_codemap.sh` help test now matches the new "framework Python resolved by lib/python_resolve.sh" wording.
- **Monitor reconnect on tmux control channel failure** (t733): The monitor now detects tmux control-channel failures, falls back to subprocess, and reconnects with bounded backoff. A control-state badge surfaces the current state in the session bar.
- **Multi-session minimonitor scaffold** (t735): Test scaffolds now initialize `_refresh_timer` and `_monitor.control_state` so post-t733 tear-down and bar-rendering paths run.
- **Monitor finds task descriptions for archived tasks** (t738): Monitor and minimonitor now fall back to `aitasks/archived/` and `aiplans/archived/` when looking up a task's description, so completed-task panes no longer show empty info.
- **Up/down arrows navigate brainstorm Compare modal** (t746): The compare-node-select modal now responds to arrow keys for checkbox navigation.
- **Up arrow on brainstorm Compare tab** (t747): Up-arrow now navigates table rows on the Compare tab instead of jumping straight to the tab bar.
- **Board view-mode filters apply** (t751): Pressing `i` (Implementing), `g` (Git), or `a` (All) on the board now actually filters cards instead of leaving the previous view.
- **Brainstorm op-help shortcut** (t752): A `?` key on the Actions wizard step 1 now opens an op-specific help modal explaining what each operation does and what input it needs.
- **Stats TUI no longer crashes on PyPy** (t755): The stats TUI now stays on CPython because its `plotext` dependency only ships in the CPython venv. PyPy fast-path users no longer hit an import error.

### Improvements

- **Extracted shared sync action runner** (t713_8): Sync logic shared between the board and syncer TUIs now lives in `lib/sync_action_runner.py`, eliminating duplicated conflict-screen and status-handling code.
- **`prev_month` bucket in verifiedstats** (t717_1): Verified stats now retain last-month data when rolling into a new month, so recent-window views (added in t717_3/t717_4) have data immediately rather than waiting a month.
- **Deduped verify-path model self-detection** (t717_6): The pick-verify and agent-attribution flows now share a single Model Self-Detection call via `detected_agent_string`, eliminating a redundant detection round-trip.
- **User-action tmux calls routed through control client** (t722): Sync user actions (kill, send-keys, switch-pane, capture-pane) now go through the persistent `tmux -C` client instead of forking subprocesses, eliminating fork overhead on the hot path.

### Documentation

- **Syncer TUI documentation** (t713_6): A full website page covers the syncer TUI's actions, failure handling, switcher integration, autostart, and configuration, with cross-links from monitor/minimonitor/sync-command pages.
- **PyPy runtime documentation** (t718_3): A new `installation/pypy.md` page documents the opt-in PyPy fast-path runtime, the `AIT_USE_PYPY` precedence table, the 6 fast-path TUIs, and which TUIs stay on CPython.
- **Crash recovery workflow page** (t725): A new workflow page explains the same-host-crash, multi-PC, and lock-anomaly cases, with the in-progress work survey and the reclaim/decline prompt walked end-to-end.

### Performance

- **Opt-in PyPy runtime infrastructure** (t718_1): `ait setup --with-pypy` now installs PyPy 3.11 (via Homebrew on macOS, uv on Linux) and creates a parallel venv for fast-path TUIs.
- **Long-running TUIs use PyPy when installed** (t718_2): The board, codebrowser, settings, stats, brainstorm, and syncer TUIs now auto-route through PyPy when `ait setup --with-pypy` has been run, dramatically reducing startup and refresh latency.
- **Persistent tmux control client** (t719_1): A new `TmuxControlClient` opens a single `tmux -C` session and multiplexes commands, returning replies via async futures — the foundation for fork-free monitor refresh.
- **Monitor refresh routed through control client** (t719_2): Hot-path monitor refresh now uses the persistent control client, achieving a ~10× speedup and 100% fork elimination on a 5-pane benchmark.

### Tests

- **Pre-flight guard on destructive tmux tests** (t750): Eight tests that destructively manipulate tmux now refuse to run inside a tmux session or alongside live aitasks tmux servers, preventing client crashes during local test runs.

### Maintenance

- **Packaging strategy and shim extraction** (t623_1): The `ait` global shim is now a standalone file at `packaging/shim/ait`, uploaded as a release asset and consumed by every PM (Homebrew/AUR/.deb/.rpm). A new `aidocs/packaging_strategy.md` is the single source of truth for downstream packaging children.

## v0.19.2

### Features

- **Warn user about remote changes after planning** (t708): Added a post-planning drift check that warns when `origin/main` has moved ahead before implementation starts. The warning is stronger when remote-only commits touch files referenced in the approved plan, helping users avoid stale-base work and late merge surprises.

### Bug Fixes

- **Fix aitask bin python symlink masks venv packages** (t706): Replaced framework Python symlinks with wrapper scripts so `ait board` and other Python tools consistently run inside the aitasks virtual environment. The update-check cache now also recovers cleanly from corrupt version data instead of printing shell arithmetic errors.
- **Fix test python resolve hardcoded bash path** (t707): Made the Python resolver test suite use the available `bash` on the host instead of assuming `/usr/bin/bash`, restoring portability on Apple Silicon macOS.
- **Fix setup starter tmux conf dev tree** (t709): `ait setup` now offers the starter tmux configuration from source-tree checkouts as well as installed framework trees, so developers running directly from a clone get the same mouse and truecolor setup prompt.
- **Fix changelog gather aborts on unresolvable task** (t712): The changelog gather command no longer aborts when a task archive is missing from local task data. It now falls back gracefully and warns when local task data appears behind `origin/aitask-data`.

### Documentation

- **macos installation subpage terminal compat** (t711): Added a macOS installation guide that explains terminal emulator compatibility for the tmux-based `ait ide` workflow. The installation and terminal setup docs now point macOS users toward truecolor-capable terminals and explain Apple Terminal limitations.

## v0.19.1

### Bug Fixes

- **Sync with origin before release and changelog** (t705): `create_new_release.sh` and the `/aitask-changelog` skill now sync with `origin/main` before pushing tags or gathering release data, so released versions and changelog entries no longer miss tasks merged on remote.

### Maintenance

- **macOS bash test suite portability audit** (t658): Two macOS-portability bugs fixed in the test suite — BSD `sed -i` calls in `test_archive_no_overbroad_add.sh` and a `mktemp` path-canonicalization mismatch in `test_multi_session_primitives.sh`. Both tests now pass on macOS, bringing parity with Linux for portability-related failures.

## v0.19.0

### Features

- **Agent progress bar in brainstorm** (t683): The brainstorm Status tab now shows a 10-character progress bar next to each running agent, so you can see how far along an agent is.
- **Cloning aitasks-enabled repos documented** (t685): The installation docs now explain that `./ait setup` is required after cloning a repo that already uses aitasks, with the symptoms you'll see if you skip it.
- **Counter scans real tasks on fresh clones** (t686): `ait setup` now consults the data branch before initializing the task-ID counter, so a fresh clone of an established project continues numbering from the next available ID instead of restarting at 1.
- **Auto-commit `.gitignore` after setup** (t687): `ait setup` now commits the `__pycache__/` rule it adds to `.gitignore` immediately, so your working tree stays clean after a fresh setup.
- **Starter `~/.tmux.conf` in setup** (t688_3): `ait setup` now offers to drop a sensible starter `~/.tmux.conf` (true-color, 50k history, focus events, sane escape-time) so first-time tmux users get a comfortable default.
- **aitask-audit-wrappers skill — Phase 1 (skill wrappers)** (t691_1): A new `aitask-audit-wrappers` skill audits and ports skill-wrapper files across the claude/gemini/codex/opencode trees, closing wrapper drift in one command.
- **aitask-audit-wrappers — Phase 2 (helper-script whitelists)** (t691_2): The audit now also covers helper-script whitelists across all five permission touchpoints, so adding a new helper script no longer means hand-editing five separate files.

### Bug Fixes

- **Whitelist bare `ait crew` form** (t674): Code-agent permission lists now allow both `./ait crew` and bare `ait crew`, so crew agents stop prompting for permission on routine heartbeat/status calls.
- **Capture real PID for tmux-launched agents** (t675): Brainstorm/crew agents launched into tmux now record the agent's actual PID, so the Status tab no longer shows "PID dead" for an agent that is in fact running.
- **Auto-fill `created_at` in brainstorm initializer** (t676): Brainstorm initializer/explorer/synthesizer outputs missing `created_at` no longer crash with a parse error — the field is auto-filled at apply time.
- **Fix PR contributor metadata test regression** (t682): Restore silent test coverage for pull-request / contributor metadata writes that was masked by a missing test fixture dependency.
- **Fix revert-analyze test regression** (t684): Same class of silent test-fixture drift, fixed by mirroring the full `.aitask-scripts/` tree into the test sandbox.
- **Fix `Select.set_options` crash on Textual 8** (t688_1): The brainstorm agent-command screen no longer crashes when opening the tmux session/window selector on Textual ≥8.0.
- **Fix brainstorm minimap crash and section-jump overshoot** (t690): Clicking or tabbing the minimap inside the node-detail modal no longer crashes, and the section jump now lands on the correct row.
- **Warn when reclaiming a self-locked task across PCs** (t692): `ait pick` now prompts when you try to pick a task already locked by you on a different machine, rather than silently re-claiming it.
- **Copy `archive_scan.sh` into three test fixtures** (t693): Restore silent test coverage for data-branch migration, issue-import contributor, and parallel-child-create flows.
- **Fix `.gitignore` trailing slashes vs symlinks** (t699): `ait setup` now writes bare `aitasks` / `aiplans` entries so the data-branch symlinks are actually ignored and don't show as untracked after setup. Existing installs are auto-migrated.

### Improvements

- **Centralized Python resolver helper** (t695_1): A new `lib/python_resolve.sh` consolidates how scripts find a usable Python interpreter (cached lookup + version enforcement), eliminating ad-hoc probe logic.
- **Upgrade venv Python to ≥3.11 with auto-install** (t695_2): `ait setup` now auto-installs a modern Python (Homebrew on macOS, uv-managed on Linux) when system Python is too old, instead of failing with a manual-install message.
- **`~/.aitask/bin` symlink with scoped PATH** (t695_3): A sourced lib prepends `~/.aitask/bin` only inside aitasks subprocesses — no more global shell-rc edits, and aitasks Python tools resolve to the framework venv automatically.
- **Migrate Python callers to the resolver helper** (t695_4): 25 caller scripts now route through `require_ait_python` / `require_python` for unified version enforcement; ~70 lines of dead version-check code removed.
- **Robust upstream-defect reporting** (t698): The task workflow now requires all related defects in the canonical "Upstream defects identified" bullet, with a sanity-check re-read for older plans that didn't follow the contract.

### Documentation

- **aitask-audit-wrappers docs page** (t691_3): New framework-development skills subsection on the docs site, with a dedicated page for `aitask-audit-wrappers` and cross-links from `aitask-add-model`.
- **Upstream-defect follow-up workflow page** (t704): New docs page explaining the post-task upstream-defect follow-up flow, with cross-links from the workflows index and follow-up-tasks page.

### Tests

- **Dynamic skill-count expectations in setup tests** (t679): Setup tests now derive expected skill/command counts from the source dirs instead of hard-coding numbers, so adding a new skill no longer breaks them.
- **Skip codex-model-detect when codex unavailable** (t680): The test now prints `SKIP` and exits 0 when `codex` or `jq` aren't installed, instead of failing on hosts that lack the tool.
- **Refresh stale assertions** (t681): Updated `test_brainstorm_cli` and `test_verified_update_flags` after upstream behavior changes.

### Maintenance

- **Use aitask venv Python in tests** (t677): 11 tests that depend on yaml/textual/rich now invoke the framework venv Python explicitly, so they stop silently using whatever `python3` is on PATH.
- **`cp -R` test fixture pattern** (t678): Replaced hand-curated copy lists in three test fixtures with a recursive `cp -R` of `.aitask-scripts/`, eliminating a recurring drift class where new lib dependencies broke tests silently.
- **Surface textual upgrade in setup** (t688_2): `ait setup` now prints "Upgraded textual: A → B" when it bumps the venv's Textual version, so a stale-venv re-run shows visible recovery output.

## v0.18.3

### Features

- **Polling activity indicator widget** (t653_5): The brainstorm TUI now shows a small dim-cycling indicator next to the initializer banner and Status tab that flashes briefly on each poll, so you can tell the agent is alive even when nothing visible has changed.
- **Brainstorm code-agents default to interactive** (t659): All six brainstorm agent types (initializer, detailer, explorer, comparator, synthesizer, patcher) now launch in interactive (tmux pane) mode by default, so you can watch and intervene during a brainstorm session.
- **Step 8 upstream-defect follow-up offer** (t667): After completing a task, the workflow now offers to spin off a follow-up task for any upstream defects you flagged during implementation, so root-cause issues uncovered while patching aren't lost.

### Bug Fixes

- **Push terminal status from agent crews** (t653_3): Terminal status changes from agent crews (Completed/Aborted/Error) are now committed and pushed to the remote immediately, and an `Error` agent can recover back to `Running` instead of being stuck.
- **Hide `M` shortcut and rebind auto-switch in monitor** (t657): The unused `M` (toggle multi-session) shortcut is hidden from the `ait monitor` footer, and the auto-switch toggle is rebound from `a` to `A` for case-consistency with the other capital-letter modal toggles (`R`, `M`, `L`).
- **Persistent error modal on brainstorm init failure** (t660): `ait brainstorm` no longer silently exits when the initializer fails. A scrollable error modal now surfaces captured stderr/stdout with Retry, Quit, and a "Delete branch & retry" action for the common stale-crew-branch case.
- **Remove `b` scrollbar-toggle shortcut from monitor** (t661): The `b` shortcut on `ait monitor` has been removed; the vertical scrollbar is now always visible.
- **Brainstorm delete cleans up stale crew branches** (t662): `ait brainstorm delete` now correctly prunes the worktree before deleting the branch, so subsequent `ait brainstorm init` calls no longer fail with "branch already exists".
- **Always forward `--launch-mode` in brainstorm addwork** (t663): `ait brainstorm` plan import now always forwards the `--launch-mode` flag to crew workers, so agents launch in the configured mode instead of silently falling back to the default.
- **Brainstorm `n000_needs_apply` requires all four delimiters** (t670): The brainstorm TUI no longer spuriously offers to apply changes on session load; it now requires all four initializer delimiters to be present before reporting "ready to apply".
- **Improve `install.sh` "already installed" error** (t673): `install.sh` now shows an interactive overwrite prompt when run in a TTY against an existing install, and the non-TTY error message spells out all three recovery paths (`ait upgrade latest`, `bash -s -- --force`, `bash install.sh --force`).

### Improvements

- **Separate heartbeat freshness from agent terminal status** (t671): Stale heartbeats no longer mutate `_status.yaml`. The `MissedHeartbeat` status (introduced in v0.18.2) has been removed; consumers should call `get_stale_agents()` / `check_agent_alive()` to observe heartbeat freshness instead. **Migration:** clean any in-flight crews with `ait crew cleanup --crew <id>` before resuming work — values written under the prior runner will be rejected by the trimmed state machine.

### Documentation

- **Encode user-feedback rules into `CLAUDE.md`** (t665): Added 7 conventions covering pane-internal cycling (← / →), TUI-switcher selected-session semantics, single tmux session per project, companion pane auto-despawn, the context-variable pattern over template substitution engines, full install-flow testing for setup helpers, and `ait setup` vs `ait upgrade` verb conventions.
- **Make Step 8 review prompt non-skippable** (t668): The task-workflow Step 8 user-review prompt is now non-skippable — auto-mode and execution-profile overrides do not bypass it, and explicit acceptance is required every iteration.

## v0.18.2

### Features

- **Multi-session aggregate stats** (t655): The `ait stats` TUI now detects multiple aitasks sessions on your machine and shows a Session panel for cycling between them with Left/Right or click. A new `sessions` preset displays a grouped bar chart comparing today/7d/30d activity across all sessions.
- **MissedHeartbeat state for agent crews** (t652): Agent crews now distinguish between transient missed heartbeats and hard failures — agents go to MissedHeartbeat first and can recover back to Running automatically. Errored agents can also be recovered to Completed without requiring manual force overrides.

### Bug Fixes

- **Self-healing brainstorm TUI on initializer failures** (t653_1): When the initializer apply fails, the brainstorm TUI now shows a persistent banner with a `ctrl+r` retry shortcut and re-attempts the apply automatically every 30 seconds and on session reopen, instead of getting stuck.
- **Tolerant initializer YAML and retry CLI** (t653_2): The initializer apply now auto-quotes problematic scalar values (em-dashes, special characters) so brainstorm sessions don't get stuck on YAML parse errors. A new `ait brainstorm apply-initializer <id>` CLI lets you manually retry stuck sessions.
- **Cross-session monitor and minimonitor** (t656): The monitor and minimonitor TUIs now correctly resolve task data, log paths, and next-sibling launches for code agents running in foreign aitasks sessions, instead of looking them up in the wrong project.
- **`ait crew` whitelist across all code agents** (t650_1): The `./ait crew` subcommand is now properly whitelisted for Claude Code, Gemini CLI, and OpenCode (both runtime and seed configs), eliminating the per-invocation permission prompts.
- **Brainstorm template procedure references** (t650_2): Brainstorm templates now reference the heartbeat, progress, and status procedures by their explicit section name instead of pseudo-verb shorthand, so code agents reliably execute the documented procedures during brainstorm runs.

## v0.18.1

### Features

- **Manual-verification render-then-ask flow** (t639): The manual-verification skill now re-renders the full numbered checklist with state markers on every iteration and accepts batch updates (e.g. `1 pass, 3 defer`) through the Other field, so you can triage many items in one answer instead of stepping through them individually.
- **Issue-type filter view in the board TUI** (t645): A new `t` view mode in `ait board` opens a multi-select dialog to filter tasks by issue type (feature/bug/refactor/etc.). Picks persist per-project and a summary line under the view selector shows the active filter; pressing `t` again reopens the picker.
- **`ait setup` warns and requires acknowledgment when no git remote** (t648): When `origin` is missing during setup, the ID-counter and lock-branch steps now surface a one-time warning explaining that branch-tracked features won't sync, and require an explicit acknowledgment before continuing. Lock operations also now distinguish "branch missing on remote" from transient "remote unreachable" failures.

### Bug Fixes

- **`ait upgrade` now commits framework files in branch-mode setups** (t644): Upgrades on projects using a separate `aitask-data` branch were leaving framework files uncommitted because the install script's symlink handling skipped them. Upgrades now correctly commit `.aitask-scripts/`, `.claude/`, etc. on the main branch and `aitasks/metadata/` + `aireviewguides/` on the data branch.
- **Crew runner restored; TUI surfaces launch failures** (t647): Fixed a silent crash where the crew runner couldn't import its `lib/` modules. The TUI now also captures runner launch logs and verifies the process is actually alive before reporting success, so future launch failures show as an error toast instead of a silent no-op.
- **TUI switcher uses the selected session's project root** (t649): When switching between aitasks sessions and spawning a new TUI window, the switcher now passes `-c <project_root>` to tmux based on the *selected* session, so cross-session launches no longer inherit the wrong project's working directory.
- **`tests/test_crew_runner.sh` no longer hangs** (t651): The test fixture now copies the full `.aitask-scripts/` tree instead of cherry-picking files, fixing a hang caused by missing helper modules pulled in after the test was written.

## v0.18.0

### Features

- **Multi-session tmux primitives** (t634_1): Foundation for cross-session awareness across aitasks TUIs — discovery of tmux sessions rooted in aitasks projects and teleport-style pane focus helpers.
- **Multi-session `ait monitor`** (t634_2): The monitor TUI now aggregates code-agent panes across every aitasks session by default. Sessions are grouped under divider rows, and an `M` binding toggles multi-session view on and off.
- **Cross-session TUI switcher** (t634_3): The TUI switcher overlay (`j`) now lists every running aitasks session. `←` / `→` cycles between them, and `Enter` (or any shortcut key) teleports tmux to the selected session automatically.
- **Multi-session `ait minimonitor`** (t634_4): The minimonitor now aggregates agent panes across every aitasks session by default, with session divider rows and the same `M` toggle as the full monitor. The title bar gains a compact `multi: Ns · Ma N idle` summary.
- **Register `gpt-5.5` for codex and opencode** (t636): `gpt-5.5` is selectable for the codex agent directly and for the opencode agent via the OpenAI and OpenCode providers.

### Bug Fixes

- **Respect default session in agent launch dialog** (t640): The launch dialog now honors the caller's `default_tmux_window` and remembers the last-used tmux session and window **per project** instead of sharing a single global memory across all projects.
- **Rename `ait install` → `ait upgrade`; fix skills missing from release tarball** (t641): Framework updates now use `ait upgrade` (`ait install` remains as a deprecated alias). Also fixes a packaging bug where skills whose names didn't start with `aitask-` (e.g. `task-workflow`, `ait-git`, `user-file-select`) were silently excluded from release tarballs and installer copies.

### Documentation

- **Multi-session documentation polish** (t634_5): Monitor, minimonitor, and TUIs index docs now describe cross-session aggregation, the `M` toggle, session divider rows, and cross-session teleport behavior.

### Style Changes

- **Remove redundant magenta session prefix in `ait monitor`** (t643): Monitor pane rows no longer emit a magenta `[project]` tag prefix; session grouping is conveyed by the divider rows alone.

## v0.17.4

### Bug Fixes

- **Preserve project settings on `ait install`** (t637): `ait install --force` no longer clobbers user-edited seed configs. `project_config.yaml`, `codeagent_config.json`, `models_*.json`, and execution profiles are deep-merged (existing values win, new seed keys are added); `task_types.txt`, `reviewtypes.txt`, `reviewlabels.txt`, and `reviewenvironments.txt` use line-union semantics; existing review-guide `.md` files are never overwritten.
- **Auto-commit framework updates only when tracked** (t637): `ait install` now gates its safety-net commit on whether `.aitask-scripts/VERSION` is already tracked. If tracked, framework updates (adds **and** modifications) are committed with a version-stamped message (`ait: Update aitasks framework to vX.Y.Z`); if untracked, the installer never touches git. The installer never pushes on its own.
- **Ship scoped `.gitignore` inside `.aitask-scripts/`** (t637): A framework-owned `.aitask-scripts/.gitignore` is now installed alongside the framework to keep `__pycache__/`, `*.pyc`, and `*.pyo` artifacts out of downstream project repos. The auto-commit path also opportunistically drops any previously-tracked `__pycache__` paths from the project's index.

## v0.17.3

### Bug Fixes

- **Exact tmux session targeting** (t632): Fixed a cross-project bug where tmux commands could target the wrong session when session names shared a common prefix; all session-denominated tmux calls now use exact-match targeting.
- **Task IDs start at 1** (t631): Task IDs in new projects now start at 1 instead of 10 — the initial buffer that forced fresh projects to begin at t10 has been removed.
- **`__pycache__/` added to `.gitignore` during setup** (t630): `ait setup` now automatically adds `__pycache__/` to your project's `.gitignore`, preventing Python cache directories from being committed.

### Documentation

- **Initializer brainstorm agent type** (t573_4): Added documentation for the `initializer` brainstorm agent type, covering how it's registered and the "initialize from an imported proposal" flow that triggers it.

## v0.17.2

### Features

- **Import proposal flow in brainstorm init (t573_3)**: When starting a new brainstorm session you can now pick an existing markdown proposal instead of starting blank. The init modal offers a three-way choice (Blank / Import Proposal… / Cancel); the import path opens a markdown-filtered file picker, runs an initializer agent, and applies its output to seed the session.

### Bug Fixes

- **Test scratch-repo setup (t626)**: Fixed test scaffolds that copied `task_utils.sh` without the companion `archive_utils.sh`, which caused several test suites to fail at source time. All 11 affected tests now set up scratch repos correctly.
- **`install.sh` missing seed config (t628)**: `install.sh` now installs `project_config.yaml` from the seed files when bootstrapping a new project, fixing missing-config errors on fresh installs.
- **`commit_framework_files` stopping at 20 files (t629)**: Fixed a SIGPIPE that caused framework-file commits to terminate after the 20th file — all framework files are now committed on update.

## v0.17.1

### Features

- **Initializer brainstorm agent** (t573_1): New `initializer` agent type and `apply_initializer_output()` ingestion helper that bootstrap a brainstorm session's root node from an imported markdown proposal, reformatting it into a structured node with dimension metadata.
- **`--proposal-file` flag for brainstorm init** (t573_2): `ait brainstorm init` now accepts a `--proposal-file` flag to seed a brainstorm session from an external markdown document, auto-registering the initializer agent and starting the crew runner.
- **Minimonitor companion in git TUI window** (t622): The TUI switcher now spawns a minimonitor companion pane alongside the git TUI (lazygit) window, with smart cleanup that preserves the companion when other panes are still active in the same window.

### Bug Fixes

- **`ait setup` reliability fixes** (t624): Multiple improvements to `ait setup` — installs `AGENTS.md` with the shared aitasks layer, prompts for a default tmux session name, includes more framework files in the initial commit with a more visible confirmation and captured error output, writes config files through symlinks instead of replacing inodes, and adds post-write verification so silent failures surface as actionable warnings. Also refreshes the seed `CLAUDE.md`/`GEMINI.md`/`AGENTS.md` content with Folded Task Semantics and Manual Verification sections.

## v0.17.0

### Features

- **Manual verification workflow** (t583_1, t583_2, t583_3, t583_5, t583_7): Added a full Pass/Fail/Skip/Defer manual-verification loop with a new `verifies` frontmatter field, follow-up task helpers, archival gate with automatic carry-over, and plan/implementation-time prompts for generating follow-up tasks.
- **Stats TUI** (t597_2, t597_3, t597_4): New `ait stats-tui` interactive statistics TUI (switcher shortcut `t`) with 12 panes across Overview/Labels/Agents/Velocity categories, including counters, charts, heatmaps, ranking tables, and an inline layout picker with user-only persistence.
- **More zoom levels in monitor** (t598): Added three XL zoom levels to the monitor TUI that size the agent list to fit exactly 3, 6, or 9 agents on screen.
- **Missing profile keys in settings TUI** (t611): Added five previously-missing execution-profile keys (child plan action, manual-verification follow-up mode, review modes and auto-continue, QA tier) to the settings TUI.

### Bug Fixes

- **Section viewer rendering and bindings** (t571_11): Fixed rendering glitches and broken Tab/arrow navigation in the shared section viewer, with a richer two-line row format in fullscreen mode.
- **Context-aware codebrowser footer** (t584): The codebrowser footer now reorders keybindings based on the currently focused pane.
- **Monitor shortcut in TUI switcher** (t596): The Monitor TUI is now reachable via `m` in the TUI switcher.
- **Stuck data-worktree detection** (t599): Added detection for a stuck `.aitask-data` worktree state with a new `./ait git-health` command and clear recovery hints when commits or pushes would fail.
- **Verified-rankings pane default** (t603): The stats TUI verified-rankings pane now defaults to the highest-run operation, with left/right arrow navigation to cycle through operations.
- **Carry-over task description** (t605): Fixed a bug where manual-verification carry-over task creation silently dropped the description; silent-mode stdout now reliably emits only the new task path.
- **Duplicate verification checklist heading** (t619): Fixed a bug where the manual-verification task wrapper emitted a duplicate `## Verification Checklist` heading.
- **GitHub username in website docs** (t620): Fixed incorrect GitHub username in website links across five pages so they now point to the correct `beyondeye/aitasks` repository.

### Improvements

- **Shared section viewer across TUIs** (t571_5, t571_8, t571_9, t571_10): New shared section-navigation widget library with minimap, click-to-scroll, and `V` fullscreen shortcut, integrated into the codebrowser detail/history panes, Brainstorm node-detail modal, and board task-detail screen.
- **Codebrowser footer binding order** (t586): The codebrowser footer now displays keybindings in a stable primary order with pane-specific extensions, keeping related keys adjacent.
- **Consolidated YAML-list helper** (t587): Consolidated duplicated YAML-list formatting logic into a single shared helper for more consistent task file output.
- **Stats data module split** (t597_1): Split stats data-collection logic into a dedicated module in preparation for the stats TUI, with no change to CLI behavior.
- **Centralized TUI registry** (t601): Centralized the TUI registry so the monitor correctly recognizes the stats TUI as a managed window; TUI-name config now merges over defaults.
- **Reliable manual-verification follow-up prompt** (t602): Moved the follow-up prompt to a reliable post-implementation step with richer discovery, added a new `manual_verification_followup_mode` profile key, and skipped the prompt in fast/remote profiles.
- **Verification parser skips section headers** (t604): Verification parsing now skips section-header bullets, carry-over task slugs use `_carryover`, and the verification loop gained a Stop-here pause option.
- **Unified verify/pause prompt** (t617): Merged the manual-verification pause prompt into the main Pass/Fail/Skip/Defer question with an "Other" free-text branch for intent-based abort routing.

### Documentation

- **Landing page and docs overhaul** (t585_1, t585_2, t585_3, t585_4, t585_5): Redesigned the website landing page around the "agentic IDE in your terminal" positioning, added a new 12-page Concepts section, rewrote the overview and top-level README around the shared 6-theme structure, and swept remaining legacy references.
- **Website-wide consistency sweep** (t594_1, t594_2, t594_3, t594_4, t594_5, t594_6): Swept the TUIs, Skills, Workflows, Concepts, and Commands sections for drift; documented five missing frontmatter fields and 16 missing `ait create`/`ait update` flags; reorganized Workflows into four categories; unified cross-cutting wording; and added consistent "Next" footers across the onboarding path.
- **Per-page maturity and depth labels** (t594_7): Added Hugo `maturity` and `depth` taxonomies with per-page badges across 89 docs pages so readers can see experimental/stabilizing and main/intermediate/advanced labels at a glance.
- **Brainstorm design docs update** (t571_6): Updated the brainstorm engine architecture docs to describe structured sections, the shared section viewer, and how section targeting flows through the wizard and agent prompts.
- **Manual verification workflow docs** (t583_4, t583_8): Added a new manual-verification workflow procedure to the task-workflow skill, a website workflow page, and documented the 5-touchpoint whitelisting convention for new helper scripts in CLAUDE.md.
- **README documentation map** (t595): Updated the README map to match the current website sidebar, adding Overview, Concepts, and TUI Applications entries.
- **Claude memory consolidated into CLAUDE.md** (t612): Consolidated per-memory Claude Code notes into CLAUDE.md so canonical conventions live with the project docs.

### Tests

- **Manual-verification issue type and tests** (t583_6): Registered the `manual_verification` issue type and added a test suite covering the verification follow-up helper across five scenarios.

### Maintenance

- **Remove `ait stats --plot` flag** (t597_5): Removed the deprecated `ait stats --plot` flag and interactive-chart code paths in favor of the new stats TUI, and added a Stats TUI documentation page.
- **Simplify pycache gitignore** (t621): Simplified the repo's gitignore to ignore Python `__pycache__` directories repo-wide.

## v0.16.1

### Features

- **Fuzzy file search in codebrowser** (t566): Added an in-TUI fuzzy file search box so you can quickly jump to any tracked file by partial name using recursive multi-alignment scoring.
- **Delete session from brainstorm TUI** (t568): Added a "Delete" session operation with double-confirmation modal so brainstorm sessions can be killed directly from the TUI.
- **Copy file path in codebrowser** (t570): Press `c` to copy the currently open file's relative or absolute path to the clipboard.
- **Word wrap toggle in codebrowser** (t572): Press `w` to toggle between truncate and wrap modes for long lines in the file view.
- **Minimonitor companion pane for `ait create`** (t574): Launching `ait create` from the board, codebrowser, or TUI switcher now automatically spawns a minimonitor companion pane alongside the new window.
- **`aitask-add-model` skill** (t579_2): New skill for registering AI code models and promoting them to defaults, with dry-run diffs, shared config/seed sync, and manual-review reporting.
- **Claude Opus 4.7 registered and promoted to default** (t579_3): Added both `opus4_7` and `opus4_7_1m` (1M context) variants; `opus4_7_1m` is now the default for pick, explore, and brainstorm ops.

### Bug Fixes

- **Enable brainstorm button for folded tasks** (t561): The brainstorm button in the board TUI is no longer disabled for folded tasks (only for Done/read-only/locked ones).
- **Fix `n` shortcut in codebrowser with no file selected** (t567): `n` now works with no file selected, defaults to the full file range, and opens the new window in the current tmux window.
- **Fix stale tmux window index in codebrowser** (t575): The codebrowser re-detects its tmux window index at action time, so `ait create` companion spawns always target the correct window.
- **Sync monitor preview after refresh** (t576): The monitor's content preview now updates correctly after focus is restored during auto-refresh.
- **Fix minimonitor auto-selection on window switch** (t577): The minimonitor now re-selects its own window's agent whenever the pane regains focus.
- **File tree refresh in codebrowser** (t580): Press `R` to refresh the codebrowser file tree against the current tracked-file set, picking up newly created or deleted files.

### Improvements

- **Section parser for brainstorm plans** (t571_1): New parser and validator for structured section markers in brainstorm proposal/plan files.
- **Structured section markers in brainstorm templates** (t571_2): Brainstorm agents now emit and consume structured section markers so downstream operations can target individual sections.
- **Section-aware brainstorm operations** (t571_3): `target_sections` parameter threaded through explore/compare/detail/patch operations for focused refinement.
- **Section selection in brainstorm TUI wizard** (t571_4): New wizard step lets you pick which sections of a proposal or plan to explore, compare, detail, or patch — enabling focused refinement of individual parts of a design.
- **Shared section-format reference for crew templates** (t578): Crew templates now support include directives, with the section-format reference extracted to a single shared partial reused by all brainstorm agents.
- **Add-model skill design audit** (t579_1): Catalogued every model reference in the repo and designed the `aitask-add-model` skill API.
- **Externalized brainstorm agent defaults** (t579_5): Brainstorm agent defaults now come from `codeagent_config.json` — model swaps only touch one file.

### Documentation

- **Document the aitask-from-file workflow** (t565): New "Create Tasks from Code" workflow page covering the `file_references` field, the codebrowser `n` flow, auto-merge safety layers, and reverse navigation from the board's File Refs row.
- **Update tests and docs for Opus 4.7 default** (t579_4): Updated all tests, aidocs, and user-facing documentation to reflect `opus4_7_1m` as the new default Claude Code model.

### Maintenance

- **Migrate persistent guidance from auto-memory to CLAUDE.md** (t582): Consolidated 13 durable team conventions and project facts from auto-memory into the project `CLAUDE.md` for reliable in-context guidance.

## v0.16.0

### Features

- **Interactive agent launch mode** (t461_1–t461_9): Agentcrew agents can now run in `interactive` mode (spawned in a tmux window you can attach to) alongside the existing `headless` mode. Brainstorm wizard gains a launch-mode toggle on the confirm screen, the Status tab shows an `e` shortcut to edit an agent's mode, per-agent-type defaults are configurable in the Settings TUI, and a new `ait crew setmode` CLI flips a Waiting agent between modes. Also introduces two new `openshell_headless` / `openshell_interactive` modes (launch semantics tracked as follow-up).
- **File references frontmatter field** (t540_1–t540_8): Tasks can now carry a `file_references` list pointing at specific files (and optional line ranges like `foo.py:10-20^30-40`). Codebrowser gains an `n` keybinding to create a task from the current selection or cursor line, an opened-file history pane, and a focus mechanism for jumping to specific ranges. The board TaskDetail modal shows a File Refs row that launches the codebrowser on press. Creating a task with `--file-ref` can auto-merge related pending tasks that touch the same file, and folds union file references across merged tasks.
- **Plan verification tracking** (t547_1–t547_3, t550): Plans now carry a `plan_verified` list recording which agents verified them against the current codebase. Profile keys `plan_verification_required` and `plan_verification_stale_after_hours` (exposed as int fields in the Settings TUI) let picks auto-skip verification when a plan has been validated recently by another agent.
- **ANSI log viewer** (t461_6): New `ait crew logview` TUI renders agent log files with ANSI color support, live tailing, search, and raw-mode toggle. Launchable via `L` from the brainstorm Status tab and monitor.
- **Task restart from monitor** (t556): Press `R` on an idle agent pane in `ait monitor` to kill the window and re-launch the task in a fresh agent.
- **Opened-file history in codebrowser** (t541): New left-sidebar recent-files list (capped at 15) persists across sessions. Three-way focus cycling between recent list, file tree, and code viewer.
- **Jump from minimonitor to full monitor** (t534): Press `m` in minimonitor to open `ait monitor` with the companion agent pane pre-focused.
- **Cascade archive/delete for parent tasks** (t531): Archiving or deleting a parent task from the board now cascades to its children with a transparent confirm dialog listing each affected file and its fate.
- **Use labels from previous task** (t540_6): Interactive task creation offers a `>> Use labels from previous task` menu entry that seeds the picker with your last selection, persisted per-user in `userconfig.yaml`.
- **Brainstorm TUI task context** (t537): The brainstorm TUI title bar now shows the owning task ID and name.
- **Refresh codebrowser history** (t552): Press `r` in the codebrowser history screen to reload archived task data with a progress modal and completion toast.
- **Plan externalize --force flag** (t542): The plan-externalize helper gains `--force` to overwrite an existing external plan file, used proactively at Step 6 while Step 8 remains idempotent.
- **Child task border style** (t554): Child task cards on the board use a dashed border (parents stay solid) for at-a-glance hierarchy visibility.

### Bug Fixes

- **Claude Code plan externalization** (t440): Claude's internal plan file is now externalized to `aiplans/` before archival via a shared `aitask_plan_externalize.sh` helper, preventing plan loss when Claude forgets.
- **Monitor preview per-pane scroll** (t532, t548, t553): Scroll position is now preserved per-pane when switching focus in `ait monitor`, anchored by top-line text so it survives content refresh. Preview freezes with a `PAUSED` badge when you scroll away from the tail, and a `t` key re-engages tail-follow. An async tmux refresh (t544) and an in-place fast rebuild path (t545) eliminate freezes and arrow-key loss during refresh ticks.
- **Narrow git add in archive script** (t533): `aitask_archive.sh` no longer stages unrelated sibling task/plan changes during archival — each file is added by explicit path.
- **Agentcrew import error from any cwd** (t536, t539): `ait crew status`, `dashboard`, and `report` now resolve imports correctly regardless of working directory; all four agentcrew scripts share a single package-style import pattern.
- **Codebrowser tab focus cycling** (t549): Fixed focus loops between sidebar, file tree, code viewer, and detail pane.
- **Fast profile stops after plan approval** (t555): The `fast` execution profile now defaults to `post_plan_action: ask` so you can approve or abort a plan before implementation starts.
- **Disable runner buttons after press** (t447_5): Brainstorm Status tab Start/Stop runner buttons are immediately disabled on press to prevent double-clicks.
- **Brainstorm launch-mode layout** (t546): Settings TUI indents the per-agent-type launch-mode rows and adds specific labels so they visually nest under the parent setting.
- **Draft finalize test harness** (t543): Fixed `test_draft_finalize.sh` regression caused by missing helper lib copies.
- **Script whitelists** (t538, t551): Added `aitask_fold_*`, `aitask_plan_externalize.sh`, and `aitask_plan_verified.sh` to Claude, OpenCode, and Gemini CLI whitelists.

### Improvements

- **Centralized launch mode vocabulary** (t461_8): Single source of truth in `lib/launch_modes.py` + `lib/launch_modes_sh.sh` so adding a new launch mode requires touching one file.
- **Minimonitor lifecycle on agent kill/restart** (t557): Introduced `kill_agent_pane_smart` so killing, restarting, or moving to a sibling agent correctly tears down the agent window (and its minimonitor companion) vs just the pane, depending on sibling count.

### Maintenance

- **Unify agentcrew package imports** (t539): All four agentcrew scripts use `from agentcrew.<module> import ...` with consistent sys.path setup.

## v0.15.1

### Features

- **Monitor preview scrollback and zoom** (t529): The monitor TUI preview now supports mouse-wheel scrolling through 200 lines of scrollback, an XL zoom preset that fills the terminal, and a `b` toggle for the scrollbar. Tail-follow keeps the view pinned to the latest output unless you scroll up.

### Bug Fixes

- **Fix shim active guard leak** (t530): The global `ait` shim no longer leaks `_AIT_SHIM_ACTIVE` into the project-local `ait` it execs, fixing spurious shim-loop errors when chaining commands like `ait ide`. Existing users should re-run `ait setup` to regenerate their installed shim.

### Documentation

- **TUI switcher docs and footer label** (t519_6): New "Available TUIs" overview page lists all built-in TUIs, and board/codebrowser/settings how-to pages now document the `j` TUI switcher. The monitor footer label is renamed from "Jump TUI" to "TUI switcher" for clarity.

## v0.15.0

### Features

- **Monitor TUI** (t475_1–t475_4, t477, t485, t486, t487, t490–t492, t501, t504, t505, t516, t518): New `ait monitor` command opens a full-screen dashboard listing tmux code-agent panes with a live content preview. Supports zone-based navigation, direct keystroke forwarding (Tab/Enter), kill-agent via `k`, inline task titles and a task detail dialog, preview size cycling, auto-switch to agents needing attention, and a live task name in the preview footer.
- **Minimonitor TUI** (t496_1–t496_3, t511, t524, t526): New compact `ait minimonitor` companion pane auto-spawns alongside agent windows. Shows a narrow agent list with Tab to focus the sibling agent pane and Enter to send Enter to it.
- **TUI switcher** (t475_2, t475_4, t479, t495, t510, t514): Reusable `j` keybinding opens a TUI switcher overlay across board, monitor, minimonitor, codebrowser, settings, and brainstorm. Includes inline shortcut hints, wrap-around navigation, dynamic brainstorm session discovery, and prioritized ordering.
- **`ait ide` launcher** (t519_1): New `ait ide` subcommand starts a tmux session (or attaches to an existing one) and opens an `ait monitor` window in a single step.
- **Explore operation and shortcut** (t480_1, t480_2): New `explore` codeagent operation, launchable via `x` in the TUI switcher to spin up an exploration agent window.
- **Git TUI integration** (t507_1–t507_4): Configure lazygit, gitui, or tig as a first-class TUI. Auto-detected during `ait setup` (with lazygit install prompt), selectable in the Settings TUI, and launchable via `g` from the switcher.
- **Brainstorm from board** (t497, t509): Launch brainstorm sessions directly from the board TUI with automatic tmux window dedup and a lock guard.
- **Rename task from board** (t500, t503): New `N` keybinding in the board TUI opens a modal to rename tasks with git commit and sync; disabled for locked tasks.
- **Per-run agent/model override** (t521_2, t521_3): The launch dialog gains `(A)gent` and `(U)se last` buttons so you can pick a different agent/model per run, wired through board, codebrowser, history, and monitor launch flows.
- **Pick next sibling from monitor** (t506, t525): Press `n` in monitor to pick the next ready sibling or child task. Works for both parent and child tasks and auto-kills the current agent pane when moving on.
- **Better folding support** (t520): Skills and scripts now support ad-hoc folding and folding of child tasks into unrelated parents.

### Bug Fixes

- **Fix tmux pick arg loss** (t478): Dry-run output now preserves task arguments via `printf '%q'` quoting.
- **Fix tmux session target ambiguity** (t483): Launching tmux windows now disambiguates session vs window targets correctly.
- **Fix board pick dialog** (t493): Arrow keys work in the Select dropdown, window targets are valid, tmux errors are surfaced, the dialog defaults to "New window", and the board auto-switches to the target window after split.
- **Fix child task rename path** (t502): `aitask update` now correctly handles child task file paths during rename.
- **Fix tmux detection in board** (t512): Board now correctly pre-selects the tmux tab when running inside a tmux session.
- **Fix tmux settings save** (t515): Saving tmux settings no longer wipes unrelated keys like `git_tui` or the `monitor` sub-dict.
- **Fix `tar_match` unbound variable** (t527): `task_utils.sh` no longer crashes under `set -u` when archive lookups return empty.
- **Monitor TUI fixes** (t482, t488, t492, t501, t504, t508): Arrow keys in modal dialogs, crash guards during widget rebuild, footer hides when preview is focused, panel vs pane terminology disambiguated, stable panel border, and delayed preview refresh after sending Enter.
- **Minimonitor fixes** (t513, t517, t523): No more auto-switch on arrow navigation, correct window index after tmux window moves, and stable agent selection across refreshes.
- **TUI switcher visual fixes** (t484): Higher-contrast `bright_green` for selected items.

### Improvements

- **Extract monitor shared widgets** (t496_1): Shared monitor components moved to `monitor_shared.py` for reuse by the minimonitor.
- **Extract agent model picker** (t521_1): `AgentModelPickerScreen` extracted to `lib/agent_model_picker.py` so other TUIs can reuse it.

### Documentation

- **Terminal setup rewrite** (t519_2): Terminal setup page now focuses on the `ait ide` workflow, clarifies terminal emulator vs multiplexer, and calls out the shared-session gotcha.
- **Getting started + tmux-ide workflow** (t519_3): Getting-started guide uses `ait ide` as the primary entry point, and a new `workflows/tmux-ide` page walks through a daily session end-to-end.
- **Monitor TUI docs** (t519_4): New `tuis/monitor/` section with overview, how-to, and reference pages.
- **Minimonitor TUI docs** (t519_5): New `tuis/minimonitor/` section with overview and how-to pages.

### Maintenance

- **Fold helper scripts** (t481, t522_1, t522_2, t528): New `aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh` scripts with shared `read_yaml_field` helper; Claude Code fold callers migrated to invoke them directly. Monitor session bar now includes an inline Tab hint. Added `aitask-contribution-review` wrappers for alt-agent frontends.

## v0.14.0

### Features

- **Completed tasks history browser** (t448_1–t448_5, t455, t458, t460): New history screen in the codebrowser TUI (`h` to open) for browsing archived tasks with a searchable list, detail view with plan toggling, label filtering, sibling navigation, left/right arrow cycling, and file navigation back to source code.
- **Process monitoring and hard kill** (t462_1–t462_4): View running agent processes and resource usage in both dashboard (`o` key) and brainstorm (Status tab) TUIs. Pause, kill, or hard-kill unresponsive agents directly from the UI.
- **Unified agent launch dialog with tmux support** (t468_1–t468_5): All agent launch actions (pick, create, explain, QA) now use a shared dialog with Direct and tmux execution tabs. Configure defaults in the new Tmux settings tab.
- **Runner control in brainstorm TUI** (t447_2): View runner status and start/stop the crew runner from the brainstorm Status tab with color-coded indicators.
- **Crew worktree auto-push** (t447_3): Crew worktree changes are automatically pushed after adding work, enabling cross-machine collaboration.
- **Reset errored agents in brainstorm** (t459): Press `w` to reset agents stuck in Error state back to Waiting from the brainstorm Status tab.
- **Brainstorm keyboard navigation** (t464, t466): Letter-key tab shortcuts (d/g/c/a/s), improved wizard navigation, tab-bar focus cycling, and consistent arrow key navigation throughout.
- **QA agent integration** (t465_1–t465_3): Added `qa` as a codeagent operation. Press `a` in the history screen to launch a QA agent, or `H` in the codebrowser to jump to the history entry for the task at the current line.
- **Prompt file passing in agentcrew** (t453): Agent prompts are now passed via temporary files with a "Your Files" section mapping shorthand names to file paths.
- **Archive migration command** (t470_6): New `ait migrate-archives` command converts existing tar.gz archives to the faster tar.zst format.

### Bug Fixes

- **Fix crew runner startup** (t447_4): Fixed `ModuleNotFoundError` preventing the crew runner from starting.
- **Fix plan retrieval from tar archives** (t448_7): Plans inside tar archives now display correctly in the history view.
- **Fix agent stale detection on launch** (t451): Agents write a heartbeat immediately on launch, preventing false stale warnings during startup.
- **Reset errored agents on runner restart** (t452): Agents in Error state are automatically reset to Waiting when the runner restarts, with manual reset via `w` in the dashboard.
- **Fix history screen focus issues** (t463): Fixed focus loss after back navigation, sibling selection, and child task navigation.
- **Fix archived child task queries** (t467): Archived task queries now correctly resolve child task IDs.
- **Fix board expand/collapse** (t476): Fixed children not expanding or collapsing after initial board load.

### Improvements

- **Migrate archives to tar.zst** (t469–t471, t470_1–t470_4): Migrated the entire archive system from tar.gz to Zstandard compression for faster performance. All bash and Python utilities updated with full backward compatibility for existing tar.gz archives.
- **Extract shared modules** (t447_1, t468_1–t468_2): Runner control and agent launch functionality extracted into reusable shared modules used across dashboard, brainstorm, and codebrowser TUIs.

### Documentation

- **History view documentation** (t448_6): Comprehensive docs for the codebrowser history feature including keyboard shortcuts, how-to guides, and screenshots.
- **Settings in getting started guide** (t449): Added settings reference to the getting started documentation.
- **QA and history navigation docs** (t465_4): Updated codebrowser reference and how-to docs with QA agent and history navigation features.

### Performance

- **Per-column board refresh** (t472): Column updates refresh only the affected column instead of the entire board, eliminating visual flicker.
- **Adjacent task DOM swap** (t473): Moving tasks within a column uses efficient DOM-level widget swapping instead of full column rebuilds.

### Tests

- **Fix brainstorm tests** (t450): Updated test expectations to match post-t434 session initialization behavior.

### Maintenance

- **Add zstd dependency** (t470_5): Added zstd to `ait setup` dependency installation and website documentation.
- **Run archive migration** (t470_7): Converted all repository archive bundles from tar.gz to tar.zst format.

## v0.13.0

### Features

- **Diff Viewer TUI** (t417): Added a complete plan diff viewer with classical and structural diff modes, side-by-side and interleaved layouts, word-level intra-line highlighting, markdown syntax highlighting, unified multi-comparison view, plan merge with selective hunk acceptance, and a file browser for plan selection.
- **Brainstorm Engine** (t419) *(WIP)*: Built the brainstorm engine with a DAG operations library, session management CLI, agent type templates (explorer, comparator, synthesizer, detailer, patcher), configurable agent model settings, and TUI scaffolding with tabbed navigation.
- **Brainstorm TUI** (t423) *(WIP)*: Added a full brainstorm TUI with a dashboard showing node list and detail pane, ASCII art DAG visualization, node detail modal with metadata/proposal/plan tabs, dimension comparison matrix, an actions wizard for launching brainstorm operations, and crew/agent status monitoring.
- **QA Skill** (t428): Introduced `/aitask-qa` as a standalone skill for analyzing test coverage gaps, with tiered testing modes (quick/standard/exhaustive), a health score system, verification gate, and configurable profile keys in the settings TUI.
- **Default Execution Profiles** (t426): Added support for default profile assignment per skill in project config, `--profile` override argument on all 8 interactive and auto-select skills, and a per-skill profile picker in the settings TUI.
- **Agent Log Browsing** (t439) *(WIP)*: Added log capture for agent subprocesses, shared log utilities, and log browsing screens in both the AgentCrew Dashboard and Brainstorm TUI.
- **Loading Indicators** (t421): Added loading overlay animations for async board operations like sync, commit, lock, unlock, archive, and delete.
- **Brainstorm Delete** (t441) *(WIP)*: Added `ait brainstorm delete` subcommand for cleaning up brainstorm sessions with proper branch and worktree removal.
- **Test and Lint Commands in Settings** (t428_4): Added `test_command` and `lint_command` configuration keys to project settings with preset support in the TUI.
- **AgentCrew Operation Groups** (t419_2) *(WIP)*: Added operation groups to AgentCrew for organizing and scheduling agents by group with priority ordering.

### Bug Fixes

- **Parallel Task Creation Race Condition** (t429): Fixed race condition when creating child tasks in parallel by adding POSIX `mkdir`-based locking around the critical section.
- **Brainstorm TUI Bootstrap** (t434): Fixed brainstorm TUI failing to create a root node on init, added brief preview display, and fixed wizard click handling.
- **Task Data Push Conflicts** (t436): Added retry-rebase logic to task push/sync for handling concurrent pushes to the aitask-data branch.
- **Task Creation Batch Procedure** (t435): Refactored task creation invocation into a shared procedure to prevent agents from struggling with shell quoting in batch mode.
- **DAG Tab Crash** (t430): Fixed crash in DAG tab caused by method name conflicting with Textual internals.
- **Enter Key in Dialogs** (t425): Added Enter key confirmation to all TUI modal dialogs with text input fields.
- **SIGPIPE in Recent Archived** (t442): Fixed crash when piping sorted output under `set -euo pipefail` in the recent-archived query.
- **Crew Init Orphan Branches** (t445): Changed AgentCrew worktrees to use orphan branches, avoiding unnecessary history from the main branch.
- **Git Log in Branch Mode** (t446): Fixed bare `git log` commands in skills to use `./ait git log` when task data lives on a separate branch.
- **Diff Viewer Visual Tweaks** (t417_13): Added colored line numbers and content padding to the diff viewer display.

### Improvements

- **Numbered Archive Scheme** (t433): Replaced the single monolithic `old.tar.gz` with numbered per-range archives for faster lookups, parallel-safe archiving, and O(1) task resolution.
- **Decouple Test Followup** (t428_2): Removed the embedded Step 8b test-followup from the task workflow, replaced by the standalone `/aitask-qa` skill.
- **Avoid Duplicate Agent Query** (t432): Eliminated redundant agent/model detection by passing the resolved agent string through the task workflow context.

### Documentation

- **Brainstorm Engine Architecture** (t419_1) *(WIP)*: Published the complete architecture specification for the brainstorm engine covering data formats, templates, context assembly, and orchestration flow.
- **Default Profiles Documentation** (t426_6): Added documentation for default profile configuration, `--profile` override, and resolution order.
- **QA Skill Documentation** (t428_5): Added skill reference page, QA testing workflow guide, and updated settings documentation.

### Tests

- **Archive Library Tests** (t433_2): Added comprehensive tests for the v2 archive path library.
- **Archive Integration Tests** (t433_6): Added end-to-end integration tests for the v2 archive system.

### Maintenance

- **Organize aidocs** (t418): Moved documentation files into brainstorming and agentcrew subdirectories.
- **Pin Dependencies** (t420): Pinned all Python dependency versions and upgraded to Textual 8.x.
- **Remove Deprecated Step 8b** (t431): Deleted the deprecated test-followup-task procedure file.

## v0.12.2

### Maintenance

- **Review scripts for macOS compat** (t416): Added `from __future__ import annotations` to codebrowser Python files to ensure compatibility with macOS system Python.

## v0.12.1

### Features

- **Plan visualization in board** (t415): The TUI board detail screen now supports toggling between task content and the associated implementation plan, with a visual border color indicator and context-aware editing.

### Bug Fixes

- **Simplified satisfaction feedback procedure** (t414_1): Agent and CLI ID can now be passed directly as flags to the verified update script, replacing the error-prone 3-file chain that agents frequently failed to follow in context-heavy conversations.

## v0.12.0

### Features

- **AgentCrew data model and initialization** (t386_1): Added `ait crew init` and `ait crew addwork` commands to create and populate multi-agent crew sessions with task decomposition, dependency tracking, and worktree management.
- **AgentCrew status and heartbeat system** (t386_2): Added `ait crew status` and `ait crew command` for monitoring agent health, tracking heartbeats, and sending commands to running agents.
- **AgentCrew runner orchestrator** (t386_3): Added `ait crew runner` to automatically launch, monitor, and manage agents through their lifecycle with DAG-aware scheduling, configurable concurrency limits, and graceful shutdown.
- **AgentCrew reporting and cleanup** (t386_4): Added `ait crew report` with summary/detail/output views and `ait crew cleanup` for tearing down completed crew sessions.
- **AgentCrew TUI dashboard** (t386_5): Added `ait crew dashboard` with real-time auto-refreshing crew list, agent card views sorted by dependency order, and runner management controls.
- **Task revert analysis** (t398_1): Added commit, file, and area analysis capabilities for identifying the scope and impact of task changes before reverting.
- **Task revert skill** (t398_2): Added `/aitask-revert` interactive skill for safely reverting completed task changes, supporting both complete and partial reversions with detailed impact analysis.
- **Post-revert integration** (t398_3): Enhanced the revert skill with task/plan file resolution and refined disposition templates for handling archived artifacts after revert.
- **Partial revert child mapping** (t398_6): Enhanced partial revert to support child-task-level selection for parent tasks, showing per-child area breakdowns for granular revert decisions.
- **Historical context gathering in planning** (t369_3): Added `gather_explain_context` profile key to control how many historical task explanations are gathered during the planning phase.
- **Satisfaction feedback in explore** (t390): Added satisfaction feedback prompt to the "Save for later" path in `/aitask-explore`.
- **Verified skill stats and build presets** (t393): Added verified skill statistics display and a `verify_build` preset editor with 17 common project type presets to the settings TUI.

### Bug Fixes

- **Wrong skill references in contribute** (t375): Fixed incorrect skill reference in `/aitask-contribute` summary message pointing to non-existent skills.
- **Instructions template CLI syntax** (t386_11): Fixed 6 incorrect CLI syntax examples in the AgentCrew auto-generated agent instructions template.
- **Contribution review list and dedup** (t388): Added `list-issues` and `check-imported` subcommands to `/aitask-contribution-review` for querying open issues and detecting already-imported contributions.
- **Check-imported crash** (t389): Fixed a pipefail crash in `check-imported` when no matching task files exist.
- **Find-related grep crash** (t391): Fixed a pipefail crash in `find-related` when no `#N` references exist in task files.
- **Silent mode exit code** (t392): Fixed incorrect exit code in contribution check's silent mode that could mask failures.
- **Obsolete child task management** (t400): Added unified Delete/Archive flow to the board TUI for managing obsolete child tasks, with dependency checking and superseded status tracking.
- **Agent detection encapsulation** (t401_1): Encapsulated model JSON lookup into a reusable script, replacing inline detection logic across all agent instruction files.
- **Archived task querying** (t403): Added `archived-task` subcommand and tar.gz archive unpacking support for the revert skill to access completed task data.
- **Smart test follow-up** (t406): The test follow-up question now auto-skips when tests were already created during the current task implementation.
- **Crew script permissions** (t411): Fixed missing execute permissions on crew scripts and added crew help text to `ait help`.
- **Folded task cleanup** (t413): Fixed folded task cleanup and consolidated YAML list parsing for more reliable task folding.

### Improvements

- **Deduplicated commit attribution** (t385): Removed duplicated commit format rules from the Code-Agent Attribution procedure by referencing the canonical Contributor Attribution section.
- **Modular procedures** (t395): Split the monolithic procedures file into individual procedure files for easier maintenance and cross-referencing.
- **Shared profile selection** (t402): Extracted execution profile selection into shared procedure files referenced by all skills, eliminating duplicated instructions.
- **Consolidated lock pre-check** (t405): Merged the lock pre-check logic directly into the pick workflow, reducing an extra script invocation during task claiming.
- **Reverted historical context feature** (t407): Removed the `gather_explain_context` planning feature introduced in t369_3 after it proved unnecessary.
- **Deferred profile selection in explore** (t412): Moved execution profile selection in `/aitask-explore` from the start to after task creation, so the profile is only selected when actually needed.

### Documentation

- **Contribution flow documentation** (t355_7): Added comprehensive contribution flow docs covering fingerprint metadata, overlap scoring, review skill workflow, and per-platform CI/CD setup.
- **Verified scores reference** (t365_5): Added a dedicated verified scores reference page with cross-links from 6 existing documentation pages.
- **AgentCrew architecture guide** (t386_6): Added architecture documentation covering the full AgentCrew system design, file schemas, status state machines, and a work2do operational guide.
- **Revert skill documentation** (t398_4): Added website skill reference page and workflow guide for `/aitask-revert` with comparison table and example walkthroughs.
- **Explore workflow documentation** (t404): Added `/aitask-explore` references to the idea capture and terminal setup documentation pages.
- **Contribution skills index** (t409): Added missing contribution skills (`/aitask-contribute`, `/aitask-contribution-review`) to the website skills index page.

### Maintenance

- **Revert skill whitelist registration** (t398_5): Added whitelist entries and skill wrappers for `/aitask-revert` across all supported code agents (Claude Code, Gemini CLI, Codex CLI, OpenCode).

## v0.11.0

### Features

- **Verified score updater** (t303_1): Added a score updater that records user satisfaction feedback per AI model and skill, building rolling averages over time.
- **Satisfaction feedback procedure** (t303_2): Added a reusable feedback workflow that prompts users to rate task completion quality, with profile-based control via `enableFeedbackQuestions`.
- **Feedback in task workflow skills** (t303_3): Integrated satisfaction feedback into all shared-workflow skills so every task completion can optionally collect quality ratings.
- **Model refresh feedback preservation** (t303_4): Model refresh now preserves verified feedback history and displays aggregated stats when listing models.
- **Feedback in standalone skills** (t303_5): Added satisfaction feedback prompts to standalone skills like explain, changelog, and review guide management.
- **Contribution fingerprint metadata** (t355_1): Contribution issues now include fingerprint metadata (affected areas, file paths, change type) for smarter overlap detection.
- **Fingerprint metadata parser** (t355_2): Extended the contribution metadata parser to read fingerprint fields for downstream overlap analysis.
- **Contribution overlap checking** (t355_3): Added automated overlap checking that detects when incoming contributions duplicate existing tasks, with GitHub, GitLab, and Bitbucket support.
- **Contribution CI/CD templates** (t355_4): Added CI/CD templates for GitHub Actions, GitLab CI, and Bitbucket Pipelines to automatically check contributions on new issues.
- **Merge issues in import** (t355_5): Added `--merge-issues` to combine multiple related contribution issues into a single task with cross-references and contributor attribution.
- **Contribution review skill** (t355_6): Added a new skill for reviewing incoming contributions, discovering related issues, and importing them as grouped or single tasks.
- **Time-windowed verified stats** (t365_2): Verified stats now track performance across time windows (all-time, monthly, weekly) with automatic migration from the previous format.
- **Verified score discoverability in settings** (t365_3): The settings TUI now shows verified scores per model with time-window breakdowns, cross-provider aggregation, and a top-verified model picker.
- **Verified rankings and plots in stats** (t365_4): Added verified model rankings and bar chart visualizations to `ait stats` output.
- **Pick command dialog in board** (t367): Added a pick command dialog to the board TUI, making it easy to launch task picks from terminal multiplexers.
- **Task detail keyboard shortcuts** (t368): Added keyboard shortcuts for all buttons in the board's task detail dialog.
- **Explain format context formatter** (t369_1): Added a Python formatter for historical task context used by the explain feature.
- **Explain context orchestrator** (t369_2): Added a shell orchestrator for gathering and caching historical context for file explanations.
- **Optional test follow-up tasks** (t372): Added an optional post-implementation step to automatically create follow-up testing tasks, controlled via execution profiles.
- **Task overlap detection in contribution review** (t376_2): Added task overlap detection to contribution review and extracted shared fold procedures for consistent merge behavior across skills.
- **Update existing task from contributions** (t376_3): Contribution review can now update existing tasks with new contribution content instead of always creating new tasks.
- **CI workflow Node.js fix** (t387): Upgraded CI workflow actions to fix Node.js 20 deprecation warnings and added missing `jq` dependency.

### Bug Fixes

- **Gemini CLI allowlist setup** (t361): Fixed Gemini CLI policy setup with proper per-skill activation entries and a consent-based global allowlist installation flow.
- **Skip reviewguide in setup** (t364): Added a skip option when selecting review guides during `ait setup`.
- **OpenCode provider mapping** (t365_1): Fixed OpenCode model attribution to use correct provider-aware naming instead of legacy aliases.
- **Verified stats display** (t366): Fixed verified stats not appearing in settings by correcting the internal operation key mismatch.
- **Pick for OpenCode/Codex** (t371): Fixed task pick command generation for OpenCode and Codex CLI agents.
- **Unsafe die patterns** (t378): Fixed 23 unsafe `cmd || die` patterns across 8 scripts that could cause silent exits under `set -e`.
- **Double commenting on contributions** (t381): Fixed contribution check workflow firing twice on issue creation by switching to label-only event triggers.
- **Duplicate overlap comment parsing** (t382): Fixed overlap comment parsing to correctly handle duplicate overlap comments by using the last one.
- **Missing feedback in child decomposition** (t383): Fixed satisfaction feedback being skipped when tasks are decomposed into child tasks during pick.

### Improvements

- **Rename aiexplains directory** (t370): Renamed `aiexplains/` to `.aitask-explain/` for consistency with the `.aitask-*` naming convention.
- **Extract related task discovery** (t376_1): Extracted related task discovery into a shared reusable procedure for explore, fold, and contribution review skills.

### Maintenance

- **macOS compatibility review** (t351): Fixed macOS compatibility issues in awk multiline handling, Python type syntax, and updated stale test assertions across all scripts.

## v0.10.0

### Features

- **Upstream contribution workflow** (t321_1, t321_2, t321_4, t321_6): Added `/aitask-contribute` command to open structured issues against upstream repositories directly from local changes, with multi-platform support for GitHub, GitLab, and Bitbucket. Issue imports now parse contributor metadata from contribution issues.
- **Agent commit coauthor support** (t339_1, t339_2, t339_3, t339_4, t339_6): Commit messages now include accurate code-agent and model attribution for all supported agents (Claude Code, Codex CLI, Gemini CLI, OpenCode). The coauthor domain is configurable via `project_config.yaml`.
- **Project config editing in settings** (t339_7): Added regression tests for the Settings TUI Project Config tab's YAML helpers.
- **Code area maps and project contributions** (t341_1, t341_2, t341_3): Added `code_areas.yaml` for defining project structure, automatic codemap generation, and dual-mode contribute workflow supporting both framework and project-level contributions with hierarchical area drill-down.
- **Code agent and model statistics** (t353): `ait stats` now shows breakdowns by code agent and LLM model, including weekly trends and plot histograms.
- **AI agent whitelist updates** (t362): Updated agent configuration whitelists to include newly added scripts.

### Bug Fixes

- **Codex CLI model resolution** (t340): Fixed model identification for Codex CLI agents by adding config-file fallback when environment detection fails.
- **Seed execution profiles out of sync** (t342): Synced seed execution profiles (`fast.yaml`, `remote.yaml`) with the canonical metadata versions.
- **Consolidated duplicate create skills** (t347): Merged `aitask-create` and `aitask-create2` into a single unified skill with full batch mode support.
- **Child task sorting in board** (t350): Fixed child tasks sorting lexicographically instead of numerically in the board TUI.
- **Contribution label failure** (t354): Contributions no longer fail when the target repository lacks the expected issue label; the script retries without the label automatically.
- **OpenCode planning detail** (t357_1): Enhanced OpenCode plan mode requirements to produce more detailed implementation plans with explicit file paths and code snippets.
- **Agent confusion with symlinked directories** (t358): Added repo-structure documentation to prevent code agents from misinterpreting `aitasks/` and `aiplans/` symlinks.
- **Stats plot title and spacing** (t359): Fixed chart titles and sizing in `ait stats --plot` output with terminal-aware rendering and visual spacing between charts.
- **Workflow skipping review after child creation** (t360): Fixed the task workflow incorrectly proceeding to review/archive steps after creating child tasks instead of stopping.

### Documentation

- **Multi-agent documentation review** (t320): Updated 26 documentation pages to remove Claude-only narration and align with the multi-agent architecture.
- **Contribution workflow documentation** (t321_3): Added skill docs, workflow guide covering all three contribution paths, and README updates.
- **Documentation site links** (t336): Updated all README links from GitHub Pages to the new `aitasks.io` domain.
- **Agent commit attribution docs** (t339_5): Added dedicated commit attribution documentation explaining how agent coauthors work across all supported agents.
- **Gemini CLI and Codex CLI known issues** (t356): Documented known limitations for Gemini CLI and Codex CLI agents on the installation known-issues page.
- **OpenCode plan mode caveats** (t357_2): Added OpenCode-specific known issues including plan mode locking skip and shallow plan workarounds.
- **Contribute docs for project repos** (t363): Updated contribution documentation to reflect support for both framework and project-level contributions.

### Performance

- **Python codemap scanner** (t348): Rewrote the codemap scanning from bash to Python for better performance, with new filtering options and framework directory exclusion.

## v0.9.0

### Features

- **Gemini CLI skill wrappers** (t131_1): Added 17 skill wrappers for Gemini CLI, enabling the full aitasks skill set to work natively with Gemini CLI.
- **Gemini CLI command wrappers** (t131_2): Added 17 command wrappers for Gemini CLI, providing slash-command access to all aitasks workflows.
- **Gemini CLI setup/install/release pipeline** (t131_3): Integrated Gemini CLI into the setup, install, and release pipelines so new projects get Gemini CLI support out of the box.
- **OpenCode skill wrappers** (t319_1): Added 17 skill wrappers for OpenCode, bringing full aitasks skill coverage to the OpenCode agent.
- **OpenCode setup/install pipeline** (t319_2): Integrated OpenCode into the setup and install pipelines with automated config merging and seed file deployment.
- **OpenCode model discovery** (t319_4): Added `ait opencode-models` command to discover and catalog available OpenCode models with provider-prefixed identifiers.
- **Model status field support** (t319_5): Models can now be marked as active or unavailable, with unavailable models dimmed in the TUI and excluded from selection.
- **OpenCode command wrappers** (t323): Added 17 command wrappers and plan-mode prerequisites for OpenCode, completing slash-command support.
- **Gemini CLI TOML migration and permission policies** (t335): Migrated Gemini CLI commands from Markdown to TOML format and added automatic permission policy merging during setup.

### Bug Fixes

- **Child task checkpoint and agent attribution** (t322): Fixed child tasks skipping the planning checkpoint and agent attribution incorrectly defaulting to "claude" instead of the actual code agent.
- **Test data branch setup failures** (t328): Fixed missing seed file copy in `setup_data_branch()` that caused 7 test failures.
- **Parent task locked after child creation** (t330): Parent tasks are now properly unlocked when child tasks are created, preventing the parent from remaining stuck in a locked state.
- **Skill definition conflicts** (t332): Consolidated Gemini CLI and Codex CLI skill wrappers into a single unified set under `.agents/skills/`, eliminating file conflicts during setup.

### Improvements

- **Rename aiscripts to .aitask-scripts — core** (t326_1): Renamed the `aiscripts/` directory to `.aitask-scripts/` to keep framework internals hidden as a dotfile directory.
- **Rename aiscripts to .aitask-scripts — docs and configs** (t326_2): Updated all skill files, documentation, seed templates, and website content to reference the new `.aitask-scripts/` path.
- **Rename aiscripts to .aitask-scripts — tests and cleanup** (t326_3): Updated all test files, removed the backward-compatibility symlink, and fixed three functional bugs the symlink had been masking.

### Documentation

- **Gemini CLI website documentation** (t131_4): Added Gemini CLI to the installation page, updated the overview to highlight multi-agent support, and updated the about page.
- **OpenCode documentation update** (t319_3): Updated the skills overview, getting started guide, and homepage to document OpenCode's invocation syntax and wrapper layout.
- **Terminal setup workflow** (t327): Moved terminal setup and git authentication documentation into dedicated installation sub-pages for easier discovery.
- **Agent known issues** (t329): Added an installation known-issues page documenting Claude Code and Codex CLI caveats.
- **Remove OpenCode recommendation** (t333): Removed the outdated suggestion to use OpenCode as an alternative for OpenAI models from the installation docs.
- **Homepage code agent copy** (t334): Refined the homepage feature card to describe workflow-oriented agent integration rather than invocation syntax details.

### Maintenance

- **OpenCode release packaging** (t324): Extended the release pipeline to bundle OpenCode command wrappers and plan-mode prerequisite files.
- **Agent instruction seed cleanup** (t331): Trimmed Gemini CLI, Codex CLI, and OpenCode seed files to contain only agent identification, removing duplicated preamble content.

## v0.8.3

### Bug Fixes

- **Exclude Python cache from setup commits** (t309): The `ait setup` framework commit scan no longer accidentally stages `__pycache__` and `.pyc` files.
- **Fix Codex skill YAML frontmatter** (t310): Fixed invalid YAML in the `aitask-explain` skill definition that broke Codex CLI wrapper parsing.
- **Require plan mode for Codex interactive skills** (t311): Added plan mode prerequisites to 14 interactive Codex CLI skill wrappers, preventing runtime failures in non-plan contexts.
- **Add agent attribution to wrap/pickrem/pickweb** (t314): Agent attribution is now recorded for tasks completed via `aitask-wrap`, `aitask-pickrem`, and `aitask-pickweb` workflows.
- **Pre-implementation ownership guard** (t316): Task workflow and pickrem now verify task ownership (status and assigned_to) before starting implementation, preventing accidental work on tasks owned by another user.

### Performance

- **Migrate ait stats to Python** (t222): Rewrote the stats command in Python for better performance, with optional `plotext`-based chart rendering configurable via `ait setup`.

### Documentation

- **Update code agent skill docs** (t130_3): Website documentation now covers multi-agent invocation syntax, distinguishing Claude `/skill` from Codex `$skill` commands.
- **Tool extraction scripts** (t312): Added scripts for extracting Claude Code and OpenCode tool definitions for reference documentation.
- **Refresh tool references** (t313): Updated Codex and Gemini CLI tool description references in `aidocs/`.
- **Document stats plot and setup flow** (t315): Clarified `--plot` usage, missing-dependency warnings, and the setup prompt for enabling plot support.
- **Document Codex continue guidance** (t317): Added explicit continuation guidance to skill docs for Codex CLI's post-implementation flow.

## v0.8.2

### Features

- **Codex CLI skill wrappers** (t130_1): Added 17 Codex CLI skill wrappers with a shared tool mapping file and a layered instructions architecture, enabling aitask skills to work natively with OpenAI's Codex CLI using `$skill-name` syntax.
- **Codex CLI install pipeline** (t130_2): Added end-to-end install pipeline for Codex CLI support, including release packaging, `ait setup` integration, TOML config merging, and a unified marker-based instruction management system (`>>>aitasks`/`<<<aitasks`) for idempotent agent configuration across all supported CLIs.

### Improvements

- **Refactored agent setup** (t308): Extracted agent-specific setup into dedicated methods (`setup_claude_code()`, `setup_codex_cli()`, etc.) with automatic CLI detection, so each agent is only configured when its CLI is installed.

### Tests

- **macOS bash test fixes** (t307): Fixed 7 failing bash tests on macOS, including a real symlink path resolution bug in `ait setup` and stale assertions from recent behavior changes.

## v0.8.1

### Bug Fixes

- **Task creation and locking without git remote** (t305): Task creation and locking now work in repositories without a configured remote. The ID counter operates locally and automatically upgrades to remote-based coordination when a remote is later added.
- **Auto-update version comparison** (t306): Fixed the auto-update check incorrectly suggesting downgrades by replacing string comparison with proper semver ordering.

### Documentation

- **Project root requirement clarity** (t302): Improved documentation and script messaging to clearly explain that `ait setup` and the curl installer must be run from the git repository root directory.

## v0.8.0

### Features

- **No-recurse flag for extract script** (t195_11): Added a `--no-recurse` flag to the code extraction script, allowing single-directory processing without traversing subdirectories.
- **PR contributor metadata fields** (t260_1): Tasks now track pull request URL, contributor name, and contributor email in frontmatter metadata.
- **PR/contributor display in board** (t260_2): The board TUI shows PR links and contributor information for imported tasks.
- **PR import script** (t260_3): New `ait primport` command imports pull requests from GitHub, GitLab, and Bitbucket as structured aitasks.
- **PR review skill** (t260_4): Added a skill to create aitasks directly from pull request reviews.
- **PR close/archive integration** (t260_5): Closing or archiving a PR-originated task now automatically closes the associated pull request.
- **Contributor attribution** (t260_6): PR-originated task commits include contributor attribution from the original pull request author.
- **Dynamic search placeholder** (t260_8): Board search placeholder text updates dynamically based on the active view mode.
- **Code agent wrapper** (t268_1): New `ait codeagent` command provides a unified entry point for invoking any supported AI code agent.
- **Per-user config overrides** (t268_2): Added `*.local.json` support for user-specific configuration that won't be committed to git.
- **Shared config library** (t268_3): New shared config library handles layered configuration loading across all TUI applications.
- **Code agent TUI integration** (t268_5): Board and settings TUIs now use the codeagent wrapper instead of hardcoded agent commands.
- **Settings TUI** (t268_6): New `ait settings` command launches a centralized TUI for managing all configuration — profiles, board settings, models, and more.
- **Implemented-with tracking** (t268_7): Task frontmatter now records which code agent was used for implementation via the `implemented_with` field.
- **Refresh code models skill** (t268_9): New skill that researches the latest AI code agent models and updates model configuration files automatically.
- **View mode filter** (t273): Board now supports All/Git/Implementing view modes to quickly filter tasks by status.
- **Bitbucket Cloud support** (t278): Fixed and validated PR import and close workflows for Bitbucket Cloud repositories.
- **Verified model scores** (t280): The settings TUI model selector now shows verification scores for tested models.
- **User-scoped profiles and revert** (t281): Profiles tab supports user-scoped profiles and a revert button to undo unsaved changes.
- **Profile save confirmation** (t284): Added a confirmation dialog before saving profile changes to prevent accidental overwrites.
- **Mouse click for CycleField** (t286_1, t286_2): CycleField widgets in both settings and board TUIs now respond to mouse clicks for easier interaction.
- **Updated project description** (t296): README now lists all supported AI code agents in the project description.
- **Board settings revert** (t299): Added a revert button to the board settings tab in the settings TUI.

### Bug Fixes

- **Settings TUI navigation fixes** (t272): Fixed tab navigation, model picker display, and configuration layer indicators in the settings TUI.
- **Keyboard hints in settings** (t275): Fixed settings TUI navigation shortcuts and added keyboard hint bars to all tabs.
- **Agent identifier rename** (t276_1, t276_2): Renamed internal agent identifiers from `claude`/`gemini` to `claudecode`/`geminicli` for clarity across scripts, configs, skills, and docs.
- **GitLab cross-repo imports** (t277_1): Fixed `glab api` flag handling and added `--repo` override for importing PRs from other repositories.
- **Cross-repo PR operations** (t277_2): Added `--repo` support to PR close and issue update commands for cross-repo GitLab workflows.
- **Settings refresh crash** (t283): Fixed a DuplicateIds crash that occurred when refreshing the settings TUI.
- **Tab switching shortcuts** (t285): Fixed tab switching keyboard shortcuts and keyboard hint placement in the settings TUI.
- **Missing scripts in whitelist** (t294): Added 5 missing scripts to the seed setup whitelist.
- **PR import interactive mode** (t295): Fixed the draft/commit flow in interactive PR import and improved UX prompts.
- **Issue import finalization** (t298): Fixed task finalization behavior when importing issues interactively.
- **Folded task archival** (t301): Fixed handling of folded tasks during child and transitive archival operations.

### Improvements

- **Board config split** (t268_4): Split board configuration into separate project and user layers for cleaner config management.
- **Profiles tab redesign** (t279): Redesigned the Profiles tab with a selector, groups, and field descriptions for better usability.
- **Settings export/import** (t292): Hardened and finalized the settings TUI export/import functionality.
- **Remove pr-close from dispatcher** (t297): Removed the standalone `pr-close` command, consolidating functionality into the archive workflow.

### Documentation

- **PR import workflow docs** (t260_7): Documented the complete PR import workflow and related commands.
- **Code agent and settings docs** (t268_8): Added documentation for the codeagent wrapper and settings TUI.
- **Parallel task planning guide** (t288): New guide explaining the parallel task planning workflow for complex multi-step tasks.
- **Codeagent wrapper docs** (t290): Updated website documentation with codeagent wrapper references and cross-links.
- **Board filtering docs** (t291): Documented view mode filtering and PR metadata display in board documentation.
- **README license fix** (t293): Removed duplicate LICENSE reference from README.
- **Skills page reorganization** (t300): Documented the refresh-models skill and reorganized the skills documentation page.

### Performance

- **Explain generation optimization** (t195_10): Improved code browser explain generation with commit limiting, cache staleness detection, pre-caching on directory expansion, and a progress timer.

### Maintenance

- **Profile path resolution** (t282): Updated skills to resolve local profile paths from the active profile context variable.

## v0.7.1

### Features

- **Code browser TUI** (t195_1): Added a new code browser TUI application with a two-pane layout for browsing project files alongside syntax-highlighted code.
- **File tree browser** (t195_2): The code browser displays a file tree of git-tracked files, filtering out hidden files and build artifacts.
- **Syntax highlighting** (t195_3): Code viewer automatically detects file languages and renders syntax highlighting with line numbers.
- **Explain data auto-generation** (t195_4): The code browser integrates with the explain data pipeline to display task history and annotations for each line of code.
- **Task annotation overlay** (t195_5): A gutter column shows which tasks modified each line of code, with color-coded task IDs for quick visual reference.
- **Cursor navigation and selection** (t195_6): Added keyboard navigation and text selection with smart viewport scrolling in the code browser.
- **Claude Code explain integration** (t195_7): Select code ranges in the code browser and launch the explain skill directly with context about the selected code.
- **Multi-platform repo fetch library** (t214_1): Built a repository file fetching library supporting GitHub, GitLab, and Bitbucket with automatic platform detection and graceful fallbacks.
- **Board unlock resets assignment** (t248): Unlocking a task in the board now prompts to reset the task status back to "Ready" and clear the assignment.
- **Click-to-select in code browser** (t250): Added mouse support for clicking to move the cursor and click-dragging to select code ranges.
- **Task detail pane** (t251): Added a detail pane showing task and plan content for the task that annotated the current line, with automatic updates as you navigate.
- **Foolproofing task name input** (t253): When creating a task, entering a long description in the name field prompts to use it as the description instead.
- **Binary file support in code browser** (t255_2): The code browser now recognizes binary files and displays their commit history instead of attempting to show unreadable content.
- **Explain cleanup command** (t258_1): Added a cleanup command to remove old explain run directories, keeping only the newest version of each source directory's data.
- **Explain auto-naming** (t258_2): Explain runs are now automatically named based on the source directory for easier organization and cleanup.
- **Updated peripheral scripts** (t258_4): Updated related scripts and documentation to work with the new explain run naming scheme and automatic cleanup.

### Bug Fixes

- **Multi-platform reviewguide import** (t214_3): The review guide import workflow now supports repositories on GitHub, GitLab, and Bitbucket instead of only GitHub.
- **Separate git operations for code and plans** (t239): Fixed workflow to use separate git commands for code changes and plan files, preventing failed commits when task data lives on a separate branch.
- **Eliminated permission prompts for child tasks** (t246): Consolidated file queries to eliminate repeated permission prompts when Claude Code discovers child tasks.
- **Dotfiles visible in code browser** (t252): Fixed the file tree to show git-tracked dotfiles like `.claude/` while still hiding `.git/` and untracked hidden files.
- **Binary file handling in extraction** (t255_1): Fixed the explain data extraction pipeline to detect and skip binary files instead of producing corrupt output.
- **Responsive code browser layout** (t256): Made the code browser layout responsive so all columns remain visible on smaller terminal widths.
- **Simplified explain manager** (t258_3): Removed duplicate directory naming logic from the Python explain manager, now that the shell script handles it.
- **Phantom tasks in board** (t264): Fixed a bug where archived tasks would reappear as corrupted stubs in the board after being moved to the archive.

### Improvements

- **Refactored task workflow skill** (t244): Split the large task-workflow skill into multiple files for better maintainability while keeping the core workflow accessible.

### Documentation

- **Documented setup.sh design** (t214_4): Documented why certain code in setup.sh is intentionally duplicated rather than sourced, making maintenance clearer.
- **Automated latest releases on website** (t243): The website landing page now automatically shows the three latest releases, eliminating manual updates after each release.
- **Reorganized ait help output** (t245): Reorganized the `ait` command help output into logical categories (TUI, Task Management, Integration, Reporting, Tools, Infrastructure) for improved discoverability.
- **Updated task querying docs** (t254): Updated documentation to describe how to query and update existing tasks during implementation.
- **Updated explain skill docs** (t258_5): Updated all documentation to reflect automatic explain run cleanup and the new directory naming convention.
- **Code browser documentation** (t267): Added code browser TUI tutorials and keyboard reference, and reorganized the website to group both board and code browser under a new "TUIs" section.

### Performance

- **Large file viewport windowing** (t195_9): Optimized rendering for large files (2000+ lines) by displaying only a 200-line viewport window, enabling smooth navigation in very large codebases.
- **Optimized board lock refresh** (t261): Lock status now refreshes only when needed (on mount, manual refresh, or after sync) instead of on every board operation. Also added Ctrl+Up/Ctrl+Down shortcuts to move tasks to column top/bottom.
- **Column collapse/expand** (t262): Added column collapse/expand to the board so you can hide columns to reduce clutter, with keyboard shortcut and command palette support.

### Tests

- **Code viewer rendering hardening** (t195_8): Improved handling of edge cases including binary files, very long lines, empty files, and fixed mouse drag selection when scrolled.

### Maintenance

- **Replaced raw ls in skills** (t247): Replaced remaining raw `ls` commands in skills with a structured query script, preventing permission prompts and improving reliability.
- **Verified seed whitelist** (t249): Ensured all scripts referenced by skill workflows are whitelisted in the seed configuration, preventing permission prompts in new installations.

## v0.7.0

### Features

- **Configurable build verification** (t51): Build verification is now configurable via `project_config.yaml`, allowing each project to define custom build/test commands that run automatically during task implementation.
- **Wrap skill reuses Claude plans** (t207): `/aitask-wrap` now detects and reuses existing Claude Code plan files, avoiding duplicate planning when wrapping uncommitted changes.
- **macOS version checks in setup** (t208): `ait setup` now validates tool versions (bash, git, Hugo, etc.) and warns about missing or outdated dependencies on macOS.
- **Remote task execution** (t215): New `/aitask-pickrem` skill enables fully autonomous task implementation in non-interactive environments (CI, SSH, remote servers) with zero user prompts.
- **Remote sync** (t216_1, t216_2, t216_3): New `ait sync` command synchronizes task and plan files with the remote repository. The board TUI supports sync via the `S` keybinding with conflict resolution dialogs.
- **Remote data branch initialization** (t225): `/aitask-pickrem` now automatically initializes the data branch on first run, removing a manual setup step.
- **Claude Code Web workflow** (t227_1, t227_2, t227_3, t227_4, t227_5, t227_6): New `/aitask-pickweb` and `/aitask-web-merge` skills enable task implementation directly in Claude Code Web. Added task locking with board TUI lock/unlock controls and lock-aware picking. Introduced `userconfig.yaml` for per-user settings.
- **Auto-merge for sync conflicts** (t228_1, t228_2, t228_3, t228_4, t228_5): New auto-merge engine intelligently resolves YAML frontmatter conflicts in task files during sync, with field-specific merge rules. Integrated into `ait sync` and the board TUI.
- **Double-click to expand parent tasks** (t229): Double-clicking a collapsed parent task in the board now expands it to show child tasks instead of opening the detail view.
- **AI agent config file detection** (t234): Environment detection now recognizes AI agent configuration directories (`.claude/`, `.gemini/`, `.codex/`, etc.) when scanning projects.
- **Public `ait lock` command** (t238): Exposed task locking as a public CLI command with email auto-detection and bare task-ID shortcut syntax.

### Bug Fixes

- **Labels included in task commits** (t68): Task creation now correctly includes `labels.txt` changes in git commits, fixing cases where label modifications were silently dropped.
- **sed portability on macOS** (t209): Fixed 7 GNU-specific `sed` usages across 4 scripts that caused failures on macOS. Added `sed_inplace()` helper for portable in-place editing.
- **Stats command macOS compatibility** (t211): Fixed `aitask stats` on macOS by replacing 16 GNU `date -d` calls with a portable date wrapper.
- **Test suite macOS portability** (t212): Fixed test portability issues on macOS including whitespace handling and hardcoded paths.
- **Task ownership on Claude Web** (t220): Fixed task claiming on Claude Code Web with structured exit codes, `--force` flag for stale locks, and a diagnostic script.
- **Child task auto-implementation prevented** (t224): Child task creation no longer triggers automatic implementation, preventing unintended workflow execution.
- **`ait git` permission whitelist** (t226): Added `./ait git` to the default permission whitelist so it works without manual approval.
- **README redesign** (t231): Redesigned README with themed logo, badges, emoji section titles, and updated installation instructions.

### Improvements

- **Shortened remote skill name** (t219): Renamed `aitask-pickremote` to `aitask-pickrem` for consistency.
- **Task data branch support** (t221_1, t221_2, t221_3, t221_4, t221_5): Introduced `./ait git` command and `task_git()` shell helper to route task/plan file operations through a dedicated data branch, enabling parallel development workflows. Updated all scripts, the board TUI, skills, and documentation.
- **Shared YAML utilities** (t228_1): Extracted YAML frontmatter parsing from the board TUI into a shared `task_yaml.py` module for reuse by other Python tools.
- **Renamed own script** (t240): Renamed `aitask_own.sh` to `aitask_pick_own.sh` for clearer naming.
- **Optimized profile scanning** (t241): Added `aitask_scan_profiles.sh` helper to optimize how execution profiles are selected during task implementation.

### Documentation

- **Release blog and RSS feed** (t186): Added a blog section with release posts, RSS feed, and automated blog post generation to the documentation site.
- **Redesigned About page** (t187): Redesigned the About page with hero cover, origin story, project stats badges, and contributor profiles.
- **Explore skill file selection docs** (t199): Updated explore skill documentation to cover the new file selection modes.
- **Explain skill file selection docs** (t200): Added file selection documentation to the explain skill page.
- **Project root directory guidance** (t204): Added guidance across 12 skill pages about running Claude from the project root directory.
- **Development dependencies** (t210): Documented ShellCheck and Hugo as development dependencies with platform-specific install instructions.
- **macOS fully supported** (t213): Comprehensive macOS compatibility audit — fixed remaining portability issues and updated docs to mark macOS as fully supported.
- **Workflow cross-references** (t232): Added workflow cross-references to all skill documentation pages and standardized section naming.
- **Apache 2.0 license** (t233): Changed the project license from MIT to Apache License 2.0.
- **Remote execution docs** (t235): Created comprehensive documentation for the `/aitask-pickrem` skill.
- **Claude Web docs** (t236): Created documentation for `/aitask-pickweb` with comparison tables and workflow diagrams.
- **Board lock documentation** (t237): Documented the board's lock/unlock feature including pre-lock workflow and multi-agent coordination guides.
- **Board screenshot images** (t242): Added board SVG screenshots to the documentation site with click-to-zoom functionality.

### Tests

- **Task git and migration tests** (t221_6): Created test suites for the task git helper and data branch migration, verified no regressions across all test suites.
- **Auto-merge unit tests** (t228_5): Added 25 Python unit tests for the auto-merge script covering conflict parsing, merge rules, and body merging.

## v0.6.0

### Features

- **Code explanation skill** (t91): Added the `/aitask-explain` skill for generating code explanations with evolution tracking, including data extraction, processing pipeline, and run management.
- **HTML/CSS environment detection** (t178): Added automatic detection of HTML/CSS projects (including SCSS, Sass, and Less) for review guide matching.
- **File selection skill** (t189): Added a reusable `user-file-select` skill with keyword search, fuzzy name matching, and functionality search for use by other skills.
- **Board auto-refresh** (t193): Added periodic auto-refresh and a settings screen to the board TUI with configurable refresh intervals.
- **Wrap skill** (t196_1): Added the `/aitask-wrap` skill for retroactively documenting uncommitted changes as tracked tasks with implementation plans.

### Bug Fixes

- **Hugo site deployment** (t188): Fixed the documentation site not rebuilding automatically when a new release is published.
- **Internal skill visibility** (t201): Fixed the `user-file-select` skill being incorrectly listed as user-invocable.
- **File selection digit conflict** (t202): Fixed digit input conflicts in user-file-select when selecting files via AskUserQuestion.
- **Gemini CLI batch mode** (t203): Fixed the Gemini CLI tools extraction script launching interactive mode instead of batch mode.
- **Install missing directory** (t205): Fixed installation failure caused by a missing `aireviewguides` directory.
- **Install PATH on macOS** (t206): Fixed `ait` command not being found after curl-pipe installation on macOS due to missing PATH configuration.

### Improvements

- **Explain file selection** (t190): Integrated user-file-select into aitask-explain for better file discovery.
- **Explore area selection** (t191): Integrated user-file-select into aitask-explore for better codebase area selection.

### Documentation

- **Explain runs command** (t192): Added the `explain-runs` command to the ait dispatcher and website documentation.
- **Explain skill docs** (t194): Added skill reference and workflow guide for the aitask-explain skill.
- **Wrap skill docs** (t196_2): Added skill reference page and retroactive tracking workflow guide for aitask-wrap.
- **Wrap usage guide** (t196_3): Added detailed walkthroughs and usage scenarios to the retroactive tracking workflow guide.
- **CLI tool extraction** (t197): Added extraction scripts and reference documentation for Codex CLI and Gemini CLI tools.
- **Settings screen docs** (t198): Added documentation for the board auto-refresh and settings screen features.

## v0.5.0

### Features

- **Review modes infrastructure** (t129_3): Added 9 seed review guide templates and an interactive setup wizard for installing review guides into projects.
- **Code review skill** (t129_4): Added the `/aitask-review` skill for performing structured code reviews with configurable review guides, multiple target selection modes, and automatic task creation from findings.
- **GitLab support** (t136): Added full GitLab support for importing issues as tasks and updating issues with task status, with automatic platform detection from git remotes.
- **Bitbucket support** (t146): Added full Bitbucket support for importing issues as tasks and updating issues with task status.
- **Additional task types** (t162): Added `chore`, `style`, and `test` task types with full support across the CLI, board, stats, and documentation.
- **Review vocabulary files** (t163_1): Added review types and labels vocabulary files for standardized review guide classification.
- **Review guide metadata** (t163_2): Added `reviewtype` and `reviewlabels` metadata fields to all review guide files for better categorization.
- **Review guide scan script** (t163_3): Added a scan script for analyzing review guide metadata completeness and finding similar guides.
- **Review guide classify skill** (t163_4): Added the `/aitask-reviewguide-classify` skill for assigning metadata to review guide files and finding similar existing guides.
- **Review guide merge skill** (t163_5): Added the `/aitask-reviewguide-merge` skill for comparing and merging similar review guides, with both single-pair and batch modes.
- **Review guide import skill** (t169): Added the `/aitask-reviewguide-import` skill for importing external content (files, URLs, or GitHub directories) as review guides.
- **New environment detection** (t175): Added environment detection for C#, Dart, Flutter, iOS, and Swift projects.
- **Hugo documentation site** (t176_1): Created a Hugo documentation website with the Docsy theme for hosting project documentation.
- **Documentation migration** (t176_2): Migrated all existing documentation to the new Hugo website with proper cross-links and navigation.
- **Landing page** (t176_3): Added a branded landing page with feature highlights, quick install instructions, and project logo.
- **Site deployment workflow** (t176_4): Added automated Hugo site deployment to GitHub Pages on release tag pushes.
- **Implementing children visibility** (t180): Parent task cards in the board now show which child tasks are currently being implemented.

### Bug Fixes

- **Internal skill visibility** (t164): Fixed the `/aitask-create2` skill being incorrectly listed as user-invocable when it's an internal-only skill.
- **Folded task issue updates** (t165): Fixed folded tasks with linked issues not getting updated during archival.
- **Setup commit handling** (t167): Fixed framework files not being committed to git during initial project setup.

### Improvements

- **Remove aitask-zipold skill** (t151): Removed the redundant `/aitask-zipold` skill in favor of the `ait zip-old` CLI command.
- **Standardized commit messages** (t157): Standardized commit message prefixes across all scripts and skills to use the `<type>: <description> (tNN)` format.
- **Review skill helper scripts** (t158): Extracted review skill logic into reusable helper scripts for commit fetching and environment detection.
- **Review guides directory structure** (t159): Reorganized review guide files from a flat directory into a categorized tree structure with subdirectories and gitignore-based filtering.
- **Board typing modernization** (t160): Replaced deprecated `typing.List` and `typing.Dict` imports with built-in `list` and `dict` in the board TUI.
- **Remove legacy metadata format** (t168): Removed support for the legacy single-line task metadata format, keeping only YAML frontmatter.
- **Reviewmode to reviewguide rename** (t172_1, t172_2, t172_3, t172_4, t172_5): Renamed all "reviewmode" references to "reviewguide" across directories, scripts, skills, and documentation for consistent terminology.

### Documentation

- **Exploration-driven development guide** (t129_5): Added a workflow guide for exploration-driven development with use cases and a concrete walkthrough.
- **Code review walkthrough** (t129_6): Added a walkthrough and practical tips to the code review workflow guide.
- **Board TUI documentation** (t148): Added comprehensive documentation for the `ait board` TUI covering tutorials, how-to guides, and feature reference.
- **Board docs cross-references** (t161): Added cross-references to board documentation across all relevant doc files.
- **Code review skills documentation** (t171): Added documentation pages for all four code review skills and the code review workflow.
- **Review guide format reference** (t174): Added a reference page documenting the review guide file format, directory structure, and environment detection algorithms.
- **Documentation restructure** (t176_5): Restructured all documentation into Hugo subpages with a new hierarchy, navigation, and getting started guide.
- **Website fixes** (t181): Fixed documentation navigation links, added an overview page, and corrected various website content issues.
- **Task folding workflow** (t182): Added a task consolidation (folding) workflow guide and updated related documentation.
- **Multi-platform references** (t183): Updated documentation to reference GitHub, GitLab, and Bitbucket where multi-platform support exists.
- **Board prerequisites cleanup** (t184): Removed the manual prerequisites section from board documentation since dependencies are handled automatically.
- **Releases workflow** (t185): Added a releases workflow documentation page covering the full release pipeline.

### Performance

- **Post-implementation speedup** (t166): Consolidated post-implementation archival operations into a single script for faster task completion.
- **Task startup improvement** (t173): Consolidated task ownership operations into a single script for faster task startup.

### Maintenance

- **Google style guides** (t179): Added 8 Google style guide review templates for C++, C#, Dart, Go, HTML/CSS, JavaScript, and TypeScript.

## v0.4.0

### Features

- **Auto-bootstrap new projects** (t127): Running `ait setup` in a directory without aitasks now automatically bootstraps the framework, eliminating the need to manually download and run the installer.
- **Interactive codebase exploration** (t129_2): Added `/aitask-explore` skill for investigating problems, exploring code areas, scoping ideas, or reviewing documentation — with guided follow-up questions and automatic task creation.
- **Task deletion in board** (t137): Added a delete action to the board TUI with confirmation prompts, child task detection, and read-only display for completed tasks.
- **Folded task navigation in board** (t142): Folded tasks are now displayed in the board task detail view with read-only navigation to view their contents.
- **Task folding skill** (t143_1): Added `/aitask-fold` skill to identify and merge related tasks into a single task, reducing duplication and organizing work.
- **Archive fallback for task/plan resolution** (t144_2): Task and plan file lookups now search inside tar.gz archives, so references to archived tasks still resolve correctly.
- **Safety-aware archive selection** (t144_3): Rewrote the zip-old selection logic to preserve archived files that are siblings of active parent tasks or dependencies of active tasks.
- **Folded status and folded_into property** (t145): Added a `Folded` status and `folded_into` metadata field so folded tasks are clearly marked and traceable to their target task.
- **Board column customization** (t147): Board columns can now be added, edited, and deleted via a command palette (Ctrl+P) or by clicking column headers, with color selection from an 8-color palette.

### Bug Fixes

- **Missing changelog in help** (t104): Added the `changelog` command to the `ait` help text.
- **Setup file handling fixes** (t128): Fixed `ait setup` to relocate VERSION into `aiscripts/`, remove CHANGELOG.md from installs, and auto-commit framework files.
- **Duplicate task prevention in explore** (t135): The `/aitask-explore` skill now discovers related existing tasks and offers to fold them instead of creating duplicates.
- **Execution profile loss during handoff** (t141): Fixed the execution profile being lost when transitioning from task selection to implementation by adding a profile refresh step.
- **Exit trap corrupting exit codes** (t150): Fixed an EXIT trap in bash scripts that was overwriting the intended exit code, causing `create_new_release.sh` to misreport failures.

### Improvements

- **Shared workflow extraction** (t129_1): Extracted the common implementation workflow (steps 3-9) into a reusable `task-workflow` skill, reducing duplication across skills.
- **Renamed clear-old to zip-old** (t144_1): Renamed the `clear-old` command and script to `zip-old` across the entire codebase for clarity.

### Documentation

- **Windows/WSL install notes** (t106): Added inline Windows/WSL guidance and authentication cross-references to the install documentation.
- **Context monitoring docs** (t107): Documented the context monitoring workflow with a claude-hud recommendation in the workflows guide.
- **README restructure** (t133): Restructured the README from 1155 lines into a concise landing page plus 6 focused documentation files under `docs/`.
- **Windows docs corrections** (t134): Moved authentication section to README, fixed terminal recommendation order, and trimmed outdated known issues.
- **Folded tasks documentation** (t140): Documented the `folded_tasks` frontmatter field, exploration workflow, and parallel exploration patterns.
- **Fold skill documentation** (t143_2): Added complete `/aitask-fold` reference documentation to the skills guide.
- **Post-release archival step** (t149): Added a zip-old step to the release process documentation.

## v0.3.0

### Features

- **Framework updater** (t85_11): Added `ait install` command for updating aitasks to the latest or a specific version, with automatic daily update checks that notify when a newer release is available.
- **Atomic task ID counter** (t108): Task IDs are now assigned from a shared atomic counter on a separate git branch, preventing duplicate IDs when multiple PCs create tasks against the same repo. Tasks are created as local drafts first and finalized with a real ID on commit.
- **Atomic task locking** (t110): Added a lock mechanism that prevents two PCs from picking the same task simultaneously, using compare-and-swap semantics on a separate `aitask-locks` git branch.

### Bug Fixes

- **Git init in setup** (t102): `ait setup` now detects when the project directory is not a git repository and offers to initialize one with an initial commit of framework files.
- **Windows install fix** (t105): Fixed `install.sh` failing silently when piped via `curl | bash` on Windows/WSL by adding TTY detection to all interactive prompts in setup.

### Documentation

- **Typical workflows** (t100): Added a "Typical Workflows" section to README covering idea capture, task decomposition, GitHub issue workflow, parallel development, multi-tab terminal setup, and monitoring during implementation.
- **Draft workflow docs** (t109): Documented the draft/finalize task creation workflow and atomic task ID counter behavior in README.
- **Follow-up task workflow** (t111): Documented how to create follow-up tasks during or after implementation, leveraging Claude Code's full session context.
- **Task locking docs** (t125): Documented the atomic task locking mechanism in the README Development section.

## v0.2.0

### Features

- **Comprehensive README** (t85_10): Added full project documentation covering installation, command reference, Claude Code skills, platform support, and task file format.
- **Terminal compatibility detection** (t89): Added automatic detection of terminal capabilities on Windows/WSL with helpful upgrade suggestions for unsupported terminals.
- **Execution profiles** (t92): Added YAML-based execution profiles for task picking that pre-answer workflow prompts, with built-in "default" and "fast" presets.
- **Centralized task types** (t94): Added "refactor" issue type and moved all task type definitions into a single configuration file for easy customization.
- **Skills as source of truth** (t95): Release workflow now builds distributable skills from `.claude/skills/`, ensuring the repository is the single source of truth.
- **Default Claude Code permissions** (t96): New installations automatically configure Claude Code tool permissions, with interactive merge during `ait setup`.
- **Changelog generation** (t97): Added `aitask-changelog` skill to generate release notes from completed tasks and archived plans, with a shared task utilities library.
- **Board child collapse** (t101): The 'x' shortcut now works when a child card is focused in the task board, collapsing back to the parent task.

### Bug Fixes

- **Board create shortcut** (t93): Fixed the 'n' keyboard shortcut in the task board that failed to launch task creation due to an incorrect script path.
- **Missing documentation type** (t98): Added the "documentation" task type to seed and active task type definitions.

### Documentation

- **CRUD commands and skills** (t99_1): Documented `ait create`, `ait ls`, and `ait update` commands with interactive workflows and batch mode options.
- **Utility commands and skills** (t99_2): Documented `ait setup`, `ait board`, `ait stats`, and `ait clear-old` commands and related skills.
- **Integration commands and changelog skill** (t99_3): Documented `ait issue-import`, `ait issue-update`, `ait changelog` commands and the `/aitask-changelog` skill.
- **Pick skill documentation** (t99_4): Expanded `/aitask-pick` documentation with a full workflow overview and key capability descriptions.
- **Architecture documentation** (t99_5): Added architecture overview, directory layout, and library script reference to the Development section.
- **README consolidation** (t99_6): Merged all documentation snippets into a comprehensive README, growing from 314 to ~720 lines.
- **README corrections** (t103): Added table of contents, fixed section hierarchy, and updated release process documentation.
