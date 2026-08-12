---
priority: high
risk_code_health: high
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, aitask_board, bash_scripts, task_metadata]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1468_5, t1468_6, t1468_7, t1468_8]
created_at: 2026-08-10 08:56
updated_at: 2026-08-12 19:07
---

## Goal

Make it possible to tell, at a glance and from metadata, whether a task is
genuine new work or an **auto-spawned follow-up** (manual verification, risk
mitigation, upstream defect, verification-failure fix, deferred carry-over, QA
test gap, review finding) — so the board and the pick queue can be used to
choose the next task again.

## Problem

The task workflow spawns follow-ups at several checkpoints. They accumulate and
today they are indistinguishable from real work.

Measured on the active corpus (382 tasks, 2026-08-09):

| category | count | marker today |
|---|---:|---|
| manual verification | 68 | `issue_type: manual_verification` + `verifies:` |
| risk mitigation | 53 | **none** |
| upstream defect | 42 | **none** |
| verification-failure fix | 4 | labels `verification,bug` only |
| review finding | 1 | label `review` only |
| **total follow-ups** | **168 (43%)** | |

- **95 of the 168 carry no marker at all.** A risk-mitigation follow-up is
  created with a *real* `issue_type` (observed: `enhancement`, `feature`,
  `test`), labels copied verbatim from the origin task, and `depends: []`.
  Example: `t1066_applink_cert_rotation.md` is `issue_type: enhancement`,
  `labels: [applink, applink_security]` — nothing in its frontmatter says it is
  a mitigation. Only the body prose `Risk-mitigation ("after") follow-up for
  t985` reveals it.
- **The one machine-readable link is a reverse pointer that dies.**
  `risk_mitigation_tasks:` lives on the *origin* task and covers 5 of 53
  mitigation ids; when the origin is archived the link is gone.
- **58 of the 168 have no `anchor`**, so even the board's By-Topic view cannot
  cluster them with their origin. `upstream-followup.md` passes no
  `--followup-of`.
- Only 59 of 382 tasks carry a `boardcol`; the remaining 323 land in the
  synthetic "Unsorted / Inbox" lane. Hand-made workaround columns
  (`manual_verifications`, `tests`, `bug_fixes`) caught 14 of 68 MV tasks —
  manual triage does not scale.

## Design decision to make first: which metadata carrier

Three options were evaluated during exploration. **Record the choice and its
rationale in the plan before implementing.**

### Option A — new `issue_type` values (`risk_mitigation`, `upstream_defect`)

Cheapest to *create*: `validate_task_type` (`aitask_create.sh:1139`,
`aitask_update.sh:870`) just greps `aitasks/metadata/task_types.txt`, and
chatlink's `payload_guard.py:90-92` reads the same file. Adding a value to
`aitasks/metadata/task_types.txt` + `seed/task_types.txt` makes it functional
with zero code change, and stats / codebrowser / applink `task_detail` pick it
up for free.

Against it:
- `issue_type` is a **behavioural dispatch key**, not a tag.
  `filter_gates_for_issue_type` (`lib/task_utils.sh:713-719`) strips gates when
  it is `manual_verification`; `gate_ledger.py:808-831` branches on it; pick
  routes MV tasks to a checklist loop instead of plan+implement.
- It **destroys the true type**: an upstream defect genuinely *is* a bug and
  should get the bug workflow; a mitigation may be a refactor.
- The vocabulary is duplicated across **32+ files** — see
  `aidocs/issue_type_vocabulary_duplication.md` and existing task **t720**
  (`issue_type_list_single_source_of_truth`). Choosing A makes t720 a hard
  prerequisite. Hardcoded per-type behaviour would silently miss a new value:
  `codebrowser/history_list.py:17-27` `_TYPE_COLORS` (8 keys; already drops
  `manual_verification` to the default colour).
