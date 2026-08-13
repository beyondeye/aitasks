---
Task: t1468_5_followup_kind_remaining_read_surfaces.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-13 11:33
---

# p1468_5 — Remaining read surfaces: work report, sibling chooser, trail

## Context

`followup_kind:` (t1468_1) marks a task as an auto-spawned follow-up rather than
genuine new work. The vocabulary and its presentation columns live in
**`.aitask-scripts/lib/followup_kinds.py`** (`FOLLOWUP_KINDS`,
`normalize_followup_kind`). t1468_2–t1468_4 wired the creation seams, the board
card glyph, and `ait ls` / pick.

Three read surfaces remain structurally blind to the kind: the **work report**,
the **minimonitor / applink sibling chooser**, and the **implementation trail**.
Each is a place where a human chooses what to work on next or reports on it, and
where "this is a follow-up someone else's work spawned" changes the reading.

The trail is the expensive one: it is **single-version by design**
(`lib/trail_schema.py` `load_schema` reads exactly one `schema_version` `const`;
`lib/trail_gather.py:155` `SCHEMA_NORMALIZATION_LOCK = {"1.0.0": "1.0.0"}`;
`lib/trail_gather.py:107-109` states "old-schema trails fail validation
(ERROR:invalid_trail) -- never a false STALE"). So: **bump, do not dual-accept.**

### Plan-verification corrections (2026-08-13)

The pre-existing plan was verified against `main` and carries five factual
errors, corrected throughout below:

1. **`followup_kinds.tsv` does not exist.** The vocabulary is
   `.aitask-scripts/lib/followup_kinds.py`.
2. **The board's `w` flow is not a `TASK:`-record consumer.**
   `action_work_report` (`board/aitask_board.py:10078`) builds its pickers from
   `manager.get_column_tasks()` — live board state — and *produces*
   `--columns` / `--tasks`. It never parses the pipe record, so its field
   indices need no change. The real fixed-index consumers are
   `.claude/skills/aitask-work-report/SKILL.md`, `tests/lib/work_report_equiv.py`
   and `tests/lib/work_report_flow_equiv.py` (`TASK_FIELDS = 9`),
   `tests/test_work_report_gather.sh` (`task_field`, `cut -f9-`) and
   `tests/test_work_report_skill_contract.sh:84`.
3. **Line anchors are stale.** `find_next_sibling` is `monitor_core.py:3520`,
   `find_ready_siblings` `:3580`; the applink sibling payload is
   `applink/router.py:641-655`; `_reconstruct_old_task_records` is
   `trail_gather.py:775`.
4. **Three trail example fixtures exist at 1.0.0, not one.**
   `shadow_review_loop.json`, `gate_framework.json` and
   `cross_topic_multiple_trails.json`.
   `tests/test_implementation_trail_design.py:71` asserts *every* example's
   `schema_version` equals the schema `const`, and
   `tests/test_board_bytrail_view.py` loads `gate_framework.json` as a live
   board fixture. All three must be bumped.
5. **The "end-to-end producer test" as written is not executable.** The trail's
   snapshot producer is an agent-authored instruction in
   `.claude/skills/aitask-trail/SKILL.md.j2`, not code — no unit test can drive
   it. The executable equivalent is a three-part guard (gatherer unit test +
   skill-contract pin across all three goldens + schema round-trip), with the
   true end-to-end left to manual verification.

## Implementation steps

### Pre-phase (risk mitigations)

1. `[characterize_pipe_record_consumers]` **Before inserting any field**, pin the
   current field positions of both records that gain one.

   - `TASK:` (`lib/work_report_gather.py`) — consumers: the
     `/aitask-work-report` skill schema block, `tests/lib/work_report_equiv.py`,
     `tests/lib/work_report_flow_equiv.py`, `tests/test_work_report_gather.sh`.
   - `MEMBER:` (`lib/trail_gather.py`) — consumer: the `aitask-trail` skill
     writer. Today `tests/test_trail_gather.py` only ever indexes `m[0]`, so the
     remaining MEMBER positions have **no** coverage at all.

   Add a characterization test that asserts each record's full field tuple by
   position for a seeded task (ref/status/priority/effort/boardcol/labels/path
   for `MEMBER:`; col/id/idx/status/priority/effort/pending/remaining/path for
   `TASK:`). Run it and see it **pass** on unmodified code first — that is the
   positive control that proves the probe reaches the real emitter. Then each
   insertion fails loudly at a missed consumer instead of silently re-reading the
   trailing path as the kind.

2. `[trail_v1_clean_rejection_fixture]` **Before touching either schema copy**,
   add to `tests/test_trail_schema.py` a fixture document pinned at
   `schema_version: "1.0.0"` and assert that after the bump it is rejected with
   rule `const` on path `schema_version` — i.e. `ERROR:invalid_trail`, never
   silently accepted and never surfacing as a false `STALE`. Pair it with an
   assertion in `tests/test_trail_gather.py`'s `VersionLockTests` that
   `SCHEMA_NORMALIZATION_LOCK` has **exactly one** entry, keyed by the schema's
   own `const` (read from `trail_schema.load_schema()`, not a literal).

### 1. Work report — `TASK:` gains `followup_kind`

1.1 `.aitask-scripts/lib/work_report_gather.py`: add `followup_kind: str` to the
`TaskRow` dataclass (before `path`), populate it with
`enum_field(metadata.get("followup_kind"))` in `scan_tasks`, and emit it
**immediately before** `sanitize_last_field(row.path)` in the `TASK:` line. New
record:

```
TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<followup_kind>|<task_file_path>
```

The single free-text field (`path`) stays LAST, so the fixed-maxsplit contract
holds. `enum_field` yields `unknown` for an absent kind — which is the common
case, since most tasks are genuine new work.

1.2 Update the module docstring's protocol block in the same edit — it is the
contract consumers are written against.

1.3 Update the consumers found in verification:
- `.claude/skills/aitask-work-report/SKILL.md` — the pinned schema block (line
  21) and the Step 4 per-task reading rules: state that `unknown` means *not a
  follow-up* and must not be surfaced, and that a recognised kind should be
  named in the task's report line (use `followup_kinds.label_for`-style wording,
  e.g. "follow-up: risk mitigation"). Regenerate nothing — this skill is
  static, `.claude`-only, with no `.j2` and no other agent tree.
