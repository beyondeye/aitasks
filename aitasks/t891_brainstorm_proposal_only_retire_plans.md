---
priority: high
effort: high
depends: [756]
issue_type: enhancement
status: Ready
labels: [ait_brainstorm, brainstom_modules, remove_support]
children_to_implement: [t891_1, t891_2, t891_3, t891_4, t891_5]
created_at: 2026-06-01 09:19
updated_at: 2026-06-01 11:49
boardidx: 10
---

# Retire plans — make `ait brainstorm` proposal-only; port plan value into the module architecture

## Goal

Simplify `ait brainstorm` to a **single-level (proposal-only)** design engine.
Retire the implementation-**plan** layer — the `detail` and `patch` operations,
the `detailer`/`patcher` agents and templates, the `br_plans/` store, the
`plan_file` node field, and the plan-export path in `finalize` — and absorb
everything useful about plans into the **module** architecture being built in
t756 (design: `aidocs/brainstorming/module_decomposition_design.md`).

Premise (user): *detailed implementation plans belong to the implementation
phase, not the brainstorm phase. In practice proposals are good enough during
brainstorm, and a detailed plan is rebuilt anyway at `/aitask-pick` time.*

This task is framed as a **sibling/companion to t756**. The deliverable of this
parent is the decision + a child decomposition + the retired-feature → module
mapping below; it is **a brainstorm-design exploration** of which ideas from the
retired plan machinery should improve the module design.

> **⚠️ REVISED SEQUENCING (2026-06-01): t891 retirement is DEFERRED until after
> t756 (module redesign) lands.** The earlier framing put t891 *upstream* of
> t756 (shrinking it). That is reversed: the existing plan-specific machinery
> (`detail`/`patch` wizard flows, the detailer/patcher agents, the
> poll/auto-apply infra, the impact-analysis escalation) is the **working
> reference model** for the new module operations t756 must build
> (`module_decompose`, `module_sync`, their wizards, the syncer's bottom-up
> reconciliation). Retiring it first would delete that model. The four children
> below are fully detailed now but **gated on `depends: 756`**; each child
> re-verifies its code anchors against the as-landed codebase at execution time.
> `ait brainstorm` is unshipped, so **no back-compat / migration** is needed.
> See the Sequencing section.

## Motivation / analysis (why plans give reduced benefit once modules land)

Today brainstorm is a **two-level** model bolted onto *one session = one task =
one plan*:
- Level 1 = proposal (architecture: dimensions + proposal markdown)
- Level 2 = plan (`detail` produces it; `patch` edits it bottom-up with impact
  analysis)
- `finalize_session()` exports **the plan** to `aiplans/p<N>_<head>.md` as the
  handoff (requires `plan_file`, else `ValueError`).

The modules lifecycle relocates where the implementation plan lives:

```
module_decompose → refine proposal → (detail) → fast-track to aitask
  → IMPLEMENTATION → module_sync → module_merge
```

Two things at fast-track gut the plan's role:
1. **Each module fast-tracks into its own aitask** (`module_decompose
   --link-to-task` → `aitask_create.sh --batch`). That aitask runs `/aitask-pick`,
   whose Step 6 (`task-workflow/planning.md`) builds a detailed plan against the
   **live** codebase at implementation time — fresher than any brainstorm-time
   `detail` plan. `br_plans/` is redundant *going down*.
2. **`module_sync` reads the plan back from the aitask, not `br_plans/`** (design
   doc §4.3): it consumes the linked task's `aiplans/p<parent>_<child>.md`
   (esp. `## Final Implementation Notes` / `## Post-Review Changes`), the scoped
   git diff, and `aitask_explain_context.sh` output. The canonical evolving plan
   is the **aitask's**. `br_plans/` is bypassed *going up*.

So the brainstorm second level is sandwiched out from both sides. The
proposal↔plan bidirectional reconciliation that `detail`/`patch` provide *within*
brainstorm becomes the proposal↔aitask reconciliation that fast-track/`module_sync`
provide *across* the brainstorm/implementation boundary — built on **observed
implementation reality** instead of hypothetical plan edits.

## Retired-feature → module mapping (port what is useful)

| Today's plan capability | Ports to (modules world) | Net effect |
|---|---|---|
| `detail` — codebase-grounded implementation steps | `/aitask-pick` Step 6 (live codebase) + fast-track seeding the aitask description from the module **proposal slice** (components/assumptions/tradeoffs) | No loss; better timing |
| `patch` + bottom-up impact analysis (IMPACT_FLAG → re-explore) | **`module_sync`** — observes what actually got built and reconciles into the proposal; "escalate to explorer" → "sync emits a new proposal node → optionally merge/re-explore" | Strictly better: real reality |
| plan as `finalize` handoff | fast-track creates the aitask; the aitask owns its plan; `module_sync` reads it back | Ported |
| section-targeted re-detailing | section machinery is shared with proposals | No loss |

**Genuine losses (accepted, aligned with the premise):**
- Pure-design implementation tweaking without implementing (`patch`). The design
  doc already says `module_sync` runs only when implementation happened; a
  design-only module skips it. This is exactly what the premise wants gone.
