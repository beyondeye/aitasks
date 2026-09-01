---
Task: t1603_5_website_docs_board_planned_lane_and_phases.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_6_manual_verification_surface_deferred_plan_marker_on_the_boar.md
Archived Sibling Plans: aiplans/archived/p1603/p1603_1_board_card_badge_and_detail_row.md, aiplans/archived/p1603/p1603_2_workflow_phase_model_and_degradation.md, aiplans/archived/p1603/p1603_3_inflight_planned_lane_and_phase_chips.md, aiplans/archived/p1603/p1603_4_expanded_gate_surface_in_task_detail.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 23:07
---

# t1603_5 — Website documentation for the board's Planned lane, phase chips and gate surface

**Verification pass** — this is the existing `aiplans/p1603/p1603_5_*.md` re-verified against
the shipped code (`plan_verified: []` → no prior verification). Findings are folded in below;
`## Verified against the shipped code` records what changed.

## Context

Children t1603_1..t1603_4 have all landed (t1603_4 = `fdbc5cf90`). Between them they shipped a
card status qualifier, a Task Detail row, a fourth In-Flight lane, per-card workflow-phase chips,
compact gate progress, and an expanded `Gates` section in Task Detail. **None of it is documented
for users**, and — worse — three shipped pages now assert the *pre-t1603* behaviour as fact.

This is layer 5 of the "Adding a new frontmatter field" checklist in
`aidocs/framework/aitasks_extension_points.md:163`, whose closing sub-bullet owes the board
reference row once the board renders the field. It does now.

## ⚠ Path correction (confirmed)

The parent t1603 named `.aitask-scripts/tuis/board/reference.md`. **That path does not exist.**
The real document is `website/content/docs/tuis/board/reference.md` (Hugo, `{{< relref >}}`).
The generated mirror at `website/public/` is **read-only** — never hand-edit it.

---

## Implementation Steps

### 1. `reference.md` — card badge in `### Task Card Anatomy` (:96)

Add the deferred-plan qualifier to the ASCII diagram's status line and its annotation:

```
│ 📋 Ready · Planned | 👤 alice     │  ← Status (· Planned when an approved plan awaits implementation), assigned to
```

No timestamp on the card — say so, and point at the detail view's `Plan approved: <ts>` row.
The block already notes that lines appear only when the data exists; do not restate it.

### 2. `reference.md` — correct the In-Flight base-filter row (:215)

Current text is **false on both counts**:

> Active `Implementing` tasks grouped by next required action: Needs your action, Agent can continue, and Blocked.

Replace with a row naming **four** lanes and the `Ready`+marker admission, linking to the new
section from step 3.

### 3. `reference.md` — new `### In-Flight Lanes and Workflow Phases`

Insert **after** the `### View Filters` block ends (after `#### Add-on filters (toggle)`, before
`### Column Configuration`). Model the shape on `### Follow-up Provenance Glyphs` (:137-172) —
its own section, a table, a "reading it" list, a Task-Detail `####` subsection, a closing
cross-reference to the CLI surface. Heading is apostrophe-free so its anchor slug
(`in-flight-lanes-and-workflow-phases`) is unambiguous.

**3a. The two-axes model — the load-bearing part.** State, in this order:

- lanes answer *what happens next*; chips answer *where the task sits in the workflow*;
- **every card sits in exactly one lane and carries exactly one chip** (both are single scalar
  values on the item — there is no multi-membership);
- "independent" means **neither axis determines the other**. It does **not** mean a task appears
  twice.

Then both worked pairs, verbatim — without *both*, a reader concludes the chip restates the lane:

*Same phase, different lanes* (the lane is not derivable from the phase):

