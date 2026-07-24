---
Task: t1225_fix_board_run_branch_command_override.md
Base branch: main
plan_verified: []
---

# t1225 — Route board "run" branches through the dialog's stored `full_command`

## Context

The board's `AgentCommandScreen` lets the user edit the command in-place and
(where a profile/agent row is rendered) override the agent, model, and profile.
`AgentCommandScreen.run_terminal()` stores the edited text back into
`screen.full_command` before dismissing with `"run"`, and the agent/profile
controls regenerate `self.full_command` (`lib/agent_command_screen.py:819,999,1031,1117-1119`).

The tmux launch branches already honor this — every one dispatches
`launch_in_tmux(screen.full_command, …)`. The **direct-run** (`"run"`) branches
do not: they rebuild default wrapper argv from the task filename, silently
discarding in-dialog edits and agent/model/profile overrides.

t1162_4 fixed this for the new work-report action only
(`run_work_report(screen.full_command)`, `aitask_board.py:5972`). The same
pre-existing flaw remains in the board's other five "run" branches:

| Call site (`.aitask-scripts/board/aitask_board.py`) | Current "run" dispatch |
|---|---|
| `_on_detail_result` pick branch, ~5696 | `run_aitask_pick(task_data.filename)` |
| `action_pick_task`, ~5866 | `run_aitask_pick(focused.task_data.filename)` |
| `_launch_brainstorm`, ~6006 | `_run_brainstorm_in_terminal(num, filename)` |
| `action_gate_resume`, ~6179 | `run_codeagent_operation("resume", filename)` |
| `action_create_task`, ~6308 | `_run_create_in_terminal()` |

Intended outcome: every dialog-backed "run" branch dispatches the dialog's
stored `screen.full_command`, exactly like the tmux branches, while keeping each
branch's existing side effects (filename-scoped refocus, task reload, the
no-terminal `suspend()` fallback, and per-branch error notification).

## Approach

Generalize the worker t1162_4 introduced (`run_work_report`,
`aitask_board.py:6275-6295`) into one scope-honest dispatcher and route all six
dialog "run" branches through it.

### 1. Rename + generalize the worker

`run_work_report(full_command)` → `run_dialog_command(full_command, refocus_filename=None, error_notice=...)`:

```python
@work(exclusive=True)
async def run_dialog_command(
    self,
    full_command: str,
    refocus_filename: str | None = None,
    error_notice: str | None = CODEAGENT_FAILURE_NOTICE,
):
    """Dispatch an agent-command dialog's stored ``full_command`` verbatim.

    Every AgentCommandScreen "run" branch routes here: run_terminal stores
    user edits into screen.full_command and the agent/profile controls
    regenerate it, so rebuilding default wrapper args at the call site would
    silently discard them (t1225). ``sh -c`` mirrors the tui_switcher "run"
    path. ``error_notice`` is None for the non-agent TUI launches (create /
    brainstorm), whose non-zero exit is an ordinary cancel, not a failure.
    """
    args = ["sh", "-c", full_command]
    terminal = find_terminal()
    if terminal:
        spawn_in_terminal(terminal, args)
    else:
        with self.suspend():
            ret = subprocess.call(args)
        if ret != 0 and error_notice:
            self.notify(error_notice, severity="error")
        self.manager.load_tasks()
        self.refresh_board(refocus_filename=refocus_filename)
```

`CODEAGENT_FAILURE_NOTICE` is a new module constant holding the existing
literal `"Code agent invocation failed — check model configuration"` (also
reused by `run_aitask_pick` / `run_codeagent_operation`, which keep their
current text).

`refresh_board(refocus_filename=None)` already behaves as today's plain
`refresh_board()` for the column-scoped callers.

### 2. Route the six "run" branches

- **work-report** (`_launch_work_report`, ~5972 and the dry-run-failure fallback
  at ~5950): `self.run_dialog_command(screen.full_command)` /
  `self.run_dialog_command(shlex.join([...]))` — unchanged semantics, new name.
- **pick ×2** (~5697, ~5867):
  `self.run_dialog_command(screen.full_command, refocus_filename=<filename>)`.
- **resume** (~6180): same, with the focused task's filename.
- **brainstorm** (~6007):
  `self.run_dialog_command(screen.full_command, refocus_filename=filename, error_notice=None)`.
- **create** (~6309):
  `self.run_dialog_command(screen.full_command, error_notice=None)`.

The `else:` fallbacks that fire when `resolve_dry_run_command` returns `None`
(`aitask_board.py:5707, 5877, 6190`) are **unchanged** — no dialog was shown, so
there is no stored command and rebuilding wrapper argv is correct. Those are the
remaining callers of `run_aitask_pick` / `run_codeagent_operation`, which stay.

### 3. Delete the now-dead per-branch workers

`_run_create_in_terminal` (~6327) and `_run_brainstorm_in_terminal` (~6339)
have no other callers once their branches are routed — remove both.

## Files

- `.aitask-scripts/board/aitask_board.py` — the six branches, the generalized
  worker, the new constant, the two deletions.
- `tests/test_board_work_report.py` — update the three `run_work_report`
  references (2 call assertions + the `__wrapped__` worker test) to
  `run_dialog_command`.
- `tests/test_board_dialog_run_dispatch.py` — **new**, see below.

## Tests

