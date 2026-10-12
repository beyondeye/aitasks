---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1797
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-11 19:13
updated_at: 2026-10-12 09:20
---

## Origin

Spawned from t1944 (restore the Codex working-timer tick) during its test runs.

## Upstream defect

- tests/test_codeagent_resume_session.sh:107 — opencode cases pin `opencode/openai_gpt_5_2`, which the live registry now marks unavailable, so 3 asserts fail with die's exit 1 instead of the RESUME_UNSUPPORTED exit 2 (reproduced on a clean HEAD worktree; same pinning pattern t1871 fixed in test_codeagent.sh by deriving the model from the fixture registry)

## Diagnostic context

While verifying t1944 (which only changed Codex argv literals in this file), `bash tests/test_codeagent_resume_session.sh` reported 36/39. The 3 failures are all in the "--resume-session: opencode is refused with exit 2" block:

- `opencode resume: exit 2 (usage), NOT die's 1` — got 1
- `opencode resume: machine-readable refusal token` — output was `Error: Model 'openai_gpt_5_2' is unavailable (not currently marked as available by connected providers). Run 'ait opencode-models' to refresh.`
- `opencode raw without --resume-session: still works` — got 1

The identical 3 failures reproduce on a detached worktree of HEAD before t1944's commit, so they are pre-existing. The launcher refuses an opencode model the registry marks unavailable before it reaches the resume-session guard, so the test asserts against a registry state that drifts with `ait opencode-models` refreshes.

## Suggested fix

Derive the opencode model from the test's fixture registry instead of pinning it, as t1871 did for `tests/test_codeagent.sh` (`codeagent_active_model` over the fixture `models_opencode.json`), or point the test at an isolated fixture registry with a known-available entry.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T06:20:30Z status=pass attempt=1 type=human
