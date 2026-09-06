---
priority: low
effort: high
depends: []
issue_type: enhancement
status: Postponed
labels: [backlog, metadata]
created_at: 2026-09-06 17:07
updated_at: 2026-09-06 17:07
---

Add a persisted **direct-origin** frontmatter field (`followup_origins:`)
populated at every follow-up creation seam, following the t1468_1 / t1468_2
shape (field foundation and creation seams as separate children).

This is a **ranking-quality** improvement, not a safety one. The
parallel-admission preflight makes the safety decision; origin quality only
affects how well the background-work roadmap *orders* candidates and how
confidently it hedges them.

## Status: GATED — the threshold is NOT met on current evidence

`aidocs/framework/background_work_roadmap.md` (§ Enhancement threshold) justifies
this field only when **both** hold:

1. the dual-signal counterfactual shows a material rank or lane change, **and**
2. the corpus-wide `UNCHECKABLE` count attributable to **origin quality** is
   non-trivial.

Measured 2026-09-06 by `aitask_backlog_roadmap.sh` over **255 candidates**:

| signal | value |
|---|---|
| origin quality (mutually exclusive) | **72 exact / 162 topic / 21 unknown** |
| `UNCHECKABLE` total | **214 of 255** |
| causes | `no_plan=214`, `unknown_history=31`, `unknown_origin=21` |
| dual-signal counterfactual | **0 of 0** — not measured this run |

**Neither condition is currently satisfied.** Condition 2 fails on
proportion, not just size: the `UNCHECKABLE` population is overwhelmingly
`no_plan=214`, which is an in-flight *plan availability* problem owned by
**t1688**, not an origin-quality problem. Only `unknown_origin=21` (~8% of the
corpus) is attributable to origin quality at all. Condition 1 was not measured,
so it is **unknown**, which is not the same as met.

## Sample bias — carry this verbatim, do not drop it

The counterfactual can only be computed over tasks carrying **both** an exact
origin signal and a topic root. Because the exact signal is written only by the
manual-verification seams, that sample is **entirely manual-verification-typed
and therefore not representative**. A result measured on it must never be
extrapolated to the topic-only population.

The divergence is also not merely "topic is wider": two live examples had exact
sets of 3 and 4 files against a topic set of 13, with an overlap of **zero**.
The topic root can be *disjoint* from the true origin, so the fallback can be
actively wrong rather than conservatively broad.

## Before implementing

Re-measure both conditions after **t1688** lands, since it should move the
`no_plan` population and change what the residual `UNCHECKABLE` is attributable
to. Only promote this task out of `Postponed` if the threshold is then met on
evidence, recorded here.
