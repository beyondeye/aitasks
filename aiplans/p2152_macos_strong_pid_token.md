---
Task: t2152_macos_strong_pid_token.md
Base branch: main
Output branch: main
---

# t2152 — Strong macOS PID identity token (`bsdinfo`)

## Context

On macOS (no `/proc`), `lib/pid_anchor.sh` can only record the `ps -o lstart`
token. It has one-second resolution, so `lock_holder_liveness` will never answer
`alive` for it (a PID recycled within the same second could carry the same
token). As a result, every macOS live-holder feature degrades to `unknown`:
- `ait note --with-live` → `LIVE_PANE`
- sync `live_lock` pane naming
- the `LOCK_LIVE_HOLDER` acquire gate

t2146 made the test suites platform-correct by adding weak-token SKIP branches.
This task fixes the product instead. It adds a strong token kind from
`proc_pidinfo(PROC_PIDTBSDINFO)`, which carries the start time in microseconds,
and then removes those SKIP branches.

Measured on this host (macOS 15.7.3, framework venv CPython 3.13):
- **Python probe through ctypes and the public `libproc` API:** about 20 ms, and
  `-I -S` makes no difference. Behaviour by target:
  - an own-uid pid returns 136 bytes, with the start time at offset 120 (two
    `uint64`: sec, usec);
  - pid 1 (root) returns 0 with EPERM;
  - an absent pid returns 0 with ESRCH.
- **Perl `syscall(336, …)`:** works in 3 ms, but SYS_proc_info 336 is a
  private, unstable syscall number. Rejected. ctypes uses the public API.

## Design decisions

- **Kind name `bsdinfo`.** The token looks like `<sec>.<usec 6 digits>`, e.g.
  `1793019250.025784`. It is strong, like `proc`.
- **Preference order** in `get_pid_starttime[_kind]`: `proc` > `bsdinfo` > `ps`.
  - The `bsdinfo` source is attempted only when `$OSTYPE == darwin*`, a bash
    builtin with no fork, so Linux behaviour and cost are untouched.
  - A process the probe cannot read (another uid, EPERM) falls back to `ps`,
    exactly as today.
- **Reader rule unchanged.** `lock_holder_liveness` re-derives from the SAME
  source the lock recorded:
  - `bsdinfo` gets its own case;
  - the strength gate becomes "`proc` or `bsdinfo` ⇒ may be `alive`";
  - `ps` stays weak.
- **Interpreter.** Lazily source `python_resolve.sh` from `$_PID_ANCHOR_LIB_DIR`,
  indented inside a function, using the same lazy pattern as
  `_anchor_tmux_pane_pid`/`tmux_exec.sh`, then call `resolve_python`.
  - If no interpreter or no resolver is available, the source fails, and the
    kind falls back to `ps`. That fallback is weak but consistent.
  - `setup_fake_aitask_repo` already copies `python_resolve.sh` and
    `terminal_compat.sh`, so the claim fixtures resolve the same interpreter.
- **One probe per writer: new `get_pid_identity <pid>`.** It prints
  `<kind> <token>` from a single source walk, and `get_pid_starttime` and
  `get_pid_starttime_kind` become thin wrappers over it, keeping their API.
  - Writers call `get_pid_identity` once, which halves the interpreter cost.
  - It also closes a real race that the python source would make plausible: a
    token taken from `bsdinfo` while a second, separate kind probe fails
    transiently and records `ps`. The reader would then compare a `ps` token
    against a `bsdinfo` value and answer **dead**, a false crash.
  - The writers are `aitask_lock.sh` lock build, `_ait_current_anchor`, and
    `merge_lock.sh` anchor capture.
- **Backward compatibility.**
  - Old locks with `pid_starttime_kind: ps` still re-derive from `ps` and read
    `unknown`, as before.
  - An older framework reading a `bsdinfo` lock sees an unrecognised kind and
    reads `unknown`. That is fail-safe and never `dead`.
  - No self-identity bridge: `lock_anchor_is_self` keeps requiring a kind
    match, which is the t1466 rule pinned by crash_recovery Test 17.
  - Accepted transitional cost: a macOS session that re-picks its OWN
    pre-upgrade `ps` lock gets `LOCK_UNVERIFIABLE_HOLDER`, which offers
    "Reclaim anyway". This happens once per lock.

## Implementation steps

