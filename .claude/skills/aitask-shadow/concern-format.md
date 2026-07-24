# The shadow concern-block format

The **single source of truth** for the structured concern block the shadow agent
emits and minimonitor parses. Read this when editing the shadow plan-review
sub-procedures (the producer), `.aitask-scripts/monitor/concern_parser.py` (the
parser), or the minimonitor concern-picker UI (the consumer). Part of the t1037
concern-picker feature.

The block lets the user **selectively forward** a shadow agent's plan concerns to
the followed code-agent (tick a subset → clipboard → paste) instead of retyping
them. It is **additive** — the shadow still prints its human-readable list; the
block is an extra machine-parseable copy for pick-and-forward.

## The format

The block is bracketed by two sentinel lines — an opening `===AITASK-CONCERNS===`
line and a closing `===END-CONCERNS===` line (those two exact literals) — with one
concern per line between them. The concern lines themselves look like:

```
- [high | Step 7 ownership guard] The guard re-runs aitask_pick_own.sh which
  double-commits when the lock was already held.
- [medium | parser module] Multi-block accumulation is undefined when the
  shadow re-issues concerns.
```

The sentinels are named inline (not shown wrapping the items above) on purpose:
the shadow reads this doc at runtime, so a contiguous `open → items → close`
example here could be captured into the shadow pane and mis-forwarded by
minimonitor's picker as if it were real concerns (t1123). See **Staleness** and
the parser-safety guard in `tests/test_concern_parser.py`.

### Fences

