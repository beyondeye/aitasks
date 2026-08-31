---
Task: t1654_manual_verification_trail_interactive_run_summary_followup.md
Base branch: main
plan_verified: []
---

# Plan: t1654 — Manual-verification auto-execution (trail run summary, t1644)

## Context

t1654 verifies t1644 (`feature: Enrich the trail run summary and link the skill
from the board docs`), which split `/aitask-trail`'s end-of-run print into three
parts: the depth+summary core (all flows), a structural recap of waves/entries/
relations (create and refresh only), and a board pointer (all flows, last).

Auto-verification was run autonomously (Step 1.5, autonomous strategy) before
the interactive loop. All six items reached `pass`.

**Scope boundary honoured throughout:** the procedure forbids mutating
user-owned files outside the checklist. Items 2–4 therefore read the **real**
trail artifacts out of the artifact store (`ait artifact get --out <tmpfile>`)
and rendered Part 2 against them, rather than running a full `--refresh`, which
would re-author and write a new version of the user's trail. The skill states in
as many words that the recap "is read back from the trail JSON this run already
has on disk", so the document is the recap's complete input either way. Items 1,
5 and 6 were end-to-end live runs.

## Execution Log

### Item 1 — show flow prints parts 1 and 3 only

- Item text: Run `/aitask-trail --show art:trail-gates-framework-landing` and
  confirm the print ends with the depth, the overview and the board pointer, and
  carries NO wave/relation recap.
- Approach: CLI invocation — executed the Show Flow end to end.
- Action run:
  - `./.aitask-scripts/aitask_artifact.sh get art:trail-gates-framework-landing --out <tmp>/trail.json` (step 1)
  - rendered title/owner/scope/freshness/waves/entries/observations/exclusions (step 2)
  - `./.aitask-scripts/aitask_trail_gather.sh drift --trail art:trail-gates-framework-landing` (step 3)
  - rendered the run summary from the fetched JSON per the Part 1 / Part 3 spec (step 4)
- Output (trimmed):
  - drift → `CURRENT` / `DIGEST:8299481f70637a29`
  - run summary, exactly three lines:
    ```
    Depth: deep
    Eight waves. Wave 1 is now fully landed (eleven of eleven original entries done) …
    Also viewable in `ait board`: press z (By-Trail), s (choose trail), v (full summary), Enter (member detail).
    ```
  - `narrative` carries no `overview` key, so the summary line correctly fell
    back to `recommendation_summary` (the documented resolution order); no
    `Waves (N):` and no `Relations (N):` block appeared.
- Verdict: **pass**

### Item 2 — mixed-provenance types split into two labelled groups

- Item text: Run `/aitask-trail --refresh` on a deep trail carrying
  mixed-provenance relations and confirm each mixed type splits into two
  separately labelled `<type> · <provenance>:` groups.
- Approach: file inspection of the real document + Part 2 rendering.
- Action run: rendered Part 2 from `<tmp>/trail.json` (the live
  `art:trail-gates-framework-landing`, v-current, 56 relations) grouping by
  `(type, provenance)` in schema order, `fact` before `advisory`.
- Output (trimmed):
  ```
    verifies · fact:
      aitasks#1271 → aitasks#635_34; aitasks#1109 → aitasks#635_15; …
    verifies · advisory:
      aitasks#635_27 → aitasks#635_19
    informs · fact:
      aitasks#1264 → aitasks#1224; … (16 pairs)
    informs · advisory:
      aitasks#1262 → aitasks#1443
  ```
  Both mixed types (`verifies` 4 fact / 1 advisory, `informs` 16 fact / 1
  advisory) split into two separately labelled groups, exactly as the checklist
  predicted. `provenance` was read off each record, never inferred: the
  cross-check against `art:trail-mobile-shadow-driving-deep` shows
  `coordinates_with · fact` there while the gates trail has
  `coordinates_with · advisory`, so type does not determine provenance.
- Not done: the preceding re-gather / re-author / artifact write of a full
  `--refresh` (see Context).
- Verdict: **pass**

### Item 3 — all five types get endpoint groups; block stays ~30 lines

- Item text: On that same 56-relation trail, confirm all five relation types get
  endpoint groups, and that the relations block stays around 30 lines rather
  than one line per edge.
