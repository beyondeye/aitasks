---
Task: t1651_concern_magnitude_color_and_focused_detail_panel.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1651 — Concern magnitude colour ramp + focused-concern detail panel

## Context

The concern picker (`ConcernPickerModal` / `_ConcernRow` in
`.aitask-scripts/monitor/monitor_shared.py`, pushed by both `ait monitor` and
`ait minimonitor`) renders a vector-bearing concern's trade profile as
`▲robus ▼simpl E:md`. Two problems, on the same surface:

1. **Magnitude is illegible.** `_magnitude_markup` (line 2795) encodes it as
   *weight only* — `[bold]▲[/]` high, bare `▲` medium, `[dim]▲[/]` low. On a
   single glyph that is close to unreadable, which is the report that opened
   this task. It also has a latent defect: **medium and unspecified are both a
   bare arrow**, so once the ladder's last rung drops the `?` marker they are
   byte-identical.
2. **The row cannot show the vector anyway.** `trade_profile_rungs` (2842) is a
   five-rung degradation ladder; at minimonitor's 28-cell row the survivor is
   `▲x ▼y E:z` — one improve, one worsen, the effort scalar. `_region_seg`
   ellipsizes the region and `render()` hard-clips the body to one row on the
   three-line layout. So even a perfect ramp leaves most of the vector invisible
   at the width where the picker is most used.

This task also carries the risk archived **t1293** raised and t1426 was to
mitigate (`risk_mitigation_tasks: [1426]`): *"the picker still never shows a
concern's full body — the two-line row truncates it at every width."* t1426
proposed a modal-over-modal; the user has settled that question in favour of an
**inline** panel, and t1426 was deleted.

**Landed mid-planning: t1648** (`d6451148c`) split the picker's single width
threshold into two tiers — `xnarrow` (width-keyed, owns horizontal chrome and
help wording) and a new `xshort` (height-keyed, owns `#concern-dialog`'s
`max-height` cap) — and added `_apply_measured_height_tier`, which *measures*
`needed` from the laid-out children instead of modelling it. This plan builds on
that mechanism rather than inventing a parallel one.

## Decisions taken (with the user)

| Question | Decision |
|---|---|
| Magnitude ramp | Reuse the dialog's existing heat vocabulary, plus an **off-ramp** colour for unspecified |
| Panel affordance | **Always-on, geometry-gated** — no new key, no help-line token |
| t1648 | Landed; plan against the post-t1648 mechanism |

**Assumption stated explicitly:** the AC "a legacy (vector-less) concern block
renders exactly as it does today" is honoured *literally* — the panel is
composed only when the block carries vectors, exactly as `_CONCERN_GUIDANCE`
already is (`compose()`, `if any(has_impact_vector(...))`). Consequence: legacy
blocks keep the truncated body. That residual is recorded under Risk.

---

### Pre-phase (risk mitigations)

Runs before any change to `_apply_size_tier` or `_magnitude_markup`.

1. `[pin_size_tier_gate_order]` Add a characterization test to
   `tests/test_concern_picker_modal.py` pinning `_apply_size_tier`'s **current**
   call order: the `self.size`-only gate that exists today
   (`_apply_guidance_visibility`) runs **before** `_apply_fit_tier`, and
   `_apply_fit_tier` is deferred a refresh exactly when
   `_apply_measured_width_tier` reports a help swap. Observe it passing against
   unmodified `HEAD` before touching production code.

   Its **negative control must mutate only code that exists at `HEAD`**: an
   in-memory source variant (the `_variant(path, old, new)` idiom from
   `tests/test_concern_body_display_contract.py`) that moves
   `_apply_guidance_visibility` *after* `_apply_fit_tier` must make the test
   fail. A control that moves `_apply_detail_visibility` cannot run here —
   verified, that symbol has **zero occurrences** in `monitor_shared.py` at
   `HEAD` — so it would silently mutate nothing and leave the control vacuous.
   The equivalent assertion for the new gate is a *separate* test introduced
   with it, listed as post-phase step 0 below.

---

## Part 1 — magnitude colour ramp

**One named mapping beside `_CONCERN_BADGE`** (line 2564), which is the single
site to retune:

```python
#: Magnitude → rich markup for a trade-profile arrow. DELIBERATELY the same
#: vocabulary as `_CONCERN_BADGE` three cells to its left: `derive_priority`
#: defines the badge as the max improve magnitude, so a red HIGH badge beside a
#: red ▲ is the SAME FACT rendered twice, not two scales colliding.
#:
#: The ramp encodes INTENSITY, never direction — the glyph (▲/▼) already carries
#: direction, so ▲high and ▼high are the same colour on purpose.
#:
#: `""` (unspecified) is deliberately OFF the heat ramp. `normalize_magnitude`
#: refuses to degrade it to `low`, and the ladder's last rung drops the `?`
#: character that carries it — so at that rung colour is its ONLY carrier and it
#: must not collapse into a real magnitude. #6272A4 is this codebase's existing
#: "inactive / unset" blue (`mark_glyphs.MARK_UNCHECKED_COLOUR`).
_MAGNITUDE_RAMP = {
    "high": "bold red",       # #800000 + bold
    "medium": "bold yellow",  # #808000 + bold
    "low": "#808080",         # explicit grey — NOT `dim`; see below
    "": "#6272A4",            # off-ramp: unspecified
}
```

**`low` carries a real colour, and this is a deliberate divergence from
`_CONCERN_BADGE["low"]`, which stays `dim`.** The task's complaint is precisely
that "bold-vs-plain-vs-dim on a single glyph is close to unreadable" — so
mapping `low` to bare `dim` would reproduce a third of the defect while a test
asserting "three distinct styles" still passed. `Style.parse("dim").color is
None` (measured), i.e. `dim` is a weight, not a colour, and colour-encoding the
magnitude is the stated goal. The ramp is therefore hot → warm → cold —
`#800000`, `#808000`, `#808080` — with `#6272A4` off it entirely. All four
values carry a resolvable colour, which also makes them uniformly assertable.

The badge keeps `dim` for LOW because it renders a **word** (`LOW`), where
weight is legible; the ramp renders a single glyph, where it is not.

**Closest pair:** `#808080` (low) vs `#6272A4` (unspecified). They differ in hue
rather than only in lightness, but this is the pair most at risk of reading alike
and it is called out explicitly in the live check below.

`_magnitude_markup(arrow, magnitude)` becomes a lookup returning
`f"[{style}]{arrow}[/]"`, with the `""` key as the fallback for an unknown
token. **Zero extra cells** — the contract in its own docstring
("the magnitude is carried by *style*, not by extra cells") is preserved, so
`check_label_widths.__doc__`'s derivation of `MAX_LABEL_CELLS = 5` and the
`ConcernRowVectorPackingTests` / `ConcernTradeProfilePackingTests` /
`ConcernPickerWidthTierTests` geometry are untouched.

Two mechanical checks before this lands:

- `trade_profile_rungs`' last rung does `seg.markup.replace("?", "", 1)`. No
  ramp value or dimension label contains `?`, so the replace still targets the
  unspecified marker. Pin it with a test at rung 5.
- Rich colour names ≠ Textual colour names, as the task warns — **measured**:
  Rich `red` → `#800000`, `yellow` → `#808000` (Textual's are `#FF0000` /
  `#FFFF00`). Tests pin the resolved truecolor hex, never the name.

**Testing note that changes the test design.** The repo's canonical `painted()`
helper (`tests/test_markup_colour_contract.py:136-196`) *skips* segments whose
`style.color is None`, and it is a **dict keyed on segment text**, so the two
arrows of the same glyph would collide. Both problems are avoided here:

