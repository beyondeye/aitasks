---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [backend, shadow]
gates: [risk_evaluated]
anchor: 1111
followup_kind: upstream_defect
created_at: 2026-07-31 10:03
updated_at: 2026-08-13 23:06
boardidx: 110592
---

## Origin

Spawned from t1353 during Step 8b review.

## Upstream defects

- `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` — a
  risk-mitigation task file was created with **no numeric id** in its filename,
  so every `TaskCard._parse_filename` consumer silently drops it; the creating
  flow should never emit an id-less task filename.
- `.aitask-scripts/lib/agent_launch_utils.py:1425-1444` —
  `attach_shadow_cleanup_hook` returns `"installed"` / `"existing"` based on a
  synchronous `show-hooks` read, but issues its `set-option` / `set-hook` writes
  through the fire-and-forget `_TMUX.spawn()` (`lib/tmux_exec.py:230`, a bare
  `Popen` that is never waited on), so the returned status can precede the write
  actually landing.

## Diagnostic context

**Defect 1 — id-less task filename.** It is currently making the aggregate
Python suite red. `bash tests/run_all_python_tests.sh` reports
`PYTHON SUITE: FAILED (runner=unittest, exit=1)` with exactly one failure out of
2951:
`test_board_work_report.WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed`
(`AssertionError: 154 != 155`).

Chain: the test picks the first populated board column (`unordered`, 155 tasks)
and asserts the work-report dialog's `SelectionList.option_count` equals
`len(get_column_tasks(col_id))`. `action_work_report`
(`.aitask-scripts/board/aitask_board.py:7269-7273`) builds its entries with
`task_num, task_name = TaskCard._parse_filename(task.filename)` and
`if not task_num: continue`. The file above has no `t<N>_` prefix, so it is
skipped — 154 offered vs 155 in the column.

The file was committed on 2026-07-29 (`9e7f18326`,
`ait: Revert t1311 to Ready (risk mitigation pending)`), so the creating flow is
the risk-mitigation "before" task creation path. Note the task file itself is
otherwise well-formed (valid frontmatter, `anchor: 1162`) — only the filename
lacks the id.

**Defect 2 — hook status race.** Surfaced while implementing t1353's live smoke:
its bypass control armed a cleanup hook via `attach_shadow_cleanup_hook`, got
`"installed"` back, and immediately killed the agent process — the `pane-died`
hook had not been written yet, so nothing fired. A standalone raw-tmux repro
confirmed the hook mechanism itself is sound; the race is purely between the
function's return and its own fire-and-forget writes. Benign in production (an
agent does not exit microseconds after its shadow spawns), which is why t1353
worked around it in the test fixture (`wait_hook_armed()` in
`tests/test_monitor_shadow_spawn_live.sh`) rather than changing the helper.

## Suggested fix

**Defect 1:** find the creation path that produced the id-less filename (the
risk-mitigation "before" creation in `risk-mitigation-followup.md` Part 2 /
`aitask_create.sh`), fix it so a task file always carries `t<N>_`, and rename the
existing file to its proper `t<N>_...` form. Consider whether
`_parse_filename`'s silent `continue` should instead surface a warning — a task
that cannot be parsed disappearing from a report is exactly the failure mode
that hid this for two days.

**Defect 2:** either wait on the `set-hook` `Popen` before probing/returning, or
route those two writes through `_TMUX.run()` (which does wait) and downgrade the
return contract's promise. Decide deliberately: `spawn()` was chosen for
non-blocking UI updates, and `attach_shadow_cleanup_hook` already blocks on a
`show-hooks` `run()` anyway, so the non-blocking argument is weak here.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1755** id=2026-09-09T10:41:11Z.41460807853361fb7667be72 from=t1755 from_verified=yes at=2026-09-09T10:41:11Z base=ec9641e79d0bc203ff54aeca4e3f0783d9da6f61 base_branch=main dirty=yes host=omg16
>
> | The id-less-filename **producer** is now closed. Your "Upstream defects" bullet 1
> | says "the creating flow should never emit an id-less task filename" — t1755 found
> | and fixed that flow.
> | 
> | What was wrong (reproduced end-to-end in a scratch fixture, twice):
> | `aitask_create.sh` could write `aitasks/t_<name>.md`, **commit** it, and exit **0**.
> | Two defects combined — an unchecked `mktemp` whose empty path made
> | `2>"$claim_stderr"` an ambiguous redirect, and a lost exit status, because bash
> | DROPS `errexit` inside every command-substitution subshell, so the `die()` in
> | `claim_parent_id_once` exited only its own subshell and the caller continued with an
> | empty id.
> | 
> | Fixed in `ec9641e79` (checked `mktemp`, status absorbed with `|| rc=$?`, and a
> | `^[0-9]+$` validation in `claim_unique_parent_id` as the single choke point).
> | Regression coverage: `tests/test_create_id_claim_abort.sh`.
> | 
> | **What I did NOT prove:** that your specific artifact
> | `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` came from this
> | path. I have no evidence tying that file to a failed claim. t1721 has since
> | renumbered it to t1730, so no id-less file is on disk as of this note.
> | 
> | **What this may change for you, and what it does not:** your bullet 1 is answered,
> | so the remaining work is the *consumer* side. That handling is now a backstop for
> | legacy/pre-existing files rather than a guard against newly created ones, which may
> | affect priority — but it does not make the task moot: a silent drop is still a
> | silent drop. Bullet 2 (the `attach_shadow_cleanup_hook` fire-and-forget status
> | race) is untouched by this and unaffected.

> **✉ note:t1794_9** id=2026-09-22T06:09:04Z.1956c994097aa06a4306c01d from=t1794_9 from_verified=yes at=2026-09-22T06:09:04Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1356_idless_task_filename_and_hook_status_race.md) cites stale line anchors: aitask_board.py:7269-7273; symbols you name -> current module: TaskCard -> board_widgets.py.
