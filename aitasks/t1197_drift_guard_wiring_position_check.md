---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1171
implemented_with: claudecode/opus4_8
created_at: 2026-07-21 11:03
updated_at: 2026-07-21 11:53
---

## Origin

Review follow-up from t1194, dispositioned at Step 8 review.

## Defect

`tests/test_seed_manifest_drift.sh` derives the install-side manifest from the
`install_seed_*` functions that `main()` actually calls, by grepping the
`declare -f main` body for each function name:

```bash
main_body="$(declare -f main)${probe_wiring}"
for fn in $(declare -F | awk '{print $3}' | grep '^install_seed_'); do
    grep -qE "(^|[^[:alnum:]_])${fn}([^[:alnum:]_]|$)" <<< "$main_body" || continue
    "$fn"
done
```

The grep matches a call **anywhere** in `main()` — including *after*
`rm -rf "$INSTALL_DIR/seed"`, which `install.sh` runs once the seed installers
are done. An installer wired after that cleanup would:

- **pass** the guard, because the test fixture still has a populated `seed/`
  when the derivation runs the function directly; but
- **deliver nothing** in a real tarball install, because `seed/` is already
  gone by the time `main()` reaches the call.

That is a false negative in exactly the class of drift the guard exists to
catch. The same gap applies to `list_unwired_installers()`, which backs the
Test 6 wiring assertion.

## Goal

Make call **position** part of the wiring contract, not just call presence.

`declare -f main` renders the cleanup verbatim as:

```
    rm -rf "$INSTALL_DIR/seed";
```

so the fix is small: truncate `main_body` at that line before the wiring grep
(e.g. with `sed '/rm -rf "\$INSTALL_DIR\/seed"/q'`), so only the pre-cleanup
portion of `main()` counts as wired. Apply the same truncation in
`list_unwired_installers()` so a post-cleanup installer is reported by name
rather than silently accepted.

Make the truncation **fail loudly if its anchor disappears**: if the cleanup
line is not found in the `main()` body, the helper must error rather than
silently fall back to scanning the whole function (which would restore the
current false negative the moment `install.sh` reworded that line).

## Verification

- A negative control that wires a synthetic `install_seed_*` **after** the
  `rm -rf "$INSTALL_DIR/seed"` line and asserts the guard reports it — mirroring
  the existing Test 3 (`probe_fn_src` + `probe_wiring`) pattern, which must keep
  the real `main()` intact and only append a synthetic call site.
- The existing Test 3 (pre-cleanup wiring) must still report no spurious drift,
  proving the truncation did not cut too early.
- A control for the missing-anchor case: feed a `main()` body with no cleanup
  line and assert the helper errors.
- `bash tests/test_seed_manifest_drift.sh` still passes end to end.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-21T08:53:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-21T09:34:06Z status=pass attempt=1 type=human
