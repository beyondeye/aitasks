---
Task: t936_tmux_tests_unrunnable_with_live_session.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# t936 — Make tmux tests runnable alongside a live user tmux session

## Context

Surfaced by the t926 macOS compat audit. Eight tmux/multi-session tests abort
with `exit 2` whenever **any** tmux session exists on the default socket — or
whenever they are launched from inside tmux (`$TMUX` set). The refusal lives in
the shared guard `tests/lib/require_no_tmux.sh` (`require_no_tmux()`), which all
8 tests source and call.

On any developer machine running tmux (very common), these 8 tests cannot run,
so the full suite can never be green locally without first detaching/killing
tmux. The guard was added defensively because historical isolation leaks once
cascaded into the user's main tmux server, killing every pane. **The guard must
not simply be removed** — the fix must keep the user's default-socket server
provably untouched while letting the tests proceed.

### What the exploration established

Every one of the 8 tests already isolates *airtight*:
- Each tmux invocation (shell **and** the Python subprocesses) runs with
  `TMUX_TMPDIR` pointed at a unique `mktemp -d` fixture dir, so its server lives
  on a socket under a private directory — never `/tmp/tmux-$UID/default`.
- Each also `unset TMUX` before invoking tmux; the Python helpers do
  `env.pop("TMUX", None)`.
- Cleanup traps kill-server with the explicit `TMUX_TMPDIR="$fixture"` prefix.

Verified by grep across all 8 files: there is **no** tmux call that lacks a
`TMUX_TMPDIR` override. The default-socket refusal is therefore pure
belt-and-suspenders for the *current* tests — its only real value is catching a
*future* test that forgets the isolation discipline.

Callers of the guard are exactly the 8 tests (+ the lib itself). No website/docs
page instructs users to run these tests "tmux-free" or to `kill-server` first
(the only tmux mentions in docs are unrelated: truecolor config, crash-recovery
narrative). So there is no "requires a tmux-free terminal" documentation to
relax — the fix is entirely in the test harness.

## Approach (recommended)

Convert the guard from **refuse-if-tmux-exists** into **establish-isolation**.
Instead of aborting, it makes the user's default socket *unreachable* for the
whole test process, which is a **stronger** guarantee than the current refusal
(the refusal only reduces blast radius by requiring zero user sessions; it does
nothing once the test is running).

Two process-level guarantees, set once in the guard (it is sourced, so the
settings persist for the whole test):

1. **`unset TMUX`** — detaches from any server inherited from the surrounding
   terminal, so a stray `tmux` call can no longer reach the user's server via
   `$TMUX`. This neutralizes the "launched from inside tmux" case.
2. **Redirect the default socket dir** — set `TMUX_TMPDIR` to a per-user
   isolated location *as the process default*, so any tmux call that lacks its
   own `TMUX_TMPDIR` override still lands in an isolated dir, never
   `/tmp/tmux-$UID/default`. Per-fixture `export TMUX_TMPDIR=...` in the tests
   still overrides this; this is the safety net that directly addresses "what if
   someone adds a test later and forgets the discipline".

With both in place the refusals are unnecessary and are dropped.

### Scope-honest rename

The file and function are renamed, because `require_no_tmux` would be an active
lie once it no longer requires no tmux:
- `tests/lib/require_no_tmux.sh` → `tests/lib/tmux_isolation.sh`
- function `require_no_tmux` → `require_isolated_tmux`

### File changes

**1. `tests/lib/require_no_tmux.sh` → renamed `tests/lib/tmux_isolation.sh`** —
rewrite the body. New function (replacing the two `exit 2` refusals):

```bash
if [[ -z "${_AIT_TMUX_ISOLATION_LOADED:-}" ]]; then
    _AIT_TMUX_ISOLATION_LOADED=1

    # Establish airtight tmux isolation for a test process. Replaces the old
    # require_no_tmux refusal guard: rather than aborting when the user has a
    # live tmux session, it makes the user's default socket unreachable so the
    # test can run safely alongside it.
    require_isolated_tmux() {
        # 1. Detach from any server inherited from the surrounding terminal.
        unset TMUX

        # 2. Redirect tmux's *default* socket dir away from the user's
        #    (/tmp/tmux-$UID) to a private, per-user location. Per-case
        #    `export TMUX_TMPDIR=...` still overrides this; this is the safety
        #    net so any tmux call WITHOUT its own override still lands in
        #    isolation and can never touch the user's server.
        if [[ -z "${_AIT_ISOLATED_TMUX_TMPDIR:-}" ]]; then
            _AIT_ISOLATED_TMUX_TMPDIR="${TMPDIR:-/tmp}/ait_isolated_tmux_$(id -u)"
            mkdir -p "$_AIT_ISOLATED_TMUX_TMPDIR" 2>/dev/null || true
            chmod 700 "$_AIT_ISOLATED_TMUX_TMPDIR" 2>/dev/null || true
            export _AIT_ISOLATED_TMUX_TMPDIR
        fi
        export TMUX_TMPDIR="$_AIT_ISOLATED_TMUX_TMPDIR"
    }
fi
```