### 1. `.aitask-scripts/lib/pid_anchor.sh`

- **Add `_pid_anchor_python`.** It returns the interpreter path or returns 1:
  ```bash
  _pid_anchor_python() {
      if ! declare -F resolve_python >/dev/null 2>&1; then
          [[ -r "$_PID_ANCHOR_LIB_DIR/python_resolve.sh" ]] || return 1
          # shellcheck source=python_resolve.sh disable=SC1091
          source "$_PID_ANCHOR_LIB_DIR/python_resolve.sh" || return 1
      fi
      local py; py="$(resolve_python)"; [[ -n "$py" ]] || return 1
      printf '%s\n' "$py"
  }
  ```
- **Add `_pid_starttime_bsdinfo <pid>`.** It runs only on `darwin*` with a
  numeric pid, and its comment block matches the style of the `proc`/`ps`
  sections:
  ```bash
  "$py" -I -S -c '
  import ctypes, struct, sys
  buf = ctypes.create_string_buffer(136)   # sizeof(struct proc_bsdinfo)
  n = ctypes.CDLL("/usr/lib/libproc.dylib").proc_pidinfo(
      int(sys.argv[1]), 3, ctypes.c_uint64(0), buf, 136)  # PROC_PIDTBSDINFO
  if n != 136:
      sys.exit(1)
  sec, usec = struct.unpack_from("=QQ", buf.raw, 120)  # pbi_start_tv{sec,usec}
  print("%d.%06d" % (sec, usec))' "$pid" 2>/dev/null
  ```
  It then validates the output against `^[0-9]+\.[0-9]{6}$` and returns 1
  otherwise. The comment block documents: the public libproc API; that the
  value is microsecond `p_start`, fixed at fork and kept across exec (the same
  field `ps lstart` truncates); the EPERM fallback; and that Perl's raw syscall
  was rejected as a private ABI.
- **Add `get_pid_identity <pid>`.** It echoes `"<kind> <token>"`, trying
  `proc` → `bsdinfo` → `ps` → `none -`. Rewrite `get_pid_starttime` as
  `get_pid_identity` + `${…#* }` and `get_pid_starttime_kind` as `${…%% *}`.
  Keep their headers and update the comments to "proc | bsdinfo | ps | none".
- **`lock_holder_liveness`.**
  - Add the case `bsdinfo) current=$(_pid_starttime_bsdinfo "$pid" 2>/dev/null) || current="-" ;;`.
  - Replace the weak gate with
    `case "$kind" in proc|bsdinfo) ;; *) echo unknown; return 0 ;; esac`.
  - Update the doc comment from `$3 = token kind (proc|ps)` to list the kinds
    and say which are strong.
- **`_ait_current_anchor`.** Make one `get_pid_identity` call, then
  `read -r _AIT_SELF_ANCHOR_KIND _AIT_SELF_ANCHOR_TOKEN`.

### 2. Writers use the single probe

- `.aitask-scripts/aitask_lock.sh:294-295` →
  `read -r lock_starttime_kind lock_starttime <<<"$(get_pid_identity "$lock_pid")"`.
  Update the comment at :289-291: kind `ps` is weak; `proc`/`bsdinfo` are
  strong.
- `.aitask-scripts/lib/merge_lock.sh:169-170` → the same pattern into
  `_merge_lock_anchor_kind` / `_merge_lock_anchor_token`.

### 3. `tests/lib/proc_fixtures.sh`

- **`liveness_token_class`** now fails closed on a weak host:
  - `proc|bsdinfo` → `strong` (0);
  - `ps` → status **4** with the stderr message "pid has only the weak
    second-granular ps token — no strong identity source on this host
    (live-holder features degraded)";
  - everything else stays as it is (2 or 3).
  - Rewrite the header comment: tests needing a provably-alive holder now
    REQUIRE strong, and a weak host FAILS instead of skipping.
- **Delete `skip_weak_token`.**
- **Simplify `expected_live_verdict`**: strong → `alive`, otherwise print
  nothing and return the class status.
  - It stays because Test 8 and Test 15 assert through it.

### 4. Remove the t2146 weak-token branches; each test now requires `strong`

The removal pattern is the same everywhere: delete the `== weak` /
`else skip_weak_token` arms, keep the strong arm unconditionally, and rewrite
the header "PLATFORM SPLIT" paragraph. Each paragraph now says the case needs a
strong token, `proc` on Linux or `bsdinfo` on macOS, and that
`liveness_token_class` fails closed otherwise.

