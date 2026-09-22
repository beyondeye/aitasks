---
priority: high
effort: medium
depends: [1569]
issue_type: feature
status: Ready
labels: [backlog, planning, skills, fold]
gates: [risk_evaluated]
anchor: 1569
created_at: 2026-08-27 08:07
updated_at: 2026-08-27 08:07
---

## Goal

Add **fold-candidate detection** to the t1569 background-work roadmap: identify
backlog tasks that touch the same code region and can be **merged (folded) into a
single task**, so one pick clears several backlog entries. Folding same-region
tasks "parallelizes" them — work that would collide file-by-file if run as
separate agents instead lands as one holistic task, with one shadow-review
cycle, one plan, one verification pass. This is an essential ingredient for
backlog-clearing efficiency: it reduces the effective task count and the
per-task overhead (review rounds, context re-acquisition), and presents related
requested changes holistically.

**Scope note:** t1569 Phase 2/3 already name "fold" as a disposition — but only
for *cross-seam redundancy* (duplicates of the same concern). This task adds the
broader signal: **consolidation folding of distinct-but-same-region tasks**.
Integrate this ingredient into t1569's design *before* its decomposition/planning
(t1569 has no plan or children yet), or as an explicit child of its tree if it is
already decomposed by pick time.

## Design findings (verified during exploration)

### The cluster signal is the hot-file-set scan t1569 already plans — used a third way

t1569's settled "one scan, two lanes" design computes a per-task file set
(origin-task git file sets via `verifies:`/`anchor:`/`## Origin` resolution;
plan-file path lists for in-flight tasks) and intersects backlog-vs-in-flight.
Fold clustering is the **same file sets intersected backlog-vs-backlog**
(pairwise overlap among Ready backlog tasks). No new gathering is required.
Per t1569's settled gatherer rule, this is **policy and lives in the roadmap
skill**, not in `lib/trail_gather.py` (the gatherer emits only facts).

### Reuse the fold machinery verbatim — it is complete

- `aitask_fold_validate.sh` is the eligibility oracle: line protocol
  (`VALID:`/`INVALID:<id>:<reason>`), always exits 0, reasons
  `not_found`/`status_*`/`has_children`/`is_self`. Call it to filter cluster
  members — do not reimplement eligibility.
- `aitask_fold_content.sh` (merge) and `aitask_fold_mark.sh` (status `Folded`,
  `folded_into`, transitive folds, `children_to_implement` cleanup) execute the
  fold; cleanup is task-workflow Step 9.
- Eligibility constraint fits the corpus: only standalone parent-level
  `Ready`/`Editing` tasks without children can fold; the ~207 followup-kind
  backlog tasks are nearly all standalone parents.
- The related-task-discovery procedure
  (`.claude/skills/task-workflow/related-task-discovery.md`) is today's
  candidate-discovery UX (labels + semantic similarity, interactive). The
  file-overlap cluster signal is deterministic and complements it; consider
  feeding detected clusters into the same selection UX shape.

### Staleness gates folding — ordering is pinned

`aitask_fold_content.sh` merges **textually** (`## Merged from tN` sections
verbatim). Folding a stale-premise task copies its stale prose into the primary.
Therefore in the disposition pipeline **staleness evaluation must run before
fold recommendation**: a task flagged stale is excluded from fold clusters and
disposed as refresh/postpone instead. Use t1569's narrow advisory premise-drift
signal (behind its small replaceable interface; t1561 adoption follow-up applies
here too). Mirror the `aitask_verification_stale.sh` contract conventions
(tri-state FRESH/ASK_STALE/SKIP, UNKNOWN drives the verdict, SKIP fail-open,
always exit 0).

### Cluster semantics

- **Pairwise overlap → clusters:** decide transitive-closure behavior explicitly
  (A∩B and B∩C but not A∩C — chain or split?). Default conservative: require
  each member to overlap the cluster's union above threshold, or split.
- **Cluster size cap:** textual merge makes large clusters produce giant tasks;
  cap cluster size (e.g., 3–4) and/or total merged effort.
- **Corroborating signal:** `anchor:` equality (topic-group root). t1569
  rejected anchors as a *primary* conflict signal (false positives), but as a
  *confidence booster where file overlap already agrees* it is sound. Same for
  shared labels.
- **Effort/priority coherence:** flag clusters mixing wildly different priority
  or summed effort above a bound; the user decides.

### User control on aggressiveness (explicit requirement)

The user must control how aggressive folding is. Profile-key precedent exists
(`explore_label_confirm`: `ask`/`auto`/`existing_only`; profiles already scope
keys per skill). Provide e.g.:
- a mode knob: `off` / `suggest` (recommend only) / `confirm-batch` (act after
  per-batch confirmation) — mapping onto t1569's phase discipline (Phase 2
  recommends dispositions, Phase 3 acts with per-batch user confirmation;
  advisory-only in Phase 1);
- an overlap-threshold knob (minimum shared-file count or Jaccard fraction);
- a cluster-size cap knob.

### Trail artifact carrier

Phase 1/2 can express clusters with existing schema vocabulary: relations
`coordinates_with` with `provenance: advisory` + a note, and observation kind
`shared_surface_collision`. The relations enum has no `fold_candidate` kind and
exclusions' `reason_code` enum has no fold value (closest `superseded_scope`) —
a dedicated `fold_candidate` relation kind is a possible schema extension to be
decided at planning, not assumed. t1470 (By-Trail intra-wave safety) is the
natural later board surface to render clusters as grouped entries.

## Explicitly rejected

- Reimplementing eligibility or merge logic — `aitask_fold_validate.sh` /
  `fold_content.sh` / `fold_mark.sh` are the seams.
- Putting cluster policy (thresholds, scoring, lane/cluster assignment) into the
  shared gatherer — t1569 settled facts-vs-policy placement.
- Label/anchor overlap as the *primary* cluster signal — file-set overlap is
  primary; labels/anchors corroborate only.
- Automatic folding without user confirmation — every acting mode is gated on
  per-batch confirmation, per t1569's staged-delivery discipline.

## Related

- **t1569** — the backlog roadmap this extends (dependency + anchor). Integrate
  into its design/decomposition rather than building a parallel surface.
- **t1561** — generalized staleness; the fold-safety pre-check adopts it when it
  lands (same adoption path t1569 already mandates).
- **t1343** — declared-claims conflict advisory; better long-term overlap signal,
  adoption follow-up per t1569.
- **t1470** — By-Trail board surface for rendering clusters.
- `.claude/skills/task-workflow/related-task-discovery.md` — existing
  candidate-discovery UX to feed clusters into.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:16Z.45ef5f3821b1ed029e922ad7 from=t1794_9 from_verified=yes at=2026-09-22T06:08:16Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
