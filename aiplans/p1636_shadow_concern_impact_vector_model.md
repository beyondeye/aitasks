---
Task: t1636_shadow_concern_impact_vector_model.md
Branch: aitask/t1636_shadow_concern_impact_vector_model
Base branch: main
Output branch: main
---

# t1636 — Shadow concern impact-vector model (parent decomposition plan)

### Pre-phase (risk mitigations)

This plan is heading-oriented (a decomposition parent implements nothing
itself), so the pre-phase block takes the documented fallback placement: top of
the plan body, immediately after the metadata header. Each step below is
executed by **this** task — the parent's implementation output is the child
specs and child plans, so "write mitigation X as the first step of child N's
plan" is a concrete, verifiable parent action. Every step must land **before**
the child it targets is picked.

1. `[characterize_parser_backcompat]` Write into `aiplans/p1636/p1636_2_*.md`,
   as its first implementation step, a characterization test to be added
   **before** `_TRAILER_SPAN` is edited, pinning the **five-field projection
   contract** (not whole-tuple equality, which appended fields necessarily
   change): for (a) a block with no trailer and (b) a block with a
   `Disposition:`/`Verified:`-only trailer — the projection of each parsed
   `Concern` onto the original five fields (`priority`, `region`, `body`,
   `disposition`, `verdict`) as literal expected values; positional
   construction with five arguments still populating exactly those five
   fields; and `display_body()` plus `build_clipboard_payload` output
   byte-identical. The step must state that this test is written and observed
   passing against unmodified `concern_parser.py` first — with the expected
   values as recorded literals that do NOT change when the implementation
   lands — so it is a real baseline rather than a post-hoc restatement.

2. `[discriminate_priced_vs_unpriced_worsens]` Write into
   `aiplans/p1636/p1636_2_*.md`, immediately after step 1, a test written
   **before** the field shape is chosen that fails unless the parser
   distinguishes three states: `Worsens: nothing.` (priced, empty), an absent
   `Worsens:` sentence (not priced), and a populated `Worsens:` list. The step
   must name all three states explicitly so the test cannot be satisfied by a
   two-state implementation.

3. `[pin_narrow_row_width_budget]` Write into `aiplans/p1636/p1636_4_*.md`, as
   its first implementation step, a two-stage render-level assertion. Stage 1,
   added **before** `_ConcernRow.render` is touched: at both 24 and 28 columns
   the region text *and* the body text reach the composited output (the t1274
   shape — a 21-char region erased region *and* body). Stage 2, extending the
   same test once the trade profile lands: at the same widths, region, body,
   **and the vector's mandatory core** (first improve token, first worsen
   token, the effort scalar) all reach the composited output — exhaustively
   over every (improve-dim × worsen-dim) pair × magnitudes (including
   unspecified-`?`) × effort tokens, measured in terminal cell widths, so the
   assertion fails when *any* combination clips the core, not merely when the
   pre-existing parts regress on one lucky example. Assert on rendered
   content, never on the widget's declared size.

4. `[state_magnitudes_advisory_in_producers]` Write into
   `aiplans/p1636/p1636_3_*.md`, as its first implementation step, the
   requirement that every producer doc states that the **dimensions are the
   load-bearing part and the magnitudes are advisory**, plus a
   `TestProducerMagnitudeFramingRule` guard over the same `KNOWN_PRODUCERS` set,
   with a negative control proving the guard can fail.

## Context

The shadow agent's four review producers classify every concern on a single,
undefined `high/medium/low` scale. Nothing anywhere states what that scale
*measures* (impact? likelihood? effort? which quality attribute?), the
`blocking/follow-up/informational` disposition rubric exists only on the
implementation side, and a concern is a pure demand with externalized costs —
nothing asks what incorporating the fix would *worsen*. The result, observed
live and worsening as the shadow runs on stronger models: reviews that do not
converge after 10 rounds, and a picker whose `forward / rejected / spinoff`
decision surface exists while the information needed to choose is absent.

The agreed direction: **a concern is a proposed delta in a shared
quality-dimension space.** Each concern declares a signed impact vector over one
closed dimension vocabulary — improve side and worsen side drawing from the
*same* dimensions — plus a separate one-time effort scalar:

