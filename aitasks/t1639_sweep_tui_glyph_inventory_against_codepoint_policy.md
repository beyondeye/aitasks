---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tui, aitask_board, aitask_monitormini, ait_brainstorm]
followup_kind: risk_mitigation
created_at: 2026-08-30 13:59
updated_at: 2026-08-30 13:59
---

## Problem

t1638 moved the multi-select mark onto codepoints covered by every supported
Nerd Font and established `.aitask-scripts/lib/mark_glyphs.py` as the authority,
with an executable admissibility policy: a glyph is only usable if **every**
family in `mark_glyphs.SUPPORTED_FONTS` covers it **and** no emoji font claims
the codepoint.

That policy currently governs only the two mark glyphs. The rest of the TUI
glyph inventory was never measured against it, and the measurement that was done
found confirmed violations already shipping.

## Confirmed violations (measured during t1638, not assumed)

- **`★` U+2605 / `☆` U+2606** — `monitor/monitor_shared.py:207-209`, the
  prioritised-agent mark. Covered by **neither** JetBrainsMono NF nor
  CaskaydiaMono NF, so both always resolve by system font fallback. t1638
  deliberately left them alone: unlike `☑` they are **not** emoji-capable, so
  they still honour the requested foreground and are not visibly broken today
  (they fall back to Noto Sans Math). This task is where that deferral is
  re-evaluated.
- **`✔` U+2714** — `board/aitask_board.py:3541,3596`, the by-trail "landed"
  entries. This is the **same defect t1638 fixed**, shipping today: covered by
  neither font and claimed by Noto Color Emoji, so on a machine whose fontconfig
  ranks the emoji font highly it paints its own colours and disappears on a dark
  background. Highest-value item here.
- **`⚠` U+26A0** — ~10 sites across board / monitor / applink. Uncovered by
  CaskaydiaMono NF and emoji-claimed.
- **`⇄` U+21C4** — `TRAIL_CLASSIFICATION_GLYPHS`. Covered by neither font, but
  not emoji-claimed, so it falls back and stays visible. Low risk.

## Scope

Run the t1638 oracle over the whole TUI glyph inventory and decide, per glyph,
whether to move it onto a covered codepoint or to record an explicit accepted
deferral. Reuse the existing machinery rather than rebuilding it:

- `tests/tools/regen_font_coverage.py` already parses each font's `cmap` table
  directly (no `fontTools`, and deliberately **not** `fc-list`, which is
  family-agnostic and was measurably wrong on U+2714 during t1638). Extend the
  codepoint set it records rather than writing a second scanner.
- `tests/test_mark_glyphs_single_source.py::CodepointPolicyTests` already holds
  the emoji-capability oracle and the per-family coverage assertions.

Decide deliberately whether the policy becomes repo-wide or stays opt-in per
glyph vocabulary — a blanket sweep is **not** safe. `lib/workflow_phase.py:121`
matches `[☐☑]` to detect **Claude Code's own** AskUserQuestion chip in captured
pane text; it detects a foreign glyph rather than rendering ours, and rewriting
it silently breaks question detection in both monitors and the shadow flow. That
trap is pinned by `QuestionDetectorPinTests` — read it before scanning anything.

Any `★`/`☆` replacement must preserve the distinction
`monitor_shared.format_mark_glyph` documents: the pair is deliberately **not**
the selection mark's vocabulary or its colour, because it sits two columns from
the agent's `●` which `_state_color` paints yellow for IDLE. Note also that
`▲`/`△` — the obvious filled/hollow replacement — collides with
`FOLLOWUP_KINDS["risk_mitigation"]`, which `monitor_shared` renders in its own
sibling picker.

## Acceptance criteria

- [ ] Every TUI glyph is measured against both halves of the policy, and the
      result is recorded in the coverage manifest rather than in prose.
- [ ] `✔` at `aitask_board.py:3541,3596` is fixed or has a recorded, reasoned
      deferral — it is a live instance of the t1638 defect.
- [ ] The `★`/`☆` decision is made explicitly: replaced, or deferred again with
      the reason stated in `monitor_shared` beside the constants.
- [ ] A replacement is only chosen after checking it against the covered,
      non-emoji, single-cell set — and against glyphs already in use on the same
      screen.
- [ ] `lib/workflow_phase.py`'s question-chip codepoints are untouched, and the
      guard that pins them still passes.
