---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [framework, bash_scripts, testing]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1681
followup_kind: verification_failure
implemented_with: claudecode/opus5
created_at: 2026-09-08 17:35
updated_at: 2026-09-08 18:36
---

## Origin

Discovered while running t1691 (the macOS bash 3.2 manual check for the t1681
EXIT-trap guard). t1691 itself **passed** — the guard is live on bash 3.2 — but
only because verification was completed with `/bin/bash` shimmed to the front of
`PATH`. See `aiplans/p1691_manual_verification_auto.md` § Finding.

## Problem

`tests/test_ledger_lock_exit_trap.sh` never tests the shell it is launched with.
Both driver entry points invoke a **bare `bash`**, which resolves through `PATH`:

- `run_driver()` — `tests/test_ledger_lock_exit_trap.sh:73`
  `OUT_ERR="$(bash "$f" "$@" 2>&1 >/dev/null)"`
- `render_of()` — `tests/test_ledger_lock_exit_trap.sh:109`
  `bash "$FIX/render.sh" "$1" 2>/dev/null`

The generated drivers also carry a `#!/usr/bin/env bash` shebang
(`driver_prelude()`, `:58`), which is moot as long as they are invoked as
`bash <file>` — but would be the *same* PATH lookup if that ever changed.

On any machine with a newer bash earlier on `PATH` — the default Homebrew macOS
setup, and the box this was found on (`/opt/homebrew/bin/bash` 5.3.9 ahead of
`/bin/bash` 3.2.57) — running

```bash
/bin/bash tests/test_ledger_lock_exit_trap.sh
```

runs the **harness** under 3.2 while all 77 assertions execute under 5.3.9, and
reports a green 3.2 result. That is exactly the silent-degradation class the
group 0 block was written to rule out: the file's own header says "A shell that
renders differently fails here — loudly — instead of silently degrading", and
today the shell it renders under is not the one the invoker chose.

Confirmed empirically on 2026-09-08: unshimmed and PATH-shimmed runs are both
77/77, and the two are only distinguishable by which interpreter the drivers
actually got.

## Proposed fix

Route drivers through the launching interpreter rather than `PATH`:

- Replace the bare `bash` in `run_driver()` and `render_of()` with
  `"${BASH:-bash}"` (bash sets `$BASH` to its own path, in 3.2 as well as 5.x),
  or with an explicit `SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-${BASH:-bash}}"`
  set once at the top — the explicit knob also lets a future CI matrix point one
  run at 3.2 and another at 5.x without a PATH shim.
- Consider asserting the interpreter identity once, near the top, so the suite
  states which bash it tested (e.g. print `$("${SHELL_UNDER_TEST}" --version |
  head -1)` alongside the results line). A verification step whose whole purpose
  is "did this pass on 3.2" should not have to be taken on trust.

## Blast radius

Check for the same bare-`bash` driver-invocation pattern in sibling test files
before fixing only this one — if other tests spawn drivers the same way, they
share the defect and the fix should be applied consistently.

## Context

- Test: `tests/test_ledger_lock_exit_trap.sh` (`:58` driver_prelude, `:73`
  run_driver, `:109` render_of)
- Seam under test: `.aitask-scripts/lib/ledger_block.sh`
  (`ait_ledger_lock_exit_trap`, `_ait_ledger_exit_trap_is_first`)
- Evidence: `aiplans/p1691_manual_verification_auto.md`
- Portability notes: `aidocs/framework/sed_macos_issues.md`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T15:36:38Z status=pass attempt=1 type=human
