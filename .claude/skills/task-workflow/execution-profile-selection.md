# Execution Profile Selection Procedure (Interactive)

This procedure scans and selects an execution profile interactively. It is
referenced from Step 0a (or Step 0) in interactive skills: aitask-pick,
aitask-fold, aitask-review, aitask-pr-import, aitask-revert.
Also referenced from Step 3b in aitask-explore (deferred until after task creation).
Also referenced from Step 3b in task-workflow for profile refresh.

For the non-interactive auto-select variant, see `execution-profile-selection-auto.md`.

## Input

- `skill_name` (string, required) — The calling skill's name key (e.g., `"pick"`, `"fold"`, `"review"`, `"pr-import"`, `"revert"`, `"explore"`, `"qa"`). Used to look up default profiles.
- `profile_override` (string, optional) — Profile name from `--profile` argument. If provided, bypasses both default lookup and interactive selection.

## Procedure

### Check for override or default profile

**If `profile_override` is provided (non-null, non-empty):**

Scan profiles to find a match:

```bash
./.aitask-scripts/aitask_scan_profiles.sh
```

Parse all `PROFILE|<filename>|<name>|<description>` lines. Find the profile whose `name` field matches `profile_override` (case-sensitive).

- **If found:** Load it directly: `cat aitasks/metadata/profiles/<filename>`. Display: "Using profile override: \<name\> (\<description\>)". Store the profile and filename. **Skip the rest of this procedure.**
- **If not found:** Warn: "Profile '\<profile_override\>' not found, falling through to selection." Continue to the default check below.

**If `profile_override` is not provided (or not found above):**

Check for a default profile configured for this skill:
1. Read `aitasks/metadata/userconfig.yaml` (if exists) — extract `default_profiles.<skill_name>` value
2. Read `aitasks/metadata/project_config.yaml` (if exists) — extract `default_profiles.<skill_name>` value
3. Use the userconfig value if present; otherwise use the project_config value

If a default profile name was found:
- Scan profiles (if not already scanned above):
  ```bash
  ./.aitask-scripts/aitask_scan_profiles.sh
  ```
- Find the profile whose `name` field matches the default value
- **If found:** Load it directly: `cat aitasks/metadata/profiles/<filename>`. Display: "Using default profile for \<skill_name\>: \<name\> (\<description\>)". Store the profile and filename. **Skip the rest of this procedure.**
- **If not found:** Warn: "Default profile '\<value\>' for \<skill_name\> not found, falling through to selection." Continue to interactive selection below.

**If neither override nor default applies:** Continue with the existing scan/select flow below.

### Scan and select

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
