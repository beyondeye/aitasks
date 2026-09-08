---
Task: t1729_fix_macos_only_suite_failures.md
Base branch: main
Output branch: main
---

# t1729 — Fix macOS-only Python suite failures

## Context

`bash tests/run_all_python_tests.sh` on macOS leaves 3 failures / 6 errors across
four modules, out of 6840 tests. t1705_4 verified each against a stashed clean
tree, so none is a regression — they are pre-existing, macOS-only, and they are
the entire non-green residue of the suite on this platform.

All three root causes are now **reproduced and measured on this box** (see
Diagnosis below). Two match the task's suggested fix. The third — the
codebrowser startup-focus failure the task explicitly deferred as "diagnose
separately" — turned out to be a different, sharper defect than the boot-budget
flake the carve-out documents, and it has a latent twin in
`tests/test_board_startup_focus_live.py`.

Goal: the four modules pass on macOS.

**Scope of the completion claim — deliberately narrowed.** This session can
prove the macOS half only. There is no Linux box reachable from here (no
container runtime: `docker`, `podman`, `colima`, `lima`, `orbctl`, `multipass`
and `vagrant` are all absent, and no daemon is reachable), and **no CI runs the
Python suite** — the four GitHub workflows are contribution-check, Hugo, release
and release-packaging. So "no behavioural change on Linux" is an *argument*
here, not a measurement (the argument is set out under Cross-platform audit).
The task therefore completes claiming macOS only, and the spawned
`verify_macos_fixes_on_linux` follow-up is named as the **outstanding proof** —
recorded as such in the Final Implementation Notes, not as an optional extra.

## Diagnosis (measured, not inferred)

**1. `shutil.copy2` of a SIP-restricted binary.** `/bin/sleep` carries the macOS
`restricted,compressed` file flags:

```
-rwxr-xr-x  1 root  wheel  restricted,compressed  101168  /bin/sleep
```

`copy2` runs `copystat`, which calls `chflags` on the destination →
`PermissionError: [Errno 1] Operation not permitted`. `shutil.copy` copies the
bytes and the permission mode but not the flags, and succeeds (measured: result
is `0o755` and executable). Both call sites already `chmod(dest, 0o755)`
immediately after, so nothing depended on `copy2`'s extra semantics.

- `tests/test_agent_keys.py:43` → 5 errors
- `tests/test_prompt_scoping_live.py:69` → 1 error in `setUpClass` (0 tests run)

**2. `TMUX_TMPDIR` overruns the AF_UNIX `sun_path` limit.** The fixture builds
its socket dir with a bare `mkdtemp`, which on macOS lands under `$TMPDIR` =
`/var/folders/<hash>/<hash>/T/`. tmux then appends `tmux-<uid>/<socket>`:

```
106  /private/var/folders/fm/8d6…/T/ait_t952_1_tmux_vum4kyz4/tmux-501/ait_t952_1_test   → "File name too long"
 62  /private/tmp/ait_t952_1_tmux_8w8g6tx3/tmux-501/ait_t952_1_test                     → connects
```

`sun_path` is ~104 bytes. Anchoring the fixture dir at `/tmp` gives 62 and the
gateway spawn succeeds (verified end-to-end: `list-sessions` returns the created
session). `tests/test_tmux_exec.py:481` → 1 failure.

**3. `_wait_for_shell` never waits.** The helper polls until
`pane_current_command` leaves the interpreter, matching against the exact,
lowercase tuple `("python", "python3", "pypy", "pypy3")`. On macOS the framework
CPython build reports **`Python`** — capital P:

```
t= 0.02  cmd=Python  marker=YES
t= 0.28  cmd=zsh     marker=no
```

`"Python"` is not in that tuple, so the wait returns on its **first poll, while
the app is still running and still drawn**. The subsequent
`assertNotIn(BOOT_MARKER, final)` then reads the codebrowser's own screen and
fails. Confirmed by the failure output: the pane *had* returned to the shell
logic-wise (the app quits correctly — this is not a focus regression), and my
instrumented rerun shows the marker clearing 0.25s later.

