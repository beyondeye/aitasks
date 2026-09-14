---
Task: t1794_1_board_package_contract_and_baseline.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_2_*.md … aitasks/t1794/t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-14 11:50
---

# p1794_1 — Board package contract, characterization test and footprint baseline

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(Decisions, Target file map and contracts C1–C10 are PINNED). This child moves
no code: it lands the package marker, the guards every later child must
satisfy, the characterization golden that makes "the board behaves exactly as
before" a checked claim, and the footprint baseline.

## Context

`aitask_board.py` (14,102 lines) is about to be split into flat-imported
`board/board_*.py` modules. Three silent failure classes (all measured) are
guarded here before any code moves: a `board.`-qualified, relative or dynamic
import, or an import-back of `aitask_board` (second class identity, canonical
`TASKS_DIR` rebound — t1613 class); a sibling resolving the task dir itself —
**either** binding `TASKS_DIR`-derived paths at import (keeps the canonical
value) **or** calling the resolver lazily at runtime (reads the env
`load_board_module()` has already restored) — both wrong, both silent; and
colliding basenames on the set-ordered `sys.path` built by
`lib/shortcut_scopes.py:83–89`.

## Step 0 — Rebase check (pre-phase `rebase_check_before_each_child`) — DONE at planning

- HEAD `b92aebc20`; `git log c78deab36..HEAD -- .aitask-scripts/board/ tests/lib/board_fixture.py`
  is empty. Anchors re-derived and unchanged: `KanbanApp :8487`,
  `BINDINGS :8796–8902`, `__init__ :8904` (`base_filter :8913`),
  `check_action :8982–9280`, `compose :9282` (`#board_container :9297`,
  `#trail_summary`/`#trail_summary_body :9318–9323`), `LoadingOverlay :8004`
  (a pushed `ModalScreen`, not composed), `TASKS_DIR… :109–118` (the board's
  only direct ambient read is `:109 TASKS_DIR = task_dir()`), lib insert `:17`.
- Foreign `Implementing` ∩ board regex: `t1688`, `t1555_2` — both match only
  incidentally (call-site count tables; labels skills/task-workflow). No
  foreign task is on the board region → no stop.

## Implementation steps

1. **Package marker + own-dir insert.**
   - NEW `.aitask-scripts/board/__init__.py`: docstring only, stating C1 (flat
     bare-name imports, `board_` prefix, no `board.`-qualified, relative or
     dynamic import, no `board/*.py` imports `aitask_board`) and C2 (no module
     but `aitask_board.py` resolves the task dir — neither at import nor lazily;
     paths are passed by parameter). Points to the parent plan and the two
     guard files.
   - `aitask_board.py:17`: add directly below the lib insert
     `sys.path.insert(0, str(Path(__file__).resolve().parent))` with a one-line
     comment (flat sibling imports under launcher / fixture
     `spec_from_file_location` / shortcut sweep / subprocess loaders).
   - Inert elsewhere (verified): nothing imports `board`; no `board/*.py`
     basename collides with lib or any manifest dir; `.aitask-scripts/board/aitasks`
     is a gitignored stray dir, not a package.

2. **Shared module-name set** — `tests/lib/board_fixture.py`: add
   `BOARD_MODULE_NAMES = frozenset({"aitask_board", "board_widgets",
   "board_trail_view", "board_task_model", "board_task_manager",
   "board_workflow_phase", "board_trail_screen", "trails_app",
   "board_detail_screen", "board_column_dialogs"})` and
   `BOARD_NON_MEMBERS = frozenset({"aitask_merge"})` (unrelated CLI), with a
   comment: a child adding a `board/*.py` must add it here (enforced below).

