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

### Round header

- The **first line inside the fences** is `Round: <N> @ <timestamp>` — e.g.
  `Round: 2 @ 2026-08-11T14:03:27Z`. `N` is the 1-based review round within the
  shadow's conversation — a positive integer, at most 9 digits
  (`1`..`999999999`, no zero-padding; the parser bounds the grammar so an
  absurd digit run reads as a malformed header rather than raising, and no
  compliant producer ever approaches the cap). The timestamp is UTC ISO-8601
  at **seconds** resolution, shell-sourced by the producer
  (`date -u +%Y-%m-%dT%H:%M:%SZ`), never estimated. Producers honor an
  externally named round ("recheck round N") and self-count only otherwise.
- **Placement is load-bearing.** The header occupies the one slot the item
  scanner already drops (a non-marker line before the first item), which is
  what makes it parser-safe: `parse_concerns`, `has_concern_block` and
  `unrecovered_markers` are byte-identical with and without it. Placed **after
  any item** it is wrap-joined into that item's body — the round is silently
  lost and the body is corrupted — and it must never itself begin with `- [`
  (that shape is recorded as an unrecovered marker). `parse_block_meta`
  consults only the first non-blank line of the region.
- **Back-compat:** a header-free block is a pre-header block —
  `parse_block_meta` returns `None` and every consumer behaves exactly as
  before the header existed.
- **Metadata-only clean-round block:** a review that finds zero concerns (or
  whose concerns were all suppressed) still emits the two fences with only the
  round header between them — the machine-readable record that the round
  completed clean, so round numbering advances on clean rounds too.
  `has_concern_block` stays **False** for it (no items ⇒ no auto-offer), by
  design. Consumers certify it with the strict `is_metadata_only_block`
  (complete fence + exactly the header): a still-streaming header-only block
  or a header followed by stray dropped prose must **not** be treated as a
  clean round.
- **Three consumer roles:** display (the picker's context line and the toast
  name the round); the auto-offer dedup lift (minimonitor keys its repeat-block
  suppression on `(round, reviewed_at, payload)`, so a repeat round re-raising
  identical concerns re-offers instead of staying silent); and the t1448
  freshness key — which is the `(round, reviewed_at)` **pair**, never the round
  alone (a restarted shadow counts from 1 again).
