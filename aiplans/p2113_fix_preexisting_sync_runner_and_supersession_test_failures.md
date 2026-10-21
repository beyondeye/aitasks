---
Task: t2113_fix_preexisting_sync_runner_and_supersession_test_failures.md
Base branch: main
Output branch: main
---

# t2113 — Fix the macOS sync-runner and supersession test failures

## Context

t2096's baseline run found 10 failures on macOS that predate it. Both reproduce
deterministically when the module is run alone:

- `python -m unittest tests.test_sync_action_runner` → `FAILED (failures=9, skipped=2)`
- `python -m unittest tests.test_model_supersession` → `FAILED (failures=1)`

### Root cause 1 — sync runner (a real product bug, not a test bug)

`_session_members()` in `.aitask-scripts/lib/sync_action_runner.py:400` has two
backends: `/proc` (Linux) and `pgrep -s <sid>` for everything else. **macOS
`/usr/bin/pgrep` has no `-s` option.** It prints `illegal option -- s` and exits 2
(checked on macOS 15.7.3). Exit 2 maps to `None` ("cannot tell"), so on every Mac:

- `_stop_sync_session` sees `members is None`, skips `_term_session` and the kill
  rounds completely, and only `proc.kill()`s the direct `sh`. The pull/rebase
  children **survive the timeout**. The t1947 containment never ran on macOS.
- The final check returns `None` too, so every timed-out sync reports
  `stray_session` (this is the assertion that fails at test line 643), and
  `sync_session_running()` stays `True` forever (the failure at test line 953).

The failure was always on the side of caution (data marked unsafe), but the
processes were never actually contained.

A probe confirmed the replacement works on macOS. List all pids with
`ps -A -o pid=,stat=` and filter them with `os.getsid(pid) == sid`. It found every
member of a test session, including one that called `setpgid`. A pid that has
already exited raises only `ProcessLookupError`. No `PermissionError` came back
for other users' processes.

### Root cause 2 — supersession test (a test-side bug)

`aitask_model_supersession.py:314` does `root = Path(args.root).resolve()` on
purpose, and line 223 prints `cd {shlex.quote(str(root))}`. On macOS the temp
dir `/var/folders/...` resolves to `/private/var/folders/...`. The test at
`tests/test_model_supersession.py:873` compares against the unresolved `root`.
The resolved path is the right contract: it is the path the CLI actually worked
on, and `cd` into it works. So the test changes, not the product.

## Implementation

1. **`.aitask-scripts/lib/sync_action_runner.py` — replace the `pgrep -s`
   fallback in `_session_members`** with a portable `ps` + `os.getsid` scan.
   Keep the `/proc` branch unchanged. The new non-`/proc` branch:

   ```python
   try:
       out = subprocess.run(["ps", "-A", "-o", "pid=,stat="],
                            capture_output=True, text=True, timeout=5)
   except (OSError, subprocess.SubprocessError):
       return None
   if out.returncode != 0:
       return None
   members = []
   for line in out.stdout.splitlines():
       try:
           pid_text, state = line.split(None, 1)
           pid = int(pid_text)
       except ValueError:
           return None
       if state.startswith("Z"):
           continue  # zombie: exited, only awaiting its reaper
       try:
           if os.getsid(pid) == sid:
               members.append(pid)
       except ProcessLookupError:
           continue  # exited between listing and asking
       except OSError:
           return None  # e.g. EPERM: it may be a member; never read as gone
   return members
   ```

   Update the docstring and comments to name the two backends. The fail-closed
   rules match the `/proc` branch: any unknown result gives `None`, and only a
   pid that has vanished is skipped. This also adds the zombie filter that the
   `pgrep` branch never had. The `ps` row of the scan itself has exited by the
   time `getsid` runs, so it is skipped as `ProcessLookupError`. It is never in
   `sid`'s session anyway.

