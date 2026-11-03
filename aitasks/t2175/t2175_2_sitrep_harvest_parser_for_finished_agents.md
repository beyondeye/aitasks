---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t2175_1]
issue_type: feature
status: Implementing
labels: [sitrep]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2182]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-10-31 19:58
updated_at: 2026-11-03 10:40
---

# Harvest parser: items and context entries from finished agents

Child of t2175. Depends on the format/writer child.

## Scope
- Read a finished or frozen agent's capture (`~/.config/aitasks/frozen/<id>/capture.txt`, record from `aitask_agent_sessions.sh list`) and its workflow-end banner (`.claude/skills/task-workflow/workflow-end.md`: `outcome:`, `pushed:`, `follow-ups created:`). Group records by project root.
- Deterministically create: items for each follow-up task id (incl. cross-repo `aitasks#tNNN`, marked unverified unless the registry resolves), plus a stub context entry per item with origin (agent, task, commit, date) and sources (task/plan paths, capture file + line range, shas).
- The free prose above the banner ("push main", "deploy dev", test gaps) is turned into `action`/`watch` items by the sitrep agent, not the parser; the parser records the passage's line range and leaves the item marked agent-derived.
- Exploration sources: take created task ids from an explore agent's final output; VERIFY first whether task files record their creating skill and use that if so.
- Trail sources: register a pointer to the trail artifact handle, never a copy.
- Idempotent (re-harvesting the same capture changes nothing). Triggers: agent freeze (`lib/agent_freeze.py`) and workflow-end. `aitask_frozen.sh drop` runs harvest first and REFUSES when harvest fails.
- Put the banner format under a contract test so a change to workflow-end.md fails a test instead of silently breaking the parser.

## Tests
Fixture captures from real frozen agents (pick, explore, no-banner, truncated), idempotency, drop-refusal on harvest failure.

## Durable source pointers (handed over by t2175_1)
Agent captures under `~/.config/aitasks/frozen/<id>/` are deleted by
`lib/agent_sessions.py` `remove_captures` — on `drop`, and also from `upsert`
(re-registration) and `freeze_abort` — so a pointer into them is not durable.
- Retain every passage a context entry points at with
  `./.aitask-scripts/aitask_sitrep_todo.sh retain` (stdin) BEFORE writing the
  item, and point `capture:` sources at the returned `sources/<hex>.txt#L…`.
  Never point at `~/.config/aitasks/frozen/` — the writer rejects it (exit 2).
- Use `add --ref <task id>` for follow-up task items: a ref that already exists
  in any state returns `EXISTS:` and writes nothing (re-harvest idempotency,
  dismissals stick). Use `add ... --context-file -` to create the item and its
  stub context entry in one atomic write.
- Format contract: `tests/fixtures/sitrep/` (golden store) and the header of
  `.aitask-scripts/aitask_sitrep_todo.sh`.
- **Acceptance:** after `aitask_frozen.sh drop <id>`,
  `aitask_sitrep_todo.sh check-sources` reports `SOURCE_OK` for every harvested
  pointer, and `context c<N>` + the retained file still show the passage.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T06:26:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-03T08:38:49Z status=pass attempt=1 type=human
