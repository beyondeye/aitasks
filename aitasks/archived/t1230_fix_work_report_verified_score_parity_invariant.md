---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
archived_reason: superseded
labels: [test, reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-24 11:50
updated_at: 2026-07-28 12:54
completed_at: 2026-07-28 12:54
---

## Origin

Spawned from t1162_5 during Step 8b review.

## Upstream defect

- `tests/test_codeagent_work_report.sh:139-152 — the verified-score parity block asserts "work-report mirrors explain, or is absent", but the satisfaction-feedback score updater writes per-operation scores independently; aitasks/metadata/models_claudecode.json now has opus4_8 with work-report: 100 and no explain key, so the suite fails 1/28 on a clean tree. Pre-existing, unrelated to t1162_5, and reproducible before any change there — the invariant is unmaintainable once real feedback accumulates.`

## Diagnostic context

t1162_5 ran the related suites as a regression check after touching only
website documentation and adding a new test. `test_codeagent_work_report.sh`
failed with:

```
FAIL: verified.work-report does not mirror verified.explain in
      aitasks/metadata/models_claudecode.json
PASS: 27 / 28
```

The file was confirmed **committed and untouched** by that task
(`./ait git status --porcelain` clean for the path). The offending entry:

```
opus4_8 -> verified: {'work-report': 100}
```

The last commit touching the file is
`ait: Update verified score for claudecode/opus4_8 pick` — i.e. the score was
written organically by the satisfaction-feedback updater
(`aitask_usage_update.sh` / the verified-score path), not by a seeding step.

The parity assertion was introduced in t1162_2 to pin that `work-report`
mirrors `explain` at seed time. That holds for `seed/models_*.json`, which are
static. It does **not** hold for the live `aitasks/metadata/models_*.json`,
which accumulate real per-operation ratings over time and can legitimately
gain a `work-report` score for a model that has never been rated on `explain`.

## Suggested fix

Scope the parity invariant to the seed files only (where it is meaningful and
stable), and drop or relax it for the live `aitasks/metadata/models_*.json` —
those are user data, not a fixture. If some live-file check is still wanted,
assert only that any present `work-report` value is a valid score, not that it
equals `explain`.

## Resolution — already fixed by t1232

Closed without implementation on 2026-07-28: the suggested fix landed
independently under **t1232** (`t1232_fix_models_verified_parity_baseline.md`,
archived), commit `09ebdb42a bug: Scope verified-parity Test 7 to seed files,
add accumulator boundary guard (t1232)`.

`tests/test_codeagent_work_report.sh` Test 7 now iterates `seed/models_*.json`
only — never the live `aitasks/metadata/models_*.json` — which is exactly the
scoping this task asked for. The `opus4_8 -> verified: {'work-report': 100}`
live entry no longer trips the assertion; all three parity checks pass. The
accumulator-side boundary (an independent per-operation score persists without
an `explain` partner) is pinned by `tests/test_verified_update.sh` Test 19/20.

The suite does still report 5 failures, but for an unrelated cause — codeagent
tests hardcoding v4 model names (`sonnet4_6` / `opus4_8`) after the v5 seed
migration. That drift is tracked separately by **t1246**
(`t1246_fix_codeagent_tests_v5_model_drift.md`) and is out of scope here.
