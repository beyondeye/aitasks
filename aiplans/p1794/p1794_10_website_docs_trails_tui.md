---
Task: t1794_10_website_docs_trails_tui.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_11_*.md, aitasks/t1794/t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-22 17:11
---

# p1794_10 — Website docs for `ait trails` (verified 2026-09-22)

## Context

Child 6 shipped `ait trails`, a stand-alone and read-only TUI for reading trails. The website still says
the board's By-Trail view is the only way to reach a trail (`skills/aitask-trail.md:87`:
"There is no `ait trail` command"). This child documents the TUI that actually shipped and
redirects those claims. Docs only; no code changes.

## Verification of the existing plan against the tree (what changed)

- Rebase check: child 6 is archived (`ARCHIVED_TASK:…t1794_6_standalone_trails_tui.md`).
  No foreign `Implementing` task touches these pages (last commits on `tuis/` are t1705_10 docs).
- Source-of-truth literals (re-read):
  - `trails_app.py` `TrailsApp.BINDINGS` = `j` (switcher), `?` (Keys), `q`, the arrows, plus
    `TRAIL_BINDINGS` (`board_trail_screen.py:95`): `enter` view_details, `r`, `R`, `d`, `s`, `S`,
    `v`, `T`, `M`.
  - `check_action` refuses `trail_move_wave` and `trail_sync`, so `M` and `S` are declared but
    never live. `m` is not declared at all.
  - `T` (`_trail_task_target`) targets the focused **live local** member's own id. On a ghost
    card, or with nothing focused, it shows the warning "T needs a live local task under focus".
  - `r`/`d`/`R` need a selected trail. `v` needs a summary.
  - The subtitle reads "no trail selected — press s" when no trail is selected.
- **Correction to the task body:** `a` is **not** an App key. It is the `toggle_all` binding
  inside the entry-detail modal (`board_trail_view.py:655`). The reference documents it under
  the detail screen, not in the main key table.
- `_TUI_SHORTCUTS["trails"] = "i"`. The registry entry is `("trails", "Trails", "ait trails")`.
  `_HINT_ITEMS` has no trails entry, so the overlay's hint row does not show `i` (the same as
  Frozen Agent's `f`).
- `ait` dispatcher: `trails  Launch the implementation-trails TUI (read-only trail reader)`.
  `--tasks-dir` is launcher-internal (argparse SUPPRESS). The user sets `TASK_DIR` instead.
- **Stale line refs in the task:** `tuis/_index.md` has no `cascade` front matter (it has
  `aliases`) and only **one** switcher paragraph (`:30`). The `:32`/`:38` refs collapse into that
  paragraph. `CLAUDE.md` already names `trails` (`:347`, `:433`), so nothing is needed there.
- Minimonitor has no `reference.md`. Frozen Agent (`tuis/frozenagent/`) is the three-page
  precedent, and I'll check its reference for the table layout.

## Implementation

1. **NEW `website/content/docs/tuis/trails/_index.md`**
   - Front matter: title "Trails", linkTitle "Trails", `weight: 12` (just after Board = 10),
     a description, `maturity: [experimental]`, `depth: [intermediate]`.
   - First paragraph: `ait trails` is the stand-alone reader for
     [implementation trails], carved out of the board's By-Trail view (`z`). That view stays
     embedded and unchanged. Both surfaces read the same stored trails.
   - `<!-- SCREENSHOT: aitasks_trails_main_view.svg — … -->`, then the "Customizable keys"
     callout. The callout also says the keys are the board's own `board`-scope entries, so a
     rebind reaches both TUIs.
   - Sections:
     - Purpose.
     - "Relationship to the board": a table comparing the two surfaces. Rows: launch, keys
       shared, move-to-column `m`/`M` (board only), sync `S` (board only), `T` semantics, writes
       `board_config.json` (board only; trails never writes it), and the switcher.
     - Launching: `ait trails`; `j` → `i` from any TUI; `j` → `b` back to the board. Note that
       the `i` letter is not advertised on the hint row but is listed in the overlay.
   - Ends with "Next: How-To Guides".
