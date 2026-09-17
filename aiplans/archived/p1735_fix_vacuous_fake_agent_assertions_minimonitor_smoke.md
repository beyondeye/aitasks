---
Task: t1735_fix_vacuous_fake_agent_assertions_minimonitor_smoke.md
Base branch: main
Output branch: main
---

# t1735 — Give the concern smoke's fake agent panes their real agent name

## Context

`tests/test_minimonitor_concern_smoke.py::FollowedPaneClassificationSmokeTests`
copies `sys.executable` to `<tmpdir>/codex|opencode|claude` and runs the Python
frame/composer stubs under those copies, on the premise that tmux's
`pane_current_command` then reads the agent name.

**Measured this session (macOS 15 / arm64, Homebrew CPython 3.13 venv)** — the
task's premise is right, but its "passes vacuously" consequence is not:

- A pane running a copied interpreter reads `codex` for ~0.4 s, then `Python`
  forever (the framework binary re-execs the app bundle).
- `_paint` already waits for `pane_current_command == agent` and `self.fail`s
  after 30 s, so the class does not pass vacuously — it **fails hard**:
  `env -u TMUX TMPDIR=/tmp python -m unittest tests.test_minimonitor_concern_smoke`
  → `FAILED (failures=17)` in 513 s, every one
  `… pane never rendered the frame exactly (command='Python', …)`.
  **That is the pre-fix control.**
- With the **default macOS `TMPDIR`** (`/var/folders/…/T/`) the whole module
  **skips** in 0.01 s (`skipped=3`): `mkdtemp()` + `tmux-501/ait_t1187_smoke_<pid>`
  goes over the 104-byte unix-socket path limit (`File name too long`). That
  skip is why the module looks "green". It is a second vacuous-green defect in the
  same module, and without fixing it the first fix can't be observed from a
  normal macOS run.

So the fix has two parts: (A) real agent-named pane processes, and (B) a
socket-safe tmpdir base.

## Design: fork launcher (the task's "keep the stub, use a ladder binary where the name matters")

tmux names a pane after its **foreground process-group leader**, which is the
pane's own pid (tmux `setsid`s the child). So the pane runs a tiny launcher,
`_AGENT_LAUNCHER`, a Python source string written to the tmpdir like the other stubs:

```python
import os, sys
agent, stub = sys.argv[1], sys.argv[2:]
if os.fork() == 0:
    os.execv(sys.executable, [sys.executable, *stub])   # child: the repaint/composer stub
os.execv(agent, [agent, "100000"])                        # pane pid becomes the agent-named binary
```

- The pane pid execs the `fake_agent_binary` sleeper, so `pane_current_command`
  is really `codex` / `opencode` / `claude`. Rung 1 of `agent_key_from_pane`
  resolves it through the real binary name, not a transient pre-exec name.
- The stub stays a Python child with the pty inherited on fds 0/1/2. It is in
  the same (foreground) process group, so the composer stubs' `tty.setraw` and
  stdin reads keep working. No shell `&` is involved, so stdin isn't redirected
  to `/dev/null`.
- No stub rewrite. `_FRAME_STUB`, `_COMPOSER_STUB`, `_CODEX_COMPOSER_STUB` and
  the `RecheckInjectionSmokeTests` class, which runs the composer under plain
  `sys.executable` and does not depend on the name, are unchanged.
- Cleanup is **not assumed**. The pre-phase measures that `kill-server` ends both
  the sleeper and the stub child (probe (c)), and main step 8 makes a leak fail
  the module on every later run.

## Implementation steps

### Pre-phase (risk mitigations)

