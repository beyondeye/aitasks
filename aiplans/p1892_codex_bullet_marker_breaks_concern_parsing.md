---
Task: t1892_codex_bullet_marker_breaks_concern_parsing.md
Branch: main
Base branch: main
Output branch: main
---

# t1892 — Codex `•` bullet marker breaks concern-block parsing

## Context

Codex CLI's markdown renderer (measured: codex-cli 0.160.0) rewrites the
mandatory `- ` concern-item marker to `• ` (U+2022, bytes `E2 80 A2`). All three
marker patterns in `.aitask-scripts/monitor/concern_parser.py` require a literal
dash, so a Codex shadow's block never parses: `c` in minimonitor shows the raw
view with the wrong cause, and the auto-offer never badges. `_MARKER_START` also
requires the dash, so `unrecovered_markers()` returns `[]` and the t1274/t1293
"N line(s) could not be parsed" report never fires for this failure.

The live capture of shadow pane `%263` was re-taken read-only during planning.
Lines 52–55 are the verbatim block head (fence, `Round: 2 @ …`, blank, `  • [high
| lifecycle and retry] Implementation step 2 sets`). The bullet bytes were
confirmed with `od`. The rest of the pane is Codex chrome, plus the other
project's prose, which must not be committed.

**Decisions (user-confirmed in planning):**
- **Consumer-side fix.** Accept a closed set of **measured** glyphs: `-`
  (canonical) and `•` (U+2022). Nothing unmeasured.
- **Widen the loss diagnostic separately.** It reports *any* single
  non-word punctuation glyph followed by whitespace and `[` (`* [`, `◦ [`, `▪ [`
  …). The next renderer that rewrites the glyph is then reported instead of
  degrading silently.
- **The producer-side alternative is rejected.** Emitting the block so no
  renderer touches it would change every agent's output, would need a live
  measurement per agent, and would not help blocks already emitted.
- **The alternate-screen/viewport-truncation issue gets its own task.** It
  is not fixed here (see Risk).

No consumer code changes: `minimonitor_app.py`, `monitor_app.py` and
`monitor_shared.py` all go through the parser's public functions
(`parse_concerns`, `has_concern_block`, `unrecovered_markers`), so fixing the
parser fixes all of them. `build_clipboard_payload` / `concern_marker_line`
already re-render canonically as `- [p | r] body`. `concern_block_signature`
hashes the raw region and is glyph-agnostic. The producer docs
(`plan-challenge.md`, `impl-challenge.md`, `plan-assumptions.md`,
`plan-diagnose-errors.md`) and the website prose state the *producer* rule (emit
`- `), which stays true, so they are unchanged.

## Implementation

### 0. Snapshot the pre-change parser for red proofs (before any edit)
Snapshot into the scratchpad. Never stash, never restore: the worktree has
unrelated dirty files from concurrent work.
```bash
S=<scratchpad>/old_monitor; mkdir -p "$S"
git show HEAD:.aitask-scripts/monitor/concern_parser.py   > "$S/concern_parser.py"
git show HEAD:.aitask-scripts/monitor/ansi_utils.py       > "$S/ansi_utils.py"
git show HEAD:.aitask-scripts/monitor/concern_dimensions.py > "$S/concern_dimensions.py"
```

### 1. Parser — `.aitask-scripts/monitor/concern_parser.py`
- Insert this before `_ITEM`, replacing its "Leading `- ` is MANDATORY" comment:
  ```python
  # Item-marker glyphs the parser ACCEPTS: a closed set of MEASURED values only.
  # The producer always emits "- "; an agent TUI's markdown renderer may rewrite
  # it before tmux sees it.
  #   "-"       canonical — what every producer emits
  #   "•"  BULLET — Codex CLI's renderer rewrites "- " to "• " (t1892,
  #             measured on codex-cli 0.160.0)
  # Collision hardening survives the widening: a renderer emits its bullet only
  # at a list-item start, so a wrapped continuation row never begins "• [" any
  # more than it begins "- [". Add a glyph here only after observing it live.
  _MARKER_GLYPHS = "-•"
  _GLYPH = f"[{re.escape(_MARKER_GLYPHS)}]"
  ```
