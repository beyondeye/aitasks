---
Task: t1638_harden_tui_multiselect_mark_rendering.md
Branch: (none — current-branch mode)
Base branch: main
Output branch: main
---

# t1638 — Harden TUI multi-select mark rendering

## Context

The repo-wide multi-select mark from t1004 — checked `☑` / unchecked `☐`,
marked = bold yellow — renders the **checked** mark almost invisibly on at least
one supported desktop, in both the minimonitor concern picker and the board's
task-selection marks. The unchecked mark is unaffected.

The trigger was environmental; the fragility is this repo's. Measured by parsing
each supported Nerd Font's `cmap` table and by `fc-match -s`:

| glyph | in JetBrainsMono NF | in Caskaydia NF | fallback rank 1 → 2 |
|---|---|---|---|
| `☑` U+2611 | no | no | Adwaita Mono → **Noto Color Emoji** |
| `☐` U+2610 | no | no | Adwaita Mono → Noto Sans Symbols 2 |

**No supported Nerd Font covers either codepoint**, so both are resolved by
system font fallback. `☑` is emoji-capable, so a fontconfig change promoted Noto
Color Emoji to rank 2 for it — a colour-bitmap glyph ignores the requested
foreground and paints its own dark colours on a dark background. `☐` is not
emoji-capable, ranks the emoji font last, and keeps honouring `#6272A4`. That
asymmetry is the entire bug.

**The task text proposed `✔` U+2714 as the replacement. Measurement rejects it:**
`✔` resolves to `Adwaita Mono → Noto Color Emoji` exactly like `☑`, so it would
reintroduce the identical bug (it is also absent from CaskaydiaMono NF). The
other suggestion, the U+FE0E (VS15) text-presentation selector, is also
rejected: VS15 is in **neither** font's cmap, so honouring it is a property of
the terminal's shaper — the same unverifiable environment-dependence the task
exists to remove.

Two further defects surfaced while measuring, both already shipping:

- **The four "bold yellow" marks are three different colours today.** Rich
  resolves `yellow` to `#808000` (ANSI-3 olive); Textual resolves it to
  `#FFFF00`. So `brainstorm_dag_display.MARK_CHECKED_STYLE =
  Style(color="yellow", bold=True)` — the only Rich-rendered mark — has been
  painting a dull olive while the three Textual-markup surfaces painted pure
  yellow. Moving to an explicit hex fixes this for free.
- **The unchecked mark has three different stylings**: `#6272A4` (board CSS,
  DAG, brainstorm list), and **unstyled** at `monitor_shared.py:3244`.

### Decisions taken with the user

1. **Selection mark → `✓` U+2713 (checked) / `□` U+25A1 (unchecked).** `✓` is the
   best-covered candidate in the repo's glyph space: present in both Nerd Fonts,
   non-emoji, and fallback rank 1 is the primary terminal font itself. `□`
   preserves the always-on empty-box affordance t1004 chose deliberately
   ("selectable but unselected") and keeps the dot t1004 rejected off the table.
   - **Accepted residual, explicitly chosen:** `□` is East Asian Width
     *Ambiguous*, where today's `☐` is *Neutral* — it occupies two cells in
     terminals configured wide-ambiguous, while Rich budgets one. The user
     accepted this after being shown the narrow-safe alternative (`▫` U+25AB).
     It is the same exposure the repo already carries for `●` and `◆` on the
     very same monitor rows. Pinned as a recorded residual, not silently taken.
2. **`★`/`☆` is NOT changed here.** It has the identical coverage gap but is not
   broken today (it falls back to Noto Sans Math, not an emoji font, so colour
   is still honoured). It keeps its glyphs and its deliberately distinct
   bold-white/dim styling; a **named follow-up** re-evaluates it if real
   rendering trouble appears. This satisfies AC 6's "deliberately deferred to a
   named follow-up" branch.
3. **Colour authority → the repo's existing Dracula palette**
   (`lib/board_columns.py:125-134`): checked becomes bold `#F1FA8C` ("Yellow"),
   unchecked stays `#6272A4` ("Gray").

---

## Design

### The authority: `.aitask-scripts/lib/mark_glyphs.py` (new)

