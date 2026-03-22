---
Task: t426_2_update_profile_selection_procedures.md
Parent Task: aitasks/t426_default_execution_profiles.md
Sibling Tasks: aitasks/t426/t426_1_*.md, aitasks/t426/t426_3_*.md, aitasks/t426/t426_4_*.md, aitasks/t426/t426_5_*.md, aitasks/t426/t426_6_*.md
Archived Sibling Plans: aiplans/archived/p426/p426_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t426_2 — Update Profile Selection Procedures

## Context

The execution profile selection procedures are the central point where profiles are loaded. This task adds two new input parameters (`skill_name`, `profile_override`) and a resolution step that checks for overrides and defaults before falling through to the existing interactive/auto-select behavior.

## Steps

### 1. Update Interactive Procedure (`execution-profile-selection.md`)

**File:** `.claude/skills/task-workflow/execution-profile-selection.md`

Add an `## Input` section after the header (before `## Procedure`):

```markdown
## Input

- `skill_name` (string, required) — The calling skill's name key (e.g., `"pick"`, `"fold"`, `"review"`, `"pr-import"`, `"revert"`, `"explore"`). Used to look up default profiles.
- `profile_override` (string, optional) — Profile name from `--profile` argument. If provided, bypasses both default lookup and interactive selection.
```

Add a new resolution section at the beginning of `## Procedure`, before the existing "Scan available execution profiles" step:

```markdown
## Procedure

### Check for override or default profile

**If `profile_override` is provided (non-null, non-empty):**

Scan profiles to find a match:
\```bash
./.aitask-scripts/aitask_scan_profiles.sh
\```

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
  \```bash
  ./.aitask-scripts/aitask_scan_profiles.sh
  \```
- Find the profile whose `name` field matches the default value
- **If found:** Load it directly: `cat aitasks/metadata/profiles/<filename>`. Display: "Using default profile for \<skill_name\>: \<name\> (\<description\>)". Store the profile and filename. **Skip the rest of this procedure.**
- **If not found:** Warn: "Default profile '\<value\>' for \<skill_name\> not found, falling through to selection." Continue to interactive selection below.

**If neither override nor default applies:** Continue with the existing scan/select flow below.

### Scan and select (existing behavior)
```

Then keep the existing "Scan available execution profiles" content as-is, but under the "Scan and select" sub-heading.

### 2. Update Auto-Select Procedure (`execution-profile-selection-auto.md`)

**File:** `.claude/skills/task-workflow/execution-profile-selection-auto.md`

Update the `## Input` section to add the new parameters:

```markdown
## Input

- `mode_label` (string) — Display prefix for messages (e.g., `"Remote"` or `"Web"`)
- `skill_name` (string, required) — The calling skill's name key (e.g., `"pickrem"`, `"pickweb"`). Used to look up default profiles.
- `profile_override` (string, optional) — Profile name from `--profile` argument. If provided, bypasses both default lookup and auto-selection.
```

Add a resolution section at the beginning of `## Procedure`, identical in logic to the interactive version but with auto-select as the fallback:

```markdown
## Procedure

### Check for override or default profile

**If `profile_override` is provided (non-null, non-empty):**

Scan profiles:
\```bash
./.aitask-scripts/aitask_scan_profiles.sh
\```

Parse `PROFILE|<filename>|<name>|<description>` lines. Find the profile whose `name` field matches `profile_override`.

- **If found:** Load it directly. Display: "\<mode_label\> mode: Using profile override '\<name\>' (\<description\>)". Store profile and filename. **Skip the rest of this procedure.**
- **If not found:** Warn and continue to default check.

**If no override (or not found):**

Check `default_profiles.<skill_name>` in userconfig.yaml then project_config.yaml (same logic as interactive procedure). If found and matches a scanned profile, load it. Display: "\<mode_label\> mode: Using default profile for \<skill_name\>: \<name\> (\<description\>)". **Skip the rest of this procedure.**

If not found, warn and continue to auto-select below.

### Auto-select (existing behavior)
```

Then keep existing auto-select content under the new sub-heading.

### 3. Verify

- Read both updated procedure files end-to-end to verify consistency
- Ensure the existing scan/select/auto-select logic is preserved unchanged as the fallback path

## Files to Modify

- `.claude/skills/task-workflow/execution-profile-selection.md`
- `.claude/skills/task-workflow/execution-profile-selection-auto.md`

## Reference Files

- `aitasks/metadata/project_config.yaml` — where `default_profiles` is read from
- `aitasks/metadata/userconfig.yaml` — where personal `default_profiles` override is read from
- `.aitask-scripts/aitask_scan_profiles.sh` — profile scanner output format

## Final Implementation Notes
- **Actual work done:** Added `## Input` section and `### Check for override or default profile` resolution logic to both `execution-profile-selection.md` (interactive) and `execution-profile-selection-auto.md` (auto-select). Existing scan/select and auto-select flows preserved under new sub-headings as fallback paths. Exactly as planned.
- **Deviations from plan:** Added `"qa"` to the skill_name examples in the interactive procedure's Input section, consistent with t426_1's addition of `qa` to valid skill names. The auto-select version uses `"pickrem"`, `"pickweb"` examples as planned.
- **Issues encountered:** None. Both files edited cleanly in a single pass.
- **Key decisions:** Used `### Scan and select` (interactive) and `### Auto-select` (auto) as sub-heading names to clearly delineate the new resolution logic from the existing fallback behavior. The auto-select version uses slightly different display messages (prefixed with `<mode_label> mode:`) to match the existing auto-select convention.
- **Notes for sibling tasks:** t426_3 (add --profile arg to interactive skills) should pass `skill_name` and `profile_override` when invoking the interactive procedure. t426_4 (add --profile arg to auto-select skills) should pass `skill_name` and `profile_override` when invoking the auto-select procedure. Both procedures now accept these as documented inputs. The resolution order is: override → default (userconfig then project_config) → interactive/auto fallback.