- Change `_ITEM`, `_ITEM_NO_REGION` and `_MARKER_START` from `^\s*-\s+\[` to
  `^\s*{_GLYPH}\s+\[` (rf-strings, mind `{{`/`}}` if any). Keep the rest of
  each pattern byte-identical.
- Add a diagnostic-only pattern next to `_MARKER_START`:
  ```python
  # Any row that LOOKS like a list-marker item: one non-word, non-space,
  # non-bracket glyph, whitespace, "[". Deliberately wider than _GLYPH and
  # REPORT-ONLY: it never yields a concern and never steers parsing — it only
  # names a marker-looking row the parser could not use, so a renderer
  # rewriting the marker to an unmeasured glyph is REPORTED, not silently
  # swallowed (t1892; the diagnostic used to require the dash and went blind
  # exactly here). Never use it as the split-join stop: a region fragment may
  # itself start with punctuation ("— [reference] …") and must stay joinable.
  _MARKER_LIKE = re.compile(r"^\s*[^\w\s\[\]]\s+\[")
  ```
- `_join_split_marker`: the stop condition stays `_MARKER_START.match(nxt)`.
  Its meaning is "this row starts a NEW item", which is an **accepted-glyph**
  item start, now `-` or `•`, so a split `•` marker cannot swallow the next `•`
  item. It does **not** become `_MARKER_LIKE`. A punctuation-led region
  continuation (`— [reference] body`) must keep rejoining exactly as today; the
  user's review simulated the broad stop and got 0 concerns plus 2 lost-marker
  reports, where today's parser recovers 1. Update the inline comment to say
  "a row that starts an accepted item marker" instead of `"- ["`.
- `_scan_items`: keep `_MARKER_START` as the split-join **gate** (accepted glyphs
  only). Change **only** the unrecovered-report test
  `if _MARKER_START.match(line)` to `_MARKER_LIKE`. Update its docstring
  paragraph about `unrecovered`.
- Update the module docstring bullet (the `- [priority | region] body` marker
  paragraph) to name the accepted glyph set and the renderer rewrite.

### 2. Real-bytes fixture — `tests/fixtures/codex_shadow_bullet_capture.txt`
Copy **only** the verbatim block head from the live capture, bytes preserved:
`sed -n '52,55p' <scratch>/cap263.txt > tests/fixtures/codex_shadow_bullet_capture.txt`.
That is the fence, the round header, the blank line and the `•` item row. None
of the other project's prose or the Codex chrome goes in. Re-check with
`od -c` that it holds `342 200 242` and no ASCII `- [`.

### 3. Parser tests — `tests/test_concern_parser.py`
New class `TestCodexBulletMarkers` (t1892). Helpers:
- `_codex_head()` reads the fixture as **bytes**, asserts
  `b"\xe2\x80\xa2 [" in raw` and `b"- [" not in raw`, and returns the decoded
  text. `_glyph()` is taken from the item row (`row.lstrip()[0]`), so every
  synthesized row uses the captured glyph, never a hand-typed one.
- `_codex_block()` is the fixture head plus Codex-style hanging-indent
  continuation rows, a second `<glyph> [medium | parser] …` item, a region-less
  `<glyph> [low] …` item, and the closing fence.
- `_dash_twin(text)` replaces the leading glyph of each marker row with `-`.

Tests:
1. `test_live_head_row_parses` (AC1, red): `parse_concerns(fixture)` gives exactly
   one concern, `("high", "lifecycle and retry", "Implementation step 2 sets")`.
2. `test_complete_block_matches_its_dash_twin` (AC1, red): equal
   `(priority, region, body)` tuples, and the count equals the number of marker
   rows.
3. `test_has_concern_block_fires` (AC2, red): `has_concern_block(_codex_block())`
   is True. The control: it is also True for the dash twin.
4. `test_malformed_bullet_rows_are_reported` (AC3, red):
   `<glyph> [ | region] no priority` and `<glyph> [medium | never closes` each
   appear in `unrecovered_markers`.
