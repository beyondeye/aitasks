---
Task: t88_ensure_task_number_in_git_commit_message.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask_issue_update.sh` script posts comments to GitHub issues referencing commits associated with a task. Currently, it uses `git log --grep` with patterns like `t88[^0-9_]` which also matches administrative commits (status changes, archival) — not just source code implementation commits. The fix is to:
1. Tag source code commits with `(t<task_id>)` (parenthesized)
2. Update the script to search for that exact parenthesized pattern
3. Since aitask/aiplan commits already use formats like `t88:` or `t88 ` (no parentheses), only source code commits will be found

## Changes

### 1. Update `aitask_issue_update.sh` — change commit search pattern

**File:** `aitask_issue_update.sh` (lines 322-330)

Change the `detect_commits()` function's auto-detect patterns from:
```bash
# Child: search_pattern="t${task_id}"
# Parent: search_pattern="t${task_id}[^0-9_]"
```
To:
```bash
# Both child and parent: search_pattern="(t${task_id})"
```

Since `git log --grep` uses basic regex where `(` and `)` are literal characters, searching for `(t88)` will match the literal string `(t88)` in commit messages. No special escaping needed.

Note: The child/parent distinction (`[^0-9_]` to avoid matching children) is no longer needed because the parentheses themselves provide the delimiter. `(t88)` won't match `(t88_1)`.

### 2. Update `.claude/skills/aitask-pick/SKILL.md` — add commit message convention to Step 8

**File:** `.claude/skills/aitask-pick/SKILL.md` (line 463)

Replace the generic instruction:
```
- Stage and commit all implementation changes (including the updated plan file) with an appropriate message
```

With explicit instructions:
```
- Stage and commit all implementation changes (including the updated plan file)
- **IMPORTANT — Commit message convention:** The commit message MUST include `(t<task_id>)` at the end (e.g., `Add channel settings screen (t16)` or `Fix login validation (t16_2)`). This tag is used by `aitask_issue_update.sh` to find commits associated with a task when posting to GitHub issues. Only source code implementation commits should include this tag — administrative commits (status changes, archival in Steps 4, 9, and Abort) must NOT include it.
```

### 3. Also add a note to Step 7 for awareness

**File:** `.claude/skills/aitask-pick/SKILL.md` (in Step 7)

Add a brief reminder after the existing Step 7 content:
```
**Note:** When committing implementation changes (in Step 8), the commit message must include `(t<task_id>)`. See Step 8 for details.
```

## Verification

1. Read the modified `aitask_issue_update.sh` and verify the pattern change
2. Read the modified SKILL.md and verify the instructions are clear
3. Run `./aitask_issue_update.sh --help` to confirm the script still works
4. Test the grep pattern: `echo "Add feature (t88)" | grep "(t88)"` should match
5. Test non-match: `echo "Start work on t88: set status" | grep "(t88)"` should NOT match
6. Test child task non-match with parent pattern: `echo "Fix bug (t88_1)" | grep "(t88)"` should NOT match

## Final Implementation Notes
- **Actual work done:** All three planned changes implemented exactly as described — updated `detect_commits()` in `aitask_issue_update.sh`, added commit message convention to SKILL.md Step 8, and added awareness note to Step 7
- **Deviations from plan:** None
- **Issues encountered:** None — the implementation was straightforward
- **Key decisions:** Used basic regex literal parentheses in `git log --grep` which works correctly without escaping since git uses BRE by default where `(` and `)` are literals
