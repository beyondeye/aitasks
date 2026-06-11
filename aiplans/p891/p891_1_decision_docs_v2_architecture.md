---
Task: t891_1_decision_docs_v2_architecture.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_2_ops_agents_removal.md, aitasks/t891/t891_3_schema_data_tui_cleanup.md, aitasks/t891/t891_4_finalize_proposal_export.md
Worktree: (current branch — profile 'fast')
Branch: aitask/t891_1_decision_docs_v2_architecture
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-11 09:53
---

# Plan — t891_1: proposal-only architecture v2 doc, archive v1

## Context

Parent t891 makes `ait brainstorm` **proposal-only**, retiring the
implementation-**plan** layer (the `detail`/`patch` ops, detailer/patcher
agents+templates, `br_plans/`, the `plan_file` node field, and the plan-export
path in `finalize`). This child ratifies that decision **in the design docs**:
author a NEW v2 architecture doc describing the proposal-only design and
**archive** the current two-level doc (per user direction — do not rewrite in
place). `ait brainstorm` is unshipped, so v2 describes only the current/target
state (no "previously…" prose, per CLAUDE.md documentation conventions).

### Verification findings (this plan was re-verified against the as-landed codebase)

The original child plan assumed t756 (the module redesign, now **Done/archived**)
would have woven module sections into `brainstorm_engine_architecture.md`, to be
folded into v2. **Verification disproved that premise:**

1. **t756 never touched `brainstorm_engine_architecture.md`** (last modified
   2026-05-20 by t807; `git log` confirms no t756 commit on the file). The doc
   has **zero module sections**. The plan's omit-anchors are therefore still
   accurate (the doc has not drifted).
2. **The module material lives only in `module_decomposition_design.md`**, which
   is itself **stale** — its header still says *"Status: design only — no
   implementation has landed"* even though t756 implemented it.
3. **Blast radius is tiny:** repo-wide there is exactly **one** external
   reference to the arch doc — `aidocs/framework/model_reference_locations.md:93`
   (an audit row, `informational_only`). No `website/`, no `.py`/`.sh` code refs.

### Decisions (confirmed with user)

- **v2 module scope = cross-ref only.** v2 = the existing arch doc with the plan
  layer removed, plus a brief pointer to `module_decomposition_design.md`. Do NOT
  author module architecture into v2 — that doc remains the canonical module
  reference; duplicating it here would diverge.
- **`module_decomposition_design.md` edit depth = scoped + entailed consistency.**
  Make the 3 parent-named edits PLUS the directly-entailed proposal-only fixes
  (remove `detail`/`patch` from op enumerations). Flag the stale "design only"
  status line (and the sync `plan_file` reference) as a **separate follow-up** —
  that is a t756-as-built reconciliation concern, out of scope here.

## Steps

### 1. Archive v1 (move, don't edit)
```
mkdir -p aidocs/brainstorming/old
git mv aidocs/brainstorming/brainstorm_engine_architecture.md \
       aidocs/brainstorming/old/brainstorm_engine_architecture.md
```

### 2. Author `aidocs/brainstorming/brainstorm_engine_architecture_v2.md`
Copy the surviving structure from v1 and **OMIT** the plan-layer content.
Verified anchors (current line numbers in v1, total 1863 lines):

- **§1 Core Concepts — node triad** (L29-32): three node files (metadata +
  proposal + **plan**) → **two** (metadata + proposal). Drop the plan file.
- **§2 Directory Layout / Naming** (L126, L150) + **`PLANS_DIR`** (L159): drop
  `br_plans/` and the plan-file naming/path entries.
- **§3 Flat YAML Node Schema** (L237-312): remove the `plan_file` field
  (L250) and its description (L305).
- **§4** — retitle "Structured Sections, Proposals, and Plans" → "…and
  Proposals"; remove **§4.4 Plan Template** (L431-474); renumber **§4.5
  Dimension Linking** → §4.4; update the TOC.
- **§5 AgentCrew** — drop `detail`/`patch` from Operation Groups (L502) and
  the **detailer/patcher** entries from Agent Type Definitions (L555). Keep
  explorer/comparator/synthesizer/initializer.
- **§6 Context Assembly** — remove **Detailer Input Assembly** (L823-866) and
  **Patcher Input Assembly** (L867-888).
