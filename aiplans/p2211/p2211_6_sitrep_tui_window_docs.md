---
Task: t2211_6_sitrep_tui_window_docs.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_6 — Docs

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. The task file lists
every page and section.

## Steps

1. Read the archived sibling plans `aiplans/archived/p2211/p2211_{1..5}_*.md` (Final
   Implementation Notes) and document the **landed** behaviour: keys, statuses, wire lines,
   refusals.
2. Rebase check of the doc files (clean against HEAD).
3. `aidocs/framework/sitrep.md`:
   - "The sitrep window": roles, layout, stamp, the two-predicate table, the four-way spawn,
     wire lines, agent exit, races;
   - a new "The sitrep TUI" section: views, pointers, actions, reload, the request-delivery
     phases + refusals + results + ack;
   - "The skill": slim;
   - "Tests": the new files.
4. `aidocs/framework/tmux_gateway.md`: verify that the inventory rows exist for
   `@aitask_sitrep_tui_root`, `@aitask_dispatch_ack` and the board-focus handoff option.
5. Website:
   - `docs/workflows/sitrep.md` and `docs/skills/aitask-sitrep.md` updates (per the task);
   - new `docs/tuis/sitrep/{_index,how-to,reference}.md`, modelled on `docs/tuis/trails/`;
   - a bullet in `docs/tuis/_index.md`;
   - `ait board --focus` in the board reference.

   Use relref links and current-state prose only.
6. `cd website && hugo build --gc --minify && python3 check_links.py --build`. Offer
   `python3 check_link_relevance.py`.

## Verification

- The Hugo build and `check_links.py --build` pass.
- The new TUI page is reachable from `tuis/_index.md`, and the sitrep workflow page links to
  it.

## Step 9

Commit with `documentation: … (t2211_6)` and archive.
