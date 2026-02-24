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

The "first email from emails.txt" pattern is broken for multi-user setups. Need a per-machine, gitignored config file.

## Implementation Steps

### Step 1: Create .gitignore entry
- Add `aitasks/metadata/userconfig.yaml` to `.gitignore`
- Add same pattern to `seed/.gitignore`

### Step 2: Add get_user_email() helper to task_utils.sh
```bash
get_user_email() {
  local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
  if [[ -f "$config" ]]; then
    grep '^email:' "$config" | sed 's/^email: *//'
  fi
}
```

### Step 3: Update ait setup
- In `aiscripts/aitask_setup.sh`, after email collection, write `userconfig.yaml`
- If file already exists, ask if user wants to update

### Step 4: Update execution profiles
- `aitasks/metadata/profiles/fast.yaml`: change `default_email: first` to `default_email: userconfig`
- `aitasks/metadata/profiles/remote.yaml`: same change

### Step 5: Update skill definitions
- `.claude/skills/task-workflow/SKILL.md` Step 4: add `userconfig` handling
  - When profile says `default_email: userconfig`, read from `get_user_email()` / `aitasks/metadata/userconfig.yaml`
  - Fall back to first email from emails.txt if userconfig missing
- `.claude/skills/aitask-pickrem/SKILL.md` Step 5: same change

### Step 6: Update aitask_own.sh
- If `--email` not provided, try reading from userconfig.yaml as fallback
- Use `get_user_email()` helper

### Step 7: Interactive email selection updates
- When user selects/enters email interactively (task-workflow Step 4), also update their userconfig.yaml
- Keeps userconfig in sync with user choices

## Key Files
- **Create:** `.gitignore` entry, `seed/.gitignore` entry
- **Modify:** `aiscripts/lib/task_utils.sh`, `aiscripts/aitask_setup.sh`, `aiscripts/aitask_own.sh`
- **Modify:** `aitasks/metadata/profiles/fast.yaml`, `aitasks/metadata/profiles/remote.yaml`
- **Modify:** `.claude/skills/task-workflow/SKILL.md`, `.claude/skills/aitask-pickrem/SKILL.md`

## Verification
- Verify userconfig.yaml is gitignored
- Run `ait setup`, verify it creates userconfig
- Verify `get_user_email()` works
- Verify profiles with `default_email: userconfig` read from userconfig.yaml

## Post-Implementation (Step 9)
Archive this child task.
