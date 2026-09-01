---
Task: t1636_7_website_docs_shadow_impact_vector_model.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_6_manual_verification_shadow_concern_impact_vector_model.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_1_concern_dimension_vocabulary_module.md, aiplans/archived/p1636/p1636_2_concern_parser_impact_trailer.md, aiplans/archived/p1636/p1636_3_producers_emit_impact_trailer.md, aiplans/archived/p1636/p1636_4_picker_trade_profile_rendering.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1636_7 — Website docs for the shadow concern impact-vector model

## Context

t1636 replaced the shadow's undefined `high/medium/low` severity scalar with an
**impact vector**: every concern declares what it improves and what it worsens,
over one closed dimension vocabulary, plus a separate effort scalar. The parent
decomposition gave website docs to t1636_3 only, scoped to two paragraphs of
`shadow-agent.md`. Those landed.

What is undocumented is the surface the user actually decides on. **t1636_4**
shipped the picker's per-row **trade profile** (`▲robus ▼simpl E:lo`), a
**derived priority badge** with a `≠` disagreement flag, and a **decision
guidance line** — and neither its task file nor its plan mentions documentation.
Four user-facing pages describe that picker today and none of them knows any of
it exists.

Two of those pages also now carry claims the t1636 children made **untrue**.

**Out of scope**, deliberately: the delta-scoped auto-recheck work is parked as
the standalone task **t1650** (`Postponed`). The "Every review round re-derives
the shadow's findings from scratch" prose stays exactly as it is — it is still
accurate, and only t1650 makes it untrue. `aidocs/framework/shadow_agent.md` is
t1650's too. This task is user-facing website docs only.

## Ground truth (read from source, not from the task's illustration)

| fact | source |
|---|---|
| `▲` improves / `▼` worsens; `E:lo` `E:md` `E:hi` `E:?` | `monitor_shared.py` `_IMPROVE_ARROW`, `_WORSEN_ARROW`, `_EFFORT_TOKENS` |
| magnitude is carried by **arrow weight** (bold high / plain medium / dim low); a `?` suffix means *unstated* | `_magnitude_markup`, `_entry_seg` |
| `▲–` / `▼–` (en dash) = the side was **priced** and the price is zero; an omitted side renders nothing at all | `_PRICED_NOTHING`, `_side_segs` |
| `+N` = entries that did not fit | `trade_profile_rungs.build` |
| the **core never degrades**: first improve entry, first worsen entry, effort scalar | `trade_profile_rungs` docstring |
| wide layout = `mark badge region profile body` on one line; narrow = 3 lines (region / body / profile); no-vector rows stay 2-line | `_ConcernRow.render`, `.three-line` CSS |
| badge = `derive_priority(improves)`; `≠` when the marker priority disagrees | `_badge_seg`, `_PRIORITY_MISMATCH_MARK = "≠"` |
| guidance text: `fwd: obligation or pure win · spin: net-positive or costly · rej: worsens ≥ improves` | `_CONCERN_GUIDANCE` |
| guidance shows only at **≥80 columns and ≥24 rows**, and only for blocks that carry vectors | `_GUIDANCE_MIN_WIDTH/_HEIGHT`, `_apply_guidance_visibility`, `compose` |
| dimension vocabulary (7, closed) | `concern_dimensions.CONCERN_DIMENSIONS` |
| **all of the above apply only to a concern that priced itself** — `has_impact_vector` is a three-way OR (`improves` / `worsens` / `effort`), so a concern that priced only its cost or only its effort still counts | `concern_parser.has_impact_vector` |
| a concern that priced **nothing** keeps its marker priority, shows no `≠`, gets no profile line, and stays 2-line — and a block with no priced concern at all gets no guidance line | `_badge_seg` (`mismatch = False` branch), `_sync_layout_classes`, `compose()`'s `if any(has_impact_vector(...))` |

The file list was re-derived against the tree — `grep -rln "concern picker\|shadow
concern" website/content/docs/` returns exactly the four pages the task names.
t1636_4 added no new surface.

## Constraints (binding)

- **C1 — do not become a third copy of the vocabulary.** `concern_dimensions.py`
  and `concern-format.md` are held in lockstep by
  `tests/test_concern_dimensions.py`; the website is not in that guard.
  `shadow-agent.md` already names the seven dimensions once (t1636_3 baseline).
  Describe the *axes* and show **one worked example**; never tabulate the short
  labels.
