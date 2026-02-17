---
Task: t158_fixes_to_review_skill.md
Branch: main (current branch, no worktree)
---

## Context

The `aitask-review` skill (`.claude/skills/aitask-review/SKILL.md`) needs three improvements:
1. Remove the "Entire codebase" review option (too broad, wastes LLM context)
2. Extract inline commit-fetching logic into a reusable bash script (saves LLM context, faster)
3. Extract inline environment auto-detection into a modular bash script (saves LLM context, extensible)

The key motivation is **delegating automatable logic to bash scripts** instead of consuming LLM context for tasks that don't need language model reasoning.

## Implementation Plan

### Step 1: Create `aiscripts/aitask_review_commits.sh`

Extracts the paginated commit-fetching logic from SKILL.md Step 1a lines 67-102.

**Interface:**
```
./aiscripts/aitask_review_commits.sh [--batch-size N] [--offset N]
```
- `--batch-size N` (default 10): relevant commits per batch
- `--offset N` (default 0): already-displayed commits to skip

**Algorithm:**
1. Fetch raw commits via `git log --oneline --shortstat` in chunks (scanning more than batch-size to skip `ait:` commits)
2. Filter out commits with `ait:` prefix (case-insensitive)
3. Skip first `offset` relevant commits, collect next `batch-size`

**Output format** (pipe-delimited, one line per commit):
```
<display_number>|<hash>|<message>|<insertions>|<deletions>
```
Final line: `HAS_MORE|<next_offset>` or `NO_MORE_COMMITS`

**`--shortstat` parsing** must handle all variants:
- `1 file changed, 5 insertions(+)` → ins=5, del=0
- `2 files changed, 10 insertions(+), 3 deletions(-)` → ins=10, del=3
- `1 file changed, 2 deletions(-)` → ins=0, del=2

**Pattern reference:** `aiscripts/aitask_lock.sh` (shebang, set -euo pipefail, SCRIPT_DIR, source terminal_compat, case/esac arg parsing)

### Step 2: Create `aiscripts/aitask_review_detect_env.sh`

Replaces inline env detection from SKILL.md Step 1b lines 115-125 with a modular, extensible approach.

**Interface:**
```
./aiscripts/aitask_review_detect_env.sh [--files-stdin | --files FILE...] [--reviewmodes-dir DIR]
```
- `--files-stdin`: read file list from stdin (one per line)
- `--files FILE...`: list of files as arguments
- `--reviewmodes-dir DIR` (default: `aitasks/metadata/reviewmodes`)

**Architecture — Modular Independent Tests:**

Each test is a function named `test_*` that updates an associative array `ENV_SCORES[env]`. Tests are registered in an `ALL_TESTS` array — adding a new test means writing a function and adding its name.

**Test functions:**

1. **`test_project_root_files`** (weight: 3 per match)
   - `pyproject.toml`/`setup.py`/`requirements.txt` → python +3
   - `build.gradle`/`build.gradle.kts` → android +3, kotlin +3
   - `CMakeLists.txt` → cpp +3, cmake +3
   - `package.json` → javascript +3, typescript +3
   - `Cargo.toml` → rust +3
   - `go.mod` → go +3

2. **`test_file_extensions`** (weight: 1 per file)
   - `.py` → python, `.sh` → bash+shell, `.kt`/`.kts` → kotlin+android
   - `.java` → android (if build.gradle), `.js`/`.jsx` → javascript
   - `.ts`/`.tsx` → typescript, `.cpp`/`.cc`/`.h`/`.hpp` → cpp
   - `.rs` → rust, `.go` → go

3. **`test_shebang_lines`** (weight: 2 per match, first 20 existing files)
   - `#!/*bash` or `#!/*sh` → bash+shell +2
   - `#!/*python` → python +2

4. **`test_directory_patterns`** (weight: 2 per match)
   - Files under `aiscripts/` or `*.sh` at root → bash+shell +2
   - Files under `src/main/kotlin/` or `src/main/java/` → android+kotlin +2

**Reviewmode parsing:** Pure bash YAML frontmatter parser extracts `name`, `description`, `environment` from each `.md` file.

