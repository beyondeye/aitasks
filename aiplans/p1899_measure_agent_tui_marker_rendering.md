---
Task: t1899_measure_agent_tui_marker_rendering.md
Base branch: main
Output branch: main
---

# t1899 — Measure opencode's concern-marker rendering (agy deferred to t835)

## Context

t1892 made the concern parser accept a closed, **measured** set of item-marker
glyphs: `_MARKER_GLYPHS = "-•"` in `.aitask-scripts/monitor/concern_parser.py:171`.
`-` is canonical and `•` is Codex's rewrite (codex-cli 0.160.0). The opencode and
agy shadow renderers were never measured, so whether their blocks parse is still
an open question.

**Scope decided during planning:**
- **opencode 1.18.32**: measure it live through the production shadow path.
- **agy 1.2.17**: not measured. `ait codeagent` supports only
  claudecode/codex/opencode (`Unknown agent: 'agy'`), so agy cannot run as a
  shadow at all. agy support is t835 (Ready, not started). The user chose to
  skip agy, record it as not applicable, and send t835 a note so the measurement
  happens when agy becomes a shadow agent.

The production code changes only if opencode rewrites the marker.

## Step 1 — Live measurement (opencode)

Everything runs in a **dedicated tmux session `t1899m`** on the user's server.
Teardown is `tmux kill-session -t t1899m` only, never `kill-server`. Scratch
output goes to the session scratchpad (`$SP`).

1. **Followed pane.** Run
   `tmux new-session -d -s t1899m -x 220 -y 60 -c "$ROOT"`. This pane runs
   `cat aiplans/p1899_measure_agent_tui_marker_rendering.md; exec sleep infinity`.
   It stands in for the followed agent, with a plan on screen. The shadow also
   gets `PLAN_FILE` from `aitask_shadow_context.sh 1899`.
2. **Shadow pane, mirroring `spawn_shadow()`** (`monitor_core.py:3761`):
   - Get the launch command with
     `./ait codeagent --agent-string opencode/openai_gpt_5_4 invoke shadow <followed> 1899 --dry-run`
     and strip the `DRY_RUN:` prefix. `openai_gpt_5_4` is chosen because it is
     the opencode model with a verified pick score and OpenAI OAuth is
     configured. The renderer does not depend on the model.
   - Split it to the right of the followed pane at `shadow_pane_width` 60
     (`project_config.yaml`):
     `tmux split-window -h -l 60 -t <followed> -c "$ROOT" -P -F '#{pane_id}' "<cmd>"`.
   - Stamp the binding:
     `tmux set-option -p -t <shadow> @aitask_shadow_target <followed>`.
3. **Trigger a plan review.** Once the shadow is idle, run
   `tmux send-keys -t <shadow> -l '>pc'` and then `Enter`. A Monitor until-loop
   waits until the turn has ended: the capture shows the `===END-CONCERNS===`
   close fence, **or** it has been unchanged for 30 s. The idle condition is
   there because a renderer that damages the close fence must not leave the
   loop waiting forever. Neither condition means the sample is sufficient; see
   1.6. A hard timeout (10 min) means the controlled sample, 1.7.
4. **Capture through the production path:**
   `./.aitask-scripts/aitask_shadow_capture.sh --deep --any-pane <shadow> > $SP/opencode_cap.txt`.
5. **Inspect the bytes:**
   - `grep -n` for `===AITASK-CONCERNS===`, `Round:` and `===END-CONCERNS===`.
     Check that both fences and the header survive byte-for-byte.
   - Run `cat -A` and `od -c` on every marker row and record the exact glyph
     bytes.
   - **Source control (renderer vs. producer):** run `opencode session list`
     and `opencode export <sid>` to get the assistant's raw markdown. Confirm the
     producer emitted `- [`. Only a difference between the raw text and the
     capture counts as a renderer rewrite.
   - Run the parser on the capture with a `python3` snippet that puts
     `.aitask-scripts/monitor` on `sys.path`. Compare the counts from
     `parse_concerns`, `has_concern_block` and `unrecovered_markers` with the
     number of marker rows in the raw source.
