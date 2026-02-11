---
Task: t85_1_create_aitasks_github_repo.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_2_*.md, aitasks/t85/t85_3_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_1 - Create aitasks GitHub Repo

## Context

Extract the aitask framework from tubetime into its own GitHub repo `beyondeye/aitasks`. This is the first child task of t85 (Cross-Platform aitask Framework Distribution) and sets up the repo structure that all subsequent tasks build on.

## Steps

### 1. Create local repo
```bash
mkdir -p ~/Work/aitasks && cd ~/Work/aitasks && git init
```

### 2. Create directory structure
```bash
mkdir -p aiscripts/board skills/{aitask-create,aitask-create2,aitask-pick,aitask-stats,aitask-cleanold} .github/workflows
```

### 3. Copy bash scripts from tubetime to `aiscripts/`
Source → Destination:
- `~/Work/tubetime/aitask_create.sh` → `aiscripts/aitask_create.sh`
- `~/Work/tubetime/aitask_ls.sh` → `aiscripts/aitask_ls.sh`
- `~/Work/tubetime/aitask_update.sh` → `aiscripts/aitask_update.sh`
- `~/Work/tubetime/aitask_issue_import.sh` → `aiscripts/aitask_issue_import.sh` (replaces deleted aitask_import.sh)
- `~/Work/tubetime/aitask_board.sh` → `aiscripts/aitask_board.sh`
- `~/Work/tubetime/aitask_stats.sh` → `aiscripts/aitask_stats.sh`
- `~/Work/tubetime/aitask_clear_old.sh` → `aiscripts/aitask_clear_old.sh`
- `~/Work/tubetime/aitask_issue_update.sh` → `aiscripts/aitask_issue_update.sh`

### 4. Copy Python TUI
- `~/Work/tubetime/aitask_board/aitask_board.py` → `aiscripts/board/aitask_board.py`

### 5. Copy Claude Code skills
- `~/Work/tubetime/.claude/skills/aitask-create/SKILL.md` → `skills/aitask-create/SKILL.md`
- `~/Work/tubetime/.claude/skills/aitask-create2/SKILL.md` → `skills/aitask-create2/SKILL.md`
- `~/Work/tubetime/.claude/skills/aitask-pick/SKILL.md` → `skills/aitask-pick/SKILL.md`
- `~/Work/tubetime/.claude/skills/aitask-stats/SKILL.md` → `skills/aitask-stats/SKILL.md`
- `~/Work/tubetime/.claude/skills/aitask-cleanold/SKILL.md` → `skills/aitask-cleanold/SKILL.md`

### 6. Create VERSION file
Write `0.1.0` to `VERSION`.

### 7. Create placeholder files
- `ait` (empty, for t85_2)
- `install.sh` (empty, for t85_7)
- `aiscripts/aitask_setup.sh` (empty, for t85_5)
- `README.md` (empty, for t85_10)

### 8. Make scripts executable
```bash
chmod +x aiscripts/*.sh
```

### 9. Initial commit
```bash
git add -A
git commit -m "Initial import of aitask framework from tubetime project"
```

### 10. Create GitHub repo and push
```bash
gh repo create beyondeye/aitasks --public --source=. --push
```

## Post-Implementation (Step 9 of aitask-pick)
Archive child task and plan files, update parent's children_to_implement.

## Verification
1. `ls ~/Work/aitasks/aiscripts/` shows all 8 bash scripts + `board/` directory
2. `ls ~/Work/aitasks/skills/` shows 5 skill directories each with SKILL.md
3. `cat ~/Work/aitasks/VERSION` shows `0.1.0`
4. `gh repo view beyondeye/aitasks` shows the repo exists

## Final Implementation Notes
- **Actual work done:** Created `~/Work/aitasks/` repo with the full directory structure. Copied 8 bash scripts (using `aitask_issue_import.sh` instead of deleted `aitask_import.sh`), Python TUI, and 5 Claude Code skills. Created VERSION file with `0.1.0`. Created empty placeholders for `ait`, `install.sh`, `aitask_setup.sh`, `README.md`.
- **Deviations from plan:** Replaced `aitask_import.sh` (deleted from git) with `aitask_issue_import.sh` as confirmed by user. Total of 9 scripts (8 real + 1 placeholder) in `aiscripts/`.
- **Issues encountered:** None.
- **Key decisions:** Used `aitask_issue_import.sh` as the replacement for deleted `aitask_import.sh`.
- **Notes for sibling tasks:** The repo is at `~/Work/aitasks/`. Scripts are in `aiscripts/`, skills in `skills/`. The `.github/workflows/` directory exists but is empty (for t85_8). Placeholder files `ait`, `install.sh`, `aiscripts/aitask_setup.sh`, and `README.md` are empty and need to be populated by their respective tasks.
