---
Task: t1569_6_backlog_roadmap_skill_and_trail_authoring.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_7_manual_verification_background_work_roadmap.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_1_gatherer_inflight_and_planned_surface_facts.md, aiplans/archived/p1569/p1569_2_batch_task_file_sets_and_origin_resolution.md, aiplans/archived/p1569/p1569_3_shared_parallel_admission_checker.md, aiplans/archived/p1569/p1569_4_task_workflow_parallel_admission_preflight.md, aiplans/archived/p1569/p1569_5_roadmap_scoring_freshness_and_lanes.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-06 16:35
---

# t1569_6 — `aitask-backlog-roadmap` skill and trail authoring

## Context

59% of the active backlog is auto-spawned follow-up work that nobody picks.
t1569's five landed slices built every *mechanism* needed to rank and de-risk
that backlog — the gatherer's in-flight facts (t1569_1), batch file-set
derivation and origin resolution (t1569_2), the shared parallel-admission
checker (t1569_3), its `task-workflow` preflight (t1569_4), and the scoring /
lanes / freshness / trail-encoding policy library plus its design record
(t1569_5). **Nothing yet runs them.** This slice ships the user-facing surface:
a skill that drives the pipeline end to end and publishes a standard
`implementation_trail` artifact, so the board's By-Trail view, `drift`,
versioning and refresh all work unchanged.

### Verification findings that change the previous plan

This plan was re-verified against the codebase on 2026-09-06. Six corrections:

1. **No driver exists, and the previous plan did not budget one.**
   `lib/roadmap_policy.py` is a *pure* library (`build()`, `to_trail()`) with no
   `__main__`, no argparse and no shell wrapper. Its only callers today are
   tests. A `SKILL.md` cannot orchestrate a pure Python library from bash, so
   this slice must ship the impure driver. `tests/test_roadmap_integration.py`
   (`run()`, L118-160) is the exact wiring blueprint.
2. **`--from origin` and `--lock-freshness allow-cached` are fields, not CLI
   flags.** The previous plan's step 3.4 invoked
   `aitask_parallel_admission.sh check --from origin --lock-freshness
   allow-cached` per candidate. The design record is explicit
   (`background_work_roadmap.md:52-58`): they are `Surface(provenance=
   "origin_derived")` and `LockEvidence(mode="allow-cached")`. Per-candidate
   subprocess `check` would also re-collect the world 246 times (~2.5s each) and
   judge each candidate against a different world.
3. **The cap's rationale was wrong, though the cap is still right.** "261
   entries with `rationale` and `confidence` each is not authorable in one run"
   assumed hand-authoring; `to_trail()` generates rationale, confidence and
   caveats deterministically. The real constraint is drift:
   `generation.input_digest` covers every scoped member, so N members = N drift
   sources.
4. **Depth is `deep`, a literal — not `<d>`.** `to_trail()` hard-codes
   `rendering_hints: {"depth": "deep"}`; validation must assert
   `--expect-depth deep`.
5. **`exclusions[]` is never emitted.** `to_trail()` builds no `exclusions` key
   at all, so the 206-task tail cannot be enumerated there even if we wanted to.
   The tail is described in `narrative.method_note` — which the schema allows.
6. **`aitask-trail` is one skill with three modes, not separate create and
   refresh skills.** Its `description:` reads "Create, refresh, or show", and
   `aitask_trail_depth.sh resolve` emits a `MODE:` line that selects between
   them (`SKILL.md.j2:177-215`). So the precedent to follow is a single skill
   with an **explicit mode selector**, which is what Step 3 does.

### Decisions settled in planning

| decision | choice |
|---|---|
| member cap | **top 40** by the policy sort key; tail described in `narrative.method_note` |
| artifact owner | a **new standing holder task**, `status: Postponed`, never archived |
| corpus | **parent tasks only** — Ready follow-ups + Ready genuine `effort: low` |

Corpus re-measured 2026-09-06: **224 Ready follow-up parents + 22 Ready genuine
`effort: Low` = 246 candidates** (the task body's `222 + 39 = 261` was measured
2026-08-27). The driver counts at run time; no count is hard-coded.