6. **Sufficient evidence (the condition for accepting *any* measurement
   result, success or failure).** This only says whether the sample can tell
   us anything. It does **not** require the rendering to be correct. Both of
   these must hold:
   - **(a) Non-empty canonical source.** The raw source block (`opencode export`)
     contains the open fence, the `Round:` header, **≥1 canonical marker row**
     (`- [p | r] body`) and the close fence.
   - **(b) Corresponding capture coverage.** Every raw-source element (open
     fence, `Round:`, each marker row, close fence) is matched to the capture
     rows where it was rendered. Elements are anchored by **content, not by
     syntax**: each marker row by its item body's first ~30 characters, `Round:`
     by its timestamp, and each fence by its position between the anchored
     neighbours (prose before it, `Round:` or the last item after it). This
     anchoring is what lets a damaged fence or a missing marker still be
     located and measured.

   **Truncation and renderer damage are distinct outcomes:**
   - **Capture truncation** (insufficient evidence, not a renderer fact). An
     anchor's rows are missing because they lie beyond the captured viewport.
     The block runs off the top or bottom edge of the capture, or the pane
     content scrolled; opencode is an alternate-screen TUI, so `--deep` buys
     no scrollback. Retry **once**: enlarge the window with
     `tmux resize-window -t t1899m -y 120` and re-capture, or use the shorter
     controlled sample. If coverage still fails, the evidence is insufficient.
   - **Demonstrated renderer damage** (a sufficient measurement). The anchors
     are all inside the capture, the surrounding rows are present, and an
     element's bytes differ from the raw source: a fence rewritten or dropped,
     `Round:` altered, a marker glyph removed or replaced.

   A legitimate `>pc` review can emit a metadata-only clean block with zero
   concerns. It fails (a): it has a close fence but **no marker bytes**, so it
   proves nothing about markers and must never be read as "clean".
7. **Controlled sample.** Run this when the live shadow produced no block (tool,
   auth or model failure), and also when the live block has zero items:
   - Launch opencode in a new pane in the same session with
     `opencode -m openai/gpt-5.4 --prompt "<reply with exactly this markdown, not in a code block: a canonical 3-item block, one item long enough to wrap>"`.
   - Run steps 4–6 on it. The sufficient-evidence check applies to it as well.
   - Record which route produced the accepted sample (live shadow or
     controlled) in the plan notes and in the doc sentence.
   - If **neither** route yields sufficient evidence, the result is
     **inconclusive**. Go to Step 2 branch E. Do not claim that opencode is
     either clean or broken.
8. Tear down: Ctrl-C each opencode pane, then `tmux kill-session -t t1899m`.

## Step 2 — Act on the measurement (exactly one branch)

**Classify in two stages.** Evidence decides whether we can conclude anything;
rendering decides what we conclude.

1. **Evidence gate.** Did Step 1.6 hold for at least one route?
   - No → **E**.
   - Yes → stage 2. Every branch A–C is reachable from here.
2. **Rendering comparison.** Compare each anchored element's rendered bytes
   with the raw source.
   - **Boundaries:** are both fences and `Round:` byte-identical to the
     source?
   - **Markers:** what does each marker row's `- ` render as? It can stay
     `-`, become `•`, become another single non-word non-space glyph G, or
     become something no glyph can represent (removed, a word character,
     several glyphs, or inconsistent across rows).

   | boundaries | markers | branch |
   |---|---|---|
   | intact | `-` | **A** |
   | intact | `•` (already accepted) | **A2** |
   | intact | new single glyph G | **B** |
   | any damage, or markers not representable as one accepted glyph | — | **C** |

**Success gate (A, A2, B only).** Run it **after** the branch's code change, so
B is checked with G already in `_MARKER_GLYPHS`. Every raw-source item must
parse: `len(parse_concerns) == raw marker rows`, `has_concern_block` is true,
and `unrecovered_markers == []`.
- If the gate fails even though the boundaries are intact and the glyph is
  accepted, the parser mishandles a correctly rendered block. That is the
  **only** case recorded as a parser defect (Final Notes "Upstream defects",
  offered in Step 8b).
- Rendering loss is never called a parser defect: that is branch C, a
  renderer-compatibility finding.

**A. Clean.** The boundaries are intact and the markers stay `-`. This is the
expected case. The success gate applies.
- `.claude/skills/aitask-shadow/concern-format.md`, "Accepted marker glyphs"
  (around line 110): add a sentence that opencode was **measured clean**. Name
  the renderer, the version, the method (live shadow `>pc`, `--deep` capture)
  and t1899. Say that agy was **not measured** because it is not yet a
  supported shadow agent (t835), so its rendering is still open.
