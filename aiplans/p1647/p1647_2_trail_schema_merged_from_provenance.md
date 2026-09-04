---
Task: t1647_2_trail_schema_merged_from_provenance.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_3_trail_merge_preflight_helper.md, aitasks/t1647/t1647_4_merge_trails_skill_and_codeagent_op.md, aitasks/t1647/t1647_5_board_bytrail_fold_trails_command.md, aitasks/t1647/t1647_6_merge_trails_docs_website_and_rfc.md, aitasks/t1647/t1647_7_manual_verification_merge_trails.md
Archived Sibling Plans: aiplans/archived/p1647/p1647_1_promote_trail_discovery_seams_to_lib.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-04 12:58
---

# Plan: t1647_2 — `merged_from` merge provenance in the trail schema

**Verify-path re-plan.** The existing plan `aiplans/p1647/p1647_2_*.md` was
re-checked against the live tree. Its core schema shape and its
optional-additive precedent hold. One of its directives is **wrong and would
land a defect** (finding 1), four contracts it leaves unstated turn out to be
load-bearing (findings 2, 2a, 2b, 2c), one work item is already done (3), and
one names half the files it must touch (4). This plan supersedes it.

## Context

t1647 adds trail-to-trail merge (fold): one trail is re-authored into another
and the folded source is retired via `ait artifact rm`. A merged trail must
record where it came from — so a human can see the fold happened, and so an
**interrupted retirement is deterministically resumable** (t1647_3 reads the
recorded version of the folded source to know what it was about to remove).

This child owns the schema half only: an OPTIONAL root property `merged_from`,
added **optional-additive with no `schema_version` bump**. That constraint is
load-bearing and verified: the root is `additionalProperties: false` and
`schema_version` is `const "1.1.0"`, which `trail_schema.py`'s loader rejects
any deviation from — so a required field or a version bump would turn all five
live trails and all three fixtures into `ERROR:invalid_trail` at once.

## Verification findings (what changed vs. the existing plan)

### 1. BLOCKING — the `generation.inputs` convention breaks drift entirely

The old plan (and the parent task, and sibling plan p1647_4) direct the producer
to add one `{"kind": "other", "ref": "<handle>@<version>"}` record to
`generation.inputs` per source trail. **This must not be done.**

`_classify_stored_inputs` (`.aitask-scripts/lib/trail_gather.py:1159-1182`)
routes every `board_state` / `gate_ledger` / `other` record to a staged error —
its docstring states the rule: *"every accepted kind has a defined live
resolver, or the verdict is refused"*. Line 1372 then does:

```python
if errors:
    emit_errors(out, sorted(set(errors)))
    return 0
```

So **one** `other` input refuses the **entire** drift verdict, not just that
input. `tests/test_trail_gather.py:907` (`test_content_kinds_without_resolver_fail_closed`)
pins exactly this for `other`: `verdict is None` plus an `undriftable_input:`
error. The drift path is live from the board (`aitask_board.py:1286`) and from
`/aitask-trail` refresh (`SKILL.md.j2:151, 295, 464, 654`) — so every merged
trail would report `ERROR:undriftable_input:` and carry no staleness verdict,
permanently.

Adding a *resolvable* artifact input kind does not rescue this: the folded
source is retired by the same merge operation, so it would resolve
`exists: false` → a permanent, false drift reason. A retired artifact is
deliberately gone; presence-tracking it is semantically wrong for a field whose
own schema description reads *"presence-tracked so a deleted input is itself
detectable drift"*.

**Settled (user decision):** `merged_from` is the **sole** carrier of merge
provenance. `generation.inputs` carries only the unioned task/plan refs of the
source trails and gets **no** artifact records. This is structurally sound
already: `input_digest` / `canonical_input_snapshot`
(`trail_schema.py:704-744`) hash `generation.inputs` only, so `merged_from` —
a **root** property outside `generation` — never enters the staleness snapshot.
Merge provenance is immutable history; drift inputs are live-resolvable
sources. They are different things and now live in different places.

**Deviation recorded:** this contradicts the "Convention" paragraph in
`aitasks/t1647/t1647_2_*.md` and the parent task's merge-provenance bullet.
The deviation is deliberate and is documented in the schema `description`
itself so no later reader re-derives the broken convention.

### 2. BLOCKING — `merged_from` semantics are unfixed by the shape

The array has `minItems: 1` and no ordering or uniqueness rule, so the shape
alone does not say whether a second merge extends, replaces, or inherits.
Leaving it unstated hands t1647_4 an undocumented choice in the one field whose
whole purpose is to be trustworthy after the fact — and the schema
`description` is this task's only carrier for it.

**Settled: `merged_from` is DIRECT merge/recovery provenance — a one-hop
record, not an ancestry ledger.** It describes exactly the merge that produced
*this* document version:

- the **base's pre-merge snapshot** *and* the **folded source's snapshot**,
  sharing one `merged_at` (they describe one event);
- written **wholesale** on each merge — a previous value is replaced, not
  extended. No inherited ancestry, and therefore no dedup and no ordering rule.

Both records are required, and finding 1 makes the base record *indispensable*
rather than merely nice to have: once artifact refs are out of
`generation.inputs`, `merged_from` becomes the **only** place recording which
version of the base the merged document was authored from.

