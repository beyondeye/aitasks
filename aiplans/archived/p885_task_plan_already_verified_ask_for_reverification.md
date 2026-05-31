---
Task: t885_task_plan_already_verified_ask_for_reverification.md
Base branch: main
plan_verified: []
---

# t885 — Show the plan and re-loop on "Revise plan"

## Context

In the task-workflow, when you pick a task whose plan **already exists and is
already verified**, the verify-decision returns `DECISION:SKIP` and the flow
jumps straight to the post-plan **Checkpoint** — without showing the plan. The
Checkpoint offers a "Revise plan" option, but today that option just says
**"Return to the beginning of Step 6."** That can't actually revise: returning
to the top of Step 6 re-runs 6.0's existing-plan preference check, and on
profiles with `plan_preference: use_current` (e.g. the `fast` parent path) 6.0
short-circuits *back* to the Checkpoint without entering plan mode — so the user
can never see or edit the plan. The agent, with no concrete plan on screen,
tends to improvise (summarize "main points" or ask an abstract multiple-choice
about plan parts), which the user cannot answer well.

**Desired behavior** (verbatim from the task): *"just reenter plan mode, show
the plan to the user and reenter the loop for plan approval, allowing the user
to answer 'other' with the specific modification they want."*

**"Revise plan" becomes the single way to view-and-edit the plan.** Per the
user's scoping decision, the Checkpoint will *not* auto-display the plan; a user
who wants to see it picks "Revise plan", which shows the full plan and re-enters
the approval loop.

## Approach

Single source-of-truth edit to the **Checkpoint** section of
`.claude/skills/task-workflow/planning.md` (a Jinja-templated `.md` rendered
per-profile into every agent tree — confirmed the only authoring copy; Codex /
OpenCode render byte-identically from it, so no separate port is needed). Two
edits, both plain prose (no Jinja), in the `## Checkpoint (after plan is saved)`
section. The Checkpoint does **not** auto-show the plan (per the user's scoping
decision); "Revise plan" is the single affordance for viewing and editing it.

### Edit 1 — Update the "Revise plan" option description

`"Re-enter plan mode to make changes"` →
`"Show the full plan, re-enter plan mode, and request specific changes"`
(signals to the user that picking this is how to see the plan).

### Edit 2 — Replace the "Revise plan" handler

Replace `If "Revise plan": Return to the beginning of Step 6.` with a concrete
loop:

> **If "Revise plan":**
> 1. Re-enter plan mode with `EnterPlanMode`.
> 2. **Show the current plan in full.** Read the saved plan file and present its
>    complete content. Do NOT condense to "main points" or ask which section to
>    change via a fixed multiple-choice list — the user needs the actual plan
>    visible to decide.
> 3. **Find out what to change.** If the user already named a specific
>    modification (in their message or via the `AskUserQuestion` "Other"
>    free-text option), apply it directly. Otherwise ask what they want to
>    change and accept a free-text answer.
> 4. Edit the plan in plan mode to incorporate the requested changes.
> 5. `ExitPlanMode`, re-run **Save Plan to External File** to persist the
>    revised plan, and return to **this Checkpoint** to re-present the approval
>    prompt with the revised plan shown. Repeat until the user selects "Start
>    implementation" or "Approve and stop here".
>
> Do NOT return to the beginning of Step 6 — that re-triggers the 6.0
> existing-plan preference check and, on `plan_preference: use_current`
> profiles, skips plan mode entirely and bounces back here without ever showing
> or revising the plan.

This satisfies each clause of the request: *reenter plan mode* (1), *show the
plan* (2), *reenter the approval loop* (5), *answer "other" with a specific
modification* (3). The verify-path `plan_verified` append is unaffected — it is
gated on "arrived via the verify path", which the Revise loop is not.

## Critical files

- `.claude/skills/task-workflow/planning.md` — the two prose edits above, both
  in the `## Checkpoint (after plan is saved)` section (~lines 382, 388).
- `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md` —
  regenerate (the added prose is unconditional, so it lands identically in all
  three goldens). Regen command per `aidocs/skill_authoring_conventions.md`:
  ```bash
  PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
  for p in default fast remote; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/task-workflow/planning.md \
      aitasks/metadata/profiles/$p.yaml claude \
      > tests/golden/procs/task-workflow/planning-$p.md
  done
  ```

## Verification

