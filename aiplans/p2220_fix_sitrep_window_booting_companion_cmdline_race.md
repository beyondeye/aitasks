---
Task: t2220_fix_sitrep_window_booting_companion_cmdline_race.md
Base branch: main
Output branch: main
---

# t2220 — Fix the booting-companion cmdline race in test_sitrep_window.py

## Context

`tests/test_sitrep_window.py::MatcherTests::test_booting_companion_without_a_marker_does_not_match`
(line ~169) spawns `python -c "import time; time.sleep(30)" minimonitor` and
immediately classifies its pid through `match_sitrep_pane` → `pane_is_helper` →
`_is_companion_process` (`.aitask-scripts/monitor/monitor_core.py:436`), which reads
`/proc/<pid>/cmdline` and looks for `minimonitor`. It failed once in a loaded
parallel suite run (seen during t2217) and passes when run alone.

**Root cause, measured during planning.** `Popen` returning does not mean the
child's new argv can be read yet. CPython's vfork path lets the parent resume
mid-exec, while the child's cmdline is still the parent's argv or is empty
(the new mm has no args yet). Probe below: reading cmdline straight after
`Popen` returned:

| condition | has `minimonitor` | empty | parent's argv |
|---|---|---|---|
| idle box, 400 spawns | 21 | 377 | 2 |
| all cores busy, 400 spawns | 109 | 239 | 52 |
| **all cores busy, with a stdout readiness handshake** | **400** | 0 | 0 |

Either wrong reading makes `_is_companion_process` return False. The pane then
falls through to the name+cwd fallback and `match` returns `"%9"`, not `None`,
so the test fails. The test usually passes only because the helper calls between
spawn and classify take a few hundred microseconds; under load that margin goes.

This is a test-harness race, not a production defect: a real companion pane is
classified long after its exec has finished. Production code is left alone.

## Approach

Keep the real-process integration, which is the point of the test (the real cmdline
rung of the shared rule, with no marker). Wait for a readiness signal from the
child that does not depend on the classifier under test: the child prints a token
once its Python code is running. By then exec has finished and argv is in place.
This needs no polling of the classifier and no seam injection, and it works on the
macOS `ps` fallback too. The wait for the token is bounded by a generous deadline
(see Step 1).

### Step 1 — edit `tests/test_sitrep_window.py` (the one test)

Replace the body of `test_booting_companion_without_a_marker_does_not_match`:

```python
    def test_booting_companion_without_a_marker_does_not_match(self):
        """No marker yet: the cmdline fallback of the shared rule classifies it.

        `Popen` returning does not mean the child's new argv is readable: the
        parent resumes mid-exec, while `/proc/<pid>/cmdline` is still empty or
        the parent's argv (t2220). The child announces itself from its own Python
        code, which runs only after exec has completed, so the cmdline rung reads
        the real `minimonitor` argv rather than racing the exec.
        """
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import sys, time; print('ready', flush=True); time.sleep(30)",
             "minimonitor"],
            stdout=subprocess.PIPE)
        self.addCleanup(proc.stdout.close)   # LIFO: runs last
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        problem = await_announcement(proc, READY_DEADLINE_S)
        if problem:
            self.fail(problem)
        companion = pane(id="%9", pid=proc.pid, window="agent-sitrep", cwd=self.ROOT)
        self.assertIsNone(self.match([companion]))
```

New module-level helper, placed beside `pane()` / `render()` (it returns the failure
text so the test owns `self.fail`, and the control below can drive it directly):

```python
# A generous ceiling, far above interpreter start-up on a loaded box. It turns a
# wedged stand-in into a failure instead of a hang, and it is never a sleep.
READY_DEADLINE_S = 20.0


def await_announcement(proc, deadline_s: float, token: bytes = b"ready\n") -> str | None:
    """Wait, bounded, for ``proc`` to write ``token`` on its stdout pipe.

    None on success, else why not. Three exits: the token arrives, EOF (the child
    exited), or the deadline passes (the child is alive but stopped or wedged before
    writing). A bare ``readline()`` only ends on the first two, so it hangs on the
    third. Raw ``os.read`` on the fd, never the buffered reader, so ``select`` never
    misses bytes held in a userspace buffer.
    """
    fd, buf = proc.stdout.fileno(), b""
    deadline = time.monotonic() + deadline_s
    while b"\n" not in buf:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            return (f"stand-in did not announce itself within {deadline_s}s "
                    f"(read so far: {buf!r})")
        chunk = os.read(fd, 64)
        if not chunk:
            return f"stand-in exited before announcing itself (read so far: {buf!r})"
        buf += chunk
    return None if buf == token else f"unexpected announcement {buf!r}"
```