```
… body … Improves: robustness(high), verification(medium). Worsens: simplicity(low). Effort: low. Disposition: follow-up. Verified: PLAUSIBLE.
```

The mandatory Worsens side is the anti-overengineering mechanism: it forces the
reviewer to price its own suggestion, so a concern improving only non-obligated
dimensions at a simplicity cost self-identifies as a bad trade.

## Decomposition

Five children. This is a **parent decomposition plan** — the parent implements
nothing itself.

| child | scope | depends on |
|---|---|---|
| `t1636_1` | dimension vocabulary module + `concern-format.md` spec section + doc↔module drift guard | — |
| `t1636_2` | parser: trailer grammar extension, derived fields, `display_body` stripping | `_1` |
| `t1636_3` | the four producers + `impl-review-angles.md` grounding rubric + producer-rule guards + website doc | `_1`, `_2` |
| `t1636_4` | picker UI: trade-profile rendering + decision guidance | `_2` |
| `_5` | delta-scoped auto-recheck (convergence by construction) | `_3`, `_4` |

(`_3` and `_4` may proceed independently after `_2`; `_5` depends on **both** —
it extends the producers' re-review entry that `_3` writes *and* edits
`monitor_shared.py` — the centralized scope-aware labeling — which `_4` also
touches, so out-of-order work would conflict in that module. `_1`/`_2` are
covered transitively.)

Sibling auto-dependency already chains these; the table records the *semantic*
dependency so a child picked out of order knows what it needs.

## Settled design decisions

These were open at task-creation time and are settled here so no child
re-litigates them.

1. **Vocabulary: 7 dimensions, `maintainability` and `simplicity` kept
   separate.** Extracting a shared helper *improves* maintainability while
   *worsening* simplicity; merging them into one `code_health` scalar makes
   exactly that trade cancel itself out, and pricing added mechanism is the
   whole reason the Worsens side is mandatory.

   `goal` · `correctness` · `robustness` · `performance` · `verification` ·
   `maintainability` · `simplicity`

2. **`priority` stays a marker field — but is bound to the vector by a
   deterministic mapping.** The `- [priority | region]` line grammar is what
   every back-compat guarantee in `concern-format.md` rests on, and widening the
   bracket is the documented t1167 drop hazard, so the marker keeps carrying a
   priority. To stop the original undefined scalar surviving in another form:

   - `concern_dimensions.derive_priority(improves)` is the **single canonical
     mapping**: max magnitude over the improve entries whose magnitude is known
     (`high` > `medium` > `low`); empty/absent improve side, or no known
     magnitudes → `low`.
   - **Producers MUST emit the marker priority equal to that mapping** for any
     concern carrying an impact trailer (stated with the two-placement
     discipline, guarded in `_3`).
   - **For a vector-bearing concern the derived value is authoritative on the
     consumer side:** the picker badge shows `derive_priority(improves)`, and a
     marker that disagrees is flagged with a dim `≠` beside the badge — visible,
     never silently reconciled. Legacy concerns (no vector) keep the marker
     priority exactly as today.

3. **`needs_addressing()` semantics unchanged** — still disposition-driven, still
   safe-direction on an unspecified disposition. The vector adds *guidance*, not
   a re-partition.

4. **The picker renders, it does not re-sort.** The Needs-addressing /
   Informational partition and the producer's within-partition order stay
   authoritative; `original_index` positional selection identity is untouched.

5. **"Priced as nothing" ≠ "not priced".** `Worsens: nothing.` and an omitted
   `Worsens:` sentence are different states and the parser must distinguish
   them — the whole anti-overengineering signal is whether the reviewer
   *did the pricing*. Shape: `improves` / `worsens` are
   `tuple[ImpactEntry, ...] | None`, where `None` means the sentence was absent
   and `()` means it was present and empty (`nothing`).