### Pre-phase (risk mitigations)

These run **before** Step 1, in this order.

**`share_replay_collection_seam`.** Extract `_run_replay`'s collection
discipline (`parallel_admission_collect.py:988-1010`) into a public function —
resolve `batch_lines` via `_batch_map(root, with_recovered=True)` and corpora
via `resolve_corpora` once, resolve every candidate surface up front, build the
base with `exclude_self=False` — returning `(base, surfaces, batch_lines)`.
Re-point `_run_replay` at it so the two callers cannot diverge, and have the
driver consume it instead of reaching into private names. `_run_replay`'s
existing tests are the regression guard; its output must be unchanged.

**`live_scale_smoke_first`.** Before writing the encoder half, run the wide
snapshot and the origin-facts collector against the **real** candidate id list
and record wall-clock plus any `INFLIGHT_SOURCE:` line reporting `degraded` /
`unavailable`. The gatherer's in-flight probe runs under a 30s budget
(`trail_gather.py:643`), and origin facts read archived bundles. If either
misses its budget at ~246 ids, the corpus or the snapshot strategy changes
**here**, while the design can still absorb it — not after the encoder is built
against it.

## Step 1 — The driver (the missing piece)

Two new files, mirroring the facts/policy split the design record pins:

| file | purity | role |
|---|---|---|
| `.aitask-scripts/lib/roadmap_run.py` | **impure** | collect → decide → premise → score → cap → encode |
| `.aitask-scripts/aitask_backlog_roadmap.sh` | wrapper | thin `exec`, mirroring `aitask_backlog_origin_facts.sh` |

`roadmap_run.py` must **not** be added to `PURE_MODULES` in
`tests/test_parallel_admission_purity.py` — it is the impure half by design, and
`roadmap_policy` / `roadmap_premise` stay pure and stay listed.

### Pipeline

Ordering matters; each numbered step feeds the next.

1. **Enumerate candidates** — Ready parents carrying a `followup_kind:`, plus
   Ready parents with no `followup_kind:` and `effort: low`. Reuse
   `aitask_ls.sh`'s existing `--followup-kind` / `--no-followup-kind` /
   `-s Ready` filters rather than re-scanning frontmatter.
2. **Wide snapshot** — `aitask_trail_gather.sh snapshot --scope task <all ids>
   --with-inflight`. Supplies `MEMBER:` / `MEMBER_EXT:` (→
   `rp.parse_members`) and the volatile `INFLIGHT*` lines. The shell wrapper
   forwards argv verbatim, so `--with-inflight` reaches `trail_gather.py`
   (`:1610`) unchanged.
3. **Origin facts** — `aitask_backlog_origin_facts.sh <ids>` → `ORIGIN_FACT:`
   rows → `rp.parse_origin_facts`.
4. **One collection, re-aimed per candidate** — exactly `_run_replay`'s shape
   (`parallel_admission_collect.py:979-1010`): resolve `batch_lines` via
   `_batch_map(root, with_recovered=True)` and corpora via `resolve_corpora`
   **once**, resolve every candidate surface up front with
   `resolve_candidate_surface(..., source="origin", ...)`, `collect()` a single
   base, then `_respin(base, ref, surface)` + `pa.decide(...)` per candidate.
   **`data_tracked` is mandatory** — `aitasks/` and `aiplans/` are gitignored
   symlinks, so without it every task-data path classifies `phantom` and two
   tasks editing the same profile YAML report no conflict.
5. **Premise** — `premise.check(origins, surface.paths, batch_lines)` per
   candidate.
6. **Score all 246** — `rp.build(candidates, origin_rows, admission, premises,
   candidate_paths, inflight_paths, now_ordinal)`.
7. **Cap to 40** — take the first 40 of the already-sorted entries. Capping
   *after* scoring is what makes "top 40 by sort key" meaningful; capping the
   input would rank an arbitrary subset.
8. **Narrow snapshot** — re-run `snapshot --scope task <the 40 ids>` (no
   `--with-inflight`) and build `generation` from **that** digest and input
   list. This is load-bearing: `cmd_drift` recomputes over
   `generation.inputs` (`trail_gather.py:1409-1453`), so a `generation` built
   from the wide snapshot would make all 206 non-members drift sources and the
   trail would report STALE on unrelated churn.
