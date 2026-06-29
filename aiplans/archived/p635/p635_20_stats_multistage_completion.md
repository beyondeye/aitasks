---
Task: t635_20_stats_multistage_completion.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_21_gate_ledger_merge_safety.md
Archived Sibling Plans: aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md
Base branch: main
---

# t635_20 — Stats redesign for multi-stage completion

## Context

`ait stats` (CLI text/CSV via `aitask_stats.py`) and `ait stats-tui` (Textual app
`stats_app.py`) both consume `collect_stats()` in `.aitask-scripts/stats/stats_data.py`,
which assumes work on a task is a single linear pass ending in archival:

1. It iterates **archived task files only** (`iter_archived_markdown_files`), and
2. dates each task via `parse_completed_date` — `completed_at`, falling back to
   `updated_at` for status `Done` (`stats_data.py:229`).

The gate framework breaks both assumptions (roadmap Phase 3, D5/D6):

- **Deferred archival (t635_4):** a task can be implementation-complete but
  unarchived for days while human/async gates pend. It is invisible to stats (not
  archived), and when it finally archives, `completed_at`/`updated_at` reflect the
  *archive* moment, not when the work happened — so daily/weekly counts silently
  shift and dip.
- **Multi-stage work:** "completed" is ambiguous — implemented? reviewed?
  all-gates-pass? archived? — and the `## Gate Runs` ledger now records a
  per-checkpoint `run=<ISO-8601-Z>` timestamp for each (`plan_approved`,
  `review_approved`, `merge_approved`, …) that pins when each milestone actually
  occurred.

The `fast`/`default` profiles already run with `record_gates: true`, so these
ledger timestamps exist on tasks completed **today** — the dating fix has live
data immediately, even before async human gates make deferral common.

This task does a **design pass** (a contract doc under `aidocs/gates/`) and then
implements the agreed scope in **both** `ait stats` and the stats TUI. Reuse the
shared Python ledger parser (`lib/gate_ledger.py`, t635_8) — **no forked gate
parsing in stats code** (D6).

## Scope (confirmed with user)

- **In:** ledger-aware completion dating; an "in-flight (impl done, gates pending)"
  secondary series; a **time-in-phase** aggregate.
- **Deferred to a follow-up task** (created in Step 8c/manual or noted): per-gate
  **pass/fail/retry-rate** analytics and **pending-human-wait** metric. These are
  data-sparse today (most gates record only a final `pass`) and add a full
  table + pane each. The design doc specifies them so the follow-up is turnkey.

## Key design decisions (rationale + rejected alternative)

### D-1. Completion date = ledger-derived, by precedence; headline COUNT stays the archived population

`collect_stats` keeps iterating the **archived** population (continuity — the
"Total / Last 7d / Last 30d" headline numbers do not jump or change definition for
existing users). What changes is the **date** each archived task is bucketed under.
New resolver precedence (first hit wins):

1. `merge_approved` ledger run timestamp — the shared/canonical "landed in main"
   event. **Primary** (per user: the date that is meaningful for *all* users once
   pushed, not just the local reviewer).
2. `review_approved` ledger run timestamp — fallback when no merge marker exists.
   This is the case on **current-branch profiles** (`fast`): Step 9 records
   `merge_approved` only under the "separate branch was created" path, so a
   current-branch task has `review_approved` (Step 8 commit) but no
   `merge_approved`. On the current branch the reviewed commit *is* the landing.
3. `completed_at` frontmatter — today's primary (pre-gates / no-ledger tasks).
4. `updated_at` (status `Done`) — today's final fallback.

So the cutover is **per-task and automatic**: a task with no `## Gate Runs` ledger
(`has_gate_markers` false) dates exactly as today; a gated task dates by when its
work landed, even if archived days later. This directly fixes the "shift and dip":
once a deferred task finally archives, it back-fills the *correct* historical day.

**Pass-only markers (resolver-only, per user):** a `merge_approved`/`review_approved`
marker is used for dating **only when its *current* derived status is `pass`**
(`derive_gate_runs` is last-wins, so a `fail`→`pass` retry correctly counts via its
final `pass`, while a marker left currently `fail`/`error` is skipped and the next
precedence rung is tried). This is a **resolver-only** rule — there is **no
whole-task exclusion**: an archived task carrying an unrelated lingering failure
(e.g. a `build_verified: fail` that proceeded anyway in Step 9) still stays in
`Total`/the archived series and is still ledger-dated by its *passing*
`review_approved`/`merge_approved`. Only the completion-date pick (and the D-3 span
endpoints) skip non-`pass` markers; the count is untouched.

