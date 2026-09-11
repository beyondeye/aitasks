---
Task: t1794_10_website_docs_trails_tui.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_9_*.md, t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_10 — Website docs for `ait trails`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(Decisions PINNED). Depends on `t1794_6`. Follow
`aidocs/framework/documentation_conventions.md` (current state only).

## Pages

- NEW `website/content/docs/tuis/trails/{_index,how-to,reference}.md`,
  modelled on `tuis/minimonitor/`; reference owns the key map (`s r d R v T
  enter a q j ?`), states the keys are the board's `board`-scope customizable
  entries, the three launch forms (`ait trails`, switcher `i`, board `j`→`i`),
  and the deliberate non-features (`m`/`M`, `S` — board only).
- `tuis/board/reference.md:32–39,63,165,224,251–275`, `how-to.md`: embedded
  view stays; pointer to the new page; `test_board_reference_doc_literals`
  must stay green.
- `tuis/_index.md`: bullets `:17–22` (rewrite the Board bullet `:20`, add
  Trails), switcher `:32` and `:38` (add `i`), cascade `:7–9`.
- `skills/aitask-trail.md:87` rewrite (there is `ait trails`; the skill
  authors/refreshes), relrefs `:12,72,92`.
- `workflows/implementation-trails.md:51,63,82`;
  `skills/aitask-backlog-roadmap.md:17`.

## Order

Rebase check (child 6 archived; re-read `trails_app.py` `BINDINGS`,
`_TUI_SHORTCUTS`) → pages → `cd website && python3 check_links.py --build`
→ `python3 check_link_relevance.py` (report) → `python3
tests/lib/docs_vocabulary_scan.py` → `hugo build --gc --minify` → grep every
documented literal against the source (record).

## Verification

- `check_links.py --build` exit 0; `hugo build` succeeds; vocabulary scan
  clean; `test_board_reference_doc_literals` green.
- `grep -rn 'no `ait trail` command' website/content/docs` empty.
- Every documented key exists in `TrailsApp.BINDINGS`; `i` in `_index.md:38`.
- Manual: `./serve.sh` and read the new page set, index, board reference.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_10`.