- `concern_parser.py`, the comment block above `_MARKER_GLYPHS`
  (lines 155–170): add one line saying that opencode 1.18.32 was measured and
  keeps `-` (t1899). The set itself is unchanged.
- **Real-bytes fixture:** create `tests/fixtures/opencode_shadow_dash_capture.txt`
  holding only the verbatim block-head rows (open fence, `Round:`, blank line,
  first marker row or rows), copied with `sed -n 'a,bp'`. Include no
  project prose beyond the block head.
- **Test** `TestOpencodeDashMarkers` in `tests/test_concern_parser.py`, placed
  next to `TestCodexBulletMarkers`:
  - the raw bytes contain `- [` and no `\xe2\x80\xa2 [`;
  - `parse_concerns` on the head gives the expected first item;
  - `has_concern_block` is true for the completed block;
  - `unrecovered_markers` returns `[]`.
  This keeps the measured claim pinned in the tree.

**A2. Rewrite to an already-accepted glyph.** opencode renders the producer's
`- ` as `•` (U+2022), which `_MARKER_GLYPHS` already accepts.
- Leave the **accepted set unchanged**.
- Record the measured bytes (`E2 80 A2`) in `concern-format.md`: opencode
  rewrites the marker the same way Codex does, measured in t1899.
- Add one line to the `_MARKER_GLYPHS` comment saying that opencode 1.18.32
  also renders `•`.
- Fixture `tests/fixtures/opencode_shadow_bullet_capture.txt` with the real
  bytes.
- Tests: turn `TestCodexBulletMarkers` into a mixin parameterised by fixture
  path and expected glyph bytes (as in B), and add an opencode subclass.
- The success gate applies, with no code change before it.
- Also record that agy is unmeasured, as in A.

**B. New glyph G** (one non-word, non-space character that is not already in
`_MARKER_GLYPHS`).
- Add G to `_MARKER_GLYPHS`, with a comment line naming the renderer, the
  version and t1899.
- Update the module docstring (lines 31–35), which currently names only `•`.
- `concern-format.md`:
  - add G to the accepted set and record the observation;
  - change the two-glyph wording ("the other accepted glyph") to
    "another accepted glyph".
- Fixture `tests/fixtures/opencode_shadow_<name>_capture.txt` with the real
  bytes.
- Tests: turn `TestCodexBulletMarkers` into a mixin parameterised by fixture
  path and expected glyph bytes. Run it once for Codex and once for opencode,
  so the seven existing cases cover both renderers. If G is `◦` or `*`, give
  `test_unmeasured_glyph_is_reported_not_parsed` different unmeasured glyphs.
- Leave the one-glyph-per-block rule and its `_yield_table` / `_block_glyph`
  tests unchanged, and check that they pass with three glyphs.
- Run the success gate **after** G is added.
- Also record that agy is unmeasured, as in A.

**C. Demonstrated renderer damage.** The evidence is sufficient and the
anchored rows are inside the capture, but a fence or `Round:` is rewritten or
dropped, or the markers cannot be represented by one accepted glyph (removed,
a word character, several glyphs, or inconsistent across rows).
- Do **not** change the grammar. No success gate runs: this is the measured
  failure outcome.
- In `concern-format.md`, record the damage as a renderer-compatibility fact:
  each damaged element with its raw-vs-rendered bytes, and the opencode
  version. This is not a parser defect.
- Save the anchored raw-vs-rendered evidence in the plan's Final Notes.
- Offer a follow-up task for renderer compatibility. Do not fix it here.
- If the boundaries are damaged **and** the markers are a new single glyph G,
  still choose C and do not add G. The block cannot parse whatever the marker
  is, and the follow-up owns the whole compatibility question.