- Collides with the `<type>: <desc> (tNN)` commit convention, enumerated by
  hand in 8 prose sites (nothing enforces it in code — only the `(tNN)` suffix
  is machine-consumed).

### Option B — reserved label namespace (`origin:risk_mitigation`)

**Not viable as specified.** `sanitize_label` (`lib/task_utils.sh:572-576`)
applies `s/[^a-z0-9_-]/_/g`, so `:` becomes `_`. Every write path funnels
through it, and chatlink's `_LABEL_RE` (`relay.py:63`) hard-*rejects* rather
than transforms. `tests/test_label_vocabulary_lib.sh:241` pins that every entry
of `labels.txt` is a `sanitize_label` fixed point. A `_`-separated prefix
(`origin_risk_mitigation`) would survive but is unenforceable and
indistinguishable from ordinary vocabulary — `labels.txt` already holds 122
snake_case topical entries.

### Option C — new orthogonal frontmatter field (recommended starting point)

Keeps `issue_type` honest (a bug can be an upstream defect). Cheapest where it
counts on the read side: `parse_frontmatter` (`lib/task_yaml.py:133-165`) is
schema-free and `serialize_frontmatter` preserves unknown keys, so **the board
needs no parser change**.

**Sharp hazard that must be handled in the same change:**
`aitask_update.sh` parses frontmatter with `if [[ "$line" =~ ^([a-z_]+):(.*)$ ]]`
followed by a `case "$key" in` **allowlist** (~`:505-540`), and
`write_task_file` (`:629`) re-emits only from the captured `CURRENT_*` vars.
**Any frontmatter key not added to BOTH the read `case` and `write_task_file`
is silently destroyed on the next unrelated `aitask_update.sh` call.** Note the
key regex also forbids digits and hyphens in the field name.

Follow the checklist in `aidocs/framework/aitasks_extension_points.md`
§"Adding a new frontmatter field". Copy the `--verifies` plumbing as the model:
- `aitask_create.sh` — usage `:115`, arg parse `:183`, and **three** separate
  serializers (`create_child_task_file` param `:485`/emit `:544-549`,
  `create_draft_file` `:612`/`:678-683`, `create_task_file` `:1821`/`:1876-1881`).
- `aitask_update.sh` — usage `:191-193`, arg parse `:341-343`, read `:529-532`,
  `write_task_file` positional `:651` (note: 27 positional args; `verifies` is
  arg 22, `risk_mitigation_tasks` arg 27), emit `:753-758`.
- `aitask_fold_mark.sh` — decide union vs drop. Precedent for both sits in one
  file: `verifies` is unioned (`:189-224`, passed at `:328`) while
  `risk_mitigation_tasks` is explicitly dropped (`:309-310`, `:334`, pinned by
  `tests/test_fold_risk_mitigation_drop.sh`).
- `aitask_archive.sh:595-609` — carry-over re-passes `verifies`; a provenance
  field needs the same or it is lost at carry-over.
- `board/aitask_merge.py` — a field with no explicit rule falls into the generic
  `else` and can be dropped to PARTIAL on a concurrent edit. A semantic scalar
  belongs in **neither** `_LIST_UNION_FIELDS` (`:135`) nor `BOARD_LAYOUT_KEYS` /
  `BOARD_KEYS`. Do **not** add it to `BOARD_KEYS` — `lib/board_columns.py:483`,
  `lib/trail_gather.py:313` and `lib/work_report_gather.py:180` treat
  "metadata ⊆ BOARD_KEYS" as "no real metadata".

A hybrid is legitimate and worth considering: keep `issue_type:
manual_verification` as-is (it already carries workflow semantics and 68 tasks
depend on it) and add the orthogonal field only for the categories that have no
marker.

## Write seams — 2 places, not 6

