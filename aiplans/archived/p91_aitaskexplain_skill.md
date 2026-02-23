---
Task: t91_aitaskexplain_skill.md
Branch: main
Base branch: main
---

# Implementation Plan: t91 — aitask-explain skill

## Context

This task creates a new Claude Code skill that explains project files through three lenses:
1. **Functionality** — what the code does
2. **Usage examples** — how it's used in the project
3. **Code evolution** — how the code changed over time, traced through git commits → aitasks → aiplans

The approach follows the established hybrid pattern (see `aitask_changelog.sh` + `aitask-changelog/SKILL.md`): a shell script gathers structured data, the skill orchestrates LLM-driven analysis.

**Dependency:** Reuses `aiscripts/lib/task_utils.sh` functions from completed t97: `resolve_task_file`, `resolve_plan_file`, `extract_final_implementation_notes`, `_extract_from_tar_gz`.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `aiscripts/aitask_explain_extract_raw_data.sh` | **Create** | Shell script: git log, git blame, commit→task mapping, raw data extraction |
| `aiscripts/aitask_explain_process_raw_data.py` | **Create** | Python script: converts raw data to YAML reference file, additional processing |
| `aiscripts/aitask_explain_runs.sh` | **Create** | Shell script: manage (list/delete) existing aiexplain run directories |
| `.claude/skills/aitask-explain/SKILL.md` | **Create** | Skill workflow definition |
| `.claude/settings.local.json` | **Modify** | Add new scripts to allowed commands |

---

## Part 1: Shell Script — `aiscripts/aitask_explain_extract_raw_data.sh`

### Purpose
Generate a structured reference directory (`aiexplains/`) containing:
- A reference file mapping lines → commits → tasks
- Extracted task and plan files (renamed to ID-only names)

### CLI Interface
```
aitask_explain_extract_raw_data.sh --gather PATH [PATH...] [--max-commits N]
aitask_explain_extract_raw_data.sh --cleanup RUN_DIR
```

- `--gather`: Analyze files/directories. If a PATH is a directory, expands to all git-tracked text files within it (`git ls-files <dir>`). Creates a run-specific subdirectory under `aiexplains/`, produces reference data. Prints `RUN_DIR: aiexplains/<run_id>` to stdout.
- `--cleanup RUN_DIR`: Remove a specific run directory (e.g., `aiexplains/20260221_143052`)
- `--max-commits N`: Limit commits per file (default: 50)

**Run ID**: Generated as `YYYYMMDD_HHMMSS` timestamp. Each invocation gets its own isolated directory, supporting concurrent runs and preventing stale data.

### Output Directory Structure
```
aiexplains/
  20260221_143052/             # Run-specific directory (timestamp)
    files.txt                  # List of analyzed files (full paths from project root, one per line)
    raw_data.txt               # Intermediate raw data from bash (pipe-delimited)
    reference.yaml             # Final YAML reference file (produced by Python)
    tasks/
      t16.md                   # Extracted task file (ID-only name)
      t18.md
    plans/
      p16.md                   # Extracted plan file (ID-only name)
      p18.md
```

### Pipeline: Bash → Python

**Stage 1 — Bash (`aitask_explain_extract_raw_data.sh`)**: Extracts raw data from git and aitask/aiplan archives. Writes `raw_data.txt` (pipe-delimited structured text) and copies task/plan files.

**Stage 2 — Python (`aitask_explain_process_raw_data.py`)**: Reads `raw_data.txt`, converts to YAML format, performs additional processing (range aggregation, cross-referencing). Writes `reference.yaml`. The bash script calls the Python script automatically at the end of `--gather`.

### Raw Data Format (`raw_data.txt` — intermediate, bash output)

```
=== FILE: path/to/file.sh ===

COMMIT_TIMELINE:
1|abc1234|2026-01-25|Author Name|refactor: Clean up imports||
2|def5678|2026-01-20|Author Name|bug: Fix login (t18)|18
3|ghi9012|2026-01-15|Author Name|feature: Add auth (t16)|16

BLAME_LINES:
1|abc1234
2|abc1234
3|def5678
...

=== END FILE ===

=== TASK_INDEX ===
16|tasks/t16.md|plans/p16.md
18|tasks/t18.md|plans/p18.md
=== END TASK_INDEX ===
```

- **COMMIT_TIMELINE**: ordered from **newest (1) to oldest** — most recent changes first
- **BLAME_LINES**: raw per-line blame data (line_num|full_hash) — Python aggregates into ranges

### Final Reference Format (`reference.yaml` — Python output)

```yaml
files:
  - path: path/to/file.sh
    commits:
      - num: 1
        hash: abc1234
        date: "2026-01-25"
        author: Author Name
        message: "refactor: Clean up imports"
        task_id: null
      - num: 2
        hash: def5678
        date: "2026-01-20"
        author: Author Name
        message: "bug: Fix login (t18)"
        task_id: 18
      - num: 3
        hash: ghi9012
        date: "2026-01-15"
        author: Author Name
        message: "feature: Add auth (t16)"
        task_id: 16
    line_ranges:
      - start: 1
        end: 25
        commits: [3]
        tasks: [16]
      - start: 26
        end: 40
        commits: [2, 3]
        tasks: [16, 18]
      - start: 41
        end: 100
        commits: [1]
        tasks: []

tasks:
  - id: 16
    task_file: tasks/t16.md
    plan_file: plans/p16.md
    has_notes: true
  - id: 18
    task_file: tasks/t18.md
    plan_file: plans/p18.md
    has_notes: true
```

---

## Part 2: Skill — `.claude/skills/aitask-explain/SKILL.md`

See SKILL.md file for full workflow definition.

---

## Part 3: Run Management Script — `aiscripts/aitask_explain_runs.sh`

Interactive CLI to manage existing aiexplain run directories: list, inspect, and delete.

---

## Follow-up Tasks (to create after t91 is complete)

1. **user-file-select skill** — Create a new skill for fuzzy file selection
2. **Refactor aitask-explain file selection** — Replace simple file input with `user-file-select` integration
3. **Refactor aitask-explore area selection** — Replace free-text area input with `user-file-select` integration

---

## Final Implementation Notes
- **Actual work done:** Created all 5 planned files: `aitask_explain_extract_raw_data.sh` (bash extraction), `aitask_explain_process_raw_data.py` (Python YAML processing), `aitask_explain_runs.sh` (run management), `.claude/skills/aitask-explain/SKILL.md` (skill definition), plus `.claude/settings.local.json` and `.gitignore` updates.
- **Deviations from plan:** Fixed binary file detection (changed from `git diff --no-index` to `file --mime-encoding`). Fixed task ID collection bug (wrong field count in `IFS='|' read`). Added `aiexplains/` to `.gitignore`.
- **Issues encountered:** (1) Binary file detection with `git diff --no-index --numstat` failed to pass text files through — replaced with `file --mime-encoding` check. (2) Task ID collection had an off-by-one in field parsing due to leading `|` in git log format string — fixed by adding an extra `_` discard field.
- **Key decisions:** Used manual YAML generation in Python instead of requiring PyYAML dependency. The bash script calls the Python processor automatically at the end of `--gather`. Each run gets an isolated timestamp directory under `aiexplains/`.

## Step 9 Reference (Post-Implementation)
After implementation and commit, archive task via `./aiscripts/aitask_archive.sh 91`.
