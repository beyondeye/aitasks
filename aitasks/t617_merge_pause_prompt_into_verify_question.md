---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_pick, task_workflow]
created_at: 2026-04-21 12:36
updated_at: 2026-04-21 12:36
---

In `.claude/skills/task-workflow/manual-verification.md`, each verification iteration currently uses two consecutive `AskUserQuestion` calls per item: (1) a pause-loop prompt ("Verify this item" / "Stop here, continue later"), then (2) the verify prompt (Pass / Fail / Skip (with reason) / Defer). The user finds this awkward — the extra prompt doubles the interaction count.

## Requested change

Merge them into a single prompt per item with these options:

- Pass
- Fail
- Skip (with reason)
- Defer
- Abort (pause/stop without changing state)

Selecting "Abort" is the current "Stop here, continue later" path: leave the current item unchanged (still pending or still defer), skip the remaining items, skip the post-loop checkpoint and commit step, and inform the user they can re-pick with `/aitask-pick <task_id>`. The task stays `Implementing` and the lock remains held.

## 4-option cap consideration

`AskUserQuestion.options` has `maxItems=4`, and "Other" is added automatically by the UI. Five explicit options is not directly representable. Options to consider:

1. Drop "Skip (with reason)" from the options list and let the user pick "Other" for skip-with-reason — but this degrades the current Skip UX.
2. Use a nested flow: one question with Pass / Fail / Defer / More…, where "More…" opens a second question offering Skip / Abort. This only adds a prompt when needed.
3. Use Pass / Fail / Defer / Abort as primary options and rely on "Other" (free text) for skip-with-reason — users typing a reason is functionally equivalent to Skip.

**Option 3** is probably the cleanest and most directly matches the user's ask. Confirm the preferred approach when implementing.

## Files to touch

- `.claude/skills/task-workflow/manual-verification.md` — remove step 2's pause-loop `AskUserQuestion` and merge into step 3; add Abort branch handling.
- Mirror the change in `.gemini/skills/task-workflow/manual-verification.md`, `.agents/skills/task-workflow/manual-verification.md`, `.opencode/skills/task-workflow/manual-verification.md` if they exist (per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" — Claude Code is the source of truth; suggest separate tasks for the other agents).

## Origin

Feedback during `/aitask-pick 610` on 2026-04-21.