This is **not** the documented under-load boot-budget flake; the carve-out
rationale in `CLAUDE.md` does not explain it, exactly as the task suspected.

`tests/test_board_startup_focus_live.py:268` carries a byte-identical predicate.
It does not fail today only because `ait board` runs on the PyPy fast path,
whose binary is named `python3` (lowercase) — so the same latent defect is one
missing PyPy install away from making that module's relaunch assertions pass
vacuously. Same defect family, two-word fix, so it is in scope.

Not in scope (checked and clean): the other 11 `shutil.copy2` call sites under
`tests/` all copy repo files or the Homebrew python binary, none of which carry
restricted flags.

## Implementation

### Pre-phase (risk mitigations)

**`baseline_board_focus_live`** — before editing anything, record the current
result of the module whose waits this task makes non-vacuous:

```bash
log="${TMPDIR:-/tmp}/t1729_board_baseline.log"
~/.aitask/venv/bin/python -m unittest tests.test_board_startup_focus_live >"$log" 2>&1
echo "baseline_exit=$?"
tail -5 "$log"
```

**Do not pipe the interpreter into `tail`** — the shell status would then be
`tail`'s `0` however the module fared, which is precisely the trap `CLAUDE.md`
documents for the suite runner, and it would silently destroy the one signal
this baseline exists to capture. Redirect to a log, record `baseline_exit`, and
read the tail separately. (`set -o pipefail` / `${PIPESTATUS[0]}` would also
work; the redirect is simpler and keeps the full log for comparison.)

Record **both** `baseline_exit` and the tail in the Final Implementation Notes.
If that module fails after step 5, this baseline is what distinguishes "the
predicate fix revealed a pre-existing failure" from "the predicate fix caused
one" — and on this box, where `ait board` runs on PyPy (`python3`, lowercase),
the expected baseline is `baseline_exit=0`.

### 1. `tests/test_agent_keys.py` — `_fake_agent_binary` (line 43)

Replace `shutil.copy2` with `shutil.copy`, and extend the existing docstring
with the reason so the next reader does not "restore" `copy2`:

```python
def _fake_agent_binary(tmpdir: str, name: str) -> str:
    """A copy of /bin/sleep named `name`, so its `comm` IS `name`.

    A copy rather than a symlink: `ps -o comm=` reports the executable's name,
    and a symlink would report the target's on some platforms.

    `copy`, not `copy2`: `copy2` also runs `copystat`, which calls `chflags` on
    the destination — and macOS ships /bin/sleep with the SIP `restricted` flag,
    so that raises PermissionError (t1729). Only the bytes and the executable
    bit matter here, and `chmod` below sets the latter explicitly.
    """
    dest = os.path.join(tmpdir, name)
    shutil.copy(shutil.which("sleep") or "/bin/sleep", dest)
    os.chmod(dest, 0o755)
    return dest
```

### 2. `tests/test_prompt_scoping_live.py` — `setUpClass`'s `fake()` (line 69)

Same one-word change, with a one-line comment referencing t1729 and the
`test_agent_keys.py` twin.

### 3. `tests/test_tmux_exec.py` — short socket dir

Add a module-level helper next to the other module-level helpers, and call it
from `TestGatewayIntegration.setUp` (line 481) in place of the bare `mkdtemp`:

```python
def _short_socket_tmpdir(prefix: str) -> str:
    """A TMUX_TMPDIR short enough for AF_UNIX's ~104-byte `sun_path` limit.

    tmux appends `tmux-<uid>/<socket>` to TMUX_TMPDIR, and on macOS $TMPDIR is
    `/private/var/folders/<hash>/<hash>/T/` — ~53 bytes before this fixture adds
    anything, which pushes the socket to 106 bytes and makes every connect fail
    with "File name too long" (t1729). `/tmp` is short and present on every
    platform this suite runs on; fall back to the platform default if it is not.
    """
    base = "/tmp" if os.path.isdir("/tmp") else None
    return tempfile.mkdtemp(prefix=prefix, dir=base)
```

`tearDown` already `rmtree`s `self._tmpdir`, so cleanup is unchanged.

