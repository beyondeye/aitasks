---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [reporting, tui, documentation]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: upstream_defect
created_at: 2026-08-24 22:51
updated_at: 2026-08-25 09:51
---

## Origin

Spawned from t1544_6 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_stats.py:471 — the backlog footnote prints "~0.3%" as a hardcoded literal, a frozen t1544_3 sample with no maintained metric behind it; stats/panes/backlog.py mirrors the line verbatim and t1544_5's CLI-parity test pins the pair, so changing it is a coupled code+test edit. Out of scope for a docs task. t1544_8 (retrospective) carries the same figure.`
- `aitasks/metadata/stats_config.json — pins five of the seven presets (sessions and backlog are absent). Harmless today because deep_merge merges the presets dict per key, so the code-only presets still appear; but the parent task's scope asked for both sites to be updated, and t1544_5 deliberately left the JSON alone (its Deliverable 3 required no config change). Recorded because the divergence is now documented behaviour rather than a silent inconsistency.`

## Diagnostic context

t1544_6 documented the two completion clocks the backlog sections use. The task
text asked the docs to state that the clocks "can name a different week for
~0.3% of tasks". Verification showed that figure is **not** computed: it is a
literal in the footnote string at `aitask_stats.py:471`, taken from a one-time
t1544_3 measurement (26 of ~1828 archived tasks differ by a day, 6 by a week
bucket — the 0.3% is the by-week figure). It drifts with every task added or
metadata repair, and nothing recomputes or guards it.

The docs therefore deliberately omit the percentage and state the behavioural
invariant instead (the two clocks agree on *whether* a task completed and can
disagree on *which week*). That leaves the rendered CLI and TUI output as the
only surfaces still asserting a stale number to users.

The second defect was found while correcting the claim that presets are defined
in `aitasks/metadata/stats_config.json`. They are defined in
`.aitask-scripts/stats/stats_config.py::DEFAULT_PRESETS`; the JSON is an
override layer that currently pins five of the seven presets.

## Suggested fix

For the footnote: either drop the percentage from the rendered string (keeping
the invariant sentence, matching what the docs now say), or compute it from the
data already collected. Note the coupling — `stats/panes/backlog.py`'s
diagnostic line is asserted equal to the CLI footnote by a t1544_5 parity test,
so both sites and the test move together.

For `stats_config.json`: decide whether the shipped JSON should mirror
`DEFAULT_PRESETS` at all. Since `deep_merge` merges the `presets` dict per key,
the file is only needed to *override*; shipping a partial copy of the code
defaults invites exactly this drift. Removing the redundant entries may be
better than completing them.