- `tests/test_work_report_skill_contract.sh:84` — the pinned schema string.
- `tests/lib/work_report_equiv.py` and `tests/lib/work_report_flow_equiv.py` —
  `TASK_FIELDS = 9` → `10`.
- `tests/test_work_report_gather.sh` — `cut -d'|' -f9-` → `-f10-` for the path
  assertion, plus new `task_field … 9` assertions for the kind (present,
  absent → `unknown`, record-breaking → `invalid`).

**No board change.** `action_work_report` never parses the record.

### 2. Sibling chooser — monitor, minimonitor, applink

2.1 `.aitask-scripts/lib/followup_kinds.py`: add the shared render boundary the
board already owns privately:

```python
def marker_for(kind):
    """`(glyph, colour)` for a follow-up kind, or None when absent/empty/junk.

    The framework's totality boundary over `followup_kind`. Deliberately NOT
    `glyph_for`/`colour_for`: those answer `("·", None)` for an *absent* kind
    just as for an unknown one, which on a card list would paint a marker on
    every ordinary task. Absent -> None (yield no marker at all); recognised ->
    its glyph + severity-family colour; present-but-unrecognised -> the `·`
    fallback with no colour, so a typo or a newer framework's kind still
    renders rather than silently vanishing.
    """
```

Then make `board/aitask_board.py`'s `_followup_marker(metadata)` (`:3338`)
delegate to it, keeping its name, signature and docstring intent intact — t1470
reads that function and must be unaffected. This is the "reuse the canonical
seam" move: one boundary, two TUIs, no second copy.

2.2 `.aitask-scripts/monitor/monitor_core.py`:
- `find_ready_siblings` (`:3580`) — return
  `(sib_id, title, blocking_sibling_ids, followup_kind)`; the frontmatter is
  already parsed in the first pass, so this is threading, not re-reading. Store
  the raw value; normalization is the render boundary's job.