Named after `lib/followup_kinds.py`, the existing precedent for a `lib/`
vocabulary module owning presentation columns (glyph + colour) and imported by
both the board and `monitor_shared`. **Not** `lib/agent_marks.py` — that is the
store/expiry policy for the `★` mark and its docstring pins "deliberately free
of Textual, tmux and subprocess imports".

**Zero module-level imports**, holding the line `followup_kinds.py` records
("the board imports this module on the PyPy fast path"). The one caller needing
a `rich.style.Style` gets it from a factory that imports Rich inside the
function body. No cycle risk: the module imports nothing from the repo.

Surface:

```python
MARK_CHECKED   = "✓"   # ✓ CHECK MARK
MARK_UNCHECKED = "□"   # □ WHITE SQUARE
MARK_CHECKED_COLOUR   = "#F1FA8C"   # Dracula "Yellow"
MARK_UNCHECKED_COLOUR = "#6272A4"   # Dracula "Gray"
MARK_CHECKED_STYLE    = f"bold {MARK_CHECKED_COLOUR}"
MARK_UNCHECKED_STYLE  = MARK_UNCHECKED_COLOUR

#: The font families this repo's glyph vocabulary is VERIFIED against. Nothing
#: in the repo declared this before t1638 — "the supported Nerd Fonts" was an
#: unwritten assumption, which is precisely how a codepoint outside all of them
#: became the convention. Coverage against every family here is asserted from a
#: checked-in manifest; see tests/data/font_coverage.json.
SUPPORTED_FONTS = ("JetBrainsMono Nerd Font", "CaskaydiaMono Nerd Font")

GLYPH_EVIDENCE = {...}   # glyph -> why it survives font fallback (AC 5)

def mark_glyph(marked)  -> str      # bare glyph
def mark_style(marked)  -> str      # bare style, for f"[{...}]"
def mark_markup(marked) -> str      # "[bold #F1FA8C]✓[/]"
def rich_mark_style(marked)         # rich.style.Style; imports Rich in-body
```

The module docstring carries the **codepoint policy** — a glyph is admissible
only if every supported Nerd Font covers it *and* no emoji font claims it — plus
the measured rationale, the rejection of `✔` and VS15, and the accepted
Ambiguous-width residual for `□`.

The hexes are **restated**, not indexed out of `PALETTE_COLORS`: that list is a
user-facing picker whose order is presentation, and deriving a semantic colour
from a picker index would let a reorder repaint every mark in the repo. The
agreement is asserted instead (§ ratification tests).

### The board CSS problem → make CSS layout-only

`aitask_board.py:7983-7986` already documents this exact pattern three lines
below the mark rules: `.task-followup-glyph` deliberately carries no `color:`
because "a `.fk-<kind>` rule here would be a second authority that CSS cannot
keep in sync with a Python dict."

The same reasoning applies with more force here — CSS cannot express the *glyph*
at all, so glyph-in-Python + colour-in-CSS splits one mark across two files. So:
delete the `.task-marked` colour rule, reduce `.task-mark` to layout, keep
`.task-marked` as a **state hook with no declarations**, and paint via
`mark_markup()` in the `Label`.

Verified against the installed Textual 8.2.7 that this costs **zero** changes to
the existing board tests: `Content.from_markup("[bold #F1FA8C]✓[/]").plain ==
"✓"`, so all seven `label.render().plain` assertions in
`tests/test_board_marking.py` pass unmodified, and a Textual class name needs no
matching CSS rule, so the `assertIn("task-marked", label.classes)` assertions
pass too. Only the assertion *message* at line 189 ("the bold-yellow class")
becomes untrue and must be reworded.

The rejected alternative — f-string interpolating the constants into `CSS` —
would require doubling every `{`/`}` in a several-hundred-line stylesheet, and
would still leave the glyph/colour split it was meant to close.

### The drift guard: `tests/test_mark_glyphs_single_source.py` (new)

Shaped on `tests/test_backlog_view_is_single_sourced.py` (AST, not grep, so a
docstring or comment cannot trip it), over a **declared consumer list** — never
repo-wide, see Risk 1.

- **Rule 1 — no re-declaration.** Flag an `Assign`/`AnnAssign` to `MARK_CHECKED`
  / `MARK_UNCHECKED` / `MARK_*_STYLE` whose RHS is a *literal*. **Allow** a
  `Name`/`Attribute`/`Call` RHS — that is the intended re-export/derivation form
  (`MARK_CHECKED_RICH_STYLE = rich_mark_style(True)`). This is the refinement
  over the `backlog_view` guard, which bans the name outright.
