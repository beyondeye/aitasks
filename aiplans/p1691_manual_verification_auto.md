---
Task: t1691_bash32_trap_shape_manual_check.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
---

# t1691 — macOS bash 3.2 trap-shape manual check (auto-executed)

Autonomous auto-verification of the `## Verification Checklist`. The checklist
was seeded from the task's own `## Verification Steps` H2 (no plan file existed,
and the section heading `## Verification Steps` does not match the parser's
`## Verification[ Checklist]` / `## Checklist` regex, so `convert` was not
usable).

## Platform under test

| fact | value |
|---|---|
| OS | Darwin 24.6.0 (macOS, arm64) |
| system bash | `/bin/bash` — GNU bash 3.2.57(1)-release (arm64-apple-darwin24) |
| PATH bash | `/opt/homebrew/bin/bash` — GNU bash 5.3.9(1)-release |

That split matters and is the one substantive discovery of this run — see
**Finding** below.

## Execution Log

### Item 1 — run `/bin/bash tests/test_ledger_lock_exit_trap.sh` on macOS

- Item text: On a macOS machine (system bash 3.2 at `/bin/bash`), run
  `/bin/bash tests/test_ledger_lock_exit_trap.sh`
- Approach: CLI invocation.
- Action run:
  ```bash
  /bin/bash tests/test_ledger_lock_exit_trap.sh
  # then, because of the Finding below:
  mkdir -p "$SCRATCH/shim32" && ln -sf /bin/bash "$SCRATCH/shim32/bash"
  PATH="$SCRATCH/shim32:$PATH" /bin/bash tests/test_ledger_lock_exit_trap.sh
  ```
- Output (trimmed): `Results: 77 passed, 0 failed (of 77)`, exit 0 — for **both**
  runs.
- Verdict: **pass**. The literal step passes; the shimmed re-run is the one that
  actually exercised bash 3.2.

### Item 2 — group 0 (0a-0d): the `trap -- '…' EXIT` rendering

- Approach: CLI invocation + direct probe.
- Action run: the shimmed suite above (0a-0d green), plus a standalone probe of
  all four handler shapes under `/bin/bash`:
  ```bash
  show() { printf 'SPEC=[%s]\n' "$(trap -p EXIT)"; }
  c() { :; }
  case "$1" in
    bare) trap show EXIT ;; quoted) trap 'show' EXIT ;;
    chained) trap 'c; show' EXIT ;; multiline) trap $'show\nc' EXIT ;;
  esac
  ```
- Output (trimmed):
  ```
  bare       -> SPEC=[trap -- 'show' EXIT]
  quoted     -> SPEC=[trap -- 'show' EXIT]
  chained    -> SPEC=[trap -- 'c; show' EXIT]
  multiline  -> SPEC=[trap -- 'show
  c' EXIT]
  ```
- Verdict: **pass**. Both unverified facts hold on bash 3.2: `trap -p EXIT`
  inside `$( )` reports the *parent's* trap (the SPEC is non-empty), and the
  handler is rendered single-quoted and verbatim in every shape a consumer can
  plausibly install.

### Item 3 — case 2 / 2b-i: the guard fires and warns on the naive chain

- Approach: CLI invocation + direct probe.
- Action run: shimmed suite (2, 2a, 2b, 2b-i, 2c green), plus a standalone
  driver sourcing the real `terminal_compat.sh` / `stale_lock.sh` /
  `ledger_block.sh` with `ait_ledger_lock_release` stubbed:
  ```bash
  trap 'cleanup; ait_ledger_lock_exit_trap' EXIT
  exit 3
  ```
  run under `/bin/bash`.
- Output (trimmed): `Warning: ait_ledger_lock_exit_trap ran behind another
  command in the EXIT trap, so the dying status was lost. …`, `RC=1`.
- Verdict: **pass**. This is the whole point of the task: the guard is **live**
  on bash 3.2, not silently degraded to a no-op. No shape-agnostic-detection
  follow-up is warranted.

### Item 4 — cases 1 / 2b / 2c exit 1; case 3 preserves 7 / 255

- Approach: CLI invocation.
- Action run: shimmed suite.
- Output (trimmed): assertions `1.`, `2b.`, `2c.`, `3.`, `3a.`, `3b.` all green.
- Verdict: **pass**.

### Item 5 — cases 8-11: the status domain and silent validation

- Approach: CLI invocation.
- Action run: shimmed suite.
- Output (trimmed): `8.` / `8-i.` (0-255 verbatim and silent), `8b.` / `8b-i.`
  (256, 512 rejected with a warning), `9.` (leading zeros `010`, `08` rejected),
  `10.` / `10a.` (empty and malformed rejected), `11.` (exactly one stderr
  line), `11a.` / `11b.` (no `value too great for base`, no `integer expected`)
  — all green.
- Verdict: **pass**.

## Finding — the suite does not test the shell it is launched with

`tests/test_ledger_lock_exit_trap.sh` runs every driver through a **bare
`bash`**, not through the interpreter the harness itself is running under:

- `run_driver()` — `tests/test_ledger_lock_exit_trap.sh:73`:
  `OUT_ERR="$(bash "$f" "$@" 2>&1 >/dev/null)"`
- `render_of()` — `tests/test_ledger_lock_exit_trap.sh:109`:
  `bash "$FIX/render.sh" "$1" 2>/dev/null`

On any box with a newer bash earlier on `PATH` — the default for a Homebrew
macOS setup, and the case here — `/bin/bash tests/test_ledger_lock_exit_trap.sh`
runs the *harness* under 3.2 while all 77 assertions execute under bash 5.3.9.
The task's verification step as literally written would therefore have reported
a green 3.2 result without 3.2 ever having been exercised, which is precisely
the silent-degradation class this task exists to rule out.

Verification here was completed by shimming `/bin/bash` to the front of `PATH`,
so the recorded pass is genuine. The harness gap itself is filed as a separate
follow-up — the fix is to route drivers through `"${BASH:-bash}"` (or an
explicit `$SHELL_UNDER_TEST`) so the suite tests the shell it was launched with.

## Cleanup

- `$SCRATCH/shim32/bash` (symlink to `/bin/bash`), `$SCRATCH/render32.sh`,
  `$SCRATCH/naive32.sh` — scratchpad only, outside the repo; nothing under
  `aitasks/` or `aiplans/` was mutated other than this plan and the task's own
  checklist.
- No tmux sessions created.
