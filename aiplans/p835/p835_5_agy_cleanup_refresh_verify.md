---
Task: t835_5_agy_cleanup_refresh_verify.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_1_*.md, aitasks/t835/t835_2_*.md, aitasks/t835/t835_3_*.md, aitasks/t835/t835_4_*.md, aitasks/t835/t835_6_*.md
Archived Sibling Plans: aiplans/archived/p835/p835_1_*.md, p835_2_*.md, p835_3_*.md, p835_4_*.md (after they archive)
Inverse Blueprint: aiplans/archived/p812/p812_5_cleanup_pending_geminicli_aitasks.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Overview

Final cleanup pass for agy support:
1. Populate the real `models_agy.json` catalog via
   `/aitask-refresh-code-models`.
2. End-to-end verification of detection in a live agy session
   (absorbs the t835_2 fold concern, migrated from t401_3).
3. Delete the consumed migration reference `aidocs/geminicli_to_agy.md`.
4. Sanity-grep agy coverage across all touchpoints.

The full plan lives in the task description. The **load-bearing
reference** is the `### For t814 (add-agy): inverse instructions`
subsection in
`aiplans/archived/p812/p812_5_cleanup_pending_geminicli_aitasks.md`.

## Order of operations

1. **Refresh model catalog.** Run `/aitask-refresh-code-models` and
   select agy. Verify `aitasks/metadata/models_agy.json` now has real
   model entries (not the stub). Copy to `seed/models_agy.json` so
   future installs get the real list out-of-the-box. Commit both
   (separate commit from later steps so it can be reverted
   independently).

2. **Manual end-to-end verification.**
   - Launch agy: `agy` from this project's root.
   - From within agy, invoke `/aitask-pick` on any Ready task.
   - Confirm `./.aitask-scripts/aitask_parse_detected_agent.sh --agent agy --cli-id <id>`
     returns `AGENT_STRING:agy/<name>` matching an entry in the
     refreshed `models_agy.json`.
   - Confirm `implemented_with` is written correctly to the picked
     task's frontmatter on completion.
   - **If detection fails**, do NOT silently patch. Loop back to
     t835_1's surface choice and open a follow-up bug task.

3. **Delete consumed reference doc.**
   ```bash
   git rm aidocs/geminicli_to_agy.md
   ./ait git commit -m "chore: Delete consumed agy migration reference (t835_5)"
   ```
   Per parent task description, this file's content has been fully
   consumed by t835_1-4 and the archived t812 inverse-instruction
   subsections are the durable reference going forward.

4. **Sanity grep.** Confirm coverage and absence of accidental
   geminicli reintroduction:
   ```bash
   grep -rn "\bagy\b" .aitask-scripts/ seed/ install.sh .github/workflows/release.yml
   grep -rn "\bgeminicli\b" .aitask-scripts/ seed/ install.sh
   ```
   First should show agy in every expected touchpoint; second should
   be empty (intentional historical references in
   `aidocs/adding_a_new_codeagent.md` are excluded per t812_4 plan).

## Verification

- `aitasks/metadata/models_agy.json` has ≥1 real (non-stub) model.
- An agy CLI session completes `/aitask-pick` end-to-end with correct `implemented_with` attribution recorded in the picked task's frontmatter.
- `aidocs/geminicli_to_agy.md` no longer exists.
- `grep -rn "\bgeminicli\b" .aitask-scripts/ seed/ install.sh` returns empty.

## Step 9 reference

Standard task-workflow Step 9 archive after Step 8 approval. Note:
this child is **mostly verification work** — Step 8 approval should
focus on whether the e2e verification passed cleanly.
