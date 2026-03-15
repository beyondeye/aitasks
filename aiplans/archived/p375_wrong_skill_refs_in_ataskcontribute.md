---
Task: t375_wrong_skill_refs_in_ataskcontribute.md
Worktree: (current directory)
Branch: main
Base branch: main
---

## Context

Task t375: The aitask-contribute skill's summary message references `/aitask-pr-import` and `/aitask-issue-import` as the skills to import contributions — neither is correct for this purpose. The correct skill is `/aitask-contribution-review`.

## Plan

**File:** `.claude/skills/aitask-contribute/SKILL.md` (line 284)

**Change:** Replace:
```
When these issues are imported via /aitask-pr-import or /aitask-issue-import,
```
With:
```
When these issues are imported via /aitask-contribution-review,
```

One-line fix. No other occurrences need changing (line 301 mentions `aitask-pr-import` in a different, correct context about execution profiles).

## Verification

- Read the modified file and confirm line 284 now references `/aitask-contribution-review`
- Confirm line 301 is unchanged (it correctly references `aitask-pr-import` in a different context)

## Final Implementation Notes
- **Actual work done:** Replaced incorrect `/aitask-pr-import or /aitask-issue-import` reference with `/aitask-contribution-review` on line 284 of SKILL.md — exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Left line 301 untouched — it references `aitask-pr-import` in a correct context (listing skills that use execution profiles).
