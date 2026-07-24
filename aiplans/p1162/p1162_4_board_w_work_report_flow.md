---
Task: t1162_4_board_w_work_report_flow.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_5_work_report_documentation.md, aitasks/t1162/t1162_6_manual_verification_add_manager_facing_work_report_skill_and.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_*_*.md
Worktree: none (profile 'fast' — current branch, current directory)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-23 18:17
---

# Plan: t1162_4 — Board `w` Work Report flow + Pilot tests

## Context

Adds the contextual, footer-visible `w` (Work Report) action to the board
TUI: column multi-select → task multi-select → shared agent-command dialog
launching `/aitask-work-report` with the exact board-reviewed selection.
Requires the t1162_2 `work-report` operation (command resolution) and pins
membership equivalence against the t1162_1 gatherer at flow level. Parent
design: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_4 section). `aidocs/framework/tui_conventions.md` has been read
(footer-visibility, shortcut-manifest, and modal conventions applied below).

**Plan re-verified 2026-07-23** against the live tree (verify path). All
structural assumptions CONFIRMED; only line numbers drifted and two
`AgentCommandScreen` parameter names were corrected (see Anchors). Sibling
deliverables confirmed in place: `aitask_work_report_gather.sh` +
`lib/work_report_gather.py` (contract incl. `ERROR:task_order_changed`),
`work-report` in `aitasks/metadata/codeagent_config.json` (default
`claudecode/sonnet4_6`, fresh-window operation), and
`.claude/skills/aitask-work-report/SKILL.md` (explicit `--columns`/`--tasks`
skips its membership prompts).

## Anchors (verified 2026-07-23)

All in `.aitask-scripts/board/aitask_board.py` unless noted:
- `KanbanApp` :4371, `_shortcuts_scope = "board"` :4372; `BINDINGS`
  :4574-4626; **no `Binding("w", ...)` anywhere** — `w` is free.
- Model binding `Binding("p", "pick_task", "Pick")` :4604; handler
  `action_pick_task` :5705-5745; its result callback `on_pick_result`
  :5733-5742 (`"run"` → `run_aitask_pick`; `TmuxLaunchConfig` →
  `launch_in_tmux`, then `maybe_spawn_minimonitor(result.session,
  result.window)` when `new_window`).
- `check_action` :4640-4751. Derived-view hiding pattern:
  `self.base_filter in ("inflight", "bytopic")` (e.g. :4738-4739). Nav keys
  already pass through to a focused `SelectionList` (:4680-4682) — our modals
  get arrow navigation for free.
- `_focused_card()` :5348-5351; `_focused_placeholder()` :5362-5367 (returns
  a focused `CollapsedColumnPlaceholder` **or `EmptyColumnPlaceholder`**);
  `_get_focused_col_id()` :5462-5470 returns `placeholder.column_id` on
  fallback. `CollapsedColumnPlaceholder` :1048-1061;
  `EmptyColumnPlaceholder` :1064-1077 (`can_focus = True`; covers a column
  with no tasks AND one whose cards are all hidden by filter/search).
- Renderer column intersection :4868-4870: `for col_id in
  self.manager.column_order: conf = next((c for c in self.manager.columns if
  c["id"] == col_id), None); if conf:` — **orphan `column_order` ids with no
  `columns` entry are silently dropped from the board**, and the gatherer
  rejects them (`ERROR:unknown_column`). Any column list this task builds
  must use this same renderable intersection.
- Direct-run precedent: `run_aitask_pick` :6003-6019 parses a task filename
  and hardcodes `invoke pick <num>` — NOT reusable for a column-scoped
  launch. `run_codeagent_operation` :6021-6038 is the model for a dedicated
  worker (`@work(exclusive=True)`, `find_terminal()` → `spawn_in_terminal`,
  else `self.suspend()` + `subprocess.call`, error notify, reload+refresh).
- Dry-run None precedent: `action_pick_task` :5719 guards `if full_cmd:` and
  falls back to direct run when `resolve_dry_run_command` returns `None`
  (wrapper failure / timeout / missing binary — `agent_launch_utils.py:222-229`).
- Columns: `TaskManager.columns` :437 / `column_order` :438 (defaults
  `DEFAULT_COLUMNS` :134, `DEFAULT_ORDER` :139); `get_column_tasks(col_id)`
  :635-645 — filters `board_col`, sorts by
  `(normalize_board_idx(t.board_idx), t.filename)` (the t1162_1 D2 shared
  key), operates on `self.task_datas` directly → ignores search/filters (the
  required full-column source); dynamic Unsorted id `"unordered"`, pickers
  prepend at index 0 (:6399, :6424; `_move_column` :6142).
