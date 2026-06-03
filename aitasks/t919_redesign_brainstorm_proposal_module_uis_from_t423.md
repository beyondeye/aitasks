---
priority: medium
effort: high
depends: [756, 891]
issue_type: feature
status: Ready
labels: [brainstorming, tui, ait_brainstorm, brainstom_modules]
created_at: 2026-06-03 09:30
updated_at: 2026-06-03 09:30
---

Redesign and port **all** salvageable UI/library ideas from the now-obsolete
t423 ("design and finalize the brainstorm TUI") into the **proposal-only +
modules** world that lands with t756 (module operations) and t891 (retire
plans, make `ait brainstorm` proposal-only).

This is a **regular implementation task** (run via `/aitask-pick`, which builds
its detailed plan against the as-landed codebase at pick time) — NOT something
run through `ait brainstorm`.

> **GATED:** `depends: [756, 891]`. Do not start until both land. The plan layer
> (`detail`/`patch`, detailer/patcher agents, `br_plans/`, `plan_file`) that
> t423's remaining children targeted is being **removed** by t891 and its
> bottom-up reconciliation is being **ported into `module_sync`** by t756.
> Re-verify every code anchor below against the as-landed (post-756/891)
> codebase before implementing — anchors here are a 2026-06-03 snapshot and will
> drift.

## Why t423 needs a redesign (not a resume)

t423 was decomposed into 11 children. **t423_1–t423_7 are already built and
archived** — the TUI scaffold, dashboard, DAG visualization, node-detail modal,
**compare tab**, actions wizard, and status/crew-monitoring tab. The brainstorm
TUI substantially exists.

Only **t423_8, t423_9, t423_10, t423_11** remained unbuilt, and every one of
them is tied to the **plan layer being retired by t891**:

- t423_8 — diffviewer parameterization (CLI args + return files) so the
  diffviewer can be launched to compare/merge **alternative implementation
  plans**.
- t423_9 — bottom-up flow: edit plan → structured diff → **Patcher** impact
  analysis → **Explorer** escalation.
- t423_10 — in-TUI plan viewer/editor with section annotations → **Patcher**
  patch request.
- t423_11 — interactive planning mode: suspend TUI, run **Detailer** agent in
  the terminal to refine a **plan**.

Since plans, the detailer, and the patcher all go away, these four cannot be
resumed as written. But their **underlying UIs and libraries are valuable** and
their **UX patterns** port cleanly to proposals/modules. That port is this task.

## Reusable assets (keep the engines, re-scope from plans → proposals/modules)

The diffviewer (`.aitask-scripts/diffviewer/`) is flagged transitional in
CLAUDE.md ("will be integrated into the brainstorm TUI later"). Its **engine/UI
layer is plan-agnostic and reusable**; only its loader/browser glue is
plan-specific. Reuse:

- `diff_engine.py` — `compute_multi_diff()`, `compute_classical_diff()`,
  `compute_structural_diff()`, `DiffHunk`, `PairwiseDiff`, `MultiDiffResult`.
- `merge_engine.py` — `MergeSession`, `apply_merge()`, `apply_merge_annotated()`,
  `compute_hunk_preview_range()`, `suggest_filename()`/`suggest_directory()`.
- `diff_display.py` — scrollable diff widget with per-line tracking (851 LOC).
- `md_parser.py` — `parse_sections()` / `normalize_section()` for
  section-level navigation (proposals are section-structured markdown too).
- `diff_viewer_screen.py`, `merge_screen.py` — the diff/merge Textual screens.

**Re-scope (currently plan-specific):** `plan_browser.py`, `plan_loader.py`,
`plan_manager_screen.py` load from `aiplans/`. Their proposal equivalent reads
brainstorm **proposal** markdown: `br_proposals/<node_id>.md`, via
`brainstorm_dag.py::read_proposal()` (`PROPOSALS_DIR = "br_proposals"`).

## Idea-by-idea port map (redesign ALL key t423 ideas)

### Parent t423 intent — design-by-alternatives, diffviewer integrated not embedded
Original intent: finalize each brainstorm-TUI component by presenting 2–3
alternatives, letting the user choose, and combining into a plan; and refactor
the diffviewer for **integration** rather than direct inclusion. **Port:** keep
the "diffviewer as a refactored, parameterized component the brainstorm TUI
*launches*" stance; apply it to the proposal/module surfaces below.