- giving `low` a real colour keeps every ramp value visible to a hex-based
  assertion (this is a second reason for the change above, not the main one);
- comparing `▲high` against `▼high` still requires `segments()` — the ordered
  list that preserves duplicates — never `painted()`.

Assert the **resolved truecolor hex**, never the style name: Rich's `red` /
`yellow` are `#800000` / `#808000`, whereas Textual's are `#FF0000` / `#FFFF00`.

---

## Part 2 — inline focused-concern detail panel

> **SCOPE REDUCED after visual review — see Post-Review Changes, Change
> Request 5.** The panel as shipped is **dimensions only**: one line per
> impact entry, full dimension name, magnitude as a word where the width
> allows. The body preview, the region, the effort/disposition line and
> the inline rubric described below were all built, tested, and then
> removed at the user's direction. Read the subsections below as design
> history; CR5 is the shipped contract.

### Placement and mechanism

A new `Static#concern-detail`, composed **between `#concern-list` and
`#concern-help`** so the reading order is rows → detail of the focused row →
keys. Gated on `any(has_impact_vector(...))` like the guidance line.

Focus tracking uses the established pattern — `on_descendant_focus` on the modal
(`monitor_app.py:2638`, `minimonitor_app.py:2355`, `stats_app.py:692`,
`section_viewer.py:342`), not a per-row message. `_ConcernRow` currently has no
focus handler at all and gains none.

**`Widget.focus()` is deferred**, so `on_mount` must seed the panel explicitly
after `rows[0].focus()`; relying on the event for the initial focus leaves the
panel blank on open. This gets its own test.

### Content (reads `display_body()`, never `.body`)

> **SUPERSEDED during implementation — see Post-Review Changes, Change
> Request 1.** The order below ranked the vector first; measured, it left
> no region and no body at all at a four-row budget. The shipped policy
> reserves the metadata line, the region and one body line first, gives
> surplus rows to the region, and lets the **vector** yield with a `+N`
> marker. Do not restore the ordering below.

For the focused concern only, in this **fixed priority order** — the order in
which content survives when the panel's row budget is exceeded:

1. every improve and every worsen entry with the **full** dimension name and its
   magnitude as a word — plus `concern_dimensions.rubric_for()`, which today has
   **no production caller** (verified: only its definition and two assertions in
   `tests/test_concern_dimensions.py`);
2. the effort scalar, disposition and verdict;
3. the **un-ellipsized** region;
4. the body, wrapped — the item that yields first.

All of it through `_escape_markup()` (2734) — a concern body and region are free
text from a shadow agent, and a bare `[` took the whole modal down at t1636_4.

### Height and overflow — an explicit, tested policy

The panel is **not** a scroll container. It is always-on with no key binding, so
nothing could ever move focus into it to scroll; an `overflow-y: auto` here
would produce a scrollbar the user cannot drive. Instead:

- **Height is geometry-derived, never content-derived:**
  `rows = clamp(spare − margin, _DETAIL_MIN_ROWS, _DETAIL_MAX_ROWS)`, written as
  an explicit `styles.height` in **cells**. The panel has no `height: auto` and
  no `max-height` — see *Vertical budget* below for why both were rejected and
  for the single-writer rule. Both bounds are pinned from measurement at
  implementation time.
- **A focus change therefore never alters the vertical budget.** This is what
  makes the mixed-block transition below layout-neutral: moving between a
  vector-bearing and a vector-less row changes the panel's *content*, not its
  height, so `_apply_fit_tier` does not need to re-run on focus and cannot churn.
- **Overflow is truncated, visibly.** Content is rendered in the priority order
  above and clipped to the budget, with a trailing `…` on the last surviving
  line whenever anything was dropped. Silent clipping is the defect this task
  exists to fix; it must not be reintroduced one level up.
- **"Untruncated body" is therefore a claim about a *range*, not about all
  inputs**, and the plan says so: at `_DETAIL_MAX_ROWS` a realistic body renders
  in full, and the verification below pins **both** ends — a body longer than a
  row but shorter than the cap renders complete (the row's truncation is the
  negative control), and a body longer than the **cap** renders truncated *with
  the marker present*. Testing only "longer than a row" would leave the cap's
  behaviour unspecified and unobserved.

### Mixed blocks — a focused concern that carries no vector

`compose()` gates the panel on `any(has_impact_vector(...))`, but
`has_impact_vector` is **per concern**: a block can mix priced and unpriced
concerns, and focus can land on an unpriced one. Leaving the previous row's
vector on screen would be actively misleading.

Defined behaviour: the panel **stays visible and renders a legacy fallback** —
items 2–4 above (disposition/verdict, un-ellipsized region, wrapped body), with
the vector section replaced by a single `no impact vector` line. It is never
cleared to blank and never hidden on focus change:

- hiding it would change the displayed-child set and hand a focus event the
  power to move the vertical budget — exactly what the geometry-derived height
  is designed to prevent;
- the fallback is still strictly more than the row shows, since the region and
  body are clipped there too.

This does not conflict with the legacy-block acceptance criterion: that criterion
is about a block in which **no** concern carries a vector, where no panel is
composed at all.

### Vertical budget — joining the existing ladder

**One authoritative mechanism: an explicit runtime `styles.height`, in cells.**
There is deliberately **no** `height: auto` and **no** `max-height` on
`#concern-detail`. Those were considered and rejected — `auto` makes the height
track the focused concern's content, which would break the two properties the
rest of this design rests on: focus changes would move the vertical budget
(§ *Mixed blocks*), and the truncation point would vary per row instead of being
a known row count (§ *Height and overflow*). A `max-height` alone has the same
defect, because under it a short concern still renders shorter than a long one.

So the contract is:

- **CSS declares a fixed fallback height** (`#concern-detail { height: <N>; }`)
  — a real cell count, never `auto` — so the widget has a defined height even if
  the gate has not run yet;
- **`_apply_detail_visibility()` overwrites it** with the geometry-derived value
  on mount and on resize, and **nothing else ever writes it** — in particular no
  focus handler does;
- the height therefore depends only on `self.size`, which makes the panel's cost
  **a constant known before it is shown**, exactly as
  `_apply_measured_height_tier` already treats `#concern-list`'s declared
  `min-height` rather than its measured (circular) height.

This contract is pinned directly: a test asserts `#concern-detail`'s resolved
`styles.height` is a fixed cell value (not `auto`), that it equals the value the
formula below predicts, and that it is **unchanged after a focus move between a
one-line concern and a very long one** — the discriminating case, since that is
precisely where an `auto` height would differ.

New `_apply_detail_visibility()`, gated on **measured geometry**, never on
`self._narrow`:

```
spare = screen_height − (rows needed by every displayed child EXCEPT the panel)
show  = spare >= _DETAIL_MIN_ROWS + margin  and  width >= _DETAIL_MIN_WIDTH
rows  = clamp(spare - margin, _DETAIL_MIN_ROWS, _DETAIL_MAX_ROWS)
```

**The denominator is the full screen height, not the current cap.** This is what
keeps the decision invariant under `xshort` and preserves t1648's stated
non-oscillation proof: if the gate read the post-cap `available`, panel
visibility would feed back into the class that sets the cap.

**Precedence, one-directional, unchanged in spirit:**
`concern list > help line (key names) > detail panel > guidance`.
The panel outranks `_CONCERN_GUIDANCE` — the guidance restates a rubric the
vector already encodes, whereas the panel shows data the row actually dropped —
so when the panel is shown at ≥80x24 the guidance yields. It never outranks the
help line or the list.

**Call order in `_apply_size_tier` is load-bearing** and t1648 documented why:
gates that read only `self.size` must run *before* `_apply_fit_tier`, because
the height tier counts every **displayed** child and would otherwise charge rows
for a widget that never renders. New order:

