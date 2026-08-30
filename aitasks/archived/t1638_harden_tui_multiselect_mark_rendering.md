---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [tui, aitask_board, ait_brainstorm, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-30 12:32
updated_at: 2026-08-30 14:00
completed_at: 2026-08-30 14:00
---

## Problem

The repo-wide multi-select mark convention (t1004: checked `☑` / unchecked `☐`,
marked = bold yellow) renders the **checked** mark almost invisibly on at least
one supported desktop. The unchecked mark is unaffected. Observed in the
minimonitor concern picker and in the board's task-selection marks.

## Root cause (investigated, not assumed)

The trigger was environmental, but it exposed a real framework fragility.

**Ruled out by measurement:**

- *Theme palette.* Active theme resolves ANSI yellow to `#e0af68` and bright
  yellow to `#ff9e64` on background `#1a1b26` — both high contrast. Colour
  choice is not the failure.
- *The nerd-font package swap.* The host upgrade force-removed
  `ttf-jetbrains-mono-nerd` and installed `ttf-jetbrains-mono-nerd-basic`.
  Extracting the removed package from the pacman cache and parsing both `cmap`
  tables shows **neither** font covers `U+2610` `☐`, `U+2611` `☑`, `U+2612` `☒`
  (nor `U+2605` `★` / `U+2606` `☆`, used by the monitor's prioritisation mark).
  Both always fell back. Real change, wrong culprit.

**Actual mechanism:** the primary terminal font has never covered these
codepoints, so every one of them is resolved by system font fallback. A host
fontconfig change altered the fallback ranking, and the two marks rank
differently because only the checked glyph is emoji-capable:

| glyph | fallback order |
|---|---|
| `☑` U+2611 | Adwaita Mono, **Noto Color Emoji (2nd)**, Font Awesome 7 Free, Noto Sans Symbols 2, … |
| `☐` U+2610 | Adwaita Mono, Noto Sans Symbols 2, Liberation Sans, …, Noto Color Emoji (**last**) |

A colour-bitmap glyph ignores the requested foreground entirely, so the checked
mark paints its own dark colours on a dark background while the unchecked mark
keeps honouring `#6272A4`.

## What this repo owns

The framework cannot control the user's fontconfig, but it currently makes the
problem worse in three ways, and has no way to detect it:

1. **No installed terminal font covers the mark glyphs.** The convention
   picked codepoints that fall outside every Nerd Font variant the framework's
   own supported setups install, so the mark's appearance is delegated wholesale
   to unpredictable system fallback.

2. **The checked and unchecked marks use different colour authorities.**
   Checked is the bare ANSI name `yellow` (palette-relative — resolves to
   whatever the terminal's ANSI 3/11 happens to be, and `bold` may promote it to
   bright); unchecked is a literal hex. The pair is therefore not guaranteed to
   stay legible together under any theme, independent of the font issue.

3. **Nothing verifies the convention renders.** t1004 unified the glyph choice
   repo-wide, and the codebase asserts on the mark's *string*, but no guard ties
   the convention to whether the mark is actually distinguishable.

### Sites (all five carry the same pattern)

- `.aitask-scripts/board/aitask_board.py:2997-2998` — `MARK_CHECKED` /
  `MARK_UNCHECKED` constants
- `.aitask-scripts/board/aitask_board.py:7982` —
  `.task-marked { color: yellow; text-style: bold; }` vs
  `.task-mark { color: #6272A4; }`
- `.aitask-scripts/monitor/monitor_shared.py:2625-2626` — concern disposition
  glyphs, `"forward": "[bold yellow]☑[/]"`
- `.aitask-scripts/monitor/monitor_shared.py:3244` — `"[bold yellow]☑[/]"`
- `.aitask-scripts/brainstorm/widgets.py:419` —
  `"[bold yellow]☑[/] "` / `"[#6272A4]☐[/] "`
- `.aitask-scripts/brainstorm/brainstorm_dag_display.py:64` —
  `MARK_CHECKED_STYLE = Style(color="yellow", bold=True)`

Related but out of scope unless it falls out for free:
`monitor_shared.py:206-207` `MARK_GLYPH = "★"` / `MARK_EMPTY_GLYPH = "☆"` have
the same coverage gap (`U+2605`/`U+2606` are also missing from both nerd-font
packages).

## Scope

Decide and implement a mark rendering strategy that does not depend on system
font fallback or on the terminal's ANSI palette. The plan should weigh at least:

- **Glyph choice** — whether to keep `☑`/`☐` or move to codepoints the
  framework's own supported fonts actually cover. `U+2714` `✔` and `U+25CF` `●`
  are both **present** in the nerd-font packages and are candidates; note that
  t1004 explicitly rejected a dot for this meaning, and `monitor_shared.py:204`
  records that `☑`/`☐` was rejected for the *prioritisation* mark because it
  already means "selected for this action" — any change must preserve both of
  those distinctions rather than collapse them.
- **Text-presentation selector** — appending `U+FE0E` (VS15) to request text
  rather than emoji presentation, and whether Textual/Rich and the supported
  terminals honour it. This may fix the fallback asymmetry without changing the
  glyph, and is the least invasive option if it works.
- **Colour authority** — replacing the bare ANSI `yellow` with an explicit,
  theme-independent colour so checked/unchecked are governed by one authority,
  consistent with the existing literal `#6272A4`.
- **Single derivation point** — the glyph/style pair is currently duplicated
  across four modules with three different expression forms (Textual CSS class,
  Rich markup string, `rich.style.Style` object). Whatever is chosen should have
  one canonical definition with a drift guard, rather than five hand-synced
  copies.

## Acceptance criteria

- [ ] The checked and unchecked marks are governed by a single canonical
      definition; the four consuming modules derive from it rather than
      restating the glyph and colour independently.
- [ ] A guard fails if a consuming site reintroduces its own literal glyph or
      its own colour for the mark pair.
- [ ] Neither mark's colour is a bare ANSI palette name; both resolve to the
      same explicit colour authority.
- [ ] A render-level assertion (per the repo's `render().plain` convention)
      pins that the checked and unchecked marks both reach the composited output
      and are distinguishable from each other — not merely that the expected
      string constant was passed in.
- [ ] The chosen glyphs are documented together with the evidence for why they
      survive font fallback, so a future change cannot silently reintroduce an
      uncovered codepoint.
- [ ] The `★`/`☆` prioritisation mark's distinct meaning
      (`monitor_shared.py:204-230`) is preserved, and the doc records whether
      its identical coverage gap was fixed here or deliberately deferred to a
      named follow-up.

## Notes

The host-side remedy (repairing the user's fontconfig so `☑` no longer resolves
to a colour-emoji font) is a machine configuration fix and is deliberately **not**
part of this task — it would mask the framework fragility on one machine while
leaving every other user exposed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-30T10:36:36Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-30T10:58:24Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-30T11:00:11Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ef510509b0ff9f59

> **✅ gate:risk_evaluated** run=2026-08-30T11:00:11Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1638/risk_evaluated_2026-08-30T11:00:11Z-risk_evaluated-a1.log`
