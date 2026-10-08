---
Task: t1913_task_workflow_explicit_completion_signal.md
Base branch: main
Output branch: main
---

# t1913 — Explicit "workflow complete" / "workflow stopped" banners

## Context

A task-workflow run never states that it is complete.

- **Success path:** it ends at Step 9b. Under `fast`, the last line shown is
  `Profile 'fast': feedback questions disabled`.
- **Other exits:** about 30 early or alternate exits each print an ad-hoc
  message or nothing at all.

Users, and Codex/OpenCode runs especially, get no reliable "the run is over"
signal. Outcome:

- A NON-SKIPPABLE final **Step 10** prints one fixed-format "complete" banner.
- Every non-success exit prints a matching "stopped" banner.
- Both banners are defined in **one shared procedure**, so no branch can drop
  them through a partial copy.

**Scope decision (user, at plan review):** the banners are **user-facing
messages only**.

- The monitor/minimonitor completion logic stays exactly as it is, including
  the COMPLETED timing at archival.
- There is no detection code, no end record, no new helper script and no
  monitor doc change.
- The task's Goal 3 (making the COMPLETED glyph wait for the workflow's last
  step) needs a separate design. Step 8 offers a follow-up task for it, carrying
  this session's findings:
  - idle is only "screen unchanged for 5 s";
  - screen text is unreliable as evidence;
  - a durable end record was rejected.
- Goal 4 is satisfied trivially: no gate or ledger change.

## Banner format

The banner is a fenced ```` ```text ```` block, so markdown rendering cannot
merge its lines into one paragraph:

```
✔ aitask workflow complete — t<id> <name>
  outcome: archived (commit <hash>) · pushed: yes|no
  follow-ups created: t…, t… | none
```
```
■ aitask workflow stopped — t<id> <name>
  outcome: <in-flight|ready|aborted|split|unchanged>
  reason: <one line>
  next: <re-pick command / action>
```

`outcome` takes one of five values:

| outcome | meaning |
|---|---|
| `in-flight` | the task stays `Implementing` |
| `ready` | reverted to Ready; the reason says whether the approved plan was kept |
| `aborted` | Task Abort, or the pickrem/pickweb Abort Procedure |
| `split` | decomposed into children |
| `unchanged` | nothing was claimed or changed by this run |

**Scope of the stopped banner**

In scope:

- Every exit after the task-workflow hand-off.
- **Every** pickrem/pickweb ending, including their pre-claim exits. Pre-claim
  exits get `unchanged` directly and never go through an Abort Procedure,
  because those procedures release locks and revert status, which must not
  touch another session's task.

Out of scope:

- Calling-skill exits before a task is handed off (explore, fold, review,
  pr-import and revert aborts or "Save for later"; resume usage errors). No task
  has been claimed, so these are not workflow runs.
- "Return to the calling skill's task selection", because the run continues.
- "Start first child" restarts, which hand off to a new run.
- aitask-qa's own Step 7.

## Implementation steps

### 1. New procedure `.claude/skills/task-workflow/workflow-end.md`

Plain `.md`, no Jinja. It is profile-invariant, never prompts, and is safe for
headless runs.

- **`## Complete`**
  - Inputs: `task_id`, `task_name`, `commit` (from `COMMITTED:`), `pushed`,
    `follow_ups` (task ids created in Steps 8b/8c/8d; a `PARENT_ARCHIVED` result
    is noted).
  - Displays the banner as the **last** output of the run.
- **`## Stopped`**
  - Inputs: `task_id`, `task_name`, `outcome`, `reason`, `next`.
  - Displayed after the exit's own message, never instead of it, and as the last
    output.
- **Rules**
  - **Outcome accuracy.** `unchanged` is reserved for a run that made no change:
    no claim, no status write and no plan saved or committed. Every other exit
    takes its outcome from the task's actual resulting state, not from the exit
    site's label:
    - re-read `status` when the site cannot know it statically;
    - name any retained plan or branch in `reason` / `next`.

    The procedure states this rule once, and each exit site follows it.
  - The first line is reproduced verbatim (no paraphrase, reflow or
    translation).
  - Exactly one banner per run.
  - pickweb has a documented alternate `## Complete` outcome text, because it
    never archives.
  - For a pickrem/pickweb pre-claim exit, use the requested `t<N>`.

### 2. `.claude/skills/task-workflow/SKILL.md`

- **New `### Step 10: Workflow End`** after Step 9b, with the same NON-SKIPPABLE
  banner as Steps 8 and 9.
  - If the task was archived → `## Complete`.
  - If the run came from the Step 9 "Defer — keep in-flight" branch →
    `## Stopped` with `in-flight`.
  - The Defer text and Step 9b both gain "then Step 10".
