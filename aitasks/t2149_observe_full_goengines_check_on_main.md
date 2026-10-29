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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2148** id=2026-10-26T13:57:23Z.6176ae4bae9c3f6bb01a13df from=t2148 from_verified=yes at=2026-10-26T13:57:23Z base=a06e4f5d8ee3cd9f9fe1c6bf4eaa2b70dfcb6df7 base_branch=main dirty=no host=omg16
>
> | Advisory context from t2148 (procsup hosted-runner leak). It doesn't change this task's scope: branch runs do not satisfy the main-only acceptance.
> | 
> | t2148's fix (commit a06e4f5d8 on local main, not yet pushed when this note was written) was probed on a throwaway branch t2148-ci-probe = origin/main 4626b080c + the fix cherry-picked as 20faee626 (since deleted). Go engines check runs 40334103309 (push), 40334114895 and 40334119129 (workflow_dispatch): the `check` job succeeded in all three, with every step after `go test` running and passing (release cross-build + sums loop, structure guard, build.sh/benchci.sh tests, annot corpus sync guard, export integrity script tests). `bench` "Benchmark gate" failed in all three (advisory, continue-on-error), with BENCH_REGRESSION/OVER_BUDGET in cmd/ait-testmap, testmap/annot, testmap/deps and testmap/modules. It failed the same way on main runs 40279191111, 40187609686 and 40161193156, so that verdict is t1878's.
> | 
> | Expect the same on the first main push run once a06e4f5d8 is pushed. The run IDs above are evidence about the branch, not about main.

> **👁 note:read** id=2026-10-29T10:37:31Z.0030d40a88b1529823eceaae by=t2149 at=2026-10-29T10:37:31Z mode=explicit ids=2026-10-26T13:57:23Z.6176ae4bae9c3f6bb01a13df
