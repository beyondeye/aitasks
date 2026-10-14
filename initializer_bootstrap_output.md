--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: "Seed proposal for a task-relations store and backlog-obsolescence layer built by background agents (t1981)"
proposal_file: br_proposals/n000_init.md
created_at: "2026-10-14 09:45"
created_by_group: bootstrap
reference_files:
  - aiwork/t1981_task_relations_proposal.md
  - aitasks/t1981_task_relations_and_obsolescence_design.md
  - aidocs/framework/task_premise_staleness.md
  - aidocs/framework/task_note_mailbox.md
  - aidocs/framework/manual_verification_staleness.md
  - aidocs/framework/aitasks_extension_points.md
requirements_precision_over_recall: "Notify list holds only tasks with real connections; in doubt, exclude; over-notification is a defect"
requirements_separate_store: "Task relations are stored separately from task files, never in frontmatter or body"
requirements_background_writers: "Relations are written by background agents at task creation and at plan approval, not by the implementing session"
requirements_static_first: "Background agents start from static candidate generation, then record only confirmed relations with a description"
requirements_consume_at_end: "End of implementation reads the store to get the notify list instead of in-session discovery"
requirements_obsolescence_layer: "Backlog obsolescence is a second layer on the same infrastructure with an obsolete score and reasons"
requirements_agent_first_surface: "Relations data is first for code agents; a TUI for relations and obsolete tasks comes later"
requirements_advisory_only: "A relation or score never changes task status or requirements and is never auto-actioned"
requirements_provenance: "Derived records carry content-hash provenance of every consumed input"
requirements_shared_optout: "New write paths honour a shared opt-out and have bounded recovery"
requirements_automation_first: "No human review step as a precondition for the layer to operate"
assumption_note_cost_is_selection: "Writing notes is cheap; the cost is selecting recipients and composing, which should move out of the implementing session"
assumption_static_signals_cheap: "Static analysis is effectively free (0.15 s path index, 2.7 s rename/delete history pass) and needs no background job to be fast"
assumption_xref_best_signal: "Task-id cross-references in task bodies are the best static signal (86% recall, ~41% precision); file overlap has 95% recall but ~4% precision"
assumption_hub_paths_depend_on_change_kind: "Hub paths carry real signal in refactors, so down-weighting must depend on the kind of change"
assumption_static_signals_leave_semantic_residue: "Some real relations (in-flight uncommitted work, vocabulary contract consumers) are unreachable by static signals"
assumption_obsolete_needs_judgement: "Static signals give cheap needs-refresh evidence; obsolete is a judgement needing an agent fed with that evidence"
assumption_file_churn_is_noise: "Missing or churned cited paths are mostly renames or relative paths, not obsolescence (3 of 577 pending tasks cite a truly deleted path)"
assumption_creation_rate: "About 8 task creations and 4 plan finalizations per day, roughly 12 analysis triggers per day"
assumption_token_budget: "About 25 candidates at ~1k tokens each gives ~30-50k input tokens per analysis, ~0.4-0.6M tokens per day"
assumption_precision_is_lower_bound: "Measured precision is a lower bound, since unnotified candidates may be genuinely related; corpus is live and bodies are read post hoc"
assumption_single_writer_reverse_lookup: "Each task's record holds only edges found when it was analysed; query is forward union reverse over about 600 small files"
assumption_plan_approval_second_moment: "Plan approval is the right second analysis moment (open: digest-driven re-run on plan change)"
component_relations_store: "Separate store of per-task relation records (lean: orphan branch aitask-relations written like aitask-locks)"
component_candidate_generator: "Static candidate generator: cross-refs, metadata edges, trails, note edges, non-hub file overlap, file:line citations, rare labels; capped near 25 with source-tagged evidence"
component_background_worker: "Headless relations operation in aitask_codeagent.sh plus local spool drained by one lock-guarded worker"
component_triggers: "Create hook in aitask_create.sh, plan-approved hook at Step 7 and plan-approved-stop, landed/archived hook, fold handling, periodic sweep"
component_relation_analysis: "Agent-side inclusion test with two-stage reading, description for the recipient agent and checkable basis"
component_consumption: "Step 8e push, pick-time pull, or hybrid reading forward union reverse relations"
component_obsolescence_layer: "Same store and worker with a different operation producing an obsolete score band, reasons and recommended disposition"
component_surfaces: "Agent-facing context, ait relations / ait obsolete CLI, later TUI and board field"
component_evaluation: "Replay harness extended to score the full pipeline and notify-list reduction"
tradeoff_store_location: "Orphan branch (conflict-free, network on every write, retry contention) vs data-branch directory (rides sync, needs resolver and commit-wrapper changes) vs local cache (not shared)"
tradeoff_push_vs_pull: "Push notes (precise but writes to other tasks, commit traffic, receipts) vs pull at pick time (zero writes, arrives when needed) vs hybrid"
tradeoff_eager_vs_lazy_refresh: "Eager re-analysis on digest change vs lazy on read"
tradeoff_precision_vs_recall: "File overlap gives high recall but low precision; cross-refs give better precision; the design chooses precision"
tradeoff_background_cost: "Per-trigger LLM cost and print-mode billing vs removing selection cost from the implementing session"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
# Task relations and backlog obsolescence — seed proposal

**Status:** seed for a brainstorm (`ait brainstorm`). NOT a final design. It
records three rounds of exploration (2026-10-14), the decisions the user has
already taken, and the design directions the brainstorm must analyse and
settle. The brainstorm's output is a finalized design document plus a
decomposition into child tasks.

