---
Task: t1453_unparseable_rich_colour_names_in_textual_markup.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1453 — Unparseable Rich colour names in Textual markup

## Context

Textual's markup parser resolves **CSS colour names only**. It does not know
Rich's xterm palette names (`dodger_blue1`, `bright_cyan`, `bright_green`,
`medium_purple1`), nor Rich's spellings of style keywords (`strikethrough` vs
Textual's `strike`). An unknown token does **not** raise —
`textual/widget.py:1309-1312` is `try: return VisualStyle.parse(style) except
Exception: return NULL_STYLE` — so the span keeps the unresolved string and the
compositor paints whatever the widget's CSS supplies, dropping every attribute
in that span.

Because `Content.from_markup` stores the style string in the span **verbatim**,
every `render().spans` assertion passes while the pixel is wrong. That is why
the defect has survived: only a composited-screen read catches it.

Four live styles have never rendered:

| markup | intended | actually painted |
|---|---|---|
| `bold dodger_blue1` | DONE / COMPLETED state, both monitors | default fg, bold dropped |
| `bold bright_cyan` | `(k)` key-hint highlight, TUI switcher | default fg, bold dropped |
| `bright_green` | running-TUI `●` indicator, TUI switcher | default fg |
| `dim strikethrough` | disabled operation row, brainstorm wizard | default fg, **dim and strike both dropped** |

The fourth was **not** in the task description — it was found by the scan
designed for this task. `brainstorm/widgets.py:680` renders a disabled operation
identically to an enabled one. Measured: `[dim strikethrough]` → `#e0e0e0`,
`dim=None`, `strike=None`; `[dim strike]` → `#999999`, `strike=True`.

t1449 hit this class itself (it first used `medium_purple1`) and left the fix
comment at `monitor_shared.py:224-233` plus the only composited test tier in the
suite. This task fixes the survivors and adds a guard so the class cannot return.

## Verified resolution matrix

Measured here (textual 8.2.7) by mounting real apps and reading
`screen._compositor.render_strips()`. The renderer is decided **per construction
site**, not per file — this is the rule both the fix and the guard depend on:

| construction | Rich-only token |
|---|---|
| Textual markup string — `Static("[bold bright_cyan]x[/]")` | **BROKEN** |
| `Widget.render()` → `rich.text.Text("x", style="bright_cyan")` (string style) | **BROKEN** |
| `Static.update(rich.text.Text("x", style="bright_cyan"))` (top-level) | **BROKEN** |
| `rich.style.Style(color="bright_cyan")` **object**, anywhere | works → `#58d1eb` |
| `Text(style="bright_cyan")` **nested in a Rich container** (`Table` → `Static.update`) | works → `#58d1eb` |
| Textual CSS / `DEFAULT_CSS` (`color: bright_cyan`) | raises `StylesheetParseError` — **fails loud, out of scope** |

Consequence: `.aitask-scripts/codebrowser/code_viewer.py:25-31` is **correct
as-is** — its `Text` cells are nested in the boxless `rich.table.Table` built at
`lib/numbered_source_view.py:156-183`. Verified composited. Must not be "fixed".

## Chosen replacements

| was | becomes | painted | why |
|---|---|---|---|
| `bold dodger_blue1` | `bold #1e90ff` | `#1e90ff`, bold kept | CSS `dodgerblue` pinned as hex. Separable from magenta/yellow/green and from `#af87ff`. |
| `bold bright_cyan` | `bold cyan` | `#00ffff`, bold kept | Matches the already-working sibling at `tui_switcher.py:336`; `#00ffff` is the brightest cyan Textual has. |
| `bright_green` | `#00ff00` | `#00ff00` | **Exactly** what Rich's `bright_green` resolves to (verified: `rich.Color.parse("bright_green").get_truecolor().hex == "#00ff00"`). |
| `dim strikethrough` | `dim strike` | `#999999`, strike kept | Textual's spelling of the same attribute. |

