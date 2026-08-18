---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [backlog, scheduling, artifacts, skills, planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-18 12:33
updated_at: 2026-08-18 12:36
---

## Problem

**59% of the active backlog is auto-spawned follow-up work that nobody picks.**

Measured over the live corpus (2026-08-18): 306 active parent tasks, 287 of them
`Ready`. **182 carry a `followup_kind:`** — risk_mitigation 67, upstream_defect
48, manual_verification 48, carry_over 9, verification_failure 5, review_finding
5. Including children, 219 of 512 active task files are follow-ups. t1544's own
prototype measured the backlog roughly **doubling in five weeks** (201 → 421),
with follow-ups going 46 → 194 while genuine new work grew only 155 → 228.

Being machine-authored, these tasks are never picked proactively. That produces
four compounding failures:

1. **Growth.** Arrivals outpace departures, and the backlog itself becomes the
   obstacle to choosing work.
2. **Staleness.** A follow-up written against code that has since churned
   describes a premise that no longer holds.
3. **Redundancy.** The same concern is re-spawned by different seams. De-dup
   exists only *per seam* (shadow concern spin-off skips already-spun markers;
   risk-mitigation has a reconcile-before-create protocol) — never across them.
4. **Context loss.** The longer a follow-up sits, the less the user remembers
   why it was spawned, which makes it even less likely to be picked.

**Nothing in the framework helps.** `followup_kind` is display-only at every
consumer (`ait ls` filter, board glyph + group roll-up, monitor sibling picker,
work report, applink). The implementation-trail schema **explicitly declares it
not ordering-relevant** and omits it from the digest and drift-code set. There is
no prioritization, no cross-seam de-duplication, and no staleness keyed on it
anywhere.

## Goal

A **background-work roadmap**: a durable, refreshable, evidence-backed ordering
of backlog work that is safe to run *in parallel with whatever is currently in
flight*, ranked by value and freshness, so the user can open it at any moment and
start a task in the background with minimal conflict risk.

## Design decisions (settled during exploration — do not re-litigate)

### Shape: a dedicated skill emitting a standard trail artifact

Keep a **dedicated backlog/background-roadmap skill**. It emits a normal
`implementation_trail` artifact via `ait artifact`, so the board's By-Trail view,
`drift`, versioning and refresh all work unchanged.

Extend the **shared gatherer** (`.aitask-scripts/lib/trail_gather.py`) with
**only generic in-flight / lock and planned-surface facts**. Scoring, freshness,
follow-up semantics and lane policy stay **inside the new skill** — they are
policy, not facts, and must not leak into the shared gatherer.

Rationale: this also makes *ordinary* active trails aware of related work in
flight, which is a standing gap (RFC §7.2 lists in-flight/lock state as an
intended gather output; `trail_gather.py` has no such probe).

### One scan, two lanes

Both chosen conflict signals reduce to the same computation — a **hot file set**
per in-flight task:

- **(a) Origin-task git file sets.** Resolve each follow-up's origin via
  `followup_of:` / `verifies:`, find that origin's landed commits (commit
  subjects carry `(tNN)`), and take their changed paths. Requires **no new
  frontmatter** and works on all 182 follow-ups today.
- **(b) In-flight tasks' plan-file path lists.** Extract declared paths from the
  `aiplans/p<N>.md` of each in-flight task.

Intersecting a backlog task's file set against the in-flight hot set is **one
computation read with two signs**:

- overlap ⇒ **unsafe to start in parallel right now**
- overlap ⇒ **high value — this is exactly the area already being worked**

So the roadmap renders **two lanes**:

- **Parallel-safe lane** — start in the background now.
- **Coordination lane** — do *not* start alongside; fold into, or queue
  immediately after, the in-flight task. This directly addresses the recurring
  failure of working an area while forgetting the existing tasks that improve it.

