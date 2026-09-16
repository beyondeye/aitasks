---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: enhancement
status: Implementing
labels: [scheduling, planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1814]
assigned_to: dario-e@beyond-eye.com
anchor: 1569
implemented_with: claudecode/opus5
created_at: 2026-09-14 17:42
updated_at: 2026-09-16 10:01
---

## Context

Part A of t1688 (parent: `aitasks/t1688_parallel_admission_prepick_assessment_and_task_body_surface.md`;
the approved parent plan, incl. the full design rationale and the `## Risk`
section, is externalized as `aiplans/p1688_*.md`; this child's detailed plan is
`aiplans/p1688/p1688_1_*.md`).

The parallel-admission checker reads an in-flight task's file surface **only
from its plan file**. `task-workflow` sets a task `Implementing` at Step 4 but
writes the plan only at the end of Step 6, so for the whole claim→plan window
the collector builds `Surface(ref, "plan_declared", (), "no_plan")`
(`parallel_admission_collect.py:568-570`) and one unplanned in-flight task
forces UNCHECKABLE on every candidate (t1569_4 measured 88.5% UNCHECKABLE,
`no_plan` on all 122 candidates; see `aiplans/archived/p1569/p1569_4_*.md`
Final Implementation Notes :677-729). Task descriptions exist from creation and
name files. This child adds a deterministic **task-description fallback
surface**, provenance `task_declared`, graded `CLEAR_CAVEATED`.

## The invariant (the whole contract)

The fallback can only turn a `no_plan` (in-flight claim or candidate) into a
**resolved** `task_declared` surface. It never introduces a new cause and never
merges with a plan surface. A description that is unreadable, yields no tokens,
or yields only phantom/malformed tokens — judged against the **union of the
code and task-data corpora**, at whichever point both are known — leaves the
surface exactly `no_plan`. Precedence: plan → description → `no_plan`.

## Key files to modify

- `.aitask-scripts/lib/plan_paths.py` — `cut_task_framework_sections(body)`
  (truncate at the first of `## Inbox` / `## Gate Runs`; import the literals
  lazily from `note_inbox.SECTION_HEADER` / `gate_ledger.SECTION_HEADER`;
  `## Inbox` is inserted *before* `## Gate Runs`, `aitask_note.sh:94-100`) and
  `task_body_text(raw)` (strip frontmatter, then cut).
- `.aitask-scripts/lib/parallel_admission_collect.py` — `task_surface` via the
  ONE extractor `plan_extraction(..., body_transform=cut_task_framework_sections)`,
  memoised `_task_surface`, `_no_plan_fallback`; wire into `collect()` (in-flight)
  and `resolve_candidate_surface()` (candidate; `--from auto`'s origin fallback
  runs only if still unresolved); `no_plan_claims` docstring.
- `.aitask-scripts/lib/parallel_admission_vocab.py` — `PROVENANCES +=
  ("task_declared",)`; `CAVEAT_REASONS["task_declared"] = NONE`.
- `.aitask-scripts/lib/parallel_admission.py` (PURE) — `decide`: validate
  in-flight provenance; `caveat("candidate"|"inflight:<ref>", "task_declared")`
  for blocking claims / the candidate (drives CLEAR_CAVEATED; a specific overlap
  stays CONFLICT); checker `INFLIGHT:` row gains a 6th `|<provenance>` field
  (document the row grammar). `surfaces_from_inflight_records` /
  `input_from_records`: handle the `task_declared` marker explicitly; phantom
  promotion via an **injected** classifier (`classify=plan_paths.classify`) over
  `data_tracked` + `data_dirs` — this module cannot import `plan_paths` (it
  imports `subprocess`, poisoned by `tests/test_parallel_admission_purity.py`).
- `.aitask-scripts/lib/trail_gather.py` — `_classify_plan_paths` (signature and
  4-tuple unchanged): no plan + no non-malformed token → `no_plan`; otherwise
  emit `INFLIGHT_PATH:<ref>|task_declared|-` then **every** classified record
  (the gatherer sees the code branch only, so it must not judge phantom-only).
  Grammar line in the module docstring (`:40`).
- `.claude/skills/aitask-trail/SKILL.md.j2:72` (+ 3 goldens
  `tests/golden/skills/aitask-trail/SKILL-*-claude.md`) — add the marker to the
  class list.
- `.claude/skills/aitask-backlog-roadmap/SKILL.md:215-218` — stale "t1688 owns
  that gap" sentence.

## Reference files / patterns

- `collect.plan_extraction` / `surface_from_plan` / `_plan_surface` (memo).
- Tests: `tests/test_parallel_admission.py` helpers (`surface`, `claim`,
  `build`); `tests/test_parallel_admission_collect.py` seam scaffolds
  (`_ReplayScaffold` :473-540, `ExcludeNoPlanPredicateTests` :812-904) — new
  tests reaching `col.main` must sit under them so t1763's `_FrozenClock` pin
  (commit 44f92f5fa, on origin/main) covers them; `tests/test_trail_gather.py`
  `InflightCase` (`write_task(..., body=...)`).

## Implementation order

1. **Pre-phase `pin_no_plan_controls` (risk mitigation, inline):** before any
   code change, add characterization tests pinning today's `no_plan` on both
   paths (collector; gatherer asserted on the adapter's surface): no task file;
   pathless body; body naming only paths resolvable in neither corpus; body
   whose only real paths sit under `## Inbox` / `## Gate Runs`. Confirm they
   pass on unmodified code.
2. Record the BEFORE census: `./.aitask-scripts/aitask_parallel_admission.sh
   replay --candidates auto --from plan --lock-freshness require-fresh`.
3. A1 → A5 as above, with tests (see the child plan's Tests section, incl. the
   new `tests/test_task_declared_parity.py` producer-to-adapter parity:
   existing task-data file, new file under an existing task-data directory,
   plan-derived path; each with a control).
4. Record the AFTER census in Final Implementation Notes — t1688_2 decides the
   shipped `parallel_admission` default on it.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (last line only);
  `bash tests/test_parallel_admission_preflight.sh`;
  `bash tests/test_skill_render_aitask_trail.sh`; `bash tests/test_plan_paths_seam.sh`.
- Live: `check --candidate <a Ready task> --from plan --lock-freshness
  require-fresh` no longer reports `no_plan` for in-flight tasks whose
  descriptions name files; they grade CLEAR_CAVEATED with
  `CAVEAT:inflight:<ref>|task_declared`.

## Risk mitigations carried from the parent plan

- pre-phase `pin_no_plan_controls` (above).
- after `measure_task_declared_precision` — create at this child's Step 8d:
  extend `aitask_parallel_admission.sh sweep` with a task-description source and
  score `task_declared` surfaces against landed files over the archived corpus.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-15T06:14:13Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-16T06:58:25Z status=pass attempt=1 type=human
