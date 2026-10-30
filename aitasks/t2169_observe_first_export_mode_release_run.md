---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [go_engine, framework, release_scripts]
gates: [risk_evaluated]
anchor: 2138
created_at: 2026-10-30 12:13
updated_at: 2026-10-30 12:13
---

## Origin

Filed by aitasks_go#t22_4 (the testmap cutover), at the user's decision.
t2150 observed the `Release` run of v0.40.1 (run 40858419630), the last
**legacy-mode** release, and is archived. The aitasks_go#t22_3 bootstrap
export (public commit `6405506d1345a46919f63cd5b984976c20d0a720`, parent
`c0483ba6e5292257cb20efcfdb195a8c8271fe47`) switched public `goengines/` to
**export mode**, so the next `v*` tag runs the release workflow's `goengines`
job in that mode for the first time. Nobody observes it otherwise.

The export-mode `Go engines check` was already probed on the bootstrap commit
(run 40970848074: `MODE:export`, `INTEGRITY_OK`, `DRIFT_NONE`, `check` and
`bench` skipped). `release.yml` has no `workflow_dispatch`, so its export
path could not be probed before a real tag.

## Goal

At the first `v*` tag after the bootstrap export, open the `Release` run
(`gh run list --repo beyondeye/aitasks --workflow release.yml`, then
`gh run view <id> --repo beyondeye/aitasks --json jobs` and `--log`) and
confirm that the `goengines` job:

- detected export mode (`MODE:export`), so the legacy test steps are skipped
  (gated on `steps.mode.outputs.mode != 'export'`);
- passed `Export integrity` with `INTEGRITY_OK`, and its drift report prints
  `DRIFT_NONE` (that step is `continue-on-error`, so read the log, not the
  step conclusion);
- built and uploaded one binary per `build.sh` MATRIX target per
  `goengines/cmd/*` executable, named `<name>_<V>_<os>_<arch>`, and every
  `*_SHA256SUMS.txt`. Compare the asset list with the v0.40.1 run
  (40858419630): the same names apart from the version, and
  `sha256sum -c` passes on the downloaded assets;
- produced binaries whose `version` / `version --json` output has the
  release version and the tagged commit (download one linux/amd64 binary and
  run it).

Record any divergence from the static guard's model
(`tests/test_release_workflow_goengines.py`) as a bug task against the
workflow wiring. Engine-side causes go to beyondeye/aitasks_go
(`./ait create --batch --project aitasks_go`). Record step-level conclusions
with run IDs in the plan's Final Implementation Notes.

## Notes

- Public `goengines/` is an export target: never fix engine code here. Changes
  arrive from beyondeye/aitasks_go through `promote/export.sh`.
- Until a tag exists this task cannot run; leave it Ready and pick it after
  the next release.