This is exactly what the field's two stated jobs need: interrupted-retirement
recovery needs the *current* folded source's handle and version, and "which
base version was this authored from" needs the *current* base record. Neither
reads an ancestor. Carrying ancestry would instead grow every descendant
document without bound with progressively staler design history — records
naming handles long retired and versions long superseded, which nothing ever
corrects.

**Deeper ancestry stays recoverable without storing it** — verified, since that
is the claim this decision rests on:

- the artifact store **retains full version history**
  (`ait artifact versions art:trail-shadow-review-loop` → 6 versions, `*`
  marking current) and `ait artifact get <handle> --version <sha256:…>` fetches
  any of them;
- each `merged_from` record's `version` **is** that fetch key, so the previous
  hop is one command away: read a merged doc's base record → fetch that base
  version → read *its* `merged_from` → repeat. The walk terminates at a
  document with no `merged_from`;
- the retired folded source's blob is recoverable from data-branch git history
  (the parent task's `ait artifact rm` note).

Direct provenance therefore already makes the chain traversable; carrying it
forward would only cache it, at permanent cost in every document.

**This vindicates the original recipe.** p1647_4's `merged_from`: "TWO entries
— folded source AND the base's pre-merge version" is correct as written, and
step 6 no longer changes it. What p1647_4 still gets wrong is the
`inputs`/digest handling (2b) and the result scope (2c).

The schema description states the wholesale-replacement rule and names the
`--version` walk, so a later reader does not "restore" transitivity as a
perceived omission; the fixture carries one two-record group; a test pins the
cardinality and that both records are present.

### 2a. BLOCKING — wholesale writes can erase a pending retirement obligation

Wholesale replacement (finding 2) is safe only if no merge is ever authored
while a previous merge's retirement is still outstanding. **t1647_3's planned
detection does not guarantee that.** `aiplans/p1647/p1647_3_...md:64` keys the
half-merge check on the **caller-supplied** folded handle:

> *"if the base doc has a `merged_from` entry whose `handle` == folded handle"*

The failure sequence is concrete:

1. Merge A+B writes the merged doc to A with `merged_from = [A@pre, B@vB]`;
   the retirement of B is interrupted (some owner still references the handle),
   so **B still resolves at `vB`**.
2. The user later requests **A+C**. Step 3 looks for a record whose `handle`
   == C, finds none (the records name A and B), and falls through to emit a
   full merge plan.
3. The A+C merge writes `merged_from = [A@pre2, C@vC]` wholesale — **erasing
   the B record**, which was the only recovery handle for a live trail whose
   content is already absorbed into A. B is now orphaned with nothing recording
   that it should have been retired.

Under a cumulative design the B record would have survived the write, so this
is a hazard my finding-2 decision sharpens rather than one it invents — which
makes closing it part of this task's contract, not an unrelated bug.

**Settled: the obligation is keyed on the record, not on the caller's
argument.** Before authoring any new merge, preflight must inspect **every**
folded-source record in the base's current `merged_from` — identified as the
record whose `handle` differs from the resolved base handle, which the
exactly-two-records-with-distinct-handles contract makes unambiguous — and:

- still resolves at its recorded `version` → `RESUME:retirement_pending` for
  **that** handle and stop, whatever folded ref the caller passed;
- resolves at a different version → `ERROR:merge_conflict` for that handle;
- no longer resolves → that retirement completed; continue.

The base's own record is excluded by construction: A is live but has moved past
the recorded pre-merge version, so a rule that did not exclude it would fire
`merge_conflict` on every well-formed merged document.

This is the structural fix — it prevents the orphan rather than recording it,
so the wholesale write can never happen with a live obligation outstanding.
**Alternative considered and rejected:** carrying forward only *unresolved*
obligations across merges. It is self-limiting (records drop out once
retirement completes), but it makes the array's content depend on live
resolution state at write time — derived state inside a provenance record — and
breaks the two-record contract and its test for no gain over blocking.

### 2b. BLOCKING — `input_digest` recomputation is unspecified for the union

Finding 1 changes `generation.inputs` to the union of the source trails'
task/plan refs. p1647_4:88-89 says only *"recompute `input_digest` policy: reuse
the base's digest inputs contract"* — which does not say how, and admits reusing
the base's digest. Verified why that fails:

- `_normalize_input_record` (`trail_schema.py:615-670`) requires `exists` (bool)
  plus per-`(kind, exists)` state fields. The **stored** `generation.inputs`
  records carry only `{ref, kind}` (schema `required: ["ref","kind"]`,
  `additionalProperties: false`). So the digest **cannot** be computed from the
  stored inputs at all — `canonical_input_snapshot` raises on every one.
- `input_digest` is a truncated sha256 over the sorted canonical *live* records,
  so two source digests **cannot** be combined; you need the underlying records.

A producer that reuses the base's digest therefore ships a document whose stored
digest cannot match a recomputation over the union — drift reports **STALE
immediately after a successful merge**, while every schema and depth check
passes. Nothing in the current plan set would catch it.

**Settled recipe (written into p1647_4 by step 6):** take **one** fresh
gatherer snapshot over the deduplicated union of both sources' scope ids and
write its returned input pairs **and** its digest together, from that single
run — never reuse, and never combine, the source digests. `snapshot` emits both
from one stability-guarded pass (`trail_gather.py:1121`); verified executable:

```
$ ./.aitask-scripts/aitask_trail_gather.sh snapshot --scope multi_topic 1647 1210
SCOPE:multi_topic|aitasks#1210,aitasks#1647
… 22 × INPUT:…
DIGEST:8b9081ce3f769609
```

This is the same inputs-and-digest-from-one-snapshot pairing the test harness
already models (`make_trail(snap)` builds `inputs` from `snap["inputs"]` and
uses `snap["digest"]`).

### 2c. BLOCKING — the result scope, and an unexecutable instruction of my own

The previous revision of step 6 said *"`--scope` matching the merged document's
own `scope.kind`"*. That is **unexecutable**: `snapshot --scope` accepts exactly
`("task", "topic", "multi_topic")` (`trail_gather.py:1608`), while the schema's
`scope.kind` also permits **`ad_hoc`** — argparse rejects it outright. This is
not hypothetical: **2 of the 5 live trails are `ad_hoc`**
(`art:trail-gates-framework-landing`, `art:trail-shadow-review-loop`), so a
merge involving either would hit it immediately. And p1647_4 never defines the
result scope for a mixed pair at all (no `ad_hoc` mention anywhere in it).

**No new gatherer capability is needed** — the framework already settles both
halves, and the policy should reuse those seams rather than invent one:

- `.claude/skills/aitask-trail/SKILL.md.j2:323` — *"the gatherer has no ad_hoc
  mode — map it to task scope: `--scope task <selected ids...>`"*, storing
  `scope.kind: "ad_hoc"` plus a `selection_note`.
- `SKILL.md.j2:526-532` (the refresh re-snapshot rule — the same
  stored-trail-to-snapshot-call problem): `task`/`ad_hoc` → `--scope task` over
  the **stored `generation.inputs` task_file refs** (the complete recorded
  member set, never just the initiating task); `topic`/`multi_topic` →
  `--scope topic` / `--scope multi_topic` over the `scope.topics` roots.
- `SKILL.md.j2:404-408` (scope widening) — *"the gatherer cannot mix scopes"*:
  adding tasks to a topic trail becomes `--scope task <all member ids>` recorded
  as `ad_hoc`; adding a topic to a topic trail becomes `multi_topic`.

**Settled result-scope policy** (written into p1647_4 by step 6):

| base `scope.kind` | folded `scope.kind` | result `scope.kind` | snapshot call | membership |
|---|---|---|---|---|
| `topic` | `topic` | `multi_topic` | `--scope multi_topic <union of roots>` | live per topic |
| `topic`/`multi_topic` | `topic`/`multi_topic` | `multi_topic` | `--scope multi_topic <union of roots>` | live per topic |
| any pair where **either** side is `task` or `ad_hoc` | | `ad_hoc` | `--scope task <union of both sources' recorded member ids>` | pinned to the exact union |

`scope.topics` on the result is the union of both sources' `topics` in every
row — the schema calls it *"a projection, not an assignment"*, so it never
defines membership. The result `selection_note` must name both source handles
and the rule row applied.

This answers the widening worry directly, in both directions: keeping the base's
topic would indeed lose live detection for the folded topic, so topic∪topic
becomes `multi_topic` (topic membership being live is what a topic trail
*means*); and any pair touching a `task`/`ad_hoc` source becomes `ad_hoc` over
the exact recorded union, so nothing widens beyond the two sources.

Drift itself is scope-kind-agnostic — it reads `generation.inputs`, not
`scope.kind` — verified: `drift --trail art:trail-shadow-review-loop`
(an `ad_hoc` trail) returns `CURRENT`. So the exposure is entirely in the
producer's snapshot call, which is what the table fixes.

### 3. The schema-copies guard already exists — that work item is a no-op

The old plan says "Add a schema-copies byte-identical assertion if none exists
yet". One does: `SchemaCopyDrift.test_lib_schema_byte_identical_to_aidocs_contract`
at `tests/test_trail_schema.py:66`, comparing `read_bytes()` of both copies. Do
not add a second.

### 4. There are TWO `FIXTURE_NAMES` lists, not one

| list | drives | consequence of missing it |
|---|---|---|
| `tests/test_implementation_trail_design.py:22` | `test_no_unexpected_fixture_files` (:45) globs `*.json` and asserts equality | **hard failure** — the suite goes red |
| `tests/test_trail_schema.py:42` | `ValidFixtures.test_fixtures_load_from_path_and_bytes` (:434), `test_fixtures_have_no_issues` (:444) | **silent under-coverage** — the new fixture is never run through the real validator, and nothing goes red |

The second is the dangerous one: the old plan's Verification claims "the suite
does this; just run it", which is false for the new fixture unless this list is
extended too.

### 5. The fixture MUST carry `rendering_hints.depth: "deep"`

The old plan never says so, but its own verification step fails without it:
`_check_depth_contract` (`trail_schema.py:345`) requires the document's marker
to equal the caller's `--expect-depth`. This makes `merged_trail.json` the
**first fixture in the corpus to record a depth marker at all** — the other
three carry none (verified) — so every fixture-iterating test in both files
exercises the marked path for the first time.

### 6. Remaining feasibility claims re-confirmed

`$defs/timestamp` exists with the `…Z` pattern. Root `required` (10 keys) does
not and must not gain `merged_from`. The `overview` precedent is real but is a
**nested** (`narrative`) property — this is the first *root* optional-additive
add; the argument carries because `narrative` is itself
`additionalProperties: false`. Live artifact versions are content digests:
`sha256:33bc627…` full, `33bc62715b61` as `ait artifact ls` prints — the fixture
should use realistic short digests.

## Steps

### Pre-phase (risk mitigations)

1. `[state_merged_from_accumulation]` The `merged_from` `description` authored in
   main step 1 MUST state all three settled contracts explicitly: (a) the array
   is **direct, one-hop** provenance written **wholesale** — a merge replaces any
   previous value and inherited ancestry is deliberately not carried forward;
   (b) each merge writes **exactly two** records sharing one `merged_at` — the
   base's pre-merge snapshot and the folded source's; (c) deeper ancestry needs
   no storage because each record's `version` is the exact
   `ait artifact get <handle> --version` key, making the chain walkable — say
   this explicitly, so a later reader does not "restore" transitive
   carry-forward as a perceived omission; (c2) the folded-source record is a
   **retirement obligation** until that source stops resolving — a producer must
   check every folded-source record (the one whose `handle` differs from the
   document's own) before authoring any new merge and finish a still-resolving
   retirement first, whatever trail the new merge names. This sentence is what
   makes wholesale replacement safe rather than lossy, so it is not optional;
   (d) merge provenance is deliberately
   **not** mirrored into `generation.inputs`, with the reason (inputs are
   live-resolvable drift sources; a retired trail has no resolver and an
   unresolvable kind refuses the whole verdict), which is also *why* the
   base-pre-merge record is indispensable — it is the only remaining record of
   the version this document was authored from. Verify the sentences are present
   and byte-identical in **both** schema copies.

### Main implementation

1. **Edit BOTH schema copies identically** — `aidocs/implementation_trail.schema.json`
   and `.aitask-scripts/lib/implementation_trail.schema.json`. Insert
   `merged_from` into root `properties` **after the `generation` block**
   (line 117 `},`, before `"freshness"`). Match the file's style: 2-space
   indent, compact `{ "$ref": … }` one-liners, inline enums.

   ```json
   "merged_from": {
     "description": "DIRECT provenance of the trail-to-trail merge that produced this document version -- one hop, not an ancestry ledger. Written by /aitask-merge-trails; absent on any trail that never absorbed another. Exactly two records sharing one merged_at: the base's pre-merge snapshot and the folded source's. Written WHOLESALE -- a merge REPLACES any previous value rather than extending it, and inherited ancestry is deliberately NOT carried forward, so a document never accumulates stale history naming retired handles and superseded versions. Deeper ancestry needs no storage because it is walkable: each record's version is the exact key for `ait artifact get <handle> --version <version>`, so reading a merged document's base record and fetching that version yields the previous merge's own merged_from, and so on until a document carries none; a retired folded source's blob remains recoverable from data-branch git history. The recorded version of the folded (retired) source is what makes an interrupted retirement deterministically resumable, and it is a RETIREMENT OBLIGATION until that source stops resolving: because a later merge replaces this value wholesale, a producer MUST check every folded-source record here -- the record whose handle differs from this document's own -- before authoring any new merge, and complete a still-resolving source's retirement first, regardless of which trail the new merge names. The base's pre-merge record is the only place recording which version this document was authored from, because merge provenance is deliberately NOT mirrored into generation.inputs -- those are live-resolvable sources whose presence is drift-tracked, a retired trail has no resolver, and an unresolvable input kind refuses the document's entire staleness verdict.",
     "type": "array",
     "minItems": 1,
     "items": {
       "type": "object",
       "additionalProperties": false,
       "required": ["handle", "version", "merged_at"],
       "properties": {
         "handle": { "type": "string", "minLength": 1 },
         "version": { "type": "string", "minLength": 1 },
         "title": { "type": "string" },
         "merged_at": { "$ref": "#/$defs/timestamp" }
       }
     }
   }
   ```

   Do **NOT** add `merged_from` to root `required`. Do **NOT** touch the
   `generation.inputs` `kind` enum. After editing, `diff` the two copies — they
   must be byte-identical.

2. **Fixture** — `aidocs/implementation_trail_examples/merged_trail.json`, a
   small **deep** trail (2 waves, 3 entries) modeled on
   `cross_topic_multiple_trails.json` (the smallest existing fixture, 4.9 KB).
   It must carry:

   - `rendering_hints: { "depth": "deep" }` — finding 5;
   - `merged_from` carrying **exactly two records** sharing one `merged_at` —
     the base's pre-merge snapshot and the folded source's — with distinct
     `handle`s and realistic 12-hex `version` digests. The `merged_at` should
     equal `generation.generated_at` (the merge authored this version). Give
     the base record the same handle the fixture's own trail would live under,
     so the walk-back key is self-evidently the base's own handle;
   - **no** artifact refs in `generation.inputs` — only task/plan refs, per
     finding 1;
   - deep shape: per-entry `evidence_refs`, plus `observations` / `relations` /
     `exclusions` (a lite trail must omit these, so their presence is what makes
     the fixture a genuine deep example rather than a lite one wearing a marker).

   It must satisfy every existing contract check in
   `tests/test_implementation_trail_design.py`: project-qualified `task` **and**
   `topic` refs matching `^[a-z0-9_-]+#[0-9]+(_[0-9]+)?$`; `trail_id` matching
   `^trail-[a-z0-9][a-z0-9_-]{2,63}$`; unique `local_id`s; strictly increasing
   wave `ordinal` and per-wave `position`; every `evidence_refs` id resolving to
   an `evidence[].evidence_id`; every relation endpoint appearing elsewhere in
   the document (entries, exclusions, `observations[].affects`, or a recorded
   `snapshot.depends`) with `provenance` in `fact|advisory`; non-empty
   `rationale` per entry and `purpose` per wave; and **no `anchor` key at any
   depth** (`test_no_anchor_encoding` walks the whole document).

3. **Tests — `tests/test_trail_schema.py`.**
   - Extend `FIXTURE_NAMES` (:42) with `merged_trail.json` — finding 4.
   - A `merged_from` test class in the file's existing style (deep-copy a
     fixture, mutate, assert on `issues_for` / `rules`):
     - valid `merged_from` accepted;
     - **document without `merged_from` still valid** — the backward-compat
       case, and the load-bearing assertion; `ValidFixtures` over the three
       unmarked fixtures is its corpus-level twin;
     - rejected shapes: missing `version`, extra key under `items`, empty array
       (`minItems`), non-timestamp `merged_at`.

4. **Tests — `tests/test_implementation_trail_design.py`.**
   - Extend `FIXTURE_NAMES` (:22) — `test_no_unexpected_fixture_files` requires
     it.
   - **Direct-provenance check** (stdlib-only, the file's style): the fixture's
     `merged_from` has **exactly 2 records**, with **distinct `handle`s**, a
     **single shared `merged_at`**, and a non-empty `version` on each (the
     version is the walk-back fetch key, so an empty one would break the
     documented recovery path). This is what fails a producer that records only
     the folded source and drops the base's pre-merge version.

     Do **not** assert anything about inherited ancestry: `merged_from` is
     one-hop by contract, so there is nothing to accumulate and no dedup or
     ordering rule to pin.
   - **Exclusion check**: no `generation.inputs` record's `ref` equals any
     `"<handle>@<version>"` or bare `handle` from `merged_from`, and no input
     record has `kind == "other"`. This makes finding 1's decision executable
     instead of prose.
   - `test_no_root_keys_outside_schema` picks up the new key automatically (it
     reads `schema["properties"]`) — no edit needed there.

5. **Test — the drift regression (`tests/test_trail_gather.py`).** The
   production-reachable proof for findings 1 and 2b. In `DriftableInputTests`
   (:891, which has `self.repo` / `snapshot` / `make_trail` / `drift`), add the
   positive twin of `test_content_kinds_without_resolver_fail_closed`. It must
   be shaped like a **real merged document** — a union snapshot, not the
   single-root `self.snap` — or it would not exercise what a merge actually
   produces:

   ```python
   def _merged_shaped_trail(self):
       """A trail over the UNION of two roots, carrying merge provenance —
       the shape /aitask-merge-trails emits. Inputs AND digest come from ONE
       snapshot run (trail_gather.py:1121): stored {ref,kind} records lack the
       `exists`/state fields _normalize_input_record requires, so the digest
       can never be derived from them or combined from two source digests."""
       self.repo.write_task("200", "folded-root")
       snap = self.snapshot("--scope", "multi_topic", "100", "200")
       trail = self.make_trail(snap, scope_kind="multi_topic",
                               topics=["mainproj#100", "mainproj#200"])
       doc = json.loads(trail.read_text())
       doc["merged_from"] = [
           {"handle": "art:trail-base", "version": "aaaaaaaaaaaa",
            "title": "Base, pre-merge", "merged_at": "2026-09-03T10:00:00Z"},
           {"handle": "art:trail-folded", "version": "bbbbbbbbbbbb",
            "title": "Folded source", "merged_at": "2026-09-03T10:00:00Z"},
       ]
       self.assertEqual(trail_schema.validate_trail(doc), [])
       trail.write_text(json.dumps(doc))
       return trail

   def test_merged_document_is_current_immediately_after_merge(self):
       """Root-level merge provenance perturbs neither the digest nor the
       verdict — which is why t1647_2 put it at the root instead of mirroring
       it into generation.inputs (the sibling test pins that an `other` INPUT
       refuses the whole verdict, trail_gather.py:1372)."""
       result = self.drift(self._merged_shaped_trail())
       self.assertEqual(result["errors"], [])
       self.assertEqual(result["verdict"], "CURRENT")

   def test_merged_document_goes_stale_when_a_source_changes(self):
       """The negative control: CURRENT above must be a live verdict over the
       union, not an artefact of nothing being checked."""
       trail = self._merged_shaped_trail()
       self.repo.write_task("200", "folded-root", status="Done")
       result = self.drift(trail)
       self.assertEqual(result["verdict"], "STALE")
   ```

   Add an `ad_hoc`-labelled variant of the same pair (`scope_kind="ad_hoc"`
   over a `--scope task` snapshot of the union), since `ad_hoc` is the kind
   with no snapshot verb and 2 of the 5 live trails carry it.

   **Scope this test's claim honestly — it is a document/drift regression, not
   a scope-selection proof.** Drift deliberately reads `generation.inputs` and
   never `scope.kind`, and the test builds its own snapshot, so it would still
   pass if the producer later invoked an unsupported `--scope ad_hoc`, omitted
   members from the union, or reused a source digest. Docstring it as: *an
   `ad_hoc`-labelled merged document with root merge provenance drifts
   normally* — and nothing more. The executable proof that the producer
   **selects** the right scope and digest lives on t1647_4's surface; step 6
   requires it there. Do not let this test's name or docstring imply otherwise:
   a guard that cannot fail for the thing it is named after is worse than no
   guard, because it retires the concern.

   Adapt the `write_task` kwargs, the canonical project prefix, and
   `make_trail`'s `scope_kind`/`topics` handling to the harness's own
   conventions (read `TrailGatherCase` / neighbouring tests) rather than
   assuming the spellings above.

   Prove the first test discriminates: temporarily also append the base handle
   as an `{"kind": "other"}` input and confirm it fails with
   `undriftable_input:` — that is the exact defect finding 1 removes.

6. **Correct the sibling plans** (user-approved for p1647_4/p1647_6; p1647_3 is
   added here because finding 2a lands squarely in it. All three are pending and
   unstarted, so nothing is superseded):

   **`aiplans/p1647/p1647_3_...md` (preflight) — finding 2a:**
   - Step 3 (`:63-72`) — replace the caller-keyed condition *"a `merged_from`
     entry whose `handle` == folded handle"* with: iterate **every**
     folded-source record in the base's `merged_from` — the record whose
     `handle` differs from the **resolved base handle** — and apply the existing
     three-way outcome to each (`RESUME:retirement_pending` when it still
     resolves at its recorded `version`, `ERROR:merge_conflict` when the version
     moved, continue when it no longer resolves). State explicitly that this
     runs **regardless of which folded ref the caller passed**, and that
     excluding the base's own record is required (the base is live but has moved
     past its recorded pre-merge version, so including it would fire
     `merge_conflict` on every well-formed merged document).
   - Its heading "Half-merged detection FIRST (reference-aware)" should say
     *record-aware*, not reference-aware — the rename is the point of the fix.
   - Add to its `## Verification` the regression this hole needs: **partial A+B
     followed by a requested A+C**. Set up a base whose `merged_from` names a
     still-resolving B at its recorded version, invoke
     `preflight -- A C`, and assert it emits
     `RESUME:retirement_pending|<B>|…` with **no plan lines** — never a
     `BASE:`/`FOLDED:` plan for A+C. Add the negative control: once B no longer
     resolves, the same call emits a normal A+C plan. Without the control the
     test cannot distinguish "blocked correctly" from "blocked always".

   **`aiplans/p1647/p1647_4_...md` (producer) and `p1647_6` (docs):**
   - `aiplans/p1647/p1647_4_...md:81-83` — **no change needed.** Re-verification
     vindicated the existing "`merged_from`: TWO entries — folded source AND the
     base's pre-merge version" recipe (finding 2). Add only a one-line note that
     the two records share one `merged_at` and that the value is written
     wholesale (a later merge replaces it), citing the schema description as the
     contract.
   - `aiplans/p1647/p1647_4_...md:86-89` — delete the "PLUS one
     `{"kind": "other", "ref": "<handle>@<version>"}` per source" clause from
     the `inputs` bullet, and replace the vague "recompute `input_digest`
     policy: reuse the base's digest inputs contract" with the settled recipe
     (finding 2b): take **one** `aitask_trail_gather.sh snapshot` run over the
     **deduplicated union**, with `--owner` the base's owner, and write that
     run's `INPUT:` pairs as the `{ref, kind}` records **and** its `DIGEST:`
     value into the merged document **together**. State explicitly that the
     source digests are never reused or combined, and why (stored `{ref, kind}`
     records lack the `exists`/state fields the normalizer requires, so no
     digest is derivable from them). Add a one-line note naming this task as the
     decision's origin.
   - `aiplans/p1647/p1647_4_...md` — add the **result-scope policy table** from
     finding 2c as a new step preceding the authoring step, since it decides both
     the stored `scope.kind` and the snapshot call. State plainly that there is
     no `--scope ad_hoc` (`trail_gather.py:1608`) and that an `ad_hoc` result
     snapshots as `--scope task <union of recorded member ids>`, citing the
     existing `SKILL.md.j2:323 / 526-532 / 404-408` rules as the seam being
     reused rather than a new convention. Require the result's
     `scope.selection_note` to name both source handles and the rule row
     applied, and `scope.topics` to be the union of both sources' topics.
   - `aiplans/p1647/p1647_4_...md` — add the **executable scope-selection and
     digest proof** as a required deliverable, because this task's drift tests
     structurally cannot provide it (they build their own snapshot; drift never
     reads `scope.kind`). The parent task already requires a contract test for
     the new skill; specify what it must pin, modelled directly on
     `tests/test_trail_skill_contract.sh` — which asserts markers in **all
     three committed goldens** (default / fast / remote) and already pins
     `/aitask-trail`'s ad-hoc scope mapping at :135-140
     (`'ad-hoc maps to task scope'`, `'scope.kind: "ad_hoc"'`). The
     `/aitask-merge-trails` equivalent must pin, per profile:
     - the result-scope policy rows (finding 2c), including that an `ad_hoc`
       result snapshots as `--scope task <union of recorded member ids>` and
       that no `--scope ad_hoc` exists;
     - that inputs and digest come from **one** snapshot run over the
       deduplicated union, and that source digests are never reused or combined;
     - that `merged_from` is written wholesale as exactly two records (base
       pre-merge + folded source) and never accumulates inherited ancestry;
     - that the producer refuses to author a merge while preflight reports
       `RESUME:retirement_pending` — the consumer-side half of finding 2a,
       without which the corrected detection is advisory.

     This is the pin that fails when a future edit reintroduces
     `--scope ad_hoc`, a partial union, or a reused digest — the failure modes
     this task's tests are blind to.
   - `aiplans/p1647/p1647_4_...md` — add to its `## Verification`: the merged
     document must report **CURRENT** on
     `aitask_trail_gather.sh drift --trail <merged>` immediately after the
     merge, and **STALE** after mutating one source's task state — checked for
     **both** a same-scope (`topic`∪`topic` → `multi_topic`) and a mixed-scope
     (→ `ad_hoc`) merge, since only the second exercises the kind with no
     snapshot verb. A merged document that is stale the moment it is written is
     the failure this recipe exists to prevent.
   - `aiplans/p1647/p1647_6_...md` — add a note that the RFC prose must state
     that merge provenance is deliberately outside `generation.inputs`, and add
     `merged_from` to the RFC's root field-group list
     (`aidocs/implementation_trail_design.md:225-256`). **Do not edit the RFC
     itself here** — that is t1647_6's deliverable and is not test-pinned.

7. **No validator change.** Deep-wins depth reconciliation is preflight policy
   and belongs to t1647_3. `_check_depth_contract` / `_check_lite_shape` /
   `--expect-depth` already enforce marker-matches-authoring and lite shape —
   leave `.aitask-scripts/lib/trail_schema.py` untouched.

### Post-phase (risk mitigations)

1. `[sync_fixture_name_lists]` Add a guard that the two fixture-corpus lists
   cannot diverge. Preferred shape: in `tests/test_implementation_trail_design.py`
   (the file that already owns the corpus pin), import the sibling list and
   assert set equality —

   ```python
   def test_fixture_name_lists_agree(self):
       """Two independently maintained corpus lists; only one fails loudly when
       a fixture is added to it alone (t1647_2). Pin them to each other."""
       import test_trail_schema
       self.assertEqual(sorted(FIXTURE_NAMES),
                        sorted(test_trail_schema.FIXTURE_NAMES))
   ```

   Resolve the import against how the runner loads these modules (both live in
   `tests/`; `test_trail_schema` does `sys.path.insert` on the lib dir at import
   time, which is harmless here). If the import proves fragile under the pytest
   lane, fall back to parsing the sibling file's literal with `ast` — do **not**
   fall back to deleting one list, which would drop the corpus pin.

   Prove the guard can fail: temporarily remove `merged_trail.json` from one of
   the two lists and confirm this test goes red before restoring it.

## Verification

- `diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json`
  → empty.
- `./.aitask-scripts/aitask_trail_depth.sh validate aidocs/implementation_trail_examples/merged_trail.json --expect-depth deep`
  → `VALID:<trail_id>` (the check that fails if finding 5 is ignored).
- Negative control for the same: flip the fixture's marker to `"lite"` in a
  scratch copy → the same command must report `depth_marker` **and**
  `lite_shape` issues, proving the assertion is not vacuous.
- `bash tests/run_all_python_tests.sh --test-dir tests` green — read **only**
  the last line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); do not pipe
  to `tail` without `pipefail`.
