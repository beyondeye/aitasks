---
Task: t202_bug_in_user_file_select.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

In the user-file-select skill, Step 4 asks users to enter file indices via the AskUserQuestion "Other" free text input. The problem: when the user selects "Other" and starts typing a digit (e.g., `1`), the AskUserQuestion UI intercepts it as selecting numbered option 1 instead of typing into the text field.

## Plan

Fix by instructing users to wrap their index input in parentheses (e.g., `(1,2)` or `(1-2,3)`), so the first character typed is `(` (not a digit), avoiding the UI conflict.

### Changes to `.claude/skills/user-file-select/SKILL.md`

1. **Step 4 question text** — Changed to: "Select files by entering indices in parentheses. Supports: individual (1,4,5), ranges (3-5), mixed (1,3-5,7), or (all)."
2. **Parsing logic** — Added step 2: strip surrounding parentheses before processing (`(1,3-5)` → `1,3-5`)
3. **Error messages** — Updated format example to `(1,3-5,7)` and `(all)`

## Verification

- [x] Question text instructs parentheses format
- [x] Parsing strips parentheses before processing
- [x] Error messages show parenthesized format
- [x] `all` keyword works both as `(all)` and `all`
- [x] Step numbers are sequential (1-9)

## Final Implementation Notes
- **Actual work done:** Updated SKILL.md Step 4 to instruct parenthesized index input, added parenthesis-stripping to the parsing logic, and updated error messages — all as planned.
- **Deviations from plan:** None. All three changes applied cleanly.
- **Issues encountered:** The step numbers needed to be renumbered after inserting step 2 (from 8 steps to 9).
- **Key decisions:** Kept backward compatibility — bare input without parentheses still works since the stripping only triggers when both `(` and `)` are present.
