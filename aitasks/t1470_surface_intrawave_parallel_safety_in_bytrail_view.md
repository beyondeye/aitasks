---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_board, tui, skills, planning, artifacts]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-08-10 11:35
updated_at: 2026-08-10 11:35
---

## Problem

The By-Trail view renders a trail's waves as columns and each entry as a card,
but it never answers the question the trail exists to support: **of the tasks in
this wave, which can I start right now, and which must not run alongside each
other?**

A wave is defined as "an ordered group of trail entries that lands as a unit
before the next wave" (`aidocs/implementation_trail_design.md:68`), and entries
carry a strictly-increasing `position`. In practice waves are large — the live
`art:trail-gates-framework-landing` has W1 with 15 entries and W2 with 9 — so
"the wave is the unit" is not actionable guidance for someone choosing what to
pick next, alone or alongside a running agent.

## What the card shows today

`TrailTaskCard.compose` (`.aitask-scripts/board/aitask_board.py:2954-2978`)
yields: title (`✔` + strike when landed), `_trail_badge_text` (classification
glyph · confidence), `📋 <status>`, an optional `_trail_drift_text` marker, and
the literal `[enter details]` hint. `TrailEntryView`
(`aitask_board.py:642-651`) carries only `entry`, `task`, `ghost_kind`,
`landed`, `drift_reasons`. There is no readiness, no blocked-by, no coupling.

`TrailTaskCard` fully overrides `TaskCard.compose`, so the base card's
`🚫 blocked` / `🌐 blocked (cross-repo)` / lock indicators
(`aitask_board.py:2663-2700`) never appear in By-Trail either.

## The data is already there and is being discarded

1. **`relations[]` is read by nothing in the board.** A grep for
   `hard_depends` / `advisory_precedes` / `coordinates_with` /
   `shared_surface_collision` / `in_flight_conflict` across
   `aitask_board.py` returns **zero** hits. The schema defines these edges with
   mandatory `provenance: fact|advisory`
   (`.aitask-scripts/lib/implementation_trail.schema.json`), and
   `trail_schema.py:370-408` already validates that `hard_depends` edges are
   facts mirroring `snapshot.depends`.

2. **`observations[]` is rendered unattributed.** `TrailDetailScreen._sections`
   (`aitask_board.py:3417-3420`) loops over **every** observation for **every**
   focused entry without consulting `obs["affects"]`. So on the live gates
   trail, `obs-settings-collision` — which names t635_24 / t635_37 / t635_30 /
   t635_31 explicitly as building the same settings-TUI surface — renders
   identically on a card it has nothing to do with. This is a defect in its own
   right and is in scope here.

3. **Live readiness is one call away.** `_render_bytrail` already passes
   `self.manager` into `TrailColumn` (`aitask_board.py:9495`), and
   `build_trail_lanes` (`:703`) already resolves each entry to a live `Task`.
   `TaskManager.unresolved_local_deps` (`:1564`, gate-aware via
   `dependency_released_by_gates` `:1559`), `cross_repo_dep_display` (`:1575`),
   `lock_map`, `_human_pending_gates` (`:1610`) and `_has_failed_gate` (`:1627`)
   are all available and already composed into a group + `next_action` string
   by `_inflight_item_for` (`:1638-1685`) for the In-Flight view.

## Measured: dependency readiness alone is the wrong signal

Computed against `art:trail-gates-framework-landing` using the framework's own
frontmatter parser (`lib/task_yaml.parse_frontmatter`) on 2026-08-10:

| wave | un-landed | dep-ready | discriminating coupling |
|---|---:|---:|---|
| W1 | 4 | 4 | one `advisory_precedes` pair (1438→1437) |
| W2 | 7 | 7 | 5 of 7 carry intra-wave `advisory_precedes`; t635_28 is downstream of **five** siblings |
| W3 | 3 | 3 | all three mutually `coordinates_with` **and** all three in `obs-settings-collision` |
| W4 | 3 | 2 | t635_31 blocked on 635_24 + 635_30 |
| W8 | 5 | 5 | one `coordinates_with` pair (1390↔1381) ⇒ genuinely ~3 parallelizable |

