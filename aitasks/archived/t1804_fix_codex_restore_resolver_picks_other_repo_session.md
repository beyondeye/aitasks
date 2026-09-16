---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [codex]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1797
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-14 16:48
updated_at: 2026-09-16 23:27
completed_at: 2026-09-16 23:27
---

## Origin

Spawned from t1797 during Step 8b review.

## Upstream defect

- .aitask-scripts/lib/agent_sessions.py:1659 — `_codex_newest_transcript` returns the newest rollout whose cwd equals the project root, so with several Codex sessions in one repo the restore fallback can resolve a different session than the one being restored (observed live in t1797's resume smoke)

## Diagnostic context

Codex's SessionStart hook does not fire in the interactive TUI (t1705_1), so a
Codex frozen-agent record normally carries no session id, and
`newest_transcript_for(root, "codex")` is the fallback. It scans
`~/.codex/sessions/*/*/*/*.jsonl` newest-first and returns the first rollout
whose `session_meta.payload.cwd` equals the project root. Nothing ties that
rollout to the pane being restored.

Observed in t1797's resume smoke (2026-09-14): a marker session was created in
the repo root through `ait codeagent invoke raw`. Immediately afterwards,
`newest_transcript_for(<repo root>, "codex")` returned a DIFFERENT repo-root
session; this machine had about 14 Codex shadows running, several in the same
repo. Resuming that id would restore another agent's conversation into the
frozen pane. t1706 notes the same indistinguishability for its live-delivery
adapter; nothing tracks it for restore.

## Suggested fix

Tie the rollout to the specific agent rather than to the root. Options: record
the rollout path or id at freeze time (e.g. from the codex process's open file
descriptors), or match the rollout's start time against the pane process's
start. Where no such correlation is possible and more than one candidate
rollout exists for the root, fall back to re-pick instead of guessing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-16T07:29:49Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-16T14:57:51Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-16T20:27:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:857ecdbe289f8b68

> **✅ gate:risk_evaluated** run=2026-09-16T20:27:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1804/risk_evaluated_2026-09-16T20:27:06Z-risk_evaluated-a1.log`
