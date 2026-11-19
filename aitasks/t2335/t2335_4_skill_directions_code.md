---
priority: medium
effort: high
depends: [t2335_2, t2335_3]
issue_type: feature
status: Ready
labels: [sitrep, skills]
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-19 05:12
---

## Context

Child of the sitrep work-directions task; depends on the store, refresh and trail-overlay children. The sitrep skill (`.claude/skills/aitask-sitrep/SKILL.md.j2`) has the codes `>t >w >q >tr >p >c >?`. Directions are created and maintained here: grouping, ranking and summary prose are agent judgment, confirmed by the user, written through the writer.

## Scope

- **`>d` — directions.**
  - Bare `>d`: read `list`, `directions`, every member context and the trail membership and critical-path evidence; propose the set of directions: which open items belong to which direction (reusing existing ones first, proposing a new slug only for items none fits), a title and summary per direction, linked trails, the `next` step, and ONE ranked order with a reason per position. Ranking evidence: task priority / effort, crash-recovery rank tiers, each trail's next wave and critical path, `/aitask-backlog-roadmap --show` (read-only). ONE confirmation for the whole proposal (the user may reorder or drop directions), then the writes: direction assignments (`upsert-context`), `direction-set`, `direction-rank`, each with `--expect-rev`; `STALE:` re-reads, never retries blind.
  - `>d <direction>`: re-summarize only that direction (the stale-refresh path the TUI will type); never touches the rank of the others.
  - The summary is written together with the digest read at that moment, so refresh can tell when it goes stale.
- **Uncovered directions**: when no trail covers a direction's tasks, offer to create one by running `/aitask-trail` (ad_hoc or multi_topic scope) on the user's yes — the same offer-only rule as the stale-trail refresh. Never create a trail unasked; never one per direction by default.
- **`>q`**: questions about directions ("what is blocking X", "what should I do next on Y", "which direction is behind") are answered from the record, its members' sources and the critical-path evidence, never from a remembered summary; a `stale` or `unknown` direction is called out before the answer. Logged to `qa.md` as today.
- **`>p`**: pick advice follows the confirmed direction order first (the next step of the top-ranked direction with an actionable task), then relates it to the backlog roadmap as today. Still never picks.
- **`>w`** keeps working, now documented as `>w <direction>` (parent decision 5: no "theme" left in the skill's text, codes or help); define its relation to `>d <direction>` (situation text is the long form, summary the short form) so the two never contradict.
- Greeting / Capabilities / `>?` list the new code; the "Requests from the sitrep TUI" section gains the request line child 5 will type, with its fresh-read check (a known direction).
- Guardrails section: recovery items are read, never written; the `crashed-agents` handling follows child 1's decision.

## Mechanics

- Regenerate goldens in the same commit; run `./.aitask-scripts/aitask_skill_verify.sh`; keep the entry template agent-invariant (Test 1b of `tests/test_skill_render_aitask_sitrep.sh`).
- `tests/test_sitrep_skill_contract.sh`: every command the skill documents exists in the real helpers; any new helper is on the five code-agent allow-lists.
- Read `aidocs/framework/skill_authoring_conventions.md` and `stub-skill-pattern.md` first. Codex / OpenCode: the skill renders for all agents; note in the plan whether the open port task for the sitrep operation needs anything for `>d`, and send it a note rather than widening this task.

## Docs

`aidocs/framework/sitrep.md` ("The skill"), `website/content/docs/skills/aitask-sitrep.md`, `website/content/docs/workflows/sitrep.md`; `check_links.py --build`.