| # | Task | Status | Phase (chip) | Lane |
|---|---|---|---|---|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | in-flight, `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

*Same lane, different phases* (the phase is not derivable from the lane):

| # | Task | Lane | Phase (chip) |
|---|---|---|---|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

A and B are two **different tasks**. Explain why they share a phase: an approve-and-stop task
reverts to `Ready` but keeps its gate ledger, so the last thing recorded is still `plan_approved`.

**3b. The four lanes**, in render order, with what each means and which card ops it offers:

| Lane | Shown | Card ops |
|---|---|---|
| **Planned** | `Ready` + an approved-but-deferred plan; implementation never started | `[p pick]` **only** |
| **Needs your action** | a human gate is pending, failed, or needs re-signing; or all gates pass | `[p pick] [g resume] [s sign-off] [f fail]` |
| **Agent can continue** | an agent can resume unattended | `[p pick] [g resume]` |
| **Blocked** | unresolved dependencies — **outranks every other lane** | `[p pick]` |

Two rules that are not guessable and must be stated:

- a dependency-blocked task with an approved plan renders in **Blocked**, not Planned — the lane
  reports "nothing can happen next";
- Planned cards offer **pick only**, and `g` / `s` / `f` are *refused* even when reached through
  a rebind or the command palette: resuming would bypass the planning checkpoint, and signing off
  would approve a review on code that was never written.

**3c. The five phases** and their chip labels:

| Phase | Chip label |
|---|---|
| `plan_approved` | `plan approved` |
| `implementing` | `implementing` |
| `awaiting_review` | `awaiting review` |
| `needs_attended_agent` | `needs attended agent` |
| `post_impl` | `post-implementation` |

Document why `needs_attended_agent` exists: `docs_updated` is `type: machine` but
`kind: procedure`, so the headless engine defers it and only an attended agent can run it — a
task whose review already passed can still be blocked from archival by it.

**The label above is the stem; the rendered form differs between the two surfaces** — the card's
chip is deliberately compact and the Task Detail chip is the expanded one. Document both, because
a reader who sees `plan approved (from marker)` on screen must be able to find it here:

| How the phase was determined | On the card | In Task Detail `Gates` |
|---|---|---|
| from the gate ledger, task is gated | `<label> · <satisfied>/<enforced>` | same |
| from the gate ledger, no enforced gates | `<label>` | same |
| from the deferred-plan marker alone | `<label>` | `<label> (from marker)` |
| ledger absent or unreadable | `<label>` | see **Honest degradation** below |

The `(from marker)` qualifier appears on a `Ready`-plus-marker task and is **detail-only**: the
marker outranks the ledger, so the chip does not claim "no ledger" — such a task usually has one.
The card omits every qualifier on purpose; its own action line already says what to do, in plainer
words than the ledger vocabulary.

**3d. `#### Gate progress`** — the two rules that read as bugs unless stated:

- the fraction's **denominator is the enforced active set** (`active_gates`), not the declared
  `gates:` list — a profile-filtered gate is not counted at all;
- a **stale signature counts as NOT satisfied** even though the ledger shows `pass`, because the
  archival guard treats it that way. Such a card says `awaiting re-sign: <gate>`.

Also: a `skip` is terminal-**satisfied** and counts toward the numerator.

**3e. `#### Honest degradation`** — under a profile that records no gates, the view derives what it
can from status, plan presence and the marker, and says so. Be precise about *which surface says
what* — the card and the detail screen deliberately differ (this heading is the anchor target for
the 3c table):

| State | Card chip | Card action line | Task Detail `Gates` |
|---|---|---|---|
| no ledger, plan file exists | `implementing` | `No gate information yet — pick/resume` | `No gate ledger — implementing (derived)` |
| no ledger, no plan file | `implementing` | `No gate information yet — pick/resume` | `No gate ledger — implementing (unknown)` |
| ledger unreadable | `implementing` | `gate state unavailable` | `Gate state unavailable: <error>` |

State plainly that **`unknown` means "we cannot tell how far it got", not "it has not started"**,
and that no fraction is printed rather than a fabricated `0/N`. Note that the card's compact chip
deliberately omits the qualifier: it would sit directly under the action line and restate it in
ledger jargon.

**3f. `#### Gates in Task Detail`** — the expanded counterpart, reached with `Enter` on a card.
A collapsible titled `Gates (<satisfied>/<enforced>)`, leading with the phase chip, then one row
per active gate:

