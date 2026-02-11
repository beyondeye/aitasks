---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 11:57
completed_at: 2026-02-11 11:57
---

## Context

This is child task 1 of parent task t85 (Cross-Platform aitask Framework Distribution). The goal is to extract the aitask framework from the tubetime project into its own GitHub repo `beyondeye/aitasks`, so it can be distributed independently and installed into any project.

The aitask framework currently consists of 8 bash scripts at the tubetime project root, a Python TUI app in `aitask_board/`, and 5 Claude Code skill definitions in `.claude/skills/`. All of these need to be copied into the new repo with a reorganized directory structure.

## What to Do

### 1. Create the local repo

```bash
mkdir -p ~/Work/aitasks
cd ~/Work/aitasks
git init
```

### 2. Create the directory structure

```
aitasks/
├── install.sh              # (created in t85_7, leave empty placeholder)
├── VERSION                  # contains "0.1.0"
├── ait                      # (created in t85_2, leave empty placeholder)
├── README.md                # (created in t85_10, leave empty placeholder)
├── .github/workflows/       # (release.yml created in t85_8)
├── aiscripts/
│   ├── aitask_setup.sh      # (created in t85_5, leave empty placeholder)
│   ├── aitask_create.sh     # copied from tubetime
│   ├── aitask_ls.sh         # copied from tubetime
│   ├── aitask_update.sh     # copied from tubetime
│   ├── aitask_import.sh     # copied from tubetime
│   ├── aitask_board.sh      # copied from tubetime
│   ├── aitask_stats.sh      # copied from tubetime
│   ├── aitask_clear_old.sh  # copied from tubetime
│   ├── aitask_issue_update.sh # copied from tubetime
│   └── board/
│       └── aitask_board.py  # copied from tubetime aitask_board/aitask_board.py
└── skills/
    ├── aitask-create/SKILL.md
    ├── aitask-create2/SKILL.md
    ├── aitask-pick/SKILL.md
    ├── aitask-stats/SKILL.md
    └── aitask-cleanold/SKILL.md
```

### 3. Copy files from tubetime

Source files in tubetime project (at `~/Work/tubetime/`):

**Bash scripts** (copy to `aiscripts/`):
- `aitask_create.sh` → `aiscripts/aitask_create.sh`
- `aitask_ls.sh` → `aiscripts/aitask_ls.sh`
- `aitask_update.sh` → `aiscripts/aitask_update.sh`
- `aitask_import.sh` → `aiscripts/aitask_import.sh`
- `aitask_board.sh` → `aiscripts/aitask_board.sh`
- `aitask_stats.sh` → `aiscripts/aitask_stats.sh`
- `aitask_clear_old.sh` → `aiscripts/aitask_clear_old.sh`
- `aitask_issue_update.sh` → `aiscripts/aitask_issue_update.sh`

**Python TUI**:
- `aitask_board/aitask_board.py` → `aiscripts/board/aitask_board.py`

**Claude Code skills** (copy to `skills/`):
- `.claude/skills/aitask-create/SKILL.md` → `skills/aitask-create/SKILL.md`
- `.claude/skills/aitask-create2/SKILL.md` → `skills/aitask-create2/SKILL.md`
- `.claude/skills/aitask-pick/SKILL.md` → `skills/aitask-pick/SKILL.md`
- `.claude/skills/aitask-stats/SKILL.md` → `skills/aitask-stats/SKILL.md`
- `.claude/skills/aitask-cleanold/SKILL.md` → `skills/aitask-cleanold/SKILL.md`

### 4. Create VERSION file

Write `0.1.0` to `VERSION` (no trailing newline is fine, but a single newline is preferred).

### 5. Create placeholder files

For files that will be created in subsequent child tasks, create empty placeholders:
- `ait` (placeholder, real content in t85_2)
- `install.sh` (placeholder, real content in t85_7)
- `aiscripts/aitask_setup.sh` (placeholder, real content in t85_5)
- `README.md` (placeholder, real content in t85_10)

### 6. Make scripts executable

```bash
chmod +x aiscripts/*.sh
```

### 7. Create the GitHub repo

```bash
gh repo create beyondeye/aitasks --public --source=. --push
```

If the user's `gh` is not authenticated or the repo already exists, handle gracefully. The initial commit should contain all the copied files.

### 8. Initial commit

```bash
git add -A
git commit -m "Initial import of aitask framework from tubetime project"
```

## Verification

1. `ls ~/Work/aitasks/aiscripts/` shows all 8 bash scripts + `board/` directory
2. `ls ~/Work/aitasks/skills/` shows 5 skill directories
3. `cat ~/Work/aitasks/VERSION` shows `0.1.0`
4. `gh repo view beyondeye/aitasks` shows the repo exists (if GitHub step was done)