1. [probe_fork_launcher] Before editing the test, in a scratch script (private
   `TMUX_TMPDIR` under `/tmp`, private `-L` socket, `TMUX` unset), start a pane as
   `sys.executable launcher.py <fake_agent_binary codex> composer_stub.py`. Check
   that (a) `list-panes -F '#{pane_current_command}'` settles on `codex` and
   **stays** there over ~5 s, and (b) `send-keys -t <pane> hi` shows up on
   the pane's `❯` line in `capture-pane`, which proves the child still owns the tty
   in raw mode, and (c) **cleanup**. Record both PIDs: the sleeper is `#{pane_pid}`,
   and the stub child comes from `pgrep -P <pane_pid>`. Then `kill-server` the private
   server and require **both** to be gone (`os.kill(pid, 0)` → `ProcessLookupError`)
   within a bounded 5 s poll. Run (c) twice, once for a pane running the
   stdin-reading composer stub and once for `_FRAME_STUB`, which never reads stdin
   and only writes on mtime change, so it can't rely on EIO and depends entirely on
   SIGHUP delivery.
   - If (c) fails for either stub, switch to the **watchdog variant** of the
     launcher. The child doesn't `execv`; it sets `sys.argv = stub` and starts a
     daemon thread that polls `os.getppid()` every 0.2 s and calls `os._exit(0)` once
     it differs from the launcher's pid (reparenting means the sleeper died). Then
     it runs `runpy.run_path(stub[0], run_name="__main__")`. Re-run (a)–(c) on that
     variant.
   - If (a), (b) or (c) still fails, stop and re-plan rather than editing the test.
   The launcher adopted in main step 2 is whichever variant passed all three.

### Main steps (all in `tests/test_minimonitor_concern_smoke.py`)

1. **Import the helper.** `tests/` is already on `sys.path`; `fake_agent_binary`
   lives in `tests/lib/`, so add `sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))`
   (same as `test_prompt_scoping_live.py`), then
   `from fake_agent_binary import FakeAgentBinaryUnavailable, fake_agent_binary`.
2. **Add `_AGENT_LAUNCHER`** (above) next to the other stub sources, with a
   comment explaining why. A copied interpreter re-execs as `Python` on macOS (measured,
   t1735), and a symlink or `exec -a` doesn't help because tmux names the resolved
   executable (see `tests/lib/fake_agent_binary.py`). The fork keeps the stub
   while the pane pid carries the name.
3. **Build the binaries once, up front** in
   `FollowedPaneClassificationSmokeTests.setUpClass`:
   `cls.agent_bins = {a: fake_agent_binary(cls.tmpdir, a) for a in ("codex", "opencode", "claude")}`
   (real-file form, no `allow_symlink`). `FakeAgentBinaryUnavailable` → `raise unittest.SkipTest(str(exc))`
   because that means the environment is unavailable, which matches the class's
   documented skip-vs-fail rule. Delete both `shutil.copy2(sys.executable, …)` sites
   and the ETXTBSY reuse comment. Each name is built exactly once before any pane
   execs it, so that race no longer exists.
4. **Route every agent-named pane through the launcher**. That's the 3 followed
   panes, the 3 `claude` shadow panes, and the `codex_shadow` followed and shadow panes:
   `sys.executable, launcher, <agent_bin>, <stub>, <stub args…>`.
   Update `cls.pane_argv[agent]` to the same tuple. Grep its consumers first and
   keep whatever they re-launch consistent.
