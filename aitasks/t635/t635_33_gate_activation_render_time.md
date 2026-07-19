---
priority: medium
risk_code_health: high
risk_goal_achievement: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [gates, task_workflow, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
folded_tasks: [635_25]
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/fable5
created_at: 2026-07-15 19:12
updated_at: 2026-07-19 09:06
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

## Absorbed deferred scope from t1147 — SPLIT OUT to t635_34 (2026-07-17)

The absorbed t1147 reconcile scope (`ait gates sync-registry` for existing
installs + the early "no verifier" warning) has been **moved to a dedicated
sibling, `t635_34` (reconcile_installed_gate_registry)**, which `depends:
[t635_33]` so it can reconcile against the `active_gates` / `rendered_gates`
model landed here. This task (t635_33) is now scoped to the correctness/
render-time **core** only. See
`aitasks/t635/t635_34_reconcile_installed_gate_registry.md`.

**Resolved open sub-decision (ceiling source):** the render ceiling is a
**distinct `rendered_gates` profile key**, defaulting to the profile's
`default_gates` when unset (backward-compatible — existing profiles need no new
key). `active_gates = resolve(task.gates, default_gates) ∩ rendered_gates`.

**Resolved coordination (t635_25):** **folded into this task** (see Folded
Tasks below) — the call-shape verbs (`active`, `backfill-declaration`,
pure-bash decision verbs) are implemented here in the same pass as the
active_gates rewrite, since both touch the same `planning.md` / `SKILL.md`
gate call-sites.

## Merged from t635_25: leaner gate check invocation


## Context

t635_14 unified profile→gate-declaration (the `risk_evaluation` Jinja toggle was
retired in favour of a `default_gates` profile key + runtime resolution). It
works, but it traded away some of the leanness the profile/template-render system
was built for: render-time `{% if %}` gates omit a block entirely for profiles
that don't use it, whereas t635_14's risk-gating is now **runtime checks present
in every rendered profile** (e.g. `default`'s rendered `SKILL.md` grew ~717→766
lines for content it previously rendered nothing for).

The agent-error risk is already mitigated (the decisions are tested helpers, not
prose conditionals). What remains suboptimal is the **call shape** of the gate
check/invocation: the sites mix three interaction styles, and the worst make the
agent parse text or run inline multi-command bash:

- **Producer trigger** (`planning.md` §6.1 end-of-planning terminal step):
  `aitask_gate.sh effective-gates <id> --profile <f>` emits a **list**, then the
  prose says "if the output contains `risk_evaluated`…" → the agent must
  grep/substring-scan multi-line text. (Same shape in the risk-section guard.)
- **Step-7 backfill** (`SKILL.md`): a ~6-line **inline bash block**
  (`has-gates-field` + `effective-gates | paste -sd,` + non-empty test +
  `aitask_update.sh --gates` + `./ait git` commit). This also **violates the
  repo's "encapsulate workflow bash in a whitelisted helper, don't inline it"
  convention** ([[feedback_encapsulate_workflow_bash_in_helper_script]]).
- **Self-record guard** (`SKILL.md` Step 7): `aitask_gate.sh should-self-record
  <id> <gate>` → exit code (the right shape) — but it `delegate_python`s, so it
  conflates "skip" with "python unavailable" (both exit 1).

This task optimizes the gate-check **invocation** so calls are concise,
unambiguous, and need no per-site parsing wrapper.

> **Coordination (t635_33):** the render-time question this task declines
> ("re-introduce `{% if %}` omission") is now owned by **t635_33**
> (gate_activation_render_time) — profile renders the gate-machinery ceiling,
> task `gates:` selects within it at runtime, enforced via a persisted
> `active_gates` field. Decide fold-vs-sequence with t635_33 at planning time;
> the call-shape verbs here remain useful under either outcome.

## Goal

Make every gate check/invocation in the task-workflow a single call the agent
either branches on by exit code or runs-and-forgets — no text grepping, no inline
multi-command bash, no per-call parsing instructions.

## Scope (the optimizations)

1. **Exit-code decision verb.** Add `aitask_gate.sh active <id> <gate> [--profile
   <f>]` → exit 0 = effectively active (task `gates:` if present else profile
   `default_gates`) / 1 = not. Replace the `effective-gates | grep` producer-trigger
   in `planning.md` and the risk-section-guard check with it:
   `aitask_gate.sh active <id> risk_evaluated && <run producer>`. Keep
   `effective-gates`/`list` for introspection/debug only.
2. **Single action verb for the backfill.** Add `aitask_gate.sh
   backfill-declaration <id> [--profile <f>]` that internally does the
   presence-check (`has-gates-field`) + resolve (`effective_gates`) + write
   (`aitask_update.sh --gates`) + path-scoped commit, printing ONE status line
   (`BACKFILLED:<csv>` / `NOOP:already-declared` / `NOOP:opt-out` /
   `NOOP:no-defaults`). Replace the Step-7 inline bash block with the single call
   (honors the encapsulate-bash convention; unit-test it).
3. **Pure-bash decision verbs (no python-availability ambiguity).** Implement the
   decision verbs (`active`, `has-gates-field`, `should-self-record`) on the
   bash/awk path (reuse `read_yaml_list`, as `cmd_list` already does) so they are
   always available → clean 0/1 with no degradation branch in the markdown.
   **Open sub-decision:** pure 0/1, OR reserve exit 2 for "couldn't determine" so
   an infra failure never silently reads as "not gated" (unambiguous vs minimal —
   decide in planning).
4. **Document the gate-CLI contract once.** A short reference (extend
   `gate-recording.md` or a new `gate-cli.md`): decision verbs → exit codes;
   action verbs → do-and-print-one-status-line. Reference it from the call sites
   instead of re-explaining parsing at each.

## Open decision (resolve during planning) — #5 self-gating procedures

The leanest option: have the workflow invoke the producer / post-approval risk
recording **unconditionally** (a one-line procedure pointer), and make each
procedure's FIRST line the exit-code gate-check that returns early if not
applicable (`aitask_gate.sh active <id> risk_evaluated || return`). This removes
gate-branching from the rendered skill entirely (closest to render-time leanness),
but the gate-check becomes less visible in the main flow. Trade-off call — present
both in the plan and let the user choose.

Also consider (may fold in or defer): moving the **backfill earlier to Step 4**
(pre-plan-mode ownership) so the task's `gates:` is canonical before planning and
every downstream site is a plain task-state read with no `--profile` fallback.
Watch: Step 4 runs for manual_verification tasks and re-entry too — guard
accordingly.

## Key files to modify

- `.aitask-scripts/aitask_gate.sh` — new `active` / `backfill-declaration`
  subcommands + dispatch + help; move decision verbs to the bash path.
- `.aitask-scripts/lib/gate_ledger.py` — keep `effective_gates` /
  `should_self_record` / `_frontmatter_has_key` as the python fallback; ensure the
  bash path mirrors them.
- `.claude/skills/task-workflow/planning.md` — producer trigger + risk-section
  guard → `active`.
- `.claude/skills/task-workflow/SKILL.md` — Step-7 backfill → `backfill-declaration`;
  self-record guard unchanged in shape (already exit-code).
- (if #5) `.claude/skills/task-workflow/risk-evaluation.md` + `gate-recording.md`
  — self-gating first line; main-flow sites become one-line pointers.
- Regenerate task-workflow goldens + committed `remote` prerenders; run
  `aitask_skill_verify.sh`.

## Reference patterns

- `cmd_list` in `aitask_gate.sh` — the bash `read_yaml_list`/awk path for the
  pure-bash verbs (#3).
- `should-self-record` (t635_14) — the exit-code decision-verb pattern to mirror
  for `active`.
- `tests/test_gate_effective_gates.sh` / `tests/test_gate_declaration_backfill.sh`
  — scaffolds for the new verb tests (real `aitask_gate.sh` entry point, fixture
  cwd + `TASK_DIR`).
- `task-creation-batch.md` `--gates` injection — the creation-side declaration.

## Out of scope / coordination

- **Step-9 gate-RUN dispatch extraction** (the ~40-line inline `ait gates run` +
  status-handling block in `SKILL.md` Step 9, from t635_12) is NOT in scope here —
  it folds into **t635_24**, which already rewrites that block to remove the legacy
  inline `verify_build` fallback. Coordinate: extend t635_24 to extract the
  gate-run glue into a procedure at the same time. (Reverse-linked from t635_24.)
- Builds on **t635_14** (DONE): the helpers (`effective-gates` / `has-gates-field`
  / `should-self-record`) and the inline glue this task refines. See
  `aiplans/archived/p635/p635_14_profile_gate_declaration_unification.md` and
  [[feedback_negative_control_for_structural_guards]] for the test shape.
- No blocking dependency — all prerequisites are landed; pickable immediately.

## Verification

- Unit tests for `active` (effective-set membership: task-declared, profile-default,
  opt-out `[]`, absent+no-profile, missing-profile) and `backfill-declaration`
  (backfills absent, preserves `[]`, no-op already-declared / no-defaults) —
  mirror the t635_14 gate tests; exercise the real `aitask_gate.sh` entry point.
- Render-content assertions in `tests/test_skill_render_task_workflow.sh` updated:
  the producer trigger uses `active`, Step-7 uses `backfill-declaration` (no inline
  bash block remains).
- `shellcheck` clean (SC1091 baseline only); `aitask_skill_verify.sh` OK; goldens
  + committed prerenders regenerated in the same commit.
- Confirm the `default`-profile rendered `SKILL.md`/`planning.md` shrink materially
  vs the post-t635_14 baseline (the leanness this task restores).

## Step 9 (Post-Implementation)

Standard cleanup / archival / merge per task-workflow Step 9.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t635_25** (`t635_25_leaner_gate_check_invocation.md`)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-17T15:40:40Z status=pass attempt=1 type=human
>
> Note: deferred

> **✅ gate:plan_approved** run=2026-07-19T05:26:40Z status=pass attempt=2 type=human
