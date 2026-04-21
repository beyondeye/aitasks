---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_pick, aitask_verification]
created_at: 2026-04-21 07:53
updated_at: 2026-04-21 09:30
---

## Context

**Clarification (2026-04-21):** "Section headers" here does **not** mean Markdown `###` headings — the task file has none. They are `- [ ]` *checkbox lines* that function as category headers because (a) their text ends with `:` and (b) the immediately following lines are `- [ ]` bullets indented by one more level (nested sub-items).

Concretely, in the archived `aitasks/archived/t597/t597_6_manual_verification.md` these are lines 28, 35, 40, 44:

```
 28  - [x] `c` opens config modal: — PASS …
 29    - [x] All four presets are listed and selectable — …
 30    - [defer] Switching preset updates the sidebar immediately — …
 31    - [skip] "+ New custom" → name input → multi-select → save … — …
 32    - [defer] Quitting and relaunching `ait stats-tui` … — …
 35  - [x] All 4 preset categories render without exceptions on the current dataset: — PASS …
 36    - [x] Overview (summary, daily, weekday) — …
 37    - [x] Labels & Issue Types (top, issue types, heatmap) — …
 …
 40  - [defer] CLI parity: — DEFER …
 41    - [x] `ait stats` text report unchanged — …
 …
 44  - [skip] Persistence file hygiene: — SKIP …
 45    - [x] `aitasks/metadata/stats_config.json` is git-tracked, … — …
```

Because each `- [ ]` line — whatever its indent or trailing `:` — is parsed as a distinct item, the interactive loop asks the user to mark the header *and* each of its children, instead of only the children. The header's "answer" is redundant with the children's.

## Context (original narrative)

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

## Acceptance criteria (section-header filter)

- Section-header `- [ ]` items with nested sub-bullets are not emitted by `aitask_verification_parse.sh parse`.
- `summary` output (`TOTAL/PENDING/PASS/FAIL/SKIP/DEFER`) excludes section headers from all counts.
- `set` still works on a header line by index (for backward compat), but the TUI loop never asks about one.
- A unit test in `tests/` covers the heuristic: `test_verification_section_headers.sh`.
- The existing `t597_6` task file remains valid (its pre-marked section headers don't need rewriting).

## Second improvement — rename carry-over tasks

Request from user (2026-04-21): the auto-created carry-over task currently gets a generic slug.

For the archived t597_6 run, the carry-over task was named `t610_manual_verification_deferred_carryover` — because `aitask_archive.sh:567` computes the carry-over slug as:

```bash
local carryover_name="${orig_name}_deferred_carryover"
# where:
orig_name=$(echo "$orig_basename" | sed -E 's/^t[0-9]+(_[0-9]+)?_//')
```

For `t597_6_manual_verification.md` → `orig_name=manual_verification` → carry-over slug = `manual_verification_deferred_carryover`, which loses the origin task context.

**Desired behavior:** the carry-over slug should be the original task's slug with a simple `_carryover` suffix (drop the `_deferred_` middle). So:

| Original file | Current carry-over name | New carry-over name |
|---|---|---|
| `t597_6_manual_verification.md` | `t<N>_manual_verification_deferred_carryover.md` | `t<N>_manual_verification_carryover.md` |
| `t42_verify_login_flow.md` | `t<N>_verify_login_flow_deferred_carryover.md` | `t<N>_verify_login_flow_carryover.md` |

Patch:

```bash
# .aitask-scripts/aitask_archive.sh, around line 567
- local carryover_name="${orig_name}_deferred_carryover"
+ local carryover_name="${orig_name}_carryover"
```

### Acceptance criteria (carry-over rename)

- `aitask_archive.sh --with-deferred-carryover <id>` creates a carry-over task whose slug is `<orig_slug>_carryover` (no `deferred_` middle).
- Existing carry-over tasks already on disk are not renamed (migration unnecessary — only new ones need to use the new convention).
- If the test suite added by the first half of this task creates a carry-over, it asserts the new naming convention.

## Reference

- Parser: `.aitask-scripts/aitask_verification_parse.sh`
- Archive: `.aitask-scripts/aitask_archive.sh` (`create_carryover_task` around line 549)
- Procedure doc: `.claude/skills/task-workflow/manual-verification.md`
- Surfaced during: t597_6 verification, 2026-04-21