| Row | Meaning |
|---|---|
| `✓ <gate> — passed` | satisfied |
| `⊘ <gate> — skipped (not applicable)` | satisfied, but distinct from passed |
| `· <gate> — pending` | declared and has not run — the ordinary state of a freshly claimed task |
| `◈ <gate> — pending; needs attended agent` | a `procedure` gate the headless engine defers |
| `✗ <gate> — failed` | |
| `⚠ <gate> — pass, signature stale; needs re-sign` | both facts at once |

Gates removed by the profile ceiling are listed under a dimmed
`filtered by profile (audit only)` heading — they are **not** counted in the fraction.

Close with the cross-reference line to the CLI surface, matching the Follow-up section's shape.

### 4. `reference.md` — keyboard rows (:66-68)

`g`, `s`, `f` currently read "In-Flight row". Qualify each: not offered on **Planned** rows, and
refused with an explanation if reached anyway. Link to the new section.

### 5. `reference.md` — `### Task Metadata Fields` (:438)

Add one row to the table (which has an `Editable from Board` column):

| `plan_approved_at` | string | Read-only | Timestamp of an approved plan whose implementation was deliberately deferred. Written and cleared **exclusively by the task-workflow** — the board offers no edit affordance. Shown as the card's `· Planned` qualifier and as `Plan approved:` under Tracking & provenance. |

### 6. `how-to.md` — `### How to Filter by View Mode`, "In-Flight view (`i`)"

Currently: *"Shows tasks with `status: Implementing` in action groups"* followed by three bullets.
Both are now false. Rewrite to admit `Ready` tasks carrying an approved-but-deferred plan, list
**four** lanes, and add the sentence that `g` / `s` / `f` are refused on Planned rows. Add a
relref to the new reference section rather than duplicating the two-axes model here.

### 7. `_index.md` — "Reading a Task Card", Status line bullet (:70)

Add the `· Planned` qualifier to the status-line description, with a relref to the new section.
This is the overview page — the qualifier has to reach it, not only the reference.

### 8. `workflows/parallel-planning.md` — "Deferring a single task's implementation"

The page enumerates the marker's read surfaces (`ait ls --plan-approved`, `ait ls -v`) and is now
incomplete: the board is a third. Add one short paragraph after the `ait ls` block — the card
badge, the Planned lane, and the `Plan approved:` detail row — with a relref to the new section.

### 9. `commands/task-management.md` — cross-reference only

The "Deferred approved plans" paragraph (:120) already documents `Plan: approved <ts>` correctly.
Add a single relref to the board's Planned lane. No rewrite.

### 10. `development/task-format.md` — **verify only, no edit**

`plan_approved_at` is **already documented** at :56 (shipped by t1595) with the full
written/cleared-by-the-workflow description. The original plan's step 5 is satisfied. Confirm the
row is present and accurate, then record in the Final Implementation Notes that no edit was owed —
do not claim work that was not done.

### 11. Repair the pre-existing broken relative links in the edited pages

Verified broken today, all in `how-to.md`, all authorized here so the post-phase sweep can reach
the new links instead of failing on old ones:

| Source | Rendered href | Resolves to | Status |
|---|---|---|---|
| `how-to.md:212` | `href=reference/#by-trail` | `/docs/tuis/board/how-to/reference/` | **dead** — that directory holds only `index.html` |
| `how-to.md:461` | `href=reference/#by-trail` | same | **dead** |
| `how-to.md:241` | `href=../../workflows/work-report/` | `/docs/tuis/workflows/work-report/` | **dead** — one level too many |

Replace all three with `{{< relref >}}` shortcodes, matching the style the same file already uses
elsewhere (`{{< relref "/docs/tuis/board/reference" >}}#by-trail`,
`{{< relref "/docs/workflows/work-report" >}}`) — a relref is resolved by Hugo against the content
tree and **fails the build** when the page moves, which a hand-written relative path never does.
`../reference/` (`:496`) and `_index.md`'s `how-to/#…` links resolve correctly and are left alone.

