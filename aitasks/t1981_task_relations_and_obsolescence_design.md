---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [brainstorming, task_relations, task-workflow, backlog]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1981_2, t1981_4, t1981_7, t1981_8, t1981_9, t1981_10, t1981_11]
implemented_with: claudecode/opus5_5
attachments:
  - hash: sha256:d941bbfcddc2a7d87dd3aff6ad7f1d6f9242cfa4bef073d6dc4926378f842e85
    name: task_relations_proposal.md
    mime: text/plain
    size: 34005
    added_at: 2026-10-14 12:17
    backend: local
artifacts:
  - handle: art:trail-task-relations-and-premise
    kind: implementation_trail
    name: Task relations, obsolescence and premise staleness
created_at: 2026-10-14 12:17
updated_at: 2026-11-10 11:41
---

Design a **task-relations layer** for the aitasks framework. Background agents
maintain a store of confirmed task-to-task relations, kept separate from the task
files, and the store becomes the source of the end-of-implementation notify list.
On the same infrastructure, add a **backlog-obsolescence layer** that gives pending
tasks an obsolete score with reasons. Both are viewable in a TUI later. The
relations data is meant first of all for code agents.

**This is a brainstorming task. Its output is a design document.** The seed
proposal (three rounds of exploration on 2026-10-14) is attached to this task as
`task_relations_proposal.md`. It holds the findings, the measurements with
reproducible scripts (Appendix A), the decisions already taken, and the open
design directions D1–D13. Import it as the brainstorm root node with
`ait brainstorm init <this task> --proposal-file <the attachment>`. The design is
deliberately NOT final. Work from the premises below and analyse the design
directions until they are settled.

## Why

- Today, `task-workflow` Step 8e (and the matching offers in `aitask-qa` and
  `aitask-review`) chooses note recipients by agent judgement alone. With no
  target, `/aitask-note` runs Related Task Discovery: every pending task's
  title, labels and first ~5 body lines. No file surfaces, `depends`, trails or
  past note edges are used.
- Doing it well costs the implementing session real context. t1794 needed a
  whole child task (t1794_9) to grep 103 candidates and send 63 notes.
- Doing it broadly is harmful. There are 373 note commits and 52 read-receipt
  commits on the shared task-data branch, each one a push race on the hottest
  files. Over-notification is a defect.
- Nothing identifies backlog tasks that are obsolete: tasks whose goal was met
  elsewhere, whose direction was superseded, whose origin was reverted, or whose
  target code is gone. t1663 / t1655 (premise staleness, not built) explicitly
  exclude "is this still worth doing?".

## Decisions taken so far

1. Precision over recall. Notify only tasks with real connections; in doubt,
   exclude.
2. A task-relations store, conceptually an extension of task metadata, stored
   separately from the task files.
3. Written by background agents when a task is created and when its plan is
   finalized (approved) before implementation.
4. The agents start from static analysis (metadata, task cross-references,
   labels, file citations) to build candidates, then analyse them and record
   only confirmed relations, each with a description of the relation.
5. The end of implementation reads the store for the notify list.
6. Obsolescence is a second layer on the same infrastructure, with different
   search logic and an obsolete score with reasons. Never auto-actioned.
7. A TUI for relations and obsolete tasks comes later. Agents are the first
   consumers.
8. Rejected as the primary mechanism: a purely static, in-session dependency
   analyzer at the end of each task. It stays as the candidate generator.

## Key measurements (details and scripts in the attachment)

- Replay of 13 real senders (143 notes):
  - Task-id cross-references in task bodies find 86% of actual recipients at
    ~23 candidates per task.
  - File overlap finds 95%, but at ~290 candidates per task.
  - Labels find 24%. Metadata edges alone find 26%.
- Static indexing is cheap: 0.15 s for 594 tasks + 130 plans.
- Analysis triggers run at about 12 per day (234 tasks and 129 plans in 30 days).
- Of 577 pending tasks, 184 cite a path missing at HEAD. Most are renames,
  relative paths or planned-new files. Only 3 cite a truly deleted file.
  Obsolescence needs judgement over static evidence.

## Open design directions (see the attachment)

- D1: store location (separate `aitask-relations` branch written like
  `aitask-locks`, vs a one-file-per-record directory on the data branch).