5. `test_unmeasured_glyph_is_reported_not_parsed`: `◦ [high | x] body` and
   `* [high | x] body` yield no concern and are reported (the
   diagnostic-blindness fix for the next renderer).
6. `test_clipboard_payload_is_byte_identical` (AC4):
   `build_clipboard_payload(parse(codex)) == build_clipboard_payload(parse(dash twin))`,
   and every payload item line starts with `- [`.
7. `test_split_bullet_marker_is_rejoined`: Codex's own hard-wrap inside the
   bracket (`<glyph> [medium | .claude/skills/aitask-shadow/impl-review-` /
   `angles.md] body`) parses to one concern, and the following item survives.
8. `test_bullet_mid_body_is_not_a_marker`: a continuation containing
   `• [high | x]` mid-line is neither an item nor reported (collision control).

Two cases in the existing `TestSplitMarkerJoin`, placed directly after
`test_failed_join_consumes_nothing` (the next-item preservation test):
9. `test_punctuation_led_region_fragment_is_still_rejoined` (regression guard
   from the review). `block("- [medium | long context", "— [reference] body")`
   parses to exactly
   `[Concern("medium", "long context — [reference", "body")]`, and
   `unrecovered_markers(...) == []`. It passes on the old parser and must keep
   passing.
10. `test_failed_bullet_join_consumes_nothing`: the `•` twin of
    `test_failed_join_consumes_nothing`. `<glyph> [high | unclosed bracket row`
    followed by `<glyph> [low | real region] The real concern.` keeps the real
    concern.

### 4. Consumer wiring tests (the pushed-instance level)
- `tests/test_minimonitor_concern_action.py`:
  - `ActionPickConcernsTests.test_codex_bullet_block_opens_the_picker`: the
    pushed screen is a `ConcernPickerModal` (not `ConcernBlockInspectModal`)
    holding the parsed concerns. There is no `unparsed`/`uncertified` warning.
  - `AutoOfferTests.test_codex_bullet_block_fires_once`.
- `tests/test_monitor_concern_action.py`: `ActionPickConcernsTests` gets one
  equivalent picker test for the full monitor.
- Both build the block from the same fixture file (a small local loader, the
  `osc8_capture_pane.txt` pattern from `tests/test_ansi_utils.py`).

### 5. Format spec — `.claude/skills/aitask-shadow/concern-format.md`
- **Concern markers:** the producer rule ("MUST emit `- `") is unchanged. Add a
  bullet: *Accepted marker glyphs (consumer tolerance)*. This is the closed set
  `-` and `•` (U+2022). It exists because Codex CLI's markdown renderer
  **replaces** the list-marker glyph (observed codex-cli 0.160.0, t1892) and the
  fences and `Round:` header survive intact. The bullet also explains why the
  collision invariant survives, and that a glyph is added only after it is
  measured live.
- **Split-marker hazard paragraph:** add the glyph-rewrite fact beside the
  hard-wrap note (same renderer, the more fundamental breakage).
- **Trigger vs. action (`unrecovered_markers` paragraph):** the loss report
  counts any row that begins with one punctuation glyph, whitespace and `[`,
  including glyphs outside the accepted set. An unmeasured renderer rewrite is
  therefore reported, never silent. Reporting removes nothing: a reported row
  that follows an item stays in that item's body and is forwarded with it. The
  wider shape is **report-only** in a second sense too: the
  split-marker recovery still stops only at an accepted item start, so a region
  fragment beginning with punctuation keeps rejoining.
- Keep the doc parser-safe: no contiguous open→items→close example. The
  `TestShadowDocsNotParserLive` guard checks this.

