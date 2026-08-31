---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [shadow, concern_format, documentation]
anchor: 1636
created_at: 2026-08-30 19:53
updated_at: 2026-08-31 16:41
---

## Context

Part of t1636 (shadow concern impact-vector model). The parent decomposition
gave website documentation to **t1636_3 only**, scoped to two paragraphs of
`website/content/docs/workflows/shadow-agent.md` (the findings description and
the concern-block description). Those landed with t1636_3.

Nothing covers the user-facing surface the remaining implementation child
changes:

- **t1636_4** ships the picker's per-row **trade profile**
  (`▲robus ▼simpl E:lo`) and explicit forward / spinoff / reject **decision
  guidance**. Neither its task file nor its plan mentions documentation, and
  **four** user-facing pages describe that picker today.
The delta-scoped auto-recheck work (formerly t1636_5) was **parked as the
standalone task t1650 on 2026-08-31** and is no longer part of this model's
delivery. Its documentation is out of scope here and travels with t1650 — the
recheck-loop prose on the website stays accurate as it is, and this task must
not pre-document a loop that does not exist yet.

This task is the dedicated website-docs child for the whole model, so the
documentation is written once against the settled surface rather than
accumulated in fragments across implementation children.

**Scope is user-facing website docs only.** The framework-internal reference
`aidocs/framework/shadow_agent.md` is not this task's either — it travels with
t1650, which already lists it.

## Key Files to Modify

- `website/content/docs/workflows/shadow-agent.md` — the primary page.
  - Leave the **"Reject a concern so it does not come back"** section alone: its
    "Every review round re-derives the shadow's findings from scratch" opening
    is still accurate, and only t1650 will make it untrue.
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
