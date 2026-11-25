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

The store contract this child builds on is the "Directions" section of `aidocs/framework/sitrep.md`, landed by t2335_1 (the verbs, the baseline evidence, "Saving a proposal"). Where this text and that section differ, the section is right. t2335_1 also did the rename: the skill, its goldens and the docs already say "direction", and `>w <direction>` checks its direction with the `directions` verb.

- **`>d` — directions.**
  - Bare `>d`: read `list`, `directions`, every member context and the trail membership and critical-path evidence; propose the set of directions: which open items belong to which direction (reusing existing ones first, proposing a new slug only for items none fits), a title and summary per direction, linked trails, the `next` step, and ONE ranked order with a reason per position. Ranking evidence: task priority / effort, crash-recovery rank tiers, each trail's next wave and critical path, `/aitask-backlog-roadmap --show` (read-only). ONE confirmation for the whole proposal (the user may reorder or drop directions), then the save sequence below.
  - `>d <direction>`: re-summarize only that direction (the stale-refresh path the TUI will type); never touches the rank of the others.
  - **One read for summary and baseline.** When the proposal is drafted, child 2's digest read builds and retains the baseline snapshot of each proposed member set, and each summary is written from its snapshot. `direction-set --summary-file - --digest <digest>` saves both. A baseline is never taken again at write time: a task that closed during the confirmation would otherwise leave prose saying open under a baseline saying closed, and refresh would call it current.
  - **The save sequence** ("Saving a proposal" in the doc). Before the first write, run child 2's recheck over every direction in the proposal; a digest that differs means nothing is written, and the proposal is re-read, revised and confirmed again. Then, in this order: `direction-assign --batch` (every membership change in one all-or-nothing write, with each item's rev; never `upsert-context` for this, and never a `recover:` item), `direction-set` per direction (with the rev `direction-assign` printed for a block it touched), `direction-rank --expect-ranked <the full ranked order the user saw>`. A direction the user drops from the proposal loses only its proposed edits: no `direction-assign` line and no `direction-set` for it, so its saved record, summary and members stay. Its rank must stay as well, and `direction-rank` unranks every ranked direction its input does not name (a block holding only its rank is then deleted), so the rank input is always the COMPLETE order to save: every currently ranked direction in its place plus the newly ranked ones. Leave a ranked direction out of that input only when the user explicitly asked to unrank it. Show the user that full order in the confirmation, not only the directions the proposal edits. `direction-remove` deletes a saved record and leaves its items assigned, so run it only when the user explicitly asks to delete that direction, never as the meaning of an omission.
  - **A refusal stops the sequence.** `STALE:`, `EVIDENCE_CHANGED:` and `STALE_ORDER:` write nothing. Earlier writes of the same save stay and are valid by themselves (a direction with new members and its previous summary reads `unknown`, never `current`). Report which writes landed and which did not, quoting the result lines; re-read `directions`; revise only what is left; confirm; resume. Never retry blind and never roll back.
  - **Too large to summarise.** When the digest read reports a snapshot above the store's limit, say so. For an ordinary direction, offer a split. `crashed-agents` cannot be split (its members are derived and never reassigned): report that it keeps its rank and situation text and has no summary until its pending items shrink.
- **Uncovered directions**: when no trail covers a direction's tasks, offer to create one by running `/aitask-trail` (ad_hoc or multi_topic scope) on the user's yes — the same offer-only rule as the stale-trail refresh. Never create a trail unasked; never one per direction by default.
- **`>q`**: questions about directions ("what is blocking X", "what should I do next on Y", "which direction is behind") are answered from the record, its members' sources and the critical-path evidence, never from a remembered summary; a `stale` or `unknown` direction is called out before the answer. Logged to `qa.md` as today.
- **`>p`**: pick advice follows the confirmed direction order first (the next step of the top-ranked direction with an actionable task), then relates it to the backlog roadmap as today. Still never picks.
- **`>w`** keeps working as `>w <direction>` (the rename landed with t2335_1; grep the skill for a leftover "theme" anyway); define its relation to `>d <direction>` (situation text is the long form, summary the short form) so the two never contradict.
- Greeting / Capabilities / `>?` list the new code; the "Requests from the sitrep TUI" section gains the request line child 5 will type, with its fresh-read check (a known direction).
- Guardrails section: recovery items are read, never written; the `crashed-agents` handling follows child 1's decision.

## Mechanics

- Regenerate goldens in the same commit; run `./.aitask-scripts/aitask_skill_verify.sh`; keep the entry template agent-invariant (Test 1b of `tests/test_skill_render_aitask_sitrep.sh`).
- `tests/test_sitrep_skill_contract.sh`: every command the skill documents exists in the real helpers; any new helper is on the five code-agent allow-lists.
- Read `aidocs/framework/skill_authoring_conventions.md` and `stub-skill-pattern.md` first. Codex / OpenCode: the skill renders for all agents; note in the plan whether the open port task for the sitrep operation needs anything for `>d`, and send it a note rather than widening this task.

## Docs

`aidocs/framework/sitrep.md` ("The skill"), `website/content/docs/skills/aitask-sitrep.md`, `website/content/docs/workflows/sitrep.md`; `check_links.py --build`.
