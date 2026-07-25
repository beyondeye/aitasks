---
Task: t1210_4_board_bytrail_view.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: aitasks/t1210/t1210_5_trail_move_to_column_commands.md, aitasks/t1210/t1210_6_implementation_trail_docs.md, aitasks/t1210/t1210_7_manual_verification_implementation_trails.md
Archived Sibling Plans: aiplans/archived/p1210/p1210_1_trail_schema_library_and_validator.md, aiplans/archived/p1210/p1210_2_trail_gatherer_and_drift_helper.md, aiplans/archived/p1210/p1210_3_aitask_trail_skill.md
Base branch: main
plan_verified: []
---

# Plan: t1210_4 — Board By-Trail view

## Context

T4 of the Implementation Trails decomposition (RFC §14, `aidocs/implementation_trail_design.md`; parent t1210). T1 (schema lib), T2 (gatherer/drift helper), T3 (`/aitask-trail` skill + `trail` codeagent operation) have all landed. This task adds the dedicated **By-Trail board view**: a new `bytrail` base filter rendering one active trail's waves as columns, with trail discovery, a selection modal, classification/confidence badges, a detail modal with the full narrative projection, the RFC §9.2 state matrix (fail-closed error cards + versions fallback), contextual create/refresh launches, and a read-only drift check on view entry. Coordination gate satisfied: t1162_4 (the other board bindings/`check_action` editor) is archived at HEAD (`1596a078a`); premises re-verified against current source — all line refs below are current.

