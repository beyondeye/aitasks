---
Task: t1688_1_parallel_admission_task_declared_surface.md
Parent Task: aitasks/t1688_parallel_admission_prepick_assessment_and_task_body_surface.md
Sibling Tasks: aitasks/t1688/t1688_2_aitask_pick_preclaim_parallel_assessment.md
Archived Sibling Plans: aiplans/archived/p1688/p1688_*_*.md
Base branch: main
Output branch: main
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
(`parallel_admission_collect.py:568-571`), and `decide()` turns any blocking
`no_plan` claim into `UNCHECKABLE_CAUSE:inflight:<id>|no_plan`
(`parallel_admission.py:302-306`). t1569_4 measured 88.5% UNCHECKABLE, `no_plan`
on all 122 candidates (`aiplans/archived/p1569/p1569_4_*.md` :677-729). Task
descriptions exist from creation and name the files they touch.

This task adds a deterministic fallback surface derived from the **task
description**, provenance **`task_declared`**, graded **`CLEAR_CAVEATED`**, on
both producers (the live collector and the trail gatherer).

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

## Pre-phase (risk mitigations)

1. [pin_no_plan_controls] **Before any code change**, add characterization
   tests pinning today's `no_plan` output on both paths, and run them green on
   the unmodified code:
   - collector — `tests/test_parallel_admission_collect.py`: an in-flight claim
     via `collect()` and a candidate via `resolve_candidate_surface()`;
   - gatherer path — `tests/test_trail_gather.py`: assert on the **surface the
     adapter builds** (`pa.surfaces_from_inflight_records` over the gatherer's
     `INFLIGHT_PATH:` lines, with `data_tracked`, `data_dirs`, and — once A4
     lands — `classify=plan_paths.classify`), not on raw gatherer lines, because
     A5 legitimately changes those lines.
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

Note `RATES:` / `VERDICT_FOR:` totals and every `CAUSE_RATE:` line.

**Clock pin prerequisite.** New tests that reach `col.main` must sit under
`_ReplayScaffold` (`tests/test_parallel_admission_collect.py:473-540`) or
`ExcludeNoPlanPredicateTests` (`:812-904`) so t1763's `_FrozenClock` pin covers
them. That pin is commit `44f92f5fa` on `origin/main`; confirm
`git merge-base --is-ancestor 44f92f5fa HEAD`. If it is absent, the planning
Checkpoint's Remote Drift Check offers the pull; do not add a `--now` flag to
`check` (a later "now" ages claims into the advisory tier — fail-open).

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

The frontmatter shape matches `parallel_admission_collect.strip_frontmatter`.
Update the module docstring's consumer framing ("plan-file extraction") to
mention task descriptions. No grammar change — the seam guard
`tests/test_plan_paths_seam.sh:46-69` ("no second copy of the grammar") must
stay green.

## A2. `.aitask-scripts/lib/parallel_admission_collect.py`

- `.aitask-scripts/lib/parallel_admission_sweep.py:90-98`:
  `PlanExtraction.as_surface(self, provenance="plan_declared")` — thread the
  provenance through (pure module; default keeps every caller unchanged).
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
  `_plan_surface` (`:786-800`), same cache, key `(ref, path)`; it must call the
  module-global `task_surface` so tests can patch it (read-once test).
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

## A4. `.aitask-scripts/lib/parallel_admission.py` (PURE — no new imports)

In `decide()`:
- after `surf = claim.surface or …` (`:286`): `check_member(surf.provenance,
  vocab.PROVENANCES, "inflight provenance")`.
- after the candidate-resolution check (`:262-265`):
  `if cand.resolution == "resolved" and cand.provenance == "task_declared":
  caveat("candidate", "task_declared")`.
- in the blocking branch (the `else:` at `:322`):
  `if surf.resolution == "resolved" and surf.provenance == "task_declared":
  caveat(scope, "task_declared")` — drives the verdict. A specific overlap still
  yields CONFLICT; advisory-tier claims get no `task_declared` caveat.
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
`tests/test_trail_gather.py:1907-1929`):

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
remains about plans — say so in `_corpus_status`'s docstring. Add
`task_declared` to the class list in the module docstring (`:40`) with one
sentence on the marker. No new prefix; no `NORMALIZATION_VERSION` bump (all
`INFLIGHT*` lines are emitted after `DIGEST:` and are digest-excluded,
`:1122-1128`).

`.claude/skills/aitask-trail/SKILL.md.j2:72`: add `task_declared` to the
`INFLIGHT_PATH:` class list, plus one sentence near `:88-92` describing the
marker. Regenerate its goldens:

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
Check for Codex/OpenCode copies (`ls .agents/skills/aitask-backlog-roadmap*
.opencode/skills/aitask-backlog-roadmap*`) and update them identically if they
are hand-maintained.

## Tests

- `tests/test_plan_paths.py`: `cut_task_framework_sections` cuts at the first
  header in either order; ignores `> | ## Inbox`; keeps `## Merged from t42: x`;
  `task_body_text` strips frontmatter.
- `tests/test_parallel_admission.py`: `claim()` (`:32-39`) gains
  `provenance="plan_declared"`; cases: in-flight `task_declared` no-collision →
  `VERDICT:CLEAR_CAVEATED` + `CAVEAT:inflight:t9|task_declared`; candidate
  `task_declared` → `CAVEAT:candidate|task_declared`; `task_declared` specific
  overlap → CONFLICT; advisory-tier `task_declared` → no such caveat;
  NegativeControl: never bare CLEAR with a `task_declared` surface; undeclared
  in-flight provenance → `VocabularyError`; `:126` exact row gains
  `|plan_declared`. Adapter: marker + resolved → `task_declared`; marker +
  unresolved → `no_plan`; injected classifier promotes a new file under a data
  directory; no classifier → exact membership.
