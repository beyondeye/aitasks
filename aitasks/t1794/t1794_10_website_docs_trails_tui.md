---
priority: medium
effort: medium
depends: [1794_6]
issue_type: documentation
status: Ready
labels: [aitask_board, tui, trails, python, refactor, website]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 10 of t1794 — the website documentation for the stand-alone `ait
trails` TUI and the resulting changes to the board pages, the TUI index and
every page that currently states the board is the only way to reach a trail.
It depends on child 6 (the command name, keys and switcher letter must be
final before the page is written) and is deliberately a separate child so the
docs describe what shipped rather than a moving target.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— "Decisions" (`ait trails`, key `i`, read-only scope, shortcut ownership,
`T` semantics, `M`/`S` hidden), child 10 section; `CLAUDE.md` "Website" and
`aidocs/framework/documentation_conventions.md` (current-state-only, no
version history, genericise agent names); `website/README.md` (link checkers).

## Key files to modify

- `website/content/docs/tuis/trails/_index.md`, `how-to.md`, `reference.md`
  — NEW page set, one directory per TUI. Model on
  `website/content/docs/tuis/minimonitor/` (front matter `title`, `linkTitle`,
  `weight`, `description`, `maturity`, `depth`; the relationship to the
  parent TUI stated in the first paragraph; the "Customizable keys" callout).
  `reference.md` owns the key map (`s` select, `r` local refresh, `d` drift,
  `R` agent refresh, `v` summary, `T` author/refresh a trail for the focused
  live member, `enter` detail, `a` reveal in detail, `q` quit, `j` switcher,
  `?` keys), the fact that the keys are the board's own customizable
  `board` entries, the launch forms (`ait trails`; switcher `i`; from the
  board via `j`), and what the stand-alone deliberately does not do
  (`m`/`M` move-to-column, `S` sync — board only).
- `website/content/docs/tuis/board/reference.md:32–39, 63, 165, 224, 251–275`
  and `how-to.md` — the By-Trail view stays embedded; add the pointer to the
  new page for the full reference and the `j` → `i` hand-off.
  `tests/test_board_reference_doc_literals.py` pins literals on this page
  against the board source — run it.
- `website/content/docs/tuis/_index.md` — bullet list `:17–22` (the Board
  bullet `:20` currently describes By-Trail: rewrite it and add a Trails
  bullet after it); switcher paragraph `:32` (core TUI list) and `:38`
  (shortcut letters — add `i`); front-matter `cascade` links `:7–9`.
- `website/content/docs/skills/aitask-trail.md:87` — "There is no `ait
  trail` command: trails are reached through this skill and through the
  board's By-Trail view." → rewrite (there is `ait trails`, the viewer;
  `/aitask-trail` remains the author/refresh skill); relrefs at `:12, 72, 92`
  point at the new page where they describe viewing.
- `website/content/docs/workflows/implementation-trails.md:51, 63, 82` —
  "Press `z` for the By-Trail view…" gains the stand-alone alternative;
  `:51` (`T` not available in By-Trail) now says `T` in `ait trails`
  authors a trail for the focused member.
- `website/content/docs/skills/aitask-backlog-roadmap.md:17`.
- `CLAUDE.md:431–435` — confirm the list already names `trails` (child 6).

## Reference files for patterns

- `website/content/docs/tuis/minimonitor/_index.md` (the precedent for a TUI
  carved out of a bigger one), `website/content/docs/tuis/board/reference.md`
  (key-map table style), `website/content/docs/tuis/_index.md`.
- `website/check_links.py`, `website/check_link_relevance.py`,
  `tests/lib/docs_vocabulary_scan.py`.
- `.aitask-scripts/board/trails_app.py` (child 6) — the source of every
  documented key literal.

## Implementation plan

1. **Rebase check** (parent pre-phase): confirm child 6 is archived
   (`./.aitask-scripts/aitask_query_files.sh archived-task 1794_6`), re-read
   `trails_app.py` `BINDINGS` and `tui_switcher.py` `_TUI_SHORTCUTS`, and
   `git log --oneline -10 -- website/content/docs/tuis website/content/docs/skills/aitask-trail.md`;
   foreign `Implementing` task on these pages → stop at the checkpoint.
2. Write the three new pages; edit the board pages, index, skill and
   workflow pages. Prefer `{{< relref "/docs/tuis/trails" >}}` over relative
   paths.
3. `cd website && python3 check_links.py --build` (mandatory) and
   `python3 check_link_relevance.py` (report — triage, not a gate);
   `python3 tests/lib/docs_vocabulary_scan.py`; `hugo build --gc --minify`.
4. Grep every documented key literal and command name against
   `trails_app.py`, `tui_switcher.py` and `ait` (record the grep in the plan).

## Verification steps

- `cd website && python3 check_links.py --build` exits 0; `hugo build --gc
  --minify` succeeds; `python3 tests/lib/docs_vocabulary_scan.py` clean.
- `python -m pytest tests/test_board_reference_doc_literals.py -q` green.
- `grep -rn 'no `ait trail` command\|only way to reach\|through the board.s By-Trail view'
  website/content/docs` returns nothing.
- Every key in `trails/reference.md` exists in `TrailsApp.BINDINGS` (grep
  both ways); `i` appears in `tuis/_index.md:38`'s letter list.
- Manual: `cd website && ./serve.sh`, open the Trails page set, the TUI index
  and the board reference; the screenshots comments follow the existing
  `<!-- SCREENSHOT: … -->` convention.