- Targeted: `test_trail_schema.py`, `test_implementation_trail_design.py`,
  `test_trail_gather.py` (step 5's union-shaped drift regression is the one
  that would have caught both the finding-1 and finding-2b defects; step 4's
  group-cardinality check is the one that catches finding 2).
- Existing live trails still load and still drift: `./.aitask-scripts/aitask_trail_gather.sh
  drift --trail art:trail-shadow-review-loop` returns a verdict, not
  `ERROR:undriftable_input`.

## Risk

### Code-health risk: medium
- The fixture corpus is pinned by **two independently maintained
  `FIXTURE_NAMES` lists** (`test_trail_schema.py:42`,
  `test_implementation_trail_design.py:22`). Only one fails loudly when a
  fixture is added without updating it; the other silently stops validating the
  new fixture. This task adds a fixture and so makes the divergence live.
  · severity: medium · → mitigation: inline post-phase sync_fixture_name_lists
- Editing a sibling's pending plan (step 6) is cross-task surface. Bounded: both
  plans are unstarted, the edits are a few lines, and leaving them guarantees the
  finding-1 defect lands. · severity: low · → mitigation: none needed
- Both schema copies must stay byte-identical across a hand edit. Already
  guarded by `SchemaCopyDrift` (`test_trail_schema.py:66`). · severity: low
  · → mitigation: none needed (existing guard)