### From t423_8 — parameterize the diff/merge component for proposals
Add CLI/programmatic entry so the diff+merge component can be launched from the
brainstorm TUI against **proposal** files (and module proposal slices) instead
of plans: skip the browser when inputs are supplied, accept `--main`/`--other`,
return modified paths + structured diff (JSON hunks) to the caller. This is the
enabling primitive for everything below.

### From t423_9 — bottom-up reconciliation review UI (reframed onto module_sync)
The patcher/explorer bottom-up loop is gone; **`module_sync`** (t756) is the new
bottom-up path — it observes what was actually implemented in a module's linked
aitask (its `aiplans/p<parent>_<child>.md`, scoped git diff,
`aitask_explain_context.sh` output) and reconciles it into the proposal.
**Port:** use `diff_display` + `merge_engine` as the **review/accept UI for the
sync delta** — let the user visually diff "current proposal" vs "sync-proposed
proposal" and selectively accept hunks before they land, instead of feeding a
patcher. (Verify `module_sync`'s actual output shape once t756 lands.)

### From t423_10 — proposal annotation/section-edit UI (reframed off patcher)
Port the in-TUI section viewer + annotation UX to **proposals**: view a node's
proposal with section navigation (`md_parser.parse_sections`), annotate sections
with change instructions, accumulate them. Submit target changes from
`Patcher` → the **surviving proposal-level design ops** (`explore` / `compare` /
`synthesize`), or directly into a `module_sync`-style reconcile. Reuse
`diff_display`'s margin-marker/line-tracking machinery for annotation markers.

### From t423_11 — interactive proposal refinement (reframed off detailer)
The suspend→agent→resume pattern (`App.suspend()` → run a code agent in the
terminal → resume and read back output) is **agent-agnostic**. Port it to
interactive **proposal** refinement: suspend the brainstorm TUI, run the
agent against the node's `br_proposals/<id>.md`, write the refined proposal
back, optionally trigger a reconcile. Replaces the retired Detailer flow with a
proposal-phase interactive refiner.

### Relationship to the existing (built) Compare tab
t423_5 already shipped a **dimension-matrix** compare tab (structured DataTable
over requirements/assumptions/components/tradeoffs). The diffviewer port adds the
complementary **textual/section-level** diff+merge of two proposal variants.
During planning, decide the seam between them (e.g. matrix for structured
dimension comparison, diff/merge for prose reconciliation) and avoid duplicating
selection UX.

## Open design directions for pick-time planning

- Where does proposal A/B diff+merge surface — a new Actions-wizard op, a
  Compare-tab mode, or a launched component? (Honor the "launch, don't embed"
  stance from t423's parent.)
- Does `module_sync` (t756) already emit a reviewable delta, or does this task
  add the review UI on top? Confirm against the landed `module_sync`.
- 3-way merge for `module_merge` (umbrella proposal vs module proposal vs
  as-implemented): is `merge_engine` (currently pairwise/multi) sufficient, or
  does it need a 3-way mode?
- Module status badges (t756 Phase D) — do any of these UIs need to read/show
  per-module status?

## Sequencing & re-verification
- Start only after **t756** and **t891** land. Re-verify all anchors against the
  post-retirement codebase (the plan-layer references above will be gone; the
  proposal/`module_*` surfaces are the targets).
- `ait brainstorm` is unshipped — no back-compat / migration concerns.

## Cleanup of t423 (do this as the FINAL step of THIS task, after the redesign lands)
Once the redesign is implemented, remove the superseded t423 source (its ideas
now live here):
- `./ait git rm aitasks/t423_design_and_finalize_brainstorm_tui.md`
- `./ait git rm aitasks/t423/t423_8_*.md aitasks/t423/t423_9_*.md aitasks/t423/t423_10_*.md aitasks/t423/t423_11_*.md`
- `./ait git rm aiplans/p423/p423_8_*.md aiplans/p423/p423_9_*.md aiplans/p423/p423_10_*.md aiplans/p423/p423_11_*.md`
- Leave the **archived** t423_1–t423_7 tasks and `aiplans/archived/p423/` untouched
  (they are completed, already-built history).
- Before removing, re-check that no other active task gained a `depends` on t423
  in the meantime.
