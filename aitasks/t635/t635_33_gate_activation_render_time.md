---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [gates, task_workflow, execution_profiles]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-15 19:12
updated_at: 2026-07-17 10:50
---

## Problem

Gate integration into task-workflow is too rigid: gates run/record when not
actually needed, appreciably slowing task execution. t635_14 retired the
render-time `{% if %}` risk-gating toggle in favour of a `default_gates` profile
key + **runtime checks present in every rendered profile** (e.g. `default`'s
rendered SKILL.md grew ~717→766 lines for content it previously rendered nothing
for). This task redesigns gate activation so execution profiles + skill
templating **insert gating steps into task-workflow only when actually
required** (render-time omission), while preserving t635_14's single-source
resolution rule.

## Why render-time gating was removed (do NOT regress)

The original problem was gate *selection* split across two sources — task
`gates:` metadata AND profile `default_gates`. t635_14 unified the **resolution
rule** (task `gates:` wins when present, else profile default) so there is one
place to reason about which gates a task runs. The redesign must preserve that
single-source resolution while recovering render-time leanness.

## Chosen model — Model 1: profile renders the ceiling; task selects within it at runtime

- The **execution profile** declares a render-time gate set (the machinery
  rendered into that profile's task-workflow variant). Lean profiles render
  none → fast, minimal skill. Rendering stays **per-profile cached** — no
  per-task render cost.
- The **task `gates:` metadata** selects/narrows WITHIN the rendered set at
  runtime. Both layers "activate": the profile decides what is *rendered*, the
  task decides what *executes*.
- **Ceiling behavior (user-confirmed):** a gate filtered out by the profile is
  **invisible**, or at most reported as **"skipped: execution profile"** —
  **never a hard error**. Assume the user intended the filter when they chose
  the profile. The skipped-notice may be omitted if that makes the
  implementation easier/safer.

## CRITICAL correctness invariant (user: "we must be very careful")

A task's `gates:` may still declare a gate the profile did NOT render. The
rendered skill has no machinery to record it, but today's runtime enforcers
(`aitask_gate.sh effective-gates`, `ait gates run`, and especially the
`aitask_archive.sh` gate guard) read the task's declared `gates:` directly — so
a declared-but-unrendered gate would **block archival with no way to satisfy
it**, recreating the t1147 bug via profile filtering.

- **Invariant:** the profile filter applies at **every** layer, not just
  rendering. `effective_gates(task) = resolve(task.gates, profile.default_gates)
  ∩ profile.rendered_set` — always a **subset of what is rendered**. Filtered
  gates are treated as skipped/absent **everywhere** (resolution, orchestrator,
  archival guard, dependency-unblock), so they can neither break the rendered
  skill nor block archival.

- **Enforcement substrate — where the filtered set is persisted.** Many
  enforcement paths run with **no live profile in scope**: dependency-unblock
  computes from a *dependent* task's perspective; the board, cross-session
  picks, and `ait gates run` may not carry the picking profile. A purely
  runtime-recomputed filter is therefore fragile. **Recommended: materialize a
  durable `active_gates` field** on the task, written at pick/claim time (and
  **re-derived on every re-pick under the CURRENT profile**). **Every** runtime
  enforcer must consume `active_gates`, never raw `gates:` alone:
  - `aitask_gate.sh archive-ready` + the `aitask_archive.sh` gate guard,
  - dependency-unblock (`blocks_dependents` computed over `active_gates`),
  - procedure-gate dispatch (`aitask_gate.sh procedure-gates`),
  - `ait gates run` orchestrator, and `effective-gates` / `should-self-record`.

  Raw `gates:` stays the task's **declared intent**; `active_gates` is the
  profile-filtered **effective set** that governs rendering AND enforcement in
  lockstep. *(Alt considered: thread a durable profile context into every
  command so each re-derives the set — rejected as primary because
  dependency-unblock genuinely has no profile to thread.)*

- **Staleness / supersession:** recompute `active_gates` at claim time under the
  current profile — a re-pick under a *different* profile updates the effective
  set; a stale `active_gates` would silently enforce the wrong gates. Never
  leave `active_gates` temporarily untrue vs the governing profile.

- **Provenance (auditability, user-requested):** persist the set **with the
  profile that produced it** — `active_gates_profile: <name>` (or similar)
  alongside `active_gates`. Recompute-at-claim keeps enforcement *correct*;
  provenance makes staleness **detectable and explainable** — a checker can
  compare the stamped profile against the currently-governing profile and flag
  "computed under `fast`, now governed by `default` → recompute" after a profile
  switch, a manual `gates:` edit, or a re-pick under another profile. Optionally
  also stamp a digest of the inputs (raw `gates:` + profile rendered-set) to
  detect a manual `gates:` edit that leaves the profile name unchanged.

- **Negative-control tests (must-have):** a task whose `gates:` includes a
  profile-filtered gate must (a) render without that gate's machinery,
  (b) archive without blocking on it, and (c) unblock its dependents without
  waiting on it.

- **Open sub-decision:** whether the render ceiling is a reused `default_gates`
  (task can only narrow) or a distinct `rendered_gates` superset
  (backward-compatible default = render-all when unset). Reconcile with
  t635_14's current override semantics (task `gates:` beyond profile default).

## Coordination (t635 umbrella is incomplete — align, don't race)

- **t635_25** (leaner_gate_check_invocation): leans the *call shape* of gate
  checks but explicitly declines render-time omission — this redesign
  **extends** it to render-time. Decide fold vs sequence at planning.
- **t635_14**: the resolution rule being extended; do not regress its
  agent-error mitigation (tested helpers, not prose conditionals).
- **t635 umbrella** (many children pending): align with t635_24 (remove legacy
  verify_build), t635_28 (docs_updated activation), t635_31 (per-gate
  agent/model selection).
- **t1147** (registry correctness): landed first — canonical
  `.aitask-scripts/gates_reference.yaml` + drift guard. Its deferred scope is
  absorbed below.

## Absorbed deferred scope from t1147

- **Reconcile existing installs** (t1147's former Part 2): `ait gates
  sync-registry` filling missing verifier keys in an already-installed project's
  `aitasks/metadata/gates.yaml` without clobbering customizations (additive
  merge; conflict-reported, never silently overwritten; reads the canonical
  `.aitask-scripts/gates_reference.yaml`, which ships downstream). Largely
  design-agnostic, but under this redesign it should also reconcile profile gate
  policy — shape it here. **Until this lands, already-installed projects
  (incl. the thinking_app reproduction from t1147) remain on the manual
  workaround** (`aitask_gate.sh append <id> risk_evaluated pass`, or hand-copy
  the reference over the project registry).
- **Early "no verifier" warning** (t1147's former Optional hardening): warn at
  pick/plan time when a declared gate's registry entry has no `verifier` and is
  not `kind: procedure`, instead of silently deferring until archival blocks.
  Likely **subsumed** by "only activate gates when required" — re-evaluate
  whether still needed.
