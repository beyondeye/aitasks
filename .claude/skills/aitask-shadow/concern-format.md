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
  clean round. What consumers do **instead** of certifying is load-bearing:
  both TUIs warn (`uncertified_round_block_msg`) and open the raw block view,
  because reporting such a block as "no concerns" would hide output the shadow
  did emit. A block whose `Round:` line fails the grammar outright
  (`has_invalid_round_header`) takes the same path, with no round to name.
- **Four consumer roles:** display (the picker's context line and the toast
  name the round); the auto-offer dedup lift (minimonitor keys its repeat-block
  suppression on `(round, reviewed_at, payload)`, so a repeat round re-raising
  identical concerns re-offers instead of staying silent); the t1448
  freshness key — which is the `(round, reviewed_at)` **pair**, never the round
  alone (a restarted shadow counts from 1 again); and the minimonitor
  auto-recheck loop, which derives the round it names in its injected
  `refetch and recheck round N` prompt as
  `parse_block_meta(previous block).round + 1`, so the round is
  machine-anchored rather than self-counted whenever a previous block exists.
- The header intentionally changes `concern_block_signature` — a round bump
  re-hashes the monitor's freshness badge even when the items are unchanged.

### Prose around the block that is not parsed

Two things every producer now emits are **prose for the human, not part of
this format**: the `In plain words:` line that ends each item of the
human-readable findings list, and the "Where this is heading" preamble that
opens every round after the first. Both live **before** the block, neither is
ever a `- [` line or inside the fences, and the parser never sees them — the
block body stays byte-identical to what the picker forwards. Owning spec:
`.claude/skills/aitask-shadow/round-preamble.md` (audience rule, the six
preamble headings and their fixed verdict rule, and the per-round snapshot
protocol behind the preamble's comparisons).

### Concern markers

- One concern per line of the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY**. This is the
  wrap-collision guard: `tmux capture-pane` returns *visually wrapped* lines, so
  a long body is split across capture lines — but tmux never prefixes a
  continuation line with `- `. Requiring the dash means a wrapped body line,
  even one whose text contains bracket-looking (`[high | x] …`) or
  key-value-looking (`priority=high …`) substrings, can never be misread as a
  new concern. The producer MUST emit the dash on every concern line.
- **Accepted marker glyphs (consumer tolerance).** The parser accepts a closed
  set of item-marker glyphs: `-` (canonical) and `•` (U+2022 BULLET). The
  bullet is there because Codex CLI's markdown renderer **replaces** the
  list-marker glyph before tmux ever sees the row: the producer's `- ` arrives
  as `• ` (observed on codex-cli 0.160.0, t1892), while the two ASCII fences and
  the `Round:` header survive intact. Without that tolerance no Codex shadow
  block can parse. The set is **measured, not guessed**: a glyph is added
  (`_MARKER_GLYPHS` in `concern_parser.py`) only after a renderer is observed
  emitting it. None of this relaxes the producer rule: producers still emit
  `- `.

  **One glyph per block.** A renderer rewrites every list item of a block the
  same way, so the block's marker glyph is the glyph of its **first marker row
  that actually yields an item**, and only rows carrying *that* glyph start
  items. A malformed leading row does not count: it cannot pick a glyph that
  would demote, or let a split rejoin swallow, the valid items after it. Its
  split-rejoin probe stops at every genuine next item, meaning a row in the
  candidate's own glyph, or an opposite-glyph row that itself yields an item
  (whether on one row or via its own bounded split rejoin), so it can never
  cross a later item to manufacture one. A non-parseable
  opposite-glyph fragment (`• [reference] body`) is not an item boundary and
  keeps rejoining into the region. That is what keeps the
  collision guard above intact once the bullet is accepted. A body may quote a
  marker, and when an agent's hard-wrap lands just before the quotation the row
  begins with it: `• [high | example] …` inside a dash-marked block, or
  `- [ … ]` inside a Codex block. Such a row is in the *other* glyph, so it
  stays body text, exactly as a dash-only parser treated a quoted bullet. A
  quotation in the block's **own** glyph at a wrap boundary is still
  indistinguishable from a real item. That is the collision hazard the format
  always had, and it is the producer's to avoid (a body row must never begin
  with the marker).

  A row carrying an unaccepted glyph, or the other accepted glyph, is not
  parsed but is reported (see the `unrecovered_markers` row under "Trigger vs.
  action contract"), so an unmeasured rewrite normally shows up as a warning
  instead of vanishing.

  **Measured renderers.**
  - **Codex CLI** rewrites the glyph to `•`, which is accepted (see above).
    It hard-wraps long bodies with literal newlines, but only at spaces
    (measured on codex-cli 0.160.0 at 60 columns: 72 breaks, none inside a
    token), so its bodies rejoin exactly.
  - **OpenCode (1.18.34): the producer code-spans the marker** (t1899
    measured the damage, t1908 the encoding).
    - **The damage.** OpenCode keeps the `-` glyph, both fences and the
      `Round:` header. But its markdown renderer strips the square brackets
      from **every** `[…]` span, list item or plain paragraph. So
      `- [medium | parser] body` arrives as `- medium | parser body`, and
      `- [low] body` arrives as `- low body`. The region/body boundary is gone
      with the brackets, so no parser grammar can recover such a row, and no
      glyph addition can repair it. A backslash-escaped `\[…\]` renders with
      its backslashes kept, so escaping does not help either.
    - **The encoding.** A code span survives. OpenCode conceals the backticks
      and keeps the brackets inside, so ``- `[high | region one]` body``
      renders as the canonical `- [high | region one] body` and parses with
      **no grammar change**. Every producer therefore carries one rule, gated
      on the `opencode` agent at render time, telling an OpenCode shadow to
      code-span each marker. The Claude and Codex renders do not contain it
      and are unchanged, and the forwarded payload stays canonical.
    - **How it was measured.** All samples were rendered by OpenCode 1.18.34
      (the session export's `version`), captured with
      `aitask_shadow_capture.sh --deep`, and compared with the assistant's
      raw text from `opencode export`.
      - A controlled sample of code-spanned rows, with a plain-bracket control
        row. The control row was stripped.
      - A live production shadow `>pc` review of a deliberately flawed plan.
        Its 4 source rows were all code-spanned, and 4 of 4 were recovered,
        with exact priority, region and round.
    - **Hard-wrapped bodies.** OpenCode draws every row itself, so a long body
      reaches the capture as separate rows that `-J` cannot rejoin, and it
      breaks *inside* tokens as well as at spaces. It breaks after:
      - an attached `-` (including between the two dashes of `--flag`);
      - `/`;
      - `(`;
      - a lone `.`;
      - `.` or `:` inside a token.

      Under a plain space-join a trailer break (`follow-` / `up`,
      `maintainability(` / `low)`) lost the whole trailer. The intra-token
      join rule (the `body` bullet below) removes that loss. It was measured
      on a known 8-item block rendered at 50, 60, 72 and 90 columns. At every
      width all 8 concerns parse their full trailer, against 0–5 of 8 before.
      At 72 and 90 columns every body is exact. What remains are the
      cosmetic residuals the `body` bullet lists: `history.` / `csv`,
      `https:` / `//` and a `--` split.
    - **What the user sees without the encoding.** A shadow that emits plain
      brackets (an older render, or a model ignoring the rule) yields no
      concern. `unrecovered_markers` reports every bracket-stripped row, so
      minimonitor's automatic path warns once ("could not be parsed — none
      are forwardable") and a manual `c` shows the same warning and the
      raw-block view.
    - **Minor.** The close fence picks up two spaces of list-continuation
      indent, which the parser tolerates.
  - **Antigravity CLI (`agy`)** is not measured. It is not yet a supported
    shadow agent.
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
  region at ~55 columns). The same renderer also **replaces the list-marker
  glyph** (`- ` → `• `, see "Accepted marker glyphs" above), which is the more
  fundamental breakage: it defeats every marker, not only a wrapped one. The
  recovery below therefore works with any accepted glyph. The parser now
  rejoins such a split, within a **bounded envelope** (t1167):

  - The marker may span at most **3 rows** (the opening row plus
    `_MAX_MARKER_JOIN_ROWS = 2`). At ~55 columns that covers ~165 chars of
    marker — a region of ~150 chars, roughly 5× the 30-char rule above.
  - A split wider than that is **still dropped**. This is the accepted,
    documented limit, not an oversight — hence the producer rule stays primary.
  - Across a join, `priority` and `body` are reconstructed **exactly**;
    `region` is **best-effort**. A capture cannot distinguish "the renderer
    consumed a space here" from "the token continues here", so the parser
    rejoins with the same intra-token rule it uses for bodies (see the `body`
    bullet below). A spaced slash (`foo / bar`) is therefore exact, while an
    absolute path broken right after its whitespace-preceded leading slash
    gains a space (`/` / `home/user` → `/ home/user`), because the two look
    identical from the broken row. That is accepted: `region` is a display
    label rendered in the picker, never a key.
  - The recovery cannot swallow a following item: the lookahead commits only
    on success, and it stops at any row that is itself an item **in its own
    glyph**, in any marker-looking glyph, accepted or not (`◦ [high | next] …`).
    That includes an item that needs its own split rejoin within the envelope
    (`◦ [high | next` / `region] …`). Stopping there leaves the unclosed
    bracket unrecovered, so it is reported, and the stopping row is reported
    too. If both follow an earlier concern they stay in its body, since nothing
    is removed (t1897). The lookahead does not stop at merely
    marker-*looking* rows. A region fragment that happens to begin with
    punctuation (`— [reference] …`, or an unclosed `— [ref …` that closes on
    the next row) is still a continuation of the bracket and keeps rejoining.
    The accepted residual is a region fragment that is itself item-shaped
    (`— [a | b] …`). It cannot be told apart from an item in another glyph,
    so it stops the join too and is reported rather than joined. A following
    item split wider than the envelope is outside the recovery bound described
    above.
- `body` is free text. A wrapped continuation line (any non-blank line between
  the fences that is **not** a marker) is appended to the current concern's
  body. The join adds **no space** when the row so far ends in an intra-token
  break, and one space otherwise. An intra-token break is one of these:
  - a `-` or `/` attached to a non-space character (`follow-` / `up`,
    `src/` / `lib`);
  - an opening `(` (`maintainability(` / `low)`);
  - a lone `.` preceded by whitespace or at the start (`in .` / `aitask-scripts`).

  A `-` or `/` preceded by whitespace is a spaced separator, so it keeps its
  space (`fix -` / `which`). The rule is a heuristic, because a capture cannot
  tell a consumed space from a continuing token. These residuals are accepted,
  and all are cosmetic; none occurs inside the trailer grammar:
  - an intra-token `.` or `:` gains a space (`history.` / `csv` →
    `history. csv`, `py:` / `415`);
  - a break between the dashes of `--flag` gains a space;
  - a suspended hyphen loses one (`pre-` / `and` → `pre-and`);
  - an absolute path broken right after its whitespace-preceded leading slash
    gains one (`in /` / `home/user` → `in / home/user`). It reads the same as
    a spaced separator (`foo /` / `bar`), and the parser chooses the separator.

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
- **Unspecified is not informational.** No trailer ⇒ `disposition == ""`, which
  `needs_addressing()` treats as needing attention — the safe direction. All
  four producers emit a disposition today; the plan-review three adopted it in
  t1636_3, so an unspecified disposition now means a block emitted before that
  or a trailer that failed to parse, not a producer that never had one.

The picker consumes this by splitting its list into **Needs addressing** and
**Informational** sections and dimming the latter. A block whose concerns all
land in one partition shows no headers.

### Derived fields: the impact vector (Improves / Worsens / Effort)

A concern is a **proposed delta in a shared quality space**, not a bare demand.
Alongside `Disposition:` and `Verified:`, the terminal trailer run carries a
signed **impact vector** — an improve side and a worsen side drawn from the
*same* closed dimension vocabulary — plus a separate effort scalar:

```
Improves: robustness(high), verification(medium). Worsens: simplicity(low). Effort: low.
```

Like `disposition` and `verdict`, these are **derived fields**: the
`[priority | region]` bracket is untouched, so every block emitted before they
existed still parses, and the t1167 drop hazard is not re-opened.

**The dimension vocabulary.** Closed and framework-semantic — the parser builds
its name alternation from this set, so a producer must not invent others. The
single source of truth is `.aitask-scripts/monitor/concern_dimensions.py`; the
table below mirrors it field for field, and `tests/test_concern_dimensions.py`
fails the build if the two drift. The order shown is canonical: producers
enumerate in it and the picker renders in it.

| dimension | label | rubric |
|---|---|---|
| `goal` | `goal` | the task's AC / the user's stated intent is delivered |
| `correctness` | `corr` | right behavior on reachable inputs |
| `robustness` | `robus` | stability under failure / concurrency / hostile input (includes security) |
| `performance` | `perf` | latency, throughput, resource cost |
| `verification` | `verif` | testability; proof the change works |
| `maintainability` | `maint` | readability, duplication, conventions; ease of safe change |
| `simplicity` | `simpl` | amount of mechanism; the classic worsen-side |

`maintainability` and `simplicity` are deliberately **separate**. Extracting a
shared helper improves maintainability while worsening simplicity; merged into
one "code health" scalar that trade would cancel itself out — and pricing added
mechanism is the entire reason the worsen side exists. The `label` column is the
short form the picker renders in its narrow layout; it is part of the contract
because that layout's width budget depends on it.

**Grammar.** Each of the three sentences is optional and their order within the
trailer run is free, exactly as for `Disposition:` and `Verified:`:

- `Improves: <entries>.` and `Worsens: <entries>.` — `<entries>` is a
  comma-separated list of `name` or `name(magnitude)`, where `name` is one of
  the closed dimensions above. `Worsens:` additionally accepts the literal
  `nothing`.
- `Effort: <magnitude>.`
- A sentence naming a dimension outside the vocabulary does **not** match. It is
  not silently dropped: it stays in the display body and in the payload
  forwarded to the followed agent, where a human sees it. A permissive name
  class is not an option — it would re-open the collision hazard the whole
  marker format rests on.
- Magnitudes are `high`, `medium` or `low`, matched case-insensitively. An
  unrecognised or omitted magnitude yields **unspecified**, rendered `?` — never
  `low`. The dimension itself is never dropped.

**Magnitudes are advisory; the dimensions are load-bearing.** Naming *which*
quality moves is the information the old bare severity scalar never carried.
Calibrating *how far* it moves is noisy, so a magnitude refines a concern and
never decides whether it is one. Degrading an unknown magnitude to `low` would
understate a cost on the worsen side, which is the unsafe direction here — hence
the unspecified state.

**The worsen side is mandatory, and "priced as nothing" is not "not priced".**
Every vector-bearing concern must price its own suggestion. `Worsens: nothing.`
is a *priced* empty set; an omitted `Worsens:` sentence is a different state,
and the parser distinguishes them. This is the anti-overengineering mechanism:
without it a concern is a pure demand with externalised costs, and accumulating
concerns silently over-engineers the solution. A concern that improves only
non-obligated dimensions at a simplicity cost self-identifies as a bad trade.

**`Effort:` is a separate one-time-cost scalar, never a vector dimension.**
Quality deltas are permanent properties of the codebase; effort is transient and
paid once. Mixing them corrupts both — a cheap fix and a durable improvement are
different facts, and the reader is choosing between them.

**Grounding the disposition in the vector.** The vector is what makes
`blocking` / `follow-up` / `informational` decidable rather than a feel:

- **blocking** — the improve side touches an *obligation dimension* for this
  task. `goal` and `correctness` are obligations categorically; `robustness` and
  `performance` become obligations only when the task's own AC or plan says so,
  which is a per-task judgement the producing agent makes against that task's
  text.
- **follow-up** — net-positive, but no obligation dimension is touched.
- **informational** — no proposed delta at all, or the point is already settled.

`impl-review-angles.md` remains the authoritative home of the disposition
rubric; this section only states how the vector grounds it.

**Priority is derived from the vector.** For a vector-bearing concern the marker
priority is `concern_dimensions.derive_priority(improves)` — the strongest known
magnitude on the improve side, with an absent, empty, or all-unspecified improve
side yielding `low`. Producers MUST emit a marker priority equal to it. On the
consumer side the derived value is authoritative: the picker badge shows it and
flags a disagreeing marker rather than silently reconciling the two. Concerns
carrying no vector keep their marker priority exactly as before.

### Capture-join contract

The parser rejoins each non-marker continuation line onto the current
concern's body with the intra-token rule from the `body` grammar bullet. That rule
is calibrated **only** for agent-emitted line breaks: a renderer's breaks fall
at spaces or after token punctuation. Raw `tmux capture-pane` (without `-J`) splits a long
logical line *mid-word* at the pane edge, wherever the column runs out, which
no join rule can reconstruct. Therefore the
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
- A capture depth only reaches older rows when the shadow pane keeps
  scrollback. An alternate-screen pane has `history_size=0`, so any depth
  returns the visible rows only. The framework therefore launches every Codex
  pane inline, shadows included (`-c tui.alternate_screen=never`, since
  codex-cli 0.160.0 defaults to the alternate screen). Its capture window is
  the pane's history plus the visible rows, and scrolling the Codex view does
  not change it.
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
| `contains_block_evidence(text)` | the **block-age applicability** test (is there a block to age?) | tolerated absent — and an orphan closing fence also counts | "no block" must stay distinct from "block of unknown age" |
| `unrecovered_markers(text)` | the **loss report** shown beside the picked list | tolerated absent — same region as `parse_concerns` | marker-looking lines that yielded no concern |

`unrecovered_markers` is what makes the remaining losses **visible**. A
continuation line can never begin `- ` followed by `[` (the collision-hardening
invariant), so any such line inside the block that produced no concern is by
definition a marker the parser could not recover — an over-bound split, a
malformed bracket, an unclosed one. A **bracket-stripped** row
(`- medium | region body`, `- low body`, any marker-looking glyph, closed
priority vocabulary) is reported too, including one that a successful split
rejoin consumed into its region: a renderer that removes the brackets
(OpenCode, see "Measured renderers") would otherwise leave the whole block
silent. Accepted false positive: a wrapped body row that begins `- high …` is
reported while staying in its concern's body. The picker shows the count so the user knows
the list is short of what the shadow emitted, instead of the block degrading
silently. It is a **report, not a recovery**: widening
`_MAX_MARKER_JOIN_ROWS` remains the accepted t1167 limit.

What it counts as marker-*looking* is deliberately wider than what the parser
accepts. Any row that begins with one punctuation glyph, whitespace and `[`
counts, including glyphs outside the accepted set (`* [`, `◦ [`, …) and the
accepted glyph that is not the block's own. So a renderer that rewrites the
marker to a glyph nobody has measured yet is **reported rather than silent**
(t1892; the report used to require the dash and was blind to exactly the Codex
rewrite). A split-marker rejoin never consumes such a row when it is an item in
its own glyph: the rejoin stops there, so the row is reported (see
"Split-marker hazard"). The wider shape is report-only in two senses:

- **It removes nothing.** A reported row that follows an item still stays in
  that item's body and is forwarded with it. That costs one accepted false
  positive: a genuine wrapped body row that happens to begin `<punctuation> [`
  draws a spurious warning, while its text is still correctly forwarded as body
  text.
- **It never steers parsing.** The split-marker recovery does not stop at a
  marker-looking row. It stops only at a row that is a whole item in its own
  glyph, or in the block's glyph. So a region fragment beginning with
  punctuation keeps rejoining.

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

The store also receives concerns the user **spun off** into their own draft
tasks (the picker's `t`), recorded with `--producer spinoff` rather than
`--producer picker`. Suppress them the same way: the concern is being tracked
elsewhere, so re-raising it is noise. Do **not** branch on the producer — `list`
output is deliberately producer-blind, because the entry records a judgement
about the concern, not about which round or key raised it.

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
  `BlockMeta`, `parse_concerns`, `parse_block_meta`, `parse_reviewed_at_epoch`,
  `is_metadata_only_block`, `has_invalid_round_header`, `has_concern_block`,
  `concern_block_signature`, `contains_any_concern_block`,
  `contains_block_evidence`, `block_head_truncated`, `unrecovered_markers`,
  `block_region`, `needs_addressing`, `DISPOSITIONS`,
  `build_clipboard_payload`).
  - `contains_block_evidence` vs `contains_any_concern_block` — **not
    interchangeable.** The first is the *runtime* applicability test for the
    block-age signal: is there a block here at all? It is true for a
    metadata-only clean round and for a head-truncated capture. The second
    requires at least one parsed **item** and exists for the *authoring-time*
    check that no shadow doc embeds a parser-live example. Using the second at
    runtime would classify a clean round as "no block".
  - `parse_reviewed_at_epoch` is the only place the header's timestamp becomes
    a *time*. It is strict — the documented shape and nothing else, verified by
    a canonical round-trip (plain `strptime` accepts `2026-8-1T1:2:3Z`) — and
    returns `None` rather than guessing, because a confident freshness verdict
    from malformed metadata is worse than no verdict.
- **Consumer:** the concern-picker modal + trigger wiring (`monitor_shared.py`,
  `minimonitor_app.py`). The shadow lookup, capture and staleness helpers behind
  them are shared in `monitor_core.py`, so the full monitor uses one
  implementation rather than a copy.

## Staleness — three signals, do not conflate them

The concern-forward surfaces carry a **staleness** signal so a stale block is not
forwarded unaware. There are **three** distinct questions behind it, and each is
answered by a different piece of code:

| signal | question | implementation |
|---|---|---|
| **block identity** | has *this block's text* changed? | `concern_block_signature` (above) |
| **read recency** | did the shadow *look* after the agent's last change? | `monitor_core.compute_shadow_staleness` (t1104) |
| **block age** | was this block *produced* after the agent's last change? | `monitor_core.compute_block_age_staleness` (t1493) |

Read recency and block age are joined by `monitor_core.combine_staleness`, which
is **fail-safe**: `True` wins, then `None` ("cannot tell"), then `False`. An
unknown therefore never *clears* a standing warning, and a block whose age cannot
be established never reads as "current".

**Block age is only asked about a block.** `combine_staleness` returns read
recency untouched when `BlockAge.applicable` is false, so a shadow used purely to
explain the screen — one that has never emitted a block — behaves exactly as it
did before block age existed. "There is no block" and "there is a block whose age
I cannot establish" are different states; only the second is uncertainty.

Why block age had to exist: read recency is keyed on when the shadow last
*looked*. A shadow that refetches the pane and then answers in prose restamps its
read stamp without emitting anything, so read recency clears while last round's
concerns sit on screen being re-offered as current.

**Which surface owns which warning:**

| surface | owns | reads |
|---|---|---|
| minimonitor `#mini-shadow-stale` banner | the continuous warning, **including the became-stale transition** | combined, recomputed every tick |
| concern-picker modal (`c`, both apps) | the actionable warning at forward time | combined, recomputed from the action's own capture |
| auto-offer toast (both apps) | the one-shot "new concerns arrived" announcement | combined, at announcement time only |

The toast deliberately does **not** re-fire when a block goes stale in place:
both apps return early on an unchanged block (round-qualified payload dedup in
minimonitor, block-signature gating in the monitor), and re-announcing every tick
would change what a toast means. The live banner owns that transition. `ait
monitor` has no such banner, so there its picker is the only owner.

See the "Feedback freshness" section of `aidocs/framework/shadow_agent.md` for the
stamping and comparison mechanism.

See `aidocs/framework/shadow_agent.md` for the shadow companion's overall pipeline.