- `find_next_sibling` (`:3520`) — same omission; return
  `(sib_id, title, followup_kind)`.
- Update both docstrings' documented return shapes.

2.3 `.aitask-scripts/monitor/monitor_shared.py` (`lib/` is already on
`sys.path` there):
- `_SiblingRow` (`:1477`) — accept `followup_kind`, and in `render()` prefix the
  row with `marker_for(...)`'s glyph, colourised when a colour is given, placed
  before the `t<id>`. Keep the row one cell wider at most — glyphs are
  single-cell by construction, and the narrow (minimonitor, ~40 col) variant
  must still show `t<id>` and title.
- `ChooseSiblingModal` — widen its `siblings` type to the 4-tuple and pass the
  kind through to `_SiblingRow`.
- `NextSiblingDialog` — accept `suggested_kind` and render the same marker on
  the `Suggested:` line.

2.4 Callers: `monitor/monitor_app.py:3259/3293` and
`monitor/minimonitor_app.py:1578/1605` unpack the widened tuples and forward the
kind into the two dialogs.

2.5 `.aitask-scripts/applink/router.py:641-655` — add `followup_kind` to both
`suggested_payload` and each `ready_payload` entry, emitting `None` (JSON
`null`) when the task carries no kind so absent stays distinguishable from a
value. Update `aidocs/applink/monitor_port_design.md:142`, whose recorded
payload shape is already stale (it omits `blocked_by`), to the real shape.

2.6 `tests/test_applink_router.sh` — update the fake task cache's tuple arities
and the `ready_siblings` assertion at `:265`; add one asserting the kind rides
through. `tests/test_multi_session_monitor.sh` indexes only `[0]`, so it is
unaffected.

2.7 **Filesystem-backed core test — the one that proves the metadata lookup.**
New `tests/test_task_info_cache_followup_kind.py`, modeled on
`tests/test_task_info_cache_archived.py`'s `tempfile.TemporaryDirectory` +
`_write_task` style: build a real `aitasks/t<N>/` tree of sibling files and
drive the **real `TaskInfoCache`**, asserting the kind through **both** widened
return shapes — `find_next_sibling` and `find_ready_siblings` — for a
**recognised** kind, an **absent** kind, and an **unrecognised** kind.

This is not optional coverage. Every other test in this step reads a replica:
`tests/test_applink_router.sh:117` supplies its own `find_ready_siblings` stub
returning hardcoded tuples, and the render test in 2.8 constructs `_SiblingRow`
directly. Neither ever parses frontmatter, so a wrong metadata key or a wrong
tuple slot in `monitor_core.py` would leave the picker and the applink payload
unmarked while every other stated test passes. `tests/test_multi_session_monitor.sh`
does drive the real cache but indexes only `[0]`, so it cannot catch it either.

2.8 New render-level test for the picker (no coverage exists today for
`_SiblingRow` / `ChooseSiblingModal` / `NextSiblingDialog`): assert
`_SiblingRow(...).render()` contains the glyph for a recognised kind, contains
no marker for an absent one, and shows the `·` fallback for an unrecognised one.

### 3. Trail schema — bump to 1.1.0

3.1 Edit **both identical copies** — `aidocs/implementation_trail.schema.json`
and `.aitask-scripts/lib/implementation_trail.schema.json` — and `diff` them
afterwards to confirm they stay byte-identical.

3.2 Add `followup_kind` as an **optional** property of `$defs/entry.snapshot`
(currently `additionalProperties: false`, `required: [status]`, with
`status`/`priority`/`effort`/`boardcol`/`depends`/`gates_pending`), typed as a
`string` with an `enum` equal to `FOLLOWUP_KINDS`' declaration order. This
matches the existing `priority`/`effort` enum precedent for closed
framework-owned vocabularies.

3.3 Bump `properties.schema_version.const` to `"1.1.0"` and the schema `$id`
(`…/implementation_trail-1.0.0.json` → `-1.1.0.json`) in both copies.