Supporting edits in the same file: add `import select` and `import time` to the
stdlib imports (only `fcntl`, `os`, `subprocess`, `sys`, `tempfile` and `unittest`
are there now; the module is already POSIX-only through `fcntl`).

### Step 2 — pin the deadline path with a regression test

Add `test_await_announcement_is_bounded_for_a_stopped_child` to `MatcherTests`. It
spawns a stand-in that `SIGSTOP`s itself before printing
(`"import os, signal; os.kill(os.getpid(), signal.SIGSTOP); print('ready', flush=True)"`),
registers the same `stdout.close / wait / kill` cleanups, and calls
`await_announcement(proc, 0.5)`. It asserts that the result contains "did not
announce itself" and that the call returned within 5 s of wall clock (measured
with `time.monotonic()`; 10× headroom, never a sleep). Add a sibling case where
the child exits without printing (`-c "pass"`): the result contains "exited before
announcing itself". Together these pin all three exits. A future switch back to
`readline()` would hang the stopped-child case, and the pytest run's own wall time
would show it, so add a `signal.alarm(10)` guard (with `SIGALRM` handler restore in
cleanup) so the regression fails instead of hanging.

**Boundedness, stated precisely.** The wait ends in one of three ways: the
`ready\n` line arrives, EOF arrives (the child exited), or the deadline passes (the
child is alive but stopped or wedged before printing). A bare `readline()` covers
only the first two. A planning probe with a child that `SIGSTOP`s itself before
printing hung `readline()` until an outer `timeout 5` killed it (rc 124), while
the `select` loop above returned at its 2 s probe deadline. Every failure path
goes through `self.fail`, and the `kill → wait → stdout.close` cleanups are
registered before the wait, so they run on a failure too. Reading the raw fd with
`os.read` (never the buffered `proc.stdout` reader) keeps `select` accurate, since
nothing can sit unseen in a userspace buffer. The real-process classification
assertion is unchanged.

No other tests share this pattern. Checked: `test_agent_sessions_lease.py:135`
uses the spawned pid only for liveness (`kill 0`), which is valid before exec;
`test_monitor_companion_filter.py:78` reaps its child to get a dead pid. Every
other cmdline-related test mocks the reader.

## Verification

1. **Pre-fix control and post-fix stress (durable repro).** Run this scratch
   harness against the current tree *before* editing, then again after,
   with all cores busy:
   ```bash
   P=~/.aitask/venv/bin/python
   for i in $(seq 1 $(nproc)); do (timeout 60 sh -c 'while :; do :; done' &); done
   cd tests && "$P" - <<'EOF'
   import sys, unittest
   sys.argv = ["x"]
   import test_sitrep_window as t
   name = "test_booting_companion_without_a_marker_does_not_match"
   fails = 0
   for _ in range(300):
       r = unittest.TestResult()
       t.MatcherTests(name).run(r)
       fails += len(r.failures) + len(r.errors)
   print(f"FAILS {fails}/300")
   EOF
   ```
   Before the fix: some failures are expected (the race is real). After the fix:
   `FAILS 0/300`. Record both counts in Final Implementation Notes. (The
   `MatcherTests` class name and the module's import side effects are
   confirmed before running.)
1b. **Deadline-path control.** Step 2's test is the durable control. In addition,
   confirm once by hand that swapping `await_announcement`'s body for
   `proc.stdout.readline()` makes the stopped-child test fail through the
   `SIGALRM` guard rather than hang (a scratch mutant: patch the module attribute
   in a harness, never the tree). Also confirm that no stray stand-in survives:
   `pgrep -f 'signal.SIGSTOP'` is empty after the run.
2. `bash tests/run_all_python_tests.sh --test-dir` is not needed; run the file:
   `~/.aitask/venv/bin/python -m pytest tests/test_sitrep_window.py -q`, which
   should report 44 passed (42 existing tests plus the 2 new deadline-path tests).
3. Probe scripts used for the root-cause table (kept verbatim for durability):
   - `race_probe.py`: Popen `[sys.executable, "-c", "import time; time.sleep(30)", "minimonitor"]`,
     read `/proc/<pid>/cmdline` at once, and classify the read as has_kw, empty or other.
   - `handshake_probe.py`: the same spawn with a `print('ready', flush=True)` child and
     `stdout=PIPE`, reading one line before the cmdline read.

## Step 9 (Post-Implementation)

Commit `bug: Wait for the booting-companion stand-in to announce itself before classifying (t2220)`
on main (current-branch mode), then archive per Step 9.

## Risk

### Code-health risk: low
None identified. Changes stay in one test file: one test body, one module helper and two small regression tests. Production code is untouched.

### Goal-achievement risk: low
None identified. The race mechanism was measured directly (table above), and the
handshake removed it in 400/400 loaded trials. The stress control in Verification
step 1 shows it on the real test.