**E. Inconclusive (insufficient evidence).** Neither route met Step 1.6: there
was no non-empty canonical source block, or capture coverage still failed after
the one truncation retry. Renderer damage is **never** E.
- Change nothing in the parser and add no fixture.
- In `concern-format.md`, record that an opencode measurement was attempted in
  t1899 and was inconclusive, giving the reason (for example "zero-item block
  and controlled sample failed: <cause>"). The open question stays open
  explicitly.
- Report the outcome to the user at Step 8 so they can decide whether to retry
  or spawn a follow-up.

## Step 3 — Note to t835 (agy)

Send the note to **t835_7** (manual verification for agy support), which is
the task that will run agy live:

```bash
./ait note 835_7 --from 1899 --file - <<'EOF'
When agy runs as a shadow, measure how its TUI renders concern-block item
markers. Capture a live `>pc` block via
`aitask_shadow_capture.sh --deep --any-pane <pane>`, check the marker bytes and
that both fences and `Round:` survive, and run
parse_concerns / unrecovered_markers on it. If agy rewrites `- `, add the glyph
to concern_parser._MARKER_GLYPHS with a real-bytes fixture, per
concern-format.md "Accepted marker glyphs". t1899 measured only opencode,
because agy was not yet a supported shadow agent.
EOF
```

This note is task data. It is committed by the note helper, not with the code.

## Verification

- `python3 -m pytest tests/test_concern_parser.py tests/test_concern_dimensions.py tests/test_concern_picker_modal.py tests/test_minimonitor_concern_action.py tests/test_monitor_concern_action.py -q`.
  Use the venv's pytest, or `unittest` if pytest is unavailable.
- `bash tests/test_skill_render_aitask_shadow.sh`, because concern-format.md is
  a shadow sub-procedure and is copied into rendered variants.
- Branches A, A2 and B: re-run the Step 1.5 parser snippet against
  `$SP/opencode_cap.txt` after any parser change. It must pass the Step 2
  success gate. Branches C and E have no success gate; their verification is
  the recorded raw-vs-rendered evidence.
- Commit only the named code paths. The working tree carries another session's
  uncommitted shadow edits (`SKILL.md.j2`, `plan-decisions.md`), so those must
  stay untouched.

## Step 9 reference

Post-implementation follows the standard task-workflow Step 9: no merge
(current branch), the gate orchestrator runs `risk_evaluated`, then archival and
push.

## Risk

### Code-health risk: low
- In branch B, widening `_MARKER_GLYPHS` changes a load-bearing parser. The
  change is one character, and the one-glyph-per-block rule plus the full
  existing parser suite guard it. Branch A changes only a comment.
  · severity: low · → mitigation: none (covered by the existing parser test suite)

### Goal-achievement risk: low
- One live sample (one opencode version, one model, width 60) stands for "the
  opencode renderer". A later opencode release could change rendering. Any
  unmeasured rewrite is still *reported* by `unrecovered_markers` rather than
  lost silently, so the remaining exposure is a visible warning.
  · severity: low · → mitigation: none (existing reporting path)
- A false "clean" reading, either because the model put the block inside a code
  fence or because a zero-item review left no marker bytes to measure. The
  method rules out both: the Step 1.5 raw-source comparison
  (`opencode export`), and the Step 1.6 sufficient-evidence rule with its
  controlled-sample fallback and an explicit inconclusive branch E. Step 2
  separates evidence from success: renderer damage (C), capture truncation (E)
  and a parser defect (the success gate failing on an intact block) each get
  their own label. · severity: low · → mitigation: none (in-method control)

## Post-Review Changes

### Change Request 1 (2026-10-06 23:09)
- **Requested by user:** Three verified review findings on concern-format.md.
  1. The version was misattributed. OpenCode auto-updated mid-session; both
     samples are 1.18.34, not 1.18.32. Correct the doc and the t835_7 note.
  2. "Silent" was unconditional. A manual `c` reaches the uncertified-round
     warning and the raw-block view.
  3. "Not supported" and "no workaround" overreached what was measured.
- **Changes made:**
  1. Version: confirmed via the session export's `version: 1.18.34` for both
     sessions. The `1.18.32` strings in the live export come from this plan's
     text, which the shadow read. Corrected the doc and appended a correction
     note to t835_7.
  2. Silent: confirmed in minimonitor_app.py (no-concern branch, about line
     4880) and monitor_app.py (about lines 3350–3398). The doc now separates
     the silent automatic paths from the manual `c` warning and raw view.
  3. Scope: narrowed the claim to "shadows launch and review, but concern
     items cannot be parsed or forwarded". Replaced "no workaround" with what
     was actually tested (backslash escaping fails; nothing else was tried).
- **Files affected:** .claude/skills/aitask-shadow/concern-format.md;
  t835_7 note (task data).

## Final Implementation Notes
- **Actual work done:**
  - Measured the opencode concern-block rendering live, outcome **branch C
    (demonstrated renderer damage)**.
  - Live route: an opencode shadow in a dedicated `t1899m` session on the
    `ait` tmux server. It was launched with the production
    `ait codeagent invoke shadow … --dry-run` command, stamped with
    `@aitask_shadow_target`, and given a `>pc` request. The block was captured
    with `aitask_shadow_capture.sh --deep --any-pane`.
  - Both routes were compared with the raw message text from
    `opencode export`.
  - Evidence was sufficient on both routes: a canonical non-empty source
    block (live: 1 item, no code fence; controlled: 3 items), and every
    anchor located in the capture.
  - Only the doc changed: `concern-format.md` gained a "Measured renderers"
    section. The parser grammar is unchanged and no fixture was added
    (branch C).
  - Advisory notes went to t835_7 (agy): one, plus a version correction.
- **Measured facts (OpenCode 1.18.34, both samples):**
  - The `-` glyph, `===AITASK-CONCERNS===`, the `Round:` header and
    `===END-CONCERNS===` survive. The close fence is rendered with +2 spaces
    of list-continuation indent, which the parser tolerates.
  - The renderer strips `[`/`]` from **every** bracket span, list items and
    paragraphs alike.
    - Live raw: `- [medium | Sample formatting] Step 1.6 requires …`.
      Rendered: `- medium | Sample formatting Step 1.6 requires an`.
    - Controlled rendered: `- high | region one First body.`,
      `- low Region-less body.` and `Plain bracket text in a paragraph`.
      `\[escaped brackets\]` rendered with its backslashes kept.
  - Parser on the live capture:
    - `parse_concerns` gives 0 items;
    - `has_concern_block` is False;
    - `unrecovered_markers` is `[]`;
    - `parse_block_meta` gives round 1;
    - `is_metadata_only_block` is False.
  - So the automatic paths are silent. A manual `c` in either TUI reaches
    `uncertified_round_block_msg` and the raw-block view.
- **Deviations from plan:**
  - **Model:** `openai/gpt-5.4` is rejected for a ChatGPT-account login
    ("not supported when using Codex with a ChatGPT account"). The shadow was
    relaunched with `opencode/openai_gpt_6_astra` through the same production
    command. The renderer does not depend on the model.
  - **Controlled sample:** it was also run although the live block had an
    item, to characterize the bracket rule (paragraph text, the region-less
    marker, escaping) for the follow-up.
  - **tmux server:** commands use `tmux -L ait` explicitly. A PreToolUse hook
    refuses unnamed-server `kill-pane`.
  - **Version:** OpenCode auto-updated from 1.18.32 (the planning-time
    `--version`) to 1.18.34 before the first measured session. The doc and
    notes say 1.18.34; see Change Request 1.
- **Issues encountered:**
  - The controlled pane was wide enough for opencode's sidebar (`LSP`) to
    share rows with the block. That made `parse_block_meta` return None for
    that capture; cutting the sidebar column gives round 1. Shadow panes
    (60 columns) are too narrow for the sidebar, so the finding is
    unaffected.
  - A concurrent session (Codex inline-launch work) edited another hunk of
    `concern-format.md` (about line 406). Only this task's hunk was
    committed, through a temporary index built from HEAD.
- **Key decisions:**
  - No grammar change. No glyph addition can repair bracket stripping, and
    accepting bracketless `- p | r body` rows would break the collision guard
    unless it is redesigned. That design belongs to a follow-up task.
  - agy was skipped by user decision (it is not a supported shadow agent;
    t835 is pending), with notes left on t835_7.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/concern_parser.py:_MARKER_LIKE` — concern items
    from opencode shadows (1.18.34) are not parsed or forwarded.
    - Cause: opencode's markdown renderer strips the `[…]` brackets, so items
      render as `- p | r body`.
    - Effect: `parse_concerns` and `has_concern_block` find nothing, so the
      auto-offer never fires.
    - The report-only `_MARKER_LIKE` needs a `[`, so `unrecovered_markers`
      is blind to it too.
    - Only the manual `c` path warns (uncertified round, raw view).
