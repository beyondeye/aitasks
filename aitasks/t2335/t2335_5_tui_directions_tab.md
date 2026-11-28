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

> **✉ note:t2335_2** id=2026-11-25T17:24:38Z.4a18f2232025b24f886c43d0 from=t2335_2 from_verified=yes at=2026-11-25T17:24:38Z base=ec774ca92a8286795b5f00062c409f0cf299e2ef base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit ec774ca92): t2335_2 landed the computed freshness of directions; this is what a Directions tab can read.
> | - Contract: aidocs/framework/sitrep.md, "The freshness verdict" (snapshot values, the verdict rules, the reason vocabulary in order).
> | - `checked_at` of a direction means "verdict last changed", not "last scanned": an equal verdict writes nothing.
> | - An `unknown` verdict can carry several reasons at once (for example `never_summarized` beside `trail_unreadable`). Codes that only come with `unknown`: baseline_too_large, baseline_unreadable, check_incomplete, trail_unreadable, task_unreadable (sitrep_direction.UNKNOWN_CODES; full ordered list in sitrep_direction.VOCABULARY).
> | - A direction with members and no block has nothing stored. The refresh reports it as `no_record` (stale, never_summarized) and writes nothing, so derive its row from st.known_directions(store).
> | - RefreshReport (sitrep_tui_model.py) gained `.directions` (payloads `<slug>|<old>-><new>|<result>|<drift>`), `.direction_counts` and `.unassigned`; `.partial` is true for an unknown or unreached direction and for a failed direction pass, and `verdict()` appends the direction part, also on the "Nothing to refresh" line.
> | - The refresh prints `REFRESH_UNASSIGNED:<n>` on every run that read the store; st.unassigned_items(store) gives the same count in process.

> **✉ note:t2335_3** id=2026-11-27T06:48:40Z.ee0b150042bc81b6a365a6c4 from=t2335_3 from_verified=yes at=2026-11-27T06:48:40Z base=7516a41b4b09216a75454e215f620cb90cc4fc3f base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2335_3 (landed as commit 7516a41b4). What the Directions tab can call to show a direction's tasks in `ait trails`, as that commit has it. Check it against the code before relying on it.
> | 
> | The launcher, in `.aitask-scripts/lib/agent_launch_utils.py`:
> | 
> | `launch_or_focus_trails(session, root, handle, task_id=None, highlight=None, direction=None, title=None)`
> | 
> | - `highlight`: task ids (bare, or `proj#id`; a leading `t` is dropped). Duplicates collapse in caller order. An empty list, and an id outside the grammar, are refused before any tmux call.
> | - More than 256 ids (`HIGHLIGHT_MAX`): the first 256 are sent with the real total, the trail still opens, the banner reads `(showing 256 of <total>)`, and the launcher returns the warning "highlighting the first 256 of <total> tasks".
> | - `direction`: the direction's slug (identity), the store's own grammar (`sitrep_todo.DIRECTION_RE`). A valid slug longer than 512 characters is left out with the warning "direction id too long to send — the trail opens with the title only"; the highlight and the trail still go out. A slug outside the grammar is an error.
> | - `title`: the display title, one line, at most 120 characters after strip (the store's `MAX_DIRECTION_TITLE` rule). It may contain spaces, `|`, non-ASCII, and may start with `-`. The banner shows `direction: <title>`, or the slug when there is no title.
> | - Warnings come back as ONE string, joined with "; " (a truncation and a dropped slug can both be in it). Show it; it is not a failure.
> | - A running `ait trails` from before this change cannot take a highlight: the trail still opens (with the task focus, if any) and the warning says "the running ait trails cannot highlight a direction — restart it to see the overlay". The same holds for a cold start in a checkout whose `trails_app.py` has no `--highlight`.
> | - Without `highlight`, the call behaves exactly as before.
> | 
> | In the trails tab: `★` marks the highlighted tasks, `»` what must land before them, `›` advisory predecessors; `h` clears the highlight on that tab. A request without a highlight leaves an existing highlight on that tab alone; one with a highlight replaces it. The highlight is view state of that tab and is never written to the trail.
> | 
> | The advice on the cards comes from the same resolver as the `critical-path` verb t2335_4 quotes, so the tab and the skill should agree over one tree. User-facing description: `website/content/docs/tuis/trails/reference.md`, section "Task highlight".

> **✉ note:t2335_4** id=2026-11-27T12:17:53Z.936e0b28d19d0367cf251d61 from=t2335_4 from_verified=yes at=2026-11-27T12:17:53Z base=b625ddd285ba5aa1dde576919538b24330b58d0c base_branch=main dirty=yes host=omg16
>
> | Advisory (tree-relative, as of commit b625ddd28): t2335_4 landed the sitrep skill's `>d` code. Check against the code before relying on it.
> | - The "Requests from the sitrep TUI" section of .claude/skills/aitask-sitrep/SKILL.md.j2 does NOT list `>d` (user decision): check r of tests/test_sitrep_skill_contract.sh refuses a code there that AGENT_REQUESTS lacks. When you add the AGENT_REQUESTS row, add the section line in the same change (e.g. "`>d <direction>` — re-summarise that direction (`>d`)", plus the store-wide `>d`; fresh-read check: a direction `directions` lists) and regenerate the three goldens. The test will report UNDOCUMENTED_REQUEST until you do.
> | - The membership dataclasses and scan now live in .aitask-scripts/lib/trail_membership.py; sitrep_tui_trails.py re-exports the same objects. The skill reads the same derivation through `aitask_trail_gather.sh membership --tasks <ids>`.
> | - A direction saved by `>d` reads `unknown` until the next refresh computes its verdict.
> | - `>w` now passes `situation --expect-rev` and may pause instead of writing when its text would contradict the direction's summary; it then offers `>d <direction>`.
> | - The agent names an `ait trails --trail … --highlight … --highlight-direction=…` command for a direction; website/content/docs/workflows/sitrep.md ("Work directions and implementation trails", step 4) shows it where your `z` key will go.
> | - Writer additions you can use: `direction-set --with-situation` (summary + situation text in one write), `situation --expect-rev`.

> **👁 note:read** id=2026-11-28T16:42:32Z.e078c704358b40e8eb5efc0d by=t2335_5 at=2026-11-28T16:42:32Z mode=explicit ids=2026-11-25T09:40:32Z.05fae169950b1c099d354b49,2026-11-25T17:24:38Z.4a18f2232025b24f886c43d0,2026-11-27T06:48:40Z.ee0b150042bc81b6a365a6c4,2026-11-27T12:17:53Z.936e0b28d19d0367cf251d61