Notes on the safety-net dir choice: a **fixed per-user** path
(`ait_isolated_tmux_<uid>`, mode 0700) is reused across runs, so it needs no
per-run cleanup and cannot accumulate `mktemp` dirs. Nothing should ever spawn a
server there (all real tests set their own fixture `TMUX_TMPDIR`), so it stays
empty in normal operation; if a stray call ever did, the server would be
isolated and harmless. This deliberately avoids a per-process `mktemp` +
EXIT-trap, which would be clobbered by each test's own `trap … EXIT`.

**2. The 8 test files** — mechanical 3-line update each (source path, shellcheck
directive, call site):
- `# shellcheck source=lib/require_no_tmux.sh` → `lib/tmux_isolation.sh`
- `. "$SCRIPT_DIR/lib/require_no_tmux.sh"` → `lib/tmux_isolation.sh`
- `require_no_tmux` → `require_isolated_tmux`

Files: `test_kill_agent_pane_smart.sh`, `test_multi_session_monitor.sh`,
`test_multi_session_primitives.sh`, `test_tmux_control.sh`,
`test_tmux_control_resilience.sh`, `test_tmux_exact_session_targeting.sh`,
`test_tmux_run_parity.sh`, `test_tui_switcher_multi_session.sh`.

No change to any test's own fixture/subshell logic — they keep their existing
per-fixture `TMUX_TMPDIR` exports, `unset TMUX`, and cleanup traps (now
redundant with the guard, but harmless and worth keeping as local discipline).

### Why not the alternatives

- **Just delete the guard / the default-socket check.** Rejected: reintroduces
  the exact leak risk the guard was added for, with no positive guarantee. The
  task explicitly says not to simply remove it.
- **Skip-with-clear-message path (exit 0 SKIP) instead of running.** This is the
  task's *fallback* ("otherwise…"). Not needed: full isolation is provably safe
  here, so we take the primary path (relax the guard) and the tests actually run
  rather than being skipped.
- **Per-process `mktemp` safety-net dir + EXIT trap.** Rejected: each test
  installs its own `trap … EXIT` after sourcing the guard, clobbering the
  guard's trap and leaking an empty dir per run. The fixed per-user dir sidesteps
  this entirely.
- **Keep the filename, rename only the function.** Rejected for scope-honesty: a
  file named `require_no_tmux.sh` that establishes isolation rather than
  requiring no-tmux is misleading.

## Verification

Current env: `TMUX` unset, no default-socket server, tmux 3.6b — clean baseline.

1. **Lint:** `shellcheck tests/lib/tmux_isolation.sh` and the 8 edited tests pass
   (confirms the `source=` directive resolves).
2. **Runs alongside a live user session, untouched (primary requirement):**
   - Start a marker session on the **default** socket:
     `tmux new-session -d -s t936_verify_$$ "sleep 600"` (env currently has no
     other default-socket server, so this is safe to create and later kill by
     name).
   - Run all 8 tests; assert each prints `PASS`/`OK` and exits 0 (previously
     `exit 2`).
   - Assert the marker session still exists: `tmux has-session -t t936_verify_$$`.
   - Tear down only the marker: `tmux kill-session -t t936_verify_$$`
     (**never** `tmux kill-server`).
3. **Runs from inside tmux (`$TMUX` set):** repeat one representative test (e.g.
   `test_tmux_run_parity.sh`) from inside the marker session's pane / with
   `$TMUX` exported, confirming it no longer aborts and the marker survives.
4. **Isolation proof:** after the run, confirm no test session leaked onto the
   default socket (`tmux list-sessions` shows only the marker, then nothing after
   teardown).

## Risk

### Code-health risk: low
- 9 files touched (1 lib rewrite + 8 mechanical 3-line test edits), but the only
  logic change is in the shared guard; the tests' own isolation logic is
  unchanged. Wrong `source=`/path in the rename would break sourcing —
  fully caught by `shellcheck` + running the 8 tests. · severity: low
- The change relaxes a *safety* guard. Mitigated by replacing refusal with a
  **stronger** positive guarantee (`unset TMUX` + redirected default socket),
  not by deletion. · severity: low

### Goal-achievement risk: low
- Approach directly satisfies the verification criteria (tests run to PASS
  alongside a live session; user's session provably untouched) and additionally
  covers the inside-tmux case. Relies only on well-established `TMUX_TMPDIR` /
  `unset TMUX` semantics. · severity: low
- None identified beyond the above.

No before/after mitigation tasks warranted (both dimensions low; the verification
section is the sufficient check). `risk_mitigations_planned = false`.

## Step 9 (post-implementation)

Single-task (no children). On approval: implement on the current branch, show
the diff for review (Step 8), commit code as
`test: <desc> (t936)`, update + commit the plan, then archive via
`./.aitask-scripts/aitask_archive.sh 936` and push.
