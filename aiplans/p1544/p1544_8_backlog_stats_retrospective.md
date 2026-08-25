---
Task: t1544_8_backlog_stats_retrospective.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_1_session_discovery_dedupe.md, aiplans/archived/p1544/p1544_2_task_category_axis_module.md, aiplans/archived/p1544/p1544_3_backlog_flow_collection.md, aiplans/archived/p1544/p1544_4_cli_backlog_sections_and_csv.md, aiplans/archived/p1544/p1544_5_stats_tui_backlog_panes.md, aiplans/archived/p1544/p1544_6_backlog_stats_documentation.md, aiplans/archived/p1544/p1544_7_manual_verification_auto.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-25 12:09
---

# p1544_8 — Backlog stats retrospective (verified 2026-08-25)

## Context

t1544 added a backlog dimension to `ait stats` (level + net flow by category,
CLI and TUI). Its decomposition committed to several design choices under
partial information — flows-only storage, an 8-week default horizon, parent+child
as the denominator, Postponed counted as open, an unproven TUI shape. Per
`aidocs/framework/planning_conventions.md`, such a decomposition gets a trailing
retrospective child. This is that child.

**This task writes no production code.** Its deliverable is a written answer to
each of the eight questions in the task body, each ending in an explicit
disposition, plus standalone follow-ups **only where the data justifies them**.
"No change needed" is the expected outcome for most.

## Verification of the prior plan (this pass)

The prior plan's method, deliverable and file paths are still valid; the
corrections found this pass are folded in below (§A–§D).

§A, §B and §D correct facts that moved or were wrong. §C–§C4 close evidence
gaps the prior plan left open: it constrained only Q2's uninstrumented half,
leaving Q6–Q8 free to turn silence into "no change needed"; it named no way to
record an evidence gap within the three dispositions the task allows; it
required live measurement without a snapshot record while another session is
changing the corpus; it called the preset hazard "surviving" without
inventorying who is exposed; and it asked for a coordination-shell ratio with no
predicate for counting one.

### A. Three tasks landed after the plan was written

They pre-dispose parts of four questions, and the findings must credit them
rather than re-derive or re-file:

| landed | what it did | pre-disposes |
|---|---|---|
| **t1586** `6a80b7bc5` | extracted the shared backlog view logic into `.aitask-scripts/lib/backlog_view.py` (`BacklogAxis`, `build_backlog_axis`, `order_categories`, `backlog_columns`) | **Q1** — this *is* the second caller the `out_offsets` contract was waiting for |
| **t1588** `a260eb599` | backlog level columns run chronologically with Now last | **Q5** — presentation changed after the plan |
| **t1590** `6e91f5d28` | dropped the frozen `~0.3%` footnote literal; unpinned the redundant `stats_config.json` preset defaults (file is now `{}`) | **Q7** (footnote half) and **Q8** bullet 1 (redundant pins half) |

Note t1590 removed the *redundant pins*; it did **not** change `deep_merge`'s
list-**replacement** semantics. Q8 bullet 1 is therefore half-disposed, not
closed — the masking hazard survives for any project that pins a preset. How
many do so today is measured in **§C3** (none), and the Q8 finding must decide
against that measured population rather than the hazard in the abstract.

### B. Five open follow-ups are already anchored to 1544

The Deliverable allows "folded into an existing task tN". These must be checked
before anything new is filed, or the retrospective will duplicate them:

- **t1585** memoize backlog category — the filed mitigation for the CSV
  `resolve_category` second pass (+62 ms / +25%). → **Q6**
- **t1579** `collect_inflight` dead `today` / `week_start_dow` params. → **Q6**
- **t1591** stats docs source-drift guard (hand-pinned counts/column lists). → **Q7**
- **t1584** `aitask-stats` SKILL.md drift, all three agent trees. → **Q7**
- **t1567** ring helpers duplicate-key livelock. → **Q1** robustness

### C. Several sub-questions ask about *behaviour*, and only some are measurable

Q2, Q6, Q7 and Q8 each contain a sub-question about what people did — not about
what the code does. A local scan of a moving repository cannot answer those, and
the failure mode is turning **absence of telemetry, tasks or reports into a
disposition of "no change needed"**. That is inference from silence, and it is
prohibited here.

**Evidence status and disposition are two separate fields.** The task body
allows exactly three dispositions — `no change needed`, `filed as tN`,
`folded into tN` — so "unmeasurable" is **not** a disposition and must never be
written as one. Every finding therefore carries both lines:

```
Evidence: <named source> → <what it returned>     (or: none — no source exists)
Disposition: no change needed | filed as tN | folded into tN
```

**How an evidence-gap finding is recorded.** When `Evidence: none`, the
disposition is still one of the three, chosen by this rule:

- **`no change needed`** is permitted, but only with the reasoning stated in the
  finding as *"no evidence exists either way; this is not a finding that the
  design is correct."* It records that **no product change is being made for
  want of evidence** — it must never be phrased, or later read, as validation of
  the original design choice. Silence is not confirmation.
- **`filed as tN`** where the gap itself is worth closing — i.e. the question
  matters enough that the missing instrumentation or evidence source should be
  built. Q2's horizon-override question is the live candidate: filing a task to
  record `ait stats` flag usage would answer it, and that decision must be taken
  on the merits rather than defaulted past.

A finding may **not** claim anything about what users did, wanted, or were
confused by unless its `Evidence:` line names a source that says so.

Verified sources, this pass:

| sub-question | treatment |
|---|---|
| Q2 — what horizon do people actually pass? | `Evidence: none`. Nothing records `ait stats` invocations or flags; `--backlog-weeks` goes straight into `argparse` (`aitask_stats.py:212-216`). Decide between the two evidence-gap dispositions above. |
| Q2 — does 8 weeks truncate the trend? / does the TUI want another value? | **measurable** — render at 8 vs a wide horizon (see the Q5 viewport procedure). |
| Q3 — has the coordination-shell ratio moved? | **measurable only under a stated predicate** — see §C4; the planning-time figure has none. |
| Q4 — has Postponed grown? | **measurable** — corpus scan. |
| Q6 — *can* a current caller benefit from `with_backlog=False`? | **measurable** — exactly four production call sites: `aitask_stats.py:803`, `work_report_gather.py:397` (already `False`), `stats_app.py:322`, `stats_app.py:356`. Inspect what each reads off the returned `StatsData`. This scan establishes **technical benefit only**. |
| Q6 — does anyone *want* it? | **demand, not call graph.** `Evidence: none` unless the concept search (pre-phase 2) turns up a task, report or issue asking for it. The call-site scan may **not** be used to answer this half. |
| Q7 — did the footnote do its job, or generate questions? | **measurable in part** — the task corpus is a real evidence source: t1590 was itself filed as an `upstream_defect` about that footnote. Search live + archived tasks for clock/footnote references. Confusion that never reached a task is **unmeasurable**. |
| Q8 — has anyone used `created_at` on the CSV? | **measurable in part** — in-repo consumers by grep (nothing currently reads the CSV back). Ad-hoc human use is **unmeasurable**; per the task body, note it rather than removing the column. |

### C4. Q3 needs a stated predicate — the planning-time figure has none

Q3 asks whether the "~29 of ~300 open parents are pure coordination shells"
ratio has moved. Verified: the parent plan asserts that figure at
`aiplans/p1544_stats_backlog_and_net_flow_by_category.md:223` **without
recording how it was counted**, and no corpus-visible predicate for
"coordination shell" exists anywhere in source. (`coordination_only` in
`board/aitask_board.py:638` is an agent-assigned `aitask-trail` *classification*
covering only tasks that appear in a trail — it is not a corpus predicate and
must not be repurposed as one.)

So the count must define its own predicate before counting, and report honestly
that the baseline does not share it:

- **Predicate P (structural, fully reproducible):** a live parent `tN` is a
  coordination shell iff `aitasks/tN/` contains ≥1 child task file. State the
  exact command used, and record its result in the snapshot.
- **P over-counts** — a parent that carries real implementation work of its own
  *and* has children satisfies it. Report `|P|` as an **exact, population-wide
  upper bound**.
- **The over-count correction is a separate, sampled estimate — never merged
  into the upper bound.** Select the sample **deterministically**, so it cannot
  be unintentionally shaped: sort P's member IDs numerically ascending and take
  a systematic every-`k`-th sample with `k = floor(|P| / 10)` starting at the
  first element (if `|P| ≤ 10`, inspect all of P and say so — no estimate is
  needed). Record in the finding: the selection rule, `k`, the resulting member
  IDs, and each one's hand verdict.
- **Report the two numbers separately and label them as such** — `|P| = <n>`
  (upper bound, whole population) and `over-count ≈ <x>% (n = <sample size>,
  systematic every-k-th)`. Do not present a single "corrected count", which
  would give a sampled estimate the appearance of a census.
