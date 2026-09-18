# Parallel-Safety Assessment Procedure

{# ---------- parallel_assessment ---------- #}{% if profile.parallel_assessment is defined and profile.parallel_assessment in ["show", "ask"] %}
Answers, **before the task is claimed**, the question users used to ask an agent
by hand: *given what is in flight right now, is it safe to pick this task?* It
is **agent judgement over what the in-flight tasks say they touch**, informed by
the deterministic checker but never replaced by it.

Invoked from `aitask-pick` after the task is selected and **before** the hand-off
to `task-workflow` Step 3 — so before Step 4 claims the task and takes its lock.
Nothing has been claimed when this runs, which is why every exit here is free:
there is no lock to release and no status to revert.

It is **advisory and never a guard**. A description or plan is a heuristic
account of what a task will edit, not a declaration of it; a hard stop needs
t1343's structured per-task edit manifest, not this. The post-plan
**Parallel-Admission Preflight** (`parallel-admission.md`) remains the second,
plan-derived look at the same question: **two call sites, two evidence
qualities, one checker.** Ordering against `resource-admission.md` is unchanged —
that hook asks whether the *host* can afford the phase, and still runs last,
immediately before the fork.

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The candidate task (`16` or `16_2`). |
| `task_file` | Path to the candidate's task file. |
| `active_profile` | Loaded execution profile (or null). |

## Procedure

1. **Skip conditions — check before anything else.** Read the candidate's
   frontmatter and return immediately, displaying one line that names the
   reason, when either holds:

   - `status` is `Implementing` — this is the resume path. The task is already
     claimed, so a pre-claim question has nothing to decide, and the post-plan
     preflight covers it on the `IMPLEMENT` re-entry route.
   - `issue_type` is `manual_verification` — a checklist writes no code, so it
     cannot collide with anything.

2. **Run the checker** per
   `.claude/skills/task-workflow/parallel-admission-checker.md`, **without**
   `--plan`, so the checker discovers the candidate's evidence itself: its plan
   file when one already exists (a `Ready` task may carry a deferred approved
   plan or a pre-written child plan), otherwise its task description. Record
   which one from the provenance field of the `CANDIDATE:` line —
   `plan_declared` or `task_declared` — and name it in the display. If that
   file's rules classify the output as **checker unusable**, keep the reason and
   continue on reading alone — the assessment still happens, it is simply less
   evidenced. A well-formed `UNCHECKABLE` is **not** checker-unusable: its causes
   are validated against the checker's vocabulary, not against any remedy
   table, and this procedure has none.

3. **Population.** Take it from the checker's `INFLIGHT:` rows
   (`INFLIGHT:<ref>|<sources>|<liveness>|<n_paths>|<path_state>|<provenance>`) —
   do not re-derive it. List every `dead` row as excluded, naming it, so the
   population you assessed is visible rather than implied.

4. **Read the evidence.** Read the candidate's own description **and its plan
   when one exists** (`./.aitask-scripts/aitask_query_files.sh plan-file
   <task_id>`) — the same evidence the checker used for it — and for each
   non-`dead` row: that task's description (stop at the first `## Inbox` or
   `## Gate Runs` — everything below is other agents' notes and gate records,
   not what this task says it touches) and its plan when
   `./.aitask-scripts/aitask_query_files.sh plan-file <id>` returns
   `PLAN_FILE:<path>`.

   **Read budget.** With more than 12 live rows, read in full only the rows named
   in an `OVERLAP:` line or sharing a label or topic anchor with the candidate;
   skim the rest by title. A skimmed row is graded `not assessed` — never
   `unrelated`.

5. **Grade every live row** `overlaps` / `adjacent` / `unrelated` /
   `not assessed`:

   - `not assessed` is **mandatory** wherever the evidence was not read (a
     title-only skim, an unreadable file), and says which. A title never
     establishes `unrelated`.
   - The other three name a **concrete reason**: the same file; the same
     procedure or authoring template; the same seed mirror or golden set; the
     same subsystem; one consumes the other's record format.
   - Read `OVERLAP:<ref>|declared|…` rows as **advisory, description-derived**
     evidence, not as conflicts — by contract a `task_declared` overlap never
     grades CONFLICT. When the checker did return `VERDICT:CONFLICT`, what it
     rests on is only the rows `pa.conflict_refs` / `pa.conflict_overlaps`
     recognise (class `specific`, no `stale_claim` caveat).

