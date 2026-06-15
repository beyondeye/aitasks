---
name: aitask-resume-fast
description: Resume an in-flight task from its gate-ledger checkpoint (programmatic re-entry surface for testing / TUI / board ops).
---

## Workflow

This is the **programmatic re-entry surface** for an in-flight task: given a
task id, it resolves the task and hands off to the shared `task-workflow`, whose
**Step 3 Check 5** and **Re-entry Routing** (the resume engine) decide where to
resume — plan from scratch, the implementation body, or post-implementation.

It does **not** re-derive resume logic and it does **not** run gate verifiers.
It is the seed of the future `aitask-run-gates` orchestrator: when that engine
lands, this skill becomes its conversational front, not a second engine.

Use `/aitask-pick <id>` for the normal user-facing flow (it also re-enters
in-flight tasks). Reach for `/aitask-resume` when you want a direct
"resume this specific task" entry without the pick funnel — initial re-entry
testing, TUI/board In-Flight launches, or any surface that already knows the id.

### Step 0: Parse arguments

Invocation: `/aitask-resume <task-id> [--gate <name>]`

- `<task-id>` (**required**) — a parent id (`16`) or a child id (`16_2`).
- `--gate <name>` (optional) — forward-compatible with the orchestrator
  invocation shape `aitask-run-gates <task-id> [--gate <name>]`. Capture the
  value; it is handled in Step 2.

If no `<task-id>` is given, display
`Usage: /aitask-resume <task-id> [--gate <name>]` and stop.

### Step 0b: Sync with Remote (best-effort)

Do a non-blocking sync so the local ledger/lock state is current before resuming
(an in-flight task may have advanced on another PC):

```bash
./.aitask-scripts/aitask_pick_own.sh --sync
```

If it fails (no network, merge conflicts), continue silently.

### Step 1: Resolve the task file + context

**If the id contains `_` → child task** (`<parent>_<child>`):

```bash
./.aitask-scripts/aitask_query_files.sh child-file <parent> <child>
```
Parse: `CHILD_FILE:<path>` → use that path; `NOT_FOUND` → display an error and
stop. Then gather sibling context:
```bash
./.aitask-scripts/aitask_query_files.sh sibling-context <parent>
```
Read the parent task file and the `ARCHIVED_PLAN:` files (primary reference for
completed siblings); `ARCHIVED_TASK:` are the fallback; `PENDING_SIBLING:` /
`PENDING_PLAN:` are pending sibling context. `NO_CONTEXT` → none.

**Otherwise → parent task** (plain number):

```bash
./.aitask-scripts/aitask_query_files.sh resolve <number>
```
Parse: `NOT_FOUND` → display an error and stop. `TASK_FILE:<path>` → use it.
If a `HAS_CHILDREN:<count>` line is present, this parent has children — resume is
**single-task scoped**, not a drill-down. List the children and stop with
guidance to re-invoke with a specific child id:
```bash
./.aitask-scripts/aitask_ls.sh -v --children <number> 99
```
Display: "t\<number\> has children — resume targets one task. Re-invoke with a
child id, e.g. `/aitask-resume <number>_<N>`." Then stop.

Read the resolved task file; capture its current `status` as `previous_status`.

### Step 2: Surface resume state (and handle `--gate`)

Derive and display where this task will resume:

```bash
./.aitask-scripts/aitask_gate.sh resume-point <task-id>
./.aitask-scripts/aitask_gate.sh status <task-id>
```

Show the recorded checkpoints and the derived target:
- `PLAN` → plan from scratch (today's `/aitask-pick` flow).
- `IMPLEMENT` → resume at the implementation body (`task-workflow` Step 7).
- `POSTIMPL` → resume at post-implementation (`task-workflow` Step 9).

**If `status` is not `Implementing` OR resume-point is `PLAN`:** display
"Task t\<id\> is not in-flight (resume-point PLAN) — resuming behaves like a
fresh `/aitask-pick`: it will plan from scratch." Continue anyway —
`task-workflow` handles this case identically; the user may still want to work
the task.

**`--gate <name>` (pre-orchestrator behavior):** the per-gate verifier engine is
the orchestrator (`aitask-run-gates`), which is not yet available, and this skill
must not fork a second engine. So, when `--gate <name>` is supplied:
- Report the named gate's current recorded state from the `status` output above.
- Note: "Automated per-gate verifier execution arrives with the orchestrator. For
  now `--gate` reports state only; to record a human-gate pass use
  `ait gate pass <task-id> <name>`."
- Do **not** run a verifier. The resume hand-off below proceeds regardless.

### Step 3: Hand off to the shared workflow

Set the following context variables, then read and follow
`.claude/skills/task-workflow/SKILL.md` starting from **Step 3: Task Status
Checks** — where **Check 5** detects the in-flight task and the **Re-entry
Routing** subsection resumes at the right step after ownership is (re)claimed:

- **task_file**: the resolved task file path (e.g., `aitasks/t16_implement_auth.md`
  or `aitasks/t10/t10_2_add_login.md`)
- **task_id**: the task identifier (e.g., `16` or `16_2`)
- **task_name**: the filename stem (e.g., `t16_implement_auth` or `t16_2_add_login`)
- **is_child**: `true` if a child id was given, `false` otherwise
- **parent_id**: the parent number if `is_child`, otherwise null
- **parent_task_file**: the parent task file path if `is_child`, otherwise null
- **active_profile**: `{ name: fast }` (baked in at render time)
- **active_profile_filename**: `fast.yaml`
- **previous_status**: the `status` read in Step 1 (for abort revert)
- **skill_name**: `"resume"`

---

## Notes

- This skill **shares** the re-entry engine landed with `task-workflow` Step 3
  Check 5 + Re-entry Routing (the 3-state `PLAN` / `IMPLEMENT` / `POSTIMPL`
  derivation from `aitask_gate.sh resume-point`). It never re-implements it.
- It is the seed of the framework's `aitask-run-gates` orchestrator: when that
  engine lands, `aitask-resume` becomes its conversational front. The `--gate`
  argument is accepted now for invocation-contract compatibility.
- For the full Execution Profiles schema and shared workflow notes, see
  `.claude/skills/task-workflow/SKILL.md`.