| Test | Change |
|---|---|
| `tests/test_lock_anchor_tmux_live.sh` | Allowed kinds `proc|ps` → `proc|bsdinfo`, at :241 |
| `tests/test_live_endpoint_tmux_live.sh` | Drop the `W` block, :209-226 |
| `tests/test_note_with_live_composition.sh` | `live_reason` → `echo "$1"`; drop the :267 NOTE; `want_3a` = `agent_unknown`; drop `3f-weak` and the skip |
| `tests/test_sync_holder_pane_live.sh` | `EXPECT_REASON=live_lock`; drop the S1h-weak, S1c-e and S2c skip arms |
| `tests/test_lock_live_holder_gate.sh` | `LIVE_SIGNAL=LOCK_LIVE_HOLDER`. Test 6's `ps`-planted weak variant drops the `uname == Linux` gate, because a `ps` token is plantable on any host |
| `tests/test_sync_protect_paths.sh` | live_lock: drop the weak arm |
| `tests/test_crash_recovery_pid_anchor.sh` | Details below |

`tests/test_crash_recovery_pid_anchor.sh`:
- **Test 8:**
  - `strong|weak` → must be `strong`;
  - the kind assertion for Linux becomes `proc`, and for Darwin `bsdinfo`;
  - the negative stubs (neg_a/neg_a2) also stub `_pid_starttime_bsdinfo`, or
    macOS still finds a token;
  - add neg_f: a `ps` kind with a real `ps` token → `[] 4`.
- **Test 15:** drop the weak `is_lock_holder_alive` arm.
- **Test 17:** replace the `uname == Linux` gate. Use
  `strong_kind=$(get_pid_starttime_kind "$ANCHOR_PID_14")`, which must be
  `proc|bsdinfo`, plus that kind's own token. That makes it run on macOS too.
  - Also update `tests/lib/sync_fixture.sh:128-134`: its comment about
    `lock_yaml_live` still describes the weak `ps` token as the no-/proc case.

### 5. New contract tests (`tests/test_crash_recovery_pid_anchor.sh`, new Test 19 "bsdinfo token")

**On every platform** (deterministic, through injected stubs inside
command-substitution subshells, with results asserted outside, as in the
existing neg_* pattern), the test asserts:
- **Reader keeps the same source when the bsdinfo probe fails.** Take a live
  pid (`sleep 300 &`) and a recorded `bsdinfo` token, with
  `_pid_starttime_bsdinfo() { return 1; }` stubbed. To prove `ps` is never
  consulted, stub `_pid_starttime_ps` to echo a DIFFERENT token, because a
  fallback to it would read `dead`, and stub `_pid_starttime_proc` the same
  way. Then `lock_holder_liveness <pid> 1793019250.025784 bsdinfo` → exactly
  `unknown`.
- **Ladder order (this exercises the Linux path of the shared refactor on any
  host):**
  - with `_pid_starttime_proc() { echo 4242; }` and a `_pid_starttime_bsdinfo`
    stub that records a call marker, `get_pid_identity <pid>` → `proc 4242`.
    The bsdinfo stub must never run, and the wrappers echo `4242` / `proc`;
  - proc fails and bsdinfo echoes `1.000001` → `bsdinfo 1.000001`;
  - both fail and ps echoes `X` → `ps X`;
  - all three fail → `none -`.
- **Writer split under a pinned proc branch.** Set `AIT_AGENT_PID` to a live
  `sleep`, stub `_pid_starttime_proc` to echo a value, and reset the
  `_AIT_SELF_ANCHOR_CACHED` memo. Then `_ait_current_anchor` must yield
  `_AIT_SELF_ANCHOR_KIND=proc` and `_AIT_SELF_ANCHOR_TOKEN=<stub value>`. This
  pins the `read -r kind token` split order that the three writers share. A
  stub cannot cross into the claim scripts' processes, so the
  `aitask_lock.sh` / `merge_lock.sh` writers are covered by the real-claim
  assertions in Test 8 and the merge-lock suites, not by this case.

**On Darwin**, the test asserts the following, using two `sleep` children
spawned back to back:
- `_pid_starttime_bsdinfo` output matches `^[0-9]+\.[0-9]{6}$`;
- it is stable across two reads;
- it fails (rc 1) for an absent pid (`dead_pid_fixture`). That is
  deterministic: the pid is reaped;