The third row carries no fragment, so the fragment sweep would not have caught it; it is repaired
because it is provably dead in a page this task edits.

### Post-phase (risk mitigations)

Runs after step 10, before the closure. (This plan is heading-oriented rather than
numbered-list-oriented, so the block sits immediately before `## Verification`, per the
canonical fallback anchor.)

1. **[sweep_doc_anchors_with_control]** Sweep every same-site fragment link, **walking the
   generated HTML — never mapping source filenames to output paths**. Deriving
   `public/<section>/<page>/index.html` from a `.md` source is wrong in both directions:
   `_index.md` builds to `board/index.html` (not `board/_index/…`), and the sources use three
   different link forms (site-root `/docs/…`, page-relative `reference/#…`, and `../../workflows/…`)
   whose resolution depends on Hugo's URL layout and permalink config, not on the filename. That
   assumption would report false failures and miss real breaks. Instead:

   - Build first: `cd website && hugo build --gc --minify`.
   - For each **built** page corresponding to an edited source, read
     `website/public/**/index.html` and extract every `href`. Hugo has already resolved these to
     their real URLs, so no source→path mapping is needed.
   - **Extract with a real HTML attribute parser** (`html.parser` / `HTMLParser`), not a regex.
     `--minify` strips attribute quotes from `href` exactly as it does from `id`: the built
     `how-to` page carries `href=reference/#by-trail` and holds only **2** quoted hrefs in total,
     so a quote-only pattern extracts almost nothing and reports a **clean sweep of an empty
     set** — a false pass, which is worse than a false failure. A parser handles quoted and
     unquoted forms alike by construction.
   - Resolution, one uniform rule per form: a bare `#frag` targets the **containing file**;
     anything else is resolved as a URL **relative to the containing file's own directory** (a
     leading `/` resolves against `public/`), then `…/` → `…/index.html`.
   - Skip `href=#` / empty (the toggle anchors Docsy emits) and off-site hrefs (scheme or host).
   - For a fragment-bearing href: assert the target file exists **and** carries the slug as the
     **unquoted** `id=<slug>` form. For a same-site href without a fragment: assert the target
     file exists — this is what catches the `../../workflows/work-report/` class repaired in
     step 11.
   - Emit a **resolved/broken count**, not a single lookup, and exit non-zero on any broken link.
   - **Two controls, both required to pass — they prove different things:**
     - a **positive control on the extractor**: assert a named, known-present, *unquoted and
       relative* fragment-bearing href (`href=how-to/#how-to-mark-tasks` on
       `public/docs/tuis/board/index.html`) is in the extracted set for that page and resolves.
       Without this, an extractor that silently captured nothing passes the whole sweep.
     - a **negative control on the resolver**: a known-good pre-existing anchor (`#by-trail` on
       the built reference page) must resolve. If it does not, the resolver is wrong and every
       "broken" verdict it produced is meaningless.