The trail schema already carries the vocabulary for both and **nothing writes
it**: observation kinds `in_flight_conflict` / `shared_surface_collision` /
`stale_premise`, and relation kind `coordinates_with`.

### Scoring — transparent, overridable, component-wise

- **Origin risk fields are the primary value signal** — `risk_code_health:` /
  `risk_goal_achievement:` on the task or its origin. A risk_mitigation follow-up
  for a `high` risk outranks one for `low`.
- **In-flight area affinity is a strong but advisory boost.** It must surface
  relevant improvements while an area is active, but **must not bury urgent
  unrelated work**.
- **`priority:` is a weak, transparent tie-breaker only.** On auto-spawned
  follow-ups it is mostly a seam default, not a considered judgment.
- **`effort:` is a background-capacity / scheduling constraint, not value.**
- **`followup_kind` is NOT ordering-relevant in phase 1.** Its categories are not
  a reliable severity model, and the trail schema deliberately treats it as
  display-only. Do not mint the framework's first ordering-relevant use of it
  here.
- **Every score component must be shown per entry** so the user can understand
  and override the ranking.

### Freshness — two independent weights

- **Recency** — how recently the follow-up was spawned.
- **Premise validity** — evidence that the origin files/plan have *not* churned
  since spawn.

They are **separate weights**, so an old-but-still-valid task is not punished the
same as a recently-invalidated one.

### Staleness — narrow now, shared later

Deliver phase 1 with a **deliberately narrow, advisory premise-drift signal**
derived from the origin-task file sets already gathered. **Do not build a second
permanent staleness framework.** Put the result behind a **small replaceable
interface** and create an explicit adoption follow-up for **t1561**.

**Reuse t1555_1's now-committed conventions** (`.aitask-scripts/aitask_verification_stale.sh`,
landed in `0c2327060`; design record `aidocs/framework/manual_verification_staleness.md`):

- line protocol, one record per line, free-ish field last;
- **always exit 0** for every content state (CLI misuse still dies);
- tri-state `FRESH` / `ASK_STALE` / `SKIP`, with **`SKIP` fail-open and silent**;
- **`UNKNOWN` drives the verdict, not advisory** — a path that cannot be checked
  means the check covers *less* scope than it claims, so `FRESH` would be a false
  all-clear;
- pathspec globbing hazard: curated paths are pathspecs and git fnmatch-globs
  `*`, `?`, `[...]` — pass them literally.

t1561 should generalize these into the shared mechanism for all task types, and
this roadmap should then **consume that shared mechanism** rather than keeping
its own.

### Staged delivery — each phase gated on the prior proving out

- **Phase 1 — order only, purely advisory.** Produce the ranked, conflict-aware
  two-lane roadmap. Never changes task state. Stale and redundant follow-ups
  still appear, flagged and ranked low. **Establish the useful roadmap first.**
- **Phase 2 — flag dispositions.** Detect stale premises and cross-seam
  redundancy and *recommend* a disposition (fold / postpone / close) per task.
  Still writes nothing.
- **Phase 3 — act on dispositions.** Fold duplicates and postpone stale
  follow-ups, after per-batch user confirmation.

Richer automation is added **only after the prior phase proves reliable**. Phase
1 is the deliverable of this task tree; 2 and 3 are gated behind it.

### Corpus

**Auto-spawned follow-ups plus low-effort genuine work** — tasks carrying a
`followup_kind:`, plus small genuine tasks that are good background fodder
(`effort: low`, no in-flight overlap). Not the whole Ready backlog; that
competes with `/aitask-pick`.

## Hazard found during exploration (must be honored)

`trail_gather.py` guarantees **"two runs over unchanged state are byte-identical"**
and deliberately excludes volatile fields (`boardidx`, timestamps) from `DIGEST:`.

**Locks and in-flight status change minute to minute.** If the new in-flight
facts enter the digest, **every existing trail reports STALE permanently**. The
new records must be *emitted but digest-excluded*, exactly like `boardidx`.
Cover this with a test that runs the gatherer twice across a lock acquisition and
asserts the digest is unchanged.