9. **Encode** — `rp.to_trail(entries, "trail-backlog-roadmap", title, owner,
   scope, generation, freshness, narrative, evidence,
   inflight_refs=[...])`. Catch `EmptyRoadmapError` and report it as "no
   candidates — nothing published", never an empty document.
10. **Emit** the JSON to `--out`, plus `rp.measurement_lines(...)` and the
    counts the run summary needs, on a protocol-clean stdout.

### Narrative input contract (one ordering, one validated surface)

The prose must exist **before** encoding — `to_trail` takes `narrative` as an
argument and the schema requires `problem_statement` and
`recommendation_summary`. So the ordering is fixed: **the skill authors prose,
then the driver runs once and encodes.** There is no post-hoc injection step.

```
aitask_backlog_roadmap.sh --narrative <narrative.json> --owner <id> --out <trail.json>
                          [--title "..."] [--cap N]
```

`--narrative` is **required** and is a JSON object with exactly:

| key | who writes it | required |
|---|---|---|
| `problem_statement` | the skill | yes |
| `recommendation_summary` | the skill | yes |
| `overview` | the skill | optional |

The driver **validates it before any encoding**: object shape, both required
keys present, every value a non-empty string with a non-whitespace character
(the schema's `overview` pattern is `\S`), and **no other key** — the schema is
`additionalProperties: false`, so an unexpected key must fail here with a named
error rather than at validation time. A missing or malformed file exits 2 (CLI
misuse), consistent with the wrapper's contract.

**`method_note` is composed by the driver, never by the skill.** It is
factual — corpus size, the cap, the selection rule, and that the tail is
unenumerated — and every one of those numbers is computed in step 7. Letting
the skill write it would either require it to know counts it has not been told,
or invite a hand-typed number that drifts from the document. This is what
removes the chicken-and-egg: the skill supplies the standing framing, which
needs no counts; the driver supplies the measured facts.

`--title` defaults to `"Background-work roadmap"`.

**`--cap` contract.** Default 40 — the product decision. It stays exposed
because the scale smoke and the tests need to drive it, so it needs a stated
contract rather than an implicit one:

- **Valid range:** an integer `>= 1`. Zero, negative, non-numeric or absurd
  values (`--cap 0`, `--cap -5`, `--cap ten`) exit **2** as CLI misuse — a cap
  of 0 would otherwise reach `to_trail` as an empty list and raise
  `EmptyRoadmapError`, reporting "no candidates" for what is really a typo.
- **Fewer candidates than the cap:** publish all of them. Never pad, never
  fail. The cap is a ceiling, not a quota.
- **`method_note` states the cap actually applied and the corpus size**, so a
  non-default run is self-describing in the artifact rather than only in the
  invocation. When the corpus is smaller than the cap, the note says so instead
  of implying a selection that never happened.

### Degraded-evidence policy

The checker already does most of this and must not be re-implemented:
`decide` emits `UNCHECKABLE_CAUSE:<scope>|<reason>` lines and
`source_degraded` / `corpus_unavailable` caveats per candidate
(`parallel_admission.py:237-306`), and `_validate_enumeration` (`:189-203`)
**raises** unless `enumeration` carries exactly one live entry per probe
(gate, lock, status). The driver's obligations are therefore threading rules,
not new policy:

- **Never synthesize an enumeration tuple.** It comes from `collect()`'s live
  probes via the shared seam. A hand-built all-`ok` tuple is the fail-open that
  would let a dead probe render as `CLEAR`.
- **Corpus unavailable ⇒ abort, do not publish.** If `resolve_corpora` reports
  the code or data corpus `unavailable`, every path classification is wrong and
  the whole ranking is unsound — not merely some candidates. Exit non-zero with
  the named cause.
- **Origin facts: zero rows for a listed id is a collector failure, not a
  fact.** `aitask_backlog_origin_facts.sh` guarantees exactly one row per task
  even with no resolvable origin (`source=absent`), so a *missing* row means
  the collector broke. Abort rather than let `reduce_origin_facts({})` quietly
  degrade that task to the `unknown` band — the header's own rule is "never
  infer a fact from an absent line".
- **Everything else publishes, hedged.** A degraded or unavailable in-flight
  source turns the affected candidates `UNCHECKABLE` with named causes, which
  is already the checker's behaviour; the run summary reports those counts and
  causes (see the honesty requirements). Partial origin resolution degrades
  `confidence` through `confidence_for`, which is also already implemented.

`trail_id` must satisfy `^trail-[a-z0-9][a-z0-9_-]{2,63}$` and the handle
`art:[a-z0-9][a-z0-9._-]{0,127}` — `trail-backlog-roadmap` /
`art:trail-backlog-roadmap` satisfy both.

### Conventions

Follow `aitask_backlog_origin_facts.sh`'s header contract: every **content**
state exits 0 (a zero-candidate corpus is an answer), CLI misuse exits 2.
`aidocs/framework/shell_conventions.md` for the wrapper.

Whitelist the new helper — 5 touchpoints (1, 3, 4, 6, 7):

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_backlog_roadmap.sh
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_backlog_roadmap.sh
```

## Step 2 — The standing holder task

Create one task whose sole purpose is owning the handle, so the roadmap
outlives t1569:

```bash
./.aitask-scripts/aitask_create.sh --batch --name backlog_roadmap_artifact_holder \
  --priority low --effort low --type chore --status Postponed --commit
```

`Postponed` is the framework's word for deliberately-not-picked work, so the
holder never surfaces in `/aitask-pick` and never archives. Its body must say
plainly that it is an artifact holder, not work, and name the handle. Record the
resulting id as the `owner` in the trail and in the skill body.

## Step 3 — The skill (4 files, static)

Profile-agnostic skills keep a single `SKILL.md` and skip the `.j2` template
(`aidocs/framework/skill_authoring_conventions.md:220-222`) — phase 1 is
advisory and read-only, so there is no genuine per-profile behaviour.

```
.claude/skills/aitask-backlog-roadmap/SKILL.md      # canonical body — write this
.agents/skills/aitask-backlog-roadmap/SKILL.md      # generated
.opencode/skills/aitask-backlog-roadmap/SKILL.md    # generated
.opencode/commands/aitask-backlog-roadmap.md        # generated
```

Template: `.claude/skills/aitask-stats/SKILL.md` (frontmatter `name` +
`description`, then `## Usage`). Generate the three wrappers — they are rendered
from the `description:` and the first `## Usage` paragraph
(`aitask_audit_wrappers.sh:253-378`); hand-writing them drifts:

```bash
for tree in agents opencode-skill opencode-command; do
  ./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper "$tree" aitask-backlog-roadmap
done
./.aitask-scripts/aitask_skill_verify.sh   # cross-tree parity: the check a static skill hits
```

### Skill body

The agent's authorship is deliberately narrow — everything ranked, hedged and
classified is computed by `roadmap_policy`.

**One skill, explicit modes** — the same shape `aitask-trail` uses (it is a
single skill whose `aitask_trail_depth.sh resolve` emits `MODE:` for create /
refresh / show; there are no separate create and refresh skills to copy). Modes
here: **`--show`** (read-only) and the default **rescan-and-update**. There is
no separate create mode — see the detection step, which makes create/update an
outcome, not a user decision.

1. **Resolve mode.** `--show` → fetch the current version, render it, perform no
   writes, stop. Otherwise continue.
2. **Detect existence, capture the base version and the previous members.**
   `ait artifact versions art:trail-backlog-roadmap` — **exit 1** means no
   manifest → this run will `create`; **exit 0** means it exists → this run will
   `update`, and the `* sha256:` line is recorded as `base_version`. Branch on
   the **exit status**, not on stdout text, and never through a pipe (a pipe
   returns the pipe's status, so `versions … | grep` would report success for a
   missing handle).

   On the update path, also fetch the current document **before** recomputation:
   ```bash
   ait artifact get art:trail-backlog-roadmap --out <prev.json>
   ```
   and collect `previous_members` = every `waves[].entries[].task` value
   (`roadmap_policy.py:_entry` writes the ref under `task`). Neither `versions`
   nor the newly encoded document carries the old member list, so without this
   fetch the run summary's join/leave delta cannot be produced truthfully — it
   would have to be guessed or silently dropped. On the create path
   `previous_members` is empty and the delta is "first publication".
3. **Author the narrative** into a JSON file with `problem_statement` and
   `recommendation_summary` (see the narrative input contract). This happens
   **before** the driver runs.
4. **Run the driver:**
   ```bash
   ./.aitask-scripts/aitask_backlog_roadmap.sh \
     --narrative <narrative.json> --owner <holder> --out <tmp.json>
   ```
5. **Validate:** `./.aitask-scripts/aitask_trail_depth.sh validate <tmp.json>
   --expect-depth deep` → `VALID:trail-backlog-roadmap`.
6. **Compute the membership delta.** Diff the encoded document's
   `waves[].entries[].task` set against `previous_members`: **joined** (in new,
   not old), **left** (in old, not new). This is what the run summary reports
   and what the confirmation below shows.
7. **Confirm before writing — NON-SKIPPABLE.** The default mode persists an
   artifact version, and `aitask-trail`'s create/refresh flows both gate that on
   an explicit confirmation; an advisory invocation must not silently publish.
   `AskUserQuestion` — "Publish this roadmap?" — stating **create vs update**,
   the `base_version` on the update path, and the membership delta (counts plus
   the joined/left ids). Options: "Publish" / "Discard". `--show` never reaches
   this step.
8. **Write, once.**
   - *Create path:*
     ```bash
     ait artifact create <holder> <tmp.json> --kind implementation_trail \
       --handle art:trail-backlog-roadmap --name "Background-work roadmap"
     ```
     Parse the `HANDLE:` line (`aitask_artifact.sh:320`).
   - *Update path:* **stale-base guard first** — re-run `ait artifact versions`
     and compare its `* sha256:` line against the `base_version` captured in
     step 2. The artifact CLI has no compare-and-swap, so this is the only thing
     standing between a concurrent refresh and a silent overwrite. If it moved,
     `AskUserQuestion`: "Re-run the analysis against the new current" /
     "Overwrite anyway (their version stays recoverable via `artifact
     versions`)" / "Abort".

     **"Overwrite anyway" must re-derive the delta before it writes.**
     `previous_members` and the delta shown at step 7 describe the version
     captured in step 2, which is no longer the one being superseded. Writing on
     that branch without re-deriving would report joins and leaves against a
     predecessor that never existed in the version chain — a summary that is
     confidently wrong rather than merely stale. So on this branch, and before
     the write:
     1. `ait artifact get art:trail-backlog-roadmap --out <prev2.json>` — the
        **newly** current document;
     2. recompute `previous_members` and re-run step 6's diff against it;
     3. present a **fresh** confirmation showing the new base version and the
        re-derived delta.

     The encoded document itself is **not** rebuilt: the corpus facts did not
     change because someone else published, and choosing "Overwrite anyway" is
     precisely the statement that this run's analysis stands. Only the
     *reported relationship to the predecessor* was invalidated, and that is all
     that is recomputed.

     Only then:
     ```bash
     ait artifact update art:trail-backlog-roadmap <tmp.json>
     ```
     No `HANDLE:` line on update.
9. **Print the run summary**, including the membership delta from step 6.

### This rerun is a rescan, not a replay-refresh

A distinction the docs and the run summary must both state, because getting it
wrong promises a currency the artifact does not have.

`generation.inputs` lists only the **published 40**, so
`aitask_trail_gather.sh drift` answers one question: have those forty members'
recorded inputs changed? A `CURRENT` verdict is therefore **not** evidence that
the top 40 are still the right 40 — a candidate outside the trail can have
gained risk, landed its origin, or become unblocked, and drift cannot see it
because it was never an input.

So this skill's rerun **recomputes the whole corpus from scratch and may change
membership**, which is a different operation from the generic trail refresh that
replays recorded inputs. Say so in three places: the skill body, the docs page,
and the run summary (naming any entries that joined or left since the previous
version). Narrowing `generation.inputs` to the published members is deliberate —
it is what keeps drift meaningful for the members instead of firing on all 206
non-members — and this wording is the honest statement of what that buys and
what it does not.

### `CURRENT` never validates the in-flight evidence

A second and sharper limit on the same verdict. Lanes, `CLEAR`/`CONFLICT` and
the whole no-known-conflict estimate are scored from the **wide** snapshot's
in-flight evidence, which is **structurally absent from every digest**. So a
published member can acquire in-flight work after publication — invalidating its
lane — while drift still reports `CURRENT`.

**Putting in-flight facts into the generation contract is not an available
option**, and not merely an undesirable one:

- `trail_gather.py` prints `DIGEST:` **before** the gated in-flight block
  (`:1119-1125`); the four `INFLIGHT*` prefixes are excluded by construction,
  not by convention (`:616-619`).
- `tests/test_trail_gather.py` enforces it from three directions:
  `test_digest_is_unchanged_by_the_flag` (`:1408`),
  `test_lock_acquisition_changes_records_but_not_the_digest` (`:1460`), and
  `test_an_inflight_fact_in_an_input_record_is_rejected` (`:1446`) — which
  **actively rejects** an in-flight fact smuggled into an input record.
- That exclusion is the hazard t1569's parent task pins by name: locks and
  in-flight status change minute to minute, so admitting them to the digest
  would make **every existing trail** report STALE permanently.

Therefore take the stated alternative: **say plainly, in the skill body, the
docs page and the run summary, that a `CURRENT` verdict covers task-record
inputs only and never validates in-flight or admission evidence** — that
evidence is as of the run, and re-running the skill is the only thing that
refreshes it. This is the same "reserving nothing" honesty the design record
already demands of `CLEAR`, applied to the freshness verdict.

Refs are canonical `<project>#<id>` — copy from the gatherer byte-identically;
digest provenance depends on it.

### Run-summary honesty requirements (correctness, not tone)

Per `background_work_roadmap.md:367-377`:

- The lanes are an **estimate** — origin/topic evidence, in-flight state as of
  the run, **reserving nothing** — and `/aitask-pick` runs the live preflight
  before implementation. A `CLEAR` estimate must never read as an admission
  decision.
- **Never** "safe to run in parallel". Say **"no known conflict at check
  time"**.
- Surface the origin-quality histogram (`ORIGIN_QUALITY:<exact>|<topic>|
  <unknown>`), mutually exclusive — never quote the raw topic-signal population.
- Show `UNCHECKABLE` counts **with their named causes** (the `UNCHECKABLE_CAUSE:`
  scopes and reasons the checker emits), not just the safe lane.
- State the corpus size and that only the top 40 are published.
- State that this run **rescanned the whole corpus and may have changed
  membership**, naming the entries that joined and left (the step-6 delta).
- State both limits of a `CURRENT` drift verdict: it speaks only for the
  **published members**, and it covers **task-record inputs only** — it never
  validates the in-flight or admission evidence the lanes were scored from.

## Step 4 — Docs

- `website/content/docs/skills/_index.md` — add a table row (analysis/reporting
  group, near `/aitask-trail` and `/aitask-stats`).
- New `website/content/docs/skills/aitask-backlog-roadmap.md`, which must cover
  the `--show` / rescan-and-update modes, state plainly that this skill's rerun
  **recomputes the corpus and may change membership** (unlike the generic trail
  refresh, which replays recorded inputs), and state both limits of a `CURRENT`
  verdict — published members only, task-record inputs only, never the in-flight
  evidence.
- A workflows note documenting t1569_4's preflight **including the residual
  race**: the check is a snapshot and reserves nothing, so overlapping work can
  begin the instant after it passes.
- `docs/README.md` if it lists skills.

Prefer `{{< relref "/docs/..." >}}` over hand-written relative paths, then run
`python3 check_links.py --build` from `website/`. Follow
`aidocs/framework/documentation_conventions.md`: current-state-only prose, no
version history, genericize passages naming specific coding agents.

## Step 5 — Two follow-ups

**t1343 adoption.** Swap the checker's *evidence backend* to the declared-claims
model (per-task claim store under `.aitask-gates/<id>/`, deterministic set
intersection emitting `PAIR:` / `PHASE:` / `UNCLAIMED:` / `CLEAN:`). t1343's
`depends: [1275]` is satisfied (t1275 landed 2026-08-25). t1569_4's preflight is
the consumer surface t1343 was missing, so this is a **backend swap behind an
unchanged verdict contract**, not a rewrite — and it is what closes the
point-in-time race, since a claim registry reserves the surface where this
checker only observes it. `depends: [1343, 1569_4]`. **Add a bidirectional
coordination note to t1343.**

**`followup_origins:` enhancement.** A persisted direct-origin field populated at
every follow-up creation seam (the t1468_1 / t1468_2 shape). **Gated on the
design record's threshold** (`background_work_roadmap.md:319-326`), which
requires *both* a material dual-signal counterfactual **and** a non-trivial
corpus-wide `UNCHECKABLE` count attributable to origin quality. A
ranking-quality improvement, not a safety one — the preflight makes the safety
decision. `depends: [1569_6]`. Carry the measured numbers **and their sample
bias** (the dual-signal sample is entirely manual-verification-typed and does
not generalise) verbatim in its Problem section.

### Post-phase (risk mitigations)

Runs **after** Step 5.

**`drift_current_regression_test`.** Pin the `generation` / `inputs` contract
with an automated test: build a document over fixtures the way the driver does,
then assert `aitask_trail_gather.sh drift` returns `CURRENT`. The test must be
able to fail — include a negative control that builds `generation` from the
**wide** snapshot (all candidates rather than the published 40) and assert it
reports `STALE`. Without that control the test passes whether or not the
two-snapshot split is implemented, which is exactly the inference it exists to
guard.

## Risk

### Code-health risk: medium

- The driver re-implements `_run_replay`'s one-collection-then-re-aim sequence
  and reaches into private `_respin` / `_batch_map` / `_DATA_TREE`; a later
  change to that discipline diverges silently, because both halves keep emitting
  plausible output · severity: medium · → mitigation: inline pre-phase
  `share_replay_collection_seam`
- New surface in one slice: an impure driver, a whitelisted `.sh` (5
  touchpoints), a 4-file static skill and docs · severity: low · → mitigation:
  none (accepted residual — every piece is **additive**; no existing module's
  behaviour changes, and cross-tree parity plus the purity guard are enforced by
  existing tests)

### Goal-achievement risk: medium

- Live behaviour at ~246 candidates is unmeasured; the gatherer's in-flight
  probe runs under a 30s budget and origin facts read archived bundles ·
  severity: medium · → mitigation: inline pre-phase `live_scale_smoke_first`
- The two-snapshot split (wide for scoring, narrow for `generation`) is inferred
  from `cmd_drift`; if wrong, the trail reports STALE permanently · severity:
  medium · → mitigation: inline post-phase `drift_current_regression_test`
- The coordination lane is **unexercisable on the live corpus** (0 entries
  today), so wave 2 rests entirely on synthetic fixtures · severity: medium ·
  → mitigation: none (accepted residual, inherited from t1569_5, which proved
  the lane with deterministic fixtures and pinned the live smoke to shape only —
  re-proving it here would re-run that same fixture argument)
- A `CURRENT` drift verdict never validates the in-flight evidence the lanes
  were scored from, so a published member can gain in-flight work and still read
  as fresh · severity: medium · → mitigation: none available in the digest (an
  existing guard, `test_an_inflight_fact_in_an_input_record_is_rejected`,
  rejects it, and admitting in-flight facts would make every trail permanently
  STALE) — bounded instead by stating the limit in the skill body, the docs page
  and the run summary
- Ranking quality has no oracle — there is no ground truth for "the right
  order" · severity: low · → mitigation: none (accepted residual — the ranking
  is advisory, every score component is shown per entry, and `/aitask-pick` runs
  the live preflight before any of it becomes an admission decision)