- Multi-select modal model: `IssueTypeFilterScreen` :3073-3126
  (`ModalScreen`, no `_shortcuts_scope` — plain modals need no shortcut
  registration; `SelectionList[str]`, Space toggles natively, Enter confirms
  via `on_key` → `dismiss(self._selected())`, Escape → `action_cancel`
  dismisses `None`).
- Launch: `AgentCommandScreen` (`lib/agent_command_screen.py:156`, `__init__`
  :363-377). **Param names corrected:** positional `title, full_command,
  prompt_str`, then keyword `default_window_name`, `operation`,
  `operation_args`, `default_agent_string`, `skill_name` (all confirmed).
  `resolve_dry_run_command(project_root, operation, *args, ...)`
  (`lib/agent_launch_utils.py:199-229`); `resolve_agent_string(project_root,
  operation)` (:232-252).
- ShortcutsMixin auto-registers new `KanbanApp.BINDINGS` under scope "board"
  — no extra wiring for customizability.
- Gatherer: `.aitask-scripts/aitask_work_report_gather.sh` →
  `lib/work_report_gather.py` (`build_parser` :486; `--columns` :496,
  `--tasks` :497 "order is significant"; `task_order_changed` emission :592).
  Board-side `--tasks` built from `get_column_tasks` output validates by
  construction (shared ordering key — t1162_1 final notes). Do NOT send
  `--velocity-model`/`--velocity-window` from the board.

**Concurrent-session caution:** `aitask_board.py` currently carries
uncommitted foreign hunks (t1210_2 topic-semantics extraction to
`lib/topic_semantics.py`). At Step-8 commit time, stage **hunk-scoped**
(`git add -p` or equivalent) so only this task's hunks land in the
`(t1162_4)` commit; verify `git diff --cached` content, not just paths.

## Implementation steps

1. **Binding:** add `Binding("w", "work_report", "Work Report")` to
   `KanbanApp.BINDINGS` (near `p` :4604).
2. **Gating in `check_action`:** for `action == "work_report"`: return
   `False` when `self.base_filter in ("inflight", "bytopic")`; return `False`
   when `self._get_focused_col_id()` is None (no focused card or placeholder
   identifying a column — covers collapsed AND empty placeholders).
   Otherwise `True`.
3. **`WorkReportColumnSelectScreen`** (new `ModalScreen` in
   `aitask_board.py`, model `IssueTypeFilterScreen` — no `_shortcuts_scope`
   needed): options = for each col in
   (`["unordered"] if unordered has tasks else []`) + **the renderable
   configured intersection** — `[col_id for col_id in column_order if a
   manager.columns entry with that id exists]`, titles from the matching
   `conf["title"]` (mirrors the renderer :4868-4870; a stale `column_order`
   entry with no `columns` definition is NOT offered — it isn't on the board
   and the gatherer would reject it as `unknown_column`):
   `Selection(title, value=col_id, initial_state=(col_id == focused_col))`.
   Space toggles, Enter confirms (dismiss list of selected col_ids in the
   presented order), Escape cancels (dismiss None). Empty confirm is allowed
   here; the caller notifies and aborts.
4. **`WorkReportTaskSelectScreen`** (new `ModalScreen`): for each chosen
   column in board order, one `Selection` per task from
   `manager.get_column_tasks(col_id)` — label prefixed with the column
   (SelectionList has no native section headers — prefix labels, e.g.
   `[now] t123 name`), value task id, `initial_state=True` (ALL checked).
   Enter confirms → dismiss ordered list of (col_id, task_id) preserving the
   DISPLAYED order restricted to still-selected ids; Escape cancels (None).
5. **`run_work_report(full_command)`** (new `@work(exclusive=True)` worker —
   the dedicated column-scoped direct-run path; `run_aitask_pick` is
   filename-bound and NOT reusable): takes the full **shell command string**
   and dispatches `["sh", "-c", full_command]` (the tui_switcher "run"
   pattern, `lib/tui_switcher.py:1188-1194`) — NOT rebuilt default wrapper
   args, because `AgentCommandScreen.run_terminal` stores user command edits
   into `screen.full_command` and the agent/profile controls regenerate it;
   rebuilding argv here would silently discard those overrides.
   `find_terminal()` → `spawn_in_terminal`, else `self.suspend()` +
   `subprocess.call` with the error notification; then
   `self.manager.load_tasks()` + `self.refresh_board()` (no filename to
   refocus — column-scoped).
