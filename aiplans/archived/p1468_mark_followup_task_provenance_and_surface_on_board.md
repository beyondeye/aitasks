---
Task: t1468_mark_followup_task_provenance_and_surface_on_board.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1468 — Mark follow-up task provenance and surface it on the board

## Context

**171 of 385** active tasks (44%) are auto-spawned follow-ups — the task file's
"168 of 382" re-measured today, which is itself the point: the ratio is growing.
They are manual verification,
risk mitigation, upstream defect, verification-failure fix, QA test gap, review
finding, deferred carry-over. **95 of them carry no marker at all**, so the board
and the pick queue can no longer be used to choose the next piece of *new* work:
a risk-mitigation follow-up is created with a real `issue_type`, labels copied
verbatim from its origin, and `depends: []` — nothing in its frontmatter says
what it is. The one machine-readable link (`risk_mitigation_tasks:`) is a reverse
pointer on the *origin* task that covers 5 of 53 ids and dies when the origin is
archived.

The outcome: every auto-spawned follow-up carries a machine-readable kind from
creation, every read surface can show and filter on it, and the 168 already in
the backlog are classified retroactively.

This plan **decomposes the work into 6 child tasks**. It records the design
decision (acceptance criterion 1) that all six inherit.

---

## Design decision: which metadata carrier

**Chosen — a new orthogonal scalar frontmatter field `followup_kind:`**, set
**uniformly on every auto-spawned follow-up**, including manual-verification
tasks (which keep `issue_type: manual_verification` as well — that value carries
real workflow dispatch semantics and 68 tasks depend on it). One field answers
"is this new work?" everywhere, with no per-surface special case.

Verified cheap on the read side: `parse_frontmatter` / `serialize_frontmatter`
(`lib/task_yaml.py:134-203`) are schema-free and preserve unknown keys, so
**every Python consumer — board, merge, columns, trail, work report, stats,
codebrowser, monitor — round-trips the field for free**. The bash layer is the
only place a key dies.

**Rejected — Option A, new `issue_type` values.** `issue_type` is a *behavioural
dispatch key*, not a tag: `filter_gates_for_issue_type`
(`lib/task_utils.sh:713-719`) strips gates on `manual_verification`,
`gate_ledger.py:808-831` branches on it, and pick routes MV tasks to a checklist
loop. It also destroys the true type — an upstream defect genuinely *is* a bug
and deserves the bug workflow. The vocabulary is duplicated across 32+ files, so
this would make **t720** (`issue_type_list_single_source_of_truth`) a hard
prerequisite, and hardcoded per-type tables would silently miss a new value
(`codebrowser/history_list.py:17-27` already drops `manual_verification` to the
default colour).

**Rejected — Option B, reserved label namespace (`origin:risk_mitigation`).**
Not viable as specified: `sanitize_label` (`lib/task_utils.sh:572-576`) applies
`s/[^a-z0-9_-]/_/g` so `:` becomes `_`; chatlink's `_LABEL_RE` (`relay.py:63`)
hard-*rejects* rather than transforms; and `tests/test_label_vocabulary_lib.sh:241`
pins every `labels.txt` entry as a `sanitize_label` fixed point. A `_`-separated
prefix would survive but is unenforceable and indistinguishable from the 122
existing snake_case topical entries.

### Supporting decisions