- **`.claude/skills/task-workflow/task-creation-batch.md`** is the single shared
  creation contract for risk-mitigation (`risk-mitigation-followup.md:385,508`),
  upstream defect (`upstream-followup.md:65`), QA test gap
  (`aitask-qa/follow-up-task-creation.md:28-58`), review findings
  (`aitask-review/SKILL.md.j2:183-221`) and docs-gap. Parent form `:80-93`,
  child form `:97-111`, optional flags `:117-124`. It has **11 rendered copies**
  (claude/codex/opencode × profile, plus goldens) — regenerate via the rerender
  driver (one call per profile) and stage with an explicit path allowlist.
- **Two shell helpers** cover the rest:
  `aitask_create_manual_verification.sh:109-125` and
  `aitask_archive.sh:602-610` (carry-over). Note these never pass `--gates`,
  while the batch procedure auto-injects the profile's `default_gates` — an
  existing asymmetry worth preserving deliberately.
- `aitask_verification_followup.sh:208-214` creates the verification-failure
  bug task.

## Board rendering — 1 seam, with a precedent to copy

- `TaskCard.compose` (`board/aitask_board.py:2625-2729`) is the only place a
  normal card's visible text is built. The title row (`:2634-2643`) is
  `[☑] [t1066] [title]`; the badge line (`:2645-2659`) is already crowded with
  `💪 effort | 🏷️ labels | GH | PR | @contributor`.
- **Precedent:** `TRAIL_CLASSIFICATION_GLYPHS` (`:612-618`) — single-width
  geometric glyphs `◆ ▲ ● ⇄ ○` keyed by a classification enum, rendered via
  `_trail_badge_text` (`:2912-2918`) with a `·` fallback, pinned by
  `tests/test_board_bytrail_view.py`. Mirror this rather than inventing emoji;
  a leading gutter glyph in the title row keeps cards scannable and aligned.
- Constraints:
  - `markable=True` is set **only** in `KanbanColumn.task_block` (`:3519`), so
    the glyph must not hang off the ☑/☐ mark — `TopicColumn` and
    `InFlightColumn` cards have no mark.
  - Subclasses `InFlightTaskCard` (`:2786`), `TrailTaskCard` (`:2956`) and
    `TrailGhostCard` (`:3006`) do **not** call `TaskCard.compose` — decide
    per-surface whether they show the glyph.
  - Verify at render level (`render().plain` + composited strips for width
    *and* colour), not by reading source.
- **In-flight collision:** t1243 board task-groups is uncommitted in the working
  tree (`lib/board_groups.py`, `GroupHeader` at `:2314-2354`, `boardgroup` key,
  448 changed lines). A collapsed group mounts no member cards, so the glyph is
  invisible there — consider whether `GroupHeader._label()` needs a kind
  summary. **Land this after or alongside t1243, not into a conflicting tree.**

## Beyond the board — surfaces that are structurally blind

| surface | today | needs work? |
|---|---|---|
| `aitask_ls.sh` (`ait ls`) | parses `issue_type` at `:310-312`, then **never reads it again** — dead metadata. No `--type` filter. Sort is blocked→priority→effort only (`:508`, `:576`). Help text `:60` still omits `manual_verification`. | **yes** — display, filter, maybe sort |
| `/aitask-pick` Steps 2a-2d | presents `[Priority, Effort, Status]` only (`SKILL.md.j2:157-160`, `:173-180`) — the human choosing work cannot see the kind | **yes** |
| work report | `work_report_gather.py` protocol (`:14`) has no `issue_type`; groups by board column only | **yes** (new pipe field; use `enum_field()` per `record_protocol.py`) |
| minimonitor / applink "next sibling" chooser | `find_ready_siblings` (`monitor_core.py:3260-3262`) drops the type although frontmatter is parsed at `:3305`; `router.py:650-653` inherits the gap | **yes** |
| aitask-trail | `implementation_trail.schema.json` entry `snapshot` is `additionalProperties: false` with no `issue_type`; `schema_version` is `const 1.0.0` | **yes, most expensive** |
| monitor `TaskDetailDialog` / `TaskPickConfirmDialog` | already shows `Type:` (`monitor_shared.py:866-869`); the confirm dialog subclasses it | no |
| `ait stats` / stats-TUI | drives off `task_types.txt` (`lib/stats_data.py:875-887`) | no |
| applink `task_detail` | ships `issue_type` (`router.py:676`) | no |
| codebrowser history detail | reads it, with a colour fallback | no |

