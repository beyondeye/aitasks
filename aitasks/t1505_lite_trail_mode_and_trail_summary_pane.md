---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [skills, aitask_board, tui, artifacts, planning, trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1505_1, t1505_2, t1505_3, t1505_4, t1505_5]
anchor: 1210
created_at: 2026-08-13 11:09
updated_at: 2026-08-13 12:31
---

## Problem

`/aitask-trail` produces an excellent artifact and the By-Trail board screen is
the right surface for "what lands next, and why" — but the create/refresh run is
so expensive that the feature goes unused. In practice the same question gets
asked conversationally ("which task should I pick now, considering what is
in-flight?") and answered in 1–2 minutes with free-form prose that is *easier to
read* than the structured trail. The conversational answer has two real defects
the trail does not: it dies with the agent session, and keeping an agent open
just to hold it costs hundreds of MB of RAM.

So the goal is not to replace trails — it is to make producing one cheap enough
to be worth doing, and to make the prose rationale visible without diving
through a modal.

### Where the cost actually is (measured)

- **The deterministic half is already fast.** `./.aitask-scripts/aitask_trail_gather.sh
  drift --trail art:trail-gates-framework-landing` completes in **0.85s**. All
  the wall-clock cost is model analysis plus authoring the JSON.
- **The skill template is 427 lines / 22KB**
  (`.claude/skills/aitask-trail/SKILL.md.j2`) and mandates, for every run:
  an evidence record per rationale/observation, propose-and-confirm scope
  expansion, a belt-and-braces `verifies` / `risk_mitigation_tasks` sweep on
  refresh, and a validate-then-write loop.
- **The output is enormous, and not proportional to trail size.** The two live
  artifacts:

  | handle | bytes | waves | entries | observations | evidence | relations |
  |---|---|---|---|---|---|---|
  | `art:trail-gates-framework-landing` | 166,868 | 8 | 40 | 19 | 56 | 52 |
  | `art:trail-shadow-review-loop` | 138,879 | 5 | **10** | 19 | 41 | 15 |

  The 10-entry trail is 139KB because `evidence` (33.5KB) + `observations`
  (28.5KB) + `narrative` (9.2KB) dominate — roughly 2KB of authored prose per
  entry regardless of how small the trail is.

### The wall of text

`TrailDetailScreen._sections()` (`.aitask-scripts/board/aitask_board.py:3858`)
renders, for **every** focused card: the entry fields, its wave, the whole trail
narrative, every drift reason, **all 19 observations, all exclusions, and all 56
evidence lines**. The per-entry part is a handful of lines; everything after it
is byte-identical on every card. That is why the modal reads as an
undifferentiated wall — there is nothing to compare one card against another.

## Goal

Three changes, one topic:

1. **A lite trail flow** — a `--lite` (or equivalent) mode of `/aitask-trail`
   that produces a schema-valid trail in the ballpark of the conversational
   answer's cost, by omitting the optional heavy sections rather than by
   changing what a trail *is*.
2. **A non-binding general summary in the trail data** — free-form prose stating
   the findings and the motivation for the proposed wave/task order. The
   existing structure stays binding; this is additive and advisory.
3. **Surface that summary in two places** — a small-height pane at the bottom of
   the By-Trail screen, and printed at the end of the `/aitask-trail` run so the
   user can decide what to pick next without returning to the board and
   refreshing.

## Constraints and findings that shape the design

### A lite trail is already schema-legal — no schema change is needed for it

Required top-level keys are `schema_version, trail_id, title, owner, scope,
generation, freshness, narrative, waves, evidence` (`evidence` has
`minItems: 1`). **`observations`, `relations`, `exclusions` and
`rendering_hints` are all optional.** Per wave the floor is
`wave_id, ordinal, title, purpose, entries`; per entry it is
`entry_id, task, topic, position, classification, snapshot, rationale,
confidence`.

The board consumes exactly `build_trail_lanes` (waves → entries →
`task` / `classification` / `snapshot`), `trail_entry_refs`, and
`TrailDetailScreen`, and reads the optional sections defensively
(`doc.get("observations") or []`). **Nothing a lite trail would drop is
load-bearing for the By-Trail lanes** — so full board compatibility is
achievable by construction, and must be pinned by a test rather than assumed.

### The summary field needs an additive schema edit, and the const must not move

`narrative` is `additionalProperties: false`, as are the top level, `wave` and
`entry`. `schema_version` is `const: "1.0.0"`.

- **Do not bump the const.** Both existing artifacts declare `1.0.0`, and the
  board fails closed on a schema-invalid document (`_render_bytrail` renders the
  "could not be loaded (fail-closed)" card). Bumping would blank the By-Trail
  view for every trail authored so far.
- Add the summary as an **optional** `narrative.*` field (e.g.
  `narrative.overview`) so existing documents stay valid, and have the pane fall
  back to the already-required `narrative.recommendation_summary` when the new
  field is absent — that way the two live trails render in the new pane
  immediately, with no migration.
- `rendering_hints` is the one genuinely open slot
  (`additionalProperties: {string|number|boolean}`), so a depth marker such as
  `{"depth": "lite"}` is legal **today** with no schema edit — useful for
  labelling a lite trail in the board subtitle or selector.

### The bottom pane must not be docked

`AitaskBoard.compose()` (`.aitask-scripts/board/aitask_board.py:7964`) yields
Header → `#filter_area` → `#board_container` (a `HorizontalScroll`, no explicit
height → `1fr`) → `MultiRowFooter`. `MultiRowFooter` inherits `dock: bottom`
from Textual's `Footer` and never unsets it. The board's own CSS comment
(`aitask_board.py:7362`, t1278) records what happens with two same-edge docked
siblings: Textual places them at the **same offset** and one silently paints
over the other, while both still report `display=True`, `visible=True` and a
correct region.

So the summary pane must be a normal flow child yielded after
`#board_container`, with `display` toggled so it appears only in the By-Trail
base filter — never `dock: bottom`.

## Acceptance criteria

- [ ] `/aitask-trail` gains an explicit lite mode, reachable from the CLI and
      from the board's agent-refresh launch path (`_launch_trail` →
      `ait codeagent invoke trail <args>` → `/aitask-trail <args>` already
      forwards free-form args, so no plumbing is required).
