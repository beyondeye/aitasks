---
Task: t1794_4_extract_task_model_manager_and_workflow_phase.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_5_*.md … t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_1_*.md, p1794_2_*.md, p1794_3_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-17 09:39
---

# p1794_4 — Extract `Task`, `TaskManager` and workflow-phase derivation

Parent plan `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1–C5 PINNED). Pattern and lessons: archived `p1794_2`, `p1794_3`.

## Context

`aitask_board.py` (12,664 lines) is being split into flat-imported
`board/board_*.py` modules. This child moves the data layer — `Task`,
`TaskManager` and the pure workflow-phase derivation — so the stand-alone
`ait trails` TUI (child 6) can load tasks without `KanbanApp`. C1 forbids any
sibling importing `aitask_board`; C2 forbids a sibling resolving the task dir,
so the manager takes its paths by parameter; C3 requires every patch on a moved
caller's global to follow the symbol, proven live by a mutant.
Behaviour-preserving: the board must not change.

## Step 0 — Rebase check (pre-phase `rebase_check_before_each_child`) — DONE at verification

- HEAD `4fa524e95`; newest board commit `5d518c967` (t1794_3); `origin/main`
  has nothing newer on `board/` or `tests/`.
- **Every line anchor in the task body is stale** (children 2+3 removed ~1,440
  lines). Re-mapped at HEAD below.
- Foreign `Implementing` ∩ board regex: `t1816` (brainstorm `modals.py`
  dismiss guard — mentions `aitask_board._modal_is_active`, which stays),
  `t1555_2` (incidental). Neighbours `t1243`, `t1632`, `t1714` are `Ready` —
  nothing landed to rebase onto. No stop.
- **Shared worktree dirty with foreign edits** to `lib/tui_switcher.py`,
  `lib/agent_launch_utils.py` (both imported by the board), `aitask_setup.sh`,
  … — this task edits none of them; suite, mutants and smoke run in an
  isolated worktree; the code commit names only this task's paths.

## Premises corrected by verification

1. **Shared helpers cannot "stay in the board".** The manager calls
   `_task_git_cmd`, `MetadataWriteError`, `MERGE_*` keys, `_resolve_plan_path_for_task`,
   `InFlightItem`, `TOPIC_SORT_MODES` and the topic-grouping build — all also
   used by `KanbanApp`/`TaskDetailScreen`/in-flight widgets. C1 forbids import-back,
   so they move **with** their lowest-level consumer and the board re-exports
   them. The manager calls **neither** `_get_user_email` nor `_load_task_types`
   (AST probe) — no provider callables are needed.
2. **55 construction calls, not 3** (AST inventory, Step 0(a)). Fixture-mode tests call
   `self.ab.TaskManager()` (~48 sites across 14 files), one passes
   `on_warning=` (`test_board_columns_reconcile.py:242`), and
   `tests/lib/work_report_{,flow_}equiv.py` import `TaskManager` from the board.
   A required-kwargs constructor breaks all of them. Resolution: a board-side
   factory `make_task_manager(**kw)` (reads the board's own constants at call
   time — the one place they bind); `KanbanApp` and fixture-mode tests use it;
   the three **patch-mode** files pass explicit paths (C3).
3. **More repointed patches than listed** (full sweep of `patch.object` string
   targets): add `test_board_group_filtering.py:1127/1133/1291`
   (`save_project_config`, `save_local_config`) and
   `test_board_columns_reconcile.py:280` (`project_columns_at`). Class-attribute
   patches (`B.Task.…`, `B.TaskManager.…`) follow the object — no change.
   `test_board_movement.py` assigns methods onto the classes, but only inside
   its child interpreter — safe under the new single class identity.
4. **13 source-text guards read `aitask_board.py` for code that moves** and
   would fail loudly or go silently vacuous (audit table in Step 5).
5. **Nine `TaskManager.__new__` stubs bypass `__init__`** and then call
   methods that read the board's paths at call time (`gate_state_for` →
   `GATES_REGISTRY_FILE`, `dep_resolver` → `TASKS_DIR`):
   `test_board_inflight_planned_lane.py:49`, `test_board_followup_glyph.py:76`,
   `test_board_topic_group.py:318`, `test_board_plan_approved_marker.py:77`,
   `test_local_dep_parity.py:240`, `test_board_workflow_phase.py:34`,
   `test_board_detail_gates_section.py:87`, `test_board_inflight_view.py:30`,
   `test_board_reference_doc_literals.py:123`. Once injected, those reads become
   `self.<path>` and the stubs lack the attributes — and where a read sits
   inside a degrade-on-exception handler the `AttributeError` would render as
   "Gate state unavailable" rather than fail. Each stub must set all three
   paths (Step 4), enforced by the inventory gate.
6. `DATA_WORKTREE` is a cwd-relative constant, not TASKS_DIR-derived — may move.
   `refresh_git_status` pathspec literal `"aitasks/"` is kept verbatim.

## Move set (anchors at HEAD `4fa524e95`)

| new module | names |
|---|---|
| `board_task_model.py` | `Task` (:762–955), `MoveResult` (:1167–1185), `MERGE_METADATA_KEY`, `MERGE_METADATA_LOCAL_KEY`, `MERGE_UNVERIFIABLE_KEY`, `MergeResult` (:1189–1260, minus `MetadataWriteError`) |
| `board_workflow_phase.py` | `GateStateResult`, `InFlightItem`, `_resolve_plan_path_for_task`, `WORKFLOW_PHASES`, `WORKFLOW_PROVENANCES`, `WorkflowPhase`, `_gate_progress`, `_pending_human_gates`, `_pending_procedure_gates`, `_failed_active_gates`, `derive_workflow_phase`, `INFLIGHT_LANES`, `LANE_FOR_PHASE`, `PHASE_LABELS`, `_inflight_lane`, `_inflight_next_action`, `phase_chip_text` (:160–650) |
| `board_task_manager.py` | `DATA_WORKTREE` (:145), `_DIGEST_UNSET` (:159), `_task_git_cmd` (:652), topic grouping (:1001–1165 minus its three mid-file lib imports: `TOPIC_SORT_MODES`, `TOPIC_SORT_MODE_LABELS`, `_topic_lane_label`, `_task_recency`, `_lane_recency`, `_topic_id_sortkey`, `_sort_topic_lanes`, `_topic_membership_signature`, `_build_topic_lanes`, `_assemble_topic_lanes`, `group_tasks_by_topic`), `MetadataWriteError`, `TaskManager` (:1263–2762) |

Stays: `task_matches_filter`, `set_unit_display`, `_task_file_paths_for_ids`,
`_task_commit_notice`, `_dedup_paths`, `_sanitize_name`, `_load_task_types`,
`_get_user_email`, all path constants, every widget/screen/App.

Dependency order (no cycles): `board_task_model` ← `board_workflow_phase`
(imports `gate_ledger`, `board_widgets._plan_approved_marker`; `Task` only in
string annotations) ← `board_task_manager` (imports both + `board_widgets.TaskCard`).

## Implementation steps

0. **Freeze the two inventories BEFORE any edit** (recorded in this plan and
   written to `$SCRATCH/expected_paths.txt` / `$SCRATCH/tm_sites_before.txt`).

   **(a) Construction-site inventory** — AST scan (not grep) of every `*.py`
   under `tests/` and `.aitask-scripts/` for a `Call` whose callee name is
   `TaskManager`, recording `file:line` and keyword names. At HEAD: **55
   calls** — `aitask_board.py:7471` `(on_warning=)`,
   `test_board_columns_reconcile.py:242` `(on_warning=)`, and 53 zero-argument
   calls in the 17 files listed in Step 4 — plus the **9 `__new__` stubs** in
   Premise 5. Every entry gets a disposition before editing: `factory`
   (`make_task_manager(...)`, the old keywords carried over), `explicit`
   (all three paths passed — patch mode), or `stub` (sets all three attributes).

   **(b) Expected changed-path list** — the exact, sorted set this task may
   touch, frozen in `$SCRATCH/expected_paths.txt` (sha256 recorded here)
   before the first edit.

   **Where edits happen.** All implementation happens in one isolated edit
   worktree, `git worktree add --detach aiwork/t1794_4_impl $BASE` (`BASE` =
   HEAD at Step 0, recorded; `aitask_init_data.sh --link-worktree`), never in
   the shared checkout, which carries another session's uncommitted edits.
   That tree is the only place where "this path was clean before I wrote it"
   can be proved.

   **Write discipline.** Every mechanical rewrite script takes
   `expected_paths.txt` as an allowlist and refuses (non-zero exit, no write)
   any target not on it. Hand edits follow the same rule.

   **Amendments — before the first write, never after.** If a path not on the
   list turns out to be necessary:
   1. Stop before touching it. Run
      `git -C aiwork/t1794_4_impl status --porcelain -uall -- <path>`; it must be
      **empty** (tracked and unmodified), or for a new file the path must not
      exist and must not be tracked (`git ls-files --error-unmatch` fails).
   2. Record the amendment in this plan (`path — reason — status output — time`),
      append it to `expected_paths.txt`, re-sort, record the new sha256.
   3. Only then write it.

   If step 1 shows the path **already modified or present**, something wrote it
   outside the list. Do not amend. Discard the edit worktree
   (`git worktree remove --force aiwork/t1794_4_impl`; it holds only this
   task's replayable work), recreate it from `BASE`, and redo the
   implementation against the frozen list, with the offending script
   fixed. The provenance check never derives its list from the edited tree,
   and an amendment timestamped after a path's first write is invalid.
   ```
   .aitask-scripts/board/aitask_board.py
   .aitask-scripts/board/board_task_manager.py          (new)
   .aitask-scripts/board/board_task_model.py            (new)
   .aitask-scripts/board/board_workflow_phase.py        (new)
   .aitask-scripts/lib/board_columns.py
   .aitask-scripts/lib/board_groups.py
   .aitask-scripts/lib/gate_ledger.py
   tests/lib/board_fixture.py
   tests/lib/board_single_home.py                       (new)
   tests/lib/work_report_equiv.py
   tests/lib/work_report_flow_equiv.py
   tests/test_atomic_task_writes.py
   tests/test_board_archived_relation_lookup.py
   tests/test_board_bytrail_view.py
   tests/test_board_column_dialog.py
   tests/test_board_column_manage.py
   tests/test_board_columns_reconcile.py
   tests/test_board_columns_seam.py
   tests/test_board_detail_gates_section.py
   tests/test_board_dom_transplant.py
   tests/test_board_fixture_harness.py
   tests/test_board_followup_glyph.py
   tests/test_board_gate_digest_budget.py
   tests/test_board_group_filtering.py
   tests/test_board_inflight_planned_lane.py
   tests/test_board_inflight_view.py
   tests/test_board_manager_moves.py
   tests/test_board_persistence_seam.py
   tests/test_board_plan_approved_marker.py
   tests/test_board_reference_doc_literals.py
   tests/test_board_refresh_degrade.py
   tests/test_board_render_scoping.py
   tests/test_board_scoped_task_commit.py
   tests/test_board_task_manager.py                     (new)
   tests/test_board_topic_group.py
   tests/test_board_topic_view.py
   tests/test_board_trail_view.py
   tests/test_board_workflow_phase.py
   tests/test_local_dep_parity.py
   tests/test_metadata_writer_inventory.py
   tests/test_task_lock.sh
   tests/test_trail_gather.py
   ```

1. **Create the three modules by script, verbatim.** Same method as p1794_3:
   cut regions in reverse order after asserting each region's first line and
   following neighbour; after writing, assert every unedited top-level block is
   a byte-for-byte substring of its new module (catches `\uXXXX`
   normalisation). Each module: docstring (what lives here, C1 flat / no
   `aitask_board`, C2 paths by parameter, "stubs of a name called inside this
   module patch it here — `ab.<module>`"), `from __future__ import annotations`,
   exactly the imports the moved bodies use (AST free-name probe recorded
   during verification).

2. **`TaskManager` constructor injection (the only non-verbatim edit).**
   `def __init__(self, *, tasks_dir: Path, metadata_file: Path,
   gates_registry_file: Path, on_warning=None)` → store `self.tasks_dir`,
   `self.metadata_file`, `self.gates_registry_file` **before** `_ensure_paths()`.
   Global reads → attribute reads, disposition table (all "constructor param"):

   | HEAD line | read |
   |---|---|
   | 1342–1343 | `TASKS_DIR.mkdir`, `METADATA_FILE.parent.mkdir` |
   | 1351, 1365, 1449, 1527, 1579, 1600 | `METADATA_FILE` (load/project_columns_at/save local/save project/commit paths) |
   | 1640, 1659, 1683, 1692, 1730, 1737, 1739, 2667 | `TASKS_DIR` (globs, lookups, archived) |
   | 1871, 1891, 1918 | `GATES_REGISTRY_FILE` (+`TASKS_DIR` at 1918) |

   Lib functions (`save_local_config`, `save_project_config`,
   `load_layered_config`, `project_columns_at`, `local_path_for`,
   `split_config`, `commit_metadata`, `gate_ledger`, `dep_resolution`,
   `board_ordering`, `find_archived_markdown_by_id`, `_task_id_sort_key`,
   `_bare_topic_id`, …) → module imports in `board_task_manager.py`.
   `str(self.gates_registry_file)` keeps `test_gate_ledger_only_surfaces`
   decidable.

3. **`aitask_board.py`.**
   - Bare-import + flat re-import pairs, after the `board_trail_view` block,
     with the same RE-EXPORT comment: `import board_task_model`,
     `import board_workflow_phase`, `import board_task_manager` and
     `from … import (<every moved name>)` — `_DIGEST_UNSET` included (tests
     read `ab._DIGEST_UNSET` and the manager compares by identity).
   - Cut the regions; one-line pointers where section comments stood.
   - Factory next to the constants' consumers:
     ```python
     def make_task_manager(**kwargs) -> TaskManager:
         """The board's TaskManager, bound to THIS module's task-dir constants
         (t1794_4, C2). Reads them at call time, so a fixture-loaded board binds
         its fixture tree. Siblings never resolve the task dir themselves."""
         return TaskManager(tasks_dir=TASKS_DIR, metadata_file=METADATA_FILE,
                            gates_registry_file=GATES_REGISTRY_FILE, **kwargs)
     ```
   - `KanbanApp.__init__` (:7471): `self.manager = make_task_manager(on_warning=self.notify)`.
   - Drop imports only moved code used (`atomic_write_text`, `board_ordering`,
     `_PROJECT_KEYS`, `_USER_KEYS`, `gate_ledger`, `dep_resolution`,
     `commit_metadata`, `load_layered_config`, `split_config`,
     `save_project_config`, `save_local_config`, `local_path_for`, unused
     `board_columns`/`task_yaml`/`topic_semantics` names) — confirmed by
     `UnresolvedGlobalsTests` (catches over-removal) plus the child-2 probe
     (every remaining import is loaded or a declared re-export).
   - `METADATA_FILE`, `GATES_REGISTRY_FILE` stay (factory + tests +
     `test_task_dir_module_constants`).

4. **Construction sites and C3 repoints (tests).**
   - Fixture mode (≈50 sites, 16 files — `test_board_column_dialog`,
     `_refresh_degrade`, `_group_filtering`, `_render_scoping`,
     `_columns_reconcile` (incl. `on_warning=` at :242), `_inflight_view`,
     `_archived_relation_lookup`, `_dom_transplant`, `_bytrail_view`,
     `_topic_view`, `_gate_digest_budget`, `_fixture_harness`, …) and
     `tests/lib/work_report_{,flow_}equiv.py`: `TaskManager(` →
     `make_task_manager(` (by script driven by the Step-0 inventory, keywords
     such as `on_warning=` carried over).
   - `__new__` stubs (Premise 5, 9 sites): after `__new__`, set
     `mgr.tasks_dir = ab.TASKS_DIR`, `mgr.metadata_file = ab.METADATA_FILE`,
     `mgr.gates_registry_file = ab.GATES_REGISTRY_FILE` (the values the
     methods read from the board's globals today).
   - Patch mode — explicit kwargs, no global patches:
     `test_board_persistence_seam.py` `_manager` (:198–204),
     `test_board_manager_moves.py` `setUp` (:91–99),
     `test_board_column_manage.py` `setUp` (:93–98) + `fresh_manager` (:163):
     `B.TaskManager(tasks_dir=…, metadata_file=…/"board_config.json",
     gates_registry_file=…/"gates.yaml")`. Remove the now-false
     "stopall would re-point the manager at the live tree" comment.
     `test_patched_module_globals_are_restored` (:713) is rewritten to its
     still-meaningful form: constructing an injected manager leaves
     `B.TASKS_DIR`/`B.METADATA_FILE` untouched **and** the manager's paths are
     the injected ones.
   - Repoint (patch target and call-through `original = …` reads):

     | site | name | new target |
     |---|---|---|
     | persistence_seam:135 | `datetime` | `B.board_task_model` |
     | persistence_seam:777,784,803,809 | `local_path_for`, `save_local_config` | `B.board_task_manager` |
     | column_manage:695 | `save_project_config` | `B.board_task_manager` |
     | column_manage:713,729,745 | `save_local_config` | `B.board_task_manager` |
     | group_filtering:1127,1133 | `save_project_config` | `self.ab.board_task_manager` |
     | group_filtering:1291 | `save_local_config` | `self.ab.board_task_manager` |
     | columns_reconcile:280 | `project_columns_at` | `self.ab.board_task_manager` |
     | gate_digest_budget:116–117 | `gate_ledger` (attr read) | `self.ab.board_task_manager` |

   - **Mutant per repointed patch** (isolated worktree, scratch copy of the
     module, never the shared tree): replace the module-global call the patch
     intercepts with a bypass (`config_utils.save_local_config(…)`,
     `config_utils.save_project_config(…)`, `board_columns.project_columns_at(…)`,
     `__import__("datetime").datetime.now()`) → the patched tests go red;
     restore → green. One line per mutant with its red run recorded here.

5. **Source-text guards that follow the code** (audit, verified). Pattern: scan
   `sorted(BOARD_DIR.glob("*.py"))`, parse each file separately, with
   anti-vacuity that the three new modules are in the set and each watched
   definition is found in the file it now lives in.
   - `test_board_columns_reconcile.py:377,508` — call-containment and
     save-path callers over the union; `def save_settings(self) -> None:`
     asserted against `board_task_manager.py` (today's `assertIn` would match
     `SettingsScreen.save_settings`); negative controls still inject into
     `aitask_board.py` text, unioned with the other trees.
   - `test_board_columns_seam.py:573,605` — `assertNotIn` forks over the union;
     `from board_columns import PROJECT_KEYS` asserted in `board_task_manager.py`.
   - `test_board_gate_digest_budget.py:369,466,494` — predicate consumers,
     `clear_gate_cache` callers `{load_tasks, refresh_board}`, digest-reset
     sites over the union; control `next(…, None)` + `assertIsNotNone`.
   - `test_board_inflight_planned_lane.py:717` — union.
   - `test_board_manager_moves.py:603` — `import board_ordering` in
     `board_task_manager.py`; `assertNotIn` defs over the union.
   - `test_board_persistence_seam.py:585,593` — `_parse_call_sites` per file,
     concatenated in file order; `_parse_variant` reads `board_task_manager.py`.
   - `test_board_scoped_task_commit.py:360` — union; anti-vacuity ≥3
     `_task_git_cmd()` calls, ≥1 in `board_task_manager.py`.
   - `test_metadata_writer_inventory.py` — keys →
     `board/board_task_manager.py::save_metadata` / `::_write_user_layer`;
     `must_find` adjusted to what discovery actually flags (no literal added
     to production to satisfy it); any still-flagged board file pinned with a
     reason.
   - `test_trail_gather.py:2698` — `assertNotIn` over the union;
     `from topic_semantics import` in both files that use it.
   - `tests/test_task_lock.sh:670` — sed over `board/*.py`, assert exactly one
     match; label "board lock regex located in board/*.py".
   - Prose only: `test_atomic_task_writes.py` docstring/mutation table →
     `board_task_model.py`; `test_board_plan_approved_marker.py:169` stale
     line cite.

6. **New tests + harness (C2/C3 pins).**
   - Lift `_name_targets`, `_top_level_bindings`, `_single_home_findings`,
     `_imported_from` from `test_board_trail_view.py` into
     `tests/lib/board_single_home.py` (verbatim; trail-view file imports them,
     its controls stay).
   - NEW `tests/test_board_task_manager.py` (fixture tier, added to
     `MIGRATED_MODULES`): `MOVED` = {module: names} from the move-set table.
     `SingleHomeTests` per module (each name defined exactly once in its module,
     nowhere in the board, both-way completeness, board imports every name
     back); `ReexportIdentityTests` (`ab.X is ab.<module>.X`, classes'
     `__module__`); `ConstructorContractTests`: `TaskManager()` and positional
     args raise `TypeError`; `make_task_manager()` passes the board's
     constants.
   - `tests/test_board_fixture_harness.py`: **pinning test** constructing
     `ab.TaskManager(tasks_dir=A/aitasks, …)` the patch-mode way while cwd is a
     second tree B → `task_datas` lists A's tasks only, and a metadata save
     lands in A; negative control: the same assertion against a manager built
     from cwd-relative `Path("aitasks")` lists B's. Explicit C2 case:
     `_ambient_task_path_reads(board_task_manager.py) == []` with anti-vacuity
     (`self.tasks_dir` present). `FreshLoadC2Tests` real-tree anti-vacuity
     gains the three modules. Exemption text (:355–378): the three patch-mode
     files now construct with explicit paths and patch no module globals.
     `MIGRATED_MODULES` += `test_board_task_manager.py`.

7. **Pointers.** `lib/gate_ledger.py:1450,1593`, `lib/board_groups.py:182`,
   `lib/board_columns.py:474` → `board_task_manager.TaskManager`
   (`monitor/monitor_core.py:4048` left: its `aitask_board.TaskManager` still
   resolves and the file is outside this task); `tests/lib/board_fixture.py`
   docstring rows naming the manager.

## Verification

Suite, gates and mutants run in the **edit worktree** `aiwork/t1794_4_impl`
(Step 0). Provenance is fail-closed against the list **frozen in Step 0(b)**
(plus only amendments recorded before their first write), never one derived
after editing:
`git -C aiwork/t1794_4_impl status --porcelain -uall | cut -c4- | sort` must be
**byte-identical** to `sort $SCRATCH/expected_paths.txt` (`diff` exit 0). A
file the list does not name fails the check; so does a listed file left
untouched. Record BASE, the list's sha256 and the diff's sha256.

**Landing the change in the commit checkout.** Before applying, confirm every
listed path is clean in the shared checkout
(`git status --porcelain -- $(cat expected_paths.txt)` empty) and that `main`
has not moved on them since `BASE` (`git diff --quiet BASE HEAD -- <list>`);
otherwise stop and rebase the worktree first. Then
`git -C aiwork/t1794_4_impl diff --binary BASE -- <list>` (+ new files) is
applied, the same byte-identical porcelain comparison runs over those paths
with the same sha256, and the Step-8 commit pathspec is exactly that list.
The smoke check's "change" worktree is the edit worktree itself; the "base"
worktree is a detached `BASE`. Both are removed after Step 8.

- **Construction-site gate (replaces the literal-`TaskManager()` grep).**
  Re-run the Step-0 AST inventory on the edited tree; fail unless **every**
  `Call` to `TaskManager` passes all of `tasks_dir`, `metadata_file` and
  `gates_registry_file` as keywords (no positional args), every former site is
  now a `make_task_manager(...)` call or such an explicit call, and every
  `TaskManager.__new__` site in a function assigns all three attributes before
  returning. Per-site before/after table (55 calls + 9 stubs) recorded here; a
  count mismatch against Step 0(a) is a failure, not an update. Negative
  controls: the gate script flags a synthetic `TaskManager(on_warning=f)`, a
  call missing one path, and a stub missing `gates_registry_file`.
  `test_board_task_manager.ConstructorContractTests` pins the runtime half
  (`TaskManager(on_warning=…)` raises `TypeError`).

- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`
  (known environmental `test_roadmap_drift_contract` linked-worktree failures
  compared against a BASE worktree before attributing anything).
- Targeted: `test_board_persistence_seam test_board_manager_moves
  test_board_movement test_board_column_manage test_followup_kind_phantom_stub
  test_atomic_task_writes test_board_workflow_phase test_task_dir_module_constants
  test_board_fixture_harness test_board_package_contract
  test_board_keymap_characterization test_board_task_manager
  test_board_trail_view test_board_columns_reconcile test_board_columns_seam
  test_board_gate_digest_budget test_board_inflight_planned_lane
  test_board_scoped_task_commit test_metadata_writer_inventory
  test_board_group_filtering test_trail_gather test_gate_ledger_only_surfaces`
  green; keymap golden **unchanged**.
- Bash: `tests/test_task_lock.sh`, `test_no_lib_to_tui_import.sh`,
  `test_no_raw_tmux.sh`, `test_shortcuts_registry_coverage.sh`,
  `test_keybinding_registry.sh`, `test_serial_carveout_doc_drift.sh`.
- `grep -nE '^class (Task|TaskManager)\b|^def derive_workflow_phase'
  .aitask-scripts/board/aitask_board.py` → empty.
- Mutants (Step 4) and guard red runs (Step 5/6 controls with checker
  neutered, pre-rescope scope shown vacuous) recorded with each red run.
- Manual smoke (isolated base + change worktrees, private tmux socket,
  state-gated keys): boot → move a card to another column (`m`) → open detail,
  edit a field (updated_at written on disk) → `z` By-Trail opens → `q`.
  Captures identical modulo timestamps; no traceback.

## Risk

### Code-health risk: medium
- A moved body loses an import or a global read escapes injection; fires only on a rare path (archived lookup, merge failure branch) · severity: medium (residual — `UnresolvedGlobalsTests` globs every `board/*.py`, the C2 static scan flags any path constant in the new modules, and the byte-for-byte block check leaves the attribute rewrite as the only textual edit) · → mitigation: none
- A patch on a moved caller's global stays green but inert (t1613 class) · severity: medium (residual — full `patch.object` sweep found 4 more sites than the task listed; each repoint carries a bypass mutant proven red) · → mitigation: none
- A source-text guard goes silently vacuous because the code it reads left `aitask_board.py` · severity: medium (residual — all 13 readers audited and rescoped to the `board/*.py` union with per-file anti-vacuity; the Step 5 red runs show the old scope finding nothing) · → mitigation: none
- A construction site keeps an old-style call (e.g. `TaskManager(on_warning=…)`) or a `__new__` stub lacks an injected path, failing only when that path runs — possibly swallowed by a degrade handler · severity: medium (residual — Step 0(a) freezes an AST inventory of all 55 calls + 9 stubs with a disposition each, and the verification gate re-runs it requiring all three paths or the factory, with negative controls) · → mitigation: none
- The mechanical edits touch ~40 files, so an unrelated change could ride into the smoke worktree or the commit, or a mistaken rewrite could be legitimized by a late list amendment · severity: medium (residual — Step 0(b) freezes the exact sorted path list; edits happen only in an isolated worktree; rewrite scripts enforce the list as an allowlist; an amendment is valid only if recorded before first write with a clean-status proof, and an already-dirty unlisted path forces a worktree discard and restart; provenance and the commit pathspec compare byte-for-byte against the list) · → mitigation: none
- `Task`/`TaskManager` become one class object across fixture loads, so an unrestored class-attribute mutation would leak across tests in a worker · severity: low (verified: in-process class patches are `patch.object`-scoped; the only direct assignments run in `test_board_movement`'s child interpreter) · → mitigation: none
- The shared checkout holds foreign edits to modules the board imports · severity: low (all runs in an isolated, provenance-checked worktree; path-scoped commit) · → mitigation: none

### Goal-achievement risk: low
- The factory is a small deviation from "KanbanApp calls `TaskManager(tasks_dir=…)` directly" · severity: low (the factory is exactly that call; the pinned kw-only required constructor is unchanged and the patch-mode pinning test constructs it directly) · → mitigation: none

Every identified risk is already addressed by this plan's own steps
(`risk_mitigations_planned = false`; no `### Planned mitigations` block).

## Post-implementation

Step 8 review (path-scoped code commit
`refactor: Extract TaskManager, Task and workflow phase into board modules (t1794_4)`;
plan commit); Step 8e offer notes to t1794_5/t1794_6 (use `make_task_manager`
or inject paths; patch manager-called lib globals on `board_task_manager`) and
t1243/t1632/t1714 (manager now lives in `board_task_manager.py`); Step 9
(gates — `risk_evaluated`; archive `t1794_4`).