```
_apply_measured_width_tier(...)   -> help_changed
_apply_guidance_visibility()      # unchanged
_apply_detail_visibility()        # NEW - may hide guidance to make room
_apply_fit_tier()                 # deferred a refresh iff help_changed
```

### Measured geometry (post-t1648, three vector concerns, `narrow=True`)

`spare` = screen rows − `needed`, computed exactly as
`_apply_measured_height_tier` computes `needed`:

| screen | xnarrow | xshort | needed | **spare** | panel |
|---|---|---|---|---|---|
| 40x20 | 0 | 1 | 24 | **−4** | no |
| 40x24 | 0 | 1 | 24 | **0** | no |
| 40x30 | 0 | 0 | 24 | **+6** | yes |
| 40x40 | 0 | 0 | 24 | **+16** | yes |
| 80x24 | 0 | 1 | 22 | **+2** | no |
| 80x30 | 0 | 0 | 22 | **+8** | yes |
| 100x40 | 0 | 0 | 20 | **+20** | yes |
| 30x24 | 1 | 0 | 16 | **+8** | yes |
| 24x20 | 1 | 1 | 18 | **+2** | no |
| 24x30 | 1 | 0 | 18 | **+12** | yes |

Two things this table settles. A **width-only** floor (e.g. `>=80`, copied from
the guidance) would be wrong in both directions: it would hide the panel at
30x24 and 24x30, which have more room than 80x24. And the geometries where the
panel is correctly refused — 40x20, 40x24, 80x24, 24x20 — are exactly the bands
**t1652** (`Ready`, `depends: [1648]`) owns, where the content does not fit even
at full height. The panel therefore never worsens t1652's problem;
`_DETAIL_MIN_ROWS`, `_DETAIL_MAX_ROWS` and `_DETAIL_MIN_WIDTH` are pinned from
re-measurement at implementation time,
not from this table.

---

## Files to modify

- `.aitask-scripts/monitor/monitor_shared.py`
  - `_MAGNITUDE_RAMP` (new, beside `_CONCERN_BADGE` ~2564); `_magnitude_markup`
    (~2795) becomes a lookup.
  - `_DETAIL_MIN_ROWS`, `_DETAIL_MAX_ROWS`, `_DETAIL_MIN_WIDTH` (new, beside
    `_GUIDANCE_MIN_*` ~3354).
  - `ConcernPickerModal`: `DEFAULT_CSS` (`#concern-detail`, declaring a **fixed
    fallback `height: <N>` in cells — never `auto`, never `max-height`**, plus
    its margin), `compose()`,
    `on_mount()` (seed), `on_descendant_focus()` (new), `_apply_size_tier()`
    (call order), `_apply_detail_visibility()` (new), and a `_detail_text()`
    helper that takes a `Concern` and returns escaped markup.
  - Import `rubric_for` from `concern_dimensions` alongside `derive_priority`,
    `label_for` (~line 81).
- `tests/test_concern_body_display_contract.py` — **one** new row in the frozen
  `EXPECTED_ACCESSES` registry:
  `("monitor_shared.py", "ConcernPickerModal._detail_text", "concern"): (DISPLAY, frozenset({"display_body"}))`.
  The receiver must be annotated `Concern` or the AST scan reports it
  `UNCLASSIFIED` and fails; there is deliberately no per-site suppression list.
- `tests/test_concern_picker_modal.py` — new `ConcernMagnitudeRampTests` and
  `ConcernDetailPanelTests`; extend `ConcernVerticalFitTierTests` rather than
  forking it (it already carries the `_needed` helper and composited-strip
  assertions).
- `tests/test_concern_dimensions.py` — `rubric_for` gains its first production
  consumer; note it there.
- `website/content/docs/tuis/minimonitor/how-to.md` — the panel is user-visible.

### Post-phase (risk mitigations)

Runs after the implementation above, before the task is considered complete.

0. `[pin_detail_gate_order]` The other half of the pre-phase pin, and the one
   that can only exist once the gate does: assert `_apply_detail_visibility` is
   called **before** `_apply_fit_tier`, with a source-variant negative control
   that moves it *after* and must fail. Splitting this out is what keeps the
   pre-phase control honest — it mutates only symbols present at `HEAD`.
1. `[pin_detail_gate_invariant_under_xshort]` Assert the detail gate's verdict is
   **identical** with `xshort` forced on and forced off at the same screen size —
   the property that keeps t1648's "cannot oscillate" proof intact. Pair it with
   a negative control: an in-memory source variant whose gate reads the post-cap
   `available` (rather than full screen height) must be shown to flip its verdict
   between the two states. Without that control the assertion passes for any
   implementation.
2. `[guard_magnitude_ramp_against_rung5_replace]` Assert no `_MAGNITUDE_RAMP`
   value contains `?`, and add a rung-5 render test (`trade_profile_rungs(...)[4]`)
   proving the positional `seg.markup.replace("?", "", 1)` still strikes the
   unspecified marker and never ramp markup. Negative control: a ramp value
   seeded with `?` must corrupt the rung and fail the test.
3. `[pin_ramp_render_properties_live]` In a **real terminal** (a tmux pane, not
   `App.run_test`), open the picker on a block carrying all four magnitude
   states and assert on the captured pane only what a capture can actually
   establish — **objective rendering properties**:
   - all four ramp values resolve to four *distinct* hexes on screen, with the
     `#808080` / `#6272A4` pair (the closest) checked explicitly;
   - `▲high` and `▼high` resolve to the *same* hex and the same weight;
   - each arrow's colour differs from the row background it is drawn on, at both
     the normal and the `:focus` background, and on an `.informational` row
     (whose `color: $text-muted` the arrows must override);
   - the ramp survives the `xnarrow` and `xshort` tiers.

   **What this step explicitly does NOT establish** is whether a human reads a
   red improve arrow as negative. That is a judgement about interpretation, and
   no captured-pane assertion can settle it; claiming otherwise would be
   verification theatre. It is carried instead by the spawned
   `manual_verify_ramp_readability` follow-up, whose result is a recorded human
   Pass/Fail — see `### Planned mitigations`.

---

## Verification

Render-level throughout — composited strips via `_screen_rows` / `_flat_text`,
never a bare `render()` string (Rich *drops* an overflowing segment during fold,
so a `render()` string proves nothing reached the screen).

**Part 1 — ramp**, at 80, 40, 30 and 24 columns:
- each magnitude yields a *distinct* resolved style for both `▲` and `▼`;
- `▲high` and `▼high` share a strength — asserted with `segments()`, not
  `painted()` (the dict would collapse the two arrows);
- all four values resolve to four *distinct* hexes — including the closest pair,
  `low` `#808080` vs unspecified `#6272A4` — so "low is legible as a colour" is
  asserted, not assumed. A ramp that left `low` as bare `dim` would still pass a
  weaker "three distinct styles" assertion, which is why the distinctness check
  is stated in hexes;
- unspecified stays distinct from every real magnitude **at rung 5**, where the
  `?` is dropped — the case that is broken today;
- the harness self-check negative control (render `[bold notacolour]`, assert the
  assertion raises), without which every colour assertion is vacuous.

**Part 2 — panel:**
- populated **on open**, before any ↑/↓ — the deferred-`focus()` trap, its own test;
- follows focus: ↓ changes the contents to the next row's concern;
- shows a dimension the row's ladder dropped, and the full body for a body longer
  than the row — **with a negative control asserting the row itself still
  truncates**, or the test is not measuring the new surface;