**Why `#00ff00` and not `ansi_bright_green`.** `ansi_bright_green` parses, but it
is `Color(0,255,0, ansi=10)` — the ANSI flag makes Textual remap it through the
*theme's* palette at render time, not the terminal's. Measured: `#98e024` under
textual-dark / nord / gruvbox, `#60cb00` under textual-light — a chartreuse, not
the bright green the name means, and unstable across themes so no test could pin
it. The hex is what the task's own rule asks for ("prefer hex where the exact
shade matters"), is stable under all four themes, and is consistent with the
surrounding full-saturation palette (`yellow` `#ffff00`, `magenta` `#ff00ff`,
`cyan` `#00ffff`).

---

### Pre-phase (risk mitigations)

**`pin_tui_switcher_hint_text`** — run this *before* Step 3 touches
`lib/tui_switcher.py`. Add a characterization test pinning the exact rendered
hint strings: `_hint_segment(action_id, label, default_key)` for every
`_HINT_ITEMS` entry, and the full `_render_hint()` text in both single- and
multi-session mode — including the escaped `\[` group hint at `:746` and the
group prefix at `:804`. Capture from the *current* code, then assert that after
Step 3 they differ only by the style token. This is what makes the
regex-template (`:248`, `\1`) and escaped-bracket edits provably text-preserving
across the 18 TUIs that mount this overlay.

## Step 1 — `monitor/monitor_shared.py`: name the four state styles

Add beside the existing constant convention (`SESSION_DIVIDER_STYLE` at `:205`,
`SECTION_HEADER_STYLE` at `:233`):

```python
STATE_STYLE_PROMPT = "bold magenta"
STATE_STYLE_DONE   = "bold #1e90ff"
STATE_STYLE_IDLE   = "yellow"
STATE_STYLE_ACTIVE = "green"
```

`STATE_STYLE_DONE` carries a comment in the same shape as
`SECTION_HEADER_STYLE`'s (`:224-233`) — the task explicitly asks that the *why*
live at the definition so a later edit does not "tidy" it back to a name:
hex-not-name because Textual's markup palette is CSS names only; `#1e90ff` is
CSS `dodgerblue`, the shade the old name intended.

Rewire `_state_color()` (`:108-127`) and `format_pane_status()` (`:795-805`) to
return/interpolate them. `:133` (`format_state_dot`) and `:163`
(`format_shadow_glyph`) interpolate `_state_color()` and are fixed transitively.
Update the `_state_color` docstring at `:110-112`, which names the old literal.

## Step 2 — the two monitor apps

Both already do `from monitor.monitor_shared import (...)` (`monitor_app.py:41`,
`minimonitor_app.py:46`). Add `STATE_STYLE_DONE` to each import and interpolate:

- `monitor_app.py:1279` — legend; lines 1276-1279 are one implicit
  concatenation, so make that element an f-string
- `monitor_app.py:1472` — session-bar done count
- `minimonitor_app.py:846` — mini done count

**5 literals → 1.** The duplication is what let this bug spread across three
files.

## Step 3 — `lib/tui_switcher.py`: two named constants, 11 sites

```python
TUI_KEY_HINT_STYLE = "bold cyan"      # not bright_cyan: Textual knows CSS names only
TUI_RUNNING_STYLE  = "#00ff00"        # the exact shade Rich's bright_green meant
```

| line | current | becomes |
|---|---|---|
| 248 | `r"[bold bright_cyan](\1)[/]"` | `rf"[{TUI_KEY_HINT_STYLE}](\1)[/]"` |
| 339 | `"[bright_green]●[/]"` | interpolate `TUI_RUNNING_STYLE` |
| 340 | `style = "bright_green"` | `style = TUI_RUNNING_STYLE` |
| 347, 736, 739, 740, 746, 749, 804 | `[bold bright_cyan]…` | interpolate `TUI_KEY_HINT_STYLE` |
| 363 | `f" [bright_green]●[/]  {self.window_name}"` | interpolate `TUI_RUNNING_STYLE` |