| Decision | Choice | Why |
|---|---|---|
| Vocabulary home | **one data file** `.aitask-scripts/lib/followup_kinds.tsv` (`kind` · `glyph` · `colour` · `label`), read by both bash and Python | Values are framework-semantic — each is produced by one specific seam — so users must *not* extend them. A single file avoids the 32-file duplication that makes `issue_type` unmaintainable, and needs no `ait setup` / seed / upgrade plumbing (unlike `aitasks/metadata/*.txt`). |
| Values | `manual_verification`, `risk_mitigation`, `upstream_defect`, `verification_failure`, `carry_over`, `qa_test_gap`, `review_finding`, `docs_gap` | One per creation seam found in the audit. |
| **Colour authority** | the **TSV `colour` column only**, applied programmatically as `Text(glyph, style=<colour>)`; CSS carries *layout only* (width / margin), never colour | Textual CSS cannot read the TSV, so a `.fk-<kind>` colour class would be a second, unsynchronisable source that a key-only drift test cannot catch. One authority makes drift impossible instead of merely detectable, and a literal style resolves in both `render().spans` and composited strips (an unresolved CSS colour name resolves in neither). |
| **`manual_verification` cross-field invariant** | `followup_kind: manual_verification` ⇒ `issue_type: manual_verification`, **enforced at both write seams**; the reverse is *not* required (an MV task may legitimately be `carry_over`) | The two fields are independently settable, so without this a task could show the MV glyph while taking the bug/feature workflow. Enforce where it can be made impossible (create + update); **tolerate at read** — the board normaliser must not crash on a hand-edited inconsistency — and have the backfill report any pre-existing violation as residue. |
| `write_task_file` plumbing | append as positional **arg 33** | `aitask_update.sh:660-665` states the convention explicitly: inserting mid-list silently renumbers every read above. |
| `aitask_create.sh` plumbing | read a **global** in the three renderer bodies, not a 17th positional | The three serializers have divergent positional numbering; `gates`, `anchor`, `xdeps` already use the global pattern. |
| Merge rule | **base-aware**, mirroring `boardgroup` — add to `_BASE_AWARE_FIELDS` (`aitask_merge.py:164`) and resolve via the existing `_resolve_base_aware` | **Newer-`updated_at`-wins is wrong here.** `merge_frontmatter` resolves one-sided presence at `:289-294`, *before* any field rule, and the code says so at `:268-270`: that branch "is unconditional and would resurrect a value the other side deliberately cleared." Since a misclassification must be correctable — including clearing the field — a clear has to survive sync, which only base comparison delivers. It also fails closed to `PARTIAL` when both sides changed it differently. `anchor`'s newer-wins rule carries this latent bug; this field must not copy it. Still goes in **none** of `_LIST_UNION_FIELDS`, `BOARD_LAYOUT_KEYS`, `BOARD_KEYS` — `board_columns.py:483`, `trail_gather.py:313` and `work_report_gather.py:180` read "metadata ⊆ BOARD_KEYS" as "no real metadata". |
| Fold | **not unioned** — no-op, documented beside the `anchor` / `boardgroup` comments at `aitask_fold_mark.sh:315-323` | It is a scalar and instance-specific provenance; the primary keeps its own. Folded files are deleted at archival anyway. |
| Board marker | title-row **gutter glyph, coloured** — shape *and* colour, so a follow-up is recognisable at a glance | User decision. Colour carries "this is a follow-up" as one visual signal; shape distinguishes which kind. |

---

### Pre-phase (risk mitigations)

The plan's first implementation steps. Each is a confirmed **inline** mitigation
and belongs to the named child — it runs *before* that child's main work, not as
a separate task.

- **`negctrl_field_destruction`** (in **t1468_1**, before touching any
  registration site). Write the round-trip test in its **final form** first —
  hand-add a `followup_kind:` line to a fixture task, run an unrelated
  `ait update --status`, and assert the field **survives**. Run it before any
  registration and confirm it goes **RED**, recording the failing test id and
  message. Then register the field and confirm it goes GREEN with the assertion
  **byte-unchanged**. Asserting the *destroyed* state instead would pass while
  the bug is present, which proves nothing — a negative control that passes
  before the fix is not a control.
- **`characterize_pipe_record_consumers`** (in **t1468_5**, before editing
  either record). **Two** pipe-delimited records gain a field in this child, both
  with the free-text-field-last rule and both consumed with a fixed maxsplit:
  `work_report_gather.py`'s `TASK:` (consumers: the `/aitask-work-report` skill
  and the board `w` flow) and `trail_gather.py`'s `MEMBER:` (consumer: the
  `aitask-trail` skill writer). Enumerate every consumer of **both** and pin the
  current field indices in a characterization test first, so each insertion fails
  loudly at any consumer that was missed rather than silently re-reading the
  path.
- **`trail_v1_clean_rejection_fixture`** (in **t1468_5**, before editing either
  schema copy). The trail is single-version by design, so the goal is **not**
  backward acceptance — it is that the bump fails *loudly and correctly*. Add a
  fixture document pinned at `schema_version: 1.0.0` and assert that after the
  bump it is rejected as `ERROR:invalid_trail` on the `const` rule — never
  silently accepted, and never surfacing as a false `STALE`. Pair it with a lock
  tripwire asserting `SCHEMA_NORMALIZATION_LOCK` has exactly one entry keyed by
  the schema's own `const`.
- **`backfill_single_revertible_commit`** (in **t1468_6**, before `--apply`).
  Require a clean working tree, then land **two separate commits** — the
  framework forbids mixing code with task/plan files, and task data lives on the
  `aitask-data` branch:
  1. the backfill script itself, via plain `git`;
  2. the field writes **plus** the reviewed classification table, via one
     `./ait git` commit over task data only.

  The table is not a loose artifact: the script writes it into the child's plan
  file (`aiplans/p1468/p1468_6_*.md`, "Final Implementation Notes"), which is
  already on the data branch and is the framework's durable record. A
  mis-classification is then a revert of commit 2 alone.

## Child task breakdown

Six children, implemented in order (siblings auto-depend). **t1468_1 is the
riskiest and most foundational — it is the spike; nothing else is meaningful
until the field survives a round-trip.**

### t1468_1 — `followup_kind` frontmatter field foundation