6. **Trailer grammar: closed dimensions, bounded-permissive magnitudes,
   per-sentence atomicity.** Three layers, each with a defined failure mode:

   - **Dimension names are the closed vocabulary** (alternation built from
     `concern_dimensions`). A sentence containing an unknown dimension
     (`Improves: frobnication(high).`) fails to match **as a whole sentence**
     and stays visible in the display body and the forwarded payload — no
     silent drop, no permissive name class (which would re-open the collision
     hazard the format rests on).
   - **Magnitudes are bounded-permissive inside a matched sentence**: an entry
     is `name` or `name(token)` where `token` is `\w{1,16}`. A recognised token
     (`high|medium|low`, case-insensitive) normalizes; an unrecognised or
     absent one yields magnitude `""` (unspecified) — **never `low`**, because
     degrading on the *worsen* side would understate a cost, the unsafe
     direction for this mechanism. The dimension is never dropped; surfaces
     render `?`. This is what reconciles "unknown magnitude → unspecified" with
     a sentence that still matches: the sentence-level regex admits the bounded
     token, and normalization decides the value.
   - **Parsing is per-sentence, and the run is a valid suffix.**
     `_TRAILER_SPAN` matches the terminal run of *valid* sentences; an invalid
     sentence (unknown dimension, malformed entry list) terminates the run's
     extension, so a valid `Disposition:`/`Effort:` suffix after an invalid
     `Improves:` sentence is still parsed, and the invalid sentence remains in
     the display body where a human sees it. Both directions are pinned by
     tests in `_2`: (invalid sentence → valid suffix still parsed, invalid text
     visible) and (fully valid run → fully stripped from display).

## Child specifications

### t1636_1 — dimension vocabulary + format spec (SSOT)

**New:** `.aitask-scripts/monitor/concern_dimensions.py` — modelled on
`.aitask-scripts/lib/followup_kinds.py:33` (`FOLLOWUP_KINDS` dict → derived
`frozenset`, per-value presentation tuple, `*_for()` accessors). It lives in
`monitor/` rather than `lib/` because its only consumers are `concern_parser.py`
(which is contractually **pure** — one sibling import, no `sys.path` insertion)
and the picker; no shell consumer needs it, unlike `followup_kinds`.

Carries per dimension: canonical name, a one-line rubric, a short display label
for the compact picker render, and declaration order (= the canonical ordering
the producers and the picker both use). Magnitude vocabulary (`high|medium|low`)
and its semantics live here too, as does `derive_priority`.

**Short labels are ≤ 5 terminal cells** (e.g. `goal`, `corr`, `robus`, `perf`,
`verif`, `maint`, `simpl`) — a *packing* constraint, not taste: the narrow
picker's mandatory core `▲label? ▼label? E:xx` must fit the 21-cell budget at
24 columns (see `_4`), which bounds `2·(W+2) + 2 + 4 ≤ 21 → W ≤ 5` with the
4-cell effort tokens. The module asserts the bound over its own table (a label
that grows past 5 fails at import-test time, not at render time).

**Doc:** a new section in `.claude/skills/aitask-shadow/concern-format.md`
defining the trailer grammar, the mandatory-Worsens rule, the effort scalar, and
the severity/disposition **grounding** rubric (`blocking` = improve side touches
an obligation dimension per the task's AC/plan goal; `follow-up` = net-positive
but non-obligated; `informational` = no proposed delta / already settled).
Placed beside the existing "Derived fields: `disposition` and `verdict`" section.

**Guard:** a drift test asserting the doc section and the module enumerate the
same vocabulary — canonical site plus drift guard, never two copies.

### t1636_2 — parser extension

`.aitask-scripts/monitor/concern_parser.py`:

- Extend `_TRAILER_SENTENCE` (line ~176) with `Improves:` / `Worsens:` /
  `Effort:` alternatives built from `concern_dimensions`. The existing terminal
  anchoring of `_TRAILER_SPAN` and free sentence order inside the run are
  preserved verbatim — they are what make the derivation safe.
- Add `improves`, `worsens`, `effort` to `Concern` (NamedTuple, **appended after
  the existing fields with defaults**, so positional construction in existing
  tests and call sites is unaffected).
- Extend `_parse_trailer` to return them; `display_body()` strips the whole
  matched span as it already does — no new stripping logic.