- **Per-branch wiring to `## Stopped`** (each exit individually):

  | Exit | Outcome |
  |---|---|
  | Step 3 Check 1 "No, skip" | `unchanged` |
  | Step 3 Check 2 "No, skip" | `unchanged` |
  | Step 3 Check 4 "No, keep it active" | `unchanged` |
  | Step 4 `LOCK_FAILED` → "Otherwise: abort" | `unchanged` |
  | Step 4 live-holder / unverifiable-holder force-claim → "Otherwise: abort" | `unchanged` |
  | Step 4 `LOCK_ERROR` → Abort | `unchanged` |
  | Step 4 `LOCK_INFRA_MISSING` | `unchanged` |
  | Step 4 unstructured script failure | `unchanged` |
  | Re-entry `UNSAFE_BRANCH` | `in-flight` |
  | Re-entry `UNSAFE_WORKTREE` | `in-flight` |
  | Step 6 child "Stop here" summary (after feedback) | `split` |
  | Step 7 ownership-guard bare aborts (`LOCK_INFRA_MISSING`, script failure, failed `--force`) | **derived from the resulting state** (see below) |
  | Step 7 risk-mitigation "before" stop | `ready`, plan kept |
  | Step 9 `UNSAFE_OUTPUT_BRANCH` | `in-flight` |

- **Step 7 guard failures: outcome derived from the resulting state.** This
  guard runs after Step 4 claimed the task and Step 6 saved and committed the
  plan, so the run is not untouched. The exit wiring instructs:
  - **Read the current state.** Read the task's `status` and `assigned_to`, and
    the lock holder from `aitask_lock.sh --check <id>`. Read-only; never change
    another session's ownership.
  - **Pick the outcome:**
    - `status: Implementing` → `in-flight`. If the lock or assignment belongs to
      someone else, the reason says "ownership not confirmed — held by
      \<owner\>@\<host\>".
    - `status: Ready` → `ready`.
  - **Name the kept plan.** `next:` names the retained plan
    (`aiplans/<plan_file>`, already committed), the lock-resolution action
    (`ait lock` / `aitask_lock_diag.sh`), and `/aitask-pick <id>`.
- **Procedures list:** add a `**Workflow End Banner Procedure**
  (\`workflow-end.md\`)` entry.

### 3. Shared exit procedures

Each change is made once and covers every caller of that procedure.

- **`plan-approved-stop.md`:** after "Display `<closing_message>`", show the
  stopped banner with `ready`. The reason depends on `stop_reason`:
  - `deferred` / `resource_admission` → "approved plan kept"
  - `drift` / `parallel_admission` → "re-plan required"
- **`task-abort.md`:** after the final "Inform user" line → `aborted`.
- **`merge-broker.md`:** add one rule under the closed-vocabulary table.
  `continues-to` `stop-in-flight` always ends with Stopped `in-flight`, shown
  after the verdict's own required wording. A `stop` row whose user answer ends
  the session ends the same way.
- **`merge-target-sync.md`:** "Stop here" → `in-flight`.
- **`manual-verification.md`:** "Abort" (paused, lock kept) and "Stop without
  archiving" → `in-flight`.
- **`planning.md`:** child checkpoint "Stop here" → `split` (after feedback).
- **`cross-repo-child-assignment.md`:** "Stop here" → `split` (after feedback).
- **`parallel-assessment.md`:** "Stop" (opt-in, pre-claim) → `unchanged`.

### 4. pickrem / pickweb (`SKILL.md.j2`)

Inventory **every** ending at implementation time and wire each branch
individually. Reference the procedure as `task-workflow/workflow-end.md`.

**pickrem**

- Step 10: `## Complete` replaces "Task t<id> completed and archived.".
- Step 9.5 human-gate pending → `in-flight`.
- Step 10 `GATE_PENDING` → `in-flight`.
- Abort Procedure → `aborted`.
- Done/orphan "skipping per profile" → `unchanged`.
- **Step 5 pre-claim exits**, each → `unchanged` directly, with no Abort
  Procedure:
  - `LOCK_FAILED` (both Jinja arms, including the failed force-claim)
  - `LOCK_LIVE_HOLDER`
  - `LOCK_UNVERIFIABLE_HOLDER`
  - `LOCK_ERROR`
  - `LOCK_INFRA_MISSING`
  - unstructured script failure
- Earlier task-known bare aborts → `unchanged`. Profile-resolution failures
  before any task number exists are out of scope; the procedure documents this.

**pickweb**

- Step 8 → `## Complete` with the alternate outcome
  `implemented on branch <b> · archive pending (run aitask-web-merge)`.
