---
Task: t227_5_introduce_peruser_config_file_userconfig_yaml.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_1_*.md, aitasks/t227/t227_2_*.md, aitasks/t227/t227_3_*.md, aitasks/t227/t227_4_*.md, aitasks/t227/t227_6_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_5 — Introduce per-user config file (userconfig.yaml)

## Context

The `fast` and `remote` execution profiles use `default_email: first` which reads the first email from the shared `aitasks/metadata/emails.txt`. In multi-user setups, the "first" email could be any team member's. We need a per-machine, gitignored config file so each user has their own identity.

## Implementation Steps

### Step 1: Gitignore the userconfig file [DONE]

- Added `aitasks/metadata/userconfig.yaml` to data branch `.gitignore` (`.aitask-data/.gitignore`)
- Updated setup script to add the entry during `ait setup`

### Step 2: Add `get_user_email()` helper to `task_utils.sh` [DONE]

- Added to `aiscripts/lib/task_utils.sh` after `task_push()`
- Reads `email:` field from `aitasks/metadata/userconfig.yaml`

### Step 3: Update `ait setup` to create userconfig.yaml [DONE]

- Added `setup_userconfig()` function to `aiscripts/aitask_setup.sh`
- Prompts for email (with git config default), writes userconfig.yaml
- Adds gitignore entry for data branch
- Called in main() after `setup_data_branch`

### Step 4: Update execution profiles [DONE]

- `aitasks/metadata/profiles/fast.yaml`: `default_email: first` → `userconfig`
- `aitasks/metadata/profiles/remote.yaml`: same
- `seed/profiles/fast.yaml`: same

### Step 5: Update skill definitions — email resolution priority [DONE]

Email resolution logic:
1. Read `assigned_to` from task metadata and `email` from `userconfig.yaml`
2. If both set and DIFFER: ask user which to use (mismatch = possibly different user)
3. If `assigned_to` set (matches userconfig or userconfig empty): use `assigned_to`
4. If only userconfig set: use userconfig email
5. Profile-based fallback (`default_email: first` or literal): existing behavior
6. Interactive question: if no profile setting and no other source

Files modified: `.claude/skills/task-workflow/SKILL.md` Step 4, `.claude/skills/aitask-pickrem/SKILL.md` Step 5

### Step 6: Update `aitask_own.sh` fallback [DONE]

- When `--email` not provided: read `assigned_to` from task → userconfig → proceed without
- Added fallback chain in main() after parse_args/sync_remote

### Step 7: Interactive email sync (ask before updating) [DONE]

- Added in task-workflow/SKILL.md Step 4: userconfig sync check after email resolution
- Asks user before updating userconfig when email differs
- Offers to create userconfig if it doesn't exist

## Key Files
- **Modified:** `aiscripts/lib/task_utils.sh`, `aiscripts/aitask_setup.sh`, `aiscripts/aitask_own.sh`
- **Modified:** `aitasks/metadata/profiles/fast.yaml`, `aitasks/metadata/profiles/remote.yaml`, `seed/profiles/fast.yaml`
- **Modified:** `.claude/skills/task-workflow/SKILL.md`, `.claude/skills/aitask-pickrem/SKILL.md`
- **Modified:** `.aitask-data/.gitignore`

## Verification
- Verify userconfig.yaml is gitignored
- Verify `get_user_email()` works
- Verify profiles with `default_email: userconfig` read from userconfig.yaml
- Verify `aitask_own.sh` falls back to userconfig when `--email` not provided

## Final Implementation Notes

- **Actual work done:** Implemented all 7 steps as planned. Added `get_user_email()` shell helper, `setup_userconfig()` in ait setup, email fallback chain in `aitask_own.sh`, updated profiles from `first` to `userconfig`, and rewrote Step 4 of both `task-workflow` and `aitask-pickrem` SKILLs with the new email resolution priority chain.
- **Deviations from plan:** The original plan mentioned `seed/.gitignore` which doesn't exist — this was corrected to update the data branch `.gitignore` programmatically in the setup script instead.
- **Issues encountered:** None.
- **Key decisions:** The email resolution priority is: assigned_to (task metadata) > userconfig.yaml > profile-based (first/literal) > interactive. Mismatch between assigned_to and userconfig triggers an interactive confirmation in task-workflow, or prefers assigned_to silently in aitask-pickrem. Userconfig updates always require user confirmation.
- **Notes for sibling tasks:** The `get_user_email()` function in `task_utils.sh` is available for any script that sources it. The `default_email: userconfig` sentinel value is now documented in the Profile Schema Reference. Sibling task t227_6 (documentation) should mention userconfig.yaml in the Claude Web workflow docs.

## Post-Implementation (Step 9)
Archive this child task via `aitask_archive.sh 227_5`.