2. **[pin_board_doc_literals_with_a_test]** Add a Python test module under `tests/` that pins the
   documented literals to their source values.

   **The documentation contract comes first, and the guard asserts exactly what the documentation
   presents — never the other way round.** Steps 3b–3f above fix that contract; the table below is
   the closed list the guard covers. Anything a render can produce that the docs deliberately do
   *not* present is **out of the guard's scope**, and the guard must not force it into the prose:

   | Source value | Class | Exact form asserted in `reference.md` |
   |---|---|---|
   | `InFlightColumn.TITLES` (4 values) | a | verbatim, in the lane table (3b) |
   | `PHASE_LABELS` (5 values) | a | verbatim, in the phase table (3c) |
   | `phase_chip_text("plan_approved", "marker", None)` | b | `plan approved (from marker)` — documented in 3c's rendered-form table |
   | `phase_chip_text("implementing", "unknown"/"derived", None)` | b | verbatim, in 3e's table |
   | `phase_chip_text("implementing", "error", None)` | b | `Gate state unavailable` — the no-`error`-argument form; 3e writes the suffix as `: <error>` prose, which is **not** asserted |
   | `_status_badge_text("Ready", <marker>)` | b | `📋 Ready · Planned` — the **concrete** documented example. Do **not** normalize the status to `<status>`: the docs present `Ready`, not a token |
   | the six `_build_gate_fields` rows | c | `<glyph> <gate> — <wording>`, gate name normalized |
   | the fraction form (`· 2/3`, `Gates (2/3)`) | — | **not asserted** — the docs present it as `<satisfied>/<enforced>` prose, and a placeholder is not a render |

   Class definitions, and why a single "output appears in the doc" assertion is wrong for (c):

   - **(a) Plain constants** — import and assert each value appears verbatim.
   - **(b) Zero-interpolation renders** — call the real function and assert the returned string
     verbatim. These need **no** normalization; normalizing them is what would fail by
     construction against the concrete examples the docs present.
   - **(c) Templated renders** — the six `Gates` rows interpolate the gate name: production emits
     `✓ risk_evaluated — passed` while the documentation writes `✓ <gate> — passed`. Asserting the
     raw output would always fail; asserting only a substring (`— passed`) would let the glyph,
     the em-dash or the wording drift unnoticed — the exact hole this guard exists to close. So:
     **render from a fixture, then normalize the fixture's own inputs to the doc's placeholder
     tokens, and assert the whole normalized row.**
     - Reuse the existing harness rather than re-deriving anything:
       `tests/lib/board_fixture.py` (`bf.FixtureBoardTestBase`) plus the
       `_section(...) → (row_texts, fraction)` shape already used by
       `tests/test_board_detail_gates_section.py`, which drives the real
       `TaskDetailScreen._build_gate_fields()`.
     - Drive one fixture task per row class over the registry's real gates
       (`risk_evaluated`, `tests_pass`, `docs_updated`, `plan_approved`, `review_approved` —
       between them they reach every branch), collect the rendered rows, then replace **the gate
       name the fixture itself supplied** with `<gate>` and the rendered fraction with the doc's
       placeholder. The substitution key comes from the fixture input, never from a regex guessed
       over the output, so the test cannot silently normalize away a genuine change.
     - Assert the full normalized row against the doc, and assert the count: all six row forms
       must be present.

   Shared constraints:
   - **The source is the authority, the doc is the assertion target.** Never hardcode a literal in
     the test — a copy in the test is a third place to drift.
   - Failures must **name the drifted literal and the file that no longer carries it**, not just
     assert `in`.
   - Keep it a plain module discoverable by `tests/run_all_python_tests.sh`; it must not join the
     serial carve-out (it boots no TUI and takes no `.git/index.lock`).
   - Resolve import paths against the running interpreter rather than assuming a cwd.

---

## Verification

1. `cd website && hugo build --gc --minify` succeeds (Hugo extended ≥ 0.155.3; installed:
   v0.165.0+extended).
2. **Every `{{< relref >}}` page target resolves** — a broken one fails the build.
3. **Anchors are NOT checked by the build.** `hugo build` fails a bad relref but *never* a dead
   `#fragment`. Satisfied by post-phase step 1 (`sweep_doc_anchors_with_control`) — its acceptance
   bar, restated here:
   - resolution walks the **generated** HTML and resolves each same-site href relative to its
     rendered file — no source-filename → output-path mapping;
   - `--minify` writes **both `id` and `href` unquoted**, so extraction uses an HTML parser and
     the id lookup uses the unquoted form — quote-only patterns match almost nothing here;
   - sweep *every* link in the edited pages and assert a resolved/broken **count**, not a single
     lookup;
   - a **positive control** proves the extractor captured a known unquoted relative
     fragment-bearing href, and a **negative control** proves the resolver finds a known-good
     pre-existing anchor. Both must pass, or the sweep's verdicts mean nothing.
4. **The three dead links repaired in step 11 resolve**, and no new dead link is introduced. The
   sweep's broken-count for the edited pages is **0**, having been non-zero before step 11.
