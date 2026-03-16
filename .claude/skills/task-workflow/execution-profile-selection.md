# Execution Profile Selection Procedure (Interactive)

This procedure scans and selects an execution profile interactively. It is
referenced from Step 0a (or Step 0) in interactive skills: aitask-pick,
aitask-explore, aitask-fold, aitask-review, aitask-pr-import, aitask-revert.
Also referenced from Step 3b in task-workflow for profile refresh.

For the non-interactive auto-select variant, see `execution-profile-selection-auto.md`.

## Procedure

Scan available execution profiles:

```bash
./.aitask-scripts/aitask_scan_profiles.sh
```

Parse the output lines. Each valid profile appears as `PROFILE|<filename>|<name>|<description>`. Lines starting with `INVALID|<filename>` indicate profiles with bad YAML — warn the user ("Profile '\<filename\>' has invalid format, skipping").

**If output is `NO_PROFILES`:** Skip this step (no profile active, all questions asked normally).

**If exactly one `PROFILE` line:** Auto-load it and inform user: "Using execution profile: \<name\> (\<description\>)". Read the full profile: `cat aitasks/metadata/profiles/<filename>`

**If multiple `PROFILE` lines:** Use `AskUserQuestion`:
- Question: "Select an execution profile (pre-configured answers to reduce prompts):"
- Header: "Profile"
- Options:
  - Each profile: label = `name` field, description = `description` field
  - "No profile" (description: "Ask all questions interactively")

**If "No profile" selected:** Proceed with all questions asked normally (no active profile).

**After selection:** Read the chosen profile file: `cat aitasks/metadata/profiles/<filename>`. Store the profile in memory for use throughout remaining steps. Store the `<filename>` value as `active_profile_filename`.