6. **`action_work_report`:** orchestrate: `focused_col =
   self._get_focused_col_id()` → push column screen → on result push task
   screen → on result compose
   `cols_csv = ",".join(chosen_cols_in_board_order)` and
   `tasks_csv = ",".join(selected_task_ids_in_displayed_grouped_order)`
   (THE reviewed sequence — the gatherer's `task_order_changed` check
   defends exactly this order; never re-sort). Empty columns →
   `self.notify("No columns selected")`; empty tasks →
   `self.notify("No tasks selected")` — no launch. Then:
   ```python
   full_cmd = resolve_dry_run_command(Path("."), "work-report",
                                      "--columns", cols_csv, "--tasks", tasks_csv)
   if full_cmd:
       agent_string = resolve_agent_string(Path("."), "work-report")
       self.push_screen(AgentCommandScreen(
           "Work Report", full_cmd,
           f"/aitask-work-report --columns {cols_csv} --tasks {tasks_csv}",
           default_window_name="agent-work-report",
           operation="work-report",
           operation_args=["--columns", cols_csv, "--tasks", tasks_csv],
           default_agent_string=agent_string,
           skill_name="work-report"), callback)
   else:
       self.run_work_report(cols_csv, tasks_csv)
   ```
   The `if full_cmd:` guard mirrors `action_pick_task` :5719-5745 —
   `resolve_dry_run_command` returns `None` on wrapper/config/timeout
   failure, and constructing `AgentCommandScreen` from `None` would show a
   broken dialog; the fallback launches the reviewed selection directly via
   `run_work_report(shlex.join([str(CODEAGENT_SCRIPT), "invoke",
   "work-report", *op_args]))` (no dialog exists, so the wrapper default IS
   the current command). Result callback (work-report variant of
   :5733-5742): `"run"` → `self.run_work_report(screen.full_command)` (the
   dialog's stored/regenerated command — NOT `run_aitask_pick`, there is no
   task filename, and NOT rebuilt default args, which would discard in-dialog
   edits and agent/profile overrides); `TmuxLaunchConfig` → `launch_in_tmux`
   + `maybe_spawn_minimonitor` when `new_window`; then `refresh_board()`.

## Tests

Python tests under `tests/` (unittest + asyncio Pilot). Harness patterns
verified: `test_board_footer_visibility.py` (chdir REPO_ROOT + real
`KanbanApp` via `app.run_test()` + Pilot, stubbed `_focused_card`,
`check_action` + `active_bindings` assertions); construction-spy canon =
`tests/test_tui_switcher_agent_launch.py` (`patch.object(alu,
"resolve_dry_run_command", ...)` + `mock_app.push_screen.call_args` +
`assertIsInstance(screen, AgentCommandScreen)` + prompt/operation asserts).

1. **Footer visibility:** `w` absent in inflight and bytopic views; absent
   with no focused column; present with a focused card in a persistent kanban
   view; present with a focused collapsed placeholder; **present with a
   focused `EmptyColumnPlaceholder`** (both the truly-empty-column case and
   the all-cards-hidden-by-search case — this supported entry point must not
   regress unnoticed).
2. **Shortcut registration:** `bash tests/test_shortcuts_registry_coverage.sh`
   passes (new binding registered under scope "board").
3. **Defaults:** column screen opens with focused column checked (and
   `unordered` offered only when it has tasks); task screen opens with all
   tasks checked.
3b. **Stale `column_order` entry:** with a `column_order` containing an id
   that has no `columns` definition, the column screen does NOT offer it
   (parity with the renderer's intersection and the gatherer's
   `unknown_column` rejection).
4. **Full-column under filter/search:** apply a search/filter that hides a
   task, open the flow → the hidden task still appears in the task screen.
5. **Cancellation:** Escape at column screen → no task screen, no launch;
   Escape at task screen → no launch.
6. **Empty selections:** deselect-all at either screen → notify, no launch.
7. **Ordering + exact args:** with a known fixture, confirm the composed
   `--columns`/`--tasks` csvs match the displayed grouped order after
   exclusions (spy on `resolve_dry_run_command`/`push_screen` args per the
   construction-spy canon — never exit codes).