- **Rule 2 — no literal glyph in consumer code.** Walk every `str` `ast.Constant`,
  skipping docstrings by identity; flag any containing `✓` or `□` unless listed
  in `ALLOWED_LITERALS` with a stated reason. This is what catches the two shapes
  that actually shipped — `widgets.py:419` and `monitor_shared.py:3244` are
  literals *inside methods*, invisible to a module-level scan.
- **Rule 3 — the positive half, and it must be a *used* import.** Each consumer
  must `from mark_glyphs import …` **and every name it imports must have a
  `Load` occurrence in the file**, and at least one of them must be a *rendering*
  helper (`mark_markup` / `rich_mark_style`). A bare "does it import the module"
  check accepts a decorative unused import sitting above hand-rolled rendering —
  the guard would then be green while the defect is present. Without Rule 3 at
  all, deleting every local copy *and* every use would pass Rules 1–2 vacuously.
- **Rule 4 — no self-composed markup. This is the rule that closes the colour
  hole.** A bare `MARK_CHECKED` / `MARK_UNCHECKED` `Name` may **not** appear
  inside a `JoinedStr` (f-string) or a string-building `BinOp`. Rules 1–3 alone
  still permit `f"[bold #FF0000]{MARK_CHECKED}[/]"` — glyph correctly sourced
  from the authority, colour hand-rolled — which is exactly the drift AC 2
  forbids, and it is unreachable by a glyph scan or an import check. Rule 4 makes
  the *only* way to render a mark be `mark_markup()` / `rich_mark_style()`.
  Legitimate bare-constant uses (comparison, membership, `len()` width maths) are
  untouched because none of them builds a string. Verified that every planned
  consumer complies: the board and `monitor_shared` call `mark_markup(...)`, the
  DAG calls `rich_mark_style(...)`, and `widgets.py`'s
  `f"{mark_markup(self.marked)} "` interpolates a `Call`, not a `Name`.
  - Colour literals are *not* separately scanned, and Rule 4 is why that is now
    sound rather than a gap: `#6272A4` legitimately appears ~8 times in
    `brainstorm_dag_display.py` for unrelated things, so a hex ban is unworkable —
    but with Rule 4 in place a consumer has no way to attach any colour of its own
    to a mark.
- **Anti-vacuity.** Every path in `CONSUMERS` exists (guards a rename); every
  `ALLOWED_LITERALS` entry still occurs in its file (guards a stale exception).
- **Negative controls** (tempdir copy + append): a literal re-declaration is
  flagged; an *alias* re-declaration is **not**; a glyph literal nested in a
  function is flagged; a commented-out one is **not**; deleting an import fails
  Rule 3; **an unused `mark_glyphs` import fails Rule 3**; and
  **`f"[bold #FF0000]{MARK_CHECKED}[/]"` fails Rule 4** while
  `f"{mark_markup(True)} "` does not.
- **Documented boundary, asserted rather than claimed.** `chr(0x2611)` and other
  runtime construction are out of scope (ship a test asserting the scan is clean
  for it, mirroring the `backlog_view` boundary test); `"☑"` *is* caught,
  because Python resolves the escape at parse time. A re-fork under a different
  name (`_my_mark = "✓"`) is caught by Rule 2 but not Rule 1. Non-consumer files
  are out of scope **by construction, and the reason is named** — see Risk 1.

### Making "a future change reintroduces a bad codepoint" executable (AC 5)

**`fc-list` cannot be the oracle, and an `fc-list` tier is worse than none.**
`fc-list :charset=<cp>` answers "does *some* locally installed family cover
this" — not the question. A machine with DejaVu but neither Nerd Font would
report full coverage while both supported deployments fall back; behind a
`skipUnless`, CI never runs it at all. And it is *actually wrong*: during this
investigation `fc-list` reported JetBrainsMono NF as **not** covering U+2714
while that font's own `cmap` contains it. So coverage is established from a
**checked-in, per-family manifest**, and `fc-list` is dropped entirely.

**`tests/data/font_coverage.json`** (new) — the measured evidence, per family:

```json
{ "generated_by": "tests/tools/regen_font_coverage.py",
  "fonts": { "JetBrainsMono Nerd Font": {"file": "…", "version": "…"},
             "CaskaydiaMono Nerd Font": {"file": "…", "version": "…"} },
  "coverage": {
    "2713": {"JetBrainsMono Nerd Font": true,  "CaskaydiaMono Nerd Font": true },
    "25A1": {"JetBrainsMono Nerd Font": true,  "CaskaydiaMono Nerd Font": true },
    "2611": {"JetBrainsMono Nerd Font": false, "CaskaydiaMono Nerd Font": false },
    "2714": {"JetBrainsMono Nerd Font": true,  "CaskaydiaMono Nerd Font": false },
    "2605": {"JetBrainsMono Nerd Font": false, "CaskaydiaMono Nerd Font": false } } }
```

**`tests/tools/regen_font_coverage.py`** (new) — regenerates it by parsing each
font's `cmap` table directly (a ~40-line pure-Python format 4/12 reader; **no
`fontTools` dependency**, and deliberately not `fc-list`). It records the
*rejected* codepoints alongside the ratified ones, so the manifest is falsifiable
on its face.

`class CodepointPolicyTests` — **unconditional, offline, needs no font installed**:

- `test_every_ratified_glyph_is_covered_by_every_supported_font` — for each mark
  glyph the manifest must carry an entry for **every** family in
  `SUPPORTED_FONTS`, all `true`. A **missing** entry is a failure, not a pass, so
  adding a glyph without regenerating the manifest fails. This is AC 5 stated
  exactly, and it is per-family rather than "some font somewhere".
- `test_the_manifest_is_not_vacuous` — `2610, 2611, 2605, 2606` must be present
  and `false` for **both** families, and `2714` `false` for at least one. Proves
  the manifest can express "not covered" and that the generator discriminates
  instead of emitting `true` everywhere.
- `test_the_manifest_covers_exactly_the_supported_fonts` — the manifest's family
  set equals `SUPPORTED_FONTS`, so dropping a family from either side fails.
- `_EMOJI_CAPABLE` — a frozenset of emoji-capable codepoints in the symbol
  blocks this repo draws from, derived once from Unicode's `emoji-data.txt`,
  with the regeneration command in the comment. Unicode does not retract the
  Emoji property, so it is a stable literal.
- `test_no_ratified_glyph_is_emoji_capable` — **the executable answer**: fires
  the moment someone tries `✔`, `☑`, `◼`.
- `test_the_emoji_table_is_not_vacuous` — asserts `0x2611, 0x2714, 0x26A0` *are*
  in the set and the ratified glyphs are not. Without it the frozenset could go
  empty and pass forever.
- `test_ratified_glyphs_are_the_chosen_codepoints` — exact `ord()` pins; the one
  place the codepoints appear as literals.
- `test_every_ratified_glyph_is_single_cell` — Rich `cell_len == 1`, plus an
  explicit assertion recording that `□` is EAW *Ambiguous* and that this is the
  **accepted residual**, not an oversight. Takes over the width rule from
  `test_concern_picker_modal.py`.
- `test_glyph_evidence_is_recorded` — every ratified glyph has a non-empty
  `GLYPH_EVIDENCE` entry.
- `class ManifestFreshnessTests(skipUnless(the font files are present))` — the
  **verification** tier, which validates the manifest rather than substituting
  for it: re-derive coverage from the real font files with the same `cmap`
  reader and assert it **equals** the manifest for every codepoint recorded.
  This is what catches a stale or hand-fabricated manifest on any developer
  machine that has the fonts, and it is the only tier allowed to skip — because
  the unconditional per-family tier above already enforces the policy.

### The render-level assertion (AC 4)

Added **into** `tests/test_markup_colour_contract.py`, which declares itself "the
single place a colour literal appears in the suite" — a parallel file would
contradict its own contract. Reuses its `_MarkupHost` / `painted()` /
`_REF_LIVE`+`_REF_PLAIN` two-control idiom verbatim.

- Ratification: the two hexes, that they are hex not palette names, that they
  match `PALETTE_COLORS`, and — explicitly — that `STATE_STYLE_IDLE`/`_ACTIVE`
  **keep** their bare ANSI names, so the next reader does not "finish the job"
  and repaint the state ladder.
