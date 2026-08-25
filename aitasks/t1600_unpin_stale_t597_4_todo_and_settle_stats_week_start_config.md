---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [reporting, tui]
anchor: 1544
followup_kind: upstream_defect
created_at: 2026-08-25 12:18
updated_at: 2026-08-25 12:18
---

## Origin

Found by t1544_8 (backlog stats retrospective), Q8 bullet 2.

## Defect

Two source comments name `t597_4` as pending work. That task **landed and is
archived** — it shipped with the stats TUI (`CHANGELOG.md:1215`) and did **not**
make the week start configurable:

- `.aitask-scripts/stats/panes/overview.py:13`
  `_WEEK_START_DOW = 1  # Monday; t597_4 will make this configurable.`
- `.aitask-scripts/stats/panes/backlog.py:12` forwards to that same TODO
  ("See the `t597_4` TODO in `overview.py`").

A comment pointing at a completed task reads as tracked work when nothing is
tracking it. t1544_8's plan relied on this premise and had to re-verify it.

## Underlying gap (still real)

`week_start` and `days` are persisted in `aitasks/metadata/stats_config.json`
(`stats/stats_config.py:30-31`, both in `_USER_KEYS`) but **never read** — the
TUI hardcodes Monday. Honouring them needs `resolve_week_start` moved from the
CLI (`aitask_stats.py:241`) into `lib/` first, which is what t597_4 was expected
to do and did not.

## Suggested fix

Two separable pieces; the first is the defect, the second is the feature:

1. **Re-point or remove the stale comments** so no source comment claims a
   landed task will do future work. Either drop the `t597_4` reference and state
   the hardcoding plainly, or point at this task.
2. **Decide whether the `week_start` / `days` keys should be honoured at all.**
   If yes, move `resolve_week_start` into `lib/` and read them in the TUI. If
   no, stop persisting them rather than leaving written-but-ignored config —
   a config key that is saved and never read is its own defect.

## Verification

- No source comment names `t597_4` as pending work
  (`grep -rn "t597_4" --include=*.py .aitask-scripts/` returns nothing, or only
  historical references that do not promise future behaviour).
- Whichever branch of step 2 is chosen, `week_start` / `days` are either read by
  the TUI or no longer persisted.