The whole point of failure. `aitask_update.sh` parses frontmatter with an
allowlist `case "$key" in` (`:511-579`, **no default arm**) and rebuilds it from
literal `echo`s in `_ait_write_task_file_body` (`:695-841`). **Any key not
registered in both is silently destroyed by the next unrelated `ait update`** —
only `attachments:` / `artifacts:` are rescued, via `extract_frontmatter_block()`
(`:614-627`, re-printed at `:812-819`).

- Create `.aitask-scripts/lib/followup_kinds.tsv` + a reader in
  `lib/task_utils.sh` (bash) and `lib/task_yaml.py` or a small
  `lib/followup_kinds.py` (Python). Both read the **same file** — no second copy.
- `aitask_create.sh`: global near `:48`; usage near `:115`; `--followup-kind`
  parse near `:191`; enum validation at the `resolve_anchor` call site `:2017`;
  emit from the global in **all three** serializers (`:556`, `:693`, `:1892`),
  mirroring the `RESOLVED_ANCHOR` blocks exactly.
- `aitask_update.sh`: globals near `:92`; usage near `:241`; parse near `:356`;
  read arm in the `case` near `:560`; **arg 33** on `write_task_file` (`:629-665`);
  emit near `:792`; **all three** call sites (`:1170`, `:1688`, `:2118`);
  `has_update` near `:1796`; batch merge near `:2022`; validation near `:2257`.
- **Cross-field validation** in both `aitask_create.sh` and `aitask_update.sh`:
  reject `--followup-kind manual_verification` unless the resulting
  `issue_type` is also `manual_verification` (checking the *resulting* value, so
  an update that changes only one of the pair is caught). Named error, non-zero
  exit, file byte-unchanged. The reverse pairing stays legal.
- `aitask_fold_mark.sh`: no-op comment beside `:315-323`.
- `board/aitask_merge.py`: base-aware, **but `_resolve_base_aware` as written
  cannot express deletion** and must not simply be reused. Two defects for this
  field:
  1. `present` (`:194-196`) is `False` only when **neither** side carries the
     key. When the winning side *deleted* it, the resolver returns
     `local_meta.get(key)` → `None`, and `serialize_frontmatter` then writes a
     literal `followup_kind: null` instead of removing the line.
  2. It compares through `normalize_group_slug` — boardgroup's tombstone
     semantics, wrong vocabulary for this field.

  Fix: make the resolver **deletion-aware and normaliser-parameterised** —
  return the *winning side's* presence separately from its value, and take the
  comparison normaliser as an argument. Keep `boardgroup`'s behaviour
  byte-identical (it relies on its persisted `""` tombstone); `followup_kind`
  passes its own `normalize_followup_kind`. Clearing is **key removal**, not a
  tombstone — the emit block follows the `anchor` `if [[ -n … ]]` pattern, so an
  empty value omits the line.

  Leave the `anchor` branch at `:312-315` alone; do **not** generalise it into a
  newer-wins set.

  Tests, extending `tests/test_aitask_merge_boardgroup.sh` and
  `tests/test_aitask_merge.py`:
  - one side clears + other unchanged ⇒ **`"followup_kind" not in merged`** —
    assert key *absence*, not `== None`, and assert the serialized file has no
    `followup_kind:` line at all. (This is the case both newer-wins and a naive
    base-aware reuse get wrong, in two different ways.)
  - both sides changed differently ⇒ `PARTIAL:followup_kind`.
  - no base available ⇒ `PARTIAL` naming the field.
  - `boardgroup`'s existing cases still pass unchanged (regression guard on the
    shared resolver).
- Docs — every layer-5 surface in `aidocs/framework/aitasks_extension_points.md:42-60`:
  `seed/aitasks_agent_instructions.seed.md` (then regenerate the `AGENTS.md`
  mirror via `ait setup`), the markerless `.codex/instructions.md` and
  `.opencode/instructions.md` (hand-edit), `CLAUDE.md` "Task File Format",
  `website/content/docs/development/task-format.md`, the extension-points
  checklist itself (add `followup_kind` as a third worked example beside
  `anchor`), the `task-creation-batch.md` Input table, and the flag list in
  `.claude/skills/aitask-create/SKILL.md`.
- **Tests** — clone the three existing pins:
  `tests/test_gate_frontmatter_roundtrip.sh` (durability under an *unrelated*
  `--status` update — the canonical hazard test), `tests/test_anchor_update.sh`
  (set / normalize / clear / read-modify-write, plus bad value rejected with the
  file byte-unchanged), and the `test_aitask_merge.py:141-155` newer-wins pair.
  Add a negative control: an *invalid* kind is rejected non-zero and writes
  nothing.

### t1468_2 — Set the kind at every creation seam

Twelve seams, verified. Nine route through the shared batch procedure; three are
shell helpers.

- `.claude/skills/task-workflow/task-creation-batch.md` (**source**; it is a
  `.md` but is Jinja-rendered): add the `followup_kind` row to the Input table
  (`:7-23`) and the flag to `### Optional flags` (`:115-124`).
