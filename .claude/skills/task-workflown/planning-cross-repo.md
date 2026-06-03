# Cross-Repo Planning Procedure (design)

Designs a single coordinated change that spans **two** registered aitasks
projects (e.g. `aitasks` + `aitasks_mobile`). The work is split into **≥2
children** — one parent per repo, never a single parent whose children
straddle two repos — so each repo's hierarchy stays locally complete and
valid; only the cross-repo edges are external (`xdeps:` + `xdeprepo:`).

**This procedure only designs the plan — it creates nothing.** It runs during
the planning phase (`planning.md` §6.1), which executes in **plan mode
(read-only)**: trigger detection, confirmation, repo resolution, paired
exploration, and decomposition are all read-only. The actual creation of the
cross-repo parent and the children happens **after the plan is approved**, in
the companion **Cross-Repo Child Assignment Procedure** (see
`cross-repo-child-assignment.md`), dispatched from Step 7. This mirrors the
single-repo decomposition flow, where task creation happens after the plan is
approved — never inside plan mode.

## Input context (from `planning.md` §6.1)

| Variable | Description |
|----------|-------------|
| `current_task_id` | The task driving `/aitask-pickn` (becomes the **local** parent). |
| `task_file` | Path to the current task file. |
| `trigger_source` | The current task's body text (scanned for cross-repo notations in Step 4 only — never for trigger detection). |
| `is_child`, `parent_id`, `active_profile`, `base_branch` | Standard workflow context. |

## Return contract

Returns `cross_repo_planned: true` (with `cross_repo_name: <name>` and the
designed decomposition recorded in the plan), or `cross_repo_planned: false`
on no-trigger / user-decline. On `false`, the caller continues its normal
local-only flow.

---

**No task is created in this phase.** Every step here is read-only — it
resolves, explores, and designs. The output is a paired decomposition written
into the local parent's plan, which the user then approves through the
standard Save-Plan + Checkpoint gate before any creation happens.

### Step 1 — Trigger detection (metadata-only)

Read the `xdeprepo` scalar from the current task's frontmatter:

```bash
./.aitask-scripts/aitask_query_files.sh task-file <current_task_id>
```

Read the resolved file's `xdeprepo` field (directly, or via
`lib/task_utils.sh::read_xdeprepo <task_file>`).

- **The trigger fires iff `xdeprepo` is non-empty.** Set `<name>` to the
  `xdeprepo` value.
- Detection is **metadata-only.** Do NOT scan the task body, match project
  names, or apply the `<project>#<id>` notation regex for trigger detection —
  these are intentionally excluded so an incidental mention of a registered
  project name (or `aitasks#N_M` notation) in prose does not trip paired
  planning.

If `xdeprepo` is empty or absent: set `cross_repo_planned: false` and return
immediately.

### Step 2 — Confirmation (always fires)

`xdeprepo` records *intent* at creation time; the planning agent still
confirms before designing a paired plan. Use `AskUserQuestion`:

- Question: "Task frontmatter declares `xdeprepo: <name>`. Plan this as a
  paired cross-repo task? The design will split the work into ≥2 children
  spanning both repos; a counterpart parent in `<name>` and all children are
  created only after you approve the plan."
- Header: "Cross-repo"
- Options:
  - "Yes, plan paired (Recommended)" (description: "Design a paired decomposition; create the counterpart parent and children after approval")
  - "No, plan locally only" (description: "Ignore `xdeprepo` and plan as a normal single-repo task")

On "No, plan locally only": set `cross_repo_planned: false` and return. Leave
the `xdeprepo` metadata intact (it remains a record of intent).

`xdeprepo` is a scalar — exactly one cross-repo project per task — so no
disambiguation prompt is needed.

> This confirmation gates whether a paired plan is even designed. The actual
> creation gate is the standard plan-approval Checkpoint later — no execution
> profile bypasses either.

