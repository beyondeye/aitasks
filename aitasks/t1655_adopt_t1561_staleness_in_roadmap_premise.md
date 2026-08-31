---
priority: medium
effort: medium
depends: [1561, t1569_5]
issue_type: feature
status: Ready
labels: [backlog, scheduling, planning]
anchor: 1569
followup_kind: carry_over
created_at: 2026-08-31 19:48
updated_at: 2026-08-31 19:48
---

## Problem

`.aitask-scripts/lib/roadmap_premise.py` (t1569_5) is a **deliberately narrow,
deliberately temporary** premise-drift signal for the background-work roadmap. It
exists only because the framework had no shared staleness mechanism when the
roadmap landed: the manual-verification helper reads its scope from
`file_references:` (0 of 483 active tasks carry it) and its baseline from
`verification_baseline:` (absent on follow-ups), so neither of its inputs applies
to an auto-spawned follow-up.

Its module docstring and `__all__` name t1561 as the substitution point, and
`tests/test_roadmap_premise.py::PublicSurfaceTests` fails if the surface grows —
the guard exists precisely so this module does not quietly become the framework's
second permanent staleness mechanism.

## Goal

Consume t1561's generalized staleness mechanism in place of the local interface,
and delete `roadmap_premise.py`.

## Scope

The substitution surface is exactly two functions plus their vocabularies (see
`__all__`):

- `baseline_for(origin_ids, commit_lines, data_prefixes=...) -> Baseline`
- `check(origin_ids, origin_paths, commit_lines, baseline=None, data_prefixes=...) -> PremiseResult`

Four properties must survive the swap, or the roadmap's honesty guarantees
regress. Each is already pinned by a test in `tests/test_roadmap_premise.py`:

1. **The baseline is the origin's last *landing* commit** — a commit that names
   the origin AND touches a path outside the task-data trees. Measured
   2026-08-31, 61 of 1714 `(tNN)`-tagged commits touch no code path and 35 of
   1615 tagged ids have a metadata-only *newest* tagged commit, so an unqualified
   "newest tagged commit" silently masks real drift as FRESH.
2. **`UNKNOWN` drives the verdict**, sharing one evidence list with `CHANGED` so
   the two cannot drift apart.
3. **`SKIP` is fail-open and silent**, and `metadata_only` stays distinct from
   `unknown_history` — the remedies differ.
4. **Purity.** `roadmap_premise` is in `PURE_MODULES` in
   `tests/test_parallel_admission_purity.py`; whatever replaces it must keep the
   roadmap's policy layer free of git, clocks and subprocesses, or
   `roadmap_policy` stops being fixture-testable.

Also re-check the two accepted narrowings recorded in
`aidocs/framework/background_work_roadmap.md` — no `DELETED:` record, and no
`:(literal)` pathspec guard — and update that design record to describe whatever
t1561 provides instead.

## Reference files

- `.aitask-scripts/lib/roadmap_premise.py` (the interface being replaced)
- `.aitask-scripts/lib/roadmap_policy.py` (its only consumer)
- `aidocs/framework/background_work_roadmap.md` (the design record to update)
- `tests/test_roadmap_premise.py`, `tests/test_roadmap_integration.py`
- `aidocs/framework/manual_verification_staleness.md` (the borrowed conventions)

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
python3 -m unittest tests.test_roadmap_policy tests.test_roadmap_integration -v
python3 -m unittest tests.test_parallel_admission_purity -v
```
