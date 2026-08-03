---
priority: high
effort: high
depends: [1275]
issue_type: feature
status: Ready
labels: [task_workflow, aitask_monitormini, bash_scripts, git]
gates: [risk_evaluated]
folded_tasks: [666]
created_at: 2026-07-29 22:01
updated_at: 2026-07-29 22:01
boardidx: 98304
---

## Problem

When many code agents run in parallel against the same repository, there is no
way to tell whether it is safe to start a new one — or to let a planning agent
progress into implementation — given what the other running agents are already
editing. Agents routinely end up editing the same files, and the collision is
only discovered after time has been lost. Follow-up tasks and risk-mitigation
tasks created by a human are especially prone to this, because they are written
against the same area as the work that spawned them.

**Nothing in the framework protects against this today.** The only existing
overlap check, `.aitask-scripts/aitask_remote_drift_check.sh`, compares
`BASE..origin/BASE` (`:202`) — i.e. commits *already pushed to origin*. Agents
working in a shared local checkout have pushed nothing, so the check reports
`NO_OVERLAP` for exactly the collisions that matter.

## Why attribution must be declared, not observed

`create_worktree: false` in `aitasks/metadata/profiles/fast.yaml:5`, and the
`default` profile asks with "No, work on current branch" as the first/default
option (`.claude/skills/task-workflow/SKILL.md:252-260`). So in practice most
concurrent agents share **one** working tree.

In a shared working tree `git status` can say *"this file is dirty"* but never
*"task 1234 dirtied it"*. There is no per-task file manifest anywhere in the
framework: plan→file linkage is prose (regex-scraped on demand), task→file
linkage for completed work is the `(tN)` commit-message tag, and for in-flight
work it is the `aiwork/<name>` worktree convention — which does not exist when
`create_worktree` is false.

⇒ Each running task must **declare** what it intends to touch. That declaration
is the core new artifact.

## Goal

An **advisory** (never blocking, never auto-acting) signal that answers:

1. Which currently-running tasks intend to touch overlapping files?
2. Which of them are actually in the implementation phase (as opposed to still
   planning, where nothing has been written yet)?
3. Is this task safe to progress from planning into implementation right now?

surfaced (a) live in `ait minimonitor` as a mark on the agent rows, and (b) as a
check at the planning→implementation boundary, where it can actually prevent the
loss rather than report it afterwards.

## Design (established during exploration — confirm in planning)

### 1. Ephemeral per-task claim registry

A git-ignored, repo-local file per task, keyed by task id, holding the paths that
task intends to modify plus liveness/provenance fields.

