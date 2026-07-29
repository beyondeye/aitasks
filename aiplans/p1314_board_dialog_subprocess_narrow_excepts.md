---
Task: t1314_board_dialog_subprocess_narrow_excepts.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1314 — Board dialog subprocess handlers catch too narrow an exception set

## Context

`t1302` fixed this defect class on the board's *refresh* path
(`TaskManager.refresh_git_status`), which caught only
`(subprocess.TimeoutExpired, FileNotFoundError)` while its twin
`refresh_lock_map` also caught `OSError`. Its scope was explicitly limited to
that one method, leaving the three **user-triggered dialog handlers** in
`TaskDetailScreen` with the same too-narrow tuple.

A survey of the module confirms the divergence is now exactly three sites — the
canonical tuple `(subprocess.TimeoutExpired, FileNotFoundError, OSError)` is
used at 10 other `subprocess.run` call sites
(`.aitask-scripts/board/aitask_board.py:729, 759, 794, 1044, 1067, 1281, 2986,
3515, 7976, 9076`), and only these three diverge:

- `:4529` `revert_task` — a `PermissionError` (or any other `OSError`) from the
  git-checkout subprocess propagates out of the button handler instead of
  surfacing as a "Revert failed" notification.
- `:4712` `_do_lock` — same tuple inside a `@work(thread=True)` worker. The
  `LoadingOverlay` pop lives in the (unreached) `except`, so an `OSError`
  escapes the worker thread with the modal spinner left on screen: the board
  appears hung.
- `:4779` `_do_unlock` — identical to `_do_lock`.

**Reproduction confirmed** against the real classes (no replica): constructing
a real `TaskDetailScreen`, patching `app` with a `PropertyMock`, and injecting
`PermissionError` into `subprocess.run` makes `revert_task()` raise
`PermissionError` and makes `_do_lock` raise with **zero** `call_from_thread`
calls recorded — i.e. the overlay is never popped.

Intended outcome: all three degrade to an error notification, and the two
workers can no longer leave the `LoadingOverlay` stranded — not even for an
exception type the handler does not name.

## Approach

Two changes, both confined to `TaskDetailScreen` in
`.aitask-scripts/board/aitask_board.py`:

1. **Widen the tuple** at all three sites to the module's canonical
   `(subprocess.TimeoutExpired, FileNotFoundError, OSError)`. (`FileNotFoundError`
   is redundant under `OSError` but is kept verbatim so the three sites read
   identically to the other ten — a lone shortened variant would look like a
   deliberate difference.)

2. **Make the overlay pop structural, not tuple-dependent** in `_do_lock` /
   `_do_unlock`, per the task's suggested fix. The task's own note that "the
   tuple may not be exhaustive" argues against relying on it: wrap **only the
   `subprocess.run` call** in an inner `try/finally` whose `finally` pops the
   overlay. This is deliberately *not* a `finally` around the whole body.

   **Why the placement matters:** `app.pop_screen()` removes the **top** screen.
   `_do_unlock`'s success path pushes `ResetTaskConfirmScreen` on top of the
   overlay; a body-wide `finally` would run the pop *after* that push and
   dismiss the confirm dialog instead of the overlay. Scoping the `finally` to
   the subprocess call keeps the pop exactly where it is today (immediately
   after `subprocess.run` returns) while also covering the raise path, and
   removes the duplicated pop — one pop site in source, unskippable by
   construction. (No `popped` flag / once-only wrapper is needed; the pop cannot
   run twice.)

### Target shape (`_do_lock`; `_do_unlock` is identical in structure)

