---
priority: medium
effort: medium
depends: [t1636_5]
issue_type: documentation
status: Ready
labels: [shadow, concern_format, documentation]
anchor: 1636
created_at: 2026-08-30 19:53
updated_at: 2026-08-30 19:53
---

## Context

Part of t1636 (shadow concern impact-vector model). The parent decomposition
gave website documentation to **t1636_3 only**, scoped to two paragraphs of
`website/content/docs/workflows/shadow-agent.md` (the findings description and
the concern-block description). Those landed with t1636_3.

Nothing covers the user-facing surface the two remaining implementation
children change:

- **t1636_4** ships the picker's per-row **trade profile**
  (`▲robus ▼simpl E:lo`) and explicit forward / spinoff / reject **decision
  guidance**. Neither its task file nor its plan mentions documentation, and
  **four** user-facing pages describe that picker today.
- **t1636_5** makes auto-recheck rounds **delta-scoped**. Its plan hedges with
  "website shadow-agent.md *if* it describes the recheck loop" — it does, and
  the current prose states the opposite of what t1636_5 makes true.

This task is the dedicated website-docs child for the whole model, so the
documentation is written once against the settled surface rather than
accumulated in fragments across implementation children.

**Scope is user-facing website docs only.** The framework-internal reference
`aidocs/framework/shadow_agent.md` stays with t1636_5, which already lists it.

## Key Files to Modify

- `website/content/docs/workflows/shadow-agent.md` — the primary page.
  - The **"Reject a concern so it does not come back"** section currently opens
    "Every review round re-derives the shadow's findings from scratch, so a
    concern you have looked at and decided against would otherwise reappear
    each time." t1636_5 makes that **untrue**; rewrite it to describe the
    delta-scoped loop and what a later round actually re-reports.
  - The impact-vector and disposition prose added by t1636_3 (the findings
    paragraph and the "Forward concerns to the followed agent" paragraph) is
    the current-state baseline — extend it for the picker rendering, do not
    duplicate it.
- `website/content/docs/tuis/minimonitor/how-to.md` — "How to pick shadow
  concerns".
- `website/content/docs/tuis/monitor/how-to.md` — "How to Pick Shadow
  Concerns".
- `website/content/docs/tuis/minimonitor/_index.md` — the picker description.

Verify this file list against the tree at implementation time (it was derived
by `grep -rln "concern picker\|shadow concern"` over `website/content/docs/`);
t1636_4 may add or rename a surface.

## What to Document

1. **The impact vector as a user-facing concept** — a concern is a proposed
   delta in a shared quality space, not a bare demand. The closed dimension
   vocabulary, that the **dimensions** are what to act on while magnitudes only
   refine them, and that **effort is separate** from the quality delta.
2. **Why the worsen side is mandatory** — the anti-overengineering mechanism.
   A concern that costs nothing still says `nothing` explicitly, and one that
   improves only non-obligated dimensions at a simplicity cost self-identifies
   as a bad trade. This is the single most important idea for a user to grasp;
   it is what lets them reject a well-argued but bad suggestion.
3. **The trade profile in the picker** (t1636_4) — how to read
   `▲robus ▼simpl E:lo`, and the decision guidance: forward = obligation
   dimensions or pure-win + low effort; spinoff = net-positive but
   non-obligated, or effort ≥ medium; reject = worsens ≥ improves.
4. **Plan reviews now carry a disposition** — a user-visible behavior change
   already shipped in t1636_3: plan concerns marked `informational` land in the
   picker's dimmed section instead of every plan concern appearing under
   "Needs addressing".
5. **Delta-scoped recheck** (t1636_5) — what a later round re-reports, and how
   that differs from the full re-derivation the docs describe today.

## Constraints

- **Current-state prose only** — no version history, no "as of t1636_N", no
  "previously the shadow…". See
  `aidocs/framework/documentation_conventions.md`.
- Do **not** name the supported coding agents in the prose; genericize per the
  same document.
- Do **not** restate the format grammar as a spec. The authority is
  `.claude/skills/aitask-shadow/concern-format.md` (and
  `.aitask-scripts/monitor/concern_dimensions.py` for the vocabulary). The
  website explains what the user sees and how to decide with it.
- Any dimension list quoted here must match `CONCERN_DIMENSIONS` in
  `concern_dimensions.py`; that module and `concern-format.md` are already held
  in lockstep by `tests/test_concern_dimensions.py`, and this page must not
  become a third, unguarded copy. Prefer describing the axes over pasting the
  table.
- Glyph choices (`▲` / `▼`) are t1636_4's to make. Document whatever it
  actually renders — read the code, not this task's illustration.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- `python -m pytest tests/test_shadow_disposition_surfaces.py` — the website
  page is an anchored SITE and a whole-file swept surface in that guard, so a
  disposition enumeration that loses `informational` fails the build.
- Re-read each edited page end-to-end for stale claims the t1636 children made
  untrue — the recheck-loop sentence is the known one, but the sweep is the
  point, not that single fix.
