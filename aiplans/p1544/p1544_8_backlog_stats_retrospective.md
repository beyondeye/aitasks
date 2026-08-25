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

## Retrospective findings

### Measurement snapshot

| field | value |
|---|---|
| measured (UTC) | 2026-08-25 09:13–09:30Z |
| code-branch HEAD | `26c4b7781` (advanced from `6e91f5d28` mid-pass — t1595 landed) |
| task-data HEAD | `f1b0070a3` at snapshot; later commits are this task's own |
| live tasks | 326 parents + 120 children |
| archived tasks | 1864 scanned (incl. `_b0/old*.tar.zst` bundles) |
| registered projects | 7, from `~/.config/aitasks/projects.yaml`; each measured individually below |
| concurrent activity | a second agent session was active in this repo throughout |

**The corpus moved during the pass, as §C2 anticipated.** Two renders minutes
apart gave `TOTAL OPEN` 440 then 439, and `Bug Fixes` 18 then 17. Level/flow
numbers below are the **439** reading unless stated. This is recorded rather
than smoothed: it is the measurement's real precision.

### Premise re-check (pre-phase `premise_recheck`)

| premise asserted by the task body | verdict | measured |
|---|---|---|
| `t597_4` is an "existing TODO" | **stale** | landed and archived (`CHANGELOG.md:1215`); never made the week start configurable |
| clocks disagree for "~0.3%" / "26 of ~1828 by a day, 6 by a week" | **holds** | 27 of 1861 by date (1.45%), **6 by week bucket (0.32%)** |
| "~29 of ~300 open parents are coordination shells" | **holds** | 31 of 320 (9.7%) vs 29/300 (9.7%) — see Q3 on comparability |
| "9 live Postponed (~2%)" | **holds** | 10 of 439 open (2.3%) |
| "0.15s of added work over ~2250 files" | **holds** | +0.165 s median on this repo (+98%) |
| "17 distinct categories" | **holds exactly** | 17 in the flows; 15 render (2 all-zero series are filtered) |

### Existing-task map (pre-phase `existing_followup_sweep`)

By anchor (`anchor: 1544`): t1585, t1579, t1591, t1584, t1567 open; t1577,
t1586, t1590 archived. By concept (`with_backlog`, `week_start`,
`resolve_week_start`, `preset`, `deep_merge`, `collect_stats`, `completed_at`,
`resolve_completion_date`, `stats_config`) across the live **and** archived
corpus: no additional covering task. Every disposition below was checked against
this map.

---

### Q1 — Was flows-only storage the right shape?

- **Did any consumer want a stored level?** No. Both surfaces derive at render
  time; no stored level exists anywhere.
- **Did the O(k) suffix-scan stay cheap?** Yes, decisively. Median
  `backlog_levels` over the live flows (261 arrival / 234 departure keys):
  **0.08 ms at 8 weeks**, 0.10 ms at 26, 0.15 ms at 52 — i.e. **0.02 %** of the
  333 ms `collect_stats` it sits inside, and sub-linear in the horizon.
- **Did the `out_offsets` contract survive a second caller?** Yes — and the
  second caller now exists. t1586 extracted `build_backlog_axis` into
  `lib/backlog_view.py`, which calls `backlog_levels` **three times** (category,
  scope, aggregate), every call passing `offsets` as output-column selection
  only. The horizon-restricted cumulation bug was **not** re-introduced, and the
  docstring's warning is intact at `lib/stats_data.py:309-317`.

`Evidence:` source inspection (`lib/stats_data.py:301`, `lib/backlog_view.py:129`) + timings above.
`Disposition:` **no change needed**.

### Q2 — Is 8 weeks the right default horizon?

- **What do people actually pass?** `Evidence: none — no source exists.`
  Nothing records `ait stats` invocations or flags; `--backlog-weeks` goes
  straight into `argparse` (`aitask_stats.py:212-216`). **This is not evidence
  that the default is never overridden**, and nothing below rests on it.
