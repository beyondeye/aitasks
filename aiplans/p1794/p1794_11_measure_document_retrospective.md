---
Task: t1794_11_measure_document_retrospective.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_12_manual_verification_split_board_monofile_and_standalone_trai.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-22 18:05
---

# p1794_11 — Measure, document, retrospective (verified 2026-09-22)

## Context

Last implementation child of t1794, the split of the board mono-file into a
package plus the stand-alone `ait trails` TUI. The parent requires every
memory or cold-start claim to be a **signed margin measured in one session**
(C8, "Margin rule" in `python_tui_performance.md`). It also left the
interpreter for `ait trails` to a real t718_6-protocol benchmark. This child
closes both, updates the developer docs to the new package layout, and runs
the retrospective.

**Rebase check (done at verify time):** children 1–10 are archived (10
archived children). The last board commits are t1794_8 `387d8cb20`, t1794_7
`4b76a992b` and t1839 `dec8a3a12`, so the tree has not moved since t1794_8. Ten
other tasks are `Implementing`, and none of them touches `board/`: the dirty
worktree files are t1848's agent_sessions/monitor edits. Current sizes:
`aitask_board.py` has 6,843 lines and 26 classes; the package has 16,377 lines
across 11 modules.

**Corrections to the original plan found during verification:**
- (c) in the retrospective is already resolved. t1794_6 added
  `exclude_modules` / `_shortcuts_exclude_sources`, so `?` in `ait trails`
  no longer imports the board, and t1794_7 extended that to exclude
  `board_detail_screen`. The retrospective records this and files no task.
- t1794_8 noted that `test_board_detail_screen.py` was missing from
  `MIGRATED_MODULES`. That is already fixed (`test_board_fixture_harness.py:385`),
  so no follow-up is needed.
- The docstring anchors in `tests/lib/board_fixture.py` are stale. Their new
  homes are `refresh_lock_map` at `board_task_manager.py:793-798`,
  `load_trail_blob` in `lib/trail_discovery.py`, `CREATE_SCRIPT` /
  `BRAINSTORM_TUI_SCRIPT` / `GATES_REGISTRY_FILE` at `aitask_board.py:221/222/223`,
  `agent_command_screen.py:1000`, and `sync_action_runner.py:218`
  (`_SYNC_SCRIPT`).
- `CLAUDE.md:433` already lists `trails` (child 6). Only `:143` (the board
  file-map line) changes.
- `tui_conventions.md` never mentions `trails`. The intro list at `:3-5`
  gains it.

## Steps

1. **Footprint (C8): one session, serial, interleaved, isolated trees.**
   - **Two detached worktrees** in the scratchpad: `new` at HEAD and `old` at
     `c52534f14` (t1794_1's commit, which is the pre-extraction board plus
     the own-dir `sys.path` insert and `__init__.py`, i.e. the code the
     t1794_1 baseline measured). Link both to the **same** `.aitask-data`
     with `aitask_init_data.sh --link-worktree`, so the task tree is
     identical. Both must be clean (`changed=none`). `git diff c52534f14 HEAD
     -- tests/perf/` is empty (verified), so both trees carry the same
     measuring script. Remove both worktrees afterwards.
   - **Strictly serial, never in the background, and nothing else of mine
     running** (no test suite, no Pilot benchmark). The samples compete only
     with the host's normal load.
   - **Interleaved round-robin:** 5 rounds. Each round runs every
     configuration once with `--runs 1`, in this fixed order per
     interpreter: board@old → trails@new → board@new → ceiling@new.
     CPython goes first in each round, then PyPy. That makes 8 configurations
     × 5 runs = 40 independent samples, and host drift spreads over every
     configuration instead of landing on one. (`--runs 1` prints a "< 5"
     warning on stderr. The rule's n ≥ 5 holds per configuration after
     aggregation.)
   - Retain the raw lines **in command order**, each preceded by its round and
     configuration label, plus each tree's provenance line. Medians and
     min–max come from a scratch aggregation over those lines. Host `load1` is
     read from the raw lines.
