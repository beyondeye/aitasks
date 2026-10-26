---
Task: t2142_fix_macos_live_tmux_socket_path_and_bounded_run_flake.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2142 — Fix macOS live-tmux socket-path length and the bounded_run readiness flake

## Context

Two independent test-infrastructure defects, both found while verifying t1689 on macOS:

1. **Socket path too long.** `require_isolated_tmux` (`tests/lib/tmux_isolation.sh:69`) sets
   the default `TMUX_TMPDIR` to `${TMPDIR:-/tmp}/ait_isolated_tmux_<uid>`. On macOS `$TMPDIR` is
   `/var/folders/…/T/`, which resolves to `/private/var/folders/…/T/` (57 bytes). tmux appends
   `tmux-<uid>/<socket>`. With the `-L ait_<name>_<pid>` names these tests use, the socket path
   comes to about 104–105 bytes, past AF_UNIX's 104-byte `sun_path` (103 characters plus NUL).
   tmux then fails with "File name too long" before the first assertion.
   Six adopters do not set a `TMUX_TMPDIR` of their own and so inherit the isolated dir with a
   long `-L` name. All six are affected:
   - `test_tmux_pane_for_pid.sh` (`ait_panepid_<pid>`)
   - `test_lock_anchor_tmux_live.sh` (`ait_anchorlive_<pid>`)
   - `test_live_endpoint_tmux_live.sh` (`ait_liveep_<pid>`)
   - `test_note_with_live_composition.sh` (`ait_notelive_<pid>`)
   - `test_scratchpad_autosave_live.sh` (`ait_scratch_<pid>`)
   - `test_sync_holder_pane_live.sh` (`ait_syncpane_<pid>`)

   The task names only the first two. Fixing the helper fixes all six.
   (Adopters that set their own `TMUX_TMPDIR` under `$TMPDIR` use the `default` socket name. They
   come to about 100 bytes, so they pass, but not by much. They are out of scope.)

2. **`test_bounded_run.TestCrewGitTimeout.test_git_cmd_timeout_reports_124` flake.** The task
   suggests raising `_read_pid`'s 5 s bound, but that **cannot fix this failure**. In this test
   `_read_pid` runs *after* `git_cmd(..., timeout=1)` has returned, so the process group has already
   been killed. If the ssh stub never ran `echo $$ > child.pid` within the 1 s deadline, nothing
   alive can ever write that file. The likely causes are a loaded box, or a cold
   `/usr/bin/git` → xcrun shim (this machine runs Apple Git-155), which can spend the whole second
   starting up. However long the wait, it waits on a file that will never be written. The real race
   is between the deadline and git starting up. The fix: notice that the stub never started, and
   retry with a doubled deadline.

## Implementation steps

