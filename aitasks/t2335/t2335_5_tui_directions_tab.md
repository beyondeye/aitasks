---
priority: medium
effort: high
depends: [t2335_4, 2334]
issue_type: feature
status: Ready
labels: [sitrep, tui]
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-19 05:12
---

## Context

Child of the sitrep work-directions task; depends on the store, refresh, overlay and skill children and on the item-type tab strip task (the strip this tab is appended to).

## Goal

```
 All 14 | Triage 3 | Tasks 6 | Recovery 2 | Watches 3 |[Directions 4]
 ---------------------------------------------------------------
 1 sitrep-directions   current   next: t2330_1   3 items
   Store format landed; skill and TUI children open.
 2 testmap-waves       STALE     next: t2301     5 items
   trail drifted: t2298 archived
 3 crashed-agents      current   next: t2199     2 items
   (4 items in no direction)
```

## Scope

- A **Directions** tab, last in the strip, its label counting directions (marked when any is stale or unknown). Rows in confirmed rank order, unranked directions after them; each row: rank, title, freshness (`current` / `STALE` / `unknown`, with the age label refreshed like the other ages), next step, open-item count, then one line of summary or, when stale, the first drift reason in plain words (one table mapping the refresh reason codes to text; an unknown code is shown raw, never hidden).
- A final line "N items in no direction"; Enter on it opens the All tab filtered to those items.
- **Enter** on a direction opens a details screen: the full summary and situation text, the drift reasons, the member items grouped Now / Next / Waiting (Enter opens the usual item details), and one row per linked trail.
- **`z`** (and Enter on a trail row): `ait trails` with the highlight overlay for this direction's member tasks (`launch_or_focus_trails` with the highlight set, the same session rule as today). A direction with no linked trail says so and names the `>d` request.
- **Request key into the agent**: one new row in `AGENT_REQUESTS` typing `>d <direction>` for the selected direction, and the store-wide form `>d` when no directions exist yet (empty state: "No directions yet" plus the key). Same availability, one-in-flight and re-check rules as the existing requests: a direction whose rev moved since the row was drawn sends nothing.
- Reads come from the same poll and last-good-parse path as the rest of the store; the tab must render a store that has themes but no direction fields (pre-`>d` state) and a format-3 store.
- Geometry: two lines per direction inside a pane that is 40% of a window; titles and summaries elide, never wrap; verify at 80 columns.
- Shortcut scopes for the new screen in `lib/shortcut_scopes.py`; read `aidocs/framework/tui_conventions.md` first.

## Tests

`tests/test_sitrep_tui_app.py`, `test_sitrep_tui_actions.py`, `test_sitrep_tui_requests.py` (the `AGENT_REQUESTS` parity test picks the new row up), `test_sitrep_tui_trails_actions.py` for the highlight launch: rank order, each freshness state, the reason-text table (every refresh reason code has text), empty state, no-direction line, stale-rev refusal, 80-column render.

## Docs

`aidocs/framework/sitrep.md` ("The sitrep TUI"), `website/content/docs/tuis/sitrep/` (`_index`, `how-to`, `reference`), `website/content/docs/workflows/sitrep.md`; `check_links.py --build`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2335_1** id=2026-11-25T09:40:32Z.05fae169950b1c099d354b49 from=t2335_1 from_verified=yes at=2026-11-25T09:40:32Z base=95d0169d8b7b7b559161028acd85264c4061ad8d base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit 95d0169d8): t2335_1 landed store format 4 and the direction records your tab reads.
> | - Contract: aidocs/framework/sitrep.md, section "Directions". Wire lines: header of .aitask-scripts/aitask_sitrep_todo.sh.
> | - The rename is done: TUI label "Direction", request template ">w {direction}", sitrep_tui_requests.item_direction (delegates to sitrep_todo.item_direction). RECOVERY_THEME no longer exists; use sitrep_todo.RECOVERY_DIRECTION.
> | - app.store.directions is {slug: Direction} with rev, title, rank (0 = unranked), trails, next, summary, digest, freshness, checked_at, drift as (code, count, [sample keys]) and situation (lines). store.situations is gone.
> | - Read helpers in sitrep_todo: known_directions(store) (ranked by rank, then unranked by slug; includes directions that exist only from their members, with no block), direction_members, pending_members, unassigned_items (state open or unknown), direction_stamp.
> | - A direction with members and no block has no record: rev shows as "-" in the `directions` verb. A block read from a not-yet-upgraded store has rev 0.
> | - _render_situation now skips blocks with no situation text.
