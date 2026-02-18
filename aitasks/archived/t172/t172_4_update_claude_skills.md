---
priority: high
effort: medium
depends: [t172_1]
issue_type: refactor
status: Done
labels: [aitask_review, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 22:04
updated_at: 2026-02-18 23:21
completed_at: 2026-02-18 23:21
---

## Context

Child task 4 of t172 (rename reviewmode to reviewguide). Updates all three Claude Code skill files to use the new naming and paths. Depends on t172_1 (directory moves) being complete.

## Key Files to Modify

### 1. `.claude/skills/aitask-reviewguide-classify/SKILL.md` (dir renamed in t172_1)

The classify skill was previously `aitask-reviewmode-classify`. Full content update needed:

**Frontmatter:**
- `name: aitask-reviewmode-classify` → `name: aitask-reviewguide-classify`
- `description:` update "review mode" → "review guide"

**All path references:**
- `aitasks/metadata/reviewmodes/` → `aireviewguides/`
- `aitasks/metadata/reviewmodes/reviewtypes.txt` → `aireviewguides/reviewtypes.txt`
- `aitasks/metadata/reviewmodes/reviewlabels.txt` → `aireviewguides/reviewlabels.txt`
- `aitasks/metadata/reviewmodes/reviewenvironments.txt` → `aireviewguides/reviewenvironments.txt`
- `.reviewmodesignore` → `.reviewguidesignore`

**Script references:**
- `./aiscripts/aitask_reviewmode_scan.sh` → `./aiscripts/aitask_reviewguide_scan.sh`

**Skill invocation references:**
- `/aitask-reviewmode-classify` → `/aitask-reviewguide-classify`
- `/aitask-reviewmode-merge` → `/aitask-reviewguide-merge`

**Terminology:**
- "reviewmode" → "reviewguide" in all prose, comments, notes
- "review mode file" → "review guide file"
- Commit messages: `ait: Classify reviewmode` → `ait: Classify reviewguide`

**fzf command:**
```bash
# OLD
find aitasks/metadata/reviewmodes/ -name '*.md' ...
# NEW
find aireviewguides/ -name '*.md' ...
```

The `sed` path stripping also needs updating:
```bash
# OLD
sed 's|aitasks/metadata/reviewmodes/||'
# NEW
sed 's|aireviewguides/||'
```

### 2. `.claude/skills/aitask-reviewguide-merge/SKILL.md` (dir renamed in t172_1)

Same pattern of changes as the classify skill:

**Frontmatter:** Update name and description
**Path references:** All `aitasks/metadata/reviewmodes/` → `aireviewguides/`
**Script references:** `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
**Skill invocation:** `/aitask-reviewmode-merge` → `/aitask-reviewguide-merge`
**fzf command:** Update find path and sed strip
**Commit messages:** `ait: Merge reviewmode` → `ait: Merge reviewguide`
**Terminology:** All prose updated

### 3. `.claude/skills/aitask-review/SKILL.md`

The main review skill references reviewmodes in several places:

**Path references:**
- Where it loads review modes from `aitasks/metadata/reviewmodes/` → `aireviewguides/`
- `.reviewmodesignore` → `.reviewguidesignore`

**Script references:**
- `./aiscripts/aitask_reviewmode_scan.sh` → `./aiscripts/aitask_reviewguide_scan.sh`

**Terminology:**
- "review mode" / "reviewmode" → "review guide" / "reviewguide" throughout
- Profile settings: `review_default_modes` → consider if this setting name should change too

**Skill invocation references:**
- `/aitask-reviewmode-classify` → `/aitask-reviewguide-classify`
- `/aitask-reviewmode-merge` → `/aitask-reviewguide-merge`

## Reference Files

- Read each skill file fully before modifying
- `.claude/skills/aitask-reviewmode-classify/SKILL.md` — current classify skill (223 lines)
- `.claude/skills/aitask-reviewmode-merge/SKILL.md` — current merge skill (280 lines)
- `.claude/skills/aitask-review/SKILL.md` — main review skill

## Verification

1. `grep -ri "reviewmode" .claude/skills/aitask-reviewguide-classify/SKILL.md` — 0 results
2. `grep -ri "reviewmode" .claude/skills/aitask-reviewguide-merge/SKILL.md` — 0 results
3. `grep -ri "reviewmode" .claude/skills/aitask-review/SKILL.md` — 0 results
4. `grep -r "aitasks/metadata/reviewmodes" .claude/skills/` — 0 results (old path gone)
5. `grep -r "aireviewguides" .claude/skills/` — should show new paths
6. Verify fzf commands use `find aireviewguides/` not the old path
7. Verify commit message templates use "reviewguide" not "reviewmode"