- **Does the 80-column compromise hold?** Exactly. The default table renders at
  **precisely 80 characters**; at 26 weeks it is **206** — unusable in an
  80-column terminal, which is what `--backlog-weeks` is for.
- **Does 8 weeks truncate the interesting part?** Partly, and it depends on the
  question. The 26-week series runs **37 → 439**; the 8-week window opens at
  165, so it shows the acceleration but not the baseline or the regime change at
  W-5 (243 → 325). For the motivating question — "do we need a consolidation
  push?" — 8 weeks answers emphatically (backlog nearly tripled, NET positive
  every single week). For "when did this start?", it does truncate.
- **Does the TUI want a different value?** No evidence it does; it reads the
  same constant, and the shared constant is pinned by
  `tests/test_stats_backlog_panes.py:231-250`.

Filing an instrumentation task to close the first bullet was considered on the
merits and rejected: the framework has **no** CLI-invocation telemetry at all,
so this would be a new subsystem built for one flag, and the default is already
shown to satisfy both its design constraint (80 columns) and its purpose.

`Evidence:` rendered output at both horizons; `argparse` source for the gap.
`Disposition:` **no change needed** — noting the first sub-question rests on
`Evidence: none` and is therefore **not** a finding that 8 is the right value,
only that nothing contradicts it.

### Q3 — Is parent + child the right denominator?

Current headline: **`TOTAL OPEN` 439, split `of which parents` 319 /
`of which children` 120**, rendered on both surfaces.

- **Does the headline mislead?** The split does its job: the two sub-rows are
  adjacent to the total on every render, so "439" is never presented without its
  composition.
- **Has the coordination-shell ratio moved?** Under **predicate P** (a live
  parent `tN` is a shell iff `aitasks/tN/` holds ≥1 child task file):
  **`|P| = 31`** — an exact, population-wide **upper bound** — against 320 open
  parents, i.e. 9.7 %.
- **Over-count estimate (separate, sampled):** members sorted ascending,
  systematic every-`k`-th with `k = floor(31/10) = 3` from the first element →
  n = 11: t259, t386, t417, t623, t745, t1076, t1149, t1162, t1210, t1357,
  t1555. **All 11 carry a non-empty `children_to_implement`**, the framework's
  own marker for a parent demoted to a parent-of-children. **Over-count ≈ 0 %
  (n = 11)** — P is a tight bound here.
- **Comparability:** the planning-time "~29 of ~300" was asserted at
  `aiplans/p1544_stats_backlog_and_net_flow_by_category.md:223` **with no
  recorded counting method**, and no corpus predicate for "coordination shell"
  exists in source (`coordination_only` in `board/aitask_board.py:638` is an
  agent-assigned trail classification, not a corpus predicate). 9.7 % vs 9.7 %
  is therefore **indicative, not a like-for-like delta** — but nothing suggests
  the ratio moved.

`Evidence:` rendered `TOTAL OPEN` rows; predicate-P scan; 11-member sample.
`Disposition:` **no change needed**.

### Q4 — Postponed counted as open — right call?

**10** live `Postponed` tasks against 439 open = **2.3 %** (planning time: 9,
~2 %). The share is flat, and 10 tasks cannot move a 439-task backlog enough to
change a consolidation decision. A separate row or a netting-out would add a
surface for a rounding error.

`Evidence:` live corpus scan.
`Disposition:` **no change needed**.

### Q5 — Did the TUI presentation hold up at real cardinality?

This was the parent plan's self-declared main unproven risk. Measured live via
`App.run_test` against the **real** corpus at a stated viewport of **120 × 40**,
entering `backlog.level` then `backlog.netflow`.

- **Cardinality:** 17 distinct categories in the flows; 15 with a non-zero level
  (`qa_test_gap` and `style` are all-zero and filtered by `build_backlog_axis`).
- **Level pane:** `DataTable` of 9 columns × **17 rows**, region height 18
  inside a content height of 36 — no clipping, no overflow, and the
  single diagnostic `Static` renders its one line.
