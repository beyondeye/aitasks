---
Task: t891_brainstorm_proposal_only_retire_plans.md
Worktree: (none — current branch, fast profile)
Branch: main
Base branch: main
---

# t891 — Retire plans: make `ait brainstorm` proposal-only (DECOMPOSITION + DEFER)

## Context

`ait brainstorm` is a two-level engine: proposal (Level 1) + implementation
**plan** (Level 2 — the `detail` op produces it, `patch` edits it bottom-up with
impact analysis, `finalize` exports it to `aiplans/`). The agreed end-state is
**proposal-only**: detailed implementation plans belong to the implementation
phase, and once the **modules** architecture (t756) lands, the plan layer is
bypassed (each module fast-tracks into its own aitask; `module_sync` reads that
aitask's plan back).

**Revised sequencing decision (this session).** The earlier framing had t891
*upstream* of t756 (shrinking it). We are **reversing** that: the existing
plan-specific machinery — the `detail`/`patch` wizard flows, the
detailer/patcher agents, the poll/auto-apply infra, the impact-analysis
escalation — is the **working reference model** for the *new* module operations
t756 must build (`module_decompose`, `module_sync`, their wizards, the
syncer's bottom-up reconciliation). Retiring it before t756 is built would
delete that model. Therefore:

> **t891's actual retirement work is DEFERRED until after t756 (module
> redesign) lands.** We fully decompose and detail it now, gate every child
> behind `depends: 756`, and add cross-links so the module work knows to use
> the plan machinery as its template and to trigger t891 on completion.

This parent **modifies no `.aitask-scripts/brainstorm/` source.** Its deliverable
is: the reversed-sequencing record, a fully-detailed child decomposition gated on
t756, and the cross-links into the module-redesign task/plan.

## Re-verification against current state

- **t873 is archived/landed.** It reworked the **section-marker / dimension-link**
  machinery (`<!-- section: name [dimensions: KEY*] -->` glob expansion, badge
  counts, compare-wizard scoping, section scroll). **Shared with proposals — must
  be preserved**; removal touches only plan-specific consumers.
- **p756 already references t891** (lines 39–58) but frames it as an *upstream*
  decision that *shrinks* t756. That framing is now **inverted** and must be
  corrected (see edits below).
- **`module_decomposition_design.md` does not reference t891**; it still shows a
  `detail` lifecycle step (§4.6) and "existing detailer/patcher templates"
  (§4.10), and confirms `module_sync` reads the plan from the linked aitask, not
  `br_plans/` (§4.3).
- **t744 / t811 (the "obsoleted" manual-verification tasks) no longer exist** —
  already removed. No close/retire action; children just note this.
- **Code anchors captured below are a 2026-06-01 pre-modules snapshot and WILL
  drift once t756 lands.** Every child plan instructs the implementer to
  re-verify anchors against the as-landed codebase; child plans describe removals
  by symbol/op name, not line number.

## Parent deliverable A — cross-links + reversed-sequencing record (done now)

1. **Edit t891's own description** (`aitasks/t891_*.md`): replace the "upstream
   of t756 / shrinks t756" Sequencing framing with the reversed decision —
   deferred until t756 lands, plan machinery preserved as the module-ops
   reference model, children gated on 756.
2. **Edit t756's description** (`aitasks/t756_brainstorm_modules.md`): append a
   short link block — "The plan-layer machinery (`detail`/`patch`,
   detailer/patcher agents, plan wizard flows, impact-analysis escalation) is the
   reference model for the new module operations; build module ops from it, then
   retire the plan layer via **t891** *after this lands*." Note that t756's own
   children (when decomposed) should carry the same reference.
3. **Edit p756** (`aiplans/p756_brainstorm_modules.md` lines 39–58): flip the
   t891 section from "upstream/shrinks" to "downstream/uses-as-model; retire after
   t756 lands." (Internal plan file — recording the deviation is allowed.)
4. **Set parent t891 `depends: [756]`** to document the gate.

All edits are aitask/plan files (`./ait git`), not brainstorm source.

## Parent deliverable B — child decomposition (created now, gated on t756)