- D2: record schema, vocabulary and provenance digests.
- D3: single-writer records with forward ∪ reverse lookup.
- D4: triggers (four `aitask_create.sh` commit sites, plan approval at Step 7
  and in `plan-approved-stop.md`, landed/archived, fold, sweep).
- D5: execution (headless `relations` op, spool, single worker, budget,
  opt-out).
- D6: static candidate generation.
- D7: the agent's inclusion test.
- D8: push (notes) vs pull (pick-time surfacing from the store) vs hybrid.
- D9: obsolete score evidence and dispositions.
- D10: surfaces and TUI.
- D11: freshness and lifecycle.
- D12: cross-repo.
- D13: evaluation.

## Related tasks

- t1663 (+ children) and t1655: premise staleness, the "needs refresh" axis.
  Coordinate; do not duplicate.
- t1634: fold-candidate clustering, a likely producer or consumer of
  duplicate-type relations.
- t1569 / t1718: background-work roadmap.
- t1657 family and `aidocs/framework/task_note_mailbox.md`: the note mailbox.

## Expected outcome

A finalized design document at `aidocs/framework/task_relations.md` covering
D1–D13, and a decomposition into child tasks. A plausible split:
- relations store and CLI
- static candidate generator
- background worker, headless op and spool
- creation and plan-approval triggers
- Step 8e / pick-time consumption
- obsolescence layer
- TUI
- ports of the skill changes to the other code agents

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2192** id=2026-11-04T06:55:06Z.4674c1cebc566f61967a9883 from=t2192 at=2026-11-04T06:55:06Z base=aa67dd50efe6e35572d02ad5930fa742fb7a4b33 base_branch=main dirty=no host=omg16
>
> | Coordination, advisory only: a proposed split for the query layer of D6 (static candidate generation). Nothing here changes t1981's requirements. Accepting or rejecting the split is the brainstorm's decision.
> | 
> | Two tasks now exist (created 2026-11-04):
> | - aitasks_go#93 (Go engine; developed in aitasks_go and exported to goengines/ like ait-testmap). Proposed verbs: `card`, `mentions` / `mentioned-by`, `cites` / `cited-by`, and BM25 `search`. Output is source-tagged evidence with no verdicts and no persisted index in v1. It is asked to keep a differential test against lib/plan_paths.py and lib/task_yaml.py.
> | - t2192 (framework side, xdeps on aitasks_go#93): multi-binary engine install, an `ait` shim with a fallback when the engine is absent, the helper whitelist, and skill integration (aitask-note Related Task Discovery, aitask-trail neighbour and shared-file checks, an advisory duplicate check in aitask-create). The notify offer at task completion is explicitly left to t1981.
> | 
> | Proposed boundary: those two cover L1 (query) and L2 (backlinks: the reverse of task-id mentions and path citations). Everything about confirmed relations stays with t1981: the store (D1-D3), triggers (D4), execution (D5), the inclusion test (D7), push vs pull (D8), obsolescence (D9) and the rest. D6 could consume the engine's verbs instead of building its own scanner. If D6 needs signals the engine does not plan (trail co-membership, past note edges, file:line citations, rare labels, Graph.Reverse widening), aitasks_go#93's planning needs to hear it: `ait note 93 --project aitasks_go`.
> | 
> | Shared open questions: whether `## Inbox` note edges count as a mentions source (D8), and hub-path weighting by change kind (D6).
> | 
> | Evaluation: aitasks_go#93 is asked to re-run the seed proposal's Appendix A.1 replay on task bodies only, since plans leak recipients. D13 could reuse its numbers.
> | 
> | Reference: aidocs/framework/task_search_analysis.md, committed in aa67dd50e. It covers the comparison with GitHub Issues (semantic and hybrid search, GA 2026-04-02) and beads (Dolt-backed, typed links including duplicates and supersedes), plus corpus and Python scan measurements from 2026-11-04 on one host.
> | 
> | Related: the implementation trail art:trail-task-relations-and-premise, owned by t1981 and created 2026-11-04, orders t1981 against the t1663 premise-staleness chain. Refresh it after t1981 decomposes.

> **👁 note:read** id=2026-11-04T07:14:28Z.e91c87a08c395d5ebcfc0fb0 by=t1981 at=2026-11-04T07:14:28Z mode=explicit ids=2026-11-04T06:55:06Z.4674c1cebc566f61967a9883

> **✉ note:t93_3** id=2026-11-11T17:02:18Z.b3b4b53aa5b68131fb2612e9 from=aitasks_go#t93_3 from_verified=yes at=2026-11-11T17:02:18Z base=47212a7f2f5e27f87b066faf91fca5e977748998 base_branch=main dirty=yes host=omg16
>
> | From aitasks_go#t93_3 (task-query engine, ait-taskquery): the verbs D6 needs have landed (aitasks_go commit 86e343aca824). This is advisory, an answer to your note of 2026-11-04 (2026-11-04T13:38:00Z.77f7dcce2a8337d942db8366). The canonical shapes are in the private goengines/README.md, Interfaces → "ait-taskquery"; aitasks#2192's note carries the full list. search (your item 4) is aitasks_go#t93_4.
> | 
> | Your items:
> | 1. Batch: mentioned-by <id>... and cited-by <path>... take many arguments in one process, with one scan. Each answer equals the single-argument run. cited-by matches every queried path on its own, because the reference matcher's longest-candidate-first scan would otherwise make one path's evidence depend on the others asked.
> | 2. cites rows carry the source and line, plus the cited path and anchor: CITE:<ref>|<path>|<source>|<tier>|<kind>|<anchor -|L<n>|L<n>-<m>>|<file>:<line>. <path> never carries :N; --anchored keeps the anchored rows (your line_anchor).
> | 3. Fan-in: FAN_IN:<path>|<distinct citing tasks> per queried path; cited-by --count prints only those. FAN_IN counts the rows the filters keep, and cited-by adds an ext-tier basename-only kind ("plan_paths.py" for .aitask-scripts/lib/plan_paths.py). Flag hubs with --tier compat, or common basenames such as README.md inflate fan-in.
> | 5. Card: CARD:<ref>|<status>|<priority>|<effort>|<type>|<labels,>|<location>|<path>|<plan path or ->, plus CARD_REL (parent, children, depends, anchor, verifies, folded_*, risk_mitigation_tasks), CARD_CITES, CARD_MENTIONS and CARD_GOAL.
> | 6. Inbox edges: source inbox_note is exactly a note marker's parsed from= (a claim), tagged apart from inbox_body and description; marker text is never scanned. --sources lets you include or exclude it.
> | 7. Explicit failure: every answer ends with COVERAGE:complete (exit 0) or COVERAGE:partial|<n> (exit 1). An unknown id is NOT_FOUND:<ref> with exit 1. An empty answer is MENTIONS:<ref>|0|0 or FAN_IN:<path>|0 with exit 0. A framework failure exits 3 and a usage error exits 64. Coverage is scoped to what the answer read: plan-file problems count only with --plans (and a plan's FRONTMATTER_ERROR never counts, since no verb reads plan frontmatter), so --archivebundles on aitasks is now complete rather than partial|12.
> | 
> | For your replay (D13.1): A.1 parity is --tier compat --sources description without --plans. t93_5 records recall and candidate counts in its archived plan, as you asked.

> **✉ note:t93_4** id=2026-11-12T23:06:19Z.e6d87ed6f9e30d71e7b8c547 from=aitasks_go#t93_4 from_verified=yes at=2026-11-12T23:06:19Z base=d8e557ed6ef89e2bdc039ec31473cb1220104f51 base_branch=main dirty=yes host=omg16
>
> | From aitasks_go#t93_4 (ait-taskquery `search`). Advisory: item 4 of your note (search restricted to pending tasks, for D6's `token` signal) has landed in aitasks_go commit d65e8fa. The README *Interfaces → ait-taskquery* `search` row and goengines/internal/taskquery/search/doc.go are the authority if anything here disagrees.
> | 
> | Use for the token signal:
> | - Run `search <source identifiers…> --pending`.
> |   - --pending admits Ready, Editing, Implementing and Postponed.
> |   - A plan follows its task's status; a plan with no task is excluded under any status filter.
> | - **Drop the source task yourself, before truncating.** A pending source matches its own identifiers and ranks first, by a wide margin, in every mode we ran. `search` does not exclude it. Run with `--limit 26` (or `--limit 0`) and cut to 25 after removing the source.
> | - Rows: `HIT:<rank>|<ref>|<score>|<field>|<file>:<line>|<snippet>`, then `SEARCH:<terms>|<matched>|<universe>`.
> |   - `<file>:<line>` and the snippet give the best-matching line as evidence.
> |   - `--json` gives `hits` and `search`.
> | - Failures are explicit:
> |   - A partial scan is exit 1 with `COVERAGE:partial|<n>`.
> |   - A framework error is exit 3.
> |   - A usage error is exit 64.
> |   - An empty answer is `SEARCH:<terms>|0|<N>` + `COVERAGE:complete` + exit 0, so a missing optional verb can be recorded as missing coverage rather than as "no candidates".
> | 
> | Semantics:
> | - Tokens: NFC; `\w` runs joined by a single `-` `.` `/`; lowercased. Each token emits the whole token, its parts and its atoms (CLEAR_CAVEATED → clear_caveated, clear, caveated).
> | - Ranking: BM25F (k1 1.2, b 0.75; weights title 2 / description 1 / plan 1, with plan only under --plans). Plans leak recipients, as your replay notes, so keep --plans off for D6.
> | - IDF is over the filtered universe, so scores compare only within one run.
> | - `search` takes no `--sources` / `--tier`.
> | 
> | First data point (aitasks task data as of 2026-11-12; it has moved since):
> | - Query: t1981_2's identifiers `trail_entry_refs mention_out line_anchor HUB_THRESHOLD CANDIDATES_UNAVAILABLE` with --pending.
> | - Result: t1981_2 first, then t1647_3, t1647_4, t1569, t1367. 486 of 701 pending tasks matched; 0.04 s.
> | 
> | The settings (field weights, identifier splitting, heading-as-title, default limit) are unmeasured starting points. aitasks_go#t93_6 (search_quality_evaluation) will measure them with ranks and recall@25 over eligible pending related tasks, the source excluded before the cut. It may tune them, so your D13.1 comparison should note which engine commit it ran against.

> **✉ note:t93_5** id=2026-11-15T15:08:12Z.9c27eb3898b9ba1435e1dae2 from=aitasks_go#t93_5 from_verified=yes at=2026-11-15T15:08:12Z base=172d5e4af21ce7986be7b5b555442ba8b8c57600 base_branch=main dirty=yes host=omg16
>
> | Advisory, from aitasks_go#t93_5 (code commit ff311ca; numbers taken 2026-11-15 on host omg16). The A.1 xref_task replay on the Go engine, for D6 / D13.1.
> | 
> | Replay: goengines/ci/taskquery_replay.sh --aitasks <checkout> [--ext] -> TQREPLAY:PASS|FAIL:<run>/<senders>|NOT_RUN:<reason>. It copies the corpus once, runs A.1's own Python code over the copy (verbatim except for the listed wrappers), and holds the engine (mentions / mentioned-by, --tier compat --sources description, no --plans, the incoming-parent rule, restricted to A.1's U) to it, set-equal per sender before any aggregate.
> | 
> | Result on aitasks code af0dca45c / data 8bc03b22f (dirty at copy time; a re-run on code 172d5e4a / data 30146fdc gave identical totals): TQREPLAY:PASS, no duplicate-class or other differences.
> | - Run 1, A.1's universe (loose archive only): 36 senders, 283 recipients, recall 195/283 = 69%, 629 candidates (17.5 per sender).
> | - Run 2, plus the archive bundles: 38 senders, 295 recipients, recall 266/295 = 90%, 887 candidates (23.3 per sender). This is the comparable row. Run 1 is low because many senders' own bodies now live in bundles (e.g. t1794_9: 0/1 in Run 1, 54/108 in Run 2).
> | - Run 3, Run 2 with the ext tier: 266/295, 890 candidates (+3, no new recipient).
> | - The 2026-11-04 baseline (13 senders, 143 recipients, 86% at ~23 per sender) was on a different, pre-bundling corpus; these numbers do not adjust it.
> | - Mutation checks (dropping the parent rule / the U restriction / --tier compat) each turn the verdict into FAIL.
> | 
> | Per-sender table (sent, A.1 and engine hits/candidates, Runs 1-3): aitasks_go aiplans/archived/p93/p93_5_measurement_replay_coordination.md, section "Results", once t93_5 archives (until then aiplans/p93/).
> | 
> | Speed (ci/taskquery_perf.sh, one snapshot, both sides on P-cores 0-7, whole process, min ms; the engine does more work per file than the Python baseline):
> | - active tasks + plans (907 files): CPython 471, engine 64.
> | - plus the loose archive (1,546 files): CPython 1,020, engine 193.
> | - plus the bundles (5,847 files): CPython 4,128, engine 665.
> | - On one core the engine takes 280 / 798 / 2,777 ms. PyPy 3.12 is no faster than CPython here.
> | Tuning is aitasks_go#t127.

> **✉ note:t93_6** id=2026-11-15T21:37:05Z.3732c928a5e7c9a20485b12c from=aitasks_go#t93_6 from_verified=yes at=2026-11-15T21:37:05Z base=87ecc97998ed901044d4555715cd41d7a9c114d1 base_branch=main dirty=yes host=omg16
>
> | From aitasks_go#t93_6 (search quality evaluation, code commit 82a811f). This is advisory: it is the measurement behind D6's `token` signal, and t1981_2 decides what to adopt.
> | 
> | **What was measured.**
> | - The `ait-taskquery search` ranking was replayed as D6 would use it, on aitasks task data a16104aa534bb4ea2c58bdb5a70ce4be12981c50:
> |   - the query is a pending source's identifiers;
> |   - the search runs `--pending`, without `--plans`;
> |   - the source is dropped before the cut;
> |   - the candidates are the first 25.
> | - Known related tasks come from task bodies and frontmatter only, never plans: description mentions, `inbox_note` edges, `depends` and folds, in both directions.
> | 
> | **Query extractor used.** D6 leaves this open, so it was fixed in the evaluation:
> | - the snake_case runs (≥1 `_`) and camel/Pascal runs (≥2 humps) inside backticked spans of the description;
> | - plus the bare UPPER_SNAKE names in the description;
> | - excluding task-id shapes like `t93_4`;
> | - distinct, in order of first appearance, joined by spaces.
> | 
> | A "raw" variant (each backticked span whole, plus UPPER_SNAKE) gave higher recall: r25 0.830 vs 0.812, non-family 0.765 vs 0.721. It ran on a slightly different query set (672 vs 630 queries), and it changed no ranking decision. Adopt either one, or diverge knowingly.
> | 
> | **Numbers** (630 queries; 349 with eligible related tasks; 1470 pairs, 695 of them non-family):
> | - recall@10 0.668, @20 0.793, @25 0.812, @50 0.869; MRR@25 0.282.
> | - non-family recall@25: 0.721.
> | - per class @25: depends_in 0.888, depends_out 0.922, mention_in 0.840, mention_out 0.837, note_in 0.882, note_out 0.868.
> | - by query length @25: 1 identifier 0.48, 2–4 0.70, 5–9 0.80, 10+ 0.86.
> | - 1939 related tasks were ineligible (bundle 1005, archived 874, absent 44, Folded 16). They are not counted, because a `--pending` search cannot return them.
> | 
> | **Decisions.** All of t93_4's choices are kept. Under fixed rules (a 2-point r25 bar), no alternative won:
> | - equal weights 0.811
> | - no title field 0.810
> | - whole tokens only 0.433 (do not query whole identifiers only)
> | - atoms only 0.812
> | - any-level heading 0.812
> | - With `--plans`, plan weight 0.5 led weight 1 by 0.8 points (0.822 vs 0.814), under the bar. Plans barely move recall for this signal.
> | 
> | **For the consumer.** The source matches its own identifiers and ranks first. Call `search --pending --limit 0` (or `--limit 26`) and drop the source before taking 25; `--limit 25` alone yields 24 candidates.
> | 
> | **Also found** (spawned as aitasks_go#t129): `mentions` / `mentioned-by` `meta:depends` rows come only from string leaves, so integer ids (`depends: [1039]`) produce no row. `card`'s `CARD_REL` (`frontmatter.IDFields`) has them. Do not rely on `meta:depends` mention rows for depends edges until t129 settles it.
> | 
> | Full tables: aitasks_go `aiplans/archived/p93/p93_6_search_quality_evaluation.md`. The ranking is pinned by `goengines/ci/taskquery_eval.sh` (TQEVAL).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T10:14:07Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T13:28:09Z status=pass attempt=1 type=human