- Callers: `risk-mitigation-followup.md:385-392` and `:505-515` →
  `risk_mitigation`; `upstream-followup.md:67` → `upstream_defect`;
  `aitask-qa/follow-up-task-creation.md:30` → `qa_test_gap`;
  `aitask-review/SKILL.md.j2:183,199,213` → `review_finding`;
  `aitask-docs-gap/SKILL.md:160-170` → `docs_gap` (**this seam bypasses the
  shared template entirely** — inline the flag there and note the divergence).
- Shell helpers: `aitask_create_manual_verification.sh:108-131` →
  `manual_verification`; `aitask_archive.sh:602-610` (`create_args`) →
  `carry_over`; `aitask_verification_followup.sh:208-216` →
  `verification_failure`.
- **Cheap independent fix, in scope here:** `upstream-followup.md` passes no
  `--followup-of`, which is why 58 follow-ups are topic roots invisible to the
  board's By-Topic view. Add it.
- Regenerate: `./.aitask-scripts/aitask_skill_rerender.sh <profile>` — **one call
  per profile** (`default`, `fast`, `remote`; the driver takes a *positional*
  profile name and loops all three agent trees internally). `task-creation-batch.md`
  has **9 rendered copies** and no goldens of its own, but its *callers* do —
  regolden `tests/golden/procs/task-workflow/risk-mitigation-followup-*.md` and
  `tests/golden/skills/aitask-review/SKILL-*-claude.md`. The three `remote`
  copies are force-tracked and must be committed. Run
  `./.aitask-scripts/aitask_skill_verify.sh`. **Stage with an explicit path
  allowlist** — the sweep touches many files.
- **Tests must cover every seam, not two.** A seam that silently omits
  `--followup-kind` still renders consistently and keeps `aitask_skill_verify.sh`
  green, so the sweep proves nothing on its own. Two complementary,
  **table-driven** suites keyed by `(seam → expected kind)`:
  1. **argv assertions** for the three shell helpers — stub `aitask_create.sh`,
     log argv, assert the expected `--followup-kind` value.
     `tests/test_archive_carryover.sh` already has exactly this stub-and-log
     harness (`:32-90`) to copy: `aitask_archive.sh` → `carry_over`,
     `aitask_create_manual_verification.sh` → `manual_verification`,
     `aitask_verification_followup.sh` → `verification_failure`. Add a real-file
     assertion for at least one, per `tests/test_archive_carryover_anchor.sh`.
  2. **rendered-content assertions** for the six skill caller paths — grep the
     *rendered* profile variants (not the source) for the expected
     `followup_kind` value at each call site:
     `risk-mitigation-followup.md` Part 2 → `risk_mitigation`, Part 3 →
     `risk_mitigation`, `upstream-followup.md` → `upstream_defect`,
     `aitask-qa/follow-up-task-creation.md` **both branches** (child and parent)
     → `qa_test_gap`, `aitask-review/SKILL.md.j2` **all three** sites →
     `review_finding`, `aitask-docs-gap/SKILL.md` → `docs_gap`.
     The table must be exhaustive by construction: fail if a listed seam is
     missing *or* if a `Batch Task Creation Procedure` call site exists that the
     table does not name.

### t1468_3 — Board card kind glyph (shape + colour)

- Glyph/colour maps derived from `followup_kinds.tsv`, mirroring
  `TRAIL_CLASSIFICATION_GLYPHS` (`aitask_board.py:609-618`) and
  `_trail_badge_text` (`:2912-2919`) with a safe fallback for an unknown value.
- **Colour comes from the TSV, not from CSS.** Build the gutter label as
  `Label(Text(glyph, style=<tsv colour>))` — one authority, so glyph and colour
  cannot drift apart, and the literal style resolves in `render().spans` *and*
  in composited strips. Add a single shared CSS class for **layout only**
  (`width: auto; margin: 0 1 0 0;`) beside `.task-mark` / `.task-number` at
  `:6808-6810`. Do **not** introduce per-kind `fk-<kind>` colour classes.
- A **totality boundary** normaliser (copy `normalize_group_slug`,
  `lib/board_groups.py:63-99`) — `task_yaml` leaves values type-honest, so a
  hand-edited field can arrive as `None`, list, dict, int or bool. Never read the
  raw value in `compose`.
- `TaskCard.compose` (`:2632-2641`): gutter `Label` in the title row, **after**
  the ☑/☐ mark and before the task number, carrying the single layout-only class
  `task-followup-glyph` (see the colour-authority decision above — no per-kind
  CSS class). It must **not** hang off the mark —
  `markable=True` is set only in `KanbanColumn.task_block:3534`; `TopicColumn`
  cards have no mark. Metadata needs no plumbing: `TaskCard` reads
  `self.task_data.metadata` unfiltered (`:2626`).
