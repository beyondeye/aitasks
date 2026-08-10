---
Task: t1468_5_followup_kind_remaining_read_surfaces.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_5 — Remaining read surfaces: work report, sibling chooser, trail

Context and the trail design constraint are in
`aitasks/t1468/t1468_5_followup_kind_remaining_read_surfaces.md`.

**Precondition:** t1468_1 has landed.

## Pre-phase (risk mitigations — before any edit)

### 0a. `characterize_pipe_record_consumers`

**Two** pipe-delimited records gain a field here, both following "at most one
free-text field and it is always LAST", both consumed with a fixed maxsplit:

| record | producer | consumers |
|---|---|---|
| `TASK:` | `lib/work_report_gather.py` | `/aitask-work-report` skill, board `w` flow |
| `MEMBER:` | `lib/trail_gather.py` (docstring `:28`) | `aitask-trail` skill writer |

Enumerate every consumer of **both** and pin the current field indices in a
characterization test **first**. Then each insertion fails loudly at a missed
consumer instead of silently re-reading the trailing path as the kind.

### 0b. `trail_v1_clean_rejection_fixture`

Before touching either schema copy, add a fixture document pinned at
`schema_version: "1.0.0"`. After the bump it must be rejected as
`ERROR:invalid_trail` on the `const` rule — never silently accepted, never a
false `STALE`. Pair it with a lock tripwire asserting `SCHEMA_NORMALIZATION_LOCK`
has exactly one entry, keyed by the schema's own `const`.

## Implementation steps

### 1. Work report

`.aitask-scripts/lib/work_report_gather.py`. Current record:

```
TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
```

1.1 Insert `<followup_kind>` **immediately before `<task_file_path>`** — the one
free-text field must stay last. Use `enum_field()` (`lib/record_protocol.py:128`).
1.2 Update the docstring's protocol block in the same edit; it is the contract
consumers are written against.
1.3 Update every consumer's index: the `/aitask-work-report` skill and the
board's `w` flow (which passes a reviewed selection back as `--columns` /
`--tasks`).

### 2. Minimonitor / applink sibling chooser

2.1 `.aitask-scripts/monitor/monitor_core.py` — `find_ready_siblings`
(`:3260-3262`) returns `(sib_id, title, blocking_sibling_ids)` and drops the type
although frontmatter is already parsed at `:3305`. Carry the kind through the
tuple. Check `find_next_sibling` just above for the same omission.
2.2 `.aitask-scripts/applink/router.py:650-653` builds `ready_payload` from those
rows and inherits the gap. Add the kind to the `pick_next_sibling` payload.
2.3 Surface it in the minimonitor's sibling picker UI.

### 3. Trail — respect the single-version design

The trail is deliberately single-version. Read these before editing:

- `lib/trail_schema.py:143-145` — `load_schema` reads exactly one
  `schema_version` **`const`** and dies if it is absent.
- `lib/trail_gather.py:155` — `SCHEMA_NORMALIZATION_LOCK = {"1.0.0": "1.0.0"}`.
- `lib/trail_gather.py:107-109` — *"old-schema trails fail validation
  (ERROR:invalid_trail) -- never a false STALE."*
- `tests/test_trail_schema.py:160` — pins const-ness via a `2.0.0` rejection.

**Bump; do not dual-accept.** A multi-version loader would mean turning `const`
into an enum, giving the lock two entries and rewriting the tripwire — fighting a
deliberate property for no gain.

3.1 Edit **both identical copies**: `aidocs/implementation_trail.schema.json` and
`.aitask-scripts/lib/implementation_trail.schema.json`. `diff` them afterwards to
confirm they stay identical.
3.2 Add `followup_kind` as an **optional** property of `entry.snapshot` (which is
`additionalProperties: false`; currently `status` required plus `priority`,
`effort`, `boardcol`, `depends`, `gates_pending`), with an enum matching
`followup_kinds.tsv`.
3.3 Bump the `const` to `"1.1.0"`; set
`SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}`.
3.4 **`NORMALIZATION_VERSION` stays `"1.0.0"`.** The lock's contract is that a
*normalization* bump requires a schema bump, not the reverse. This holds **only
if `followup_kind` stays out of the normalized digest** — keep it out and say so
in the lock comment. If it ever enters the digest, `NORMALIZATION_VERSION` must
bump too and every stored digest becomes incomparable.
3.5 Writer emits `1.1.0`.

### 4. Trail — plumb the PRODUCER

A schema property with no producer validates perfectly while carrying nothing,
and the enum drift guard cannot see that — it only checks the vocabulary. **Both
halves are required:**

4.1 **Gatherer** — `lib/trail_gather.py`'s `MEMBER:` record is
`MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<path>`. Add
`<followup_kind>` **immediately before `<path>`** via `enum_field()`. Update the
docstring protocol block.
4.2 **Skill writer** — `.claude/skills/aitask-trail/SKILL.md.j2` must place the
value into each generated `entry.snapshot`. Rerender per profile
(`aitask_skill_rerender.sh default|fast|remote`) and regolden
`tests/golden/skills/aitask-trail/SKILL-*-claude.md`.

### 5. Trail — explicitly NOT a drift dimension

Keep `followup_kind` out of `GATHERER_DRIFT_CODES` and out of
`_reconstruct_old_records`'s completeness requirement (`:777-781`, currently
status + depends + gates_pending). It is display provenance, not
ordering-relevant, and adding it would mark every pre-existing snapshot
"incomplete" and force lossy reconstruction.

### 6. Trail — the accepted consequence

Bumping the schema invalidates every stored 1.0.0 trail until refreshed. Today:

- `art:trail-gates-framework-landing`
- `art:trail-shadow-review-loop`
- `aidocs/implementation_trail_examples/cross_topic_multiple_trails.json`

Regenerate the example doc in the same commit. **Tell the user** to re-run the
trail refresh for the two artifacts — do not refresh them silently.

## Verification

1. Characterization tests for both pipe records pass **before** the insertions,
   then are updated deliberately as part of the change.
2. Work report: every consumer reads the correct fields after the shift; the `w`
   flow round-trips a reviewed selection unchanged (membership **and** order).
3. Sibling chooser: `find_ready_siblings`, `find_next_sibling` and the
   `pick_next_sibling` payload all carry the kind; the minimonitor shows it.
4. Both schema copies still `diff`-identical; the `followup_kind` enum equals
   `followup_kinds.tsv` (drift guard).
5. `test_wrong_schema_version` keeps its shape with the rejected value updated; a
   `1.0.0` fixture is rejected **cleanly** as `ERROR:invalid_trail`, not as a
   false `STALE`; the lock tripwire asserts a single entry keyed by the schema's
   own `const`.
6. **End-to-end producer test — the one check that fails on an absent producer:**
   mark a fixture task with a known `followup_kind`, generate/refresh a trail
   from it, and assert the **stored** `entry.snapshot` contains that value. A
   schema-validity test alone passes against an empty producer, which is exactly
   the failure mode this step exists to prevent.
7. Regenerated example trail validates at 1.1.0.
8. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
9. `bash tests/run_all_python_tests.sh` — read the **last** line.

## Notes for sibling tasks

- Two records changed shape here (`TASK:`, `MEMBER:`). Any later work touching
  either must re-read the docstring protocol block, not assume the old indices.
- The trail schema is now 1.1.0 and still single-version: a future field means
  another bump and another round of trail refreshes.