- **C2 — the disposition guard sweeps the whole page.**
  `tests/test_shadow_disposition_surfaces.py` fails if `blocking` and
  `follow-up` occur within ~160 normalized characters without `informational`,
  anywhere in `shadow-agent.md`. The new prose therefore states the decision
  rule in **forward / spin off / reject** terms and cross-references the
  existing disposition paragraph rather than re-enumerating dispositions.
- **C3 — current-state prose only**; no "as of t1636_N", no "previously".
- **C4 — do not name the supported coding agents.**
- **C5 — extend the t1636_3 baseline, do not duplicate it.**
- **C6 — every claim about the badge, the `≠`, the profile line, the 3-line
  row and the guidance line MUST carry the "only for a concern that priced
  itself" qualifier**, on all three picker-describing pages — not just on
  `shadow-agent.md`. A concern that priced nothing keeps its marker priority
  exactly as before and shows none of it. Without the qualifier the TUI pages
  would falsely describe every legacy row the user still sees. Use the priced /
  not-priced distinction, **not** "has an Improves side": `has_impact_vector`
  is a three-way OR.

  **This binds all four pages, `_index.md` included.** An overview page is the
  easiest place to lose the qualifier and the worst place to lose it — a reader
  meets the rule there first, and a false universal learned in an overview is
  not undone by a qualifier further in.

## Changes

### 1. `website/content/docs/workflows/shadow-agent.md` — primary

**(a)** New `### Read the trade profile` — deliberately apostrophe-free, so the
generated anchor (`#read-the-trade-profile`) is unambiguous for the three pages
that will link to it — inserted between
`### Forward concerns to the followed agent` and `### Reject a concern so it does
not come back`. Covers, in this order:

- the compact rendering, anchored on one example — `▲robus ▼simpl E:lo` — with
  `▲` the improve side, `▼` the worsen side, `E:` the effort scalar
  (`E:lo`/`E:md`/`E:hi`, `E:?` when unstated). Labels are short forms of the
  dimension names already listed on this page (C1: no second table).
- **magnitude is styling, not text** — the arrow is bold for high, plain for
  medium, dim for low; a `?` after a label means the magnitude was not stated
  and is never read as `low`. The dimensions are what to act on; magnitudes only
  refine them.
- `▲–` / `▼–` means the side was **priced and the answer is nothing**, and an
  omitted side renders nothing at all — because "priced as nothing" and "never
  priced" are different facts, and the second is what the mandatory worsen side
  exists to expose.
- `+N` for entries that did not fit, plus the guarantee that matters: the first
  improve entry, the first worsen entry and the effort scalar are **never**
  dropped, so a row can never show an improvement without its price.
- **layout** — wide: the profile sits between the region and the body on one
  line; narrow companion pane: the row grows to three lines and the profile gets
  its own. A concern with no vector renders exactly as it always has.
- **the badge** — for a vector-bearing concern the priority shown is derived
  from its improve side. A `≠` beside it means the shadow's own stated priority
  disagrees with what its vector implies; the picker shows both rather than
  reconciling them, because the picker is where a human decides.
- **the decision guidance** — forward when the improve side touches something
  this change is obliged to deliver, or when it is a pure win at low effort;
  spin off when it is real and net-positive but obliges nothing, or costs medium
  effort or more; reject when the worsen side is at least as large as the
  improve side. Note that the one-line reminder appears above the list only in a
  picker with room for it (about 80 columns and 24 rows); in a companion pane
  the key hints take that space and the per-row profile is the data.

**(b)** In `### Forward concerns to the followed agent` (the informational-section
sentence, ~line 102), add a pointer to the new section.

### 2. `website/content/docs/tuis/minimonitor/how-to.md` — `### How to Pick Shadow Concerns`

- **Fix the stale claim** (~line 186): "For an implementation review, the modal
  splits the list into **Needs addressing** and **Informational**" — plan reviews
  now classify their findings too, so the split is not implementation-only.
  Rephrase to key it on the block carrying dispositions.
