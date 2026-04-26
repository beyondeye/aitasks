---
title: "Manual Verification Workflow"
linkTitle: "Manual Verification"
weight: 80
description: "Human-checked verification items (TUI flows, live agent launches, artifact inspection) as first-class gated tasks"
depth: [intermediate]
---

Some behavior cannot be covered by automated tests: TUI flows, tmux-driven agents, multi-screen navigation, on-disk artifact inspection, live LLM calls. [`/aitask-qa`](../../skills/aitask-qa/) handles everything that is script-testable; manual verification covers the rest as first-class tasks with their own checklist, lock, and archival gate.

A task with `issue_type: manual_verification` is a human-checklist runner. When [`/aitask-pick`](../../skills/aitask-pick/) picks one, Step 3 Check 3 routes it into a dedicated Pass/Fail/Skip/Defer loop instead of the normal plan-and-implement flow. Failing items auto-generate pre-populated bug tasks; deferred items block archival or spawn carry-over tasks for later.

## The Checklist Format

A manual-verification task body contains one H2 section:

```markdown
## Verification Checklist

- [ ] Open the brainstorm TUI and confirm the left pane renders
- [ ] Ctrl+N in the monitor creates a new task
- [ ] Agent spawn lands in a fresh tmux window
```

Each item is stateful. The parser rewrites item lines in place as the picker marks them:

| State | Line format |
|---|---|
| pending | `- [ ] text` |
| pass | `- [x] text — PASS YYYY-MM-DD HH:MM` |
| fail | `- [fail] text — FAIL YYYY-MM-DD HH:MM follow-up t<new_id>` |
| skip | `- [skip] text — SKIP YYYY-MM-DD HH:MM <reason>` |
| defer | `- [defer] text — DEFER YYYY-MM-DD HH:MM` |

Annotations live after ` — ` (em dash + spaces); the parser strips and rewrites the suffix on each state change, so repeated marks do not accumulate trailing text. Inspect `.aitask-scripts/aitask_verification_parse.sh --help` for the full subcommand surface (`parse`, `set`, `summary`, `terminal_only`, `seed`).

## Where Checklists Come From — Two Generation Paths

Manual-verification tasks are not written by hand. Two places in the [`/aitask-pick`](../../skills/aitask-pick/) workflow seed them automatically, both shelling out to the same `./.aitask-scripts/aitask_create_manual_verification.sh` helper.

### Aggregate-Sibling (Parent → Children Planning)

When `/aitask-pick` on a parent task splits it into two or more children during planning, after the child plans are committed the skill offers to add a **sibling** manual-verification task that verifies some or all of the children.

Three choices:

- **No, not needed** — skip; the normal flow continues to the child-task checkpoint.
- **Yes, aggregate sibling covering all children** — recommended for TUI/UX-heavy work.
- **Yes, but let me choose which children it verifies** — multi-select a subset of the children.

The seeder extracts each selected child's plan `## Verification` bullets, prefixes each with `[t<parent>_<child>] ` for at-a-glance origin, and creates the sibling with `verifies: [<selected_child_ids>]`. Skipped when only one child was created — a post-implementation follow-up covers that case instead.

### Post-Implementation Follow-up (Step 8c)

After the "Commit changes" branch of `/aitask-pick`'s review step, Step 8c offers a standalone manual-verification follow-up. The new task is picked after the current one archives and verifies behavior introduced by this task.

The prompt is skipped when:

- The current task is a child (aggregate-sibling covers children).
- The current task's `issue_type` is itself `manual_verification`.
- An aggregate sibling was already created during the same session.

Candidate checklist bullets are assembled from four de-duplicated sources:

1. The task's `## Verification Steps` H2 section.
2. The plan's `## Verification` H2 section.
3. The plan's Final Implementation Notes — bullets under `**Deviations from plan:**` and `**Issues encountered:**`.
4. A diff scan of the task's commits (files matching interactive surfaces — TUI code, `textual` imports, `fzf`/`gum`-driven scripts — emit `TODO: verify <file> end-to-end in tmux` bullets).

If all four sources are empty, a single `TODO: define verification for t<id>` stub is written — the picker fills it in interactively when they later pick the follow-up.

Set `manual_verification_followup_mode: never` in an active profile to skip Step 8c entirely. See [Execution Profiles](../../skills/aitask-pick/execution-profiles/).

## Running a Manual-Verification Task

When [`/aitask-pick`](../../skills/aitask-pick/) picks a task whose `issue_type` is `manual_verification`, Step 3 Check 3 dispatches to the Manual Verification Procedure — replacing Steps 6 (plan), 7 (implement), and 8 (review). Steps 4 (ownership lock) and 5 (worktree) still run first: manual verification is owned work that should be locked against concurrent pickers.

