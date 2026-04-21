---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_pick, aitask_verification]
created_at: 2026-04-21 07:53
updated_at: 2026-04-21 07:53
---

## Context

During `/aitask-pick` manual-verification runs, the checklist parser (`.aitask-scripts/aitask_verification_parse.sh`) emits every `- [ ]` line as a separate item, including **section header bullets** whose text ends with `:` and has nested sub-bullets beneath it.

Concrete example (from `t597_6_manual_verification.md`):

```markdown
- [ ] `c` opens config modal:
  - [ ] All four presets are listed and selectable
  - [ ] Switching preset updates the sidebar immediately
  - [ ] "+ New custom" → name input → multi-select → save → custom appears in the list and in the sidebar
  - [ ] Quitting and relaunching `ait stats-tui` restores the active layout (persistence works)
```

The first line is a category header — it has no standalone verifiable assertion. But the current parser surfaces it as a checklist item, prompting the user to pass/fail a header that the sub-bullets already cover. This creates noise (the user doesn't know whether to pass the header itself or treat it as covered by sub-items) and pollutes the verification record with redundant marks.

This came up during t597_6 verification (items 5, 12, 17, 21 in that task are all section headers).

## Desired behavior

Section-header checklist items should NOT be surfaced as interactive prompts during the `aitask-pick` manual-verification loop. They should either:

- Be filtered out of `aitask_verification_parse.sh parse` output entirely (preferred — keep the checklist as authored but skip at enumeration time), OR
- Be auto-marked as `pass` when all nested sub-items reach a terminal state (pass / fail / skip), so they serve as folder summaries in the final record.

The preferred approach is **filter at enumeration**: the `parse` command should detect section headers (heuristic: line ends with `:` AND the next non-blank sibling is a nested `- [ ]` at one more level of indent) and omit them. `summary` totals should also exclude them so the user doesn't see a confusing pending count.

## Acceptance criteria

- Section-header `- [ ]` items with nested sub-bullets are not emitted by `aitask_verification_parse.sh parse`.
- `summary` output (`TOTAL/PENDING/PASS/FAIL/SKIP/DEFER`) excludes section headers from all counts.
- `set` still works on a header line by index (for backward compat), but the TUI loop never asks about one.
- A unit test in `tests/` covers the heuristic: `test_verification_section_headers.sh`.
- The existing `t597_6` task file remains valid (its pre-marked section headers don't need rewriting).

## Reference

- Parser: `.aitask-scripts/aitask_verification_parse.sh`
- Procedure doc: `.claude/skills/task-workflow/manual-verification.md`
- Surfaced during: t597_6 verification, 2026-04-21