3.4 `lib/trail_gather.py`: `SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}`.
**`trail_schema.NORMALIZATION_VERSION` stays `"1.0.0"`** — the lock's contract is
that a *normalization* bump requires a schema bump, not the reverse. This holds
only because `followup_kind` never enters the normalized digest: the digest
hashes `generation.inputs` records, and the snapshot reconstruction in
`_reconstruct_old_task_records` (`:775`) reads only status + depends +
gates_pending. Say so in the lock comment. If it ever enters the digest,
`NORMALIZATION_VERSION` must bump too and every stored digest becomes
incomparable.

3.5 Update every remaining `1.0.0` site the verification enumerated:
`aidocs/implementation_trail_design.md:173`;
`tests/test_trail_gather.py:1326` (assert the const is `1.1.0`) and its
`make_trail` fixture at `:232` — derive that one from
`trail_schema.load_schema()["properties"]["schema_version"]["const"]` rather than
re-hardcoding, so it cannot drift on the next bump.
`tests/test_trail_schema.py:162`'s `2.0.0` rejection keeps its shape unchanged
(2.0.0 is still ≠ the const); the 1.0.0 rejection is the pre-phase's new fixture.

### 4. Trail — plumb the PRODUCER

A schema property with no producer validates perfectly while carrying nothing,
and the enum drift guard cannot see that — it only checks the vocabulary. Both
halves are required.

4.1 **Gatherer.** `lib/trail_gather.py` `member_line` (`:492`) — add
`<followup_kind>` **immediately before** `<path>` via `enum_field()`, then clamp
it: a value that is neither `unknown` nor a member of `VALID_FOLLOWUP_KINDS`
becomes `invalid`. New record:

```
MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<followup_kind>|<path>
```

Update the module docstring's protocol block. **Why clamp here and not in the
work report:** this value lands in a schema-`enum`-validated document, so an
out-of-vocabulary value (a typo, or a kind from a newer framework) would make
the *whole trail* fail as `ERROR:invalid_trail` — a total failure for a cosmetic
provenance field. Sanitizing at the write site is the only point where the
distinction is still knowable. The work report's value lands in prose, where
raw pass-through is harmless.

4.2 **Skill writer.** `.claude/skills/aitask-trail/SKILL.md.j2`:
- line 55 — the `MEMBER:` schema line.
- line 393 — `schema_version`: `"1.1.0"`.
- lines 403-406 — the snapshot-population rule: add `followup_kind` to the
  fields read from the MEMBER line, **and add the generic omission rule**:
  *"omit any optional snapshot field whose MEMBER value is `unknown` or
  `invalid` — those are transport sentinels, not values, and writing one into an
  enum-typed property invalidates the document."*

  This rule is generic on purpose. It also closes a **pre-existing** hole: today
  a task with no `priority` yields `MEMBER:…|unknown|…`, and the skill has no
  instruction to drop it, so the writer would emit `"priority": "unknown"` and
  fail the existing enum. Record it under "Upstream defects identified" at
  Step 8.

Then rerender per profile — `./.aitask-scripts/aitask_skill_rerender.sh default`
/ `fast` / `remote` (one call per profile) — and regolden
`tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`. Stage
the rerender output explicitly by path; the sweep touches many unrelated
rendered dirs.

4.3 `tests/test_trail_skill_contract.sh` — add markers asserting, in **all
three** committed goldens, that the writer is instructed to populate
`followup_kind` into `entry.snapshot` **and** to omit `unknown`/`invalid`. This
is the executable stand-in for "the producer is plumbed" (see correction 5).

4.3a **Pin the sentinel rejection explicitly** (`tests/test_trail_schema.py`).
The omission rule guards the **common** path, not an edge case: most tasks are
genuine new work, so `enum_field` yields `unknown` for them, and `unknown` is
deliberately **not** in the enum. If the writer ever stores the sentinel instead
of omitting the key, every ordinary trail becomes `ERROR:invalid_trail`. Assert
that a snapshot of `{"status": "Ready", "followup_kind": "unknown"}` is rejected
on the `enum` rule, the same for `"invalid"`, and — the positive control — that
a snapshot **without** the key at all validates. That makes the failure mode
named and executable rather than resting on prose alone.