- **The row cap is per block, not per table** (`_cap_block`,
  `stats/panes/backlog.py:84`). Follow-ups: 6 categories ≤ `_LEVEL_ROW_CAP = 6`
  → **all shown, no `Other` row at all**. Genuine: 8 > 6 → 5 shown
  (Features 111, Documentation 29, Enhancement 27, Bug Fixes 17, Chores 12)
  plus **`Other` = 27**.
- **Acceptance rule (written before observing):** the cap is adequate only if
  `Other` conceals no category outranking a displayed row. Highest concealed is
  **Tests 10**; lowest shown is **Chores 12**. **The rule passes — but by 2
  tasks.** Worth stating plainly: the aggregate `Other` (27) is larger than the
  three lowest shown rows, so the cap is reconcilable (`shown + Other ==
  subtotal`) but close to the point where a reader would want one more row.
- **Net-flow split:** 5 series + `Other`, and they **are** individually
  distinguishable — the chart carries **5 distinct ANSI colours** (9, 10, 12,
  13, 14), one per series. An earlier read of this as "illegible" was an
  artifact of capturing `.plain`, which strips exactly the attribute that
  carries the distinction; in a colour terminal the split reads fine. The
  residual caveat, recorded not filed: in monochrome, or in copied/pasted text,
  every series is the same `██` glyph and the split conveys nothing.
- **Did either pane need a shape the plan did not anticipate?** No. t1588
  reordered columns chronologically with `Now` last after the plan was written;
  both panes and the CLI share that ordering.

`Evidence:` live `App.run_test` render at 120×40 against the real corpus; span-style inspection for colour.
`Disposition:` **no change needed**.

### Q6 — Did the doubled `collect_stats` cost matter?

Protocol: `collect_stats` timed in-process with `perf_counter` (excludes
interpreter start and rendering); one discarded warm-up per repo per condition,
then 5 measured runs; the two `with_backlog` conditions run **back-to-back per
repository**; median with min–max. All figures are **warm-cache**. No run
exceeded 2× its repo median, so no outlier flags. A second agent session was
active throughout — the pairing is what protects the delta from that.

| repo | `with_backlog=True` | `False` | delta |
|---|---|---|---|
| aitasks | 0.333 s (0.321–0.356) | 0.168 s (0.154–0.175) | +0.165 s (+98 %) |
| thinking_app | 0.103 s (0.101–0.108) | 0.059 s (0.057–0.061) | +0.044 s |
| thinking_backend | 0.024 s | 0.011 s | +0.013 s |
| aitasks_go | 0.020 s | 0.009 s | +0.011 s |
| aitasks_mobile | 0.014 s | 0.007 s | +0.007 s |
| teamim | 0.002 s | 0.001 s | +0.001 s |
| timexchange | 0.001 s | 0.001 s | ~0 |
| **sum of medians** | **0.497 s** | **0.256 s** | **+0.241 s (+94 %)** |

All 7 registered repositories were reachable and had task data; none errored.

- **Did it matter?** The doubling is real and matches the planning-time
  estimate (+0.165 s here vs "0.15 s" predicted). In absolute terms a
  multi-repo user pays **+0.241 s once per session** — below the threshold that
  would justify work.
- **Multi-repo shape, measured:** `stats_app._load_data` collects **every**
  session on mount, not just the selected one, because the `session_breakdown`
  loop calls `_stats_for(s)` for all sessions (`stats/stats_app.py:343-348`).
  Results are memoised in `_session_cache`, so it is once per session, not per
  pane switch.
- **Was `with_backlog=False` on `work_report_gather` sufficient, or *can*
  another caller benefit?** A second caller genuinely could: that
  `session_breakdown` loop reads only `daily_counts`, `tasks_7d` and `tasks_30d`
  — none backlog-derived. But it is **not free**: `_stats_for` shares
  `_session_cache` with the pane data path, which *does* need backlog, so
  passing `False` there would poison the cache for whichever session is
  selected. Recorded as a real but non-trivial opportunity, not filed — the
  measured prize is a fraction of 0.241 s.