1. **`tests/lib/tmux_isolation.sh` — short base for the isolated dir, every candidate validated.**
   Add a validator inside the `_AIT_TMUX_ISOLATION_LOADED` guard and replace the block at
   lines 68–73:
   ```bash
   # A usable isolated socket dir: a real directory (never a symlink) that
   # this user owns. Applied to EVERY candidate, before chmod or export.
   _ait_isolated_dir_ok() { [[ ! -L "$1" && -d "$1" && -O "$1" ]]; }
   ```
   ```bash
   if [[ -z "${_AIT_ISOLATED_TMUX_TMPDIR:-}" ]]; then
       # /tmp, not $TMPDIR: tmux appends tmux-<uid>/<socket>, and macOS's
       # $TMPDIR (/private/var/folders/<hash>/<hash>/T/, ~57 bytes resolved)
       # pushes a `-L ait_<name>_<pid>` socket past AF_UNIX's ~104-byte
       # sun_path — every connect fails with "File name too long" (t2142,
       # the t1729 class).
       #
       # /tmp is shared, so the fixed name is only a candidate. If it is
       # squatted (a symlink, a file, another user's dir), take a FRESH
       # mktemp dir instead — never a second fixed name, which can equal the
       # rejected one (TMPDIR unset or =/tmp) and never $TMPDIR, which is the
       # long path this fixes. mktemp creates it atomically, 0700, ours; in
       # that rare case one dir per run is left behind (this sourced helper
       # owns no EXIT trap). The sticky bit on /tmp stops anyone else
       # replacing a validated entry before the chmod below.
       _ait_iso_dir="/tmp/ait_isolated_tmux_$(id -u)"
       mkdir -p -m 700 "$_ait_iso_dir" 2>/dev/null || true
       if ! _ait_isolated_dir_ok "$_ait_iso_dir"; then
           _ait_iso_dir="$(mktemp -d /tmp/ait_isotmux_XXXXXX 2>/dev/null)" || _ait_iso_dir=""
       fi
       # Fail closed: without a private dir there is no isolation to offer.
       if [[ -z "$_ait_iso_dir" ]] || ! _ait_isolated_dir_ok "$_ait_iso_dir" \
             || ! chmod 700 "$_ait_iso_dir" 2>/dev/null; then
           echo "ERROR: require_isolated_tmux: could not establish a private tmux socket dir under /tmp" >&2
           exit 2
       fi
       _AIT_ISOLATED_TMUX_TMPDIR="$_ait_iso_dir"
       unset _ait_iso_dir
       export _AIT_ISOLATED_TMUX_TMPDIR
   fi
   ```
   Also update the step-2 comment above it ("to a private, per-user location") so it names
   `/tmp/ait_isolated_tmux_<uid>` and the mktemp fallback. The adopting tests need no edits.
   The hard `exit 2` is a narrow exception to the helper's "isolate, never refuse" policy: that
   policy is about not refusing because a *user session* is alive. It does not cover the case
   where no private dir can be created at all, and continuing would silently void the guarantee.

2. **`tests/test_bounded_run.py` — `test_git_cmd_timeout_reports_124`.** Replace the single
   `git_cmd` call and the post-mortem `_read_pid` with a retry loop:
   ```python
   # The deadline also bounds git's own start-up: under load (or a cold
   # /usr/bin/git xcrun shim on macOS) git can spend the whole second before
   # it execs the stub, and the group is killed before the stub writes its
   # pid. No readiness wait can recover a pid that was never written — the
   # group is already dead when we look (t2142). So retry with a doubled
   # deadline until the stub demonstrably ran; every assertion below is
   # about the attempt in which it did.
   for timeout in (1, 2, 4, 8):
       self.pidfile.unlink(missing_ok=True)
       start = time.monotonic()
       result = git_cmd(str(repo), "ls-remote", "origin", check=False, timeout=timeout)
       elapsed = time.monotonic() - start
       text = self.pidfile.read_text().strip() if self.pidfile.exists() else ""
       if text:
           break
   else:
       self.fail("the ssh stub never ran, even with an 8s deadline")
   pid = int(text.splitlines()[0])
   self.leftovers.append(pid)
   self.assertEqual(result.returncode, 124)
   self.assertIn(f"timed out after {timeout}s", result.stderr)
   self.assertIn("AIT_CREW_GIT_TIMEOUT", result.stderr)
   self.assertLess(elapsed, timeout + br.KILL_GRACE_SECONDS + 1)
   self.assertTrue(_gone_within(pid))
   ```
   (`agentcrew_utils.py:346` formats the deadline with `{timeout:g}`, so integer deadlines render as
   `2s`, `4s` and so on.) An empty pidfile, where the stub was killed partway through its `echo`,
   also counts as "did not run" and triggers a retry.

3. **`_read_pid` (`tests/test_bounded_run.py:58`).** Raise the default bound from 5.0 to 30.0 s, as
   the task asks. It is a readiness ceiling, so a quick fixture pays nothing for it. Add a docstring
   saying it only helps a fixture that is **still alive**: `test_sigint_kills_the_tree…` (CLI
   timeout 30) is a real readiness wait, but a read after the group was killed cannot be rescued
   (see step 2).

## Verification

Each fix gets a pre-fix control first, in which it is watched failing against the unfixed code:

- **Socket path, pre-fix control:** before step 1, run `bash tests/test_tmux_pane_for_pid.sh` and
  `bash tests/test_lock_anchor_tmux_live.sh`, and confirm they fail ("could not start a test pane").
  After step 1, run the same two files plus the other four adopters
  (`test_live_endpoint_tmux_live.sh`, `test_note_with_live_composition.sh`,
  `test_scratchpad_autosave_live.sh`, `test_sync_holder_pane_live.sh`) one at a time. Each must
  report PASS with zero failures. These tests use only `require_isolated_tmux`, which unsets
  `$TMUX` and runs a private `-L` server, so they are safe to run from this tmux-hosted session.