4.4 Drift guard — a new test asserting the schema's `followup_kind` enum equals
`list(FOLLOWUP_KINDS)` in **both** schema copies, so adding a kind later cannot
land without updating the schema. (Adding an enum value does *not* require
another `schema_version` bump: older documents stay valid.)

### 5. Trail — explicitly NOT a drift dimension

Keep `followup_kind` out of `GATHERER_DRIFT_CODES` and out of
`_reconstruct_old_task_records`'s completeness requirement (`:775-781`, currently
status + depends + gates_pending). It is display provenance, not
ordering-relevant; adding it would mark every pre-existing snapshot "incomplete"
and force lossy reconstruction. Add a test asserting a snapshot **without**
`followup_kind` still reconstructs (a negative control for exactly this).

### 6. Trail — the accepted consequence

The `const` bump invalidates every stored 1.0.0 trail until refreshed.

- **Regenerate in this commit:** all **three** fixtures under
  `aidocs/implementation_trail_examples/` (`shadow_review_loop.json`,
  `gate_framework.json`, `cross_topic_multiple_trails.json`) — bump
  `schema_version` to `1.1.0`, and add a `followup_kind` to **exactly one**
  `entry.snapshot`, leaving every other entry without the key. Both shapes then
  live in the validated corpus: the present case exercises the new property, and
  the absent case pins that omission — the ordinary path — is valid. (The corpus
  already models partial snapshots this way: no example carries `boardcol` or
  `gates_pending`.) This cannot change any digest (step 3.4), and
  `tests/test_board_bytrail_view.py`'s use of `gate_framework.json` is
  byte-stability only, not content-shape.
- **Do NOT refresh silently:** the two live artifacts
  `art:trail-gates-framework-landing` and `art:trail-shadow-review-loop` will
  read `ERROR:invalid_trail` until re-run through `/aitask-trail refresh`. Tell
  the user explicitly at Step 8; the spawned `after` mitigation
  `refresh_and_verify_live_trails` tracks the refresh so it is not a verbal
  hand-off that evaporates.

### 7. Cutover sequencing guard for t1470 (post-commit, before merge)

Spawning the refresh task *records* the work but does not *sequence* it: t1470
is `Ready`, high/high, has `depends: []`, and its acceptance criteria are
written against both artifacts. Between this landing and the refresh running,
anyone picking t1470 meets a genuine `ERROR:invalid_trail` that is a transient
consequence of this task, not a t1470 regression.

t1470 already carries a prose warning ("Live hazard if t1468_5 lands first",
`aitasks/t1470_…md:212-218`) and explicitly declines a hard `depends` **on
t1468_5** — "deliberately", because its implementation works off live task
metadata. Respect that: do **not** add a `t1468_5` edge.

Instead, immediately after the Step 8d creation of `refresh_and_verify_live_trails`
(which runs before the Step 9 merge, so the edge exists the moment this lands):

7.1 Add **that task's** id to t1470's `depends:`. The flag is `--deps` and it
**replaces the whole list**, so re-read t1470's current `depends:` first and
pass the union (it is `[]` today, but do not assume that at execution time):
```bash
./.aitask-scripts/aitask_update.sh --batch 1470 --deps "<existing_csv_plus_refresh_task_id>"
```
This edge is strictly narrower than the one t1470 declined: the refresh task
exists *only* if this task landed, so if t1468_5 never lands t1470 is never
blocked. It is conditional on the hazard actually being real.

7.2 Update t1470's "Live hazard" paragraph in place to name the task by id, and
state that the edge is **verification-scoped** — someone who wants to start
implementing t1470 early may drop it deliberately, but must not read
`ERROR:invalid_trail` as a defect until the refresh is Done. Record the reverse
pointer here (the Coordination section below) so the link is bidirectional.

Both edits go through `./ait git`, in the same administrative commit.

## Verification

1. Pre-phase characterization tests pass on unmodified code **first**, then are
   updated deliberately as part of the change.