### Post-phase (risk mitigations)
1. [pin_marker_like_residual] In `TestCodexBulletMarkers`, add
   `test_punctuation_led_continuation_is_reported_accepted_residual`. A wrapped
   body row beginning `— [see t1167] …` after a `•` item stays a continuation of
   that concern and **is** listed by `unrecovered_markers`. The test asserts
   three things:
   - the concern's `body` contains the row's text, so nothing is removed;
   - `build_clipboard_payload` **includes** that text, so it is forwarded as
     part of the body;
   - `unrecovered_markers` reports the row.

   The docstring states the accepted residual. The diagnostic is advisory: it
   warns (a count and the raw view) but never removes text from a forwardable
   body, so a false positive costs a spurious warning and the row is still
   forwarded with its concern, which is correct because it really is body
   text. Mirror one sentence in `concern-format.md`, worded the same way.

## Verification
1. **Red proofs (AC5).** Copy `tests/test_concern_parser.py` to the scratchpad
   and rewrite its `sys.path.insert` target (and the fixture path) with `sed` to
   the step-0 snapshot. Run only `TestCodexBulletMarkers`. Tests 1–4 must
   **fail** against the old parser. Then run them against the real tree: pass.
   Record both outputs in the plan's Final Implementation Notes.
   **Mutant check for test 9.** Copy the *new* parser to the scratchpad and
   switch its join stop to `_MARKER_LIKE` (the rejected design). Run test 9
   against that copy: it must **fail**. The real tree must pass. This proves the
   guard catches exactly the regression the review found. Mutate only the
   scratch copy, never the tree.
2. Unchanged suites (AC7):
   `python3 -m pytest tests/test_concern_parser.py tests/test_minimonitor_concern_action.py tests/test_monitor_concern_action.py tests/test_concern_picker_modal.py tests/test_minimonitor_concern_smoke.py tests/test_shadow_seam.py -q`.
3. Full Python suite once: `bash tests/run_all_python_tests.sh` (`set -o pipefail`;
   read only the last-line verdict).
4. Live re-check (read-only). Re-capture `%263` via
   `aitask_shadow_capture.sh --deep --any-pane %263` and print `parse_concerns` /
   `unrecovered_markers`. Expect 1 concern now. Its body carries Codex chrome
   because the block is viewport-truncated, which is the follow-up's evidence.

## Risk

### Code-health risk: low
- The wider `_MARKER_LIKE` diagnostic can report a genuine wrapped body row that
  happens to start with `<punct> [` as an unparsed marker. The diagnostic warns
  (a count and the raw view) without removing text: the row stays in the
  preceding concern's body and is forwarded with it, as before. The cost of a
  false positive is one spurious warning, never lost or altered body text.
  · severity: low (residual — pinned by inline post-phase pin_marker_like_residual) · → mitigation: inline post-phase pin_marker_like_residual
- The split-join stop condition keeps its "accepted item start" meaning and
  widens only by the newly accepted `•` glyph. A region fragment beginning
  `• [` would now stop a join. That is implausible, because renderers emit the
  bullet only at a list-item start. The broader `_MARKER_LIKE` is
  report-only by construction (the rejected design regressed punctuation-led
  region fragments; it is pinned by test 9 plus the mutant check).
  · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Planning reproduced the user's actual observed capture (`%263`), and the
  block in it is **viewport-truncated**. Codex runs on the alternate screen, so
  tmux keeps no scrollback and `--deep` buys nothing. Once markers parse, `c` on
  such a capture opens a picker whose last item carries Codex chrome
  (`New activity · ↓ Back to bottom`, composer, footer) via the forgiving
  parse-to-EOF, where today it shows the raw view. The ACs are met, but that
  live scenario is only clean when the whole block is on screen.
  · severity: medium · → mitigation: t1898
- Only `•` is measured. opencode and agy were not measured. A different rewrite
  would still not parse, though it would now be *reported*.
  · severity: low · → mitigation: t1899

