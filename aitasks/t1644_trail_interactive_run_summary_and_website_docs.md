---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [skills, documentation, artifacts, web_site]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
created_at: 2026-08-31 09:48
updated_at: 2026-08-31 09:55
---

## Problem

Implementation trails have two entry points, but only one of them is treated as
real in the product surface.

**The board path is documented.** `website/content/docs/tuis/board/reference.md`
(§By-Trail) and `how-to.md` describe the By-Trail view at length — wave columns,
classification glyphs, confidence, drift markers, the summary pane, the depth
label, the five refresh keys.

**The direct-invocation path is not.** A user can ask the code agent "create an
implementation trail for X" and the `/aitask-trail` skill runs the whole
create flow. Yet:

- There is **no `website/content/docs/skills/aitask-trail.md`**. Every one of the
  other 28 skills has a page under `docs/skills/`; `aitask-trail` has none.
- `docs/skills/_index.md` has **no row for it** in any of its category tables
  (`grep -i trail` over that file returns nothing).
- The only mention of the skill anywhere in the docs is one sentence inside the
  board reference: "Trails are created and re-authored by the `/aitask-trail`
  skill — on the board, focus a task in any other view and press `T` to start
  one." That frames the skill as a board affordance, not as a standalone
  workflow.

**And the interactive run ends thin.** The skill does already print a run summary
— `## Run summary print` in `.claude/skills/aitask-trail/SKILL.md.j2:675`, fired
by create (Step 2e.5), refresh (Step 3.7) and show (Step 1.4). But it is
deliberately just **two lines**:

1. the authoring depth (`lite` / `deep` / `unrecorded`), and
2. `narrative.overview`, falling back to `narrative.recommendation_summary`,
   whitespace-stripped — resolved exactly as the board's
   `trail_summary_text()` (`.aitask-scripts/board/aitask_board.py:1055`) does,
   so the two surfaces stay identical.

The section's own rationale is "so the user can decide what to pick next
**without opening the board**". As a consequence the print carries **none** of
the structure the agent just authored and the board renders:

- no wave / phase breakdown (`W<ordinal> · <title>`, purpose, why_now),
- no per-entry implementation order (`position`, task ref, classification,
  confidence),
- no dependency relations (`hard_depends` / `advisory_precedes`),
- and **no pointer telling the user the trail is viewable in `ait board`**
  (press `z` for By-Trail, `s` to choose the trail).

So someone who invoked the skill conversationally gets a prose blurb, is never
told the artifact has a rich board view, and has no way to learn either fact
from the website.

## Goal

Close both halves of the gap:

1. **Enrich the end-of-run summary for the interactive create/refresh flows** so
   it shows the phase (wave) structure, the implementation order, the dependency
   relations, and a closing note that the trail can also be viewed in
   `ait board` (By-Trail, `z` / `s`).
2. **Document the standalone `/aitask-trail` workflow on the website** — a
   `docs/skills/aitask-trail.md` page plus its row in `docs/skills/_index.md`,
   and cross-links between it and the board By-Trail reference.

## Constraints and design notes

These came out of the exploration and should be respected (or deliberately
overridden with a stated reason) during planning:

- **Scope the enrichment to the interactive path.** `## Run summary print` is
  shared by all three flows and every profile. `--show` is strictly read-only
  and headless profiles must never write (both are hard invariants in the skill
  Overview). Decide explicitly whether the richer print also applies to `--show`
  (it is arguably the flow that benefits most) and to headless runs, rather than
  letting it leak in by editing one shared section.
- **Do not break the `trail_summary_text()` parity pin.** The existing two-line
  print is pinned to the board resolver's field order and stripping: "the two
  surfaces read the same field on the same artifact, so they must render it
  identically; do not print the raw value, and do not reorder the fallback." The
  new structural lines must be **added around** that pinned line, not folded
  into it. Check whether any golden or test asserts the current two-line shape
  before changing it.
- **Anti-fabrication still applies.** No time estimates, no progress claims, no
  commitments; the printed structure must be read back from the authored trail
  JSON, not re-derived or embellished.
- **Lite vs deep.** At `depth: "lite"` the validator rejects `relations`,
  `observations`, `exclusions` and per-entry `evidence_refs` (rule
  `lite_shape`). A lite trail therefore has **no** `relations` to print — the
  dependency section must degrade honestly (say the depth carries none) rather
  than render an empty heading or imply there are no dependencies.
- **Board parity, not board duplication.** The board renders classification
  glyph, confidence, status and drift marker per card. Decide which of those
  belong in a terminal print; the point is orientation plus a pointer, not a
  second full By-Trail implementation in prose.
- **The board pointer must be accurate.** `z` enters By-Trail, `s` chooses which
  trail is shown, `v` opens the full summary, `Enter` opens a member's narrative
  (`docs/tuis/board/reference.md`). Verify the keys against the live bindings in
  `aitask_board.py` before writing them into either the skill or the docs.
- **Templating.** The skill is profile-aware: edit
  `.claude/skills/aitask-trail/SKILL.md.j2` (the authoring template), not a
  rendered variant, and regenerate goldens / run
  `./.aitask-scripts/aitask_skill_verify.sh` per
  `aidocs/framework/skill_authoring_conventions.md`. Per CLAUDE.md, do the
  Claude Code version first and suggest separate aitasks for the Codex CLI and
  OpenCode wrappers if their surfaces need it.
- **Docs conventions.** Website prose is current-state-only (no version
  history), and per `aidocs/framework/documentation_conventions.md` any passage
  naming the supported coding agents must be genericized. The new skill page
  should follow the shape of a sibling page such as
  `docs/skills/aitask-work-report.md`.
- **Decomposition hint.** If this is split, the website documentation deserves
  its own child rather than being appended to the behavioural child.

## Acceptance criteria

- Running `/aitask-trail` interactively to create (and to refresh) a trail ends
  with a summary that states, in addition to the existing depth + overview
  lines: each wave in order with its ordinal and title, the entries in each wave
  in `position` order with their task refs, and the recorded dependency
  relations — degrading honestly on a lite trail that carries none.
- That summary ends with a note that the trail can also be viewed in `ait board`
  under By-Trail, naming the correct keys.
- The `--show` and headless behaviours are explicitly decided and documented in
  the skill, not left implicit.
- The existing `narrative.overview` line still resolves and strips exactly as
  `trail_summary_text()` does; any test pinning that behaviour still passes.
- `website/content/docs/skills/aitask-trail.md` exists, describes the standalone
  create / refresh / show workflow (including invoking it conversationally), and
  is linked from `docs/skills/_index.md`.
- `docs/tuis/board/reference.md` §By-Trail links to the new skill page, and the
  new page links back to the By-Trail reference.
- `./.aitask-scripts/aitask_skill_verify.sh` passes and affected goldens are
  regenerated in the same commit.

## Evidence

- `.claude/skills/aitask-trail/SKILL.md.j2` — `## Run summary print` (line 675),
  Step 1.4 / 2e.5 / 3.7 call sites, Overview invariants, `## Notes` ("Board
  integration … is a separate surface").
- `.aitask-scripts/board/aitask_board.py:1055` — `trail_summary_text()`, the
  parity target.
- `website/content/docs/skills/` — 28 skill pages, none for `aitask-trail`.
- `website/content/docs/skills/_index.md` — no trail row.
- `website/content/docs/tuis/board/reference.md:242+` — the §By-Trail section and
  its single `/aitask-trail` sentence; `:61` (`T` key) and `:215` (`z`).
- `aidocs/implementation_trail_design.md` — wave / entry / relation model.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-31T15:29:13Z status=pass attempt=1 type=human
