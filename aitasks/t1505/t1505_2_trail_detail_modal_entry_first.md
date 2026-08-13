---
priority: high
effort: medium
depends: [t1505_1]
issue_type: enhancement
status: Implementing
labels: [aitask_board, tui, trails, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-08-13 12:26
updated_at: 2026-08-13 23:44
---

## Context

Parent: **t1505**. Read the parent plan
`aiplans/p1505_lite_trail_mode_and_trail_summary_pane.md`.

This child fixes the **wall of text** in the By-Trail detail modal. It is
independent of the in-flight t1468_5 (which does not edit `aitask_board.py`), but
depends on **t1505_1** because both edit the same file.

## The defect, precisely

`TrailDetailScreen._sections()` (`.aitask-scripts/board/aitask_board.py:3858`)
builds one `Text` for the focused card and appends, in order: the entry's fields,
its wave, the whole trail narrative, **every** drift reason, **every**
observation, **every** exclusion, and **every** evidence record.

Measured against the live `art:trail-gates-framework-landing`: 19 observations,
2 exclusions and 56 evidence lines. Those sections are **byte-identical on every
card** — only the leading entry/wave block differs. So the modal for t635_29 and
the modal for t1416 are ~95% the same text, and the part that distinguishes them
scrolls off the top. There is nothing to compare one card against another with,
which is exactly the reported experience.

The current code is not wrong about *what* it has — the sections are all
legitimately part of the document. It is wrong about *scope*: it renders
document-level content in an entry-level view.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `TrailDetailScreen` (`:3825-3935`),
  chiefly `_sections()`.
- `aidocs/implementation_trail_design.md` — §9 (By-Trail view) and §15
  (wireframes).
- `tests/test_board_bytrail_view.py`.

## Implementation plan

### 1. Make the projection entry-scoped

Restructure `_sections()` so the focused entry leads and document-level bulk is
filtered to what concerns that entry:

1. **Entry** — classification, confidence, rationale, expected outcome, why order
   matters, caveats (unchanged content, still first).
2. **Wave** — purpose, why now, consequence of delay.
3. **Drift for this entry** — the reasons naming this entry's ref, not the whole
   list. (`trail_drift_by_ref` at `:764` already canonicalizes and buckets
   reasons by ref — reuse it rather than re-filtering by hand.)
4. **Trail narrative** — problem statement, recommendation summary,
   `narrative.overview` when present (t1505_3), method note, caveats.
5. **Observations affecting this entry** — those whose `affects` names the
   entry's ref, plus a count of the rest.
6. **Evidence this entry cites** — resolved from the entry's `evidence_refs`,
   plus a count of the rest.
7. **Exclusions** — document-level and short (2 and 13 in the live trails); keep
   them, but after the entry-scoped material.

Add a key that reveals the withheld document-level sections in full, so nothing
becomes unreachable — the goal is ordering and scoping, not deletion. Follow the
`check_action` gating and in-action re-check discipline used by the other
By-Trail keys.

**Ref comparison must go through `canonical_trail_ref`** (`:704`) — a stored
trail may spell a member `aitasks#t42` while drift reasons and other refs use
`aitasks#42`. That helper exists for exactly this mismatch; comparing raw strings
would silently drop matches.

### 2. A lite trail must read as complete, not broken

After t1505_4, the common trail will have **no** observations, **no** relations,
**no** exclusions and exactly one evidence record. A modal that renders empty
section headings, or silently nothing at all, reads as a bug in that case.
Decide explicitly what an absent section looks like and pin it — an omitted
heading is fine, a heading with nothing under it is not.

This is `unverifiable is not negative` in miniature: "this trail has no
observations" and "the observations failed to render" must not look the same.

### 3. Docs

- §9 — the detail modal's entry-first projection, and t1505_1's summary pane.
- §15 — update the wireframes to match.

## Post-phase (risk mitigation)

**`modal_assertion_tripwire`.** `tests/test_board_bytrail_view.py` is 3,335 lines
and pins current modal content. Re-pointing those assertions is legitimate, but a
restructure like this can be quietly undone later by a well-meaning edit that
"restores" the missing sections.

Add a tripwire that **fails if the trail-global sections regress to rendering on
every card**: render the modal for two different entries of a multi-observation
fixture trail and assert their texts differ by more than the entry block — i.e.
that the document-level bulk is not duplicated into both. A test that only checks
"entry appears first" would still pass after a regression.

When you change an existing assertion, check whether it encoded an invariant or
merely the old fixture's shape. If it was an invariant, keep it and re-point it;
do not delete a guard because it now fails.

## Verification steps

- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the LAST
  line for the verdict.
- Modal for an entry with observations shows only those affecting it, with an
  accurate count of the rest.
- Modal for a lite trail (no observations/exclusions, one evidence record) reads
  as complete.
- The reveal key shows the full document-level sections.
- The tripwire fails when the filtering is reverted (verify by temporarily
  reverting it — a tripwire that has never been seen to fail is not a tripwire).
- Live check in a real terminal: open a card's modal in By-Trail and confirm the
  entry-specific content is what you see first, without scrolling.

**Trail artifact availability:** t1468_5's schema bump to `1.1.0` invalidates both
stored artifacts until t1468_7 refreshes them. An `ERROR:invalid_trail` on those
handles is expected and is not a defect of this child.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T20:44:29Z status=pass attempt=1 type=human
