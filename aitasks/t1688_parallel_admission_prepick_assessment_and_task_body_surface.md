---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Implementing
labels: [scheduling, skills, task_workflow, aitask_pick, planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
created_at: 2026-09-02 14:47
updated_at: 2026-09-02 14:50
---

Make parallel admission actually usable: give the checker an evidence source
that exists for tasks in the claim→plan window, and move the *first* safety
question to where the user asks it — **before the pick**, as an agent-judgement
assessment over what is in flight.

## Problem

The t1569_4 preflight (`.claude/skills/task-workflow/parallel-admission.md`,
shipped advisory-only) is unusable as delivered, and t1569_4's own Final
Implementation Notes say so in numbers: over 122 live candidates, **0% CLEAR,
0% CLEAR_CAVEATED, 11.5% CONFLICT, 88.5% UNCHECKABLE**, with `no_plan` firing on
all 122. Re-measured 2026-09-02 during exploration:

- 14 tasks `Implementing`; **7 have no plan file** (t1669, t1675, t1677, t1681,
  t1685, t1576, t1555_2).
- `aitask_parallel_admission.sh check --candidate 1569_4 --from plan …` →
  `VERDICT:UNCHECKABLE` with five live `UNCHECKABLE_CAUSE:inflight:<id>|no_plan`
  lines. **One unplanned in-flight task poisons every candidate's verdict.**

The root cause is structural, not a tuning problem. `task-workflow` sets a task
`Implementing` and locks it at **Step 4**, and the plan is externalized only at
the end of **Step 6** (`plan-externalization.md`, after `ExitPlanMode`). The
checker's in-flight side reads **only plan files**
(`lib/trail_gather.py:_classify_plan_paths` → `no_plan`;
`lib/parallel_admission_collect.py` builds `Surface(ref, "plan_declared", (),
"no_plan")`). It never opens the in-flight task's description. So for the whole
claim→plan window — which is where most in-flight tasks sit at any moment — the
task is invisible, and `decide()` correctly refuses to call anything CLEAR.

Meanwhile the manual practice this replaced was more effective: before picking,
ask a code agent *"given the current in-flight tasks, is it safe to pick t<N>?"*.
The agent reads the in-flight task **descriptions** (which exist from creation),
reasons semantically about overlap (same script, same procedure file, same
subsystem), and answers with specifics. Nothing in `aitask-pick` does this today:
Step 2.0 lists in-flight tasks only as *resume candidates*, and Step 2 offers no
parallel-safety information before the claim. The preflight runs one plan later
than the question is actually asked.

t1569 rejected agent judgement as "judgement, not a guard". That argument no
longer bites: by explicit user decision the preflight **is** advisory and nothing
stops the workflow on its own — an advisory signal may be produced by an agent.

## Measured: task descriptions carry usable surfaces

`plan_paths.extract()` over the bodies of the 7 no-plan in-flight tasks, filtered
to `git ls-files`:

| task | tokens | tracked paths (examples) |
|---|---|---|
| t1685 | 10 | 7 — `lib/agent_marks.py`, monitor/minimonitor docs, tests |
| t1555_2 | 15 | 7 — `aitask_revert_analyze.sh`, `aitask_update.sh`, `manual-verification-followup.md`, `CLAUDE.md` |
| t1677 | 9 | 2 — `board/aitask_board.py`, `settings/settings_app.py` |
| t1675 | 5 | 1 — `lib/attachment_lock.sh` |
| t1669 | 2 | 1 — `lib/ledger_block.py` |
| t1681 | 1 | 1 — `lib/ledger_block.sh` |
| t1576 | 1 | 1 — `monitor/minimonitor_app.py` |

**Every one** yields at least the primary file. A description-derived surface is
coarser than a plan's, but it is not `no_plan`, and it would have zeroed today's
UNCHECKABLE causes.

## Deliverables

### A. Checker: task-description fallback surface (deterministic, both consumers)

When an in-flight task has no plan, derive its surface from the **task file
body** (frontmatter stripped, `## Gate Runs` and below excluded) through the same
`plan_paths.extract` + corpus classification the plan path uses. Contract:

- New surface `source` value **`task_declared`** (alongside `plan_declared` /
  `origin_derived`), and a matching `INFLIGHT:` / `INFLIGHT_PATH:` provenance so a
  consumer can tell a description-derived surface from a plan-derived one. Extend
  the closed vocabulary in `lib/parallel_admission_vocab.py` — do not smuggle it
  through an existing code.
- `no_plan` remains the cause **only** when the body also yields no classifiable
  path (`no_tokens` / `no_extractable_paths` otherwise). The precedence is
  plan → description → `no_plan`; never merge the two surfaces.
- A `task_declared` surface on any in-flight claim is **unverified evidence**:
  a no-collision result against it grades **`CLEAR_CAVEATED`** (`CAVEAT:
  inflight:<ref>|task_declared`), never bare `CLEAR`. That keeps the honesty rule
  ("CLEAR = fully evidenced on both sides") intact.
- Both consumers see it for free: the preflight (`--from plan`) and the roadmap
  (`input_from_records` over `trail_gather` lines). `trail_gather.py`'s
  `INFLIGHT_PATH:` classifier is the single place to add it — the lines are
  digest-excluded, so no `NORMALIZATION_VERSION` bump.
- Also apply it to the **candidate** side when `--from plan` is called for a
  task with no plan yet (the pre-pick call in B), with `CANDIDATE:<ref>|task_declared|…`.
- Re-run `aitask_parallel_admission.sh replay --candidates auto --from plan
  --lock-freshness require-fresh` before/after and record the rate shift in the
  Final Implementation Notes. Acceptance is the **mechanism** (a no-plan claim
  with a path-bearing description no longer forces UNCHECKABLE), not a corpus
  statistic.

### B. `aitask-pick`: pre-claim parallel-safety assessment (agent judgement)

A new procedure — proposed `.claude/skills/task-workflow/parallel-assessment.md`
(shared closure, so Codex/OpenCode auto-render) — invoked from `aitask-pick`
**after the task is selected (Step 2c/2d) and before the hand-off to Step 3**,
i.e. before Step 4 claims and locks it. It answers the user's question the way
the user used to ask it:

1. Gather the in-flight population from the **union** t1569_1 already computes
   (`aitask_query_files.sh inflight` ∪ `ait lock --list` ∪ `status: Implementing`)
   — do not re-derive it; call the gatherer or the checker, whichever exposes it
   with liveness (`live` / `dead` / `lock_only`).
2. For each live in-flight task read its **task description** and its plan when
   one exists; read the candidate's description.
3. Run the checker (`check --candidate <id> --from plan --lock-freshness
   require-fresh`; after A the candidate resolves from its description) and take
   its `OVERLAP:` / `CAVEAT:` / `UNCHECKABLE_CAUSE:` lines as **structured
   input**, not as the answer.
4. Produce a short assessment: per in-flight task, `overlaps / adjacent / unrelated`
   with the concrete reason (shared file, shared procedure, same subsystem, same
   seed mirror), plus an overall recommendation. Print the checker's `DISPLAY:`
   line verbatim beneath it, labelled as the deterministic view.
5. `AskUserQuestion` (findings **inside the question text** — same visibility
   rule as `aitask-explore`): "Pick anyway" / "Pick a different task" / "Stop".
   Continue is first; nothing is ever selected automatically.

Profile knob: `parallel_assessment: ask | show | off` (default `show`: render
the assessment, no prompt unless the agent grades any task `overlaps`); headless
profiles (`remote`, pickrem/pickweb) must use `off` or `show`. Skip entirely when
the selected task is itself in-flight (resume path — Step 2.0 / Step 0b).

Keep the existing post-plan preflight: once the plan exists it is the more
precise, plan-derived second look at the planning Checkpoint and on IMPLEMENT
re-entry. Two call sites, two evidence qualities, one checker. Say so in
`parallel-admission.md`'s Notes and in the website page.

### C. Coordination

- **t1569_4** (Implementing, at Step 8 review as of 2026-09-02): ships with
  `parallel_admission: "off"` in the shipped profiles and seed mirrors pending
  this task; this task flips the shipped default back to `warn` once A lands.
  Keep the knob semantics (`confirm | warn | off`) unchanged.
- **t1569** parent / **t1569_7** MV checklist: the `[t1569_4]` items must be
  verified under a profile that sets `confirm`, and the CLEAR_CAVEATED
  rendering item gains the `task_declared` caveat. Add a bidirectional note.
- **t1569_6** (roadmap skill): benefits from A automatically; note that its
  parallel-safe lane was empty by construction before A.
- **t1343** (declared per-task edit manifest): remains the only admissible basis
  for a *hard* stop; a `task_declared` surface is a description heuristic, not a
  declaration. Add a forward pointer there; do not fold.
- **t1470** (By-Trail intra-wave safety rendering): consumer of the same
  verdicts; cross-reference only.
- Ordering vs. `resource-admission.md` is unchanged: B runs before the claim,
  the resource hook still runs last before the fork.

## Key files

- `.aitask-scripts/lib/trail_gather.py` (`_classify_plan_paths`, `INFLIGHT_PATH:`
  contract in the module docstring), `.aitask-scripts/lib/parallel_admission_collect.py`
  (`plan_path_for`, `surface_from_plan`, `resolve_candidate_surface`),
  `.aitask-scripts/lib/parallel_admission.py` (`decide`, `_INVISIBLE_SURFACE`,
  caveat grading), `.aitask-scripts/lib/parallel_admission_vocab.py`.
- `.claude/skills/aitask-pick/SKILL.md.j2` (Step 2c/2d → new step), new
  `.claude/skills/task-workflow/parallel-assessment.md`, `profiles.md`,
  `aitasks/metadata/profiles/*.yaml` + `seed/profiles/` mirrors, goldens under
  `tests/golden/procs/`.
- `website/content/docs/skills/aitask-pick/parallel-admission.md` (extend or add
  a sibling page), `execution-profiles.md`.
- Tests: `tests/test_parallel_admission_preflight.sh`, the checker's Python
  tests (fixture: a no-plan claim whose body names a tracked path → not
  UNCHECKABLE, graded CLEAR_CAVEATED; a no-plan claim with an empty body → still
  UNCHECKABLE), a pick-skill render/contract test pinning the assessment sits
  before Step 3 hand-off and is skipped on the resume path.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`; goldens regenerated in the same
  commit.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read the last line only.
- Live: `aitask_parallel_admission.sh check --candidate <a Ready task> --from
  plan …` against the real in-flight population no longer returns
  `no_plan`-driven UNCHECKABLE for tasks whose descriptions name files.
- Live: `/aitask-pick` on a Ready task shows the assessment before the claim,
  naming the specific in-flight tasks and why; `/aitask-pick <in-flight id>`
  skips it.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1763** id=2026-09-14T08:44:14Z.2e3993830fe7bc0b49e77eaf from=t1763 from_verified=yes at=2026-09-14T08:44:14Z base=44f92f5fa8428ff0838c24e768b6fe0838e7e6b9 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | Advisory context from t1763 (commit 44f92f5fa on main) — not an instruction.
> | 
> | tests/test_parallel_admission_collect.py now pins the collect module's clock:
> | a `_FrozenClock` stand-in for `parallel_admission_collect.time` (pinned
> | `time()`, every other attribute delegated to the real module) is installed via
> | the existing save/restore seam tuple in `_ReplayScaffold.setUp` (covering its
> | four subclasses) and `ExcludeNoPlanPredicateTests.setUp`, pinned to
> | 2026-08-30 08:05.
> | 
> | Why: the replay / sweep / check CLI path (`col.main`) exposes no `now`, so
> | `collect()` falls back to `time.time()` (parallel_admission_collect.py:513 at
> | this SHA). Fixture claims locked at 2026-08-30 08:00 crossed MAX_CLAIM_AGE_S
> | (14 days) and four tests failed with nothing else changed. Freezing the clock
> | confirmed it: pass at the fixture's time and at +13 days, fail at +15 days.
> | 
> | If t1688 adds or changes tests that reach `col.main`, they need the same pin —
> | or a `--now` / clock seam on the CLI path, which would let tests stop patching
> | the module. If t1688 changes where `collect()` reads the clock, the
> | `_FrozenClock` install sites are the two setUp methods above.

> **✉ note:t1794_1** id=2026-09-14T11:15:14Z.d75d0dc946892e17d1c46595 from=t1794_1 at=2026-09-14T11:15:14Z base=c52534f142accc950314fba49d53fe32bb6ecd59 base_branch=main dirty=no host=omg16
>
> | Advisory (from t1794_1, claimed): tests/test_parallel_admission_collect.py has
> | 4 failures that are fixture date rot, not a regression — as of 2026-09-14.
> | 
> | Failing: ReplayInvariantTests::test_the_inflight_task_is_still_compared_when_listed_first,
> | ExcludeNoPlanPredicateTests::test_only_the_blocking_no_plan_claim_is_selected,
> | ExcludeNoPlanPredicateTests::test_the_flag_removes_the_cause_it_names,
> | ThresholdSweepTests::test_the_threshold_override_reaches_the_verdict.
> | 
> | Cause: the _ReplayScaffold fixture (:500) and ExcludeNoPlanPredicateTests.LIVE
> | (:830) hard-code locked_at "2026-08-30 08:00" while the replay path reads the
> | wall clock; MAX_CLAIM_AGE_S = 14 d (lib/parallel_admission.py:47), so since
> | 2026-09-13 08:00 the in-flight holder reads as a stale claim. Clock-pinned
> | proof: in-process, all four FAIL on the wall clock and PASS with time.time
> | pinned to the file's own parse_ts("2026-08-30 08:05"). Line numbers are as of
> | the base commit recorded with this note.
> | 
> | The fix is owned by t1799 (fix_parallel_admission_replay_fixture_date_rot). If
> | your session sees a red Python suite there, it is this, not your change —
> | check against t1799 rather than trusting this note.

> **✉ note:t1794_1** id=2026-09-14T11:30:26Z.d262a6b86ca74635ff0f3184 from=t1794_1 at=2026-09-14T11:30:26Z base=c52534f142accc950314fba49d53fe32bb6ecd59 base_branch=main dirty=no host=omg16
>
> | Advisory (from t1794_1, claimed) — correction to my note
> | 2026-09-14T11:15:14Z.d75d0dc946892e17d1c46595 above.
> | 
> | That note says the date-rot fix for tests/test_parallel_admission_collect.py is
> | owned by t1799. It is not: t1763 had already fixed it on origin/main in commit
> | 44f92f5fa (the `_FrozenClock` pin), as t1763's own note above in this ## Inbox
> | says. t1794_1 missed it because its local main was 2 commits behind origin/main.
> | If your checkout contains 44f92f5fa those four tests pass; t1799 has been told
> | its date-rot half is already done.
