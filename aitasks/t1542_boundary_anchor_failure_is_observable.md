---
priority: medium
effort: medium
depends: [t1159_7]
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-17 12:50
updated_at: 2026-08-17 16:21
---

## Origin

Risk-mitigation ("after") follow-up for t1518, created at Step 8d after implementation landed.

## Risk addressed

`addresses:` code-health — silent rot of a native-dialog boundary literal, whose surface triples when the agent set widens.

Verbatim from t1518's plan `## Risk` → Code-health risk:

> Adds **version-sensitive TUI literals** to a safety-relevant classification
> path. Codex/OpenCode UI churn rots them, and the failure is *silent in
> production*: a boundary that stops anchoring returns `UNKNOWN`, so the loop
> simply never fires, while the tests keep passing against the old stored fixture.
> Widening from one agent to three triples that surface · severity: medium ·
> → mitigation: boundary_anchor_failure_is_observable

## Goal

Surface a native-dialog boundary that has stopped anchoring, so literal rot is an
observable signal instead of a loop that silently never fires.

Today `review_loop.classify_followed_change` returns `UNKNOWN` when
`_native_block_start` cannot locate the block for a kind that HAS a boundary
entry. That is indistinguishable — from every surface a user or an operator can
see — from "the agent did no work". The loop stays armed, the banner keeps
reading `⟳ auto-recheck ARMED`, and nothing ever fires.

The distinction worth making is between:

- a kind with **no** boundary entry, where `UNKNOWN` is correct and expected
  (the conservative default, deliberately preserved by t1518); and
- a kind **with** an entry whose pattern/strategy no longer matches the live
  frame — which means the shipped literal has rotted against a new CLI version
  and needs re-measuring.

Only the second is a defect. Suggested direction: count or flag the second case
and surface it (a banner qualifier, a counter, or a one-shot notify), keeping it
advisory — the loop must never refuse to run because a boundary failed to
anchor. Do not weaken the `UNKNOWN` default itself; the point is to make its
*cause* visible, not to change what it returns.

Reference: t1518's archived plan records the measurement recipe and the shipped
tables (`NATIVE_DIALOG_BOUNDARIES`, `NATIVE_DIALOG_STRATEGIES`,
`DELIBERATELY_UNANCHORED_KINDS`).

## Coordination

`depends: [t1159_7]`, added after creation. Step 8d spawns "after" mitigations
with no dependency by default, and that was wrong here.

- **t1159_7** (refactor review-loop post-review accretion) restructures
  `review_loop.py` and splits `_service_review_loop` into named stages. This
  task adds observability *into* that function, i.e. exactly the accretion
  t1159_7 exists to clean up. Its own task file already applies this reasoning
  to the neighbouring work: "**t1503** … is sequenced after this task so it does
  not add fresh accretion to `_service_review_loop`." The same applies here.
- **t1503** (surface review-loop non-convergence) targets the **same user
  surface** — "say so where the user already looks — the minimonitor loop
  banner". Read t1503 before designing this one: if it lands first, this signal
  should attach to whatever seam it establishes rather than adding a second,
  competing banner qualifier. t1503 is itself blocked on t1159_6 + t1159_7.

Neither is a scope change — the goal above stands. The sequencing exists so this
signal is designed against the post-refactor seam instead of being rewritten by
it.