- No production code path changes: an additive optional property plus
  test/fixture data. · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- The plan **deliberately deviates** from the convention stated in the task file
  and the parent task (artifact refs in `generation.inputs`). The deviation is
  correct — the convention as written makes every merged trail permanently
  undriftable (finding 1, pinned by `tests/test_trail_gather.py:907`) — and is
  user-approved, but it must reach t1647_4 and t1647_6 or the defect returns
  through them. · severity: medium · → mitigation: inline main step 6
  (sibling-plan correction) + the schema description as the durable carrier
- `merged_from` semantics are not fixed by the shape alone (an array with
  `minItems: 1`, no ordering or uniqueness rule), so the producer would be left
  to choose between extend, replace and inherit. Settled as one-hop
  direct provenance written wholesale; the residual is that a later reader may
  see the absent ancestry as an omission and "restore" it, reintroducing
  unbounded growth. · severity: medium · → mitigation: inline pre-phase
  state_merged_from_accumulation — the description states the wholesale rule
  *and* names the `--version` walk that makes ancestry recoverable, so the
  omission reads as a decision + step 2/4 (two-record fixture and an
  exactly-2/distinct-handles assertion)
- **Wholesale replacement can erase a pending retirement obligation** (finding
  2a): t1647_3's caller-keyed half-merge check misses a still-live B when the
  user requests A+C, and the A+C write then destroys B's recovery record. This
  is a hazard the finding-2 decision sharpens, so closing it belongs to this
  task's contract — but the detection lives in t1647_3 and the refusal in
  t1647_4, so this plan can state the invariant durably (schema description)
  and specify the fix, not execute it. · severity: medium · → mitigation:
  inline pre-phase state_merged_from_accumulation (clause c2 makes the
  obligation part of the field's definition) + step 6 (record-keyed detection,
  the A+B-then-A+C regression with its negative control, and a producer-side
  refusal marker)