```python
    @work(thread=True)
    def _do_lock(self, task_id: str, email: str):
        """Run lock subprocess in a thread worker."""
        try:
            try:
                result = subprocess.run(
                    ["./.aitask-scripts/aitask_lock.sh", "--lock", task_id, "--email", email],
                    capture_output=True, text=True, timeout=15
                )
            finally:
                # Dismiss LoadingOverlay. Scoped to the subprocess call, not the
                # whole body: pop_screen removes the TOP screen, so this must run
                # before any later push (see _do_unlock's ResetTaskConfirmScreen).
                # `finally` — not the `except` below — is what keeps the overlay
                # off-screen for an exception type this handler does not name.
                self.app.call_from_thread(self.app.pop_screen)
            if result.returncode == 0:
                self.app.call_from_thread(self.app.notify, f"Locked t{task_id}", severity="information")
                self.app.call_from_thread(self.dismiss, "locked")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.app.notify, f"Lock failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.app.call_from_thread(self.app.notify, f"Lock failed: {e}", severity="error")
```

`revert_task` needs only the tuple widening (it pushes no overlay).

**Explicitly out of scope** (per the task's closing note): factoring a shared
"run a helper subprocess, degrade on failure" helper out of the 30+ call sites.
t1302 rejected that on the grounds the sites have genuinely different degrade
semantics; this task does not revisit it.

## Files

- `.aitask-scripts/board/aitask_board.py` — the three handlers (`revert_task`
  ~:4515, `_do_lock` ~:4697, `_do_unlock` ~:4745).
- `tests/test_board_dialog_subprocess_degrade.py` — **new**, modelled on
  `tests/test_board_refresh_degrade.py` (t1302).

## Test plan

New `tests/test_board_dialog_subprocess_degrade.py`, reusing the proven
in-repo patterns:

- Real class, not a replica: build a real `Task` via `Task.from_text(...)` (no
  disk I/O) and a real `TaskDetailScreen(task)` — it constructs fine outside a
  running app (verified).
- `patch.object(ab.TaskDetailScreen, "app", new_callable=PropertyMock,
  return_value=MagicMock())` — the pattern already used in
  `tests/test_tui_switcher_agent_launch.py:106`.
- Drive the `@work(thread=True)` workers synchronously through
  `TaskDetailScreen._do_lock.__wrapped__(screen, ...)` — the pattern already
  used in `tests/test_board_work_report.py:240` (`functools.wraps` on Textual's
  work decorator exposes the raw function; verified on textual 8.2.7).
- Parametrize the injected failure over the **same** set as t1302's suite so
  the dialog and refresh boundaries cannot silently re-diverge:
  `PermissionError`, bare `OSError`, `FileNotFoundError`,
  `subprocess.TimeoutExpired`.

Cases:

1. **`revert_task` degrades** — for each failure: no exception escapes, and
   `app.notify` is called once with a `"Revert failed: …"` message and
   `severity="error"`.
2. **`_do_lock` / `_do_unlock` degrade** — for each failure: no exception
   escapes; `call_from_thread(app.pop_screen)` is requested **exactly once**;
   a `call_from_thread(app.notify, "Lock failed: …"/"Unlock failed: …",
   severity="error")` is requested.
3. **Overlay backstop (pins the `finally`, not the tuple)** — inject a
   `RuntimeError`, deliberately *not* in the caught tuple. Assert the exception
   still propagates **and** `pop_screen` was still requested exactly once. This
   case fails under a tuple-only fix, so it discriminates change (2) from
   change (1).
4. **Ordering control (pins the `finally` placement)** — `_do_unlock` success
   path with `status: Implementing` + `assigned_to` set: assert the
   `pop_screen` request precedes the `push_screen(ResetTaskConfirmScreen, …)`
   request in `call_from_thread.call_args_list`. This is the case a body-wide
   `finally` would break.
5. **Normal-outcome controls (no exception injected).** The refactor moves the
   result-handling block out of the immediate `try` body into the *outer* `try`,
   so a mis-scoped inner `try` or a mis-indented `if result.returncode == 0:`
   could strand an overlay, skip a dismissal, or change error notification text
   while every case above still passes. Each control stubs `subprocess.run` with
   a fixed `returncode`/`stderr` and asserts **exactly one** `pop_screen` plus
   the exact dispatch. All five contracts were captured from current `HEAD` by
   probing the real class, so they pin *observed* behavior, not assumed:

   | Case | Fixture | Expected `call_from_thread` sequence |
   |---|---|---|
   | `_do_lock` success | `rc=0` | `pop_screen` · `notify("Locked t42", severity="information")` · `dismiss("locked")` |
   | `_do_lock` failure | `rc=1`, `stderr="boom-lock\n"` | `pop_screen` · `notify("Lock failed: boom-lock", severity="error")` · **no** `dismiss` |
   | `_do_unlock` success, **no reset** | `rc=0`, task `status: Ready` | `pop_screen` · `notify("Unlocked t42", severity="information")` · `dismiss("unlocked")` · **no** `push_screen` |
   | `_do_unlock` failure | `rc=1`, `stderr="boom-unlock\n"` | `pop_screen` · `notify("Unlock failed: boom-unlock", severity="error")` · **no** `dismiss` |
   | `revert_task` failure | `rc=1`, `stderr="boom-revert\n"` | *(no worker)* direct `app.notify("Revert failed: boom-revert", severity="error")`, **no** `dismiss` |

   The `_do_unlock` "no reset" row is the counterpart to case 4: together they
   pin both branches of the `status == "Implementing" and assigned_to` fork, so
   neither the confirm-dialog push nor the plain dismissal can be lost.
   `revert_task`'s row also pins that this path notifies **directly** (not via
   `call_from_thread`) — it runs on the main thread and pushes no overlay.
   `revert_task`'s `rc=0` path is deliberately not asserted: it calls
   `self.dismiss("reverted")` inline, which needs a mounted screen; it is
   covered by the manual board check below.

