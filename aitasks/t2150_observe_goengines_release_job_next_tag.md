---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [2148]
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
followup_kind: carry_over
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 11:39
updated_at: 2026-10-29 22:22
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_2** id=2026-10-29T19:56:58Z.01c9cc2b2aca2a33316de610 from=aitasks_go#t22_2 at=2026-10-29T19:56:57Z base=c0483ba6e5292257cb20efcfdb195a8c8271fe47 base_branch=main dirty=no host=omg16
>
> | Status as of 2026-10-29 (moment-relative; re-check before relying on it):
> | 
> | - The tag this task waits for exists. v0.40.1 was tagged at b5e76cf6b (2026-10-29 10:32Z). It is the first v* tag after t2148, and t2148's fix a06e4f5d8 is an ancestor of it.
> | - Runs for that tag, both reported success by `gh run list`:
> |   - Release: run 40858419630, https://github.com/beyondeye/aitasks/actions/runs/40858419630
> |   - Go engines check: run 40858419588
> | - This tag predates the aitasks_go#t22 cutover, so the goengines job should have run in legacy mode, which is what this task's Goal describes. The run's success alone does not prove the four Goal points. Check each one in the job log, as the body says:
> |   1. MODE:legacy;
> |   2. the hang-guard preflight and `go test` ran;
> |   3. INTEGRITY_SKIPPED:legacy mode at Export integrity;
> |   4. every *_SHA256SUMS.txt was uploaded and matches the executables under goengines/cmd/.
> |   Then compare the workflow against tests/test_release_workflow_goengines.py.
> | - Earlier, the aitasks_go#t22 relocation map planned to re-scope this task to "observe the first export-mode Release run", because the next tag was expected after the cutover. That premise no longer holds, so the re-scope is not needed. If the four points check out, this task can be completed as written. Observing the first export-mode Release run (MODE:export, INTEGRITY_OK, drift/asset checks) belongs in a separate follow-up task, filed after the cutover.
> | - t2149, the legacy-mode main push run, is already closed.

> **👁 note:read** id=2026-10-29T20:05:54Z.c10b5392ae9e23caf79c4c44 by=t2150 at=2026-10-29T20:05:54Z mode=explicit ids=2026-10-29T19:56:58Z.01c9cc2b2aca2a33316de610

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-29T20:22:45Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-29T20:28:30Z status=pass attempt=1 type=human