5. **Every documented literal matches the source**, per the closed coverage table in post-phase
   step 2 — lane titles, phase labels, the four `phase_chip_text` qualifier forms, the
   `📋 Ready · Planned` badge, and the six Gates rows, all from
   `.aitask-scripts/board/aitask_board.py`. Checked manually while writing, then pinned by
   post-phase step 2 (`pin_board_doc_literals_with_a_test`); that module must pass. The guard's
   coverage is bounded by that table: it must not have forced any string into the prose that the
   documentation did not independently need.
6. **Rows A–D match the shipped fixtures** in
   `tests/test_board_inflight_planned_lane.py::TwoAxisFixtureTests` — already confirmed during
   this verification pass; re-check if the tables are reworded.
7. Current-state-only prose, no version history in the body
   (`aidocs/framework/documentation_conventions.md`).
8. `website/public/` was not hand-edited (`git status` clean for that tree apart from a build).

---

## Verified against the shipped code

Confirmed as the original plan stated:

- the path correction; rows A–D match `TwoAxisFixtureTests` exactly (`("planned", "agent")` /
  `("awaiting_review", "post_impl")`, both lanes `human`);
- badge `📋 Ready · Planned`, no timestamp; detail row `Plan approved: <ts>` under
  `Tracking & provenance`;
- four lanes `Planned` / `Needs your action` / `Agent can continue` / `Blocked`; five phases;
- gate-progress denominator = `active_gates`; stale signature demoted; `skip` satisfied;
  filtered gates audit-only;
- `Follow-up Provenance Glyphs` is the right structural precedent.

Changed by this pass:

- **Step 5 split.** `task-format.md` already carries `plan_approved_at` (t1595). Only the board
  reference's metadata table is owed → now step 10 (verify-only) and step 5 (the row).
- **Four falsified claims added to scope** (steps 2, 4, 6, 7) — `reference.md:215`,
  `how-to.md`, `_index.md:70` and the `g`/`s`/`f` keyboard rows all still describe the pre-t1603
  board. Confirmed with the user.
- **`parallel-planning.md` added** (step 8): it enumerates the marker's read surfaces and the
  board is now a third.
- **Two lane rules added** (3b): `blocked` outranks `planned`, and the Planned refusals live in
  the actions themselves, not only in the ops hint.
- **Degradation table sharpened** (3e): `implementing (unknown)` is the **detail-screen** string;
  the card shows a bare `implementing` chip plus a friendly action line.
- **Anchor verification added** (verification 3): the original plan's "a broken relref fails the
  build" is true for pages but **not** for `#fragment` targets.
- Line references refreshed: 94→96, 135-171→137-172, 196→198, 342-348→383, 397→438.

Corrected after plan review (both findings verified against the build and the source):

- **Anchor sweep must walk generated HTML, not map source paths.** Confirmed: Hugo renders every
  relref to a uniform output URL (`/docs/development/task-format/#frontmatter-fields`) or a bare
  `#fragment`, while the sources use three different forms; and `_index.md` builds to
  `board/index.html`, which the `<section>/<page>/index.html` rule gets wrong. The original
  formulation could report false failures and miss real breaks.
- **The doc-literal guard needs three literal classes, not one assertion.** Confirmed:
  `_build_gate_fields` emits `✓ risk_evaluated — passed` (the gate name is interpolated) while
  the documentation writes `✓ <gate> — passed`; `phase_chip_text` likewise emits
  `plan approved · 2/3` and `Gate state unavailable: <error text>`. A raw-output assertion always
  fails and a substring assertion would let the glyph or wording drift. Now specified as
  fixture-backed rendering (reusing `tests/lib/board_fixture.py` and the `_section` shape from
  `tests/test_board_detail_gates_section.py`) with source-derived normalization.

Corrected after the second plan review (both findings verified against the built site):

- **Three pre-existing dead links in `how-to.md`** (step 11, new). `href=reference/#by-trail`
  (`:212`, `:461`) resolves to `/docs/tuis/board/how-to/reference/`, a directory that holds only
  `index.html`, and `href=../../workflows/work-report/` (`:241`) is one level too deep. The sweep
  would have failed on the first two before reaching any new link, and no step authorized the
  repair. Now in scope, and the sweep also checks non-fragment same-site targets so the third is
  caught too.
