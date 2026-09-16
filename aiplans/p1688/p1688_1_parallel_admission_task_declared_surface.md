---
Task: t1688_1_parallel_admission_task_declared_surface.md
Parent Task: aitasks/t1688_parallel_admission_prepick_assessment_and_task_body_surface.md
Sibling Tasks: aitasks/t1688/t1688_2_aitask_pick_preclaim_parallel_assessment.md
Archived Sibling Plans: aiplans/archived/p1688/p1688_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-15 08:42
---

# t1688_1 — `task_declared`: a task-description fallback surface for the parallel-admission checker

Parent plan (design record, full Risk section): `aiplans/p1688_parallel_admission_prepick_assessment_and_task_body_surface.md`.
This plan is self-contained; the parent is background only.

## Context

The parallel-admission checker (`.aitask-scripts/lib/parallel_admission*.py`,
CLI `./.aitask-scripts/aitask_parallel_admission.sh`) derives an in-flight
task's file surface **only from its plan file**. `task-workflow` sets a task
`Implementing` and locks it at Step 4; the plan is externalized only at the end
of Step 6. For that whole claim→plan window `collect()` builds
`pa.Surface(ref, "plan_declared", (), "no_plan", "n/a")`
(`parallel_admission_collect.py:568-570`), and `decide()` turns any blocking
`no_plan` claim into `UNCHECKABLE_CAUSE:inflight:<id>|no_plan`
(`parallel_admission.py:302-306`). t1569_4 measured 88.5% UNCHECKABLE, `no_plan`
on all 122 candidates (`aiplans/archived/p1569/p1569_4_*.md` :677-729). Task
descriptions exist from creation and name the files they touch.

This task adds a deterministic fallback surface derived from the **task
description**, provenance **`task_declared`**, graded **`CLEAR_CAVEATED`**, on
both producers (the live collector and the trail gatherer).

## Verification pass (2026-09-14, plan re-checked against HEAD `d03e29cf3`)

The approach holds. Deltas against the original plan text:

- **t1799 landed** (`d03e29cf3`): the `_FrozenClock` pin (t1763, `44f92f5fa`) is
  an ancestor of HEAD; t1799 added `FixtureClockTests` and a `now=` parameter on
  `collect_population`, and `tests/test_parallel_admission_preflight.sh` now
  stamps fixture `updated_at` with `$NOW_TS` (the wall clock). The working tree
  is clean for every file this task touches — no concurrent hunks to separate.
- **Shifted test anchors:** `_ReplayScaffold` is now `tests/test_parallel_admission_collect.py:494-566`,
  `ExcludeNoPlanPredicateTests` `:897-1000`, `_FrozenClock` `:474-491`. All
  source-code anchors cited below were re-read and are current.
- **Only one parser of the checker's `INFLIGHT:` row exists outside the renderer:**
  `tests/test_parallel_admission.py:126` (exact match) plus the field-index
  reads in `tests/test_parallel_admission_vocab.py:221-223`
  (`ClosedSetTests.test_rendered_enums_are_declared`). `parallel_admission_collect.py:129-130`
  parses `aitask_query_files.sh inflight` output (a different `INFLIGHT:`
  grammar) and is unaffected.
- **`input_from_records` has no production caller** — `roadmap_run.run` goes
  through `col.collect_population(..., source="origin")`, i.e. the collector,
  so the roadmap's in-flight side is fixed by A2. The adapter change (A4)
  serves the gatherer-record contract, its tests and
  `tests/test_roadmap_integration.py:141-156`; keep it, it is what makes the
  two producers agree.
- `trail_gather.TaskRow.text` is the **raw** file (frontmatter included,
  `_load_row` `:345-357`), so `task_body_text` must strip frontmatter — as A1
  specifies.
- The Codex/OpenCode roadmap copies (`.agents/skills/aitask-backlog-roadmap`,
  `.opencode/skills/aitask-backlog-roadmap`, `.opencode/commands/aitask-backlog-roadmap.md`)
  do **not** carry the stale "t1688 owns that gap" sentence — only
  `.claude/skills/aitask-backlog-roadmap/SKILL.md:216-217` does. No port needed.
- Tracked trail-skill artefacts: `.claude/skills/aitask-trail/SKILL.md.j2`, its
  stub `SKILL.md`, and three goldens `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`.
  The `aitask-trail-*-/` rendered variants are untracked.
- Existing fixtures stay `no_plan` after the change: `_ReplayScaffold` and
  `ExcludeNoPlanPredicateTests` write **no task files** (t9/t20 have none →
  `task_file_for` is `None`); the preflight control's t200 body is `other`
  (no path token); `test_trail_gather` `write_task` defaults to `body\n`.

## Review revision (2026-09-14): description precision — `task_declared` overlaps never CONFLICT

**Concern (review, blocking):** the fallback extracts every path-looking token
from the whole task body, but bodies mix edit targets with Context, Reference
files / patterns, parent-plan links, verification commands and prose citations.
Under the original plan a `task_declared` specific overlap stayed a hard
CONFLICT, so an unrelated in-flight task could block a candidate merely for
*mentioning* one of its files.

