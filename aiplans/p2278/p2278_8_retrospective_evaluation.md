---
Task: t2278_8_retrospective_evaluation.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_8 — retrospective evaluation

The eight questions are in the task file. They are fixed before the evidence is
read; do not add or drop questions to fit what is found.

## Steps

1. Read every archived sibling plan under `aiplans/archived/p2278/`, in
   particular their "Notes for sibling tasks" and Final Implementation Notes.
2. Gather evidence per question:
   - Q1: for each spec field, count the scenes that use it
     (`grep -l` over `website/screenshots/scenes/`); list adapter hooks used by
     exactly one scene.
   - Q2: list scenes overriding `size`, theme or title.
   - Q3: `git log --oneline -- tests/lib/board_fixture.py` and the other
     imported fixtures since child 2 landed; for each change, did a screenshot
     test fail?
   - Q4: `website/screenshots.sh capture --all` twice; `cmp` every image.
   - Q5 and Q7: child 5 and child 6 notes.
   - Q6: child 5 notes and the current markers, if any.
   - Q8: `ait ls` for the port tasks.
3. Write one verdict per question (pass / change) with its evidence into the
   plan's Final Implementation Notes.
4. For each "change" verdict, propose a follow-up task to the user and create
   the ones they confirm. Small doc corrections may be made directly.

## Verification

- Eight verdicts recorded, each with evidence.
- `python3 website/check_screenshots.py --strict` and
  `cd website && python3 check_links.py --build` pass.

Post-implementation: Step 9 of the task workflow; archiving this child
completes the parent.
