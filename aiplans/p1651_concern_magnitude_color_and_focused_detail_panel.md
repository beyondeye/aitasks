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
