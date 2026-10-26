---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [go_engine, framework, release_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2138
followup_kind: risk_mitigation
created_at: 2026-10-25 12:56
updated_at: 2026-10-26 09:50
---

## Origin

Risk-mitigation ("after") follow-up for t2138, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — Actions semantics unverifiable locally

- GitHub Actions semantics (`!cancelled()` with a failed `needs`, a skipped job reported as success, `GITHUB_OUTPUT` plumbing) cannot be executed locally. The first real proof is the post-push run · severity: medium · → mitigation: observe_first_ci_runs

## Goal

t2138 made `goengines-check.yml` and the release `goengines` job two-mode, keyed on whether `goengines/EXPORT.txt` exists (`.github/scripts/goengines_integrity.sh mode`). The wiring is pinned statically by `tests/test_release_workflow_goengines.py` and was linted with actionlint, but it has never run on a hosted runner. Confirm it does what it claims:

1. **Legacy mode on `main` (the current state).** After t2138's push, open the `Go engines check` run for that commit (`gh run list --workflow goengines-check.yml`, then `gh run view <id>`) and confirm:
   - the `mode` job prints `MODE:legacy` and exposes `mode=legacy`;
   - `check` ran in full (gofmt, vet, preflight, go test, cross-build with the per-executable sums loop, every repo-side guard including `tests/test_goengines_export_integrity.sh`);
   - `bench` ran (advisory);
   - `export-integrity` ran and printed `INTEGRITY_SKIPPED:legacy mode …` and `DRIFT_SKIPPED:legacy`, and its export-only guard steps show as skipped.
2. **Fail-closed condition (optional, cheap).** If it can be done without disrupting `main`, confirm with a `workflow_dispatch` on a throwaway branch where the mode step is made to fail that `check`/`bench` still run (the `!cancelled() && … != 'export'` condition).
3. **Export mode (optional).** On a throwaway branch, add a fixture `goengines/EXPORT.txt` (format 1, generated from the tree's real hashes, as in t2138's real-tree dry run in `aiplans/archived/p2138_*.md`) and dispatch the workflow: `check`/`bench` must be skipped, `export-integrity` must print `INTEGRITY_OK`, and drift must be reported as warnings only. Expect the tests/ci/bench files of the legacy tree to appear as `DRIFT:unlisted` unless the record lists them. Delete the branch afterwards.
4. **Release job.** At the next `v*` tag, confirm in the `Release` run that the `goengines` job detected legacy mode, ran the preflight and `go test`, reported legacy at `Export integrity`, and uploaded every `*_SHA256SUMS.txt`.

Record any divergence from the static guard's model as a bug task against the workflow wiring.