**11 literals → 2.** Care at **248** (regex replacement template — `\1` must
survive, needs `rf`), **746** (`"…\\[/][/] group  "`) and **804**
(`f"…\\[{glabel}][/]  "`) — both carry an escaped literal `\[` that must stay
escaped. The pre-phase characterization test is what proves these three.

Lines **336-337** (`bold cyan`) already resolve — leave them. The hint at 347 is
suppressed when `is_current` (`:348`), so it never shares a row with the `▶`
marker; the two sharing cyan is a deliberate, non-colliding choice.

## Step 4 — `brainstorm/widgets.py:680`

`[dim strikethrough]` → `[dim strike]` in `OperationRow.render()`. Same defect
class, found by this task's own scan; a disabled operation currently renders
identically to an enabled one.

## Step 5 — retarget the existing tests

Both hard-code the literal, which is how this bug hid. Note that most of
`test_monitor_completed_status.py`'s assertions are **tautological today** —
`assertEqual(format_state_dot(s, True), "[bold dodger_blue1]●[/]")` asserts that
`_state_color` returns what `_state_color` returns. It protects nothing and only
makes a colour change expensive.

- **`tests/test_monitor_completed_status.py`** — 12 literals at 194, 195, 205,
  219, 242, 243, 254, 255, 273, 278, 310 plus the docstring at `:4`. Import the
  constants and derive (`f"[{STATE_STYLE_DONE}]●[/]"`). The `assertNotIn` at 219
  and 273 (collision sentinels) become `assertNotIn(STATE_STYLE_DONE, …)`; the
  precedence test at 205 becomes `assertIn(STATE_STYLE_DONE, …)` /
  `assertNotIn(STATE_STYLE_IDLE, …)`.
  **Every literal moves out** — the ratification point is the single
  `RatifiedStylesTests` class in Step 8, not scattered per-module.
  Add `test_the_four_state_styles_are_pairwise_distinct` — the property the 12
  literals were trying to express and never did.

- **`tests/test_monitor_session_divider.py:119,138`** — these go **silently
  vacuous**, which is worse than failing: `dodger_blue1` stops being a taken
  colour, so the loop entry keeps passing while checking nothing, and the
  collision guard loses a sixth of its coverage with no signal. Retarget to the
  constants, and compare the **colour token** rather than substring —
  `assertNotEqual(taken.split()[-1], SESSION_DIVIDER_STYLE.split()[-1])` — the
  idiom already at `:66-68`. (With `bold #1e90ff` vs `bold cyan`, a substring
  `assertNotIn` is strictly weaker than it was for bare names.)
  The docstrings at `:445` and `:512` naming `[bold medium_purple1]` **stay
  verbatim** — they are the prose record of the defect, and the scan excludes
  docstrings precisely so that stays safe.

## Step 6 — correct the stale claim in `aidocs/`

`aidocs/framework/monitor_idle_and_prompt_detection.md:138-142` documents the
badge as `[bold dodger_blue1]` and asserts `dodger_blue1` (`#0087ff`) beats plain
`blue` on contrast, "**Verified by tmux capture**". Both claims are false: the
badge has never painted `#0087ff`, so no capture can have verified it. Rewrite
for `bold #1e90ff`, keep the real reason (CSS `blue` is `#000080`, far too dark
on the `#1a1a1a` card), drop the fabricated verification claim. Per the
current-state-only rule, do not narrate the history.

Grep found no other docs, `.j2`, `.sh`, `.json`, `.yaml` or `.tcss` referencing
the names (`CHANGELOG.md:1271` is a historical release note and stays).

## Step 7 — new guard: `tests/test_textual_markup_colours.py`

Follows the repo's scan-guard convention (`tests/test_gate_ledger_only_surfaces.py`,
`tests/test_collection_structure.py`): docstring stating scope **and** non-scope,
`REPO_ROOT`/`SCRIPTS_DIR` constants, `sorted(rglob("*.py"))`, a waiver dict with
per-entry reasons, a module-level `REMEDIES` string, non-vacuity assertions, and
synthetic-source negative controls.