- The header intentionally changes `concern_block_signature` — a round bump
  re-hashes the monitor's freshness badge even when the items are unchanged.

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
  concern targets). It is **mandatory and never empty**: it is the row's only
  title in the picker, so an omitted one renders as a visible `(no region)`
  placeholder rather than a blank. Producers MUST keep it **short** (≤ ~30 chars — a
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

### The region-less marker

A marker that omits the `| region` half entirely — `- [medium] body` — parses
with an **empty region** rather than being lost. Without that tolerance the row
is neither an item (no `|`) nor a split-marker candidate (it *does* contain
`]`), so it fell through to continuation handling and was silently appended to
the previous concern's body — or dropped outright when it was the block's first
item (t1274).

The priority here is matched against the **closed** `high|medium|low`
vocabulary, not `\w+` as in the full marker. The `|` separator is what makes the
full marker's shape unmistakable; without it, a permissive class would let an
ordinary wrapped body line (`- [see below] …`) start a spurious concern and
break the collision-hardening guarantee above. This is a *tolerance*, not a
licence: the producer rule that `region` is mandatory still stands.

### Derived fields: `disposition` and `verdict`

The shadow's **implementation** review ends each body with a prose trailer —
`Disposition: blocking.` / `Disposition: follow-up.` / `Disposition:
informational.`, and in Advanced/Deep a `Verified: CONFIRMED.` /
`Verified: PLAUSIBLE.` verdict. The parser derives `Concern.disposition` and
`Concern.verdict` from it. They are **derived fields, not marker fields**: the
line format is unchanged, so every block emitted before this existed still
parses, and widening the `[priority | region]` bracket — the documented t1167
drop hazard — was deliberately avoided.

Three rules make the derivation safe:

- **Terminal anchor.** The trailer is matched only as a *run of sentences ending
  the body*. A body that quotes or discusses `Disposition: informational.`
  mid-prose is neither classified by it nor has that prose removed. Sentence
  order within the run is free.
- **`body` stays canonical.** It is exactly what the producer emitted, trailer
  included, because `build_clipboard_payload` re-renders it verbatim — stripping
  the trailer would delete the disposition from what the followed agent
  receives. Display surfaces call `Concern.display_body()`, which removes
  exactly the matched span. The clipboard path must always use `body`.
- **Unspecified is not informational.** No trailer (the three plan-review
  producers emit none) ⇒ `disposition == ""`, which `needs_addressing()` treats
  as needing attention — the safe direction.

The picker consumes this by splitting its list into **Needs addressing** and
**Informational** sections and dimming the latter. A block whose concerns all
land in one partition shows no headers.

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

The parser exposes three entry points with deliberately different strictness; all
scope every fence check to the **last** opening fence (so an older block's
closing fence cannot stand in for a newer, still-streaming block):

| Entry point | Used by | Closing fence | Rationale |
|-------------|---------|---------------|-----------|
| `parse_concerns(text)` | the **explicit** user action (picker hotkey) | tolerated absent — parses the newest block to EOF | the user asked for it; scrollback may have truncated the close |
| `has_concern_block(text)` | the **auto-offer** trigger | **required** after the last opening fence, plus ≥1 parsed concern | do not offer the picker for an incomplete, empty, or malformed block |
| `concern_block_signature(raw)` | the **freshness** trigger (has this block changed?) | **required** | a reflow-stable digest, compared for equality only |
| `unrecovered_markers(text)` | the **loss report** shown beside the picked list | tolerated absent — same region as `parse_concerns` | marker-looking lines that yielded no concern |

`unrecovered_markers` is what makes the remaining losses **visible**. A
continuation line can never begin `- ` followed by `[` (the collision-hardening
invariant), so any such line inside the block that produced no concern is by
definition a marker the parser could not recover — an over-bound split, a
malformed bracket, an unclosed one. The picker shows the count so the user knows
the list is short of what the shadow emitted, instead of the block degrading
silently. It is a **report, not a recovery**: widening
`_MAX_MARKER_JOIN_ROWS` remains the accepted t1167 limit.

The degenerate case — a **complete block whose markers are *all* malformed** —
needs its own handling, because it reaches neither surface above: nothing parses,
so `has_concern_block` is false (no auto-offer) and the picker hotkey has no rows
to show a banner beside. Both paths therefore consult `unrecovered_markers`
before reporting emptiness, and warn that the block was emitted but none of it is
forwardable. Reporting "no concerns" there would be a false all-clear — the same
class of silent false negative as the clipped-head case above.

The first two take a **wrap-joined, escape-free** capture (`capture-pane -p -J`,
as `aitask_shadow_capture.sh` produces). `concern_block_signature` is the odd one
out: it reads the **raw refresh-tick capture** (`-p -e`, *not* wrap-joined), which
is what lets a monitor tell "this block changed" for many agents at no extra tmux
cost. That makes it a **trigger only** — its input has soft-wrapped bodies split
mid-word, so it must never be turned into forwardable concerns. A caller acting on
a change re-captures with `-J` and goes through `parse_concerns`. It also returns
nothing on a pane narrower than `_SENTINEL_SAFE_COLS` (24), where the fence itself
can wrap; such panes need the authoritative capture instead.

**Producers must emit the closing fence** so the strict auto-offer fires.

## Rejected-concern suppression

The concern picker lets the user **reject** a concern — "do not show me this one
again next round". Rejections are persisted per task by
`.aitask-scripts/aitask_shadow_rejected.sh` at
`.aitask-shadow/<task_id>/rejected.md` (bare task id mirroring `.aitask-gates/`,
git-ignored, never committed, pruned at archival), and every producer consults
them before emitting its block.

**Matching is semantic, and the shadow agent performs it — not the parser.**
Bodies are re-worded between review rounds, so no consumer-side hash can serve
as a cross-round identity: `Concern` carries no id, and `region` is a display
label and never a key (see above). A rejected concern must therefore be
recognised by *meaning*, which only the producing agent can do.

**The reader contract.** A producer runs
`./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and branches on
exactly three outcomes:

| Outcome | Meaning |
|---------|---------|
| the single line `NO_REJECTIONS` | nothing is rejected — proceed normally |
| a printed body | the user's previously-rejected concerns |
| anything else | the store could not be consulted |

"Anything else" covers a **non-zero exit** (a malformed task id exits `2`),
empty output, and output matching neither shape above. It is **not** the same as
"nothing was rejected": the producer emits every fresh concern and states that
rejection suppression was skipped. The helper's own "all resolution outcomes
exit 0" note scopes to *resolution* outcomes — missing, drained, or populated
store — and says nothing about a bad argument, so a producer must never decide
this on the exit status alone.

**Fail-open.** When the agent is unsure whether a fresh concern matches a
rejected one it **keeps** the concern and says why. That is the safe direction,
and the same one `needs_addressing()` takes for an unspecified disposition.
Suppression is also never silent: whenever N ≥ 1 concerns were dropped the
producer reports `Suppressed N previously-rejected concern(s).` in the prose
before the block.

**The store can never become a block.** `add` accepts only lines beginning
`- [`, so a fence can never be stored. `list` output echoed into the shadow pane
therefore carries item lines with neither sentinel, and cannot be parsed as a
forwardable block.

Every producer listed under "Where it lives" states this rule inline **twice** —
as a bolded pre-emit directive at the head of its emit step, and as an entry in
its parser-rules list — and
`tests/test_concern_parser.py::TestProducerRejectionSuppressionRule` fails the
build if one drops either copy. Both placements are pinned because the directive
is the high-attention one: a guard that could not tell them apart would stay
green after it was deleted. The duplication is deliberate for the same reason
the short-region rule is duplicated: these are prompt files read at runtime, and
an extra file read is a rule the agent may skip.

The **round-header rule** follows the same two-placement pattern in every
producer (bolded emit directive + rules-list bullet), guarded by
`TestProducerRoundHeaderRule` — including its negative half: no producer may
retain the pre-round "omit the block when clean" wording, which the
metadata-only clean-round block replaced.

## Where it lives

- **Producer:** the `.claude/skills/aitask-shadow/` plan-review sub-procedures
  that emit concern lists — `plan-challenge.md`, `impl-challenge.md`,
  `plan-assumptions.md`, `plan-diagnose-errors.md`. These live **only** in the
  Claude tree; the `.agents/` and `.opencode/` shadow trees carry a `SKILL.md`
  wrapper only (no mirrored sub-procedure files).
- **Parser:** `.aitask-scripts/monitor/concern_parser.py` — pure (`Concern`,
  `BlockMeta`, `parse_concerns`, `parse_block_meta`, `is_metadata_only_block`,
  `has_invalid_round_header`, `has_concern_block`, `concern_block_signature`,
  `contains_any_concern_block`, `block_head_truncated`, `unrecovered_markers`,
  `block_region`, `needs_addressing`, `DISPOSITIONS`,
  `build_clipboard_payload`).
- **Consumer:** the concern-picker modal + trigger wiring (`monitor_shared.py`,
  `minimonitor_app.py`). The shadow lookup, capture and staleness helpers behind
  them are shared in `monitor_core.py`, so the full monitor uses one
  implementation rather than a copy.

## Staleness

The concern-forward surfaces also carry a **staleness** signal (t1104): when the
followed agent has moved on since the shadow produced these concerns, the auto-offer
notify appends a STALE marker and the picker modal shows a red banner, so a stale
block is not forwarded unaware. See the "Feedback freshness" section of
`aidocs/framework/shadow_agent.md` for the mechanism — it compares **timestamps**
(when the shadow last read the agent vs when the agent last changed), which is a
different question from `concern_block_signature` above (has *this block's text*
changed). Do not conflate the two.

See `aidocs/framework/shadow_agent.md` for the shadow companion's overall pipeline.