- **both ends of the overflow policy**, since a cap that is never exceeded is a
  cap that is never tested: a body longer than a row but shorter than the panel's
  budget renders **complete with no `…`**, and a body longer than
  `_DETAIL_MAX_ROWS` renders truncated **with the `…` marker present**. Assert
  the marker's presence and absence, not just the text;
- **the height contract itself**, as its own test: `#concern-detail`'s resolved
  `styles.height` is a fixed cell value — **not `auto`** — and equals the value
  `clamp(spare − margin, _DETAIL_MIN_ROWS, _DETAIL_MAX_ROWS)` predicts at that
  geometry. Assert the *absence* of `auto`/`max-height` explicitly, since a
  height that merely happens to look right under one fixture is what an `auto`
  panel would also produce;
- the panel's height is **geometry-derived**: moving focus between a one-line
  concern and a very long one — the discriminating case, where an `auto` height
  would differ — leaves the panel's row count and `_apply_fit_tier`'s verdict
  unchanged;
- **mixed block, both directions:** with one vector-bearing and one vector-less
  concern, focusing the vector-less row replaces the vector section with the
  `no impact vector` line and shows its region and body; focusing back restores
  the vector. Explicitly assert **no field of the previously focused concern
  survives** the transition — a stale region or body is the failure mode;
- a body/region containing `[/]` and `[dim]` renders literally and does not crash;
- hidden at 40x20 / 40x24 / 80x24 / 24x20 and shown at 40x30 / 30x24 / 24x30 /
  100x40, with `_clipped_rows` empty at each;
- every help-line key token still reaches the screen at every geometry above —
  the invariant `ConcernGuidanceContractTests` and `ConcernVerticalFitTierTests`
  already state;
- a negative control forcing the panel on at 40x20 must visibly cost the keys.

**Regression:**
- `ConcernRowVectorPackingTests`, `ConcernTradeProfilePackingTests`,
  `ConcernPickerWidthTierTests`, `ConcernVerticalFitTierTests`,
  `ConcernHelpLineBudgetTests`, `LegacyRowRenderCharacterizationTests` unchanged
  and green; `check_label_widths.__doc__`'s geometry table still accurate.
- A legacy (vector-less) block composes no panel and renders exactly as today.
- Both push paths — `narrow=True` (minimonitor) and `narrow=False` (monitor).
- `bash tests/run_all_python_tests.sh` — **read only the last line**
  (`PYTHON SUITE: …`); piping discards the status.
- Live: a real minimonitor companion pane, asserted on the captured pane — for
  the **objective** rendering properties only. The human-interpretation question
  (does a red improve arrow read as negative?) is out of reach of any capture and
  is carried by the `manual_verify_ramp_readability` follow-up.

## Risk

### Code-health risk: low