- **The comparison to ~29/300 is indicative, not exact**, because the two
  numbers were produced by different (and in the baseline's case, unrecorded)
  methods. The finding must say this rather than presenting a delta as if both
  sides were measured the same way.

### C2. Measurement baseline — the corpus moves under this task

Another session is active in this repository right now, and `main` already
advanced mid-session during this pass (t1590 landed and was archived between two
reads). Counts, timings, category cardinality and per-repository results taken
minutes apart can therefore describe **different repository states**, making the
findings irreproducible.

Before deriving any finding, record a **`### Measurement snapshot`** block at the
top of `## Retrospective findings`:

- UTC timestamp of the measurement pass;
- code-branch `HEAD` sha and task-data branch `HEAD` sha (`./ait git rev-parse HEAD`);
- live and archived task counts at that moment;
- the registered-project list actually used, with each repository's result
  recorded **individually** (never only an aggregate);
- any measurement re-taken after the corpus moved, and why.

Every number quoted in a finding cites this snapshot. If `HEAD` moves mid-pass,
either re-take the affected measurements or record both stamps and say which
number came from which.

### C3. Q8's preset hazard has an empty affected population — measured

§A calls the merge-vs-replace masking hazard "surviving". Inventoried this pass,
its current population is **empty by every reachable route**:

- 0 of the 7 registered projects pin any preset — six have no
  `aitasks/metadata/stats_config.json` at all; this repository's exists but has
  no `presets` key (t1590 emptied it to `{}`);
- `seed/` ships **no** `stats_config.json`, so a newly set-up project pins
  nothing either.

Only a hand edit enters the affected set. The Q8 finding must record this
inventory and the before/after **effective** pane lists a merge-semantics change
would produce, and decide the follow-up against a measured population of zero —
not against the hazard in the abstract.

### D. Q8's `t597_4` premise is stale — a finding in itself

The task body says honouring `week_start` / `days` "needs `resolve_week_start`
moved from the CLI into `lib/` first (existing TODO t597_4)". Verified:

- **t597_4 already landed and is archived** (`CHANGELOG.md:1215`, shipped with
  the stats TUI) and did **not** make the week start configurable.
- `.aitask-scripts/stats/panes/overview.py:13` still reads
  `_WEEK_START_DOW = 1  # Monday; t597_4 will make this configurable.` and
  `.aitask-scripts/stats/panes/backlog.py:12` forwards to that TODO.
- The other half of the premise holds: `resolve_week_start` is still CLI-local
  at `aitask_stats.py:241`, not in `lib/`.

So two source comments point at a completed task as if it were pending work.
That is a concrete, fileable finding for Q8 independent of whether
`week_start` / `days` are ever honoured.

### Pre-phase (risk mitigations)

1. `[premise_recheck]` Before answering any question, re-verify every factual
   premise the task body asserts and record each as **holds** or **stale** in a
   short table that opens `## Retrospective findings`. At minimum: `t597_4`'s
   status (archived — `CHANGELOG.md:1215` — while
   `stats/panes/overview.py:13` and `stats/panes/backlog.py:12` still call it
   pending); the `~0.3%` and "26 of ~1828 / 6 by a week" clock-disagreement
   figures (no longer rendered after t1590); the "~29 of ~300 open parents are
   coordination shells" ratio; the "9 live Postponed (~2%)" count; and the
   "0.15s of added work over ~2250 files" cost. A premise that fails here must
   not be reused as an answer's basis.
2. `[existing_followup_sweep]` Build the question→existing-task map by **two**
   searches, not one — an anchor alone is too narrow, since a task filed before
   t1544 or without the anchor can cover the same finding:
   - **by anchor:** `grep -l "^anchor: 1544" aitasks/*.md aitasks/*/*.md`
     (currently t1585, t1579, t1591, t1584, t1567);
   - **by concept:** search the whole live corpus — and `aitasks/archived/`, to
     avoid re-filing something already done — for the terms each candidate
     finding turns on (e.g. `week_start`, `resolve_week_start`, `preset`,
     `deep_merge`, `collect_stats`, `backlog`, `completed_at`,
     `resolve_completion_date`, `stats_config`).

   Every disposition consults this map first. A new task may be filed only after
   the finding names why no task found by **either** search covers it.
3. `[live_surface_measurement]` Measure the rendered surfaces under a **fixed,
   restated viewport** so the observation is repeatable:
   - **Geometry:** capture the CLI report at exactly **80 columns** (this is the
     width Q2's default-horizon compromise was chosen for — render at both the
     8-week default and a wide horizon and compare), and boot `ait stats-tui`
     at a stated terminal size, recording that size in the snapshot.
   - **Initial state:** state the preset and the pane selected on entry
     (`backlog.level`, then `backlog.netflow`), and the distinct category set
     present in the corpus at measurement time.
   - **Acceptance rules — write these down before looking, then judge against
     them.** Row cap (`_LEVEL_ROW_CAP = 6`, `stats/panes/backlog.py:51`) is
     adequate only if the `Other` bucket does not conceal a category whose open
     count rivals a displayed row; if any collapsed category would outrank a
     shown one, the cap is wrong and the finding says so. The netflow split is
     legible only if every rendered series stays individually distinguishable at
     the capped plot width — degradation into noise at the real category count
     is a finding, not a cosmetic note.
   - **Timings — one uniform protocol, stated before measuring.** A single
     uncontrolled run is dominated by filesystem cache, process startup and
     scheduler noise, and **another agent session is active in this repository
     right now**, so contention is a live confound rather than a theoretical
     one. Fix all four variables:
     - **Boundary:** time the `collect_stats(...)` call itself in-process with
       `time.perf_counter`, excluding interpreter start and rendering — that
       call is the doubled cost Q6 asks about. Time `ait stats-tui` startup
       separately, defining and stating the endpoint used; if no reliable
       first-paint signal exists, time only the collect phase and **say so**
       rather than reporting a boundary that was not measured.
     - **Cache state:** one discarded warm-up run per repository per condition,
       then measure — all reported numbers are warm-cache. State this; do not
       claim cold-cache figures, which are not reproducible here without root.
     - **Repetition and aggregation:** ≥5 measured runs per repository per
       condition; report the **median** with the min–max range. Never a mean,
       and never a single run.
     - **Pairing:** run the `with_backlog` True/False conditions **back-to-back
       per repository** and compare within that pair, so a contention spike
       moves both sides rather than manufacturing a delta.
     - **Preserve failures and outliers:** repositories that error or hold no
       task data are reported as such, never dropped; any run beyond 2× that
       repository's median is kept and flagged in the snapshot, never discarded.
     - Every repository's result is recorded individually per §C2, alongside a
       note of concurrent agent activity observed during the pass.

   Q5 and Q6 quote observed output and timings, never source reading.

## Method

1. **Re-measure against the corpus at the time of writing.** Do not copy the
   parent plan's planning-time snapshot — the corpus moved measurably during
   planning alone. Every number quoted in the findings must come from a command
   run in this session.
2. Read the seven archived siblings' Final Implementation Notes
   (`aitasks/archived/t1544/`) and the archived plans
   (`aiplans/archived/p1544/`) — several questions are answered directly by what
   the implementers recorded.
3. Before filing anything, check it against the five open anchor-1544 tasks in
   §B. Prefer **folded into tN** over a new task.
4. Answer each question in `## Retrospective findings` in the plan file, one
   subsection per question, each ending in an `Evidence:` line and then a
   `Disposition:` line holding exactly one of **no change needed** /
   **filed as tN** / **folded into tN** (§C).

## Measurements to take

| question | measurement |
|---|---|
| Q1 | `backlog_levels` (`lib/stats_data.py:301`) cumulation cost at the current archived-tree size; whether `lib/backlog_view.py`'s `build_backlog_axis` honours the output-columns-only contract |
| Q2 | render the level table at 8 weeks vs a wide horizon at exactly 80 columns; the "what do people pass" half is **unmeasurable** (§C) |
| Q3 | current `TOTAL OPEN` with its `(parents / children)` split; coordination-shell count under **predicate P** (§C4) as an upper bound, plus a 10-parent sample for the over-count |
| Q4 | current live `Postponed` count and share of open |
| Q5 | live category cardinality vs `_LEVEL_ROW_CAP = 6` (`stats/panes/backlog.py:51`) and the `Other` bucket; netflow split legibility |
| Q6 | `collect_stats` with/without backlog; `ait stats-tui` startup against the **7** registered repos in `~/.config/aitasks/projects.yaml`; whether a current caller can *benefit* from `with_backlog=False` (call-site scan) — kept separate from whether anyone *wants* it (§C) |
| Q7 | current disagreement between `completed_at` and `resolve_completion_date` (re-measure; the old "26 of ~1828 / ~0.3%" is stale and no longer rendered) |
| Q8 | the three deferred items, with §A and §D corrections applied |

## Files

- `aiplans/p1544/p1544_8_backlog_stats_retrospective.md` — this plan, extended
  with `## Retrospective findings`
- New task files **only** where a finding justifies one and no existing
  anchor-1544 task already covers it

## Verification

- Every one of the eight questions has a written answer with an explicit
  disposition.
- Any follow-up created is referenced by ID in the findings; any question folded
  into an existing task names that task's ID.
- Every number quoted was re-measured in this session and cites the
  `### Measurement snapshot` block (§C2), not the parent plan or the task body.
- Every finding carries **both** an `Evidence:` line (named source and what it
  returned, or `none — no source exists`) and a `Disposition:` line holding
  exactly one of the task's three allowed values (§C). "Unmeasurable" appears
  only as evidence status, never as a disposition.
- Every `no change needed` resting on `Evidence: none` states in the finding
  that no evidence exists either way and that this is **not** a finding that the
  design is correct. No finding claims anything about what users did, wanted or
  were confused by without an `Evidence:` source that says so.
- Q6's two halves are answered separately: technical benefit from the call-site
  scan, user demand only from a source found by the concept search.
- Q5's findings state the viewport, initial pane state and category set they
  were observed under, and judge the row cap and netflow split against the
  acceptance rules written down before the observation.
- The Q8 preset finding records the measured population (0 of 7 registered
  projects pin presets; the seed ships no config) and the before/after
  **effective** pane lists a merge-semantics change would produce.
- Q3 reports `|P|` as an exact population-wide upper bound and the over-count as
  a **separately labelled** sampled estimate, naming the deterministic selection
  rule, `k`, the sampled IDs and each verdict — never a single blended
  "corrected count". It states that the ~29/300 baseline used an unrecorded
  method, so the delta is indicative.
- Q6's timings state the measured boundary, warm-cache protocol, run count and
  median-with-range aggregation; the two `with_backlog` conditions were run
  back-to-back per repository; erroring repositories and flagged outliers appear
  in the snapshot rather than being dropped.
- Every new task filed names why no task found by **either** the anchor search
  or the concept search already covers it.

## Risk

### Code-health risk: low
- None identified. The task writes no production code; its output is a
  `## Retrospective findings` section in this plan file plus, at most, new task
  files. No existing module, caller or test is touched.

### Goal-achievement risk: low
- **The task body carries premises that have already gone stale, and answering
  from them would certify wrong facts as retrospective findings.** Two of them
  are confirmed stale in this pass alone: `t597_4` is named as an "existing
  TODO" but landed and is archived (`CHANGELOG.md:1215`), and the `~0.3%` /
  "26 of ~1828" figures were removed from the rendered surface by t1590. A
  retrospective is a durable record — a wrong number in it outlives the
  session. · severity: low (residual — addressed by inline pre-phase
  `premise_recheck`, which forces a holds/stale verdict on every premise before
  it can be used) · → mitigation: inline pre-phase premise_recheck
- **Findings may be filed as new tasks that duplicate the five open
  anchor-1544 follow-ups** (t1585, t1579, t1591, t1584, t1567). Duplicate
  filing inflates the very backlog whose growth t1544 exists to measure, and
  the Deliverable's "folded into tN" disposition exists precisely to prevent
  it. · severity: low (residual — addressed by inline pre-phase
  `existing_followup_sweep`, which requires naming why no listed task covers a
  finding before a new one may be filed) · → mitigation: inline pre-phase
  existing_followup_sweep
- **Q5 and Q6 are answerable only by live measurement, and are the easiest to
  answer shallowly from source.** Q5 (TUI shape at real cardinality) is the
  parent plan's self-declared main unproven risk; reading `_LEVEL_ROW_CAP = 6`
  in the source proves nothing about whether the pane is legible at live
  category counts. Q6 needs a real `ait stats-tui` boot across the 7 registered
  repos. · severity: low (residual — addressed by inline pre-phase
  `live_surface_measurement`, which requires observed pane output and timings)
  · → mitigation: inline pre-phase live_surface_measurement

### Planned mitigations
- timing: pre-phase | name: premise_recheck | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — stale task-body premises certified as findings | desc: Re-verify every factual premise the task body asserts and record holds/stale before any question is answered.
- timing: pre-phase | name: existing_followup_sweep | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — findings duplicating the open anchor-1544 follow-ups | desc: Build an explicit question-to-existing-task map over the open anchor-1544 tasks that every disposition must consult before filing anything new.
- timing: pre-phase | name: live_surface_measurement | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — Q5/Q6 answered from source instead of live measurement | desc: Boot ait stats-tui against the real corpus and time collect_stats across the 7 registered repos so Q5/Q6 quote observed output.
