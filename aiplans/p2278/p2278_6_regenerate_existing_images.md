---
Task: t2278_6_regenerate_existing_images.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_6: regenerate the 18 existing images

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` (revised
2026-11-15). Read the archived plans of children 2-5. This child is done with
the skill `aitask-docs-screenshots`; it writes datasets, not adapters.

## Steps

1. **Replay everything, prove the mapping, repair the drift.** Confirm
   `python3 website/check_screenshots.py` lists zero unresolved markers. Run
   `website/screenshots.sh replay --all`: every recipe from children 2-5 must
   stage its scene under its `output` filename, and
   `python3 website/check_screenshots.py --owners` must list each of those
   images with its scene. Run the skill's repair loop over the results: a
   `FAILED:` recipe, or a passing one whose image no longer matches its page,
   is re-discovered and replaced. A recipe that cannot be repaired is reported
   to the user. A defect in the tool itself is reported to the child that
   owns it, not patched around here.

2. **Inventory.** Re-list `website/static/imgs/` and every `static-img`,
   `split-hero` and `tour-tile` use. For each existing image, record what state
   it shows (open it) and what its alt and caption claim.

3. **Datasets.** Add the sample data these images need (codebrowser sources
   with history and annotations, archived tasks for stats, settings
   metadata), each a data builder with a build test and a live check that the
   real TUI shows it. Invented names only.

4. **Scenes.** One recipe per existing image, recorded through the discovery
   loop, `output:` equal to the existing filename. `home/board.svg` and
   `aitasks_board_main_view.svg` currently hold the same content; give them
   two recipes (one scene, one output).

5. **User decisions** (ask, do not assume): the `annotaitions` filename typo;
   the unreferenced `aitasks_settings_code_agent_default_models_tab.svg`.

6. **Review and apply.** `preview` (it shows old beside new for replaced
   files), user review, `apply --batch`. For any image where the regenerated
   state no longer matches the alt or caption, fix the recipe, not the prose,
   unless the user says otherwise.

## Verification

- `python3 website/check_screenshots.py --owners`: no `hand-made` image except
  those the user kept.
- `python3 website/check_screenshots.py --strict`;
  `website/screenshots.sh replay --all`;
  `cd website && python3 check_links.py --build`.
- `bash tests/run_all_python_tests.sh --test-dir tests`.
- Home page and each TUI page viewed on the local Hugo server.

## Notes for sibling tasks

Record: every recipe repaired in step 1 and why; every scene that needed a
size other than the default and why; datasets added (child 8 reads it).

Post-implementation: Step 9 of the task workflow.