Before each prompt, the picker re-renders the **full numbered checklist** with each item's current state (`pending` / `pass` / `fail` / `skip` / `defer`), so the overview is always in view, then prints a one-line tip advertising the Other-field batch path. The prompt itself is scoped to the first remaining `pending` or `defer` item — the "current item" — but the Other field also accepts a **batch update** that resolves multiple items in one round-trip. Example checklist render:

```
Verification checklist (5 items):
  1. ✓ pass    Open the brainstorm TUI and confirm the left pane renders
  2. ✓ pass    Ctrl+B opens the brainstorm view
  3. ⏳ pending Ctrl+N spawns a new task from the brainstorm view
  4. ⏳ pending Agent spawn lands in a fresh tmux window
  5. ⏸ defer   Verify tmux session reuse logic

Tip: in the Other field you can batch-resolve multiple items in one go,
e.g. "3 pass, 4 fail, 5 skip not applicable" (verbs: pass / fail / skip / defer).
```

Per-item outcomes:

| Choice | Effect |
|---|---|
| **Pass** | Marks the current item `pass` with timestamp. |
| **Fail** | Runs `aitask_verification_followup.sh` — creates a pre-populated bug task with commit hashes, touched files, verbatim failing text, and `depends: [<origin>]`. The current item is annotated `follow-up t<new_id>`. |
| **Skip (with reason)** | Prompts for a free-text reason; marks the current item `skip` with the reason appended. |
| **Defer** | Marks the current item `defer` — the task will not archive cleanly while any item is in this state. |
| **Other (free text)** | Triaged by intent. **Batch update** (e.g. `3 pass, 4 fail, 5 skip not applicable`) — one or more `<idx> <verb> [args]` entries, comma- semicolon- or newline-separated, each routed through the same handler as its per-option counterpart; failing entries spawn the same follow-up bug task, skip entries take the rest of the entry text as the reason. The shorthand `pass` / `skip <reason>` (no leading index) targets the current item. **Pause / abort / stop** phrasing ends the loop without mutating state; the task stays `Implementing` with the lock held so only the original picker can resume. Anything else is treated as a conversational message — answer a question, perform an investigation, apply a correction — and the current item is re-asked without advancing. |

After every state mutation (single-option choice or batch entry) the loop re-renders the checklist, re-prints the tip, and re-picks the new first-remaining item as the current one. Invalid batch entries (out-of-range index, index already in a terminal state, unknown verb) stop the batch — no silent drops; the user is shown the problem entries and re-asked. Already-applied entries from the same batch stay applied (no rollback).

The "Other" path intentionally has no fixed keyword list — intent is judged from the user's phrasing, not string-matched. This is how conversational corrections ("check this one more time with the minimonitor open") stay inside the loop without interrupting the verification flow.

## Fail → Follow-up Bug Task

On **Fail**, `.aitask-scripts/aitask_verification_followup.sh` creates a pre-populated bug task and links it back to the origin. The helper does five things:

1. **Resolves the origin task.**
   - User-supplied `--origin` wins.
   - Otherwise, the single entry in the current task's `verifies:` frontmatter list is used.
   - Empty `verifies:` falls back to the current task itself as origin.
   - Multiple entries in `verifies:` (aggregate-sibling case) emit `ORIGIN_AMBIGUOUS:<csv>` (exit 2). The picker prompts the user with one `AskUserQuestion` option per candidate and re-invokes with `--origin <chosen>`.
2. **Collects commits** for the origin: `git log --oneline --all --grep="(t<origin>)"`.
3. **Collects touched files** from those commits: `git show --name-only`, deduped.
4. **Creates a `bug` task** via `aitask_create.sh --batch` with `depends: [<origin>]`, `labels: verification,bug`, and a description containing the verbatim failing item text, commit list, touched-file list, and a **Source** block (MV task path, origin task ID, origin archived plan path).
5. **Best-effort back-reference.** Appends a bullet under the origin's archived plan `## Final Implementation Notes` section:
   ```
   - **Manual-verification failure:** item "<text>" failed; follow-up task t<new_id>.
   ```
   Skipped silently if the archived plan cannot be found or `./ait git` is unavailable.

On success, stdout ends with `FOLLOWUP_CREATED:<new_id>:<path>` and the picker announces the new task id.

## The `verifies:` Field

