---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [reporting, documentation, web_site]
gates: [risk_evaluated]
anchor: 1544
followup_kind: risk_mitigation
created_at: 2026-08-24 22:52
updated_at: 2026-08-24 22:52
---

## Origin

Risk-mitigation ("after") follow-up for t1544_6, created at Step 8d after implementation landed.

## Risk addressed

`addresses: code-health — hand-pinned doc counts/column lists have no drift guard`

The `## Risk` bullet, verbatim:

> **The corrected prose re-pins hand-written counts and column lists with no
> drift guard** — the same shape that let this page claim "Four presets" while
> seven shipped, and let the skill doc claim 7 CSV columns against 12. Step 1
> removes the standalone count, which narrows but does not close it: the preset
> table, the 13-section list and the 12-column list all still duplicate source
> values by hand. · severity: medium

## Goal

Assert the doc↔source agreement that t1544_6 verified **by hand**, so it cannot
rot again silently. t1544_6's own verification is the working prototype — it
already ran and passed; this task turns it into a committed test.

Three claims to guard:

1. **Preset table.** Parse the markdown table under `## Built-in layouts
   (presets)` in `website/content/docs/tuis/stats/_index.md` and assert it equals
   `{k: [PANE_DEFS[i].title for i in v] for k, v in DEFAULT_PRESETS.items()}`
   (`.aitask-scripts/stats/stats_config.py`, `.aitask-scripts/stats/panes`). This
   exact comparison ran during t1544_6 and returned `True` — reuse it verbatim.
   It guards both the preset set and every pane title, which is what was wrong
   before ("Four presets ship with the framework, each bundling three panes"
   against seven presets with 2-4 panes each).

2. **CSV column lists.** Assert the column list documented in
   `website/content/docs/commands/board-stats.md` ("CSV export format") and in
   `.claude/skills/aitask-stats/SKILL.md` ("Export Format") matches the header
   `aitask_stats.write_csv` actually emits, and likewise for the
   `--csv-backlog` columns. The skill doc claimed 7 columns against the 10 the
   script emitted even before t1544_4 took it to 12 — it had been wrong for a
   long time with nothing to catch it.

3. **Rendered section list.** Assert the numbered "Statistics provided" list in
   `board-stats.md` (and the mirror in `.claude/skills/aitask-stats/SKILL.md`)
   has one entry per `^### ` section `render_text_report` emits, in the same
   order. t1544_6 checked this by pairing the doc list against
   `./ait stats | grep '^### '`.

## Notes

- **Do not assert on live `ait stats` output** for claim 3 if it makes the test
  depend on repo data — prefer rendering a report from a synthetic `StatsData`,
  or extract the section headings statically. The existing
  `tests/test_aitask_stats_py.py` shows how the module is driven in isolation.
- Claims 2 and 3 have **two** doc sites each (website + `.claude` skill). Guard
  both, or the skill tree drifts alone — which is exactly what happened.
- `.opencode/` and `.agents/` carry only a one-line flag list and are already
  covered by `aitask_skill_verify.sh`'s wrapper-parity check; they need nothing
  here.
- A parse failure (heading renamed, table restructured) must **fail**, not skip.
  A guard that silently finds nothing to compare is the failure mode this task
  exists to prevent.
