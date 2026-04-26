---
Task: t639_show_all_manual_verification_list_in_skill.md
Base branch: main
plan_verified: []
---

# Plan: Show full numbered checklist + batch updates in manual-verification loop

## Context

The current manual-verification loop (`.claude/skills/task-workflow/manual-verification.md`,
Step 2) iterates verification items one at a time: it renders a single `Item N: <text>`
line and asks Pass/Fail/Skip/Defer (or free-text via Other). The user sees only the
current item — they have no overview of remaining work, can't recall what they already
marked, and can't batch-resolve obvious items (e.g., "items 1, 2, 3 all pass") in a
single round-trip. With long checklists this is friction.

**Goal:** before each `AskUserQuestion`, render the full numbered checklist (with each
item's current state) so the user always has the overview, and teach the Other branch
to accept batch updates of the form `<idx> <verb> [args]`, comma-separated, so the
user can resolve multiple items in one question.

Out of scope: changes to `aitask_verification_parse.sh` (the existing `parse` /
`set` / `summary` subcommands already support all needed reads/writes), the gating
script (`aitask_archive.sh`), the followup helper (`aitask_verification_followup.sh`),
or the Defer/carry-over checkpoint in step 3. Other-agent SKILL.md ports (opencode /
codex / gemini) — those wrappers don't currently embed the manual-verification flow at
all (it lives only in `.claude/skills/task-workflow/manual-verification.md`); a port
would be a separate follow-up if/when those wrappers grow it.

## Files to Modify

1. **`.claude/skills/task-workflow/manual-verification.md`** — restructure Step 2.
2. **`website/content/docs/workflows/manual-verification.md`** — update the
   "Running a Manual-Verification Task" section + the "Other (free text)" row of the
   outcome table.

## Change 1 — `.claude/skills/task-workflow/manual-verification.md` Step 2

Current shape (procedural, skim):

```
2. Main loop
   parse → for each item whose state is pending|defer:
     1. Render "Item N: text"
     2. AskUserQuestion (Pass/Fail/Skip/Defer + Other hint about pause)
     3. Handle answer:
        Pass / Fail / Skip / Defer → mutate item, advance
        Other → pause-intent => abort branch
              → otherwise => conversational, re-ask SAME item
     4. Move to next pending/deferred item
```

New shape — render-then-ask outer loop, current-item inner ask:

```
2. Main loop (re-entrant after every mutation)
   a. parse → emit ITEM lines.
   b. If no item is in state pending|defer → break loop, go to step 3 (post-loop checkpoint).
   c. Render the FULL NUMBERED CHECKLIST as plain text, one line per item, e.g.:
        Verification checklist (5 items):
          1. ✓ pass    Open the brainstorm TUI and confirm the left pane renders
          2. ✓ pass    Ctrl+B opens the brainstorm view
          3. ⏳ pending Ctrl+N spawns a new task from the brainstorm view
          4. ⏳ pending Agent spawn lands in a fresh tmux window
          5. ⏸ defer   Verify tmux session reuse logic
      Use one-character/short state markers per state:
        pending  → ⏳ pending
        pass     → ✓ pass
        fail     → ✗ fail
        skip     → ⊘ skip
        defer    → ⏸ defer
      (Plain ASCII fallback is fine — agents may render to terminals that drop unicode.)
   d. Immediately after the checklist, print a one-line HINT advertising the
      Other-field batch-update functionality so the user sees it before the
      AskUserQuestion is rendered. Example:
        Tip: in the Other field you can batch-resolve multiple items in one go,
        e.g. "3 pass, 4 fail, 5 skip not applicable" (verbs: pass / fail / skip / defer).
      Print the hint on every loop iteration — it's the discovery surface for the
      batch path; burying it inside the AskUserQuestion text is what we are
      explicitly avoiding.
   e. Identify the FIRST item whose state is pending|defer — call this the "current item".
   f. AskUserQuestion for the current item:
      - Question:
          "Item <idx>: <text>
          
          Pass / Fail / Skip / Defer for this item, or use Other (see tip above)."
      - Header: "Verify"
      - Options: Pass / Fail / Skip (with reason) / Defer  — unchanged.
   g. Handle answer:
      - Pass / Fail / Skip / Defer  → apply to CURRENT item (commands unchanged from
        the existing procedure: `set ... pass`, the followup helper for fail,
        `set ... skip --note`, `set ... defer`). Loop back to step a.
      - Other → interpret intent (in priority order):
          (i) PAUSE INTENT — abort/stop/quit phrasing → execute existing Abort branch
              (no commit, current item unchanged).
          (ii) BATCH UPDATE — text consists of one or more entries matching the
              pattern `<idx> <verb> [args]`, separated by commas, semicolons, or
              newlines. <verb> is pass | fail | skip | defer (case-insensitive).
              <idx> must be a valid item index (1-based) currently in state
              pending|defer. For each parsed entry, in order:
                pass  → set <task_file> <idx> pass
                fail  → aitask_verification_followup.sh --from <task_id> --item <idx>
                        (handle ORIGIN_AMBIGUOUS / ERROR exactly as in the
                         single-item Fail branch — prompt for origin if needed)
                skip  → set <task_file> <idx> skip --note "<rest-of-entry-text>"
                        (rest-of-entry-text is everything after `skip` until the
                         next delimiter; if empty, prompt once for a reason via
                         AskUserQuestion as in the single-item Skip branch)
                defer → set <task_file> <idx> defer
              Also accept a SHORTHAND single-entry form with no leading index
              (e.g., user types just `pass`): apply to the current item.
              VALIDATION: if any entry references an out-of-range index, an index
              already in a terminal state (pass/fail/skip), or an unknown verb, do
              NOT silently skip. Stop, list the problem entries, and re-ask the
              current item. Already-applied entries stay applied (no rollback).
              After all valid entries are applied, loop back to step a (which
              re-renders the checklist with the updated states and re-picks the
              new current item).
          (iii) CONVERSATIONAL — neither pause nor batch update: handle as a normal
              chat message (existing behavior: answer the question, perform the
              investigation, etc.). After handling, loop back to step f for the
              SAME current item (no checklist re-render needed unless the user's
              instructions caused state changes).
```

Editing notes:
- Step 2 currently lives at lines 43–109 of `manual-verification.md`. The
  restructure replaces the per-item loop scaffolding and the Other-branch
  case-list. Step 1 (pre-loop seed), step 3 (post-loop Defer checkpoint), step 4
  (commit), step 5 (hand off to Step 9) are untouched.
- Keep the existing per-state command examples (`./.aitask-scripts/aitask_verification_parse.sh set …`,
  the followup helper invocation, the ORIGIN_AMBIGUOUS handling) verbatim — only
  the surrounding control flow changes.
- The state-marker set above is the canonical list to use; keep it consistent
  between the skill file and the website doc.

## Change 2 — `website/content/docs/workflows/manual-verification.md`

Two edits inside the **"Running a Manual-Verification Task"** section
(lines 74–88 of the current file):

1. Add one paragraph (between the current paragraph 2 and the outcome table)
   describing the new render-then-ask flow:

   > Before each prompt, the picker re-renders the full numbered checklist with
   > each item's current state (`pending` / `pass` / `fail` / `skip` / `defer`),
   > so you always have the overview, then prints a one-line tip advertising the
   > Other-field batch path. The prompt itself is still scoped to the first
   > remaining `pending` or `defer` item — but the Other field now also accepts
   > a **batch update** like `3 pass, 4 fail, 5 skip not applicable` (one or
   > more `<idx> <verb> [args]` entries, comma- semicolon- or newline-
   > separated). Each entry is applied with the same handler as the per-option
   > Pass / Fail / Skip / Defer choice; failing entries spawn the same follow-up
   > bug task, skip entries take the rest of the entry text as the reason. The
   > checklist is re-rendered after the batch is applied and the next remaining
   > item becomes the new current item.

2. Update the "Other (free text)" row of the outcome table to reflect the new
   triage order (pause / batch / conversational) — currently it only documents
   pause + conversational. New cell content:

   > Treated by intent. **Batch update** (`3 pass, 4 fail, 5 skip not applicable`)
   > resolves multiple items in one shot — each entry runs through the same
   > handler as its per-option counterpart, then the checklist re-renders.
   > **Pause / abort / stop** phrasing ends the loop without mutating state; the
   > task stays `Implementing` with the lock held so only the original picker
   > can resume. Anything else is treated as a conversational message — answer a
   > question, perform an investigation, apply a correction — and the current
   > item is re-asked without advancing the index.

3. Optionally, in the "Tips" section near the end, add one bullet:

   > - **Batch out the obvious items.** When the first 4 items are all clearly
   >   passing, type `1 pass, 2 pass, 3 pass, 4 pass` in Other instead of
   >   round-tripping four times. Mix verbs freely (`1 pass, 2 fail, 3 skip n/a`).
   >   Failing entries still create the standard follow-up bug task.

Other website pages (`aitask-pick/_index.md`, `blog/v0170-…`) reference the
manual-verification flow at a higher level and do not need updates — they don't
describe the per-item loop mechanics.

## Verification

This is a docs/skill-instruction change with no script changes, so existing tests
remain green automatically. Manual verification:

1. Lint the changed files for broken markdown / dangling references:
   ```bash
   shellcheck .aitask-scripts/aitask_verification_parse.sh   # unchanged but sanity check
   ```
2. Re-read the modified skill file end-to-end and confirm the Step 2 → Step 3
   handoff still reads coherently (no orphaned references to "Move to the next
   pending item" sub-step etc.).
3. Build the website to confirm the docs page renders without Hugo errors:
   ```bash
   cd website && hugo build --gc --minify
   ```
4. End-to-end smoke (manual, no automated coverage exists for the LLM-driven
   loop): create a throwaway manual-verification task with 4–5 items, pick it
   via `/aitask-pick <id>`, confirm the new render-then-ask loop fires, then
   exercise:
     - a batch update mixing pass/skip/defer (`1 pass, 2 skip n/a, 3 defer`)
     - a batch update that includes a fail (verify the followup task is created
       and the same checklist re-renders with item marked `fail follow-up t<N>`)
     - a single-verb shorthand (`pass`) → applies to current item
     - a malformed batch (`99 pass`) → no silent drop; user is shown the error
       and the current item is re-asked
     - a conversational Other ("can you re-check item 3?") → loop stays on the
       current item, no state mutation
     - a pause Other ("stop for today") → existing Abort branch fires, no commit

## Step 9 (Post-Implementation)

Standard cleanup, archival, and merge per the shared task-workflow Step 9 — no
branch was created (profile fast: `create_worktree: false`), so the workflow
runs straight into archival via `./.aitask-scripts/aitask_archive.sh 639`.

## Follow-up Suggestions (post-implementation, not in scope)

Per CLAUDE.md, when skill instructions change in `.claude/skills/`, the analogous
opencode / codex / gemini ports may need updating. In this case the
manual-verification flow is not currently present in any other agent wrapper —
the runners under `.opencode/skills/aitask-pick/SKILL.md`,
`.agents/skills/aitask-pick/SKILL.md`, and `.gemini/` contain no `verification`
content. So no port task is needed unless those wrappers later grow the flow.

## Final Implementation Notes

- **Actual work done:** Step 2 of `.claude/skills/task-workflow/manual-verification.md`
  was restructured from an item-iterating loop into a re-entrant render-then-ask
  loop (sub-steps 1–7): every iteration re-runs `parse`, renders the full numbered
  checklist with state markers (⏳ pending / ✓ pass / ✗ fail / ⊘ skip / ⏸ defer),
  prints a one-line tip about Other-field batch updates, picks the first remaining
  pending|defer item as the "current item", and asks Pass/Fail/Skip/Defer scoped to
  it. The "Other" branch now triages by intent in priority order: (i) pause/abort,
  (ii) batch update parsing `<idx> <verb> [args]` entries comma/semicolon/newline-
  separated with a shorthand single-entry-no-index form targeting the current item,
  (iii) conversational fallback. Per-state commands (`set …`, the followup helper)
  are unchanged — only the surrounding control flow was rewritten. The website
  workflow page (`website/content/docs/workflows/manual-verification.md`) was
  mirrored: the "Running a Manual-Verification Task" section now describes the
  render-then-ask flow with an example checklist render, the outcome table's "Other
  (free text)" row was rewritten to document the three-way triage, the example
  end-to-end was rewritten to demonstrate a `1 pass, 3 defer` batch followed by an
  Item 2 per-option Fail, and a "Batch out the obvious items" Tips bullet was
  added.
- **Deviations from plan:** None of structural significance. The example
  end-to-end on the workflow doc was rewritten more aggressively than the plan
  initially called for (the plan only listed two non-optional edits inside
  "Running a Manual-Verification Task" + an optional Tips bullet) — but the
  pre-existing example contradicted the new flow ("rendered one at a time"), so
  it was updated in the same pass to keep the page coherent.
- **Issues encountered:** The pre-existing working tree had unrelated dirty
  files (`.aitask-scripts/board/aitask_board.py` adding `SelectionList`/`Selection`
  imports, `.claude/settings.local.json` adding a `Bash(./ait ls *)` permission).
  Both were excluded from the commit by staging only the two intended files.
- **Key decisions:**
  1. Render the checklist as plain text printed BEFORE `AskUserQuestion`, plus a
     standalone Tip line — not embedded in the question text. This was an explicit
     mid-plan course correction from the user ("show a hint to the user that the
     other branch allow the new functionality, perhaps just after printing the
     list of items"). Matching the rendered checklist + tip on every iteration
     (rather than once per session) is what makes the batch path discoverable.
  2. Allow the shorthand single-entry no-index form (`pass`, `skip not applicable`)
     to target the current item — keeps the legacy single-item answer path
     reachable through Other without forcing the user to remember the index.
  3. Batch validation is fail-stop, no rollback. If entry 5 of 8 references an
     invalid index, entries 1–4 stay applied and processing halts at 5; the
     checklist re-render shows exactly what was applied. Rollback would require
     transactional state on a Python helper that only mutates lines in place — not
     worth the complexity for an LLM-driven path that can simply re-prompt.
- **Notes for sibling tasks:** None — this task has no siblings. The deferred
  follow-up of porting this flow to opencode / codex / gemini wrappers stands as
  documented in "Follow-up Suggestions" above; those wrappers do not currently
  embed the manual-verification flow at all, so no port task was filed.
- **Build verification:** `hugo build --gc --minify` ran clean (169 pages, 867
  ms, single pre-existing `.Site.AllPages` deprecation warning unrelated to this
  task).
