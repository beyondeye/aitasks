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
  · severity: medium · → mitigation: codex_alternate_screen_block_capture
- Only `•` is measured. opencode and agy were not measured. A different rewrite
  would still not parse, though it would now be *reported*.
  · severity: low · → mitigation: measure_agent_tui_marker_rendering

### Planned mitigations
- timing: post-phase | name: pin_marker_like_residual | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: wider _MARKER_LIKE diagnostic false-positive (code-health) | desc: Pin the report-only false positive of a punctuation-led continuation row with a test and one spec sentence
- timing: after | name: codex_alternate_screen_block_capture | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: viewport-truncated Codex block parsed to EOF with chrome in the last concern (goal-achievement) | desc: Codex shadow panes run on the alternate screen (no tmux scrollback): define the capture strategy and how an unclosed block is presented on `c` so pane chrome is never forwarded as concern body
- timing: after | name: measure_agent_tui_marker_rendering | type: chore | priority: low | effort: low | inline_risk: medium | added_complexity: medium | addresses: only the Codex glyph is measured (goal-achievement) | desc: Measure live whether opencode and agy shadow panes rewrite the `- ` concern marker; add any measured glyph to concern_parser._MARKER_GLYPHS and concern-format.md

Reassessment (post-inline, single pass): the inline post-phase only adds a test
and a spec sentence, so both levels are unchanged (code-health low,
goal-achievement medium). The `codex_alternate_screen_block_capture` follow-up is
created by Step 8d. It must **not** also be listed under "Upstream defects
identified", because that would offer it a second time at Step 8b.

## Post-implementation
Step 9 of task-workflow: current-branch mode, so there is no merge. The steps
are build verification / gates (`risk_evaluated`), then archival with
`aitask_archive.sh 1892`, then push with `./ait git push`.