`verifies:` is an optional list of task IDs that a manual-verification task validates — populated automatically by the aggregate-sibling seeder (one entry per selected child). It drives origin disambiguation in the Fail flow: a single entry auto-resolves, multiple entries trigger `ORIGIN_AMBIGUOUS`.

Edit via `ait update`:

```bash
./.aitask-scripts/aitask_update.sh --batch <id> --verifies 571_4,571_5,571_6   # replace list
./.aitask-scripts/aitask_update.sh --batch <id> --add-verifies 571_7           # append one
./.aitask-scripts/aitask_update.sh --batch <id> --remove-verifies 571_4        # drop one
```

See the field reference in [Task Format](../../development/task-format/) and the full CLI surface in [Task Management]({{< relref "/docs/commands/task-management" >}}).

## Defer and Carry-over

Deferred items block clean archival. `aitask_archive.sh <id>` errors out on a manual-verification task while any item is still `pending` or `defer`. Two resolutions are offered at the post-loop checkpoint when `DEFER > 0`:

- **Archive with carry-over.** Sets an internal flag so Step 9 calls:
  ```bash
  ./.aitask-scripts/aitask_archive.sh --with-deferred-carryover <id>
  ```
  The script archives the current task and creates a fresh `manual_verification` task seeded with only the deferred items. The original `verifies:` list is copied forward so Fail attribution still works on the carry-over.
- **Stop without archiving.** Leaves the task `Implementing` with the lock held so only the original picker can resume it. Re-pick later with `/aitask-pick <id>` to continue the remaining items — no new plan, no re-verification; the checklist state is durable on disk.

If all items are terminal (`pass`, `fail`, or `skip`), the procedure proceeds to standard Step 9 archival without the carry-over prompt.

## Example End-to-End

A parent task `t571` splits into three children during planning: `t571_4`, `t571_5`, `t571_6`. At the aggregate prompt, answer **"Yes, aggregate sibling covering all children"**. The seeder creates `t571_7_manual_verification_structured_brainstorming.md` with `verifies: [571_4, 571_5, 571_6]` and a pre-seeded checklist assembled from the three child plans' `## Verification` bullets.

The children implement and archive normally. Eventually:

```
/aitask-pick 571_7
```

Step 3 Check 3 routes to the Manual Verification Procedure. The picker re-renders the three-item checklist before every prompt; you can answer the current item with the per-option button or batch-resolve several at once via Other:

- **Items 1 + 3:** typed in Other as `1 pass, 3 defer` (mixing pass with a defer for the tmux work). After the batch, the checklist re-renders with item 1 marked `pass`, item 3 marked `defer`, and the current item is now item 2.
- **Item 2:** "Ctrl+N spawns a new task from the brainstorm view" → **Fail** (per-option). The helper emits `ORIGIN_AMBIGUOUS:t571_4,t571_5,t571_6`; pick `571_5` as the attribution. `FOLLOWUP_CREATED:612:aitasks/t612_fix_failed_verification_t571_7_item2.md`. The item line is now `[fail] ... follow-up t612`.

Post-loop: `DEFER=1` → **"Archive with carry-over"** → `t571_7` archives as Done. A new `t613_manual_verification_structured_brainstorming_deferred.md` is created with only item 3 pending. Pick it later with `/aitask-pick 613` once the tmux wrapper ships.

## Tips

- **Seed aggregate siblings from child plans.** The aggregate-sibling prompt pre-fills bullets from each child plan's `## Verification` H2 — make sure child plans write concrete, testable verification bullets during planning. Stub items become friction at verification time.
- **Use "Other" for conversational adjustments.** Ask clarifying questions, request follow-up investigations, or instruct one-off commands from inside the verification loop without leaving the picker. The item index does not advance until a terminal outcome is recorded.
- **Batch out the obvious items.** When the first four items are clearly passing, type `1 pass, 2 pass, 3 pass, 4 pass` in Other instead of round-tripping four times. Mix verbs freely (`1 pass, 2 fail, 3 skip n/a`); failing entries still create the standard follow-up bug task. The shorthand `pass` (no leading index) targets the current item.
- **Set `manual_verification_followup_mode: never` for batched work.** When you are archiving many small commits, the per-task Step 8c prompt can be noisy. Profile the prompt off until you hit a larger feature that warrants one.
- **Child tasks don't get Step 8c prompts.** The aggregate-sibling path during parent planning is the correct place to cover children. If a single child needs post-implementation verification, add it during the parent's planning phase with the "let me choose" option.
- **Deferred items keep the task implementing.** Re-pick the same task later with `/aitask-pick <id>` (same owner, same PC) to resume rather than forcing an archive.