- **The merged document's `input_digest` must be recomputed from one fresh
  snapshot over the union** (finding 2b). This task fixes the schema and pins
  the behaviour with a union-shaped drift test, but the producer lives in
  t1647_4 — a recipe correction (step 6) is the only lever here, and it cannot
  bind a future re-plan of that task. · severity: medium · → mitigation: inline
  main step 5 (union drift test, current-then-stale) + step 6 (explicit
  producer recipe and verification criterion in p1647_4)
- **The result `scope.kind` and its snapshot call are undefined in p1647_4 for
  mixed pairs, and `ad_hoc` has no `--scope` value at all** (finding 2c) — live
  exposure, since 2 of the 5 stored trails are `ad_hoc`. Resolved by reusing the
  existing `SKILL.md.j2` ad_hoc→task and refresh re-snapshot rules rather than
  adding gatherer capability, so no new surface is introduced. · severity:
  medium · → mitigation: step 6 (policy table + a golden-pinned contract test
  on the producer surface, modelled on `test_trail_skill_contract.sh`)
- **This task cannot prove the producer selects the right scope or digest.**
  Drift reads `generation.inputs`, never `scope.kind`, and step 5's tests build
  their own snapshots — so a wrong `--scope`, a partial union, or a reused
  source digest would leave them green. The coverage is deliberately split:
  document/drift regression here, scope-and-digest selection pinned in t1647_4's
  contract test. The residual is that the second half lives in another task and
  this plan can specify it but not enforce it. · severity: medium
  · → mitigation: step 6 (named deliverable with the exact markers to pin) +
  step 5's honest test scoping, so the gap is visible rather than papered over
