---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests, board_columns, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-12 08:23
updated_at: 2026-08-12 09:36
---

## Origin

Spawned from t1468_4 during Step 8b review.

## Upstream defect

- `tests/test_boardcol_update.sh:81-83 — scaffold copy list omits
  record_protocol.py, so every --boardcol validation fails inside the scaffold`

`tests/test_boardcol_update.sh` is **red on `main`** and has been for some time.
Its `setup_project()` builds an isolated scaffold and copies a hand-maintained
subset of Python modules:

```bash
for m in board_columns board_ordering config_utils task_yaml; do
    cp "$PROJECT_DIR/.aitask-scripts/lib/$m.py" .aitask-scripts/lib/
done
```

But `.aitask-scripts/lib/board_columns.py:73` does `from record_protocol import
(...)`, and `record_protocol.py` is not in that list. Importing `board_columns`
inside the scaffold therefore raises:

```
ModuleNotFoundError: No module named 'record_protocol'
```

which surfaces to the caller as:

```
Error: board column 'c1': could not read the configured column list.
```

so `aitask_update.sh --batch 1 --boardcol c1` exits 1.

## Why it is invisible

The failure is masked twice over:

1. The test invokes the command as
   `./.aitask-scripts/aitask_update.sh --batch 1 --boardcol c1 >/dev/null 2>&1`,
   discarding the diagnostic.
2. The file runs under `set -e`, so it aborts at that first call.

The net effect is that `bash tests/test_boardcol_update.sh` prints only its first
test header and exits 1, with **no FAIL line, no summary, and no error text** —
it looks like a hang or a truncated run rather than an assertion failure.

## Suggested fix

Add `record_protocol` to the module copy loop. Rather than extending the
hand-maintained list again, consider deriving the closure — the list has now
drifted at least once, and any future import added to `board_columns.py` (or its
transitive deps) breaks the scaffold the same silent way.

Separately, drop the `2>&1` from the `--boardcol` invocations (or capture stderr
into a variable and assert on it) so the next such breakage reports its own
cause instead of vanishing.

## Verification

- `bash tests/test_boardcol_update.sh` runs to completion and prints a
  `Passed: N / N` summary.
- Deliberately removing `record_protocol.py` from the copy list again makes the
  suite fail with a **named, visible** assertion, not a silent `exit 1`.

## Provenance note

Reproduced on a clean `HEAD` worktree during t1468_4 (identical exit code and
byte-identical output to the working tree), confirming it is independent of that
task's changes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-12T06:36:26Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-12T07:00:42Z status=pass attempt=1 type=human
