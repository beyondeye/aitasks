---
Task: t1908_opencode_shadow_concerns_lost_to_bracket_stripping.md
Base branch: main
Output branch: main
---

# t1908 — OpenCode shadow concerns lost to bracket stripping

## Context

t1899 measured OpenCode 1.18.34 live. Its markdown renderer strips `[`/`]` from
every bracket span, so a shadow's `- [medium | region] body` reaches the parser
as `- medium | region body`. The results:

- `parse_concerns` returns `[]` and `has_concern_block` is False, so nothing is
  auto-offered.
- The report-only `_MARKER_LIKE` needs a `[`, so `unrecovered_markers` is blind
  too.
- Only a manual `c` warns.

Once the brackets are gone, the region/body boundary is unrecoverable
(`- medium | Sample formatting Step 1.6 …`). A consumer-only grammar therefore
cannot restore `region`, so the fix has to be on the producer side.

User decision (planning): **diagnostic + producer fix**.
- Diagnostic: report bracketless `- <priority> …` rows, so the automatic path
  warns.
- Producer fix: an **OpenCode-only** rule, chosen at shadow render time via a
  Jinja `{% if agent == "opencode" %}` gate, that puts the marker bracket in a
  code span, `` - `[priority | region]` body ``.
- Gate: a live OpenCode measurement must confirm the code-span encoding before
  it ships.

Current-branch mode (profile `fast`). Concurrent sessions have uncommitted
hunks in `concern-format.md` (around line 406) and in several monitor files. My
commits must name only my paths. For `concern-format.md`, commit only my hunks,
through a temporary index built from HEAD, as t1899 did.

### Pre-phase (risk mitigations)

1. [codespan_render_probe] Run Step 1 to completion, including the recorded
   `od -c` bytes and the outcome row (O1–O5), **before** editing any producer
   doc or any parser grammar. Step 2 (the diagnostic) is encoding-independent
   and may proceed in parallel. Steps 3/3b/4 may start only on O1/O2. The
   recorded outcome goes into the plan's Final Implementation Notes.

## Step 1 — Controlled measurement of the code-span encoding (decides Steps 3–4)

Use a dedicated tmux session `t1908m` on the `ait` server (`tmux -L ait …`).
Tear it down with `kill-session -t t1908m` only, never `kill-server`. Scratch
files go to the session scratchpad.

1. Resolve the OpenCode launch and model from the production command:
   `./ait codeagent --agent-string opencode/openai_gpt_6_astra invoke shadow <pane> 1908 --dry-run`.
   This is the model t1899 got working. `openai/gpt-5.4` is rejected for this
   account. The renderer does not depend on the model.
2. Use a 60-column pane, which is the shadow width and too narrow for
   OpenCode's sidebar. Launch OpenCode with `--prompt` asking it to reply with
   exactly this markdown, not inside a code block:
   ```
   ===AITASK-CONCERNS===
   Round: 1 @ 2026-10-06T00:00:00Z
   - `[high | region one]` First body.
   - `[low]` Region-less body.
   - `[medium | parser.py:12]` A body long enough to wrap at sixty columns so a continuation row is observed too.
   - [medium | canonical] Canonical control row.
   ===END-CONCERNS===
   ```
3. Capture through the production path:
   `aitask_shadow_capture.sh --deep --any-pane <pane>`.
   Get the raw source with `opencode session list` + `opencode export <sid>`.
   Record `od -c` on every marker row.
4. **Usable-sample predicate**, checked before any outcome is decided. Both
   must hold:
   - (a) The exported raw text contains ≥1 code-spanned marker row verbatim.
   - (b) Every row's body anchor ("First body", "Region-less body",
     "continuation row", "Canonical control row") is found in the capture.

   Anchors are on body text, not on syntax the renderer may damage. If (b)
   fails, the cause is truncation: enlarge the window and re-capture once. If
   it still fails, the outcome is **inconclusive**.
