---
priority: high
effort: high
depends: [t1569_1, t1569_2]
issue_type: feature
status: Ready
labels: [scheduling, planning, git]
gates: [risk_evaluated]
anchor: 1569
created_at: 2026-08-27 11:28
updated_at: 2026-08-27 11:29
---

The **single definition of "safe"** for parallel work. Slice 3 of 6 for t1569 —
read the parent task and
`aiplans/p1569_background_work_roadmap_trail_for_followup_backlog.md` first.

Depends on t1569_1 (gatherer in-flight facts) and t1569_2 (file sets + origin
resolution). **Set `depends: [t1569_1, t1569_2]`** — the sibling default only
records t1569_2.

## Context

The framework has ownership locks, a remote-drift check and worktree/merge
protection, but **no authoritative check against other active tasks**. An agent
may notice a collision while planning; that is judgement, not a guard.

**One shared checker, two consumers** — t1569_4 (`task-workflow` required
preflight) and t1569_5 (roadmap advisory preview). Two implementations would mean
two subtly different definitions of "safe", which is exactly what this task
exists to prevent. **All collision verdicts are computed here and nowhere else.**

## Contract

`./.aitask-scripts/aitask_parallel_admission.sh` — a shell entry point (so it is
whitelistable for skills and callable from `task-workflow`) over a pure Python
lib.

```
check --candidate <id> --from plan|origin [--plan <path>]
      --lock-freshness require-fresh|allow-cached [--max-lock-age <s>]

CANDIDATE:<ref>|<plan_declared|origin_derived>|<n_paths>|<resolved|unresolved:<reason>>|<exact|topic|unknown|n/a>
LOCKS:<fetched|cached|unavailable>|<age_seconds|->
INFLIGHT:<ref>|<source>|<live|lock_only|dead|unknown>|<n_paths>|<tracked|phantom|mixed|none>
OVERLAP:<ref>|<path>
NARROWED:<path>|<n_tasks_touching>
CAVEAT:<inflight:<ref>|locks>|<reason>
UNCHECKABLE_CAUSE:<candidate|inflight:<ref>|locks>|<reason>
DISPLAY:<one-line human summary>
VERDICT:<CLEAR|CLEAR_CAVEATED|CONFLICT|UNCHECKABLE>
```

Follow `aitask_verification_stale.sh`'s conventions **verbatim**: line protocol,
one record per line with the free-ish field last; **always exit 0** for every
content state while CLI misuse still dies; `%`-then-`|` injective path encoding
(`%` first is what makes it injective); `:(literal)` pathspec guard on every
`git log -- <path>`; a closed reason vocabulary.

### Verdicts — four values, and `CLEAR_CAVEATED` is not folded into `CLEAR`

- **CLEAR** — fully evidenced on **both** sides, no collision found.
- **CLEAR_CAVEATED** — no collision found, but at least one source's evidence was
  *unverified* rather than absent: a `lock_only` source, a holder whose liveness
  is `unknown`, or a cached lock ref under `allow-cached`. **Visually distinct
  from CLEAR**, and requires confirmation under the blocking profile. Collapsing
  it into CLEAR would make a real-but-unverified holder look identical to a fully
  evidenced all-clear.
- **CONFLICT** — named overlapping task(s) and file(s).
- **UNCHECKABLE** — the comparison could not be made at all. Never rendered as
  CLEAR. `CLEAR_CAVEATED` and `UNCHECKABLE` are deliberately distinct: "I
  compared and found nothing, but one input was unverified" and "I could not
  compare" have different remedies.

### CLEAR is an observation, not a reservation

The checker takes a snapshot; it does **not** reserve the candidate's planned
surface. Another agent can begin overlapping work in the instant after
`VERDICT:CLEAR` — the task lock reserves the *task*, never the *file surface*.
So the wording is fixed everywhere it surfaces as **"no known conflict at check
time"**, never "safe to run in parallel". The residual race closes only when
**t1343**'s declared-claims backend is adopted (its per-task claim registry,
written at plan externalization and reaped fail-closed, is the reservation this
checker deliberately does not attempt). Document the residual; do not paper over
it.

## Three hazards the verdict logic must close by construction

### (a) Self-exclusion

`task-workflow` claims the candidate at **Step 4** — it sets `status:
Implementing` **and** acquires the lock — long before Step 6 writes the plan.
Verified live: while t1569 was being planned it was `Implementing` and appeared
in `ait lock --list`. Since the checker unions both sources, **the candidate
lands in its own comparison set and overlaps every path of its own approved
plan** — a guaranteed CONFLICT on every pick.

Exclude the candidate ref from **every** source (`inflight`, `lock --list`, and
the derived surfaces) *before* overlap is evaluated — not by filtering results
afterwards. Fixture-test that a candidate never conflicts with itself, with the
candidate deliberately present in both sources.

### (b) An unresolved candidate surface is UNCHECKABLE, not CLEAR

An empty intersection is meaningless when the candidate side is unknown. Emit
`CANDIDATE:...|unresolved:<reason>` -> UNCHECKABLE for **each** of:

| shape | live incidence |
|---|---|
| plan yields **no extractable paths** (extension list misses the project's language) | 0/108 here, structural elsewhere |
| **every** extracted path is `phantom` (fails `git ls-files`) | **22 of 108 active plans (20%)** |
| the remainder is empty only **because narrowing removed it** | must not silently become CLEAR |
| `UNKNOWN_HISTORY` from t1569_2 (`--from origin`) | 41 of 260 candidates |
| `unknown` origin quality (`--from origin`) | 13 of 229 follow-ups |

### (c) Lock freshness is a parameter, not a fixed behaviour

t1569_1's gatherer reads `origin/aitask-locks` **without fetching** so the shared
gatherer stays offline-safe — correct for an estimate, fatal for an admission
decision: a stale ref hides a lock another agent took seconds ago, producing a
false CLEAR at exactly the point meant to prevent concurrent work.

One verdict logic, one explicit knob. `require-fresh` (the preflight) attempts a
bounded fetch and, if the fetch fails or the ref is older than `--max-lock-age`,
emits `LOCKS:cached|<age>` or `LOCKS:unavailable` -> **UNCHECKABLE**.
`allow-cached` (the roadmap) accepts the cached read and labels it. **Neither
mode may report CLEAR on lock evidence it could not establish.**

## Provenance-aware narrowing — settle this BEFORE writing the verdict logic

The verdict vocabulary and evidence rules are single-sourced, but the two
provenances have measurably different noise:

- **plan-declared** sets are sparse: any given hub file appears in only 2-8 of
  107 active plans;
- **origin-derived** sets are broad: median 11 files, p90 39, max 272, and
  **57 of 260** candidates' sets contain `.aitask-scripts/board/aitask_board.py`
  (28 contain `.claude/skills/task-workflow/SKILL.md`).

Without narrowing the origin-derived side fires on ~22% of the corpus. Same
lesson `aidocs/framework/manual_verification_staleness.md` records: *"Narrowing
is mandatory"* — t632's unfiltered set includes hub files touched by 91/73/72
tasks.

The checker therefore takes the candidate set **plus its provenance** and narrows
accordingly. **Emit every dropped path as a `NARROWED:` record** so the narrowing
is auditable rather than silent.

## Availability is a design constraint, not just something to measure

A naive rule — *any* incomplete in-flight source makes the candidate UNCHECKABLE
— yields **UNCHECKABLE for 100% of picks today**: 2 of the 4 non-candidate
`Implementing` tasks have no plan at all (t1576, t1555_2), and t259's is
all-phantom. A guard that prompts on every pick is one the user learns to
dismiss — the same failure `manual_verification_staleness.md` records ("otherwise
the user is re-prompted forever and learns to ignore it").

Three structural mitigations, settled here alongside the narrowing rule:

1. **UNCHECKABLE is per-source and named, never global.** `UNCHECKABLE_CAUSE:`
   identifies *which* in-flight task could not be ruled out, so the consumer can
   say "cannot rule out a collision with **t1576** (no plan file)" and offer a
   concrete per-task remedy.
2. **Classify the in-flight source rather than blindly unioning it.** Tag each
   `live` (`Implementing`, lock alive), `lock_only` (locked but not
   `Implementing` — t259 has been so since 2026-02-26), `dead` (holder provably
   dead via `lib/pid_anchor.sh::lock_holder_liveness`) or `unknown` (no liveness
   token — every pre-PID-anchor lock, t259 included; note `lock_holder_liveness`
   returns `unknown`, not `dead`, when the token is absent).
   A `dead` holder is not concurrent work and drops out. A `lock_only` or
   `unknown` source still produces **CONFLICT** on a real path overlap; when it
   produces no overlap it downgrades the verdict to **`CLEAR_CAVEATED`** with a
   `CAVEAT:` record — **never plain CLEAR**. That downgrade is what keeps this
   mitigation from buying availability at the cost of silent under-reporting.
3. **Verdict-rate metric, and it gates the default.** Emit a `RATES:` summary
   over a replay. Both a high false-CONFLICT rate and a high UNCHECKABLE rate are
   ship blockers for t1569_4's blocking default.

## Key files

- New `.aitask-scripts/aitask_parallel_admission.sh` + its pure Python lib under
  `.aitask-scripts/lib/`.
- Consumes: t1569_1's `INFLIGHT:` / `INFLIGHT_PATH:` / `INFLIGHT_SCAN:` lines and
  its extracted plan-path helper; t1569_2's batch map and `lib/followup_origin.py`.

## Reference files for patterns

- `.aitask-scripts/aitask_verification_stale.sh` — the whole convention set:
  always-exit-0 split (L26-32), tri-state ordering (L34-41), UNKNOWN-drives-the-
  verdict (L48-53), `:(literal)` pathspec hazard (L55-65), `_enc()` (L122-127).
- `.aitask-scripts/lib/pid_anchor.sh` — `lock_holder_liveness` (L148-173),
  `_pid_exists` tri-state (L115-126).
- `.aitask-scripts/aitask_lock.sh` — `list_locks()` L414-462 (note: it fetches;
  note the `info()`-to-stdout degenerate paths); `check_lock()` L378-401.
- `tests/test_change_surface.sh` — synthetic-git-repo fixture scaffold.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (last line only)
- `shellcheck .aitask-scripts/aitask_parallel_admission.sh`

Required tests — **overlap, no-overlap, missing-plan, all-phantom-plan,
unknown-history, hub-narrowed, self-as-candidate, stale-locks,
unresolved-candidate-surface, lock-only-holder, unknown-liveness-holder** — plus:

- determinism (same fixture twice -> byte-identical output);
- negative controls proving that a narrowed path, an empty candidate surface, and
  an unverified holder can **none** of them produce plain `CLEAR`;
- a measured false-positive rate for `--from plan` over a replay of recent real
  picks, recorded in the Final Implementation Notes — it is t1569_4's entry
  criterion.
