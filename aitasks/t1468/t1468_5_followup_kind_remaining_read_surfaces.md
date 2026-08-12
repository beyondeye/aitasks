---
priority: medium
effort: high
depends: [t1468_4]
issue_type: feature
status: Implementing
labels: [task_metadata, aitask_board]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1468
created_at: 2026-08-10 16:30
updated_at: 2026-08-12 19:16
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind.
Depends on **t1468_1** (the `followup_kind:` field and
`.aitask-scripts/lib/followup_kinds.tsv`).

Three remaining surfaces are structurally blind to the kind: the work report, the
minimonitor/applink "next sibling" chooser, and the implementation trail. The
trail is the most expensive and has a **deliberate single-version design** that
must be respected rather than worked around.

Read the parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`.

## Pre-phase (risk mitigations — do these FIRST)

**`characterize_pipe_record_consumers`.** **Two** pipe-delimited records gain a
field in this child, both following the "at most one free-text field and it is
always LAST" rule, both consumed with a fixed maxsplit:
- `lib/work_report_gather.py`'s `TASK:` — consumers: the `/aitask-work-report`
  skill and the board's `w` flow;
- `lib/trail_gather.py`'s `MEMBER:` — consumer: the `aitask-trail` skill writer.

Enumerate every consumer of **both** and pin the current field indices in a
characterization test **before** inserting anything. Then each insertion fails
loudly at a missed consumer instead of silently re-reading the path as the kind.

**`trail_v1_clean_rejection_fixture`.** Before editing either schema copy, add a
fixture document pinned at `schema_version: 1.0.0` and assert that after the bump
it is rejected as `ERROR:invalid_trail` on the `const` rule — never silently
accepted, and never surfacing as a false `STALE`. Pair it with a lock tripwire
asserting `SCHEMA_NORMALIZATION_LOCK` has exactly one entry keyed by the schema's
own `const`.

## Surface 1 — Work report

`.aitask-scripts/lib/work_report_gather.py`. The `TASK:` record is:

    TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>

`<task_file_path>` is the single free-text field and must stay LAST, so
`<followup_kind>` goes **immediately before it**. Use `enum_field()`
(`lib/record_protocol.py:128`). Every consumer's fixed-maxsplit index shifts —
update the `/aitask-work-report` skill and the board `w` flow.

## Surface 2 — Minimonitor / applink sibling chooser

`.aitask-scripts/monitor/monitor_core.py` `find_ready_siblings` (`:3260-3262`)
drops the type although frontmatter is parsed at `:3305`. It returns rows of
`(sib_id, title, blocking_sibling_ids)`; carry the kind through the tuple.
`.aitask-scripts/applink/router.py:650-653` builds `ready_payload` from those
rows and inherits the gap — add the kind to the `pick_next_sibling` payload.
Check `find_next_sibling` (just above) for the same omission.

## Surface 3 — aitask-trail (the expensive one)

### The design constraint — read before editing

The trail is **single-version by design**:
- `lib/trail_schema.py:143-145` — `load_schema` reads exactly one
  `schema_version` **`const`** and dies if it is missing.
- `lib/trail_gather.py:155` — `SCHEMA_NORMALIZATION_LOCK = {"1.0.0": "1.0.0"}`.
- `lib/trail_gather.py:107-109` states the intent outright: *"old-schema trails
  fail validation (ERROR:invalid_trail) -- never a false STALE."*
- `tests/test_trail_schema.py:160` pins const-ness by asserting a `2.0.0`
  document is rejected on the `const` rule.

**Therefore: bump, do not dual-accept.** A multi-version loader would mean
turning `const` into an enum, giving the lock two entries and rewriting the
tripwire — fighting a deliberate property for no gain.

### Changes

- Edit **both identical copies** of the schema: `aidocs/implementation_trail.schema.json`
  and `.aitask-scripts/lib/implementation_trail.schema.json` (verify with `diff`
  that they stay identical).
- Add `followup_kind` as an **optional** property of `entry.snapshot` (which is
  `additionalProperties: false`, currently `status`/`priority`/`effort`/
  `boardcol`/`depends`/`gates_pending`), enum-derived from `followup_kinds.tsv`.
- Bump the `const` to `"1.1.0"`; set
  `SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}`.
- **`NORMALIZATION_VERSION` stays `"1.0.0"`** — the lock's contract is that a
  *normalization* bump requires a schema bump, not the reverse. This holds **only
  if `followup_kind` does not enter the normalized digest**; keep it out and say
  so in the lock comment. If it must enter the digest, `NORMALIZATION_VERSION`
  bumps too and every stored digest becomes incomparable.
- Writer emits `1.1.0`.

### Plumb the PRODUCER, not just the schema

A schema property with no producer validates perfectly while carrying nothing,
and the enum drift guard cannot see that — it only checks the vocabulary. **Both
halves are required:**
1. **Gatherer** — `lib/trail_gather.py`'s `MEMBER:` record (docstring `:28`) is
   `MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<path>`.
   Add `<followup_kind>` **immediately before `<path>`** via `enum_field()`.
2. **Skill writer** — `.claude/skills/aitask-trail/SKILL.md.j2` must place the
   value into each generated `entry.snapshot`. Rerender per profile and regolden
   `tests/golden/skills/aitask-trail/SKILL-*-claude.md`.

### Not a drift dimension

Keep `followup_kind` out of `GATHERER_DRIFT_CODES` and out of
`_reconstruct_old_records`'s completeness requirement (`:777-781`, currently
status + depends + gates_pending). It is display provenance, not
ordering-relevant, and adding it would make every pre-existing snapshot
"incomplete" and force lossy reconstruction.

### Accepted consequence — tell the user

Bumping the schema invalidates every stored 1.0.0 trail until refreshed. Today
that is **two live artifacts** — `art:trail-gates-framework-landing` and
`art:trail-shadow-review-loop` — plus
`aidocs/implementation_trail_examples/cross_topic_multiple_trails.json`.
Regenerate the example in the same commit; tell the user to re-run the trail
refresh for the two artifacts.

## Verification steps

1. Characterization tests for both pipe records pass **before** the field
   insertions, then are updated deliberately as part of the change.
2. Work report: every consumer reads the correct fields after the shift; the
   `w` flow round-trips a reviewed selection unchanged.
3. Minimonitor / applink: the sibling chooser and `pick_next_sibling` payload
   carry the kind.
4. Trail schema: both copies still `diff`-identical; enum equals
   `followup_kinds.tsv` (drift guard).
5. `test_wrong_schema_version` keeps its shape with the rejected value updated;
   a `1.0.0` fixture is rejected **cleanly** as `ERROR:invalid_trail`, not as a
   false `STALE`; lock tripwire asserts a single entry keyed by the schema's own
   `const`.
6. **End-to-end producer test — the one that catches an empty producer:** mark a
   fixture task with a known `followup_kind`, generate/refresh a trail from it,
   and assert the **stored** `entry.snapshot` contains that value. A
   schema-validity test alone passes on an absent producer.
7. Regenerate the example trail; re-render + regolden the `aitask-trail` skill;
   `./.aitask-scripts/aitask_skill_verify.sh` clean.
8. `bash tests/run_all_python_tests.sh` (read the LAST line for the verdict).

## Coordination — t1470 (By-Trail parallel-safety)

**t1470** (`surface_intrawave_parallel_safety_in_bytrail_view`, Ready,
high/high) consumes follow-up provenance in the By-Trail view but deliberately
does **not** depend on this child: it reads `issue_type` and `followup_kind`
from live task metadata via `_followup_marker`
(`board/aitask_board.py:3315`), so it works with the schema still at `1.0.0`.

Two things this child owes it:

- **`entry.snapshot.followup_kind` is the ghost fallback.** Archived /
  missing / cross-repo trail entries resolve to no live `Task`, so the live
  path cannot serve them. Once this child lands, t1470 wires the snapshot
  field in as a one-line fallback for exactly that case.
- **Tell the user to refresh before t1470 is verified.** The `1.1.0` bump
  invalidates `art:trail-gates-framework-landing` and
  `art:trail-shadow-review-loop` until refreshed, and t1470's acceptance
  criteria are written against both. If this child lands first, the refresh is
  a prerequisite for verifying t1470 — the resulting `ERROR:invalid_trail` is
  expected, not a t1470 defect.

Whichever lands first, re-read the other's scope section before planning.