5. **Outcomes**, by the code-span rows' rendered shape relative to what the
   parser accepts today:

   | # | Rendered code-span row | Action |
   |---|---|---|
   | O1 | `- [high \| region one] First body.` (backticks concealed, brackets kept) — **already accepted** | No grammar change. Ship the gate (Step 3) with a real-bytes fixture. |
   | O2 | ``- `[high \| region one]` First body.`` (backticks kept) — **new shape** | Add the paired-backtick tolerance (Step 3b) and ship the gate with a fixture. |
   | O3 | Brackets and `\|` survive in some other shape | Stop and show the bytes to the user. Never guess a grammar. |
   | O4 | Brackets still stripped inside the code span — **unrepresentable** | Do not ship the gate. Record the measured fact in `concern-format.md` and ship the diagnostic only (Step 2). Create a follow-up for other encodings. |
   | O5 | No usable sample — **inconclusive** | Ask the user. Never record it as "works". |

   The canonical control row must render as `- medium | canonical …`, which
   re-confirms t1899. If it does not, the renderer changed: stop and report.

## Step 2 — Diagnostic: report bracketless rows (unconditional)

`.aitask-scripts/monitor/concern_parser.py`:

- Add a report-only pattern next to `_MARKER_LIKE`:
  ```python
  # A marker whose brackets a renderer stripped (OpenCode 1.18.34, t1899):
  # `- medium | region body`, `- low body`. REPORT-ONLY, like _MARKER_LIKE:
  # without its brackets the region/body boundary is gone, so it is never
  # parsed — only named, so the automatic paths stop being silent (t1908).
  _BRACKETLESS_LIKE = re.compile(
      rf"^\s*{_ANY_GLYPH}\s+(?:high|medium|low)(?:\s*\||\s+\S)", re.IGNORECASE
  )
  ```
- In `_scan_items`, report bracketless rows **on both paths**:
  - **Fallback path.** Extend the report test to
    `if _MARKER_LIKE.match(line) or _BRACKETLESS_LIKE.match(line):`. The rows
    still fall through to continuation handling, exactly as today.
  - **Consumed-by-recovery path** (shadow review finding). A successful split
    rejoin (`_join_split_marker` returning `consumed > 1`) can swallow a
    bracketless row into the region. Reproduced: the rows `- [high | split` /
    `- medium | stripped Second body.` / `end] First body.` yield
    region `split - medium | stripped Second body. end`, with
    `unrecovered_markers == []`.

    After a successful join, scan the consumed rows
    `lines[i+1 : i+consumed]` and append every `_BRACKETLESS_LIKE` match to
    `unrecovered`. The rows stay consumed and the concern is still produced.
    This is reporting only:
    - item acceptance is not widened;
    - the join boundary does not move;
    - `_yield_table` / `_block_glyph` are untouched.

    The fabricated region stays a known join residual, but it is no longer
    silent.
- Update the module docstring, the `_scan_items` docstring (the unrecovered
  shapes and the accepted false positive) and the `unrecovered_markers`
  docstring.

The accepted false positive: a wrapped body row inside a block that begins
`- high …` / `- low …` is reported and stays in its concern's body. This is the
same class as the existing `<punctuation> [` false positive.

The effect on consumers needs no code change. Callers already branch on
`unrecovered_markers`:

- Minimonitor's `_maybe_offer_concerns` (`minimonitor_app.py:5050`) now warns
  once per pane with `unparsed_concerns_msg(n)`.
- A manual `c` in both TUIs takes the `lost` branch (unparsed warning + raw
  view) instead of the uncertified-round branch.

## Step 3 — Producer gate (O1/O2 only)

In each of the four producers — `.claude/skills/aitask-shadow/{plan-challenge,plan-assumptions,plan-diagnose-errors,impl-challenge}.md` — add one gated rule
immediately after `- One concern per line, in the form `- [priority | region] body`.`:

```
{% if agent == "opencode" -%}
- **OpenCode: put the marker in a code span.** OpenCode's renderer strips the
  `[` `]` of every bracket span, so a plain marker reaches minimonitor as
  `- high | region body` and the concern is lost. Write every concern line as
  ``- `[priority | region]` body`` (or ``- `[priority]` body``): the whole
  bracket, and nothing else, inside one pair of backticks. Every other rule
  here is unchanged.
{% endif -%}
```

- Wording is finalized against what Step 1 measured.
- The `-%}` on both tags keeps the claude and codex renders **byte-identical**
  to today. This is verified by diffing a pre-change and post-change render of
  each file for claude and codex.
- The gated line must not create a contiguous open→item→close example (the
  t1123 hazard). This is checked by the tests in Step 5.

### Step 3b — Grammar tolerance (O2 only)