- pid 1, **conditional on observed access, never assuming denial**:
  - if `_pid_starttime_bsdinfo 1` fails, `get_pid_starttime_kind 1` must be
    `ps` (or `none` if `ps` also cannot read it), never `bsdinfo`;
  - if it succeeds (for example on a root-run CI box), the kind must be
    `bsdinfo`;
  - either way, assert that the kind and the token come from the same source;
- **cross-check:** the seconds field formatted with
  `LC_ALL=C date -r <sec> '+%a %b %e %T %Y'`, whitespace-collapsed, equals the
  `ps lstart` token. This pins the offset-120 ABI assumption. If the offset
  were wrong, this would fail rather than silently record garbage;
- **distinctness:** two children started back to back get different `bsdinfo`
  tokens. In the same run, assert that their `ps` tokens are equal whenever
  their `bsdinfo` seconds are equal. That shows the case the strong kind exists
  for;
- `get_pid_identity $$` → `bsdinfo <tok>`, and the wrappers agree with it;
- `lock_holder_liveness` with a matching `bsdinfo` token → `alive`, and with a
  wrong token → `dead`;
- `_pid_anchor_python` failing (stubbed) → kind falls back to `ps`, never
  `none` for a live own pid.

**On non-Darwin**, it asserts:
- `_pid_starttime_bsdinfo $$` returns 1;
- `lock_holder_liveness $$ 1.000000 bsdinfo` → `unknown` (never `dead`).

### 6. Docs