- **Regression:** run `bash tests/test_tmux_control.sh` and `bash tests/test_session_hook_live.sh`.
  Both are adopters that set their own `TMUX_TMPDIR`, and both must still pass.
- **Squat fallback:** a scratch harness in the scratchpad. It defines `id() { echo 99999; }` before
  sourcing the helper, and runs each case in a fresh `bash` subprocess so the helper's
  once-per-process guard does not carry over. Cases:
  - (a) No squat: `TMUX_TMPDIR` is `/tmp/ait_isolated_tmux_99999`, a real dir with mode 700.
  - (b) The name is a symlink to a scratch target set to mode 0755. This is the reviewer's repro,
    run three times: with `TMPDIR` set to the macOS default, with `TMPDIR` unset, and with
    `TMPDIR=/tmp`. Each time, `TMUX_TMPDIR` must be a fresh `/tmp/ait_isotmux_*` dir that differs
    from the squatted name, is not a symlink, is owned by us and has mode 700. The symlink target's
    mode must still be 0755.
  - (c) The name is a plain file: the same fallback assertions as (b).
  - (d) Pre-fix control: run (b) against the *originally proposed* block (a copy in the
    scratchpad) and confirm it fails, i.e. the selected path is the symlink and the target's mode
    changes to 0700.

  Another user's directory cannot be simulated without root. That branch rests on the same `-O`
  test the validator applies. The harness removes everything it created.
- **bounded_run, pre-fix control:** copy the module to the scratchpad and change the stub to
  `sleep 1.5; echo $$ > …`, which simulates a slow start. Against the original test body this must
  fail with "fixture never wrote". Against the new body it must pass, on the 2 s attempt.
- `python3 -m pytest tests/test_bounded_run.py`: all pass.
- `shellcheck tests/lib/tmux_isolation.sh`: clean.
- Full Python suite:
  `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3`. Read the final
  `PYTHON SUITE:` line.

## Step 9 (Post-Implementation)

Commit the code (`test: … (t2142)`), then archive the task through the normal Step 9 flow. The
work stays on the current branch.

## Risk

### Code-health risk: low
- Moving the default isolated dir from `$TMPDIR` to the shared `/tmp` could let another local user
  squat the name. Every candidate passes one validator (not a symlink, a directory, owned by us)
  before any `chmod` or export. The fallback is a fresh `mktemp -d` dir, which can never equal the
  rejected name. If no private dir can be made, the helper fails closed. tmux itself also refuses
  a `tmux-<uid>` dir it does not own. The dir is only the safety net: most of the ~40 adopters set
  their own `TMUX_TMPDIR`. · severity: low · → mitigation: none
- The fallback leaks one `/tmp/ait_isotmux_*` dir per run, but only while the fixed name is
  squatted. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The cause of the bounded_run flake is inferred from the code (the pid is read after the group is
  killed), not reproduced from the observed failure. The slow-stub control shows the mechanism is
  real, but cannot prove it is the one that fired. · severity: medium · → mitigation: none
- Six other `test_bounded_run.py` tests also read the pid after the group is killed, under short
  deadlines, and carry the same race in principle: the run at line 102 (1 s), and those at lines
  117 (1 s), 146 (0.5 s KeyboardInterrupt), 175 (0.3 s), 198 (0.5 s) and 236 (CLI 0.5 s). They
  spawn `sh` directly, which takes milliseconds, and none has been seen to flake. Step 3's longer
  bound does not help them. · severity: low · → mitigation: post_mortem_pid_reads

### Planned mitigations
- timing: after | name: post_mortem_pid_reads | type: test | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: the latent started-before-deadline race in the six other post-mortem _read_pid callers of tests/test_bounded_run.py | desc: Factor t2142's "did the fixture start? else retry with a doubled deadline" loop into a helper and apply it to the post-mortem _read_pid callers (lines ~102, 117, 146, 175, 198, 236)