5. **Fix the comments that state the premise** ("`pane_current_command` must
   really be the agent name…", the class docstring). Say how the name is now
   guaranteed, not only that it has to be.
6. **Socket-safe tmpdir (part B)** for all three classes' `mkdtemp` calls:
   use a module-level helper
   `_short_tmpdir(prefix)` → `tempfile.mkdtemp(prefix=prefix, dir="/tmp" if os.path.isdir("/tmp") else None)`,
   with a comment recording the measured `File name too long` skip. The
   `addClassCleanup(shutil.rmtree …)` stays as is.
7. **Guard the fixture itself.** Add
   `test_pane_commands_are_the_agent_names` to the class. It polls `list-panes`
   (bounded, like `_paint`) until every followed and shadow pane reports its
   agent name, and asserts that the name is still there after a further ~1 s. A
   copied-interpreter regression (name correct only for the first instant) then
   fails with a clear message instead of as 17 frame timeouts.
8. **Durable leak check in `tearDownClass`.** After `_tmux("kill-server")`, poll
   (bounded 5 s) `pgrep -f <cls.tmpdir>`. Every launcher, sleeper and stub has the
   per-class tmpdir in its argv, and nothing else does. If processes are still
   alive at the deadline, `os.kill` them with SIGKILL, **then** raise
   `AssertionError` naming the surviving pids and commands. Killing first stops a
   failure from leaking; raising turns the leak into a reported class-teardown
   error instead of a silent one. When `pgrep` is absent, skip the check (it's an
   optional binary) without failing.

## Verification

Run from this session (`TMUX` set to `-L ait`, but the module uses its own
per-PID socket and `TMUX_TMPDIR`, so it is safe with `env -u TMUX`):

1. **Pre-fix control (already recorded above):** `FAILED (failures=17)` with
   `command='Python'`, and a default-TMPDIR run gives `skipped=3`.
2. **Fixed, default TMPDIR:** `env -u TMUX ~/.aitask/venv/bin/python -m unittest -v tests.test_minimonitor_concern_smoke`
   → all classes **run** (no `File name too long` skip) and `OK`, with 0 skips.
3. **State change check (task item 2):** the `_case` assertions
   `s1.agent_key == agent` and the kind or verdict assertions now run and pass.
   Before the fix they were never reached, so the assertions do change state and
   the comment is truthful once corrected.
3b. **Leak check control:** in a scratch copy of the module, replace
   `kill-server` in the classification class's teardown with a no-op, run only that
   class, and confirm the step-8 check **raises** and names the surviving pids
   (it SIGKILLs them first, so nothing is left behind). Then confirm the real
   module's teardown passes it, with `pgrep -f ait_t1518_follow_` empty afterwards.
4. Suite verdict: `bash tests/run_all_python_tests.sh --test-dir` is unnecessary
   for one module. Run the module through the serial unittest command above and
   report its last line.
5. Post-implementation: Step 9 (Post-Implementation) — commit, archive.

## Follow-ups to consider at review

- Other modules that set `TMUX_TMPDIR` to a default `mkdtemp()`
  (`test_launch_in_tmux_pane_pid.py`, `test_pane_state_probe.py`,
  `test_tmux_exec.py`, `tests/lib/tmux_socket_containment.py`) may skip the same
  way on macOS. Run each once under default TMPDIR and file a follow-up for any that
  skip with `File name too long`.

## Risk

### Code-health risk: low
- Test-only change in one module. The launcher adds one more fixture process per pane, and a stub child that never reads stdin could outlive `kill-server` if SIGHUP isn't delivered. It would leak processes and stale pane/file activity across runs while the module still looks clean · severity: low (residual — gated by inline pre-phase probe_fork_launcher (c), with the watchdog-variant fallback; kept durable by main step 8) · → mitigation: inline pre-phase probe_fork_launcher

### Goal-achievement risk: low
- The fork launcher is not yet measured under tmux. If the pty ownership or pgrp assumption is wrong (name reverts, or the composer stub loses the tty), the class keeps failing · severity: low (residual — addressed by inline pre-phase probe_fork_launcher, which stops before any edit if the assumption fails) · → mitigation: inline pre-phase probe_fork_launcher
- Linux CI names the pane via `/proc` rather than `proc_pidinfo`. The design relies on the pgrp-leader rule on both platforms, but only macOS is available here · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: probe_fork_launcher | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: fork launcher pgrp/tty assumption unmeasured | desc: scratch tmux probe that the launcher pane keeps its agent name, the stub keeps the tty, and kill-server ends both sleeper and stub (frame + composer) within 5 s

## Final Implementation Notes

- **Actual work done:** All plan steps landed in `tests/test_minimonitor_concern_smoke.py`: the `fake_agent_binary` import, `_short_tmpdir()` for all three classes, `_AGENT_LAUNCHER`, binaries built once up front, every agent-named pane (3 followed, 3 claude shadows, codex_shadow followed + shadow) routed through the launcher, premise comments rewritten, `test_pane_commands_are_the_agent_names`, and the `tearDownClass` leak check.
- **Pre-phase probe_fork_launcher (done):** the exec variant passed everything. (a) The pane read `{'codex'}` across 5 s. (b) Typed `hi` arrived as `❯\xa0hi` on the composer line. (c) After `kill-server`, both sleeper and stub were gone within 5 s for both the composer stub and `_FRAME_STUB`. The watchdog variant was not needed.
- **Deviations from plan:** none in substance. `pane_argv` turned out to be written but never read, so it was just updated to the launcher tuple.
- **Verification results:**
  - Pre-fix control: default TMPDIR gave `OK (skipped=3)` in 0.01 s, and `TMPDIR=/tmp` gave `FAILED (failures=17)` in 513 s with `command='Python'`.
  - Fixed, default TMPDIR: `Ran 17 tests in 14.487s, OK`, 0 skips. The `_case` `agent_key == agent` and kind/verdict assertions are now actually reached.
  - Leak-check control: importing the real module with `kill-server` suppressed made teardown raise `fixture processes outlived kill-server (now SIGKILLed)` listing the tmux server, 8 sleepers and 8 stubs. `pgrep` found nothing afterwards.
- **Follow-up check:** the other `TMUX_TMPDIR` modules (`test_launch_in_tmux_pane_pid`, `test_pane_state_probe`, `test_tmux_exec`, `test_agent_restore`, `test_minimonitor_shadow_pick`, `test_monitor_shadow_pick`) run with 0 skips under the default TMPDIR. The socket-length skip was specific to this module, so there is no follow-up.
- **Key decisions:** kept the Python stubs and put the agent name on the pane pid through a fork launcher rather than rewriting the stubs. Leaks are SIGKILLed before they are reported, so a failing teardown cannot itself leak.
- **Upstream defects identified:** None
- **Issues encountered:** the task's "passes vacuously" claim was inaccurate. The module either skipped (default macOS TMPDIR) or failed hard. Both were fixed.

## Post-Review Changes

### Change Request 1 (2026-09-17 13:20)
- **Requested by user:** the leak check returned early when `pgrep` was missing, so a tmux-capable environment without that optional binary could leak forked stubs while the module still passed — contradicting the durable-cleanup mitigation. Track fixture PIDs at launch or use a portable fallback instead.
- **Changes made:** `_AGENT_LAUNCHER` now takes a pid-file path as `argv[1]` and writes both its own pid (the pane pid, which becomes the agent binary) and the forked stub's pid before exec'ing. `_assert_no_fixture_process_survives` reads those files and decides purely with `os.kill(pid, 0)` — no process search, no optional binary, and the check now runs everywhere. `ps` is used only to label a survivor in the message, degrading to `?`; the verdict never depends on it. Two defects found while verifying: survivors were described one-at-a-time *while* being killed, so each stub read `?` because killing its agent binary made tmux tear the pane down first (now all are described before any is killed); and `pane_argv` called `as_agent()` a second time, allocating a pid file no process would ever write (now it reuses the launched pane's argv).
- **Files affected:** `tests/test_minimonitor_concern_smoke.py`
- **Re-verified:** module `Ran 17 tests in 13.680s, OK` (default TMPDIR, 0 skips). Leak control with `kill-server` suppressed now names all **16** processes (8 agent binaries + 8 stubs) with full command lines, SIGKILLs them, and leaves nothing behind.

### Change Request 2 (2026-09-17 13:35)
- **Requested by user:** the pid files record numbers but no identity. If a fixture process exits and its pid is reused while another survivor keeps the 5 s wait alive, `os.kill(pid, 0)` would treat the replacement as the fixture and the later SIGKILL could terminate an unrelated process. Validate the command before signalling, or report an unverified pid without killing it.
- **Changes made:** the aliveness test became a three-state identity check (`gone` / `ours` / `unverified`). A pid that exists is described with `ps` and counts as a fixture process only when its command still contains this class's tmpdir; a pid whose command names something else is treated as recycled and **ignored entirely** (neither reported nor signalled); a pid `ps` cannot describe is reported as `[unverified]` and **never signalled**. Only `[ours]` is SIGKILLed. The report labels each survivor with its state.
- **Files affected:** `tests/test_minimonitor_concern_smoke.py`
- **Re-verified:** module `Ran 17 tests in 14.372s, OK` (default TMPDIR, 0 skips). New controls: a live `sleep 60` planted in a pid file is not reported and stays alive (recycled path, returns in 0.0 s); with `_process_command` stubbed to `?` the same pid is reported `[unverified]` and still alive afterwards. The kill-server-suppressed control still names all 16 fixture processes as `[ours]`, kills them, and leaves nothing behind.
