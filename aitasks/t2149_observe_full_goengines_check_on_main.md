---
priority: medium
effort: low
depends: [2148]
issue_type: test
status: Ready
labels: [go_engine, framework, release_scripts]
gates: [risk_evaluated]
anchor: 2138
followup_kind: carry_over
created_at: 2026-10-26 11:39
updated_at: 2026-10-26 11:39
---

## Origin

Carry-over from t2141 (observe the first CI runs of t2138's two-mode goengines
wiring). t2141 could verify only part of its item 1. On `main`, runs 40187609686
and 40279191111 showed the `mode` job printing `MODE:legacy`, `check` and `bench`
admitted, and `export-integrity` reporting legacy. But `check` stopped at
`go test` on the procsup hosted-runner leak (t2148), so every step after it was
skipped and never observed.

## Goal

On the first `Go engines check` **push run on `main`** after t2148 lands
(`gh run list --workflow goengines-check.yml --branch main`, then
`gh run view <id> --json jobs` and `--log`), confirm:

- `mode` prints `MODE:legacy`;
- `check`: `go test` passes, and then each of these steps runs and passes:
  - Release cross-build, including the per-executable sums loop: `sha256sum -c`
    once per `*_SHA256SUMS.txt`, and at least one such file exists;
  - Release workflow structure guard;
  - build.sh tests;
  - benchci.sh tests;
  - annot conformance corpus sync guard;
  - export integrity script tests;
- `export-integrity` prints `INTEGRITY_SKIPPED:legacy mode …` and `DRIFT_SKIPPED:legacy`,
  and its export-only steps show as skipped;
- `bench` runs, advisory (`continue-on-error`; its verdict belongs to t1878).

If the run is triggered off `main` (for example on a PR), it does not count. This item
is about `main`.

Record any divergence from the static guard's model
(`tests/test_release_workflow_goengines.py`) as a bug task against the workflow
wiring. Record step-level conclusions with run IDs in the plan's Final
Implementation Notes.
