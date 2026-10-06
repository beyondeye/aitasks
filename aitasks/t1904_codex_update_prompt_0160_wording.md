---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, codex, codeagent]
assigned_to: dario-e@beyond-eye.com
anchor: 1892
followup_kind: upstream_defect
created_at: 2026-10-06 22:29
updated_at: 2026-10-06 22:32
---

## Origin
Spawned from t1900 during Step 8b review.

## Upstream defect
- `.aitask-scripts/monitor/prompt_patterns.py:290-293` — `codex_update_prompt` matches only the pre-0.160 wording (`Press enter to continue`). codex-cli 0.160.0 renders `enter continue · esc skip`, so the startup update dialog is no longer pattern-detected on followed panes. The review loop still classifies it as `dialog` structurally, through the option row.

## Diagnostic context
t1900 measured the 0.160.0 update dialog live:
- **Setup:** codex launched as a shadow (`-c tui.alternate_screen=never`), with an isolated `CODEX_HOME` whose `version.json` claimed 0.161.0, plus `CODEX_MANAGED_BY_NPM=1` (a mise install shows only a notice box instead of the dialog).
- **Fixtures:** the capture is stored as `CODEX_0160_INLINE_UPDATE_PROMPT_RAW` (live) and `CODEX_0160_INLINE_DISMISSED_UPDATE_RAW` (after "2. Skip") in `tests/review_loop_fixtures.py`.
- **Rendering:** the header now reads `Update available · 0.160.0 → 0.161.0`, and the hint line is `enter continue · esc skip`.

t1900 also made the review loop's whole-tail dialog sweep skip historical matches (`review_loop._codex_dialog_is_historical`). `test_review_loop.CodexHistoricalDialogTests.test_a_pattern_for_the_0160_wording_would_not_wedge_it` already shows that a pattern for the new wording is safe for the review loop.

## Suggested fix
Extend `codex_update_prompt` (or add a sibling pattern) to match the 0.160 option-3 row plus the new hint, keeping the `skip_trailing_blank_rows` top-aligned handling. Pin it with the 0.160 live fixture, and check followed-pane detection and the review loop together.
