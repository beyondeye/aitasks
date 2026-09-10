# The Task in Plain Words

A sub-procedure of the shadow skill (`aitask-shadow`). Shortcode `>t`. Use it
when the user wants to know *what the followed agent's task is actually about*
without reading the task file or the plan — someone who walked up to the pane,
or who queued the task days ago and has lost the thread.

It is **task-first and non-interactive**: a few short paragraphs built from the
task description and, when one can be found, the current plan. That is what
sets it apart from `plan-explain.md`, which is plan-only and walks the user
through the plan's technical subjects interactively.

**Never emitted unprompted.** Run it only when the user asks for it — by its
shortcode or in words. Do not produce it at startup, after a capture or
refetch, or as a proactive offer.

**Not a concern producer.** It emits no concern block, consults no rejection
store, and carries no round header — `concern-format.md` does not apply. Of
`round-preamble.md` exactly two parts do: §1 (the audience rule) and §6's
**source selection** (which plan text to read, and in what order); its snapshot
writes, round headers and review preambles do not. It is prose for a human,
nothing more.

**Inputs:** the source task id (shadow Step 2), then

    ./.aitask-scripts/aitask_shadow_context.sh <source_task_id>

Read `TASK_FILE:` and, when it is not `NOT_FOUND`, `PLAN_FILE:`. No `--siblings`,
no `aitask_explain_context.sh` — this is meant to be cheap.

**`PLAN_FILE:NOT_FOUND` does not mean "no plan".** The helper resolves only
plans that have been externalized under `aiplans/`. While the followed agent is
still *in* plan mode, its plan is a draft at `~/.claude/plans/<name>.md` and the
helper answers `NOT_FOUND` although a complete plan is right there on the
screen. So on `NOT_FOUND`, fall through the source ladder `round-preamble.md`
§6 defines (it is stated there, not here): rung 2 — exactly one distinct
`~/.claude/plans/<name>.md` path visible on the deep capture → read that file;
else rung 3 — the plan as rendered on the deep capture, treated as possibly
partial. Only when every rung comes up empty say that **no plan could be found
from here** — never that none exists — and summarise the task alone.

**Audience:** the reader `round-preamble.md` §1 defines — someone who will not
read the plan. Outcomes and behaviours, not mechanisms; no file paths, function
names or framework terms unless a word has no plain substitute, unpacked in the
same sentence. That rule is binding here and lives only there.

**Advisory-only:** present everything to the user; never drive the followed
agent's pane.

## Procedure

1. **Resolve the task id** by shadow Step 2's rules (argument → window name /
   screen → ask once). Degrade explicitly:
   - no id, and the user cannot supply one → say you cannot summarise a task
     without knowing which one, and offer `>e` (explain what is on screen)
     instead;
   - `TASK_FILE:NOT_FOUND` → say the task file could not be resolved for that
     id, and stop.

2. **Read the task file. Then read the plan** from the first source that
   applies: `PLAN_FILE:<path>` → that file; else the `round-preamble.md` §6
   ladder (a single draft-plan path on the deep capture → the deep capture
   itself). Say in one line where the plan came from. A capture-sourced plan is
   possibly partial — say that too. Nothing found → say a plan could not be
   found from here, and continue with the task alone.

3. **Write a few short paragraphs**, in this order — the last two only when a
   plan was found:
   - **What this is trying to achieve, and why it is worth doing** — the
     problem as a person would feel it, and what "done" looks like.
   - **What changes for someone using it** — the visible difference, and
     anything that stops working or works differently.
   - **How the agent means to get there** — the approach, in the order it
     happens, as steps a non-expert can picture.
   - **Roughly how far along it is** — planned / partly done / nearly done,
     read from the plan's own progress marks and from the screen; say "unclear"
     rather than guess.

4. **Writing rules:** lead with outcomes; no jargon unless it is unpacked in the
   same sentence; no file paths, function names or task ids beyond the one being
   summarised; a minute to read, not five.

5. **Offer follow-ups**, in one line: `>px` for a deeper walkthrough of the
   plan, `>pc` to challenge it, `>pa` for what it silently assumes.