3. **`tests/test_board_package_contract.py` (C1)** — every checker is a pure
   function over sources/dirs so each negative control feeds a synthetic
   offender through the *same* checker (pattern: `test_board_fixture_harness`
   `_chdir_expressions`, `test_record_protocol.DependencyFreeTests`).
   - `_qualified_board_imports(source)`, scanned over `.aitask-scripts/**/*.py`
     + `tests/**/*.py` (green on tree — verified no hits today):
     - static: `import board` / `import board.x` / `from board[.x] import …`,
       and relative `from . import …` / `from .x import …` (level>0);
     - **dynamic, alias-tracked**: a call whose callee resolves to
       `import_module` or `__import__` — direct `importlib.import_module`,
       `from importlib import import_module [as X]`, `import importlib as X` →
       `X.import_module`, simple assignment aliases (`Y = importlib.import_module`,
       `Y = X`), `builtins.__import__`, `getattr(importlib, "import_module")(…)`
       — whose first argument is a string literal equal to `"board"`, starting
       `"board."`, or starting `"."` (dot-relative, whatever `package=` says).
     Negatives: one synthetic source per spelling above, including
     `import_module(".board_task_model", package=pkg)` and an aliased
     `im(".board_x", package=__package__)`; a `"import board.x"` string literal
     and `import_module("board_columns")` (a flat `lib/` name) NOT flagged.
   - `_board_dynamic_imports(source)` — **deny-by-default inside `board/*.py`**
     (all files, `aitask_board.py` included): any reference, call or value, to
     `importlib` (the import statement itself), `import_module`, `__import__`,
     `spec_from_file_location`, `module_from_spec`, or a `getattr(…, "<one of
     those>")`, whatever the argument — a flat module never needs to load a
     sibling dynamically, and rejecting the reference catches aliases without
     dataflow (same rationale as `_chdir_expressions`). Exemptions are exact
     expressions in `BOARD_DYNAMIC_IMPORT_ALLOWED`, **empty today** (verified:
     zero such references in `board/*.py`); an allowlist-staleness test as in
     `CHDIR_ALLOWED`. Negatives: synthetic board files with
     `importlib.util.spec_from_file_location(...)`, `im = importlib.import_module`,
     `from importlib import import_module as im; im("x")`, `__import__("x")`.
   - `_aitask_board_imports(source)` over every `board/*.py` except
     `aitask_board.py`: `import aitask_board`, `from aitask_board import …`
     (dynamic forms are already covered by the deny-by-default rule). Negative:
     synthetic `board_fake.py`.
   - Membership drift: every `board/*.py` stem (minus `__init__`) ∈
     `BOARD_MODULE_NAMES ∪ BOARD_NON_MEMBERS`; negative on a synthetic dir.
   - `_basename_collisions(dirs)`: dirs = parents of `KNOWN_BINDING_SOURCES`
     (read from `lib/shortcut_scopes.py`, so the guard follows the manifest) +
     `lib/` + `.aitask-scripts/` + `board/`; `__init__.py` excluded.
     **Pre-existing collisions exist:** `paths.py` and `audit.py` in both
     `applink/` and `chatlink/` (upstream defect, see Notes). Pinned as
     `KNOWN_COLLISIONS = {"paths.py": {"applink","chatlink"}, "audit.py": {…}}`.
     Rules: no collision outside the pin; **no collision may involve `board/`
     even if pinned**; every pinned entry must still be real (stale pin fails).
     Negatives on temp dirs: `board/widgets.py` vs `brainstorm/widgets.py`
     flagged; an unpinned non-board collision flagged; a removed pinned file
     reports a stale pin.
   - `_unpaired_patch_targets(board_dir, tests_sources)`: names from
     `patch.object(<expr>, "<name>"…)` calls in `tests/**/*.py` (any callee
     ending `patch.object`); for each `board/board_*.py` defining that name at
     top level (def/async def/class/assign/annassign), `aitask_board.py` must
     contain a plain `import <module>` (no `as`) so `ab.<module>` is a patch
     target. Vacuous today (no `board_*.py`) — anti-vacuity: the scanned name
     set is non-empty and contains `discover_trails`; negative: synthetic
     `board_fake.py` defining `discover_trails` + synthetic `aitask_board.py`
     without / with `import board_fake` → finding / none.
   - `OwnDirInsertTests`: subprocess (`sys.executable`, clean `PYTHONPATH`,
     `cwd=REPO_ROOT`, `TASK_DIR` unset) execs `aitask_board.py` via
     `spec_from_file_location` and prints whether `board/` is on `sys.path`.
     Must be a subprocess: every board test pre-inserts `board/`, so an
     in-process check passes without the insert. Red on HEAD before step 1's
     edit, green after (record both).