Children auto-depend on the previous sibling; **t891_1 gets `--deps 756`** so the
whole chain `756 → 891_1 → 891_2 → 891_3 → 891_4` is gated. Each child plan opens
with a **DEFER + RE-VERIFY** banner and notes that by execution time the module
equivalents already exist, so retirement is pure removal (the "port to
module_sync" already happened inside t756).

### t891_1 — Decision + docs (documentation)
**Author a NEW v2 doc; archive (don't rewrite) the current one.**
- `git mv aidocs/brainstorming/brainstorm_engine_architecture.md
  aidocs/brainstorming/old/brainstorm_engine_architecture.md` — preserves the v1
  two-level (proposal + plan) design as a historical reference, consistent with
  keeping the plan machinery as a model.
- Write `aidocs/brainstorming/brainstorm_engine_architecture_v2.md` — the
  proposal-only architecture: two-file node (metadata + proposal, no plan),
  no Detail/Patch/Finalize-plan-export, no Detailer/Patcher agents, redrawn
  Top-Down/Bottom-Up flow, proposal-only finalize. The v2 doc describes only the
  current (proposal-only) state per the doc convention; the retired internals
  stay documented only in the archived v1.
- Repoint cross-references that target the old filename (sweep `aidocs/`,
  `aiplans/`, `website/`, code comments) to the v2 doc or the `old/` path as
  appropriate.
- Add the t891 cross-ref to `module_decomposition_design.md` and drop its
  `detail` lifecycle step. Docs-only.

### t891_2 — Ops/agents removal (refactor)
Remove `detail`/`patch` ops and detailer/patcher agents:
`GROUP_OPERATIONS` (schemas); `_NODE_SELECT_OPS`/`_WIZARD_OP_TO_AGENT_TYPE`/
`_DESIGN_OPS`/`_OPERATION_HELP` + the `detail`/`patch` branches of
`_execute_design_op` + poll/auto-apply infra (`_ensure/_stop/_poll/_try_apply`
×{detailer,patcher}, `_scan_existing_detailers`, timer/source/target state) in
`brainstorm_app.py`; `register_detailer`/`register_patcher`,
`_assemble_input_detailer`/`_patcher`, agent-type keys in `brainstorm_crew.py`;
`apply_detailer_output`/`apply_patcher_output` + helpers/delimiters in
`brainstorm_session.py`. Delete `aitask_brainstorm_apply_detailer.sh`,
`aitask_brainstorm_apply_patcher.sh`, `templates/detailer.md`,
`templates/patcher.md`. **Preserve** shared section/dimension machinery and the
`compare` read path.

### t891_3 — Schema/data + TUI cleanup (refactor)
Remove `plan_file` from `NODE_OPTIONAL_FIELDS`; remove `read_plan`/`PLANS_DIR`
(`br_plans`) in `brainstorm_dag.py`; remove the `NodeDetailModal` Plan tab +
`read_plan` call, `_node_has_plan`, patch-wizard gating, `l`/`V` plan bindings in
`brainstorm_app.py`; remove plan badges (●/○), `view_plan` binding,
`PlanRequested`, `action_view_plan` in `brainstorm_dag_display.py`.

### t891_4 — Finalize replacement (refactor)
Replace `finalize_session`'s plan-export path (retrieve `plan_file` → ValueError
if missing → copy `br_plans/<head>.md` → `aiplans/p<N>_<head>.md`) with a
proposal export (or rely on fast-track + aitask ownership).
**No migration / back-compat:** `ait brainstorm` is not a shipped feature, so
`plan_file`-bearing nodes and `br_plans/` stores can be removed outright — no
tolerate-legacy path, no load-time shims, no data migration anywhere across the
four children.

## Manual-verification sibling
After the 4 children, offer an aggregate manual-verification sibling (children
2/3/4 produce TUI behavior). It is gated by the same chain; seed from each
child's `## Verification` section via `aitask_create_manual_verification.sh`.

## Parent mechanics (after approval)
1. Edit t891 / t756 descriptions + p756 (deliverable A); set t891 `depends:756`.
2. Create 4 children (`aitask_create.sh --batch --parent 891 ...`, full per-child
   context); add `--deps 756` to the first child.
3. Write `aiplans/p891/p891_<n>_<name>.md` per child (DEFER+RE-VERIFY banner).
4. Revert parent t891 → Ready, clear `assigned_to`, release parent lock.
5. Commit task files + plans + the cross-link edits via `./ait git`.
6. Offer the manual-verification sibling.
7. Child checkpoint (interactive): "Stop here" (expected — children are deferred)
   or "Start first child".

## Verification (of this decomposition)
- `./.aitask-scripts/aitask_ls.sh -v --children 891 99` lists 4 children; each
  carries the t756 gate (chain via `--deps 756` + sibling auto-deps).
- `aiplans/p891/` holds a plan per child, each with the DEFER+RE-VERIFY banner.
- t756 description + p756 reference t891 with the reversed (model + defer)
  framing; t891 description records the reversed sequencing.
- `git status` shows only `aitasks/` + `aiplans/` changes — no
  `.aitask-scripts/brainstorm/` source modified by the parent.
