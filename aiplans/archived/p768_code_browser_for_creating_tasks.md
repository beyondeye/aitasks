---
Task: t768_code_browser_for_creating_tasks.md
Worktree: (none — working on current branch per `fast` profile)
Branch: main
Base branch: main
---

# Plan — t768 Code Browser for creating tasks

## Context

The TUIs overview page at `website/content/docs/tuis/_index.md` (lines 18–19) describes the Board and Code Browser TUIs with workflow framings:

- Board is described as "used at the **beginning** of the workflow".
- Code Browser is described as "Used at the **end** of the workflow or when onboarding to unfamiliar code."

The user wants to update the page to:

1. **Add task-creation capability to the Code Browser bullet.** The `n` key in codebrowser already spawns a new task pre-filled with a `file_references` line range, with optional auto-merge (fold) of existing tasks referencing the same file. This is documented in `website/content/docs/tuis/codebrowser/_index.md` lines 107–116 and the workflow page `/docs/workflows/create-tasks-from-code`. The TUIs overview page does not mention it.
2. **Remove "Used at the end of the workflow"** from the Code Browser bullet.
3. **Remove "used at the beginning of the workflow"** from the Board bullet.

These workflow-stage framings are being dropped — both TUIs are useful throughout the workflow, and the new task-creation capability in particular makes "end of the workflow" inaccurate.

## Files to modify

- `website/content/docs/tuis/_index.md` — lines 18–19 (the Board and Code Browser bullets).

No other file changes. No code, no scripts, no schema. Pure prose edit.

## Edit details

### Bullet 1 — Board (current line 18)

Current:
```
- **[Board](board/)** (`ait board`) — Kanban-style task board used at the **beginning** of the workflow: triage tasks, set priorities, organize work into columns, and decide what to implement next.
```

New (drop the workflow-stage clause; lead directly with the action verbs):
```
- **[Board](board/)** (`ait board`) — Kanban-style task board for triaging tasks, setting priorities, organizing work into columns, and deciding what to implement next.
```

### Bullet 2 — Code Browser (current line 19)

Current:
```
- **[Code Browser](codebrowser/)** (`ait codebrowser`) — Code navigation and diff review with task-aware annotations that show which aitasks contributed to each section, plus a **completed tasks history** screen (press `h`) for browsing archived work. Used at the **end** of the workflow or when onboarding to unfamiliar code.
```

New (drop "Used at the end of the workflow or"; add task-creation sentence at the end):
```
- **[Code Browser](codebrowser/)** (`ait codebrowser`) — Code navigation and diff review with task-aware annotations that show which aitasks contributed to each section, plus a **completed tasks history** screen (press `h`) for browsing archived work. Useful when onboarding to unfamiliar code. Also lets you create new tasks that reference specific line ranges in specific files (press `n` on a selected range), with optional automatic merge of existing tasks referencing the same file — see [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}).
```

Notes on the chosen phrasing:
- "Useful when onboarding to unfamiliar code." preserves the onboarding hint from the original sentence (the user only asked to remove the "end of the workflow" framing, not the onboarding mention).
- The new sentence reuses the same `relref` link to the existing workflow doc that the codebrowser page itself uses (line 116 of `codebrowser/_index.md`), keeping cross-references consistent.
- "automatic merge (optional)" → rendered as "with optional automatic merge" for natural prose.

## Verification

- Read the edited `website/content/docs/tuis/_index.md` to confirm both bullets render as intended.
- Optional: build the Hugo site locally (`cd website && ./serve.sh`) and load `/docs/tuis/` to visually confirm the bullets — but this is optional for a prose-only edit. Per CLAUDE.md, "type checking and test suites verify code correctness, not feature correctness" applies less here since there is no behavior change.
- Confirm the `relref` target still resolves: `website/content/docs/workflows/create-tasks-from-code` directory should exist.

## Step 9 (Post-Implementation)

Per task-workflow Step 9:
- No branch was created (profile `fast` → `create_worktree: false`), so no merge/worktree cleanup.
- Commit code change with subject `documentation: <description> (t768)`.
- Archive task via `./.aitask-scripts/aitask_archive.sh 768`.
- Push via `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Edited the two affected bullets in `website/content/docs/tuis/_index.md` exactly as proposed in the plan. The Board bullet now reads "Kanban-style task board for triaging tasks, setting priorities, organizing work into columns, and deciding what to implement next." The Code Browser bullet now reads "…browsing archived work. Useful when onboarding to unfamiliar code. Also lets you create new tasks that reference specific line ranges in specific files (press `n` on a selected range), with optional automatic merge of existing tasks referencing the same file — see [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}})."
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Kept the "Useful when onboarding to unfamiliar code." clause — the user only asked to remove the "end of the workflow" framing, not the onboarding hint. Reused the same `relref` target (`/docs/workflows/create-tasks-from-code`) that the codebrowser page itself already uses.
- **Upstream defects identified:** None