- *Why precedence, not a config knob?* The user weighed `review_approved` (local
  milestone) vs `merge_approved` (shared milestone) and it's a genuine tension.
  The precedence **resolves** it rather than forcing one: prefer the shared event,
  fall back to the local one only where the shared one cannot exist. A
  `completion_event:` config key was rejected — its only effect would be shifting
  dates by hours/days, and the ledger-derived date is strictly more accurate than
  archive time, so there is no real use case for choosing "archive time".
- *Why not "last gate pass"?* A late async human gate (t635_15) would push the date
  well past the actual work — the opposite of the goal.
- *Why keep the COUNT on the archived population?* Folding in-flight tasks into the
  headline would (a) break continuity of "Total", (b) double-count when the task
  later archives, (c) conflate "done" with "done-but-gated". Kept separate — see D-2.

### D-2. In-flight "completed, awaiting gates" = a SEPARATE secondary series

Add a distinct series, never summed into the archived totals, sourced from
**active** (non-archived) task files. A task qualifies as in-flight-complete iff
(classified via the shared parser `read_task_gate_state`):

- `has_gate_markers` is true, AND
- `review_approved` is `pass` (implementation reviewed/committed), AND
- `archive_decision == "BLOCKED"` (a declared gate is not yet `pass` — i.e. the
  task is being *held back* by t635_4's gate guard, not merely mid-implementation).

This is exactly t635_4's deferred-archival state. Tasks that are `Implementing`
with only `plan_approved` (work not done) are **excluded** — they are not
"completed". The series is dated by each task's `review_approved` timestamp.

- *Rejected:* merging into the headline (see D-1); or sourcing from `status`
  frontmatter alone (a `status: Implementing` task may be mid-work OR done-but-gated
  — only the ledger distinguishes them).
- Today this series is usually **empty** (the only default gate, `risk_evaluated`,
  passes at planning time, so nothing defers). It becomes populated once human/async
  gates (t635_15, `docs_updated` t635_19) enter the picture. It renders gracefully
  as `0` / "No in-flight tasks" until then — the honest "no data yet" path.

### D-3. Ledger-enabled metric (this task) = time-in-phase aggregate — **ledger timestamps only**

Compute spans **exclusively from `## Gate Runs` `run=` timestamps** (uniform
UTC second-precision), and surface aggregates (count `N`, median, mean) over the
tasks that have *both* endpoint markers. **No archival-date fallback in the timing
metric** — that is the key correction below.

- **Implement span:** `plan_approved` → `review_approved` (both markers required,
  **both current status `pass`**).
- **Review→Merge span:** `review_approved` → `merge_approved` (**both markers
  required and `pass`; computed only when `merge_approved` exists**). Renamed from
  the earlier "verification span" and **deliberately scoped to merge profiles**.

A non-`pass` endpoint marker drops that task from *that span's* sample (consistent
with D-1's pass-only, resolver-only rule) — never from the task count.

**Why no archival fallback (resolves the high-severity self-contradiction with
D-1):** D-1 establishes that current-branch tasks (`fast`) have **no
`merge_approved`** and complete at `review_approved`. Today's real archived gate
data is overwhelmingly `review_approved`-only. If the second span fell back to the
*archival date* it would (a) measure **post-review archival delay**, not
verification, and (b) mix a second-precision UTC ledger timestamp with a
**day-granular** archival `date` (`resolve_completion_date` returns a `date`;
`completed_at` is minute-precision *local* time). So a review-only / current-branch
task contributes a sample to **Implement span only** and **no sample** to
Review→Merge span (it is *not* recorded as zero — zero would bias the median). Each
span reports its own `N`, so the sample base is explicit and the two profiles never
blend semantics. (D-1 dating may still fall back to the archival `date` — dating is
day-granular by design; the *timing metric* must not.)

- *Rejected (for this task):* a "planning" span (`created_at` → `plan_approved`) —
  dominated by how long a task sat `Ready` before pickup; noise, not signal.
- *Deferred (design doc only):* per-gate pass/fail/retry table + pending-human-wait.

### D-4. Continuity / mixed-population honesty

- Pre-gates archived tasks (no ledger) date via the legacy fallback (D-1 steps 3-4)
  — **no flag day**, no behavior change for users who have not adopted gates.
- The time-in-phase section and the in-flight card **show their `N`** (e.g. "based
  on 12 gated tasks") so a small gated sample is never mistaken for the whole
  population.
- The headline COUNT is unchanged (archived population), so existing dashboards read
  identically until gates are adopted.

### D-5. Derivation location — extend `stats_data.py`, import from `gate_ledger.py`

All new derivation lives in the pure data layer (`stats_data.py`), consumed by both
the CLI and TUI. **No forked parsing** — call `gate_ledger.parse_gate_run_blocks` /
`read_task_gate_state` (D6). `parse_completed_date` is **kept intact** (still the
no-ledger fallback and still covered by existing tests); the new resolver wraps it.

## Deliverables (file by file)

### 0. Shared parser — `.aitask-scripts/lib/gate_ledger.py` (small additive extension)

Add a **content-based** public wrapper so stats can classify a task from its file
content without opening a path (deterministic under `project_root` rebasing and in
tests — see D-2 path concern):

```python
def archive_status_from_text(text: str) -> tuple[str, list[str]]:
    """Content-level twin of archive_status() — no filesystem open."""
    return _archive_status_from_state(
        read_declared_gates_from_text(text), derive_gate_runs(text))
```

This mirrors the existing path-based `archive_status` (line 687) and the existing
content-based `read_declared_gates_from_text` (line 392); it forks no parsing (D6),
just composes the shared primitives. Add a unit case to
`tests/test_gate_ledger_python_parser.py` (NO_GATES / ALL_PASS / BLOCKED from text).

### 1. Data layer — `.aitask-scripts/stats/stats_data.py`

- **Import the shared parser** (lib is already on `sys.path`, line 21-24):
  `from gate_ledger import parse_gate_run_blocks, derive_gate_runs, has_gate_markers, archive_status_from_text`.
  (Use **content-level** primitives only — never the path-opening `read_task_gate_state`
  in the active scan; see D-2 path concern.)
- **`resolve_completion_date(content, frontmatter) -> Optional[date]`** — the D-1
  resolver. If `has_gate_markers(content)`: derive `{gate: GateRun}` (last-wins) via
  `derive_gate_runs`; take the `merge_approved` run ts **iff its `.status == "pass"`**,
  else the `review_approved` run ts **iff `.status == "pass"`**; parse `run`
  (ISO-8601-Z → `date`, slice `[:10]` like the existing code). If neither qualifies
  (absent or not `pass`), or no markers, fall back to
  `parse_completed_date(frontmatter)`. (Pass-only, resolver-only — no whole-task drop.)
  Add a small `_ledger_ts_to_date(run_id)` helper (`date.fromisoformat(run_id[:10])`,
  `ValueError` → None), mirroring `parse_completed_date`'s defensive slice.
- **`iter_active_markdown_files(project_root=None) -> Iterable[Tuple[str,str]]`** —
  walk `<task_dir>` (from `_paths_for`) for `t*.md`, **excluding** `archived/` and
  `metadata/`. Sibling to `iter_archived_markdown_files`; reuse `_paths_for`. Yields
  `(filename, content)` where `content` is read directly from the resolved path —
  so classification needs **no second open** (it operates on `content`), and the
  scan is correct under a rebased `project_root` / `TASK_DIR` (D-2 concern).
- **`InflightData` dataclass** + **`collect_inflight(today, week_start_dow,
  project_root=None) -> InflightData`** — iterate active files; classify **purely
  from `content`** (no path open): `has_gate_markers(content)` →
  `derive_gate_runs(content)` to check `review_approved` is `pass` →
  `archive_status_from_text(content)[0] == "BLOCKED"` (D-2). Collect count + per-day
  counts (by the `review_approved` `run=` ts) + ids. Empty-safe.
- **`PhaseTimings` dataclass** + compute in `collect_stats` (D-3): for each archived
  task, from its ledger `run=` timestamps only, accumulate an **implement-span**
  delta when both `plan_approved` and `review_approved` exist **and are `pass`**, and
  a **review→merge-span** delta **only when `merge_approved` also exists and both are
  `pass`** (no archival fallback). Store the two sample lists separately (for median/mean + per-
  span `N`). Add `phase_timings: Optional[PhaseTimings]` and
  `inflight: Optional[InflightData]` fields to `StatsData` (defaulted `None` so
  `merge_stats_data`/`_empty_stats_data` and existing constructors stay valid;
  extend both to sum/union the new fields — `merge_stats_data` concatenates the
  span sample lists and sums the in-flight counters).
- **`collect_stats`** — switch the per-file dating from `parse_completed_date(fm)`
  to `resolve_completion_date(content, fm)` (content is already in scope, line 818);
  accumulate `PhaseTimings`; attach `inflight` via `collect_inflight`. Everything
  else (labels/agents/dow/csv) unchanged — only the *date* source moves.

### 2. CLI report — `.aitask-scripts/aitask_stats.py`

- Re-export the new names in the `stats_data` import block + `__all__` (the module
  re-exports its data-layer surface, lines 31-100).
- **Summary table** (`render_text_report`, ~line 219): add a row
  `| In Flight (impl done, gates pending) | <N> |` from `data.inflight`.
- **New section `### Pipeline Timing (gated tasks)`** after the day-of-week section:
  a small table with one row per span — **Implement** (`plan_approved`→`review_approved`)
  and **Review→Merge** (`review_approved`→`merge_approved`, merge profiles only) —
  each showing median, mean, and its **own** sample `N` (D-4 honesty; the two spans
  legitimately have different `N`, e.g. current-branch tasks count toward Implement
  but not Review→Merge). Print "No gated tasks with ledger timing yet." when both
  `N == 0`; print a per-row "—" when only that span has no sample.
- CSV: unchanged (per-archived-task rows; dating already flows through
  `resolve_completion_date`). No new CSV columns this task.

### 3. TUI — `.aitask-scripts/stats/panes/` + `stats_app.py`

- **Overview summary card** (`panes/overview.py` `_render_summary`, line 18): append
  a card `("In flight", stats.inflight.count if stats.inflight else 0)`.
- **New pane `panes/pipeline.py`** — category `"Pipeline"`, registering
  `pipeline.timing` (time-in-phase: a small bar/summary via `render_chart` or a
  `Static` table) and `pipeline.inflight` (in-flight per-day, or an empty_state).
  Follow the `overview.py` pattern exactly (`register(PaneDef(id, title, category,
  fn))`, `empty_state` when `N == 0`).
- **Register the module** in `panes/__init__.py` side-effect import line
  (`from . import overview, labels, agents, velocity, sessions, pipeline`).
- **Default layout — update BOTH config files** (config is layered: `stats_config.py`
  is verified to `load_layered_config(METADATA_FILE, defaults=DEFAULTS)`, and the
  shipped **`aitasks/metadata/stats_config.json` carries its own full `presets`
  dict that overrides the Python `DEFAULT_PRESETS`**). Editing only Python would
  register the panes but never surface them. So add a new
  `"pipeline": ["pipeline.timing", "pipeline.inflight"]` preset to **both**:
  - `stats/stats_config.py` `DEFAULT_PRESETS` (the no-metadata-file fallback), and
  - `aitasks/metadata/stats_config.json` `presets` (the authoritative shipped layer).
  The new "pipeline" preset becomes a sidebar layout entry; panes are also always
  reachable via `PaneSelectorModal` (lists all `PANE_DEFS`). The in-flight overview
  *card* needs no layout change (it rides on the already-default `overview.summary`).
  During impl, confirm `load_layered_config`'s merge granularity (deep vs shallow on
  `presets`) — updating both files is correct under either.

### 4. Design doc — `aidocs/gates/stats-multistage-completion.md` (new)

Contract doc mirroring sibling design-doc frontmatter
(title/category/tags/sources/confidence/created/updated; see
`gate-guarded-archival.md`). Covers all five design questions from the task:
completion-event precedence (D-1) + rationale for merge-over-review + rejected
config knob; in-flight separate series + classifier (D-2); time-in-phase (D-3) and
the **deferred** per-gate-rate / pending-wait metrics (full spec so the follow-up is
turnkey); continuity/mixed-population rules (D-4); derivation-location / no-fork
rule (D-5). Add a `[[stats-multistage-completion]]` back-link from
`integration-roadmap.md` Phase 3's stats bullet.

### 5. Tests

Extend `tests/test_aitask_stats_py.py` (Python, the richer harness) — or add
`tests/test_stats_multistage.py` if cleaner — covering:

- **`resolve_completion_date` precedence:** ledger with `merge_approved` → its date;
  ledger with only `review_approved` (no merge) → its date; ledger with both →
  merge wins; no markers → `completed_at`; `Done` + no `completed_at` → `updated_at`
  (regression parity with `parse_completed_date`).
- **Pass-only resolver (resolver-only):** `merge_approved` currently `fail` but
  `review_approved` `pass` → dates by `review_approved` (skips the failed marker);
  `merge_approved` `fail`→`pass` retry (last-wins `pass`) → dates by `merge_approved`;
  a task with a lingering unrelated `build_verified: fail` but passing
  `review_approved` → still ledger-dated and still counted (no whole-task drop).
- **In-flight classifier:** active task with `review_approved` pass + a declared
  pending gate (`archive_decision` BLOCKED) → counted; `Implementing` with only
  `plan_approved` → excluded; archived task → never in the in-flight set (no
  double-count).
- **Time-in-phase (corrected D-3):** a task with all three stamps → contributes to
  both spans; a **review-only / current-branch** task (no `merge_approved`) →
  contributes to Implement span and is **absent** from the Review→Merge sample (not
  zero); per-span `N` reflects exactly the contributing tasks. Assert **no archival
  date** ever enters a span delta.
- **`archive_status_from_text`** (in `tests/test_gate_ledger_python_parser.py`):
  NO_GATES / ALL_PASS / BLOCKED derived from text, matching the path-based
  `archive_status`.
- **Back-compat regression:** an ungated archived task buckets on exactly the same
  date as before this change (proves the no-ledger path is untouched).

Keep `tests/test_stats_data.sh` green. Build fixtures as temp files with
hand-written `## Gate Runs` blocks (use the real marker format:
`> **✅ gate:review_approved** run=2026-06-21T15:50:11Z status=pass attempt=1 type=human`).

## Risk

### Code-health risk: medium
- `parse_completed_date` / `collect_stats` are the shared spine of every stats
  surface (CLI, TUI, CSV, multi-session merge) · severity: medium · → mitigation
  (in-task): **add** `resolve_completion_date` rather than mutating
  `parse_completed_date` (kept intact + still tested); new `StatsData` fields are
  `Optional` with `None` defaults so `_empty_stats_data`/`merge_stats_data`/all
  constructors stay valid; back-compat regression test asserts ungated tasks bucket
  identically.
- New active-task scan adds I/O and a second population that must never leak into
  the archived totals · severity: medium · → mitigation: `has_gate_markers`
  prefilter; strict series separation (in-flight is its own dataclass, never summed
  into `total_tasks`); double-count test. (Stats TUI is **not** on the board PyPy
  fast path, so no PyPy constraint.)
- New TUI pane + `panes/__init__.py` + **dual config-file** default-layout wiring
  (layered config — the metadata `stats_config.json` overrides Python defaults) ·
  severity: low · → mitigation: copy the proven `overview.py`/`base.py` register
  pattern; update **both** preset files; `empty_state` for the no-data path.
- Additive `archive_status_from_text` wrapper in the shared `gate_ledger.py`
  (t635_8 module) · severity: low · → mitigation: pure composition of existing
  primitives (no parsing fork, D6); its own unit case; the existing path-based
  `archive_status` is untouched.

### Goal-achievement risk: low
- UTC ledger stamps vs local `completed_at`/`updated_at` could shift a near-midnight
  task by one day · severity: low · → mitigation: date-only `[:10]` slicing (same
  granularity the code already uses); documented as an accepted approximation in the
  design doc.
- In-flight series is mostly empty until async/human gates land (t635_15/_19) ·
  severity: low · → mitigation: this is correct/honest behavior, not a defect;
  renders as `0`/empty-state; the dating fix (the immediate-value half) has live
  data now via `record_gates`.

### Planned mitigations
None — all risks are bounded and mitigated in-task by the test deliverables (no
separate before/after mitigation tasks warranted).

## Verification

1. `python tests/test_aitask_stats_py.py` (+ new multistage cases) and
   `bash tests/test_stats_data.sh` green.
2. `python -m py_compile .aitask-scripts/stats/stats_data.py
   .aitask-scripts/aitask_stats.py .aitask-scripts/stats/panes/pipeline.py`.
3. `./ait stats` renders the new Summary "In Flight" row + "Pipeline Timing"
   section against the real archive (no crash; honest `N`).
4. `./ait stats-tui` launches; Overview shows the In-flight card; the new Pipeline
   pane renders (timing chart + in-flight, or empty-state).
5. Smoke a synthetic deferred task (active file with `review_approved` pass + a
   pending declared gate): confirm it appears in the in-flight series and NOT in the
   archived totals; archive it and confirm it then buckets under its
   `merge_approved`/`review_approved` date.
6. macOS static sweep on any edited shell (none expected — all Python); no
   `grep -P`, etc.

## Follow-up (deferred, per scope)

Create a child/standalone task for the **deferred analytics** (per-gate
pass/fail/retry-rate table + pending-human-wait metric in CLI + a TUI pane), fully
specified in `aidocs/gates/stats-multistage-completion.md`. Offer at Step 8c.

## Step 9 reference

Post-implementation cleanup and archival follow the shared **Step 9
(Post-Implementation)** flow (`fast` profile — current branch, no worktree/merge).
This task's own archival: it declares the profile default gate `risk_evaluated`
(recorded `pass` at planning), so the gate guard lets it archive straight through.

## Final Implementation Notes

- **Actual work done:** Implemented all six deliverables as planned.
  `lib/gate_ledger.py` gained `archive_status_from_text()` (content-level twin of
  `archive_status`, no filesystem open). `stats/stats_data.py` gained
  `resolve_completion_date()` (pass-only, resolver-only ledger precedence
  merge_approved → review_approved → completed_at → updated_at),
  `iter_active_markdown_files()`, `InflightData` + `collect_inflight()`,
  `PhaseTimings` + ledger-timestamp-only span computation (`_accumulate_phase_timings`
  / `_span_hours`), `format_duration()` (shared by CLI + TUI), plus
  `_ledger_ts_to_date`/`_ledger_ts_to_datetime`; `collect_stats` dates via the
  resolver and attaches `inflight`/`phase_timings`; `_empty_stats_data` and
  `merge_stats_data` extended for the two new fields. `aitask_stats.py` re-exports the
  new surface, prints a Summary "In flight" line and a `### Pipeline Timing (gated
  tasks)` section (per-span N). TUI: overview "In flight" card, new
  `stats/panes/pipeline.py` (`pipeline.timing` + `pipeline.inflight`), registered in
  `panes/__init__.py`, and a `pipeline` preset added to BOTH `stats/stats_config.py`
  and `aitasks/metadata/stats_config.json`. New design doc
  `aidocs/gates/stats-multistage-completion.md` + roadmap backlink. Tests:
  `tests/test_stats_multistage.py` (22 cases) + a new `archive_status_from_text` case
  in `tests/test_gate_ledger_python_parser.py`.

- **Deviations from plan:** Minor surface choice — the in-flight figure renders as a
  note line under the Summary table (and an overview card) rather than a table row,
  since the label is wider than the fixed Summary column and a row would break
  plain-text alignment. Confirmed at impl time that `load_layered_config` `deep_merge`s
  the `presets` dict (either config file alone would surface the pane) but updated both
  as planned. `format_duration` was placed in `stats_data.py` (shared) rather than
  private to the CLI, so CLI and TUI format spans identically (no duplication).

- **Issues encountered:** None functional. An initial smoke ran from the wrong cwd
  (TASK_DIR is repo-relative) showing 0 tasks — re-ran from repo root (1479 archived,
  101 implement-span samples, 0 review→merge — current-branch records no merge).

- **Key decisions (settled with user during planning):** (1) Completion date = ledger
  precedence preferring `merge_approved` (shared/canonical landing), falling back to
  `review_approved` on current-branch profiles — resolves the review-vs-merge tension
  without a config knob. (2) Pass-only, **resolver-only**: a checkpoint is honored for
  dating only when its current derived status is `pass`; no whole-task exclusion (an
  unrelated lingering `build_verified: fail` still dates by its passing checkpoint and
  stays counted). (3) Time-in-phase spans use ledger timestamps ONLY (no archival
  fallback); Review→Merge is scoped to merge profiles, so current-branch tasks
  contribute to Implement only, and each span reports its own N. (4) In-flight is a
  strictly separate series, never summed into the archived totals. Scope: Core +
  time-in-phase; per-gate pass/fail/retry + pending-human-wait deferred to a follow-up.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t635_15 (async human gates) / t635_19 (`docs_updated` gate):** once these land
    and enter `default_gates` (or per-task `gates:`), the in-flight "completed,
    awaiting gates" series and the Review→Merge timing span begin to populate — the
    surfaces already render them (currently `0`/empty by design).
  - **Deferred-analytics follow-up:** per-gate pass/fail/retry-rate table +
    pending-human-wait metric (CLI + a `pipeline.gate_health` pane) are fully specified
    in `aidocs/gates/stats-multistage-completion.md` — turnkey.
  - **`archive_status_from_text` (gate_ledger.py):** content-level archival decision
    for any consumer that already holds the task body — prefer it over the
    path-opening `archive_status`/`read_task_gate_state` in scans.