### Planned mitigations
- timing: pre-phase | name: share_replay_collection_seam | type: refactor | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — driver duplicates _run_replay's collection discipline and couples to private names | desc: Extract the one-collection-then-re-aim sequence into a public function in parallel_admission_collect.py and consume it from both _run_replay and the roadmap driver.
- timing: pre-phase | name: live_scale_smoke_first | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — live behaviour at ~246 candidates unmeasured against the gatherer's 30s in-flight budget | desc: Run the wide snapshot and origin-facts collector over the real candidate id list before writing the encoder, recording wall-clock and any degraded or unavailable source.
- timing: post-phase | name: drift_current_regression_test | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — the two-snapshot generation/inputs split is an inference that, if wrong, makes the trail permanently STALE | desc: Assert drift returns CURRENT for a document built the driver's way, with a negative control building generation from the wide snapshot that must report STALE.

## Verification

```bash
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_*.sh
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
cd website && python3 check_links.py --build
```

New tests:

- `tests/test_roadmap_run.py` — the driver over frozen fixtures:
  - the cap takes the first 40 *after* sorting;
  - the narrow snapshot supplies `generation`;
  - `EmptyRoadmapError` surfaces as "nothing published" rather than an empty
    document;
  - `data_tracked` is passed — a negative control omitting it must show the
    phantom-collapse, proving the assertion can fail;
  - **narrative validation**: a missing file, a missing required key, a
    whitespace-only value and an unexpected extra key each exit 2 with a named
    error, and none of them produce an output document;
  - **degraded-evidence threading**: a fixture whose corpus reports
    `unavailable` aborts and publishes nothing; a fixture where one listed id
    has no `ORIGIN_FACT:` row aborts; and a fixture with a degraded in-flight
    source publishes with those candidates `UNCHECKABLE` and their causes named.
    The last one is the discriminating case — it must **not** abort, or the
    policy collapses into "abort on anything";
  - **cap contract**: `--cap 0`, `--cap -1` and `--cap ten` each exit 2 and
    write nothing; a corpus smaller than the cap publishes every candidate and
    says so in `method_note`.
