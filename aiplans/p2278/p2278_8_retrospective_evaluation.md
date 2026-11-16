---
Task: t2278_8_retrospective_evaluation.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_8: retrospective evaluation

The eleven questions are in the task file. They were fixed with the design
revision of 2026-11-15, before any evidence existed; do not add or drop
questions to fit what is found.

## Steps

1. Read every archived sibling plan under `aiplans/archived/p2278/`, in
   particular their "Notes for sibling tasks" and Final Implementation Notes.
2. Gather evidence per question:
   - Q1: `website/screenshots.sh replay --all --no-keep`; count `FAILED:`.
   - Q2: the repair records in the notes of children 5 and 6;
     `git log --oneline -- website/screenshots/scenes/` for replaced recipes.
   - Q3: the "primitives missed" notes of children 3-6; for unused verbs,
     the journal kinds that appear in no recipe.
   - Q4: `grep -c` over `website/screenshots/scenes/` for `setup:` entries and
     dataset names; the notes for refusals and reported scenes.
   - Q5, Q9: the user's review comments recorded by children 4, 5 and 6.
   - Q6: capture two batches of every scene and diff the images; classify
     each difference.
   - Q7: child 5 and child 6 notes.
   - Q8: child 5 notes and the current markers, if any.
   - Q10: `website/screenshots.sh session list`, `tmux` socket directory,
     `hyprctl monitors` (if child 7 was built), and the notes.
   - Q11: `ait ls` for the port tasks.
3. Write one verdict per question (pass / change) with its evidence into the
   plan's Final Implementation Notes.
4. For each "change" verdict, propose a follow-up task to the user and create
   the ones they confirm. Small doc corrections may be made directly.

## Verification

- Eleven verdicts recorded, each with evidence.
- `python3 website/check_screenshots.py --strict` and
  `cd website && python3 check_links.py --build` pass.

Post-implementation: Step 9 of the task workflow; archiving this child
completes the parent.