### 4. `tests/test_codebrowser_startup_focus_live.py` — the real fix

**(a)** Add a module-level predicate and use it in `_wait_for_shell` (line 274):

```python
def _is_interpreter(command: str) -> bool:
    """Is `pane_current_command` still the app's interpreter?

    Matched case-insensitively and by prefix, not against an exact lowercase
    list: a macOS framework CPython reports `Python` (capital P), and a
    versioned build can report `python3.13` / `pypy3.11`. The old exact tuple
    matched none of those, so `_wait_for_shell` returned on its FIRST poll while
    the app was still running — and the post-quit capture then read the app's
    own screen, failing an assertion about a defect that was not there (t1729).

    `tests/test_board_startup_focus_live.py` carries the same predicate for the
    same reason; keep the two in step.
    """
    return command.lower().startswith(("python", "pypy"))
```

and in `_wait_for_shell`:

```python
            if command and not _is_interpreter(command):
                return
```

**(b)** Make the post-quit screen assertion poll rather than sample once. Even
with a correct wait, the pane leaving the interpreter and tmux draining the
alternate-screen restore are two different events; they flipped in the same poll
in every measurement, but a single sample makes that a coin toss under load. Add
a budget constant beside the existing ones:

```python
#: After the pane leaves the interpreter, tmux may still be draining the
#: alternate-screen restore. Short, because the two normally flip in the same
#: poll — exceeding it is a genuine "the app's screen is still drawn" FAILURE.
SCREEN_CLEAR_TIMEOUT_S = 5.0
```

and replace the final `assertNotIn(BOOT_MARKER, final)` in
`test_bare_q_quits_a_codebrowser_launched_outside_a_git_repo` with a poll that
breaks when `BOOT_MARKER` is gone and otherwise fails with the **same** message
and the last capture. Failure semantics are preserved: an app that really left
its screen drawn still fails.

**(c)** Update the module docstring's "What this test can and cannot fail on"
paragraph to record that the interpreter predicate is load-bearing on macOS.

### 5. `tests/test_board_startup_focus_live.py` — the latent twin (line 268)

Add the identical `_is_interpreter` helper and use it in that module's
`_wait_for_shell`. No other change; the module's assertions are unaffected on a
PyPy-backed box and become non-vacuous on a CPython-backed one.

The two live modules already duplicate `_capture` / `_pane_command` / `_send` /
`_search_*` / `_wait_for_shell` wholesale — they are deliberately parallel but
independent — so duplicating a three-line predicate matches the existing shape
and stays under the 3-file single-sourcing threshold in
`aidocs/framework/planning_conventions.md`. Each copy names the other site.

### Cross-platform audit (`aidocs/framework/aitasks_extension_points.md`)

No `_macos` / `_linux` branch pair is involved — these are single code paths, so
the symmetric-branch audit is trivially satisfied.

**Linux-invariance argument, per change.** This is reasoning, not a measurement
— see the narrowed completion claim in Context. It is written out so the
follow-up has something specific to falsify:

| change | why Linux behaviour is unchanged |
|---|---|
| `copy2` → `copy` (2 sites) | Linux has no `chflags`, so `copystat` never took the failing path there; `copy` still copies the mode bits, and both sites `chmod 0o755` immediately after regardless. |
| `mkdtemp(dir="/tmp")` | On Linux `$TMPDIR` is normally `/tmp` already, so the resulting path is the same one the fixture used before; the `os.path.isdir("/tmp")` guard falls back to the platform default if it is absent. |
| `_is_interpreter` predicate | A strict **superset** of the old exact tuple: `python`, `python3`, `pypy`, `pypy3` all still match under `lower().startswith(("python", "pypy"))`. It can only change behaviour for a name the old tuple missed — and the pane's post-quit process is a shell, never a `python*`/`pypy*` name. |
| polled screen assertion | Strictly **more tolerant** than the single sample it replaces (same predicate, same failure message, now with a budget), so it cannot turn a Linux pass into a failure. |

The residual Linux risk is therefore concentrated in the one place the argument
is weakest — a `/tmp`-less or differently-mounted Linux environment — which is
exactly what `verify_macos_fixes_on_linux` is scoped to check.