- **§7 Orchestration** — remove **§7.5 Detail** (L1181-1260) and **§7.6 Patch**
  (L1262-1347); rework **§7.7 Finalize** (L1349-1359) into a **proposal export**
  (mirror t891_4's decision — finalize exports the proposal, no plan export);
  redraw **Top-Down vs Bottom-Up Flow Summary** (L1360-1400) without the
  Detailer boxes and the IMPACT_FLAG → Patcher → Detailer escalation chain.
- **§8 Subagent Prompts** — remove **§8.4 Detailer** (L1634-1714) and **§8.5
  Plan Patcher** (L1716-1788).
- **§9 Section Viewer** (L1792-1855): keep unchanged.
- **References + TOC**: drop plan-layer entries, renumber/relink sections.
- **Module pointer (new, brief):** add a one-line cross-ref directing readers to
  `module_decomposition_design.md` for the module-decomposition operations
  (`decompose`/`sync`/`merge`) — modules are not described in this engine doc.

**Carry forward unchanged:** proposal nodes, dimensions, the section-marker
machinery (t873, shared with proposals), explore/compare/synthesize ops, and
the agent-crew infrastructure that remains.

**Doc convention:** v2 describes only the current proposal-only state — no
"previously…" prose. The two-level history survives in `old/`.

### 3. Edit `aidocs/brainstorming/module_decomposition_design.md` (scoped + entailed)
Parent-named edits:
- **Add a t891 cross-ref** noting the plan layer (`detail`/`patch`) is retired
  and the lifecycle is proposal-only (no existing t891/891 mention — confirmed).
- **Drop the `detail` lifecycle step** — §4.6 worked example step 5 (L415):
  rework so the parser HEAD (n012) **fast-tracks directly** from the refined
  proposal (remove `detail` and `n012_plan.md`). Steps 6-9 remain coherent.
- **Drop the detailer/patcher templates note** — §4.10 (L523-525): change
  "Existing templates (explorer, comparator, synthesizer, detailer, patcher)"
  → "(explorer, comparator, synthesizer)".

Entailed proposal-only consistency (same logical edit — `detail`/`patch` are
removed ops, so enumerating them as current is now wrong):
- **§1 op-list** (L18): "(`explore`, `compare`, `synthesize`, `detail`, `patch`)"
  → "(`explore`, `compare`, `synthesize`)".
- **Lifecycle one-liner** (L190): "decompose → (existing ops refine) → detail →
  fast-track" → "decompose → (existing ops refine) → fast-track".
- **§4.5** (L384): "`explore`, `compare`, `synthesize`, `detail`, `patch` all
  currently…" → "`explore`, `compare`, `synthesize` all currently…".

**Explicitly NOT edited (flagged follow-up):** the stale L9 "Status: design only
— no implementation has landed" line and the §4.3 sync `plan_file` reference
(L330). These reflect a t756-as-built reconciliation, a different axis from the
plan-layer retirement; recorded in Final Implementation Notes for a follow-up.

### 4. Repoint the single external reference
`aidocs/framework/model_reference_locations.md:93` — repoint the path from
`brainstorm_engine_architecture.md` to `brainstorm_engine_architecture_v2.md`
(the row is about agent-type assignment rationale, which **survives** in v2's
AgentCrew section — so v2, not `old/`). Refresh the cited line numbers to the
surviving explorer/comparator/synthesizer rationale lines in v2 (best-effort;
the row is `informational_only`).

### 5. Commit
- Doc files (`aidocs/`) use regular `git`.
- The plan file (`aiplans/`) uses `./ait git`.
- Use `git mv` for the archive move so history is preserved.

## Verification

- `aidocs/brainstorming/old/brainstorm_engine_architecture.md` exists; v2 exists.
- v2 contains **no** Detail/Patch/plan-template/detailer/patcher sections and no
  `plan_file`/`br_plans`/`PLANS_DIR`/`read_plan`:
  ```
  grep -nEi 'detail|patch|plan_file|br_plans|PLANS_DIR|read_plan|Plan Template' \
    aidocs/brainstorming/brainstorm_engine_architecture_v2.md
  ```
  (expect no plan-layer hits; any "plan" left should be incidental prose, not the
  retired layer.)
- v2's TOC and internal section links are self-consistent after removals/renumber.
- `grep -rn "brainstorm_engine_architecture\.md" .` shows no dangling link to the
  moved path that should point at v2 (only the repointed
  `model_reference_locations.md` and intentional `old/` references remain).
- `module_decomposition_design.md` references t891, lists ops as
  `explore`/`compare`/`synthesize` only, and has no `detail` lifecycle step.

See **Step 9 (Post-Implementation)** of the shared workflow for archival/merge.

## Risk

### Code-health risk: low
- Pure-documentation change; no code, no `website/`, single audit-table reference
  repointed. No runtime blast radius. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Large doc transformed by hand — a stray plan-layer remnant or a broken TOC /
  internal section link could slip through. Bounded: the grep-based verification
  above catches plan-layer remnants and a TOC self-consistency check covers
  links. · severity: low · → mitigation: covered by Verification step (no
  separate task)