**Evidence dating.** Every measurement below was taken against code `main` at
`8718afa08` and the task-data branch as of 2026-10-14. Counts over task bodies
read the bodies *as they are today*, not as they were when the notes were sent
(see the caveats in §2.3). The measurement scripts are reproduced verbatim in
Appendix A so the brainstorm can re-run them.
<!-- /section: overview -->

<!-- section: problem [dimensions: requirements_*] -->
## 1. Problem

At the end of a task's implementation, `task-workflow` Step 8e (and the
matching offers in `aitask-qa` and `aitask-review`) asks the agent to *offer*
an `ait note` to existing tasks the work affects — a stale assumption, a wider
blast radius, a design decision that changes their approach. Two problems:

1. **Who gets notified is pure agent judgement, with no structured input.**
   Step 8e is prose: "if the work surfaced context an existing task needs…
   offer". When `/aitask-note` is given no target, it runs the Related Task
   Discovery Procedure (`task-workflow/related-task-discovery.md`): list every
   pending task, read each title + labels + the first ~5 body lines, and let
   the model judge. File surfaces, `depends`, `anchor`, `verifies`, trails and
   past note edges are not consulted.
2. **Doing it well is expensive, and doing it broadly is harmful.**
   - Cost lands inside the implementing session: reading candidates and
     composing per-target notes. The extreme case, t1794 (board mono-file
     split), needed a dedicated child task (t1794_9) that grepped 103
     candidate files, triaged them by hand and sent 63 notes.
   - Every note is a commit + push race on the task-data branch, on exactly the
     files other sessions edit; every acknowledgement is another commit (a read
     receipt). Notifying too many tasks multiplies git sync traffic and
     conflict exposure. **The user regards over-notification as a defect, not a
     safe default.**

A second, related gap: **nothing identifies backlog tasks that are obsolete** —
not tasks that need a note, but tasks whose design direction or target code no
longer exists or no longer matters.
<!-- /section: problem -->

<!-- section: findings [dimensions: assumption_*, component_*] -->
## 2. Findings

### 2.1 Note traffic today

| measure | value |
|---|---|
| notes present in task files (active + archived) | 322 |
| distinct sending tasks | 117 (~2.75 notes per sender) |
| notes by month | 225 in 2026-09, 97 in 2026-10-01..14 |
| `ait: Record note` commits on the data branch | 373 |
| read-receipt commits | 52 |
| active task files with a `## Inbox` | 143–188 (depending on scan root) |
| largest single sender | t1794_9: 63 notes |

Writing is not the bottleneck: t1794_9's 63 notes were written in 2 min 41 s,
t1893_1's 13 in 30 s, t1853_2's 8 in 42 s. **The cost is selecting and
composing**, which today happens in the implementing session's context.

How t1794_9 chose recipients (`aiplans/archived/p1794/p1794_9_*.md`): grep for
the changed path across pending task + plan files (93 matches at planning, 103
at implementation), drop tasks already notified by sibling children, drop tasks
already written against the new layout, send one shared body plus a per-target
"your stale citations" line. That is a static candidate generator followed by
a manual precision pass — the shape this proposal automates.

### 2.2 Sync behaviour of notes

- `board/aitask_merge.py` already unions `## Inbox` blocks across PCs
  (identity `(id,)`, order `(at, id)`), so two-sided Inbox appends usually
  AUTOMERGE, and a one-sided append next to a status change does not conflict
  at all (the note writer touches no frontmatter).
