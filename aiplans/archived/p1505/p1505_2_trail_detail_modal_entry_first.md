---
Task: t1505_2_trail_detail_modal_entry_first.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/t1505/t1505_3_trail_narrative_overview_field.md, aitasks/t1505/t1505_4_trail_skill_lite_default.md, aitasks/t1505/t1505_5_manual_verification_lite_trail_mode_and_trail_summary_pane.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_1_bytrail_summary_pane.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-13 23:37
---

# p1505_2 — Entry-first trail detail modal

Fixes the By-Trail detail modal's wall of text. Depends on t1505_1 (same file,
landed as `c9f692fc9`), independent of t1468_5 (landed as `b25bb4893`).

## Context

`TrailDetailScreen._sections()` renders, for whichever card is focused: the
entry, its wave, the whole trail narrative, **every** drift reason, **every**
observation, **every** exclusion and **every** evidence record.

Against the live `art:trail-gates-framework-landing` that is 19 observations, 2
exclusions and 56 evidence lines — **byte-identical on every card**. Only the
leading entry/wave block differs, and it scrolls off the top. The code is not
wrong about what it has; it is wrong about scope, rendering document-level
content in an entry-level view. Intended outcome: the modal opens on what
distinguishes *this* entry, with the document-level bulk one key away.

## Verification pass (2026-08-13) — corrections to the previous plan

Re-verified against `main` at `c9f692fc9` (t1505_1 landed since this plan was
written). Anchors first:

| Claim in the previous plan | Reality |
|---|---|
| `_sections()` at `:3858` | **`:3874`** (`TrailDetailScreen` at `:3841`; `:3858` is now CSS) |
| `trail_drift_by_ref` at `:764` | **`:765`** |
| `canonical_trail_ref` at `:704` | **`:705`** |
| `tests/test_board_bytrail_view.py` is 3,335 lines | **3,946** lines (t1505_1 added 28 tests in 5 classes) |

**Correction 1 — the post-phase mitigation's premise is false, and it inverts
the risk.** The previous plan says the test file "pins current modal content"
and that "re-pointing those assertions is legitimate". It does not. The entire
file contains **one** reference to `TrailDetailScreen` — an `assertIsInstance`
at `:681` — and **zero** references to `_sections`. There are no modal-content
assertions to re-point, weaken, or preserve. The real hazard is the opposite of
the one recorded: the modal is **untested**, so this restructure starts with no
safety net at all. The mitigation therefore changes shape — content tests are a
*deliverable of this plan*, not a re-pointing exercise.

**Correction 2 — a naive `trail_drift_by_ref` filter silently breaks a
documented contract.** The helper deliberately **drops** trail-level reasons
(`task_ref == "-"`, e.g. `input_missing`), and its docstring (`:771-774`) states
they "stay visible in the subtitle count and **the trail detail modal**".
Filtering the modal's drift section through that helper alone would make them
unreachable in the default view and quietly falsify the docstring. The design
below keeps trail-level reasons in the default view (they are trail-scoped facts
with no owning card, and there are 0–2 of them) and pins that with a test.

**Correction 3 — the reveal key is screen-scoped, not App-scoped.** The previous
plan says to gate it "with the same `check_action` discipline the other By-Trail
keys use", which describes `KanbanApp.check_action` (`:7705`). The reveal key
belongs to the **modal**, which declares no `_shortcuts_scope` (exactly like
`TrailSummaryScreen`, t1505_1) — so `lib/shortcut_scopes.py` needs no manifest
entry and the gate is `TrailDetailScreen.check_action`. Two consequences the
previous plan did not name:

- **Modals here mount no `Footer`.** No modal in `aitask_board.py` yields one, so
  a `show=True` binding surfaces nowhere. Discoverability has to be an
  **in-body hint line**, not a footer label — the same shape
  `tui_conventions.md` allows ("put the hint in the pane's own header text").
- **`a` is bound at App level** to `view_all` (`:7725`, `show=False`, **no**
  `priority=True`). A screen binding wins the chain, so the modal's `a` shadows
  it — but that is an assumption, and an unpinned one would mean pressing `a`
  silently switches the board to the `all` view behind the open modal. Pinned by
  a negative control below.

**Confirmed sound (verified first-hand):**

- `TrailDetailScreen(...)._sections()` runs **outside an App** — probed directly
  with the venv interpreter and it returns the expected `Text`. Content tests
  need no pilot, so they are cheap and exact (`.plain`). The pilot-driven
  `_dialog_text(app, widget)` helper (`tests/test_board_bytrail_view.py:115`)
  remains the surface for the one key-press test.
- The push site is `action_view_details` (`:9929`), which passes
  `self._trail_drift[1]` — **all** reasons, unfiltered — plus the focused card's
  `trail_entry` / `trail_wave` (`:9938`).
