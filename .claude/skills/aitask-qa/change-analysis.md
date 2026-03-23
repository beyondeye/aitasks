# Change Analysis Procedure `[Tier: s, e]`

Analyzes the changes introduced by a task — gathers context, detects commits,
and categorizes changed files. Referenced from Step 2 of the main SKILL.md workflow.

**This procedure is skipped when `tier = q`.**

**Input:**
- `task_file` — path to the task file
- `task_id` — task identifier (e.g., `42` or `16_2`)
- `is_child` — whether this is a child task
- `is_archived` — whether the task is archived

**Output:**
- List of changed files categorized by type
- Commit range (first..last) if commits exist
- Diff stats

---

## 2a: Gather task context `[Tier: s, e]`

- Read the target task file
- Find the plan file:
  - If active: `aitask_query_files.sh plan-file <task_id>`
  - If archived: also check `aiplans/archived/` — for parent tasks: `aiplans/archived/p<N>_*.md`, for child tasks: `aiplans/archived/p<parent>/p<parent>_<child>_*.md`
- Read the plan file if found (contains implementation details and final notes)

## 2b: Detect commits `[Tier: s, e]`

Use the commit detection pattern from `aitask_issue_update.sh`:

```bash
git log --oneline --all --grep="(t<task_id>)" 2>/dev/null || true
```

**Note:** The parentheses in `(t<task_id>)` act as delimiters — `(t88)` won't match `(t88_1)`.

If commits found:
- Extract the first (oldest) and last (newest) commit hashes
- Get changed files:
  ```bash
  git diff <first_commit>^..<last_commit> --name-only 2>/dev/null || true
  ```
- Get diff stats:
  ```bash
  git diff <first_commit>^..<last_commit> --stat 2>/dev/null || true
  ```

If no commits found (task not yet implemented or commits not tagged):
- Analyze the plan file for expected changes
- Display: "No commits found for t<task_id>. Using plan file for analysis."

## 2c: Categorize changes `[Tier: s, e]`

Sort changed files into categories:
- **Source code:** `.sh`, `.py`, `.js`, `.ts`, `.go`, `.rs`, `.toml`, `.yaml` (excluding test files)
- **Test files:** Files matching `test_*`, `*_test.*`, `tests/`, `__tests__/`, `*_spec.*`
- **Config/docs:** `.md`, `.json` (config), `.yml` (CI), `Makefile`, etc.

Display a summary table of changes by category.
