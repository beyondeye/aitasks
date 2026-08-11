---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor, minimonitor, tui, ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1449
implemented_with: claudecode/opus5
created_at: 2026-08-07 12:16
updated_at: 2026-08-11 17:17
---

## Origin

Spawned from t1449 during Step 8b review. t1449 recoloured the monitors'
`── … ──` rules and, in doing so, hit this bug itself: the first attempt used
`medium_purple1` and rendered as plain default text while every span-level
assertion passed.

## Upstream defect

Textual's markup parser resolves **CSS colour names only** — it does not know
Rich's xterm palette names. An unknown name does **not** raise: the span keeps
the unresolved string and the compositor paints the theme's default foreground
(`#e0e0e0`), dropping any `bold` in the same span. The colour is silently
inert.

Two live cases, both verified at the composited-screen level (not inferred from
`Color.parse` alone):

- `.aitask-scripts/monitor/monitor_shared.py:120 — "bold dodger_blue1" is the COMPLETED/DONE state colour returned by _state_color(); it paints #e0e0e0 with no bold, so DONE has never rendered blue in either monitor. Same string at monitor_shared.py:798 (DONE badge), monitor_app.py:1261 (legend), monitor_app.py:1454 (session-bar done count), minimonitor_app.py:706 (mini done count).`
- `.aitask-scripts/lib/tui_switcher.py:248 — "bold bright_cyan" (the (K) key-hint highlight) and "bright_green" (the running-TUI ● indicator) are likewise inert. bright_cyan appears at lines 248, 347, 736, 739, 740, 746, 749, 804; bright_green at 339, 363. The same file's "bold cyan" at line 336 DOES resolve, so the two sit side by side in one render path with only one of them working.`

Measured in Textual 8.2.7:

| markup | painted |
|---|---|
| `[bold dodger_blue1]` | `#e0e0e0`, bold dropped |
| `[bold bright_cyan]`  | `#e0e0e0`, bold dropped |
| `[bright_green]`      | `#e0e0e0` |
| `[bold cyan]`         | `#00ffff`, bold kept |
| `[bold #af87ff]`      | `#af87ff`, bold kept |

## Diagnostic context

From t1449's plan (`aiplans/archived/p1449_*.md`), "Issues encountered":

> The first pass used `medium_purple1` (the name the user picked from a preview
> swatch). It rendered as default foreground. Textual's markup parser resolves
> CSS colour names only — it does not know Rich's xterm names, and an unknown
> name fails *silently* rather than raising. All 15 span-level tests passed
> while the header painted `#e0e0e0`. Only the composited probe caught it.

**Why no test catches this today.** The repo's TUI convention is to assert
against `render()` output. For colour that usually means
`Static.render().spans`, and a span stores the markup's style string *verbatim*,
resolved or not — so a bad colour name is invisible at that level. Detecting it
requires mounting the widget and reading
`screen._compositor.render_strips()`. t1449 added such a tier in
`tests/test_monitor_session_divider.py` (`CompositedColourTests`); it is
currently the only place in the suite that checks a resolved colour.

## Suggested fix

1. Replace each unparseable name with a Textual-resolvable equivalent — a CSS
   name (`dodgerblue`, `cyan`, `springgreen`) or a hex literal pinning the
   intended shade (`dodger_blue1` is `#1e90ff`, `bright_cyan` `#00ffff`,
   `bright_green` `#00ff00`). Prefer hex where the exact shade matters, and
   record *why* at the call site, as `monitor_shared.SECTION_HEADER_STYLE`
   does — otherwise a later edit "tidies" it back to a name.
2. Add a guard so this cannot regress: a test that walks every `[...]` markup
   token under `.aitask-scripts/**/*.py` and asserts `textual.color.Color.parse`
   accepts each colour-ish word. That is a cheap static check and would have
   caught all three names at once. The scan t1449 ran is a working starting
   point; it needs a keyword allowlist (`bold`, `dim`, `italic`, `on`, …) and
   an exclusion for prose/f-string false positives (`[filtered]`, `[ordered]`,
   `[rendered]`, `[required]`, `[configured]` all showed up).
3. While there, confirm whether any other Rich-only name is in use in markup
   that a *Rich* renderer (not Textual) consumes — those are fine and must not
   be "fixed". Establish per-file which renderer is in play before editing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-11T14:17:08Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-11T16:06:25Z status=pass attempt=1 type=human
