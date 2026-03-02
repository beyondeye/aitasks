---
priority: low
effort: low
depends: [281]
issue_type: chore
status: Done
labels: [ait_settings, ait_skills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claude/opus4_6
created_at: 2026-03-02 14:03
updated_at: 2026-03-02 14:36
completed_at: 2026-03-02 14:36
---

The profile scanner (aitask_scan_profiles.sh) now outputs local/<filename> as the filename for user-local profiles. Skills that read profile files after scanner output need to update their profile resolution logic to use the scanner-returned path directly (e.g., cat aitasks/metadata/profiles/<returned_filename> which resolves to aitasks/metadata/profiles/local/fast.yaml for user profiles). Skills to update: aitask-pick, aitask-explore, aitask-fold, aitask-review, aitask-pr-review, task-workflow (Step 3b profile refresh).