- Composited liveness: checked paints the checked colour, unchecked paints the
  unchecked colour, **both composite and are mutually distinguishable and both
  differ from unstyled text** (AC 4, and the literal user-visible failure), and
  the checked mark keeps its `bold`.
- **Every changed production surface, not just the helper.** Asserting only on
  `mark_markup()` would prove the helper paints while leaving each call site
  unverified — and `_RejectedRow` is the site whose rendering actually *changes*
  (bare unstyled `☐` → styled `□`), so it is the one that most needs this.
  Verified all four return markup strings or a Rich renderable, so all four drop
  straight into `_MarkupHost` with no app boot:
  - `NodeRow.render()` — `widgets.py:417`
  - `_ConcernRow.render()` — `monitor_shared.py:2781`
  - `_RejectedRow.render()` — `monitor_shared.py:3243`
  - `_render_node_box()` — `brainstorm_dag_display.py:224`, the **Rich `Style`**
    path and the only surface whose colour visibly changes (olive `#808000` →
    `#F1FA8C`); feed its `Text` row to `Static` and walk the same segments.

  Each asserts both states composite, differ from each other, and differ from
  unstyled text. The board is covered separately below because it needs its real
  CSS.
- **A negative control the file currently lacks**: assert that
  `assert_painted_with` *raises* for a deliberately inert style. Without it every
  assertion in the class is potentially vacuous.
- Board composited test in `tests/test_board_marking.py`: the board needs its
  real CSS, so boot the app and walk `_compositor.render_strips()` (the helper
  shape already copied at `test_board_followup_glyph.py:134-158`). Assert the two
  states differ from each other and from the card title's foreground — **no
  literal hex**, per `test_monitor_session_divider.py:558-566` (composited
  truecolor depends on colour depth and quantisation).

---

## Implementation steps

### Pre-phase (risk mitigations)

**`pin-question-detector`** — before touching any glyph, add to
`tests/test_mark_glyphs_single_source.py` an assertion that
`workflow_phase._QUESTION_HEADER_RE.pattern` still contains `☐`, with a
comment recording why. `lib/workflow_phase.py:121` matches **Claude Code's own
terminal chip** in captured pane text — it detects a foreign glyph, it does not
render ours — and sweeping it would silently break AskUserQuestion detection in
both monitors and the shadow flow. The guard must exist before the sweep, not
after.

### Wave 1 — the authority

1. **NEW** `.aitask-scripts/lib/mark_glyphs.py` — the surface and docstring above.

### Wave 2 — consumers (each independently runnable after Wave 1)

2. `.aitask-scripts/board/aitask_board.py`
   - add `from mark_glyphs import MARK_CHECKED, MARK_UNCHECKED, mark_markup`
     (the `lib/` path push is already at line 16; the `from … import` re-binds
     both names into the module, so `tests/test_board_marking.py:103-104`'s
     `cls.ab.MARK_CHECKED` keeps working unchanged)
   - `2992-2998` delete the two constants; rewrite the rationale comment, which
     currently asserts "☑/☐ … marked = bold yellow"
   - `3117-3118` `Label(mark_markup(marked), …)`, classes unchanged
   - `7981-7982` `.task-mark` → layout-only with the rationale comment; delete
     the `.task-marked` colour rule, keep the class as a state hook
   - `10193` `label.update(mark_markup(marked))`; docstrings `10181`, `2811`
3. `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — `60-65` import +
   `MARK_CHECKED_RICH_STYLE` / `MARK_UNCHECKED_RICH_STYLE` (**renamed**: the
   locals are Rich `Style` objects while `mark_glyphs.MARK_*_STYLE` are markup
   strings — same name, two types, about to sit in one import block); emission
   `270-272`; docstrings `238`, `266`, `649`
4. `.aitask-scripts/brainstorm/widgets.py` — import; comment `400`; `419` →
   `mark = f"{mark_markup(self.marked)} "` (trailing space stays at the call
   site: the DAG and `_ConcernRow` use different separators, so baking one in
   would move a layout decision into the vocabulary module)
5. `.aitask-scripts/monitor/monitor_shared.py` — import beside the existing
   `followup_kinds` import with `# noqa: E402`; `_CONCERN_MARKS` `"none"` and
   `"forward"` from `mark_markup()`; `3244` → `mark_markup(self._marked)`;
   docstrings `2643`, `2654`, `3196`. **`MARK_GLYPH`/`MARK_EMPTY_GLYPH` and
   `format_mark_glyph` at `202-230` are untouched** (★/☆ deferred).

