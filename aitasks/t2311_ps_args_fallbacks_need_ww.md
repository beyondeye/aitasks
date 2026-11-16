---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-11-15 23:45
updated_at: 2026-11-16 08:48
---

## Origin

Spawned from t2306 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_questions/owner.py:38 — non-procfs fallback reads `ps -o args=` without `-ww`; in a process that imported readline (COLUMNS=80 exported) argv is cut at 80 columns (macOS-only path; BSD ps COLUMNS handling not measured)`
- `.aitask-scripts/monitor/monitor_core.py:502 — same `ps -p <pid> -o args=` without `-ww` in the non-procfs companion-keyword check; keywords past column 80 can be missed`

## Diagnostic context

t2306 found that two `test_aitask_questions.py` StoreTests failed only under
pytest. pytest imports `readline`, and GNU readline exports `COLUMNS=80` into
the C-level environment. That change is invisible to `os.environ` but is
inherited by child processes. procps `ps` honours `COLUMNS` and cut the
fixture's `ps -o args=` lines at 80 columns:

- `python -c "import readline; …"` truncates.
- Without readline the lines are full width.
- With `-ww` they are full width either way.

t2306 fixed the test fixture (`_runs_below` now uses `ps -ww`). The two
production call sites above make the same `ps -o args=` call, but only on
their non-procfs fallback paths (macOS), so on Linux they are unaffected. Both
procps and BSD ps accept `-ww` (unlimited width). Whether BSD ps honours
`COLUMNS` when stdout is a pipe was **not measured**: confirm on macOS before
calling it a live bug there.

## Suggested fix

Add `-ww` to both `ps` invocations (and audit any other `ps -o args=`/`command=`
reader whose matched text can sit past column 80, e.g.
`tests/test_minimonitor_concern_smoke.py:195`).