- **Extend** (~line 184) "each tagged with a priority … and the plan region it
  targets": **for a concern that priced itself**, the badge is derived from its
  impact vector, with `≠` when the shadow's own stated priority disagrees. A
  concern that priced nothing keeps its stated priority and shows no `≠` (C6).
- **New paragraph — "Reading a row's trade profile."** This is the page that
  should carry the narrow layout, because minimonitor's companion pane *is* it:
  line 1 mark + badge + region, line 2 the body, line 3 the profile — **and only
  for a priced concern**; an unpriced one stays two lines, exactly as before
  (C6). State that the decision-guidance line is not shown at companion-pane
  width and link to `shadow-agent.md#read-the-trade-profile` for the rule and
  the glyph key.

### 3. `website/content/docs/tuis/monitor/how-to.md` — `### How to Pick Shadow Concerns`

- **Extend** (~line 194) the same "tagged with a priority" sentence: **for a
  priced concern**, the derived badge, `≠`, and the profile between the region
  and the body; an unpriced concern renders exactly as it always has (C6).
- **New paragraph** for the decision-guidance line — monitor is the surface that
  normally has the ~80×24 needed to show it — stating that it appears only when
  the block carries at least one priced concern (C6), plus the note that a
  narrow monitor falls back to the multi-line row form by measurement, not by a
  hint.

### 4. `website/content/docs/tuis/minimonitor/_index.md`

One clause on the picker sentence (~line 80). **C6 applies here too** — this is
an overview page, so an unqualified "each concern row carries its trade profile"
would teach a false universal rule even though both how-to pages carry the
qualifier. Scope it: a concern **that priced itself** shows a trade profile, so
what it improves, what it costs and the effort are visible before you decide.
Keep it to one clause and let the link to
[How to Pick Shadow Concerns](how-to/#how-to-pick-shadow-concerns) carry the full
priced / unpriced distinction rather than restating it here.

## Verification

**What the automated checks do NOT cover — read this first.** No test in this
repo reads the four website pages for UI accuracy.
`tests/test_concern_dimensions.py` compares `concern_dimensions.py` against
`.claude/skills/aitask-shadow/concern-format.md` only (`CONCERN_FORMAT`, line
67) — no website path appears in it. `hugo build` proves the site *compiles*:
it fails a broken `{{< relref >}}`, but a wrong glyph, a wrong threshold, a
wrong layout rule or a broken `#fragment` all build green. Steps 1 and 2 below
are therefore the real verification and are **not optional**.

1. **Source-to-prose comparison — every stated UI fact, re-read from the symbol
   that implements it.** Not from this plan's "Ground truth" table (that is the
   same claim, restated); from the code. Walk the table and confirm each written
   sentence against its source, then tick it off:

   | prose claim | re-read |
   |---|---|
   | `▲` / `▼` / `E:lo`,`E:md`,`E:hi`,`E:?` | `monitor_shared._IMPROVE_ARROW`, `_WORSEN_ARROW`, `_EFFORT_TOKENS` |
   | bold/plain/dim = high/medium/low; `?` = unstated | `_magnitude_markup`, `_entry_seg` |
   | `▲–`/`▼–` = priced-as-nothing; omitted side renders nothing | `_PRICED_NOTHING`, `_side_segs` |
   | `+N`; and the core never degrades | `trade_profile_rungs` (the `build(...)` ladder, not only its docstring) |
   | wide `mark badge region profile body` / narrow 3-line | `_ConcernRow.render`, `.three-line` CSS |
   | badge derived + `≠`, and the unpriced exemption | `_badge_seg`, `_PRIORITY_MISMATCH_MARK` |
   | guidance wording, quoted exactly | `_CONCERN_GUIDANCE` (copy the string; do not paraphrase the `·` separators) |
   | guidance needs ~80 cols **and** 24 rows, on the picker's own screen | `_GUIDANCE_MIN_WIDTH`, `_GUIDANCE_MIN_HEIGHT`, `_apply_guidance_visibility` |
   | "priced" = three-way OR | `concern_parser.has_impact_vector` |
   | the 7 dimension names already on the page | `concern_dimensions.CONCERN_DIMENSIONS` |

   Any disagreement: **the code wins and the prose changes** — this task
   documents what ships, not what t1636_4's task file illustrated.

