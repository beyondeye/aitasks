---
Task: t1569_background_work_roadmap_trail_for_followup_backlog.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1569 — Background-work roadmap + shared parallel-admission checker

## Context

59% of the active backlog is auto-spawned follow-up work nobody picks. Measured
fresh today: **461 active task files, 229 carrying `followup_kind:`**
(manual_verification 76, risk_mitigation 74, upstream_defect 60, carry_over 9,
review_finding 6, verification_failure 4). The phase-1 corpus — Ready follow-ups
plus Ready `effort: low` genuine work — is **222 + 39 = 261 tasks**.

t1569 asks for a **background-work roadmap**: a refreshable, evidence-backed,
conflict-aware ordering of that backlog, emitted as a standard
`implementation_trail` artifact so the board's By-Trail view, `drift`, versioning
and refresh all work unchanged. Phase 1 is **order only, purely advisory** — it
never changes task state.

**Scope expansion (user-directed, beyond the task's original Goal).** The roadmap
alone gives a *pre-estimate*: "this looks safe based on the task's origin/topic
evidence and what was in flight when the roadmap ran." That is not a safety
decision — the candidate has no plan yet, and the world moves. The framework
today has ownership locks, a remote-drift check and worktree/merge protection,
but **no authoritative check against other active tasks**; an agent may notice a
collision during planning, but that is judgement, not a guard.

So this task also delivers a **shared parallel-admission checker** with two
consumers:

```
Roadmap estimate → candidate selected → plan written
                                  ↓
                       Remote-drift check          (exists today)
                                  ↓
                  Parallel-admission preflight     (new, required)
                                  ↓
                  proceed / confirm / stop-and-replan
```

**The key design rule: one shared checker, two consumers.** The roadmap calls it
for an advisory preview; `task-workflow` calls the *same* checker as a required
preflight. Two implementations would mean two subtly different definitions of
"safe". t1569's Goal statement is amended in Step 0 to cover this.

Effort is `high`. This plan decomposes into **6 children + 1 manual-verification
sibling**, riskiest first.

---

## Step 0 (do this first) — amend t1569's settled design

Four corrections/expansions, all verified, recorded into the task file and
committed **before** children are created.

### 0.1 `followup_of:` is not a field — phase 1 degrades honestly instead

The task's design decision (a) says resolve each follow-up's origin via
`followup_of:` / `verifies:`. **`followup_of:` is not a persisted frontmatter
field.** It is a creation-time flag on `aitask_create.sh` (`resolve_anchor()`,
`:228-266`) that reads the source task's anchor and writes **`anchor:`** — the
*topic root*, which by contract "always points at the root and never chains".
Zero task files carry `followup_of:`.

Phase 1 resolves origin from existing metadata only and **renders the quality
honestly**. Measured over the 229 follow-ups, **mutually exclusive**
(`verifies:` wins over `anchor:` where both are present):

| evidence | quality | count |
|---|---|---|
| `verifies:` present | **exact** | **86** (49 `verifies`-only + 37 carrying both) |
| `anchor:` only | **topic** — explicitly *not* an exact origin | **130** |
| neither | **unknown** | **13** |

Raw signal counts are `verifies` 86 and `anchor` 167 with a **37-task overlap** —
quoting 167 as the topic population double-counts that overlap and would inflate
the residual and mislead the later direct-origin decision.

`followup_kind:` already classifies *that* a task is a follow-up and *which
category*; that is settled and is not an open problem here. A persisted
direct-origin field (`followup_origins:`) is deferred to a **separately justified
enhancement** — and the parallel-admission preflight below reduces the need for
it further, since the real safety decision now uses the candidate's concrete
plan, not its provenance. Roadmap provenance stays a **ranking and early-warning**
signal only.

### 0.2 t1275 is done — the plan-path allowlist caveat is stale

The task's seam table flags `aitask_remote_drift_check.sh`'s plan-path extractor
as carrying "the live bug t1275". **t1275 landed 2026-08-25** (`26c4b7781`); the
repo-specific root allowlist is gone. What remains is the *extension* narrowing
(`sh|py|md|yaml|yml|json|toml`) plus char-class / NFC-NFD / non-UTF8 gaps, all
recorded in `aidocs/framework/plan_path_reference_extraction_findings.md`.

### 0.3 The coordination lane is unexercisable on the live corpus

Simulated today: **coordination 0, parallel-safe 220, unresolvable 40**. The
cause is real. Of the five non-candidate in-flight sources: **2 of the 4
`Implementing` tasks have no plan file at all** (t1576, t1555_2); t259 is
lock-only (`status: Ready`, locked since 2026-02-26, a pre-PID-anchor lock with
no liveness token) and its plan references `aiscripts/…`, a directory that no
longer exists, so **0 of its 45 extracted paths resolve on disk**; only t887 and
t1631 carry a usable declared surface.

Consequences: conflict signals stay scoped to **declared plan paths +
origin-derived file sets** (checkout-wide uncommitted changes are out — they
cannot be attributed safely to a specific in-flight task); the lane is proven by
**deterministic synthetic fixtures** (overlap, no-overlap, missing-plan,
all-phantom-plan); and output distinguishes **CLEAR / CONFLICT / UNCHECKABLE**,
never rendering missing or non-resolving evidence as safe.

### 0.4 Add the parallel-admission preflight to the Goal

Record the expansion described in Context: the roadmap is the advisory preview,
`task-workflow` gains a required preflight, and both call one shared checker.

---

## Verified findings that shape the decomposition

| Finding | Consequence |
|---|---|
| `aitask_revert_analyze.sh --task-files <id>` already derives a task's git file set, children-inclusive. **0.53 s/call → ~115 s for 216 follow-ups.** A single `git log --all --name-only` pass + bucketing produces the whole map in **1.0 s**; verified byte-identical vs `--task-files` for t1626, t1555 (parent w/ children), t1275. | Reuse the seam, **add a batch mode** — do not fork the scan (CLAUDE.md "Reusable Helpers"). 115x. |
| `trail_schema._normalize_input_record()` **hard-errors on any unknown key** (`_RECORD_BASE_FIELDS = ref,kind,exists`; `_ALL_STATE_FIELDS = status,depends,gates_pending,content_hash`). | The digest-exclusion hazard is **structurally enforced**, not remembered — provided new facts arrive as **new line prefixes**, never INPUT fields. An INPUT field would force `NORMALIZATION_VERSION` → `schema_version` bump → every stored digest incomparable. |
| Trail schema **already** has `in_flight_conflict` / `stale_premise` / `shared_surface_collision` observation kinds, `coordinates_with` relation, and **`classification: coordination_only`** (rendered with `⇄` at `aitask_board.py:639`). | No schema bump for the lanes. **Do not invent a lane field.** |
| `aitask_query_files.sh inflight` requires `Implementing` **and** a `## Gate Runs` heading — returns `NO_INFLIGHT` today while 5 tasks are `Implementing`. `ait lock --list` returns 5 locks; t259 is locked but not `Implementing`, t887 is `Implementing` but not locked. | Neither source suffices. Emit their **union**, tagged by source. |
| `ait lock --list` performs a network `git fetch origin aitask-locks` (`aitask_lock.sh:414-421`) and prints ANSI-coloured human lines to **stdout** on degenerate paths. | Unconditionally inside `trail_gather.py snapshot` this makes the **shared** gatherer network-dependent for every ordinary trail. Opt-in flag; no-fetch local read of `origin/aitask-locks`; parse only `^t<id>: locked by `. |
| `MEMBER:` carries ref/status/priority/effort/boardcol/labels/followup_kind/path — **no `created_at`, `anchor`, `verifies`, `risk_code_health`, `risk_goal_achievement`**. | Add an **additive `MEMBER_EXT:` line**. Do not append to `MEMBER:` — its free-ish `path` field is last by contract. |
| **Hub-file asymmetry (measured).** Origin-derived sets: median 11 files, p90 39, max 272; **57 of 260** candidates' sets contain `aitask_board.py`, 28 contain `task-workflow/SKILL.md`. Plan-declared sets: only **2–8 of 107** active plans mention any given hub file. | The two consumers need the **same verdict vocabulary but different narrowing tolerance**. The checker takes the candidate set **plus its provenance** (`plan_declared` \| `origin_derived`) and narrows accordingly — single-sourced verdicts, provenance-aware evidence. Without narrowing the origin-derived side fires on ~22% of the corpus. (Same lesson as `manual_verification_staleness.md`: "Narrowing is mandatory".) |
| `aitask_verification_stale.sh` reads scope from `file_references:` (0/461 coverage — explicitly rejected here) and baseline from `verification_baseline:` (absent on follow-ups). | The t1555_1 reuse is **conventions only**. The premise-drift **baseline must be invented**. |
| `entry` is `additionalProperties: false`; `rendering_hints` allows only scalars and is top-level. | "Every score component shown per entry" is satisfiable **as prose in `rationale`** without a schema bump. |

---

## Decomposition — 6 children + 1 MV sibling

**Wave 1 (parallel, disjoint files):** `_1`, `_2`
**Wave 2:** `_3` (the shared checker)
**Wave 3 (parallel):** `_4` (preflight consumer), `_5` (roadmap policy)
**Wave 4:** `_6`, then `_7`

### t1569_1 — In-flight / planned-surface facts in the shared gatherer *(frontloaded risk)*
`depends: []`

Extend `lib/trail_gather.py snapshot` with **generic facts only** — no scoring,
no freshness, no follow-up semantics, no lanes. This has blast radius over every
existing trail.

New **digest-excluded** line prefixes (new prefixes, never INPUT fields):

```
INFLIGHT:<ref>|<gate|lock|both>|<PLAN|IMPLEMENT|POSTIMPL|->|<gate_state>
INFLIGHT_PATH:<ref>|<tracked|phantom|planned_new>|<path>
INFLIGHT_SCAN:<n_tasks>|<n_tracked>|<n_phantom>|<full|partial|uncheckable>
MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>
```

- Source = union of `aitask_query_files.sh inflight` and `ait lock --list`,
  tagged by which produced it.
- Plan paths extracted per in-flight task and **validated against `git ls-files`**.
  Decide `planned_new` here (a plan legitimately naming a not-yet-created file);
  discovering it later means reopening this contract, the goldens and the pinned
  block.
- **Factor the plan-path extractor out** of `aitask_remote_drift_check.sh:225-230`
  into a shared helper and make the drift check **consume** it, with
  `tests/test_remote_drift_check.sh` as the regression guard. `_3` and `_4` use
  the same extractor — three consumers, one grammar.
- **The lock probe must not make the shared gatherer network-dependent.** Opt-in
  flag; no-fetch local read; strict `^t<id>: locked by ` parse; hard timeout
  degrading to `INFLIGHT_SCAN:…|uncheckable`.
- Update the **PINNED gatherer output contract** at
  `.claude/skills/aitask-trail/SKILL.md.j2:47-78`, regenerate the three goldens
  under `tests/golden/skills/aitask-trail/`, and update
  `tests/test_trail_skill_contract.sh` — same commit.
- Amend the module docstring's determinism claim: "two runs over unchanged state
  are byte-identical" is stated for the *whole output*; scope it to
  digest-relevant lines, or the determinism test encodes the wrong property and
  passes while the real one rots.
- Tests (`tests/test_trail_gather.py`): gather twice **across a lock
  acquisition** and assert `DIGEST:` unchanged; audit every existing full-output
  byte-comparison in that file; the probe needs an injectable seam + env
  kill-switch so the synthetic-repo suite stays machine-independent.

### t1569_2 — Batch task→file-set derivation, history index, origin resolution
`depends: []`

Add a batch mode to `.aitask-scripts/aitask_revert_analyze.sh` — **one**
`git log --all --format='…%H…%ct…%s' --name-only` pass — emitting:

- `task_id → paths` (children-inclusive, same `(tNN)` matching as `--task-files`);
- `path → [(sha, committed_at, task_ids)]` — the commit index premise-drift needs;
- the tracked-path set from one `git ls-files`.

**Carry `%ct` from the start.** Without timestamps, `_5` must re-shell git per
path and the 115x win is lost — the most likely mechanical rework in the tree.

**`UNKNOWN_HISTORY` is a first-class third state, not an empty set.** A task id
with no recognised reachable commit — never landed, landed under a differently
labelled subject, rebased away, or reachable only from a ref this scan does not
walk — currently produces *nothing*: `--task-files` prints a `No commits found`
warning to stderr and returns 0 with empty stdout, so an absent map entry is
byte-indistinguishable from "this task touched no files". That is a
**false no-conflict**, and it is live today:

- **7 of the 86 `exact`-quality follow-ups** resolve to an origin with an empty
  file set; **41 of 260** candidates have an empty origin-derived set overall;
- among the 37 dual-signal tasks, t1206's *topic root* has an empty file set;
- **all 4** non-candidate `Implementing` tasks have zero reachable commits.

The batch mode emits, per queried id, exactly one of `FILES` / `NO_FILES` (id
matched, commits genuinely touched nothing) / `UNKNOWN_HISTORY` (id never
matched). `_3` maps `UNKNOWN_HISTORY` to **UNCHECKABLE**, never CLEAR.
Fixture-test all three, including a task whose commits exist only under a child
id and a task with no commit at all.

Plus the pure origin resolver (new `lib/followup_origin.py`, mirroring
`lib/followup_backfill_classify.py`'s pure / no-git / no-subprocess contract):

```
resolve(metadata) -> (origins, quality)   # quality ∈ exact | topic | unknown
  verifies:  -> exact     (the verification cases only)
  anchor:    -> topic     (a topic ROOT, never an exact origin)
  neither    -> unknown
```

It must **never** report `anchor` as `exact`, and must not consult
`followup_kind` — classification and origin are separate concerns.

- **Acceptance oracle for the batch mode:** byte-identical output vs
  `--task-files` for **every** task id in the corpus, not a spot-check (~2 min of
  CPU, once). Cover multi-task subjects (`(t100, t101)`), reverts and merges.
- Tests: `tests/test_followup_origin.py` — resolver truth table including the
  **`anchor`-is-never-exact negative control**; a live-corpus coverage assertion
  on *shape*, not frozen counts.

### t1569_3 — The shared parallel-admission checker *(the single definition of "safe")*
`depends: [1569_1, 1569_2]`

One helper, `./.aitask-scripts/aitask_parallel_admission.sh` (shell entry point
so it is whitelistable for skills and callable from `task-workflow`), backed by a
pure Python lib. It is the **only** place a collision verdict is computed.

**Contract**, following the `aitask_verification_stale.sh` conventions verbatim
(line protocol, one record per line, free-ish field last; **always exit 0** for
every content state, CLI misuse dies; `%`-then-`|` injective path encoding;
`:(literal)` pathspec guard):

```
check --candidate <id> --from plan|origin [--plan <path>]
      --lock-freshness require-fresh|allow-cached [--max-lock-age <s>]

CANDIDATE:<ref>|<plan_declared|origin_derived>|<n_paths>|<resolved|unresolved:<reason>>|<exact|topic|unknown|n/a>
LOCKS:<fetched|cached|unavailable>|<age_seconds|->
INFLIGHT:<ref>|<source>|<live|lock_only|dead|unknown>|<n_paths>|<tracked|phantom|mixed|none>
OVERLAP:<ref>|<path>
NARROWED:<path>|<n_tasks_touching>          # dropped as a hub file
CAVEAT:<inflight:<ref>|locks>|<reason>      # unverified evidence, no overlap found
UNCHECKABLE_CAUSE:<candidate|inflight:<ref>|locks>|<reason>
DISPLAY:<one-line human summary>
VERDICT:<CLEAR|CLEAR_CAVEATED|CONFLICT|UNCHECKABLE>
```

Verdicts (four values — `CLEAR_CAVEATED` is deliberately not folded into CLEAR):

- **CLEAR** — fully evidenced on **both** sides, and no collision found.
- **CLEAR_CAVEATED** — no collision found, but at least one source's evidence was
  *unverified* rather than absent: a `lock_only` source, a lock holder whose
  liveness is `unknown`, or a cached lock ref under `allow-cached`. It must be
  **visually distinct from CLEAR** and, under the blocking profile, **requires
  confirmation**. Collapsing it into CLEAR would make an unverified holder look
  identical to a fully evidenced all-clear, which is the whole failure this
  verdict exists to prevent.
- **CONFLICT** — named overlapping task(s) and file(s).
- **UNCHECKABLE** — the comparison could not be made at all. **Never rendered as
  CLEAR.** This is `UNKNOWN`-drives-the-verdict, the checker's most important
  property. `CLEAR_CAVEATED` and `UNCHECKABLE` are deliberately distinct: "I
  compared and found nothing, but one input was unverified" and "I could not
  compare" have different remedies.

**CLEAR is a point-in-time observation, not a reservation — say so everywhere.**
The checker takes a snapshot; it does **not** reserve the candidate's planned
surface. Another agent can begin overlapping work in the instant after
`VERDICT:CLEAR`, before this task writes or commits anything. The task lock
reserves the *task*, never the *file surface*. So the wording is fixed in all
three surfaces — the `DISPLAY:` line, `_4`'s procedure text, and `_5`/`_6`'s run
summary — as **"no known conflict at check time"**, never "safe to run in
parallel". The residual race is documented in the design record and the website
workflow page, and it is closed only when the **t1343 declared-claims backend**
is adopted: t1343 specifies exactly the missing piece — a per-task claim registry
written at plan externalization, widened at Step 8 pre-commit, and reaped
fail-closed. Until then this is an advisory admission check with a real,
named residual, and the plan does not pretend otherwise.

**Three hazards the verdict logic must close by construction — each fixture-tested:**

**(a) Self-exclusion.** `task-workflow` claims the candidate at **Step 4** — it
sets `status: Implementing` *and* acquires the lock — long before Step 6 writes
the plan and Step 7 implements. Verified live while writing this plan: t1569 is
`Implementing` and appears in `ait lock --list` right now. Since the checker
unions in-flight status and locks, **the candidate lands in its own comparison
set and overlaps every path of its own approved plan** — a guaranteed CONFLICT on
every pick. The candidate ref must be excluded from **every** source (`inflight`,
`lock --list`, and the derived surfaces) *before* overlap is evaluated, not
filtered out of the results afterwards. Fixture-test that a candidate never
conflicts with itself, with the candidate present in both sources.

**(b) The candidate's own surface can be unresolved — that is UNCHECKABLE, not
CLEAR.** An empty intersection is meaningless when the candidate side is unknown.
Emit `CANDIDATE:…|unresolved:<reason>` → UNCHECKABLE for **each** of:

| shape | live incidence |
|---|---|
| plan yields **no extractable paths** (the extension list excludes the project's language — findings doc §1) | 0/108 here, but structural for non-shell/Python projects |
| **every** extracted path is `phantom` (fails `git ls-files`) | **22 of 108 active plans (20%)** |
| the remainder is empty only **because narrowing removed it** | must not silently become CLEAR |
| `UNKNOWN_HISTORY` from `_2` (`--from origin`) | 41 of 260 candidates |
| `unknown` origin quality (`--from origin`) | 13 of 229 follow-ups |

**(c) Lock freshness is a parameter, not a fixed behaviour.** `_1`'s gatherer
reads `origin/aitask-locks` **without fetching** so the shared gatherer stays
offline-safe — correct for an estimate, and fatal for an admission decision: a
stale ref hides a lock another agent acquired seconds ago, producing a false
CLEAR at exactly the point meant to prevent concurrent work. One verdict logic,
one explicit knob: `--lock-freshness require-fresh` (the preflight) attempts a
bounded fetch and, if the fetch fails or the ref is older than `--max-lock-age`,
emits `LOCKS:cached|<age>` or `LOCKS:unavailable` → **UNCHECKABLE**;
`allow-cached` (the roadmap) accepts the cached read and labels it. Neither mode
may report CLEAR on lock evidence it could not establish.

**Provenance-aware narrowing (step 1 of this child).** The verdict vocabulary and
evidence rules are single-sourced, but the two provenances have measurably
different noise: plan-declared sets are sparse (a hub file appears in 2–8 of 107
plans), while origin-derived sets are broad (57 of 260 candidates' sets contain
`aitask_board.py`; p90 39 files, max 272). Settle the narrowing rule and its
threshold **before** writing the verdict logic, and emit every dropped path as a
`NARROWED:` record so the narrowing is auditable rather than silent.

**Availability is a first-class design constraint, not just something to measure.**
A naive rule — *any* incomplete in-flight source makes the candidate UNCHECKABLE —
yields **UNCHECKABLE for 100% of picks today**: 2 of the 4 non-candidate
`Implementing` tasks have no plan at all, and t259's is all-phantom. A guard that
prompts on every pick is one the user learns to dismiss, which is the same
failure `manual_verification_staleness.md` records ("otherwise the user is
re-prompted forever and learns to ignore it"). Three structural mitigations,
settled here alongside the narrowing rule:

1. **UNCHECKABLE is per-source and named, never global.** `UNCHECKABLE_CAUSE:`
   identifies *which* in-flight task could not be ruled out, so the prompt says
   "cannot rule out a collision with **t1576** (no plan file)" and the recovery
   path is concrete and per-task — not an undifferentiated "something is unknown".
2. **Classify the in-flight source rather than blindly unioning it.** Tag each as
   `live` (`Implementing`, lock alive), `lock_only` (locked but not
   `Implementing` — t259 has been in this state since 2026-02-26), `dead` (lock
   holder provably dead via `lib/pid_anchor.sh::lock_holder_liveness`) or
   `unknown` (no liveness token — every pre-PID-anchor lock, t259 included).
   A `dead` holder is not concurrent work and drops out silently. A `lock_only`
   or `unknown` source still produces **CONFLICT** on a real path overlap; when
   it produces no overlap it downgrades the verdict to **`CLEAR_CAVEATED`** with
   a `CAVEAT:` record — **never plain CLEAR**, because a real but unverified
   holder must not look identical to a fully evidenced clear. That downgrade is
   what keeps this mitigation from buying availability at the cost of silently
   under-reporting; it is cheaper than UNCHECKABLE without being a lie.
3. **Verdict-rate metric, and it gates the default.** The helper emits a
   `RATES:` summary over a replay, and `_4` reports live
   CLEAR / CONFLICT / UNCHECKABLE counts. Both a high false-positive CONFLICT
   rate *and* a high UNCHECKABLE rate are ship blockers.

- Tests: **overlap / no-overlap / missing-plan / all-phantom-plan /
  unknown-history / hub-narrowed / self-as-candidate / stale-locks /
  unresolved-candidate-surface / lock-only-holder / unknown-liveness-holder**,
  plus determinism (same fixture twice → byte-identical output), plus negative
  controls proving that a narrowed path, an empty candidate surface, or an
  unverified holder can none of them produce plain `CLEAR`.

### t1569_4 — `task-workflow` parallel-admission preflight *(consumer #1: required)*
`depends: [1569_3]`

New procedure `.claude/skills/task-workflow/parallel-admission.md`, modelled on
`remote-drift-check.md`, wired in at **two** call sites:

1. **After** the Remote Drift Check returns "Continue anyway" at the planning
   Checkpoint, **before** Step 7 implementation.
2. **Again on implementation re-entry** (`SKILL.md` Re-entry Routing, the
   `IMPLEMENT` route, after its drift check) — the world may have changed since
   the plan was approved.

Dispositions:

- **CLEAR** → proceed, stating "no known conflict at check time" — never "safe to
  run in parallel".
- **CLEAR_CAVEATED** → **require explicit confirmation under `block`**, naming
  the unverified source (e.g. "t259 holds a lock but is not `Implementing`, and
  its holder's liveness cannot be established"). Under `warn`, a visible note.
  Rendered distinctly from CLEAR in both modes.
- **CONFLICT** → **stop-and-replan by default**, naming the overlapping task(s)
  and file(s); the alternative is an explicit user override.
- **UNCHECKABLE** → **require explicit user confirmation**, naming *why* the
  evidence was insufficient. Never auto-proceed.

The procedure text states the residual race explicitly: this check is a snapshot
and reserves nothing, so overlapping work can begin immediately after it passes.

- Calls the checker with `--lock-freshness require-fresh` and **excludes the
  candidate**, which `task-workflow` has already claimed and locked at Step 4.
  Re-reads **live** state at call time — it must never reuse the roadmap's
  snapshot, which is by construction older.
- **Operator recovery path, printed with every UNCHECKABLE**, keyed to the named
  cause: an in-flight task with no plan → plan it, or release its lock
  (`ait lock --unlock <id>`), or override for that task; an all-phantom plan →
  the plan is stale, refresh or release it; unavailable locks → check the
  network, or re-run. A prompt with no remedy is what trains users to dismiss it.
- Profile knob `parallel_admission: block | warn | off` in
  `aitasks/metadata/profiles/*.yaml` + `seed/`, mirroring `remote_drift_check`.
  **CONFLICT's disposition is stop-and-replan in both `block` and `warn`** — that
  is the design and it does not change.
  **Deviation, with evidence:** the knob **ships defaulting to `warn`**, not
  `block`, because the measured projection is UNCHECKABLE on 100% of picks
  against today's in-flight population. Promotion of the default to `block` is a
  separate, explicitly gated step, its entry criterion being the measured
  UNCHECKABLE and false-CONFLICT rates from `_3` falling to an agreed level. In
  `warn`, UNCHECKABLE still prompts for explicit confirmation — it is only the
  hard stop that is deferred.
- Regenerate the per-profile renders and the `tests/golden/procs/task-workflow/`
  goldens in the same commit. **No Codex / OpenCode port task is needed:**
  `parallel-admission.md` is shared-closure content with no `{% if agent %}`
  gates, and Claude is the single source
  (`SOURCE_AGENT_ROOT = ".claude/skills"` in `lib/skill_template.py`), so
  `.agents/skills/task-workflow-*-codex-/` and `.opencode/skills/task-workflow-*/`
  auto-render from it — verified identical modulo digits for an existing
  procedure. CLAUDE.md's port guidance targets agent-specific surfaces only. The
  helper whitelist below **is** such a surface and still needs its entries.
- Helper whitelist: 5 touchpoints via
  `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_parallel_admission`
  — **verify them against `aidocs/framework/aitasks_extension_points.md:286-318`
  before editing**.
- Tests: a bash test driving the real helper through a synthetic repo for each
  disposition; a **self-exclusion end-to-end test** that claims a task exactly as
  Step 4 does and asserts the preflight returns CLEAR rather than conflicting
  with the candidate's own plan; and a workflow-contract test pinning that the
  preflight sits **after** the drift check at both call sites (order is
  load-bearing: the drift check can pull the base, changing what is in flight).

### t1569_5 — Roadmap scoring, dual freshness, premise-drift, lanes *(consumer #2: advisory)*
`depends: [1569_3]`

A pure library consuming `_1`'s gatherer lines, `_2`'s index/resolver and `_3`'s
checker as **injected data** — no git, no subprocess, fixture-testable.

- **The lanes are the checker's verdicts, not a second opinion.**
  `CLEAR` → parallel-safe (`classification: core`);
  `CLEAR_CAVEATED` → parallel-safe but visibly caveated, `confidence` reduced and
  the unverified source named in `rationale`;
  `CONFLICT` → coordination (`classification: coordination_only`, `⇄`);
  `UNCHECKABLE` → surfaced hedged, never silently in the safe lane.
  The roadmap runs the checker with `--from origin --lock-freshness allow-cached`
  and labels the whole output an **estimate** — origin/topic evidence, in-flight
  state as of the run, reserving nothing — distinct from `_4`'s live,
  plan-derived admission decision. The run summary says so in those words.
- **Scoring, component-wise and overridable:** origin `risk_code_health:` /
  `risk_goal_achievement:` primary; in-flight area affinity a strong but
  **advisory** boost that must not bury urgent unrelated work; `priority:` a weak
  transparent tie-break; `effort:` a background-capacity constraint, not value;
  **`followup_kind` NOT ordering-relevant** — enforced by a test that permutes
  `followup_kind` across the fixture corpus and asserts byte-identical ranking.
- **Origin quality is carried, not hidden.** Every entry states `exact` /
  `topic` / `unknown`; a `topic`/`unknown` entry is visibly hedged.
- **Freshness as two independent weights:** recency, and premise validity.
- **Premise drift** behind a small replaceable t1561-shaped interface, reusing
  the `aitask_verification_stale.sh` conventions. **Step 1 of this child is to
  settle the baseline** — `created_at` → nearest ancestor commit, or the origin's
  last landed commit — since neither `verification_baseline:` nor
  `file_references:` exists on follow-ups.
- **Resolution-quality measurement — a counterfactual on a biased 37-task sample,
  labelled as one.** The true direct origin of the 130 `topic`-only tasks is
  **unknown**, so nothing can measure the fallback's impact on them. The only
  tasks where both an exact origin and a topic root exist are the **37 carrying
  both signals**, and because `verifies:` is written only by the
  manual-verification seams those 37 are all MV-typed — not representative.

  Measured today on those 37: the two file sets differ in **21 cases**, and the
  divergence is not merely "topic is wider" — t1497 (exact 3, topic 13,
  **overlap 0**) and t1513 (exact 4, topic 13, **overlap 0**) show the topic root
  can be **disjoint** from the true origin, so the fallback can be actively wrong
  rather than conservatively broad.

  Emit per run: the mutually exclusive `exact`/`topic`/`unknown` histogram; the
  count of estimates degraded to UNCHECKABLE by origin quality or
  `UNKNOWN_HISTORY`; and the counterfactual over the dual-signal sample only,
  reported as *"n of N dual-signal tasks (MV-typed) would rank differently"* —
  never extrapolated to the 130.
- **Ships the aidocs design record** (`aidocs/framework/background_work_roadmap.md`):
  the scoring model, the two freshness weights, the baseline decision, the
  narrowing rule, the measured residual, and the **trail encoding contract** —
  because `_6` implements against it.
- **Settle the score-component representation here**: `entry` is
  `additionalProperties: false`, so components go in `rationale` prose unless a
  `schema_version` bump is accepted. Recommendation: prose, no bump.
- **Trail encoding contract** (all existing vocabulary, no schema change):
  waves 1 = parallel-safe / 2+ = coordination;
  `relations[]: {type: coordinates_with, provenance: advisory}` backlog → in-flight;
  `observations[]: in_flight_conflict | shared_surface_collision | stale_premise`
  with `affects` + `evidence_refs`;
  `evidence[]: source_type: command_output` naming the checker/gatherer invocations.
- **Creates the t1561 adoption follow-up.**

### t1569_6 — `aitask-backlog-roadmap` skill + trail authoring
`depends: [1569_5]`

A **static** (non-profile-aware) skill — 4 files, no `.j2`, no goldens, no render
test:

```
.claude/skills/aitask-backlog-roadmap/SKILL.md      # canonical body
.agents/skills/aitask-backlog-roadmap/SKILL.md      # generated wrapper
.opencode/skills/aitask-backlog-roadmap/SKILL.md    # generated wrapper
.opencode/commands/aitask-backlog-roadmap.md        # generated wrapper
```

- Generate the wrappers with
  `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> aitask-backlog-roadmap`;
  verify with `./.aitask-scripts/aitask_skill_verify.sh` (cross-tree parity is
  the one check a static skill hits).
- Authors the `implementation_trail` JSON per `_5`'s encoding contract, validates
  with `aitask_trail_depth.sh validate`, creates the artifact with
  `ait artifact create … --kind implementation_trail`, parsing `HANDLE:`.
- **Two decisions in this child's plan step 1, not during implementation:**
  - **Member cap / selection rule.** 261 candidates × required `rationale` +
    `confidence` per entry is not authorable in one run, and a digest over ~500
    inputs goes STALE on any status change anywhere — the freshness signal would
    degenerate to noise. Pick a top-N and record corpus size and selection rule
    in `narrative.method_note` (`exclusions[]` requires a reason per task, so a
    200-item tail is not free).
  - **Artifact owner.** `owner` is required and task-owned, but this roadmap
    outlives t1569. Pick a standing holder task; check handle resolution after
    the owner archives.
- Run summary states plainly that the lanes are an **estimate** and that
  `/aitask-pick` will run the live preflight before implementation — so a CLEAR
  estimate is never read as an admission decision.
- Website docs: `website/content/docs/skills/_index.md` + a new page, plus a
  workflows note documenting the preflight from `_4`.
- **Creates the t1343 adoption follow-up** and the **`followup_origins:`
  enhancement follow-up**.

### t1569_7 — Manual verification sibling
`depends: [1569_4, 1569_6]`, `issue_type: manual_verification`,
`verifies: [1569_1, 1569_3, 1569_4, 1569_5, 1569_6]`

Human-only checks the automated suite cannot make:

- Lanes are visually distinct in the By-Trail view via the `⇄ coordination_only` glyph.
- Score components **and origin quality** (`exact`/`topic`/`unknown`) are legible
  per entry — a `topic`-quality entry must not read like an exact one.
- An `uncheckable` run is **visibly hedged**, not silently green — including the
  `UNKNOWN_HISTORY` cause, the easiest to render as a false all-clear.
- `/aitask-pick` on a real task shows the preflight **after** the drift check, and
  each of CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE presents its intended
  disposition — including that a freshly claimed candidate does **not** conflict
  with itself, and that `CLEAR_CAVEATED` is visibly different from `CLEAR`.
- Neither the preflight nor the roadmap ever describes a pass as "safe to run in
  parallel" — both say "no known conflict at check time", and the residual race
  is discoverable from the workflow docs.
- An UNCHECKABLE prompt **names the specific task it could not rule out and a
  remedy the operator can actually act on** — the difference between a guard that
  gets used and one that gets dismissed.
- `/aitask-backlog-roadmap` end-to-end on the live repo produces a usable ordering.

---

## Verification

```bash
# _2, _3, _5 — Python libs
bash tests/run_all_python_tests.sh --test-dir tests    # read ONLY the last line
# _1, _2, _3, _4 — bash + contracts
bash tests/test_remote_drift_check.sh
bash tests/test_trail_depth_resolve.sh
bash tests/test_trail_skill_contract.sh
bash tests/test_skill_render_aitask_trail.sh
python3 -m unittest tests.test_trail_gather tests.test_trail_schema -v
# _4, _6
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_*.sh
```

Whole-tree, after `_6`:

```bash
./.aitask-scripts/aitask_revert_analyze.sh --task-files 1555            # unchanged output
./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task 1569     # new lines, DIGEST stable
./.aitask-scripts/aitask_parallel_admission.sh check --candidate 1569 --from plan
```

Note: piping the Python runner discards its status — use `set -o pipefail` or
check `${PIPESTATUS[0]}`.

---

## Risk

### Code-health risk: high

- `_4` inserts a guard into the **pre-implementation path every task pick runs
  through**. A checker that mis-fires stops all work; one that fails open is
  useless · severity: high · → mitigation: inline in `_3`/`_4` —
  provenance-aware narrowing settled before the verdict logic, measured
  false-CONFLICT **and** UNCHECKABLE rates as the entry criterion, every dropped
  path emitted as `NARROWED:` for audit, and a
  `parallel_admission: block|warn|off` knob shipping at `warn` until the rates
  are measured
- **Availability collapse:** a naive "any incomplete in-flight source ⇒
  UNCHECKABLE" rule prompts on **100% of picks today** (2 of 4 non-candidate
  `Implementing` tasks have no plan; t259's is all-phantom), which trains the
  user to dismiss the guard · severity: high · → mitigation: inline in `_3` —
  per-source named `UNCHECKABLE_CAUSE:`, in-flight sources classified
  `live`/`lock_only`/`dead`/`unknown` via `lib/pid_anchor.sh` so a merely-locked
  or unverified source downgrades to **`CLEAR_CAVEATED`** instead of forcing
  UNCHECKABLE — while never collapsing into plain CLEAR — plus a concrete
  per-cause operator recovery path in `_4`, and the verdict-rate metric gating
  the default
- `lib/trail_gather.py` is a load-bearing shared module whose determinism
  invariant every existing trail depends on; volatile in-flight lines break the
  docstring's whole-output byte-identity claim as written · severity: medium ·
  → mitigation: inline in `_1` — new line prefixes only (unknown-key rejection
  makes digest exclusion structural), plus the lock-across-runs digest test and
  the docstring amendment
- `ait lock --list` fetches from the network and prints coloured human lines to
  stdout; in the shared gatherer that would slow and fragilize *every* ordinary
  trail · severity: medium · → mitigation: inline in `_1` — opt-in flag,
  no-fetch local read, strict parse, hard timeout degrading to `uncheckable`
- Three consumers of one plan-path extractor (`_1`, `_3`, `_4`) plus the existing
  drift check · severity: low · → mitigation: covered in-plan — `_1` extracts it
  once and the drift check consumes it, with `tests/test_remote_drift_check.sh`
  as the regression guard; not forking is what prevents divergence on the
  documented NFC / extension / char-class edges

### Goal-achievement risk: high

- **The candidate claims itself before the preflight runs.** Step 4 sets
  `Implementing` and takes the lock; the checker unions both sources, so without
  explicit exclusion the candidate overlaps 100% of its own plan and every pick
  is a CONFLICT — verified live against t1569 while writing this plan · severity:
  high · → mitigation: inline in `_3` — the candidate ref is removed from every
  source *before* overlap is evaluated, with a self-non-conflict fixture and an
  end-to-end test in `_4` that claims a task exactly as Step 4 does
- **The check reserves nothing.** It is a point-in-time snapshot: another agent
  can start overlapping work in the instant after `VERDICT:CLEAR`, and the task
  lock reserves the task, not the file surface · severity: high ·
  **accepted residual, not mitigated in phase 1** · → mitigation: covered
  in-plan — CLEAR is worded as "no known conflict at check time" in the
  `DISPLAY:` line, `_4`'s procedure and `_5`/`_6`'s run summary, the residual is
  documented in the design record and the website workflow page, and the
  **t1343 adoption follow-up** is what closes it (its per-task claim registry,
  written at plan externalization and reaped fail-closed, is the reservation this
  checker deliberately does not attempt)
- **A stale lock ref produces a false CLEAR at the admission point.** The
  gatherer's no-fetch `origin/aitask-locks` read is correct for an estimate and
  fatal for a decision · severity: high · → mitigation: inline in `_3` —
  `--lock-freshness require-fresh|allow-cached` with `--max-lock-age`, a `LOCKS:`
  provenance record, and cached/unavailable ⇒ UNCHECKABLE under `require-fresh`
- **An unresolved candidate surface yields an empty intersection that reads as
  CLEAR.** 22 of 108 active plans (20%) are all-phantom; a plan in a language the
  extension list misses yields zero paths; narrowing can empty the remainder ·
  severity: high · → mitigation: inline in `_3` —
  `CANDIDATE:…|unresolved:<reason>` ⇒ UNCHECKABLE for every such shape, each
  fixture-tested, plus a negative control proving an empty candidate surface
  cannot produce CLEAR
- **A task with no recognised commit history is indistinguishable from one that
  touched no files**, producing a false no-conflict; 7 of the 86 exact-quality
  follow-ups, 41 of 260 candidates and all 4 non-candidate `Implementing` tasks
  are in that state today · severity: high · → mitigation: inline in `_2` —
  `UNKNOWN_HISTORY` as an explicit third state alongside `FILES` / `NO_FILES`,
  mapped to UNCHECKABLE in `_3`, all three fixture-tested
- **Accepted residual:** **130 of 229** follow-ups resolve only to a *topic root*.
  On the 37 tasks where both are available the sets differ in 21 cases and can be
  **disjoint** (t1497, t1513: overlap 0) — the fallback is not merely coarser, it
  can be wrong · severity: medium (down from high: the preflight, not provenance,
  now makes the safety decision) · → mitigation: inline in `_5` — the
  counterfactual is reported over the dual-signal sample only and explicitly
  labelled biased (MV-typed), the corpus-wide UNCHECKABLE count is the
  generalising signal, and `followup_origins:` is gated on both
- The coordination lane is 0/220 on the live corpus and its value is entirely a
  function of in-flight population · severity: high · → mitigation: covered
  in-plan — four deterministic fixtures (overlap / no-overlap / missing-plan /
  all-phantom-plan) prove the lane, and the live smoke asserts shape only, never
  lane counts
- The premise-drift **baseline is undefined**: the reused helper's baseline and
  scope fields are both absent on follow-ups · severity: high · → mitigation:
  inline in `_5` — settling the baseline is step 1 of that child, and `_2`
  carries commit timestamps so the decision needs no reopening of a git helper
- "Every score component shown per entry" may be structurally unsatisfiable
  (`entry` is `additionalProperties: false`; `rendering_hints` takes only
  scalars) · severity: medium · → mitigation: inline in `_5` — settle
  prose-vs-schema-bump before `_6` authors against it; prose recommended
- 261 candidates against a schema requiring `rationale` + `confidence` per entry,
  and a digest that goes STALE on any status change anywhere · severity: medium ·
  → mitigation: inline in `_6` — member cap and selection rule decided in that
  child's plan step 1, recorded in `narrative.method_note`

**Mitigation-creation deviation (deliberate):** this parent decomposes, so
Steps 7/8/8d never run for it and any spawned "after" mitigation would silently
never be created. All mitigations above are therefore folded into the children
that own them as explicit first steps, rather than spawned as separate tasks.

---

## Follow-ups to create at decomposition time

- **t1561 adoption** — consume the generalized staleness mechanism in place of
  `_5`'s local interface. `depends: [1561, 1569_5]`. Created by `_5`.
- **t1343 adoption** — swap the checker's *evidence backend* to the
  declared-claims model (per-task claim store, deterministic set intersection).
  t1343's `depends: [1275]` is now satisfied. The preflight from `_4` is the
  consumer surface t1343 was missing, so this is a backend swap behind an
  unchanged verdict contract, not a rewrite — **and it is what closes the
  point-in-time race**, since a claim registry reserves the surface where this
  checker only observes it. `depends: [1343, 1569_4]`. Created by `_6`.
  **Add a bidirectional coordination note to t1343.**
- **`followup_origins:` enhancement** — a persisted direct-origin field populated
  at every follow-up creation seam (t1468_1/t1468_2 shape). **Gated on `_5`'s
  measurement**: a material rank change on the dual-signal counterfactual **and**
  a non-trivial corpus-wide UNCHECKABLE-by-origin-quality count. It is now a
  **ranking-quality** improvement, not a safety one. `depends: [1569_6]`. Created
  by `_6`, carrying the measured numbers and their sample bias verbatim.
*(No Codex / OpenCode port follow-up: `_4`'s procedure is shared-closure content
and auto-renders to both — see `_4`.)*

Post-implementation (Step 9) is the standard cleanup / archival / merge flow.
