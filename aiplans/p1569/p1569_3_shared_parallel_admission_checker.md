---
Task: t1569_3_shared_parallel_admission_checker.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_1_*.md, aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_5_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
---

# t1569_3 — The shared parallel-admission checker

The **single definition of "safe"**. Two consumers: t1569_4 (`task-workflow`
required preflight) and t1569_5 (roadmap advisory preview). All collision
verdicts are computed here and nowhere else.

## Step 1 (before any verdict logic) — settle the narrowing rule

The verdict vocabulary is single-sourced, but the two provenances have measurably
different noise:

| provenance | shape |
|---|---|
| `plan_declared` | sparse — any given hub file appears in only **2–8 of 107** active plans |
| `origin_derived` | broad — median 11 files, p90 39, max 272; **57 of 260** candidates' sets contain `.aitask-scripts/board/aitask_board.py`, 28 contain `.claude/skills/task-workflow/SKILL.md` |

Without narrowing the origin-derived side fires on ~22% of the corpus. Same
lesson `aidocs/framework/manual_verification_staleness.md` records: *"Narrowing
is mandatory"* — t632's unfiltered set includes hub files touched by 91/73/72
tasks.

So the checker takes the candidate set **plus its provenance** and narrows
accordingly. Use t1569_2's `COMMIT:` index for the touch count. Emit **every**
dropped path as `NARROWED:<path>|<n_tasks_touching>` so the narrowing is
auditable rather than silent, and pick the threshold from measurement, not
intuition.

Write the chosen rule and its threshold into the task's Final Implementation
Notes — t1569_5's design record cites it.

## Step 2 — The CLI and line protocol

```
./.aitask-scripts/aitask_parallel_admission.sh check \
    --candidate <id> --from plan|origin [--plan <path>] \
    --lock-freshness require-fresh|allow-cached [--max-lock-age <s>]
```

Shell entry point over a pure Python lib — the shell is what makes it
whitelistable for skills and callable from `task-workflow`; the Python is what
makes the verdict logic fixture-testable without git.

