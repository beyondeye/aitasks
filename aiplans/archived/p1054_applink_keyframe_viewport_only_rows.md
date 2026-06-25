---
Task: t1054_applink_keyframe_viewport_only_rows.md
Worktree: (current branch — profile 'fast')
Branch: (current)
Base branch: main
---

# Plan: AppLink keyframes carry viewport-only rows (t1054)

## Context

AppLink streams tmux pane content to the mobile companion app. The wire spec
([`aidocs/applink/content_transport.md` §Row schema](aidocs/applink/content_transport.md))
is explicit: **`row_id 0` is the top of the visible viewport; scrollback rows
use NEGATIVE ids and are served only by the (future) history RPC.** Live
`keyframe`/`delta`/`append` frames must carry only the visible viewport.

Today they violate this. The applink monitor captures with
`tmux capture-pane -p -e -S -<capture_lines>` (`capture_lines=200`,
`monitor_core.py:1178-1182`), so `PaneSnapshot.content` is **~200 scrollback
rows + the ~24 visible rows**. In the push path
(`pusher.py:147` → `content.parse_snapshot`), every captured line is parsed and
numbered `0..223` with **`row_id 0 = oldest scrollback`**. The keyframe is then
emitted with the wire `rows` field = `dims[1]` (pane height ~24) but a
`full_rows` array of ~224 rows (`pusher.py:202-208`). `delta`/`append` inherit
the same scrollback-based row-id basis (their `row_sigs` baseline and
`detect_append`/`deltify` all derive from the same `parsed`).

**Second symptom (same root cause): cursor misalignment.** The cursor row comes
from `#{cursor_y}` (`monitor_core.py:1226`), which is **viewport-relative**
(`0 = top of visible`). It was being sent alongside scrollback-based row_ids, so
it pointed at the wrong absolute row. Trimming to the viewport realigns the
cursor for free.

This is the server-side root cause of the mobile rendering bug that
`aitasks_mobile` t14_10 fixed defensively (the client now renders against both
buggy and spec-compliant servers; this is the real fix). Paired with the
`aitasks_mobile` t14_11 audit.

## Approach

Fix at the **single production parse site**, structurally. Everything the push
path emits derives from the one `parsed = content.parse_snapshot(snap.content)`
call (`pusher.py:147`): keyframe `full_rows`, the `new_sigs`/`row_sigs` delta
baseline, `deltify`, `detect_append`, and `build_osc8`. Trim *that* to the live
viewport and **all** frame types become viewport-only at once — no per-frame-type
patching, no fragile invariant to remember.

**Why not change the capture?** The `capture_lines=200` capture is shared: the
same `TmuxMonitor` instance drives idle/prompt change-detection (which benefits
from scrollback context) and the same monitor config feeds the `ait monitor`
TUI; the captured scrollback is also exactly what the future Stage-5 history RPC
(`content_transport.md §Scrollback`) will need. So we **keep capturing
scrollback** and trim only the *live* stream. Decision recorded per the task's
"decide whether to keep capturing scrollback" question: **keep capture, trim at
encode.**