- Abort Procedure → `aborted`.
- Task-known pre-claim aborts → `unchanged`.

### 5. Regeneration

- **Goldens** to regenerate:
  - all three profiles: `SKILL`, `planning`, `plan-approved-stop`,
    `manual-verification`
  - `-default` only: `merge-broker`, `cross-repo-child-assignment`,
    `parallel-assessment`
  - `tests/golden/skills/aitask-pick{rem,web}/SKILL-remote-claude.md`

  `workflow-end.md`, `task-abort.md` and `merge-target-sync.md` have no Jinja,
  so they get no array entry and no golden.
- **Remote prerenders:** run `./.aitask-scripts/aitask_skill_rerender.sh remote`,
  then `git add` the new `workflow-end.md` in all three committed remote trees,
  together with the re-rendered pickrem/pickweb outputs. Then run
  `./.aitask-scripts/aitask_skill_verify.sh`.
- **Ports:** Codex and OpenCode render task-workflow and pickrem/pickweb from
  this same Claude source, and their stubs only dispatch, so nothing needs
  hand-porting. Step 8 states this instead of creating port tasks.

### Post-phase (risk mitigations)

- **exit_site_contract_test**: add `tests/test_workflow_end_banner_contract.sh`,
  a **per-branch** scanner (python heredoc) over `task-workflow/*.md` and the
  pickrem/pickweb `.j2`.
  - **Exit phrases matched:**
    - "end the workflow" / "ends the workflow" / "END the workflow"
    - "end this session"
    - `Abort.` / `**Abort.**` / `abort.` / "Otherwise: abort"
    - "then stop"
  - **Per-match rule:** the enclosing list item or paragraph must reference
    `workflow-end.md` with a valid outcome token. Otherwise the line must be on
    an explicit (file, substring) allowlist of descriptive or relayed mentions.
    An allowlist entry that matches nothing fails.
  - **Also checked:**
    - every `unchanged` reference in `task-workflow/SKILL.md` sits **before**
      the `### Step 6` heading. Steps 3–4 are pre-claim and pre-plan. The
      Re-entry UNSAFE stops are `in-flight`. The test asserts the count and the
      positions, so a post-claim site cannot be mislabelled `unchanged`;
    - both banner first-line keys are in `workflow-end.md`;
    - Step 10 and NON-SKIPPABLE are in the rendered fast/default/remote
      SKILL.md.
  - **Negative controls on temp copies:**
    - removing one branch's reference in a file that still has other references
      makes the check fail;
    - a stale allowlist entry makes the check fail.
  - Every check asserts a hit count.
- **render_drift_sweep**:
  - run all `tests/test_skill_render_*.sh`;
  - run `tests/test_task_workflow_reentry_drift.sh`,
    `tests/test_merge_broker_rendered_verdicts.sh`,
    `tests/test_plan_approved_marker_contract.sh` and
    `tests/test_workflow_phase_prompt_drift.sh`;
  - run `aitask_skill_verify.sh`;
  - `git status --porcelain -- .claude/skills .agents/skills .opencode/skills`
    must show no untracked rendered remote file.

## Verification