4. **C2 guard — `tests/test_board_fixture_harness.py`.**
   - Widen `_canonical_board_imports` (`:479–493`) from the literal
     `"aitask_board"` to `bf.BOARD_MODULE_NAMES` (same `canonical import: …`
     finding text, so `CANONICAL_IMPORT_ALLOWED` entries still match); extend
     `test_guard_flags_a_canonical_board_import` with `import board_task_manager`
     and `from board_trail_view import X`.
   - **Static half — `_ambient_task_path_reads(source)`, position-independent.**
     Scope: every `board/*.py` except `aitask_board.py` and `BOARD_NON_MEMBERS`
     (the unrelated CLI never runs under the fixture; it has no such reads
     today anyway — verified). Reports, **in any AST position** (module body,
     class body, decorator, default argument, function body, lambda body):
     (a) any reference, call or value, to the direct resolvers `task_dir` /
     `metadata_dir` — the `from config_utils import task_dir [as X]` statement
     itself, bare-name references (so `td = task_dir` and passing `task_dir` as
     a factory are caught without dataflow), `<alias>.task_dir` attribute
     references, `getattr(…, "task_dir")`; (b) ambient environment reads of
     `"TASK_DIR"` — `os.environ["TASK_DIR"]`, `os.environ.get("TASK_DIR", …)`,
     `os.getenv("TASK_DIR")`, `environ.get(…)`: any call argument or subscript
     slice that is the string constant `"TASK_DIR"`; (c) any reference to
     `TASKS_DIR`, `METADATA_FILE`, `GATES_REGISTRY_FILE`, `USERCONFIG_FILE`,
     `EMAILS_FILE`, `TASK_TYPES_FILE`. Findings name the position
     (`import-time` / `runtime`) for the message only — both are failures. The
     compliant pattern is a resolved path parameter (C2: `TaskManager(*,
     tasks_dir, …)`, `load_local_project_name(tasks_dir, …)`). Exact-expression
     allowlist `C2_AMBIENT_ALLOWED`, **empty**, with a staleness test.
     Negatives: temp-dir modules for every form — module-level, class-body,
     default-arg, decorator, **in-function call**, **lambda body**, `from … as`
     alias, value alias, attribute, `getattr`, each env-read spelling,
     constant-name — all flagged; a module taking `tasks_dir` as a parameter and
     a docstring mentioning `task_dir()` NOT flagged.
   - **Boundary, stated in the guard docstring and in Notes:** the guard covers
     *direct* ambient resolution in board modules. `lib/` functions that resolve
     the task dir internally — `trail_discovery._tasks_dir` (behind
     `discover_trails`, the pinned trail seam), `config_utils.load_all_models`
     and its import-time `MODEL_FILES`, `work_report_gather.scan_tasks` /
     `load_columns`, `trail_gather._local_dirs`, `roadmap_origin_facts._dirs`,
     `userconfig_persist._userconfig_path` — are a pre-existing `lib/`-layer
     property the canonical board already relies on; a sibling calls them only
     where the moved code already did (behaviour-preserving move), and changing
     that layer is out of scope for t1794 (C6: nothing moves to `lib/`). Step 8
     records the exact current board call sites of these functions.
   - **Runtime half — fresh-process, sentinel `TASK_DIR`, freshness-asserted.**
     An in-process check after `load_board_module()` is unsound (a sibling
     already in the worker's `sys.modules` is reused, not re-executed), and with
     the fixture's `TASK_DIR_VALUE == "aitasks" ==` the default a wrong binding
     or a lazy read is indistinguishable from a right one. So
     `_fresh_load_report(workdir, *, board_path=None, names=None, preimport=(),
     calls=())` runs a **subprocess** (`sys.executable`, `cwd=workdir`,
     `TASK_DIR` unset, `PYTHONPATH` = `tests/lib` + `.aitask-scripts` + `board`
     + `lib`) in a temp `workdir` holding a sentinel dir `c2_sentinel_tasks/`.
     Its script: imports `board_fixture as bf`; optionally repoints
     `bf.BOARD_PATH` (read at call time, `board_fixture.py:534`) and imports
     `preimport` modules; snapshots `before = set(sys.modules)` and asserts
     `BOARD_MODULE_NAMES ∩ before == ∅`; calls the real
     `board = bf.load_board_module("c2_sentinel_tasks", tag="c2fresh")`;
     **asserts `board.TASKS_DIR == Path("c2_sentinel_tasks")`** (anti-vacuity:
     the load honoured the sentinel); then — with the env already restored, as
     in every fixture test — emits JSON: for each name in `names` (default
     `BOARD_MODULE_NAMES − {"aitask_board"}`) present in `sys.modules`,
     `{"fresh": name not in before, "bound": [Path attrs derived from the
     sentinel or the default "aitasks"]}`, and for each `"module:function"` in
     `calls`, the function's return value next to `board.TASKS_DIR`.
     `_c2_findings(report)` fails closed on a present sibling with
     `fresh: false` (**"imported before the fixture load — the check did not
     exercise it"**), any non-empty `bound`, and any `calls` result that differs
     from `board.TASKS_DIR`. The real-tree test runs it with the real
     `BOARD_PATH` and records which siblings it exercised (none today → stated
     as vacuous-until-child-2 in the docstring; the static half is the
     enforcement for lazy reads, which only a behaviour path can execute).
     Negative controls (temp dir, no repo edits), all through the same loader
     via a repointed `BOARD_PATH` — a stand-in `aitask_board.py` that inserts
     its own dir, sets `TASKS_DIR = task_dir()` and `import board_c2_probe`:
     (i) probe binds `TASKS_DIR = task_dir()` → `bound` finding, `fresh: true`;
     (ii) harmless probe with `preimport=("board_c2_probe",)` → staleness
     finding (the freshness assertion discriminates on its own);
     (iii) probe binds `SCRIPT = Path(".aitask-scripts")/"x.sh"` → no finding;
     (iv) **deferred read** — probe `def tasks_root(): return task_dir()`,
     `calls=("board_c2_probe:tasks_root",)`: invoked after restoration it
     returns `Path("aitasks")` while `board.TASKS_DIR` is
     `Path("c2_sentinel_tasks")` — no exception, wrong tree; the test asserts
     that divergence (the failure mode is real and silent) **and** that
     `_ambient_task_path_reads` flags that same probe source;
     (v) compliant probe `def tasks_root(tasks_dir): return tasks_dir`, invoked
     with `board.TASKS_DIR` → returns the sentinel, and the static guard is
     clean on it.
   - Add `test_board_keymap_characterization.py` to `MIGRATED_MODULES`
     (reaches the board only through the harness → strict tier 2).

5. **`tests/test_board_keymap_characterization.py`**
   (pre-phase `characterize_board_keymap_and_views`), `FixtureBoardTestBase`:
   - (a) `GOLDEN_BINDINGS`: ordered list of `(key, action, description, show,
     priority)` for `ab.KanbanApp.BINDINGS` — the class attribute, i.e. the
     defaults (`ShortcutsMixin.__init__` applies user overrides per instance).
     Order is pinned: duplicate-key dispatch and footer order follow it.
   - (b) `GOLDEN_CHECK_ACTION`: under `run_test(size=(200, 48))`, focus states
     `none` (`set_focus(None)`) and `parent_card` (the `t9000_parent.md`
     `TaskCard`, which has children) × `base_filter ∈ {all, locked, free,
     inflight, bytopic, bytrail}` set **directly on the attribute** (no
     `_set_base_filter` → no trail selector modal, no workers) → for every bound
     action, `check_action(action, None)`. Stored losslessly and reviewably as
     `{"<filter>/<focus>": {"hidden": [...False], "greyed": [...None]}}`, every
     other bound action asserted `True`. Precondition asserted: one screen on
     the stack, no active trail.
   - (c) widget contract after boot: `query_one("HeaderTitle")`,
     `#board_container`, `#trail_summary` containing `#trail_summary_body`;
     `issubclass(ab.LoadingOverlay, ModalScreen)`. Negative: a nonexistent id
     raises `NoMatches` (the query discriminates).
   - Negatives: `_diff_bindings` on the real observed table with one row removed
     is non-empty; `_diff_matrix` with one cell flipped is non-empty.
   - Header comment: children 5 and 6 keep this green **unchanged**; any other
     change to the golden is a deliberate behaviour change named in that task's
     plan. No golden-dump path in the file — generate once with a scratch script
     at implementation time, hand-review, paste.
   - Worker hygiene per `aidocs/framework/testing_conventions.md` §"`@work` left
     in flight": pause after boot as `FixtureBootTests` does; add
     `assertNoLiveWorkers(app)` at block end if boot leaves none live.

6. **`tests/perf/board_footprint.sh [--runs N] <module> <interpreter>`**
   (manual; not collected — the runner globs top-level `tests/test_*.py` only)
   + **`tests/perf/footprint_ceiling.py`**.
   - `#!/usr/bin/env bash`, `set -euo pipefail`; sources
     `.aitask-scripts/lib/tmux_exec.sh` (gateway + `die`). Module resolved as
     `<module>.py` under `.aitask-scripts/board` or `tests/perf`;
     `PYTHONPATH=<moddir>:board:lib:.aitask-scripts`; cwd = repo root.
     `--runs N` default **5**, minimum 1; `N < 5` prints a stderr warning that
     the sample is too small for the margin rule in the post-phase.
   - Per invocation: 1 discarded warm-up import (pycache). Per run `i`, both
     samples independent of every other run: **cold start** = median of 5
     fresh `"$interp" -c 'import <module>'` processes, wall time via
     `date +%s%N` (interpreter startup included — stated in the doc); **RSS** =
     a fresh launch in its own tmux session, sampled once at 10 s idle.
   - Launch: private socket `AITASKS_TMUX_SOCKET=ait_footprint_$$` (never the
     live `ait` server; `unset TMUX TMUX_PANE` too), `ait_tmux new-session -d -s
     footprint_$$_<i> -x 200 -y 50 -c <repo> "exec env PYTHONPATH=… <interp>
     <file>"` (`printf %q`-quoted); `pane_pid` via `display-message`; fail
     closed unless `/proc/<pid>/exe` is the interpreter; `sleep 10`; fail
     closed (dump `capture-pane` to stderr) if the process died; `VmRSS` → MiB
     (1 dp). Teardown trap: `kill-session -t =<session>` only (no
     `kill-server`; the private server exits when empty).
   - stdout: one **raw line per run** —
     `<sha>[-dirty] <module> <impl>-<ver> run=<i>/<N> rss_mib=<n> coldstart_ms=<n> load1=<x> parent_tasks=<n>`
     (`-dirty` if `.aitask-scripts/` differs from HEAD; `load1` from
     `/proc/loadavg` at the RSS sample; `parent_tasks` = `aitasks/t*.md` count —
     C8 requires the same tree) — then one line
     `summary <module> <impl>-<ver> n=<N> rss_mib=<median> [<min>–<max>] coldstart_ms=<median> [<min>–<max>]`.
     `shellcheck` clean.
   - `footprint_ceiling.py`: imports only `textual`, `rich`, `yaml` and `App`,
     `Static`, `Label`, `Button`, `VerticalScroll`, `Container`, `ModalScreen`,
     `Binding`; `__main__` runs a minimal App (one `Static` in a
     `VerticalScroll`). It is the RSS floor for a trails app — the ceiling on
     achievable savings child 6 is judged against.

7. **Measure + record** — run `aitask_board` and `footprint_ceiling` under
   `~/.aitask/venv/bin/python` (CPython 3.14.7) and
   `~/.aitask/pypy_venv/bin/python` (PyPy 3.11.15), textual 8.2.7 both, each
   with `--runs 5` (four configurations — the three required + ceiling under
   PyPy; ~6 min, run in the background). New section
   `## t1794 baseline — board footprint (2026-09-14)` in
   `aidocs/framework/python_tui_performance.md` before `## Related Tasks`:
   protocol (script, pane size, 10 s idle, cold-start definition, warm-up, one
   RSS sample per independent launch), **all 20 raw lines verbatim** plus the
   four summary lines, SHA, parent-task count, and the margin rule of the
   post-phase step below.

8. **C5 inventory** — finalize `## Notes for sibling tasks` (below) from a
   fresh re-grep; name the owning child for each path-keyed entry, and record
   the current `aitask_board.py` call sites of the `lib/` ambient resolvers
   listed in step 4's boundary.

### Post-phase (risk mitigations)

1. [measure_noise_band] The baseline is a **sample, not a threshold**. In the
   "t1794 baseline" section, retain every raw run value (step 7) and state the
   margin rule children 6 and 11 use: collect n ≥ 5 independent runs per
   configuration with the same script, same interpreter and same task tree;
   report the margin as the **difference of medians**, always alongside both
   samples' min–max; call it a saving or regression **only when the two
   samples do not overlap at all** (complete separation of two 5-samples ⇔ the
   exact Mann–Whitney extreme, two-sided p = 2/252 ≈ 0.008 under
   exchangeability), otherwise "within observed variation". Never classify from
   fewer than 5 runs, and never derive a threshold from the baseline's own
   spread. Raw values stay recorded so a later child can apply a different test.
2. [golden_change_protocol] Make a golden failure self-explaining in
   `tests/test_board_keymap_characterization.py`: the failure message renders
   `_diff_bindings` / `_diff_matrix` as readable lines (`+ added row`,
   `- removed row`, `~ changed row`, `<filter>/<focus> <action>: <old> → <new>`)
   and names the rule (children 5 and 6: must stay green unchanged; any other
   task: update the golden deliberately and name the change in its own plan).
   A negative control asserts the rendered message for the one-row-removed and
   one-cell-flipped copies names the removed row / flipped cell. Add the golden
   to `## Notes for sibling tasks` so child 9's notes to board tasks mention it.

## Verification

- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`
  (check `${PIPESTATUS[0]}` if piped).
- `~/.aitask/venv/bin/python -m pytest tests/test_board_package_contract.py
  tests/test_board_fixture_harness.py tests/test_board_keymap_characterization.py -q`
  green.
- Red runs recorded in this plan: `OwnDirInsertTests` red on HEAD before
  step 1's edit; each negative control red when its checker is neutered — done
  in-process (`python -c` imports the test module, replaces the checker with
  `lambda *a, **k: []`; for `_c2_findings` also variants that ignore `fresh`
  and ignore `calls`; for `_ambient_task_path_reads` a variant that skips
  function/lambda bodies — the pre-revision scope — which must turn negative
  control (iv) red), runs that TestCase via `unittest`, never by editing repo
  files.
- `bash tests/test_no_lib_to_tui_import.sh`, `bash tests/test_no_raw_tmux.sh`,
  `python -m pytest tests/test_task_dir_module_constants.py
  tests/test_shortcut_scopes.py -q`, `bash tests/test_shortcuts_registry_coverage.sh`
  green; `shellcheck tests/perf/board_footprint.sh`.
- 20 raw + 4 summary footprint lines, and the margin rule, present in the aidoc.
- `ait board` boots in a tmux pane on a private socket and `q` quits.

## Notes for sibling tasks

C5 inventory (re-grep of `board/aitask_board.py` in `tests/`, `lib/`,
`.aitask-scripts/`; finalized in step 8):
- Path-keyed, must follow moved code: `lib/shortcut_scopes.py:48`
  (`KNOWN_BINDING_SOURCES`; children 6, 7);
  `tests/test_mark_glyphs_single_source.py:82,117,132` (+ its negative
  controls `:341–353`; child 2); `tests/test_no_raw_tmux.sh:56` (unchanged —
  raw-tmux sites stay); `tests/test_board_reference_doc_literals.py`
  (children 2, 3); `tests/test_metadata_writer_inventory.py:85,130,282`
  (`aitask_board.py::save_metadata` / `::_write_user_layer` keys; child 4);
  `tests/test_task_lock.sh:670` (sed-extracts a regex literal from
  `aitask_board.py`; whichever child moves it); `tests/test_task_dir_module_constants.py`
  (positive control, untouched); `tests/test_shortcuts_registry_coverage.sh:31`
  (child 6); `tests/test_board_fixture_harness.py` `_canonical_board_imports`
  (now reads `board_fixture.BOARD_MODULE_NAMES`).
- Docstring/comment-only mentions (update when the cited code moves):
  `tests/test_record_protocol.py:14,133`, `tests/test_atomic_task_writes.py:102`
  (Task.save → child 4), `tests/test_keybinding_registry.sh:34`,
  `tests/test_monitor_completed_status.py:163`, `tests/test_textual_markup_structure.py:8`,
  `lib/followup_kinds.py:22` (child 3), `lib/topic_semantics.py:3`,
  `lib/board_columns.py:8,103,137`, `lib/record_protocol.py:34`,
  `brainstorm/widgets.py:799`, `board/aitask_merge.py:34`.
- Launcher, unchanged: `aitask_board.sh:27`.
- Every new `board/*.py` must be added to `board_fixture.BOARD_MODULE_NAMES`
  (drift test) and, if it owns a `patch.object` target, bare-imported by
  `aitask_board.py`. No `board/*.py` may use a dynamic import (deny-by-default,
  exact-expression allowlist).
- C2 applies to lazy reads too: a moved function that called `task_dir()` /
  `metadata_dir()` / read `TASK_DIR` — even inside a function body — must take
  the resolved path as a parameter instead (child 3's `load_local_project_name`,
  child 4's `TaskManager`). Calls into the `lib/` ambient resolvers are allowed
  only where the canonical board already makes them (boundary in step 4).
- The C2 runtime check runs in a fresh subprocess and fails on a sibling that
  was already imported before the fixture load — do not "fix" such a failure by
  importing the sibling earlier; the fix is to stop resolving paths in the
  sibling.
- `tests/test_board_keymap_characterization.py` golden: children 5 and 6 keep
  it unchanged; any other board task that adds a binding or a `check_action`
  gate updates it deliberately and names the change (child 9: include this in
  the notes to board tasks, e.g. t1647_5).
- Footprint margins: `tests/perf/board_footprint.sh --runs 5` per
  configuration; apply the recorded margin rule (difference of medians, both
  ranges shown, "saving/regression" only on complete separation).

## Risk

### Code-health risk: low
- Golden brittleness across concurrent board work: the characterization golden pins every `KanbanApp` binding and the `check_action` matrix, so any pending task that adds a board binding or gate (t1647_5's By-Trail command explicitly) must update it, and a careless regeneration would hide a real regression · severity: low (residual — addressed by inline post-phase golden_change_protocol) · → mitigation: inline post-phase golden_change_protocol
- Repo-wide structural scans (C1 static + dynamic over `.aitask-scripts/` + `tests/`, the widened canonical-import guard) could false-positive and block unrelated work · severity: low · → mitigation: none (each guard green on the current tree, structural not substring, dynamic rule keyed on literal `board`/dot-relative strings repo-wide and deny-by-default only inside `board/`, negative controls per form)
- The own-dir insert puts `board/` at `sys.path[0]` in every board process; a future `board_*` basename equal to a `lib/` module would shadow it · severity: low · → mitigation: none (the basename guard never exempts `board/`)
- The footprint script drives tmux; a mistake could touch the live `ait` server · severity: low · → mitigation: none (private `-L ait_footprint_$$` socket, `kill-session` only, manual script)

### Goal-achievement risk: low
- Baseline noise: cold-start (and to a lesser degree RSS) varies with host load, scheduling and cache state, so a small sample may make the signed margins children 6/11 report uninterpretable · severity: low (residual — addressed by inline post-phase measure_noise_band) · → mitigation: inline post-phase measure_noise_band
- A runtime C2 check that inspects cached siblings could pass without exercising the failure it guards · severity: low (residual — addressed by design: fresh subprocess, sentinel `TASK_DIR`, `sys.modules` snapshot, fail-closed staleness finding with its own negative control) · → mitigation: none
- A sibling resolving the task dir lazily cannot be observed by any module-attribute check until a behaviour path runs · severity: low (residual — addressed by design: the static C2 rule is position-independent, and negative control (iv) executes a deferred read after restoration to prove both the divergence and the flag) · → mitigation: none
- `lib/` functions that resolve the task dir internally stay reachable from siblings (pinned trail seam `discover_trails` among them), so C2 does not make the board modules fully tree-agnostic · severity: low · → mitigation: none (explicit, documented boundary — pre-existing `lib/`-layer behaviour the canonical board already has; C6 keeps `lib/` out of scope)
- The C2 runtime check and the patch-pairing check are vacuous until child 2 adds modules; their discriminating power rests on negative controls alone · severity: low · → mitigation: none (data-driven by design; anti-vacuity asserted)
- The basename guard cannot be fully strict: `applink/`↔`chatlink/` already collide on `paths.py`/`audit.py` and are pinned · severity: low · → mitigation: none (stale pin fails; `board/` never pinnable; defect routed via Step 8b)

### Planned mitigations
- timing: post-phase | name: measure_noise_band | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — baseline noise making later signed margins uninterpretable | desc: n>=5 independent runs per configuration with raw values retained; margins reported as a difference of medians with both ranges, classified only on complete sample separation
- timing: post-phase | name: golden_change_protocol | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — characterization golden brittleness across concurrent board work | desc: readable golden-diff failure message naming the update rule, pinned by a negative control, and a sibling note routing the rule to board tasks via child 9

Post-inline reassessment (one pass against the augmented plan): code-health
**medium → low** — the one medium item is bounded by a self-explaining golden
failure and a routed update rule; goal-achievement **medium → low** — the
baseline is a retained n=5 sample with a separation-based margin rule, and both
C2 halves now exercise the failure they guard (fresh import with a sentinel,
position-independent static rule proven by a deferred-read control).

## Revision notes (plan review, before approval)

- C2 runtime check moved from an in-process `sys.modules` inspection to a fresh
  subprocess with a pre-load snapshot and a fail-closed staleness finding (a
  cached sibling was reused, not re-executed, so the check could pass vacuously).
- C1 gained dynamic-import coverage: alias-tracked literal `board`/dot-relative
  forms repo-wide, and deny-by-default for any dynamic import inside `board/`.
- The noise mitigation no longer derives a threshold from a two-run spread:
  n ≥ 5 independent runs, raw values retained, separation-based classification.
- C2 static rule is now position-independent: `task_dir` / `metadata_dir`
  references and `TASK_DIR` env reads are rejected in function and lambda
  bodies too (the task's own context names the lazy read as a silent failure);
  the runtime harness loads with a sentinel `TASK_DIR` so a wrong binding or a
  deferred read is distinguishable from the default, and negative control (iv)
  invokes a deferred resolver after restoration. The `lib/`-layer ambient
  resolvers are stated as an explicit boundary.

## Post-implementation

Task-workflow Step 8 (review, path-scoped code commit `test: … (t1794_1)`,
plan commit), Step 8b (upstream defect: applink/chatlink basename collision),
Step 9 (gates run, archive `t1794_1`).