- Remaining breakage: prose edited next to the Inbox (PARTIAL), hand edits
  inside `## Inbox` (whole-body fallback), `aitask_update.sh --desc-file`
  silently dropping the Inbox (`aidocs/framework/task_note_mailbox.md`, "Known
  constraints").
- The real cost is **volume**: one commit and one push race per note and per
  receipt, on the hottest files of the shared branch.

### 2.3 Static candidate signals — replay against real senders

Ground truth: the 13 senders with ≥4 notes (143 notes). For each sender, every
other task (active + archived) was tested against a signal; *recall* = share
of the actual recipients the signal finds; *candidates* = total tasks the
signal returns; *precision* = recall hits / candidates.

| signal | recall | candidates (13 senders) | precision |
|---|---|---|---|
| file overlap, sender's declared surface (task + plan), exact or basename | 136/143 = 95% | 3786 | ~4% |
| file overlap, landed change set (first replay) | 134/143 = 94% | 13–412 per sender | — |
| file overlap, hub paths (fan-in ≥10 tasks) removed | 62/143 = 43% | 406 | ~15% |
| **task-id cross-references, both directions, task bodies only** | **123/143 = 86%** | **302 (~23/sender)** | **~41%** |
| cross-ref: recipient body names sender (or sender's parent) | 68/143 = 48% | 202 | ~34% |
| cross-ref: sender body names recipient | 84/143 = 59% | 153 | ~55% |
| cross-refs including plans | 138/143 = 97% | 360 | ~38% (contaminated, see below) |
| recipient cites `file:line` in a sender-surface file | 41/143 = 29% | 718 | ~6% |
| shared rare label (label used by <40 tasks) | 35/143 = 24% | 355 | ~10% |
| metadata edges (`depends` / `anchor` / `verifies` / siblings) | 37/143 = 26% | — | — |
| metadata edges *added* on top of file overlap | +3 | — | — |

Caveats the brainstorm must carry:

- **Live corpus.** Concurrent sessions create tasks while this runs; two runs
  an hour apart differed by 1–8 in candidate counts (recall was identical).
  The figures above are from the later run (Appendix A.1 as printed).

- **Precision is a lower bound.** "Notified" is not "all real connections";
  some unnotified candidates were genuinely related.
- **Post-hoc bodies.** Bodies are read today; a recipient edited after reading
  a note to cite the new paths inflates file-overlap recall.
- **Plan contamination.** A sender's archived plan is written *after* it sends
  notes and often lists its recipients (p1794_9 does), so cross-refs that read
  plans leak the answer. The 86% figure reads task bodies only.
- **Hub paths carry real signal in refactors.** Removing hub paths (e.g.
  `CLAUDE.md` fan-in 62, `tests/run_all_python_tests.sh` 55,
  `.aitask-scripts/board/aitask_board.py` 47) kills the t1794_9 case, whose
  whole point *was* a hub file. Down-weighting must depend on the kind of
  change (split/rename/contract change vs ordinary edit).
- **Extractor gaps.** `lib/plan_paths.py` extracts only
  `sh|py|md|yaml|yml|json|toml`, so `.go`, `.kt`, `.ts` citations are
  invisible; bare basenames (`aitask_board.py`) and paths relative to
  `.aitask-scripts/` (`lib/stats_data.py`) need suffix resolution.

Misses worth naming (the semantic residue static signals cannot reach):

- t1852_2 → t1869: a review finding about **another task's uncommitted
  in-flight work** (`aitask_project_resolve.sh`), routed to its owner.
- t1688_2 → t1470: a consumer of a **verdict vocabulary contract**
  (`CLEAR_CAVEATED`, `task_declared`) with no file path in common.

### 2.4 Cost envelope

- Full path index over 594 active tasks + 130 active plans (4.2 MB): **0.15 s**.
  One whole-history rename/delete pass (`git log --all -M --diff-filter=DR`):
  **2.7 s**. Static analysis is effectively free; it does not need a
  background job to be fast.
- Task creation rate: **234 tasks / 30 days** (52 of them child-task creates),
  **129 plans / 30 days** — roughly 8 creations + 4 plan finalizations a day,
  ~12 analysis triggers/day.
- Task body size: median 3.5 KB, p90 8.6 KB (~0.9k / ~2.2k tokens).
- At ~25 candidates × ~1k tokens per candidate excerpt, one LLM analysis is
  ~30–50k input tokens; ~0.4–0.6M tokens/day at current rates, before any
  landed-time re-scoring.

### 2.5 Reusable infrastructure

| piece | what it gives | limits |
|---|---|---|
| `lib/plan_paths.py` (`extract`, `classify`, `task_body_text`, `find_references`, `find_suffix_references`) | path tokens from task/plan text; tracked / planned_new / phantom classes; heading-aware reference search | extension allowlist; bare new top-level names classify phantom |
| `lib/parallel_admission*.py` | overlap semantics: `specific` / `hub` (≥10 tasks) / `declared`; `OVERLAP:` rows naming counterparties and shared files | compares only against **in-flight** tasks; no persistent cache; ~2.5 s/check dominated by a full `git log --all --name-only` |
| `aitask_revert_analyze.sh --batch-map` (`lib/task_file_sets.py`) | whole-corpus task → landed files map in one git pass (`TASKFILES:`, `COMMIT:`, `TRACKED:`, `STATUS:`) | `--no-renames` by design |
| `lib/dep_resolution.py`, `lib/followup_origin.py` (`canonical_dep_id`, `resolve_detailed`) | `depends` resolution; exact (`verifies`) / topic (`anchor`) origins | no reverse-dependents CLI; never inspects the origin's state |
| implementation trails (`lib/implementation_trail.schema.json`, `lib/trail_gather.py`, `lib/trail_links.py export`) | `relations[]` with `hard_depends / advisory_precedes / coordinates_with / verifies / informs`; `observations[]` incl. `stale_premise`, `shared_surface_collision`; `new_related_task` drift reason | only tasks inside a stored trail; files appear in free text only; no "trails containing task X" CLI |
| note inbox (`lib/note_inbox.py`) | durable sender → recipient edges (`from=`), with `base` SHA | no verb lists all notes with senders |
| `goengines/internal/testmap/deps` `Graph.Reverse` / `Closure` | static import graph (bash, Python, Go, Kotlin, Java, Gradle): changed file → dependent files | no CLI; no task mapping |
| `aitask_lock.sh` on the `aitask-locks` orphan branch | conflict-free per-task records: plumbing (`hash-object`/`mktree`/`commit-tree`) + push-as-CAS, retries | network on every write; single ref → retry contention; invisible to `ait sync` / board / archival |
| `aitask_codeagent.sh` `explore-relay` op | template for a headless op: `claude --print`, restricted `--allowedTools`, env timeouts, model from `codeagent_config.json` | Claude Code only; print mode bills at a higher per-token rate (`aitask_codeagent.sh:548-551`) |
| agentcrew runner (`agentcrew_runner.py`, `start_runner`) | the only existing enqueue-and-drain mechanism; detached start | every enqueue commits + pushes the crew branch — heavy per trigger |

### 2.6 Trigger points

- **Task created.** Every committed task goes through `aitask_create.sh`. No
  post-create hook exists. Four commit sites (`finalize_draft` child/parent,
  `run_batch_mode --commit` child/parent) are each followed by
  `run_auto_merge_if_needed`; a single silent, detached
  `_notify_task_created <id> <file>` after auto-merge and after the child lock
  is released covers all creators (skills, follow-up wrappers, issue/PR
  import, chatlink, brainstorm, board).
  Timing hazards: planning creates children one at a time *before* child plans
  exist (debounce per parent); the manual-verification wrapper and archive
  carry-over seed the body in a *later* commit; risk-mitigation "before"
  creation rewrites the origin's `depends:` afterwards. With `--silent`,
  stdout must stay a single path line.
- **Plan finalized.** Externalization is *not* approval (the Checkpoint's
  "Revise plan" loop re-externalizes). Approval is the Checkpoint's "Start
  implementation" → Step 7, and "Approve and stop here"
  (`plan-approved-stop.md`, which stamps `plan_approved_at`). The existing
  `aitask_gate_record.sh … plan_approved` call is guarded by
  `profile.record_gates` (only the `fast` profile), so a hook needs its own
  unconditional call at both sites. Child plans written during decomposition
  skip approval; each child is approved when picked.
- **Task landed / archived** (needed for the obsolescence layer, §4):
  `aitask_archive.sh`.

### 2.7 Obsolescence — what exists and what the data says

- **Designed, not built:** t1663 (advisory task premise staleness, 6 children,
  all Ready) and t1655 (adopt it in the roadmap). Decision record:
  `aidocs/framework/task_premise_staleness.md`. It explicitly puts "is this
  still worth doing?" **out of scope**. Its own measurement: checking origin
  files against the origin's landing commit flagged 78/87 (89.7%) follow-ups
  as ASK_STALE, with 0 of 5 sampled actionable — file churn is noise. The one
  discriminating signal measured anywhere is line survival (`git blame -w -M`
  over origin lines), at 3.7–9 s per task
  (`aidocs/framework/manual_verification_staleness.md`).
- **Built, narrow:** `lib/roadmap_premise.py` (FRESH / ASK_STALE / SKIP for
  roadmap candidates only; module frozen and scheduled for deletion by t1655);
  `aitask_verification_stale.sh` (manual-verification tasks only); trail drift
  (`task_completed / task_archived / task_folded / new_related_task / …`, trail
  members only).
- **Missing entirely:** a reverted-origin signal (the revert skill writes
  `## Revert Notes`; no script reads it); moved-vs-deleted awareness for cited
  paths (`--no-renames` in the batch map; `-M --diff-filter=D` in the MV check
  reports a move as DELETED with an unknown culprit).
- **This session's measurement** over 577 pending (Ready / Editing /
  Postponed) tasks: 481 cite ≥1 repo path; 184 cite ≥1 path that does not
  exist now; 24 cite *only* missing paths. But the missing paths are mostly
  **not** obsolescence: 26 tasks cite **renamed** paths (e.g. the t259_* batch
  review children still cite the pre-rename `aiscripts/` layout — refresh, not
  obsolete; their goal is still unbuilt), relative paths misclassify as
  phantom (t1357 cites `lib/stats_data.py`, which exists under
  `.aitask-scripts/lib/`), and planned-new files are phantom by construction.
  Only **3** tasks cite a truly deleted path.
- **Conclusion:** static signals produce *"needs refresh"* evidence cheaply;
  *"obsolete"* (goal met elsewhere, direction superseded, origin reverted,
  target removed) is a judgement that needs an agent fed with that evidence.
<!-- /section: findings -->

<!-- section: decisions_taken [dimensions: requirements_*] -->
## 3. Decisions already taken (premises for the brainstorm)

1. **Precision over recall.** The notify list contains tasks with real
   connections only. In case of doubt, exclude. Over-notification is a
   defect (git traffic, conflict exposure, recipient noise).
2. **A task-relations store**, conceptually an extension of task metadata, is
   **stored separately from the task files** — never in frontmatter or body.
3. **Written by background agents**, not by the implementing session, at two
   moments: when a task is **created**, and when its **plan is finalized**
   (approved) before implementation.
4. **Background agents start from static analysis** (task metadata, task
   cross-references, labels/tags, file citations) to build a candidate list,
   then analyse candidates and record only confirmed relations, each with a
   description of how it relates to the task.
5. **The end of implementation reads the store** to get the final notify
   list, instead of discovering recipients in-session.
6. **Backlog obsolescence is a second layer on the same infrastructure**:
   different search logic, an **obsolete score** with reasons.
7. **A TUI to view relations and obsolete tasks** will be designed and built,
   not necessarily immediately. Relations data is first of all **for code
   agents**; the TUI is a later consumer.
8. **Rejected as the primary mechanism:** a purely static, in-session
   dependency analyzer run at the end of each task (the round-1 direction). It
   stays useful as the candidate generator inside the background analysis.
<!-- /section: decisions_taken -->

<!-- section: design_directions_intro -->
## 4. Design directions to analyse

Each item lists the options found so far and an initial lean. The brainstorm
decides; nothing here is settled beyond §3.

<!-- /section: design_directions_intro -->

<!-- section: d1_relations_store [dimensions: component_relations_store, tradeoff_store_location] -->
### D1 — Where the relations store lives

- **(a) Separate orphan branch `aitask-relations`, written like `aitask-locks`**
  (plumbing + push-CAS, one flat file per task, e.g. `t<id>_rel.json`). No
  content conflicts by construction; never touches the shared `.aitask-data`
  index, rebase gate or `ait sync` sweep. Needs: an offline / no-remote local
  fallback (as `aitask-ids` has), a larger retry budget (many writers on one
  ref), a cleanup verb for archived/deleted tasks, unbounded history growth
  handled.
- **(b) New top-level directory on the data branch**, mirroring
  `artifacts/manifests/`, **one file per record**
  (`relations/t<id>/<iso>_<rand>.json`) so concurrent writers add different
  paths and never conflict. Rides normal sync; but the auto-merge resolver
  handles only `aitasks/*.md` / `aiplans/*.md`, the scoped commit wrapper
  refuses paths outside them, dirty files under a new top-level dir are
  invisible to the sync sweep (commit immediately, retry on `index.lock`).
- **(c) Local-only cache (gitignored)** — rejected unless relations need not be
  shared across PCs; listed for completeness.
- **Initial lean:** (a), because the read pattern (one fetch per task at the
  end of implementation) is cheap and the write pattern (bursty background
  writers) is exactly what CAS-on-a-separate-ref absorbs.

<!-- /section: d1_relations_store -->

<!-- section: d2_record_schema [dimensions: component_relations_store] -->
### D2 — Record schema and relation vocabulary

- One record per (source task, analysis run): `task`, `trigger`
  (`created | plan_approved | landed | sweep | fold`), `at`, `base` SHA,
  analyser identity (agent/model), **input digest** (content hashes of every
  input read: source body, source plan, each candidate's body/plan), and
  `relations[]`.
- Each relation: `to`, `type`, `direction`, `description` (written for the
  *other* task's agent), `basis` (mechanically checkable anchors: paths,
  symbols, task ids, vocabulary tokens), `evidence[]` (source-tagged), and a
  confidence that is recorded only above the inclusion bar (§3.1).
- Vocabulary: reuse the trail relation types where they fit
  (`hard_depends`, `advisory_precedes`, `coordinates_with`, `verifies`,
  `informs`) and add only what notification and obsolescence need (e.g.
  `affects`, `supersedes`, `duplicates`). A closed vocabulary with a reserved
  namespace; writers fail closed on unknown types.
- Open: whether to cache **rejections** (analysed, not related) so the next
  run skips them while their digests are unchanged — and where (shared store
  vs local cache).

<!-- /section: d2_record_schema -->

<!-- section: d3_single_writer_reverse_lookup [dimensions: assumption_single_writer_reverse_lookup] -->
### D3 — Single writer, reverse lookup

- Each task's record holds only edges found **when that task was analysed**.
  No agent ever writes another task's record. The query for task X is
  `forward(X) ∪ reverse(X)`: X's own record plus every other record naming X
  (one tree read over ~600 small files).
- Consequence: a task created *after* X's plan was finalized is still found
  at X's end of implementation, through the newer task's record.
- Open: whether reverse edges need their own index for speed, or a scan is
  enough at this scale.

<!-- /section: d3_single_writer_reverse_lookup -->

<!-- section: d4_triggers [dimensions: component_triggers] -->
### D4 — Triggers and their timing

- Create hook in `aitask_create.sh` (single helper, 4 sites, silent,
  detached, never fails the create); debounce per parent during decomposition;
  delay or re-trigger for wrappers that seed the body in a later commit.
- Plan-approved hook: unconditional call at Step 7 and in
  `plan-approved-stop.md`.
- Landed/archived hook for the obsolescence layer (§D9) and for refreshing
  relations whose `basis` the landing changed.
- Fold: re-point or merge the folded tasks' relations into the primary.
- Periodic sweep: who runs it, how often, under what budget.
- Open: is plan approval the right second moment, or should analysis re-run
  whenever the plan changes (digest-driven)?

<!-- /section: d4_triggers -->

<!-- section: d5_execution_model [dimensions: component_background_worker] -->
### D5 — Execution model

- New headless `relations` operation in `aitask_codeagent.sh` (modelled on
  `explore-relay`), with its own default agent/model in
  `codeagent_config.json` (a cheap model), restricted tools.
- A local spool directory (atomic `*.tmp` + `os.replace`, as
  `chatlink/relay.py` writes) drained by **one** lock-guarded worker that the
  trigger starts if it is not running (detached, as `start_runner` does).
  The spool de-duplicates and coalesces triggers.
- Per-job timeout enforcement; completion judged from the written record,
  never from pane idleness or banner text.
- A shared opt-out knob (disable the whole layer; disable per trigger) and a
  daily token budget.
- Open: Claude print-mode billing vs other agents' headless modes; whether
  the worker should run only on one designated host.

<!-- /section: d5_execution_model -->

<!-- section: d6_candidate_generation [dimensions: component_candidate_generator] -->
### D6 — Static candidate generation (input to the agent)

- Signals, ranked by the replay: task-id cross-references (both directions,
  bodies; parent/child expansion), then metadata edges (`depends`, `anchor`,
  `verifies`, `children_to_implement`, `risk_mitigation_tasks`, folds), trail
  co-membership and trail relations, past note edges, non-hub file overlap,
  `file:line` citations into the source's surface, rare labels.
- Cap the list (order of ~25) and pass **source-tagged evidence**, not a
  verdict: the helper reports, the agent judges.
- Fix the extractor gaps (extensions, suffix/relative resolution) or use
  `find_suffix_references`; decide how hub paths are weighed by change kind.
- Optional widening: `Graph.Reverse` from the testmap engine (files that
  import the changed files).

<!-- /section: d6_candidate_generation -->

<!-- section: d7_analysis [dimensions: component_relation_analysis] -->
### D7 — The analysis itself (agent side)

- Inclusion test, not a quota: a relation is recorded only when the agent can
  state concretely what the other task would do differently. No "find at
  least N" pressure.
- Two-stage reading: excerpts for screening, full body/plan only for
  survivors.
- The `description` is written for the recipient's future agent; the `basis`
  makes it checkable later.
- Coverage of the two named misses: in-flight uncommitted work of another task
  (needs `aitask_change_surface.sh` / in-flight surfaces), and vocabulary or
  contract consumers with no shared path (needs symbol / token evidence).

<!-- /section: d7_analysis -->

<!-- section: d8_consumption [dimensions: component_consumption, tradeoff_push_vs_pull] -->
### D8 — Consumption at the end of implementation: push vs pull

- **Push (current model, made precise).** Step 8e reads `forward ∪ reverse`
  relations of the task, keeps still-pending targets, re-validates each
  relation's `basis` against the **actual landed diff** (a plan-time relation
  may no longer hold), and offers notes only for survivors, pre-filled from
  `description`. Composition could move to the background worker after merge,
  off the implementing session's critical path.
- **Pull (alternative to analyse).** Write nothing to the other tasks. When a
  task is picked, its pick-time checks read the store: "since this task was
  created / planned, these related tasks landed: …, relation: …". Zero
  writes to other task files; the information arrives exactly when it is
  needed; no read receipts. Notes remain for findings that are not derivable
  from relations (review findings, decisions made in conversation).
- **Hybrid.** Pull by default; push a note only when the relation is strong
  and the recipient is likely to be picked before it would otherwise notice
  (e.g. it is next on a trail).
- Also: batch multiple notes from one sender into fewer commits.
- Open: which model the store optimises for; whether `/aitask-note`'s
  no-target path and the Related Task Discovery Procedure (explore, fold,
  contribution-review) should read the store first.

<!-- /section: d8_consumption -->

<!-- section: d9_obsolescence [dimensions: component_obsolescence_layer] -->
### D9 — Obsolescence layer and the obsolete score

- Same store, same worker, different operation and prompt.
- Evidence (static, cheap): cited paths **deleted vs renamed** (`-M`
  rename-aware history), with suffix/relative resolution; line survival for
  exact-origin follow-ups (expensive, use selectively); origin state
  (reverted via `## Revert Notes`, folded, archived, deleted); `supersedes` /
  `duplicates` relations pointing at the task; landed tasks since creation
  whose surface and goal overlap the task's; age without activity as a weak
  prior only (never a verdict on its own).
- Judgement: an agent assigns a score band with reasons and a recommended
  disposition (keep / refresh / fold into tX / drop). **Never auto-actioned.**
- Triggers: when task A lands, re-score the pending tasks A's relations point
  to (landing is what makes tasks obsolete); plus a slow full-backlog sweep.
- Disposition gap: there is no `Obsolete` status; dropping today means delete
  or fold. Decide whether a new terminal status or an archive reason is
  needed.
- Boundary with t1663 / t1655: they own "does the premise still hold / needs
  refresh"; this layer owns "is it still worth doing". Decide whether they
  share an engine (`task_premise.py`) or only evidence rows.

<!-- /section: d9_obsolescence -->

<!-- section: d10_surfaces [dimensions: component_surfaces] -->
### D10 — Surfaces

- Agent-facing first: pick-time context (Step 3 checks), planning context
  (related tasks section), Step 8e, fold candidates (t1634 is adjacent),
  trail/roadmap inputs.
- CLI: e.g. `ait relations show <task>`, `ait relations why <a> <b>`,
  `ait obsolete ls`.
- TUI (later): per-task relation list with type, description, evidence,
  freshness; neighbourhood graph; obsolete list sorted by score with reasons;
  actions (open task, send note, fold, drop). Board detail-screen field or
  badge as a lighter first step. Registered in the TUI switcher.

<!-- /section: d10_surfaces -->

<!-- section: d11_lifecycle [dimensions: tradeoff_eager_vs_lazy_refresh] -->
### D11 — Lifecycle and freshness

- A relation is stale when any input digest changes. Re-analysis policy:
  eager (on digest change) vs lazy (on read).
- Archive: keep records for history or prune; renumber / delete / fold
  handling; garbage collection.

<!-- /section: d11_lifecycle -->

<!-- section: d12_cross_repo -->
### D12 — Cross-repo

- Relations across registered projects (xdeps, linked trails) — likely later.
  Note routing already exists (`ait note --project`).

<!-- /section: d12_cross_repo -->

<!-- section: d13_evaluation [dimensions: component_evaluation] -->
### D13 — Evaluation

- The replay harness (Appendix A) gives recall against real note history.
  Extend it to score the full pipeline (candidates → agent → recorded
  relations) and to measure the notify-list size reduction.
- Automation-first: no human review step as a precondition for the layer to
  operate.

<!-- /section: d13_evaluation -->

<!-- section: constraints [dimensions: requirements_*] -->
## 5. Constraints from project conventions

- Helpers report source-tagged evidence; the agent judges. No classifier
  tables, no transcript parsing.
- Heuristic evidence stays advisory. A relation or score never changes a
  task's status, requirements or authority, and is never auto-actioned.
- Derived records carry provenance (content hashes of every consumed input),
  never stat freshness.
- New write paths honour a shared opt-out and have bounded recovery: stop,
  report actual state, targeted retry.
- New helper scripts invoked from skills need the 5-touchpoint permission
  allowlist (`aidocs/framework/aitasks_extension_points.md`); skills change in
  `.claude/skills/` first, with follow-up tasks for the other agents' trees.
- Notes remain untrusted advisory input; `from=` is a claim.

<!-- /section: constraints -->

<!-- section: related_tasks -->
## 6. Related tasks

- t1663 (+ children) and t1655 — premise staleness ("needs refresh").
- t1634 — fold-candidate clustering for the backlog roadmap (same-region
  tasks); a likely consumer or producer of `duplicates`-type relations.
- t1569 / t1718 — background-work roadmap and its trail artifact.
- t1657 family / `aidocs/framework/task_note_mailbox.md` — the note mailbox.

<!-- /section: related_tasks -->

<!-- section: expected_outcome -->
## 7. Expected outcome of the brainstorm

A finalized design document (target: `aidocs/framework/task_relations.md`)
covering D1–D13, and a decomposition into child tasks. A plausible split, for
the brainstorm to confirm or replace: relations store and CLI; static
candidate generator; background worker + headless operation + spool;
creation and plan-approval triggers; Step 8e / pick-time consumption;
obsolescence layer; TUI; ports of the skill changes to the other code agents.

<!-- /section: expected_outcome -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

- Writing a note is cheap (t1794_9: 63 notes in 2 min 41 s); the cost is selecting and composing recipients in the implementing session.
- Static analysis is effectively free (full path index 0.15 s; rename/delete history pass 2.7 s) and does not need a background job to be fast.
- Task-id cross-references (task bodies only) are the best static candidate signal; file overlap has high recall but very low precision.
- Hub paths carry real signal in refactors, so their down-weighting must depend on the kind of change.
- Static signals cannot reach the semantic residue (another task's uncommitted in-flight work; vocabulary-contract consumers with no shared path).
- "Obsolete" is a judgement needing an agent fed with static evidence; static signals only yield "needs refresh".
- Missing cited paths are mostly renames, relative paths or planned-new files, not obsolescence (only 3 pending tasks cite a truly deleted path).
- Creation rate stays near 8 tasks and 4 plan finalizations per day (~12 triggers/day); one analysis costs ~30-50k input tokens.
- Measured precision is a lower bound; the corpus is live (candidate counts drift 1-8 between runs) and bodies are read post hoc.
- A task's record holds only edges found when it was analysed; the query for X is forward(X) union reverse(X), and a scan of ~600 small files may be enough without a reverse index.
- Plan approval (Checkpoint "Start implementation" / "Approve and stop here") is the right second analysis moment; whether to re-run on plan change is open.
- Notes remain untrusted advisory input; `from=` is a claim.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

- **Store location (D1):** orphan branch avoids content conflicts and the shared data index but adds network on every write, retry contention on one ref and invisibility to sync/board/archival; a data-branch directory rides normal sync but needs resolver and commit-wrapper changes and is invisible to the sync sweep; a local cache is not shared across PCs.
- **Push vs pull (D8):** pushing notes keeps the current model but writes to other tasks' files (commits, receipts, conflict exposure); pulling at pick time has zero writes and no receipts but needs notes for findings not derivable from relations; hybrid pushes only strong relations likely to be picked soon.
- **Eager vs lazy freshness (D11):** re-analysis on digest change keeps relations fresh at higher token cost; lazy re-analysis on read is cheaper but slower at the point of use.
- **Precision vs recall (D6):** file overlap reaches 95% recall at ~4% precision; cross-references reach 86% recall at ~41%; the chosen bias is precision, accepting missed semantic relations.
- **Background cost:** removing selection cost from the implementing session costs ~0.4-0.6M tokens/day in background analysis, with Claude print-mode billing at a higher per-token rate.
<!-- /section: tradeoffs -->

<!-- section: appendix_measurement_scripts -->
## Appendix A — measurement scripts (verbatim)

Run from the repository root. Read-only.

### A.1 Signal replay (§2.3)

```python
import sys, re, glob, os, collections
sys.path.insert(0, '.aitask-scripts/lib')
import plan_paths as pp
def tid_of(path):
    b=os.path.basename(path); m=re.match(r'[tp](\d+(?:_\d+)?)_', b); return m.group(1) if m else None
tasks=glob.glob('aitasks/t*.md')+glob.glob('aitasks/t*/t*.md')+glob.glob('aitasks/archived/t*.md')+glob.glob('aitasks/archived/t*/t*.md')
plans=glob.glob('aiplans/p*.md')+glob.glob('aiplans/p*/p*.md')+glob.glob('aiplans/archived/p*.md')+glob.glob('aiplans/archived/p*/p*.md')
tbody={}; pbody=collections.defaultdict(str); fm={}; recips=collections.defaultdict(set)
notere=re.compile(r'\*\*✉ note:t[0-9_]+\*\* id=\S+ from=t([0-9_]+)')
for f in tasks:
    t=tid_of(f)
    if not t: continue
    raw=open(f,encoding='utf-8',errors='replace').read()
    for s in notere.findall(raw): recips[s].add(t)
    tbody[t]=pp.task_body_text(raw)
    m=re.match(r'---\n(.*?)\n---',raw,re.S); fm[t]=m.group(1) if m else ''
for f in plans:
    t=tid_of(f)
    if t: pbody[t]+=open(f,encoding='utf-8',errors='replace').read()
def text(t): return tbody.get(t,'')+pbody.get(t,'')
paths={t:set(pp.extract(text(t))) for t in tbody}
fan=collections.Counter(p for ps in paths.values() for p in ps)
base=lambda p: os.path.basename(p)
fanb=collections.Counter(base(p) for ps in paths.values() for p in {base(x) for x in ps})
HUB=10
def labels(t):
    m=re.search(r'^labels:\s*\[(.*?)\]',fm.get(t,''),re.M); return {x.strip() for x in m.group(1).split(',') if x.strip()} if m else set()
labfan=collections.Counter(l for t in tbody for l in labels(t))
def root(t): return t.split('_')[0]
def mentions(txt, t):
    return re.search(r'(?<![\w#])t'+re.escape(t)+r'(?![\d_])', txt) is not None
rows=[]; agg=collections.defaultdict(lambda:[0,0])
senders=[s for s,r in recips.items() if len(r)>=4]
for s in sorted(senders,key=lambda s:-len(recips[s])):
    R=recips[s]-{s}
    sp={p for p in paths.get(s,set())}
    sb={base(p) for p in sp}
    U=[t for t in tbody if t!=s]
    sig={}
    sig['file_all']={t for t in U if (paths[t]&sp) or ({base(p) for p in paths[t]}&sb)}
    sig['file_nohub']={t for t in U if {p for p in paths[t]&sp if fan[p]<HUB} or {b for b in ({base(p) for p in paths[t]}&sb) if fanb[b]<HUB}}
    sig['xref_in']={t for t in U if mentions(tbody[t]+pbody.get(t,''), s) or (root(s)!=s and mentions(tbody[t]+pbody.get(t,''), root(s)))}
    sig['xref_out']={t for t in U if mentions(text(s), t)}
    sig['label_rare']={t for t in U if {l for l in labels(t)&labels(s) if labfan[l]<40}}
    sig['xref_in_task']={t for t in U if mentions(tbody[t], s) or (root(s)!=s and mentions(tbody[t], root(s)))}
    sig['xref_out_task']={t for t in U if mentions(tbody.get(s,''), t)}
    sig['xref']=sig['xref_in']|sig['xref_out']
    sig['xref_task']=sig['xref_in_task']|sig['xref_out_task']
    fam_sp=set(sp)
    if not fam_sp:
        for t2 in tbody:
            if root(t2)==root(s): fam_sp|=paths[t2]
    fam_b={base(x) for x in fam_sp}
    def anchored(t):
        txt=tbody.get(t,'')+pbody.get(t,'')
        for m in re.finditer(r'([A-Za-z0-9_./-]+\.(?:sh|py|md|go|kt|json|yaml|yml|toml)):(\d+)', txt):
            if m.group(1) in fam_sp or base(m.group(1)) in fam_b: return True
        return False
    sig['line_anchor']={t for t in U if anchored(t)}
    sig['xref_task|anchor']=sig['xref_task']|sig['line_anchor']
    sig['nohub|xref']=sig['file_nohub']|sig['xref']
    sig['nohub&(xref|label)']=sig['file_nohub']&(sig['xref']|sig['label_rare'])
    line=f"t{s:8} sent={len(R):3} "
    for k,v in sig.items():
        h=len(R&v); agg[k][0]+=h; agg[k][1]+=len(v)
        line+=f"| {k}={h}/{len(v)} "
    print(line)
tot=sum(len(recips[s]-{s}) for s in senders)
print(f"\nTOTAL recipients={tot}")
for k,(h,c) in agg.items(): print(f"  {k:22} recall={h}/{tot}={h/tot:.0%}  candidates={c}  precision~{h/c:.0%}")
```

The first replay (landed change sets, §2.3 row 2) differs only in the
sender's surface: the files of commits whose subject ends in `(t<sender>)`
(`git log --all --name-only -E --grep '\(t<id>\)$'`), falling back to the
sender's whole family (`(t<root>(_N)?)`) for note-only children such as
t1794_9, matched exactly or by basename (excluding `CLAUDE.md`, `SKILL.md`,
`README.md`), plus the metadata edges `depends` / `anchor` / `verifies` /
same root.

### A.2 Missing cited paths over pending tasks (§2.7)

```python
import sys, re, glob, os, subprocess, collections, time
sys.path.insert(0, '.aitask-scripts/lib')
import plan_paths as pp
tracked,tdirs=pp.tracked_sets()
log=subprocess.run(['git','log','--all','-M','--name-status','--diff-filter=DR','--pretty=format:'],capture_output=True,text=True).stdout
deleted=set(); renamed={}
for l in log.splitlines():
    p=l.split('\t')
    if p[0]=='D' and len(p)>1: deleted.add(p[1])
    elif p[0].startswith('R') and len(p)>2: renamed[p[1]]=p[2]
rows=[]
for f in glob.glob('aitasks/t*.md')+glob.glob('aitasks/t*/t*.md'):
    raw=open(f,encoding='utf-8',errors='replace').read()
    m=re.search(r'^status:\s*(\S+)',raw,re.M); st=m.group(1) if m else '?'
    if st not in ('Ready','Editing','Postponed'): continue
    toks=[t for t in pp.extract(pp.task_body_text(raw)) if '/' in t and not t.startswith(('aitasks/','aiplans/'))]
    if not toks: rows.append((f,st,0,0,0,0)); continue
    cls={t:pp.classify(t,tracked,tdirs) for t in toks}
    ph=[t for t,c in cls.items() if c=='phantom' or (c=='planned_new' and (t in deleted or t in renamed))]
    dele=[t for t in ph if t in deleted and t not in renamed]
    ren=[t for t in ph if t in renamed]
    rows.append((f,st,len(toks),len(ph),len(dele),len(ren)))
withp=[r for r in rows if r[2]>0]
b=collections.Counter()
for r in withp:
    fr=r[3]/r[2]; b['0%' if fr==0 else '<50%' if fr<.5 else '<100%' if fr<1 else '100%']+=1
print("pending:",len(rows),"with cited paths:",len(withp),"buckets:",dict(b))
print("any deleted-cited:",sum(1 for r in withp if r[4]),"any renamed-cited:",sum(1 for r in withp if r[5]))
```

Output on 2026-10-14: `pending: 577 with cited paths: 481 buckets: {'0%':
297, '<50%': 113, '<100%': 47, '100%': 24}`; `any deleted-cited: 3 any
renamed-cited: 26`.
<!-- /section: appendix_measurement_scripts -->

--- PROPOSAL_END ---
