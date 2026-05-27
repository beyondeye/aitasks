# Execution Profile Selection Procedure (Auto-Select)

This procedure auto-selects an execution profile without interactive prompts.
It is referenced from Step 1 in non-interactive skills: aitask-pickrem,
aitask-pickweb.

For the interactive variant with `AskUserQuestion`, see `execution-profile-selection.md`.

## Input

- `mode_label` (string) — Display prefix for messages (e.g., `"Remote"` or `"Web"`)
- `skill_name` (string, required) — The calling skill's name key (e.g., `"pickrem"`, `"pickweb"`). Used to look up default profiles.
- `profile_override` (string, optional) — Profile name from `--profile` argument. If provided, bypasses both default lookup and auto-selection.

## Procedure

### Check for override or default profile

**If `profile_override` is provided (non-null, non-empty):**

Scan profiles:

```bash
./.aitask-scripts/aitask_scan_profiles.sh
```

Parse `PROFILE|<filename>|<name>|<description>` lines. Find the profile whose `name` field matches `profile_override`.

- **If found:** Load it directly. Display: "\<mode_label\> mode: Using profile override '\<name\>' (\<description\>)". Store profile and filename. **Skip the rest of this procedure.**
- **If not found:** Warn: "Profile '\<profile_override\>' not found, falling through to auto-select." Continue to the default check below.

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
- **If found:** Load it directly. Display: "\<mode_label\> mode: Using default profile for \<skill_name\>: \<name\> (\<description\>)". Store profile and filename. **Skip the rest of this procedure.**
- **If not found:** Warn: "Default profile '\<value\>' for \<skill_name\> not found, falling through to auto-select." Continue to auto-select below.

**If neither override nor default applies:** Continue with the existing auto-select flow below.

### Auto-select

Auto-select an execution profile:

```bash
./.aitask-scripts/aitask_scan_profiles.sh --auto
```

**If output is `NO_PROFILES`:** Display error: "\<mode_label\> workflow requires an execution profile. Create one at `aitasks/metadata/profiles/remote.yaml`." Abort.

**If output starts with `AUTO_SELECTED|`:** Parse the line as `AUTO_SELECTED|<filename>|<name>|<description>`. Display: "\<mode_label\> mode: Using profile '\<name\>' (\<description\>)". Read the full profile: `cat aitasks/metadata/profiles/<filename>`. Store all profile fields in memory for use throughout remaining steps.

**Error handling:** If `INVALID|<filename>` lines appear on stderr, display error "Profile '\<filename\>' has invalid format" and abort if no valid profiles remain.
