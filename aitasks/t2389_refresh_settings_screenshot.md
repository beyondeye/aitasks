---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [tui, execution_profiles]
gates: [risk_evaluated]
anchor: 2363
followup_kind: risk_mitigation
created_at: 2026-11-27 14:40
updated_at: 2026-11-27 14:40
---

## Origin

Risk-mitigation ("after") follow-up for t2380, created at Step 8d after implementation landed.

## Risk addressed

stale home/settings.svg screenshot without the restored layer badges

- The home/settings page screenshot (`website/static/imgs/home/settings.svg`, recipe `home_settings`) will not show the restored badges until it is regenerated. The recipe's `expect` lines still match, so nothing fails, but the image goes stale against the docs text. · severity: low · → mitigation: refresh_settings_screenshot

## Goal

Regenerate the `home_settings` TUI screenshot (`website/static/imgs/home/settings.svg`, recipe `website/screenshots/scenes/home_settings.yaml`) with the `aitask-docs-screenshots` skill, so the Agent Defaults rows show the `[PROJECT]` / `[USER]` layer badges that t2380 restored (commit ea8484647). The image is used on the home page and on `website/content/docs/tuis/settings/_index.md` ("The Agent Defaults tab shows which code agent and model is configured for each operation").

- Drive the real Settings TUI on the `settings` sample dataset at the recipe's 160x40 size, preview the batch, and apply it after review.
- The recipe's existing `expect` lines (`pick:  claudecode/opus5_5`, `shadow:  codex/gpt6_2_sol`, `(inherits project)`) still match as substrings. Consider adding `[PROJECT]` / `[USER]` expectations so a future regression of the badge is caught by the recipe.