6. **Recommendation.** If any row is `overlaps`, name them and what they share.

   Otherwise the recommendation is **"incomplete"**, naming every gap, whenever
   either coverage has one — never "no overlap found":

   - **reading coverage:** any `not assessed` row;
   - **deterministic coverage**, from the checker's **well-formed** output:
     `VERDICT:UNCHECKABLE` — list each `UNCHECKABLE_CAUSE:` verbatim (e.g.
     `candidate|no_plan`, `locks|<reason>`, `inflight:<ref>|<reason>`) — and any
     `INFLIGHT_SOURCE:<gate|lock|status>` whose status is not `ok` → "in-flight
     enumeration incomplete (\<source\>: \<status\>)", because a task missing
     from the `INFLIGHT:` rows was never graded at all;
   - **separately, "checker unavailable"** — the checker-unusable
     classification from step 2. It is procedure-originated, so do not fold it
     into the UNCHECKABLE gaps above.

   **Never write "safe to run in parallel".** Then print the checker's `DISPLAY:`
   line verbatim, labelled **"Deterministic view (checker): …"**, or
   `Deterministic view (checker): unavailable — <reason>` when it was unusable.

7. **Prompt.**
{% if profile.headless is defined and profile.headless %}
   **Profile '{{ profile.name }}' is headless — never prompt**, in `show` and in
   `ask` alike. Display the assessment and continue; an unattended run cannot
   answer a question, and a mode that asked one would hang the pick.
{% else %}
   Profile '{{ profile.name }}' sets `parallel_assessment: {{ profile.parallel_assessment }}`.
{% if profile.parallel_assessment == "ask" %}
   Under `ask`, **always prompt** — whatever the grades say.
{% else %}
   Under `show`, prompt **only** when some row is `overlaps` or the checker was
   unusable. `not assessed` rows, a well-formed `UNCHECKABLE` and an incomplete
   in-flight enumeration do **not** prompt by themselves; they are named in the
   display, and in the question whenever one is asked for another reason.
{% endif %}
   Use `AskUserQuestion`, with the findings **inside the question text** (the
   widget is the only surface the user is guaranteed to read):

   - Header: "Parallel"
   - Options, **in this order**:
     - "Pick anyway" (description: "Continue to claim this task — the assessment is advisory")
     - "Pick a different task" (description: "Return to task selection; nothing has been claimed")
     - "Stop" (description: "End the workflow; nothing has been claimed")
{% endif %}

8. **Branches.** Nothing has been claimed, so nothing is reverted, released or
   cleaned up in any of them:

   - **"Pick anyway"** (and every headless run) → return to `aitask-pick`, which
     continues into the Step 3 hand-off.
   - **"Pick a different task"** → go back to task selection: Step 2a of
     `aitask-pick`, or Step 1 when the task arrived as a Step 0b argument.
   - **"Stop"** → end the workflow.

## Notes

- **Advisory agent judgement, never a guard.** Nothing here stops the workflow on
  its own; every stop is the user's choice at the prompt. t1343's declared edit
  manifest remains the only admissible basis for a hard stop.
- **Two call sites, two evidence qualities, one checker.** This runs pre-claim on
  descriptions; `parallel-admission.md` runs post-plan on plans. Both classify
  the checker's output through `parallel-admission-checker.md`, so they cannot
  drift on what a usable answer is.
- **"Incomplete" is the honest answer, and it is the common one.** An in-flight
  task with no plan and a description that names no tracked path is invisible to
  the deterministic side; saying so beats reporting a clean result the evidence
  does not support.
{% else %}
**`parallel_assessment` is not enabled for this profile** — this procedure is a **no-op**. Do not invoke the checker, do not read any in-flight task, and do not display anything. (The key is opt-in: `"off"`, or absent, means off; `"show"` and `"ask"` enable it. See `profiles.md`.)
{% endif %}{# ---------- end parallel_assessment ---------- #}