- **`website/content/docs/workflows/crash-recovery.md:178`** ("macOS
  portability" bullet), rewritten to current state: on macOS the token comes
  from `proc_pidinfo` through the framework's Python, has microsecond
  resolution, and is recorded as `bsdinfo`. It can prove a live holder.
  `ps -o lstart=` remains the fallback when that is unavailable, for example a
  process owned by another user or no Python. That fallback is second-granular
  and yields "unknown".
- **`website/content/docs/commands/lock.md`**: its sample is fine as it is. If
  needed, add one sentence naming the `proc` / `bsdinfo` / `ps` kinds.
- Then run `cd website && python3 check_links.py --build`.

## Verification

1. **Pre-fix control** (memory: run-the-pre-fix-control). Before editing the
   product, apply only the test edits (steps 3-5) and run
   `bash tests/test_crash_recovery_pid_anchor.sh` and
   `bash tests/test_lock_live_holder_gate.sh`. They must FAIL on this Mac, with
   class 4 or a missing `bsdinfo`. Then apply steps 1-2.
2. **Post-fix, macOS** (in-session; these suites use `require_isolated_tmux`,
   as t2146 established). Run each file individually:
   - `tests/test_crash_recovery_pid_anchor.sh`
   - `tests/test_lock_live_holder_gate.sh`
   - `tests/test_lock_anchor_tmux_live.sh`
   - `tests/test_live_endpoint_tmux_live.sh`
   - `tests/test_note_with_live_composition.sh`
   - `tests/test_sync_holder_pane_live.sh`
   - `tests/test_sync_protect_paths.sh`

   All must pass with zero `SKIP: … weak ps identity token` lines.
3. **Regression, the other users of the helpers:**
   - `tests/test_task_lock.sh`
   - `tests/test_lock_diag.sh`
   - `tests/test_live_endpoint_degradation.sh`
   - `tests/test_session_hook.sh`
   - `tests/test_sync_deferral_and_quarantine.sh`
   - `tests/test_sync_auto_commit_scoping.sh`
   - `tests/test_archive_carryover_anchor.sh`
   - the merge-lock tests, found with `grep -l merge_lock tests/*.sh`
   - `bash tests/run_all_python_tests.sh --test-dir tests` filtered to
     `test_parallel_admission_collect.py` (run it via `--test-dir` on a scratch
     dir holding only that file, or run it directly with the venv python)
4. **Lint:** `shellcheck .aitask-scripts/lib/pid_anchor.sh .aitask-scripts/aitask_lock.sh .aitask-scripts/lib/merge_lock.sh tests/lib/proc_fixtures.sh` plus the edited tests.
5. **Live product check:** run `./ait lock --check 2152`, or re-run
   `aitask_pick_own.sh 2152` from this session, and confirm that the
   re-written lock carries `pid_starttime_kind: bsdinfo`.
6. **Linux evidence, stated honestly.** The `bsdinfo` source is `$OSTYPE`-gated,
   but the shared refactor runs on Linux:
   - `get_pid_identity` and its wrappers;
   - the three writers' `read -r kind token`;
   - the new `lock_holder_liveness` strength `case`.

   **No external runner covers it.** The checked-in workflows (`hugo.yml`,
   `goengines-check.yml`, `release*.yml`, `contribution-check.yml`) run no
   lock, crash-recovery or merge-lock shell suite, and this host has no Linux
   runtime (no docker, podman or lima). So this session claims only:
   - (a) the platform-independent Test 19 ladder and writer-split cases, which
     drive the proc-first branch through stubs on this host;
   - (b) Linux-real verification deferred to a **follow-up** task: the
     `after` mitigation `linux_lock_suite_run`, created at Step 8d. It runs on
     a Linux host, each individually:
     - `tests/test_crash_recovery_pid_anchor.sh`
     - `tests/test_lock_live_holder_gate.sh`
     - `tests/test_task_lock.sh`
     - `tests/test_lock_diag.sh`
     - `tests/test_lock_anchor_tmux_live.sh`
     - `tests/test_live_endpoint_tmux_live.sh`
     - `tests/test_note_with_live_composition.sh`
     - `tests/test_sync_holder_pane_live.sh`
     - `tests/test_sync_protect_paths.sh`
     - `tests/test_merge_lock_broker.sh`
     - `tests/test_merge_lock_concurrency.sh`
     - `tests/test_merge_broker_rendered_verdicts.sh`
     - `tests/test_session_hook.sh`

     It expects zero failures and records each file's summary line. The
     follow-up is recorded below as a planned `after` mitigation.

   Do not describe Linux as verified in the commit or the Final Implementation
   Notes.

Step 9 (Post-Implementation): commit code and plan separately, then archive via
`aitask_archive.sh 2152`.

## Risk

### Code-health risk: medium
- On macOS the lock hot path (claim, re-pick, sync sweep, note `--with-live`)
  now spawns the framework Python, about 20 ms per probe. Writers make one
  probe through `get_pid_identity` and readers one per evaluated lock.
  · severity: low · → mitigation: none (measured; single-probe writer API is part of the plan)
- Lazily sourcing `python_resolve.sh` pulls `terminal_compat.sh` into
  `pid_anchor.sh` callers on Darwin. Every current caller already sources
  `terminal_compat`, and both files are double-source guarded.
  · severity: low · → mitigation: none
- A macOS session re-picking its own pre-upgrade `ps`-kind lock gets
  `LOCK_UNVERIFIABLE_HOLDER` once, because the kind mismatch is kept by design
  (t1466). · severity: low · → mitigation: none (documented transitional cost; "Reclaim anyway" recovers)

- The shared refactor (`get_pid_identity`, the writer `read -r` split, the
  liveness strength `case`) executes on Linux, but no checked-in CI job runs
  the lock, crash-recovery or merge-lock shell suites, and this host has no
  Linux runtime. In-session evidence is limited to the stub-driven proc-branch
  cases in Test 19. · severity: medium · → mitigation: linux_lock_suite_run

### Goal-achievement risk: low
- The `proc_bsdinfo` layout (136 bytes, start time at offset 120) is an ABI
  assumption. · severity: low · → mitigation: none (pinned in-plan by the Test 19 `date -r` ↔ `ps lstart` cross-check)
- The failure coverage could have let the reader silently switch source when
  the `bsdinfo` probe fails on an already-recorded lock. · severity: low ·
  → mitigation: none (pinned in-plan: Test 19 injected probe-failure case
  asserts `unknown` with a `ps` stub that would read `dead` if consulted;
  pid 1 handled by observed access, not assumed EPERM)
- Removing the weak branches makes the seven suites fail, rather than skip, on
  a macOS host with no usable Python. This is intended fail-closed behaviour,
  because such a host's live features really are degraded. · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: linux_lock_suite_run | type: test | priority: medium | effort: low | inline_risk: high | added_complexity: low | addresses: shared refactor unverified on Linux (no CI job, no local Linux runtime) | desc: Run the pid_anchor/lock/crash-recovery/merge-lock/live-holder shell suites individually on a Linux host and record each file's result for t2152