2. **Anchor resolution — `hugo build` will not do this for you.** After the
   build, confirm every new heading really produced the id the links use, and
   that every fragment those links target exists in the built HTML:

   ```bash
   cd website && hugo build --gc --minify
   grep -o 'id="read-the-trade-profile"' public/docs/workflows/shadow-agent/index.html
   grep -o 'id="how-to-pick-shadow-concerns"' \
     public/docs/tuis/minimonitor/how-to/index.html \
     public/docs/tuis/monitor/how-to/index.html
   ```

   Each must print a hit. Then grep the four edited sources for every `#`
   fragment written or touched by this change and confirm each one appears as an
   `id=` in the corresponding built page. A missing hit means a silently dead
   link, not a build failure.

2b. **C6 sweep — the qualifier is present on every page that makes the claim.**
   Grep all four edited pages for each of `trade profile`, `≠`, and the
   guidance-line mention, and confirm **every** hit sits in a sentence that
   scopes it to a concern that priced itself. A hit without the qualifier is a
   defect even on the overview page — especially there. This is a manual read of
   each hit, not a pattern match: there is no test for it.

3. `python -m pytest tests/test_shadow_disposition_surfaces.py` — green
   (13 passed is the current baseline). `shadow-agent.md` is both an anchored
   site and a whole-file swept surface there, so C2 is enforced mechanically.
   This is the one class of staleness with a real machine check; it does **not**
   validate any claim in step 1.
4. `python -m pytest tests/test_concern_dimensions.py` — confirms the vocabulary
   this prose leans on is still the one in the tree. It does not read the
   website; it is a precondition for step 1's last row, not a check of it.
5. Re-read each of the four edited pages **end to end** for stale claims the
   t1636 children made untrue. The two found in planning are listed above; the
   sweep is the point, not those two fixes. The known **non**-finding: the
   recheck-loop prose ("Every review round re-derives the shadow's findings from
   scratch") is still accurate and must be left alone — it travels with t1650.
6. Confirm no new `blocking`/`follow-up` pair was written without
   `informational` nearby (step 3 proves this mechanically).

## Risk

### Code-health risk: low
- The page becomes a third, unguarded copy of the dimension vocabulary and
  drifts from `concern_dimensions.py` · severity: low · → mitigation: inline —
  constraint C1 above (describe the axes, one worked example, never tabulate the
  short labels)
- Documentation-only change across four markdown files; no code, no scripts, no
  test fixtures touched. Blast radius is website prose.

### Goal-achievement risk: medium
- **No automated check reads these four pages for UI accuracy.** A wrong glyph
  meaning, a wrong 80×24 threshold, a wrong layout rule or a wrong badge rule
  ships green — `hugo build` only compiles and `test_concern_dimensions.py`
  never opens a website file · severity: medium · → mitigation: inline —
  Verification step 1, a claim-by-claim re-read against the implementing symbol,
  marked non-optional
- **A broken `#fragment` is not a build failure.** Hugo fails a bad `relref` but
  not a bad anchor, and this change adds one new heading plus links to it from
  three pages · severity: medium · → mitigation: inline — Verification step 2
  greps the built HTML for each `id=`; the heading is also named apostrophe-free
  so its generated anchor is unambiguous
- Prose describes the derived badge / `≠` / profile row / guidance line as
  universal, falsely describing the unpriced rows the user still sees ·
  severity: medium · → mitigation: inline — constraint C6, required explicitly
  in **all four** change items (the `_index.md` overview is the easiest place to
  drop it and the worst place to drop it) and checked by Verification steps 1
  and 2b
- The end-to-end stale-claim sweep (Verification step 5) misses a claim a t1636
  child made untrue · severity: low · → mitigation: inline — full re-read of
  each edited page; the disposition guard covers the one class with a machine
  check

Every risk above is discharged by a constraint or a verification step already
written into this plan, so no *separate* mitigation task is proposed:
`risk_mitigations_planned = false`. The honest read of the medium levels is that
this task's correctness rests on **disciplined manual verification**, because
the surface being documented has no doc-accuracy guard — which is precisely why
steps 1 and 2 are marked non-optional rather than left as a habit.

## Post-implementation

Follow **Step 9 (Post-Implementation)** of the shared task workflow for the
commit, gate recording, and archival steps. Current-branch mode: nothing is
merged.
