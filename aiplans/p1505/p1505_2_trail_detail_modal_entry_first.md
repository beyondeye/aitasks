---
Task: t1505_2_trail_detail_modal_entry_first.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/t1505/t1505_1_bytrail_summary_pane.md, aitasks/t1505/t1505_3_trail_narrative_overview_field.md, aitasks/t1505/t1505_4_trail_skill_lite_default.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_*_*.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# p1505_2 — Entry-first trail detail modal

Fixes the By-Trail detail modal's wall of text. Depends on t1505_1 (same file),
independent of t1468_5.

## The defect

`TrailDetailScreen._sections()` (`.aitask-scripts/board/aitask_board.py:3858`)
appends, for the focused card: the entry, its wave, the whole trail narrative,
**every** drift reason, **every** observation, **every** exclusion and **every**
evidence record.

Against the live `art:trail-gates-framework-landing` that is 19 observations, 2
exclusions and 56 evidence lines — **byte-identical on every card**. Only the
leading entry/wave block differs, and it scrolls off the top. The code is not
wrong about what it has; it is wrong about scope, rendering document-level
content in an entry-level view.

## Implementation steps

### 1. Entry-scoped projection

Restructure `_sections()` to this order:

1. **Entry** — classification, confidence, rationale, expected outcome, why order
   matters, caveats.
2. **Wave** — purpose, why now, consequence of delay.
3. **Drift for this entry** — reasons naming this entry's ref only. Reuse
   `trail_drift_by_ref` (`:764`), which already canonicalizes and buckets reasons
   by ref; do not re-filter by hand.
4. **Trail narrative** — problem statement, recommendation summary,
   `narrative.overview` when present (t1505_3), method note, caveats.
5. **Observations affecting this entry** — those whose `affects` names the
   entry's ref, plus a count of the rest.
6. **Evidence this entry cites** — resolved from the entry's `evidence_refs`,
   plus a count of the rest.
7. **Exclusions** — document-level and short; keep, but after the entry-scoped
   material.

Add a key that reveals the withheld document-level sections in full — the goal is
ordering and scoping, not deletion. Gate it with the same `check_action` +
in-action re-check discipline the other By-Trail keys use.

**All ref comparisons go through `canonical_trail_ref` (`:704`).** A stored trail
may spell a member `aitasks#t42` while drift reasons use `aitasks#42`; that helper
exists for exactly this mismatch, and raw string comparison would silently drop
matches.

### 2. A lite trail must read as complete

After t1505_4 the common trail has no observations, no relations, no exclusions
and exactly one evidence record. Decide explicitly what an absent section looks
like and pin it: an omitted heading is fine, a heading with nothing under it is
not. "This trail has no observations" and "the observations failed to render"
must not look the same.

### 3. Docs

- `aidocs/implementation_trail_design.md` §9 — the modal's entry-first projection
  and t1505_1's summary pane.
- §15 — update the wireframes to match.

## Post-phase (risk mitigations)

### modal_assertion_tripwire

`tests/test_board_bytrail_view.py` is 3,335 lines and pins current modal content.
Re-pointing those assertions is legitimate; the risk is a later well-meaning edit
"restoring" the missing sections.

Add a tripwire that fails **if the trail-global sections regress to rendering on
every card**: render the modal for two different entries of a multi-observation
fixture trail and assert their texts differ by more than the entry block — i.e.
that the document-level bulk is not duplicated into both. A test that only checks
"entry appears first" would still pass after such a regression.

When an existing assertion breaks, decide whether it encoded an invariant or just
the old fixture's shape. If it was an invariant, keep and re-point it — do not
delete a guard because it now fails.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the **last**
  line for the verdict.
- Modal for an entry with observations shows only those affecting it, with an
  accurate count of the rest.
- Modal for a lite trail (no observations/exclusions, one evidence record) reads
  as complete, with no empty section headings.
- The reveal key shows the full document-level sections.
- **The tripwire is observed to fail** when the filtering is temporarily reverted.
  A tripwire never seen failing is not a tripwire.
- Live check in a real terminal: open a card's modal in By-Trail and confirm the
  entry-specific content is what you see first, without scrolling.

**Trail artifact availability:** `ERROR:invalid_trail` on the two stored handles
before t1468_7 refreshes them to 1.1.0 is expected and is not a defect of this
child.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
