# Test Discovery Procedure `[Tier: s, e]`

Scans for existing tests, maps them to changed source files, and identifies
coverage gaps. Referenced from Step 3 of the main SKILL.md workflow.

**This procedure is skipped when `tier = q`.**

**Input:**
- List of changed source files from Step 2 (change analysis)

**Output:**
- Source-to-test mapping
- List of coverage gaps (source files without tests)

---

## 3a: Scan for existing tests `[Tier: s, e]`

For each changed source file, look for corresponding test files using common naming conventions:
- `tests/test_<name>.sh` (bash test pattern used in this project)
- `tests/<name>_test.py`, `test_<name>.py`
- `__tests__/<name>.test.ts`, `<name>.spec.ts`

## 3b: Map source to tests `[Tier: s, e]`

Create a mapping of source files to their test files (if any exist).

## 3c: Identify gaps `[Tier: s, e]`

List source files that have changes but no corresponding test files. These are the primary candidates for new tests.

Display the test coverage map:
```
Source File                          Test File              Status
.aitask-scripts/aitask_foo.sh       tests/test_foo.sh      Covered
.aitask-scripts/aitask_bar.sh       (none)                 GAP
```
