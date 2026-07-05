# Implementation Challenge (adversarial)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
the **code actually written** for a task stress-tested — "review the
implementation", "did it actually do what the plan said", "check the code that was
written". This is the implementation-side companion to `plan-challenge.md` (which
reviews the *plan*). Your job is to be a constructive adversary against the
**implementation**: actively look for where the code, as written, is wrong — not
to reassure.

**Advisory-only:** present the findings to the user; never drive the followed
agent's pane. (Reading local git state — commits, diffs — is fine; "advisory-only"
governs the *followed pane*, not your own repo reads.)

## Inputs

1. **Task definition + plan** — via `./.aitask-scripts/aitask_shadow_context.sh <task_id>`
   (`TASK_FILE:` + active `PLAN_FILE:`). This is "what was supposed to be built."
   Resolve `<task_id>` as in the shadow SKILL.md Step 2 if it wasn't passed.

   **Archived-plan fallback (needed once the task is committed/archived).**
   `aitask_shadow_context.sh` returns only the *active* plan and deliberately does
   not scan the archive — so a completed task yields `PLAN_FILE:NOT_FOUND` even
   though its plan (carrying the Final Implementation Notes you most need here)
   lives under `aiplans/archived/`. When the active plan is missing, look there
   before concluding there is no plan:
   ```bash
   ls aiplans/archived/p<N>_*.md 2>/dev/null                        # parent task
   ls aiplans/archived/p<parent>/p<parent>_<child>_*.md 2>/dev/null  # child task
   ```
   Use the archived plan if found. Only when *neither* an active nor an archived
   plan exists is the plan genuinely unavailable.
2. **The actual code changes (real diff)** — first discover the task's commits:
   ```bash
   ./.aitask-scripts/aitask_revert_analyze.sh --task-commits <task_id>
   ```
   Each `COMMIT|<hash>|<date>|<subject>|<ins>|<del>|<matched-id>` line names a
   commit; read their diff (`git show <hash>`, or `git diff <first>^..<last>`).

   **Working-tree fallback (important — this is often the live case).** The task
   workflow commits the code *and* writes Final Implementation Notes only **after**
   the Step 8 review prompt. So at the common pre-commit review moment there may be
   **no task commit yet**, with all real changes sitting in the working tree /
   index. If `--task-commits` returns nothing (or only older sessions' commits),
   inspect the uncommitted state instead:
   ```bash
   git status --short   # what changed
   git diff             # unstaged changes
   git diff --cached    # staged changes
   ```
   Review whichever of committed / staged / unstaged actually carries this task's
   changes. **Tell the user which source you reviewed** (committed vs
   working-tree) — a working-tree review is of in-progress, not-yet-final state.
3. **The plan's `## Final Implementation Notes`** — the agent's own narrative
   (*Actual work done*, *Deviations from plan*, *Issues encountered*, *Key
   decisions*), written by task-workflow Step 8 at end of implementation. This is
   where deviations are *justified*.

When you (re)capture the followed pane to read long content, use the deep
plan-review capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep <followed_pane_id>` —
so a long diff or notes section isn't truncated to the default window's tail.

## "Too early to review" gate (required — run first)

If the resolved plan — **after** applying the archived-plan fallback in input 1 —
does **not** contain a `## Final Implementation Notes` section, the implementation
phase of the task workflow has not completed. (Resolve the archived plan first: a
committed/archived task has an archived plan *with* the notes, and must not trip
this gate.) When the notes are genuinely absent, before doing anything else
**warn the user**: it is probably too early to review the implementation — the
task workflow likely has not finished, so the diff may be partial and no
deviations have been narrated yet. Let the user decide: **abort**,
or **proceed anyway** against the partial state. Do not silently continue. If the
user proceeds anyway, the diff to review is necessarily the **working-tree /
index** state (input 2's fallback), not committed history — review that and say so.

## Attack the implementation along these axes

(Skip any that don't apply; add others the change invites.)

- **Implementation flaws** — bugs, missed cases, incorrect logic, off-by-ones,
  mishandled error/empty/edge inputs, or regressions in the code *as actually
  written*, checked against the plan/task intent and the real diff.
- **Risks left unmitigated** — cross-reference the plan's `## Risk` section and
  Final Implementation Notes. Do **NOT** re-flag a risk the implementation
  explicitly addressed/mitigated; surface only risks that remain **open** in the
  landed code.
- **Unjustified deviations from the plan** — compare the diff against the plan. A
  deviation the Final Implementation Notes justify is fine. Flag only
  deviations that are unexplained or whose justification does not hold up.

## Produce a prioritized list, then stay honest

Produce a prioritized list of concrete problems. For each: a one-line statement,
*why* it bites (the triggering scenario), and severity (high / medium / low).
Order by severity. Separate fatal (should block acceptance) from fixable
(follow-up). **Stay honest** (same rule as `plan-challenge.md`): if a dimension is
genuinely clean, say so briefly — a short list of real problems beats a long list
of weak ones. No generic "consider adding tests" filler.

## Also emit the structured concern block (for pick-and-forward)

After the human-readable list, append a machine-parseable copy of the *same*
concerns so the user can tick a subset and forward them to the followed agent via
minimonitor's concern picker. This block is **additive** and does **not** relax
the advisory-only guardrail (it is text for the *user* to copy).

**Emit this block as the final output of your review — nothing after it.**
Minimonitor's picker captures the tail of your pane and forwards the *last*
concern block it finds, so trailing commentary after the block (or forgetting to
emit it) makes the picker fall back to an earlier/stale block. Print the review,
then the block, then stop.

Emit a block delimited by an opening `===AITASK-CONCERNS===` line and a closing
`===END-CONCERNS===` line (those two exact literals; single source of truth:
`.claude/skills/aitask-shadow/concern-format.md`), with one concern per line
between them. The concern lines themselves look like:

```
- [high | path/to/file.ext:120] The new guard compares the raw email instead of the normalized one, so a task assigned with a trailing-space email never matches and re-locks every resume. It bites on the common reclaim path. Normalizing both sides before compare would fix it — exact form your call.
- [medium | unmitigated risk] The plan's Risk section flagged concurrent writers to the ledger, but the diff adds no locking around the append, so two resumes can interleave and drop one run. The Final Implementation Notes don't mention it, so it looks unaddressed rather than deliberately deferred.
```

Rules — all load-bearing for minimonitor's parser; match them exactly:
- One concern per line, in the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY** on every concern line —
  it is the wrap-collision guard (a soft-wrapped continuation line never carries
  it, so the parser can't mistake wrapped text for a new item).
- `priority` is one of `high`, `medium`, `low` — reuse the severity you assigned.
- `region` for implementation concerns should identify the **code locus**
  (e.g. `path/to/file.ext:LINE`) or the **axis** (`unmitigated risk`,
  `unjustified deviation`, `correctness`).
- `body` carries the **full framing** — the problem, *why it bites*, and enough
  context for the receiving agent to choose **how** to fix it. Do **not** compress
  it to a bare one-liner. "One logical line" is a **parser constraint** (emit no
  literal newline mid-concern — let the terminal soft-wrap), not a brevity
  constraint.
- Order items by severity, matching the prose list.
- **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
  auto-offer only fires on a complete block.
- Emit the block **only when you have at least one concern**. If the
  implementation is genuinely clean, omit the block entirely.
