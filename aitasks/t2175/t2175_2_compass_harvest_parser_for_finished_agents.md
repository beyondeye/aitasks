---
priority: medium
effort: medium
depends: [t2175_1]
issue_type: feature
status: Ready
labels: [compass]
anchor: 2175
created_at: 2026-10-31 19:58
updated_at: 2026-10-31 19:58
---

# Harvest parser: items and context entries from finished agents

Child of t2175. Depends on the format/writer child.

## Scope
- Read a finished or frozen agent's capture (`~/.config/aitasks/frozen/<id>/capture.txt`, record from `aitask_agent_sessions.sh list`) and its workflow-end banner (`.claude/skills/task-workflow/workflow-end.md`: `outcome:`, `pushed:`, `follow-ups created:`). Group records by project root.
- Deterministically create: items for each follow-up task id (incl. cross-repo `aitasks#tNNN`, marked unverified unless the registry resolves), plus a stub context entry per item with origin (agent, task, commit, date) and sources (task/plan paths, capture file + line range, shas).
- The free prose above the banner ("push main", "deploy dev", test gaps) is turned into `action`/`watch` items by the compass agent, not the parser; the parser records the passage's line range and leaves the item marked agent-derived.
- Exploration sources: take created task ids from an explore agent's final output; VERIFY first whether task files record their creating skill and use that if so.
- Trail sources: register a pointer to the trail artifact handle, never a copy.
- Idempotent (re-harvesting the same capture changes nothing). Triggers: agent freeze (`lib/agent_freeze.py`) and workflow-end. `aitask_frozen.sh drop` runs harvest first and REFUSES when harvest fails.
- Put the banner format under a contract test so a change to workflow-end.md fails a test instead of silently breaking the parser.

## Tests
Fixture captures from real frozen agents (pick, explore, no-banner, truncated), idempotency, drop-refusal on harvest failure.
