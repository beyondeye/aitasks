---
priority: medium
effort: medium
depends: [t1647_5]
issue_type: documentation
status: Ready
labels: [trails, web_site, docs]
gates: [risk_evaluated]
anchor: 1647
created_at: 2026-09-01 18:51
updated_at: 2026-09-01 18:51
---

## Context

Sixth child of t1647 (trail-to-trail merge). Document the finished feature:
the board `F` command + dialogs (t1647_5), the `/aitask-merge-trails` skill
(t1647_4), the merge workflow, and the RFC's merge flow. Current-state prose
only (aidocs/framework/documentation_conventions.md — no version history, no
"new in" phrasing).

**Coordination:** t1603_5 (Implementing at planning time) edits OTHER
sections of `website/content/docs/tuis/board/reference.md` (Task Card
Anatomy ~94, View Filters ~196, Task Metadata Fields ~397). Disjoint from
this child's sections, but same file — re-verify section anchors against the
landed state before editing.

## Files

1. `website/content/docs/tuis/board/reference.md`
   - By-Trail section (~L242-341): document `F` — add it to the
     "Keeping the view current" key table or an adjacent paragraph, with
     the cost note (launches an agent; the merge happens in the launched
     skill after its own confirmation, never in the board) and the
     visibility conditions (active trail + ≥2 trails).
   - Modal Dialogs Reference table (~L499): the table currently lists NO
     trail modals — close the gap: add rows for **Trail Select** (`s` in
     By-Trail), **Trail Detail** (`Enter` on a trail card), **Trail Merge
     (pick)** (`F` in By-Trail), **Trail Merge Confirm** (confirming the
     pick).
2. `website/content/docs/tuis/board/how-to.md` — By-Trail block
   (~L210-245): a "merge two trails" how-to (focus the surviving trail,
   `F`, pick, confirm, agent completes; where the result appears).
3. `website/content/docs/workflows/implementation-trails.md` — new
   "Merging Two Trails" section: when to merge (duplicate trail; expanded
   scope), the deep-wins depth rule and the downgrade confirmation, what
   retirement means (EVERY referencing task's entry is removed; the
   artifact remains recoverable from data-branch git history), the
   resumable retirement behavior, and the three invocation shapes
   (board `F`, `/aitask-merge-trails <approx-name>`,
   `/aitask-merge-trails <base> <folded>`). Link from the existing flow
   sections; do not restate their content.
4. `website/content/docs/skills/aitask-merge-trails.md` — new skill page
   (model: `aitask-trail.md` sibling page) + a row in
   `website/content/docs/skills/_index.md` (Task Creation & Analysis
   table, next to `/aitask-trail` — the list is manual).
5. `aidocs/implementation_trail_design.md` — add the merge flow to the RFC:
   invocation surfaces, the candidates/preflight line protocol (summary,
   pointing at the module docstrings as the pinned source),
   `merged_from` + `generation.inputs` provenance, deep-wins, the
   confirmation + stale-base guard + all-owner retirement semantics, and
   the RESUME/merge_conflict states. Keep §13 (alternatives) consistent:
   merge is explicit user intent, never auto-dedup (A6 stands).

## Tests / checks

- `cd website && hugo build --gc --minify` succeeds. Hugo does NOT fail on
  dead `#fragment` anchors and `--minify` unquotes `id=` — verify any
  in-page anchors manually (project memory: hugo_anchor_checks).
- `python3 -m unittest tests.test_implementation_trail_design` still green
  (the RFC edit must not break the design-contract guard).
- Grep sweep: no "superseded/replaced" language for folded trails — use
  "merged/incorporated/retired" per the folded-task vocabulary; describe
  the supported agents generically per documentation_conventions.

## Verification

- Hugo production build clean; new page renders in the local dev server
  (`cd website && ./serve.sh`) with working relrefs.
- The skills index row links resolve; the workflows page section reads as
  one flow with the existing page.

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1725_6** id=2026-09-10T18:36:37Z.ce0c66ed8d50dd4f1c848fd6 from=t1725_6 at=2026-09-10T18:36:37Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting.
> | 
> | 1. The t1603_5 coordination is obsolete: t1603_5 landed (2697ec612).
> | 
> | 2. Line refs drifted: tuis/board/reference.md By-Trail is ~249-389 (not
> |    242-341); the "Keeping the view current" table is ~285-294 (still five
> |    keys); Modal Dialogs Reference is ~655 (not ~499). how-to By-Trail block is
> |    ~215-255.
> | 
> | 3. skills/_index.md has no "Task Creation & Analysis" table; /aitask-trail sits
> |    under § Task Management (row ~50).
> | 
> | 4. The Modal Dialogs table still lists no trail modals, and your four planned
> |    rows miss the `v` trail-summary dialog (reference.md ~39).
> | 
> | 5. Follow the plan, not the body, on provenance: implementation_trail.schema.json
> |    ~119 supports the plan's step-5 correction. RFC §13 A6 is about "many trails
> |    per task; one active trail" and the RFC has no merge/dedup text, so "never
> |    auto-dedup" must be added, not kept. `merged_from` is absent from the §6
> |    field groups.
> | 
> | 6. SHARED: t1725_6 adds a "Sync Deferred" row to the same Modal Dialogs table
> |    (after Sync Conflict) — different rows, adjacent-edit rebase. t1363 edits
> |    how-to § How to Generate a Work Report, not your block. t1687 (Concepts gap
> |    sweep) may write a trails concept page; add a merge line to it if it lands
> |    first.

> **✉ note:t1794_9** id=2026-09-22T06:08:26Z.3dddbcba014639da6208bc58 from=t1794_9 from_verified=yes at=2026-09-22T06:08:26Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.

> **✉ note:t1687_4** id=2026-09-24T06:22:40Z.50cb0913c192dd012e73802a from=t1687_4 from_verified=yes at=2026-09-24T06:22:40Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | t1687_4 (commit 833ba3c13) added website/content/docs/concepts/implementation-trails.md with no merge line, because merged trails had not shipped to the website and this task owns them. When the merge feature's docs land, that concept page likely needs a merge mention too. Its "Found through its owner" section says a fold copies the artifacts: handle to the primary while the folded task keeps its entry until archival, and discovery dedups one handle across several owners (trail_discovery.py _trail_owner_rank). If merging changes how handles or owners relate, that paragraph may need updating. The workflow page is linked as /docs/workflows/implementation-trails; the concept page slug collides with it, so use the full /docs/concepts/implementation-trails relref path.