**Negative control (run manually during implementation, recorded in the plan's
Final Implementation Notes):** the suite already fails against current `HEAD` —
the probe above showed `PermissionError` escaping both `revert_task` and
`_do_lock`. After the fix lands, re-narrow each tuple one at a time and confirm
the suite exits non-zero for each, then restore. This proves the tests
discriminate per-site rather than passing on one site's fix.

## Verification

```bash
# New suite (must exit 0 after the fix)
python3 tests/test_board_dialog_subprocess_degrade.py -v

# t1302's companion suite must stay green (shared exception set)
python3 tests/test_board_refresh_degrade.py -v

# Board suite — no regression in the dialog/worker area
bash tests/run_all_python_tests.sh --test-dir tests
# Read ONLY the last line: `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`
```

Manual check (the failure path is not reachable from a normal board session):
open `ait board`, press `Enter` on a task, and confirm the Lock/Unlock/Revert
buttons still behave normally (overlay appears and clears, notifications fire).
The degraded paths are covered by the automated suite.

## Risk

### Code-health risk: low

- The `try/finally` restructure in `_do_lock` / `_do_unlock` could regress the
  screen-stack ordering if the `finally` were scoped to the whole worker body,
  popping `ResetTaskConfirmScreen` instead of the `LoadingOverlay`. · severity:
  low · → mitigation: covered in-task — the plan pins the `finally` to the
  `subprocess.run` call only; test case 4 asserts the pop-before-push order and
  the case-5 controls pin exactly one pop plus the exact dispatch on every
  normal (non-injected) outcome of all three handlers.
- The three widened tuples could re-diverge from the module's other ten sites in
  a future edit. · severity: low · → mitigation: covered in-task — the new suite
  drives the same parametrized failure set as `test_board_refresh_degrade.py`,
  so a re-narrowing at any of the three sites fails the suite.

### Goal-achievement risk: low

- None identified. The task names the exact lines and the exact fix, the
  approach is the module's already-established pattern, and both the current
  failure and the test harness were verified by probing the real classes before
  planning.

No `### Planned mitigations` subsection: both identified risks are `low` and are
mitigated **inside this task** (by the chosen `finally` placement and by test
cases 3–5), so there is nothing for a before/after follow-up task to carry.

## Post-implementation

Follow `SKILL.md` Step 9: merge to `main` (current-branch mode — no worktree to
remove), run `./ait gates run 1314` (`risk_evaluated` is the active gate), then
`./.aitask-scripts/aitask_archive.sh 1314`.
