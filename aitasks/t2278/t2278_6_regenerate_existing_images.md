---
priority: low
effort: medium
depends: [t2278_5]
issue_type: enhancement
status: Implementing
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-20 09:04
---

## Context

Child 6 of t2278 (docs TUI screenshot generator). Read the parent plan
`aiplans/p2278_docs_tui_screenshot_generator.md` first; the design was revised
on 2026-11-15 to an agent driving the real TUI in an isolated tmux session.
Children 1-5 delivered the tool, the skill (discovery and repair loops) and
the images for the 17 former placeholders.

The 18 older images in `website/static/imgs/` were captured by hand, from the
real repo, in two themes and four terminal sizes. This child regenerates each
with the same workflow, so every image on the site comes from the sample
project and has a recipe.

By now no marker is left in the docs, so this child runs entirely on the
recipes' `output:` fields. It is also the first real use of the repair loop
on recipes that have aged.

## Existing images (19 `static-img` uses, 18 distinct files; re-list before use)

- Board: `aitasks_board_main_view.svg`, `aitasks_board_task_detail.svg`,
  `aitasks_board_customize_column.svg`, `aitasks_board_commit.svg`,
  `home/board.svg` (same content as the main view; used by `split-hero`),
  `home/child_tasks.svg`.
- Codebrowser: `aitasks_codebrowser.svg`,
  `aitasks_codebrowser_w_annotations.svg`,
  `aitasks_codebrowser_w_annotaitions_w_details.svg` (typo in the name),
  `codebrowser_task_history.svg`, `home/codebrowser.svg`.
- Settings: `home/settings.svg`,
  `aitasks_settings_select_model_step1_codeagent.svg`,
  `aitasks_settings_select_model_step2_llmmodel.svg`,
  `aitasks_settings_board_tab.svg`, `aitasks_settings_llmmodels_tab.svg`,
  `aitasks_settings_execution_profiles_tab.svg`.
- Monitor: `home/monitor.svg`. Stats: `home/statistics.svg`.
- `aitasks_settings_code_agent_default_models_tab.svg` is referenced nowhere.

## Key Files to Modify

- `website/screenshots/sample_project.py`: datasets for what these images
  show and the sample project lacks: source files with task history and
  annotations (codebrowser), archived tasks over several weeks (stats), model
  and profile metadata (settings). Data builders only.
- `website/screenshots/scenes/`: one recorded recipe per existing image,
  `output:` equal to the existing filename.
- `website/static/imgs/`: replaced images.
- Pages only where a filename changes (see the two decisions below).

## Reference Files for Patterns

- The existing images themselves: open each to see the state it shows.
- `website/content/_index.md:11, 69-71, 81-115`: the home-page uses
  (`split-hero`, `tour-tile`, `static-img`).
- `.claude/skills/aitask-docs-screenshots/SKILL.md` (child 5): the loops.
- `aiplans/archived/p2278/p2278_5_*.md`: repairs and missing primitives
  recorded in the first pass.

## Implementation Plan

See `aiplans/p2278/p2278_6_regenerate_existing_images.md`. Its first step
replays every recipe recorded so far, proves the scene-to-file mapping is
durable with zero markers in the docs, and repairs what has drifted.

Two decisions go to the user, not to the implementer:

- rename `aitasks_codebrowser_w_annotaitions_w_details.svg` to fix the typo
  (one page edit), or keep the name;
- delete or keep the unreferenced
  `aitasks_settings_code_agent_default_models_tab.svg`.

Old and new images are shown side by side before anything is replaced. A
regenerated image must show the same state its alt and caption describe.

## Verification Steps

- `python3 website/check_screenshots.py --owners` lists no image as
  `hand-made` except any the user chose to keep.
- `python3 website/check_screenshots.py --strict` exits 0.
- `website/screenshots.sh replay --all` passes.
- `cd website && python3 check_links.py --build` passes.
- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with a build
  test for each new dataset.
- The home page and each TUI page are viewed on the local Hugo server.