**Verified — valid.** Measured over the 527 active Ready/Implementing task
bodies (frontmatter stripped, cut at `## Inbox` / `## Gate Runs`, same
extractor, code ∪ task-data corpus): 2669 resolved token occurrences, of which
only ~424 sit under a key-files-style heading ("key files to modify" 267, "key
files" 157). The rest: verification sections ~440, context/goal/problem ~375,
reference sections ~178, "files touched by those commits" 78, upstream-defect /
diagnostic ~183; by kind, 493 are `aidocs/` / `CLAUDE.md` citations and 179 are
task-data documents (`aiplans/`, `aitasks/`). Narrowing to a declared section
alone is not viable as the mechanism: only 119/527 tasks carry a key-files-like
heading (107 with a resolved token under it), so ~75% of tasks would fall back
to `no_plan` and the goal (no `no_plan`-forced UNCHECKABLE for path-bearing
descriptions) would be missed.

**Decision:** keep whole-body extraction for **resolution** (it is what removes
the UNCHECKABLE), but make description evidence **non-blocking**: an overlap in
which **either** side's surface is `task_declared` never grades CONFLICT. It is
rendered as its normal `OVERLAP:` line (the stale-claim precedent — an advisory
overlap is rendered and caveated, `parallel_admission.py:315-321`) and carries
`CAVEAT:inflight:<ref>|task_declared_overlap:<path>`, which drives
`CLEAR_CAVEATED`. Only plan-derived (or origin-derived) evidence on **both**
sides can produce CONFLICT. This matches the standing rule that a description
is a heuristic, not a declaration (hard stops remain plan evidence and, later,
t1343's manifest). Whether `task_declared` overlaps may ever grade CONFLICT —
and whether a key-files-section-preferred extraction buys enough precision to
justify it — is exactly what `measure_task_declared_precision` decides, with the
section distribution above as its starting evidence. Section narrowing is
deliberately **not** added here (it would add heading-name heuristics for a
precision gain nobody has measured, while non-blocking already removes the
false CONFLICT).

## Review revision 2 (2026-09-14): mixed-result consumers

**Concern (review, blocking):** excluding `task_declared` overlaps from the
verdict is not enough while every overlap still renders an identical `OVERLAP:`
row — in a mixed result (weak overlap with A, real conflict with B) downstream
consumers still label A as conflicting and can discard the evidence that
distinguishes it.

**Verified — valid.** Every consumer of `OVERLAP:` rows reads **all** of them:
- `.aitask-scripts/lib/roadmap_run.py:386-394` — `CONFLICT_WITH:<ref>|<n>`
  counts every `OVERLAP:` ref of every published `coordination_only` (CONFLICT)
  entry;
- `.aitask-scripts/lib/roadmap_policy.py:791-817` `_overlapping_refs` — every
  `OVERLAP:` ref, feeding both `_relations` (`:767-788`, a `coordinates_with`
  edge per ref) and `_observations` (`:831-849`, the `in_flight_conflict`
  observation's `affects`);
- `roadmap_policy.py:524-527` `_caveats` — copies checker `CAVEAT:` lines only
  for `CLEAR_CAVEATED` / `UNCHECKABLE`, so under `CONFLICT` the caveat saying
  "A is description-derived" is dropped;
- `.claude/skills/task-workflow/parallel-admission.md:97` — the `CONFLICT`
  disposition says to name the overlapping tasks "from the `OVERLAP:` lines".
The same shape already mislabels a pre-existing case: an advisory-tier (stale
claim) overlap renders `OVERLAP:<ref>|specific|…` too, so inside a CONFLICT
driven by another claim it is also counted as a counterparty.

**Decision — make the row self-describing and give consumers one definition:**
1. A description-derived specific overlap renders with its own overlap class:
   `OVERLAP:<ref>|declared|<n>|<path>` (`vocab.OVERLAP_CLASSES` gains
   `"declared"`). This replaces the first revision's hidden tuple flag: the
   class IS the flag, so `blocking_specific`, `_display` and every row reader
   see the same fact. Hub precedence is kept — a weak overlap on a hub path stays
   `hub` (already non-blocking, already caveated).
2. NEW pure helper `pa.conflict_refs(lines)` in `parallel_admission.py`'s
   adapter section — **the one definition of "the refs a CONFLICT rests on"**
   for line consumers: refs of `OVERLAP:` rows whose class is `specific` **and**
   whose scope carries no `stale_claim` caveat (i.e. blocking tier) — exactly
   `decide`'s `blocking_specific` set, recovered from the rendered lines. Plus
   `vocab.ADVISORY_OVERLAP_CAVEATS = ("task_declared_overlap",
   "hub_overlap_only", "stale_claim_overlap")` naming the caveats that explain
   an overlap which is NOT a conflict.
3. Consumers switch to it (A6 below): `roadmap_run` `CONFLICT_WITH`, and
   `roadmap_policy._overlapping_refs` (→ relations + conflict observation
   `affects`); `_caveats` additionally keeps the `ADVISORY_OVERLAP_CAVEATS`
   lines under `CONFLICT`, so the entry records that A's overlap is advisory.
   The stale-claim miscount is fixed by the same helper — deliberately, one
   condition plus one test: a helper named "the refs a CONFLICT rests on" that
   counted advisory-tier rows would encode a known-wrong definition.
4. The procedure's `CONFLICT` row is corrected **in this child** (not deferred
   to t1688_2), using **the same condition as `pa.conflict_refs`**: name the
   conflicting tasks/files from the `OVERLAP:` rows of class `specific` **whose
   ref has no `stale_claim` caveat** (`CAVEAT:inflight:<ref>|stale_claim:<n>d`),
   and list everything else separately as advisory, never as conflicts —
   `declared` / `hub` rows with their `task_declared_overlap` /
   `hub_overlap_only` caveat, and stale `specific` rows with their
   `stale_claim_overlap` caveat (advisory-tier claims still emit `specific`
   rows, `tests/test_parallel_admission.py:141-144`). No new helper or
   protocol change: the prose restates the helper's condition. Only the enabled
   (`warn`/`confirm`) branch changes; all three shipped profiles render the
   `off` no-op, so `tests/golden/procs/task-workflow/parallel-admission-*.md`
   and the committed `task-workflow-remote-` closures (`.claude`, `.agents`
   codex, `.opencode`) are expected byte-identical — `aitask_skill_verify.sh`
   confirms. The Codex/OpenCode copies are renders of this same source, so no
   separate port task is needed. The rest of the procedure/website wording
   (Notes, "plan prose", remedy rows) stays with t1688_2 (C2); the CLEAR_CAVEATED
   row already names every `CAVEAT:` line, so it needs no change.

## PINNED contracts (t1688_2 depends on these — do not re-decide)

1. **Invariant.** The fallback can only turn a `no_plan` (in-flight claim or
   candidate) into a **resolved** `task_declared` surface. It never introduces a
   new cause and never merges with a plan surface. A description that is
   unreadable, yields no tokens, or yields only phantom/malformed tokens —
   judged against the **union of the code and task-data corpora** — leaves the
   surface exactly `no_plan` (`Surface(ref, "plan_declared", (), "no_plan")`).
   Precedence: plan → description → `no_plan`.
2. **Vocabulary.** `vocab.PROVENANCES` gains `"task_declared"`;
   `vocab.CAVEAT_REASONS["task_declared"] = NONE` (bare code; the scope carries
   the task). Rendered lines: `CAVEAT:inflight:<ref>|task_declared`,
   `CAVEAT:candidate|task_declared`, `CANDIDATE:<ref>|task_declared|…`.
3. **Checker `INFLIGHT:` row** gains a 6th field:
   `INFLIGHT:<ref>|<sources>|<liveness>|<n_paths>|<path_state>|<provenance>`.
4. **Gatherer marker.** `INFLIGHT_PATH:<ref>|task_declared|-` precedes the
   description's classified records. It is a provenance marker — not a
   sentinel, not an UNCHECKABLE code.
5. **Body cut.** A task body is cut at the first of `## Inbox` /
   `## Gate Runs` (frontmatter stripped first).
6. **Non-blocking description evidence.** An overlap where the candidate's or
   the in-flight claim's surface has provenance `task_declared` never yields
   `CONFLICT`. It renders `OVERLAP:<ref>|declared|<n>|<path>` (a weak overlap on
   a hub path stays `hub`) and, in the blocking tier,
   `CAVEAT:inflight:<ref>|task_declared_overlap:<path>` (drives
   `CLEAR_CAVEATED` when nothing else conflicts; still rendered under
   `CONFLICT`). A plan-derived specific overlap with any other blocking claim
   still yields `CONFLICT` — a weak overlap never masks a real one.
7. **One definition for line consumers.** `pa.conflict_refs(lines)` returns the
   refs a `CONFLICT` rests on: class `specific` **and** no `stale_claim` caveat
   on `inflight:<ref>` (blocking tier). Every code consumer that names conflict
   counterparties from rendered lines calls it; the attended procedure states
   the identical condition in prose; no consumer treats an arbitrary `OVERLAP:`
   row as a conflict.

## Pre-phase (risk mitigations)

1. [pin_no_plan_controls] **Before any code change**, add characterization
   tests pinning today's `no_plan` output on both paths, and run them green on
   the unmodified code:
   - collector — `tests/test_parallel_admission_collect.py`: an in-flight claim
     via `collect()` and a candidate via `resolve_candidate_surface()`, in a new
     `_ReplayScaffold`-style class (seams + `_FrozenClock` saved/restored the
     same way) that writes `aitasks/t<N>_*.md` bodies into the fixture root;
   - gatherer path — `tests/test_trail_gather.py` (`InflightCase` subclass,
     `write_task(..., body=...)`): assert on the **surface the adapter builds**
     (`pa.surfaces_from_inflight_records` over the gatherer's `INFLIGHT_PATH:`
     lines, with `data_tracked`, `data_dirs`, and — once A4 lands —
     `classify=plan_paths.classify`), not on raw gatherer lines, because A5
     legitimately changes those lines.
   Cases, each with **no plan file**: (a) no task file; (b) a body with no path
   token; (c) a body naming only paths that resolve in **neither** corpus (not
   tracked, and not under a tracked directory, on the code or the task-data
   branch); (d) a body whose only real paths sit under `## Inbox` and under
   `## Gate Runs`. All four must still be `no_plan` after A lands. Case (d)
   passes trivially today; it becomes the section-cut guard.

## Step 0 — baseline measurement

Record the BEFORE census (keep the raw output for the Final Implementation Notes):

```bash
./.aitask-scripts/aitask_parallel_admission.sh replay --candidates auto \
  --from plan --lock-freshness require-fresh
```

Note `RATES:` / `VERDICT_FOR:` totals and every `CAUSE_RATE:` line. Clock-pin
prerequisite confirmed present (see Verification pass). New tests that reach
`col.main` must install `_FrozenClock` via the same save/restore seam tuple as
`_ReplayScaffold.setUp` / `ExcludeNoPlanPredicateTests.setUp`. Do not add a
`--now` flag to `check`.

## A1. `.aitask-scripts/lib/plan_paths.py`

Add, next to `extract()`:

```python
def cut_task_framework_sections(body: str) -> str:
    """Truncate a task body at the first framework-appended section.

    `## Inbox` (note framework) is inserted BEFORE `## Gate Runs`
    (aitask_note.sh:94-100), so cutting only at Gate Runs would leave other
    agents' note prose -- arbitrary paths from other tasks -- in a
    task-declared surface. Note bodies cannot fake either header: every body
    line is prefixed `> | ` (aitask_note.sh note_render_body).
    """
    import gate_ledger   # lazy: keeps the plan_paths_sh.sh bridge's load path unchanged
    import note_inbox
    headers = (note_inbox.SECTION_HEADER, gate_ledger.SECTION_HEADER)
    pattern = re.compile(
        r"^(?:%s)[ \t]*$" % "|".join(re.escape(h) for h in headers), re.MULTILINE)
    match = pattern.search(body)
    return body if match is None else body[:match.start()]


def task_body_text(raw: str) -> str:
    """A task file's declared text: frontmatter stripped, framework sections cut."""
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            raw = raw[end + 4:]
    return cut_task_framework_sections(raw)
```

`note_inbox.SECTION_HEADER = "## Inbox"` (`note_inbox.py:55`),
`gate_ledger.SECTION_HEADER = "## Gate Runs"` (`gate_ledger.py:89`). Verify at
implementation time that importing both lazily from `plan_paths` does not pull
anything heavy/cyclic (if it does, fall back to the two literals with a
drift-guard test asserting they equal the modules' constants). The frontmatter
shape matches `parallel_admission_collect.strip_frontmatter`. Update the module
docstring's consumer framing to mention task descriptions. No grammar change —
`tests/test_plan_paths_seam.sh` ("no second copy of the grammar") must stay green.

## A2. `.aitask-scripts/lib/parallel_admission_collect.py`

- `.aitask-scripts/lib/parallel_admission_sweep.py:90-98`:
  `PlanExtraction.as_surface(self, provenance="plan_declared")` — thread the
  provenance through (default keeps `collect.py:359`, `:1225` and tests unchanged).
- New, after `surface_from_plan` (`:351-359`):

```python
def task_surface(ref, task_path, tracked, tracked_dirs):
    """Description-derived surface, or None when the description resolves nothing.

    THE ONE EXTRACTOR again (`plan_extraction`), with the task-body cut as its
    body_transform -- a second extractor could disagree with the plan path on
    exactly the edges plan_paths documents. None (never an unresolved Surface)
    because the caller's fallback is `no_plan`: a description may upgrade that
    state, never replace it with a different cause (t1688 invariant).
    """
    extraction, _stripped = plan_extraction(
        ref, task_path, tracked, tracked_dirs,
        body_transform=plan_paths.cut_task_framework_sections)
    if extraction.resolution != "resolved":
        return None
    return extraction.as_surface(provenance="task_declared")
```

- `_task_surface(ref, path, tracked, dirs, cache=None)`: the memoised twin of
  `_plan_surface` (`:786-800`), same cache, key `(ref, path)` (task and plan
  paths never collide); it must call the module-global `task_surface` so tests
  can patch it (read-once test).
- `_no_plan_fallback(root, ref, tracked, dirs, cache=None)`:
  `path = task_file_for(root, ref)` (`:403-413`); return `_task_surface(...)` or,
  when that is `None` / there is no task file,
  `pa.Surface(ref, "plan_declared", (), "no_plan", "n/a")`.
- `collect()` in-flight site (`:568-572`): `if p is None: surf =
  _no_plan_fallback(root, ref, all_tracked, all_dirs, surface_cache)`.
- `resolve_candidate_surface()` (`:815-819`): `if p is None: cand =
  _no_plan_fallback(root, key, tracked, dirs, cache)`. The `--from auto` origin
  fallback (`:820-827`) is unchanged and runs only while `cand` is unresolved.
- `no_plan_claims()` (`:869-903`): code unchanged; add one docstring sentence —
  a claim resolved from its description is not `no_plan` and is not swept up.

The collector already classifies against the union (`resolve_corpora`,
`:467-492`), so task-data files **and directories** count here.

## A3. `.aitask-scripts/lib/parallel_admission_vocab.py`

- `PROVENANCES = ("plan_declared", "origin_derived",
  "plan_declared+origin_fallback", "task_declared")`.
- `CAVEAT_REASONS["task_declared"] = NONE` with a comment: "t1688: the surface
  was derived from the task description, not a plan — unverified evidence".
- `CAVEAT_REASONS["task_declared_overlap"] = PATH` with a comment: "t1688: a
  specific overlap whose evidence on one side is a task description — reported,
  never a CONFLICT (descriptions cite files as context as well as edit
  targets)".
- `OVERLAP_CLASSES = ("specific", "hub", "declared")` — comment: `specific` is
  the only class that can drive CONFLICT; `declared` = description-derived
  (t1688), non-blocking.
- `ADVISORY_OVERLAP_CAVEATS = ("task_declared_overlap", "hub_overlap_only",
  "stale_claim_overlap")` — the caveat codes that explain an overlap which is
  NOT a conflict; a unit test asserts each is a declared `CAVEAT_REASONS` key.

## A4. `.aitask-scripts/lib/parallel_admission.py` (PURE — no new imports)

In `decide()`:
- after `surf = claim.surface or …` (`:286`): `check_member(surf.provenance,
  vocab.PROVENANCES, "inflight provenance")`.
- after the candidate-resolution check (`:262-265`):
  `if cand.resolution == "resolved" and cand.provenance == "task_declared":
  caveat("candidate", "task_declared")`.
- in the blocking branch (the `else:` at `:322`):
  `if surf.resolution == "resolved" and surf.provenance == "task_declared":
  caveat(scope, "task_declared")` — drives the verdict. Advisory-tier claims get
  no `task_declared` caveat (their overlaps already carry `stale_claim_overlap`).
- **weak overlaps (PINNED 6) — via the overlap class, no tuple change:**
  compute once per claim
  `weak = surf.provenance == "task_declared" or cand.provenance == "task_declared"`
  and pass it to `_classify_overlap(path, touch_counts, hub_threshold, weak)`,
  which returns `hub` when the touch count reaches the threshold, else
  `declared` when `weak`, else `specific`. Consequences, all without touching
  any unpacking site:
  - `blocking_specific` (`:342`, `cls == "specific"`) excludes `declared`, so
    description evidence can never reach CONFLICT; `_display` (`:374-375`)
    names only `specific` blocking refs, so a mixed CONFLICT names only the
    strong counterparty;
  - in the blocking branch, for each hit with `cls == "declared"`:
    `caveat(scope, "task_declared_overlap", p)` (drives CLEAR_CAVEATED when
    nothing else conflicts; rendered under CONFLICT too);
  - advisory tier: `declared` rows get `stale_claim_overlap` as today, no
    `task_declared_overlap`; NARROWED stays hub-only.
  - Module docstring: document the `OVERLAP:` class vocabulary next to the
    `INFLIGHT:` row grammar, and add next to "CLEAR IS AN OBSERVATION":
    description evidence can downgrade a verdict to CLEAR_CAVEATED but can never
    assert a conflict (the same one-directional rule as `recovered_only`).
- **`conflict_refs(lines)` (PINNED 7)** in the adapter section (pure):

```python
def conflict_refs(lines):
    """The in-flight refs a CONFLICT verdict rests on, from rendered lines.

    THE definition for line consumers (roadmap summary, relations,
    observations, the preflight's CONFLICT display): an `OVERLAP:` row of
    class `specific` whose scope is in the blocking tier -- `decide`'s own
    `blocking_specific` set. `declared` (t1688) and `hub` rows are advisory by
    construction; an advisory-tier (stale) claim is recognised by its
    `stale_claim` caveat. Counting every OVERLAP row labels an advisory
    overlap as a conflict counterparty.
    """
```

  Parse `OVERLAP:<ref>|<cls>|…` with `split("|", 2)` (the path is the last,
  encoded field) and `CAVEAT:<scope>|<reason>` on the first `|`, reason code on
  the first `:`. Returns a sorted tuple of the row refs as rendered (callers
  qualify them, as today).
- `inflight_rows` carries `surf.provenance`; `_render_lines` (`:412-417`) emits
  `INFLIGHT:%s|%s|%s|%d|%s|%s`, the last field via
  `check_member(prov, vocab.PROVENANCES, "inflight provenance")`. Document the
  row grammar in the module docstring.

Adapter (`:522-564`) — new signature
`surfaces_from_inflight_records(lines, local_name=None, data_tracked=None,
data_dirs=None, classify=None)`:
- `_TASK_DECLARED_MARKER = "task_declared"` next to `_SENTINELS`; a marker
  record adds the ref to a `declared` set and contributes no path.
- phantom promotion via one helper:

```python
def _data_side_resolves(path, data_tracked, data_dirs, classify):
    """Does `path` resolve on the task-data side the gatherer cannot see?

    With an injected classifier this is the collector's own rule
    (plan_paths.classify over files AND directories), so code-branch phantom
    AND data-side resolved <=> union resolved. Injected because this module is
    pure and plan_paths imports subprocess. Without one: exact membership,
    the documented degraded mode.
    """
    if classify is not None:
        return classify(path, data_tracked or set(), data_dirs or set()) \
            in ("tracked", "planned_new")
    return bool(data_tracked) and path in data_tracked
```

- surface per ref: sentinel wins; else resolved paths → `resolved` with
  provenance `task_declared` if the ref is in `declared` else `plan_declared`;
  else a `declared` ref → `Surface(ref, "plan_declared", (), "no_plan")`
  (never `all_phantom`); else `all_phantom`.
- `input_from_records` gains `data_dirs=None, classify=None` and passes them
  through (`:583`).

## A5. `.aitask-scripts/lib/trail_gather.py`

`_classify_plan_paths` (`:808-834`; keep the signature and 4-tuple — stubbed by
`tests/test_trail_gather.py:1909-1922`):

```python
plan = plan_path_for(row, tree) if row is not None else None
if plan is None:
    if row is None:
        return [("no_plan", "-")], False, False, False
    tokens = plan_paths.extract(plan_paths.task_body_text(row.text))
    if not any(not plan_paths.is_malformed(t) for t in tokens):
        return [("no_plan", "-")], False, False, False
    # The gatherer sees the CODE branch only: aitasks/ paths classify phantom
    # here. The phantom-only judgement belongs to the adapter, which holds the
    # task-data corpus (t1688) -- so emit every record.
    return ([("task_declared", "-")]
            + [(plan_paths.classify(t, tracked, tracked_dirs), t) for t in tokens],
            False, False, False)
```

`has_plan` / `read_ok` / `yielded` stay False: `INFLIGHT_SCAN`'s corpus axis
remains about plans — say so in `_corpus_status`'s docstring (`:963-972`). Add
`task_declared` to the class list in the module docstring (`:40`) with one
sentence on the marker. No new prefix; no `NORMALIZATION_VERSION` bump
(`emit_inflight` runs at `:1128`, after `DIGEST:` at `:1121`, so every
`INFLIGHT*` line is digest-excluded).

`.claude/skills/aitask-trail/SKILL.md.j2:72`: add `task_declared` to the
`INFLIGHT_PATH:` class list, plus one sentence near `:83-95` describing the
marker (a provenance marker preceding a description-derived surface for a task
with no plan; not a sentinel). Regenerate its goldens:

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do "$PYTHON" .aitask-scripts/lib/skill_template.py \
  .claude/skills/aitask-trail/SKILL.md.j2 aitasks/metadata/profiles/$p.yaml claude \
  > tests/golden/skills/aitask-trail/SKILL-$p-claude.md; done
```

`.claude/skills/aitask-backlog-roadmap/SKILL.md:215-218`: replace the "an
in-flight claim's surface is read from its plan file, and most `Implementing`
tasks carry no plan (t1688 owns that gap)" sentence with the current state: a
claim with no plan is read from its task description (`task_declared`,
CLEAR_CAVEATED); only a description that names no file still reads `no_plan`.
(No Codex/OpenCode copy carries this sentence — verified.)

## A6. Consumers of mixed results (review revision 2)

- `.aitask-scripts/lib/roadmap_run.py:382-396`: factor the counterparty loop
  into `_conflict_counterparties(published, project)` and build it from
  `pa.conflict_refs(entry.admission_lines)` instead of every `OVERLAP:` row;
  update the comment ("the in-flight tasks the CONFLICT verdicts are against —
  never an advisory overlap").
- `.aitask-scripts/lib/roadmap_policy.py:791-817` `_overlapping_refs`: take the
  refs from `pa.conflict_refs(scored.admission_lines)` (qualification unchanged;
  rename nothing — its two callers `_relations` and `_observations` then emit
  `coordinates_with` edges and `in_flight_conflict` `affects` only for real
  counterparties). Docstring: advisory overlaps (`declared`, `hub`, stale) are
  recorded as entry caveats, never as conflict relations.
- `roadmap_policy.py:524-527` `_caveats`: keep today's rule for
  `CLEAR_CAVEATED` / `UNCHECKABLE` (all `CAVEAT:` / `UNCHECKABLE_CAUSE:` lines);
  for `CONFLICT` additionally copy the `CAVEAT:` lines whose reason code is in
  `vocab.ADVISORY_OVERLAP_CAVEATS`, same rendering (`inflight:<ref>:
  task_declared_overlap:<path>`), so the evidence that A's overlap is advisory
  survives in the entry.
- `.claude/skills/task-workflow/parallel-admission.md:97` (`CONFLICT` row, enabled
  branch only): "name the conflicting task(s) and file(s) from the `OVERLAP:`
  lines of class **`specific`** whose task has **no** `stale_claim` caveat
  (`CAVEAT:inflight:<ref>|stale_claim:…`) — those are what the verdict rests
  on. List every other overlap separately, as advisory, with the reason from
  its `CAVEAT:` line — `declared` (description-derived: `task_declared_overlap`),
  `hub` (`hub_overlap_only`), and a stale claim's `specific` row
  (`stale_claim_overlap`) — never as conflicts; then ask the step-6 question".
  This is the prose form of `pa.conflict_refs` — keep the two conditions
  identical.
  Render check: `./.aitask-scripts/aitask_skill_verify.sh`; goldens and the
  committed remote closures are `off` renders and must come out unchanged (if
  verify reports drift, run `./.aitask-scripts/aitask_skill_rerender.sh remote`
  and commit the result with the code).

## Tests

- `tests/test_plan_paths.py`: `cut_task_framework_sections` cuts at the first
  header in either order; ignores `> | ## Inbox`; keeps `## Merged from t42: x`;
  `task_body_text` strips frontmatter.
- `tests/test_parallel_admission.py`: `claim()` (`:32-39`) gains
  `provenance="plan_declared"`; cases: in-flight `task_declared` no-collision →
  `VERDICT:CLEAR_CAVEATED` + `CAVEAT:inflight:t9|task_declared`; candidate
  `task_declared` → `CAVEAT:candidate|task_declared`; advisory-tier
  `task_declared` → no such caveat; undeclared in-flight provenance →
  `VocabularyError`; `:126` exact row gains `|plan_declared`.
  **Weak-overlap cases (PINNED 6/7)** — a new `TaskDeclaredOverlapTests` class:
  - in-flight `task_declared` surface overlapping a plan-declared candidate →
    `VERDICT:CLEAR_CAVEATED`, an `OVERLAP:t9|declared|…` row (not `specific`),
    and `CAVEAT:inflight:t9|task_declared_overlap:<path>` +
    `CAVEAT:inflight:t9|task_declared`;
  - candidate `task_declared` overlapping a **plan-declared** in-flight claim →
    CLEAR_CAVEATED with a `declared` row (candidate-side weakness also demotes);
  - **control:** the same overlap with both sides `plan_declared` → CONFLICT,
    row class `specific`;
  - **mixed result (no masking, no mislabel):** a weak overlap with t9 plus a
    plan-vs-plan overlap with t10 → CONFLICT; rows `OVERLAP:t9|declared|…` and
    `OVERLAP:t10|specific|…`; DISPLAY names only t10; the t9
    `task_declared_overlap` caveat is still rendered; `pa.conflict_refs(lines)
    == ("t10",)`;
  - `conflict_refs` also excludes an advisory-tier (stale) `specific` row in a
    CONFLICT driven by another claim, and excludes `hub` rows;
  - weak hub overlap → row class `hub`, only `hub_overlap_only`;
  - `NegativeControlTests`: over every provenance combination where either side
    is `task_declared`, no fixture yields CONFLICT or a `specific` row, and none
    yields bare CLEAR. Adapter (`AdapterTests` `:349-404`): marker + resolved →
  `task_declared`; marker + unresolved → `no_plan`; injected classifier
  promotes a new file under a data directory; no classifier → exact membership.
- `tests/test_parallel_admission_vocab.py`: a `task_declared` fixture in
  `_fixtures()` (`:152-175`); `ClosedSetTests.test_rendered_enums_are_declared`
  (`:210-231`) also asserts `INFLIGHT` field `[5]` ∈ `PROVENANCES`;
  `UpstreamDriftTests` (`:240-271`) asserts the marker appears in the trail
  grammar line.
- `tests/test_parallel_admission_collect.py` (write `aitasks/t<N>_*.md` bodies
  into the fixture root): no plan + body naming a tracked path → resolved
  `task_declared`, not UNCHECKABLE, graded CLEAR_CAVEATED; candidate with no
  plan resolves from its description; read-once (patch `col.task_surface`, as
  `ReplayInvariantTests` `:672-710` patches `surface_from_plan`); `no_plan_claims`
  omits a `task_declared` claim; the pre-phase controls.
- `tests/test_trail_gather.py`: marker + all records for a path-bearing body;
  `no_plan` for an empty or malformed-only body; existing no-plan tests
  (`:1579-1598`, `:1757-1762`, `:1837-1844`) stay green (their body is
  `"body\n"`).
- NEW `tests/test_task_declared_parity.py` — **producer-to-adapter parity**
  (catches evidence discarded upstream, which adapter-only tests cannot): one
  tmp git repo as project root. Producer: `trail_gather.load_tree(name, root,
  is_local=False)` + `trail_gather.emit_inflight` with injected `_GATE_PROBE` /
  `_LOCK_PROBE` (`trail_gather.py:804-805`) so one no-plan task is in flight;
  feed its `INFLIGHT_PATH:` lines to `pa.surfaces_from_inflight_records(...,
  data_tracked=D, data_dirs=DD, classify=plan_paths.classify)`. Reference:
  `col.collect(...)` with `_DATA_TREE` stubbed to `(D, DD, None)`,
  `batch_lines=[]`, a pinned `now`. Assert identical
  `(paths, resolution, provenance)` for:
  1. description names only a tracked task-data file
     (`aitasks/metadata/profiles/fast.yaml` ∈ D) → resolved `task_declared`;
     control: path ∉ D → `no_plan` on both;
  2. description names only a proposed new file under a tracked task-data
     directory (`aitasks/metadata/profiles/custom.yaml`, directory ∈ DD) →
     resolved (`planned_new`) on both; control: directory ∉ DD → `no_plan`;
  3. the same new file named by a **plan** → both resolved (the adapter's
     pre-existing blind spot is closed).
- `tests/test_parallel_admission_preflight.sh`: keep the `no_plan` control
  (`:145-156`, body `other`); add two end-to-end cases after it, through the
  real CLI (write each task file with `updated_at: $NOW_TS`, as `add_inflight`
  does — extend `add_inflight` with an optional task-body argument rather than
  forking it):
  1. **disjoint description** — t200 has no plan and its body names only
     `src/beta.py` → `VERDICT:CLEAR_CAVEATED`, `CAVEAT:inflight:200|task_declared`,
     an `INFLIGHT:200|…|task_declared` row, and no `OVERLAP:` line;
  2. **referenced-but-not-edited regression (the review's case)** — t200 has no
     plan and its body is a realistic mixed body: `## Key files to modify` names
     `src/gamma.py`, and `## Reference files / patterns` cites `src/alpha.py`
     (the candidate's planned file) "for the pattern" → `VERDICT:CLEAR_CAVEATED`
     (**not** CONFLICT), `OVERLAP:200|declared|…|src/alpha.py` rendered,
     `CAVEAT:inflight:200|task_declared_overlap:src/alpha.py`, and a DISPLAY
     that does not start with "conflict with". The existing CONFLICT case
     (`:134-143`: the same file declared by t200's **plan**, row class
     `specific`) is the paired control proving the demotion is
     provenance-driven, not a lost overlap;
  3. **mixed result** — t200's **plan** declares `src/alpha.py` and a second
     in-flight task t300 (no plan) cites `src/alpha.py` in its description
     (generalise `add_inflight` to take the task id) → `VERDICT:CONFLICT`,
     `OVERLAP:200|specific|…`, `OVERLAP:300|declared|…`,
     `CAVEAT:inflight:300|task_declared_overlap:src/alpha.py`, and a DISPLAY
     naming 200 but not 300.
- `tests/test_parallel_admission_collect.py`: add the collector-level twin of
  case 2 (in-flight no-plan claim whose description cites the candidate's plan
  file as a reference → `pa.decide(...)` grades CLEAR_CAVEATED with the
  `task_declared_overlap` caveat), so the regression is also pinned below the
  CLI.
- **Roadmap mixed-result regression — producer to document.**
  `tests/test_roadmap_integration.py`: a candidate whose admission comes from a
  real `pa.decide` over two in-flight claims — A with a `task_declared` surface
  overlapping the candidate, B with a plan-declared surface overlapping it →
  CONFLICT. Assert on the built document: `relations` contains a
  `coordinates_with` edge to B and none to A; the `in_flight_conflict`
  observation's `affects` is `[candidate, B]` (A absent); the entry's
  `caveats` include `inflight:A: task_declared_overlap:<path>`. Control: with A
  plan-declared too, both edges and both `affects` appear. (The suite's own
  fixtures in `tests/test_roadmap_policy.py` hand-write `specific` rows via
  `admission()` `:58-62`; extend that helper with an optional class and caveat
  lines, and add the same mixed case at unit level in `LaneTests`/relations
  tests next to `:547-561`.)
- **Roadmap run summary.** `tests/test_roadmap_run.py`: unit-test
  `_conflict_counterparties` with a published CONFLICT entry carrying the mixed
  lines → only B is counted in `CONFLICT_WITH`; control with both `specific` →
  both counted.
- **Rendered workflow instructions.** `tests/test_skill_render_task_workflow.sh`
  Test 4e (`:503-630`, synthetic `warn` / `confirm` / `off` profiles): the
  `warn` and `confirm` renders of `parallel-admission.md` contain the
  "of class **`specific`**" CONFLICT instruction **with its "no `stale_claim`
  caveat" exclusion**, and the advisory clause naming all three non-conflict
  reasons (`task_declared_overlap`, `hub_overlap_only`, `stale_claim_overlap`)
  with "never as conflicts"; the `off` render contains none of them. A
  source-level parity pin asserts the procedure's condition mentions the same
  two tests `pa.conflict_refs` applies (class `specific`, `stale_claim`), so the
  prose and the helper cannot drift silently.
  `tests/test_parallel_admission_preflight.sh` (which reads the procedure
  text as `proc_default`) asserts the same clause beside its existing
  disposition pins, so the CLI mixed case (3) and the instruction that
  consumes it are checked in one file.

## Verification

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
"$PYTHON" -m pytest -q tests/test_plan_paths.py tests/test_parallel_admission.py \
  tests/test_parallel_admission_vocab.py tests/test_parallel_admission_collect.py \
  tests/test_parallel_admission_purity.py tests/test_trail_gather.py \
  tests/test_task_declared_parity.py tests/test_roadmap_integration.py \
  tests/test_roadmap_policy.py tests/test_roadmap_run.py
bash tests/test_parallel_admission_preflight.sh
bash tests/test_skill_render_task_workflow.sh
bash tests/test_parallel_admission_cli.sh
bash tests/test_skill_render_aitask_trail.sh
bash tests/test_trail_skill_contract.sh
bash tests/test_plan_paths_seam.sh
set -o pipefail; bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
./.aitask-scripts/aitask_skill_verify.sh
```

Live: re-run the Step 0 `replay` (AFTER census) and
`check --candidate <a Ready task> --from plan --lock-freshness require-fresh`:
in-flight tasks whose descriptions name files no longer cause `no_plan`; their
rows read `…|task_declared`.

## Final Implementation Notes must include

The BEFORE and AFTER `replay` census (verdict counts and every `CAUSE_RATE:`),
the remaining UNCHECKABLE causes by name, the prompt-producing rate
(CONFLICT + UNCHECKABLE) / candidates, and — new with PINNED 6 — the count of
candidates whose CLEAR_CAVEATED carries a `task_declared_overlap` caveat (the
would-have-been-CONFLICTs) — t1688_2 re-measures this and decides the shipped
`parallel_admission` default on it.

**Notes for sibling tasks** must state, for t1688_2: PINNED 6 makes its C1
"precision sample of CONFLICT verdicts involving a `task_declared` surface"
empty by construction — sample `task_declared_overlap` caveats instead; the
assessment should read `OVERLAP:…|declared|…` rows as description-derived
(advisory) evidence and use `pa.conflict_refs` — class `specific` with no
`stale_claim` caveat on its scope — for what a CONFLICT rests on (a stale
claim's `specific` row is advisory, `stale_claim_overlap`); the prompt rate no longer includes description-only
overlaps; and the procedure's CONFLICT row was already corrected here (PINNED
7), so C2 must keep it. Send the same as an
advisory `./ait note 1688_2` at Step 8e.

## Risk

### Code-health risk: medium
- The fallback changes the in-flight surface for every consumer at once
  (preflight, roadmap, `replay`); a body cut that lets `## Inbox` prose through
  would manufacture CONFLICTs · severity: low (residual — the four no_plan
  controls are pinned before the code changes, including the section-cut case)
  · → mitigation: inline pre-phase pin_no_plan_controls
- Two line protocols change (`INFLIGHT:` 6th field, `INFLIGHT_PATH:` marker);
  the adapter files an unknown class as phantom · severity: medium ·
  → mitigation: covered in-plan — explicit marker handling with tests; the only
  exact-match consumer (`test_parallel_admission.py:126`) and the field-index
  guard (`test_parallel_admission_vocab.py:221-223`) updated
- The gatherer (code branch only) and collector (code ∪ task-data) judge
  against different corpora · severity: medium · → mitigation: covered in-plan —
  judgement moved to the adapter with the injected shared classifier; parity
  test (existing file, new file under a data dir, plan-derived)

- The new `OVERLAP:` class `declared` changes a consumed row vocabulary; any
  consumer that treats every `OVERLAP:` row as a conflict mislabels an advisory
  overlap in a mixed result (found: `roadmap_run` `CONFLICT_WITH`,
  `roadmap_policy` relations / conflict observations / CONFLICT caveats, the
  procedure's CONFLICT row) · severity: medium · → mitigation: covered in-plan —
  one pure definition `pa.conflict_refs` used by both roadmap sites, advisory
  caveats kept under CONFLICT, the procedure row restricted to `specific`, and
  mixed-result regressions at checker, CLI, roadmap-document, run-summary and
  rendered-procedure level; the only other `OVERLAP:` parsers in the tree
  (`aitask_contribution_review.sh`, `aitask_remote_drift_check.sh`) are
  unrelated grammars

### Goal-achievement risk: medium
- Descriptions name files as context as well as edit targets (measured: ~16%
  of resolved description tokens sit under a key-files heading), so
  `task_declared` overlaps are coarse · severity: medium (residual — they can no
  longer produce a false CONFLICT, PINNED 6; the cost is caveat noise, and a
  real description-only collision is reported as a caveat rather than stopped)
  · → mitigation: t1814
- Only `no_plan`-driven UNCHECKABLEs are fixed; other causes remain · severity:
  medium · → mitigation: covered in-plan — the AFTER census names them;
  acceptance is the mechanism, not a corpus statistic

### Planned mitigations
- timing: pre-phase | name: pin_no_plan_controls | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — fallback changes every consumer's surface / body-cut leak | desc: pin today's no_plan output on the collector and gatherer paths (no task file, pathless body, phantom-only body, paths only under Inbox/Gate Runs) before A changes code
- timing: after | name: measure_task_declared_precision | type: enhancement | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — description surfaces may be too coarse to justify warn | desc: extend `aitask_parallel_admission.sh sweep` with a task-description source and score task_declared surfaces against landed files over the archived corpus (precision/recall, as t1643 did for plan surfaces), comparing whole-body extraction with a key-files-section-preferred variant, to decide whether task_declared overlaps may ever grade CONFLICT (t1688_1 ships them non-blocking) | created: t1814

The `after` line is created at **this child's Step 8d**.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1688_1`.

## Implementation progress (2026-09-15)

All plan steps implemented: pre-phase `pin_no_plan_controls` (8 tests, green
on the unmodified code before any change), A1–A6, the procedure's CONFLICT row,
the trail grammar + goldens, the roadmap-skill sentence, and every test listed
above including the new `tests/test_task_declared_parity.py`.

### Replay census (same HEAD `757a7e59f`, same 129 candidates, `--candidates auto --from plan --lock-freshness require-fresh`)

| | CLEAR | CLEAR_CAVEATED | CONFLICT | UNCHECKABLE |
|---|---|---|---|---|
| BEFORE | 0 | 0 | 12 | 117 |
| AFTER | 0 | 103 | 12 | 14 |

- `CAUSE_RATE:` BEFORE — all_phantom 5, cross_host_lock 128, hub_overlap_only
  11, no_extractable_paths 9, no_liveness_token 129, **no_plan 129**,
  stale_claim 129.
- `CAUSE_RATE:` AFTER — all_phantom 5, cross_host_lock 128, hub_overlap_only
  64, no_extractable_paths 9, no_liveness_token 129, stale_claim 129,
  **task_declared 129**, **task_declared_overlap 6**; `no_plan` is gone.
- Remaining UNCHECKABLE causes by name: `all_phantom` (5) and
  `no_extractable_paths` (9) — 14, matching the 14 UNCHECKABLE verdicts.
- Prompt-producing rate (CONFLICT + UNCHECKABLE) / candidates: **100%
  (129/129) → 20.2% (26/129)**.
- Would-have-been CONFLICTs (candidates whose CLEAR_CAVEATED carries a
  `task_declared_overlap` caveat): **6**. CONFLICT stayed at 12 — description
  evidence added no conflicts (PINNED 6).
- (`CAUSE_RATE:` counts every reason code, caveats included, per candidate.)

### Live check

`check --candidate 1688_2 --from plan --lock-freshness require-fresh`: 8
in-flight rows now read `…|resolved|task_declared` (incl. t1555_2 and t1576,
two of the seven no-plan tasks from the original problem statement), zero
`UNCHECKABLE_CAUSE:` lines, and a genuine plan-vs-plan CONFLICT with sibling
t1688_1 (the two children do share files).

### Mutation check (isolated scratch copy of `.aitask-scripts/` + `tests/`)

- M1 — `_classify_overlap` returns `specific` for weak overlaps (description
  evidence may conflict): 6 of the targeted tests fail.
- M2 — `conflict_overlaps` stops excluding stale claims: 2 fail
  (checker + roadmap run summary).
- M3 — `cut_task_framework_sections` cuts nothing: 8 fail (both pre-phase
  case-(d) guards + `TaskBodyTests`).
- Unmutated control over the same files: 146 passed.

## Final Implementation Notes

- **Actual work done:** A1–A6 as planned, plus both review revisions. A no-plan
  in-flight task (and a no-plan candidate) is now read from its task
  description through the ONE extractor (`plan_extraction` +
  `plan_paths.cut_task_framework_sections`), provenance `task_declared`,
  memoised per run; precedence plan → description → `no_plan` with no merging.
  `decide` caveats it (`task_declared`), renders the provenance as the
  `INFLIGHT:` row's 6th field, and classes any overlap involving a description
  `declared` — reported, never a CONFLICT. The gatherer emits a
  `task_declared` marker before the description's classified records and the
  adapter judges phantom-only with an injected `plan_paths.classify` over the
  task-data corpus. Consumers: `pa.conflict_overlaps` / `pa.conflict_refs` are
  the one definition of "what a CONFLICT rests on", used by `roadmap_run`'s
  `CONFLICT_WITH` and `roadmap_policy._overlapping_refs` (relations +
  `in_flight_conflict` affects), with `vocab.ADVISORY_OVERLAP_CAVEATS` kept on
  CONFLICT entries by `_caveats`. Docs: the preflight's CONFLICT row, the trail
  grammar + 3 goldens, the backlog-roadmap sentence.
- **Deviations from plan:** (1) review revision 1 proposed a hidden "6th
  overlap-tuple element"; revision 2 replaced it with the `declared` overlap
  CLASS, which is self-describing to every row consumer and touched no
  unpacking site. (2) Added `conflict_overlaps` beside `conflict_refs` so
  `roadmap_run` keeps its per-file counting semantics (`CONFLICT_WITH:<ref>|<n>`
  is documented as a file count) while filtering to real conflicts. (3) The
  same helper also fixes a PRE-EXISTING miscount — an advisory-tier (stale)
  claim still renders `specific` rows and was being counted as a conflict
  counterparty; one condition plus two tests, deliberately in scope because a
  helper named "the refs a CONFLICT rests on" cannot encode a known-wrong
  definition. (4) The procedure's CONFLICT row was corrected here rather than
  deferred to t1688_2 (review), since this task is what makes it wrong.
- **Issues encountered:** the `_overlapping_refs` docstring edit first landed
  AFTER the closing `"""` (a syntax error) — caught immediately by the targeted
  suite and fixed. Three Test 4e pins in
  `tests/test_skill_render_task_workflow.sh` asserted the old CONFLICT wording
  verbatim; they were repinned to the new condition (the wording change is the
  point of A6), and a source-level parity pin now asserts the prose and
  `conflict_refs` test the same two things.
- **Key decisions:** whole-body extraction is kept for RESOLUTION (measured:
  only ~16% of resolved description tokens sit under a key-files heading, and
  just 119/527 active tasks have such a heading, so a section allowlist would
  return ~75% of tasks to `no_plan` and miss the goal), while precision is
  handled by making description evidence NON-BLOCKING. `task_declared` is a
  provenance marker, never a sentinel or an UNCHECKABLE code. The corpus axis
  (`INFLIGHT_SCAN`) still reports plan evidence only, so a description-read task
  counts toward `no_plans`.
- **Upstream defects identified:** None. (The stale-claim counterparty miscount
  found during review is fixed in this task, not deferred — see Deviations (3).)
- **Notes for sibling tasks:** for **t1688_2** — the PINNED contracts hold as
  written, plus two additions it must build on. **PINNED 6:** a `task_declared`
  overlap renders `OVERLAP:<ref>|declared|<n>|<path>` and NEVER grades CONFLICT,
  so C1's planned "precision sample of CONFLICT verdicts involving a
  `task_declared` surface" is empty by construction — sample the
  `task_declared_overlap` caveats instead (the AFTER census has 6 across 129
  candidates, against 12 CONFLICTs that are all plan-derived). **PINNED 7:**
  `pa.conflict_refs(lines)` / `pa.conflict_overlaps(lines)` are the only
  sanctioned way to name a CONFLICT's counterparties from rendered lines (class
  `specific` AND no `stale_claim` caveat on `inflight:<ref>`); the pre-claim
  assessment should read `declared` rows as advisory evidence and use these for
  conflicts. C1's prompt-producing rate at this commit is **20.2% (26/129)**,
  already inside C1's ≤30% rule, but C1 must re-measure. C2 must KEEP the
  corrected CONFLICT row in `parallel-admission.md` (A6) — do not revert it to
  "from the `OVERLAP:` lines"; the rest of that file's wording (Notes, "plan
  prose", the `no_plan` remedy row) is still C2's. `vocab.ADVISORY_OVERLAP_CAVEATS`
  names the caveat codes that explain a non-conflicting overlap.