- **`href` is minified unquoted, exactly like `id`.** The built `how-to` page carries
  `href=reference/#by-trail` and only **2** quoted hrefs in total, so a quote-only extractor
  yields an almost-empty set and reports a **clean sweep of nothing**. The sweep now requires a
  real HTML attribute parser plus a **positive control** asserting a named unquoted relative
  fragment-bearing href was actually captured and resolved — the negative control alone only
  proves an anchor exists, not that the extractor saw any link.

Corrected after the third plan review (finding verified against the source):

- **The guard's source forms did not match the forms the documentation presents**, so it would
  have failed by construction. `phase_chip_text("plan_approved", "marker", None)` returns
  `plan approved (from marker)` while the phase table documented only the bare `plan approved`;
  and `_status_badge_text` was slated for `<status>` normalization while the card example
  deliberately shows the concrete `📋 Ready · Planned`. Resolved by deciding the **documentation
  contract first**: 3c now documents the four rendered chip forms (and the card/detail split that
  makes `(from marker)` detail-only), 3e gets a real `#### Honest degradation` heading so 3c's
  cross-reference has a live anchor, and post-phase step 2 carries a **closed coverage table**
  binding each source value to the exact form the docs present — with the badge asserted
  concretely, the error suffix and the fraction explicitly **not** asserted, and a standing rule
  that the guard never forces a string into the prose.

---

## Risk

*(Reassessed once against the augmented plan, after both mitigations were confirmed inline.)*

### Code-health risk: low
- Five markdown files under `website/content/` (including three one-line link repairs) plus one
  **additive** test module under `tests/`.
  No production code path is touched, and the test imports the board's constants rather than
  copying them, so it adds no second source of truth. · severity: low · → mitigation: none
  (accepted residual)
- A doc-literal guard is a narrow source-scan test and can over-fit — an innocuous rewording of
  the surrounding prose must not fail it. Bounded by asserting only the literals themselves, and
  by failing with the drifted value named. · severity: low · → mitigation: none (accepted
  residual, constrained in the post-phase step)
- The templated-row normalization is itself a place a bug can hide: too aggressive and it erases
  the drift it exists to catch. Bounded by keying the substitution on the **fixture's own input
  values** rather than a pattern guessed over the output, and by asserting the whole normalized
  row plus the expected row count. · severity: low · → mitigation: none (accepted residual)

### Goal-achievement risk: low
- The documented literals can drift from the shipped strings, which is how doc rot starts; the
  grep-each-literal step is manual, and website docs pages have no doc-accuracy guard of their
  own. · severity: medium · → mitigation: inline post-phase pin_board_doc_literals_with_a_test
- A new heading's `#fragment` cross-references can be dead while the build stays green, so the
  new section could ship with links that silently go nowhere. · severity: medium ·
  → mitigation: inline post-phase sweep_doc_anchors_with_control

Both goal-achievement risks now carry an executable guard inside this plan rather than a manual
step, which is what moves the dimension from `medium` to `low`.

### Planned mitigations
- timing: post-phase | name: sweep_doc_anchors_with_control | type: documentation | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: dead `#fragment` cross-references shipping green | desc: walk the generated HTML with a real attribute parser (href is minified unquoted), resolve every same-site link relative to its rendered file, assert the unquoted `id=` form for fragments and file existence otherwise, report a resolved/broken count, and require both a positive extractor control and a negative resolver control
- timing: post-phase | name: pin_board_doc_literals_with_a_test | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: documented literals drifting from the shipped board strings | desc: a Python test over three literal classes — plain constants, zero-interpolation renders, and fixture-rendered templated rows normalized on the fixture's own inputs — asserting each whole form is present in `reference.md` and failing with the drifted literal named

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header (base `main`, output `main`, current branch —
no worktree), archive the task and plan. The Final Implementation Notes must record that step 10
was verify-only.