- **Does anyone *want* it?** `Evidence: none.` The concept search over the live
  and archived corpus found `with_backlog` named only in t1585, archived
  t1544_3, and this task — no report, issue or task asks for it.
- **Is the no-live-walk opt-out worth filing?** Not on this data. The related
  cost concern already has an open, more specific owner in **t1585** (memoise
  `resolve_category`, +62 ms / +25 % on the CSV path).

`Evidence:` per-repo paired timings above; `stats_app.py:320-356` source; concept search for demand.
`Disposition:` **no change needed** (cost concern already owned by **t1585**).

### Q7 — Two completion clocks — did anyone get confused?

Re-measured across the whole archived corpus (1864 tasks; 1861 dated by both
clocks): **27 differ by date (1.45 %)** and **6 differ by ISO week bucket
(0.32 %)**. Planning time recorded 26 by a day and 6 by a week (~0.3 %) — so
over five weeks and ~36 further archived tasks the by-week count is **unchanged
at 6**.

- **Did the footnote do its job, or generate questions?** `Evidence:` the task
  corpus. It generated exactly one downstream item — **t1590** — and that was a
  *maintenance* finding (the footnote asserted a frozen `~0.3%` literal that
  nothing recomputed), not a user asking which clock applied. t1590 has since
  landed, replacing the number with the behavioural invariant. Confusion that
  never reached a task is **unmeasurable**, and nothing here rests on its
  absence.
- **Is converging the two clocks worth a task?** No. Six tasks in 1861, static
  over five weeks, and the divergence is deliberate: the backlog sections need
  `completed_at` to meet the task's stated definition. Note also that the
  literal t1590 removed had not in fact rotted — which does not make removing it
  wrong (an unmaintained number is unmaintained whether or not it has drifted
  yet), but is worth recording accurately.

`Evidence:` full archived-corpus re-measure; task-corpus search for downstream items.
`Disposition:` **no change needed** (footnote already fixed by **t1590**).

### Q8 — Deferred items that may now be worth filing

**(a) Preset list-replacement semantics.** Population inventoried, and it is
**empty by every reachable route**: 0 of the 7 registered projects pin any
preset — six have no `aitasks/metadata/stats_config.json` at all, and this
repository's is `{}` after t1590 removed the redundant pins — while `seed/`
ships no such file, so a newly set-up project pins nothing either. With nothing
pinned, merge-instead-of-replace would produce **identical effective pane lists
everywhere today**; the change would be all risk and no observable benefit. The
hazard is real but latent, and its trigger is precise: the first time any
project pins a preset in that JSON. t1590 additionally left a guard
(`test_no_shipped_json_pin_duplicates_a_code_default`) that stops the redundant
form coming back.

`Evidence:` inventory of all 7 registered projects + `seed/`; `stats_config.py:17-24`.
`Disposition:` **no change needed**.

**(b) `week_start` / `days` persisted but never read — and a stale premise.**
Both keys are in `_USER_KEYS` (`stats/stats_config.py:30-35`) and saved, but
nothing reads them; the TUI hardcodes Monday. The task body attributed this to
"existing TODO t597_4" — **that premise is wrong**: t597_4 landed and is
archived (`CHANGELOG.md:1215`) without making the week start configurable, yet
`stats/panes/overview.py:13` and `stats/panes/backlog.py:12` still name it as
pending. Two source comments therefore claim tracked work that nothing tracks.
Checked against the existing-task map: t1584 covers `aitask-stats` SKILL.md
drift and t1591 covers website-doc↔source count drift; **neither covers source
comments naming a landed task**, so this is not a duplicate.

`Evidence:` `CHANGELOG.md:1215`; the two source comments; existing-task map.
`Disposition:` **filed as t1600**.

