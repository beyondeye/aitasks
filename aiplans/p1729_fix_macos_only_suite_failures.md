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

**Scope grew during implementation, on an explicit user decision.** Three further
defects surfaced that the task body's "entire non-green residue" claim missed —
two of them only *because* the planned fix removed the error that was hiding
them. See the Implementation Record for what changed and why. The largest,
folded in at the user's direction, is a BSD `mktemp` bug in the repo's own
documented portability idiom, spanning 32 call sites and the doc that recommends
it.

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

## Implementation Record (deviations from the approved plan)

All five planned changes landed. Two of them turned out to be **necessary but
not sufficient**, and the shape of steps 1-2 changed materially. Recorded here
because the plan's own text is now wrong about them.

### Deviation A — `copy2` -> `copy` fixed the error and exposed two real failures

With the `chflags` error gone, `test_agent_keys` ran its 5 previously-erroring
tests and **2 of them failed**; `test_prompt_scoping_live` ran its 4 and all 4
failed. Neither failure was visible to t1705_4, because `setUpClass`/the fixture
helper died before any assertion executed. Root cause, measured:

> macOS refuses to **execute** a copy of `/bin/sleep` at all. It is a
> platform-signed binary on the signed system volume; a copy anywhere else is
> SIGKILLed on exec (exit 137). Clearing the file flags, `codesign
> --remove-signature`, and an ad-hoc `codesign -f -s -` all leave it dead — the
> constraint is on where the binary lives, not on its signature.

So the fixture could not produce a working fake agent at all on macOS, and
`shutil.copy` alone only moved the failure one step later.

### Deviation B — the fixture is now a verified ladder in `tests/lib/`

The plan said "same one-word change" in two files. What was actually needed is a
shared helper, `tests/lib/fake_agent_binary.py`, which tries three rungs and
**verifies each by running it** rather than branching on `sys.platform`:

1. copy the system `sleep` — the historical fixture; what Linux uses;
2. copy a locally compiled sleeper (`cc`/`clang`/`gcc`, compiled once per
   process) — macOS, where rung 1 cannot run;
3. symlink to the system `sleep` — **opt-in**, because the two readers disagree
   about a symlink (measured):
   - `ps -o comm=` reports the *invoked* path, so the basename is the agent
     name and a symlink works -> `test_agent_keys` passes `allow_symlink=True`;
   - tmux's `pane_current_command` reports the *resolved* executable, so a
     symlink named `claude` reads `sleep` -> `test_prompt_scoping_live` must not
     allow it, and raises `FakeAgentBinaryUnavailable` -> `SkipTest` when no
     rung produces a real file (its documented skip-vs-fail rule).

`exec -a claude /bin/sleep` was also measured and rejected: both readers name a
process after the file it executed, never after `argv[0]`.

Single-sourced rather than duplicated: this is a ~15-line platform workaround
with a subtle rationale, and two independent copies would drift.

### Deviation C — the negative control was inconclusive as written

The plan's step-2 control ("revert the predicate, confirm it fails") does **not**
fail, so it proves nothing. The full 2x2 was run instead:

| | no poll | with poll |
|---|---|---|
| **old predicate** | **FAILED** (the original defect) | OK |
| **new predicate** | **OK** | OK (shipped) |

The predicate fix is **sufficient on its own** — it is the real fix. The poll
alone also goes green, but by *tolerating* the premature return rather than
removing it, which is exactly the masking the control existed to detect. Both
ship: with the correct predicate, `_wait_for_shell` establishes the quit within
its 20s budget before the 5s screen poll runs, so the poll cannot mask a slow
quit — it only absorbs tmux's alternate-screen drain.

### Deviation D — a fifth defect, folded in on the user's decision