- Back-compat is the acceptance bar, stated as the **five-field projection
  contract** (appending NamedTuple fields necessarily changes tuple length and
  whole-tuple equality, so "byte-identical tuples" is not the claim): for a
  no-trailer block and a disposition-only-trailer block, (a) each parsed
  `Concern`'s projection onto the original five fields (`priority`, `region`,
  `body`, `disposition`, `verdict`) equals today's output, (b) positional
  construction with five arguments still populates those five fields with the
  new fields at defaults, (c) `display_body()` and `build_clipboard_payload`
  outputs are byte-identical to today's.

Tests extend `tests/test_concern_parser.py::TestDispositionDerivation` (line
568) and add a class for the vector grammar, covering at minimum:
`Worsens: nothing.` vs. absent vs. populated (three distinct states, per
decision 5); missing magnitude and unknown magnitude (`""`, never `low`);
unknown dimension on each side (sentence stays in display body); an invalid
`Improves:`/`Worsens:` sentence followed by a valid `Disposition:`/`Effort:`
suffix (suffix parsed, invalid text visible); `derive_priority` edge cases
(empty, all-unknown magnitudes); and `build_clipboard_payload` still forwarding
`.body` verbatim (the `tests/test_concern_body_display_contract.py`
FORWARD/DISPLAY contract must stay green untouched).

### t1636_3 — producers + rubric + guards

Extend all four producers — `plan-challenge.md`, `impl-challenge.md`,
`plan-assumptions.md`, `plan-diagnose-errors.md` — to emit the impact trailer,
following the **two-placement discipline** the round-header and
rejection-suppression rules already use (a bolded pre-emit directive at the head
of the emit step **and** an entry in the rules list), because these are prompt
files read at runtime and a single placement is a rule the agent may skip.

Ground the disposition rubric in the vector in
`.claude/skills/aitask-shadow/impl-review-angles.md` ("Disposition rubric"), and
give the **plan-side** producers a disposition trailer for the first time —
today they emit none, so every plan concern lands undifferentiated in "Needs
addressing".

The producers also state the **priority-mapping rule** (settled decision 2): a
concern carrying an impact trailer MUST emit its marker priority equal to
`derive_priority(improves)` — max known improve magnitude, `low` when empty —
stated with the same two-placement discipline and covered by the producer-rule
guard, so the marker and the vector cannot drift into contradictory decision
signals.

Guards: a new `TestProducerImpactVectorRule` in `tests/test_concern_parser.py`
mirroring `TestProducerRoundHeaderRule` (line 1364) — both placements, plus a
negative control proving the guard can fail. `KNOWN_PRODUCERS` /
`PRODUCER_MARKER` are reused from `TestProducerShortRegionRule` (line 1033).
`tests/test_shadow_disposition_surfaces.py` gains the new enumeration sites.
Rendered-variant coverage comes free via
`TestRenderedShadowDocsKeepTheGuarantees` (line 1570), which re-renders the
`fast` profile.

User-facing: `website/content/docs/workflows/shadow-agent.md:70,98`.

### t1636_4 — picker UI

`.aitask-scripts/monitor/monitor_shared.py`:

- `_ConcernRow.render` (line 2781) gains the compact trade profile
  (`▲robus ▼simpl E:lo`) built from `concern_dimensions`' short labels.
- **Narrow layout is specified, not left to fit where it can** (there is no
  spare room: the two-line row spends line 1 on mark+badge+region and line 2 on
  body). A vector-bearing concern's narrow row becomes **three lines** — a new
  `three-line` CSS class (`height: 3`) beside the existing `two-line` (line
  2671), vector on its own third line: `   ▲robus ▼simpl E:lo`. A concern
  with no vector stays two-line, so legacy blocks render exactly as today.
  **Wide layout**: the profile is inserted between region and body on the one
  line, before the body's own truncation.