- **Location:** beside the existing gate sidecars, `.aitask-gates/<task_id>/`
  (already git-ignored via `.gitignore:19`, already keyed by task id, already
  carrying that task's phase). Confirm during planning whether a sibling file
  there or a new top-level dir is cleaner.
- **Explicitly NOT the task file.** Task files live on the shared `aitask-data`
  branch; a high-churn field there means a commit per update on a branch that
  concurrent writers already diverge on. Measured shape: ~1ms for a plain local
  write vs 0.3–1.5s plus lock contention for an `ait git` commit.
- **Explicitly NOT `file_references:`.** That field exists
  (`aitask_create.sh --file-ref`, reader `.aitask-scripts/aitask_find_by_file.sh`,
  union-on-fold in `aitask_fold_mark.sh:172-176`) but was designed for review
  findings with line ranges feeding `--auto-merge` at creation, and adoption is 2
  of ~196 active tasks. Reusing it would overload a field with different
  semantics and persist ephemeral data in the durable record.
- **Liveness/reaping:** carry pid + starttime via `.aitask-scripts/lib/pid_anchor.sh`
  (already provides PID-recycling-safe liveness, used by `aitask_lock.sh`).
  Reaping is **fail-closed**: a claim whose liveness cannot be determined is
  kept, not dropped.

### 2. Claim production — derived by default, zero agent overhead

- **Primary (free):** derive the path set from the plan at plan externalization
  (`.claude/skills/task-workflow/planning.md:357`, helper
  `aitask_plan_externalize.sh`) using the same extractor the drift check uses.
  A script greps the just-written plan — zero extra agent turns, zero tokens.
- **Refresh:** at Step 8 pre-commit, widen the claim from `git status`
  (`.claude/skills/task-workflow/SKILL.md:452-456`).
- **Optional early claim:** one helper call during §6.1, before `ExitPlanMode`,
  so a planning agent becomes visible before approval. Costs ~1 tool call. Make
  this opt-in (profile key), not mandatory.

**Extractor must be hoisted, not duplicated.** The path-scrape currently inlined
at `aitask_remote_drift_check.sh:210-219` becomes a shared function used by both
callers. See `depends:` note on t1275 below — that extractor has a live bug.

### 3. The PLAN-phase blind spot (accepted, fail-closed)

In Claude Code the plan exists only at `~/.claude/plans/<random>.md` until
`ExitPlanMode` — a flat per-user directory with random names and no task
association, which `aitask_plan_externalize.sh:405-430` disambiguates purely by
mtime and which **refuses when more than one recent candidate exists**. With
several agents planning at once it is unattributable by construction and cannot
be used as a live source.

⇒ An agent still in PLAN phase with no claim renders as **unknown**, never as
**safe**. (Asymmetry worth noting: OpenCode / Codex CLI write plans directly to
`aiplans/`, so they *are* visible pre-approval.)

### 4. Phase signal — already available

`./.aitask-scripts/aitask_query_files.sh inflight` already emits
`INFLIGHT:<id>|<path>|<PLAN|IMPLEMENT|POSTIMPL>|<archive_status>`
(`aitask_query_files.sh:94-96`), derived from the gate ledger — no tmux, no git.
Coverage caveat: gated tasks only; decide in planning what an ungated task shows.

### 5. Detection — deterministic, no LLM

With ≤ ~15 live tasks the whole computation is a set intersection over already-
parsed data. Detection must **not** be an LLM skill. Reserve an on-demand LLM
adjudication path ("same file, different functions — actually fine?") that is off
the hot path and writes an advisory verdict with a provenance stamp.

New helper (name to confirm): a scan command emitting a line protocol in the
style of `aitask_remote_drift_check.sh` / `lib/desync_state.py`, e.g.
`PAIR:<a>:<b>:<n>:<paths>`, `PHASE:<id>:<phase>`, `UNCLAIMED:<path>`, `CLEAN:<id>`.
"Dirty file claimed by no running task" is itself a useful signal.

### 6. Display in minimonitor

- Render seam: `_agent_card_text` (`.aitask-scripts/monitor/minimonitor_app.py:643`),
  the single builder for a general-list agent row; glyph vocabulary lives in
  `.aitask-scripts/monitor/monitor_shared.py` (`_state_color:88`,
  `format_state_dot:110`, `format_shadow_glyph:121`).
- Read pattern: mtime-gated re-read exactly like `GateSummaryCache`
  (`monitor_core.py:2459-2514`), or subprocess + TTL cache exactly like
  `.aitask-scripts/monitor/desync_summary.py` (30s TTL, line protocol, compact
  badge). Both precedents already ship; pick one, do not invent a third.
- Minimonitor already holds, per tick and for free: every agent pane across
  sessions, `session → project_root` (`monitor_core.py:1358`), the task id
  (`TaskInfoCache.get_task_id_for_pane`, `monitor_core.py:2617`) and the parsed
  task frontmatter. Filtering to "same repo" is a filter on `project_root`.
- Three-state, advisory: **unknown** / **clear** / **overlapping**. Per project
  convention prefer an always-on glyph pair over presence/absence.
- A session-bar counter and a detail modal listing the conflicting pairs/files.

### 7. Peer Conflict Check at the planning Checkpoint

The place where time is actually saved. `.claude/skills/task-workflow/planning.md:418-458`
already runs the **Remote Drift Check** right before Step 7. A **Peer Conflict
Check** procedure sits beside it with the same shape: "your plan overlaps N files
with in-flight task tXXX, currently in IMPLEMENT phase" → proceed / wait /
re-scope. Advisory: the user always decides.

### 8. Not a shadow subskill

`aidocs/framework/shadow_agent.md:217-241` explicitly forbids the shadow becoming
"a flow step, a prerequisite, or a gate", and the shadow is bound 1:1 to a single
followed agent. Conflict safety is a **fleet-level** question over N agents —
that is minimonitor's domain. The shadow may *consume* the report; it must not
own it.

## Dependency

`depends: [1275]` — t1275 records that the path extractor at
`aitask_remote_drift_check.sh:216-219` keeps only paths under a hardcoded
allowlist of *this* repository's top-level directories, so in any consumer
project the intersection is always empty and the helper silently degrades to a
no-op. That extractor is about to gain a second caller; fix it before sharing it.

## Follow-up (separate task): t1344

`t1344_worktree_aware_conflict_semantics_line_ranges` (`depends: [1343]`) covers
worktree/branch-aware safety semantics and line-range granularity: agents working
in **separate worktrees on separate branches** do not clobber each other at edit
time — overlap becomes a *merge* risk, and non-overlapping hunks in the same file
may be perfectly safe. That needs line-range information, whose cost and
reliability are unknown (plans state paths, not line numbers; `git diff -U0`
hunks are reliable but only observational, after the edit). Tracked separately.

## Acceptance criteria

- [ ] A task's intended file set is recorded in an ephemeral, git-ignored,
      per-task claim store, produced automatically at plan externalization with
      no added agent turns, and refreshed at pre-commit.
- [ ] The path extractor is a single shared function; `aitask_remote_drift_check.sh`
      and the new scanner both call it (no duplicated regex).
- [ ] A scan command reports, for the currently-running tasks of one repo, the
      overlapping pairs with the offending paths, each task's phase, and any
      dirty file claimed by no running task — deterministically, with no LLM,
      in well under a second for ~15 live tasks.
- [ ] Stale claims are reaped fail-closed: a claim whose owner's liveness cannot
      be determined is retained (negative-control test).
- [ ] `ait minimonitor` renders a three-state advisory mark per agent row
      (unknown / clear / overlapping), asserted at render level
      (`widget.render().plain`), plus a session-bar counter.
- [ ] An agent in PLAN phase with no claim renders as **unknown**, never as
      **clear** (explicit test).
- [ ] A Peer Conflict Check runs at the planning Checkpoint beside the Remote
      Drift Check and surfaces overlaps with in-flight tasks; it is advisory —
      the user chooses proceed / wait / re-scope.
- [ ] Nothing blocks or auto-acts: no task status is changed, no agent is killed,
      no keystroke is sent, on the strength of this signal.
- [ ] Unit tests for the store/scan logic run without tmux and without a live
      agent; minimonitor tests follow the existing `tests/test_minimonitor_*.py`
      pattern.
- [ ] Docs updated: `website/content/docs/tuis/minimonitor/how-to.md` (new mark +
      semantics) and the task-workflow docs for the Peer Conflict Check.

## Open questions for planning

1. Claim store layout: a file inside `.aitask-gates/<id>/` vs a new top-level
   git-ignored dir. What purges it — archival, a reaper, or both?
2. What does an **ungated** task show, given `inflight` only covers gated tasks?
3. Should the optional early (pre-`ExitPlanMode`) claim be a profile key, and
   default on or off?
4. Glyph and key choice in minimonitor — must not collide with t1326.
   **RESOLVED by t1326, which landed first.** What it took and what it left:
   - **Key:** `space` is taken (both TUIs). Still free in both: `x`, `f`, `g`,
     `b`, `v`, `w`, `y`.
   - **Glyphs:** `★`/`☆` are taken (`MARK_GLYPH` / `MARK_EMPTY_GLYPH` in
     `monitor_shared.py`), alongside the pre-existing `●` (state), `◆`/`◆!`
     (shadow) and `≈`/`=` (compare mode). `☑`/`☐` are also spoken for — they
     mean "selected for this action" in `ConcernPickerModal`.
   - **Reusable plumbing:** `format_*_glyph(bool) -> str` returning Rich markup;
     the leftmost-glyph row layout; the `AgentMarksMixin` shape (guarded
     `action_*`, an injectable `_run_marks_cmd` subprocess seam, and
     `call_later(self._refresh_data)` to repaint). Reuse the shape, not the file.
   - **NOT reusable:** the store. t1326's is per-user and cross-repo
     (`~/.config/aitasks/agent_marks.json`); t1343's claims are repo-local and
     ephemeral. Deliberately kept as separate files — do not generalize
     `agent_marks.py` into a multi-kind container.
   - **Width:** the minimonitor row is at its budget. t1326 already cut the
     window-name cap 22 → 20 to pay for two columns; a third always-on glyph
     needs its own budget decision, not another silent cut.
5. Does the same mark belong in `ait monitor` (`_format_agent_card_text`,
   `monitor_app.py`) as well, or is minimonitor enough for v1? (t1326 chose
   both, so the seam is already wired in each app.)
6. Should the on-demand LLM adjudication path be in v1 at all, or deferred?

## Merged from t666: planning check sibling task overlap


Add a step to the planning workflow that requires the agent to search for
in-flight sibling/parent tasks on overlapping components/labels before
adding child tasks that may compete with existing fixes.

## Origin

Spawned from t664 (review claude memories). Encodes the rule from the
auto-memory `feedback_check_sibling_tasks_before_planning_overlap.md`,
which captured a user correction during t653 planning where the agent
proposed an `agentcrew` heartbeat fix child without checking that t650
already had three children mid-flight on the same heartbeat issue. User
pushback: "we have started planning how to tackle this issue in task 650,
look at it before suggesting more changes."

## Rule (verbatim from memory)

> When planning a fix for a multi-layer bug, the user expects you to find
> tasks already addressing nearby layers and **defer to them** instead of
> adding overlapping children.
>
> **Why:** Duplicate or competing children fragment the fix, increase merge
> risk, and confuse "which layer fixed it." The user prefers one canonical
> fix path per layer; siblings should be **complementary, not redundant**.
>
> **How to apply:**
> - Before writing a multi-child plan, `ls aitasks/` and search for tasks
>   with overlapping labels (e.g., `agentcrew`, `ait_brainstorm`) — not just
>   by name. Read child task files of any candidate parent, not only its
>   frontmatter.
> - If a sibling/parent already covers a layer, drop that layer from your
>   plan and add `depends: [<that_parent>]` to your task. Reference the
>   deferral explicitly in the Context section so reviewers can verify the
>   boundary.
> - Keep a child only if it adds defense-in-depth value the existing fix
>   demonstrably does not provide; if it's belt-and-suspenders for the same
>   scenario, drop it.
> - This is not about avoiding all overlap — complementary fixes are fine —
>   but about not *competing* for the same layer.

## Where to add

Target file: `.claude/skills/task-workflow/planning.md`

Section: §6.1 Planning, in the **Complexity Assessment** sub-section,
right before the "If creating child tasks:" branch (or as a new sub-step
between complexity assessment and child-task creation).

Suggested placement: a new sub-step labeled **Sibling-task overlap check**
that fires when the user has confirmed creating child tasks. The check:

1. Identify the labels and component areas the planned children will
   touch.
2. Run `aitask_ls.sh -v -l <label>` for each relevant label, plus a `grep`
   over `aitasks/` for component-name matches.
3. For each match, read the candidate parent's child task files (not just
   frontmatter) to check for in-flight overlap.