Scope which of these are in-scope for this task versus deferred — the board
plus `ait ls`/pick is the minimum that addresses the stated pain.

## Backfill of the 168 existing follow-ups

Forward-only marking leaves the current backlog unchanged, which is where the
pain actually is. Retro-classification is viable and precise — the creation
templates emit stable prose:

| category | detection |
|---|---|
| manual verification | `issue_type: manual_verification` (68) |
| risk mitigation | body matches `Risk-mitigation \("(before\|after)"\)` (53) |
| upstream defect | body has `^## Upstream defect` or `Spawned from t<id> during Step 8b review` (42) |
| verification failure | body has `^## Failed verification item from t` (4) |
| carry-over | body has `Carry-over of deferred manual-verification items` (7, subset of MV) |

Precision spot-check: 41 of 42 upstream-defect hits carry the exact Step 8b
sentence; the single outlier (`t1246_fix_codeagent_tests_v5_model_drift.md`) is
still a genuine upstream defect written in freeform prose.

Deliver the backfill as a **one-shot, reviewable script** (dry-run first,
printing a per-task classification table), not a hand edit of 168 files. It must
write through the sanctioned update path so nothing else in the frontmatter is
lost.

## Acceptance criteria

1. A recorded design decision (in the plan) naming the chosen carrier and why
   the two rejected options were rejected.
2. Every auto-spawned follow-up created from that point carries a
   machine-readable kind, set at **both** write seams (shared batch procedure +
   the shell helpers), with the rendered skill copies regenerated in the same
   commit.
3. If a new frontmatter field is chosen: it survives an unrelated
   `aitask_update.sh` round-trip (regression test), survives fold and archive
   carry-over per an explicit documented decision, and has an explicit
   `board/aitask_merge.py` rule.
4. The board card shows a single-width kind glyph, verified at render level
   (`render().plain` plus composited strips), with an unknown/absent value
   falling back safely. Behaviour under a collapsed t1243 group is decided and
   documented.
5. `ait ls` surfaces the kind and can filter on it; the `/aitask-pick`
   presentation template shows it. Other blind surfaces are either done or
   explicitly deferred with a stated disposition.
6. A dry-run-first backfill script classifies the 168 existing follow-ups, with
   its classification table reviewed before any write.
7. Docs updated across the drifting surfaces named in
   `aidocs/framework/aitasks_extension_points.md` §5.

## Related tasks (not folded — each has its own deliverable)

- **t720** `issue_type_list_single_source_of_truth` — de-duplicates the
  `issue_type` vocabulary across 32+ files. **Becomes a hard prerequisite if
  Option A is chosen**; independent otherwise. Add a `depends:` edge at planning
  time if the design lands on A.
- **t1287** `manual_verification_path_skips_upstream_defect_followup` —
  manual-verification tasks never reach Step 8b, so defects noticed *while
  verifying* are buried. Same follow-up machinery, different defect; fixing it
  would add another source of upstream-defect tasks that this task must mark.

## Exploration notes

- Existing partial hooks worth reusing rather than reinventing: `verifies:`
  (63 tasks), `risk_mitigation_tasks:` (reverse pointer on the origin),
  `--followup-of` (sets `anchor` to the topic root — grouping, *not* kind), and
  an `upstream_defect_followup` entry already sitting unused in `labels.txt`.
- `aitask_create.sh --followup-of` is passed by `aitask_verification_followup.sh`
  and `aitask_archive.sh` but **not** by `upstream-followup.md` — which is why
  58 follow-ups are topic roots. Adding it there is a cheap independent
  improvement.
