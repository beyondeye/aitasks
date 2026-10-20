---
Task: t2074_12_broken_layout_docs.md
Parent Task: aitasks/t2074_branch_mode_layout_hardening.md
Sibling Tasks: aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_3_setup_layout_repair.md, aitasks/t2074/t2074_9_branch_layout_enforcement.md, aitasks/t2074/t2074_14_manual_verification_branch_mode_layout_hardening.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_12: Damaged branch-layout docs

The full detail is in the task description. Legacy documentation stays as it
is.

## Steps
1. Copy the exact refusal and recovery strings from the landed t2074_3 and
   t2074_9 code, and the `git-health` output.
2. Write the troubleshooting section. Cover:
   - every C1a and C1b state, including the wedged rebase and bisect states;
   - missing_storage cases A and B, the no-branch case and the mixed case;
   - the never-prune rule;
   - the narrowed reader contract.
3. Add `relref` links from `commands/setup-install.md` and `commands/sync.md`.
   Update the quote at `installation/_index.md:89`.
4. Check whether the aidocs detection descriptions need updating
   (`aitasks_extension_points.md`, `tui_conventions.md`).

## Verification
From `website/`: `hugo build --gc --minify`, then `python3 check_links.py
--build` (must pass), then `python3 check_link_relevance.py` and triage its
output.

## Step 9
Commit with `documentation: … (t2074_12)`, then archive.