4. If overlap is found:
   - Drop the redundant child(ren) from this plan, OR
   - Add `depends: [<other_parent>]` to this task and reference the
     deferral in the Context section.
   - Keep a child only if it adds defense-in-depth value the existing fix
     demonstrably does not provide.

## Implementation suggestions

- Express the step as a numbered procedure with a concrete command
  example, similar to other planning.md sub-steps (e.g., "Ad-Hoc Fold
  Procedure" at lines 113-139).
- Include the t650 vs t653 correction as the worked example.
- Cross-reference CLAUDE.md "Planning Conventions" if helpful (the
  "Refactor duplicates before adding to them" rule there is adjacent in
  spirit).

## Cross-agent parity follow-up

Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS":
> Skill/custom command changes and development, if not specified
> otherwise, should be done in the Claude Code version first. When such
> changes take place, suggest to the user to create separate aitasks to
> update the corresponding skills/commands in their codex cli / gemini cli
> / opencode versions.

After this Claude Code change lands, suggest follow-up tasks to mirror
the change in:
- `.opencode/skills/task-workflow/planning.md`
- `.gemini/skills/task-workflow/planning.md`
- `.agents/skills/task-workflow/planning.md`

## Verification

- `git diff .claude/skills/task-workflow/planning.md` shows a new
  numbered sub-step in §6.1.
- The new step references the t650 vs t653 example.
- No other files modified.
- Manual: walk through the planning of a hypothetical multi-child
  parent task and confirm the new step would surface adjacent in-flight
  work.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t666** (`t666_planning_check_sibling_task_overlap.md`)
