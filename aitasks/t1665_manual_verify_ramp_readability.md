---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [shadow, aitask_monitormini, aitask_monitor, tui]
anchor: 1037
followup_kind: manual_verification
created_at: 2026-09-01 15:25
updated_at: 2026-09-01 15:25
---

## Origin

Risk-mitigation ("after") follow-up for t1651, created at Step 8d after implementation landed.

## Risk addressed

From `aiplans/p1651_*.md` `## Risk`:

> Reusing the badge's red/yellow for magnitude makes a *high improve* red, which
> reads as "bad" until the reader learns it means "big". Chosen deliberately
> over a second vocabulary · severity: low

## Why a human has to answer this

t1651 replaced a weight-only magnitude encoding (bold / plain / dim on a single
arrow glyph) with a colour ramp, and pinned the rendered result thoroughly: the
four values resolve to four distinct hexes, a high improve and a high worsen
resolve to the SAME hex and weight, the arrows keep their colours on rows whose
own text is muted, and the ramp survives the `xnarrow` and `xshort` tiers. All
of that is automated and green.

None of it establishes the thing this task exists to check. Whether a reader
**interprets** a red improve arrow as a negative signal is a judgement about
perception, and no captured-pane assertion can settle it — asserting otherwise
would be verification theatre. The ramp deliberately encodes *intensity*, not
valence: direction is already carried by the glyph, so `▲high` and `▼high` are
the same colour on purpose.

## The ramp as shipped

| magnitude | style | renders as |
|---|---|---|
| high | `bold red` | #ff0000 + bold |
| medium | `bold yellow` | #ffff00 + bold |
| low | `#808080` | grey |
| unspecified | `#6272A4` | muted blue, deliberately off the heat ramp |

Note these are **Textual's** palette values, not Rich's — `rich.style.Style.parse`
reports #800000 / #808000 for the same names, which is not what reaches a
Textual widget.

## Verification Steps

- Open the concern picker on a block carrying all four magnitude states, in a real minimonitor companion pane
- Are the four states separable at a glance, without consulting a legend?
- Do a high improve arrow and a high worsen arrow read as the SAME strength, rather than as good-vs-bad?
- Is a red improve arrow misread as a negative signal? (This is the risk being checked; a "yes" here is a real finding, not a nitpick)
- Is the closest pair — low grey #808080 vs unspecified muted blue #6272A4 — distinguishable on your terminal, theme and display?
- Do the arrows stay legible on an `.informational` row and on a rejected row, where the row's own text is muted?
- Compare against the badge three cells to the left: does sharing the red/yellow vocabulary help (one scale for "how much") or confuse?

## Outcome

If the ramp reads as valence rather than intensity, the follow-up is to pick a
second vocabulary for magnitude that does not collide with the badge's — the
alternative t1651 considered and rejected. `_MAGNITUDE_RAMP` in
`.aitask-scripts/monitor/monitor_shared.py` is the single retune site, and
`ConcernMagnitudeRampTests.RESOLVED` is the pin that must move with it.