**22 of 27 un-landed entries are dep-ready.** A bare "ready" badge would tell
the user to start any of 7 tasks in W2 — the obvious implementation, and an
actively misleading one. The trail's declared coupling is what discriminates,
and W8 is the case where the honest answer ("about three of these five are
independent") is derivable today with no new data.

## Absence of an edge is not safety

The other live trail, `art:trail-shadow-review-loop`, has **zero** intra-wave
relations across all five of its waves. `aitask-trail/SKILL.md.j2:407-409`
mentions `advisory_precedes` only inside a provenance rule for `hard_depends`;
nothing instructs the generator to consider and declare intra-wave coupling.

⇒ A missing edge means **not assessed**, and must render as a third state
distinct from "independent". A UI that reads silence as "safe to parallelize"
would be worse than the current blank.

## Scope

### A. Board — derive and render (advisory only)

- Extend `build_trail_lanes` (`:703`) to attach per-entry parallel-safety state
  to `TrailEntryView`. Keep the function testable: inject the live-state lookup
  as a callable parameter rather than reaching for a global or requiring the
  full `TaskManager` — it is currently pure over
  `(doc, tasks_by_id, local_project, archived_lookup, drift_by_ref)`.
- Two independent axes, never collapsed into one verdict:
  - **hard readiness** — unresolved `depends` (gate-aware), cross-repo deps,
    live `status == Implementing`, another machine's lock, pending human gate.
    Derived from **live** state only; the entry `snapshot` is a point-in-time
    copy and must never be trusted over the task file.
  - **advisory coupling** — intra-wave `advisory_precedes` / `coordinates_with`
    edges, plus `observations[]` whose `affects[]` names this entry. Three
    states: coupled / independent / **not assessed**.
- Per-card rendering on `TrailTaskCard`, and a wave-level roll-up on
  `TrailColumn` (`:3036`) answering "N of M startable, K coupled, J not
  assessed".
- Fix `TrailDetailScreen._sections` (`:3417`) to attribute observations by
  `affects[]` — the focused entry's own observations first, the rest clearly
  separated as trail-level context.
- **Never writes anything.** No `depends` mutation, no gating, no reordering —
  RFC §4.5: "Advisory ordering never impersonates the DAG."

### B. Generator — make the coupling declarable

- Teach the `aitask-trail` skill to consider intra-wave coupling explicitly
  when forming waves, and to emit `advisory_precedes` / `coordinates_with`
  edges (and `shared_surface_collision` observations) for entries it places in
  the same wave — or to state in `narrative.method_note` that intra-wave
  coupling was not assessed, so the board can render that honestly.
- Source of truth is `.claude/skills/aitask-trail/SKILL.md.j2`; per
  `CLAUDE.md`, suggest separate follow-up tasks for the Codex CLI / OpenCode
  ports, and run `./.aitask-scripts/aitask_skill_verify.sh` plus goldens
  regeneration (one rerender call per profile) in the same commit.
- Decide during planning whether the schema needs anything new here. The
  preference is **no schema change**: `relations` and `observations` already
  express everything above, and `schema_version` is `const 1.0.0`.

## Explicitly out of scope — coordinate, do not absorb

- **`issue_type` / task-kind awareness → t1468**
  (`mark_followup_task_provenance_and_surface_on_board`). Its "surfaces that
  are structurally blind" table already claims the trail: *"entry `snapshot` is
  `additionalProperties: false` with no `issue_type`; `schema_version` is
  `const 1.0.0` — yes, most expensive"*. It also owns the carrier decision
  (new `issue_type` values vs. an orthogonal provenance field). **Do not add
  `issue_type` to the trail schema or to `trail_gather.py` here.** This task
  must be useful without it and consume whatever t1468 lands. Add the reverse
  pointer to t1468.
- **Predicted file overlap → t1343** (`parallel_agent_file_conflict_advisory`,
  Ready, high/high). It owns declared per-task file manifests and the overlap
  signal; t1344 refines granularity for worktrees. Leave a named seam so a
  file-overlap term can be added to the coupling axis later, but do not build
  file comparison here. `file_references:` frontmatter exists and
  `aitask_find_by_file.sh` computes path overlap, but its only consumer
  (`aitask_create.sh:1672`) uses it to propose **folding** at create time; it is
  agent-declared and never validated against a diff.

## Sequencing — two live conflicts in this exact file

- **t1243** (board task-groups) is **uncommitted in the working tree**:
  `aitask_board.py` modified, `tests/test_board_group_focus.py` untracked,
  ~448 changed lines including `lib/board_groups.py` and `GroupHeader`.
- **t1468** flipped to `status: Implementing` on 2026-08-10 and also edits
  `aitask_board.py` card rendering.

Land after or alongside both — do not start into a conflicting tree. Re-check
both before planning.

## Render-surface constraints (verified)

- `tests/test_board_bytrail_view.py::TrailCardRenderTests::test_trail_task_card_badges_and_strike`
  asserts `.trail-badges` **exact-equals** `"◆ hard_prerequisite · conf: high"`.
  A new badge must be its own Label with its own class, mounted **after** that
  line — not appended to it, and not mounted before it (Textual's `query_one`
  returns the first DOM match).
- `test_ghost_card_kind_and_badges` reads the **first** `.task-info` Label on a
  ghost and requires `"cross-repo member"` / `"read-only"` — nothing
  `task-info`-classed may precede it in `TrailGhostCard.compose`.
- `test_no_drift_marker_when_entry_is_clean` asserts `len(query(".trail-drift")) == 0`
  on a clean card — do not reuse the `trail-drift` class.
- `test_glyph_map_pins_schema_classification_enum` pins the **key set** of
  `TRAIL_CLASSIFICATION_GLYPHS` against the schema enum — new glyphs go in a
  new dict, and must not collide with `◆ ▲ ● ⇄ ○ ✔ 👻 📋 ⚠` or the base card's
  `🚫 🌐 🔗 ↗ 📎 ⚡ 👶 💪 🏷️ 👤 🔒`.
- `tests/test_board_marking.py` requires exactly one `TrailGhostCard(`
  construction site in the source, and `markable is False` on every derived-view
  card.
- Row budget: a live trail card is 7 rows today (8 with drift) in a 44-wide
  column (`TrailColumn.on_mount:3066`, ~38 cells of text, 36 when scrolling).
  The board area starts at y=4. Each added Label costs one row per card, so
  prefer one compact line over several; an over-long column title wraps and
  costs every lane a row.
- `ColumnHeader` (`:2370-2390`) has no suffix parameter and bakes its count at
  construction. Either fold the roll-up into the `title` string at the
  `TrailColumn.compose` call site (`:3052-3057`) or add a trailing kwarg.
  By-Trail refreshes by full remount (`_render_bytrail:9494-9495`), so a
  compose-time roll-up stays fresh.
- Closest precedent for a readiness vocabulary is In-Flight
  (`InFlightTaskCard:2779-2818`, `InFlightColumn:2840-2852`): group carried by
  **border colour** and **header background colour**, an unglyphed
  `blocked by: <ids>` line, and a bracketed `markup=False` ops hint. Consider
  reusing that vocabulary rather than minting more glyphs.
- **There is no in-app legend.** The glyph contract lives in the comment at
  `aitask_board.py:609-611` and in `aidocs/implementation_trail_design.md`
  §9.1 (`:326-332`) and the §15 wireframe (`:528-545`) — register any new
  visual vocabulary in both.
- Verify at render level (`render().plain` plus composited strips for width
  **and** colour), not by reading source.

## Acceptance criteria

1. On the live `art:trail-gates-framework-landing`, the By-Trail view
   distinguishes W3 (all three entries mutually coupled and collision-flagged)
   from W8 (one coupled pair, the rest independent) without opening the detail
   modal.
2. An entry blocked by an unresolved `depends`, by a cross-repo dep, by another
   machine's lock, or by a pending human gate is visibly not startable, and the
   reason is nameable.
3. A wave whose trail declares no intra-wave relations renders **"not
   assessed"** — never "independent" / "safe".
4. Cross-wave honesty: an entry in a later wave that is dep-ready is not
   presented as blocked merely because an earlier wave is unfinished (live
   example: W6's t635_16 while W1–W5 are open). The wave boundary is advisory.
5. Observations are attributed: the detail modal shows the focused entry's own
   `affects` observations distinctly from trail-level context.
6. Nothing in this change writes to a task file, a trail artifact, or any gate.
7. Ghost cards (archived / missing / cross-repo) degrade cleanly — no live
   state to read, and no misleading readiness claim.
8. A trail generated after part B declares intra-wave coupling, or records in
   `method_note` that it was not assessed.