- [ ] A lite trail validates against the unchanged `schema_version: "1.0.0"` and
      renders in the By-Trail view with correct lanes, badges, landed marks and
      drift markers — pinned by a test that feeds a minimal lite document
      through `build_trail_lanes` and `TrailDetailScreen`, not by inspection.
- [ ] The trail JSON carries an optional free-form summary field; the schema
      edit is additive and the `const` is unchanged. Both existing live
      artifacts still validate (`aitask_trail_gather.sh drift --trail <handle>`
      on each).
- [ ] The By-Trail screen shows the summary in a small-height pane below the
      board container, visible only in By-Trail, and the footer is still fully
      visible with it mounted (verified at render level / real terminal, per the
      project's TUI verification conventions — a docked-sibling collision is
      invisible to `display`/`visible` assertions).
- [ ] The summary is printed at the end of a `/aitask-trail` create and refresh
      run, after the `HANDLE:` line, so no board round-trip is needed.
- [ ] The detail modal no longer repeats the entire global observation/evidence
      list on every card — the entry-specific content leads, and the global
      sections are reachable without dominating the view.
- [ ] Where the summary comes from is stated in the docs: which field the pane
      reads, and the fallback to `recommendation_summary` for pre-existing
      trails.

## Blast radius

- `.aitask-scripts/lib/implementation_trail.schema.json` +
  `.aitask-scripts/lib/trail_schema.py` (additive field; validator's own copy of
  the schema).
- `.aitask-scripts/board/aitask_board.py` — `compose()`, the By-Trail
  render/teardown path, `TrailDetailScreen._sections()`, CSS.
- `.claude/skills/aitask-trail/SKILL.md.j2` — lite flow + end-of-run print.
  `tests/test_trail_skill_contract.sh` pins ~20 exact phrases from the template,
  and any `.md.j2` edit carries the goldens/rerender obligation
  (`aitask_skill_rerender.sh`, one call per profile). Porting to
  `.agents/skills/` and `.opencode/skills/` is a separate follow-up per
  CLAUDE.md.
- `aidocs/implementation_trail_design.md` — §6 schema walkthrough, §9 board
  integration, §15 wireframes.
- Tests: `tests/test_trail_schema.py`, `tests/test_board_bytrail_view.py`
  (3,335 lines), `tests/test_trail_skill_contract.sh`,
  `tests/test_implementation_trail_design.py`.

## Non-goals

- Removing or weakening the full trail flow — lite is an added mode, not a
  replacement, and the heavyweight analysis stays available.
- Changing what the board treats as binding: waves, entries, ordering and
  classifications remain the structured contract. The summary is advisory prose
  and must never become an input to lane construction.
- Bumping `schema_version`, or any change that invalidates the two existing
  artifacts.

## Related tasks

- **t1470** (`surface_intrawave_parallel_safety_in_bytrail_view`) — same topic
  (anchor 1210) and same view, but a different question: which entries within a
  wave can run in parallel. Considered for folding during exploration and
  deliberately kept separate.
- **t1487** — a By-Trail test-teardown flake; touches
  `tests/test_board_bytrail_view.py`, which this task also edits.