- **Per-surface behaviour — decided now, not at implementation time.** All three
  subclasses **fully override** `compose` (no `super()` call), so each needs the
  glyph added explicitly; none inherits it. The marker is the board's primary
  differentiator, so "normal cards only" is not acceptable:

  | card | decision | data source |
  |---|---|---|
  | `TaskCard` (`:2625`) — kanban, topic, child | **must show** | `self.task_data.metadata` |
  | `InFlightTaskCard` (`:2786`) | **must show** | `InFlightItem.task` (`:104`) is the **real `Task`** — read `item.task.metadata`; no new plumbing |
  | `TrailTaskCard` (`:2956`) | **must show** | `__init__` passes `view.task` to `super()`, so `self.task_data` is the real `Task` — read frontmatter, **not** the trail snapshot |
  | `TrailGhostCard` (`:3006`) | **shows no glyph, by design** | `_GhostTaskStub.metadata` is `{}` (`:2905`). A ghost is a referenced task with no local file — there is nothing to classify and nothing to pick. Test that it renders cleanly *without* a glyph and does not crash on the empty-metadata fallback. |
  | `GroupHeader` (`:2314`) | **must show a roll-up** | `self.members` (task data) |

  Reading frontmatter rather than the trail snapshot on `TrailTaskCard`
  **removes any dependency of this child on t1468_5** — the snapshot field added
  there serves the trail *document*, not board rendering.
- **Collapsed groups:** `KanbanColumn.compose:3500-3517` mounts no member cards
  when a group is collapsed, so the glyph is invisible there. Add a roll-up to
  `GroupHeader._label()` (`:2340-2342`) — it already carries `self.members` as
  data for exactly this purpose (`· 1 follow-up`).
- **Verify at render level, on every surface in the table above** — one test per
  card class, not just `TaskCard`: `label.render().plain` for the glyph (copy
  `tests/test_board_marking.py` `MarkGlyphRenderTests:159`; the per-card `CardApp`
  harness at `tests/test_board_bytrail_view.py:411-431` and
  `tests/test_board_inflight_view.py:225-249` already exist for the two override
  classes) **plus composited strips** for width *and* colour (`_screen_rows`,
  `test_board_bytrail_view.py:101-112`). Include the ghost's no-glyph case and a
  collapsed-group roll-up case. Pin glyph uniqueness and single-cell width, and
  add a drift guard: map keys == `followup_kinds.tsv` (precedent:
  `test_board_bytrail_view.py:184`).

### t1468_4 — `ait ls` and `/aitask-pick`

- `aitask_ls.sh`: parse arm beside `:310`; display suffix at `:503` (copy the
  `risk_info` / `assigned_info` idiom at `:479-502`); a `--followup-kind` filter
  in `process_task_file` using the early-`return` idiom (`:450-466`) — one edit
  serves all four listing modes; help text `:35-66`. **Display-only, not a sort
  dimension**, mirroring the explicit `risk` precedent at `:229`.
- Fix the dead metadata while here: `issue_type_text` is parsed at `:311` and
  **never read** (`grep` confirms writes at `:235`, `:311`, `:404` only). Surface
  it and add a `--type` filter — the task names this surface as needing display,
  filter, and possibly sort.
- Unknown long flags hard-fail at `:112-131`, so both new flags must be added to
  the `case`.
- `.claude/skills/aitask-pick/SKILL.md.j2`: the `-v` format note (`:157-160`) and
  the Step 2b presentation template (`:173-180`). Rerender per profile + regolden
  `tests/golden/skills/aitask-pick/SKILL-*-claude.md`.
- Tests: no test asserts the `-v` display line as a whole and **none exercises
  `-l/--labels` at all**. Copy the substring-assertion style of
  `tests/test_xdeps_blocking.sh:114-125` (with `assert_not_contains` negative
  controls) and cover both filters.

### t1468_5 — Remaining read surfaces

- **Work report** — `lib/work_report_gather.py` `TASK:` record. The protocol
  rule is "at most one free-text field, always LAST", and `<task_file_path>` is
  last, so the new field goes **immediately before it** and every consumer's
  fixed-maxsplit index shifts: the `/aitask-work-report` skill and the board's
  `w` flow. Use `enum_field()` (`lib/record_protocol.py:128`).
- **Minimonitor / applink sibling chooser** — `find_ready_siblings`
  (`monitor/monitor_core.py:3260-3262`) drops the type although frontmatter is
  parsed at `:3305`; `applink/router.py:650-653` inherits the gap. Carry the
  kind through the row tuple and into the `pick_next_sibling` payload.