- **Packing invariant, then overflow policy** (budget = width −3 indent =
  21 cells at 24 columns). The **mandatory core** — first improve entry, first
  worsen entry, effort scalar — is *guaranteed* to fit by construction, never
  by ellipsis: effort renders as the 4-cell tokens `E:lo`/`E:md`/`E:hi`
  (`E:?` unspecified), short labels are ≤5 cells (enforced in
  `concern_dimensions`, see `_1`), magnitude renders as at most one trailing
  `?` cell — worst case `▲maint? ▼simpl? E:hi` = 2·(1+5+1) + 2 + 4 = 20 ≤ 21.
  Ellipsis therefore only ever governs the *optional* tail: at most 2 entries
  per side, further entries collapse to `+N`; drop order under pressure is 2nd
  improve, then `+N` markers, then 2nd worsen — the worsen side's first entry
  and `E:` are core and never dropped. All marks single-width (`▲`/`▼` are
  East-Asian-Width Ambiguous, width 1 outside CJK — same class as the existing
  marks), keeping `_NARROW_PREFIX_COLS = 8` (line 2634) valid.
- **The invariant is proven exhaustively, not by example**: a test renders
  every (improve-dim × worsen-dim) pair × magnitude values including
  unspecified-`?` × all effort tokens at 24 columns, measuring **terminal cell
  widths** on composited output, and asserts the full core is present in every
  combination. A packing claim checked on one lucky pair passes while
  `maint?`+`simpl?`+`E:hi` clips.