Two rules, deliberately using **two different oracles**. State the reason in the
docstring — it is the design's central trade and a reader will otherwise ask why:

> A bracketed token carries a syntactic marker of intent, so it gets the exact
> oracle. A bare string has none, so it gets the conservative blocklist —
> running the exact oracle over bare strings produces 44 prose false positives
> (`'not found'`, `'Sync on refresh'`, …).

**Rule A — markup tokens. Oracle: `textual.markup.parse_style`.** Textual's own
decision procedure, so there is no vocabulary to maintain and it tracks Textual
version by version. AST-walk `ast.Constant[str]` (docstrings excluded), regex
`(?<!\\)\[([^\[\]\n]*)\]`, gate to candidates, then flag anything `parse_style`
rejects. Three details are load-bearing, each measured:

1. **Pass theme variables explicitly** —
   `BUILTIN_THEMES["textual-dark"].to_color_system().generate()` (168 tokens).
   Without them `parse_style` consults `active_app`, finds none, and
   `$accent` raises → 9 false positives in `brainstorm/widgets.py`.
2. **Candidate gate**: every word must be word-shaped, and **at least one word
   must be *triggering*** — a `textual.markup.STYLES` keyword, a
   `Color.parse`-able name, a `#hex`/`$var`, or a known Rich-only name. Without
   the "≥1 triggering word" requirement, prose like `[applink]`, `[READ ONLY]`,
   `[str]`, `[registry]`, `[enter details]` floods in — measured **39 false
   positives**.
3. **`on` / `not` / `auto` / `link` are permitted but non-triggering**, and
   single-letter abbreviations are excluded entirely. Otherwise
   `[not a marker]` (`tests/test_minimonitor_concern_action.py:667`) and
   `[press b for full text]` / `[a All | l Locked]` / `[a, b]` become findings.

Requiring a Rich-only name to be *triggering* (not merely present) is what keeps
`[bright_green]` — a token with no other style word — in scope.

**Measured over the live tree:**

| tree | candidate tokens | findings | false positives |
|---|---|---|---|
| `.aitask-scripts/**/*.py` | 493 | **15** | **0** |
| `tests/**/*.py` | 41 | 8 | **0** |

The 15 are the 14 known sites plus `brainstorm/widgets.py:680`; the 8 are all in
`test_monitor_completed_status.py` and vanish with Step 5. **Rule A needs no
waivers at all.** It also catches `[bold blu]`, `[bodl cyan]` and `[bold $acent]`
for free — the typo class the vocabulary-only design could not see.

**Rule B — bare style strings. Oracle: the Rich-only blocklist.** A whole string
constant where ≥1 word is a Rich-only name and every other word is a style
keyword or `Color.parse`-able. This is the false-negative that matters:
`monitor_shared.py:124` and `tui_switcher.py:340` never appear inside brackets in
their own file — they are interpolated into a tag elsewhere (`:133`/`:163`,
`:351`).

- **No word cap.** Measured with caps of 4, 8 and ∞ — identical 12 hits. All the
  discriminating power is in the "every other word" test (any prose word fails
  immediately). A cap is a magic number that would one day silently exclude a
  legitimate `not blink bold underline on dark_blue`.
- **Assert the invariant that makes it prose-safe**: all 223 Rich-only names
  contain an underscore or a digit — *not one is a bare alphabetic word*
  (`[n for n in RICH_ONLY if n.isalpha()] == []`). That is *why* prose never
  trips Rule B, and a future `rich` release could break it silently.

**Waivers** — Rule B only, 5 entries, keyed
`(relpath, enclosing_qualname_or_"MODULE", token)`, mirroring
`LEDGER_ONLY_CONSUMERS`'s `(relpath, qualname)` key at
`test_gate_ledger_only_surfaces.py:70`:

- 4 × `codebrowser/code_viewer.py` (`bright_cyan`, `bright_green`, `grey27`,
  `dark_blue`) — Rich-consumed.