New `tests/test_board_dialog_run_dispatch.py`, following the `MagicMock`-app
construction-spy pattern of `tests/test_board_work_report.py`
(`sys.path` insert of `board/` + `lib/`, `os.chdir(REPO_ROOT)` in
`setUpClass`).

Per branch (pick-from-detail, pick-from-board, brainstorm, resume, create),
mirroring `test_run_result_dispatches_dialog_command_not_pick`:

1. Drive the action with a mock app (`_modal_is_active()` → False,
   `_focus_existing_agent_window()` → False, `_resolve_pick_command` /
   `_resolve_resume_command` → a real command string, `_resolve_*_profile` →
   `"fast"`; patch `ab.resolve_agent_string`, and `ab.find_window_by_name` →
   `None` for brainstorm).
2. Grab `(screen, callback)` from `app.push_screen.call_args.args`.
3. Overwrite `screen.full_command` with an override string (simulating the
   in-dialog edit `run_terminal` stores).
4. `callback("run")` and assert
   `app.run_dialog_command.assert_called_once_with(<override>, refocus_filename=…[, error_notice=None])`
   **and** that the old dispatcher is not called
   (`app.run_aitask_pick` / `app.run_codeagent_operation` /
   absence of `_run_create_in_terminal` / `_run_brainstorm_in_terminal`).

Negative controls (prove the fix is targeted, not blanket):

- `resolve_dry_run_command`/`_resolve_pick_command` → `None`: `push_screen` is
  not called and `run_aitask_pick(filename)` / `run_codeagent_operation("resume", filename)`
  still fire — the no-dialog path must keep rebuilding wrapper argv.
- The tmux branch still receives `screen.full_command` (unchanged behavior).

Worker-level tests on `KanbanApp.run_dialog_command.__wrapped__` (the
`asyncio.run(coro)` pattern already used at
`tests/test_board_work_report.py:234-246`). **Both** dispatch paths are
covered — the no-terminal `suspend()` branch is the one neither the
construction-spy tests nor the live manual check reach (the manual check runs
with a real terminal available), so its side effects need their own assertions:

- **Terminal path** (`ab.find_terminal` → `"footerm"`, `ab.spawn_in_terminal`
  spied): shells out `["sh", "-c", <command verbatim>]`; `app.manager.load_tasks`
  and `app.refresh_board` are **not** called (that branch is fire-and-forget —
  the dialog callback owns the refresh).
- **No-terminal / suspend path** (`ab.find_terminal` → `None`,
  `patch.object(ab.subprocess, "call", return_value=0)`): assert the full side
  effect set —
  - `subprocess.call` received `["sh", "-c", <command verbatim>]`,
  - `app.manager.load_tasks` called once,
  - `app.refresh_board` called once with `refocus_filename="t42_alpha.md"` when
    the caller passed one, and with `refocus_filename=None` when it did not
    (the column-scoped work-report case).
- **Notification branch** on the suspend path with `subprocess.call` → 1:
  default `error_notice` → `app.notify` called once with
  `CODEAGENT_FAILURE_NOTICE` and `severity="error"`; `error_notice=None` →
  `app.notify` not called. In both cases `load_tasks` / `refresh_board` still
  fire (a failed launch must not strand the board).

Also assert `_run_create_in_terminal` / `_run_brainstorm_in_terminal` no longer
exist on `KanbanApp` (guards against the dead helpers being re-added and
re-wired).

## Verification

```bash
python3 tests/test_board_dialog_run_dispatch.py
python3 tests/test_board_work_report.py
bash tests/run_all_python_tests.sh          # full Python suite, no regressions
python3 -c "import ast,sys; ast.parse(open('.aitask-scripts/board/aitask_board.py').read())"
```

Prove the harness can fail: before wiring each branch, confirm the new test
exits 1 against the unmodified `aitask_board.py` (the assertion must fail on
`run_aitask_pick` being called), then re-run green after the change.

Manual (live board, `ait board`): focus a task → `p` → edit the command in the
dialog (e.g. append `--model haiku` or change the slash args) → choose the
direct **Run** action → confirm the terminal that opens carries the edited
command, not the default `aitask_codeagent.sh invoke pick <n>`. Repeat for `n`
(create), brainstorm, and an In-Flight task's resume.

## Risk

### Code-health risk: medium
- The create / brainstorm branches move from direct-argv `subprocess`/`spawn_in_terminal`
  dispatch to `sh -c "<command>"`, so the command string is now shell-parsed. The
  strings are repo-relative script paths plus a numeric task id, so this is safe
  today, but it is a real semantic change on two load-bearing launch paths ·
  severity: medium · → mitigation: none (declined — bounded to two fixed
  repo-relative script paths)
- The live dialog interaction (real widgets, real `run_terminal` → dismiss) is
  not reachable from the construction-spy tests · severity: medium · →
  mitigation: none (declined — the Step 8c manual-verification follow-up covers
  this). The `suspend()` no-terminal fallback, which the live manual check also
  misses (it runs with a real terminal available), is instead pinned directly by
  the no-terminal worker test above.

### Goal-achievement risk: low
- None identified. The defect, the five call sites, and the target pattern
  (`run_work_report`, already shipped and tested in t1162_4) are all pinned by
  the upstream-defect report; the change is a mechanical extension of an
  existing, verified fix.

## Step 9 (Post-Implementation)

Standard: merge approval, `ait gates run 1225` (the `risk_evaluated` gate is the
task's enforced active set), archival via
`./.aitask-scripts/aitask_archive.sh 1225`, push.
