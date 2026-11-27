---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui, execution_profiles]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2363
followup_kind: upstream_defect
created_at: 2026-11-27 10:37
updated_at: 2026-11-27 10:38
---

## Origin

Spawned from t2371 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/profile_editor.py:ConfigRow.render` — the `[PROJECT]`/`[USER]` layer badge never draws. The old markup `"[#50FA7B][PROJECT][/]"` parsed `[PROJECT]` as an unknown style tag, and `[/]` closed that tag, so only the colour stayed open over the rest of the row. A mounted row draws `    k:  v` with no badge text. t2371 kept the badge blank to preserve output.

## Diagnostic context

t2371 rebuilt `ConfigRow.render` as `textual.content.Content` (key and value literal, trusted `suffix`). Probe on Textual 8.2.7: `Content.from_markup("  [#50FA7B][PROJECT][/]  [bold]k:[/bold]  v")` gives plain `'    k:  v'` with `Span(2, end, '#50FA7B')`. To stay byte- and style-identical, t2371 emits an empty badge and applies the layer colour to the post-badge tail via `stylize_before(color)` (see the comment in `ConfigRow.render`). The pin is `tests/test_configrow_markup_escape.py::RowRenderTests::test_ordinary_rows_match_the_old_render_in_text_and_style`, an oracle against the verbatim old render.

## Suggested fix

Decide whether the badge should draw at all. Restoring it (e.g. `Content.styled("[PROJECT]", "#50FA7B")`, with the key/value colour decided explicitly) adds 9-11 columns to every settings row: re-check the clipping-sensitive tests (`tests/test_settings_superseded_models.py` negative control, 80-col layouts) and update the old-render oracle, which intentionally pins today's output. Alternatively, drop the dead badge code and the leaked colour, or keep the colour as the layer signal.