**Output format (two sections):**
```
ENV_SCORES
python|8
bash|5
shell|5
---
REVIEW_MODES
python_best_practices.md|Python Best Practices|Check type hints...|8
shell_scripting.md|Shell Scripting|Check variable quoting...|5
code_conventions.md|Code Conventions|Check naming...|universal
security.md|Security|Check for injection...|universal
android_best_practices.md|Android Best Practices|Check lifecycle...|0
```

Modes sorted: highest-scoring env-specific → universal → zero-scoring env-specific.

### Step 3: Update `aitasks/metadata/claude_settings.seed.json`

Add two entries after the existing `aitask_lock.sh` line:
```json
"Bash(./aiscripts/aitask_review_commits.sh:*)",
"Bash(./aiscripts/aitask_review_detect_env.sh:*)"
```

### Step 4: Update `.claude/skills/aitask-review/SKILL.md`

**4a. Step 1a — Remove "Entire codebase" option:**
- Remove from `AskUserQuestion` options (line 61)
- Delete line 104 (`**If "Entire codebase":**...`)

**4b. Step 1a — Replace inline commit logic with script call:**
Replace lines 67-102 (the entire "Recent changes" inline logic) with:
- Call `./aiscripts/aitask_review_commits.sh --batch-size 10 --offset 0`
- Document the pipe-delimited output format
- Show how to format for user display
- Keep the `AskUserQuestion` commit selection (Last 5, Last 10, Show more, Custom)
- Keep the commit hash resolution and changed files logic (steps 3-4) unchanged

**4c. Step 1b — Replace inline env detection with script call:**
Replace lines 108-126 (the "List reviewmodes" + "Auto-detect" section) with:
- Determine files to analyze (from Step 1a's changed files or user-selected paths)
- Call `./aiscripts/aitask_review_detect_env.sh --files-stdin`
- Use the script's sorted `REVIEW_MODES` output for the `AskUserQuestion` pagination
- Keep the profile check and pagination logic unchanged

**4d. Notes section — update references:**
- Remove any "Entire codebase" mention
- Add notes about both helper scripts

## Verification

1. **Test commit script:**
   ```bash
   ./aiscripts/aitask_review_commits.sh --batch-size 5 --offset 0
   ./aiscripts/aitask_review_commits.sh --batch-size 5 --offset 5
   ```
   Verify: numbered output, no `ait:` commits, correct +N/-M stats, HAS_MORE/NO_MORE_COMMITS marker

2. **Test env detection script:**
   ```bash
   echo "aiscripts/aitask_lock.sh
   aiscripts/aitask_ls.sh" | ./aiscripts/aitask_review_detect_env.sh --files-stdin
   ```
   Verify: bash/shell scored high, review modes sorted correctly

3. **Test with no files:**
   ```bash
   echo "" | ./aiscripts/aitask_review_detect_env.sh --files-stdin
   ```
   Verify: still detects environments from project root files

4. **Verify SKILL.md changes** are coherent: read through the updated Step 1a and 1b flow to ensure the script output format matches what the skill expects

## Final Implementation Notes

- **Actual work done:** All 4 planned steps completed as designed:
  1. Created `aiscripts/aitask_review_commits.sh` (~140 lines) — paginated commit fetching with `ait:` filtering
  2. Created `aiscripts/aitask_review_detect_env.sh` (~230 lines) — modular env scoring with 4 independent test functions
  3. Updated `aitasks/metadata/claude_settings.seed.json` — added both scripts to whitelist
  4. Updated `.claude/skills/aitask-review/SKILL.md` — removed "Entire codebase" option, replaced inline logic with script calls
  5. Also created task t159 for the reviewmodes directory tree restructuring (separate future task)
- **Deviations from plan:** None — implementation followed the plan exactly
- **Issues encountered:** None
- **Key decisions:**
  - Pipe `|` delimiter for script output (safe since it doesn't appear in commit messages or file paths)
  - `ENV_SCORES` and `REVIEW_MODES` two-section output format with `---` separator for the detect_env script
  - Bash associative arrays for scoring (requires bash 4+, available everywhere this project runs)

## Post-Implementation (Step 9)

Archive task and plan files per standard workflow.