- **aitask-trail** — the most expensive item, and the one whose compatibility
  story must be decided *before* any edit. The trail is deliberately
  **single-version**: `load_schema` (`lib/trail_schema.py:143-145`) reads exactly
  one `schema_version` **`const`**; `SCHEMA_NORMALIZATION_LOCK`
  (`lib/trail_gather.py:155`) is `{"1.0.0": "1.0.0"}`; and the module docstring
  (`:107-109`) states the intent outright — *"old-schema trails fail validation
  (ERROR:invalid_trail) -- never a false STALE."* `tests/test_trail_schema.py:160`
  pins const-ness by asserting a `2.0.0` document is rejected on the `const` rule.

  **Therefore: bump, do not dual-accept.** A multi-version loader would mean
  turning `const` into an enum, giving the lock two entries, and rewriting the
  tripwire — fighting a deliberate design property for no gain.
  - Edit **both identical copies** (`aidocs/` and `.aitask-scripts/lib/`).
  - Add `followup_kind` as an **optional** property of `entry.snapshot`
    (`additionalProperties: false`), enum-derived from `followup_kinds.tsv`.
  - Bump the `const` to `"1.1.0"`; set `SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}`.
  - **`NORMALIZATION_VERSION` stays `"1.0.0"`** — the lock's stated contract is
    that a *normalization* bump requires a schema bump, not the reverse. This
    holds **only if `followup_kind` does not enter the normalized digest**; keep
    it out (it is display provenance), and say so in the lock comment. If it must
    enter the digest, `NORMALIZATION_VERSION` bumps too and all stored digests
    become incomparable.
  - Writer emits `1.1.0`.
  - **Plumb the producer, not just the schema.** A schema property with no
    producer validates perfectly while carrying nothing, and the enum drift
    guard cannot see a missing producer — it only checks the vocabulary. Both
    halves are required:
    1. **Gatherer** — `lib/trail_gather.py`'s `MEMBER:` record is
       `MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<path>`
       (docstring `:28`). Add `<followup_kind>` **immediately before `<path>`**
       (the one free-text field must stay last) via `enum_field()`
       (`lib/record_protocol.py:128`). This is the *same* fixed-maxsplit shift
       hazard as the work-report record — see the extended pre-phase mitigation.
    2. **Skill writer** — `.claude/skills/aitask-trail/SKILL.md.j2` must place
       the value into each generated `entry.snapshot`. Rerender per profile and
       regolden `tests/golden/skills/aitask-trail/SKILL-*-claude.md`.
  - **Not a drift dimension.** Keep `followup_kind` out of
    `GATHERER_DRIFT_CODES` and out of `_reconstruct_old_records`'s completeness
    requirement (`:777-781`, currently status + depends + gates_pending) — it is
    display provenance, not ordering-relevant, and adding it would make every
    pre-existing snapshot "incomplete" and force lossy reconstruction.
  - **End-to-end producer test** (the one that would have caught this): mark a
    fixture task with a known `followup_kind`, generate/refresh a trail from it,
    and assert the **stored** `entry.snapshot` contains that value. A
    schema-validity test alone passes on an empty producer.
  - **Accepted consequence:** the two stored trails —
    `art:trail-gates-framework-landing` and `art:trail-shadow-review-loop` —
    and `aidocs/implementation_trail_examples/cross_topic_multiple_trails.json`
    become invalid until refreshed. Regenerate the example in the same commit and
    tell the user to re-run the trail refresh for the two artifacts.
  - **Test redesign** (not just new tests): `test_wrong_schema_version` keeps its
    shape but the rejected value changes; add a fixture asserting a `1.0.0`
    document is rejected **cleanly** as `ERROR:invalid_trail` (not a false
    `STALE`), and a lock tripwire asserting the map has exactly one entry keyed
    by the schema's own `const`.
- Drift guard: the schema's `followup_kind` enum equals `followup_kinds.tsv`.

### t1468_6 — Backfill the existing follow-ups

Forward-only marking leaves the backlog — where the pain actually is —
unchanged. The creation templates emit stable prose, so retro-classification is
precise.

**The corpus is live and the task file's figures are already stale.** Re-measured
today: **385** active tasks (not 382), **171** follow-ups (not 168). Counts below
are today's measurement, not an acceptance target — **the script must derive them
at run time** and the acceptance check is "every follow-up is classified or
listed as reviewed residue", never a hard-coded total.

| kind | detection | today |
|---|---|---|
| `carry_over` | body has `Carry-over of deferred manual-verification items` | 7 |
| `manual_verification` | `issue_type: manual_verification` | 62 |
| `risk_mitigation` | body matches `Risk-mitigation \("(before\|after)"\)` | 54 |
| `upstream_defect` | body has `^## Upstream defect` or `Spawned from t<id> during Step 8b review` | 43 |
| `verification_failure` | body has `^## Failed verification item from t` | 4 |
| `review_finding` | **frontmatter `labels` contains `review`** | 1 |
| `qa_test_gap` | `labels` contains `qa` | 0 |
| `docs_gap` | filename matches `docs_gaps_since_` | 0 |

Rules must be applied **in the order listed** — `carry_over` is a subset of
manual-verification and must win; every other rule is body/label-based and
disjoint in the current corpus.