- 1 × `tests/test_board_columns_seam.py:741` (`bright_blue` in
  `ColorPolicyTests.ACCEPTED`) — a deliberate fixture proving `_COLOR_RE`
  accepts colour *names*.

Not per-line (line numbers drift — the bug report's own were off by 4, 18 and
140). Not per-file (would blanket-exempt a file that later gains a real markup
site). Adding the qualname narrows a waiver to one function instead of letting
one entry silently absorb every future occurrence in that file.

**The waiver's reason must be checkable, not just prose.** `ANNOTATION_COLORS`
is *defined* in `code_viewer.py:25-28` but the fact making it correct lives in
`lib/numbered_source_view.py:156-183`. A refactor routing it into a top-level
`Text` breaks the reason **without touching `code_viewer.py`**, and the scan
stays green forever. So each reason must (a) name the consumer as
`file:function`, and (b) name a `pinned_by=` composited test — with a
`test_every_waiver_names_a_pinning_test` assertion that the named test exists.

**Explicitly out of scope**, with the reason stated in the docstring:

- Textual CSS / `DEFAULT_CSS` / `.tcss` — raises `StylesheetParseError` at app
  construction; already fails loud, and every TUI smoke test catches it.
- Fully dynamic tags `f"[{x}]"` (65 sites) — undecidable; **Rule B is the
  compensating control**, cite `monitor_shared.py:133`/`:163` as the shape.
- Colour names from JSON/YAML — `lib/board_columns.py:175-176`'s `_COLOR_RE`
  deliberately accepts `bright_blue`; `monitor_shared._safe_column_color`
  (`:1482-1507`) is the runtime answer. All shipped values are hex today. Point
  the reader at `_safe_column_color`.
- Names that parse in **both** libraries to **different** colours (`purple`,
  `orchid`, `tan`, `violet`; Rich `purple` = `#af00ff` vs CSS `#800080`) — not
  inert, so not this defect.
- `.md.j2` / seed / `.sh` — verified empty by grep; skill templates render to
  Markdown read by an LLM, never a compositor.

**Negative controls** (`ScannerDiscriminationTest`, synthetic sources, never the
live tree — one mutation each). Must be caught: a Rich-only tag; `[dim
strikethrough]`; `[bold blu]`; `[bodl cyan]`; `[bold $acent]`; implicit
concatenation folded into one token; a bare Rule-B string; a 6-word Rule-B
string (pins the cap removal). Must **not** be findings: `[bold cyan]`,
`[bold #1e90ff]`, `[#00ff00]`, `[bold $accent]`, `[dim]`, `[on #202020]`,
`[@click=x]`; the four *measured* prose shapes (`[a All | l Locked | f Free | i
In-Flight]`, `[press b for full text]`, `[a, b]`, `[i - 2]`) — each of which
fails today if single-letter abbreviations are added back to the gate, which is
what makes them real controls; a backslash-escaped `\[…]`; a closing `[/red]`;
a docstring containing `[bold medium_purple1]`.

Structural: a syntactically bad file must raise rather than be skipped;
`assertGreater(candidates, 300)` on the live tree (measured 493);
and **`test_the_oracle_itself_still_discriminates`** — `parse_style("bold cyan")`
succeeds, `parse_style("bold bright_cyan")` raises, `RICH_ONLY` is non-empty and
has no bare-alphabetic member. Without this, an upstream rename turns the whole
guard vacuously green.

### Post-phase (risk mitigations)

**`guard_allowlist_selfcheck`** — assert waiver-set **equality** with the scan's
findings (`assertEqual(set(findings), set(WAIVERS))`, as
`test_gate_ledger_only_surfaces.py:288-292` does), so a stale entry is itself a
failure, plus the `test_every_waiver_names_a_pinning_test` check above. Together
these make the waiver list self-policing: it cannot rot into a silent exemption
without a test failing.