- Approach: same rendering as item 2, plus a line count.
- Output (trimmed): per-type count line
  `hard_depends 12, advisory_precedes 16, coordinates_with 6, verifies 5, informs 17`,
  followed by seven `(type, provenance)` groups covering **all five** types —
  `hard_depends · fact` (12), `advisory_precedes · advisory` (16),
  `coordinates_with · advisory` (6), `verifies · fact` (4),
  `verifies · advisory` (1), `informs · fact` (16), `informs · advisory` (1).
  No type reduced to a bare count. Rendered relations block = **33 lines** for
  56 edges (heading + count line + 7 group headers + wrapped pairs), versus 63+
  at one line per edge.
- Verdict: **pass**

### Item 4 — lite trail's relations line

- Item text: Create or refresh a trail at lite depth and confirm the relations
  line reads exactly `Relations: none recorded at this depth (lite trails omit
  them).`
- Approach: used a **real** lite artifact instead of fabricating one —
  `art:trail-mobile-shadow-driving` (`rendering_hints.depth == "lite"`,
  `relations` key **absent**, which is what rule `lite_shape` requires).
- Action run: `aitask_artifact.sh get art:trail-mobile-shadow-driving --out …`,
  then Part 2 rendering.
- Output (trimmed):
  ```
  Relations: none recorded at this depth (lite trails omit them).
  ```
  Not `Relations (0):`, not an empty heading. The sibling deep trail
  (`…-driving-deep`, 13 relations) confirms the other branch renders the
  count form, so the two degradations stay distinct.
- Verdict: **pass**

### Item 5 — task refs print verbatim, cross-repo included

- Item text: Confirm entry and relation task refs print verbatim
  (`aitasks#635_27`), never shortened to `635_27`, including for any cross-repo
  member.
- Approach: scanned every ref in all four stored trails, plus visual check in
  the live board.
- Output (trimmed): across `trail-gates-framework-landing`,
  `trail-shadow-review-loop`, `trail-mobile-shadow-driving` and
  `trail-mobile-shadow-driving-deep`, **zero** unqualified refs — every entry
  `task` and every relation `from`/`to` carries a `<project>#<id>` form. The
  gates trail's own recap printed `aitasks#635_27`, `aitasks#1076_4`, etc.
  **Cross-repo coverage:** `art:trail-mobile-shadow-driving-deep` mixes
  `aitasks#…` with `aitasks_mobile#32_1` / `aitasks_mobile#32_2`; the
  `coordinates_with · fact` group printed those with the foreign project
  segment intact. The board's own member-detail pane also headed the card
  `Entry aitasks#635_27`.
- Verdict: **pass**

### Item 6 — board pointer keys do what the line claims

- Item text: In `ait board`, press `z`, then `s`, then `v`, then `Enter` on a
  member card, and confirm each key does what the run summary's board pointer
  line claims it does.
- Approach: TUI interaction — real `ait board` in a detached tmux session
  (`av1654`, 200x50), driven with `tmux send-keys`, read back with
  `tmux capture-pane -p`.
- Action run / output (trimmed):
  - `z` → header became `aitasks board — By-Trail: …`; with nothing selected the
    view itself said "No trail selected — press s to choose one". **By-Trail ✓**
  - `s` → modal "Select trail — ↑/↓ move · Enter open · Esc cancel" listing all
    four stored trails; footer read `s Select Trail`. **choose trail ✓**
  - selected "Gate framework landing order (t635 topic)" → eight wave columns of
    member cards, header `· deep`.
  - `v` → "Trail summary — Gate framework landing order (t635 topic)" overlay
    carrying the whole narrative. **full summary ✓** — and its text is
    character-identical to the run summary's Part 1 line, which is the
    `trail_summary_text()` parity the skill requires of the two surfaces.
  - `Enter` on a focused member card → "Entry aitasks#635_27" detail with
    classification, confidence, rationale, expected outcome, why-order-matters,
    caveats and wave context. **member detail ✓**
  - Static drift guard: `pytest tests/test_board_bytrail_view.py` → **145
    passed** (includes t1644's `RunSummaryBoardPointerTests`, which reads the
    App-level BINDINGS by action name and asserts the golden prose names those
    keys).
  - Note: `.aitask-scripts/board/aitask_board.py` carried uncommitted in-flight
    work from t1603_3 during this run. The diff touches none of
    `view_bytrail` / `trail_select` / `trail_summary_expand` / `view_details`
    nor `BINDINGS`, so the four keys under test were unaffected.
- Verdict: **pass**

## Cleanup

- `tmux kill-session -t av1654` — done; no `av1654` session remains.
- Scratch dir `<scratchpad>/av1654/` (fetched artifact JSON, `recap.py`,
  rendered output) — session-scoped scratchpad, removed below.
- No file under `aitasks/` or `aiplans/` was mutated other than this plan and
  t1654's own checklist. No artifact version was written.
