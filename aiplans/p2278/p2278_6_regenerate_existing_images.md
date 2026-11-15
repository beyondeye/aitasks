---
Task: t2278_6_regenerate_existing_images.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_6 — regenerate the 18 existing images

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md`. Read the
archived plans of children 2-5.

## Steps

1. **Prove the mapping is durable.** Confirm `python3
   website/check_screenshots.py` lists zero unresolved markers. Run
   `website/screenshots.sh capture --all` and check that every scene from
   children 2-4 is staged under its `output` filename, and that
   `python3 website/check_screenshots.py --owners` lists each of those images
   with its scene. If either fails, stop: that is a defect in an earlier child,
   to be reported to it, not patched around here.

2. **Inventory.** Re-list `website/static/imgs/` and every `static-img`,
   `split-hero` and `tour-tile` use. For each existing image, record what state
   it shows (open it) and what its alt and caption claim.

3. **Adapters.** `codebrowser` (fixture git repo with source files, annotation
   data and a task history; settle on a selector, since `_apply_focus` uses a
   real timer), `settings` (temp `aitasks/metadata/`, reset the keybinding
   registry), `stats`. Each with a fixture using invented names, and a capture
   test with the double-capture byte-equality check.

4. **Scenes.** One per existing image, `output:` equal to the existing
   filename. `home/board.svg` and `aitasks_board_main_view.svg` currently hold
   the same content; give them two scenes or one scene plus a documented copy
   step, whichever keeps the one-scene-one-output rule intact (two scenes is
   the default).

5. **User decisions** (ask, do not assume): the `annotaitions` filename typo;
   the unreferenced `aitasks_settings_code_agent_default_models_tab.svg`.

6. **Review and apply.** `capture`, `preview` (it shows old beside new for
   replaced files), user review, `apply --batch`. For any image where the
   regenerated state no longer matches the alt or caption, fix the scene, not
   the prose, unless the user says otherwise.

## Verification

- `python3 website/check_screenshots.py --owners`: no `hand-made` image except
  those the user kept.
- `python3 website/check_screenshots.py --strict`;
  `cd website && python3 check_links.py --build`.
- `bash tests/run_all_python_tests.sh --test-dir tests`.
- Home page and each TUI page viewed on the local Hugo server.

## Notes for sibling tasks

Record: every scene that overrides the pinned look and why (child 8 reads it).

Post-implementation: Step 9 of the task workflow.