**User decisions at planning:** view-switch key = `z`, contextual trail action key = `T` (free keys verified; `m`/`M` reserved for sibling t1210_5's move commands).

## Key design decisions

1. **Reuse shipped seams; the board never re-derives trail logic.**
   - Validation/load: `trail_schema.load_trail()` (`.aitask-scripts/lib/trail_schema.py` — stdlib-only, PyPy-safe; board already has `lib/` on `sys.path`). Any `TrailValidationError` → fail-closed error card (RFC §12: no partial render).
   - Drift: `./.aitask-scripts/aitask_trail_gather.sh drift --trail art:<handle-id>` — first stdout token is the verdict (`CURRENT` / `STALE` / `ERROR:<kind>:<id>`), then `DRIFT:<code>|<task_ref or ->|<detail>` lines. The wrapper resolves `art:` handles itself and exits 0 with `ERROR:artifact_unresolved:<handle>` when the manifest/blob is broken — exactly the §9.2 error-card signal.
   - Blob/version reads: `./.aitask-scripts/aitask_artifact.sh get <handle> --out <tmp>` / `versions <handle>` (read-only verbs only).
   - Refs: `cross_repo_notation.parse_ref` for `<project>#<id>` task refs; local project name from `aitasks/metadata/project_config.yaml` `project.name` (cached; missing → banner warning, refs treated as unresolvable ghosts — never a crash).
   - Topic roots for the By-Topic launch entry point: existing `topic_key`/`task_anchor_id` imports (already in the board from `topic_semantics`).

2. **Discovery is frontmatter-driven (the manifest stores no kind), deduplicated by handle.** Active side: `task.metadata.get("artifacts")` is already populated by `task_yaml.parse_frontmatter` (no allowlist — verified) for `manager.task_datas + child_task_datas`; keep entries with `kind == "implementation_trail"`. Archived side: `archive_iter.iter_archived_frontmatter(ARCHIVED_DIR, <parse_fn>)` (verified signature: yields `(filename, metadata)` from loose files + numbered archives). **Dedup rule (fold-aware):** `_fold_transfer_artifacts` copies the handle to the fold primary but never strips the folded file's entry, so between fold and archival two active tasks legitimately list the same handle. Discovery dedupes by handle with pinned owner precedence: active non-folded > active folded (status `Folded` or `folded_into` present) > archived; final tie-break = lowest owner id. One selection-modal row per handle, showing the winning owner. Discovery + per-trail blob load (needed for title/scope/freshness/"also in" overlap) runs in a `@work(thread=True)` worker with a `LoadingOverlay`, cached on the app for the session; re-scanned when the selection modal is opened via `s`.

3. **Keys and overload precedent.**
   - `Binding("z", "view_bytrail", "By-Trail", show=False)` joins the `a/l/f/i/y` base family; `ViewSelector.BASES` gets `("view_bytrail", "By-Trail", "bytrail")` and the `on_click` membership tuple at `aitask_board.py:1188` gains `"bytrail"`.
   - `Binding("T", "trail_task", "Trail")` (shown) — contextual create/refresh launch: in normal views → the focused card's task id; in `bytopic` → the focused card's lane root (`topic_key`); hidden in `inflight`/`bytrail` and when nothing is focused (`check_action`).
   - In-view overloads (inflight `f/g/s` precedent, pinned by the RFC wireframe): `s` (`action_sync_remote`) → trail-selection modal; `r` (`action_refresh_board`) → refresh launch `/aitask-trail --refresh <handle>`; `enter` (`action_view_details`) → trail detail modal (duck-typed on the focused widget carrying `trail_entry`). Each action branches on `base_filter == "bytrail"` at the top.
   - **Keyboard-vs-timer refresh split (auto-refresh must never open a dialog):** `_auto_refresh_tick` (`:4927-4934`) calls `action_refresh_board()` directly today. Extract the current body into `_refresh_board_data()`; `action_refresh_board()` becomes: `bytrail` with an active trail → `_launch_trail_refresh()`, else → `_refresh_board_data()`. The timer tick (and any other programmatic caller — audit all `action_refresh_board()` call sites) switches to `_refresh_board_data()`, so periodic refresh stays a passive data reload in every view. Regression test: `_auto_refresh_tick` fired while in By-Trail pushes no screen (AgentCommandScreen spy) and still reloads data.
   - No `keybinding_registry` edit needed: `_DEFAULTS` auto-populates from `BINDINGS` at App init (verified); no new `_shortcuts_scope` on the modals (mirror `GateChoiceScreen` / the work-report modals), so `shortcut_scopes.py` is untouched.

4. **Banner via the existing `Header`, through a single subtitle composer.** The board composes a Textual `Header()` (`:4888`) and `sub_title` is already owned by the auto-refresh status (`_update_subtitle`, `:4936-4944`) — direct assignment would clobber it and "clear on exit" would blank it. Introduce one central writer `_refresh_subtitle()`: when `base_filter == "bytrail"` with an active trail it renders `By-Trail: "<title>"` plus the freshness suffix (`⚠ stale: <n>` / `⟳ checking freshness…` / `drift unavailable: <kind>` / nothing when current); otherwise it renders the existing auto-refresh text. `_update_subtitle` delegates to it; view switches, drift callbacks, and settings changes all go through it — leaving By-Trail automatically restores the auto-refresh subtitle. Test: `z` then `a` restores the `Auto-refresh: …` subtitle.

5. **Pure model layer for testability** (mirrors the `_build_topic_lanes` section, module scope):
   - `TRAIL_CLASSIFICATION_GLYPHS = {"hard_prerequisite": "◆", "preferred_predecessor": "▲", "core": "●", "coordination_only": "⇄", "optional": "○"}` (landed adds `✔` + strike-through) — pinned by a unit test.
   - `build_trail_lanes(doc, tasks_by_id, local_project, archived_lookup) -> list[TrailWaveLane]` — waves sorted by `ordinal`, entries by `position`; each entry resolved to `(entry, live_task | None, ghost_kind | None, landed: bool)` where `ghost_kind ∈ {"cross_repo", "archived", "missing"}` and `landed` = live status `Done` or archived-with-status-Done. `tasks_by_id` is the same parents+children universe By-Topic uses; `archived_lookup` seam = `archive_iter.find_archived_markdown_by_id` behind a small cached callable (injectable in tests).
   - `compute_trail_overlaps(trail_docs) -> dict[handle, list[(task_ref, other_title)]]` for the selection modal's "also in" sub-lines.

6. **State matrix (§9.2) mapping** — every row implemented:
   - No trails → empty-state `Static` hint ("No implementation trails found — create one with T on a task card or /aitask-trail").
   - Current → normal wave columns; sub_title `✓ current` omitted (plain title).
   - Stale → sub_title `⚠ stale: <n>`; deduplicated `DRIFT:` reasons listed in the detail modal; `r` offers refresh.
   - Owner archived → still discoverable/selectable; selection-modal row + banner note "(owner archived)".
   - Missing blob / corrupt manifest (`ERROR:artifact_unresolved` at load, or `get` failure) and schema-invalid blob (`TrailValidationError`) → error card in place of waves + read-only `versions <handle>` listing (fallback), never a partial render.
   - Member deleted/folded → ghost card; drift reasons surface it; refresh (launched skill) re-evaluates membership.
   - Multiple trails referencing a task → "also in" note in the selection modal.
   - Drift infra errors that are NOT load failures (e.g. `ERROR:unresolved_project` on a cross-repo trail) → waves still render from the valid blob; sub_title notes "drift unavailable: <kind>" (honest: freshness unknown, never a fabricated CURRENT).

7. **Read-only guarantee (negative control).** The board process only ever spawns `aitask_trail_gather.sh drift`, `aitask_artifact.sh get`, `aitask_artifact.sh versions`. Drift results update rendered state only (`sub_title`, badges, cached reasons) — never the artifact, no `freshness` rewrite (RFC §8.2 passive-observation rule). Pinned by a subprocess-spy test.

8. **Drift on entry, non-blocking, supersession-guarded.** Entering `bytrail` with an active trail renders immediately from the loaded doc with the `⟳ checking freshness…` subtitle suffix, then a `@work(thread=True)` worker runs the drift verb (single subprocess — PyPy spawn cost is fine at this rate) and updates via `app.call_from_thread`. Timeout 15s, tolerant `except (TimeoutExpired, FileNotFoundError, OSError)` → "drift unavailable". **Generation guard:** a monotonically increasing `self._trail_gen` is bumped on EVERY re-entry point — entering/leaving `bytrail`, selecting a trail, re-opening the selection modal. Discovery and drift workers capture `(gen, handle)` at spawn; every `call_from_thread` callback re-checks `gen == self._trail_gen and self.base_filter == "bytrail"` before mutating cache, subtitle, or rendered state, and discards stale results otherwise (a slow artifact read or drift check can outlive a trail switch or view exit). Negative-control test: deliver a stale-token result → no state change.

9. **Session-only view state.** `active_trail_handle`, discovery cache, loaded doc, and last drift result live on the app instance; nothing persisted (matches `base_filter` non-persistence). Entering the view with no active trail auto-opens the selection modal (via `call_after_refresh`), per §9.1.

## Files

- **Modified:** `.aitask-scripts/board/aitask_board.py` (all view code — widgets, modals, actions, model functions; new classes need no manifest registration)
- **Modified:** `tests/test_board_work_report.py` (extend the derived-views loop `("inflight", "bytopic")` → `+ "bytrail"` in `test_hidden_in_derived_views_and_without_column`)
- **New:** `tests/test_board_bytrail_view.py`
- **Checked, likely untouched:** `tests/test_board_view_filter.py`, `tests/test_board_footer_visibility.py` (extend only if they enumerate base views)

## Implementation steps

### 1. Model layer (module scope, near the topic-grouping section)

`TRAIL_CLASSIFICATION_GLYPHS`, `build_trail_lanes`, `compute_trail_overlaps`, `_local_project_name()` (cached read of `project_config.yaml`), `_trail_ref_to_local_id(ref, local_project)` (via `cross_repo_notation.parse_ref`; returns `None` for foreign projects), plus a `TrailInfo` namedtuple for discovery rows (`handle, owner_id, owner_archived, name, doc | None, load_error`).

### 2. Discovery + load helpers

`discover_trails(manager) -> list[TrailInfo]`: scan active universe metadata + `iter_archived_frontmatter`; dedupe by handle with the decision-2 owner precedence (active non-folded > active folded > archived, tie → lowest id); for each surviving entry, `get --out <tmp>` + `trail_schema.load_trail` (errors captured into `load_error`, fail-closed). `_trail_versions(handle) -> list[str]` for the fallback listing. Both called only from thread workers.

### 3. Widgets

- `TrailColumn(VerticalScroll)` — mirror `TopicColumn` (`:1433-1463`): `col_id = f"trail-w{ordinal}"`, `ColumnHeader(col_id, f"W{ordinal} · {title}", len(entries), editable=False)`, carries `self.wave` (T5 seam).
- `TrailTaskCard(TaskCard)` — mirror `InFlightTaskCard` (`:1350-1389`): overrides `compose()`; title row with strike-through (`Rich [strike]`) + `✔` when `landed`; badge line `"<glyph> <classification> · conf: <confidence>"` and an ops-hint `Label(..., markup=False)` (`[enter details] [r refresh] [s select]`); carries `self.trail_entry`.
- `TrailGhostCard(TaskCard)` — subclasses `TaskCard` (NOT a bare `Static`): the board's focus/nav/refocus seams all query `TaskCard` (`_focused_card` → `query("TaskCard:focus")`, `_get_column_cards`, `_refocus_card` by `task_data.filename`), and Textual type queries match subclasses, so ghost cards stay reachable by keyboard and restorable after refresh with zero seam changes. Carries a synthetic lightweight `task_data` (`.filename = f"trail-ghost-{ref}.md"` as stable refocus key, `.filepath = Path(filename)`, `.metadata = {}` — defensive completeness so un-enumerated accessors degrade to a no-match instead of raising); overrides `compose()` entirely (dimmed border, ref + ghost kind `cross-repo` / `archived` / `missing` + badges); carries `self.trail_entry` and `self.is_ghost = True` (T5 exclusion seam). **Primary safety is an explicit `check_action` ghost guard, not the stub:** footer evaluation calls task-only gates against the focused card (`commit_selected` → `manager.is_modified(task_data)` reads `.filepath` (`:911-913`); `open_cross_repo` → `_gather_cross_repo_refs(task_data)`; `toggle_children` parses the filename) — a near-miss stub would crash the footer refresh. An early clause in `check_action` returns `False` for every task-only action (`commit_selected`, `toggle_children`, `pick_task`, `brainstorm_task`, `open_cross_repo`, `trail_task`, `move_task_*`, `work_report`) when `getattr(self._focused_card(), "is_ghost", False)`, while `view_details` stays visible (`enter` → `TrailDetailScreen`).
- `TrailErrorCard(Static)` — error text + `versions` fallback listing.
- Empty-state `Static` hint.
- Add `TrailColumn` to `_get_visible_col_ids` (`:5532-5537`) — lateral nav breaks otherwise.

### 4. Base-filter plumbing (audit list — every site)

- `KanbanApp.__init__` comment + state (`:4758`): add `"bytrail"`; init `self.active_trail_handle = None`, `self._trail_cache = None`, `self._trail_drift = None`.
- `ViewSelector.BASES` (`:1116-1122`) + `on_click` membership (`:1188`).
- `_set_base_filter` (`:5345`): entering `bytrail` triggers the discovery/selection flow; entering AND leaving bump `_trail_gen` and route the subtitle through `_refresh_subtitle()` (the single writer restores the auto-refresh text — never clear `sub_title` directly).
- View-name mapping used by `_refresh_selector` (`:5405-5422`).
- `_compute_search_placeholder` (`:5416-5439`): bytrail placeholder + update the base-switch hint to `(a/l/f/i/y/z …)`.
- `apply_filter` (`:5113`): `bytrail` joins the `visible = None` derived-view arm.
- `refresh_board` (`:4955`): new early-return branch after `bytopic` — no active trail → empty-state or auto-select; load error → `TrailErrorCard`; else mount `TrailColumn`s from `build_trail_lanes`, set sub_title, kick the drift worker.

### 5. `check_action` audit (`:4765`) + new gates

- Add `"bytrail"` to the derived-view exclusions: `toggle_children` (`:4835`), `work_report` (`:4854`), `move_task_*` (`:4872`), `move_col_*`/`toggle_column_collapsed` (`:4878`).
- `sort_topic` stays bytopic-only (`:4883`, unchanged).
- New: `trail_task` → `False` unless (`base_filter` not in `("inflight", "bytrail")` and a card is focused).
- New: the early **ghost guard** (decision on `TrailGhostCard` above) — task-only actions return `False` when the focused card `is_ghost`; `view_details` remains.
- `view_details`/`sync_remote`/`refresh_board` stay visible; their actions branch on `bytrail` internally (inflight precedent).

### 6. Modals

- `TrailSelectScreen(ModalScreen)` — `GateChoiceScreen` pattern (`:1581-1614`): one focusable row per `TrailInfo` (title · `owner t<id>` [+ "(archived)"] · scope kind · freshness badge · last updated from `generation.generated_at`), indented `└ also references: …` overlap sub-lines, Cancel; dismisses the chosen handle.
- `TrailDetailScreen(ModalScreen)` — scrollable narrative projection (all text through `rich.markup.escape` or `markup=False`): entry focus (classification/confidence, rationale, expected_outcome, why_order_matters, caveats, evidence via `evidence_refs`) + wave context (purpose, why_now, consequence_of_delay) + trail sections (problem_statement, recommendation_summary, method_note, observations, exclusions) + current drift reasons when stale.

### 7. Launch seams (mirror `_launch_work_report`, `:5948-5982`)

`_launch_trail(op_args, window_suffix)` building: `resolve_dry_run_command(Path("."), "trail", *op_args)` → fallback `run_dialog_command(shlex.join([str(CODEAGENT_SCRIPT), "invoke", "trail", *op_args]))` → `AgentCommandScreen(..., operation="trail", operation_args=op_args, skill_name="trail", default_agent_string=resolve_agent_string(Path("."), "trail"), default_window_name=f"agent-trail-{suffix}")` (`"trail"` is already in `_FRESH_WINDOW_OPERATIONS` — verified). Callers: `action_trail_task` (`[<task_or_root_id>]`), bytrail `r` (`["--refresh", <handle>]`). Args are whitespace-free ids/handles (the codeagent guard refuses otherwise).

### 8. Drift worker + refresh split + subtitle composer

- `@work(thread=True)` `_check_trail_drift(handle, gen)`: run wrapper, parse first token + `DRIFT:` lines, `call_from_thread` → guard on `(gen, base_filter)` per decision 8, then update via `_refresh_subtitle()` + cache reasons for the detail modal. Never touches the artifact.
- Extract `_refresh_board_data()` from `action_refresh_board` and re-route `_auto_refresh_tick` (+ any other programmatic caller) to it; `action_refresh_board` keeps the keyboard-only bytrail → `_launch_trail_refresh()` branch (decision 3).
- Implement `_refresh_subtitle()` as the single `sub_title` writer and fold `_update_subtitle` into it (decision 4).

### 9. Tests

- **Extend** `tests/test_board_work_report.py` derived-views loop with `"bytrail"`.
- **New** `tests/test_board_bytrail_view.py`:
  - *Model:* `build_trail_lanes` against a deep-copied `aidocs/implementation_trail_examples/gate_framework.json` + synthetic `Task.from_text` tasks — wave ordering, position ordering, ghost classification (cross-repo / archived / missing), landed detection, glyph-map pin; `compute_trail_overlaps` with the cross-topic fixture.
  - *Render:* throwaway `CardApp` harness (`test_board_inflight_view.py:187` pattern) — `TrailTaskCard` shows glyph + confidence + strike-through when landed; ghost card shows kind; assert `.render().plain` / label text.
  - *Pilot (live repo):* press `z` → `base_filter == "bytrail"` + empty-state (live repo has no `artifacts:` frontmatter — that IS the no-trails fixture); footer gating via the `_footer_actions` helper — move/`work_report`/`toggle_children`/`sort_topic` absent in bytrail, `trail_task` present in "all" with a stubbed focused card and absent in bytrail/inflight.
  - *Ghost navigation (Pilot, synthetic lanes):* mount a trail with a ghost-only wave — arrow keys reach the ghost card (`_focused_card()` returns it), `enter` on the focused ghost opens `TrailDetailScreen`, and lateral nav crosses the ghost-only column.
  - *Focused-ghost footer regression:* with a ghost focused, evaluate `_footer_actions(app)` (drives `check_action` across all bindings) → no exception raised, every task-only action absent (`commit_selected`, `pick_task`, `brainstorm_task`, `open_cross_repo`, `toggle_children`, `trail_task`), `view_details` present.
  - *Auto-refresh regression:* in By-Trail with an active trail, fire `_auto_refresh_tick()` → no screen pushed (AgentCommandScreen spy), `_refresh_board_data` invoked; `r` keypress → launch spy fires instead.
  - *Supersession negative control:* deliver a drift/discovery result carrying a stale `_trail_gen` token (or after switching back to "all") → cache, subtitle, and rendered state unchanged.
  - *Subtitle restore:* `z` (trail subtitle) then `a` → `Auto-refresh: …` subtitle restored.
  - *Fold dedup:* discovery fixture where an active primary and an active folded task (status `Folded`, `folded_into` set) both list the same handle → exactly one row, primary owner wins; archived-owner variant → active wins.
  - *Launch construction spy* (`test_board_dialog_run_dispatch.py:206` pattern): patch `AgentCommandScreen`/`resolve_dry_run_command`, assert `operation="trail"`, `operation_args`, window name, prompt string for both the `T` action and the `r` refresh.
  - *Read-only negative control:* synthetic trail doc + monkeypatched `subprocess.run` recording every argv through a full bytrail entry + drift cycle → assert only `drift`/`get`/`versions` verbs appear and the temp trail blob bytes are unchanged.
  - Error-state render: `TrailInfo.load_error` → `TrailErrorCard` mounted, versions fallback text present.

### 10. Verification

- `python3 -m pytest tests/test_board_bytrail_view.py tests/test_board_work_report.py tests/test_board_footer_visibility.py tests/test_board_topic_view.py tests/test_board_view_filter.py tests/test_shortcut_scopes.py -v` (or unittest fallback) — green.
- `bash tests/test_shortcuts_registry_coverage.sh` — green (new actions auto-register).
- `bash tests/run_all_python_tests.sh` — no regressions.
- Live smoke: `ait board` → `z` shows the empty-state hint; `T` on a focused card opens the trail AgentCommandScreen with `/aitask-trail <id>`.
- Step 9 (post-implementation): `./ait gates run 1210_4` (risk_evaluated via orchestrator), archive via `aitask_archive.sh 1210_4`.

## Out of scope (owned by siblings)

- `m`/`M` move-to-column commands (T5, t1210_5) — seams left: `TrailColumn.wave`, `card.trail_entry`, `is_ghost`.
- Docs incl. RFC §8.2 `premise_invalidated` wording sync (T6, t1210_6).
- Live TUI/UX validation (t1210_7 manual verification).

## Risk

### Code-health risk: low
- The derived-view audit spans many enumerated sites (`check_action` ×4, `apply_filter`, placeholder, `ViewSelector` ×2, `_get_visible_col_ids`, view-name map); missing one degrades gating in an existing view · severity: low · → mitigation: TBD
- New widgets + a thread worker land in the 7.4k-line board file · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- §9.2 state-matrix breadth (error cards, ghosts, overlap, drift-unavailable) is wide for one child; a missed state renders wrong-but-plausible UI · severity: medium · → mitigation: TBD
- No live task carries `artifacts:` frontmatter yet — the discovery path is exercised only through synthetic fixtures until first real use · severity: low · → mitigation: TBD
