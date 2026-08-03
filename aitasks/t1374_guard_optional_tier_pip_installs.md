---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1387]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-08-03 09:41
updated_at: 2026-08-03 16:09
---

## Origin

Spawned from t1354_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:722,730 — setup_chat_deps() runs `pip install` unguarded under `set -e`, so a failed chat-tier install aborts all of `ait setup`, contradicting its own "never fails the overall setup" comment (same defect class as the one fixed in t1354_3's setup_dev_deps)`
- `.aitask-scripts/aitask_setup.sh:663,664,673 — setup_pypy_venv() has the same unguarded `pip install` calls under `set -e`; a PyPy dep failure aborts setup instead of degrading to the documented warn-and-remove path`

## Diagnostic context

`aitask_setup.sh` runs under `set -euo pipefail` (line 2). The optional-tier
installers are each written as: run `pip install`, then validate imports/specs,
then warn and `return 0` on failure — the documented contract being that an
optional tier can never break the core install.

That contract is false whenever pip itself exits non-zero (offline machine,
unreachable index, a wheel that will not build). `set -e` aborts the entire
script at the bare `pip install` line, so the validate / warn / `return 0` path
below it is never reached. The failure mode is worst exactly when it matters
most: a user on a flaky network runs `ait setup`, an optional tier fails, and
the whole setup dies partway through instead of warning and continuing.

Confirmed empirically in t1354_3 (not merely reasoned about) with a stub `pip`
that always exits 1, driven through the real extracted function body:

    unguarded:  setup exits 1, the continuation line is never printed
    guarded:    warns, returns 0, setup continues, exit 0

t1354_3 fixed only its own new `setup_dev_deps()`; these two pre-existing call
sites were left untouched as out of scope.

Note both are reached on ordinary runs, not just opt-in ones: each tier
revalidates on every plain `ait setup` once installed (`chat_deps_present` /
the `-d "$PYPY_VENV_DIR"` clause), so an offline `ait setup` on a machine that
has either tier can abort today.

## Suggested fix

Apply the pattern already proven in `setup_dev_deps()`: wrap each fallible
command as `if ! cmd; then warn "..."; return 0; fi` so the failure stays inside
a condition where `set -e` does not fire. Covers both `pip install` calls in
`setup_chat_deps` and all three in `setup_pypy_venv` (including
`pip install --quiet --upgrade pip`).

Worth auditing the rest of `aitask_setup.sh` for the same shape in any other
function that documents a best-effort / never-block contract — the two found
here were not sought out, they surfaced while modelling a new tier on the chat
one, so the enumeration is not known to be complete.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T09:07:46Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-03T12:57:46Z status=pass attempt=1 type=human