- Warm-start seed for the fast-tracked aitask plan — mitigated/improved by handing
  aitask-pick the module **proposal** (dimensions are a better spec than a stale
  plan).

## Sequencing (binding)

- **DOWNSTREAM of t756; gated on `depends: 756`.** Retirement runs only *after*
  the module redesign lands. Rationale: the plan-specific machinery
  (`detail`/`patch`, detailer/patcher agents, plan wizard flows, impact-analysis
  escalation) is the **reference model** for the module operations t756 builds.
  Build the module ops from that model first, then retire the plan layer here.
- **t873 has landed** (archived). It reworked the section-marker / dimension-link
  machinery that is **shared with proposals** — removal children must preserve it
  and touch only the plan-specific consumers.
- **Re-verify** each child's code anchors against the as-landed codebase before
  implementing: the anchors recorded in the child plans are a 2026-06-01
  pre-modules snapshot and will drift once t756 lands.
- Cross-links recorded as part of this decomposition: `t756`'s description and
  `aiplans/p756_brainstorm_modules.md` reference this task with the reversed
  (model + defer) framing; `module_decomposition_design.md` gets a t891 cross-ref
  (deferred to child t891_1).
- **No back-compat / migration:** `ait brainstorm` is not a shipped feature, so
  `plan_file` nodes and `br_plans/` stores are removed outright.

## Child decomposition (created — gated on `depends: 756`; full plans in `aiplans/p891/`)

1. **Decision + docs**: ratify proposal-only by authoring a **new v2 doc**
   `aidocs/brainstorming/brainstorm_engine_architecture_v2.md` (proposal-only
   architecture) and **archiving** the current
   `aidocs/brainstorming/brainstorm_engine_architecture.md` to
   `aidocs/brainstorming/old/` (preserve the two-level design as a reference, not
   an in-place rewrite). Repoint cross-references. Add a t891 cross-ref to the
   module design doc and drop its `detail` lifecycle step.
2. **Ops/agents removal**: retire `detail`/`patch` from `GROUP_OPERATIONS`,
   `BRAINSTORM_AGENT_TYPES`, `_DESIGN_OPS`, `_WIZARD_OP_TO_AGENT_TYPE`,
   `_NODE_SELECT_OPS`, `_OPERATION_HELP`, `_execute_design_op`; remove
   `register_detailer`/`register_patcher`, `_assemble_input_detailer/patcher`,
   `apply_detailer_output`/`apply_patcher_output` + `aitask_brainstorm_apply_detailer.sh`/
   `_apply_patcher.sh` + `templates/detailer.md`/`patcher.md` + the TUI poll/auto-apply
   infra (`_poll_detailers`/`_poll_patchers` etc.).
3. **Schema/data + TUI cleanup**: `plan_file` out of `NODE_OPTIONAL_FIELDS`,
   remove `read_plan`/`PLANS_DIR`/`br_plans/`; NodeDetailModal Plan tab, `l`/`V`
   plan bindings, plan badges (`brainstorm_dag_display.py`), patch wizard step +
   `_node_has_plan` gating.
4. **Finalize replacement**: replace `finalize_session()` plan-export with a
   proposal export (or rely on fast-track + aitask ownership). No migration —
   `plan_file` nodes and `br_plans/` are removed outright (unshipped feature).

## Obsoleted by this task
- `t744_manual_verification_brainstorm_apply_patcher_output_followup` and
  `t811_manual_verification_brainstorm_reconcile_patcher_into_apply_` —
  **already removed** (not present in active or archived dirs as of 2026-06-01).
  No close/retire action required.

## Key references
- `aidocs/brainstorming/brainstorm_engine_architecture.md` — §3 node triad,
  §4.4 plan template, §7.5–7.7 detail/patch/finalize, Top-Down/Bottom-Up flow.
- `aidocs/brainstorming/module_decomposition_design.md` — §4.3 `sync` inputs,
  §4.6 lifecycle, §4.10 templates.
- `aiplans/p756_brainstorm_modules.md` — t756 decomposition + t873 sequencing.
- Code anchors: `brainstorm_schemas.py` (`GROUP_OPERATIONS`, `NODE_OPTIONAL_FIELDS`),
  `brainstorm_crew.py` (`register_detailer`/`register_patcher`,
  `_assemble_input_detailer/patcher`), `brainstorm_session.py`
  (`finalize_session`, `apply_detailer_output`, `apply_patcher_output`),
  `brainstorm_dag.py` (`read_plan`, `PLANS_DIR`), `brainstorm_app.py`
  (NodeDetailModal Plan tab, `_node_has_plan`, patch wizard gating,
  detailer/patcher poll loops), `brainstorm_dag_display.py` (plan badges).

## Verification (of this decomposition task, once executed)
- Decision recorded in the architecture doc; `p756` + module design doc reference
  this task.
- Children created for the four areas above (re-verified against t873), each with
  full per-child context; `aiplans/p<this>/` holds a plan per child.
- No `.aitask-scripts/brainstorm/` source modified by this parent — removal is
  deferred to children.