- **The three rules the task file omits are the ones that make AC 6 reachable.**
  Its table sums to 167, not 168, and silently drops the single review finding
  (`t804_planning_md_skill_authoring_review.md`, `labels: [review, skill,
  task-workflow]`), which matches no body rule. `aitask-review/SKILL.md.j2:187`
  hard-codes `labels: "review"` on every task it creates, so the label *is* the
  reliable marker. `qa_test_gap` and `docs_gap` have zero active instances today —
  include the rules anyway so the script does not need editing the first time one
  appears, and assert the zero explicitly rather than leaving it unexamined.
- One reviewable script, **dry-run by default**, printing a per-task
  classification table (id · matched rule · assigned kind); `--apply` writes.
- Writes go through `aitask_update.sh --batch --followup-kind` — the sanctioned
  path — so nothing else in the frontmatter is lost. Never hand-edit the files.
- **Also report violations of the MV cross-field invariant** (`followup_kind:
  manual_verification` with a different `issue_type`) as residue rather than
  writing them, since t1468_1 makes that pair unwritable through the CLI.
- Scope decision to document: active corpus only, or archived too.
- Precision is not 100%: 41 of 42 upstream-defect hits carry the exact Step 8b
  sentence; `t1246_fix_codeagent_tests_v5_model_drift.md` is a genuine upstream
  defect written in freeform prose and will not match. **Review the table before
  applying** and record the unmatched residue — an unmatched task is an explicit
  reviewed outcome, not a silent zero.

---

## Deferred / dispositions

Nothing from the task's surface table is deferred — the user scoped in all
surfaces including the trail. Surfaces already covered and needing **no** work,
recorded so a later reader does not re-investigate: monitor `TaskDetailDialog` /
`TaskPickConfirmDialog` (`monitor_shared.py:866-869` already shows `Type:`),
`ait stats` / stats-TUI (drives off `task_types.txt`), applink `task_detail`
(`router.py:676` already ships `issue_type`), codebrowser history detail.

**t720** (`issue_type_list_single_source_of_truth`) is *not* a prerequisite —
that dependency only existed under the rejected Option A. **t1287**
(`manual_verification_path_skips_upstream_defect_followup`) stays independent;
it adds another source of upstream-defect tasks, which this field then marks for
free.

---

### Post-phase (risk mitigations)

- **`mv_sibling_board_recognisability`** (runs at decomposition, immediately
  after the six children and their plans are committed). Create the aggregate
  manual-verification sibling covering the perceptual acceptance criterion no
  unit test can settle: the glyph is identifiable by **colour and shape** at a
  glance, at narrow terminal widths, in a kanban column, in the By-Topic view,
  and as a collapsed-group roll-up — plus `ait ls` display/filter output and the
  `/aitask-pick` selection prompt. Recorded inline so it is not double-created as
  a separate mitigation task: the manual-verification sibling **is** this
  mitigation.

## Verification

Per child, plus this end-to-end pass once all six land:

1. `bash tests/run_all_python_tests.sh` and the new/changed shell tests
   individually (no runner: `bash tests/test_<name>.sh`).
2. `shellcheck .aitask-scripts/aitask_*.sh`.
3. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
4. **Round-trip proof (the core hazard):** create a task with
   `--followup-kind risk_mitigation`, run an *unrelated* `ait update --status`,
   and confirm the field is still there.
4b. **Clear survives sync:** clear the field on one side, leave the other side
   untouched, run the merge — the merged file must have **no `followup_kind:`
   line at all**. Not resurrected (the newer-wins failure) and not written as
   `followup_kind: null` (the naive base-aware-reuse failure).
4c. **Cross-field invariant:** `--followup-kind manual_verification` on a
   `feature` task is rejected non-zero with the file byte-unchanged.
5. **Live board:** launch `ait board` in a real terminal and confirm a
   follow-up is identifiable at a glance by colour and shape, at a narrow width,
   in a kanban column, in By-Topic, in **In-Flight**, in **By-Trail**, and as a
   collapsed group roll-up — and that a trail *ghost* renders cleanly with no
   glyph.
6. `ait ls -v` shows the kind; `ait ls --followup-kind risk_mitigation` filters;
   `/aitask-pick` lists it in the selection prompt.
7. Backfill dry-run table reviewed, then applied; spot-check ~5 tasks per
   category, confirm the residue list is non-empty-and-explained rather than
   assumed empty, and confirm `t804` is classified `review_finding`.
8. Trail: the two live artifacts and the example doc are refreshed/regenerated;
   a stale 1.0.0 document reports `ERROR:invalid_trail`, not `STALE`; and a
   freshly refreshed trail built from a marked task **actually contains**
   `followup_kind` in its stored `entry.snapshot` — not merely validates.

An aggregate manual-verification sibling will be offered after child creation —
the board glyph, `ait ls` output and pick presentation are exactly the kind of
behaviour only a human at a terminal can sign off.

---

## Risk