2. **NEW `tuis/trails/how-to.md`** — task-oriented sections. Initial selection, reselection
   and post-sync refresh are three separate situations (source-verified, see the behavioural
   checklist under Verification):
   - **How to open a trail:** `ait trails` boots straight into the trail selector
     (`on_mount` → `_open_trail_select`); pick a trail there. Dismissing the selector leaves the
     subtitle "no trail selected — press s".
   - **How to switch to another trail:** `s` reopens the selector **and rescans** the trail
     artifacts, so a trail created since launch is listed.
   - How to read waves and the summary: the arrows, `v`, the depth label.
   - How to read one member's reasoning: `Enter`, then `a` in the detail to reveal the whole
     document.
   - **How to keep it current** — match the key to what changed:
     - A task's status changed on this machine → `r`. It reloads the task files and redraws the
       **cached** trail; it reads no artifact.
     - The shown trail may have a newer stored version, or you want freshness re-checked → `d`.
       It re-fetches the active trail's stored artifact and re-runs drift, and never writes.
     - A trail was created elsewhere or since launch → `s` (rescan).
     - After syncing remote task data (`ait sync`, or `S` on the board — this TUI has no sync
       key): `r` for task statuses, `d` for the shown trail's latest stored version, `s` if a
       new trail may have arrived. `r` alone does **not** pick up a new or updated trail.
     - `R` opens the agent workflow that re-authors the shown trail (heavyweight).
   - **How to start a trail for a member:** `T` on a live local card **opens the
     `/aitask-trail` create-or-refresh workflow** for that task through the agent-launch dialog.
     The TUI writes nothing: the agent shows its proposal and writes the trail only after you
     confirm it there. When it lands, press `s` to list and select it (there is no automatic
     pickup for `T`). On a ghost card, or with nothing focused, it shows the warning
     "T needs a live local task under focus" and launches nothing.
   - **How to move a wave onto the board.** The switch transfers **neither the selected trail
     nor the focused card**: the board keeps its own active trail, independent of this TUI's
     selection.
     1. Press `j` → `b` to switch to the board, then `z` for By-Trail. The board opens its
        selector on `z` **only when it has no active trail**. Otherwise it shows the trail it
        last had.
     2. Check the subtitle (`By-Trail: <handle>`). If it names a different trail, press `s` and
        select the intended one.
     3. Focus a **live** member card in the wave you want (not a ghost card), then press `M`.
        Its review dialog lists the wave's tasks before any destination is chosen.
   - Cross-link [Implementation Trails] and the board reference.
3. **NEW `tuis/trails/reference.md`**
   - Key table (Key | Action | Context), with contexts matching `check_action`:
     - `s` — reopen the selector (rescans).
     - `r` — reload task files and redraw the cached trail.
     - `d` — re-fetch the stored trail and re-check freshness.
     - `R` — open the agent re-author workflow.
     - `T` — open the `/aitask-trail` create-or-refresh workflow for the focused live local
       member; the workflow confirms before it writes.
     - `v`, `Enter`, the arrows, `q`, `j`, `?`.
   - A short "What each refresh reads" table: task files / stored artifact / trail list.
   - State that launching opens the selector automatically.
   - A detail-screen table with `a`.
   - "Not available here": `m`/`M`/`S` (board only), and why.
   - Shortcut customization: `shortcuts.board.<action>` in `userconfig.yaml` rebinds both
     surfaces. `?` here lists only the rows this TUI declares plus the shared scope. Kanban-only
     keys are edited from `ait board` or Settings → Shortcuts.
   - Launch & environment: `ait trails`, `TASK_DIR`, read-only (never creates
     `board_config.json`).
   - Point to the board reference `#by-trail` for drift markers, the ghost card taxonomy and
     refresh costs, and restate them only briefly.
4. **`tuis/board/reference.md` By-Trail section (`#### By-Trail`, ~:249)**
   - Add one paragraph after the intro: the same view also runs stand-alone as
     [`ait trails`] (link to `/docs/tuis/trails`). It shares these keys, reached from here with
     `j` → `i`. `m`/`M`/`S` exist only on the board.
   - State that the two TUIs keep **separate** trail selections, so a switch does not carry the
     selected trail or the focus across. Do not claim a hand-off of state.
   - Do not touch any literal pinned by `test_board_reference_doc_literals.py`.
5. **`tuis/board/how-to.md` By-Trail block (~:215–240):** add a single sentence plus a link to
   `ait trails` for reading trails without the board.
6. **`tuis/board/_index.md:51`** — no change (it only lists view keys). Optionally add a
   "see also Trails" phrase. **Decision: leave it**, to keep the diff minimal.
