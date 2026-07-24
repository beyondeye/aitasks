---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [test, reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-24 11:50
updated_at: 2026-07-24 11:50
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