*(Re-assessed after the inline mitigations were confirmed, per `risk-evaluation.md`'s reassessment note: the pre-phase pins the call order before it is touched, and two post-phases pin the oscillation invariant and the rung-5 replace. The levels below describe the plan as approved.)*
- The panel adds a rung to a vertical-precedence ladder that **t1652** (`Ready`)
  is chartered to formalize, and lands in `_apply_size_tier`, whose call order
  t1648 documented as load-bearing three days ago. A gate placed after
  `_apply_fit_tier` instead of before it would charge rows for a hidden widget
  and lift the cap at healthy geometries · severity: medium ·
  → mitigation: inline pre-phase pin_size_tier_gate_order + inline post-phase pin_detail_gate_order
- Gating on the post-cap `available` instead of full screen height would feed
  panel visibility back into the class that sets the cap, breaking t1648's
  explicit "cannot oscillate" proof · severity: medium · → mitigation: inline post-phase pin_detail_gate_invariant_under_xshort
- `_magnitude_markup` is consumed by the packing ladder, whose last rung does a
  positional `replace("?", "", 1)` on the markup string; a ramp value containing
  `?` would corrupt it silently · severity: low · → mitigation: inline post-phase guard_magnitude_ramp_against_rung5_replace

### Goal-achievement risk: medium

*(Unchanged by the mitigations: the two substantive gaps — no panel at 40x20/40x24, and no panel for legacy blocks — are deliberately deferred to spawned follow-ups, so they remain residual in this task.)*
- The panel is refused at 40x20 / 40x24 — measured, `spare` is −4 and 0 — which
  is minimonitor's real companion geometry and the width the task names as
  "where the picker is most used". Part 2 therefore does **not** serve that
  width until t1652 decides what yields; it serves 40x30+ and narrow-but-tall
  panes · severity: medium · → mitigation: panel_at_minimonitor_40x20_after_t1652
- Honouring "a legacy block renders exactly as today" literally means legacy
  blocks keep the truncated body, so t1293's `picker_full_body_view` risk is
  discharged only for vector-bearing blocks · severity: low · → mitigation: extend_detail_panel_to_legacy_blocks
- Reusing the badge's red/yellow for magnitude makes a *high improve* red, which
  reads as "bad" until the reader learns it means "big". Chosen deliberately
  over a second vocabulary · severity: low · → mitigation: manual_verify_ramp_readability (objective half: inline post-phase pin_ramp_render_properties_live)

### Planned mitigations
- timing: pre-phase | name: pin_size_tier_gate_order | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the panel lands in `_apply_size_tier`, whose call order t1648 documented as load-bearing | desc: characterization test pinning that the `self.size`-only gate that EXISTS AT HEAD (`_apply_guidance_visibility`) runs before `_apply_fit_tier` and that the fit tier is deferred exactly on a help swap, observed passing on unmodified HEAD; its source-variant negative control must move `_apply_guidance_visibility` after the fit tier and MUST NOT reference `_apply_detail_visibility`, which has zero occurrences at HEAD and would make the control vacuous — the equivalent assertion for the new gate is the separate post-phase `pin_detail_gate_order`
- timing: post-phase | name: pin_detail_gate_invariant_under_xshort | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — gating on the post-cap `available` would break t1648's "cannot oscillate" proof | desc: assert the detail gate's verdict is identical with `xshort` forced on and off, with a negative-control variant reading post-cap `available` shown to flip between the two states
- timing: post-phase | name: guard_magnitude_ramp_against_rung5_replace | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the ladder's rung-5 positional `replace("?", "", 1)` could silently corrupt ramp markup | desc: assert no `_MAGNITUDE_RAMP` value contains `?` plus a rung-5 render test, with a `?`-seeded ramp value as the negative control
- timing: after | name: panel_at_minimonitor_40x20_after_t1652 | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — measured `spare` is -4 at 40x20 and 0 at 40x24, so the panel is refused at minimonitor's real companion geometry | desc: revisit the panel's geometry gate once t1652 lands its precedence decision so the panel becomes reachable at 40x20/40x24; depends on t1652
- timing: after | name: extend_detail_panel_to_legacy_blocks | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — t1293's `picker_full_body_view` risk is discharged only for vector-bearing blocks | desc: extend the detail panel to vector-less blocks, which this task excludes to honour the "legacy renders exactly as today" acceptance criterion
- timing: post-phase | name: pin_detail_gate_order | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the pre-phase control cannot mutate `_apply_detail_visibility`, which does not exist at HEAD | desc: assert the new detail gate runs before `_apply_fit_tier`, with a source-variant negative control that moves it after; the half of the ordering pin that can only exist once the gate does
- timing: post-phase | name: pin_ramp_render_properties_live | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the ramp's legibility claim needs evidence a capture can actually supply | desc: in a real tmux pane assert only objective rendering properties (four distinct hexes including the #808080/#6272A4 pair, high improve and high worsen identical, contrast against normal/focus/informational backgrounds, survival of the xnarrow and xshort tiers)
- timing: after | name: manual_verify_ramp_readability | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — whether a human reads a red improve arrow as negative is a judgement no captured-pane assertion can settle | desc: human Pass/Fail on the ramp in a real companion pane: are the four magnitudes separable at a glance, do high improve and high worsen read as one strength, and is a red improve arrow misread as a negative signal

---

## Implementation notes

### Correction: a composited `dim` segment DOES report a colour

The plan stated that `Style.parse("dim").color is None` and concluded that a
`dim` arrow would therefore be "invisible" to a hex-based assertion. The first
half is true; **the conclusion is not.** Measured during implementation: by the
time a `dim` segment reaches the compositor it has been blended against the
inherited foreground and reports `#999999`. The self-check written on that
premise failed, correctly, and was replaced.

The decision to give `low` a real colour is unchanged, but it now rests on a
better argument, and the test says so
(`test_dim_is_a_weight_whose_colour_is_inherited_not_chosen`): `dim` names no
colour of its own, so what it paints is a blend of whatever it inherits. The
same `dim` arrow therefore resolves *differently* on a normal row and on an
`.informational` row, whose CSS already sets `color: $text-muted`. A ramp value
has to be a fixed point, not a modifier applied to someone else's colour.

The harness self-check is now
`test_the_harness_distinguishes_styled_from_unstyled` — an unstyled arrow and a
ramp-styled one must paint differently — which is what actually proves the
measurement observes the applied style.

### Correction: the rung-5 corruption is a markup/plain divergence

The plan described the `?`-in-a-ramp-value hazard as corrupting the rung's text.
Measured, the failure is sharper and the first control written for it was
looking at the wrong field. `build`'s two sides are independent —
`seg.plain.rstrip("?")` versus `seg.markup.replace("?", "", 1)` — so a `?`
inside a style tag is struck *there*, the real `?` markers survive in the
markup, and `.plain` drops them anyway:

```
clean   plain='▲maint ▼simpl E:hi'   markup='[#6272A4]▲[/]maint ▼…'      agree
poisoned plain='▲maint ▼simpl E:hi'  markup='[#6272A4]▲[/]maint? ▼…?'   DISAGREE
```

Since `_Seg.cells` measures `.plain`, the row would budget 18 cells and render
20. The test now pins the real invariant — `Text.from_markup(markup).plain ==
plain` — and the control asserts the poisoned ramp breaks it.

### Deviation: the gate's denominator is the DECLARED 80% budget, not raw screen height

The plan specified `spare = screen_height - needed`. Implemented that way, the
panel grew to 8 rows at 24x30, pushed `needed` past the 80% cap, and set
`xshort` — breaking `ConcernVerticalFitTierTests.test_the_width_tier_is_unchanged_by_the_height_tier`,
which pins 24x30 as narrow-but-**not**-short. The test caught it.

The denominator is now `screen_height * _PICKER_MAX_HEIGHT_PCT // 100`. The
distinction the plan blurred is between the *declared* budget (a constant times
the screen size — invariant under `xshort`, because nothing reads the class) and
the dialog's *resolved* `max-height` (which is the one thing `xshort` rewrites).
Only the latter would have been circular; the former is safe **and** keeps the
panel from inflating the dialog to full height wherever it appears, which would
have hollowed out the tier's meaning.

Cost, stated plainly: the panel is refused at some geometries with raw screen
rows to spare — 40x30 (`+0`), 30x24 (`+3`), 50x30 (`+3`). Those are t1652's
bands. Pinned by `test_the_panel_cannot_by_itself_flip_the_vertical_fit_tier`.

### Deviation: the gate must also defer the fit tier while layout catches up

The plan had `_apply_detail_visibility` return nothing. Measured, that is not
enough. `_apply_measured_height_tier` sums each child's **laid-out**
`size.height`, which lags a `styles.height` write by a refresh — the same
staleness t1648 documented for the help-text swap, and it bites harder here
because the gate converges over two passes (at 24x30: 8 -> 6 -> 6). Every
fit-tier call still measured the panel as 8, summed 26 against a budget of 24,
and set `xshort`.

The gate now returns a bool and `_apply_size_tier` defers on
`help_changed or detail_changed`. It reports `True` not only when it rewrote the
style but also while `panel.size.height != target` — the pass where it changed
nothing yet layout had not applied the previous pass's value. It cannot spin:
the deferral re-runs only `_apply_fit_tier`, never the gate.

### Observed geometry (replaces the plan's predicted table)

Measured on the real modal, three vector concerns, `narrow=True`.
`needed(-panel)` is `_apply_measured_height_tier`'s own sum with the panel
excluded; `spare = budget - needed`; the panel needs `_DETAIL_MIN_ROWS + 1 = 5`.

| screen | xshort | budget | needed(-panel) | spare | panel | rows | guidance |
|---|---|---|---|---|---|---|---|
| 40x20 | 1 | 16 | 24 | -8 | no | 0 | hidden |
| 40x24 | 1 | 19 | 24 | -5 | no | 0 | hidden |
| 40x30 | 0 | 24 | 24 | +0 | no | 0 | hidden |
| 40x40 | 0 | 32 | 24 | +8 | yes | 7 | hidden |
| 50x30 | 0 | 24 | 21 | +3 | no | 0 | hidden |
| 80x24 | 1 | 19 | 22 | -3 | no | 0 | shown |
| 80x30 | 0 | 24 | 19 | +5 | yes | 4 | **yielded** |
| 80x40 | 0 | 32 | 22 | +10 | yes | 8 | shown |
| 100x40 | 0 | 32 | 20 | +12 | yes | 8 | shown |
| 120x50 | 0 | 40 | 20 | +20 | yes | 8 | shown |
| 30x24 | 1→0 | 19 | 16 | +3 | no | 0 | hidden |
| 30x30 | 0 | 24 | 16 | +8 | yes | 7 | hidden |
| 24x20 | 1 | 16 | 18 | -2 | no | 0 | hidden |
| 24x30 | 0 | 24 | 18 | +6 | yes | 5 | hidden |

80x30 is the precedence rule firing: the guidance yielded its rows to the panel,
which is the one-directional order `list > help line > panel > guidance`. At
80x40 there is room for both. At 80x24 hiding the guidance bought too little, so
it was given back and the panel refused — the bounded single retry.

### Correction: the named ramp values resolve through TEXTUAL's palette, not Rich's

The task warned about exactly this ("Rich colour names are not Textual colour
names… Pin the actual rendered colour, not the name") and the plan then repeated
the wrong numbers, because the measurement was taken with
`rich.style.Style.parse` in isolation rather than in the surface the markup
actually renders on. Measured in a real Textual app and confirmed in a real
tmux pane:

| magnitude | style | plan claimed | **actually renders** |
|---|---|---|---|
| high | `bold red` | #800000 | **#ff0000** + bold |
| medium | `bold yellow` | #808000 | **#ffff00** + bold |
| low | `#808080` | #808080 | #808080 |
| unspecified | `#6272A4` | #6272a4 | #6272a4 |

The ramp is unaffected in substance — brighter, if anything — but the tests had
only asserted *distinctness* and *parity*, which is why the wrong constants
survived to this point. `test_the_resolved_colours_are_pinned` now pins all four
as they composite, and `test_the_named_values_are_not_the_bare_rich_colours`
keeps the trap visible by asserting the bare-Rich values are the ones NOT on
screen.

### Live verification (real tmux pane, not `App.run_test`)

100x40 — the panel renders, and the ANSI capture shows the ramp resolving per
entry: `verification (medium)` as `38;2;255;255;0` bold, `simplicity (low)` as
`38;2;128;128;128`, `performance (unspecified)` as `38;2;98;114;164`. Three
distinct colours on three adjacent lines, with the full dimension names and
rubrics the row cannot show.

40x20 — the real minimonitor companion geometry. The panel is **absent**, every
help key token (`[r] reject` … `[Esc] cancel`) reaches the pane, and both dialog
borders are intact. The row still degrades to `▲corr +1 ▼simpl +1 E:lo`. So the
panel does not regress the geometry the picker is most used at; it simply does
not appear there, which is the measured trade recorded above.

Contrast against the row states that recolour their own text
(`.informational` / `.rejected`, both `color: $text-muted`) is covered by
`test_the_ramp_survives_the_row_states_that_recolour_their_text` — automated
rather than asserted live, since it is objectively checkable.

---

## Post-Review Changes

### Change Request 1 (2026-09-01 10:45)

- **Requested by user:** three blocking review concerns — (1) `_wrap_cells`
  silently dropped source characters on wide glyphs; (2) the panel broke its own
  content contract at some geometries where it was nonetheless displayed;
  (3) the gate-denominator change reduced coverage further than the approved
  plan recorded, and needed explicit acceptance rather than a silent deviation.
- **Changes made:** all three verified as real and fixed; see below.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `tests/test_concern_picker_modal.py`,
  `website/content/docs/workflows/shadow-agent.md`,
  `website/content/docs/tuis/minimonitor/how-to.md`.

**(1) `_wrap_cells` lost text on wide glyphs — CONFIRMED, fixed.**
Reproduced exactly as reported: `_wrap_cells("插件配置模块", 3, 5)` returned
`['插 ', '配 ', '模 ']`, losing `件`, `置` and `块`. The cause is that
`set_cell_size` **pads** to an exact cell count, so `set_cell_size(src, 3)` is
`"插 "` — two characters for a three-cell result — and advancing the source by
that `len()` skipped the next character. New `_take_cells(text, budget)` splits
on real characters and returns the consumed source, so the wrap is lossless by
construction. `ConcernDetailWrapTests` pins losslessness across widths 2–5 for
CJK, mixed and ASCII input, pins the primitive directly, and covers the
single-glyph-wider-than-the-line case (emitted over budget rather than dropped,
which also terminates the loop).

**(2) The panel broke its own contract where it was displayed — CONFIRMED, fixed.**
Two distinct failures, both measured:
- at 80x30 the four-row budget was entirely consumed by vector and metadata
  lines, so the region and body — the two fields the row clips hardest, and the
  t1293/t1426 risk this task carries — were **absent altogether**;
- at 24x30 the dimension name was clipped mid-word (`verification (medi…`) and
  the region ellipsized, contradicting the full-name and un-ellipsized-region
  goals while still advertising a detail panel.

Three changes: rows are now **reserved** for the metadata line, the region and
at least one body line (`_DETAIL_RESERVED_ROWS`) before the vector may spend
anything, and surplus rows go to the **region first**; the vector yields with an
explicit `+N` marker instead. Width is handled by a two-rung ladder rather than
clipping — full (`name (magnitude) — rubric`) above
`_DETAIL_FULL_CONTENT_CELLS`, compact (`name` alone, magnitude carried by the
arrow colour) above `_DETAIL_MIN_CONTENT_CELLS`, and no panel below that. Both
floors are **derived from `CONCERN_DIMENSIONS`**, so a longer dimension name
moves them instead of silently clipping. The `@` region marker is no longer
repeated on wrapped continuation lines.

**(3) Scope — explicitly accepted, not silently deviated.**
The strict-contract fix initially pushed the floor to 48 columns, which would
have removed the panel from every companion-pane width. Put to the user with the
measured table; the user chose the **two-tier content ladder**, restoring
coverage from 24 columns up with honest degradation. The panel now shows at
24x30, 30x30, 40x40, 80x30, 100x40, 120x50 and is refused at 40x20, 40x24,
40x30, 50x30, 80x24, 24x20.

Residual, recorded rather than papered over: at 24x30 the region needs four
wrapped rows and the panel has three, so it is truncated **with a visible
ellipsis** — pinned by `test_where_the_region_cannot_fit_the_truncation_is_visible`,
which is the negative control for
`test_the_region_is_shown_in_full_wherever_the_rows_allow_it`.

**Live re-verification after the fixes (real tmux pane, 30x30).** The compact
tier renders `▲correctness`, `▲verification`, `▼simplicity`, `▼performance` —
four full dimension names — plus `@ monitor_shared.py:2795` and the body, with
every key hint still on screen and both borders intact. The row immediately
above shows `▲corr ▼simpl E:lo`, so the panel's value is visible in the same
capture: the row abbreviates, the panel spells it out.

### Change Request 2 (2026-09-01 11:05)

- **Requested by user:** (1) the panel escaped the region *before* wrapping it,
  so a narrow wrap could split an escape sequence and a producer-controlled
  region could crash the picker; (2) the ramp's leading comment still quoted the
  bare-Rich colours the correction below had already superseded.
- **Changes made:** both verified as real and fixed.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `tests/test_concern_picker_modal.py`.

**(1) Escape-before-wrap crashed the picker — CONFIRMED.** Reproduced exactly as
reported: a region of `[dim]abcdefghijk[/]` at 24x30 raised
`MarkupError: auto closing tag ('[/]') has nothing to close` inside
`Static.update`. `_escape_markup` turns `[` into `\[`, and `_wrap_cells` then
split the escaped text as `['\[dim]abcdefghijk\', '[/]']` — the backslash ended
one line and the next opened with a live `[/]`.

This is the t1636_4 failure class reintroduced through the panel's own wrapping,
and the file already states the rule it broke: `_ConcernRow._region_seg`'s
docstring says escaping "is applied only to the markup half, **after**
truncation". The region now wraps RAW and each completed line is escaped;
measuring raw also fixes a width miscount, since a backslash occupies a cell in
the escaped string and none on screen.

**The same ordering bug was present on the metadata line** and was not in the
report: `disposition` and `verdict` were escaped individually and the *joined*
string was then clipped, so `_clip_cells` could cut a `\[` pair the same way.
Both are now raw through the join and the clip, escaped once at the end.

`ConcernDetailMarkupSafetyTests` covers it: the reported region case at four
geometries (24x30 is the load-bearing one — the only width where the region
wraps), literal rendering rather than mere survival, hostile body/disposition/
verdict together, a swept bracket-length fixture so the split is guaranteed to
land inside an escape pair at some point, and a **negative control** that
asserts the rejected ordering genuinely raises `MarkupError` while the shipped
one is lossless and literal.

**(2) Stale ramp comment — CONFIRMED, corrected.** The leading sentence quoted
`#800000, #808000, #808080` while the mapping, the note beneath it and the tests
all carried the real Textual-rendered values. It now names #ff0000 / #ffff00 /
#808080 and points at the palette note. The only surviving mention of the
bare-Rich values is the deliberate contrast in that note ("NOT the #800000 /
#808000 that `rich.style.Style.parse` reports"), which is the point of it.

### Change Request 3 (2026-09-01 11:20)

- **Requested by user:** `_detail_text`'s docstring still described the original
  row-priority order (vector first, body yielding first) while the shipped
  implementation deliberately does the opposite.
- **Changes made:** CONFIRMED and corrected. The docstring said "The body yields
  first", which is now false in the strongest way — the **vector** yields, and
  the body is one of the three reserved items. A stale docstring is how the
  measured defect gets reintroduced by a later well-meaning edit, so it now
  states the allocation policy, *why* the vector is the item with a usable
  fallback (the row already shows its first entry per side, while it ellipsizes
  the region and clips the body), and explicitly warns that reversing the order
  re-creates the four-row failure. Also folded in the raw-then-escape ordering
  rule from Change Request 2, which was equally load-bearing and equally
  undocumented at that call site.
- **Also swept the plan itself.** The "Content" section above carried the same
  superseded ordering; it now opens with a blockquote pointing at Change Request
  1 and saying not to restore it. The reviewer's point is that stale
  documentation misleads a future change — that applies to this plan as much as
  to the source.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `aiplans/p1651_concern_magnitude_color_and_focused_detail_panel.md`.

### Change Request 4 (2026-09-01 11:35) — NOT REPRODUCED

- **Requested by user:** "Informational/rejected row CSS overrides the
  magnitude-arrow color: the live picker test observes #363636 where high must
  be #ff0000."
- **Outcome:** investigated thoroughly; **could not reproduce**. The guard was
  strengthened anyway, because the *class* of defect is real even though this
  instance was not observed.

**What was measured.** Every improve arrow rendered `#ff0000` and every worsen
arrow `#808080`, in all of:

| context | result |
|---|---|
| real tmux pane, 100x40, actionable **and** informational rows | `▲` `#ff0000` x2, `▼` `#808080` x2 |
| `run_test`, state `none` / `forward` / `rejected` / `spinoff`, both rows | `▲` `#ff0000` x2, `▼` `#808080` x2 each |
| picker under a pushed modal | arrows are off-screen entirely; no colour to observe |

`#363636` was not observed in any of them. The mechanism explains why: Rich
markup sets an explicit colour on the segment, which beats CSS `color:`
inheritance from the row — so `.informational` / `.rejected` recolour the row's
own text and leave the arrows alone.

`monitor_shared.py:3148`, the cited line, is inside `_ConcernRow.render`'s
docstring about the one-line vs multi-line layout choice — it is not row CSS.
The `_ConcernRow` CSS block is at ~2980-3010.

For the record, `#363636` sits between the theme's `background-lighten-2`
(`#313131`) and `background-lighten-3` (`#414141`), which is the signature of a
colour blended toward the background — a `text-opacity` / tint / backdrop
effect rather than a `color:` override. Nothing in this modal applies one.

**What changed anyway.** `test_the_ramp_survives_the_row_states_that_recolour_
their_text` was replaced by
`test_the_ramp_survives_every_row_state_that_recolours_its_text`, which sweeps
**state x row-class** (four dispositions across an actionable and an
informational row, asserting the two rows genuinely differ in class) instead of
sampling one combination. A one-case test could not have seen a state-specific
regression; this one can.

If the `#363636` observation came from a specific terminal, theme, or geometry,
that context is what is needed to take it further — the current evidence says
the contract holds.

### Change Request 5 (2026-09-01 12:10) — scope reduction after visual review

- **Requested by user, after testing the build visually:** "I would drop the
  concern preview from the detail panel: show only the concern dimensions",
  and "also don't show the explanation of the dimension inline with the
  dimension value. drop it from the detail pane."
- **Changes made:** the panel is now **dimensions only** — one line per impact
  entry, coloured arrow, full dimension name, and the magnitude as a word where
  the width allows. No body preview, no region, no effort/disposition/verdict
  line, no inline rubric.

**Why this is a simplification and not a loss.** The row directly above the
panel already carries the region and the disposition; repeating them a few rows
down read as duplication rather than detail. The rubric, repeated on every
entry, dominated the panel and buried the names it exists to surface. What is
left is exactly what the row cannot show: it degrades to ONE improve entry, ONE
worsen entry and 5-cell labels, so every additional entry and every full name is
missing from it by construction.

**What was removed with it**, rather than left as dead weight:

- `_wrap_cells`, `_take_cells`, `_mark_overflow` — the wrapping machinery (and
  its CJK-losslessness fix) existed only for the body and region. Deleted, along
  with `ConcernDetailWrapTests`.
- `_DETAIL_RESERVED_ROWS` and the whole reserve-and-surplus allocation.
- The `rubric_for` import; `tests/test_concern_dimensions.py` now records that
  the accessor has **no** production caller and why, so the next reader does not
  read the absence as an oversight.
- The `display_body()` read, and with it the `EXPECTED_ACCESSES` row in
  `tests/test_concern_body_display_contract.py`. The guard confirmed the removal
  (a declared read that vanishes fails just as loudly as an undeclared one).

**Two improvements the simplification enabled.** The content is now a small,
known line count, so the panel is sized to what it draws instead of taking every
spare row (`_detail_lines` is split out for the gate to count), and entries that
do not fit are dropped with a `+N` marker rather than a bare ellipsis.
`_DETAIL_MIN_ROWS` drops from 4 to 2 — one improve and one worsen entry — which
widens where the panel fits: it now shows at **30x24** and **30x30**, which the
previous build refused.

Measured after the change — shown at 24x30, 30x24, 30x30, 40x40, 80x30, 100x40;
refused at 24x20, 40x20, 40x24, 40x30, 80x24.

**Upstream defect found and fixed while sweeping for this.** See the Final
Implementation Notes.

**Live re-verification (real tmux pane, 100x40).** The panel renders
`▲correctness (high)` / `▼simplicity (low)`; the ANSI capture shows three improve
arrows (two rows plus the panel) all at `38;2;255;0;0` and three worsen arrows
all at `38;2;128;128;128` — so the ramp holds across both surfaces and on the
`.informational` row.

---

## Final Implementation Notes

- **Actual work done:** two changes to `ConcernPickerModal` in
  `.aitask-scripts/monitor/monitor_shared.py`.
  **(1)** Magnitude is colour-encoded. `_MAGNITUDE_RAMP` sits beside
  `_CONCERN_BADGE` as the single retune site and `_magnitude_markup` became a
  lookup — high `#ff0000`+bold, medium `#ffff00`+bold, low `#808080`,
  unspecified `#6272A4` off the ramp. Zero extra cells, so every packing suite
  passes untouched.
  **(2)** A focused-concern detail panel (`Static#concern-detail`) between the
  list and the help line, composed only for a vector-bearing block, seeded in
  `on_mount` and followed via `on_descendant_focus`. It renders the impact
  vector and nothing else: one line per entry, full dimension name, magnitude as
  a word where the width allows, `+N` for entries that do not fit. Visibility
  and height come from `_apply_detail_visibility`, gated on measured geometry
  against the declared 80% budget.

- **Deviations from plan:** five, each recorded in full above with the
  measurement that forced it — the gate denominator (declared budget, not raw
  screen height); the fit-tier deferral while layout catches up; the two-tier
  width ladder; the raw-then-escape ordering; and the CR5 scope reduction to
  dimensions only, which removed the body, region, metadata line and rubric
  along with `_wrap_cells` / `_take_cells` / `_mark_overflow`,
  `_DETAIL_RESERVED_ROWS`, the `rubric_for` import and the `display_body()`
  read.

- **Issues encountered:**
  - The ramp's named values resolve through **Textual's** palette, not Rich's —
    the exact trap the task warned about, reproduced because the first
    measurement used bare `rich.style.Style.parse`. Now pinned as rendered.
  - Sizing the panel from raw screen height flipped `xshort` at 24x30 and broke
    a t1648 contract; the fit tier separately read a **stale** panel height,
    because `styles.height` lags layout by a refresh.
  - Escaping before wrapping split a `\[` pair and crashed the modal with
    `MarkupError` — the t1636_4 class, reintroduced by ordering. The same bug
    was present on the metadata line and was fixed with it. Both surfaces are
    gone under CR5, but the ordering rule now lives in the docstring.
  - An early revision let the vector consume the whole row budget, leaving no
    region and no body at four rows — caught by review, fixed by reserving, then
    made moot by CR5.
  - One full-suite run failed on
    `test_minimonitor_startup_input_latency.py::MountWindowProbeTests::test_mount_returns_while_the_window_probe_is_still_blocked`.
    Unrelated to this change (a latency assertion), passed 3/3 in isolation and
    on a clean re-run; the box was at load 3.2 with concurrent agents. Recorded
    rather than silently re-run.

- **Key decisions:** the ramp reuses the dialog's existing heat vocabulary
  deliberately (`derive_priority` makes the badge the max improve magnitude, so
  badge and arrow are the same fact rendered twice); `low` is an explicit grey
  rather than the badge's `dim`, because `dim` names no colour and blends with
  whatever it inherits; the panel is always-on and geometry-gated rather than
  key-toggled, which costs no help-line token; and its height is an explicit
  runtime `styles.height` with no `auto` and no `max-height`, so a focus change
  can never move the vertical budget.

- **Upstream defects identified:**
  `.aitask-scripts/monitor/monitor_shared.py:2811 — _entry_seg interpolated an unknown dimension name into Rich markup unescaped, so a producer-supplied name of five or more '[' characters truncates to '[[[[[' whose dangling tag swallows the arrow's '[/]', raising MarkupError and taking the whole picker down at narrow widths (pre-existing since t1636_4; fixed in this commit by escaping the markup half only, leaving the plain half raw for cell counting, with a swept regression test).`

### Change Request 6 (2026-09-01 12:45)

- **Requested by user:** (1) `_detail_text` appended the `+N` marker to an
  already full-width line without reserving cells, so the line could overflow
  and Rich would fold it — undermining the geometry and key-budget guarantee;
  (2) the visibility-gate docstring still claimed the panel "yields rather than
  degrades", contradicting the compact rung CR5 kept.
- **Both CONFIRMED and fixed.**

**(1) The marker overflowed.** Reproduced exactly as reported: five entries at
width 30 in one row rendered `▲maintainability (unspecified) +4` at **33** cells.
Every entry line is already clipped to the full width, so appending the marker
afterwards overflows whenever the last surviving entry is a long one. Rich folds
that to a second row, so the panel draws more rows than its declared
`styles.height` — which is the number `_apply_measured_height_tier` sums, so the
overflow propagates into the cap decision and the help line's budget.

Fixed structurally rather than by clamping after the fact. `_detail_vector_lines`
became `_detail_parts`, returning raw `(prefix_markup, prefix_cells, text)`
triples instead of finished lines, with `_detail_render(part, budget)` doing the
clip-then-escape. `_detail_text` now **re-renders the final surviving entry
against `width - cell_len(marker)`** instead of bolting the marker on. Returning
raw text is what makes that possible: re-clipping an assembled markup string
would cut a tag, which is the hazard Change Request 2 was about.

Guarded by `test_the_overflow_marker_never_pushes_a_line_past_the_width`, swept
over width 16-89 x rows 1-6 (the overflow only appears when the marker lands on
a line already at the limit, so a sampled fixture would miss it), plus
`test_the_marker_is_still_present_when_entries_are_dropped` so the fix cannot be
"implemented" by dropping the marker.

**(2) Stale gate docstring.** It described the width floor as an all-or-nothing
promise, which was true of the pre-CR5 design and is not true now: between
`_DETAIL_MIN_CONTENT_CELLS` and `_DETAIL_FULL_CONTENT_CELLS` the panel
deliberately degrades to the name alone. The docstring now says which floor the
gate enforces and what happens above it, so a future edit cannot read it as
licence to delete the compact rung. It also dropped a stale geometry (30x24) from
its example list — that geometry shows the panel since CR5 lowered
`_DETAIL_MIN_ROWS`.

### Change Request 7 (2026-09-01 13:05)

- **Requested by user:** (1) the CR6 marker-reserve fix can clip a dimension
  name — at 16x2 with five entries the second line rendered
  `▲maintainabi… +3`, violating the panel's core full-name contract; (2) the
  compact-rung comment still described rung 1 as "name + magnitude word +
  rubric" after CR5 removed inline rubrics.
- **Both CONFIRMED and fixed.**

**(1) The CR6 fix traded one contract violation for another.** Reproduced
exactly once the long name is placed where it survives last —
`▲maintainabi… +3` at 16x2, and `▲maintainability (unspecif… +3` at 30x2.
Reserving the marker's cells kept the line inside `width`, but bought that by
abbreviating the one thing the panel promises never to abbreviate.

The rule is now a **tie-break rather than an unconditional reserve**: the marker
is inlined only when the last surviving entry still fits *whole* beside it;
otherwise that entry is dropped too and the marker takes a row of its own. Fewer
names at the tightest geometries, but every name shown is complete and the count
stays honest about what was dropped.

Four invariants now hold together, and each had been broken on its own by a fix
for one of the others:

1. no line exceeds the panel width;
2. no more lines than the declared height;
3. no dimension name is ever abbreviated;
4. a `+N` marker is present whenever entries were dropped.

Verified exhaustively during implementation over **all 2520 orderings** of five
dimension names x widths 16-59 x rows 1-5: zero violations of any of the four.
The shipped guard (`test_the_truncated_panel_holds_all_four_invariants`) sweeps
five representative orderings — chosen to place the longest name in each
position, since every one of these defects only appears when the long name lands
on the last surviving line — plus two tests pinning both sides of the tie-break,
so "marker always takes a row" cannot pass either.

**(2) Stale rung comment.** `_DETAIL_MIN_CONTENT_CELLS`'s doc-comment still
described a three-part rung 1. Corrected, with a pointer to `_detail_parts` and
a note that the rubric was a rung that CR5 removed — so its absence reads as a
decision rather than an omission.

### Change Request 8 (2026-09-01 13:25)

- **Requested by user:** the CR7 tie-break only tested whether the last entry's
  *current* form fits beside `+N`; it never retried the compact rung against the
  reduced budget. At 30x2 with five `maintainability` entries it rendered one
  full entry and `+4`, although `▲maintainability +3` fits in 19 of 30 cells —
  hiding a full dimension name, which is the thing the panel exists to recover.
- **CONFIRMED and fixed** — and the fix surfaced a second problem worth stating.

**The root cause was structural.** `_detail_parts` chose the rung ONCE from the
panel width and baked it into every line's text, so the line that shares its row
with the marker had no way to fall back. Parts now carry **both** forms as raw
text — `(prefix_markup, prefix_cells, full_text, compact_text)` — and
`_detail_form(part, budget)` returns the widest that fits, or `None` when not
even the name does. The tie-break asks `_detail_form` against the reduced
budget, so an entry whose full form will not fit beside the marker is **kept
compact** instead of dropped.

**The obvious version of that fix was worse, and was rejected.** Letting *every*
line take the widest form that fits its own budget renders
`▲correctness (high)` beside `▲verification` — and since `(unspecified)` is a
real value on this surface, a reader cannot tell the second from a genuinely
unpriced dimension. A missing parenthetical must not be able to mean two
different things. So the rung stays **uniform for the panel's ordinary lines**
(`_detail_uses_full_form`), and only the marker line may fall back — where the
`+N` sitting beside it explains why that line is shorter.

Six invariants now hold together, verified exhaustively over **all 2520
orderings** of five dimension names x widths 16-59 x rows 1-5, with zero
violations of any: no line over width; no more lines than the declared height;
no abbreviated dimension name; a `+N` whenever entries were dropped; **no entry
dropped whose compact form would have fitted beside the marker**; and **no mixed
rungs among ordinary lines**. The last two are new guards
(`test_the_marker_line_falls_back_a_rung_rather_than_dropping_an_entry`,
`test_ordinary_lines_all_use_the_same_rung`, plus check (5) folded into the
existing sweep).
