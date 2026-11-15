---
priority: low
effort: medium
depends: [t2278_5]
issue_type: enhancement
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 6 of t2278 (docs TUI screenshot generator). The full design is in the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`. Children 1-5
delivered the tool, the skill and the images for the 17 former placeholders.

The 18 older images in `website/static/imgs/` were captured by hand. They use
two themes and four terminal sizes. This child adds a scene for each and
regenerates them, so every image on the site shares the pinned look.

By now no marker is left in the docs, so this child runs entirely on the scene
specs' `output:` fields.

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

- `website/screenshots/registry.py`: adapters for codebrowser, settings and
  stats, plus their fixtures.
- `website/screenshots/scenes/`: one spec per existing image, `output:` set to
  the existing filename.
- `website/static/imgs/`: replaced images.
- Pages only where a filename changes (see the two decisions below).

## Reference Files for Patterns

- `tests/test_codebrowser_startup_focus.py:131-190`: `_build_tree` (a git repo
  with `src/alpha.py`, `beta.py` and a recent-files history) and the cwd rule.
  `_apply_focus` uses a real 0.15 s timer; settle on a selector, not a pause.
- `tests/test_settings_shortcuts_tab.py:58-73`: a temp dir with
  `aitasks/metadata/userconfig.yaml`, `chdir`, and
  `keybinding_registry._reset_for_tests()`.
- `website/content/_index.md:11, 69-71, 81-115`: the home-page uses
  (`split-hero`, `tour-tile`, `static-img`).

## Implementation Plan

See `aiplans/p2278/p2278_6_regenerate_existing_images.md`. Its first step
proves the scene-to-file mapping is durable: with zero markers in the docs,
`capture --all` must stage every scene from children 2-4 under its original
filename, and `check_screenshots.py --owners` must list each of those images
with its scene.

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
- `cd website && python3 check_links.py --build` passes.
- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with a capture
  test for each new adapter.
- The home page and each TUI page are viewed on the local Hugo server.