7b. **Direct-run path ("Run" result):** after pushing the dialog, simulate a
   stored in-dialog command override (mutate `screen.full_command`), invoke
   the callback with `"run"`, and assert `run_work_report` is dispatched
   with the OVERRIDDEN command (not rebuilt default args) and
   `run_aitask_pick` is never touched. Separately assert the worker shells
   out `["sh", "-c", <command>]` verbatim (spy `spawn_in_terminal`).
7c. **Dry-run resolution failure:** patch `resolve_dry_run_command` to
   return `None` → no `AgentCommandScreen` is pushed and the flow falls back
   to `run_work_report` with the shlex-joined wrapper default carrying the
   same reviewed args (no broken dialog, no silent drop of the selection).
8. **Round-trip equivalence (flow-level oracle):** shared fixture tree with
   Unsorted tasks, `boardidx` ties, archived tasks, a parent with children, a
   task missing `boardcol`, and a phantom layout stub (frontmatter with ONLY
   `boardcol`/`boardidx`). Compute the args the board flow would launch, run
   `.aitask-scripts/aitask_work_report_gather.sh` with them, and assert the
   gatherer's `TASK:` membership AND order equal the board's
   `get_column_tasks` per column. Reuse the headless-`TaskManager`-with-
   `TASK_DIR` machinery from `tests/lib/work_report_equiv.py` (t1162_1's
   data-layer oracle) rather than reinventing it; this test is the
   higher-level flow oracle. Any divergence fails here — reconcile by fixing
   the gatherer to match the board, not vice versa.

## Verification

- All new Python tests pass; `bash tests/test_shortcuts_registry_coverage.sh`.
- Existing board tests still green (`tests/test_board_*.py`).
- Manual smoke (also covered by the aggregate manual-verification sibling
  t1162_6): `ait board` → focus column → `w` → adjust selections → launch
  dialog shows the exact command.

## Risk

### Code-health risk: low
- `aitask_board.py` is a load-bearing 7k-line TUI, but every change is
  additive (one binding, one `check_action` arm, two new modal classes, one
  action) — no existing code path is modified · severity: low ·
  → mitigation: covered in-task by the existing `tests/test_board_*.py`
  regression run