### Step 3 — Resolve both repos (read-only)

Resolve the cross-repo project to its root:

```bash
./.aitask-scripts/aitask_project_resolve.sh <name>
```

Parse the single output line:
- `RESOLVED:<root>` — record `<B-root>` = `<root>` for the exploration step.
- `STALE:<name>:<path>` — die: "Project `<name>` is registered but its path
  is stale (`<path>`). Run `cd <correct-path> && ait projects add` to fix."
- `NOT_FOUND:<name>` — die: "Project `<name>` is not registered. Run `cd
  /path/to/<name> && ait projects add`."

The local project is implicit (current working directory). For symmetric
cross-edges (B → A) to validate at creation time, the **local** project must
also be registered: obtain its registered name `<local_project_name>` from
`ait projects list` by matching the current repo root. If the local repo is
not registered, note in the plan that cross-repo children cannot carry
`xdeps:` back to the local repo until `ait projects add` is run here.

### Step 4 — Paired exploration (read-only)

Spawn **two `Explore` subagents in parallel** — one rooted in the local repo,
one rooted in `<B-root>` — each with a focused question distilled from
`trigger_source`. Keep both results in this conversation's context for the
design step.

**Cross-repo reference resolution.** Before spawning the subagents, scan
`trigger_source` for the two authoring notations documented in
`aidocs/framework/cross_repo_references.md` (consumed here, during exploration — never
during Step 1 trigger detection):

- `<project>#<id>` (e.g. `aitasks_mobile#42_3`) — resolve the referenced
  task's title/description so the cross-repo subagent's question can name the
  work instead of quoting a bare ID:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh --project <project> task-file <id>
  ```
- `<project>:<relative/path>` (e.g. `aitasks_mobile:Sources/Login.kt`) —
  resolve the cross-repo root via `aitask_project_resolve.sh <project>` →
  `RESOLVED:<root>`, then add `<root>/<relative/path>` to the cross-repo
  subagent's high-priority reading list.

### Step 5 — Design the decomposition (≥2 children, nominal assignment)

Design the change as a sequence of **at least two** children — usually more,
because cross-repo work evolves in parallel staged steps (e.g. add a field on
repo B → consume it on repo A → migrate older payloads on B → display on A).

Assign each planned child **nominally** to one of two parents:

- the **local parent** = `current_task_id` (this task — it already exists), or
- the **future cross-repo parent** — a counterpart parent in `<name>` that
  **does not exist yet** and will be created by the Cross-Repo Child
  Assignment Procedure after approval.

For each planned child record (no IDs are assigned yet):

- A stable **label** (e.g. `A1`, `B1`, `B2`) for symbolic dependency wiring.
- Owning side (`local` / `cross-repo`) and therefore its nominal parent.
- Title / brief description / labels / `issue_type`.
- **In-repo deps** — other planned children on the same side (by label).
- **Cross-repo deps** — planned children on the opposite side that must
  finish first (by label).

Because cross-repo task IDs are unknown until creation, deps are recorded
**symbolically by label** here and resolved to real IDs after approval.

### Step 6 — Record the design in the plan and return

Write the full paired decomposition into the **local parent's** plan file
(the plan the user is about to approve) as authoritative for both repos —
e.g. a table of `label | side | nominal parent | in-repo deps | cross-repo
deps | description`, plus the mirrored cross-repo parent title.

Return `cross_repo_planned: true` (with `cross_repo_name: <name>`). The caller
(`planning.md` §6.1) then:
- skips its own single-repo child creation / child-plan writing /
  manual-verification sibling / child-task checkpoint,
- sets `cross_repo_planned = true` in the workflow context,
- proceeds to **Save Plan to External File** + the **Checkpoint** (the
  standard plan-approval gate).

**Nothing has been created.** The Cross-Repo Child Assignment Procedure (see
`cross-repo-child-assignment.md`) runs only after the plan is approved, from
Step 7.