2. Work report: `bash tests/test_work_report_gather.sh`,
   `bash tests/test_work_report_skill_contract.sh` — the kind appears at
   position 9, the path stays last, absent → `unknown`, record-breaking →
   `invalid`.
3. Sibling chooser, three levels — **the core one is not optional**:
   `python3 tests/test_task_info_cache_followup_kind.py` drives the real
   `TaskInfoCache` over a real task tree and asserts recognised / absent /
   unrecognised kinds through **both** `find_next_sibling` and
   `find_ready_siblings`; `bash tests/test_applink_router.sh` (kind in both
   payloads); the new `_SiblingRow` render test (glyph present / absent / `·`
   fallback); `bash tests/test_multi_session_monitor.sh` still green.
   **Negative control:** revert only the `metadata.get("followup_kind")` lookup
   in `monitor_core.py` and confirm the filesystem-backed test goes red by name
   while the stub-based router test stays green — that is the proof the new test
   reaches the real class rather than a replica.
4. `diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json`
   is empty; the enum-drift test equates both copies' enum to `FOLLOWUP_KINDS`.
5. `test_wrong_schema_version` keeps its shape; the new 1.0.0 fixture is rejected
   **cleanly** on the `const` rule as `ERROR:invalid_trail`, not as a false
   `STALE`; the lock tripwire asserts a single entry keyed by the schema's own
   `const`.
6. Producer coverage — **both the follow-up path and the ordinary no-kind
   path.** The executable parts: the gatherer unit test asserts a seeded task's
   kind on the MEMBER record *and* that an ordinary task's field is exactly
   `unknown`; `tests/test_trail_skill_contract.sh` asserts both writer
   instructions (populate, and omit `unknown`/`invalid`) in all three goldens;
   the schema tests of 4.3a assert a valid kind validates, `unknown`/`invalid`
   are rejected on the `enum` rule, and an absent key validates.
7. All three regenerated example trails validate at 1.1.0
   (`python3 -m unittest tests.test_trail_schema tests.test_implementation_trail_design`),
   with one entry carrying `followup_kind` and the rest omitting it.
8. Sequencing: `./ait ls` shows t1470 as Blocked on the refresh task, and its
   "Live hazard" paragraph names that task by id.
9. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
10. `bash tests/run_all_python_tests.sh` — read the **LAST** line for the verdict
    (`set -o pipefail` if piping).

## Coordination — t1470 (By-Trail parallel-safety)

t1470 reads `issue_type` and `followup_kind` from live task metadata via
`_followup_marker` (`board/aitask_board.py:3338`) and deliberately does not
depend on this child. Two things this child owes it:

- **`entry.snapshot.followup_kind` is the ghost fallback.** Archived / missing /
  cross-repo trail entries resolve to no live `Task`, so the live path cannot
  serve them; once this lands, t1470 wires the snapshot field in as a one-line
  fallback for exactly that case.
- **Refresh before t1470 is verified.** t1470's acceptance criteria are written
  against the two live artifacts; after the 1.1.0 bump their
  `ERROR:invalid_trail` is expected, not a t1470 defect. Step 7 turns that from
  a prose warning into a board-visible edge: t1470 gains a `depends` on the
  spawned `refresh_and_verify_live_trails` task (**not** on t1468_5 — t1470
  declines that one deliberately, and the narrower edge only exists if this
  task actually landed).

Step 2.1 keeps `_followup_marker`'s name and signature intact, so t1470's
reference survives the shared-seam extraction.

**Reverse pointer:** t1470 is edited by step 7 of this plan (its `depends:` and
its "Live hazard" paragraph); the refresh task it will depend on is created at
Step 8d from the `refresh_and_verify_live_trails` mitigation line below.

## Notes for sibling tasks

- Two pipe records changed shape here (`TASK:`, `MEMBER:`). Any later work must
  re-read the docstring protocol block, never assume the old indices.
- The trail schema is now 1.1.0 and still single-version: a future *field* means
  another `const` bump and another round of trail refreshes. Adding a new
  **follow-up kind**, by contrast, only needs the schema enum updated in both
  copies — the drift guard enforces it and no version bump is required.

