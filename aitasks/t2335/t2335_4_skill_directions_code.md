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

- Add a **Work directions and implementation trails** section to the website’s sitrep workflow. Include a short side-by-side comparison of what each groups, how each is ordered, and when to use each. A direction groups sitrep items around a current line of work, with a user-confirmed rank and a suggested next step. A trail records a recommended landing order for tasks in waves, with dependencies and evidence.
- Explain how sitrep uses task IDs to link directions to existing trails. A direction can use several trails, and a trail can serve several directions. Show how opening a linked trail highlights the direction’s tasks and marks their unfinished predecessors while leaving the saved trail intact. Use a worked example where a task outside the direction needs to land first because it is in an earlier wave. Explain when sitrep offers to create a trail for an uncovered direction.
- Cross-link the comparison and `website/content/docs/concepts/implementation-trails.md`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2335_1** id=2026-11-25T09:40:37Z.7cd9c512172e33c598beb3f9 from=t2335_1 from_verified=yes at=2026-11-25T09:40:37Z base=95d0169d8b7b7b559161028acd85264c4061ad8d base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit 95d0169d8): t2335_1 landed the writer verbs >d will use. Your task text was updated to match; this is where to look and what is easy to miss.
> | - Contract: aidocs/framework/sitrep.md, "Directions", especially "Saving a proposal". Wire lines: header of .aitask-scripts/aitask_sitrep_todo.sh.
> | - The rename is done in the skill template, its goldens and the docs; `>w <direction>` checks its direction with the `directions` verb.
> | - direction-assign --batch prints DIRECTION:<slug>|updated|<rev> for a block it touched: use that rev for the following direction-set. An item's rev changes when it is assigned. It never moves a recover: item (KEPT:c<N>|recovery, nothing written) and refuses the reserved slug crashed-agents.
> | - direction-set --summary-file - --digest <16 hex>: the summary is ONE line on stdin; the digest must name a retained baseline whose member / trail / next lines match the store at that moment, else EVIDENCE_CHANGED:<slug>|<kind>|<key> and nothing is written.
> | - direction-rank replaces the whole order and takes --expect-ranked (the full order the user saw). Its input must be the COMPLETE order to save: a ranked direction left out is unranked, and a block that held only its rank is deleted.
> | - direction-remove deletes a saved record and leaves its items assigned: only on an explicit request.
> | - upsert-context now accepts --expect-rev.

> **✉ note:t2335_2** id=2026-11-25T17:24:35Z.e3cb0ebe13e1ee245f0fa64b from=t2335_2 from_verified=yes at=2026-11-25T17:24:35Z base=ec774ca92a8286795b5f00062c409f0cf299e2ef base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit ec774ca92): t2335_2 landed the refresh side of direction freshness and the two reads a proposal is saved with.
> | - Contract: aidocs/framework/sitrep.md, "The freshness verdict" and "Saving a proposal"; wire lines in the header of .aitask-scripts/aitask_sitrep_refresh.sh.
> | - Draft: `aitask_sitrep_refresh.sh snapshot`, stdin one line per direction `<slug>|<members>|<trails>|<next>` (`=` as stored, `-` none, or values: `c1,c2`; trail handles; a next key). It retains each baseline and prints `SNAPSHOT:<slug>|<digest>|baselines/<digest>.txt|<pending>|<unreadable count>`. Write the summary from that file.
> | - Before the first write: `aitask_sitrep_refresh.sh recheck`, the same lines plus `|<digest>`. Write only after exit 0. It fails when a digest moved, when a retained baseline no longer loads as ok (also with equal digests), and when the run was cut short (`RECHECK_FAILED:incomplete|<done> of <requested>`): a prefix of results is never a pass.
> | - `SNAPSHOT_UNREADABLE:<slug>|<kind>|<key>` names an input whose value is `unreadable`. The summary can still be saved; the direction then reads `unknown` until the input can be read.
> | - A proposed `next: c<N>` must name an existing item, and an unknown member id is refused: exit 2, nothing retained.
> | - `SNAPSHOT_TOO_LARGE:<slug>|<bytes>|<limit>`: nothing retained for that direction.
> | - The skill owes the code-agent permission touchpoints for aitask_sitrep_refresh.sh when it first calls it.
> | - The stamp `directions` prints now also covers the item a `next: c<N>` points at.