- `tests/test_implementation_trail_design.py` pins schema and fixtures only; no
  test pins design-doc prose, so §9/§15 can be edited freely.
- The task's active gate set is `risk_evaluated` only — no `docs_updated` gate,
  so the §9/§15 edits are this plan's own responsibility.

**Deviation from t1505_1's sibling note, stated explicitly.** That note says to
reuse `trail_summary_text` when the modal surfaces `overview`. This plan does
**not**: `trail_summary_text` resolves a *preference between two fields* for a
single-slot pane (overview, else recommendation_summary). The modal has room for
both, and using the resolver there would hide `recommendation_summary` — a
required field — whenever `overview` exists (t1505_3). The modal renders the
narrative fields as they are.

## Implementation steps

All changes are in `.aitask-scripts/board/aitask_board.py` (`TrailDetailScreen`,
`:3841-3951`), `tests/test_board_bytrail_view.py`, and
`aidocs/implementation_trail_design.md`.

### 1. `_scope()` — one partition, two consumers

Add a private helper on `TrailDetailScreen`, above `_sections()`. It partitions
the document into what concerns the focused entry and what is withheld, and is
the **single** source for both the rendering and the `check_action` gate — so
the hint line can never promise a reveal that would show nothing.

```python
def _scope(self) -> dict:
    """Partition the document three ways against the focused entry: owned by
    it, owned by another member, and UNOWNED.

    The modal is an ENTRY-level view: rendering every observation, evidence
    record and drift reason made each card's text ~95% identical to its
    neighbour's (19 obs / 56 evidence on the live gate-framework trail), so
    the part that distinguishes the focused entry scrolled off the top.

    Only the middle bucket is withheld. Unowned material — a trail-level or
    non-member drift reason (see `trail_drift_by_ref`), an observation
    affecting no member — has no owning card, so filing it under "other"
    would hide it on EVERY card instead of duplicating it on every card:
    strictly worse than the defect this scoping removes.

    Displayed evidence follows what is DISPLAYED, not just the entry: an
    observation shown here without the record it cites is an unsupported
    claim in an evidence-backed artifact. A record cited by nothing at all is
    unowned like the rest — and that is the whole of a lite trail's evidence,
    since the lite writer omits per-entry `evidence_refs` while the schema
    still requires >=1 record.

    Read by `_sections`, `check_action` and `action_toggle_all` alike; a
    second computation could let the hint offer a reveal that reveals
    nothing.  With no focused entry (`entry is None`) there is no anchor to
    scope against, so nothing is withheld and the full document renders."""
```

**The partition is three-way, not two-way.** *Owned by this entry* / *owned by
another entry* / **unowned**. Only the middle bucket is ever withheld. Collapsing
"unowned" into "other" is the trap: a fact that no card owns would then be
withheld from **every** card and reachable from nowhere in the default view —
strictly worse than the duplication this plan exists to remove.

Compute the member set once: `{canonical_trail_ref(r) for r in
trail_entry_refs(self.doc)}` (`trail_entry_refs` at `:784` returns raw refs, so
canonicalize each). Returned keys:

| key | contents |
|---|---|
| `entry_drift` | reasons whose canonical ref equals this entry's |
| `unowned_drift` | reasons with `task_ref` in `(None, "", "-")` **or** whose canonical ref is not in the member set |
| `other_drift` | the remainder — reasons owned by *another* member (**the only withheld drift**) |
| `entry_obs` | observations whose `affects` names this entry's ref |
| `unowned_obs` | observations whose `affects` is empty/absent **or** intersects no member ref |
| `other_obs` | the remainder (**the only withheld observations**) |
| `shown_evidence` | records resolved from the union of this entry's `evidence_refs`, the `evidence_refs` of every observation in `entry_obs` + `unowned_obs`, and every **uncited** record (cited by no entry and no observation anywhere in the document) — each tagged with what cited it |
| `other_evidence` | the remainder, as the same `(ref, record-or-None, provenance)` tuples — records cited only by *another* entry or observation, **plus any cited ref that resolves to no record at all** (**the only withheld evidence**) |
| `withheld` | `len(other_drift) + len(other_obs) + len(other_evidence)` |

Rules:

- **Every ref comparison goes through `canonical_trail_ref` (`:705`)** — on both
  sides, including the member set. A stored trail may spell a member
  `aitasks#t42` while drift reasons and `affects` entries use `aitasks#42`; that
  helper exists for exactly this mismatch and raw string comparison would
  silently drop matches.
