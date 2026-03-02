---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [ait_settings]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-02 13:34
updated_at: 2026-03-02 13:37
---

Two improvements for the Profiles tab in ait settings:

1. **Revert button**: Add a "Revert" button alongside Save/Delete that reverts all field values to the currently saved values (re-reads from YAML file and repopulates). This allows users to undo unsaved changes without leaving and re-entering the tab.

2. **Clarify project-scoped profiles**: Update the explanation text at the top of the Profiles tab to clearly state that execution profiles are project-specific (git-tracked, shared with all users). If a user modifies a profile, the change affects everyone.

3. **User-specific execution profiles**: Add support for user-local profiles that are gitignored and user-specific:
   - Store in `aitasks/metadata/profiles/local/` (gitignored directory)
   - User profiles override project profiles with the same name
   - Show a layer badge (PROJECT/USER) similar to Agent Defaults tab
   - When creating a new profile, ask whether it should be project or user-local
   - User profiles appear in the profile selector alongside project profiles
   - The profile scanner script (`aitask_scan_profiles.sh`) needs to be updated to scan both directories