2. **Pilot benchmark (t718_6 protocol) for `trails_app`.** Run strictly after
   step 1 finishes, and serially per interpreter. Add a new manual script,
   `tests/perf/trails_pilot_bench.py`, which is not `test_*`-named and is
   never collected. It reuses the settle discipline of
   `tests/test_trails_app.py:99-150` (`_settle`: `workers.wait_for_complete()`
   ×3, then forced `screen.refresh(layout=True)` + `pause` until the card set,
   focused widget and screen type are stable across two pauses, bounded at 40)
   and its `_wait_screen` / `_wait_until`. It runs against this repo's real
   task tree through `TrailsApp(tasks_dir=…)`, constructed like
   `bf.make_trails_app`, with `run_test(size=(160,48))`.
   - **Deterministic trail:** `--trail <handle>` (chosen once, recorded in the
     doc). After `_settle` on boot, the script moves the selector highlight to
     that handle (it asserts the handle is present and fails otherwise),
     presses `enter`, and asserts `TrailsScreen` plus the selected handle.
   - **Deterministic drift:** as in the keyboard-flow test,
     `board_trail_screen.load_trail_blob` returns the doc cached at selection
     and `run_trail_drift` returns a fixed verdict. The subprocess latency is
     identical under both interpreters, so it is kept out of the interpreter
     comparison. Boot-time discovery stays real, as it did in t718_6.
   - **Settling and an assertion after every step:** boot → settle → select
     trail → settle, and assert that `TaskCard`s exist and a card is focused →
     `enter`, wait for `TrailDetailScreen` → `escape`, settle, assert a focused
     card → `v`, wait for `TrailSummaryScreen` → `escape`, settle, assert a
     focused card → `d`, settle, assert `app._trail_drift[0]` equals the
     patched verdict → 10× `down`, each followed by `_wait_until` (focused card
     changed, or at the wave end) → final settle, and assert no live workers.
     **Any failed assertion aborts the run.** A repetition is recorded only if
     every state was reached.
   - 5 warmup and 8 measured repetitions in one process per interpreter, each
     timed with `perf_counter` around the whole `run_test` block. The script
     prints every repetition (warmups labelled) and the measured median. Cold
     start comes from step 1's `trails_app` `coldstart_ms`.
   - **Verdict rule (t718_6 plus the margin rule):** SWITCH to
     `require_ait_python_fast` only if PyPy's median steady state is at least
     10% faster **and** the two 8-samples do not overlap, **and** the
     cold-start regression is acceptable for the modal session length.
     Otherwise KEEP CPython and leave `aitask_trails.sh` unchanged. On SWITCH:
     edit `aitask_trails.sh:12` and extend the `tui_conventions.md` scope
     heading, `:7-11`, and the `AIT_USE_PYPY` table at `:39-63`.