- `tests/test_backlog_roadmap_membership_delta.py` — a **two-version** fixture:
  encode v1, change the corpus so one candidate qualifies and another drops out,
  encode v2, and assert the diff over `waves[].entries[].task` reports **both**
  the join and the leave. Asserting only one direction would pass against an
  implementation that reports joins and silently swallows departures — and a
  departure is the more consequential half, since it is a task the user was
  previously told to consider.

  Same module, **race fixture**: capture the base at v1, publish an intervening
  v2 with a *different* member set, then take the "Overwrite anyway" branch and
  assert the reported delta is computed against **v2** — the version actually
  superseded — not against the v1 captured at step 2. The fixture must be built
  so the two deltas differ (a task present in v2 but absent from v1, or the
  reverse), or it passes whether or not the re-derivation happens.
- Purity guard unchanged: `roadmap_run` must **not** appear in `PURE_MODULES`,
  and `roadmap_policy` / `roadmap_premise` must still be listed.

End-to-end on the live repo:

1. Run the skill; artifact created and `HANDLE:` parsed.
2. `aitask_trail_depth.sh validate <file> --expect-depth deep` → `VALID:trail-backlog-roadmap`.
3. `aitask_trail_gather.sh drift --trail art:trail-backlog-roadmap` → `CURRENT`
   immediately after creation.
4. `ait artifact versions art:trail-backlog-roadmap` lists v1 as current.
5. Re-run; existence detection selects `update` (exit 0), the previous document
   is fetched, the confirmation shows the base version and the membership delta,
   the stale-base guard passes, `update` produces v2, and the holder's task file
   is untouched.
6. `--show` renders the current version and writes nothing (`artifact versions`
   still reports v2 as current afterwards); answering "Discard" at the
   confirmation likewise leaves the current version untouched.
7. `ait board` By-Trail view shows the trail; any coordination entries glyphed `⇄`.
8. Archive-resolution check: confirm `ait artifact get art:trail-backlog-roadmap`
   still resolves from the manifest independently of the owner's task file.

Step 9 (Post-Implementation) handles cleanup, archival and merge.
