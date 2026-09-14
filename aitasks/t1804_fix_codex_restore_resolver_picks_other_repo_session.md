---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codex]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1797
followup_kind: upstream_defect
created_at: 2026-09-14 16:48
updated_at: 2026-09-14 17:07
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