Levels below are the **reassessment after** the five inline mitigations were
folded into the plan. Code-health stays `high`: the mitigations sharply improve
*detection*, but the blast radius across four trees is intrinsic to the change
and is not reduced by them. Goal-achievement stays `medium`: the two named
medium risks now have concrete coverage, but completeness still depends on all
six children landing.

### Code-health risk: high
- `aitask_update.sh`'s allowlist parser + fixed-positional writer silently
  destroys any unregistered frontmatter key, and the field must be registered at
  **11 separate sites** in that one file (globals, usage, parse, read arm, arg 33,
  emit, three call sites, `has_update`, batch merge, validation). A single missed
  site produces data loss that is invisible until a user's field vanishes ·
  severity: high · → mitigation: inline pre-phase negctrl_field_destruction
- Blast radius is wide and crosses four languages/trees: bash CLI, Python board
  and merge, 9 rendered skill copies across 3 agent trees with force-tracked
  `remote` prerenders, and a JSON schema with two identical copies · severity:
  high · → mitigation: none confirmed (accepted — t1468_2 requires
  `aitask_skill_verify.sh` plus an explicit staging path allowlist)
- The backfill writes 168 real task files in one pass; a classification or
  precedence bug (carry-over is a subset of manual-verification) mislabels the
  backlog it is meant to fix · severity: medium · → mitigation: inline pre-phase
  backfill_single_revertible_commit
- Two pipe-delimited records (`work_report_gather.py`'s `TASK:` and
  `trail_gather.py`'s `MEMBER:`) are consumed with a fixed maxsplit; inserting a
  field shifts every downstream index and a missed consumer mis-reads the path
  as the kind · severity: medium · → mitigation: inline pre-phase
  characterize_pipe_record_consumers
- A schema property with no producer validates cleanly while carrying no data,
  and neither the enum drift guard nor a schema-validity test can see the gap —
  the trail could ship at 1.1.0 with every snapshot empty · severity: medium ·
  → mitigation: none confirmed (accepted — t1468_5 requires an end-to-end test
  asserting a *stored* snapshot contains the value, which is the only check that
  fails on an absent producer)
- The base-aware merge resolver must be **modified**, not merely reused: it
  cannot express deletion (returns `present=True` with a `None` value, which
  serializes as `followup_kind: null`) and hard-codes boardgroup's normaliser.
  Editing a resolver `boardgroup` also depends on risks regressing an unrelated
  field · severity: medium · → mitigation: none confirmed (accepted — t1468_1
  requires `boardgroup`'s existing merge cases to pass unchanged as a regression
  guard on the shared resolver)

### Goal-achievement risk: medium
- "Recognisable at first sight" is a perceptual requirement that unit tests
  cannot settle — glyph width and colour must hold in a real terminal at narrow
  widths, and a wrong palette delivers the field without delivering the outcome ·
  severity: medium · → mitigation: inline post-phase
  mv_sibling_board_recognisability
- The trail `schema_version` bump invalidates every stored 1.0.0 trail (two live
  artifacts plus the example doc) — by design, but a bump that failed as a false
  `STALE` instead of a clean `ERROR:invalid_trail` would deliver the marker at
  the cost of an existing feature · severity: medium · → mitigation: inline
  pre-phase trail_v1_clean_rejection_fixture
- Decomposition into 6 sequential children means the goal is only reached when
  the last one lands; a stall after t1468_1/_2 leaves the field written but
  invisible — strictly worse than today for a reader who now expects it ·
  severity: low · → mitigation: none confirmed (accepted — child order puts the
  visible surfaces t1468_3/_4 immediately after the foundation)

### Planned mitigations
- timing: pre-phase | name: negctrl_field_destruction | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — 11 unregistered-key destruction sites in aitask_update.sh | desc: write the survival assertion in final form, confirm it goes RED before any registration and record the failing test id, then register the field and confirm GREEN with the assertion byte-unchanged
- timing: pre-phase | name: characterize_pipe_record_consumers | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — fixed-maxsplit consumers of the TASK: and MEMBER: records shift | desc: pin the current field indices of both work_report_gather TASK: and trail_gather MEMBER: for every consumer before inserting the new field
- timing: pre-phase | name: trail_v1_clean_rejection_fixture | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — schema_version bump invalidates existing trails | desc: assert a 1.0.0 fixture is rejected as ERROR:invalid_trail on the const rule rather than surfacing as a false STALE, plus a one-entry lock tripwire
- timing: pre-phase | name: backfill_single_revertible_commit | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the backfill mislabels the backlog | desc: clean tree, then two commits — the script via plain git, and the field writes plus the reviewed table (written into the child plan file) via one ./ait git task-data commit
- timing: post-phase | name: mv_sibling_board_recognisability | type: manual_verification | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: goal-achievement — perceptual "recognisable at first sight" criterion | desc: the aggregate manual-verification sibling created at decomposition covers glyph colour and shape at narrow widths across kanban, By-Topic and collapsed groups, plus ait ls and pick output