2. **`tests/test_sync_action_runner.py` — pin the non-`/proc` backend on every
   platform.** Add these tests next to the `/proc` backend tests (~line 981).
   Each forces the fallback by patching `sync_action_runner.os.path.exists` to
   return `False` for `"/proc/self/stat"`:
   - `test_ps_backend_lists_a_live_session`: `_session_members(os.getsid(0))`
     contains `os.getpid()`, and `sync_session_running` is `True`.
   - `test_ps_backend_reports_an_ended_session_empty`: start
     `sh -c 'exit 0'` with `start_new_session=True` and `wait()` it. Its pid's
     session is then `[]`, and `sync_session_running` is `False`.
   - `test_ps_backend_unknown_is_not_gone`: patch `os.getsid` to raise
     `PermissionError` and `ps` to fail (`returncode=1` via a mocked
     `subprocess.run`). Each case gives `None` / running=`True`.
   - `test_ps_backend_skips_a_vanished_pid`: patch `os.getsid` to raise
     `ProcessLookupError` for every pid. The result is `[]`.
   - **Zombie filtering, made deterministic.** The ended-session test above
     `wait()`s first, so the child is reaped before the query and no zombie
     ever reaches the filter. A regression that dropped the `Z` check would
     still pass it. These cases mock the `ps` listing instead: patch
     `sync_action_runner.subprocess.run` to return a `CompletedProcess` with
     fixed rows, and patch `sync_action_runner.os.getsid` to map every listed
     pid to the probed sid (4242):
     - `test_ps_backend_zombie_only_session_is_empty`: rows `"4242 Z"`,
       `"4243 Z+"` → `_session_members(4242) == []`, and
       `sync_session_running(4242)` is `False`. A zombie-only session must not
       keep task data marked unsafe.
     - `test_ps_backend_counts_only_live_members`: rows `"4242 Ss"`,
       `"4243 Z"`, `"4244 R+"`, `"4245 Z+"` → exactly `[4242, 4244]`.

3. **`tests/test_model_supersession.py:873`** — compare against the resolved
   path: `command.startswith(f"cd '{root.resolve()}' && ")`. Add a one-line
   comment saying that the CLI resolves `--root` (so `/var` becomes
   `/private/var` on macOS).

## Verification

- **Pre-fix control (already run):** both modules fail on unfixed `main` as
  listed above. Before step 1, also run the new step-2 tests and confirm that
  `test_ps_backend_lists_a_live_session` **fails** against the old `pgrep -s`
  code on macOS (it returns `None`).
- **Zombie-filter control:** after step 1, temporarily remove the
  `if state.startswith("Z"): continue` line and confirm that both zombie cases
  fail (the zombie-only case returns `[4242, 4243]`, and the mixed case
  includes 4243/4245). Then restore the line. This shows that the tests pin the
  filter rather than passing by accident.
- After the change:
  - `~/.aitask/venv/bin/python -m unittest tests.test_sync_action_runner` → OK
  - `~/.aitask/venv/bin/python -m unittest tests.test_model_supersession` → OK
  - Full suite: `bash tests/run_all_python_tests.sh`, read only the last line
    (`PYTHON SUITE: …`). It should show no failures in these two modules. Any
    other failure gets compared against t2096's baseline (10 failures, all in
    these two modules) and reported.
- `shellcheck` is not needed (no shell files are touched).

## Step 9 (Post-Implementation)

Commit the code (`bug: … (t2113)`), then archive the task per the workflow's
Step 9.

## Risk

### Code-health risk: low
- On macOS the stop path now really signals the sync session's members for the first time (it was a silent no-op before). The targets are only processes in the session that `start_new_session` created for the sync, so the sid is the sync's own pid and cannot be another session. · severity: low · → mitigation: none (covered by the existing containment suite, which now runs for real on macOS)
- The new zombie filter could regress silently if only real-process tests covered it, because a reaped child never shows as `Z`. A dropped filter would leave a zombie-only session reading as "running", which keeps task data marked unsafe. · severity: medium (residual: low) · → mitigation: covered in-plan by step 2's mocked zombie-only / mixed listings and the zombie-filter control
- `ps` is now called on every poll of `_wait_session_empty` on non-`/proc` hosts, where `pgrep` was called before. The cost is similar (one fork per poll). · severity: low · → mitigation: none

### Goal-achievement risk: low
- Once membership is visible, other macOS-specific containment failures could show up in the 9 tests (for example, timing in the nested bounded-runner cases). · severity: low · → mitigation: none (the verification step runs the module; anything new is diagnosed in this task)