**`pin_the_upstream_oracle`** — the guard now depends on
`textual.markup.parse_style`, `textual.markup.STYLES` and
`BUILTIN_THEMES[...].to_color_system().generate()`, all Textual internals. Import
them at module scope so a rename is an `ImportError` (loud) rather than a silent
`except` (green), and let `test_the_oracle_itself_still_discriminates` above
carry the behavioural half. This replaces the `extend_markup_scan_to_typos`
follow-up — `parse_style` already covers the typo class that mitigation existed
for.

## Step 8 — the colour contract: ratification + composited liveness

Both tiers live in one new file, `tests/test_markup_colour_contract.py`, so each
colour's two tests sit adjacent. They answer different questions and neither
substitutes for the other:

| tier | question | fails when |
|---|---|---|
| **ratification** | is this the value we chose? | someone changes the shade without deciding to |
| **composited** | does that value actually paint? | the value is syntactically inert |

### 8a — Ratification (`RatifiedStylesTests`)

The **single** place any colour literal appears in the test suite. A shade change
is then one deliberate, reviewable edit here — not a scatter of mechanical ones.
Same shape as `test_style_is_not_dim` (`test_monitor_session_divider.py:108-112`).

```python
def test_done_state_style_is_the_ratified_value(self):
    self.assertEqual(monitor_shared.STATE_STYLE_DONE, "bold #1e90ff")

def test_tui_key_hint_style_is_the_ratified_value(self):
    self.assertEqual(tui_switcher.TUI_KEY_HINT_STYLE, "bold cyan")

def test_tui_running_style_is_the_ratified_value(self):
    self.assertEqual(tui_switcher.TUI_RUNNING_STYLE, "#00ff00")

def test_disabled_operation_row_is_dim_and_struck(self):
    row = OperationRow("k", "Label", "desc", disabled=True)
    markup = row.render()
    self.assertIn("[dim strike]", markup)
    self.assertNotIn("strikethrough", markup)   # Rich's spelling; inert in Textual
```

The disabled row has no named constant (the markup is inline in
`OperationRow.render()`, `widgets.py:678-680`), so it is ratified on the rendered
markup directly — including the explicit `assertNotIn("strikethrough", …)`, which
is what makes the regression it guards against nameable.

### 8b — Composited liveness

Static scanning cannot prove a colour *paints*. Follow
`tests/test_monitor_session_divider.py:444-526` (`_RuleHost(App)` +
`CompositedColourTests`) — but with one correction.

**`#e0e0e0` is not a valid sentinel.** Measured on the real `_TuiListItem`
mounted in a bare `ListView`: the three inert runs paint **`#ddedf9`** (the
ListView item colour), not the theme default. The existing idiom
`assertNotEqual(painted, "#e0e0e0")` would have **passed on all three live
defects**. Do not copy it.

Instead put two controls in the *same* CSS context in each host —
`Static(f"[{STYLE_CONST}]REF[/]")` and a plain `Static("REF")` — and assert
`painted[target] == painted[REF_LIVE]` **and** `painted[REF_LIVE] !=
painted[REF_PLAIN]`. Theme- and CSS-independent, and it decomposes: the first
says *the call site uses the constant*, the second says *the constant is live*.
`_WindowListItem.compose` (`:363`) yields one `Static` holding both the glyph and
the window name, so `painted['●'] != painted[window_name]` is a zero-cost
in-context control.

Hosts, chosen for coverage per unit of complexity:

1. **`_TuiListItem` + `_WindowListItem` in a bare `ListView`** — verified
   mountable headlessly with no tui_switcher machinery. Covers three defect
   classes at once: the running `●` (`:339`), the `style` variable path
   (`:340`→`:351`), and the `(K)` hint via `_hint_segment` (`:248`, `:347`).
   Mounting the real classes brings `DEFAULT_CSS` along, which is what surfaced
   the `#ddedf9` finding — a bare `Static` host would have missed it.
2. **`format_pane_status` / `format_state_dot` output in `Static`s** — pure
   formatters; covers `:124` + `:802` and by construction `format_shadow_glyph`.