Accept a paired code span around the bracket, using a conditional group so that
an unpaired backtick never matches. Put it in the shared tails, so the
accepted-glyph and any-glyph shapes stay in agreement:
- `_ITEM_TAIL`
- `_ITEM_NO_REGION_TAIL`
- `_MARKER_START` / `_MARKER_START_ANY` / `_MARKER_LIKE` (an optional
  `` ` `` before `[`)

The region class `[^\]]*` already stops at `]`. Then:

- Add an entry to the `_MARKER_GLYPHS`-style "measured, not guessed" comment.
- Update the `concern-format.md` "Accepted marker" text.
- Confirm that `concern_marker_line` / the clipboard payload stay **canonical**
  (no backticks are forwarded).

## Step 4 — Live confirmation through the production shadow path (O1/O2)

1. Re-render the OpenCode variant:
   `./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile fast --agent opencode --force`.
   Confirm with `grep` that the gated rule is in all four
   `.opencode/skills/aitask-shadow-fast-/` producers.
2. Mirror t1899 / `spawn_shadow()`:
   - The followed pane `cat`s a **deliberately flawed sample plan**, then runs
     `sleep infinity`. The plan is written to the scratchpad and is
     self-contained (a short "Context / Steps / Verification" plan), with
     ≥3 planted, independent defects so a nonempty review is near-certain:
     - a step that contradicts an earlier step;
     - a verification section that only checks the exit code;
     - a step that edits a shared file with no locking.
   - Point the shadow at it rather than at this plan, so the review cannot
     come back clean. Use `aitask_shadow_context.sh` with no task, or a plain
     `>pc`, whichever the dry-run launch supports. Confirm which during the
     step.
   - The shadow pane is split at 60 columns from the `--dry-run` command.
   - Run `set-option -p @aitask_shadow_target`, then send `>pc`.
   - Wait with a Monitor until-loop: the close fence appears, or the capture is
     unchanged for 30 s; hard timeout 10 min.
3. Capture with `--deep --any-pane` and compare against `opencode export`.
4. **Success gate — complete recovery, not "≥1 parsed".**

   **Source decoding (scratch script only, never the runtime grammar).** The
   exported source carries the producer's paired code span around every marker
   under **both** O1 and O2. Under O1 the runtime parser deliberately does not
   accept that form: an unchanged parser reads
   ``- `[high | region one]` First body.`` as zero concerns. So the script
   decodes the source before parsing.
   - **Step (i) — independent raw count.** Count the source block's marker
     rows (between the fences) with a script-local regex that accepts both the
     wrapped and the plain forms. With the backticks spelled out explicitly:

     ```
     ^\s*[-•]\s+(?:`\[(?:high|medium|low)\b[^\]`]*\]`|\[(?:high|medium|low)\b[^\]]*\])
     ```

     This count does not come from `parse_concerns`, so a shared parsing
     omission cannot hide a loss on both sides.
   - **Step (ii) — unwrap.** Unwrap **only** a validated paired span that
     encloses the marker at the start of a row. Match it with this regex,
     which consumes **both** backticks of the wrapper:

     ```
     ^(\s*[-•]\s+)`(\[[^\]`]*\])`
     ```

     Replace the match with `\1\2`. The body, including any code spans inside
     it, is left byte-intact.
   - **Self-check before use.** For every rewritten row, the script asserts
     that the text after the decoded `]` equals the text after the original
     ``]` `` byte-for-byte. As a fixed self-test it asserts that
     ``- `[high | region one]` First body.`` decodes to
     `- [high | region one] First body.`, with parsed body `First body.`.
   - **Step (iii) — parse.** Run `parse_concerns` / `parse_block_meta` on the
     decoded source.

   Then require all of the following:
   - **Source shape.** The source block has ≥1 item, and **every** source
     marker row is code-spanned (proves producer compliance).
   - **Same item count, three ways.** These three must be equal:
     - the raw source marker-row count from step (i);
     - `len(parse_concerns(decoded_source))`;
     - `len(parse_concerns(capture))`.

     Rows absent from the capture can never be reported, so a count match is
     what catches lost items. The independent raw count catches a parser
     omission that would hit both sides alike.
   - **Ordered field-by-field equality.** For every concern, in order, these
     fields must be equal: `priority`, `region`, `body`, `disposition`,
     `verdict`, `improves`, `worsens` and `effort`.
     - `body` is compared under a documented normalization `norm()`, applied
       to both sides: collapse whitespace runs, then delete exactly the
       inline-markdown delimiter characters Step 1 **measured** as concealed
       by the renderer (e.g. `` ` ``, `*`).
     - `norm()` is written down in the Final Implementation Notes with its
       measured basis.
     - Any difference beyond it fails the gate.
     - The trailer fields are compared un-normalized. Since they derive from
       the body, a renderer that damages a trailer fails here.
   - **Round metadata.** `parse_block_meta(capture) == parse_block_meta(source)`
     (round and reviewed_at).
   - **Strict trigger and report.** `has_concern_block(capture)` is True and
     `unrecovered_markers(capture) == []`.

   A small script in the scratchpad (not committed) prints a per-field diff
   table. Its output goes into the Final Implementation Notes.

   **Empty review is not evidence of compliance.** A metadata-only clean round
   is not a usable sample. Re-ask once with `>pc`, against the flawed plan. If
   the shadow still produces no items, record **producer compliance:
   inconclusive**. Never pass this gate from the controlled sample: the
   controlled prompt dictates the format, so it proves rendering, not that the
   shadow follows the gated rule among the canonical examples. Stop and ask the
   user before committing the producer gate.
5. If the model ignored the rule (raw source has plain brackets), strengthen
   the gated wording once and retry. If it still fails, report to the user
   rather than ship a rule shown not to be followed.
6. Tear down: Ctrl-C the panes, then `tmux -L ait kill-session -t t1908m`.

## Step 5 — Tests

`tests/test_concern_parser.py`:
- `TestBracketlessMarkersReported`:
  - Use a real-bytes fixture of a stripped OpenCode block,
    `tests/fixtures/opencode_shadow_bracketless_capture.txt`, taken from Step 1's
    canonical control row or from the live capture.
  - Assertions:
    - `parse_concerns == []`
    - `has_concern_block` False
    - `unrecovered_markers` names each stripped row (pipe and region-less forms)
  - Negative control: a canonical dash block whose continuation row begins
    `- high-level` (no whitespace after the word) is not reported.
  - `- high | x` outside any block is not reported (no block region).
  - **Consumed-by-recovery regression** (the review repro). Block rows:
    `- [high | split`, `- medium | stripped Second body.`, `end] First body.`.
    - Exactly one concern is produced (acceptance unchanged), with region
      `split - medium | stripped Second body. end`. This pins the known join
      residual.
    - `unrecovered_markers` contains `- medium | stripped Second body.`.
    - Without the consumed-row scan, this assertion fails. The mutant in the
      post-phase covers it.
- `TestOpencodeCodeSpanMarkers` (O1/O2):
  - Use the real-bytes fixture `tests/fixtures/opencode_shadow_codespan_capture.txt`.
  - It parses to the expected priority/region/body, and its clipboard
    payload is canonical.
  - O2 adds: an unpaired backtick does not match, and a dash-twin of the block
    parses identically.
- `TestRenderedShadowDocsKeepTheGuarantees`: add an OpenCode render
  (`--agent opencode`, `.opencode/skills/aitask-shadow-fast-/`) with the same
  "no rendered doc is parser-live" check. The OpenCode surface now diverges.

`tests/test_skill_render_aitask_shadow.sh`:
- Move `plan-assumptions`, `plan-challenge` and `plan-diagnose-errors` out of
  `PROC_FILES_INVARIANT` into a new `PROC_FILES_AGENT_GATED` array. Test 0
  inventory covers it.
- Their Test: claude and codex renders are byte-identical and profile-invariant.
  The OpenCode render equals a new golden,
  `tests/golden/procs/aitask-shadow/<f>-opencode.md`.
- impl-challenge (Test 1p): codex == claude; OpenCode matches a new
  `impl-challenge-<profile>-opencode.md` golden.
- New assertion: every OpenCode producer render contains the code-span rule;
  no claude or codex render contains it.
- Update the inventory comment ("impl-challenge is the only procedure carrying
  Jinja").

## Step 6 — Docs

`.claude/skills/aitask-shadow/concern-format.md` (my hunks only):

- Rewrite the "Measured renderers → OpenCode" bullet with:
  - the code-span encoding and the Step 1/4 measurement
  - the outcome
  - what the user sees now, i.e. the automatic path warns on bracketless rows
- In the "Trigger vs. action contract" `unrecovered_markers` row, add the
  bracketless shape.
- Note the OpenCode-only producer rule under "Concern markers".

Under O4, record only the measured failure and the diagnostic.

Run `./.aitask-scripts/aitask_skill_verify.sh` and regenerate goldens in the
same commit.

### Post-phase (risk mitigations)

1. [live_shadow_followthrough] After Steps 3–6 land in the working tree, run
   Step 4's production-path live confirmation against the **final** gated
   wording and grammar, not a draft. Use the flawed sample plan from Step 4.2.
   Record the full Step 4.4 success-gate results in the Final Implementation
   Notes:
   - source and parsed item counts
   - code-spanned source rows
   - the ordered per-field diff table and the `norm()` definition
   - the round metadata pair
   - `has_concern_block`
   - `unrecovered_markers`

   A failed gate blocks the commit of the producer gate. An inconclusive
   result (no nonempty production review) is not a pass either: stop and ask
   the user.
2. [collision_guard_regression_tests] Run these checks and confirm each one
   fails without the change it guards:
   - **O2 only — paired backticks.** In `tests/test_concern_parser.py`, assert
     that an unpaired backtick (``- `[high | r] body`` / ``- [high | r]` body``)
     yields no concern.
   - **O2 only — opposite-glyph quotation.** A code-spanned quotation row in
     the opposite glyph inside a dash block stays body text.
   - **O2 only — split marker.** A split code-span marker
     (``- `[high | long``, then `region]` body` on the next row) is rejoined
     or reported, never fabricated into two concerns.
   - **All outcomes — render identity.** Render each gated producer for claude
     and codex before and after the edit, and `cmp` the pairs byte-for-byte.
   - **Mutants for the diagnostic.** Two separate scratch copies of
     `concern_parser.py`, each imported by path; do not edit the shared
     worktree:
     - (a) The fallback-path `_BRACKETLESS_LIKE` test is removed. The
       stripped-fixture assertions fail.
     - (b) Only the consumed-rows scan is removed. Exactly the
       consumed-by-recovery regression fails.

     Each mutant gives a guard-specific signal.

## Verification

- `bash tests/test_skill_render_aitask_shadow.sh`
- `python3 -m pytest tests/test_concern_parser.py tests/test_minimonitor_concern_action.py -q`
  (or via unittest)
- `bash tests/run_all_python_tests.sh --test-dir tests`, reading only the last
  verdict line with `set -o pipefail`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `shellcheck` is not needed, since no shell scripts change except the test file.
- The Step 4 live success gate is the end-to-end proof.

## Step 9 — Post-Implementation

Archive via the task-workflow Step 9. Use a path-scoped commit:
`bug: Report bracketless OpenCode concern markers and code-span them at the producer (t1908)`.
For `concern-format.md`, commit through a temporary index containing only my
hunks.

## Risk

### Code-health risk: low
- (O2) The code-span tolerance changes a heavily hardened grammar and could weaken the collision guard or split-join boundary · severity: medium · → mitigation: inline post-phase collision_guard_regression_tests
- First per-agent Jinja gate in shadow procedures — a whitespace slip would perturb claude/codex renders, and it adds golden churn · severity: low · → mitigation: inline post-phase collision_guard_regression_tests
- Bracketless report false positive on a wrapped body row starting `- high …` (spurious warning only, nothing removed) · severity: low · → mitigation: TBD (accepted, documented)

### Goal-achievement risk: medium
- OpenCode may also mangle code spans (O4), so the producer fix cannot ship · severity: medium · → mitigation: inline pre-phase codespan_render_probe
- The OpenCode model may copy the canonical examples and ignore the gated rule · severity: medium · → mitigation: inline post-phase live_shadow_followthrough
- A partial live recovery (lost items, damaged bodies or trailers) could pass a weak gate · severity: medium · → mitigation: inline post-phase live_shadow_followthrough (complete-recovery gate, Step 4.4)
- A bracketless row consumed by a split rejoin would stay silent · severity: medium · → mitigation: Step 2 consumed-rows scan + regression test (collision_guard_regression_tests mutant b)

### Planned mitigations
- timing: pre-phase | name: codespan_render_probe | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: OpenCode mangles code spans (O4) | desc: Controlled OpenCode render measurement of the code-span marker before any producer/grammar edit
- timing: post-phase | name: live_shadow_followthrough | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: model ignores gated rule | desc: Production-path live OpenCode shadow >pc run against the final wording, with a success gate that blocks the commit
- timing: post-phase | name: collision_guard_regression_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: grammar collision guard / render perturbation | desc: Unpaired-backtick, opposite-glyph, split code-span tests plus a claude/codex render byte-identity check and a diagnostic mutant