- `tests/test_parallel_admission_vocab.py`: a `task_declared` fixture in
  `_fixtures()` (`:152-175`); `UpstreamDriftTests` (`:240-271`) also asserts the
  marker appears in the trail grammar line.
- `tests/test_parallel_admission_collect.py` (write `aitasks/t<N>_*.md` bodies
  into the fixture root): no plan + body naming a tracked path → resolved
  `task_declared`, not UNCHECKABLE, graded CLEAR_CAVEATED; candidate with no
  plan resolves from its description; read-once (patch `col.task_surface`, as
  `:578-625` patches `surface_from_plan`); `no_plan_claims` omits a
  `task_declared` claim; the pre-phase controls.
- `tests/test_trail_gather.py`: marker + all records for a path-bearing body;
  `no_plan` for an empty or malformed-only body; existing no-plan tests
  (`:1579-1598`, `:1837-1844`, `:1757-1762`) stay green (their body is
  `"body\n"`).
- NEW `tests/test_task_declared_parity.py` — **producer-to-adapter parity**
  (catches evidence discarded upstream, which adapter-only tests cannot): one
  tmp git repo as project root. Producer: drive `trail_gather.emit_inflight`
  with injected `_GATE_PROBE` / `_LOCK_PROBE` (`trail_gather.py:804-805`) so one
  no-plan task is in flight; feed its `INFLIGHT_PATH:` lines to
  `pa.surfaces_from_inflight_records(..., data_tracked=D, data_dirs=DD,
  classify=plan_paths.classify)`. Reference: `col.collect(...)` with
  `_DATA_TREE` stubbed to `(D, DD, None)`, `batch_lines=[]`, a pinned `now`.
  Assert identical `(paths, resolution, provenance)` for:
  1. description names only a tracked task-data file
     (`aitasks/metadata/profiles/fast.yaml` ∈ D) → resolved `task_declared`;
     control: path ∉ D → `no_plan` on both;
  2. description names only a proposed new file under a tracked task-data
     directory (`aitasks/metadata/profiles/custom.yaml`, directory ∈ DD) →
     resolved (`planned_new`) on both; control: directory ∉ DD → `no_plan`;
  3. the same new file named by a **plan** → both resolved (the adapter's
     pre-existing blind spot is closed).
- `tests/test_parallel_admission_preflight.sh`: keep the `no_plan` control
  (`:140-151`, body `other`); add an end-to-end case — the in-flight task has no
  plan and its body names `src/beta.py` → `VERDICT:CLEAR_CAVEATED` and
  `CAVEAT:inflight:200|task_declared`.

## Verification

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
"$PYTHON" -m pytest -q tests/test_plan_paths.py tests/test_parallel_admission.py \
  tests/test_parallel_admission_vocab.py tests/test_parallel_admission_collect.py \
  tests/test_parallel_admission_purity.py tests/test_trail_gather.py \
  tests/test_task_declared_parity.py
bash tests/test_parallel_admission_preflight.sh
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
the remaining UNCHECKABLE causes by name, and the prompt-producing rate
(CONFLICT + UNCHECKABLE) / candidates — t1688_2 re-measures this and decides the
shipped `parallel_admission` default on it.

## Risk

### Code-health risk: medium
- The fallback changes the in-flight surface for every consumer at once
  (preflight, roadmap, `replay`); a body cut that lets `## Inbox` prose through
  would manufacture CONFLICTs · severity: low (residual — the four no_plan
  controls are pinned before the code changes, including the section-cut case)
  · → mitigation: inline pre-phase pin_no_plan_controls
- Two line protocols change (`INFLIGHT:` 6th field, `INFLIGHT_PATH:` marker);
  the adapter files an unknown class as phantom · severity: medium ·
  → mitigation: covered in-plan — explicit marker handling with tests; the one
  exact-match consumer updated
- The gatherer (code branch only) and collector (code ∪ task-data) judge
  against different corpora · severity: medium · → mitigation: covered in-plan —
  judgement moved to the adapter with the injected shared classifier; parity
  test (existing file, new file under a data dir, plan-derived)

### Goal-achievement risk: medium
- Descriptions name files as context as well as edit targets, so
  `task_declared` overlaps are coarser than plan-derived ones · severity:
  medium · → mitigation: measure_task_declared_precision
- Only `no_plan`-driven UNCHECKABLEs are fixed; other causes remain · severity:
  medium · → mitigation: covered in-plan — the AFTER census names them;
  acceptance is the mechanism, not a corpus statistic

### Planned mitigations
- timing: pre-phase | name: pin_no_plan_controls | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — fallback changes every consumer's surface / body-cut leak | desc: pin today's no_plan output on the collector and gatherer paths (no task file, pathless body, phantom-only body, paths only under Inbox/Gate Runs) before A changes code
- timing: after | name: measure_task_declared_precision | type: enhancement | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — description surfaces may be too coarse to justify warn | desc: extend `aitask_parallel_admission.sh sweep` with a task-description source and score task_declared surfaces against landed files over the archived corpus (precision/recall, CONFLICT vs CLEAR_CAVEATED split), as t1643 did for plan surfaces

The `after` line is created at **this child's Step 8d**.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1688_1`.
