---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, macos]
anchor: 1630
created_at: 2026-08-26 22:50
updated_at: 2026-08-26 22:50
---

## Problem

`tests/test_crash_recovery_pid_anchor.sh:611` is the last bare `timeout`
invocation in `tests/` (swept: it is the only real call site — every other
match in the directory is prose):

```bash
output18=$(cd "$TMPDIR_18/local" && timeout 30 env -u AIT_AGENT_PID \
    "PATH=$TMPDIR_18/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ... ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
rc18=$?
```

`timeout` is GNU coreutils. **macOS is a supported platform and ships no
`timeout`** — Homebrew coreutils exposes it as `gtimeout`. The framework itself
already guards this at `aitask_sync.sh:97` and
`aitask_remote_drift_check.sh:152`.

## It fails SILENTLY, which is the reason this is worth a task

The file runs under `set -e` (line 27), and the call sits inside a **command
substitution assignment**. Verified directly:

```
$ PATH=<no timeout, no gtimeout> bash -c 'set -e; out=$(timeout 30 echo hi); rc=$?; echo "reached rc=$rc"'
before
<no further output>   # exit 127
```

The assignment inherits the substitution's 127 and `set -e` aborts **before**
`rc18=$?` is ever reached. So on such a host the file does **not** report a
failed assertion — it dies mid-run with no `FAIL:` line, no `Results:` summary
and no error text, taking Test 7 (Syntax checks, declared after this point)
with it. That reads as a hang or a crash rather than a test failure: exactly
the class `t1488` documents and that `tests/test_boardcol_update.sh`'s header
calls out.

Baseline on a GNU box today: 78 passed / 0 failed, 17 tests.

## Fix — reuse the shared helper, do not hand-roll another guard

`run_bounded <secs> <outfile> <cmd...>` now lives in
`tests/lib/proc_fixtures.sh` (promoted there by t1630 so the two copies could
not drift). It tries `timeout`, then `gtimeout`, then a `set -m` +
process-group-kill watchdog, and returns the command's status or `124` on
timeout — so the existing `rc18 -ne 124` budget check keeps working unchanged.

## Why this is not a literal one-line swap

Three things change shape at this call site — the task is small, but each of
these is a way to get it silently wrong:

1. **`run_bounded` writes to a FILE, not stdout.** `output18=$(...)` must
   become `run_bounded 30 "$out_file" ...` followed by
   `output18="$(cat "$out_file")"`.
2. **The `cd` has to be preserved.** `run_bounded` execs the command directly,
   so the `cd "$TMPDIR_18/local" &&` prefix needs a subshell —
   `( cd "$TMPDIR_18/local" && run_bounded ... )` — or the `cd` folded into the
   already-present `env` invocation.
3. **`rc18` capture must survive `set -e`.** `run_bounded` returns non-zero on
   a timeout or a failing command, so it needs the
   `rc18=0; run_bounded ... || rc18=$?` form. Writing it as a bare call would
   re-create the very silent abort this task removes.

Also add the `. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"` source line (the file
currently sources only `test_scaffold.sh` and `asserts.sh`), and remember to
clean up the temp output file.

## Verification

- `bash tests/test_crash_recovery_pid_anchor.sh` still reports **78 passed /
  0 failed / 17 tests** on a GNU box — the assertions and the 30s budget check
  are unchanged.
- **The portability claim is exercised, not assumed.** Run the file with a
  `PATH` containing neither `timeout` nor `gtimeout` (a shim directory holding
  only the other tools) and confirm it now completes with a `Results:` summary
  instead of dying at Test 18 — and separately with a `PATH` where only
  `gtimeout` exists, to cover the middle rung.
- Negative control: confirm the pre-change file really does abort on that same
  stripped `PATH` (exit 127, no summary), so the fix is demonstrably the thing
  that changed the outcome.
- Test 18's own semantics still hold: a real hang must still be caught — verify
  `rc18 == 124` is reachable, e.g. by pointing the bounded command at a
  deliberate sleep, so the budget assertion is not left unfalsifiable.
- `grep -rnE '(^|[^a-zA-Z_-])timeout[[:space:]]+[0-9]' tests/` returns nothing
  afterwards.

## Context

Surfaced by t1630's review, which hit the identical defect in a new test and
fixed it by promoting `run_bounded` into `tests/lib/proc_fixtures.sh`. This is
the one remaining call site that predates that helper.