- The file carries uncommitted foreign hunks (t1210_2); a careless commit
  could sweep them into this task's commit · severity: low · → mitigation:
  hunk-scoped staging + `git diff --cached` content check (pinned in the
  plan's concurrent-session caution)

### Goal-achievement risk: low
- Board modal and gatherer are two membership implementations that could
  drift, but equivalence is already pinned at the data layer (t1162_1 D11,
  shared `normalize_board_idx` + filename key); this task adds the flow-level
  oracle on top · severity: low · → mitigation: covered in-task by test 8
- `SelectionList` has no native section headers for the grouped task screen;
  the label-prefix fallback is a minor UX compromise, recoverable ·
  severity: low · → mitigation: none (accepted)
- The launch surface has two non-tmux paths that pick's precedent does not
  transfer to (filename-bound `run_aitask_pick`; `resolve_dry_run_command`
  returning `None`) — both identified in plan review and now designed as a
  dedicated `run_work_report` worker + `if full_cmd:` fallback ·
  severity: low · → mitigation: covered in-task by tests 7b/7c

No standalone before/after mitigation tasks are warranted — every identified
risk is already mitigated inside this task's own test plan.

## Post-Review Changes

### Change Request 1 (2026-07-23 18:40)
- **Requested by user:** [high | blocking] The "run" result callback called
  `run_work_report(cols_csv, tasks_csv)`, rebuilding default wrapper args —
  but `AgentCommandScreen.run_terminal()` stores user command edits into
  `screen.full_command` before dismissing, and the dialog's agent/profile
  controls regenerate that command. Run-in-terminal therefore silently
  discarded in-dialog overrides that the tmux path honored. Dispatch the
  actual dialog command, and replace the canonical-argv test with
  overridden-command coverage.
- **Changes made:** `run_work_report` now takes the full shell command
  string and dispatches `["sh", "-c", full_command]` (mirroring the
  tui_switcher "run" path); the callback passes `screen.full_command`; the
  dry-run-failure fallback composes the wrapper default with `shlex.join`
  (added `import shlex`). Tests: `test_run_result_dispatches_dialog_command_
  not_pick` now mutates `screen.full_command` to simulate a stored override
  and asserts it is what gets dispatched; the fallback test pins the
  shlex-joined default; the worker test pins the `sh -c` dispatch. The same
  discard flaw exists pre-existing in the pick/brainstorm/resume/create
  "run" branches — recorded as an upstream defect, out of scope here.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_work_report.py`, this plan (steps 5-6, tests 7b/7c).

## Final Implementation Notes

- **Actual work done:** Implemented as planned in
  `.aitask-scripts/board/aitask_board.py` (+257 lines, purely additive):
  `Binding("w", "work_report", "Work Report")`; the `check_action` arm hiding
  `w` in `inflight`/`bytopic` and when `_get_focused_col_id()` is `None`;
  two `ModalScreen`s (`WorkReportColumnSelectScreen`,
  `WorkReportTaskSelectScreen`) modeled on `IssueTypeFilterScreen`;
  `_work_report_columns()` (renderable configured intersection, Unsorted
  first when non-empty); `action_work_report()` orchestration; the
  `_launch_work_report()` resolve/dialog/fallback surface; and the
  `run_work_report()` `@work(exclusive=True)` direct-run worker. Tests:
  `tests/test_board_work_report.py` (23 tests), the flow-level round-trip
  oracle `tests/test_board_work_report_roundtrip.sh` +
  `tests/lib/work_report_flow_equiv.py`.
- **Deviations from plan:** The single `action_work_report` of the plan was
  split into `action_work_report` (columns → tasks orchestration via dismiss
  callbacks) and `_launch_work_report` (dry-run resolve → `AgentCommandScreen`
  or direct-run fallback) — cleaner and independently spy-testable.
  `AgentCommandScreen` is constructed with `project_root=Path(".")` (a valid
  keyword the plan's corrected param list omitted). Column title for Unsorted
  is `"Unsorted / Inbox"`; task labels use the `[{col_id}] {task_num}
  {task_name}` prefix fallback (SelectionList has no section headers); task
  ids derive from `TaskCard._parse_filename(...).lstrip("t")`.
- **Issues encountered:** The originating session (PID 318672 on omg16)
  crashed mid-task after `plan_approved` was recorded but before Step-8
  commit, leaving the +257-line board change and the three test files
  uncommitted. Resumed via gate-ledger re-entry (`resume-point` = `IMPLEMENT`):
  reclaimed the lock (`RECLAIM_CRASH`), re-attributed to `claudecode/opus4_8`,
  and re-ran the full verification — all green (23 board-work-report tests,
  round-trip, `test_shortcuts_registry_coverage.sh`, all 14 existing
  `test_board_*.py` suites). No code changes were needed on resume.
- **Key decisions:** The `"run"` result callback dispatches
  `screen.full_command` (the dialog's stored/regenerated command), never
  rebuilt default args — honoring in-dialog edits and agent/profile overrides
  (Change Request 1). The direct-run worker shells `["sh", "-c", full_command]`
  (tui_switcher "run" pattern). The dry-run-failure fallback composes the
  wrapper default via `shlex.join` so the reviewed selection is never dropped.
- **Upstream defects identified:**
  `.aitask-scripts/board/aitask_board.py:5696,5866 — the pick "run" result
  callbacks (and the brainstorm :6006, resume :6179, create :6308 branches)
  call run_aitask_pick/rebuild default wrapper args instead of dispatching the
  dialog's stored screen.full_command, silently discarding in-dialog command
  edits and agent/profile overrides. This is the same flaw fixed for
  work-report here (Change Request 1); pre-existing and out of scope for
  t1162_4.`
- **Notes for sibling tasks:**
  - t1162_5 (documentation) should document the board `w` action and — worth
    calling out, the user asked during review — **how to customize the
    work-report code-agent default**: `aitasks/metadata/codeagent_config.json`
    → `defaults."work-report"` (project, committed) or
    `codeagent_config.local.json` (user override, wins), editable via
    `ait settings` → "Agent defaults", plus the per-launch/per-project picker
    in the `AgentCommandScreen`.
  - t1162_6 is the aggregate manual-verification sibling; the manual smoke
    (`ait board` → focus column → `w` → adjust → launch dialog shows the exact
    command) is covered there.
  - The board `--tasks` csv is composed in the displayed grouped order — the
    gatherer's `task_order_changed` check defends exactly this sequence; never
    re-sort it.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
