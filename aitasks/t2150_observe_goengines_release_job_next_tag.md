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

Carry-over from t2141, item 4. The release workflow's `goengines` job became
two-mode in t2138, but the last tag (v0.40.0) predates t2138, so the job has never
run with that wiring. This depends on t2148: until the procsup hosted-runner leak
is fixed, the job's `go test` fails the same way the `Go engines check` job does.

## Goal

At the first `v*` tag after t2148 lands, open the `Release` run
(`gh run list --workflow release.yml`, then `gh run view <id> --json jobs` and `--log`)
and confirm that the `goengines` job:

- detected legacy mode (`MODE:legacy`; the mode step's output gates the later steps
  with `steps.mode.outputs.mode != 'export'`);
- ran the hang-guard preflight and `go test`;
- reported legacy at `Export integrity` (`INTEGRITY_SKIPPED:legacy mode …`);
- uploaded every `*_SHA256SUMS.txt`. Compare the release assets against the
  executables under `goengines/cmd/`.

Record any divergence from the static guard's model
(`tests/test_release_workflow_goengines.py`) as a bug task against the workflow
wiring. Record step-level conclusions with run IDs in the plan's Final
Implementation Notes.