### Wave 3 — guards and contracts

6. **NEW** `tests/tools/regen_font_coverage.py` — the pure-Python `cmap` reader
   and manifest generator
7. **NEW** `tests/data/font_coverage.json` — generated by step 6; covers the
   ratified glyphs **and** the rejected ones (`2610, 2611, 2714, 2605, 2606`)
8. **NEW** `tests/test_mark_glyphs_single_source.py` — drift guard Rules 1–4,
   `CodepointPolicyTests`, `ManifestFreshnessTests`, the pre-phase assertion
9. `tests/test_markup_colour_contract.py` — ratification tests, `MarkPaintingTests`
   over all four changed production surfaces, the missing negative control

### Wave 4 — existing tests

10. `tests/test_board_marking.py` — reword the assertion message at `189`; add the
   composited colour test. **No other change** (verified above).
11. `tests/test_brainstorm_dag_node_mark.py` — import the renamed style;
   `_has_bold_yellow_span` → a colour-parameterised helper; `76-77` →
   `assertEqual(MARK_CHECKED_RICH_STYLE.color.name, MARK_CHECKED_COLOUR.lower())`
   (`.color.name` for a hex is `"#f1fa8c"`, not `None`)
12. `tests/test_concern_picker_modal.py` — replace the hardcoded `"☑"`/`"☐"` at
    `177,182,187,208,234,248-262,328,335` with the imported constants; reduce
    `test_every_mark_is_single_width` to the non-mark glyphs `✗`/`»` (the mark
    half moves to `CodepointPolicyTests`); docstring line 5

### Wave 5 — docs sweep (`☑`/`☐` lines only; ★/☆ lines stay)

`website/content/docs/tuis/board/_index.md:67`, `board/how-to.md:74`,
`board/reference.md:57,98`, `brainstorm/reference.md:99`,
`monitor/how-to.md:198`, `minimonitor/how-to.md:188`,
`workflows/shadow-agent.md:100`, `aidocs/framework/shadow_agent.md:906`.
Glyphs updated and "bold yellow" → "bold Dracula yellow (`#F1FA8C`)".

**Must NOT be changed** — these are Claude Code's own chip being *detected*, not
our mark being *rendered*: `lib/workflow_phase.py:121,386`;
`tests/review_loop_fixtures.py:159,161`; `aidocs/framework/shadow_agent.md:1118,1133`.
Also leave `website/content/blog/v0260-….md:26` (a dated release note correctly
recording what shipped then) and `website/public/**` (gitignored Hugo output).

### Post-phase

13. Spawn the named follow-up (AC 6) and record its id in the `mark_glyphs`
    docstring: re-evaluate the `★`/`☆` coverage gap, and run the
    `CodepointPolicyTests` oracle over the whole TUI glyph inventory. That sweep
    already has confirmed targets: **`✔` U+2714 at `aitask_board.py:3541,3596`
    is this exact defect shipping today** (covered by neither font, claimed by
    Noto Color Emoji, in the by-trail "landed" entries), and `⚠` U+26A0 is
    uncovered by CaskaydiaMono and emoji-claimed. The follow-up carries an
    explicit `depends: [1638]`.

---

## Verification

```bash
# the new guard + contract, first and alone
~/.aitask/venv/bin/python3 -m pytest tests/test_mark_glyphs_single_source.py -v
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only

# the directly affected modules
for t in test_board_marking test_brainstorm_dag_node_mark test_concern_picker_modal \
         test_markup_colour_contract test_board_followup_glyph test_monitor_agent_marks; do
  ~/.aitask/venv/bin/python3 -m pytest "tests/$t.py" -q
done

# the markup-validity scanner must stay green (hex tokens need no waiver)
~/.aitask/venv/bin/python3 -m pytest tests/test_textual_markup_colours.py -q

# question detection must be intact after the sweep
~/.aitask/venv/bin/python3 -m pytest tests/test_workflow_phase.py -q
```

