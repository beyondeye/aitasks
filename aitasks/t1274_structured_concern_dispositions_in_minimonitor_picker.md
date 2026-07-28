---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus5
created_at: 2026-07-28 01:03
updated_at: 2026-07-28 10:45
---

The minimonitor concern picker presents every shadow concern as an identical
flat row, so an `informational` finding (nothing to do — reported for the
user's judgement) is visually indistinguishable from a `blocking` one that
must be addressed. Separately, concern rows are sometimes rendered with no
title at all.

Make the picker distinguish concerns that need addressing from concerns that
are purely informational, and stop rows from losing their title.

## Part 1 — Disposition is not a machine-readable field

The shadow's disposition (`blocking` / `follow-up` / `informational`) is
emitted as **free prose at the tail of the concern body**, not as a parsed
field:

```
- [medium | accepted risk] Automated verification still does not execute a
  real Step-9 merge ... Disposition: informational. Verified: CONFIRMED.
```

`.claude/skills/aitask-shadow/impl-challenge.md:345` documents this as a
deliberate, currently-accepted "UX boundary":

> minimonitor displays and forwards the disposition/verdict text inside each
> concern body, but it has no native blocking / follow-up / informational
> sections, badges, filters, or separate actions yet — an `informational` item
> looks like any other row in the picker, distinguished only by its body text.
> Those affordances belong to the future concern-format redesign.

This task is that redesign, scoped to the disposition axis only.

**Live evidence** (window `agent-pick-1233`, shadow pane): a 3-concern block
where two items end `Disposition: informational.` and one ends
`Disposition: follow-up.` — all three parse to the same `Concern` shape and
render as identical rows.

### Design considerations (decide at planning time)

- **Where the disposition lives.** Options: a 4th marker field
  (`- [priority | disposition | region] body`), a separate optional token, or
  parsing the existing `Disposition: X.` prose out of the body. Each has a
  different back-compat story for blocks emitted by an older shadow — the
  parser must keep accepting today's 3-field markers and degrade to an
  "unspecified" disposition rather than dropping the item.
- **Presentation.** Grouping/section headers vs. a per-row badge vs. dimming
  informational rows vs. a filter toggle. Note the picker also runs in the
  **narrow** minimonitor variant (~40 cols, `ConcernPickerModal.narrow`), where
  a 1-line row already struggles: rows are `height: 1` and a long region can
  consume the entire row. Whatever is chosen must survive that width.
- **Selection semantics.** Consider whether `a` (select all) and `A`
  (copy ALL) should still include informational items, and whether the
  auto-offer notify should count them.

### Files in scope

- `.claude/skills/aitask-shadow/concern-format.md` — single source of truth
  for the block format; must be updated first.
- `.aitask-scripts/monitor/concern_parser.py` — `Concern` NamedTuple, `_ITEM`
  regex, `_join_split_marker`, `build_clipboard_payload`.
- `.aitask-scripts/monitor/monitor_shared.py` — `_ConcernRow.render()`
  (line ~573), `_CONCERN_BADGE`, `ConcernPickerModal` (grouping/CSS).
- Producer sub-procedures, all four of which restate the format inline:
  `impl-challenge.md`, `plan-challenge.md`, `plan-assumptions.md`,
  `plan-diagnose-errors.md` (Claude tree only — the `.agents/` and
  `.opencode/` shadow trees carry a `SKILL.md` wrapper with no mirrored
  sub-procedures).
- `tests/test_concern_parser.py`, `tests/test_concern_picker_modal.py`.
  Note `TestProducerShortRegionRule` already fails the build when a producer
  drops a format rule — an equivalent guard should cover the new field.

## Part 2 — Concerns rendered without a title

Reported symptom: picker rows frequently show no title (the `region` label).

Two silent-failure mechanisms were **confirmed by probing the parser
directly**, but neither was reproduced from live panes — 85 concerns across 6
live shadow panes yielded 0 empty regions. So planning must start with a
diagnostic step rather than assume a cause.

Confirmed mechanisms:

1. A marker with **no `|` separator** — `- [medium] body` — does not match
   `_ITEM`. Because the row contains a `]`, the split-marker recovery is not
   even attempted (`_parse_items` requires `"]" not in line`), so the line is
   treated as a wrap continuation: it is **appended to the previous concern's
   body**, or **silently dropped** when it is the first item in the block.
2. `- [medium | ] body` parses with `region=''`, which
   `_ConcernRow.render()` renders as a dim `—`.

Additional candidate observed live (pane for `agent-pick-40`): five markers
hard-wrapped mid-bracket and recovered by `_join_split_marker`, producing
long regions such as
`aiplans/archived/p40_dev_mirror_prod_test_account.md:565` (53 chars, well
over the producer's ≤30-char rule). In the narrow modal such a region
consumes the whole row — the inverse symptom (title present, body invisible)
and possibly what was actually seen. Worth confirming with the user which
shape they observed.

### Requirements

- Reproduce and identify the actual cause before changing behaviour; capture
  a failing sample into a fixture.
- A malformed marker must never be silently dropped or silently merged into
  the preceding concern — degrade visibly (parse with a placeholder region /
  surface a warning) so the failure is observable, consistent with how an
  unknown priority already degrades to `low` without dropping the item.
- Long regions must not squeeze the body out of the row in the narrow variant.

## Related work (not folded)

- **t1159** — shadow review-loop automation. The larger redesign of the
  shadow ↔ minimonitor feedback cycle; this task's format change is an input
  to it. Coordinate rather than duplicate.
- **t1182**, **t1222** — manual-verification carryovers whose checklists
  cover the concern picker (disposition/verdict text visible in bodies,
  blocking-first ordering, short regions). Their expectations will need
  re-reading if the row format changes.
- **t1216_3** — monitor-side concern picker (Ready). It reuses the same
  `ConcernPickerModal`, so any row-format change lands in both surfaces.

## Verification

- Unit tests over the parser for each disposition value, for absent/unknown
  dispositions (back-compat), and for the malformed-marker cases in Part 2.
- Render-level assertions on `_ConcernRow.render().plain` (and the modal's
  grouping widgets) at both the wide and narrow widths.
- A live check in a real minimonitor against a shadow block containing at
  least one item of each disposition.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T07:45:01Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-28T09:53:10Z status=pass attempt=1 type=human