3. **`MonitorApp._agents_header_text(3)` and `_rebuild_session_bar()`** — do
   **not** boot the real apps; `test_monitor_completed_status.py:318-337` already
   constructs `MonitorApp` unmounted with a stubbed `query_one`. Take the
   returned markup string and mount it. Covers `monitor_app.py:1276`, `:1472`,
   `minimonitor_app.py:846`.
4. **`brainstorm.OperationRow(disabled=True)`** — assert the label's painted
   style has `strike=True`. The newly found bug, cheapest possible mount.
5. One cross-surface identity test (mirroring `CrossTuiAgreementTests`,
   `test_monitor_session_divider.py:530-551`) asserting all four DONE surfaces
   emit the same `STATE_STYLE_DONE`.

**The composited tier asserts no literals** — the reference-control pair makes
them unnecessary, and 8a already owns the values. Where a hex is genuinely
needed, derive it (`STATE_STYLE_DONE.split()[-1]`, the idiom at `:66-68`). No
carve-out entry in `tests/run_all_python_tests.sh` is needed — none of the 10
existing `render_strips()` tests are carved out.

## Verification

```bash
~/.aitask/venv/bin/python -m pytest \
  tests/test_monitor_completed_status.py tests/test_monitor_session_divider.py \
  tests/test_textual_markup_colours.py tests/test_markup_colour_contract.py -q

bash tests/run_all_python_tests.sh      # read only the LAST line for the verdict
```

Negative control: revert one call site to `bold dodger_blue1` and confirm the
scan fails naming that exact file:line; revert `[dim strike]` to
`[dim strikethrough]` and confirm both the scan and the `OperationRow`
composited test fail. Then restore.

Manual: `ait monitor` with a completed agent shows a blue `DONE`/`●`; `j` shows a
cyan `(k)` hint and a `#00ff00` `●` on running TUIs; the brainstorm Actions
wizard shows disabled operations struck through.

## Step 9 (Post-Implementation)

Merge to `main`, archive task + plan per the standard flow.

## Risk

### Code-health risk: medium

- `lib/tui_switcher.py:248` is a **regex replacement template** (`\1` must
  survive; needs `rf`) and `:746` / `:804` carry escaped literal brackets. A
  careless swap silently changes rendered hint text — and this overlay is
  mounted into 18 TUIs, so the damage is everywhere at once · severity: medium
  · → mitigation: inline pre-phase pin_tui_switcher_hint_text
- The guard's waiver list can rot into a silent exemption: the fact that makes a
  waived site correct lives in a *different* file, so a refactor can invalidate
  the reason without touching the waived file, leaving the scan green forever
  · severity: medium · → mitigation: inline post-phase guard_allowlist_selfcheck
- The guard depends on Textual internals (`markup.parse_style`, `markup.STYLES`,
  `BUILTIN_THEMES`). An upstream rename could make it vacuously green rather
  than failing · severity: medium · → mitigation: inline post-phase
  pin_the_upstream_oracle

### Goal-achievement risk: low

- None identified. The original typo gap (a colour name neither library knows,
  e.g. `[bold blu]`) is closed by adopting `parse_style` as Rule A's oracle —
  verified to reject `blu`, `bodl`, `strikethrough` and `$acent`.

### Planned mitigations

- timing: pre-phase | name: pin_tui_switcher_hint_text | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tui_switcher regex-template and escaped-bracket edits (code-health) | desc: Characterization test pinning the exact rendered hint strings before the style swap, so the replacement is provably text-identical apart from the style token.
- timing: post-phase | name: guard_allowlist_selfcheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: waiver-list rot (code-health) | desc: Assert waiver/finding set equality and that every waiver names an existing pinning test, so a stale or invalidated waiver fails loudly instead of becoming a silent exemption.
- timing: post-phase | name: pin_the_upstream_oracle | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: guard depends on Textual internals (code-health) | desc: Module-scope imports so a rename is a loud ImportError, plus a discrimination test asserting the oracle still accepts a good token and rejects a bad one.
