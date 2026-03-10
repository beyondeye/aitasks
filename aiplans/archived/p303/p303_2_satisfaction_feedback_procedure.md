---
Task: t303_2_satisfaction_feedback_procedure.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_1_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_4_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_2 — Satisfaction Feedback Procedure

## Steps

### 1. Add Model Self-Detection Sub-Procedure to procedures.md

Extract detection logic from current Agent Attribution Procedure into standalone sub-procedure. Input: none. Output: agent string.

### 2. Refactor Agent Attribution Procedure

Replace inline detection with: "Execute Model Self-Detection Sub-Procedure to get agent_string."

### 3. Add Satisfaction Feedback Procedure

New section in procedures.md with:
- Profile check (`enableFeedbackQuestions`, default enabled when absent)
- Call Model Self-Detection
- AskUserQuestion with 4 options (5/4/3/1-2 stars)
- Call `aitask_verified_update.sh` with result
- Display updated score

### 4. Update SKILL.md procedures list

Add the two new procedures to the reference list.

### 5. Update profile definitions and docs

- Add `enableFeedbackQuestions: true` to `aitasks/metadata/profiles/fast.yaml`
- Add `enableFeedbackQuestions: false` to `aitasks/metadata/profiles/remote.yaml`
- Mirror the same changes in `seed/profiles/fast.yaml` and `seed/profiles/remote.yaml`
- Document the new field in `.claude/skills/task-workflow/profiles.md`
- Add the field to the Settings TUI profile schema/help text in `.aitask-scripts/settings/settings_app.py`
- Update website docs so `/aitask-pick` links to a dedicated Execution Profiles subpage that documents `enableFeedbackQuestions`

### 6. Harden `aitask_verified_update.sh` for concurrent updates

- Replace the current one-shot local read/modify/write flow with a remote-aware retry strategy
- When a remote tracking branch exists, clone the latest task-data branch into a temp repo, apply exactly one vote update, commit, and push
- If the push is rejected because another agent/user updated the same branch first, discard the temp clone and retry from a fresh clone so no vote is lost
- After a successful push, sync the current task-data worktree so local metadata reflects the merged result
- Keep local-only behavior for repos without a remote

### 7. Extend regression tests

- Keep the existing validation and rolling-average tests
- Add coverage for the remote retry path so concurrent updates preserve both votes instead of losing one

## Verification

- procedures.md is internally consistent
- Agent Attribution still works after refactor
- New procedure references correct script paths
- `enableFeedbackQuestions` is documented consistently across workflow docs, shipped profiles, Settings TUI, and website docs
- concurrent remote updates to `aitask_verified_update.sh` preserve both votes after retry

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** Added a reusable Model Self-Detection Sub-Procedure and a new Satisfaction Feedback Procedure to `.claude/skills/task-workflow/procedures.md`, refactored Agent Attribution to reuse the shared detection flow, and updated the task-workflow procedures list accordingly. Replaced the earlier proposed `skip_satisfaction_feedback` concept with the new execution-profile key `enableFeedbackQuestions`, then wired that key through shipped/seed profiles, task-workflow profile docs, the Settings TUI schema/help text, and website docs. Also split the `/aitask-pick` website Execution Profiles section into a dedicated subpage and updated cross-links from pick, pickrem, pickweb, and the Claude Web workflow docs.
- **Deviations from plan:** Expanded scope to cover all profile-key exposure surfaces called out during review (Settings TUI, website docs, pickrem/pickweb references) and added explicit local-only fallback documentation/warning in `aitask_verified_update.sh`. Also hardened `aitask_verified_update.sh` beyond the original doc-only child-task scope by implementing remote-aware optimistic retries for concurrent updates and regression coverage for that behavior.
- **Issues encountered:** The first remote-retry test fixture cloned from a bare origin without setting its default branch, which produced an empty worktree; fixed by setting the bare repo HEAD to `main` before cloning. A second issue came from trying to simulate concurrency by recursively invoking the same script inside the hook; replaced with a direct competing remote commit to make the test deterministic. The Settings TUI edit also surfaced type-check warnings around nullable callbacks/selection state, which were resolved with small guards/casts while leaving runtime behavior unchanged.
- **Key decisions:** `enableFeedbackQuestions` defaults to enabled when omitted, matching the interactive-first profile model, while the shipped `remote` profile sets it to `false`. For concurrency safety, the verified-score updater now uses a temp clone of the latest remote-tracking task-data branch when a remote exists, applies exactly one vote, and retries on push rejection; when no remote exists it still works locally but emits a non-fatal warning that concurrency protection is unavailable.
- **Notes for sibling tasks:** Later tasks can call the documented Satisfaction Feedback Procedure and rely on `enableFeedbackQuestions` as the shared profile gate. The helper script `./.aitask-scripts/aitask_verified_update.sh` now has two modes: remote-aware retry when task data tracks a remote, and local-only update with warning when no remote exists. Any later doc or workflow changes around feedback should point users to `website/content/docs/skills/aitask-pick/execution-profiles.md` for the canonical website profile reference.