The full suite left **one** failure that was **not** in any of the four modules:
`test_settings_project_config_value_types.TheReportedDefectTests.test_the_saved_hook_actually_runs`,
`DIAG:could not create a temporary log file`. Verified pre-existing (fails
identically with this task's changes stashed), so the task body's "entire
non-green residue ... all in these four modules" was incomplete.

Root cause, and it is much wider than one test:

> BSD `mktemp` only substitutes `XXXXXX` when the placeholder **ends** the
> template. `mktemp "$TMPDIR/foo_XXXXXX.log"` therefore does not fail on macOS —
> it creates a file named literally `foo_XXXXXX.log` and exits 0. Every later
> call dies with `mkstemp failed: File exists`, **permanently**, because that
> fixed name persists in `$TMPDIR`. GNU `mktemp` substitutes, so Linux never
> sees it.

Proven by experiment: with the stale name removed, run 1 passed and run 2
failed. A stale `aitask_resource_admission_XXXXXX.log` dated two days earlier was
already sitting in `$TMPDIR`.

**This was the repo's documented idiom.** `aidocs/framework/sed_macos_issues.md`
explicitly recommended `mktemp "${TMPDIR:-/tmp}/prefix_XXXXXX.ext"` as the
portable replacement for GNU-only `mktemp --suffix` (introduced by t213). It
appeared at 32 sites across 20 files. Beyond the test failure it broke real
behaviour: `ait`'s resource-admission hook and project-command logging fail after
first use on any macOS machine, and each wrote to a fixed, predictable path.

The user was asked whether to fold this in, file it, or patch only the one
blocking site, and chose **fold the full fix**. Delivered:

- `.aitask-scripts/lib/terminal_compat.sh`: new `mktemp_suffixed`, a **drop-in**
  taking the same single template argument (so migration is a rename). It splits
  at the last `XXXXXX`, lets `mktemp` pick a unique name, then renames to carry
  the suffix — the rename cannot collide, because the chosen base is already
  exclusive. Sits beside `sed_inplace` / `portable_date`, the established home
  for this class.
- 15 sites across 10 production scripts, and 17 across 6 bash tests, migrated;
  four tests gained a `terminal_compat.sh` source line (already in the
  `test_scaffold.sh` baseline, so no scaffold change was needed).
- `.claude/skills/task-workflow/manual-verification.md`: the **no-suffix** form,
  because a skill procedure is executed by an agent with no framework libs in
  scope. Rendered variants for all three profiles and all three agent trees
  re-rendered; the three procedure goldens regenerated — their diff is exactly
  the one intended line.
- `aidocs/framework/sed_macos_issues.md`: the recommendation corrected, the
  superseded t213 row annotated so nobody copies it, and a "Files Fixed in t1729"
  section added.
- `tests/test_sed_compat.sh` Test 14 rewritten. The old version is *why this
  survived*: it made a single `mktemp` call and asserted the file existed and
  ended in `.md` — both true on macOS while broken. It now pins the properties
  that were actually violated: the placeholder is substituted, and a second call
  yields a distinct file.

### Deviation E — one more BSD/GNU footgun, in a file this task already touched

`tests/test_skill_render_task_workflow.sh:193` used `find -printf`, GNU-only;
BSD/macOS errors with "unknown primary or operator" and Test 0's orphan-golden
check failed. Verified pre-existing (identical 294/293/1 on a stashed tree), and
the only broken site — the repo already documents this footgun in the two places
it was fixed before (`tests/test_seed_manifest_drift.sh`,
`.aitask-scripts/aitask_followup_backfill.sh`). Fixed with that same `sed`
prefix-strip idiom; the module now runs 294/294. Called out separately because it
is a *different* footgun from the mktemp one, fixed only because it sat in a file
this task had to modify and regenerate goldens for.

### Out of scope, filed rather than fixed

`tests/test_minimonitor_concern_smoke.py` builds its fake agents with
`shutil.copy2(sys.executable, ...)` and states that `pane_current_command` must
really be the agent name. On macOS it is **not**: a copied framework CPython
re-execs the app bundle and tmux reports `Python`. That module is green, so the
assertions resting on that premise are passing vacuously. It is not one of
t1729's four modules and fixing it is a behavioural change to a passing test —
filed as a follow-up instead.

## Post-Implementation

Step 9 applies as usual: current-branch mode (profile `fast`), so nothing is
merged; commit with type `test` (`test: … (t1729)`), then archive the task and
this plan. Step 8d creates the confirmed spawned "after" mitigation
(`verify_macos_fixes_on_linux`); the `risk_evaluated` gate is the task's single
active gate and is recorded post-approval at Step 7.

## Final Implementation Notes

- **Actual work done:** All five planned edits landed (two `shutil.copy2` fixture
  sites, the tmux socket dir, the codebrowser interpreter predicate + polled
  screen assertion, the board latent twin). Two of them proved necessary but not
  sufficient, so the fixture became a shared verified ladder in
  `tests/lib/fake_agent_binary.py`. Beyond the plan, and on an explicit user
  decision, a BSD `mktemp` defect was fixed across 32 call sites in 20 files plus
  the doc that recommended it, and one GNU-only `find -printf` site was fixed in
  a file this task already had to modify.

- **Deviations from plan:** Five, recorded in full under "Implementation Record"
  above (A: `copy` exposed two real failures beneath the error; B: the fixture is
  now a verified three-rung ladder, single-sourced; C: the planned negative
  control was inconclusive and was replaced by a 2x2 matrix; D: the folded-in
  `mktemp` sweep; E: the `find -printf` fix). The plan's step-1/2 text ("same
  one-word change") and its step-2 control no longer describe what shipped.

- **Issues encountered:**
  - macOS will not **execute** a copy of `/bin/sleep`: it is a platform binary on
    the signed system volume, so a copy elsewhere is SIGKILLed on exec (exit
    137). Clearing file flags, `codesign --remove-signature` and an ad-hoc
    `codesign -f -s -` were all measured and none rescues it. `exec -a` was also
    measured and rejected — neither reader names a process after `argv[0]`.
  - The two readers disagree about a symlink, which is why the ladder's rung 3 is
    opt-in: `ps -o comm=` reports the invoked path (basename is the agent name),
    tmux's `pane_current_command` reports the resolved executable (reads `sleep`).
  - A copy of `sys.executable` — the pattern `tests/test_minimonitor_concern_smoke.py`
    uses — reports `Python` under tmux, so it could not serve either.
  - BSD `mktemp` does not substitute `XXXXXX` unless it ends the template, and
    does not fail when it doesn't. Proven by experiment: with the stale fixed
    name removed, run 1 passed and run 2 failed.

- **Key decisions:**
  - The ladder decides by **running** each candidate rather than branching on
    `sys.platform`, so a future OS change needs no edit here.
  - `mktemp_suffixed` takes the **same single argument** as the broken calls, so
    the 32-site migration is a mechanical rename and stays reviewable.
  - The skill procedure got the no-suffix form, not the helper: an agent
    executing it has no framework libs in scope.
  - `tests/test_sed_compat.sh` Test 14 was rewritten rather than extended — the
    old single-call version is *why* the defect survived, so leaving it as the
    regression test would have preserved the blind spot.

- **Verification:** `PYTHON SUITE: PASSED (runner=unittest, exit=0)`, 6954 tests,
  0 failures, 10 skipped (exit status captured directly, not through a pipe).
  Pre-phase baseline `baseline_exit=0`. Codebrowser 2x2 control: old predicate +
  no poll FAILED, new predicate alone OK — the predicate is the fix, the poll is
  tolerance for tmux's alternate-screen drain. `mktemp`: the previously-failing
  module passes 3 consecutive runs and leaves no `*XXXXXX*` artifacts.
  `test_skill_render_task_workflow` 293/1 -> 294/294; `test_sed_compat` 42/42;
  `aitask_skill_verify.sh` OK (13 templates, 3 agents, wrapper parity clean);
  seed-manifest drift 44/44; `shellcheck` on every touched script shows no new
  findings.

- **Completion claim (deliberately narrowed):** proved here — the suite passes
  **on macOS**. Argued but NOT proved — unchanged behaviour on Linux: no Linux
  box or container runtime is reachable from this session (`docker`, `podman`,
  `colima`, `lima`, `orbctl`, `multipass`, `vagrant` all absent) and no CI runs
  the Python suite. The per-change invariance argument is in the Cross-platform
  audit section; the outstanding proof is the spawned `verify_macos_fixes_on_linux`
  task. This is not a cross-platform claim.

- **Upstream defects identified:**
  - `tests/test_minimonitor_concern_smoke.py:541 — builds fake agents with shutil.copy2(sys.executable, ...) and documents that pane_current_command "must really be the agent name"; on macOS a copied framework CPython re-execs the app bundle and tmux reports `Python`, so every assertion resting on that premise passes vacuously. The module is green, which is why it went unnoticed.`
  - `aidocs/framework/sed_macos_issues.md:363 — the t213 row records `mktemp "${TMPDIR:-/tmp}/aitask_XXXXXX.md"` as the fix for GNU-only `mktemp --suffix`; that replacement is itself broken on BSD. Annotated in place rather than rewritten, since the section is a historical audit record.`
