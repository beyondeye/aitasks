# Execution Profile Selection Procedure (Auto-Select)

This procedure auto-selects an execution profile without interactive prompts.
It is referenced from Step 1 in non-interactive skills: aitask-pickrem,
aitask-pickweb.

For the interactive variant with `AskUserQuestion`, see `execution-profile-selection.md`.

## Input

- `mode_label` (string) — Display prefix for messages (e.g., `"Remote"` or `"Web"`)

## Procedure

Auto-select an execution profile:

```bash
./.aitask-scripts/aitask_scan_profiles.sh --auto
```

**If output is `NO_PROFILES`:** Display error: "\<mode_label\> workflow requires an execution profile. Create one at `aitasks/metadata/profiles/remote.yaml`." Abort.

**If output starts with `AUTO_SELECTED|`:** Parse the line as `AUTO_SELECTED|<filename>|<name>|<description>`. Display: "\<mode_label\> mode: Using profile '\<name\>' (\<description\>)". Read the full profile: `cat aitasks/metadata/profiles/<filename>`. Store all profile fields in memory for use throughout remaining steps.

**Error handling:** If `INVALID|<filename>` lines appear on stderr, display error "Profile '\<filename\>' has invalid format" and abort if no valid profiles remain.