1. `bash tests/test_skill_render_task_workflow.sh` → all green (Test 1 golden
   diffs match after regen; Test 3's `'Plan saved to'` / `'An existing
   implementation plan was found at'` assertions still hold).
2. `./.aitask-scripts/aitask_skill_verify.sh` → clean (closure renders, no
   stub-pattern or staleness errors).
3. Eyeball `git diff` of the three goldens: the only change in each is the
   updated "Revise plan" option description + rewritten Revise handler — no
   unrelated drift.

## Blast radius

`planning.md` is in the render closure of **every** task-based skill (pick,
explore, fold, review, qa, …), so it's a high-traffic shared file. Mitigations:

- The edits are **purely additive prose inside the interactive Checkpoint** —
  no Jinja, no new conditionals, no control-flow change for non-interactive
  (`start_implementation`) profiles. The remote profile still skips the
  Checkpoint as before.
- Intended rendered-output change → goldens regenerated in the **same commit**
  (the convention). `tests/test_skill_render_task_workflow.sh` Test 1 fails
  loudly if a future editor touches `planning.md` without re-rendering, so the
  "someone edits this unaware" failure mode is caught by CI, not shipped.
- "Re-run Save Plan to External File" in the Revise loop reuses the existing,
  idempotent externalize path (`OVERWRITTEN:` for an existing plan); no new
  persistence code.

## Alternatives considered (rejected)

- **Add a new option at 6.0 ("Show current plan and revise").** Rejected: the
  task explicitly asks to fix the *existing* "Revise plan" option, and a
  parallel 6.0 entry point doubles the surface that can drift. Fixing the one
  handler is the smaller, truer change.
- **Auto-show the plan at the Checkpoint (an earlier draft's "Edit 1").**
  Dropped per the user's scoping decision: it adds prose to the always-rendered
  Checkpoint and re-displays a plan most users don't need to re-read. Folding
  "view the plan" into "Revise plan" keeps one affordance and a smaller diff.
- **Add a profile key to gate "show the plan".** Rejected as over-engineering —
  `post_plan_action` already decides whether the Checkpoint is interactive at
  all.

## Out of scope / follow-ups

- No new profile key — `post_plan_action` already gates whether the Checkpoint
  is interactive; this only changes what the interactive path does.
- task-workflow is shared across agents via the single Claude source, so no
  Codex/OpenCode port task is needed (unlike user-invocable skills).

## Final Implementation Notes

- **Actual work done:** Two prose edits to the `## Checkpoint (after plan is
  saved)` section of `.claude/skills/task-workflow/planning.md` — (1) the
  "Revise plan" option description now reads "Show the full plan, re-enter plan
  mode, and request specific changes"; (2) the `If "Revise plan":` handler was
  replaced from "Return to the beginning of Step 6" with a 5-step loop
  (EnterPlanMode → show full plan → take free-text/"Other" change → edit →
  ExitPlanMode + re-run Save Plan + return to this Checkpoint), with an explicit
  "Do NOT return to Step 6" caveat. Regenerated the three render goldens
  `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`.
- **Deviations from plan:** None to the source edit. Scope was trimmed during
  planning (the user dropped the earlier "auto-show plan at Checkpoint" Edit 1;
  "Revise plan" is now the single view-and-edit affordance).
- **Issues encountered:** Rendering the committed `task-workflow-remote-`
  prerenders surfaced pre-existing staleness unrelated to t885 (see Upstream
  defects). Restored those 6 files to HEAD so this commit stays scoped to the
  source edit + its test goldens. Plan externalize hit `MULTIPLE_CANDIDATES`
  (two recent internal plans); disambiguated via the plan-mode reminder path
  rather than prompting.
- **Key decisions:** Edit the single source of truth
  (`.claude/skills/task-workflow/planning.md`) only — Codex/OpenCode render
  byte-identically from it, so no per-agent port. Fixing the existing "Revise
  plan" handler (vs. a new 6.0 option or a new profile key) keeps the smallest
  surface. Verified via `tests/test_skill_render_task_workflow.sh` (70/70) and
  `aitask_skill_verify.sh` (clean).
- **Upstream defects identified:** `.claude/skills/task-workflow-remote-/planning.md:136 — committed task-workflow-remote- prerenders (planning.md + SKILL.md, across claude/codex/opencode) are stale vs source: missing the cross-repo dispatch (planning.md) and cross-repo child-assignment (SKILL.md) paragraphs that a prior cross-repo task added to source without rerendering the committed remote prerenders. aitask_skill_verify.sh enforces headless-prerender freshness only for aitask-pickrem (TODO t777_29 to generalize), so the drift was not caught. Fix: ./.aitask-scripts/aitask_skill_rerender.sh remote, then commit the refreshed task-workflow-remote- files.`