**Viewport = the last `height` captured rows.** With `-S -<N>` and no `-E`, tmux
captures `[N scrollback rows … height visible rows]`; the visible viewport is the
trailing `height` rows. Renumbering them `0..height-1` makes `row_id 0` the top
of the visible area, exactly per spec. Robust under short scrollback (fresh pane
→ capture returns `≤ height + N` rows; trailing `height` still = viewport) and
under `total < height` (defensive: take what's there, number from 0).

### Changes

**1. `.aitask-scripts/applink/content.py` — `parse_snapshot` gains an optional
`viewport_height`:**

```python
def parse_snapshot(content: str, viewport_height: int | None = None):
    """...
    When ``viewport_height`` is given, only the **live viewport** (the trailing
    ``viewport_height`` rows of the capture) is parsed and the rows are
    renumbered ``0..viewport_height-1`` — ``row_id 0`` == top of the visible
    viewport, per content_transport.md §Row schema. Scrollback rows above the
    viewport are dropped from live frames (history is served separately via the
    history RPC with negative row_ids). ``None`` (default) parses every captured
    row 0.. (legacy/full behavior, used by ``snapshot_to_rows`` and its tests).
    """
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]  # drop the trailing empty cell from a final newline
    if viewport_height is not None:
        lines = lines[-viewport_height:] if viewport_height > 0 else []
    parsed = []
    for row_id, line in enumerate(lines):   # enumerate from 0 == viewport top
        spans, urls = parse_sgr_line(line)
        parsed.append((row_id, spans, urls))
    return parsed
```

Note the `viewport_height > 0` guard: `lines[-0:]` is `lines[:]` (all rows), so a
zero-height pane must short-circuit to `[]`.

`snapshot_to_rows(content)` stays unchanged (no height → full parse), preserving
its "byte-for-byte identical" test contract. Its docstring gets a one-line
pointer that the **live push path must pass `viewport_height`**, so a future
caller can't silently reintroduce the bug.

**2. `.aitask-scripts/applink/pusher.py` — pass the viewport height at the call
site (`pusher.py:147`):**

```python
parsed = content.parse_snapshot(snap.content, dims[1])   # dims = (width, height)
```

`dims` is already computed at `pusher.py:122` (`dims = (pane.width, pane.height)`).
No other line in `_push_pane` changes — `new_sigs`, `deltify`, `detect_append`,
`build_osc8`, and the keyframe `full_rows` all read from `parsed` and become
viewport-only automatically. The keyframe's wire `rows` field (`dims[1]`) now
matches the `full_rows` length.

### Tests

**3. `tests/test_applink_content.sh` — unit tests for the new param:**
- `parse_snapshot(scrollback+viewport, height)` returns exactly `height` rows,
  renumbered `0..height-1`, content == the trailing rows (the viewport).
- `row_id 0` maps to the **first viewport** row, not the oldest scrollback row.
- `viewport_height=0` → `[]`; `viewport_height` greater than the captured row
  count → all rows, numbered from 0 (defensive).
- `parse_snapshot(content)` with no height is unchanged (regression guard for
  the `snapshot_to_rows` path).

**4. `tests/test_applink_pusher.sh` — integration test through `_push_pane`:**
- Build a `FakeSnap` whose `content` has scrollback above the viewport, e.g.
  `FakePane("%1", height=3)` with content `"s0\ns1\ns2\nv0\nv1\nv2\n"` (3
  scrollback + 3 viewport).
- Force a pass; decode the binary keyframe and assert: wire `rows` field == 3,
  `full_rows` has exactly 3 rows with `row_id` `[0,1,2]` and text
  `["v0","v1","v2"]` (the viewport), **not** the scrollback `s*`.
- Assert the existing equal-rows scenarios (content rows == height) are
  unaffected (they already pass — trailing-`height` of an `H`-row snapshot is the
  whole snapshot).

## Risk

### Code-health risk: low
- Additive optional parameter with a backward-compatible default; exactly one
  production call-site change; all downstream frame types derive from the single
  trimmed `parsed`, so there is no scattered/fragile invariant. Existing tests
  (content rows == height) remain green. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Root cause confirmed end-to-end (capture → parse → encode) and the
  "viewport = trailing `height` rows" mapping is robust across tmux capture edge
  cases (short scrollback, fresh pane, blank rows). The mobile client already
  renders correctly against the fixed server (t14_10). The only behavior not
  covered by unit/integration tests is a live end-to-end render against a real
  paired device — handled by the standard manual-verification follow-up offer
  (Step 8c), not a dedicated mitigation task. · severity: low · → mitigation: none

No before/after risk-mitigation tasks are warranted (`risk_mitigations_planned =
false`).

## Verification

1. **Unit:** `bash tests/test_applink_content.sh` (and the existing
   `snapshot_to_rows` regression checks pass).
2. **Integration:** `bash tests/test_applink_pusher.sh` — the new scrollback
   keyframe test asserts viewport-only `full_rows` + matching `rows` count.
3. **Lint:** `shellcheck` is N/A (Python edits); confirm `python -c "import
   content"` parses.
4. **Manual (offered at Step 8c):** pair a device via `ait applink`, scroll an
   agent pane to build scrollback, subscribe, and confirm the mobile keyframe
   renders only the visible viewport with the cursor on the correct row.

## Post-Implementation (Step 9)

Single-task flow on the current branch: Step 8 review → commit code
(`bug: ...(t1054)`) + plan separately → Step 9 archive via
`aitask_archive.sh 1054` → push. No worktree/branch cleanup (current-branch
profile).

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, at the single structural
  point. `content.parse_snapshot` gained an optional `viewport_height`
  (`content.py`); when given it trims to the trailing `height` capture rows and
  renumbers them `0..height-1`. `pusher._push_pane` now calls
  `parse_snapshot(snap.content, dims[1])` — every downstream live frame
  (keyframe `full_rows`, the delta `row_sigs` baseline, `deltify`,
  `detect_append`, `build_osc8`) became viewport-only with no further edits.
  `snapshot_to_rows` left unchanged; its docstring now warns the live push path
  must pass `viewport_height` so a future caller can't reintroduce the bug.
- **Deviations from plan:** None.
- **Issues encountered:** None. Existing equal-rows test scenarios
  (content rows == height) stayed green because the trailing-`height` slice of an
  `H`-row snapshot is the whole snapshot.
- **Key decisions:** Kept the `capture_lines=200` scrollback capture (shared with
  change/idle detection, the `ait monitor` TUI, and the future history RPC) and
  trimmed only the live stream — recorded answer to the task's "keep capturing
  scrollback?" question. Cursor alignment (`#{cursor_y}` is viewport-relative)
  was corrected for free by the same trim. The history-RPC consumer of the
  retained scrollback is already tracked as **t1057** (cross-references t1054);
  no new task created.
- **Upstream defects identified:** None. (The scrollback-based row-id basis was
  the in-scope bug itself, not a separate pre-existing defect elsewhere.)
- **Tests:** `test_applink_content.sh` (84 ✓, +viewport-trim unit cases) and
  `test_applink_pusher.sh` (67 ✓, +scrollback keyframe integration case decoding
  real wire bytes); `test_applink_router.sh` (140 ✓), headless and smoke suites
  green.