- Everything else in the task's stated requirement was verified present and
  feasible against the live schema (findings 5–6). · severity: low
  · → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: state_merged_from_accumulation | type: feature | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — unspecified merged_from semantics, the retirement obligation, and the inputs-exclusion rationale | desc: State the one-hop wholesale-replacement rule, the exactly-two-records-per-merge shape, the folded-source record as a retirement obligation a producer must clear before any new merge, the artifact --version walk that keeps deeper ancestry recoverable, and the deliberate generation.inputs exclusion in the merged_from schema description, byte-identical in both copies.
- timing: post-phase | name: sync_fixture_name_lists | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — two independently maintained FIXTURE_NAMES lists | desc: Add a guard asserting the two fixture-corpus lists name the same set, so a fixture can never be added to only the loud one.

### Reassessment (post-inline)
Seven blocking findings were resolved by design decisions, not by deferring
work: merge provenance moved out of the drift snapshot entirely; `merged_from`
settled as one-hop direct provenance written wholesale, with the artifact
`--version` walk documented so the absent ancestry reads as a decision rather
than a gap; the safety precondition that wholesale replacement depends on became
an explicit, record-keyed retirement obligation; the digest recipe became a
single-snapshot-over-the-union rule; and the result-scope policy reuses the
framework's existing `ad_hoc`→`--scope task` mapping instead of adding gatherer
capability.

Two findings reversed earlier revisions of this plan — the ledger design was
traded for the walk once the artifact store was confirmed to retain every
version and to fetch by digest, which is what made stored ancestry redundant
rather than merely costly. The net effect on this task's own surface is still a
**smaller** change than the ledger revision: no dedup rule, no ordering rule, a
two-record fixture instead of six.

What grew instead is the specification carried into siblings: finding 2a is the
cost of the simpler field, and it is paid in t1647_3 (record-keyed detection +
an A+B-then-A+C regression with a negative control) and t1647_4 (a refusal
marker). Goal-achievement therefore stays at **medium** and would be
dishonest lower: this plan now settles four contracts whose enforcement lives in
three sibling tasks, and step 6 can specify them but not guarantee they survive
a re-plan. Code-health is unchanged at medium — two hand-maintained
`FIXTURE_NAMES` lists a guard reduces but does not erase.