- **The composited assertion covers the vector, not just survival of the old
  parts**: at 24 and 28 columns, region, body, **and** the vector line's
  leading tokens (first improve token, first worsen token, `E:` scalar) must
  all reach the composited output — an assertion that passes while the trade
  profile is clipped away would let the feature silently not exist at exactly
  the width the picker actually runs at (t1274's lesson).
- The priority badge for a vector-bearing concern renders
  `derive_priority(improves)`; a disagreeing marker priority gets a dim `≠`
  (settled decision 2).
- Decision guidance goes in `_context_line()` (line 3521) or its own Static —
  **not** in `_CONCERN_HELP_FULL` / `_CONCERN_HELP_COMPACT` (line 2864), whose
  token budget at `_PICKER_MIN_COLS = 24` is measured and pinned by
  `ConcernHelpLineBudgetTests`.
- `_partitions()` (line 3501) is untouched (decision 4 above).

`minimonitor_app.py` consumes the shared modal, so no parallel change is
expected — but the companion-pane (narrow) render is the surface that must be
verified at real width.

### t1636_5 — delta-scoped auto-recheck

`review_loop.compose_recheck_prompt` (`.aitask-scripts/monitor/review_loop.py:1242`)
today injects "re-run the review sub-procedure **end to end**" every round, so
each round is a fresh unbounded search over an ill-defined space rather than a
delta check against round N-1. Only user-rejected concerns are suppressed.

Scope: make a recheck round *delta-scoped* so the loop converges by
construction. The delta contract has three parts — the first exists because
"report only NEW concerns" alone would let an unresolved prior concern vanish
into a metadata-only block that `is_metadata_only_block` then **certifies as a
clean round** (a false all-clear, the exact silent-false-negative class the
format doc guards against):

- **Unresolved or regressed prior concerns are RE-EMITTED**, as ordinary
  `- [priority | region]` items (every existing consumer keeps working), with
  the body opening on their status — e.g. `Unresolved from round <N-1>: …` /
  `Regressed: …` — so the block is never metadata-only while anything
  actionable is outstanding.
- **Resolved prior concerns are named in the prose** (not re-emitted as items)
  — the human-readable record of what the round verified.
- **Newly discovered concerns are emitted with their TRUE rubric disposition —
  disposition is never relabeled for control flow.** The rubric `_3` installs
  states "informational is never a parking slot" (`impl-review-angles.md:238`),
  and a net-positive non-obligated finding is `follow-up` by that rubric — a
  picker spin-off candidate, not dimmable noise. Convergence comes from
  **scope, declared machine-readably**, not from disposition:

  - A delta round's *search* is scoped: verify prior concerns' status, and
    hunt for new concerns **whose improve side touches an obligation
    dimension**. Non-obligation findings are simply out of the round's
    declared scope (the no-silent-omission rule already binds "within the
    tier's declared scope"); one *incidentally* noticed anyway is emitted with
    its true disposition — never suppressed, never relabeled.
  - **The scope is carried in the round header**: the `_META_LINE` grammar
    gains an optional trailing `| scope: delta` (parsed into a new
    `BlockMeta.scope: str = ""`; absent → `""`, full back-compat — a headerless
    or scopeless block behaves byte-identically). `parse_reviewed_at_epoch`'s
    input is unaffected: the scope token is a separate named group, not a
    suffix on the timestamp.
  - **Scope-aware review labeling is centralized in `monitor_shared.py` and
    consumed by every surface — never re-derived per app.** The clean-round
    literal is currently duplicated verbatim at `monitor_app.py:3099` **and**
    `minimonitor_app.py:4245` ("Clean review (round N) — no concerns"), and
    `format_block_meta` (`monitor_shared.py:2914`) — the shared suffix on the
    picker context line and the auto-offer toasts — shows only the round. A
    scope token honored on one surface while the others still claim a general
    all-clear (or stay scope-silent) just moves the false-clean to whichever
    surface the user happens to read. So: one shared `clean_round_msg(meta)`
    (scope `delta` → "Clean delta review (round N) — prior concerns resolved,
    no new obligation concerns"; scopeless → today's wording) replacing both
    app literals, and `format_block_meta` gains the scope in its suffix
    (`round 3, 14:03:27Z, delta`) so the picker context and every concern
    notification carry it. Tests cover each surface: both apps' metadata-only
    messages, the picker context line, and the toast — each asserting the
    scoped wording appears where a `scope: delta` block is shown.

**The prior round's items get a durable data path — conversational memory is
not one.** Today's delivery path (`minimonitor_app.py:4041-4051`) extracts only
`parse_block_meta(tick).round + 1` and injects a single line; the shadow's
knowledge of the prior items lives solely in its conversation, which compaction
or a session disruption can lose or paraphrase — an unresolved concern could
still silently disappear. So:

- **At recheck-fire time, minimonitor persists a bounded round record** from
  its own authoritative `-J` capture (it already parses the block at this
  point): the prior block's items + round meta, written to
  `.aitask-shadow/<task_id>/prior_round.md` by a helper modeled on
  `aitask_shadow_rejected.sh` — which means its actual write discipline, not a
  paraphrase: the `lib/registry_lock.sh` mutex around the RMW **and**
  `lib/atomic_write.sh`'s `ait_atomic_render` for the landing write
  (`aitask_shadow_rejected.sh:41` is explicit: "Never an open-coded
  mktemp-then-mv" — that seam owns the symlink, zero-byte-refusal and cleanup
  guarantees). **Items-only — the store can never contain a fence**, so it can
  never be parsed as a forwardable block if echoed into the pane. If the
  capture at fire time is head-truncated (`block_head_truncated`) or yields no
  complete block, **no record is written** — a partial record is worse than
  none.
- **The write runs off the event loop, bounded.** The fire path is async
  (`_maybe_fire`'s neighborhood already uses `asyncio.create_subprocess_exec`
  / `to_thread` for exactly this reason), and the helper can wait on the
  registry mutex — a synchronous call there freezes the whole TUI for the
  lock wait. The record write goes through an asyncio subprocess seam with a
  **bounded timeout**; a timeout or `LOCK_BUSY` (exit 3, nothing written) is
  handled as "no record this round": the recheck still fires, the prompt
  names no record, and the producer's fail-safe runs a full review — the
  degradation is a slower round, never a frozen UI and never a false clean.
- **The record is identity-bound, not a task-wide mutable alias.** A file
  keyed by task id alone aliases across shadow sessions and blocks — the exact
  hazard the t1448 contract exists for (`concern_parser.py:219`: the freshness
  key is the `(round, reviewed_at)` **pair**, never round alone, because a
  restarted shadow counts from 1 again; two monitors on one task are the same
  shape). So: the record carries `round`, `reviewed_at`, and a digest of the
  wrap-joined block region it was derived from; the injected recheck prompt
  **names that exact identity** ("recheck round N — prior round M @ <ts>,
  record <digest-prefix>"); and the producer's read **verifies** the stored
  identity against the prompt's before using it. A mismatch — another
  monitor's overwrite, a stale file from a previous session — reads as
  "could not consult", never as the prior round. One file plus
  verify-on-read is deliberate (per-identity files would accumulate
  unboundedly); the mutex guarantees the write is untorn, the identity check
  guarantees an intact-but-wrong record is refused.
- **The producers' re-review entry reads the record** with the same
  three-outcome reader contract as the rejection store: a record whose
  identity matches the prompt / the single line `NO_RECORD` / anything else —
  including an identity mismatch or a malformed record — = "could not
  consult".
- **Fail-safe when the record is unavailable** (could not consult, mismatch,
  or `NO_RECORD` on a round > 1): the producer runs a **full** review, states
  that delta scoping was skipped, emits **no** `scope: delta` token, and
  **must not emit a metadata-only block on the basis of prior-round claims it
  cannot verify** — an unverifiable delta never certifies clean.

**Clean is redefined for recheck rounds**: a metadata-only block is emitted
only when the identity-verified round record was consulted, *all* prior
actionable concerns are resolved, **and** the scoped search found nothing new.
Previously-reported informational items that stand unchanged are suppressed
via the round record and named in prose (they were already machine-emitted to
the user in the round that found them). Touches `compose_recheck_prompt` (the
injected wording states the delta contract and names the record identity, not
"end to end"), the fire path's record write, the new helper, the `_META_LINE`
scope extension in `concern_parser.py`, the centralized scope-aware labeling
in `monitor_shared.py` (both apps' clean-round messages, `format_block_meta`),
the producers' re-review entry, and the producer-rule guards.

**`BlockMeta` compatibility is a defined two-field contract, not a slogan.**
Adding `scope: str = ""` preserves two-argument construction but necessarily
changes NamedTuple length, whole-tuple equality, repr, and 2-tuple unpacking —
that is documented as **not** backward compatible, in the field's docstring.
The executable contract pins what *is*: (a) every legacy header shape (with
and without `@ <ts>`) parses to unchanged `round` and `reviewed_at` values
with `scope == ""`; (b) `BlockMeta(3, "…")` two-argument construction still
populates exactly those two fields; (c) `parse_reviewed_at_epoch` is tested
on scoped headers to prove the scope group never leaks into the timestamp
(the strict round-trip would silently return `None` — a freshness regression,
not an error); (d) the t1448 freshness key stays the `(round, reviewed_at)`
attribute pair, never whole-tuple equality — asserted at the dedup call
sites.

Split last deliberately: it is the only child whose correctness depends on the
vector already existing end-to-end, and the task text itself flags it as
separable.

## Verification

Per child; the parent verifies only that the decomposition landed.

- `bash tests/run_all_python_tests.sh --test-dir tests` — **read the last line
  only** (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); piping discards the
  status, so use `set -o pipefail` or `${PIPESTATUS[0]}`.
- Targeted: `tests/test_concern_parser.py`,
  `tests/test_concern_body_display_contract.py`,
  `tests/test_shadow_disposition_surfaces.py`,
  `tests/test_concern_picker_modal.py`.
- **t1636_5 round-record plumbing gets its own tests — the parser/picker
  suites above cannot see a false-clean revived through a stale or broken
  record.** Required, mirroring `tests/test_shadow_rejected.sh` for the
  helper and the minimonitor delivery suites for the fire path:
  - helper: malformed record, truncated/fence-bearing input refused,
    failed/partial write leaves no record (`ait_atomic_render` refusal paths —
    zero-byte result, render failure), concurrent writer → `LOCK_BUSY` (exit
    3) with nothing written, identity fields round-tripped exactly;
  - delivery: the fire path writes the record with the identity of the very
    block it parsed, and the injected prompt names that identity; a
    head-truncated or incomplete capture writes **no** record; a helper
    **timeout or `LOCK_BUSY` at fire time** still fires the recheck with no
    record named and never blocks the event loop — pinned as a fail-safe
    full-review path, not an error;
  - the invariant, pinned end-to-end: an unavailable, mismatched, or missing
    record forces a full review and can **never** certify a clean round — the
    fail-safe must be able to fail (negative control: a producer-doc mutation
    dropping the fail-safe rule trips the producer-rule guard).
- `./.aitask-scripts/aitask_skill_verify.sh` before committing any shadow-doc
  change.
- Live surface (t1636_4): a real minimonitor companion pane at ~28 columns and
  at 24 columns — a render-level assertion, not a screenshot claim.

## Step 9 (Post-Implementation)

Standard: the parent is archived once every child is done. Per
`aidocs/framework/` convention a decomposed parent skips the Step 8d spawned
"after" mitigations — the children carry their own.

## Risk

Levels below are the **post-inline reassessment** — they describe the plan as
approved, with the four confirmed pre-phase mitigations in it.

### Code-health risk: medium
- The trailer grammar extension touches `_TRAILER_SPAN`, the one regex that
  every existing disposition/verdict derivation and `display_body()` strip
  depends on; a permissive alternation would re-open the wrap-collision hazard
  the whole format rests on · severity: low (residual — a byte-identical
  back-compat baseline is pinned by inline pre-phase
  characterize_parser_backcompat before the regex is edited) ·
  → mitigation: inline pre-phase characterize_parser_backcompat
- Adding fields to the `Concern` NamedTuple has a positional-construction blast
  radius across the parser, both TUIs, the spin-off/rejection store path, and
  ~4 test modules · severity: low (residual — field positions are pinned
  positionally by the same pre-phase) ·
  → mitigation: inline pre-phase characterize_parser_backcompat
- The picker row is already at its width budget in the narrow companion pane;
  the t1274 failure (region *and* body erased) is the precedent for what
  over-spending it costs · severity: low (residual — region and body are pinned
  at 24 and 28 columns by inline pre-phase pin_narrow_row_width_budget before
  the render is touched) · → mitigation: inline pre-phase pin_narrow_row_width_budget
- The change still spans a pure parser, four runtime-read prompt docs, and two
  TUIs; the pre-phases bound each individual failure but not the breadth, which
  is what keeps this dimension at medium rather than low · severity: medium ·
  → mitigation: none

### Goal-achievement risk: medium
- LLM magnitude calibration is noisy — the named dimensions are the load-bearing
  part and the magnitudes are advisory; if that framing is lost in the producer
  docs the trailer becomes noise the user learns to ignore · severity: low
  (residual — the framing is required in every producer and guarded, per inline
  pre-phase state_magnitudes_advisory_in_producers) ·
  → mitigation: inline pre-phase state_magnitudes_advisory_in_producers
- The anti-overengineering mechanism only works if the Worsens side is genuinely
  mandatory and "not priced" is distinguishable from "priced as nothing"; a
  parser that collapses the two silently removes the feature's whole point ·
  severity: low (residual — a three-state discriminator is written before the
  field shape is chosen, per inline pre-phase
  discriminate_priced_vs_unpriced_worsens) ·
  → mitigation: inline pre-phase discriminate_priced_vs_unpriced_worsens
- Convergence (t1636_5) is the outcome the user actually feels; if it is
  deferred indefinitely the first four children add annotation burden without
  delivering the observed pain relief · severity: medium · → mitigation: none —
  tracked as child t1636_5, which is a named artifact with a real dependency
  edge rather than a deferred intention

### Planned mitigations
- timing: pre-phase | name: characterize_parser_backcompat | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — trailer regex is the single derivation point; Concern positional blast radius | desc: pin the five-field projection, five-arg positional construction, and display/clipboard byte-identity for no-trailer and disposition-only blocks, before _TRAILER_SPAN is edited
- timing: pre-phase | name: discriminate_priced_vs_unpriced_worsens | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — collapsing "priced as nothing" with "not priced" deletes the mechanism | desc: three-state test (nothing / absent / populated) written before the field shape is chosen
- timing: pre-phase | name: pin_narrow_row_width_budget | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — narrow picker row is already at its width budget (t1274 shape) | desc: two-stage composited assertion at 24 and 28 columns — region+body pinned pre-change, then region+body+vector core exhaustively over dim pairs, magnitudes and effort tokens once the trade profile lands
- timing: pre-phase | name: state_magnitudes_advisory_in_producers | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — noisy magnitude calibration turning the trailer into ignorable noise | desc: every producer must state dimensions are load-bearing / magnitudes advisory, with a guard and a negative control