### Planned mitigations
- timing: post-phase | name: pin_marker_like_residual | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: wider _MARKER_LIKE diagnostic false-positive (code-health) | desc: Pin the report-only false positive of a punctuation-led continuation row with a test and one spec sentence
- timing: after | name: codex_alternate_screen_block_capture | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: viewport-truncated Codex block parsed to EOF with chrome in the last concern (goal-achievement) | desc: Codex shadow panes run on the alternate screen (no tmux scrollback): define the capture strategy and how an unclosed block is presented on `c` so pane chrome is never forwarded as concern body. USER REQUIREMENT (acceptance criterion, 2026-10-05): scrolling the Codex shadow window must not change the latest review's concern list or its freshness verdict — both must refer to the same latest completed review, independently of the visible screen | created: t1898
- timing: after | name: measure_agent_tui_marker_rendering | type: chore | priority: low | effort: low | inline_risk: medium | added_complexity: medium | addresses: only the Codex glyph is measured (goal-achievement) | desc: Measure live whether opencode and agy shadow panes rewrite the `- ` concern marker; add any measured glyph to concern_parser._MARKER_GLYPHS and concern-format.md | created: t1899

Reassessment (post-inline, single pass): the inline post-phase only adds a test
and a spec sentence, so both levels are unchanged (code-health low,
goal-achievement medium). The `codex_alternate_screen_block_capture` follow-up is
created by Step 8d. It must **not** also be listed under "Upstream defects
identified", because that would offer it a second time at Step 8b.

## Post-implementation
Step 9 of task-workflow: current-branch mode, so there is no merge. The steps
are build verification / gates (`risk_evaluated`), then archival with
`aitask_archive.sh 1892`, then push with `./ait git push`.

## Post-Review Changes

### Change Request 1 (2026-10-05 17:24)
- **Requested by user:** (a, blocking) Accepting U+2022 in `_ITEM` made a
  wrapped body row that begins with a quoted `• [high | example] …` inside an
  ordinary dash block parse as a second concern. The pre-change parser gave one
  concern there. Distinguish continuation text using reliable capture structure.
  (b, follow-up) A split-marker rejoin consumes a following marker-looking row
  (`◦ [high | next] …`) into the region without reporting it. This is inherited
  from the dash baseline. Pin the boundary and qualify the doc's universal
  "reported, never silent" claim.
- **Changes made:**
  - (a) A **one-glyph-per-block** rule. `_GLYPH` now captures the glyph;
    `_block_glyph(lines)` takes the block's glyph from its first accepted marker
    row; `_starts_item(line, glyph)` gates `_ITEM`, the split-join gate and stop,
    and `_ITEM_NO_REGION`. A row led by the other accepted glyph is body text,
    still reported by `_MARKER_LIKE`, and never removed. The reliable structure
    is that a renderer rewrites every list item of a block the same way.
  - Tests:
    - `test_quoted_bullet_at_wrap_boundary_in_a_dash_block_stays_body`, the
      reviewer's exact case. It gives one concern, field-identical to the
      baseline, plus a report.
    - Its mirror, `test_quoted_dash_at_wrap_boundary_in_a_bullet_block_stays_body`.
    - `test_same_glyph_quote_at_wrap_boundary_is_an_inherited_limit`, which pins
      the limit that predates this change, for both glyphs.
  - `test_malformed_bullet_rows_are_reported` now uses a `•` good item, so it
    tests a malformed row *within* a bullet block (AC3).
  - (b) `test_split_join_consumes_a_marker_looking_row_known_gap` pins the
    inherited gap for both first-marker glyphs. The comments, docstrings and
    `concern-format.md` now say "reported rather than silent", with the
    split-join exception stated.
- **Red proof:** against the first implementation (`v1` snapshot), exactly the
  two new wrap-boundary tests fail and the other 21 Codex/split tests pass.
  Baseline checks on the pre-change parser: the reviewer's case gives 1 concern
  and no report, and the dash-first split gap is identical (1 concern, no
  report).
- **Files affected:** `.aitask-scripts/monitor/concern_parser.py`,
  `tests/test_concern_parser.py`, `.claude/skills/aitask-shadow/concern-format.md`

### Change Request 2 (2026-10-05 17:44)
- **Requested by user:** (blocking) `_block_glyph` chose the first
  marker-*looking* row before it parsed. In `• [medium | malformed` followed by
  `- [high | real] real body`, the split rejoin crossed the valid item and
  manufactured a fake medium concern; `• [ | bad] malformed` before the same
  item gave zero concerns. Both returned the real concern before t1892. Keep the
  cross-glyph quotation fix, stop malformed leading rows from selecting the
  glyph, and add regression tests for both cases.