## Verification

1. Each module individually, expecting no failures:
   ```bash
   ~/.aitask/venv/bin/python -m unittest tests.test_agent_keys
   ~/.aitask/venv/bin/python -m unittest tests.test_prompt_scoping_live
   ~/.aitask/venv/bin/python -m unittest tests.test_tmux_exec
   ~/.aitask/venv/bin/python -m unittest tests.test_codebrowser_startup_focus_live
   ~/.aitask/venv/bin/python -m unittest tests.test_board_startup_focus_live
   ```
2. **Negative control for fix 4** — the fix must be the *cause* of the pass.
   Temporarily revert `_is_interpreter` to the old exact tuple and confirm
   `test_bare_q_quits_a_codebrowser_launched_outside_a_git_repo` fails again with
   the "screen is still drawn" message, then restore. Without this the new poll
   in (b) alone could be masking the defect rather than fixing it.
3. Full suite, reading **only the last line** for the verdict and preserving the
   exit status (`CLAUDE.md`: piping discards it):
   ```bash
   set -o pipefail
   bash tests/run_all_python_tests.sh 2>&1 | tail -20
   ```
   Expected: `PYTHON SUITE: PASSED (runner=…, exit=0)`, and the 3 failures /
   6 errors gone. `test_codebrowser_startup_focus_live` and
   `test_board_startup_focus_live` are in the serial carve-out, so the run
   exercises both lanes.
4. **State the completion claim explicitly** in the Final Implementation Notes,
   in these terms and no stronger:
   - proved here: the four modules and the full Python suite pass **on macOS**
     (quote the verdict banner), plus the pre-phase `baseline_exit`;
   - argued but **not** proved here: unchanged behaviour on Linux — no Linux box
     is reachable from this session and no CI runs the Python suite. The
     outstanding proof is the spawned `verify_macos_fixes_on_linux` task, named
     by its real `t<id>`.

   Do not write "fixed on macOS and Linux", "cross-platform", or "no regressions
   anywhere" in the notes or the commit message.

## Risk

### Code-health risk: low
- Broadening `_wait_for_shell`'s interpreter predicate turns two previously
  vacuous waits into real ones, which could surface a latent failure in
  `test_board_startup_focus_live.py` that the premature return was masking ·
  severity: low · → mitigation: inline pre-phase baseline_board_focus_live

### Goal-achievement risk: low
- Every fix is verified on macOS only, and **no CI runs the Python suite** (the
  four GitHub workflows cover contribution checks, Hugo and release packaging) —
  so the task body's "not visible on Linux CI" is an assumption, and a Linux-side
  regression would not be caught anywhere. The task cannot close this itself (no
  Linux box or container runtime is reachable), so it is handled by **narrowing
  the completion claim** — see Context and Verification step 4 — with the spawned
  task as the named outstanding proof · severity: low · → mitigation:
  verify_macos_fixes_on_linux

### Planned mitigations
- timing: pre-phase | name: baseline_board_focus_live | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk (the predicate fix makes previously vacuous waits real) | desc: Record test_board_startup_focus_live's result before editing it, so a post-fix failure can be attributed.
- timing: after | name: verify_macos_fixes_on_linux | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: low | addresses: goal-achievement risk (macOS-only verification, no Python-suite CI) | desc: On a Linux box, run the five touched modules and the full Python suite; this is t1729's named outstanding proof, so its checklist must falsify the per-change invariance argument (especially the /tmp socket dir), not merely re-run the suite.

**Reassessment after inlining.** Adding the pre-phase baseline changes neither
level: it is a read-only measurement that touches no file and alters no step.
Code-health stays `low`, goal-achievement stays `low`.

## Post-Implementation

Step 9 applies as usual: current-branch mode (profile `fast`), so nothing is
merged; commit with type `test` (`test: … (t1729)`), then archive the task and
this plan. Step 8d creates the confirmed spawned "after" mitigation
(`verify_macos_fixes_on_linux`); the `risk_evaluated` gate is the task's single
active gate and is recorded post-approval at Step 7.