3. **`aidocs/framework/python_tui_performance.md`.** Add a new section
   `### t1794_11 — final footprint and trails interpreter verdict (2026-09-22)`
   after the t1794_6 section. It contains:
   - the protocol (round-robin, `--runs 1` × 5 rounds, command order
     retained), both provenance lines, the parent-task count and the load
     range;
   - an 8-row table (board@old, board@new, trails, ceiling × 2 interpreters;
     median plus min–max);
   - **C8 signed margins, all in-session and same-tree**, classified by the
     margin rule: board@new − board@old (the extraction's own effect),
     trails − board@new, and trails − ceiling. "Saving" or "regression"
     appears only where the samples separate;
   - the t1794_1 figures, in a separate paragraph titled **"Historical trend
     (not a C8 comparison)"**, as cross-session absolutes with **no saving or
     regression claim**, noting that the in-session board@old row supersedes
     them for any claim;
   - the Pilot table (steady state + cold start per interpreter), the trail
     handle, the patched seams, the KEEP or SWITCH verdict, and all raw lines
     (footprint in command order, Pilot per repetition) in `<details>`.

   Add a t1794_11 row to "Related Tasks". Write current-state prose only.
4. **`aidocs/framework/tui_conventions.md`.** Add `trails` to the intro list.
   Add a new section, "The board package (`board/`): layout and import
   contract", covering:
   - the file map (module → contents, one line each, both Apps);
   - C1: flat bare-name imports, the `board_` prefix and unique basenames, no
     `import aitask_board` from any sibling, and helpers the siblings need
     injected as callables (`make_task_detail_screen`), with the bare-import
     pairing for patch targets;
   - C2: no module other than `aitask_board.py` resolves the task dir, so paths
     are passed as parameters (`tasks_dir`, `TrailsApp(tasks_dir=…)`,
     `--tasks-dir` from the launcher);
   - C10: `TrailsApp` registers under the owning scope `board` with the same
     `TRAIL_BINDINGS` objects, and unsupported `M`/`S` stay declared but are
     hidden and refused (the memory rule "shared screen = owning TUI's
     shortcut scope");
   - the per-new-module guard checklist: `BOARD_MODULE_NAMES`, the
     `HeadlessImportTests` probe, the anti-vacuity sibling tuple, and
     `MIGRATED_MODULES`;
   - pointers to the enforcing tests (`test_board_package_contract.py`,
     `test_board_fixture_harness.py`, `test_trails_app.py`).
5. **`CLAUDE.md:143`.** The board line becomes a two-line package description
   naming `aitask_board.py` (KanbanApp) and `trails_app.py` (the `ait trails`
   App), with a pointer to the new tui_conventions section for the module map.
6. **`tests/lib/board_fixture.py` docstring.** Repoint the stale anchors listed
   above. The docstring is text only.
7. **`aidocs/framework/aitasks_extension_points.md`.** Decision: **no edit.**
   The doc covers framework surfaces (frontmatter, helper-script allowlists,
   hooks, install), and adding an App to a TUI package is already covered by
   the tui_conventions sections (four-part switcher registration, the shortcut
   manifest, and the new package section). A line here would duplicate them.
   Record this in the Final Implementation Notes.
8. **Retrospective** (recorded in the plan's Final Implementation Notes, with
   numbers):
   - (a) Further extraction. Judge it against the 26 residual classes and the
     measured board RSS. Default is **no follow-up**, because the residual is
     the planned end state and the board's RSS is dominated by Textual (see
     the ceiling), not by board code size. File a task only if the data
     contradicts this.
   - (b) Promotion to `lib/`. Only `board_widgets` (no board imports) and
     `board_task_model` (imports only `lib/board_columns`) qualify
     structurally. Promotion is justified only by a consumer outside `board/`,
     which is to be grepped. Without one: no follow-up.
   - (c) Resolved by t1794_6/7, so no follow-up.
   - Walk the parent's 7 acceptance criteria one by one, each with its evidence
     (test, number or page).

## Verification

- `bash tests/run_all_python_tests.sh` → the last line reads
  `PYTHON SUITE: PASSED` (check `PIPESTATUS`).
- `bash tests/test_serial_carveout_doc_drift.sh` is green (no carve-out
  change).
- `grep -n 'board/' CLAUDE.md` shows the package description.
- The perf doc has 8 in-session footprint rows (board@old and board@new
  included), the historical paragraph makes no claim, and it carries the Pilot
  table and verdict. Also,
  `aitask_trails.sh`'s resolver matches the verdict. If a switch happens:
  `shellcheck .aitask-scripts/aitask_trails.sh`.
- The fixture docstring anchors grep-resolve at the cited lines.
- No website page is touched, so `check_links.py` is not needed.

## Post-implementation

Step 9 of the task workflow: path-scoped commit (`documentation: … (t1794_11)`),
the `risk_evaluated` gate, then archive t1794_11. The parent archives after
t1794_12, the manual-verification sibling.

## Risk

### Code-health risk: low
- Docs could restate file maps or line anchors that later drift · severity: low · → mitigation: none (every anchor is grep-verified at write time; the section cites the enforcing tests rather than restating their rules)
- The new `tests/perf/trails_pilot_bench.py` could be collected by the suite · severity: low · → mitigation: none (not `test_*`-named and lives beside the existing manual `board_footprint.sh`; the suite run in Verification proves it)

### Goal-achievement risk: low
- Host load (many concurrent agents) can make cold-start and steady-state samples overlap, leaving margins "within observed variation" · severity: low · → mitigation: none (serial round-robin interleaving spreads drift across configurations; the margin rule classifies any remaining overlap honestly; an inconclusive benchmark resolves to KEEP CPython, the current state)
- A Pilot repetition could time a half-finished flow (async drift or re-mount still pending) and bias the verdict · severity: low · → mitigation: none (settle + per-state assertions from `test_trails_app.py`; a repetition that misses a state aborts instead of recording)
- The pre-extraction board at `c52534f14` might not boot against today's task data · severity: low · → mitigation: none (the footprint script fails closed; if so, the extraction delta is reported as unmeasured, never inferred)
- The Pilot workload depends on at least one real trail existing in this repo · severity: low · → mitigation: none (checked at run time; child 6's smoke used real trails)

## Final Implementation Notes

- **Actual work done:**
  - **Footprint (C8), 40 samples in one quiet session** (host load 1.09–1.81,
    the quietest of the three t1794 sessions): two isolated detached worktrees
    (`c52534f14` = the pre-extraction board, `85abc4217` = after children 2–8)
    linked to the **same** `.aitask-data`, both clean (`changed=none`), driven
    by a serial round-robin of `board_footprint.sh --runs 1` — 5 rounds ×
    {board@old, trails_app, board@new, ceiling} × {CPython, PyPy}. Results,
    signed margins and all 40 raw lines (in command order) are in
    `aidocs/framework/python_tui_performance.md`, section "t1794_11 — final
    footprint and the `ait trails` interpreter verdict".
  - **`tests/perf/trails_pilot_bench.py`** (new, manual, not `test_*`-named so
    no runner collects it — confirmed against the suite log): the t718_6 Pilot
    protocol for `trails_app`, 5 warmup + 8 measured reps in one process
    against the real task tree, with `_settle` + per-state assertions ported
    from `tests/test_trails_app.py` so a repetition that misses a state aborts
    instead of timing a half-finished flow.
  - **Docs:** the new perf section (incl. the corrected board LOC figures and a
    Related Tasks row); a new `tui_conventions.md` section "The board package
    (`board/`): two Apps, one flat-import contract" (file map, C1, C2, C10, the
    four-site guard checklist, the enforcing tests), `trails` added to that
    doc's intro list and to the empirically-verified CPython exceptions;
    `CLAUDE.md`'s board line rewritten as the package; `tests/lib/board_fixture.py`'s
    stale docstring anchors repointed.
- **The numbers (medians; a claim is made only where the 5-samples separate):**
  - **The split's own effect on the board** — RSS **−12.1 MiB under CPython**
    (176.4 < 187.9: a saving) but **+20.7 MiB under PyPy** (344.4 > 326.3: a
    **regression**, +6.4%). Cold start overlaps under both: no claim.
  - **`trails_app` − board@new** — RSS **−115.4 MiB** (CPython) and
    **−154.8 MiB** (PyPy); cold start **−35 ms** (CPython, separated) and
    within variation under PyPy.
  - **`trails_app` − ceiling** — +20.7 MiB (CPython), +77.9 MiB (PyPy).
  - **Pilot:** PyPy 7451 ms [7352–7731] vs CPython 8305 ms [8006–8584] —
    10.3% faster, no overlap; cold start +138 ms and RSS +130.8 MiB on PyPy.
- **Interpreter verdict: KEEP CPython** (user-confirmed at the threshold call).
  The 10.3% steady-state win clears the t718_6 bar by 0.3 points, while PyPy
  adds 138 ms per launch and 130.8 MiB RSS — more than the CPython **full
  board** (176.2 MiB) — which removes the light footprint the stand-alone
  exists for. `aitask_trails.sh` is unchanged (`require_ait_python`), so the
  `AIT_USE_PYPY` table and the fast-path scope line needed no edit.
- **Deviations from plan:** (1) the plan's "six footprint rows" became **eight**
  — the in-session board@old rows were added after review found the child-1
  figures cannot support a C8 claim; the t1794_1 numbers are now a
  "Historical trend (not a C8 comparison)" paragraph that makes no claim.
  (2) The round-robin uses `--runs 1` × 5 rounds instead of `--runs 5` per
  configuration, so host drift spreads across configurations. (3) Two extra
  doc fixes were made where the new text would otherwise contradict the file:
  the stale `aitask_board.py: 5200 LOC` line, and a `trails` row in the
  permanent-CPython exceptions list. (4) `aitasks_extension_points.md` was
  **not** edited (see Key decisions).
- **Issues encountered:** a task was archived mid-run, so the last two raw
  lines read `parent_tasks=423` instead of 424 — noted in the doc; RSS is
  insensitive to one task file. The first planning pass proposed reporting the
  cross-session child-1 comparison as a signed margin, running the
  configurations concurrently, and pressing `d` without settling; all three
  were corrected before implementation (see Deviations and the Pilot design).
- **Key decisions:**
  - Docstring anchors in `board_fixture.py` were repointed to **file-level**
    references rather than new line numbers: they had already drifted twice,
    and no test pins them.
  - No `aitasks_extension_points.md` line: that doc covers framework surfaces
    (frontmatter, helper-script allowlists, hooks, install). Adding an App to
    a TUI package is covered by `tui_conventions.md`'s switcher four-part rule,
    the shortcut manifest section and the new package section; a line here
    would duplicate them.
  - The Pilot patches `load_trail_blob` / `run_trail_drift` (interpreter-
    independent subprocess latency) but keeps boot-time `discover_trails`
    real, matching what t718_6 did for the board's refresh.
- **Retrospective (the parent's child-11 obligation):**
  - **(a) Further extraction — no follow-up.** The 26 residual classes of
    `aitask_board.py` (6,843 lines) are exactly the end state the parent's
    file map describes: `KanbanApp`, the Kanban render paths, the key map /
    `check_action`, the task-select and confirm modals, the module constants
    and the three injected helpers. The numbers say the remaining win is small
    and not where the code is: the CPython board sits at 176.2 MiB against a
    40.1 MiB ceiling that imports only Textual, Rich and yaml, and a further
    2,000 lines of Python would move a fraction of that 136 MiB, which is
    framework and widget-set cost. The one measured effect of extraction on
    RSS was −12.1 MiB (CPython) and **+20.7 MiB (PyPy)**, so more of the same
    is not a memory argument.
  - **(b) `lib/` promotion — no follow-up.** Only `board_widgets` (no board
    imports at all) and `board_task_model` (imports only `lib/board_columns`)
    qualify structurally. A grep for any consumer of `board_widgets`,
    `board_task_model` or `board_workflow_phase` **outside** `.aitask-scripts/board/`
    returns nothing, and C6 fixed `lib/` promotion as evidence-driven, not a
    default. Promoting a module only the board imports would add a layer
    boundary (`tests/test_no_lib_to_tui_import.sh`) for no consumer.
  - **(c) The C10 `?`-editor limitation — already resolved, no follow-up.**
    t1794_6 replaced the parent plan's "documented limitation" with
    `register_scope_bindings(exclude_modules=…)` and
    `ShortcutsMixin._shortcuts_exclude_sources`, and t1794_7 extended the
    exclusion to `board_detail_screen`; `?` inside `ait trails` therefore
    never executes the board. `tests/test_shortcut_scopes.py` and the trails
    probe pin it.
  - Also checked and closed: t1794_8's note that `test_board_detail_screen.py`
    was missing from `MIGRATED_MODULES` — it is present
    (`tests/test_board_fixture_harness.py:385`), so no follow-up is needed.
- **Acceptance-criteria walk (parent t1794), with the evidence for each:**
  1. *`ait board` behaves exactly as before* — `bash tests/run_all_python_tests.sh`
     → `PYTHON SUITE: PASSED (runner=pytest, exit=0)` at this SHA, including
     `test_board_keymap_characterization.py` (child 1's golden key map /
     `check_action` matrix) and the 4.5k-line `test_board_bytrail_view.py`.
     Live keys/views/modals are t1794_12's checklist.
  2. *Stand-alone trail TUI, switcher-reachable* — `trails_app.py` +
     `aitask_trails.sh`; `tests/test_trails_app.py` (20 tests) and the registry
     / switcher tests; child 6's tmux smoke (`j`→`i` and back, `TUI_NAMES`
     contains `trails`).
  3. *`aitask_board.py` materially smaller; `board/` a package with the flat-import
     contract* — 14,102 → **6,843 lines**, 92 → **26 classes**; no trail,
     TaskManager, detail-screen or column-dialog class remains
     (`tests/test_board_package_contract.py`, `tests/lib/board_single_home.py`
     pins).
  4. *Memory and cold start measured before/after in the same interpreter and
     task tree, reported as signed margins; the stand-alone's RSS reported
     against the board's* — this task: the 8-row table and the margins above,
     both worktrees on one `.aitask-data`, one session.
  5. *No moved module binds `TASKS_DIR`-derived constants at import* —
     the C2 guard in `tests/test_board_fixture_harness.py` (static AST scan
     over every board module plus the fresh-load runtime check), green in the
     suite run above.
  6. *Every task in the notes list has received a note* — child 9, plus the
     two notes child 8 sent to t1441 / t1442 when its move invalidated their
     line references.
  7. *Website documents the stand-alone TUI* — child 10:
     `website/content/docs/tuis/trails/{_index,how-to,reference}.md`, the TUI
     index and board pages updated, `skills/aitask-trail.md:87` rewritten;
     `check_links.py --build` clean there. No website page is touched by this
     child.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t1794_12 (manual verification):** nothing in this child changes runtime
    behaviour — the only non-doc file added is a manual benchmark script — so
    no checklist item needs adding. If a trails item needs a repeatable
    keyboard flow, `tests/perf/trails_pilot_bench.py --trail <handle>` drives
    boot → select → detail → summary → drift → 10× down with assertions, and
    `--list` prints the discovered handles.
  - **Any future board extraction:** re-measure with the two-worktree
    round-robin recorded in the perf doc, not against the figures in it —
    cross-session absolutes on this host drift ~10%, the size of the effects
    being measured. Note that the PyPy board regressed +20.7 MiB across this
    split; if `ait board`'s PyPy routing is ever revisited, that is the
    starting number.
