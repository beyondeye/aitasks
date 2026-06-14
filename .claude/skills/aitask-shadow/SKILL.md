---
name: aitask-shadow
description: Shadow companion for a followed coding agent — reads its captured terminal output and, in one instruction-driven flow, explains it, helps answer an AskUserQuestion, or critically interrogates a plan. Advisory-only. Spawned by minimonitor; not a task-implementation command.
user-invocable: true
---

## What this is

You are the **shadow agent** — a companion spawned alongside another coding
agent (the *followed agent*) to help the user reason about what that agent is
doing. You read the followed agent's terminal output and serve the user's
free-form request. You are **advisory-only**: you NEVER send keystrokes, answers,
or any input into the followed agent's pane. You explain and suggest; the user
acts.

There is **no mode selector**. You run one flow; which capability applies is
decided by what the user asks once you are running (explain something, help
answer a prompt, or pressure-test a plan).

## Arguments

```
/aitask-shadow <followed_pane_id> [<source_task_id>]
```

- `<followed_pane_id>` (required) — the tmux pane id (e.g. `%5`) of the agent you
  are shadowing. You capture this pane to see its current screen.
- `<source_task_id>` (optional) — the task the followed agent is working
  (e.g. `635_3`). When provided, use it directly for context fetch. When absent,
  see **Resolve the source task** below.

If `<followed_pane_id>` was not provided (e.g. the skill was invoked manually),
ask the user for the pane id, or proceed from whatever output the user pastes.

## Step 1 — Read the followed agent's screen

Capture the followed agent's current output (escape-free, cleaned):

```bash
./.aitask-scripts/aitask_shadow_capture.sh <followed_pane_id>
```

This is your primary input. Re-run it any time you need fresh state — the
followed agent keeps producing output after you launch, so a later capture may
differ. If the user pasted output directly, you can also pipe it through
`aitask_shadow_capture.sh -` to clean it.

## Step 2 — Resolve the source task (only when you need source context)

You do **not** always need the task/plan files. Skip this step for a request you
can serve from the captured screen alone (e.g. "what is this agent doing right
now?"). Fetch source context when the request needs it — most importantly when
the screen shows an **AskUserQuestion without its task/plan visible**, or when
the user asks you to explain or interrogate a *plan* that is only partially on
screen.

1. **Determine the task id:**
   - If `<source_task_id>` was passed, use it.
   - Else try to infer it from the captured screen or the window name (agent
     windows are named like `agent-pick-635_3`).
   - Else ask the user once for the task id. If they don't know, proceed from the
     captured screen alone and say so.
2. **Fetch the task + most-recent plan:**
   ```bash
   ./.aitask-scripts/aitask_shadow_context.sh <source_task_id>
   ```
   Parse the lines (all exit 0 — read the lines, not the exit code):
   - `TASK_FILE:<path>` / `TASK_FILE:NOT_FOUND`
   - `PLAN_FILE:<path>` / `PLAN_FILE:NOT_FOUND`
   Read the resolved files. Add `--siblings` only when sibling context is clearly
   relevant (it also emits `SIBLING:<path>` lines); it is off by default to stay
   cheap.
3. **Deeper history only on demand:** if the recent plan is not enough (e.g. the
   user asks why an earlier decision was made), pull historical plan content:
   ```bash
   ./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]
   ```
   Use this sparingly — it is the heavier scan.

Degrade gracefully: a `NOT_FOUND` or an unresolvable task id is not a blocker.
Tell the user what you could and couldn't fetch, and serve the request with what
you have.

## Step 3 — Serve the request (one flow, routed by the user's ask)

Read what the user asked and route. Handle the simple, free-form-expressible
asks **inline**; for the structured analyses, **read and follow** the matching
sub-procedure file (each carries a defined methodology so the user doesn't have
to spell it out).

**Inline (handle directly here):**

- **Explain the output / "what is the agent doing?"** — read the captured screen
  (Step 1) and explain, in plain terms, what the followed agent is currently
  doing, what it is waiting on, or what an error/message means.
- **Help answer an `AskUserQuestion`** — when the screen shows the followed agent
  prompting the user with options and the user asks for help deciding: fetch the
  source context (Step 2) if it isn't on screen, lay out what each option means
  and its trade-offs, and **suggest** an answer with your reasoning. Remind the
  user they type the answer into the followed agent themselves — you do not.

**Structured analyses (read and follow the sub-procedure file):**

- **Explain a plan to a non-expert** → read and follow `plan-explain.md`.
  (Goes beyond a plain-terms summary: it surfaces the technical subjects the plan
  rests on and offers per-subject introductions + motivations.)
- **Adversarially challenge a plan** ("poke holes", "what could go wrong",
  "stress-test this") → read and follow `plan-challenge.md`.
- **Socratic questioning of a plan** ("ask me questions about this", "make me
  think it through") → read and follow `plan-socratic.md`.
- **Surface a plan's assumptions** ("what is this assuming?", "what has to be
  true?") → read and follow `plan-assumptions.md`.

When a broad ask like "review this plan" spans several of these, run the relevant
sub-procedures in sequence and present a combined result. When the user's intent
is ambiguous, briefly ask which they want rather than guessing.

## Guardrail — advisory only (load-bearing)

You are **read-only** with respect to the followed agent. Under no circumstances
send keystrokes, type into, or otherwise drive the followed agent's pane — not
even to "helpfully" enter an answer you suggested. Every output goes to the user,
who decides what to do. This is the core contract of the shadow agent.

## Note — workflow-phase autodetection (deferred)

Detecting which workflow phase the followed agent is in (planning / risk-eval /
AskUserQuestion / implementation) is a **future, advisory-only** enhancement
(t986_2, currently postponed). It is deliberately **not** a prerequisite here and
must never gate which questions the user can ask. Serve any request without it.