Then **look at it**: `ait board` (mark a card with `space`), `ait brainstorm`
(list and graph views), and the minimonitor concern picker — confirm the checked
mark is visible and clearly distinct from the unchecked one on this machine,
which is where the bug was reported.

Prove each guard can actually fail — run all five, each reverted after:

| injected defect | must turn red |
|---|---|
| re-add `MARK_CHECKED = "☑"` to `aitask_board.py` | drift Rule 1 |
| replace a call site with `f"[bold #FF0000]{MARK_CHECKED}[/]"` | drift Rule 4 |
| delete a `from mark_glyphs import …` line, or leave it unused | drift Rule 3 |
| set `MARK_CHECKED = "✔"` (U+2714) | `test_every_ratified_glyph_is_covered_by_every_supported_font` (false for Caskaydia) **and** `test_no_ratified_glyph_is_emoji_capable` |
| set `MARK_CHECKED_COLOUR = "notacolour"` | the composited contract tests |

Also flip a `false` to `true` in `tests/data/font_coverage.json` and confirm
`ManifestFreshnessTests` goes red on a machine with the fonts — the manifest
must not be trustworthy merely because it is checked in.

---

## Risk

### Code-health risk: medium
- Sweeping `U+2610`/`U+2611` repo-wide would break `lib/workflow_phase.py:121`'s
  `_QUESTION_HEADER_RE`, silently disabling AskUserQuestion detection in both
  monitors and the shadow flow · severity: high · → mitigation: inline pre-phase
  `pin-question-detector`
- Blast radius is 4 source modules, 5 test files and 8 doc lines; a missed
  consumer leaves a stale glyph that only shows up visually · severity: medium ·
  → mitigation: inline pre-phase `pin-question-detector` (the same AST guard's
  Rule 3 proves every declared consumer really imports *and uses* the module,
  and Rule 4 stops a consumer sourcing the glyph but hand-rolling its colour)
- A consumer could satisfy the import check yet still render the mark with its
  own hard-coded colour, leaving the guard green while the drift is present ·
  severity: medium · → mitigation: drift Rule 4 forbids the bare glyph constants
  inside any f-string or string concatenation, so `mark_markup()` /
  `rich_mark_style()` are the only reachable rendering paths; pinned by a
  dedicated negative control
- `monitor_shared.py:3244`'s unchecked mark becomes styled `#6272A4` where it was
  bare/unstyled — a real, intended visual change (dimmer) that could read as a
  regression · severity: low · → mitigation: called out in the commit message
- `□` U+25A1 is EAW *Ambiguous* where `☐` was *Neutral*, so it can occupy two
  cells in wide-ambiguous terminals against the `_NARROW_PREFIX_COLS = 8` and DAG
  `BOX_WIDTH` budgets · severity: low · → mitigation: user-accepted residual,
  pinned as an explicit assertion in `CodepointPolicyTests` rather than left
  implicit
- The board's composited colour test boots a real TUI and the `NodeRow.render()`
  test sets a `reactive` on an unmounted widget · severity: low · → mitigation:
  documented fallback — assert `mark_markup(True)` directly and pin `NodeRow` with
  a plain-string `assertIn` if the reactive path misbehaves

### Goal-achievement risk: low
- Every acceptance criterion has an executable check, and the root cause was
  measured rather than assumed · severity: low · → mitigation: none needed
- The checked-in coverage manifest is only as good as its last regeneration, and
  a hand-edited entry would assert a coverage fact that is not true · severity:
  medium · → mitigation: `test_the_manifest_is_not_vacuous` (it must record the
  rejected codepoints as `false`) plus `ManifestFreshnessTests`, which re-derives
  from the real `cmap` and fails on any mismatch wherever the fonts exist
- `SUPPORTED_FONTS` is a **new declaration** — the repo names no supported font
  anywhere today — so the coverage claim is only as broad as that tuple; a
  deployment on a third font is unverified by construction · severity: low · →
  mitigation: stated plainly in the module docstring as the declared scope, not
  implied to be universal; extending it is one tuple entry plus a regeneration
- AC 6 is satisfied by the deferral branch rather than the fix branch, so its
  value depends on the follow-up actually being created and linked · severity:
  low · → mitigation: post-phase step 11 creates it with an explicit
  `depends: [1638]` and records its id in the `mark_glyphs` docstring