7. **`tuis/_index.md`**
   - Board bullet (`:20`): keep the By-Trail sentence and append "also available stand-alone as
     Trails".
   - Add a **Trails** bullet after it: `[Trails](trails/) (ait trails)` — a read-only trail
     reader.
   - Switcher paragraph (`:30`): add "Trails" to the core-TUI list. Extend the Frozen Agent
     sentence so it names both reachable-but-unadvertised letters: `f` for Frozen Agent and `i`
     for Trails.
8. **`skills/aitask-trail.md`**
   - `:87` → "Trails are authored and refreshed through this skill and read in
     [`ait trails`] or in the board's By-Trail view (`z`)."
   - `:12` → mention both viewers.
   - `:92` Related → add a `[Trails TUI]` bullet and keep the board-reference bullet.
   - `:72` describes the skill's actual printed pointer (it names the board, per
     `SKILL.md.j2:801`), so it stays accurate. Leave it.
9. **`workflows/implementation-trails.md`**
   - `:51`: add "In `ait trails`, `T` opens the same create-or-refresh workflow for the focused
     live member; the trail is written only after you confirm the agent's proposal".
   - `:63`: unchanged (the skill output is still the board pointer).
   - `:82` heading "Reading a Trail on the Board" → add a sentence: "or run `ait trails` for the
     same view without the board (`j` → `i` from any TUI)".
   - The `S` row in the refresh-cost table gains a "(board only)" note.
10. **`skills/aitask-backlog-roadmap.md:17`**: "the board's By-Trail view" → "the trail viewers
    (`ait trails` and the board's By-Trail view)".

All new internal links use `{{< relref "/docs/..." >}}`. Current-state wording only: no "new in",
no mention of the refactor history. Agent names stay generic.

## Verification

- `cd website && python3 check_links.py --build` exits 0 (mandatory).
- `hugo build --gc --minify` succeeds.
- `python3 check_link_relevance.py` is a triage report; review any hit it reports on the new
  links.
- `python3 tests/lib/docs_vocabulary_scan.py` is clean.
- `python3 -m pytest tests/test_board_reference_doc_literals.py -q` is green.
- `grep -rn 'no \`ait trail\` command' website/content/docs` returns nothing.
- Key grep both ways, recorded in the Final Implementation Notes: every key in
  `trails/reference.md` exists in `TRAIL_BINDINGS` + `TrailsApp.BINDINGS` (or is the modal `a`).
  Every live binding is documented. `i` appears in `tuis/_index.md`.
- **Behavioural claims checklist** (source-backed; re-grep each before publishing and record
  the file:line in Final Implementation Notes — a key grep cannot prove these):
  1. Auto-selection on launch — `trails_app.py` `on_mount` calls
     `call_after_refresh(self._open_trail_select)`.
  2. Cached vs rescanned — `board_trail_screen.py` `action_trail_refresh_local` (`r`) =
     `manager.load_tasks()` + `_rerender_trail` (docstring: "CACHED trail document … no
     artifact read"); `action_trail_select` (`s`) = `_open_trail_select(rescan=True)` →
     `discover_trails()`; `action_trail_refresh_drift` (`d`) = `_reload_active_trail` →
     `load_trail_blob` (re-fetch, read-only).
  3. `T` launches a workflow, not a write — `trails_app.py` `_trail_task_target` →
     `action_trail_task` → `_launch_trail` (`resolve_dry_run_command(... "trail" ...)`
     → confirmation dialog; docstring "The launched skill owns every artifact write (after
     its own confirmation)"); `T` passes no `watch_handle`, so no auto-pickup.
  4. No state hand-off to the board — `aitask_board.py` `_set_base_filter("bytrail")`
     opens the selector only `if self.active_trail_handle is None` (board keeps its own
     trail); `check_action` gates `trail_move_wave` on a focused live (non-ghost) card.
  Any doc sentence contradicting one of these is fixed before commit.
- Step 9 (Post-Implementation): path-scoped commit, gates, archive `t1794_10`.

## Risk

### Code-health risk: low
- None identified. The change is docs only. `check_links.py` and hugo catch broken relrefs and
  anchors, and the board-reference literal test guards the pinned strings.

### Goal-achievement risk: low
- A documented key or context could misstate the shipped behaviour (e.g. the task body's `a` as
  an App key, or `T`/`r` over-claiming what they write or reload). severity: low. → mitigation:
  none needed. The plan's "key grep both ways" step and the source-backed behavioural claims
  checklist (auto-select, cached vs rescanned, `T` launches a workflow) already cover it.