```
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

Copy `aitask_verification_stale.sh`'s conventions verbatim:

- one record per line, free-ish field **last**, split with
  `maxsplit = fieldcount - 1`;
- **always exit 0** for every content state; CLI misuse (missing verb, absent
  `--plan` target) still `die`s — a silent verdict for a typo'd path is the
  "silent-skip masks a broken implementation" hazard (`aitask_verification_stale.sh:26-32`);
- `_enc()`-style path encoding: `%` → `%25` **first**, then `|` → `%7C`. The
  `%`-first order is what makes it injective;
- `:(literal)` on every `git log -- <path>` — `*`, `?`, `[...]` are legal
  filename characters that git fnmatch-globs as pathspecs;
- closed reason vocabularies for `CAVEAT:` and `UNCHECKABLE_CAUSE:`.

## Step 3 — Verdicts

Four values. `CLEAR_CAVEATED` is deliberately **not** folded into `CLEAR`.

| verdict | meaning |
|---|---|
| `CLEAR` | fully evidenced on **both** sides, no collision found |
| `CLEAR_CAVEATED` | no collision found, but at least one source's evidence was *unverified* rather than absent |
| `CONFLICT` | named overlapping task(s) and file(s) |
| `UNCHECKABLE` | the comparison could not be made at all |

`CLEAR_CAVEATED` and `UNCHECKABLE` are distinct because their remedies differ:
"I compared and found nothing, but one input was unverified" versus "I could not
compare". Collapsing the former into `CLEAR` would make a real-but-unverified
holder look identical to a fully evidenced all-clear.

### CLEAR is an observation, not a reservation

The checker takes a snapshot; it does **not** reserve the candidate's planned
surface. Another agent can begin overlapping work in the instant after
`VERDICT:CLEAR` — the task lock reserves the *task*, never the *file surface*.

Fix the wording at the source: the `DISPLAY:` line says **"no known conflict at
check time"**, never "safe to run in parallel". Both consumers inherit it.
Document the residual in the helper's header comment; it closes only when
**t1343**'s declared-claims backend is adopted (a per-task claim registry written
at plan externalization and reaped fail-closed is the reservation this checker
deliberately does not attempt).

## Step 4 — Self-exclusion (hazard a)

`task-workflow` claims the candidate at **Step 4** — `status: Implementing` **and**
the lock — long before Step 6 writes the plan. Verified live: while t1569 was
being planned it was `Implementing` and appeared in `ait lock --list`.

Since the checker unions both sources, the candidate lands in its own comparison
set and overlaps every path of its own approved plan: a guaranteed `CONFLICT` on
every pick.

**Remove the candidate ref from every source before overlap is evaluated** —
`INFLIGHT:` construction, the lock list, and the derived surfaces. Not by
filtering results afterwards: a post-filter leaves `INFLIGHT:` and
`INFLIGHT_SCAN:` counts wrong and the next reader re-introduces the bug.

Match on the canonical ref, and handle `N` / `N_M` / `tN` spellings — the
candidate may be a child.

## Step 5 — Unresolved candidate surface ⇒ UNCHECKABLE (hazard b)

An empty intersection is meaningless when the candidate side is unknown. Emit
`CANDIDATE:...|unresolved:<reason>` → `UNCHECKABLE` for each of:

| reason | live incidence |
|---|---|
| `no_extractable_paths` — the extension list misses the project's language | 0/108 here, structural elsewhere (findings doc §1) |
| `all_phantom` — every extracted path fails `git ls-files` | **22 of 108 active plans (20%)** |
| `all_narrowed` — the remainder is empty only because narrowing removed it | — |
| `unknown_history` — from t1569_2, `--from origin` | 41 of 260 candidates |
| `unknown_origin` — `unknown` resolution quality, `--from origin` | 13 of 229 follow-ups |

`all_narrowed` is the subtle one: narrowing must not be able to manufacture a
CLEAR by emptying the candidate side.

## Step 6 — Lock freshness as a parameter (hazard c)

t1569_1's gatherer reads `origin/aitask-locks` **without fetching** so the shared
gatherer stays offline-safe — right for an estimate, fatal for an admission
decision: a stale ref hides a lock another agent took seconds ago.

One verdict logic, one explicit knob:

- `require-fresh` (t1569_4) — attempt a bounded fetch. On fetch failure, or a ref
  older than `--max-lock-age`, emit `LOCKS:cached|<age>` or `LOCKS:unavailable`
  → **UNCHECKABLE**.
- `allow-cached` (t1569_5) — accept the cached read and label it
  `LOCKS:cached|<age>`; contributes a `CAVEAT:` rather than UNCHECKABLE.

**Neither mode may report `CLEAR` on lock evidence it could not establish.**

## Step 7 — Availability

A naive rule — any incomplete in-flight source ⇒ UNCHECKABLE — yields
**UNCHECKABLE on 100% of picks today**: 2 of the 4 non-candidate `Implementing`
tasks have no plan (t1576, t1555_2) and t259's is all-phantom. A guard that
prompts on every pick is one the user learns to dismiss.

1. **Per-source, named.** `UNCHECKABLE_CAUSE:inflight:<ref>|no_plan_file` lets
   the consumer say "cannot rule out a collision with **t1576**" and offer a
   per-task remedy, instead of an undifferentiated "something is unknown".
2. **Classify, do not blindly union.** Per in-flight source:

   | class | test | effect when no overlap |
   |---|---|---|
   | `live` | `Implementing`, holder `alive` | evidenced — allows `CLEAR` |
   | `lock_only` | locked, `status != Implementing` (t259 since 2026-02-26) | `CAVEAT:` → `CLEAR_CAVEATED` |
   | `dead` | holder provably `dead` | dropped — not concurrent work |
   | `unknown` | no liveness token (every pre-PID-anchor lock, t259 included) | `CAVEAT:` → `CLEAR_CAVEATED` |

   Use `lib/pid_anchor.sh::lock_holder_liveness` (L148-173) — note it returns
   `unknown`, **not** `dead`, when the token is absent, and `is_lock_holder_alive`
   collapses both to false, so the **tri-state** is required here.

   A `lock_only` / `unknown` source still produces **CONFLICT** on a real path
   overlap. It only affects the no-overlap case.
3. **`RATES:` summary** over a replay — CLEAR / CLEAR_CAVEATED / CONFLICT /
   UNCHECKABLE counts. Both a high false-CONFLICT rate and a high UNCHECKABLE
   rate are ship blockers for t1569_4's blocking default.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
shellcheck .aitask-scripts/aitask_parallel_admission.sh
./.aitask-scripts/aitask_parallel_admission.sh check --candidate 1569 --from plan \
    --lock-freshness allow-cached
```

Required fixtures — **overlap, no-overlap, missing-plan, all-phantom-plan,
unknown-history, hub-narrowed, self-as-candidate, stale-locks,
unresolved-candidate-surface, lock-only-holder, unknown-liveness-holder** — plus:

- **determinism**: same fixture twice → byte-identical output;
- **negative controls**: a narrowed path, an empty candidate surface, and an
  unverified holder must **none** of them be able to produce plain `CLEAR`;
- **self-non-conflict**: the candidate present in *both* sources still yields no
  `OVERLAP:` against itself, and the `INFLIGHT_SCAN` counts exclude it;
- a **measured false-positive rate** for `--from plan` over a replay of recent
  real picks, recorded in the Final Implementation Notes — it is t1569_4's entry
  criterion.

Fixture scaffold: `tests/test_change_surface.sh`.