- Opening: `===AITASK-CONCERNS===` — Closing: `===END-CONCERNS===`.
- ASCII so they round-trip through tmux/terminal capture without escape damage,
  and do **not** collide with markdown ```` ``` ```` code fences common in agent
  output.

### Concern markers

- One concern per line of the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY**. This is the
  wrap-collision guard: `tmux capture-pane` returns *visually wrapped* lines, so
  a long body is split across capture lines — but tmux never prefixes a
  continuation line with `- `. Requiring the dash means a wrapped body line,
  even one whose text contains bracket-looking (`[high | x] …`) or
  key-value-looking (`priority=high …`) substrings, can never be misread as a
  new concern. The producer MUST emit the dash on every concern line.
- `priority` ∈ {`high`, `medium`, `low`}, matched case-insensitively. An unknown
  value degrades to `low`; the item is **never dropped**.
- `region` is a free-text plan-region / axis label (which part of the plan the
  concern targets). Producers MUST keep it **short** (≤ ~30 chars — a
  `basename.ext:LINE` locus or an axis label, never a full repo path; full
  paths go in the body). This rule is the **primary defense** against the
  split-marker hazard below, and it remains in force: keeping the region short
  means the bracket never wraps at all, so the region stays exact and nothing
  relies on the parser's recovery envelope. **Every** producer listed under
  "Where it lives" states this rule inline, and
  `tests/test_concern_parser.py::TestProducerShortRegionRule` fails the build if
  one of them drops it or a new producer appears without it.

  **Split-marker hazard and its bounded recovery.** Some agent TUIs (e.g. Codex
  CLI's markdown renderer) hard-wrap long output rows with **literal newlines**
  that even the `-J` wrap-join cannot rejoin. A wrap landing *inside* the
  `[priority | region]` bracket leaves no parseable marker line, and the whole
  item used to be **silently dropped** (observed live with a 53-char full-path
  region at ~55 columns). The parser now rejoins such a split, within a
  **bounded envelope** (t1167):

  - The marker may span at most **3 rows** (the opening row plus
    `_MAX_MARKER_JOIN_ROWS = 2`). At ~55 columns that covers ~165 chars of
    marker — a region of ~150 chars, roughly 5× the 30-char rule above.
  - A split wider than that is **still dropped**. This is the accepted,
    documented limit, not an oversight — hence the producer rule stays primary.
  - Across a join, `priority` and `body` are reconstructed **exactly**;
    `region` is **best-effort**. A capture cannot distinguish "the renderer
    consumed a space here" from "the token continues here", so the parser
    treats a fragment ending in `-` or `/` as an intra-token break (exact for
    paths, the only failure mode seen live) and restores a space otherwise. A
    *prose* region broken right after a spaced slash therefore loses that
    space. That is accepted: `region` is a display label rendered in the
    picker, never a key.
  - The recovery cannot swallow a following concern: the lookahead commits only
    on success and stops at any row that itself begins a marker.
- `body` is free text. A wrapped continuation line (any non-blank line between
  the fences that is **not** a marker) is appended, space-joined, to the current
  concern's body.

### Capture-join contract

The parser space-joins each non-marker continuation line onto the current
concern's body. That is correct **only** for agent-emitted, word-boundary line
breaks. Raw `tmux capture-pane` (without `-J`) splits a long logical line
*mid-word* at the pane edge, which space-join would corrupt. Therefore the
capture handed to the parser **must be wrap-joined** — capture with
`tmux capture-pane -J` (or otherwise rejoin soft-wrapped rows) so the only
newlines the parser sees are real, agent-emitted breaks. The minimonitor capture
path (t1037_4) owns this; if it routes through `aitask_shadow_capture.sh`, that
helper must join wrapped lines.

### Capture-window contract

A pane capture is a bounded *window*, so the block can also be lost by being
older than the window rather than by being malformed. Two rules follow:

- Minimonitor captures the shadow pane at **plan-review depth** (`--deep`,
  `SHADOW_PLAN_CAPTURE_LINES`, default 400). What it must find is plan-review
  output — the human-readable list plus this fully-framed block — and at the
  narrow widths a shadow pane runs at, the ordinary 200-line depth can start
  inside the block.
- When the window still starts *inside* a block, both parser entry points key
  off the last opening fence and so report nothing. `block_head_truncated(text)`
  detects that shape (a closing fence with **no** opening fence anywhere in the
  capture) and the UI reports it as a **truncated block**, never as "no
  concerns". It is a detector only: the text above an orphan closing fence is
  untrusted, so it is never parsed into forwardable concerns — the explicit
  picker hotkey re-captures once with a much deeper window instead.

### Multi-block policy

When several blocks are present in the capture, **the last block wins** — a
re-issued review supersedes an earlier one. Only the most recent block is
parsed.

## Trigger vs. action contract

The parser exposes two entry points with deliberately different strictness; both
scope every fence check to the **last** opening fence (so an older block's
closing fence cannot stand in for a newer, still-streaming block):

| Entry point | Used by | Closing fence | Rationale |
|-------------|---------|---------------|-----------|
| `parse_concerns(text)` | the **explicit** user action (picker hotkey) | tolerated absent — parses the newest block to EOF | the user asked for it; scrollback may have truncated the close |
| `has_concern_block(text)` | the **auto-offer** trigger | **required** after the last opening fence, plus ≥1 parsed concern | do not offer the picker for an incomplete, empty, or malformed block |

**Producers must emit the closing fence** so the strict auto-offer fires.

## Where it lives

- **Producer:** the `.claude/skills/aitask-shadow/` plan-review sub-procedures
  that emit concern lists — `plan-challenge.md`, `impl-challenge.md`,
  `plan-assumptions.md`, `plan-diagnose-errors.md`. These live **only** in the
  Claude tree; the `.agents/` and `.opencode/` shadow trees carry a `SKILL.md`
  wrapper only (no mirrored sub-procedure files).
- **Parser:** `.aitask-scripts/monitor/concern_parser.py` — pure
  (`Concern`, `parse_concerns`, `has_concern_block`, `build_clipboard_payload`).
- **Consumer:** the minimonitor concern-picker modal + trigger wiring
  (`monitor_shared.py`, `minimonitor_app.py`).

## Staleness

The concern-forward surfaces also carry a **staleness** signal (t1104): when the
followed agent has moved on since the shadow produced these concerns, the auto-offer
notify appends a STALE marker and the picker modal shows a red banner, so a stale
block is not forwarded unaware. See the "Feedback freshness" section of
`aidocs/framework/shadow_agent.md` for the content-signature mechanism.

See `aidocs/framework/shadow_agent.md` for the shadow companion's overall pipeline.