- Bucket the per-entry drift with **`trail_drift_by_ref` (`:765`)** rather than
  re-filtering by hand — it already canonicalizes and groups. Derive
  `unowned_drift` separately from `self.drift_reasons`, because that helper
  deliberately discards **both** unowned categories — its docstring (`:771-774`)
  names them explicitly: *"Trail-level reasons (`task_ref` == "-", e.g.
  `input_missing`) **and reasons naming a task that is not a trail member
  (`new_related_task`)** have no owning card; they are dropped here and stay
  visible in the subtitle count and the trail detail modal."* A `new_related_task`
  warning is globally relevant and must not be filed under "for other entries".
- The same rule applies to observations, and the shipped fixture proves it is not
  hypothetical: `gate_framework.json`'s `obs-missing-model-defaults` carries
  `affects: []`. Treating it as "other" would hide it on every card.
- **Evidence follows what is displayed, not just the entry.** An observation's
  claim without its supporting record is a broken provenance path: on the
  `aitasks#635_29` card, `obs-red-suite` cites `ev-red-suite` while the entry
  itself cites `ev-premise-check`, so scoping evidence to `entry.evidence_refs`
  alone would show the claim and withhold its support until `a` is pressed. The
  union is always resolvable: the schema makes `observations.evidence_refs`
  **required** with `minItems: 1`.
- **Uncited evidence is unowned, not "other" — and the lite trail is exactly
  that case.** `entry.evidence_refs` is **optional** in the schema (absent from
  `entry.required`), while root `evidence` is **required** with `minItems: 1`.
  After t1505_4 the lite writer omits per-entry `evidence_refs` and emits exactly
  the one gatherer-snapshot record, so on the common trail **no entry cites
  anything** and that record is cited by nobody. Filing it under `other_evidence`
  would hang a reveal hint on a document that has nothing to reveal, and would
  contradict the lite-trail contract in step 2. A record cited by neither any
  entry nor any observation is therefore always shown, marked trail-level.
  Checked against the shipped fixture: all 7 of `gate_framework.json`'s records
  are cited, so this bucket is empty there and the fixture-based counts below are
  unaffected.
- **The evidence universe is `records ∪ cited-refs-that-resolve-to-nothing`,
  computed ONCE for every projection.** An unresolved ref exists *only* in a
  citation — never in the `evidence` array — so any projection built from the
  records alone silently drops it. `other_evidence` therefore carries the same
  `(ref, record-or-None, provenance)` tuples as `shown_evidence`, and the
  reveal renders both through one path. **Compute the universe above the
  no-anchor early return, not inside each branch:** every projection that
  claims to show "everything" must agree on what everything is, and deriving
  it twice is what let the same defect appear in two places.
- `affects` is a list; treat a bare string defensively as a one-element list.
- Exclusions are document-level, short (2 and 13 in the live trails) and carry no
  entry anchor — they are **never** withheld, only re-ordered (step 2).

### 2. Restructure `_sections()`

Keep the existing `head()` / `line()` closures verbatim (`:3877-3889`) — the
`""`/`[]`/`None` skip in `line()` is what already keeps absent fields from
printing empty labels. New order, each section emitted **only when it has
content** (an omitted heading is fine; a heading with nothing under it is not):

1. **Entry** — `classification`, `confidence`, `rationale`, `expected outcome`,
   `why order matters`, `caveats`. **Drop the raw `evidence_refs` line**
   (`:3899`): section 6 now renders those refs resolved to their records, and
   unresolved refs are shown there verbatim, so nothing is lost.
2. **Wave** — `purpose`, `why now`, `consequence of delay` (unchanged).
3. **Drift affecting this entry** — `entry_drift`, then `unowned_drift` under a
   `trail-level` label so the reader can tell a global warning from one about
   this card, same `• <code> <ref>: <detail>` bullet shape as today. Heading
   counts what is shown. When `other_drift` is non-empty, a trailing
   `… N more reason(s) for other entries` line.
4. **Trail narrative** — `problem`, `recommendation`
   (`narrative.recommendation_summary`), `overview` (`narrative.overview`, absent
   until t1505_3 — `line()` skips it silently), `method note`, `caveats`.
5. **Observations affecting this entry** — `entry_obs`, then `unowned_obs`
   marked `trail-level`, then `… N more observation(s) not affecting this entry`
   when `other_obs` is non-empty.
6. **Evidence** — `shown_evidence`, same `• <id> (<source_type>): <summary>`
   bullet shape, each bullet carrying its provenance so a record pulled in by an
   observation does not look like one the entry cited:
   `• ev-red-suite (test_run): … — cited by obs-red-suite`. Records the entry
   itself cites carry no suffix; an uncited record is marked `— trail-level
   (uncited)`. An `evidence_refs` entry with no matching record renders
   `• <ref> (unresolved)` rather than vanishing. Then
   `… N more evidence record(s)` when `other_evidence` is non-empty.