## Post-Review Changes

### Change Request 1 (2026-10-26, plan review)
- **Requested by user:** the first proposed Step 1 fallback (`${TMPDIR:-/tmp}/ait_isolated_tmux_<uid>`) can equal the rejected `/tmp` path (TMPDIR unset or `/tmp`), so it followed a squatted symlink, chmod'ed its target and exported it; on macOS it also restored the long socket path.
- **Changes made:** one validator (`_ait_isolated_dir_ok`: real dir, not a symlink, owned) applied to every candidate before chmod/export; fallback is a fresh `mktemp -d /tmp/ait_isotmux_XXXXXX`; fail closed (exit 2) when no private dir validates.
- **Files affected:** `tests/lib/tmux_isolation.sh`

### Change Request 2 (2026-10-26)
- **Requested by user:** the retry loop discarded pid-less attempts before checking returncode/diagnostic/elapsed, so a transient non-timeout git failure (exit 128) passed as a slow start.
- **Changes made:** returncode 124, `timed out after {timeout}s`, `AIT_CREW_GIT_TIMEOUT` and the elapsed bound are asserted per attempt, before any retry.
- **Files affected:** `tests/test_bounded_run.py`

### Change Request 3 (2026-10-26)
- **Requested by user:** per-attempt assertions ran before the fixture pid was registered in `self.leftovers`, so a failing attempt that had written a pid left a surviving fixture teardown could not kill.
- **Changes made:** the pidfile is read and the pid appended to `self.leftovers` immediately after each call, before any assertion.
- **Files affected:** `tests/test_bounded_run.py`

## Final Implementation Notes
- **Actual work done:** `require_isolated_tmux` now defaults the isolated `TMUX_TMPDIR` to `/tmp/ait_isolated_tmux_<uid>` (validated; fresh mktemp fallback; fail closed), fixing the macOS `sun_path` overflow for all six adopters that run a private `-L ait_<name>_<pid>` server in the inherited dir. `test_git_cmd_timeout_reports_124` retries with 1/2/4/8s deadlines until the ssh stub demonstrably ran, asserting a genuine timeout on every attempt and registering any pid before asserting. `_read_pid` default raised to 30s with a docstring stating it only helps a still-alive fixture.
- **Deviations from plan:** the helper uses a function-`local iso_dir` instead of a global + `unset`; `mkdir -m 700` without `-p` (shellcheck SC2174). Change Requests 1–3 above. Plan verification expected all six live adopters to PASS; only two do — the other four now pass the socket stage and fail on a separate pre-existing macOS defect (below). `test_tmux_control.sh` (a planned regression check) fails under system `python3` (no `yaml`, pre-existing) and passes with `PYTHON_BIN=~/.aitasks/venv/bin/python`.
- **Issues encountered:** the task's suggested bounded_run fix (raise `_read_pid`'s bound) could not work: the pid is read after the group is killed. Diagnosed and fixed the deadline-vs-startup race instead.
- **Key decisions:** fixed the helper rather than the two named tests, so every inheriting adopter benefits. Verification evidence: pre-fix control (both named tests fail at pane start; after: no socket failures in any of the six); squat harness 8/8 on the new helper vs 6/8 failing on the rejected proposal; slow-stub control (old body `fixture never wrote` after 6.2s, new passes); exit-128 injection (previous body passes, new fails); leak control (previous body leaves fixture alive after teardown, new kills it); `test_bounded_run` 26 OK (1 skipped); full Python suite `PYTHON SUITE: PASSED (runner=unittest, exit=0)` (run before Change Requests 2–3; module re-run after each); shellcheck clean.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/pid_anchor.sh:276 — on macOS (no /proc) lock_holder_liveness can only return "unknown" for the weak ps token, so tests/test_lock_anchor_tmux_live.sh, test_live_endpoint_tmux_live.sh, test_note_with_live_composition.sh and test_sync_holder_pane_live.sh fail their alive / LIVE_PANE / live_lock expectations on macOS (24 assertions); previously masked by the socket-path failure`
  - `tests/test_tmux_control.sh:22 — PYTHON_BIN defaults to bare python3; a system python without PyYAML fails importing monitor_core (task_yaml) — should default to the framework venv python`
