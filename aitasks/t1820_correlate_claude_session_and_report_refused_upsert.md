---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
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
created_at: 2026-09-16 18:08
updated_at: 2026-09-17 09:02
---

## Origin

Spawned from t1804 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_sessions.py:1839` — `_claude_newest_transcript` has the same uncorrelated newest-by-cwd guess t1804 removed from the codex side; with two claude sessions in one repo it can return another agent's transcript. Lower impact than the codex case (claude's SessionStart hook normally records the id, so this is only a backstop), and deliberately left unchanged by t1804 to keep that task codex-scoped.
- `.aitask-scripts/lib/agent_freeze.py:515-517` — the freeze engine's fallback upsert parses any `<WORD>:<id>|…` line as success, so an `UPSERT_REFUSED:<id>|<reason>` reply (which exits 0) is read as the record id. The freeze then fails at `freeze-begin` with a misleading `begin`-stage error instead of reporting the refusal. Pre-existing; not triggered by t1804's change.

## Diagnostic context

t1804 fixed the codex half of the first defect: matching a transcript on `cwd`
alone answers "some session of this project", not "this agent's session", so the
newest match is routinely a different agent's conversation. The codex path now
resolves from the rollout the agent's own process holds open
(`codex_session_for_pid`) and the uncorrelated scan refuses to guess
(`MISS_AMBIGUOUS`). `_claude_newest_transcript` still returns the newest
cwd-match.

Two things differ for claude and should shape the fix rather than be assumed
away:

- claude's SessionStart hook DOES fire, so the resolver is a backstop rather
  than the mechanism — the blast radius is smaller;
- the fd-correlation trick may not transfer. t1804 measured that a codex process
  holds exactly one `rollout-*.jsonl` open; whether a claude process keeps its
  `~/.claude/projects/<dir>/<sid>.jsonl` open was never measured. Measure before
  designing, exactly as t1804's pre-phase probe did.

The second defect was found while reading the same function's error handling and
is unrelated to sessions.

## Suggested fix

For the first: either correlate via the live process (measure the fd behaviour
first) or, failing that, apply t1804's refusal rule — group candidates by
session id and return an ambiguity miss rather than the newest. For the second:
test the `UPSERTED:` prefix before parsing a record id out of the line, and
surface `UPSERT_REFUSED:` as its own resolve-stage failure.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T06:02:29Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T06:37:46Z status=pass attempt=1 type=human