7. **Exclusions** — unchanged content, now last.

**Always-rendered closing block** (this is the answer to "a lite trail must read
as complete, not broken"):

```
Trail totals: 0 observations · 0 exclusions · 1 evidence · 0 drift reasons
Showing the full trail.
```

The totals line renders unconditionally, so "this trail has no observations" and
"the observations failed to render" cannot look the same — the first states zero,
the second would show no totals line at all. The second line is the mode/hint
line, in three forms:

- withheld, scoped view → `Showing what concerns this entry — press a for the full document.`
- nothing withheld → `Showing the full trail.`
- `show_all` → `Showing the full document — press a to scope back to this entry.`

When `self.entry is None` the render is the full document with no hint (nothing
to scope against).

### 3. The reveal key

```python
BINDINGS = [
    Binding("escape", "cancel", "Close", show=False),
    Binding("a", "toggle_all", "Show all", show=False),
]
```

`show=False` because this modal mounts no footer (Correction 3) — the in-body
hint line from step 2 is the discoverability surface, and it appears only when
there is something to reveal.

- `__init__` gains `self.show_all = False`.
- `compose()` (`:3940`) gives the body `Static` an id (`#trail_detail_text`) so
  the toggle can rewrite it.
- **`check_action`** on the screen returns `False` for `toggle_all` when
  `self._scope()["withheld"] == 0 and not self.show_all` (must stay live while
  revealed, so the user can scope back).
- **`action_toggle_all` re-checks the same condition and returns early** — a
  binding gate is not an action guard; the action stays reachable through the
  command palette and a remap. Then flip `show_all`, `update()` the Static with
  `self._sections()`, and call `self.refresh_bindings()`.

### 4. Docs

`aidocs/implementation_trail_design.md`:

- **§9.1** — rewrite the "Detail modal (`enter`)" bullet: an entry-first
  projection (entry → wave → drift affecting it → trail narrative → observations
  affecting it → the evidence backing everything shown → exclusions), a totals
  line, and `a` to reveal the material owned by other entries. State the
  scoping rule explicitly — **only material owned by another entry is withheld;
  unowned trail-level facts stay on every card** — because that is the part a
  future reader is most likely to "simplify" away. Add the bottom **summary
  pane** and its `v` expand key (t1505_1) to the same bullet list; §9 does not
  mention it at all today.
- **§9.2** — the `Trail stale` row currently reads "drift reasons listed in
  detail modal"; narrow it to the focused entry's reasons plus unowned
  trail-level ones, with the rest behind `a`.
- **§15** — update the By-Trail wireframe (summary pane below the columns, `[v]
  summary` in the key strip) and the detail-modal wireframe (new section order,
  the totals + hint footer line).

### Post-phase (risk mitigations)

1. **[modal_assertion_tripwire]** Add a tripwire that fails **if the
   document-level sections regress to rendering on every card**.

   Use the real example document already imported as `FIXTURE_PATH`
   (`tests/test_board_bytrail_view.py:44` → `gate_framework.json`: 4
   observations, 3 exclusions, 7 evidence, 6 entries across 5 waves — deep-copy
   it, per the module docstring's never-mutate rule). Render `_sections()` for
   two entries in different waves and assert:

   - a statement / evidence summary that belongs to entry A's scope is **present
     in A's text and absent from B's**, and symmetrically for one of B's;
   - the two texts differ by more than the entry/wave block — i.e. assert the
     *absence*, not merely that each entry's own block appears first. A test
     that only checks "entry appears first" stays green after the regression
     this tripwire exists to catch.

   **Anchor it on genuinely owned material.** `aitasks#635_29` (via
   `obs-red-suite`) and `aitasks#635_30` (via `obs-skill-collision`) are the
   right pair — each of those observations names exactly one member. Do **not**
   anchor on `obs-missing-model-defaults` / `ev-model-defaults`: those are
   unowned and are *supposed* to appear on both cards, so an assertion against
   them would fail the correct implementation.

   **Confirm it fails before keeping it:** temporarily restore the old
   unfiltered `_sections()` body and observe the tripwire go red. A tripwire
   never seen failing is not a tripwire.

   If any pre-existing assertion breaks, decide whether it encoded an invariant
   or merely the old shape — re-point invariants, do not delete a guard because
   it now fails. (Per the verification pass there is exactly one such assertion,
   `:681`'s `assertIsInstance`, and it is shape-independent.)

2. **[self_supplying_live_artifact]** Self-supply the artifact for the live
   terminal check rather than blocking on t1468_7.

   `art:trail-gates-framework-landing` and `art:trail-shadow-review-loop` return
   `ERROR:invalid_trail` until t1468_7 refreshes them to 1.1.0 — that is
   t1468_5's landed schema bump, **not** a regression of this child, and must not
   be recorded as one. Instead reuse t1505_1's recipe: copy
   `aidocs/implementation_trail_examples/gate_framework.json` (already at
   `schema_version 1.1.0`), give it a distinct `trail_id` / `title`, then

   ```bash
   ait artifact create <task> <file> --kind implementation_trail --handle art:<id>
   ```

   Its 4 observations / 3 exclusions / 7 evidence across 6 entries are what make
   the live check meaningful — a lite trail would show nothing withheld and
   would not exercise the scoping at all. Run the live check against that
   handle, then remove the artifact. Two things t1505_1 recorded and this step
   inherits: `aitask_trail_gather.sh drift` reports `ERROR:undriftable_input` on
   that document (a *drift-input* verdict, not a schema failure —
   `trail_schema.validate_trail` returns no issues), and `ait artifact rm` leaves
   a dangling empty `artifacts:` key in the task frontmatter that must be cleaned
   up by hand.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the **last**
  line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`, on stderr). Piping
  discards the exit status; use `set -o pipefail` or `${PIPESTATUS[0]}`.
- New `TrailDetailSectionTests` (pure — construct `TrailDetailScreen` and assert
  on `_sections().plain`; no pilot needed, verified to work outside an App):
  - **Entry-first order:** the entry block's first line precedes the narrative,
    observations and evidence headings.
  - **Observation scoping:** a fixture with 3 observations, one naming this
    entry in `affects` — only that statement appears, and the line
    `… 2 more observation(s) not affecting this entry` does.
  - **Evidence scoping:** only the records the entry's `evidence_refs` resolve
    to, with an accurate count of the rest; an `evidence_refs` entry with no
    matching record renders `(unresolved)` rather than vanishing.
  - **Canonical refs:** an entry stored as `aitasks#t42` matches drift reasons
    and `affects` written as `aitasks#42`. This test fails on raw string
    comparison, which is the point.
  - **Unowned drift survives scoping — both categories.** A reason with
    `task_ref == "-"` (e.g. `input_missing`) **and** a `new_related_task`-shaped
    reason naming a task that is **not** a trail member both appear in the
    default view, marked trail-level. A reason owned by *another member* does
    not, and is counted instead. This is the full
    `trail_drift_by_ref:771-774` contract; a test covering only the `"-"` case
    would pass while the non-member reason was silently withheld.
  - **Unowned observations survive scoping:** an observation with
    `affects: []` — `obs-missing-model-defaults` in the real fixture — appears on
    a card it does not name, while an observation affecting only another member
    does not.
  - **Observation provenance is not broken by scoping.** Against the real
    fixture, the `aitasks#635_29` view contains `ev-premise-check` (the entry's
    own), `ev-red-suite` (pulled in by `obs-red-suite`, which affects this entry)
    and `ev-model-defaults` (pulled in by the unowned observation), each
    labelled with what cited it — with `… 4 more evidence record(s)` for the
    rest. Assert the *observation-sourced* record is present: showing
    `obs-red-suite`'s claim while withholding `ev-red-suite` is precisely the
    provenance gap this rule closes.
  - **Lite trail reads as complete — and is genuinely unscoped.** Build the
    t1505_4 shape: no observations, exclusions or relations, **no per-entry
    `evidence_refs`**, and exactly one evidence record. Assert no `Observation`
    or `Exclusions` heading; the single record **rendered**, marked trail-level
    (uncited); the closing block reading `0 observations · 0 exclusions ·
    1 evidence`; the mode line reading `Showing the full trail.`; **and no
    `… more evidence record(s)` line**. Assert `_scope()["withheld"] == 0` and
    `check_action("toggle_all", ())` falsey directly — the hint line alone would
    let a wrong bucket assignment pass if the wording ever changed.
  - **Uncited and withheld coexist:** a document with one uncited record *and*
    one cited only by another entry shows the first and counts exactly the
    second — the two rules are independent, and a single-record fixture cannot
    tell them apart.
  - **`show_all` reveals everything:** with the flag set, every withheld
    statement, evidence summary and drift reason is present, and the hint line
    offers scoping back.
- **Reveal key (pilot, extending `ByTrailTestBase` and driving the view with
  `_enter_synthetic_bytrail` — t1487: never leave a `@work` worker in flight):**
  `enter` on a By-Trail card opens the modal, `a` reveals the withheld sections
  (asserted through `_dialog_text`). **Negative controls:** (a) `a` does **not**
  change `app.base_filter` — the App's `view_all` binding must stay shadowed; (b)
  with nothing withheld, `check_action("toggle_all", ())` is falsey **and**
  calling `action_toggle_all()` directly leaves `show_all` False (the action
  guard, not just the binding gate).
- **Still green:** `test_board_bytrail_view.py:681`'s `assertIsInstance` — the
  only pre-existing modal assertion.
- **Live check in a real terminal** (not only `run_test` — `run_test` and the
  real driver are measured to diverge on focus/compositing, per
  `aidocs/framework/tui_conventions.md`): open a card's modal in By-Trail and
  confirm the entry-specific content is what you see first without scrolling,
  that `a` reveals the rest, and that a second `a` scopes back.

**Trail artifact availability:** `ERROR:invalid_trail` on
`art:trail-gates-framework-landing` / `art:trail-shadow-review-loop` until
t1468_7 refreshes them to 1.1.0 is **expected** (t1468_5's landed schema bump)
and is not a defect of this child.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.

## Final Implementation Notes

- **Actual work done:** All four planned steps plus both post-phase mitigations
  landed as designed. `TrailDetailScreen._scope()` partitions the document three
  ways against the focused entry; `_sections()` renders entry → wave → drift
  affecting it → narrative → observations affecting it → evidence backing
  everything shown → exclusions, closing with an always-rendered `Trail totals:`
  line and a mode line; `a` toggles the full document, gated in `check_action`
  and re-guarded inside the action. 20 tests across two new classes
  (`TrailDetailSectionTests`, `TrailDetailRevealKeyTests`). Design doc §9.1,
  §9.2 and both §15 wireframes updated.

- **Deviations from plan:** None in approach. Two shape changes forced by
  review (see Post-Review Changes): the evidence universe became
  `records ∪ unresolved-cited-refs`, and it is computed once above the
  no-anchor branch rather than per-projection.

- **Issues encountered:**
  - **The plan's inherited premise about the test file was false, and the
    verification pass caught it before any code moved.** `test_board_bytrail_view.py`
    had **one** `TrailDetailScreen` reference (an `assertIsInstance` at `:681`)
    and **zero** `_sections` assertions — not "3,335 lines pinning modal
    content". There was nothing to re-point; the modal was simply untested, so
    the content tests became a deliverable rather than a migration.
  - **`trail_drift_by_ref` drops two unowned categories, not one.** Its
    docstring names both (`task_ref == "-"` **and** refs naming a non-member)
    and promises they stay visible in this modal. A two-way "mine / everything
    else" split would have hidden them on *every* card. The fixture proved this
    is not hypothetical: `obs-missing-model-defaults` carries `affects: []`.
  - **Evidence had to follow what is displayed, not just the entry.**
    `obs-red-suite` affects `aitasks#635_29` and cites `ev-red-suite`, which the
    entry does not cite — scoping to `entry.evidence_refs` would have rendered
    a claim while withholding its support.
  - **Two review rounds found the same defect in two places** (see CR1/CR2):
    the withheld projection, then the no-anchor projection, both built from the
    `evidence` array while an unresolved ref lives only in a citation. The
    lesson generalizes past this file: when more than one code path claims to
    render "everything", derive that set once — fixing only the reported branch
    leaves the shape that produced the bug.
  - `_dialog_text(app, widget)` captures only the **visible** slice of a
    scrolling modal body, so the totals/mode line at the bottom is not
    assertable through it. The pilot test uses `_dialog_text` to prove the
    modal is composited and `Static.render().plain` (the repo's existing idiom)
    for the body's tail.

- **Key decisions:**
  - **The reveal key is screen-scoped and `show=False`.** No modal in this app
    mounts a `Footer`, so a visible binding would surface nowhere; the in-body
    hint line is the discoverability surface and renders exactly when something
    is withheld. `TrailDetailScreen` declares no `_shortcuts_scope` (like
    `TrailSummaryScreen`), so `lib/shortcut_scopes.py` needs no manifest entry.
  - **`a` deliberately shadows the App-level `view_all`.** Screen bindings win
    the chain and the App binding carries no `priority=True`; pinned by a
    negative control asserting `base_filter` is unchanged after the press, and
    confirmed live in a real terminal.
  - **`narrative.overview` is rendered as its own field, NOT through
    `trail_summary_text`** — contrary to t1505_1's sibling note. That resolver
    picks *one* of two fields for the single-slot pane; reusing it here would
    hide the schema-required `recommendation_summary` whenever an overview
    exists (t1505_3). The modal has room for both.
  - **An always-rendered `Trail totals:` line** is what makes "this trail has no
    observations" distinguishable from "the observations failed to render".
  - **No pre-phase characterization test.** Characterizing the old output would
    have been rewritten by step 1, and t1505_1 recorded the same lesson: a
    characterization test written before the target surface exists is not the
    guard it appears to be.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1505_3** adds `narrative.overview`. The modal already renders it
    (`line("overview", …)`) and `line()` skips absent fields, so no board change
    is needed when it lands — `test_overview_is_rendered_alongside_recommendation_not_instead`
    already covers it against a synthetic doc.
  - **t1505_4** writes lite trails. `test_lite_trail_reads_as_complete_and_is_genuinely_unscoped`
    encodes the shape this modal expects: no observations/exclusions/relations,
    **no per-entry `evidence_refs`**, exactly one evidence record. Because that
    record is then cited by nobody, the "uncited evidence is always shown" rule
    is what makes a lite trail read as complete rather than scoped — if the lite
    writer starts emitting `evidence_refs`, re-check that test's expectations.
  - The unowned/uncited rules are the subtle part of this surface. Anything
    later "simplifying" `_scope()` into a two-way mine/other split will hide
    trail-level facts on every card while every scoping test still passes except
    the three that pin unowned material.
  - The two stored trail handles still return `ERROR:invalid_trail` until
    t1468_7 refreshes them to 1.1.0 — observed again live during this task (the
    selector shows both as "unreadable"). Expected, not a t1505 regression.

## Post-Review Changes

### Change Request 1 (2026-08-14 00:20)

- **Requested by user:** `_scope()` built `other_evidence` from the root
  `evidence` records only, while a ref that resolves to no record exists solely
  in the citation. A ref cited by another entry (reproduced with
  `evidence_refs: ['ev-missing-other']` on `aitasks#635_33`) was therefore
  neither counted as withheld nor added when `show_all` is true — pressing `a`
  silently lost document content. Asked to preserve unresolved refs for
  non-focused material in the withheld/full projection and to add a regression
  test alongside the current-entry unresolved-ref test. Disposition: blocking.
- **Verified before fixing (CONFIRMED):** rendering the `aitasks#635_29` card
  with that fixture showed `ev-missing-other` absent from **both** views, and
  `withheld` reported 5 where 6 was correct. The bug is asymmetric by
  construction: the focused entry's own unresolved ref goes through `_show()`,
  which carries `(ref, None, provenance)` and renders `(unresolved)`, whereas
  the withheld set was a list of records — so the existing
  `test_unresolvable_evidence_ref_is_shown_not_dropped` could never catch it.
- **Changes made:** `cited_anywhere` became an ordered, deduped list (it was a
  set); the withheld universe is now `records ∪ refs-that-resolve-to-nothing`,
  and `other_evidence` carries the same `(ref, record-or-None, provenance)`
  tuple shape as `shown_evidence`, so the reveal renders both through one path
  and the existing `rec is None → "(unresolved)"` branch covers it.
  `_sections()`'s full-mode append dropped its now-redundant re-tupling.
  Added `test_unresolvable_ref_of_ANOTHER_entry_is_counted_and_revealed`,
  asserting the ref is absent-but-counted when scoped (`… 5 more evidence
  records`, `withheld == 6`) and rendered as `• ev-missing-other (unresolved)`
  when revealed.
- **Negative control:** with the universe restricted back to records only, the
  new test fails and the pre-existing current-entry unresolved-ref test stays
  green — confirming first-hand that the old test could not have caught this.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_bytrail_view.py`.

### Change Request 2 (2026-08-14 00:38)

- **Requested by user:** the `not entry_ref` early return promises a full
  document but built `shown_evidence` from the root `evidence` records only —
  the same defect as CR1, in the branch CR1 did not touch. Reproduced by adding
  `ev-missing` to an entry's refs and constructing `TrailDetailScreen(doc, [])`:
  `withheld` was 0 and the ref was absent while the mode line still read
  "Showing the full trail." Asked to build the no-entry universe from records
  plus unresolved citations and pin it in the no-focused-entry test.
  Disposition: blocking.
- **Verified before fixing (CONFIRMED):** reproduced exactly as described —
  7 evidence bullets, `ev-missing` absent, `withheld == 0`, mode line
  "Showing the full trail."
- **Root cause, and why it recurred:** CR1's fix was applied *inside* the
  anchored path, leaving two independent derivations of "everything". The
  no-anchor branch was written before the universe rule existed and kept its
  own records-only view. Fixing only the reported branch again would have left
  the same shape in place.
- **Changes made (structural, not local):** `by_id`, the ordered
  `cited_anywhere` walk and `universe` are now computed **once, above** the
  no-anchor branch, and both projections consume that one definition — the
  no-anchor return builds `shown_evidence` from `universe`, and the anchored
  path's `other_evidence` filters the same list. `totals` was hoisted with them
  (it was also duplicated across the two returns). The no-focused-entry test
  now carries an unresolved ref and pins `• ev-missing (unresolved)`, the
  "Showing the full trail." mode line, `withheld == 0` and
  `len(shown_evidence) == 8`.
- **Negative control:** with `universe` restricted back to records only, the
  no-focused-entry test **and** CR1's test both fail; both pass after.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_bytrail_view.py`.

## Risk

Levels are the **reassessed** ones — they describe the plan *with* both inline
mitigations incorporated.

### Code-health risk: low
- `_sections()` is restructured with **no pre-existing content tests** to fall back on — the file's only modal assertion is an `assertIsInstance` (`tests/test_board_bytrail_view.py:681`), so the "3,335 lines pin the modal" premise this plan inherited is false and the change starts unguarded · severity: medium · → mitigation: inline post-phase modal_assertion_tripwire, plus the content tests in Verification, which are a deliverable of this plan rather than a re-pointing exercise
- A two-way "mine / everything else" partition would withhold **unowned** material — `task_ref == "-"` reasons, `new_related_task` reasons naming a non-member, and observations with `affects: []` — from *every* card, making a globally relevant stale-trail warning reachable from nowhere in the default view and falsifying `trail_drift_by_ref`'s own docstring (`:771-774`). The failure is silent and worse than the duplication being removed · severity: medium · → mitigation: structural — `_scope()` is a three-way partition against the canonical member set and only "owned by another entry" is ever withheld (step 1), pinned by the unowned-drift and unowned-observation tests
- Scoping evidence to `entry.evidence_refs` alone breaks the provenance path of a displayed observation: on `aitasks#635_29`, `obs-red-suite`'s claim would render while its `ev-red-suite` support sat behind the reveal key. Unsupported claims are exactly what an evidence-backed artifact must not show · severity: medium · → mitigation: structural — `shown_evidence` unions the entry's refs with those of every displayed observation and labels each bullet's citation source (step 1/2), pinned by the provenance test against the real fixture
- Ref comparison has a known spelling mismatch (`aitasks#t42` vs `aitasks#42`) that raw string equality drops silently — the failure is invisible, not loud · severity: medium · → mitigation: structural — every comparison routes through `canonical_trail_ref` (`:705`), pinned by a test that fails on raw comparison
- Blast radius is narrow: one modal class in one module, one test file, one design doc — no schema, skill-template or goldens surface · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- "Entry-first is actually more readable" is a human judgement that only a real terminal can settle, and this repo has a measured case of `run_test` diverging from the real driver (t1495). A green headless suite is not evidence · severity: medium · → mitigation: inline post-phase self_supplying_live_artifact + the live-terminal check in Verification. If the projection turns out to be the wrong shape, the remedy is a section re-order — cheap and recoverable, which is why this stays `medium` rather than `high`
- An omitted section and a failed render look identical to a reader, so a lite trail (after t1505_4: no observations, no exclusions, one evidence record) could read as broken · severity: medium · → mitigation: structural — the always-rendered `Trail totals:` line (step 2) states the zeroes explicitly, pinned by the lite-trail test
- The lite writer omits per-entry `evidence_refs` (schema-optional) while root `evidence` stays required, so on the trail this feature is designed for **every** record is uncited. A cited-only ownership rule would withhold the document's only evidence and offer a reveal on a document with nothing to reveal — the scoped mode leaking into the one case that must read as unscoped · severity: medium · → mitigation: structural — uncited records are their own always-shown bucket (step 1), pinned by the lite-trail test asserting `withheld == 0` on the state, not just on the hint wording
- The modal's `a` shadows the App-level `a` (`view_all`, `:7725`); if dispatch resolved App-first, pressing it would switch the board view behind the open modal · severity: low · → mitigation: covered by the Verification negative control asserting `app.base_filter` is unchanged
- The reveal key surfaces in no footer (no modal in this board mounts one), so an unhinted key would leave the withheld material effectively unreachable · severity: low · → mitigation: structural — the in-body hint line renders exactly when something is withheld (step 2)

### Planned mitigations
- timing: post-phase | name: modal_assertion_tripwire | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — an unguarded restructure could be silently undone by a later edit "restoring" the sections | desc: Render _sections() for two entries of the real gate_framework.json fixture and assert each entry's scoped material is absent from the other's text, confirmed red against the pre-change body first.
- timing: post-phase | name: self_supplying_live_artifact | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — live acceptance needs a valid multi-observation trail that t1468_5 invalidated | desc: Register a local 1.1.0 artifact from gate_framework.json, run the live terminal check against that handle, and record that ERROR:invalid_trail on the two stored handles before t1468_7 is expected.

**Why there is no pre-phase.** A characterization test of today's `_sections()`
output would be rewritten by the very first step, and t1505_1 recorded the
general lesson first-hand: a characterization test written before the target
surface exists cannot assert on it and is not the guard it appears to be. The
guard here has to live in the post-change suite, which is where the tripwire
sits.