## Risk

### Code-health risk: medium

- The `schema_version` `const` bump invalidates every stored 1.0.0 trail, and
  the blast radius is wider than the task recorded: three example fixtures (not
  one), two schema copies including their `$id`, a design doc, the skill
  template plus three goldens plus rendered variants across three agent trees,
  and two test constants. A missed site fails as a whole-document
  `ERROR:invalid_trail`, not as a localized error. · severity: medium ·
  → mitigation: inline pre-phase trail_v1_clean_rejection_fixture
- Two pipe-delimited records gain a field mid-record. Every consumer reads with
  a fixed maxsplit, so a missed one silently re-reads the trailing path as the
  kind rather than failing — and `MEMBER:`'s field positions have no test
  coverage at all today. · severity: medium ·
  → mitigation: inline pre-phase characterize_pipe_record_consumers
- The change touches three otherwise-unrelated subsystems (report gatherer,
  monitor/applink sibling flow, trail schema + gatherer + skill) in one commit,
  plus a shared-seam extraction in `board/aitask_board.py` that t1470 is
  concurrently reading. · severity: low (bounded — the extraction preserves
  `_followup_marker`'s name and signature, and the three subsystems share no
  code beyond `followup_kinds.py`) · → mitigation: none

### Goal-achievement risk: medium

- Every naturally-reachable test for the sibling surface reads a **replica**:
  the applink router test supplies its own `find_ready_siblings` stub and the
  render test constructs `_SiblingRow` directly. A wrong frontmatter key or
  tuple slot in `monitor_core.py` would ship an unmarked picker with a fully
  green suite. · severity: low (residual — step 2.7 drives the real
  `TaskInfoCache` over a real task tree through both return shapes, with a named
  negative control) · → mitigation: none (addressed by plan step 2.7)
- The trail's snapshot producer is an agent-authored skill instruction, not
  code. A schema property with a correct enum and a correct gatherer can still
  carry nothing if the writer never populates it, and no automated test can
  drive the writer — so "it works" rests on a prose contract plus manual
  verification. · severity: medium (residual — the three-part executable guard
  of step 4.3/4.4/6 bounds it; the true end-to-end lands in the spawned
  follow-up) · → mitigation: refresh_and_verify_live_trails
- The two live trail artifacts become invalid on landing and are refreshed only
  by a human re-running the trail skill. A verbal "tell the user" instruction
  leaves nothing tracked, and t1470's acceptance criteria depend on the refresh
  having happened. · severity: medium (residual — tracked as a spawned
  follow-up rather than a verbal hand-off) ·
  → mitigation: refresh_and_verify_live_trails

### Planned mitigations
- timing: pre-phase | name: characterize_pipe_record_consumers | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a missed fixed-maxsplit consumer silently re-reads the trailing path as the kind | desc: Pin the current field tuples of TASK: and MEMBER: by position, with a passing positive control, before any field insertion.
- timing: pre-phase | name: trail_v1_clean_rejection_fixture | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the schema const bump's blast radius is wider than the task recorded | desc: Add a schema_version 1.0.0 fixture that must be rejected on the const rule after the bump (never a false STALE), plus a lock tripwire asserting SCHEMA_NORMALIZATION_LOCK has exactly one entry keyed by the schema's own const.
- timing: after | name: refresh_and_verify_live_trails | type: manual_verification | priority: high | effort: low | inline_risk: high | added_complexity: low | addresses: goal-achievement — the agent-authored snapshot producer is undrivable by tests, and the two live artifacts stay invalid until a human refreshes them | desc: Re-run /aitask-trail refresh for art:trail-gates-framework-landing and art:trail-shadow-review-loop at schema 1.1.0, then inspect BOTH a member task carrying a known followup_kind (the value is stored) AND an ordinary member with no kind (the key is absent, never the literal "unknown"/"invalid") — the second is the common path and the only end-to-end proof of the writer's omission rule. Both artifacts must end at freshness current, not ERROR:invalid_trail. t1470 depends on this task (step 7).
