---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [thinking_app#322, 1610]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-25 14:04
updated_at: 2026-08-25 17:42
completed_at: 2026-08-25 17:42
---

# `run_command_gate` records a project command's exit 2 (skip) as `fail`

## Origin

Risk-mitigation ("after") follow-up for thinking_app's t280, created at Step 8d
after that implementation landed. Filed here rather than there because
`.aitask-scripts/` is framework-owned and overwritten by `ait upgrade`.

## The defect

`.aitask-scripts/lib/gate_verifier_lib.sh` → `run_command_gate()`:

```bash
for c in "${cmds[@]}"; do
    printf '$ %s\n' "$c" >> "$log"
    if ! bash -c "$c" >> "$log" 2>&1; then
        status=fail; code=1; result="command failed: ${c}"
        break
    fi
done
```

Every non-zero exit from the configured project command becomes `status=fail`.
The only `skip` this function can emit is the "no `<config_key>` configured"
branch above it. So a project command that deliberately reports **"I did not
run"** is recorded as **"I ran and failed"**.

The verifier's own header — `exit 0=pass 1=fail 2=skip(no command) 3=error` —
describes the **verifier's** exit status, not the command's, and is easy to
misread as evidence that the distinction is already honoured. It is not:
measured in thinking_app while implementing t280, and a comment in that repo
asserting the opposite had to be deleted as false.

This affects every `kind`-less machine gate routed through this helper:
`tests_pass` (`test_command`), `build_verified` (`verify_build`), `lint`
(`lint_command`).

## Why it matters

`tests_pass` is `blocks_dependents: true` with `max_retries: 1`. A downstream
project whose test command legitimately reports "did not run" therefore records
a `fail` and **blocks its dependents** for a run that never executed, with one
retry to survive a condition that retrying will not clear.

Concretely, in thinking_app: `test_command` is
`tools/verification/screenshot-tests.sh verify-active`, which is host-globally
serialised by a capacity-one heavy-run lock (two concurrent runs are ~13 GiB on a
30 GiB host). Since t280 it exits **2** when another worktree's agent holds that
lock — the run never started, nothing was rendered, no results directory was even
touched. Under this helper that still lands as a red `tests_pass` gate. With
several agents working sibling worktrees, this is the normal case, not an edge
one. thinking_app's t320 (parallel task-workflow throughput) treats an honest gate
result under contention as a prerequisite.

## The fix

Map a project command's exit **2** to `status=skip` (and keep `1` = fail).
Design points for planning:

1. **Which codes are meaningful.** At minimum `0`/`1`/`2`. Consider whether a
   command's `3` should be `error`, and what happens to the helper's own exit
   contract — the caller distinguishes `2=skip(no command)` from `3=error`
   today, and a command-driven skip is a *different* fact from "no command
   configured" even though both are skips. Decide whether `result=` must say
   which.
2. **Multi-command lists.** `test_command` may be a list. Decide the aggregation
   rule and state it: a skip among passes is presumably a skip, but a skip
   beside a fail must stay a fail — the same "only the documented skip code is a
   skip; anything else non-zero is a failure" guard thinking_app's `all()` uses,
   so an unexpected status cannot be laundered into a skip.
3. **Opt-in or universal.** Whether a project must declare that its command
   speaks the 0/1/2 contract, or whether 2 is simply reserved. A project whose
   command returns 2 for something else would silently start recording skips.

## Acceptance

- A configured command exiting 2 records `status=skip`, and the gate does not
  block dependents.
- A command exiting 1 still records `fail` — a **reachable** rejection probe,
  observed failing, since mapping non-zero to skip over-broadly is the obvious
  way to satisfy this vacuously.
- A command exiting an unexpected non-zero (e.g. 3) does **not** record a skip.
- The "no command configured" skip stays distinguishable from a command-driven
  skip in `result=`.
- The multi-command aggregation rule is asserted, not just documented.
- The verifier header comment is corrected so it cannot be read as a claim about
  the command's exit code.

## Reference

thinking_app t280 (`bug: Report a heavy-lock refusal as a skip, not a test
failure`) is the downstream consumer that now emits 2, and its
`tools/verification/screenshot-tests.sh` exit-code comment records the measurement
behind this task.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T14:07:30Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-25T14:34:58Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-25T14:42:00Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:386fa979f89e623f

> **✅ gate:risk_evaluated** run=2026-08-25T14:42:00Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1605/risk_evaluated_2026-08-25T14:42:00Z-risk_evaluated-a1.log`