- **Changes made:**
  - `_block_glyph` now returns the glyph of the first marker row that
    **yields an item**: it parses on its own (`_ITEM` / `_ITEM_NO_REGION`),
    or its split rejoin succeeds under a **conservative** stop at any accepted
    marker, whatever its glyph. It returns `None` when nothing yields an item.
  - `_join_split_marker(..., glyph=None)` is that probe mode.
  - Docs (`concern_parser.py` comment and docstring, `concern-format.md`)
    now say "first row that yields an item".
  - Tests:
    - `test_unclosed_leading_row_does_not_swallow_the_next_item` and
      `test_closed_malformed_leading_row_does_not_demote_the_next_item` (the
      review's two cases).
    - Two edge guards for the new rule:
      `test_split_leading_marker_still_selects_its_glyph` and
      `test_split_only_bullet_block_still_parses`.
- **Red proof:**
  - Against v2 (the previous iteration), exactly the two review tests fail.
  - Against the pre-change parser, the concerns are field-identical
    (`[('high','real','real body')]` for both), and only the new report
    assertion differs.
  - Mutant with the probe stopping only at the same glyph: exactly
    `test_unclosed_leading_row_does_not_swallow_the_next_item` fails, so the
    conservative probe is pinned.
- **Files affected:** `.aitask-scripts/monitor/concern_parser.py`,
  `tests/test_concern_parser.py`, `.claude/skills/aitask-shadow/concern-format.md`

### Change Request 3 (2026-10-05 18:04)
- **Requested by user:** (blocking) The glyph probe (`glyph=None`) stopped at
  every accepted marker prefix, including a non-parseable opposite-glyph region
  fragment. For `- [medium | long context` / `• [reference] body` /
  `  • [high | example] illustrative text.`, the baseline and v2 recovered one
  medium concern with the quotation in its body. v3 returned only the quoted
  high example, and the clipboard forwarded it while the real concern was lost.
  Distinguish genuine next-item boundaries from non-parseable opposite-glyph
  fragments, keep the malformed-leading-row fixes, and add the combined
  regression test.
- **Changes made:**
  - `_join_split_marker(lines, start, glyph, *, probe=False)`. The stop is a
    row in `glyph`; in probe mode it is **also** an opposite-glyph row that
    `_parses_alone` (a complete one-row item in any accepted glyph).
    `_block_glyph` probes with the candidate's own glyph and `probe=True`, so
    a non-parseable `• [reference]` fragment is rejoined into the region as
    before t1892, while a genuine next item (either glyph) still ends the probe.
  - Docs updated (`_block_glyph` / `_join_split_marker` docstrings, the stop
    comment, `concern-format.md`).
  - Test `test_nonparseable_opposite_glyph_fragment_does_not_end_the_probe`
    asserts the fields **and** that the clipboard payload carries the medium
    concern and not the quoted example.
- **Red proof:**
  - v3: exactly the new combined test fails.
  - v2: exactly the two malformed-leading-row tests fail.
  - Pre-change parser: the combined test passes.
  - Mutant "probe stops at any accepted prefix": exactly the combined test
    fails.
  - Mutant "probe never stops at an opposite-glyph complete item": exactly
    `test_unclosed_leading_row_does_not_swallow_the_next_item` fails.
  - So each half of the stop rule is pinned by its own guard.
- **Files affected:** `.aitask-scripts/monitor/concern_parser.py`,
  `tests/test_concern_parser.py`, `.claude/skills/aitask-shadow/concern-format.md`

### Change Request 4 (2026-10-05 22:05)
- **Requested by user:** (blocking) The probe stopped at an opposite-glyph row
  only when it parsed on one row, so a valid next concern that itself needed
  split recovery was swallowed. For `• [medium | malformed` / `- [high | real`
  / `region] real body`, the baseline and v3 return the genuine high concern;
  v4 returned a corrupted medium concern, reported nothing and forwarded it. The
  mirror direction failed too. Recognise recoverable split concerns as
  boundaries without restoring the broad prefix stop, add tests for both
  directions, and keep the earlier guards.
- **Changes made:**
  - New `_yields_item(lines, i)`, the single definition of "a genuine item
    starts here, read in its own glyph": a one-row item, or a successful
    probe-mode split rejoin. It replaces `_parses_alone`.
  - It is shared by `_block_glyph` (the glyph choice) and by the probe's
    boundary test in `_join_split_marker`. **Correction (Change Request 5):**
    this note originally said "The recursion walks forward only and is bounded
    by `_MAX_MARKER_JOIN_ROWS`", which was wrong. That constant bounds each
    local join, not the chain, and alternating-glyph unclosed markers recursed
    once per row (a RecursionError at the 1500-row deep capture). The recursion
    was replaced by an iterative table in CR5.
  - A non-parseable `• [reference]` fragment contains `]`, so it is neither a
    one-row item nor a split candidate, and it keeps rejoining.
  - Docs updated (docstrings, stop comment, `concern-format.md`).
  - Test `test_unclosed_leading_row_does_not_swallow_a_split_next_item` covers
    both directions and asserts the fields, the report, and that the payload
    carries no "malformed".
- **Red proof:**
  - v4: exactly the new test fails.
  - v3: the new test passes, and only its own combined case fails.
  - Pre-change parser: the bullet-first direction is correct and the
    dash-first mirror is corrupted (it never parsed bullets).
  - All earlier guards pass on the current tree.
- **Files affected:** `.aitask-scripts/monitor/concern_parser.py`,
  `tests/test_concern_parser.py`, `.claude/skills/aitask-shadow/concern-format.md`

### Change Request 5 (2026-10-05 22:51)
- **Requested by user:** (blocking) `_yields_item` called probe-mode
  `_join_split_marker`, which called `_yields_item` again on an
  opposite-glyph candidate with a fresh join allowance.
  `_MAX_MARKER_JOIN_ROWS` bounds each local loop, not the recursion depth.
  600 rows alternating `• [medium | unclosed` / `- [medium | unclosed` plus a
  final valid concern made `parse_concerns`, `has_concern_block` and
  `unrecovered_markers` raise RecursionError. The baseline returns the real
  concern, and the monitor supports 1500-line retry captures. Make it
  iterative or genuinely bounded, correct the explanation (docstring and CR4),
  and add long-block regressions for the three public entry points, with and
  without a final concern.
- **Changes made:**
  - `_yield_table(lines)` fills the per-row "yields an item in its own
    glyph" answers **back to front**, iteratively. A row's probe reads only
    already-filled later entries.
  - `_join_split_marker(..., boundary=yields)` replaces `probe=True` and
    reads the table instead of recursing.
  - `_block_glyph(lines, yields)` picks the first True row. The semantics are
    identical to CR4 (the same recurrence), and it is O(rows ×
    `_MAX_MARKER_JOIN_ROWS`) with constant stack depth.
  - Docstrings say this explicitly; CR4's claim is corrected in place.
  - Tests:
    - `test_long_alternating_malformed_block_with_a_final_concern` and
      `..._without_a_final_concern`, at `_DEEP_CAPTURE_ROWS = 1500`
      (`monitor_core._SHADOW_DEEP_RETRY_LINES`).
    - Both assert all three entry points. With a final concern: the real
      concern, a True trigger, and every malformed row reported. Without:
      `[]`, a False trigger, and every row reported.
- **Red proof:**
  - v5: exactly the two long-block tests fail, with RecursionError.
  - v4: only its own case fails.
  - All earlier guards and the full concern-parser suite pass.
  - Pre-change parser on the 1500-row block: `[('high','real')]`, reporting
    the 750 dash rows; the new parser reports all 1500 malformed rows.
  - Timing: 3.6 ms for the 1500-row block.
- **Files affected:** `.aitask-scripts/monitor/concern_parser.py`,
  `tests/test_concern_parser.py`

### Change Request 6 (2026-10-05 23:14)
- **Requested by user:** A requirement for the planned follow-up
  `codex_alternate_screen_block_capture`, not for this task's code:
  "Scrolling the Codex shadow window must not change the latest review's
  concern list or freshness verdict. Both must refer to the same latest
  completed review, independently of the visible screen."
- **Changes made:** The requirement is added verbatim, as an acceptance
  criterion, to that mitigation's `desc` in `### Planned mitigations`. Step 8d
  builds the follow-up's `## Goal` from `desc`, so it reaches the created task.
  No code change.
- **Files affected:** this plan file only.

## Final Implementation Notes
- **Actual work done:**
  - The parser (`.aitask-scripts/monitor/concern_parser.py`) accepts a closed,
    measured marker-glyph set `_MARKER_GLYPHS = "-•"`.
  - It applies a **one-glyph-per-block** rule. The block's glyph is that of
    its first row that *yields an item*, from `_yield_table`: a back-to-front
    iterative table, where "yields" means one-row or a probe-mode split
    rejoin. Only rows in that glyph start items.
  - A wider, **report-only** `_MARKER_LIKE` drives `unrecovered_markers`, so a
    marker in an unmeasured glyph, or in the off-block glyph, is reported
    rather than silently swallowed.
  - The split-marker rejoin stops at block-glyph item starts. In probe mode it
    also stops at opposite-glyph rows that yield an item.
  - There are no consumer code changes: minimonitor, monitor and
    monitor_shared all go through the parser's public functions. Forwarding
    stays canonical (`- [p | r] body`).
  - Spec: `.claude/skills/aitask-shadow/concern-format.md` records the Codex
    glyph rewrite, the accepted set, the one-glyph rule and its inherited
    same-glyph limit, the report-only diagnostic, and the split-join known gap.
  - Fixture `tests/fixtures/codex_shadow_bullet_capture.txt` holds the 4
    verbatim rows of the live block head (`E2 80 A2` bytes); none of the other
    project's prose is in it.
  - Tests: 25 new parser cases (`TestCodexBulletMarkers`, and two in
    `TestSplitMarkerJoin`), plus consumer wiring tests in
    `test_minimonitor_concern_action.py` (picker and auto-offer) and
    `test_monitor_concern_action.py` (picker).
- **Deviations from plan:**
  - The plan's single closed-set widening proved insufficient. Five review
    rounds (CR1–CR5 above) added the one-glyph-per-block rule, glyph selection
    from the first row that *yields* an item, the probe boundary on
    opposite-glyph items (one-row or split), and an iterative table replacing
    a recursion that overflowed at deep-capture size.
  - CR6 added a user requirement to the `codex_alternate_screen_block_capture`
    follow-up spec.
- **Issues encountered:**
  - Every review finding was confirmed against snapshots of each prior
    revision (old, v1–v5 in the scratchpad). Each new guard fails on exactly
    the revision it targets.
  - Probe mutants pin both halves of the stop rule.
  - The live re-check of pane `%263`: the pane had moved to a newer round
    whose opening fence was off the alternate screen (head-truncated). With
    the fence re-attached, its 3 real `•` items parsed with trailers.
- **Key decisions:**
  - Consumer-side fix, with only measured glyphs accepted.
  - The diagnostic is wider than the grammar but never steers parsing or
    removes body text.
  - A quotation in the block's *own* glyph at a wrap boundary stays the
    inherited producer-owned hazard; it is pinned by a test, not "fixed".
  - The alternate-screen viewport problem is spawned as an "after" follow-up
    (Step 8d), so it is deliberately not listed below.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/concern_parser.py:_join_split_marker` — a split
    rejoin whose unclosed bracket is followed, within the envelope, by a
    marker-looking row in a non-accepted glyph (`◦ [high | next] …`) swallows
    that row into the region and never reports it. This predates t1892 and is
    identical with a dash first marker. It is pinned by
    `test_split_join_consumes_a_marker_looking_row_known_gap`. Changing the
    recovery must keep `test_punctuation_led_region_fragment_is_still_rejoined`
    passing.