**(c) `created_at` on the per-task CSV.** Added for lead-time analysis; open
tasks are not rows in that export, so it does not serve backlog. **No in-repo
consumer reads it back** — nothing reads the CSV at all (`aitask_stats.py:743`
is the writer; `artifact_manifest.py`'s `created_at` is unrelated artifact
metadata). Ad-hoc human use is **unmeasurable**, and per the task body's own
instruction the column is noted rather than removed.

`Evidence:` in-repo consumer grep; task-body instruction.
`Disposition:` **no change needed**.

---

### Summary

Eight questions, eight dispositions: **seven "no change needed", one filed
(t1600)**. Two questions credit work that landed while this retrospective was
pending — **t1590** (Q7 footnote, Q8a redundant pins) and **t1586** (Q1's second
caller) — and one defers to an already-open owner, **t1585** (Q6 cost). That is
the expected shape for an evaluation task: the design commitments t1544 made
under partial information have held up, and the one genuinely new defect is a
pair of stale source comments, not a design error.


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

## Final Implementation Notes

- **Actual work done:** Exactly the planned evaluation — no production code. The
  three inline pre-phases ran first (`premise_recheck`, `existing_followup_sweep`,
  `live_surface_measurement`), then all eight questions were answered into
  `## Retrospective findings` with an `Evidence:` line and one of the three
  allowed dispositions each. Ten dispositions total (Q8 has three sub-items):
  nine "no change needed", one "filed as t1600".
- **Deviations from plan:** None in scope or method. One correction mid-pass:
  the net-flow chart was first read as illegible from a `.plain` capture, which
  strips the ANSI colour that distinguishes the series. Re-inspecting the render
  spans showed 5 distinct colours (ansi 9/10/12/13/14), one per series, so the
  split does hold up. The finding records both the corrected verdict and the
  residual monochrome/copied-text caveat.
- **Issues encountered:**
  - The corpus moved during the pass, exactly as §C2 anticipated: `main`
    advanced from `6e91f5d28` to `26c4b7781` (t1595 landed in a concurrent
    session), and two renders minutes apart gave `TOTAL OPEN` 440 then 439.
    Recorded in the measurement snapshot rather than smoothed away.
  - Two harness bugs in my own measurement scripts, both fixed before any number
    was recorded: `collect_stats(project_root=...)` needs a `Path`, not a `str`,
    and `iter_archived_markdown_files()` yields `(name, content)` pairs, not
    triples.
- **Key decisions:**
  - Predicate P for Q3 (`aitasks/tN/` holds ≥1 child file) was defined here
    because the planning-time "~29 of ~300" has **no recorded counting method**
    and no corpus predicate for "coordination shell" exists in source. `|P|` is
    reported as an exact upper bound and the over-count as a separately labelled
    systematic sample (k=3, n=11), never blended.
  - An instrumentation task for Q2's override question was considered and
    rejected on the merits: the framework has no CLI-invocation telemetry at
    all, so it would be a new subsystem for one flag.
  - Q6's `session_breakdown` opportunity (the loop reads only completion-derived
    fields, so it could take `with_backlog=False`) was recorded but **not**
    filed: `_stats_for` shares `_session_cache` with the pane path that does need
    backlog, and the measured prize is a fraction of 0.241 s.
- **Upstream defects identified:**
  - `.aitask-scripts/stats/panes/overview.py:13` — `_WEEK_START_DOW = 1  # Monday; t597_4 will make this configurable.` names a task that landed and is archived (`CHANGELOG.md:1215`) without making the week start configurable; the comment claims tracked work that nothing tracks. Filed as t1600.
  - `.aitask-scripts/stats/panes/backlog.py:12` — forwards to that same stale `t597_4` TODO. Filed as t1600.
  - `.aitask-scripts/stats/stats_config.py:30-35` — `week_start` and `days` are persisted via `_USER_KEYS` but read by nothing; the TUI hardcodes Monday. Written-but-ignored config. Covered by t1600.
