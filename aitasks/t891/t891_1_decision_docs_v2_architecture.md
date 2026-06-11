---
priority: high
effort: medium
depends: [756]
issue_type: documentation
status: Implementing
labels: [ait_brainstorm, brainstom_modules, remove_support]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 10:51
updated_at: 2026-06-11 09:42
---

# t891_1 — Decision + docs: author proposal-only architecture v2, archive v1

> **⚠️ DEFERRED — gated on `depends: 756`.** Do NOT implement until the module
> redesign (t756) has landed. The plan-layer machinery this doc describes is the
> reference model for the t756 module operations; documenting it as "removed"
> before t756 is built would be wrong. **Re-verify** all section references below
> against the as-landed `brainstorm_engine_architecture.md` before editing —
> section numbers/line ranges are a 2026-06-01 snapshot and t756 will have added
> module sections.

## Context

Parent t891 makes `ait brainstorm` **proposal-only**, retiring the
implementation-plan layer. This child ratifies that decision in the design docs.
Per the user's explicit direction, do **not** rewrite the architecture doc in
place — instead author a **new v2 document** describing the proposal-only design
and **archive** the current (two-level) doc so it survives as a historical
reference (consistent with the parent theme of keeping the plan machinery as a
model). `ait brainstorm` is unshipped, so the v2 doc describes only the
current/target proposal-only state (no "previously…" prose, per the
documentation conventions in CLAUDE.md).

## Key files to modify

- **Archive (move, don't edit):**
  `git mv aidocs/brainstorming/brainstorm_engine_architecture.md
  aidocs/brainstorming/old/brainstorm_engine_architecture.md`
  (create the `old/` subdir). This preserves the v1 two-level design.
- **Author new:** `aidocs/brainstorming/brainstorm_engine_architecture_v2.md` —
  the proposal-only architecture.
- **Cross-reference:** `aidocs/brainstorming/module_decomposition_design.md` —
  add a t891 cross-ref and drop the `detail` lifecycle step (§4.6, ~line 415:
  the `n012_plan.md` detail step) and the "existing detailer/patcher templates"
  reference (§4.10, ~line 523).
- **Repoint references:** sweep `aidocs/`, `aiplans/`, `website/`, and code
  comments for links to `brainstorm_engine_architecture.md` and repoint to the
  v2 doc (or the `old/` path where the reference is specifically about the
  retired two-level design). Use:
  `grep -rn "brainstorm_engine_architecture" --include='*.md' --include='*.py' --include='*.sh' .`

## Reference for patterns (what the v2 doc drops vs v1)

The v1 doc (now in `old/`) contains these plan-layer sections to OMIT from v2
(verify against the archived file — these were lines in the pre-t756 snapshot):
- §3 node triad: v1 had three node files (metadata + proposal + **plan**); v2
  has **two** (metadata + proposal). Drop the plan file.
- §4.4 Plan Template — omit entirely.
- §7.5 Detail, §7.6 Patch, §7.7 Finalize (plan-export path) — v2 has no Detail/
  Patch ops; Finalize becomes a **proposal export** (or fast-track + aitask
  ownership; mirror t891_4's decision).
- Top-Down / Bottom-Up flow diagrams — redraw without the Detailer boxes and the
  IMPACT_FLAG → Patcher → Detailer escalation chain.
- §6 Detailer/Patcher Input Assembly, §8.4/§8.5 detailer/patcher subagent
  prompts — omit.
- Mark `plan_file`, `br_plans/`, `read_plan`, `PLANS_DIR` as no longer part of
  the model.

v2 should carry forward (unchanged): proposal nodes, dimensions, the
section-marker machinery (reworked by t873, shared with proposals), explore /
compare / synthesize ops, and the agent-crew infrastructure that remains.

## Implementation plan

1. Re-read the as-landed `brainstorm_engine_architecture.md` (t756 may have added
   module sections — those belong in v2, kept).
2. `mkdir -p aidocs/brainstorming/old` and `git mv` the v1 doc into it.
3. Write `brainstorm_engine_architecture_v2.md`: copy the surviving structure,
   drop the plan-layer sections listed above, and fold in the proposal-only
   finalize + the module operations (as landed in t756).
4. Edit `module_decomposition_design.md`: add the t891 cross-ref, drop the
   `detail` lifecycle step.
5. Repoint all cross-references found by the grep sweep.
6. Commit doc moves/edits via `./ait git` where they touch `aiplans/`; code/aidocs
   doc files use regular `git`.

## Verification

- `aidocs/brainstorming/old/brainstorm_engine_architecture.md` exists; the v2
  doc exists and contains no Detail/Patch/plan-template/detailer/patcher
  sections.
- `grep -rn "brainstorm_engine_architecture\.md" .` shows no dangling links to
  the moved path that should point at v2.
- `module_decomposition_design.md` references t891 and no longer lists a `detail`
  lifecycle step.
- Docs describe only the current proposal-only state (no version-history prose in
  the v2 body).