## Existing seams to build on (verified, do not reinvent)

| Need | Existing seam |
|---|---|
| In-flight, gated | `.aitask-scripts/aitask_query_files.sh inflight` → `INFLIGHT:<id>\|<path>\|<PLAN\|IMPLEMENT\|POSTIMPL>\|<NO_GATES\|ALL_PASS\|BLOCKED:csv>` |
| In-flight, all | `ait lock --list` → `t<id>: locked by <email> on <host> since <ts>` (branch `aitask-locks`; liveness via `lib/pid_anchor.sh`) |
| Plan path extraction | `aitask_remote_drift_check.sh:211-219` — **note its allowlist is repo-specific, the live bug t1275** |
| Staleness conventions | `aitask_verification_stale.sh` (see above) |
| Trail storage | `ait artifact create/update/get/versions`; schema `lib/implementation_trail.schema.json` |
| Gatherer / drift | `lib/trail_gather.py`, `aitask_trail_gather.sh`, `lib/trail_schema.py` |
| Mode/depth resolution | `aitask_trail_depth.sh resolve` — depth is resolved by a helper, never self-decided by the model |
| Retro-classification | `lib/followup_backfill_classify.py::classify()` — pure, no writes, no git, no subprocess |
| Board In-Flight view | `aitask_board.py:1835-1908` `_inflight_item_for` (blocked / agent / human + `next_action`) |

## Explicitly rejected

- **`file_references:` as the conflict signal.** Coverage is effectively zero —
  **0 of 306 active parent tasks** carry the frontmatter key; the MV staleness
  design measured 0/77 on manual_verification tasks; t1343 measured 2 of ~196.
  t1343 additionally rejects it for claim tracking on design grounds (it is a
  durable committed field, wrong for ephemeral data).
- **`aitask_remote_drift_check.sh` as the overlap check.** It compares
  `BASE..origin/BASE` — commits *already pushed*. Concurrent local agents have
  pushed nothing, so it reports `NO_OVERLAP` for exactly the collisions that
  matter.
- **Making `followup_kind` ordering-relevant** (phase 1) — see Scoring above.
- **Anchor/topic/label overlap as the primary conflict signal** — considered and
  not selected; high false-positive rate.

## Decomposition guidance

Effort is `high` because phase 1 alone spans a new skill surface, a shared
gatherer extension, and a staleness seam. Decompose into children; put the
**riskiest/most uncertain piece first** — the hot-file-set derivation and the
digest-exclusion contract are the parts most likely to invalidate the design.
Prefer pure, testable units (file-set derivation, scoring, lane assignment) ahead
of the agent-authored skill instructions.

## Related tasks (deliberately NOT folded)

- **t1561** — *generalize task staleness detection*. This roadmap should consume
  its shared mechanism once it lands. Create an explicit **adoption follow-up**.
- **t1555** / **t1555_1** — manual-verification staleness. **Design evidence and
  reusable conventions**, not a dependency or a stable contract to build on.
- **t1343** — *parallel agent file conflict advisory*. The declared-claims model
  (per-task claim store under `.aitask-gates/<id>/`, deterministic set
  intersection emitting `PAIR:/PHASE:/UNCLAIMED:/CLEAN:`, minimonitor glyph, peer
  conflict check at the planning checkpoint) is a **better long-term conflict
  signal** than the derived one used here. Treat as an adoption follow-up.
  `depends: [1275]`.
- **t1470** — *surface intra-wave parallel safety in the By-Trail view*. The
  natural board surface for this roadmap's lanes, once the trail exists.
- **t1544** — *backlog and net-flow stats by category*. Supplies the measurement
  that tells you whether the roadmap is actually draining the backlog.
- **t1275** — drift-check plan-path allowlist is repo-specific; affects any reuse
  of the plan-path extractor.
- **t1210** — the implementation-trail brainstorm this builds on.