- `bash tests/test_workflow_end_banner_contract.sh`
- `bash tests/test_skill_render_task_workflow.sh`
- `bash tests/test_skill_render_aitask_pickrem.sh`
- `bash tests/test_skill_render_aitask_pickweb.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `shellcheck` on the new test script
- No Python or monitor code changes, so the Python suite is not affected.

Then Step 9 archives t1913, and this run ends with the new Step 10 banner.

## Risk

### Code-health risk: medium
- **Wide doc blast radius:** about 12 skill files, 7 golden families and 3
  committed remote prerender trees. A missed golden or an untracked rendered
  file breaks fresh clones or CI · severity: medium · → mitigation: inline
  post-phase render_drift_sweep
- Reassessed after inlining: still medium, because the blast radius is
  unchanged.

### Goal-achievement risk: medium
- **Goal 3 is deferred by user decision.** The COMPLETED glyph still fires at
  archival, which is the reported symptom · severity: medium · → mitigation:
  follow-up design task offered at Step 8 (not a risk-mitigation spawn; it is
  the deferred goal itself)
- An exit branch is missed, or a later edit drops its banner, so some outcome
  ends silently again · severity: medium · → mitigation: inline post-phase
  exit_site_contract_test
- Agents may paraphrase or reflow the banner · severity: low · → mitigation:
  t1924

### Planned mitigations
- timing: post-phase | name: exit_site_contract_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: missed or later-dropped exit-branch banner | desc: per-branch scanner pinning a workflow-end.md reference in every exit block, with self-checking allowlist and negative controls
- timing: post-phase | name: render_drift_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: missed golden or untracked rendered prerender | desc: run every skill-render test, aitask_skill_verify.sh and an untracked-file check over the 3 remote prerender trees
- timing: after | name: live_banner_render_check | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: banner paraphrased or reflowed in a live pane | desc: run a fast-profile pick in Claude Code (and one of Codex/OpenCode if available) and confirm the complete and one stopped banner render verbatim as the last output | created: t1924

## Post-Review Changes

### Change Request 1 (2026-10-08, plan review)
- **Requested by user:** three review rounds on the plan.
  - First, rejected the archived-and-idle COMPLETED fallback and screen-banner
    matching.
  - Then rejected a per-pane end-record design.
  - Then descoped all monitor/minimonitor detection: the banners are user-facing
    messages only, and the COMPLETED glyph keeps its current archival timing.
    Goal 3 needs a separate design.
  - Also required: pickrem Step 5 pre-claim exits get `unchanged` banners
    directly, never through the Abort Procedure; per-branch, not per-file, exit
    verification; and Step 7 ownership-guard failures derive their outcome from
    the task's actual state, never from Step 4's `unchanged`.
- **Changes made:** the plan was rewritten accordingly before approval.
- **Files affected:** plan only.

## Final Implementation Notes
- **Actual work done:**
  - New `.claude/skills/task-workflow/workflow-end.md`, the Workflow End Banner
    Procedure:
    - `## Complete` and `## Stopped` banners;
    - a closed `outcome` vocabulary (`in-flight`, `ready`, `aborted`, `split`,
      `unchanged`);
    - an outcome-accuracy rule;
    - the pickweb alternate Complete outcome.
  - `task-workflow/SKILL.md` gained a NON-SKIPPABLE Step 10, and Step 9b and the
    Step 9 Defer branch now hand off to it.
  - Every exit in Steps 3, 4, Re-entry Routing, 6, 7 and 9 is wired to the
    Stopped banner. Step 7's guard gets an explicit state-derived outcome block.
  - Shared exit procedures each wired once: plan-approved-stop, task-abort,
    merge-broker (one rule under the vocabulary table plus three inline
    stop-in-flight lines), merge-target-sync, manual-verification, planning,
    cross-repo-child-assignment, parallel-assessment and
    execution-profile-selection-auto.
  - pickrem and pickweb: every ending is wired. The Step 5 pre-claim refusals are
    marked `unchanged` directly.
  - Regenerated:
    - 14 procs goldens;
    - the pickrem and pickweb remote-claude goldens;
    - the remote prerenders in all 3 agent trees, including the new
      `workflow-end.md`.
  - New `tests/test_workflow_end_banner_contract.sh`: a per-branch scanner with a
    self-checking allowlist, a Guard 2 that keeps `unchanged` before Step 6, Step
    10 render checks for all 3 profiles, and negative controls.
- **Deviations from plan:**
  - `execution-profile-selection-auto.md` was also wired: its aborts run with a
    requested task id. The scanner found it.
  - Step 4's unstructured script failure re-reads status instead of assuming
    `unchanged`, because it can fail part-way.
  - The merge-broker `recovery` rows are included alongside `stop`.
  - The parallel-assessment golden did not change, because its Stop branch renders
    away under `default`.
- **Issues encountered:**
  - The scanner's block detection initially treated column-0 Jinja tag lines as
    block ends (false positive in pickrem Step 5). Jinja lines are now
    transparent, and multi-line `(description: "…` option labels are stripped.
  - The pickrem/pickweb render Test 6 compares against HEAD, so it fails until
    this commit lands (expected).
  - During review the user reported the minimonitor losing task titles and DONE
    glyphs for this tmux session. This is unrelated to t1913: one pane's cwd had
    moved to thinking_app, and pane-cwd discovery overrides
    `AITASKS_PROJECT_<session>`. Filed as t1922.
- **Key decisions:**
  - Banners are fenced `text` blocks with a verbatim first line.
  - No monitor, gate or ledger change, so Goal 4 holds trivially.
  - Codex and OpenCode render from this same Claude source, so no port tasks are
    needed.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_launch_utils.py:1289` — `_collect_live_roots` lets
    the first pane cwd that walks up to a project override the explicit
    `AITASKS_PROJECT_<session>`, so one wandering pane remaps the whole session.
    Filed as t1922.
  - `.claude/skills/aitask-pickrem/SKILL.md.j2:320` — any Step 8
    ownership-guard failure, including `LOCK_LIVE_HOLDER` /
    `LOCK_UNVERIFIABLE_HOLDER`, triggers the Abort Procedure. That procedure
    unlocks and reverts the task even when another live session holds it.
