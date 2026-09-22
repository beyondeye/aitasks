---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tmux]
gates: [risk_evaluated]
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-18 08:07
updated_at: 2026-09-18 08:07
---

## Origin

Risk-mitigation ("after") follow-up for t1828, created at Step 8d after implementation landed.

## Risk addressed

> `load_tmux_defaults` now refuses a name it has always returned, and it feeds
> actual session **creation** (`agentcrew_runner.py:437`) plus window targeting in
> the board and both monitors. A project deliberately running a dotted session
> moves to `aitasks`, which is explicitly *not* unique across repos.
> · severity: medium (residual — the fallback stays silent for these consumers
> until `surface_illegal_name_in_yaml_readers` lands)

Addresses: load_tmux_defaults falls back silently for board / monitors / agentcrew.

## Goal

Give `load_tmux_defaults` a status channel so its consumers can notify on a
`default_session` fallback the way the TUI switcher already does.

Today `agent_launch_utils.load_tmux_defaults` returns a bare `dict` and wraps its
whole body in `except Exception: pass`. It has **no way to say why** a value was
replaced. After t1828 it falls back for two distinct reasons — the file did not
parse, or the configured name holds `.` / `:` and tmux cannot address it — and in
both cases every consumer substitutes `aitasks` with no message:

| call site | what the user sees today |
|---|---|
| `monitor/monitor_app.py:3901` | nothing |
| `monitor/minimonitor_app.py:5324` | nothing |
| `board/aitask_board.py:10768`, `:10946` | nothing |
| `agentcrew/agentcrew_runner.py:436-437` | nothing — and this one **creates** the session |
| `lib/agent_command_screen.py:412, 566, 580` | nothing (it is also the default text of the "create new session" input) |
| `lib/tui_switcher.py:1498-1499` | nothing — note the switcher's *notice* at `:697` comes from the **line** reader, not from here |

The line-reader family (`read_default_session_status`, and the bash twin's
`DEFAULT_SESSION_UNREADABLE:<shape>:<cfg>` sentinel) already returns a shape, and
`tui_switcher._ensure_session_live` turns it into a `notify()`. This task extends
that ability to the YAML-backed family.

## Suggested direction

Add a sibling that returns the shape alongside the values — e.g.
`load_tmux_defaults_status(root) -> (dict, str | None)` — and keep
`load_tmux_defaults` as a thin wrapper so the ~8 existing call sites need no
change until each opts in. Reuse the existing `DEFAULT_SESSION_PROBLEM_SHAPES`
vocabulary rather than inventing a second one; `illegal_tmux_name` and the
file-level shapes (`encoding`, `non_printable`) are the cases that matter here.

Then decide, per consumer, whether it has a surface to show a notice on. A
Textual app does; `agentcrew_runner` may need to print. **Do not add a print to a
reader that runs inside a TUI** — the no-stderr rule that shaped
`read_default_session_status` applies here too (stderr corrupts the screen).

Worth settling while implementing: `except Exception: pass` currently swallows
every failure, so a status channel that only reports *known* shapes would still
be silent on an unexpected error. Decide whether the tuple's second element
distinguishes "no problem" from "problem we could not classify".

## Verification

- A project whose `project_config.yaml` has `default_session: a.b` produces a
  visible notice in the board, monitor and minimonitor — not just the switcher.
- `agentcrew` does not create a session under a name it fell back from without
  saying so.
- The existing `tui_switcher` notice at `:697` is unchanged (it is fed by the
  line reader, and t1828's `tests/test_tui_switcher_default_session_notify.py`
  pins its three wordings).
- `tests/test_tmux_default_session_resolvers.py`'s five-resolver parity still
  holds — the wrapper must not change any returned *value*.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:25Z.88c99abaf8f3e7676f6277c9 from=t1794_9 from_verified=yes at=2026-09-22T06:10:25Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1835_surface_illegal_name_in_yaml_readers.md) cites stale line anchors: aitask_board.py:10768.
