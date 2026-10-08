---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [task_workflow, monitor, minimonitor, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 10:19
updated_at: 2026-10-08 16:43
---

## Problem

A task-workflow run (used by aitask-pick, explore, fold, review, qa, pr-import,
revert, … via `.claude/skills/task-workflow/SKILL.md`) has no explicit
"workflow completed" signal, either for the user reading the conversation or for
the monitor/minimonitor agent list.

### 1. The conversation never states that the workflow is complete

- No step instructs the agent to write a closing summary or a completion
  message. The last steps are Step 9 (`aitask_archive.sh` → parse its
  `ISSUE:`/`PR:`/`FOLDED_*`/`PARENT_ARCHIVED:`/`COMMITTED:` lines → `./ait git
  push`) and Step 9b (Satisfaction Feedback). Any end-of-run summary Claude Code
  writes is model habit, not an instruction — it is not guaranteed, its wording
  varies, and other agents (Codex, OpenCode) may not write one at all.
- Under the `fast` profile (`enableFeedbackQuestions: false`) Step 9b only runs
  the usage bump (`satisfaction-feedback.md` Step 0). The last thing displayed
  is `Profile 'fast': feedback questions disabled` — the run just stops.
- The many early/alternate exits each print an ad-hoc message or nothing:
  gate-pending "Defer — keep in-flight" (Step 9), merge-broker in-flight stops
  (`merge-broker.md` `stop-in-flight`), manual-verification "Stop without
  archiving", the child-split "Stop here" (`planning.md`), the risk-mitigation
  "before" stop (Step 7), Task Abort, and Step 3's "No, skip" exits. Only
  `plan-approved-stop.md` has an explicit `<closing_message>` display — a usable
  precedent.
- The gate ledger has no completion checkpoint: `resume-point` /
  `workflow-phase` know only `PLAN|IMPLEMENT|POSTIMPL` (+`UNKNOWN`). Completion
  is implicit in archival (`status: Done`, file moved to `aitasks/archived/`).

### 2. The monitor/minimonitor COMPLETED glyph fires before the workflow ends

`is_task_completed()` (`.aitask-scripts/monitor/monitor_shared.py:132`), used by
both `MonitorApp._compute_completed_panes` and
`MiniMonitorApp._compute_completed_panes` (t1322), is **not** gate-based: it
returns true when the pane's task has `status: Done` **or** its file path
contains `/archived/`. `aitask_archive.sh` writes both partway through Step 9,
so the blue `STATE_STYLE_DONE` dot/badge lights while the agent still has to
handle issue/PR/folded follow-ups, push, and Step 9b. (A pending prompt still
renders PROMPT, which outranks COMPLETED, but between prompts and during the
push the row already reads "completed".) Reported by the user: "the completed
glyph mark in the agent list is triggered BEFORE the task workflow actual last
step".

## Goal

1. **Explicit end-of-workflow step.** Add a final step (e.g. Step 10
   "Workflow Complete") to `task-workflow/SKILL.md` that always runs last on
   the success path, after Step 9b, regardless of profile, and is marked
   NON-SKIPPABLE like the other user-visible gates. It displays one
   fixed-format banner, e.g.:

   ```
   ✔ aitask workflow complete — t<id> <name>
     outcome: archived (commit <hash>) · pushed: yes|no
     follow-ups created: t…, t… (or none)
   ```

   Exact format is a planning decision, but it must be a stable, greppable
   first line so humans (and, if chosen below, the monitor) can recognize it.
2. **Matching "stopped" banner for every non-success exit**, carrying the
   outcome (in-flight / reverted to Ready / aborted / split into children),
   the reason, and the next action (`/aitask-pick <id>`, etc.). Prefer one
   shared procedure file (like `plan-approved-stop.md`'s
   `<closing_message>` contract) referenced from every exit site, so no
   branch can drop it by partial copy. Inventory every "end the workflow" site
   (`grep -n 'end the workflow\|END the workflow\|ends the workflow'` across
   `.claude/skills/task-workflow/*.md` and the calling skills).
3. **Make COMPLETED mean "the workflow reached its last step".** Planning
   chooses the mechanism and records why, e.g.:
   - a durable end-of-workflow marker written at the final step (note: the
     gate ledger lives *inside the task file*, which is already archived and
     committed by then, so this costs another commit to the archived file —
     or a different sidecar location), or
   - keep the archive signal but combine it with a pane-side signal (the
     banner line, via the existing prompt-pattern / screen-capture machinery).
     Screen evidence must stay advisory per project convention.

   Whatever is chosen, **keep the current Done/archived fallback** for agents
   that never reach the new step (older rendered skills, other code agents,
   crashed sessions) so those rows do not regress to "never completed".
4. **Do not break existing gate-recording consumers** if gate recording is
   added or changed: `aitask_gate.sh resume-point` / `workflow-phase`
   (`lib/gate_ledger.py`, `lib/workflow_phase.py`,
   `board/board_workflow_phase.py`, `monitor/review_loop.py`,
   `lib/trail_gather.py`), the archive gate guard (`archive-ready`, which keys on
   declared gates and must not start requiring the new marker), and the
   minimonitor/monitor gate-status reads. Any new record must not be a declared
   gate.
5. **Ports and regeneration.**
   - Apply the same ending to `aitask-pickrem` and `aitask-pickweb` (their own
     "Step 10: Archive and Push").
   - Regenerate goldens for every touched `.md.j2` / procedure and run
     `./.aitask-scripts/aitask_skill_verify.sh`.
   - Suggest follow-up aitasks to port the change to the Codex
     (`.agents/skills/`) and OpenCode (`.opencode/`) trees.

## Pointers

- `.claude/skills/task-workflow/SKILL.md` — Step 9 (~L831), Step 9b (~L1072)
- `.claude/skills/task-workflow/satisfaction-feedback.md` — feedback-disabled path
- `.claude/skills/task-workflow/plan-approved-stop.md` — `<closing_message>` precedent
- `.claude/skills/task-workflow/merge-broker.md` — in-flight exits
- `.aitask-scripts/monitor/monitor_shared.py` — `is_task_completed`, `_state_color`
- `.aitask-scripts/monitor/minimonitor_app.py` / `monitor_app.py` — `_compute_completed_panes`
- `.aitask-scripts/monitor/prompt_patterns.py`, `aidocs/framework/monitor_idle_and_prompt_detection.md` — if a screen-side signal is used
- `.aitask-scripts/aitask_gate.sh` (`resume-point`, `workflow-phase`), `.aitask-scripts/lib/gate_ledger.py`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-08T13:43:54Z status=pass attempt=1 type=human
